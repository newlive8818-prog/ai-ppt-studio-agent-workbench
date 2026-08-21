import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { invokePythonBridge } from "./runtime-bridge/python-runtime.mjs";
import { readProjectAsset } from "./project-asset.mjs";
import { createReviewBridge } from "./review-bridge.mjs";
import {
  createHostConfirmationAuthority,
  HOST_CONFIRMATION_SECRET_ENV,
} from "./host-confirmation-assertion.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(
  readFileSync(path.join(ROOT, ".codex-plugin", "plugin.json"), "utf8"),
);
const BROWSER_REVIEW_HTML = path.join(ROOT, "widget", "dist", "index.html");

const projectSchema = {
  projectRoot: z.string().trim().optional(),
};

function requestForProject(operation, input) {
  const request = { operation };
  if (input?.projectRoot) request.project_root = input.projectRoot;
  return request;
}

function projectAssetPath(assetRef) {
  const value = String(assetRef || "").trim();
  const prefix = "project-asset://";
  return value.startsWith(prefix) ? value.slice(prefix.length) : value;
}

function textResult(message, structuredContent) {
  return {
    content: [{ type: "text", text: message }],
    structuredContent,
  };
}

function toolErrorResult(error) {
  const code = typeof error?.code === "string" ? error.code : "INTERNAL_ERROR";
  const message =
    typeof error?.message === "string" && error.message.trim()
      ? error.message.trim()
      : "AI PPT Studio 暂时无法完成该操作。";
  const details =
    error?.details && typeof error.details === "object" ? error.details : {};
  return {
    isError: true,
    content: [{ type: "text", text: message }],
    structuredContent: { ok: false, error: { code, message, details } },
  };
}

function nativeMissionConfirmationMessage(input) {
  const summary = input.missionSummary || {};
  const fields = [
    ["汇报主题", summary.topic],
    ["汇报对象", summary.primaryAudience],
    ["期望判断或行动", summary.desiredJudgmentOrAction],
    ["材料状态", summary.materialSummary],
  ];
  const missing = fields
    .filter(([, value]) => typeof value !== "string" || !value.trim())
    .map(([label]) => label);
  if (missing.length) {
    return {
      ok: false,
      error: {
        code: "MISSION_NOT_CONFIRMED",
        message: `宿主确认前必须展示完整当前任务卡；缺少：${missing.join("、")}。`,
        details: { missingFields: missing },
      },
    };
  }
  const proposalNotice =
    input.materialMode === "no-materials-confirmed"
      ? "\n内容身份：当前无材料，将以方案建议模式继续；客户现状仅作诊断假设，能力与结果均待联合验证。"
      : "\n内容身份：仅依据当前已登记材料进入 material-backed 内容链。";
  return {
    ok: true,
    message: [
      "请确认当前 AI PPT Studio 任务卡：",
      ...fields.map(([label, value]) => `${label}：${value.trim()}`),
    ].join("\n") + proposalNotice,
  };
}

async function requestHostMissionConfirmation(server, input) {
  if (!server.server.getClientCapabilities()?.elicitation) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message:
          "当前宿主未提供原生确认能力；任务卡和材料状态已保留，可在能力可用后重试。",
        details: {},
      },
    };
  }
  const prompt = nativeMissionConfirmationMessage(input);
  if (!prompt.ok) return prompt;
  let result;
  try {
    result = await server.server.elicitInput({
      mode: "form",
      message: prompt.message,
      requestedSchema: {
        type: "object",
        properties: {
          confirmed: {
            type: "boolean",
            title: "确认当前任务卡并继续",
            description:
              "只有勾选确认并提交，AI PPT Studio 才会生成 MissionConfirmation。",
            default: false,
          },
        },
        required: ["confirmed"],
      },
    });
  } catch (_error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message:
          "宿主原生确认暂时不可用；任务卡和材料状态已保留，可重试确认。",
        details: {},
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_DECLINED",
        message: "任务确认已取消；项目状态未改变，可修改任务卡或再次确认。",
        details: { action: result.action },
      },
    };
  }
  return {
    ok: true,
    userActionRef: `host-elicitation://${randomUUID()}`,
  };
}

function nativeGateConfirmationMessage(context) {
  const gate = context?.gate || "";
  const summary = context?.review_summary || "";
  const sourceVersion = context?.source_version || "";
  if (!gate || !summary || !sourceVersion) {
    return {
      ok: false,
      error: {
        code: "GATE_NOT_CONFIRMED",
        message: "当前用户检查点缺少可验证的审阅版本或摘要。",
        details: {},
      },
    };
  }
  return {
    ok: true,
    message: [
      `请确认当前 AI PPT Studio ${gate} 用户检查点：`,
      summary,
      `当前审阅源：${sourceVersion}`,
      "本次确认只适用于此检查点和当前版本，不能用于其他任务或 Gate。",
    ].join("\n"),
  };
}

