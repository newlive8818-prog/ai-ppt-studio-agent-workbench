import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  RESOURCE_MIME_TYPE,
  registerAppResource,
} from "@modelcontextprotocol/ext-apps/server";

const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WIDGET_DIST = path.join(PLUGIN_ROOT, "widget", "dist", "index.html");

export async function readWidgetHtml() {
  return readFile(WIDGET_DIST, "utf8");
}

export function registerWorkbenchResource(server, uri) {
  const description =
    "AI PPT Studio 项目认知工作台：展示交付目标、AI 当前判断、不确定性、成果、质量门和需要用户处理的一个关键判断。";
  const csp = { connectDomains: [], resourceDomains: ["data:", "blob:"] };
  const openAiCsp = { connect_domains: [], resource_domains: ["data:", "blob:"] };
  const metadata = {
    ui: { prefersBorder: false, csp },
    "openai/widgetDescription": description,
    "openai/widgetPrefersBorder": false,
    "openai/widgetCSP": openAiCsp,
  };
  registerAppResource(
    server,
    "ai-ppt-studio-workbench",
    uri,
    { title: "AI PPT Studio 工作台", description, _meta: metadata },
    async () => ({
      contents: [
        {
          uri,
          mimeType: RESOURCE_MIME_TYPE,
          text: await readWidgetHtml(),
          _meta: metadata,
        },
      ],
    }),
  );
}
