import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { registerAppTool } from "@modelcontextprotocol/ext-apps/server";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { invokePythonBridge } from "./runtime-bridge/python-runtime.mjs";
import { readProjectAsset } from "./project-asset.mjs";
import { registerWorkbenchResource } from "./widget-resource.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(
  readFileSync(path.join(ROOT, ".codex-plugin", "plugin.json"), "utf8"),
);

export const AI_PPT_WIDGET_URI = "ui://ai-ppt-studio/workbench.html";

const projectSchema = {
  projectRoot: z.string().trim().optional(),
};

function requestForProject(operation, input) {
  const request = { operation };
  if (input?.projectRoot) request.project_root = input.projectRoot;
  return request;
}

function textResult(message, structuredContent, widgetData) {
  const result = {
    content: [{ type: "text", text: message }],
    structuredContent,
  };
  if (widgetData) result._meta = { widgetData };
  return result;
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

async function invokeForTool(invokeBridge, request) {
  try {
    return { ok: true, payload: await invokeBridge(request) };
  } catch (error) {
    return { ok: false, result: toolErrorResult(error) };
  }
}

export function createAiPptMcpServer(options = {}) {
  const invokeBridge = options.invokeBridge || invokePythonBridge;
  const readProjectAssetFn = options.readProjectAsset || readProjectAsset;
  const server = new McpServer(
    { name: manifest.name, version: manifest.version },
    {
      instructions:
        "Use render_ai_ppt_workbench to open the native AI PPT project workbench. Persist material, Agent tasks, immutable artifacts, human decisions, and G0-G4 through the provided revision-safe tools. The managed project directory is the business truth source; never edit its state JSON directly. Image 2 is the visual concept route and Codex Presentations is the only PPTX route.",
    },
  );

  registerWorkbenchResource(server, AI_PPT_WIDGET_URI);

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
          "classify-materials",
          "generate-blueprint",
          "revise-blueprint",
          "explore-concepts",
          "build-engineering-samples",
          "freeze-visual-contract",
          "build-pptx",
          "qa-render",
          "repair-pptx",
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
          "material-findings",
          "mission",
          "content-blueprint",
          "visual-brief",
          "concept-set",
          "engineering-samples",
          "visual-contract",
          "slide-scene-graph",
          "feedback",
          "presentation-handoff",
          "delivery",
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
        "Pass one open G0-G4 gate after runtime evidence checks. This tool represents an explicit human confirmation.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G1", "G2", "G3", "G4"]),
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
        ...requestForProject("confirm-gate", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
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
    "reopen_ai_ppt_scope",
    {
      title: "Reopen AI PPT Scope",
      description:
        "Reopen one quality gate with a human reason, lock downstream gates, and preserve all historical artifacts.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G1", "G2", "G3", "G4"]),
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

  registerAppTool(
    server,
    "read_ai_ppt_project_asset",
    {
      title: "Read AI PPT Project Asset",
      description:
        "Read one bounded image or text preview from inside the selected managed project. Available to the workbench app only.",
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
      _meta: {
        ui: { visibility: ["app"] },
      },
    },
    async (input) => {
      try {
        const asset = readProjectAssetFn({
          projectRoot: input.projectRoot,
          assetRef: input.assetRef,
        });
        return textResult(`已读取项目资源 ${asset.assetRef}。`, { asset }, { asset });
      } catch (error) {
        return toolErrorResult({
          code: "SOURCE_UNREADABLE",
          message: error instanceof Error ? error.message : "项目资源无法读取。",
          details: { assetRef: input.assetRef },
        });
      }
    },
  );

  registerAppTool(
    server,
    "render_ai_ppt_workbench",
    {
      title: "Render AI PPT Studio Workbench",
      description:
        "Open the native AI PPT Studio project workbench in Codex. It shows the Agent cognition map in compact inline mode and can expand to fullscreen when the host supports it.",
      inputSchema: {
        ...projectSchema,
        initialSpace: z.enum(["overview", "materials", "blueprint", "visual", "delivery"]).optional(),
        requestedDisplayMode: z.enum(["inline", "fullscreen"]).optional(),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
      _meta: {
        ui: { resourceUri: AI_PPT_WIDGET_URI, visibility: ["model", "app"] },
        "ui/resourceUri": AI_PPT_WIDGET_URI,
        "openai/outputTemplate": AI_PPT_WIDGET_URI,
        "openai/widgetAccessible": true,
        "openai/toolInvocation/invoking": "正在打开 AI PPT Studio 工作台…",
        "openai/toolInvocation/invoked": "AI PPT Studio 工作台已就绪",
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-snapshot", input),
      );
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      const widgetData = {
        snapshot: payload.snapshot,
        selectedProjectRoot: payload.selected_project_root || payload.snapshot.project.project_root,
        initialSpace: input.initialSpace || "overview",
        requestedDisplayMode: input.requestedDisplayMode || "inline",
      };
      return {
        content: [
          {
            type: "text",
            text: `已打开“${payload.snapshot.project.name}”的 AI PPT Studio 原生工作台。`,
          },
        ],
        structuredContent: widgetData,
        _meta: {
          "openai/outputTemplate": AI_PPT_WIDGET_URI,
          widgetData,
        },
      };
    },
  );

  return server;
}

export async function startServer() {
  const server = createAiPptMcpServer();
  await server.connect(new StdioServerTransport());
  return server;
}
