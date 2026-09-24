import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { createOpenAIFormCompatibleTransport } from "./host-form-transport.mjs";
import { readProjectAsset } from "./project-asset.mjs";
import { invokePythonBridge } from "./runtime-bridge/python-runtime.mjs";
import { createReviewBridge } from "./review-bridge.mjs";
import {
  createHostConfirmationAuthority,
  HOST_CONFIRMATION_SECRET_ENV,
} from "./host-confirmation-assertion.mjs";
import { createHostMessageVerifier } from "./host-message-verifier.mjs";
import { registerContentTools } from "./tools/content-tools.mjs";
import { registerDeliveryExperienceTools } from "./tools/delivery-experience-tools.mjs";
import { registerProjectTools } from "./tools/project-tools.mjs";
import { registerReviewTools } from "./tools/review-tools.mjs";
import { registerVisualTools } from "./tools/visual-tools.mjs";
import { registerOptimizationTools } from "./tools/optimization-tools.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BROWSER_REVIEW_HTML = path.join(ROOT, "widget", "dist", "index.html");
const manifest = JSON.parse(
  readFileSync(path.join(ROOT, ".codex-plugin", "plugin.json"), "utf8"),
);

const OpenAIFormResultSchema = z.looseObject({
  _meta: z.record(z.string(), z.unknown()).nullable().optional(),
  action: z.enum(["accept", "decline", "cancel"]),
  content: z.record(z.string(), z.unknown()).nullable().optional(),
});

function hostFormTransport(server) {
  const capabilities = server.server.getClientCapabilities() || {};
  if (capabilities.extensions?.["openai/form"]) return "openai-form";
  if (capabilities.elicitation) return "standard-elicitation";
  return null;
}

async function requestHostForm(server, params, transport, options) {
  const startedAt = new Date().toISOString();
  const started = performance.now();
  const attemptId = randomUUID();
  try {
    const requestOptions = { timeout: options.timeoutMs, signal: options.signal };
    let result;
    if (transport === "openai-form") {
      result = await server.server.request(
        { method: "openai/form", params }, OpenAIFormResultSchema, requestOptions,
      );
    } else if (transport === "standard-elicitation") {
      result = await server.server.elicitInput({ ...params, mode: "form" }, requestOptions);
    } else {
      throw new Error("Host form transport is unavailable");
    }
    options.signal?.throwIfAborted();
    return result;
  } catch (error) {
    // Never copy provider text/data, prompts, credentials or customer content.
    const errorName = error?.name === "$ZodError" ? "ZodError" : error?.name;
    const safe = new Error("Host confirmation request did not complete");
    safe.hostConfirmationDetails = {
      reason: options.signal?.aborted ? "cancelled" :
        error?.code === -32001 ? "timeout" :
        error?.code === -32602 || errorName === "ZodError" ? "invalid-response" : "transport-error",
      error_name: ["McpError", "AbortError", "ZodError", "Error"].includes(errorName) ? errorName : "Error",
      error_code: Number.isSafeInteger(error?.code) ? error.code : null,
      attempt_id: attemptId,
      tool_request_id: options.requestId ?? null,
      started_at: startedAt,
      ended_at: new Date().toISOString(),
      elapsed_ms: Math.round(performance.now() - started),
      timeout_ms: options.timeoutMs,
    };
    throw safe;
  }
}

function hostNonConfirmation(result, details = {}) {
  const incomplete = result.action === "accept";
  return { ok: false, error: {
    code: incomplete ? "HOST_CONFIRMATION_NOT_COMPLETED" : "HOST_CONFIRMATION_DECLINED",
    message: incomplete ? "表单已提交，但未形成有效确认；已有决定保留，项目状态未改变。" :
      "本次表单确认已取消；已有决定保留，项目状态未改变。",
    details: { ...details, action: result.action, confirmed: result.content?.confirmed === false ? false : null },
  } };
}

function cancelledConfirmation(extra) {
  if (!extra?.signal?.aborted) return null;
  return toolErrorResult({
    code: "HOST_CONFIRMATION_UNAVAILABLE",
    message: "本次确认请求已停止；已有决定保留，项目状态未改变。",
    details: { phase: "confirmation-before-write", reason: "cancelled" },
  });
}

async function checkHostVerifier(verifier, request) {
  try {
    return { verified: await verifier.verify(request) };
  } catch (_error) {
    return { error: toolErrorResult({
      code: "HOST_CONFIRMATION_UNAVAILABLE",
      message: "宿主暂时无法验证已有确认；已有决定保留，项目状态未改变。",
      details: { phase: "host-message-verification", reason: "verifier-unavailable" },
    }) };
  }
}

function requestForProject(operation, input = {}) {
  return {
    operation,
    ...(input.projectRoot ? { project_root: input.projectRoot } : {}),
  };
}

function textResult(message, structuredContent) {
  return { content: [{ type: "text", text: message }], structuredContent };
}