async function requestHostGateConfirmation(server, context) {
  if (!server.server.getClientCapabilities()?.elicitation) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message:
          "当前宿主未提供原生确认能力；当前审阅版本和 Gate 状态已保留，可在能力可用后重试。",
        details: { gate: context?.gate || "" },
      },
    };
  }
  const prompt = nativeGateConfirmationMessage(context);
  if (!prompt.ok) return prompt;
  let result;
  try {
    result = await server.server.elicitInput({
      mode: "form",
      message: prompt.message,
      requestedSchema: {
        type: "object",
        properties: {
          confirmed: {
            type: "boolean",
            title: `确认当前 ${context.gate} 并继续`,
            description:
              "只有确认当前展示的审阅版本，AI PPT Studio 才会放行此 Gate。",
            default: false,
          },
        },
        required: ["confirmed"],
      },
    });
  } catch (_error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message:
          "宿主原生 Gate 确认暂时不可用；项目状态未改变，可重试确认。",
        details: { gate: context.gate },
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_DECLINED",
        message: `${context.gate} 确认已取消；项目状态未改变。`,
        details: { gate: context.gate, action: result.action },
      },
    };
  }
  return {
    ok: true,
    userActionRef: `host-elicitation://${randomUUID()}`,
    userMessageRef: "",
  };
}

async function invokeForTool(invokeBridge, request) {
  try {
    return { ok: true, payload: await invokeBridge(request) };
  } catch (error) {
    return { ok: false, result: toolErrorResult(error) };
  }
}

