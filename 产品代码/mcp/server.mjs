import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { registerAppTool } from "@modelcontextprotocol/ext-apps/server";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { invokePythonBridge } from "./runtime-bridge/python-runtime.mjs";
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
  const server = new McpServer(
    { name: manifest.name, version: manifest.version },
    {
      instructions:
        "Use render_ai_ppt_workbench to open the native AI PPT project workbench. Use get_ai_ppt_project_snapshot for headless state reads and submit_ai_ppt_human_decision for revision-safe human choices. The managed project directory is the business truth source; never edit its workbench JSON directly.",
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