function toolErrorResult(error) {
  const code = typeof error?.code === "string" ? error.code : "INTERNAL_ERROR";
  const message =
    typeof error?.message === "string" && error.message.trim()
      ? error.message.trim()
      : "AI PPT Studio 暂时无法完成该操作。";
  const details = error?.details && typeof error.details === "object" ? error.details : {};
  return {
    isError: true,
    content: [{ type: "text", text: message }],
    structuredContent: { ok: false, error: { code, message, details } },
  };
}

async function invokeForTool(invokeBridge, request) {
  try {
    return { ok: true, payload: await invokeBridge(request) };
  } catch (error) {
    return { ok: false, result: toolErrorResult(error) };
  }
}

function nativeMissionConfirmationMessage(input) {
  const fields = [
    ["汇报主题", input.missionSummary?.topic],
    ["汇报对象", input.missionSummary?.primaryAudience],
    ["期望判断或行动", input.missionSummary?.desiredJudgmentOrAction],
    ["材料状态", input.missionSummary?.materialSummary],
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
  const identity =
    input.materialMode === "no-materials-confirmed"
      ? "当前无材料，将以方案建议模式继续；客户现状仅作诊断假设，能力与结果均待联合验证。"
      : "依据当前已登记材料进入证据盘点，由 PresalesEvidenceBook 判断 material-backed 或 mixed-evidence。";
  return {
    ok: true,
    message: [
      "请确认当前 AI PPT Studio 任务卡：",
      ...fields.map(([label, value]) => `${label}：${value.trim()}`),
      `内容身份：${identity}`,
    ].join("\n"),
  };
}

async function requestHostMissionConfirmation(server, input, options) {
  const transport = hostFormTransport(server);
  if (!transport) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "当前宿主未提供原生确认能力；任务卡已保留，可在能力可用后重试。",
        details: {},
      },
    };
  }
  const prompt = nativeMissionConfirmationMessage(input);
  if (!prompt.ok) return prompt;
  let result;
  try {
    result = await requestHostForm(server, {
      message: prompt.message,
      requestedSchema: {
        type: "object",
        properties: {
          confirmed: {
            type: "boolean",
            title: "确认当前任务卡并继续",
            default: false,
          },
        },
        required: ["confirmed"],
      },
    }, transport, options);
  } catch (error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生确认暂时不可用；任务卡已保留。",
        details: { phase: "host-form-response", transport, ...error.hostConfirmationDetails },
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return hostNonConfirmation(result);
  }
  return { ok: true, userActionRef: `host-elicitation://${randomUUID()}` };
}

async function requestHostGateConfirmation(server, context, options) {
  const transport = hostFormTransport(server);
  if (!transport) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "当前宿主未提供原生 Gate 确认能力；项目状态未改变。",
        details: { gate: context?.gate || "" },
      },
    };
  }
  let result;
  try {
    result = await requestHostForm(server, {
      message: [
        `请确认当前 AI PPT Studio ${context.gate} 用户检查点：`,
        context.review_summary,
        `当前审阅源：${context.source_version}`,
        "本次确认只绑定当前版本、证据与 revision，不能复用于其他操作。",
      ].join("\n"),
      requestedSchema: {
        type: "object",
        properties: {
          confirmed: {
            type: "boolean",
            title: `确认当前 ${context.gate} 并继续`,
            default: false,
          },
        },
        required: ["confirmed"],
      },
    }, transport, options);
  } catch (error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生 Gate 确认暂时不可用；项目状态未改变。",
        details: {
          gate: context.gate,
          phase: "host-form-response",
          transport,
          ...error.hostConfirmationDetails,
        },
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return hostNonConfirmation(result, { gate: context.gate });
  }
  return { ok: true, identityRef: `host-elicitation://${randomUUID()}` };
}

async function requestHostRevisionPlanConfirmation(server, context, options) {
  const transport = hostFormTransport(server);
  if (!transport) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "当前宿主未提供原生整套修改方案确认能力；项目状态未改变。",
        details: { planRef: context?.scope_id || "" },
      },
    };
  }
  let result;
  try {
    result = await requestHostForm(server, {
      message: [
        "请确认当前整套内容修改方案：",
        context.review_summary,
        `当前内容源：${context.source_version}`,
        "本次确认只绑定当前审核批次、修改方案、阅读稿与 revision；不等于 G0。",
      ].join("\n"),
      requestedSchema: {
        type: "object",
        properties: {
          confirmed: {
            type: "boolean",
            title: "确认当前整套修改方案并继续",
            default: false,
          },
        },
        required: ["confirmed"],
      },
    }, transport, options);
  } catch (error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生整套修改方案确认暂时不可用；项目状态未改变。",
        details: {
          planRef: context.scope_id,
          phase: "host-form-response",
          transport,
          ...error.hostConfirmationDetails,
        },
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return hostNonConfirmation(result, { planRef: context.scope_id });
  }
  return { ok: true, identityRef: `host-elicitation://${randomUUID()}` };
}

