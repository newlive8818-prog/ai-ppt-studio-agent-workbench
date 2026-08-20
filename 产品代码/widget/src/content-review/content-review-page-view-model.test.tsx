import { expect, it } from "vitest";

import type { ContentReviewProjection, ContentReviewSlide } from "../types/content-review";
import {
  ContentReviewPageViewModelAdapterError,
  toContentReviewPageViewModel,
} from "./content-review-page-view-model";

type SlideWithCustomerJudgment = ContentReviewSlide & { customerJudgment?: string };

function projection(
  customerJudgment: string | null = "客户确认现状边界后，再判断是否进入联合方案验证。",
): ContentReviewProjection {
  const value: ContentReviewProjection = {
    project_id: "p1",
    review_type: "content-full-deck",
    review_session_id: "review-1",
    review_session: {},
    source_version: "content-v1",
    revision: 7,
    authoritative_revision: 8,
    reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    material_mode: "mixed-evidence",
    section_flow: ["现状判断"],
    slides: [{
      slide_id: "S01",
      order: 1,
      section_id: "problem",
      page_task: "确认当前流程断点及证据边界",
      reading_question: "现有材料能否支撑当前判断？",
      neutral_title: "当前流程断点与证据边界",
      visible_copy_blocks: [{
        block_id: "copy-1",
        text: "当前流程存在三个待核实断点。",
        identity: "来源事实",
      }],
      identity_labels: ["来源事实"],
      evidence_bindings: [{ source_ref: "internal-only" }],
      material_views: [{
        material_view_id: "S01-M01",
        source_ref: "internal-source",
        asset_ref: "review-assets/content/S01-M01.png",
        source_file_name: "客户材料.pptx",
        page_number: 3,
        region_label: "整页",
        purpose: "证明流程断点",
        treatment: "只读呈现",
        evidence_identity: "来源事实",
      }],
      analysis_or_proposal_blocks: [{
        block_id: "analysis-1",
        text: "内部建议",
        identity: "方案建议",
      }],
      solution_mapping_refs: ["mapping-1"],
      previous_relation: "",
      next_relation: "进入方案验证",
      speaker_notes: "内部演讲备注",
      reading_quality: {
        independently_readable: true,
        information_density: "moderate",
        review_note: "内部检查",
      },
      material_mode: "mixed-evidence",
    }],
    decisions: [],
    progress: { completed: 0, total: 1, remaining: 1, unsaved: 0 },
    batch: null,
    revision_plan: null,
    content_acceptance_ref: `artifact://content-acceptance/${"c".repeat(64)}`,
  };
  if (customerJudgment !== null) {
    Object.defineProperty(value.slides[0] as SlideWithCustomerJudgment, "customerJudgment", {
      configurable: true,
      enumerable: true,
      value: customerJudgment,
      writable: true,
    });
  }
  return value;
}

function collectKeys(value: unknown, keys = new Set<string>()): Set<string> {
  if (!value || typeof value !== "object") return keys;
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, keys));
    return keys;
  }
  Object.entries(value).forEach(([key, item]) => {
    keys.add(key);
    collectKeys(item, keys);
  });
  return keys;
}

it("projects only the accepted content review frontend contract", () => {
  const viewModel = toContentReviewPageViewModel(projection());

  expect(Object.keys(viewModel).sort()).toEqual([
    "authoritativeRevision",
    "availableActions",
    "batchState",
    "progress",
    "projectId",
    "projectLabel",
    "readingBlueprintRef",
    "reviewSessionId",
    "revision",
    "sections",
    "slides",
    "sourceVersion",
  ].sort());
  expect(Object.keys(viewModel.slides[0]).sort()).toEqual([
    "customerJudgment",
    "draftContent",
    "localDraftState",
    "materialVisuals",
    "neutralTitle",
    "order",
    "pageGoal",
    "readingQuestion",
    "savedDecision",
    "sectionId",
    "slideId",
  ].sort());
  expect(viewModel.slides[0]).toMatchObject({
    slideId: "S01",
    pageGoal: "确认当前流程断点及证据边界",
    customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
    readingQuestion: "现有材料能否支撑当前判断？",
    draftContent: {
      title: "当前流程断点与证据边界",
      blocks: [{
        blockId: "copy-1",
        type: "paragraph",
        text: "当前流程存在三个待核实断点。",
      }],
    },
    materialVisuals: [{
      visualId: "S01-M01",
      assetRef: "review-assets/content/S01-M01.png",
      altText: "第 1 页《当前流程断点与证据边界》页面画面 1",
    }],
  });
});

