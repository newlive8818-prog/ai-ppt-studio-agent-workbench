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
const contentFixture = JSON.parse(
  await readFile(path.join(root, "widget", "src", "__fixtures__", "content-sidebar-review.json"), "utf8"),
);
collectAssetRefs(payload.snapshot.workspace);
collectAssetRefs(contentFixture);
const previewAssets = {};
for (const assetRef of assetRefs) {
  try {
    previewAssets[assetRef] = readProjectAsset({ projectRoot, assetRef });
  } catch (_error) {
    // A missing optional preview must not prevent the state-only workbench from opening.
  }
}
const serializedAssets = JSON.stringify(previewAssets).replaceAll("<", "\\u003c");
const html = await readFile(path.join(root, "widget", "dist", "index.html"), "utf8");
const outputDirectory = path.resolve(
  process.env.AI_PPT_PREVIEW_OUTPUT_DIR?.trim() || path.join(root, "output", "playwright"),
);
await mkdir(outputDirectory, { recursive: true });

function injectPreview(contentReviewProjection, scenario, fixtureMode = false) {
  const contentSerialized = JSON.stringify(contentReviewProjection || null).replaceAll("<", "\\u003c");
  const scenarioSerialized = JSON.stringify(scenario || "").replaceAll("<", "\\u003c");
  const data = fixtureMode
    ? {
        ...widgetData,
        previewEvidence: {
          evidenceScope: "deterministic-contract-fixture",
          proofEligible: false,
          realHostEvidence: false,
          evidenceIdentity: "deterministic-contract-fixture-not-real-project-proof",
        },
      }
    : widgetData;
  const dataSerialized = JSON.stringify(data).replaceAll("<", "\\u003c");
  return html.replace(
    /<script\b[^>]*>/i,
    (openingTag) => `<script>window.__AI_PPT_ACCEPTANCE_START__=performance.now();window.__AI_PPT_PREVIEW__=${dataSerialized};window.__AI_PPT_PREVIEW_ASSETS__=${serializedAssets};window.__AI_PPT_CONTENT_REVIEW_PREVIEW__=${contentSerialized};window.__AI_PPT_CONTENT_REVIEW_PROJECT_ROOT__=${JSON.stringify(projectRoot).replaceAll("<", "\\u003c")};window.__AI_PPT_CONTENT_REVIEW_SCENARIO__=${scenarioSerialized};window.__AI_PPT_PREVIEW_CALLS__={};</script>${openingTag}`,
  );
}

async function writePreview(name, projection, scenario, fixtureMode = false) {
  const previewHtml = injectPreview(projection, scenario, fixtureMode);
  if (previewHtml === html) throw new Error("Built widget did not contain an inline script insertion point.");
  const outputPath = path.join(outputDirectory, name);
  await writeFile(outputPath, previewHtml, "utf8");
  return outputPath;
}

function completedState(selected, index) {
  const comments = {
    modify: "请补充问题到方案的跨页衔接，并改写本页第二段文字。",
    evidence: "当前判断缺少客户实际流转记录，请补充或降级为待联合验证。",
    "merge-or-delete": "建议与后一页合并，保留材料边界与验证动作。",
  };
  return {
    selected,
    comment: selected === "approved" ? "" : `${comments[selected]}（第 ${index + 1} 页）`,
    completed: true,
    saved: true,
    frozen: false,
  };
}