async function requestHostImageLedConfirmation(server, context, options) {
  const transport = hostFormTransport(server);
  const unavailable = {
    code: "CAPABILITY_GAP",
    message: "当前宿主无法提供 Image-led 可信确认；项目状态未改变。",
    details: { capability: "image-led-host-confirmation", targetRef: context.target_ref },
  };
  if (!transport) return { ok: false, error: unavailable };
  const action = context.choice === "revoked" ? "撤销材料授权" :
    context.scope_kind === "image-led-selection" ? "确认图片定版" : "确认材料授权";
  let result;
  try {
    result = await requestHostForm(server, {
      message: [
        `请${action}：`, context.review_summary,
        `当前目标：${context.target_ref}`,
        "决定绑定当前确切目标与证据；材料授权在已确认范围内持续有效。",
      ].join("\n"),
      requestedSchema: {
        type: "object",
        properties: { confirmed: { type: "boolean", title: action, default: false } },
        required: ["confirmed"],
      },
    }, transport, options);
  } catch (error) {
    return { ok: false, error: { ...unavailable, details: {
      ...unavailable.details, phase: "host-form-response", transport,
      ...error.hostConfirmationDetails,
    } } };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return hostNonConfirmation(result, { targetRef: context.target_ref });
  }
  return { ok: true, identityRef: `host-elicitation://${randomUUID()}` };
}

