import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { readProjectAsset } from "./project-asset.mjs";
import { invokePythonBridge } from "./runtime-bridge/python-runtime.mjs";
import {
  createHostConfirmationAuthority,
  HOST_CONFIRMATION_SECRET_ENV,
} from "./host-confirmation-assertion.mjs";
import { registerContentTools } from "./tools/content-tools.mjs";
import { registerDeliveryExperienceTools } from "./tools/delivery-experience-tools.mjs";
import { registerProjectTools } from "./tools/project-tools.mjs";
import { registerReviewTools } from "./tools/review-tools.mjs";
import { registerVisualTools } from "./tools/visual-tools.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(
  readFileSync(path.join(ROOT, ".codex-plugin", "plugin.json"), "utf8"),
);

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

async function requestHostMissionConfirmation(server, input) {
  if (!server.server.getClientCapabilities()?.elicitation) {
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
    result = await server.server.elicitInput({
      mode: "form",
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
    });
  } catch (_error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生确认暂时不可用；任务卡已保留。",
        details: {},
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_DECLINED",
        message: "任务确认已取消；项目状态未改变。",
        details: { action: result.action },
      },
    };
  }
  return { ok: true, userActionRef: `host-elicitation://${randomUUID()}` };
}

async function requestHostGateConfirmation(server, context) {
  if (!server.server.getClientCapabilities()?.elicitation) {
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
    result = await server.server.elicitInput({
      mode: "form",
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
    });
  } catch (_error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生 Gate 确认暂时不可用；项目状态未改变。",
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
  return { ok: true, identityRef: `host-elicitation://${randomUUID()}` };
}

async function requestHostRevisionPlanConfirmation(server, context) {
  if (!server.server.getClientCapabilities()?.elicitation) {
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
    result = await server.server.elicitInput({
      mode: "form",
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
    });
  } catch (_error) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_UNAVAILABLE",
        message: "宿主原生整套修改方案确认暂时不可用；项目状态未改变。",
        details: { planRef: context.scope_id },
      },
    };
  }
  if (result.action !== "accept" || result.content?.confirmed !== true) {
    return {
      ok: false,
      error: {
        code: "HOST_CONFIRMATION_DECLINED",
        message: "整套修改方案确认已取消；项目状态未改变。",
        details: { planRef: context.scope_id, action: result.action },
      },
    };
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
  const confirmationVerifier = options.confirmationVerifier || null;
  const server = new McpServer(
    { name: manifest.name, version: manifest.version },
    {
      instructions:
        "Use the revision-safe data tools for the managed AI PPT project. Codex chat is the only primary entry; professional review surfaces are opened on demand. Never edit state JSON directly and use Codex Presentations as the only PPTX route.",
    },
  );

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
        requestForProject(operation, input),
      );
      if (!outcome.ok) return outcome.result;
      return textResult("已读取项目快照。", { snapshot: outcome.payload.snapshot });
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
    confirmMission: async (input, operation) => {
      let userActionRef = input.userActionRef || "";
      const userMessageRef = input.userMessageRef || "";
      if (confirmationVerifier && (userActionRef || userMessageRef)) {
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
      } else {
        const native = await requestHostMissionConfirmation(server, input);
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
      }
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
    requestAgentAction: genericHandler(invokeBridge),
    submitHumanDecision: genericHandler(invokeBridge),
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
      return textResult("受治理制品已提交。", outcome.payload.result);
    },
    confirmGate: async (input) => {
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
        identityType = "host-action";
        identityRef = native.identityRef;
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
    confirmContentRevisionPlan: async (input) => {
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
        const verified = await confirmationVerifier.verify({
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
        if (!verified) {
          return toolErrorResult({
            code: "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
            message: "整套修改方案确认凭据未通过宿主验证。",
            details: { planRef: input.planRef },
          });
        }
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostRevisionPlanConfirmation(server, context);
        if (!native.ok) return toolErrorResult(native.error);
        identityType = "host-action";
        identityRef = native.identityRef;
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
    openOrResumeReviewSession: genericHandler(invokeBridge),
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
  };

  registerProjectTools(server, handlers);
  registerContentTools(server, handlers);
  registerReviewTools(server, handlers);
  registerVisualTools(server, handlers);
  registerDeliveryExperienceTools(server, handlers);
  return server;
}

export async function startServer() {
  const server = createAiPptMcpServer();
  await server.connect(new StdioServerTransport());
  return server;
}