it("does not expose rejected governance or material metadata fields", () => {
  const keys = collectKeys(toContentReviewPageViewModel(projection()));
  for (const field of [
    "analysis_or_proposal_blocks",
    "identity",
    "identity_labels",
    "evidence_bindings",
    "solution_mapping_refs",
    "previous_relation",
    "next_relation",
    "speaker_notes",
    "reading_quality",
    "source_file_name",
    "page_number",
    "region_label",
    "purpose",
    "treatment",
    "evidence_identity",
    "source_ref",
  ]) expect(keys).not.toContain(field);
});

it("preserves stable review identity and initializes frontend state without mutating input", () => {
  const input = projection();
  input.decisions = [{
    page_decision_id: "decision-1",
    project_id: "p1",
    review_session_id: "review-1",
    source_version: "content-v1",
    reading_blueprint_ref: input.reading_blueprint_ref,
    slide_id: "S01",
    slide_order: 1,
    slide_title_snapshot: "当前流程断点与证据边界",
    decision: "modify",
    comment: "请补充现状依据。",
    status: "completed",
    saved_at: "2026-08-20T09:00:00+08:00",
    supersedes_decision_ref: "",
  }];
  input.progress = { completed: 1, total: 1, remaining: 0, unsaved: 0 };
  input.batch = { status: "submitted" };
  const before = structuredClone(input);

  const viewModel = toContentReviewPageViewModel(input);

  expect(viewModel).toMatchObject({
    projectId: "p1",
    projectLabel: "p1",
    reviewSessionId: "review-1",
    readingBlueprintRef: input.reading_blueprint_ref,
    sourceVersion: "content-v1",
    revision: 7,
    authoritativeRevision: 8,
    progress: { completed: 1, total: 1, remaining: 0, unsaved: 0 },
    batchState: "submitted",
    availableActions: { savePageDecision: false, submitReviewBatch: false },
    sections: [{ sectionId: "problem", title: "现状判断", slideIds: ["S01"] }],
  });
  expect(viewModel.slides[0].savedDecision).toEqual(input.decisions[0]);
  expect(viewModel.slides[0].savedDecision).not.toBe(input.decisions[0]);
  expect(viewModel.slides[0].localDraftState).toEqual({
    decision: "modify",
    comment: "请补充现状依据。",
    dirty: false,
  });
  expect(input).toEqual(before);
});

it.each([null, "", " 未去除空白 "])(
  "fails when customerJudgment is not an authoritative nonblank value: %s",
  (customerJudgment) => {
    const input = projection(customerJudgment);
    expect(() => toContentReviewPageViewModel(input)).toThrow(ContentReviewPageViewModelAdapterError);
    try {
      toContentReviewPageViewModel(input);
    } catch (error) {
      expect(error).toMatchObject({
        code: "CONTENT_REVIEW_CUSTOMER_JUDGMENT_MISSING",
        slideId: "S01",
        fieldPath: "slides[0].customerJudgment",
      });
      expect(String(error)).not.toContain(input.slides[0].neutral_title);
      expect(String(error)).not.toContain(input.slides[0].reading_question);
      expect(String(error)).not.toContain(input.slides[0].page_task);
    }
  },
);

it("rejects inherited or accessor-backed customerJudgment without invoking a getter", () => {
  const inherited = projection(null);
  Object.setPrototypeOf(inherited.slides[0], { customerJudgment: "继承值" });
  expect(() => toContentReviewPageViewModel(inherited)).toThrow(ContentReviewPageViewModelAdapterError);

  const accessor = projection(null);
  Object.defineProperty(accessor.slides[0], "customerJudgment", {
    enumerable: true,
    get() { throw new Error("getter must not run"); },
  });
  expect(() => toContentReviewPageViewModel(accessor)).toThrow(ContentReviewPageViewModelAdapterError);
});