function deck(count, mode = "empty") {
  const projection = structuredClone(contentFixture);
  const templates = projection.slides;
  projection.slides = Array.from({ length: count }, (_, index) => {
    const slide = structuredClone(templates[index % templates.length]);
    const serial = String(index + 1).padStart(2, "0");
    slide.slide_id = `S${serial}`;
    slide.order = index + 1;
    slide.section_id = `C${String(Math.floor(index / 6) + 1).padStart(2, "0")}`;
    slide.neutral_title = `${slide.neutral_title} · 第 ${index + 1} 页`;
    const copyBlockIds = new Map(
      slide.visible_copy_blocks.map((block, blockIndex) => [block.block_id, `${slide.slide_id}-C${blockIndex + 1}`]),
    );
    slide.visible_copy_blocks = slide.visible_copy_blocks.map((block, blockIndex) => ({
      ...block,
      block_id: `${slide.slide_id}-C${blockIndex + 1}`,
      text: `${block.text} 本段属于第 ${index + 1} 页的完整可见内容，不因长文档验收而截断。`,
    }));
    slide.evidence_bindings = slide.evidence_bindings.map((binding, bindingIndex) => ({
      ...binding,
      binding_id: `EV-${slide.slide_id}-${bindingIndex + 1}`,
      supports_block_refs: binding.supports_block_refs.map((blockId) => copyBlockIds.get(blockId) || blockId),
    }));
    slide.speaker_notes = `${slide.speaker_notes} 第 ${index + 1} 页逐字稿完整保留。`;
    slide.previous_relation = index === 0 ? "从封面与任务进入当前业务事项。" : `承接第 ${index} 页并继续当前论证。`;
    slide.next_relation = index === count - 1 ? "收束为联合验证与下一步工作。" : `进入第 ${index + 2} 页的下一项业务问题。`;
    if (mode === "complete" || (mode === "mixed-23" && index < 23)) {
      const decisions = ["approved", "modify", "evidence", "merge-or-delete"];
      slide.decision_state = completedState(decisions[index % decisions.length], index);
    } else {
      slide.decision_state = { selected: "", comment: "", completed: false, saved: false, frozen: false };
    }
    return slide;
  });
  projection.chapters = Array.from(new Map(projection.slides.map((slide) => [slide.section_id, {
    section_id: slide.section_id,
    title: `第 ${Number(slide.section_id.slice(1))} 章`,
    first_slide_id: slide.slide_id,
  }])).values());
  const completed = projection.slides.filter((slide) => slide.decision_state.completed).length;
  projection.review_progress = {
    total: count,
    completed,
    remaining: count - completed,
    saved_comment_count: projection.slides.filter((slide) => slide.decision_state.comment).length,
    next_incomplete_slide_id: projection.slides.find((slide) => !slide.decision_state.completed)?.slide_id || "",
    counts: {
      approved: projection.slides.filter((slide) => slide.decision_state.selected === "approved").length,
      modify: projection.slides.filter((slide) => slide.decision_state.selected === "modify").length,
      evidence: projection.slides.filter((slide) => slide.decision_state.selected === "evidence").length,
      merge_or_delete: projection.slides.filter((slide) => slide.decision_state.selected === "merge-or-delete").length,
    },
  };
  return projection;
}

const outputPath = await writePreview(
  "ai-ppt-workbench-preview.html",
  contentFixture,
  "local-development-preview",
  false,
);
if (process.env.AI_PPT_CONTENT_REVIEW_PREVIEWS === "1") {
  const progress = (phase) => ({
    display_policy: "content-sidebar-progress",
    phase,
    project_id: contentFixture.project_id,
    revision: contentFixture.revision,
    mission_summary: contentFixture.mission_summary,
    next_action: "continue-content-production",
  });
  const submitted = deck(24, "complete");
  submitted.phase = "review-batch-submitted";
  submitted.review_session = {
    ...submitted.review_session,
    status: "submitted",
    submitted_at: "2026-08-24T10:02:00Z",
  };
  submitted.slides.forEach((slide) => { slide.decision_state.frozen = true; });
  const planned = structuredClone(submitted);
  planned.phase = "batch-plan-proposed";
  planned.current_plan = {
    plan_ref: "artifact://content-batch-revision-plan/deterministic-proposed",
    confirmation_ref: "",
    status: "proposed",
    requires_blueprint_revision: true,
  };
  const newVersion = deck(24, "empty");
  newVersion.source_version = "artifact://reading-deck-blueprint/content-v4";
  newVersion.revision = 58;
  newVersion.previous_round = {
    source_version: contentFixture.source_version,
    review_batch_ref: "artifact://content-review-batch/prior-submitted",
    revision_plan_ref: "artifact://content-batch-revision-plan/prior-confirmed",
    plan_confirmation_ref: "artifact://content-batch-revision-plan-confirmation/prior",
    result: "新版本已生成，全部页面从零复审。",
  };
  const scenarios = [
    ["content-review-producing.html", progress("content-producing"), "content-producing"],
    ["content-review-hard-gate.html", progress("content-hard-gate-review"), "content-hard-gate-review"],
    ["content-review-hard-gate-failed.html", progress("content-hard-gate-review"), "content-hard-gate-failed"],
    ["content-review-hard-gate-repaired.html", progress("content-hard-gate-review"), "content-hard-gate-repaired"],
    ["content-review-ready-10.html", deck(10), "ready-10"],
    ["content-review-mixed-24.html", deck(24, "mixed-23"), "mixed-decisions-24"],
    ["content-review-ready-24.html", deck(24, "complete"), "ready-24"],
    ["content-review-long-60.html", deck(60), "long-review-60"],
    ["content-review-save-failure.html", deck(10), "save-failure"],
    ["content-review-source-conflict.html", deck(10), "source-conflict"],
    ["content-review-submitted-frozen.html", submitted, "submitted-frozen"],
    ["content-review-plan-proposed.html", planned, "plan-proposed"],
    ["content-review-new-version-zero.html", newVersion, "new-version-zero-decisions"],
  ];
  for (const [name, projection, scenario] of scenarios) {
    await writePreview(name, projection, scenario, true);
  }
}
process.stdout.write(`${outputPath}\n`);
