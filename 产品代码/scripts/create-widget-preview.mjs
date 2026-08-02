import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { invokePythonBridge } from "../mcp/runtime-bridge/python-runtime.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = process.argv[2]?.trim();
if (!projectRoot) {
  throw new Error("Usage: node scripts/create-widget-preview.mjs <managed-project-root>");
}

const payload = await invokePythonBridge({
  operation: "get-project-snapshot",
  project_root: projectRoot,
});
const widgetData = {
  snapshot: payload.snapshot,
  selectedProjectRoot: projectRoot,
  initialSpace: "overview",
  requestedDisplayMode: "inline",
};
const serialized = JSON.stringify(widgetData).replaceAll("<", "\\u003c");
const html = await readFile(path.join(root, "widget", "dist", "index.html"), "utf8");
const previewHtml = html.replace(
  /<script\b[^>]*>/i,
  (openingTag) => `<script>window.__AI_PPT_PREVIEW__=${serialized};</script>${openingTag}`,
);
if (previewHtml === html) {
  throw new Error("Built widget did not contain an inline script insertion point.");
}

const outputDirectory = path.join(root, "output", "playwright");
await mkdir(outputDirectory, { recursive: true });
const outputPath = path.join(outputDirectory, "phase-a-workbench-preview.html");
await writeFile(outputPath, previewHtml, "utf8");
process.stdout.write(`${outputPath}\n`);
