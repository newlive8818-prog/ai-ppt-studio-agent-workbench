import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { invokePythonBridge } from "../mcp/runtime-bridge/python-runtime.mjs";
import { readProjectAsset } from "../mcp/project-asset.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = process.argv[2]?.trim();
const workspaceConfig = process.argv[3]?.trim();
const initialSpace = process.argv[4]?.trim() || "overview";
if (!projectRoot) {
  throw new Error("Usage: node scripts/create-widget-preview.mjs <managed-project-root> [workspace-config] [initial-space]");
}

const payload = await invokePythonBridge({
  operation: "get-project-snapshot",
  project_root: projectRoot,
  ...(workspaceConfig ? { workspace_config: workspaceConfig } : {}),
});
const widgetData = {
  surface: "workbench",
  snapshot: payload.snapshot,
  selectedProjectRoot: projectRoot,
  initialSpace,
  previewEvidence: {
    evidenceScope: "local-development-preview",
    proofEligible: false,
    realHostEvidence: false,
  },
};
const assetRefs = new Set();
function collectAssetRefs(value) {
  if (Array.isArray(value)) {
    value.forEach(collectAssetRefs);
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    if (
      typeof child === "string" &&
      (key.endsWith("_ref") || key === "asset_ref") &&
      /\.(png|jpe?g|webp|gif|svg)$/i.test(child)
    ) {
      assetRefs.add(child);
    }
    collectAssetRefs(child);
  }
}
collectAssetRefs(payload.snapshot.workspace);
const previewAssets = {};
for (const assetRef of assetRefs) {
  try {
    previewAssets[assetRef] = readProjectAsset({ projectRoot, assetRef });
  } catch (_error) {
    // A missing optional preview must not prevent the state-only workbench from opening.
  }
}
const serialized = JSON.stringify(widgetData).replaceAll("<", "\\u003c");
const serializedAssets = JSON.stringify(previewAssets).replaceAll("<", "\\u003c");
const html = await readFile(path.join(root, "widget", "dist", "index.html"), "utf8");
const previewHtml = html.replace(
  /<script\b[^>]*>/i,
  (openingTag) => `<script>window.__AI_PPT_ACCEPTANCE_START__=performance.now();window.__AI_PPT_PREVIEW__=${serialized};window.__AI_PPT_PREVIEW_ASSETS__=${serializedAssets};</script>${openingTag}`,
);
if (previewHtml === html) {
  throw new Error("Built widget did not contain an inline script insertion point.");
}

const outputDirectory = path.resolve(
  process.env.AI_PPT_PREVIEW_OUTPUT_DIR?.trim() || path.join(root, "output", "playwright"),
);
await mkdir(outputDirectory, { recursive: true });
const outputPath = path.join(outputDirectory, "ai-ppt-workbench-preview.html");
await writeFile(outputPath, previewHtml, "utf8");
process.stdout.write(`${outputPath}\n`);
