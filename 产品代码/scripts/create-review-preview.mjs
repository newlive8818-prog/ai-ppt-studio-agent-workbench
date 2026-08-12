import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { invokePythonBridge } from "../mcp/runtime-bridge/python-runtime.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = process.argv[2]?.trim();
const workspaceConfig = process.argv[3]?.trim();
const reviewType = process.argv[4]?.trim() || "content";
if (!projectRoot || !["content", "visual"].includes(reviewType)) {
  throw new Error("Usage: node scripts/create-review-preview.mjs <managed-project-root> [workspace-config] <content|visual>");
}

const payload = await invokePythonBridge({
  operation: "get-review-projection",
  project_root: projectRoot,
  review_type: reviewType,
  ...(workspaceConfig ? { workspace_config: workspaceConfig } : {}),
});
const widgetData = {
  surface: "review",
  selectedProjectRoot: projectRoot,
  snapshotRevision: payload.snapshot_revision,
  review: payload.review,
  previewEvidence: {
    evidenceScope: "local-development-preview",
    proofEligible: false,
    realHostEvidence: false,
  },
};
const serialized = JSON.stringify(widgetData).replaceAll("<", "\\u003c");
const html = await readFile(path.join(root, "widget", "dist", "index.html"), "utf8");
const previewHtml = html.replace(
  /<script\b[^>]*>/i,
  (openingTag) => `<script>window.__AI_PPT_ACCEPTANCE_START__=performance.now();window.__AI_PPT_PREVIEW__=${serialized};</script>${openingTag}`,
);
if (previewHtml === html) {
  throw new Error("Built widget did not contain an inline script insertion point.");
}
const outputDirectory = path.resolve(
  process.env.AI_PPT_PREVIEW_OUTPUT_DIR?.trim() || path.join(root, "output", "playwright"),
);
await mkdir(outputDirectory, { recursive: true });
const outputPath = path.join(outputDirectory, `ai-ppt-${reviewType}-review-preview.html`);
await writeFile(outputPath, previewHtml, "utf8");
process.stdout.write(`${outputPath}\n`);
