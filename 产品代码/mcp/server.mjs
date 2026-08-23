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
import { PUBLIC_TOOL_CATALOG } from "./tool-catalog.mjs";
import { registerProjectTools } from "./tools/project-tools.mjs";
import { registerContentTools } from "./tools/content-tools.mjs";
import { registerReviewTools } from "./tools/review-tools.mjs";
import { registerVisualTools } from "./tools/visual-tools.mjs";
import { registerDeliveryExperienceTools } from "./tools/delivery-experience-tools.mjs";

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
  const catalogNames = new Set(PUBLIC_TOOL_CATALOG.map((tool) => tool.name));
  const registeredNames = new Set();
  const registerTool = server.registerTool.bind(server);
  server.registerTool = (name, ...args) => {
    if (!catalogNames.has(name)) {
      throw new Error(`MCP tool ${name} is missing from PUBLIC_TOOL_CATALOG`);
    }
    if (registeredNames.has(name)) {
      throw new Error(`MCP tool ${name} is registered more than once`);
    }
    registeredNames.add(name);
    return registerTool(name, ...args);
  };

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

  const toolContext = {
    server,
    projectSchema,
    invokeBridge,
    invokeForTool,
    requestForProject,
    textResult,
    toolErrorResult,
    readProjectAssetFn,
    projectAssetPath,
    hostSidebarAdapter,
    browserSurfaceAdapter,
    startScopedReviewSession,
    invokeScopedContentWrite,
    confirmationAuthority,
    confirmationVerifier,
    requestHostMissionConfirmation,
    requestHostGateConfirmation,
    obtainScopedConfirmation,
  };
  registerProjectTools(toolContext);
  registerContentTools(toolContext);
  registerReviewTools(toolContext);
  registerVisualTools(toolContext);
  registerDeliveryExperienceTools(toolContext);

  const missingRegistrations = PUBLIC_TOOL_CATALOG
    .map((tool) => tool.name)
    .filter((name) => !registeredNames.has(name));
  if (missingRegistrations.length) {
    throw new Error(
      `PUBLIC_TOOL_CATALOG tools are not registered: ${missingRegistrations.join(", ")}`,
    );
  }
  return server;
}

export async function startServer() {
  const server = createAiPptMcpServer();
  await server.connect(new StdioServerTransport());
  return server;
}