function snake(key) {
  return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function genericRequest(operation, input) {
  const request = requestForProject(operation, input);
  for (const [key, value] of Object.entries(input || {})) {
    if (key !== "projectRoot") request[snake(key)] = value;
  }
  return request;
}

function genericHandler(invokeBridge, message = "操作已完成。") {
  return async (input = {}, operation) => {
    const outcome = await invokeForTool(invokeBridge, genericRequest(operation, input));
    if (!outcome.ok) return outcome.result;
    const structured = outcome.payload.result || outcome.payload;
    return textResult(message, structured);
  };
}

export function createAiPptMcpServer(options = {}) {
  // Internal host integration setting, never accepted as a public tool input.
  // Human response time must not inherit the SDK's 60-second RPC default.
  const hostConfirmationTimeoutMs = options.hostConfirmationTimeoutMs ?? 10 * 60 * 1000;
  if (!Number.isSafeInteger(hostConfirmationTimeoutMs) || hostConfirmationTimeoutMs <= 0) {
    throw new TypeError("hostConfirmationTimeoutMs must be a positive safe integer");
  }
  const hostRequestOptions = (extra) => ({
    timeoutMs: hostConfirmationTimeoutMs, signal: extra?.signal, requestId: extra?.requestId,
  });
  const confirmationAuthority =
    options.confirmationAuthority || createHostConfirmationAuthority();
  const invokeBridge =
    options.invokeBridge ||
    ((request) => invokePythonBridge(request, {
      env: {
        ...process.env,
        [HOST_CONFIRMATION_SECRET_ENV]: confirmationAuthority.secret,
      },
    }));
  const readProjectAssetFn = options.readProjectAsset || readProjectAsset;
  const browserSurfaceAdapter = options.browserSurfaceAdapter || null;
  const reviewBridgeFactory = options.reviewBridgeFactory || createReviewBridge;
  const confirmationVerifier = options.confirmationVerifier || null;
  const gateMessageVerifier = options.gateMessageVerifier || null;
  const server = new McpServer(
    { name: manifest.name, version: manifest.version },
    {
      instructions:
        "Use the revision-safe data tools for the managed AI PPT project. Codex chat is the only primary entry; professional review surfaces are opened on demand. Never edit state JSON directly and use Codex Presentations as the only PPTX route.",
    },
  );

  async function startScopedReviewBridge(scope) {
    let bridge;
    try {
      bridge = reviewBridgeFactory({
        ...scope,
        invokeBridge,
        readReviewHtml: () => readFileSync(BROWSER_REVIEW_HTML, "utf8"),
        readProjectAsset: readProjectAssetFn,
        createReviewSession: createAuthoritativeReviewSession,
        notifyHost: options.notifyHost,
        verifyAiReceipt: options.verifyAiReceipt,
      });
      const session = await bridge.start();
      if (
        !session
        || typeof session.url !== "string"
        || !session.url
        || typeof session.bridgeSessionId !== "string"
        || !session.bridgeSessionId
      ) {
        const error = new Error("Review Bridge returned an invalid scoped session");
        error.code = "REVIEW_BRIDGE_UNAVAILABLE";
        throw error;
      }
      return { bridge, session };
    } catch (error) {
      if (bridge && typeof bridge.stop === "function") {
        try {
          await bridge.stop();
        } catch (_stopError) {
          // Preserve the original bridge startup error.
        }
      }
      if (typeof error?.code === "string") throw error;
      const wrapped = new Error(
        error?.message || "Review Bridge could not start the scoped review session",
      );
      wrapped.code = "REVIEW_BRIDGE_UNAVAILABLE";
      throw wrapped;
    }
  }

  function scopeFromRuntimeSession(payload) {
    const result = payload?.result;
    const session = result?.session;
    const snapshot = result?.snapshot;
    const scope = {
      projectRoot: String(payload?.selected_project_root || "").trim(),
      reviewType: String(session?.review_type || "").trim(),
      reviewSessionId: String(session?.review_session_id || "").trim(),
      sourceVersion: String(session?.source_version || "").trim(),
      expectedRevision: snapshot?.revision,
    };
    if (
      !scope.projectRoot
      || !["content-full-deck", "visual-professional"].includes(scope.reviewType)
      || !scope.reviewSessionId
      || !scope.sourceVersion
      || !Number.isSafeInteger(scope.expectedRevision)
      || scope.expectedRevision < 0
    ) {
      const error = new Error("Runtime did not return a complete ReviewSession scope");
      error.code = "REVIEW_SOURCE_UNAVAILABLE";
      throw error;
    }
    return scope;
  }

  async function createAuthoritativeReviewSession({ projectRoot, reviewType }) {
    const requestedReviewType = String(reviewType || "").trim();
    const formalReviewType = {
      content: "content-full-deck",
      visual: "visual-professional",
    }[requestedReviewType] || requestedReviewType;
    const outcome = await invokeForTool(invokeBridge, {
      operation: "get-review-projection",
      project_root: projectRoot,
      review_type: formalReviewType,
    });
    if (!outcome.ok) {
      const error = new Error(
        outcome.result?.structuredContent?.error?.message
          || "Target review projection is unavailable",
      );
      error.code = outcome.result?.structuredContent?.error?.code || "REVIEW_SOURCE_UNAVAILABLE";
      throw error;
    }
    const payload = outcome.payload;
    const scope = {
      projectRoot: String(payload?.selected_project_root || projectRoot).trim(),
      reviewType: formalReviewType,
      reviewSessionId: String(payload?.review?.review_session_id || "").trim(),
      sourceVersion: String(payload?.review?.source_version || "").trim(),
      expectedRevision: payload?.snapshot_revision,
    };
    if (
      !scope.projectRoot
      || !["content-full-deck", "visual-professional"].includes(scope.reviewType)
      || !scope.reviewSessionId
      || !scope.sourceVersion
      || !Number.isSafeInteger(scope.expectedRevision)
      || scope.expectedRevision < 0
    ) {
      const error = new Error("Target review projection is unavailable");
      error.code = "REVIEW_SOURCE_UNAVAILABLE";
      throw error;
    }
    const { session } = await startScopedReviewBridge(scope);
    return {
      ...session,
      reviewType: requestedReviewType || formalReviewType,
    };
  }

  async function openOrResumeReviewSession(input, operation) {
    const outcome = await invokeForTool(invokeBridge, genericRequest(operation, input));
    if (!outcome.ok) return outcome.result;
    let scope;
    try {
      scope = scopeFromRuntimeSession(outcome.payload);
    } catch (error) {
      return toolErrorResult(error);
    }
    let bridgeSession;
    try {
      bridgeSession = await startScopedReviewBridge(scope);
    } catch (error) {
      return toolErrorResult(error);
    }
    const { session } = bridgeSession;
    let opened = false;
    if (
      browserSurfaceAdapter?.canOpen
      && typeof browserSurfaceAdapter.openUrl === "function"
    ) {
      try {
        opened = (await browserSurfaceAdapter.openUrl(session.url))?.opened === true;
      } catch (_error) {
        opened = false;
      }
    }
    const structured = outcome.payload.result || outcome.payload;
    const status = opened ? "opened" : "review-session-ready";
    const message = opened
      ? "已在兼容的宿主 Browser 打开专业审阅。"
      : "专业审阅已准备，请立即使用 Codex 内置 Browser 打开 scoped URL。";
    return textResult(message, {
      ...structured,
      status,
      opened,
      openMode: opened ? "host-adapter" : "agent-browser",
      browserAction: "open-scoped-url",
      url: session.url,
      expiresAt: session.expiresAt,
      bridgeSessionId: session.bridgeSessionId,
      projectRoot: scope.projectRoot,
      reviewType: scope.reviewType,
      reviewSessionId: scope.reviewSessionId,
      sourceVersion: scope.sourceVersion,
      revision: scope.expectedRevision,
    });
  }

  const handlers = {
    createProject: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, {
        operation,
        name: input.name,
        project_id: input.projectId || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("项目已创建。", { snapshot: outcome.payload.snapshot });
    },
    getSnapshot: async (input = {}, operation) => {
      const outcome = await invokeForTool(
        invokeBridge,
        {
          ...requestForProject(operation, input),
          ...(input.includeImage2Preflight !== undefined
            ? { include_image2_preflight: input.includeImage2Preflight } : {}),
        },
      );
      if (!outcome.ok) return outcome.result;
      return textResult("已读取项目快照。", {
        snapshot: outcome.payload.snapshot,
        ...(input.includeImage2Preflight === true
          ? { image2_preflight: outcome.payload.image2_preflight } : {}),
      });
    },
    getUserStatus: genericHandler(invokeBridge, "已读取项目状态。"),
    addMaterial: genericHandler(invokeBridge, "材料已登记。"),
    saveMission: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, input),
        expected_revision: input.expectedRevision,
        payload: input.missionDraft,
      });
      if (!outcome.ok) return outcome.result;
      return textResult("Mission 草稿已保存。", outcome.payload.result);
    },
    confirmMission: async (input, operation, extra) => {
      let userActionRef = input.userActionRef || "";
      const userMessageRef = input.userMessageRef || "";
      if (confirmationVerifier && (userActionRef || userMessageRef)) {
        const verification = await checkHostVerifier(confirmationVerifier, {
          projectRoot: input.projectRoot || "",
          missionDraftRef: input.missionDraftRef,
          materialMode: input.materialMode,
          materialInventoryRef: input.materialInventoryRef || "",
          expectedRevision: input.expectedRevision,
          userActionRef,
          userMessageRef,
        });
        if (verification.error) return verification.error;
        const verified = verification.verified;
        if (verified !== true) {
          return toolErrorResult({
            code: "MISSION_NOT_CONFIRMED",
            message: "用户确认凭据未通过宿主验证。",
            details: {},
          });
        }
      } else {
        const native = await requestHostMissionConfirmation(server, input, hostRequestOptions(extra));
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
      }
      const cancelled = cancelledConfirmation(extra);
      if (cancelled) return cancelled;
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, input),
        expected_revision: input.expectedRevision,
        mission_draft_ref: input.missionDraftRef,
        material_mode: input.materialMode,
        material_inventory_ref: input.materialInventoryRef || "",
        user_action_ref: userActionRef,
        user_message_ref: confirmationVerifier ? userMessageRef : "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("Mission 已确认。", outcome.payload.result);
    },
    requestAgentAction: async (input, operation) => {
      if (input.actionType !== "generate-slide-images") {
        return genericHandler(invokeBridge)(input, operation);
      }
      const outcome = await invokeForTool(invokeBridge, genericRequest(operation, input));
      if (!outcome.ok) return outcome.result;
      const structured = outcome.payload.result || outcome.payload;
      const generation = structured.generation_response;
      const result = textResult(structured.follow_up_message || "已读取生图任务结果。", {
        ...structured,
        ...(generation ? { generation_response: { ...generation } } : {}),
      });
      if (generation) {
        delete result.structuredContent.generation_response.image_base64;
        if (generation.status === "completed" && generation.image_base64) {
          result.content.push({ type: "image", data: generation.image_base64,
            mimeType: generation.image_mime_type });
        }
      }
      return result;
    },
    submitHumanDecision: async (input, operation, extra) => {
      const contextOutcome = await invokeForTool(invokeBridge, {
        ...requestForProject("get-image-led-confirmation-context", input),
        target_ref: input.targetRef,
        choice: input.choice,
      });
      if (!contextOutcome.ok) return contextOutcome.result;
      if (contextOutcome.payload.image_led === false) {
        return genericHandler(invokeBridge)(input, operation);
      }
      const context = contextOutcome.payload.confirmation_context;
      const choices = {
        "image-led-authorization": "approved",
        "image-led-revocation": "revoked",
        "image-led-selection": "approved",
      };
      if (
        contextOutcome.payload.image_led !== true || !context ||
        !context.project_id || !context.project_root ||
        context.target_ref !== input.targetRef || context.scope_id !== input.targetRef ||
        context.choice !== input.choice || choices[context.scope_kind] !== input.choice ||
        !Array.isArray(context.evidence_refs) || !context.evidence_refs.includes(input.targetRef) ||
        context.challenge_revision !== input.expectedRevision
      ) {
        return toolErrorResult({
          code: "REVISION_CONFLICT",
          message: "当前 Image-led 目标、决定或项目 revision 已变化，请刷新后重试。",
          details: { targetRef: input.targetRef, expectedRevision: input.expectedRevision,
            actualRevision: context?.challenge_revision },
        });
      }
      const userMessageRef = String(input.userMessageRef || "").trim();
      let identityType;
      let identityRef;
      if (input.confirmationMode === "verified-message-only" &&
          (!confirmationVerifier || !userMessageRef)) {
        return toolErrorResult({
          code: "CAPABILITY_GAP",
          message: "既有授权的范围记录尚未绑定；当前仅复用路径未触发表单。",
          details: {
            capability: "image-led-host-confirmation", targetRef: input.targetRef,
            reason: !confirmationVerifier ? "verified-message-adapter-unavailable" :
              "verified-message-reference-unavailable",
          },
        });
      }
      if (confirmationVerifier && userMessageRef) {
        let verified;
        try {
          verified = await confirmationVerifier.verify({
            projectRoot: context.project_root, projectId: context.project_id,
            targetRef: input.targetRef, choice: input.choice,
            scopeKind: context.scope_kind, scopeId: context.scope_id,
            sourceVersion: context.source_version, evidenceRefs: context.evidence_refs,
            challengeId: context.challenge_id, challengeRevision: context.challenge_revision,
            userMessageRef,
          });
        } catch (_error) {
          return toolErrorResult({
            code: "CAPABILITY_GAP", message: "宿主暂时无法验证 Image-led 确认凭据；项目状态未改变。",
            details: { capability: "image-led-host-confirmation", targetRef: input.targetRef },
          });
        }
        if (verified !== true) return toolErrorResult({
          code: "IMAGE_LED_NOT_CONFIRMED", message: "Image-led 确认凭据未通过宿主验证。",
          details: { targetRef: input.targetRef },
        });
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostImageLedConfirmation(server, context, hostRequestOptions(extra));
        if (!native.ok) return toolErrorResult(native.error);
        identityType = "host-action";
        identityRef = native.identityRef;
      }
      const cancelled = cancelledConfirmation(extra);
      if (cancelled) return cancelled;
      let assertion;
      try {
        assertion = confirmationAuthority.issue(context, { identityType, identityRef });
      } catch (_error) {
        return toolErrorResult({
          code: "CAPABILITY_GAP", message: "宿主无法签发 Image-led 确认断言；项目状态未改变。",
          details: { capability: "image-led-host-confirmation", targetRef: input.targetRef },
        });
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, { projectRoot: context.project_root }),
        expected_revision: input.expectedRevision, target_ref: input.targetRef,
        choice: input.choice, feedback: input.feedback || "",
        source_version: context.source_version, challenge_id: context.challenge_id,
        challenge_revision: context.challenge_revision, host_confirmation_assertion: assertion,
      });
      if (!outcome.ok) return outcome.result;
      return textResult("当前 Image-led 决定已记录；此决定不等于 G3。", outcome.payload.result);
    },
    commitArtifact: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, input),
        command_id: input.commandId || "",
        expected_revision: input.expectedRevision,
        task_id: input.taskId || "",
        kind: input.kind,
        payload: input.payload,
      });
      if (!outcome.ok) return outcome.result;
      const result = outcome.payload.result;
      if (input.payload?.artifact_type !== "image-led-authorization-scope") {
        return textResult("受治理制品已提交。", result);
      }
      // A scope registration is already durable. Missing continuation metadata
      // must never turn its successful receipt into a failed-write report.
      const snapshot = result?.snapshot;
      const root = outcome.payload.selected_project_root;
      const scopeRef = result?.artifact_ref;
      const validReceipt = typeof scopeRef === "string" &&
        /^artifact:\/\/image-led-authorization-scope\/[0-9a-f]{64}$/.test(scopeRef) &&
        Number.isSafeInteger(snapshot?.revision) && snapshot.revision >= input.expectedRevision &&
        typeof root === "string" && path.isAbsolute(root) &&
        snapshot?.project?.project_root === root &&
        typeof input.payload.project_id === "string" && input.payload.project_id.length > 0 &&
        snapshot?.project?.project_id === input.payload.project_id &&
        snapshot?.artifacts?.["visual/image-led/scope"] === scopeRef;
      const continuation = validReceipt ? {
        status: "requires-verified-message",
        call: {
          name: "submit_ai_ppt_human_decision",
          arguments: { projectRoot: root, expectedRevision: snapshot.revision,
            targetRef: scopeRef, choice: "approved", confirmationMode: "verified-message-only" },
        },
      } : { status: "capability-gap", reason: "scope-receipt-identity-unavailable" };
      return textResult("材料范围已登记；授权承接调用仅允许复用可验证消息。", {
        ...result, authorization_continuation: continuation,
      });
    },
    confirmGate: async (input, _operation, extra) => {
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
        : null;
      if (
        !context ||
        context.gate !== input.gate ||
        context.scope_kind !== "gate" ||
        context.scope_id !== input.gate ||
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

      const userMessageRef = String(input.userMessageRef || "").trim();
      let identityType;
      let identityRef;
      const verifier = input.gate === "G3" ? gateMessageVerifier : confirmationVerifier;
      if ((userMessageRef && !verifier)
          || (input.gate === "G3" && (gateMessageVerifier || confirmationVerifier) && !userMessageRef)) {
        return toolErrorResult({
          code: "HOST_CONFIRMATION_UNAVAILABLE",
          message: "当前检查点需要可核验的对话消息引用；已有决定保留。",
          details: { gate: input.gate, reason: "verified-message-reference-or-adapter-unavailable" },
        });
      }
      if (verifier && userMessageRef) {
        const verification = await checkHostVerifier(verifier, {
          projectRoot: input.projectRoot || "",
          projectId: context.project_id,
          gate: input.gate,
          sourceVersion: context.source_version,
          evidenceRefs: context.evidence_refs,
          challengeId: context.challenge_id,
          challengeRevision: context.challenge_revision,
          userMessageRef,
        });
        if (verification.error) return verification.error;
        const verified = verification.verified;
        if (verified !== true) {
          return toolErrorResult({
            code: "GATE_NOT_CONFIRMED",
            message: "用户 Gate 确认凭据未通过宿主验证。",
            details: { gate: input.gate },
          });
        }
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostGateConfirmation(server, context, hostRequestOptions(extra));
        if (!native.ok) return toolErrorResult(native.error);
        identityType = "host-action";
        identityRef = native.identityRef;
      }

      const cancelled = cancelledConfirmation(extra);
      if (cancelled) return cancelled;

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
      return textResult(`${input.gate} 已确认。`, outcome.payload.result);
    },
    closeProject: genericHandler(invokeBridge),
    abortProject: genericHandler(invokeBridge),
    reopenScope: genericHandler(invokeBridge),
    setReleaseTargetPolicy: genericHandler(invokeBridge),
    readProjectAsset: async (input) => {
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
    buildEvidenceBook: genericHandler(invokeBridge),
    buildDecisionContext: genericHandler(invokeBridge),
    buildProblemSolutionFit: genericHandler(invokeBridge),
    buildReadingDeckBlueprint: genericHandler(invokeBridge),
    runEvidenceGate: genericHandler(invokeBridge),
    runPresalesReadingGate: genericHandler(invokeBridge),
    repairReadingDeckBlueprint: genericHandler(invokeBridge),
    getContentReviewProjection: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, input),
        review_session_id: input.reviewSessionId,
      });
      if (!outcome.ok) return outcome.result;
      return textResult("已读取完整内容审核投影。", { review: outcome.payload.review });
    },
    saveContentPageDecision: genericHandler(invokeBridge),
    submitContentReviewBatch: genericHandler(invokeBridge),
    withdrawContentReviewBatch: genericHandler(invokeBridge),
    saveContentRevisionPlan: genericHandler(invokeBridge),
    confirmContentRevisionPlan: async (input, _operation, extra) => {
      const contextOutcome = await invokeForTool(invokeBridge, {
        ...requestForProject(
          "get-content-revision-plan-confirmation-context",
          input,
        ),
        plan_ref: input.planRef,
        source_version: input.sourceVersion,
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
        : null;
      if (
        !context ||
        context.scope_kind !== "content-revision-plan" ||
        context.scope_id !== input.planRef ||
        context.source_version !== input.sourceVersion ||
        context.challenge_revision !== input.expectedRevision
      ) {
        return toolErrorResult({
          code: "REVISION_CONFLICT",
          message: "当前整套修改方案、内容源或项目 revision 已变化，请刷新后重试。",
          details: {
            expectedRevision: input.expectedRevision,
            actualRevision: context?.challenge_revision,
            planRef: input.planRef,
          },
        });
      }

      const userMessageRef = String(input.userMessageRef || "").trim();
      let identityType;
      let identityRef;
      if (confirmationVerifier && userMessageRef) {
        const verification = await checkHostVerifier(confirmationVerifier, {
          projectRoot: input.projectRoot || "",
          projectId: context.project_id,
          scopeKind: context.scope_kind,
          scopeId: context.scope_id,
          sourceVersion: context.source_version,
          evidenceRefs: context.evidence_refs,
          challengeId: context.challenge_id,
          challengeRevision: context.challenge_revision,
          userMessageRef,
        });
        if (verification.error) return verification.error;
        const verified = verification.verified;
        if (verified !== true) {
          return toolErrorResult({
            code: "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
            message: "整套修改方案确认凭据未通过宿主验证。",
            details: { planRef: input.planRef },
          });
        }
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostRevisionPlanConfirmation(server, context, hostRequestOptions(extra));
        if (!native.ok) return toolErrorResult(native.error);
        identityType = "host-action";
        identityRef = native.identityRef;
      }

      const cancelled = cancelledConfirmation(extra);
      if (cancelled) return cancelled;

      let hostConfirmationAssertion;
      try {
        hostConfirmationAssertion = confirmationAuthority.issue(context, {
          identityType,
          identityRef,
        });
      } catch (_error) {
        return toolErrorResult({
          code: "HOST_CONFIRMATION_UNAVAILABLE",
          message: "宿主无法签发当前整套修改方案的版本绑定确认断言；项目状态未改变。",
          details: { planRef: input.planRef },
        });
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("confirm-content-batch-revision-plan", input),
        expected_revision: input.expectedRevision,
        plan_ref: input.planRef,
        source_version: context.source_version,
        challenge_id: context.challenge_id,
        challenge_revision: context.challenge_revision,
        host_confirmation_assertion: hostConfirmationAssertion,
        user_action_ref: "",
        user_message_ref: "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套内容修改方案已确认。", outcome.payload.result);
    },
    createContentChangeSet: genericHandler(invokeBridge),
    openG0Review: genericHandler(invokeBridge),
    openOrResumeReviewSession,
    recordReviewHostOpen: genericHandler(invokeBridge),
    recordReviewHostNotification: genericHandler(invokeBridge),
    recordReviewAiReceipt: genericHandler(invokeBridge),
    getVisualReviewProjection: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject(operation, input),
        review_session_id: input.reviewSessionId,
      });
      if (!outcome.ok) return outcome.result;
      return textResult("已读取视觉审核投影。", { review: outcome.payload.review });
    },
    submitVisualAnchorBatch: genericHandler(invokeBridge),
    saveVisualContractMarks: genericHandler(invokeBridge),
    recordInternalGate: genericHandler(invokeBridge),
    getDeliveryStatus: genericHandler(invokeBridge),
    recordChatDelivery: genericHandler(invokeBridge),
    recommendExperience: genericHandler(invokeBridge),
    recordExperienceApplication: genericHandler(invokeBridge),
    summarizeProjectExperience: genericHandler(invokeBridge),
    beginExistingDeck: genericHandler(invokeBridge, '现有 PPT 原稿已绑定。'),
    setExistingDeckExternalScope: genericHandler(invokeBridge, '原稿外发范围已登记。'),
    registerExistingDeckRequest: genericHandler(invokeBridge, '逐页设计请求已登记。'),
    registerExistingDeckHistoricalDesign: async (input, operation) => genericHandler(
      invokeBridge, '历史设计图已按原始身份登记。')({
        projectRoot: input.projectRoot, expectedRevision: input.expectedRevision,
        requestId: input.requestId, slideId: input.slideId, titleItemId: input.titleItemId,
        commonRules: input.commonRules, imageBase64: input.imageDataBase64,
        imageSha256: input.imageSha256,
        provenance: {
          source_pptx_sha256: input.sourcePptxSha256,
          page_order: input.pageOrder,
          historical_request_id: input.historicalRequestId,
          historical_request_sha256: input.historicalRequestSha256,
          historical_response_sha256: input.historicalResponseSha256,
          historical_receiver: input.historicalReceiver,
          historical_model: input.historicalModel,
          historical_quality: input.historicalQuality,
        },
      }, operation),
    executeExistingDeckRequest: genericHandler(invokeBridge, '已读取本次 CRS 设计结果。'),
    recoverExistingDeckRequest: genericHandler(invokeBridge, '已只读恢复原请求的持久化状态。'),
    withdrawExistingDeckRequest: genericHandler(invokeBridge),
    supersedeExistingDeckResponse: genericHandler(invokeBridge),
    composeExistingDeckMedia: genericHandler(invokeBridge, '原稿媒体已本地合成到设计图。'),
    reviewExistingDeckResponse: genericHandler(invokeBridge, '逐页来源审核已登记。'),
    selectExistingDeckImages: genericHandler(invokeBridge, '整套设计图已内部选定。'),
    registerExistingDeckPlan: genericHandler(invokeBridge, '区域与原生对象计划已登记。'),
    compileExistingDeckHandoff: genericHandler(invokeBridge, '已编译原生转换交接。'),
    registerExistingDeckResult: genericHandler(invokeBridge, '原生 PPTX 结果已登记。'),
    registerExistingDeckTarget: genericHandler(invokeBridge, '目标 PowerPoint 证据已登记。'),
    registerExistingDeckQa: genericHandler(invokeBridge, '整套逐页 QA 已登记。'),
    getExistingDeckStatus: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, genericRequest(operation, input));
      if (!outcome.ok) return outcome.result;
      return textResult('已读取现有稿优化状态。', outcome.payload.optimization);
    },
    previewExistingDeckImage: async (input, operation) => {
      const outcome = await invokeForTool(invokeBridge, genericRequest(operation, input));
      if (!outcome.ok) return outcome.result;
      const { image_base64: data, ...identity } = outcome.payload.image;
      const shown = textResult('已读取当前逐页设计图。', identity);
      shown.content.push({ type: 'image', data, mimeType: identity.image_mime_type });
      return shown;
    },
  };

  registerProjectTools(server, handlers);
  registerContentTools(server, handlers);
  registerReviewTools(server, handlers);
  registerVisualTools(server, handlers);
  registerDeliveryExperienceTools(server, handlers);
  registerOptimizationTools(server, handlers);
  return server;
}

export async function startServer() {
  const server = createAiPptMcpServer({
    gateMessageVerifier: createHostMessageVerifier(),
  });
  await server.connect(
    createOpenAIFormCompatibleTransport(new StdioServerTransport()),
  );
  return server;
}