export function createAiPptMcpServer(options = {}) {
  const confirmationAuthority =
    options.confirmationAuthority || createHostConfirmationAuthority();
  const invokeBridge =
    options.invokeBridge ||
    ((request) =>
      invokePythonBridge(request, {
        env: {
          ...process.env,
          [HOST_CONFIRMATION_SECRET_ENV]: confirmationAuthority.secret,
        },
      }));
  const readProjectAssetFn = options.readProjectAsset || readProjectAsset;
  const hostSidebarAdapter = options.hostSidebarAdapter || null;
  const browserSurfaceAdapter = options.browserSurfaceAdapter || null;
  const reviewBridgeFactory = options.reviewBridgeFactory || createReviewBridge;
  const confirmationVerifier = options.confirmationVerifier || null;
  const server = new McpServer(
    { name: manifest.name, version: manifest.version },
    {
      instructions:
        "Use the revision-safe data tools for the managed AI PPT project. Chat is a text collaboration and delivery channel and must never render the workbench or professional review as an MCP App. A real Codex sidebar host adapter is required for the compact workbench. Browser review uses a dedicated loopback bridge: when open_ai_ppt_browser_review returns status=review-session-ready, immediately open its scoped URL with the Codex in-app Browser and do not claim it is open before that succeeds. The managed project directory is the business truth source; never edit state JSON directly. Codex Presentations is the only PPTX route.",
    },
  );

  async function obtainScopedConfirmation(context, input, actionLabel) {
    const userMessageRef = String(input.userMessageRef || "").trim();
    let identityType = "host-action";
    let identityRef = "";
    if (userMessageRef) {
      if (!confirmationVerifier) {
        return {
          ok: false,
          error: {
            code: "HOST_CONFIRMATION_UNAVAILABLE",
            message: "当前宿主不能验证消息确认身份；状态未改变。",
            details: { scope_kind: context.scope_kind },
          },
        };
      }
      const verified = await confirmationVerifier.verify({
        projectRoot: input.projectRoot || "",
        scopeKind: context.scope_kind,
        scopeId: context.scope_id,
        sourceVersion: context.source_version,
        userMessageRef,
      });
      if (!verified) {
        return {
          ok: false,
          error: {
            code: "HOST_CONFIRMATION_DECLINED",
            message: "消息确认身份未通过宿主验证；状态未改变。",
            details: { scope_kind: context.scope_kind },
          },
        };
      }
      identityType = "verified-message";
      identityRef = userMessageRef;
    } else {
      if (!server.server.getClientCapabilities()?.elicitation) {
        return {
          ok: false,
          error: {
            code: "HOST_CONFIRMATION_UNAVAILABLE",
            message: "当前宿主未提供原生确认能力；状态未改变，可稍后重试。",
            details: {
              scope_kind: context.scope_kind,
              scope_id: context.scope_id,
            },
          },
        };
      }
      let result;
      try {
        result = await server.server.elicitInput({
          mode: "form",
          message: [
            actionLabel || "请确认当前操作",
            `操作范围：${context.scope_kind}`,
            `当前来源：${context.source_version}`,
            "本次确认只绑定当前版本、证据与 revision，不能复用于其他操作。",
          ].join("\n"),
          requestedSchema: {
            type: "object",
            properties: {
              confirmed: {
                type: "boolean",
                title: "确认当前操作",
                default: false,
              },
            },
            required: ["confirmed"],
          },
        });
      } catch (_error) {
        return {
          ok: false,
          error: {
            code: "HOST_CONFIRMATION_UNAVAILABLE",
            message: "宿主原生确认暂时不可用；状态未改变。",
            details: {},
          },
        };
      }
      if (result.action !== "accept" || result.content?.confirmed !== true) {
        return {
          ok: false,
          error: {
            code: "HOST_CONFIRMATION_DECLINED",
            message: "当前操作已取消；项目状态未改变。",
            details: { action: result.action },
          },
        };
      }
      identityRef = `host-elicitation://${randomUUID()}`;
    }
    try {
      return {
        ok: true,
        hostConfirmationAssertion: confirmationAuthority.issue(context, {
          identityType,
          identityRef,
        }),
      };
    } catch (error) {
      return {
        ok: false,
        error: {
          code: "HOST_CONFIRMATION_UNAVAILABLE",
          message:
            error instanceof Error
              ? error.message
              : "宿主无法签发当前操作的确认断言。",
          details: {},
        },
      };
    }
  }

  async function invokeScopedContentWrite({
    input,
    contextOperation,
    contextFields = {},
    writeOperation,
    writeFields = {},
    actionLabel,
  }) {
    const contextOutcome = await invokeForTool(invokeBridge, {
      ...requestForProject(contextOperation, input),
      ...contextFields,
    });
    if (!contextOutcome.ok) return contextOutcome;
    const context = contextOutcome.payload.context;
    const confirmation = await obtainScopedConfirmation(
      context,
      input,
      actionLabel,
    );
    if (!confirmation.ok) {
      return { ok: false, result: toolErrorResult(confirmation.error) };
    }
    return invokeForTool(invokeBridge, {
      ...requestForProject(writeOperation, input),
      expected_revision: input.expectedRevision,
      challenge_id: context.challenge_id,
      challenge_revision: context.challenge_revision,
      host_confirmation_assertion: confirmation.hostConfirmationAssertion,
      ...writeFields,
    });
  }

  async function startScopedReviewSession({
    projectRoot,
    reviewType,
    sourceVersion,
    expectedRevision,
    evidenceScope,
    evidenceAsset,
  }) {
    const bridge = reviewBridgeFactory({
      projectRoot,
      reviewType,
      sourceVersion,
      expectedRevision,
      evidenceScope,
      evidenceAsset,
      invokeBridge,
      readReviewHtml: () => readFile(BROWSER_REVIEW_HTML, "utf8"),
      createReviewSession: createAuthoritativeReviewSession,
    });
    const session = await bridge.start();
    return { bridge, session };
  }

  async function createAuthoritativeReviewSession({ projectRoot, reviewType }) {
    if (reviewType !== "visual") {
      const error = new Error(
        "Content review is not a professional Browser target",
      );
      error.code = "INVALID_REVIEW_SWITCH";
      throw error;
    }
    const payload = await invokeBridge({
      operation: "get-review-projection",
      project_root: projectRoot,
      review_type: reviewType,
    });
    const targetSourceVersion = payload?.review?.source_version;
    const targetRevision = payload?.snapshot_revision;
    if (!targetSourceVersion || !Number.isInteger(targetRevision)) {
      const error = new Error("Target review projection is unavailable");
      error.code = "REVIEW_SOURCE_UNAVAILABLE";
      throw error;
    }
    const targetProjectRoot = payload.selected_project_root || projectRoot;
    const { session } = await startScopedReviewSession({
      projectRoot: targetProjectRoot,
      reviewType,
      sourceVersion: targetSourceVersion,
      expectedRevision: targetRevision,
    });
    return session;
  }

  server.registerTool(
    "create_ai_ppt_project",
    {
      title: "Create AI PPT Project",
      description:
        "Create one managed schema 3 reading-first presales project. Project files are written only below the configured AI-PPT-Workspace runtime root.",
      inputSchema: {
        name: z.string().trim().min(1),
        projectId: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        operation: "create-project",
        name: input.name,
        project_id: input.projectId || "",
      });
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      return textResult(
        `已创建 schema 3 项目“${payload.snapshot.project.name}”，revision ${payload.snapshot.revision}。`,
        { snapshot: payload.snapshot },
        { snapshot: payload.snapshot },
      );
    },
  );

  server.registerTool(
    "get_ai_ppt_project_snapshot",
    {
      title: "Get AI PPT Project Snapshot",
      description:
        "Read the latest compact project cognition, gate, artifact, and decision projection. Omit projectRoot to use the most recently created managed project.",
      inputSchema: projectSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-snapshot", input),
      );
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      const snapshot = payload.snapshot;
      return textResult(
        `已读取 AI PPT 项目“${snapshot.project.name}”，revision ${snapshot.revision}。`,
        { snapshot },
        { snapshot },
      );
    },
  );

  server.registerTool(
    "get_ai_ppt_sidebar_projection",
    {
      title: "Get AI PPT Sidebar Projection",
      description:
        "Read the compact five-space projection for a real Codex sidebar host. This is a pure data tool and never attaches a chat UI template.",
      inputSchema: {
        ...projectSchema,
        initialSpace: z
          .enum(["overview", "materials", "blueprint", "visual", "delivery"])
          .optional(),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-snapshot", input),
      );
      if (!outcome.ok) return outcome.result;
      const projection = {
        project: outcome.payload.snapshot.project,
        revision: outcome.payload.snapshot.revision,
        initialSpace: input.initialSpace || "overview",
        workspace: outcome.payload.snapshot.workspace,
        missionDraftRef: outcome.payload.snapshot.missionDraftRef || "",
        missionConfirmationRef:
          outcome.payload.snapshot.missionConfirmationRef || "",
        materialMode: outcome.payload.snapshot.materialMode || "unconfirmed",
        contentIdentityMode:
          outcome.payload.snapshot.contentIdentityMode || "blocked",
      };
      if (!hostSidebarAdapter) {
        return toolErrorResult({
          code: "HOST_SIDEBAR_UNAVAILABLE",
          message:
            "当前 Codex 宿主未提供可验证的持久侧边栏入口；聊天不会渲染替代 Widget。",
          details: { projection },
        });
      }
      return textResult(
        `已读取“${projection.project.name}”的侧边栏投影，revision ${projection.revision}。`,
        { projection },
      );
    },
  );

  server.registerTool(
    "open_ai_ppt_browser_review",
    {
      title: "Open AI PPT Browser Review",
      description:
        "Prepare the fixed G3 visual review through a short-lived loopback Review Bridge. Content review stays in the sidebar; a directly connected host adapter may open the session, otherwise the Agent opens its scoped URL with the Codex in-app Browser.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        reviewType: z.literal("visual"),
        sourceVersion: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const projection = await invokeForTool(invokeBridge, {
        ...requestForProject("get-review-projection", input),
        review_type: input.reviewType,
      });
      if (!projection.ok) return projection.result;
      const payload = projection.payload;
      if (payload.review?.source_version !== input.sourceVersion) {
        return toolErrorResult({
          code: "REVIEW_SOURCE_STALE",
          message: "请求的专业审阅版本已经变化，请刷新后重试。",
          details: {
            expected_source: input.sourceVersion,
            actual_source: payload.review?.source_version || "",
          },
        });
      }
      let bridge;
      let session;
      try {
        ({ bridge, session } = await startScopedReviewSession({
          projectRoot: payload.selected_project_root || input.projectRoot,
          reviewType: input.reviewType,
          sourceVersion: input.sourceVersion,
          expectedRevision: payload.snapshot_revision,
        }));
      } catch (error) {
        if (bridge) await bridge.stop();
        return toolErrorResult({
          code:
            typeof error?.code === "string"
              ? error.code
              : "BROWSER_REVIEW_SAVE_UNAVAILABLE",
          message:
            error instanceof Error && error.message
              ? error.message
              : "专业审阅的读取与保存会话暂时无法建立。",
          details: {
            reviewType: input.reviewType,
            sourceVersion: input.sourceVersion,
          },
        });
      }

      let opened = false;
      if (browserSurfaceAdapter?.canOpen) {
        try {
          opened = Boolean((await browserSurfaceAdapter.openUrl(session.url))?.opened);
        } catch (_error) {
          opened = false;
        }
      }

      const common = {
        projectRoot: payload.selected_project_root || input.projectRoot,
        reviewType: input.reviewType,
        sourceVersion: input.sourceVersion,
        revision: payload.snapshot_revision,
        expiresAt: session.expiresAt,
      };
      if (!opened) {
        return textResult(
          `“${payload.review.project_name}”的专业审阅会话已准备；请立即使用 Codex 内置 Browser 打开返回的短时地址。`,
          {
            status: "review-session-ready",
            opened: false,
            openMode: "agent-browser",
            browserAction: "open-scoped-url",
            url: session.url,
            ...common,
          },
        );
      }
      return textResult(
        `已在 Codex 内置 Browser 打开“${payload.review.project_name}”的专业审阅。`,
        {
          status: "opened",
          opened: true,
          openMode: "host-adapter",
          ...common,
        },
      );
    },
  );

  server.registerTool(
    "open_content_evidence_browser",
    {
      title: "Open Content Evidence Browser",
      description:
        "Prepare one exact read-only content evidence scope in the Codex built-in Browser. Page decisions remain in the maximum-width sidebar.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        sourceVersion: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        evidenceId: z.string().trim().min(1),
        materialRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const projection = await invokeForTool(invokeBridge, {
        ...requestForProject("get-content-sidebar-review-projection", input),
      });
      if (!projection.ok) return projection.result;
      const payload = projection.payload;
      if (payload.review?.source_version !== input.sourceVersion) {
        return toolErrorResult({
          code: "REVIEW_SOURCE_STALE",
          message: "请求的内容证据版本已经变化，请刷新内容审核后重试。",
          details: {
            expected_source: input.sourceVersion,
            actual_source: payload.review?.source_version || "",
          },
        });
      }
      const slides = Array.isArray(payload.review?.slides)
        ? payload.review.slides
        : [];
      const slide = slides.find(
        (item) => String(item?.slide_id || "") === input.slideId,
      );
      const evidenceItems = Array.isArray(slide?.evidence_items)
        ? slide.evidence_items
        : [];
      const evidence = evidenceItems.find(
        (item) =>
          String(item?.evidence_id || "") === input.evidenceId &&
          String(item?.material_ref || "") === input.materialRef,
      );
      if (!slide || !evidence || !String(evidence.asset_ref || "").trim()) {
        return toolErrorResult({
          code: "CONTENT_EVIDENCE_SCOPE_INVALID",
          message: "请求的页面与材料证据不再匹配，请刷新内容审核后重试。",
          details: {
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
          },
        });
      }
      const selectedProjectRoot =
        payload.selected_project_root || input.projectRoot;
      let evidenceAsset;
      try {
        evidenceAsset = readProjectAssetFn({
          projectRoot: selectedProjectRoot,
          assetRef: projectAssetPath(evidence.asset_ref),
        });
      } catch (error) {
        return toolErrorResult({
          code: "SOURCE_UNREADABLE",
          message:
            error instanceof Error ? error.message : "项目证据无法读取。",
          details: { assetRef: evidence.asset_ref },
        });
      }
      let bridge;
      let session;
      try {
        ({ bridge, session } = await startScopedReviewSession({
          projectRoot: selectedProjectRoot,
          reviewType: "content-evidence",
          sourceVersion: input.sourceVersion,
          expectedRevision: payload.snapshot_revision,
          evidenceScope: {
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
            assetRef: evidence.asset_ref,
          },
          evidenceAsset,
        }));
      } catch (error) {
        if (bridge) await bridge.stop();
        return toolErrorResult({
          code:
            typeof error?.code === "string"
              ? error.code
              : "BROWSER_REVIEW_UNAVAILABLE",
          message:
            error instanceof Error && error.message
              ? error.message
              : "内容证据会话暂时无法建立。",
          details: {},
        });
      }
      let opened = false;
      if (browserSurfaceAdapter?.canOpen) {
        try {
          opened = Boolean(
            (await browserSurfaceAdapter.openUrl(session.url))?.opened,
          );
        } catch (_error) {
          opened = false;
        }
      }
      const common = {
        reviewType: "content-evidence",
        sourceVersion: input.sourceVersion,
        revision: payload.snapshot_revision,
        expiresAt: session.expiresAt,
        slideId: input.slideId,
        evidenceId: input.evidenceId,
        materialRef: input.materialRef,
      };
      if (!opened) {
        return textResult(
          "只读内容证据会话已准备；请立即使用 Codex 内置 Browser 打开返回的短时地址。",
          {
            status: "review-session-ready",
            opened: false,
            openMode: "agent-browser",
            browserAction: "open-scoped-url",
            url: session.url,
            ...common,
          },
        );
      }
      return textResult("已在 Codex 内置 Browser 打开只读内容证据。", {
        status: "opened",
        opened: true,
        openMode: "host-adapter",
        ...common,
      });
    },
  );

  server.registerTool(
    "get_content_sidebar_review_projection",
    {
      title: "Get Content Sidebar Review Projection",
      description:
        "Read the authoritative production-progress or complete full-deck sidebar projection without starting a model turn.",
      inputSchema: projectSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-content-sidebar-review-projection", input),
      );
      if (!outcome.ok) return outcome.result;
      return textResult(
        `已读取内容侧边栏投影，revision ${outcome.payload.snapshot_revision}。`,
        outcome.payload.review,
      );
    },
  );

  server.registerTool(
    "save_content_page_decision",
    {
      title: "Save Content Page Decision",
      description:
        "Silently save one page decision and comment. This never starts Codex processing or changes content/Gate state.",
      inputSchema: {
        projectRoot: z.string().trim().optional(),
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        decision: z.enum([
          "approved",
          "modify",
          "evidence",
          "merge-or-delete",
        ]),
        comment: z.string().max(1200),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("save-content-page-decision", input),
        expected_revision: input.expectedRevision,
        source_version: input.sourceVersion,
        review_batch_id: input.reviewBatchId,
        slide_id: input.slideId,
        decision: input.decision,
        comment: input.comment,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "本页判断已保存；尚未触发集中处理。",
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "submit_content_review_batch",
    {
      title: "Submit Complete Content Review Batch",
      description:
        "Freeze and submit all page decisions, then return one follow-up instruction for Codex to prepare a whole-deck revision plan.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        userMessageRef: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-review-batch-submission-context",
        contextFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        writeOperation: "submit-content-review-batch",
        writeFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        actionLabel: "提交整套逐页内容审核判断",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套审核判断已冻结并提交。", outcome.payload.result);
    },
  );

  server.registerTool(
    "withdraw_content_review_batch",
    {
      title: "Withdraw Submitted Content Review Batch",
      description:
        "Withdraw an exact submitted pre-plan batch, preserve history, and create a new editable draft batch without starting Codex processing.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        reason: z.string().trim().min(1),
        userMessageRef: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-review-batch-withdrawal-context",
        contextFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        writeOperation: "withdraw-content-review-batch",
        writeFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
          reason: input.reason,
        },
        actionLabel: "撤回已提交的整套审核批次",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "批次已撤回并创建新的可编辑审核批次。",
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "save_content_batch_revision_plan",
    {
      title: "Save Whole-Deck Content Revision Plan",
      description:
        "Save Codex's whole-deck revision plan for the exact frozen review batch without applying it.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        revisionPlan: z.record(z.string(), z.unknown()),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("save-content-batch-revision-plan", input),
        expected_revision: input.expectedRevision,
        payload: input.revisionPlan,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "整套修改方案已保存，等待用户确认。",
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "confirm_content_batch_revision_plan",
    {
      title: "Confirm Whole-Deck Content Revision Plan",
      description:
        "Confirm one exact whole-deck revision plan before governance or content changes can be created.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        reviewBatchId: z.string().trim().min(1),
        planRef: z.string().trim().min(1),
        userMessageRef: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-batch-plan-confirmation-context",
        contextFields: {
          review_batch_id: input.reviewBatchId,
          plan_ref: input.planRef,
        },
        writeOperation: "confirm-content-batch-revision-plan",
        writeFields: {
          review_batch_id: input.reviewBatchId,
          plan_ref: input.planRef,
        },
        actionLabel: "确认整套内容修改方案",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套修改方案已确认。", outcome.payload.result);
    },
  );

  server.registerTool(
    "create_content_batch_change_set",
    {
      title: "Create Governed Content Batch Change Set",
      description:
        "Create governance and a ContentChangeSet only from the exact confirmed whole-deck plan.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        planConfirmationRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("create-content-batch-change-set", input),
        expected_revision: input.expectedRevision,
        plan_confirmation_ref: input.planConfirmationRef,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "已按确认方案创建治理记录与修改集。",
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "save_ai_ppt_mission_draft",
    {
      title: "Save AI PPT Mission Draft",
      description:
        "Save an AI-authored MissionDraft. Complete required fields become confirmable but this tool never confirms the mission.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        missionDraft: z.record(z.string(), z.unknown()),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("save-mission-draft", input),
        expected_revision: input.expectedRevision,
        payload: input.missionDraft,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `任务草稿已保存，项目进入 revision ${outcome.payload.result.snapshot.revision}；尚未生成用户确认。`,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "confirm_ai_ppt_mission",
    {
      title: "Confirm AI PPT Mission",
      description:
        "Create one immutable MissionConfirmation bound to the current draft, material identity, revision, and a real user action or host message reference.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        missionDraftRef: z.string().trim().min(1),
        materialMode: z.enum([
          "materials-provided",
          "no-materials-confirmed",
        ]),
        materialInventoryRef: z.string().trim().optional(),
        userActionRef: z.string().trim().optional(),
        userMessageRef: z.string().trim().optional(),
        missionSummary: z
          .object({
            topic: z.string().trim().min(1),
            primaryAudience: z.string().trim().min(1),
            desiredJudgmentOrAction: z.string().trim().min(1),
            materialSummary: z.string().trim().min(1),
          })
          .optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      let userActionRef = input.userActionRef || "";
      const userMessageRef = input.userMessageRef || "";
      if (userActionRef || userMessageRef) {
        if (!confirmationVerifier) {
          const native = await requestHostMissionConfirmation(server, input);
          if (!native.ok) return toolErrorResult(native.error);
          userActionRef = native.userActionRef;
        } else {
          const verified = await confirmationVerifier.verify({
            projectRoot: input.projectRoot || "",
            missionDraftRef: input.missionDraftRef,
            materialMode: input.materialMode,
            userActionRef,
            userMessageRef,
          });
          if (!verified) {
            return toolErrorResult({
              code: "MISSION_NOT_CONFIRMED",
              message: "用户确认凭据未通过宿主验证。",
              details: {},
            });
          }
        }
      } else {
        const native = await requestHostMissionConfirmation(server, input);
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("confirm-mission", input),
        expected_revision: input.expectedRevision,
        mission_draft_ref: input.missionDraftRef,
        material_mode: input.materialMode,
        material_inventory_ref: input.materialInventoryRef || "",
        user_action_ref: userActionRef,
        user_message_ref: confirmationVerifier ? userMessageRef : "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `任务已由用户显式确认，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "submit_ai_ppt_human_decision",
    {
      title: "Submit AI PPT Human Decision",
      description:
        "Persist one explicit human choice or feedback against the current project revision. Returns a follow-up message for Codex and a refreshed project projection.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        targetRef: z.string().trim().min(1),
        choice: z.string().trim().min(1),
        feedback: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const request = {
        ...requestForProject("submit-human-decision", input),
        expected_revision: input.expectedRevision,
        target_ref: input.targetRef,
        choice: input.choice,
        feedback: input.feedback || "",
      };
      const outcome = await invokeForTool(invokeBridge, request);
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      return textResult(
        `已保存用户判断，项目进入 revision ${payload.result.snapshot.revision}。`,
        payload.result,
        payload.result,
      );
    },
  );

  server.registerTool(
    "add_ai_ppt_material",
    {
      title: "Add AI PPT Material",
      description:
        "Persist one user-provided text, URL, or bounded base64 file into the managed project. This never searches or fetches external customer material.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        materialType: z.enum(["text", "url", "bytes"]),
        value: z.string().optional(),
        dataBase64: z.string().optional(),
        label: z.string().optional(),
        filename: z.string().optional(),
        mimeType: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const request = {
        ...requestForProject("add-material", input),
        expected_revision: input.expectedRevision,
        material_type: input.materialType,
        value: input.value || "",
        data_base64: input.dataBase64 || "",
        label: input.label || "",
        filename: input.filename || "",
        mime_type: input.mimeType || "",
      };
      const outcome = await invokeForTool(invokeBridge, request);
      if (!outcome.ok) return outcome.result;
      return textResult(
        `材料已写入项目，revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "request_ai_ppt_agent_action",
    {
      title: "Request AI PPT Agent Action",
      description:
        "Persist a governed AI task and bounded context pack before Codex uses reasoning, Image 2, or Presentations.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        actionType: z.enum([
          "build-presales-strategy",
          "build-claim-evidence-map",
          "build-deck-argument-map",
          "build-slide-draft-set",
          "repair-content",
          "review-content-presales",
          "review-content-decision-maker",
          "review-content-evidence",
          "review-content-narrative",
          "review-content-editorial",
          "aggregate-content-reviews",
          "design-deck-system",
          "design-slide-visuals",
          "build-native-first",
          "generate-image-assets",
          "review-visual-aesthetic",
          "review-visual-engineering",
          "verify-target-render",
          "govern-feedback",
          "curate-experience",
          "evaluate-experience",
          "coordinate-delivery",
        ]),
        targetRefs: z.array(z.string().trim().min(1)).min(1),
        instructions: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("request-agent-action", input),
        expected_revision: input.expectedRevision,
        action_type: input.actionType,
        target_refs: input.targetRefs,
        instructions: input.instructions || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `Agent 任务已保存，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "commit_ai_ppt_artifact",
    {
      title: "Commit AI PPT Artifact",
      description:
        "Validate and save one immutable material, blueprint, visual, scene, handoff, or delivery artifact and optionally complete its Agent task.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        kind: z.enum([
          "mission",
          "content-blueprint",
          "content-acceptance",
          "visual-brief",
          "concept-set",
          "visual-contract",
          "native-anchor-set",
          "feedback",
          "delivery",
          "experience",
          "target-render-evidence",
        ]),
        payload: z.record(z.string(), z.unknown()),
        taskId: z.string().trim().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("commit-artifact", input),
        expected_revision: input.expectedRevision,
        kind: input.kind,
        payload: input.payload,
        task_id: input.taskId || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.kind} 已回写，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "confirm_ai_ppt_gate",
    {
      title: "Confirm AI PPT Quality Gate",
      description:
        "Confirm the exact current G0, G3, or G4 review source through a host-verified user message/action or fresh host-native confirmation. A MissionConfirmation or reused message never confirms a Gate.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G3", "G4"]),
        userMessageRef: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const contextOutcome = await invokeForTool(invokeBridge, {
        ...requestForProject("get-gate-confirmation-context", input),
        gate: input.gate,
      });
      if (!contextOutcome.ok) return contextOutcome.result;
      const rawContext = contextOutcome.payload.confirmation_context;
      const context = rawContext
        ? {
            ...rawContext,
            project_root:
              rawContext.project_root ||
              contextOutcome.payload.selected_project_root ||
              input.projectRoot ||
              "",
          }
        : rawContext;
      if (
        !context ||
        context.gate !== input.gate ||
        context.challenge_revision !== input.expectedRevision
      ) {
        return toolErrorResult({
          code: "REVISION_CONFLICT",
          message: "当前 Gate 审阅版本或项目 revision 已变化，请刷新后重试。",
          details: {
            expectedRevision: input.expectedRevision,
            actualRevision: context?.challenge_revision,
          },
        });
      }
      let userActionRef = "";
      let userMessageRef = input.userMessageRef || "";
      let identityType = "";
      let identityRef = "";
      if (confirmationVerifier && userMessageRef) {
        const verified = await confirmationVerifier.verify({
          projectRoot: input.projectRoot || "",
          projectId: context.project_id,
          gate: input.gate,
          sourceVersion: context.source_version,
          evidenceRefs: context.evidence_refs,
          challengeId: context.challenge_id,
          challengeRevision: context.challenge_revision,
          userMessageRef,
        });
        if (!verified) {
          return toolErrorResult({
            code: "GATE_NOT_CONFIRMED",
            message: "用户 Gate 确认凭据未通过宿主验证。",
            details: { gate: input.gate },
          });
        }
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostGateConfirmation(server, context);
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
        userMessageRef = native.userMessageRef;
        identityType = "host-action";
        identityRef = userActionRef;
      }
      let hostConfirmationAssertion;
      try {
        hostConfirmationAssertion = confirmationAuthority.issue(context, {
          identityType,
          identityRef,
        });
      } catch (_error) {
        return toolErrorResult({
          code: "HOST_CONFIRMATION_UNAVAILABLE",
          message: "宿主无法签发当前 Gate 的版本绑定确认断言；项目状态未改变。",
          details: { gate: input.gate },
        });
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("confirm-gate", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        host_confirmation_assertion: hostConfirmationAssertion,
        user_action_ref: "",
        user_message_ref: "",
        source_version: context.source_version,
        challenge_id: context.challenge_id,
        challenge_revision: context.challenge_revision,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 已确认，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "get_delivery_status_projection",
    {
      title: "Get AI PPT Delivery Status",
      description:
        "Read the lightweight production and delivery projection, including gates, blocker, target PowerPoint evidence, and chat-send status.",
      inputSchema: projectSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-delivery-status-projection", input),
      );
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      const projection = {
        surface: "workbench",
        selectedProjectRoot: payload.selected_project_root,
        snapshotRevision: payload.snapshot_revision,
        delivery: payload.delivery,
      };
      return textResult(
        `已读取制作与交付状态，revision ${payload.snapshot_revision}。`,
        projection,
        projection,
      );
    },
  );

  server.registerTool(
    "set_ai_ppt_release_target_policy",
    {
      title: "Set AI PPT Release Target Policy",
      description:
        "Activate the known product-version release target policy for an existing schema 3 project. This migration tool cannot accept arbitrary target arrays or act as a per-project platform-skip preference.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        policyId: z.literal("v1.6-macos-powerpoint"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        operation: "set-release-target-policy",
        project_root: input.projectRoot,
        expected_revision: input.expectedRevision,
        policy_id: input.policyId,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `发布目标策略已绑定，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "record_internal_gate",
    {
      title: "Record AI PPT Internal Gate",
      description:
        "Record an authorized binary internal review for G1 or G2. G2 passes only after independent aesthetic and PPT engineering reviews plus target PowerPoint evidence.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G1", "G2"]),
        reviewerRole: z.enum(["独立审美审查智能体", "PPT 工程审查智能体"]),
        acceptanceRecordRefs: z.array(z.string().trim().min(1)).min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("record-internal-gate", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        reviewer_role: input.reviewerRole,
        acceptance_record_refs: input.acceptanceRecordRefs,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 内部审查已记录，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "record_chat_delivery",
    {
      title: "Record AI PPT Chat Delivery",
      description:
        "Persist a Codex chat message receipt for a visual sample, comparison, PPTX, preview, or delivery note without rebuilding the referenced artifact.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        deliveryType: z.enum([
          "visual-sample",
          "comparison",
          "pptx",
          "preview",
          "delivery-note",
        ]),
        artifactRefs: z.array(z.string().trim().min(1)).min(1),
        messageRef: z.string().trim().min(1),
        sendStatus: z.enum(["sent", "failed"]),
        retryOf: z.string().trim().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("record-chat-delivery", input),
        expected_revision: input.expectedRevision,
        delivery_type: input.deliveryType,
        artifact_refs: input.artifactRefs,
        message_ref: input.messageRef,
        send_status: input.sendStatus,
        retry_of: input.retryOf || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `聊天交付回执已记录，revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "save_review_marks",
    {
      title: "Save AI PPT Review Marks",
      description:
        "Save content or visual review marks against one exact source version. This never confirms G0 or G3.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        reviewType: z.enum(["content", "visual"]),
        sourceVersion: z.string().trim().min(1),
        marks: z.array(
          z.object({
            mark_id: z.string().trim().min(1),
            field_anchor: z.string().trim().min(1),
            exact_text: z.string(),
            prefix: z.string(),
            suffix: z.string(),
            comment: z.string().trim().min(1),
          }).strict(),
        ).min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("save-review-marks", input),
        expected_revision: input.expectedRevision,
        review_type: input.reviewType,
        source_version: input.sourceVersion,
        marks: input.marks,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `标记已保存，revision ${outcome.payload.result.snapshot.revision}；保存不等于 Gate 确认。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "reopen_ai_ppt_scope",
    {
      title: "Reopen AI PPT Scope",
      description:
        "Reopen one quality gate with a human reason, lock downstream gates, and preserve all historical artifacts.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G3", "G4"]),
        reason: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("reopen-scope", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        reason: input.reason,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 已重新打开，历史成果保留。`,
        outcome.payload.result,
        outcome.payload.result,
      );
    },
  );

  server.registerTool(
    "read_ai_ppt_project_asset",
    {
      title: "Read AI PPT Project Asset",
      description:
        "Read one bounded image or text preview from inside the selected managed project.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        assetRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      try {
        const asset = readProjectAssetFn({
          projectRoot: input.projectRoot,
          assetRef: input.assetRef,
        });
        return textResult(`已读取项目资源 ${asset.assetRef}。`, { asset });
      } catch (error) {
        return toolErrorResult({
          code: "SOURCE_UNREADABLE",
          message: error instanceof Error ? error.message : "项目资源无法读取。",
          details: { assetRef: input.assetRef },
        });
      }
    },
  );

  return server;
}

export async function startServer() {
  const server = createAiPptMcpServer();
  await server.connect(new StdioServerTransport());
  return server;
}
