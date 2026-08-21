import { describe, expect, it } from "vitest";

import type { VisualReviewProjection } from "../types/visual-review";
import { toVisualReviewPageViewModel } from "./visual-review-page-view-model";

function projection(): VisualReviewProjection {
  return {
    project_id: "p1",
    project_name: "测试项目",
    review_type: "visual-professional",
    review_session_id: "visual-session-1",
    review_session: { internal_only: "must-not-reach-react" },
    source_version: "visual-v1",
    revision: 8,
    authoritative_revision: 9,
    visual_contract_ref: "artifact://visual-contract/" + "a".repeat(64),
    deck_design_system_ref: "artifact://deck-design-system/" + "b".repeat(64),
    deck_design_system: {
      production_route: "strict-B",
      theme_proposition: "克制、证据清楚",
      color_tokens: { accent: "#234B3D" },
      typography_tokens: { title: "32pt" },
      future_backend_governance: { must_not_render: true },
    },
    anchor_slide_set_ref: "artifact://anchor-slide-set/" + "c".repeat(64),
    anchors: ["S01", "S02", "S03"].map((slide_id) => ({
      slide_id,
      current_asset_ref: `review-assets/anchors/${slide_id}.png`,
      previous_asset_ref: "",
    })),
    anchor_identity: {
      visual_contract_set_ref: "artifact://visual-contract-set/" + "d".repeat(64),
      slide_ids: ["S01", "S02", "S03"],
      selection_reason: "覆盖问题、方案和证据页",
      native_first_frozen: true,
      native_first_pptx_ref: "artifact://native-pptx/" + "e".repeat(64),
      pptx_sha256: "f".repeat(64),
      editability_evidence_refs: ["artifact://editability-evidence/" + "1".repeat(64)],
      preflight_render_refs: ["artifact://preflight-render/" + "2".repeat(64)],
      render_assets: ["S01", "S02", "S03"].map((slide_id) => ({
        slide_id,
        current_asset_ref: `review-assets/anchors/${slide_id}.png`,
        previous_asset_ref: "",
      })),
    },
    slide_visual_contracts: [{
      slide_id: "S01",
      order: 1,
      neutral_title: "经营协同仍有断点",
      page_family: "问题诊断页",
      page_task: "说明当前问题",
      core_claim: "业务断点需要被看见",
      visible_copy_blocks: [{ block_id: "B01", text: "页面可见文案" }],
      speaker_notes: "讲解备注",
      evidence_bindings: [{ source_ref: "source-1" }],
      communication_goal: "建立问题共识",
      composition_intent: "左事实、右因果链",
      information_hierarchy: "标题—事实—建议",
      reading_order: ["标题", "事实", "建议"],
      regions: ["标题区", "正文区"],
      object_relationships: ["事实支持建议"],
      diagram_chart_table_treatment: "原生对象",
      image_selection_and_crop: "无图",
      color_application: "单一强调色",
      typography_application: "层级清晰",
      native_bitmap_routing: "原生优先",
      editability_requirements: "可编辑",
      fallbacks: ["保留原生结构"],
      acceptance_criteria: ["无溢出"],
      identity_labels: ["方案建议"],
      analysis_or_proposal_blocks: [{ internal: true }],
      solution_mapping_refs: ["mapping-1"],
      reading_quality: { internal: true },
      material_mode: "proposal-led",
      future_backend_governance: { must_not_render: true },
    }],
    anchor_feedback_batch_ref: null,
    anchor_feedback_batch: null,
    contract_review_marks_ref: null,
    contract_review_marks: null,
    gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
    host_submission_capability: "unknown",
    ai_receipt_capability: "unknown",
  };
}

describe("VisualReviewPageViewModel", () => {
  it("closes the React contract and normalizes compatibility fields", () => {
    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: projection(),
    });

    expect(viewModel.review).not.toHaveProperty("review_session");
    expect(viewModel.review).not.toHaveProperty("gate_status");
    expect(viewModel.review.deck_design_system).not.toHaveProperty("future_backend_governance");
    expect(viewModel.review.anchor_identity).toEqual({
      slide_ids: ["S01", "S02", "S03"],
      selection_reason: "覆盖问题、方案和证据页",
      native_first_frozen: true,
    });
    expect(viewModel.review.slide_visual_contracts[0]).toMatchObject({
      core_claim: "业务断点需要被看见",
      visible_copy: ["页面可见文案"],
      source_refs: ["source-1"],
      anchor_title: "经营协同仍有断点",
      validation_purpose: "说明当前问题",
    });
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("identity_labels");
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("analysis_or_proposal_blocks");
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("future_backend_governance");
  });

  it("keeps explicit empty visible-copy blocks ahead of the legacy frozen-copy fallback", () => {
    const input = projection();
    input.slide_visual_contracts[0] = {
      ...input.slide_visual_contracts[0],
      visible_copy_blocks: [],
      frozen_copy: ["legacy"],
    };

    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    expect(viewModel.review.slide_visual_contracts[0].visible_copy).toEqual([]);
  });
});
