import { App as McpApp } from "@modelcontextprotocol/ext-apps";

import type { HostBridge, WidgetData } from "../types";

function widgetDataFromResult(result: unknown): WidgetData | undefined {
  const value = result as {
    _meta?: { widgetData?: WidgetData };
    structuredContent?: WidgetData;
  } | undefined;
  return value?._meta?.widgetData || value?.structuredContent;
}

export function createMcpAppClient(): HostBridge {
  const app = new McpApp(
    { name: "ai-ppt-studio", version: "0.4.0" },
    { availableDisplayModes: ["inline", "fullscreen"] },
    { autoResize: true },
  );

  return {
    async connect(onData) {
      if (onData) {
        app.addEventListener("toolresult", (event) => {
          const result = (event as unknown as { detail?: unknown }).detail || event;
          const data = widgetDataFromResult(result);
          if (data?.snapshot) onData(data);
        });
        window.addEventListener("message", (event) => {
          if (event.data?.method !== "ui/notifications/tool-result") return;
          const data = widgetDataFromResult(event.data?.params?.result);
          if (data?.snapshot) onData(data);
        });
      }
      await app.connect();
      const initial = widgetDataFromResult(window.openai?.rawToolResult)
        || (window.openai?.toolOutput as WidgetData | undefined);
      if (initial?.snapshot && onData) onData(initial);
    },
    async callTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
      const result = await app.callServerTool({ name, arguments: args });
      const structured = result?.structuredContent as T | undefined;
      if (result?.isError || !structured) {
        const error = new Error("AI PPT Studio 工具调用失败") as Error & { code?: string };
        error.code = (structured as { error?: { code?: string } } | undefined)?.error?.code;
        throw error;
      }
      return structured;
    },
    async updateModelContext(context) {
      if (typeof app.updateModelContext !== "function") return;
      await app.updateModelContext({ content: [{ type: "text", text: JSON.stringify(context) }] });
    },
    async sendFollowUp(message) {
      if (typeof app.sendMessage !== "function") throw new Error("sendMessage unavailable");
      await app.sendMessage({ role: "user", content: [{ type: "text", text: message }] });
    },
    async requestDisplayMode(mode) {
      if (typeof app.requestDisplayMode !== "function") throw new Error("display mode unavailable");
      await app.requestDisplayMode({ mode });
    },
    notifySize() {
      if (typeof app.sendSizeChanged !== "function") return;
      app.sendSizeChanged({
        width: Math.ceil(window.innerWidth),
        height: Math.ceil(document.documentElement.scrollHeight),
      });
    },
  };
}
