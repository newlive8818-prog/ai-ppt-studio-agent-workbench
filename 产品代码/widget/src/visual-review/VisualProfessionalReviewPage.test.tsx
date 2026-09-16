import { readFileSync } from "node:fs";

import { StrictMode, useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { HostBridge } from "../types/host";
import type {
  AnchorFeedbackBatch,
  VisualContractReviewMarkSet,
  VisualReviewProjection,
  VisualReviewSurfaceData as VisualReviewProjectionSurfaceData,
} from "../types/visual-review";
import { ReviewSurfaceRouter } from "../ReviewSurfaceRouter";
import {
  createReviewDraftContext,
  createReviewDraftEnvelope,
  reviewDraftStorageKey,
  type AnchorFeedbackComposerState,
  type AnchorFeedbackDraftState,
  type ContractMarkComposerState,
  type ContractMarkDraftState,
  type VisualReviewDraftUi,
} from "../review-draft/reviewDraftStore";
import { AnchorResultsView } from "./AnchorResultsView";
import { REVIEW_WRITE_DEADLINE_MS } from "./review-write-deadline";
import { VisualContractView } from "./VisualContractView";
import { validateInitialVisualContractMarkSet } from "./visual-contract-mark-validation";
import { VisualProfessionalReviewPage } from "./VisualProfessionalReviewPage";
import { deriveVisualReceiptFacts } from "./visual-receipt-facts";
import {
  toVisualReviewPageViewModel,
  type VisualReviewPageViewModel,
} from "./visual-review-page-view-model";

type VisualReviewSurfaceData = VisualReviewPageViewModel;

const VISUAL_REVIEW_CSS = readFileSync(
  "widget/src/styles/visual-review.css",
  "utf8",
);
const VISUAL_CONTRACT_REF = "artifact://visual-contract/" + "a".repeat(64);
const VISUAL_BRIEF_REF = "artifact://visual-brief/" + "9".repeat(64);
const DECK_DESIGN_SYSTEM_REF = "artifact://deck-design-system/" + "b".repeat(64);
const ANCHOR_SLIDE_SET_REF = "artifact://anchor-slide-set/" + "c".repeat(64);
const NEXT_VISUAL_CONTRACT_REF = "artifact://visual-contract/" + "2".repeat(64);
const NEXT_ANCHOR_SLIDE_SET_REF = "artifact://anchor-slide-set/" + "3".repeat(64);
const ANCHOR_FEEDBACK_BATCH_REF = "artifact://visual-anchor-feedback-batch/" + "4".repeat(64);
const CONTRACT_MARK_SET_REF = "artifact://visual-contract-review-mark-set/" + "5".repeat(64);

class TestPointerEvent extends MouseEvent {
  pointerId: number;
  isPrimary: boolean;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId || 0;
    this.isPrimary = init.isPrimary ?? true;
  }
}

beforeEach(() => {
  Object.defineProperty(window, "PointerEvent", { configurable: true, value: TestPointerEvent });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  document.body.style.overflow = "";
  Object.defineProperty(window, "scrollX", { configurable: true, value: 0 });
  Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  Reflect.deleteProperty(window, "PointerEvent");
});

function visualData(
  previousAssets: Record<string, string> = {},
  anchorFeedbackBatch: AnchorFeedbackBatch | null = null,
): VisualReviewSurfaceData {
  return toVisualReviewPageViewModel({
    surface: "review",
    selectedProjectRoot: "/managed/project",
    snapshotRevision: 12,
    review: {
      project_id: "p1",
      project_name: "测试项目",
      review_type: "visual-professional",
      review_session_id: "visual-session-1",
      review_session: {},
      source_version: "visual-v1",
      revision: 11,
      authoritative_revision: 12,
      visual_contract_ref: VISUAL_CONTRACT_REF,
      visual_brief_ref: VISUAL_BRIEF_REF,
      visual_brief: {
        design_proposition: "可信、克制、有清晰视觉焦点",
        audience_fit: "面向经营与数字化决策者的阅读优先汇报",
        decision_task: "判断是否进入一期联合验证",
        design_stance: "证据优先，关系驱动，不用装饰制造专业感",
        emotional_boundary: "冷静、可信，不煽情",
        brand_boundary: "尊重客户品牌，不使用泛科技蓝紫模板",
        density_strategy: "关键结论疏，证据页中密度",
        narrative_rhythm: "章节聚焦—证据展开—方案收束",
        imagery_strategy: "图片必须承担证据或语境任务",
        diagram_strategy: "关系语义决定图示，不套固定图形",
        powerpoint_constraints: "事实文字、关系和数字保持原生可编辑",
        forbidden_patterns: ["平均卡片墙", "无意义科技装饰"],
        five_second_test_contract: {
          prompt: "五秒后隐藏页面并记录第一判断",
          expected_judgment: "读者形成与页面合同一致的核心判断",
          record_fields: [
            "first_noticed_object",
            "perceived_message",
            "perceived_relationship",
            "next_reading_step",
            "misdirection",
          ],
        },
        design_philosophy_refs: ["阅读顺序与章节结构聚焦"],
      },
      deck_design_system_ref: DECK_DESIGN_SYSTEM_REF,
      deck_design_system: {
        theme_proposition: "克制、证据清楚的售前阅读系统",
        typography_tokens: { title: "32pt", body: "16pt" },
        color_tokens: { ink: "#1D2421", accent: "#234B3D" },
        composition_grammar: "正文优先，证据侧置",
        page_families: ["问题", "方案", "证据"],
        density_rhythm: ["low", "medium", "pause"],
        cross_slide_rhythm_rules: ["相邻页面避免重复同一轮廓"],
        emphasis_budget: {
          max_primary_focal_points_per_slide: 1,
          max_accent_color_roles: 2,
          consecutive_high_density_slide_limit: 2,
        },
        imagery_strategy: "证据和语境优先",
        image_language: "图片只承担证据、解释或语境任务",
        diagram_strategy: "原生关系图优先",
        diagram_language: "连接器必须表达明确业务语义",
        table_strategy: "只保留支持判断的关键列",
        editability_rules: ["正文、数字、图形和连接器原生可编辑"],
        accessibility_rules: ["保持正文与背景对比度"],
        forbidden_patterns: ["整页位图"],
        five_second_test_rules: ["第一眼能识别页面主关系"],
        anchor_specification: "三页锚点覆盖问题、方案和证据家族",
        production_route: "strict-B",
        fallback_fonts: { macOS: "PingFang SC", Windows: "Microsoft YaHei" },
      },
      anchor_slide_set_ref: ANCHOR_SLIDE_SET_REF,
      anchors: ["S01", "S02", "S03"].map((slide_id) => ({
        slide_id,
        current_asset_ref: `review-assets/anchors/${slide_id}-current.png`,
        previous_asset_ref: previousAssets[slide_id] || "",
      })),
      anchor_identity: {
        visual_contract_set_ref: "artifact://visual-contract-set/" + "e".repeat(64),
        slide_ids: ["S01", "S02", "S03"],
        selection_reason: "覆盖问题、方案和证据三类页面",
        native_first_frozen: true,
        native_first_pptx_ref: "artifact://native-pptx/" + "a".repeat(64),
        pptx_sha256: "b".repeat(64),
        editability_evidence_refs: [
          "artifact://editability-evidence/" + "c".repeat(64),
        ],
        preflight_render_refs: [
          "artifact://preflight-render/" + "d".repeat(64),
        ],
        render_assets: ["S01", "S02", "S03"].map((slide_id) => ({
          slide_id,
          current_asset_ref: `review-assets/anchors/${slide_id}-current.png`,
          previous_asset_ref: previousAssets[slide_id] || "",
        })),
      },
      slide_visual_contracts: [1, 2].map((order) => ({
        slide_id: `S0${order}`,
        order,
        ...(order === 1
          ? { neutral_title: "系统在线，经营仍然断裂" }
          : { title: "一期围绕经营闭环建设" }),
        page_family: order === 1 ? "问题诊断页" : "方案设计页",
        anchor_title: order === 1 ? "系统在线，经营仍然断裂" : "一期围绕经营闭环建设",
        validation_purpose: order === 1 ? "验证问题关系焦点" : "验证方案结构焦点",
        core_claim: `核心主张 ${order}`,
        visible_copy: [`页面可见文案 ${order}`],
        page_task: `页面任务 ${order}`,
        frozen_copy: `冻结正文 ${order}`,
        speaker_notes: `完整备注 ${order}`,
        source_refs: [`source-${order}`],
        communication_goal: `沟通目标 ${order}`,
        composition_intent: "左侧事实，右侧因果链",
        information_hierarchy: "标题—事实—建议",
        reading_order: ["标题", "事实", "建议"],
        regions: ["标题区", "正文区"],
        object_relationships: ["事实支持建议"],
        diagram_chart_table_treatment: "使用原生关系图表达主要关系",
        image_selection_and_crop: "本页不使用装饰图片",
        color_application: "强调色只用于视觉焦点",
        typography_application: "标题与证据正文形成清晰层级",
        native_bitmap_routing: "原生优先",
        editability_requirements: "文字、形状和连接器可独立编辑",
        fallbacks: ["缺图时保持原生结构"],
        acceptance_criteria: ["无溢出", "原生可编辑"],
        reader_judgment: `读者五秒内形成第 ${order} 页核心判断`,
        primary_relationship: order === 1 ? "causality" : "hierarchy",
        secondary_relationship: order === 1 ? "system-boundary" : null,
        visual_mechanism: "主次对象对照",
        focal_point: `第 ${order} 页视觉焦点`,
        asset_roles: [{
          asset_id: `fact-evidence-${order}`,
          role: "evidence",
          source_ref: `source-${order}`,
          narrative_task: "用事实对象支持页面判断",
          replaceable: false,
        }],
        forbidden_patterns: ["平均卡片阵列"],
        previous_rhythm_relation: order === 1 ? "承接章节聚焦" : "承接问题证据",
        next_rhythm_relation: order === 1 ? "转入方案收束" : "进入验证计划",
        text_density_budget: {
          max_body_lines: 8,
          max_text_blocks: 3,
          reduction_strategy: "先删解释性重复句",
        },
        powerpoint_implementation_requirements: {
          object_plan: [{
            role: "primary-subject",
            object_type: "native-shape",
            layer: "foreground",
            editability: "native-editable",
          }],
          connector_semantics: [{
            from_role: "facts",
            to_role: "judgment",
            meaning: "事实支持页面判断",
            direction: "forward",
            crossing_forbidden: true,
          }],
          layout_constraints: {
            entry_region: "left",
            focal_region: "center-right",
            minimum_clear_space: "one-body-line",
          },
          native_bitmap_routing: "事实、标签与关系原生",
          degradation_strategy: "复杂图像失败时保留原生主体与边界关系",
        },
        acceptance_evidence_plan: {
          automated_checks: ["native-object-routing", "overflow"],
          human_review_checks: ["five-second-judgment", "anti-pattern-review"],
          target_powerpoint_checks: ["font", "connector", "editability"],
          user_review_question: "五秒内是否先看到页面主张与支持关系？",
        },
      })),
      anchor_feedback_batch_ref: anchorFeedbackBatch ? ANCHOR_FEEDBACK_BATCH_REF : null,
      anchor_feedback_batch: anchorFeedbackBatch,
      contract_review_marks_ref: null,
      contract_review_marks: null,
      gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
      host_submission_capability: "unavailable",
      ai_receipt_capability: "unavailable",
    } as unknown as VisualReviewProjection,
  });
}

function secondModalVisualData(): VisualReviewSurfaceData {
  const data = visualData({ S02: "review-assets/anchors/S02-previous.png" });
  return {
    ...data,
    review: {
      ...data.review,
      project_id: "p2",
      project_name: "第二测试项目",
      review_session_id: "visual-session-2",
      anchors: [
        data.review.anchors[1],
        data.review.anchors[0],
        data.review.anchors[2],
      ],
    },
  };
}

function existingAnchorBatch(): AnchorFeedbackBatch {
  return {
    batch_id: "anchor-batch-existing",
    project_id: "p1",
    review_session_id: "visual-session-1",
    visual_contract_ref: VISUAL_CONTRACT_REF,
    deck_design_system_ref: DECK_DESIGN_SYSTEM_REF,
    anchor_slide_set_ref: ANCHOR_SLIDE_SET_REF,
    items: [{
      feedback_id: "existing-feedback-1",
      anchor_slide_id: "S02",
      anchor_artifact_ref: ANCHOR_SLIDE_SET_REF,
      normalized_region: { x: 0.1, y: 0.2, width: 0.3, height: 0.25 },
      comment: "保留证据，但降低视觉重量",
      order: 1,
      visual_source_version: "visual-v1",
      revision: 12,
      created_at: "2026-08-15T00:00:00Z",
      created_by: "user",
    }],
    source_version: "visual-v1",
    revision: 12,
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    immutable_after_submit: true,
    submitted_at: "2026-08-15T00:00:00Z",
    submitted_by: "user",
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function contractMarkResult(args: Record<string, unknown>) {
  const revision = Number(args.expectedRevision);
  const marks = structuredClone(args.marks as VisualContractReviewMarkSet["marks"]);
  const savedAt = marks.reduce(
    (latest, mark) => mark.created_at > latest ? mark.created_at : latest,
    marks[0]?.created_at || "1970-01-01T00:00:00Z",
  );
  return {
    mark_set_ref: CONTRACT_MARK_SET_REF,
    mark_set: {
      mark_set_id: "visual-marks-1",
      project_id: "p1",
      review_session_id: "visual-session-1",
      visual_contract_ref: VISUAL_CONTRACT_REF,
      source_version: "visual-v1",
      revision,
      marks,
      persistence_status: "saved" as const,
      host_notification_status: "not-requested" as const,
      ai_receipt_status: "pending" as const,
      saved_at: savedAt,
    },
    snapshot: { revision: revision + 1 },
  };
}

function contractDraft(
  comment: string,
  markId = "contract-mark-draft",
): ContractMarkDraftState {
  return {
    mark_id: markId,
    target_type: "text-range",
    slide_id: "S01",
    deck_section_id: "",
    target_key: "visible_copy",
    selected_text: "页面可见文案 1",
    context_before: "选中文本前文",
    context_after: "选中文本后文",
    comment,
    created_at: "2026-08-15T00:00:00Z",
  };
}

function contractComposer(
  comment: string,
  editingMarkId = "",
): ContractMarkComposerState {
  return {
    editing_mark_id: editingMarkId,
    target_type: "text-range",
    slide_id: "S01",
    deck_section_id: "",
    target_key: "visible_copy",
    selected_text: "页面可见文案 1",
    context_before: "选中文本前文",
    context_after: "选中文本后文",
    comment,
  };
}

function projectedContractMarkSet(revision = 20): VisualContractReviewMarkSet {
  return {
    mark_set_id: "visual-marks-grown-projection",
    project_id: "p1",
    review_session_id: "visual-session-1",
    visual_contract_ref: VISUAL_CONTRACT_REF,
    source_version: "visual-v1",
    revision,
    marks: [{
      mark_id: "authoritative-grown-mark",
      target_type: "contract-field",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "page_family",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "权威投影中的合同标记",
      visual_contract_ref: VISUAL_CONTRACT_REF,
      source_version: "visual-v1",
      revision,
      created_at: "2026-08-15T00:00:00Z",
      created_by: "user",
    }],
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    saved_at: "2026-08-16T00:00:00Z",
  };
}

function host(
  anchorBatchResponse?: (args: Record<string, unknown>) => Promise<unknown>,
  contractMarksResponse?: (args: Record<string, unknown>) => Promise<unknown>,
  recovery: {
    retryVisualHostNotification?: NonNullable<HostBridge["retryVisualHostNotification"]>;
    verifyVisualAiReceipt?: NonNullable<HostBridge["verifyVisualAiReceipt"]>;
  } = {},
) {
  const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
    if (name === "read_ai_ppt_project_asset") {
      return { asset: { assetRef: args.assetRef, mimeType: "image/png", dataBase64: "iVBORw0KGgo=", bytes: 8 } };
    }
    if (name === "submit_visual_anchor_feedback_batch") {
      if (anchorBatchResponse) return anchorBatchResponse(args);
      const items = args.feedback as AnchorFeedbackBatch["items"];
      const batch: AnchorFeedbackBatch = {
        batch_id: "anchor-batch-1", project_id: "p1", review_session_id: "visual-session-1",
        visual_contract_ref: VISUAL_CONTRACT_REF,
        deck_design_system_ref: DECK_DESIGN_SYSTEM_REF,
        anchor_slide_set_ref: ANCHOR_SLIDE_SET_REF, items,
        source_version: "visual-v1", revision: 12, persistence_status: "saved",
        host_notification_status: "not-requested", ai_receipt_status: "pending",
        immutable_after_submit: true, submitted_at: new Date().toISOString(), submitted_by: "user",
      };
      return { batch_ref: ANCHOR_FEEDBACK_BATCH_REF, batch, snapshot: { revision: 13 } };
    }
    if (name === "save_visual_contract_review_marks") {
      if (contractMarksResponse) return contractMarksResponse(args);
      return contractMarkResult(args);
    }
    throw new Error(`Unexpected tool ${name}`);
  });
  const bridge: HostBridge = {
    connect: vi.fn(async () => undefined),
    callTool: callTool as HostBridge["callTool"],
    ...recovery,
  };
  return { bridge, callTool };
}

function mockSlideRect() {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0, y: 0, top: 0, left: 0, right: 1000, bottom: 562,
    width: 1000, height: 562, toJSON: () => ({}),
  });
}

function visualDraftUi(overrides: Partial<VisualReviewDraftUi> = {}): VisualReviewDraftUi {
  return {
    view: "anchors",
    current_anchor_slide_id: null,
    anchor_feedback_drafts: [],
    anchor_feedback_composer: null,
    contract_mark_drafts: [],
    contract_mark_composer: null,
    anchor_logical_scroll: null,
    contract_logical_scroll: null,
    ...overrides,
  };
}

function seedVisualDraft(data: VisualReviewSurfaceData, ui: VisualReviewDraftUi) {
  const context = createReviewDraftContext(data);
  const key = reviewDraftStorageKey(context);
  window.sessionStorage.setItem(key, JSON.stringify(
    createReviewDraftEnvelope(context, ui, "2026-08-16T00:00:00Z"),
  ));
  return key;
}

function readVisualDraft(key: string): { ui: VisualReviewDraftUi } | null {
  const stored = window.sessionStorage.getItem(key);
  return stored ? JSON.parse(stored) as { ui: VisualReviewDraftUi } : null;
}

function anchorDraft(
  comment: string,
  slideId = "S01",
  feedbackId = `feedback-${slideId}`,
): AnchorFeedbackDraftState {
  return {
    feedback_id: feedbackId,
    anchor_slide_id: slideId,
    normalized_region: { x: 0.1, y: 0.2, width: 0.3, height: 0.25 },
    comment,
    created_at: "2026-08-15T00:00:00Z",
  };
}

function anchorComposer(
  comment: string,
  slideId = "S01",
  editingFeedbackId = "",
): AnchorFeedbackComposerState {
  return {
    anchor_slide_id: slideId,
    candidate_region: { x: 0.2, y: 0.15, width: 0.4, height: 0.35 },
    editing_feedback_id: editingFeedbackId,
    comment,
  };
}

function closedAnchorResult(
  args: Record<string, unknown>,
  data: VisualReviewSurfaceData,
  batchId = "anchor-batch-7c",
): {
  batch_ref: string;
  batch: AnchorFeedbackBatch;
  snapshot: { revision: number };
} {
  const revision = Number(args.expectedRevision);
  const items = structuredClone(args.feedback as AnchorFeedbackBatch["items"]);
  const submittedAt = items.reduce(
    (latest, item) => item.created_at > latest ? item.created_at : latest,
    items[0]?.created_at || "1970-01-01T00:00:00Z",
  );
  return {
    batch_ref: ANCHOR_FEEDBACK_BATCH_REF,
    batch: {
      batch_id: batchId,
      project_id: data.review.project_id,
      review_session_id: data.review.review_session_id,
      visual_contract_ref: data.review.visual_contract_ref,
      deck_design_system_ref: data.review.deck_design_system_ref,
      anchor_slide_set_ref: data.review.anchor_slide_set_ref,
      items,
      source_version: data.review.source_version,
      revision,
      persistence_status: "saved" as const,
      host_notification_status: "not-requested" as const,
      ai_receipt_status: "pending" as const,
      immutable_after_submit: true as const,
      submitted_at: submittedAt,
      submitted_by: "user",
    },
    snapshot: { revision: revision + 1 },
  };
}

function customPrototypeRecord(value: Record<string, unknown>): Record<string, unknown> {
  return Object.assign(Object.create({ custom: true }), value);
}

function inheritedExpectedRecord(
  value: Record<string, unknown>,
  inheritedField: string,
): Record<string, unknown> {
  const own: Record<string, unknown> = { ...value, camouflage: true };
  const inheritedValue = own[inheritedField];
  delete own[inheritedField];
  return Object.assign(Object.create({ [inheritedField]: inheritedValue }), own);
}

function symbolExtraRecord(value: Record<string, unknown>): Record<string, unknown> {
  const copy = { ...value };
  Object.defineProperty(copy, Symbol("unexpected"), { enumerable: true, value: true });
  return copy;
}

function accessorRecord(
  value: Record<string, unknown>,
  field: string,
): { value: Record<string, unknown>; getterReads: () => number } {
  let reads = 0;
  const copy = { ...value };
  Object.defineProperty(copy, field, {
    configurable: true,
    enumerable: true,
    get() {
      reads += 1;
      return value[field];
    },
  });
  return { value: copy, getterReads: () => reads };
}

function customPrototypeArray<T>(items: T[]): T[] {
  const copy = [...items];
  Object.setPrototypeOf(copy, Object.create(Array.prototype));
  return copy;
}

function accessorArray<T>(item: T): { value: T[]; getterReads: () => number } {
  let reads = 0;
  const array: T[] = [];
  Object.defineProperty(array, "0", {
    configurable: true,
    enumerable: true,
    get() {
      reads += 1;
      return item;
    },
  });
  return { value: array, getterReads: () => reads };
}

type AnchorResultAttack = (valid: Record<string, unknown>) => {
  result: unknown;
  getterReads: () => number;
};

const noGetterReads = () => 0;

const anchorResultAttacks: Array<[string, AnchorResultAttack]> = [
  ["ordinary-string batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "saved-anchor-batch" },
    getterReads: noGetterReads,
  })],
  ["wrong-kind batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "artifact://visual-contract/" + "4".repeat(64) },
    getterReads: noGetterReads,
  })],
  ["HTTP batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "https://example.test/visual-anchor-feedback-batch/" + "4".repeat(64) },
    getterReads: noGetterReads,
  })],
  ["non-64 batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "artifact://visual-anchor-feedback-batch/abc123" },
    getterReads: noGetterReads,
  })],
  ["uppercase-digest batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "artifact://visual-anchor-feedback-batch/" + "A".repeat(64) },
    getterReads: noGetterReads,
  })],
  ["malformed batch artifact ref", (valid) => ({
    result: { ...valid, batch_ref: "artifact:/visual-anchor-feedback-batch/" + "4".repeat(64) },
    getterReads: noGetterReads,
  })],
  ["custom-prototype result envelope", (valid) => ({
    result: customPrototypeRecord(valid),
    getterReads: noGetterReads,
  })],
  ["inherited expected result field", (valid) => ({
    result: inheritedExpectedRecord(valid, "batch"),
    getterReads: noGetterReads,
  })],
  ["accessor-backed result field", (valid) => {
    const attacked = accessorRecord(valid, "batch");
    return { result: attacked.value, getterReads: attacked.getterReads };
  }],
  ["symbol-keyed result extra", (valid) => ({
    result: symbolExtraRecord(valid),
    getterReads: noGetterReads,
  })],
  ["open result envelope", (valid) => ({
    result: { ...valid, unexpected: true },
    getterReads: noGetterReads,
  })],
  ["custom-prototype snapshot", (valid) => ({
    result: { ...valid, snapshot: customPrototypeRecord({ ...(valid.snapshot as object) }) },
    getterReads: noGetterReads,
  })],
  ["accessor-backed snapshot field", (valid) => {
    const attacked = accessorRecord({ ...(valid.snapshot as object) }, "revision");
    return { result: { ...valid, snapshot: attacked.value }, getterReads: attacked.getterReads };
  }],
  ["custom-prototype batch", (valid) => ({
    result: { ...valid, batch: customPrototypeRecord({ ...(valid.batch as object) }) },
    getterReads: noGetterReads,
  })],
  ["inherited expected batch field", (valid) => ({
    result: {
      ...valid,
      batch: inheritedExpectedRecord({ ...(valid.batch as object) }, "submitted_at"),
    },
    getterReads: noGetterReads,
  })],
  ["symbol-keyed batch extra", (valid) => ({
    result: { ...valid, batch: symbolExtraRecord({ ...(valid.batch as object) }) },
    getterReads: noGetterReads,
  })],
  ["open batch", (valid) => ({
    result: { ...valid, batch: { ...(valid.batch as object), unexpected: true } },
    getterReads: noGetterReads,
  })],
  ["custom-prototype items array", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    return {
      result: { ...valid, batch: { ...batch, items: customPrototypeArray([...(batch.items as unknown[])]) } },
      getterReads: noGetterReads,
    };
  }],
  ["sparse items array", (valid) => ({
    result: { ...valid, batch: { ...(valid.batch as object), items: new Array(1) } },
    getterReads: noGetterReads,
  })],
  ["accessor-backed items index", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const attacked = accessorArray((batch.items as unknown[])[0]);
    return {
      result: { ...valid, batch: { ...batch, items: attacked.value } },
      getterReads: attacked.getterReads,
    };
  }],
  ["symbol-keyed items extra", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as unknown[])];
    Object.defineProperty(items, Symbol("unexpected"), { enumerable: true, value: true });
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["custom-prototype item", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = customPrototypeRecord({ ...items[0] });
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["inherited expected item field", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = inheritedExpectedRecord({ ...items[0] }, "created_at");
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["accessor-backed item field", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    const attacked = accessorRecord({ ...items[0] }, "created_at");
    items[0] = attacked.value;
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: attacked.getterReads };
  }],
  ["open item", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = { ...items[0], unexpected: true };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["custom-prototype normalized region", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = {
      ...items[0],
      normalized_region: customPrototypeRecord({ ...(items[0].normalized_region as object) }),
    };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["inherited normalized-region field", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = {
      ...items[0],
      normalized_region: inheritedExpectedRecord(
        { ...(items[0].normalized_region as object) },
        "height",
      ),
    };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["accessor-backed normalized-region field", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    const attacked = accessorRecord({ ...(items[0].normalized_region as object) }, "x");
    items[0] = { ...items[0], normalized_region: attacked.value };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: attacked.getterReads };
  }],
  ["symbol-keyed normalized-region extra", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = {
      ...items[0],
      normalized_region: symbolExtraRecord({ ...(items[0].normalized_region as object) }),
    };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
  ["open normalized region", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const items = [...(batch.items as Record<string, unknown>[])];
    items[0] = {
      ...items[0],
      normalized_region: { ...(items[0].normalized_region as object), unexpected: true },
    };
    return { result: { ...valid, batch: { ...batch, items } }, getterReads: noGetterReads };
  }],
];

function makeRouterValid(data: VisualReviewSurfaceData): VisualReviewProjectionSurfaceData {
  const reviewSession = {
    review_session_id: data.review.review_session_id,
    review_type: "visual-professional",
    project_id: data.review.project_id,
    target_artifact_ref: data.review.visual_contract_ref,
    source_version: data.review.source_version,
    revision: data.review.revision,
    status: "ready",
    open_policy: "foreground-if-waiting",
    host_open_status: "not-requested",
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    created_at: "2026-08-15T00:00:00Z",
    last_opened_at: null,
    submitted_at: null,
  };
  return {
    ...data,
    review: {
      ...data.review,
      review_session: reviewSession,
      deck_design_system: {
        theme_proposition: "克制、证据清楚的售前阅读系统",
        composition_grammar: "正文优先，证据侧置",
        color_tokens: { ink: "#1D2421", accent: "#234B3D" },
        typography_tokens: { title: "32pt", body: "16pt" },
        page_families: ["问题", "方案", "证据"],
        density_rhythm: ["low", "medium", "pause"],
        cross_slide_rhythm_rules: ["相邻页面避免重复同一轮廓"],
        emphasis_budget: {
          max_primary_focal_points_per_slide: 1,
          max_accent_color_roles: 2,
          consecutive_high_density_slide_limit: 2,
        },
        imagery_strategy: "证据优先",
        image_language: "图片只承担证据、解释或语境任务",
        diagram_strategy: "原生图形优先",
        diagram_language: "连接器必须表达明确业务语义",
        table_strategy: "少量关键列",
        editability_rules: ["正文与图形可编辑"],
        accessibility_rules: ["保持对比度"],
        forbidden_patterns: ["整页位图"],
        five_second_test_rules: ["第一眼能识别页面主关系"],
        anchor_specification: "三页锚点覆盖主要页面家族",
        production_route: "strict-B",
      },
      slide_visual_contracts: data.review.slide_visual_contracts.map((contract, index) => ({
        ...contract,
        diagram_chart_table_treatment: "关系使用原生形状",
        image_selection_and_crop: "无图时保持原生结构",
        color_application: "中性底色配单一强调色",
        typography_application: "标题与正文层级分明",
        editability_requirements: "所有正文与图形可编辑",
        acceptance_criteria: [{
          criterion_id: `criterion-${index + 1}`,
          level: "must-follow",
          expected_outcome: "阅读顺序清晰且原生可编辑",
        }],
      })),
    },
  } as unknown as VisualReviewProjectionSurfaceData;
}

function mockVisualLogicalGeometry(options: {
  sticky?: boolean;
  headerBottom?: number;
  anchorTops?: Record<string, number>;
  contractTops?: Record<string, number>;
} = {}) {
  const {
    sticky = true,
    headerBottom = 80,
    anchorTops = { S02: 200 },
    contractTops = { S01: 300 },
  } = options;
  const rect = (top: number, bottom = top + 100): DOMRect => ({
    x: 0,
    y: top,
    top,
    left: 0,
    right: 1000,
    bottom,
    width: 1000,
    height: bottom - top,
    toJSON: () => ({}),
  });
  const getComputedStyle = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((element, pseudoElt) => {
    const style = getComputedStyle(element, pseudoElt);
    if (!(element instanceof HTMLElement) || !element.classList.contains("visual-professional-header")) {
      return style;
    }
    return new Proxy(style, {
      get(target, property) {
        if (property === "position") return sticky ? "sticky" : "static";
        const value = Reflect.get(target, property, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    });
  });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function getRect(this: HTMLElement) {
    if (this.classList.contains("visual-professional-header")) return rect(0, headerBottom);
    const anchorId = this.dataset.anchorLogicalObject;
    if (anchorId && Object.prototype.hasOwnProperty.call(anchorTops, anchorId)) return rect(anchorTops[anchorId]);
    const contractId = this.dataset.contractLogicalObject;
    if (contractId && Object.prototype.hasOwnProperty.call(contractTops, contractId)) return rect(contractTops[contractId]);
    return rect(500);
  });
}

function controlledAnimationFrames() {
  let nextId = 1;
  const callbacks = new Map<number, FrameRequestCallback>();
  const request = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    const id = nextId;
    nextId += 1;
    callbacks.set(id, callback);
    return id;
  });
  const cancel = vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
    callbacks.delete(id);
  });
  return {
    request,
    cancel,
    pendingIds: () => [...callbacks.keys()],
    runAll: () => {
      const scheduled = [...callbacks.entries()];
      callbacks.clear();
      scheduled.forEach(([, callback]) => callback(performance.now()));
    },
  };
}

async function readyActiveAnchor() {
  const image = await screen.findByRole("img", { name: /S0[1-3] 锚点页成果/ });
  fireEvent.load(image);
  return image;
}

async function addRegion(comment: string, start = [100, 100], end = [420, 280]) {
  await readyActiveAnchor();
  fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
  const canvas = screen.getByTestId("anchor-canvas");
  fireEvent.pointerDown(canvas, { pointerId: 1, button: 0, clientX: start[0], clientY: start[1], isPrimary: true });
  fireEvent.pointerMove(canvas, { pointerId: 1, clientX: end[0], clientY: end[1], isPrimary: true });
  fireEvent.pointerUp(canvas, { pointerId: 1, clientX: end[0], clientY: end[1], isPrimary: true });
  fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: comment } });
  fireEvent.click(screen.getByRole("button", { name: "加入本轮反馈" }));
}

function ControlledAnchorResults({
  data,
  bridge,
  revision,
  onRevision,
}: {
  data: VisualReviewSurfaceData;
  bridge: HostBridge;
  revision: number;
  onRevision: (revision: number) => void;
}) {
  const [drafts, setDrafts] = useState<AnchorFeedbackDraftState[]>([]);
  const [composer, setComposer] = useState<AnchorFeedbackComposerState | null>(null);
  const [currentSlideId, setCurrentSlideId] = useState(data.review.anchors[0]?.slide_id || "");
  return (
    <AnchorResultsView
      data={data}
      bridge={bridge}
      revision={revision}
      onRevision={onRevision}
      commandIdentity="direct-anchor-test"
      drafts={drafts}
      composer={composer}
      onSliceChange={(nextDrafts, nextComposer) => {
        setDrafts(nextDrafts);
        setComposer(nextComposer);
      }}
      onClearSlice={() => {
        setDrafts([]);
        setComposer(null);
      }}
      currentSlideId={currentSlideId}
      onCurrentSlideChange={setCurrentSlideId}
    />
  );
}

function ControlledVisualContract({
  data,
  bridge,
  revision,
  onRevision,
}: {
  data: VisualReviewSurfaceData;
  bridge: HostBridge;
  revision: number;
  onRevision: (revision: number) => void;
}) {
  const [drafts, setDrafts] = useState<ContractMarkDraftState[]>([]);
  const [composer, setComposer] = useState<ContractMarkComposerState | null>(null);
  return (
    <VisualContractView
      data={data}
      bridge={bridge}
      revision={revision}
      onRevision={onRevision}
      commandIdentity="direct-contract-test"
      drafts={drafts}
      composer={composer}
      onSliceChange={(nextDrafts, nextComposer) => {
        setDrafts(nextDrafts);
        setComposer(nextComposer);
      }}
      onClearSlice={() => {
        setDrafts([]);
        setComposer(null);
      }}
    />
  );
}

async function recoverPersistedComposer(comment = "恢复后仍应保留的当前输入") {
  await addRegion("已经加入的反馈");
  fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
  const canvas = screen.getByTestId("anchor-canvas");
  fireEvent.pointerDown(canvas, { pointerId: 91, button: 0, clientX: 120, clientY: 120, isPrimary: true });
  fireEvent.pointerMove(canvas, { pointerId: 91, clientX: 520, clientY: 320, isPrimary: true });
  fireEvent.pointerUp(canvas, { pointerId: 91, clientX: 520, clientY: 320, isPrimary: true });
  fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: comment } });
  const candidateStyle = document.querySelector<HTMLElement>(".anchor-region.candidate")?.getAttribute("style");

  fireEvent.error(screen.getByRole("img", { name: "S01 锚点页成果" }));
  fireEvent.click(screen.getByRole("button", { name: "预览暂不可读，点击重试" }));
  const reloaded = await screen.findByRole("img", { name: "S01 锚点页成果" });
  fireEvent.load(reloaded);
  return { canvas, candidateStyle, comment };
}

describe("visual professional review surface", () => {
  it("[7C A] restores one same-session view, current anchor, and two independent logical scrolls", async () => {
    const data = visualData();
    const key = seedVisualDraft(data, visualDraftUi({
      view: "contract",
      current_anchor_slide_id: "S02",
      anchor_logical_scroll: { object_id: "S02", offset: 40 },
      contract_logical_scroll: { object_id: "S01", offset: 70 },
    }));
    Object.defineProperty(window, "scrollX", { configurable: true, value: 23 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 100 });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    mockVisualLogicalGeometry();
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "完整视觉合同" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "S02 锚点页", hidden: true })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({
      behavior: "auto",
      left: 23,
      top: 390,
    }));

    fireEvent.click(screen.getByRole("tab", { name: "3 页锚点成果" }));
    await waitFor(() => expect(scrollTo).toHaveBeenLastCalledWith({
      behavior: "auto",
      left: 23,
      top: 260,
    }));
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(JSON.parse(window.sessionStorage.getItem(key) || "null").ui).toEqual(expect.objectContaining({
      view: "anchors",
      current_anchor_slide_id: "S02",
      anchor_logical_scroll: { object_id: "S02", offset: 40 },
      contract_logical_scroll: { object_id: "S01", offset: 70 },
    }));
  });

  it("binds a sticky-origin scroll rAF to anchors across a tab switch and preserves scrollX", () => {
    const data = visualData();
    const key = seedVisualDraft(data, visualDraftUi({
      view: "anchors",
      current_anchor_slide_id: "S01",
      anchor_logical_scroll: { object_id: "S01", offset: 10 },
      contract_logical_scroll: { object_id: "S01", offset: 73 },
    }));
    Object.defineProperty(window, "scrollX", { configurable: true, value: 23 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 100 });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    mockVisualLogicalGeometry({
      sticky: true,
      anchorTops: { S01: 20 },
      contractTops: { "deck-design-system": 300, S01: -50, S02: 400 },
    });
    const frames = controlledAnimationFrames();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    scrollTo.mockClear();

    fireEvent.scroll(window);
    expect(frames.request).toHaveBeenCalledTimes(1);
    expect(frames.pendingIds()).toEqual([1]);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    expect(scrollTo).toHaveBeenLastCalledWith({
      behavior: "auto",
      left: 23,
      top: 43,
    });
    act(() => frames.runAll());
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual(expect.objectContaining({
      view: "contract",
      anchor_logical_scroll: { object_id: "S01", offset: 60 },
      contract_logical_scroll: { object_id: "S01", offset: 73 },
    }));
    expect(frames.cancel).toHaveBeenCalledWith(1);
  });

  it("captures and restores a non-sticky scroll rAF origin without changing scrollX", () => {
    const data = visualData();
    const key = seedVisualDraft(data, visualDraftUi({
      view: "anchors",
      current_anchor_slide_id: "S01",
      anchor_logical_scroll: { object_id: "S01", offset: 10 },
      contract_logical_scroll: { object_id: "S01", offset: 25 },
    }));
    Object.defineProperty(window, "scrollX", { configurable: true, value: 37 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 100 });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    mockVisualLogicalGeometry({
      sticky: false,
      anchorTops: { S01: -35 },
      contractTops: { "deck-design-system": 400, S01: 200, S02: 500 },
    });
    const frames = controlledAnimationFrames();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    scrollTo.mockClear();

    fireEvent.scroll(window);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    expect(scrollTo).toHaveBeenLastCalledWith({
      behavior: "auto",
      left: 37,
      top: 325,
    });
    act(() => frames.runAll());
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual(expect.objectContaining({
      anchor_logical_scroll: { object_id: "S01", offset: 35 },
      contract_logical_scroll: { object_id: "S01", offset: 25 },
    }));
    expect(frames.cancel).toHaveBeenCalledWith(1);
  });

  it("does not rewrite an identical logical position on repeated scroll rAF captures", () => {
    const data = visualData();
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    mockVisualLogicalGeometry({ sticky: true, anchorTops: { S01: 20 } });
    const frames = controlledAnimationFrames();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    const toIsoString = vi.spyOn(Date.prototype, "toISOString")
      .mockReturnValueOnce("2026-08-16T00:00:01Z")
      .mockReturnValueOnce("2026-08-16T00:00:02Z");

    fireEvent.scroll(window);
    expect(frames.request).toHaveBeenCalledTimes(1);
    act(() => frames.runAll());
    fireEvent(window, new PageTransitionEvent("pagehide"));
    const firstSaved = window.sessionStorage.getItem(key);
    expect(firstSaved).not.toBeNull();
    expect(toIsoString).toHaveBeenCalledTimes(1);

    fireEvent.scroll(window);
    act(() => frames.runAll());
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(window.sessionStorage.getItem(key)).toBe(firstSaved);
    expect(toIsoString).toHaveBeenCalledTimes(1);
  });

  it.each(["pagehide", "visibilitychange to hidden", "unmount"] as const)(
    "captures the final logical scroll before the %s persistence flush and restores it",
    async (exitKind) => {
      const data = visualData();
      const key = seedVisualDraft(data, visualDraftUi({
        view: "anchors",
        current_anchor_slide_id: "S01",
        anchor_logical_scroll: { object_id: "S01", offset: 10 },
      }));
      Object.defineProperty(window, "scrollX", { configurable: true, value: 17 });
      Object.defineProperty(window, "scrollY", { configurable: true, value: 100 });
      const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
      mockVisualLogicalGeometry({ sticky: true, anchorTops: { S01: 20 } });
      const frames = controlledAnimationFrames();
      const { bridge } = host();
      const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
      await waitFor(() => expect(scrollTo).toHaveBeenCalled());
      scrollTo.mockClear();

      fireEvent.scroll(window);
      expect(frames.pendingIds()).toEqual([1]);

      if (exitKind === "pagehide") {
        fireEvent(window, new PageTransitionEvent("pagehide"));
        rendered.unmount();
      } else if (exitKind === "visibilitychange to hidden") {
        vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
        fireEvent(document, new Event("visibilitychange"));
        rendered.unmount();
      } else {
        rendered.unmount();
      }

      expect(frames.pendingIds()).toEqual([]);
      expect(readVisualDraft(key)?.ui.anchor_logical_scroll).toEqual({
        object_id: "S01",
        offset: 60,
      });

      scrollTo.mockClear();
      render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
      await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({
        behavior: "auto",
        left: 17,
        top: 100,
      }));
    },
  );

  it("cancels a pending scroll rAF when the visual review root unmounts", () => {
    const data = visualData();
    const frames = controlledAnimationFrames();
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    fireEvent.scroll(window);
    expect(frames.pendingIds()).toEqual([1]);
    rendered.unmount();

    expect(frames.cancel).toHaveBeenCalledWith(1);
    expect(frames.pendingIds()).toEqual([]);
  });

  it("[7C A] anchors the storage key to review revision instead of a newer Runtime snapshot", () => {
    const data = visualData();
    data.snapshotRevision = 99;
    data.review.authoritative_revision = 99;
    const key = seedVisualDraft(data, visualDraftUi({
      view: "contract",
      current_anchor_slide_id: "S02",
    }));
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    expect(key.endsWith(":visual-session-1:visual-v1:11")).toBe(true);
    expect(screen.getByRole("tab", { name: "完整视觉合同" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "S02 锚点页", hidden: true })).toHaveAttribute("aria-selected", "true");
  });

  it.each([
    ["review session", (data: VisualReviewSurfaceData) => { data.review.review_session_id = "visual-session-2"; }],
    ["source version", (data: VisualReviewSurfaceData) => { data.review.source_version = "visual-v2"; }],
    ["source revision", (data: VisualReviewSurfaceData) => {
      data.review.revision = 15;
      data.review.authoritative_revision = 16;
      data.snapshotRevision = 16;
    }],
  ])("[7C A] restores only the current $0 identity/revision envelope", (_label, mutate) => {
    const oldData = visualData();
    seedVisualDraft(oldData, visualDraftUi({ view: "contract", current_anchor_slide_id: "S02" }));
    const currentData = visualData();
    mutate(currentData);
    seedVisualDraft(currentData, visualDraftUi({ view: "contract", current_anchor_slide_id: "S03" }));
    const { bridge } = host();

    render(<ReviewSurfaceRouter data={makeRouterValid(currentData)} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "完整视觉合同" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "S03 锚点页", hidden: true })).toHaveAttribute("aria-selected", "true");
  });

  it("[7C A] rejects an old-lineage envelope and rewrites only the current lineage", () => {
    const oldData = visualData();
    const key = seedVisualDraft(oldData, visualDraftUi({ view: "contract", current_anchor_slide_id: "S02" }));
    const currentData = visualData();
    currentData.review.visual_contract_ref = NEXT_VISUAL_CONTRACT_REF;
    expect(reviewDraftStorageKey(createReviewDraftContext(currentData))).toBe(key);
    const { bridge } = host();

    render(<ReviewSurfaceRouter data={makeRouterValid(currentData)} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "S01 锚点页" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent(window, new PageTransitionEvent("pagehide"));
    const stored = JSON.parse(window.sessionStorage.getItem(key) || "null");
    expect(stored.lineage.visual_contract_ref).toBe(NEXT_VISUAL_CONTRACT_REF);
    expect(stored.ui.view).toBe("contract");
    expect(stored.ui.current_anchor_slide_id).toBeNull();
  });

  it("[7C B] restores same-session anchor drafts and composer synchronously, then gates recovered editing on real image load", async () => {
    const data = visualData();
    const drafts = [anchorDraft("已恢复的 S02 反馈", "S02", "restored-feedback")];
    const composer = anchorComposer("已恢复但尚未加入的输入", "S02");
    seedVisualDraft(data, visualDraftUi({
      current_anchor_slide_id: "S02",
      anchor_feedback_drafts: drafts,
      anchor_feedback_composer: composer,
    }));
    const { bridge, callTool } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    expect(screen.getByText("已恢复的 S02 反馈")).toBeInTheDocument();
    expect(screen.getByText("1 条待提交")).toBeInTheDocument();
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("已恢复但尚未加入的输入");
    expect(document.querySelector(".anchor-region.candidate")).toHaveStyle({
      left: "20%",
      top: "15%",
      width: "40%",
      height: "35%",
    });
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeDisabled();
    expect(screen.getByLabelText("当前框选区域反馈")).toBeDisabled();
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeDisabled();
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(0);

    fireEvent.load(await screen.findByRole("img", { name: "S02 锚点页成果" }));
    expect(screen.getByLabelText("当前框选区域反馈")).toBeEnabled();
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeDisabled();
  });

  it("rejects a persisted null-region anchor composer instead of restoring an invisible global lock", async () => {
    const data = visualData();
    seedVisualDraft(data, visualDraftUi({
      current_anchor_slide_id: "S01",
      anchor_feedback_drafts: [anchorDraft("畸形 envelope 中不应恢复的反馈")],
      anchor_feedback_composer: {
        anchor_slide_id: "S01",
        candidate_region: null,
        editing_feedback_id: "",
        comment: "没有可见候选区域的隐藏输入",
      },
    }));
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.load(await screen.findByRole("img", { name: "S01 锚点页成果" }));

    expect(screen.queryByText("畸形 envelope 中不应恢复的反馈")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    const start = screen.getByRole("button", { name: "开始标注" });
    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(screen.queryByRole("group", { name: "预设标注范围" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消标注" })).toBeInTheDocument();
  });

  it("[7C B] clears only the anchor slice after one strictly closed success", async () => {
    const data = visualData();
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const anchorDrafts = [anchorDraft("仅成功后清理的锚点反馈", "S02", "success-feedback")];
    const contractDrafts: VisualReviewDraftUi["contract_mark_drafts"] = [{
      mark_id: "contract-sibling-draft",
      target_type: "contract-field",
      slide_id: "",
      deck_section_id: "deck-design-system",
      target_key: "theme_proposition",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "必须保留的合同兄弟草稿",
      created_at: "2026-08-15T00:00:00Z",
    }];
    const contractComposer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]> = {
      editing_mark_id: "",
      target_type: "contract-field",
      slide_id: "",
      deck_section_id: "deck-design-system",
      target_key: "color_tokens",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "必须保留的合同兄弟输入",
    };
    const expectedUi = visualDraftUi({
      view: "anchors",
      current_anchor_slide_id: "S02",
      anchor_feedback_drafts: anchorDrafts,
      contract_mark_drafts: contractDrafts,
      contract_mark_composer: contractComposer,
      anchor_logical_scroll: { object_id: "S02", offset: 41 },
      contract_logical_scroll: { object_id: "S01", offset: 72 },
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.load(await screen.findByRole("img", { name: "S02 锚点页成果" }));
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    expect(await screen.findByText("反馈批次已保存")).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual({
      ...expectedUi,
      anchor_feedback_drafts: [],
      anchor_feedback_composer: null,
    });
  });

  it.each([
    [
      "generic failure",
      async () => { throw new Error("save failed"); },
      "反馈尚未保存；全部本地反馈仍保留，可直接重试。",
    ],
    [
      "invalid result",
      async () => ({ batch_ref: "malformed" }),
      "提交结果未闭合，请刷新/重新打开核对权威批次",
    ],
    [
      "unclosed result",
      async () => { throw { code: "VISUAL_ANCHOR_FEEDBACK_RESULT_UNCLOSED" }; },
      "提交结果未闭合，请刷新/重新打开核对权威批次",
    ],
    [
      "revision conflict",
      async () => { throw { code: "REVISION_CONFLICT" }; },
      "当前视觉版本已变化；全部本地反馈仍保留，请刷新后重试。",
    ],
    [
      "stale source",
      async () => { throw { code: "REVIEW_SOURCE_STALE" }; },
      "当前视觉版本已变化；全部本地反馈仍保留，请刷新后重试。",
    ],
  ])("[7C B] preserves the complete anchor slice after $0", async (_label, respond, expectedMessage) => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      current_anchor_slide_id: "S01",
      anchor_feedback_drafts: [anchorDraft("失败后仍保留的锚点反馈")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge, callTool } = host(respond);

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    expect(screen.getByText("失败后仍保留的锚点反馈")).toBeInTheDocument();
    fireEvent.load(await screen.findByRole("img", { name: "S01 锚点页成果" }));
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1));
    await waitFor(() => expect(screen.getByText(expectedMessage)).toBeInTheDocument());
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual(expectedUi);
  });

  it.each([
    ["review identity", (data: VisualReviewSurfaceData) => { data.review.review_session_id = "visual-session-2"; }],
    ["source revision", (data: VisualReviewSurfaceData) => {
      data.review.revision = 15;
      data.review.authoritative_revision = 16;
      data.snapshotRevision = 16;
    }],
    ["lineage", (data: VisualReviewSurfaceData) => { data.review.anchor_slide_set_ref = NEXT_ANCHOR_SLIDE_SET_REF; }],
  ])("[7C B] ignores an old pending anchor completion after a $0 change", async (_label, mutate) => {
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    const oldViewModel = visualData();
    seedVisualDraft(oldViewModel, visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("旧任务待返回的反馈", "S01", "old-pending-feedback")],
    }));
    const oldData = makeRouterValid(oldViewModel);
    const rendered = render(<ReviewSurfaceRouter data={oldData} bridge={bridge} />);
    fireEvent.load(await screen.findByRole("img", { name: "S01 锚点页成果" }));
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1));
    const oldArgs = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as Record<string, unknown>;

    const currentData = visualData();
    mutate(currentData);
    const currentProjection = makeRouterValid(currentData);
    const currentUi = visualDraftUi({
      current_anchor_slide_id: "S03",
      anchor_feedback_drafts: [anchorDraft("新任务必须保留的反馈", "S03", "current-feedback")],
    });
    const currentKey = seedVisualDraft(currentData, currentUi);
    rendered.rerender(<ReviewSurfaceRouter data={currentProjection} bridge={bridge} />);
    expect(screen.getByText("新任务必须保留的反馈")).toBeInTheDocument();

    await act(async () => {
      pending.resolve(closedAnchorResult(oldArgs, oldViewModel, "old-completion-batch"));
      await pending.promise;
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(currentKey)?.ui).toEqual(currentUi);
    expect(screen.queryByText("反馈批次 old-completion-batch")).not.toBeInTheDocument();
  });

  it("[7C B] uses the latest same-identity snapshot revision while preserving dirty anchor work", async () => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("投影增长后仍保留的本地反馈")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge, callTool } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);
    expect(await screen.findByText(/· revision 30/)).toBeInTheDocument();
    expect(screen.getByText("投影增长后仍保留的本地反馈")).toBeInTheDocument();
    fireEvent.load(await screen.findByRole("img", { name: "S01 锚点页成果" }));
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1));
    const args = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as {
      expectedRevision: number;
      feedback: AnchorFeedbackBatch["items"];
    };
    expect(args.expectedRevision).toBe(30);
    expect(args.feedback.every((item) => item.revision === 30)).toBe(true);
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.anchor_feedback_drafts).toEqual(expectedUi.anchor_feedback_drafts);
  });

  it("[7C B] reconciles authoritative anchor batches monotonically without copying over dirty root drafts", () => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("权威批次不得覆盖的本地反馈")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    const authoritativeBatch = existingAnchorBatch();
    authoritativeBatch.batch_id = "anchor-batch-grown-projection";
    authoritativeBatch.revision = 20;
    authoritativeBatch.items[0].revision = 20;
    grown.review.anchor_feedback_batch = authoritativeBatch;
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);

    expect(screen.getByText("anchor-batch-grown-projection", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/· revision 30/)).toBeInTheDocument();
    rendered.rerender(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    expect(screen.getByText("anchor-batch-grown-projection", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/· revision 30/)).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.anchor_feedback_drafts).toEqual(expectedUi.anchor_feedback_drafts);
  });

  it("keeps projected anchor batch authority monotonic by batch revision while advancing equal-revision receipts", () => {
    const initial = visualData();
    const expectedUi = visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("权威批次变化不得覆盖的本地反馈")],
    });
    const key = seedVisualDraft(initial, expectedUi);
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={initial} bridge={bridge} />);

    const snapshot30 = visualData();
    snapshot30.snapshotRevision = 30;
    snapshot30.review.authoritative_revision = 30;
    const revision20 = existingAnchorBatch();
    revision20.batch_id = "authoritative-anchor-batch-r20";
    revision20.revision = 20;
    revision20.items[0].revision = 20;
    snapshot30.review.anchor_feedback_batch = revision20;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot30} bridge={bridge} />);
    expect(screen.getByText("authoritative-anchor-batch-r20", { exact: false })).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：未请求")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：待回执")).toBeInTheDocument();

    const snapshot31Stale = visualData();
    snapshot31Stale.snapshotRevision = 31;
    snapshot31Stale.review.authoritative_revision = 31;
    const revision19 = existingAnchorBatch();
    revision19.batch_id = "stale-anchor-batch-r19";
    revision19.revision = 19;
    revision19.items[0].revision = 19;
    snapshot31Stale.review.anchor_feedback_batch = revision19;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Stale} bridge={bridge} />);
    expect(screen.getByText("authoritative-anchor-batch-r20", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("stale-anchor-batch-r19", { exact: false })).not.toBeInTheDocument();

    const snapshot31Receipt = visualData();
    snapshot31Receipt.snapshotRevision = 31;
    snapshot31Receipt.review.authoritative_revision = 31;
    const receiptAdvanced = existingAnchorBatch();
    receiptAdvanced.batch_id = "authoritative-anchor-batch-r20";
    receiptAdvanced.revision = 20;
    receiptAdvanced.items[0].revision = 20;
    receiptAdvanced.host_notification_status = "sent";
    receiptAdvanced.ai_receipt_status = "received";
    snapshot31Receipt.review.anchor_feedback_batch = receiptAdvanced;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Receipt} bridge={bridge} />);
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：已接收")).toBeInTheDocument();

    const snapshot32Null = visualData();
    snapshot32Null.snapshotRevision = 32;
    snapshot32Null.review.authoritative_revision = 32;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot32Null} bridge={bridge} />);
    rendered.rerender(<VisualProfessionalReviewPage initialData={initial} bridge={bridge} />);
    expect(screen.getByText("authoritative-anchor-batch-r20", { exact: false })).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：已接收")).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.anchor_feedback_drafts).toEqual(expectedUi.anchor_feedback_drafts);
  });

  it.each([
    ["null authority", () => null],
    ["lower authority revision", (authority: AnchorFeedbackBatch) => {
      const lower = structuredClone(authority);
      lower.batch_id = "higher-snapshot-lower-anchor-r19";
      lower.revision = 19;
      lower.items[0].revision = 19;
      return lower;
    }],
    ["equal-revision immutable conflict", (authority: AnchorFeedbackBatch) => {
      const conflict = structuredClone(authority);
      conflict.batch_id = "higher-snapshot-conflicting-anchor-r20";
      return conflict;
    }],
  ] as Array<[
    string,
    (authority: AnchorFeedbackBatch) => AnchorFeedbackBatch | null,
  ]>)("uses the observed anchor snapshot watermark after a higher snapshot with $0", (_label, higherCandidate) => {
    const snapshot30 = visualData();
    snapshot30.snapshotRevision = 30;
    snapshot30.review.authoritative_revision = 30;
    const authority = existingAnchorBatch();
    authority.batch_id = "observed-anchor-authority-r20";
    authority.revision = 20;
    authority.items[0].revision = 20;
    snapshot30.review.anchor_feedback_batch = authority;
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={snapshot30} bridge={bridge} />);

    const snapshot40 = visualData();
    snapshot40.snapshotRevision = 40;
    snapshot40.review.authoritative_revision = 40;
    snapshot40.review.anchor_feedback_batch = higherCandidate(authority);
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot40} bridge={bridge} />);

    const snapshot35 = visualData();
    snapshot35.snapshotRevision = 35;
    snapshot35.review.authoritative_revision = 35;
    const lowerSnapshotCandidate = structuredClone(authority);
    lowerSnapshotCandidate.batch_id = "lower-snapshot-anchor-r21";
    lowerSnapshotCandidate.revision = 21;
    lowerSnapshotCandidate.items[0].revision = 21;
    lowerSnapshotCandidate.items[0].comment = "不得安装的低快照锚点反馈";
    snapshot35.review.anchor_feedback_batch = lowerSnapshotCandidate;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot35} bridge={bridge} />);

    expect(screen.getByText("observed-anchor-authority-r20", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("不得安装的低快照锚点反馈")).not.toBeInTheDocument();

    const snapshot40ReceiptRepair = visualData();
    snapshot40ReceiptRepair.snapshotRevision = 40;
    snapshot40ReceiptRepair.review.authoritative_revision = 40;
    const receiptOnly = structuredClone(authority);
    receiptOnly.host_notification_status = "sent";
    receiptOnly.ai_receipt_status = "received";
    snapshot40ReceiptRepair.review.anchor_feedback_batch = receiptOnly;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot40ReceiptRepair} bridge={bridge} />);

    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：已接收")).toBeInTheDocument();
  });

  it("times out a never-settling anchor write, retries the exact body, and ignores the original late completion", async () => {
    vi.useFakeTimers();
    const data = visualData();
    seedVisualDraft(data, visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("超时后必须保留的锚点反馈", "S01", "deadline-anchor-feedback")],
    }));
    const original = deferred<unknown>();
    let attempt = 0;
    const { bridge, callTool } = host(async (args) => {
      attempt += 1;
      return attempt === 1
        ? original.promise
        : closedAnchorResult(args, data, "deadline-anchor-replay");
    });
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    const firstCall = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch");
    expect(firstCall).toBeDefined();
    const firstBody = structuredClone(firstCall![1]);

    await act(async () => {
      vi.advanceTimersByTime(REVIEW_WRITE_DEADLINE_MS);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("保存请求超时；结果尚未确认，全部本地反馈仍保留。请使用相同内容重试。")).toBeInTheDocument();
    expect(screen.getByText("超时后必须保留的锚点反馈")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeEnabled();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    const writeCalls = callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch");
    expect(writeCalls).toHaveLength(2);
    expect(writeCalls[1][1]).toEqual(firstBody);
    expect(JSON.stringify(writeCalls[1][1])).toBe(JSON.stringify(firstBody));
    expect(screen.getByText("反馈批次 deadline-anchor-replay")).toBeInTheDocument();
    expect(screen.getByText("超时后必须保留的锚点反馈")).toBeInTheDocument();
    expect(screen.getByText("1 条已提交")).toBeInTheDocument();
    expect(screen.getByText(/visual-v1.*revision 13/)).toBeInTheDocument();

    const late = closedAnchorResult(firstBody, data, "late-anchor-result");
    late.snapshot.revision = 99;
    await act(async () => {
      original.resolve(late);
      await original.promise;
      await Promise.resolve();
    });
    expect(screen.queryByText("late-anchor-result", { exact: false })).not.toBeInTheDocument();
    expect(screen.getByText(/visual-v1.*revision 13/)).toBeInTheDocument();
  });

  it.each([
    ["batch identity", (batch: AnchorFeedbackBatch) => { batch.batch_id = "mutated-anchor-batch-r20"; }],
    ["feedback identity", (batch: AnchorFeedbackBatch) => { batch.items[0].feedback_id = "mutated-feedback-r20"; }],
    ["feedback comment", (batch: AnchorFeedbackBatch) => { batch.items[0].comment = "同 revision 不可替换的反馈正文"; }],
    ["normalized region", (batch: AnchorFeedbackBatch) => { batch.items[0].normalized_region.x = 0.4; }],
    ["feedback slide", (batch: AnchorFeedbackBatch) => { batch.items[0].anchor_slide_id = "S03"; }],
    ["submission time", (batch: AnchorFeedbackBatch) => { batch.submitted_at = "2026-08-15T00:00:01Z"; }],
  ])("rejects equal-revision anchor immutable authority mutation: %s without consuming its snapshot for receipt-only authority", (_label, mutate) => {
    const snapshot30 = visualData();
    snapshot30.snapshotRevision = 30;
    snapshot30.review.authoritative_revision = 30;
    const authority = existingAnchorBatch();
    authority.batch_id = "immutable-anchor-batch-r20";
    authority.revision = 20;
    authority.items[0].revision = 20;
    snapshot30.review.anchor_feedback_batch = authority;
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={snapshot30} bridge={bridge} />);

    expect(screen.getByText("immutable-anchor-batch-r20", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("保留证据，但降低视觉重量")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：未请求")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：待回执")).toBeInTheDocument();

    const snapshot31Mutated = visualData();
    snapshot31Mutated.snapshotRevision = 31;
    snapshot31Mutated.review.authoritative_revision = 31;
    const mutated = structuredClone(authority);
    mutate(mutated);
    mutated.host_notification_status = "sent";
    mutated.ai_receipt_status = "received";
    snapshot31Mutated.review.anchor_feedback_batch = mutated;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Mutated} bridge={bridge} />);

    expect(screen.getByText("immutable-anchor-batch-r20", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("保留证据，但降低视觉重量")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：未请求")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：待回执")).toBeInTheDocument();

    const snapshot31Receipt = visualData();
    snapshot31Receipt.snapshotRevision = 31;
    snapshot31Receipt.review.authoritative_revision = 31;
    const receiptOnly = structuredClone(authority);
    receiptOnly.host_notification_status = "sent";
    receiptOnly.ai_receipt_status = "received";
    snapshot31Receipt.review.anchor_feedback_batch = receiptOnly;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Receipt} bridge={bridge} />);

    expect(within(screen.getByLabelText("反馈提交事实")).getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(within(screen.getByLabelText("反馈提交事实")).getByText("AI 接收：已接收")).toBeInTheDocument();
  });

  it("[7C C] restores same-session contract drafts, composer comment, and all seven target-selection identity fields", () => {
    const data = visualData();
    const drafts = [contractDraft("已恢复的合同草稿", "restored-contract-mark")];
    const composer = contractComposer("已恢复的合同输入", "restored-contract-mark");
    const expectedUi = visualDraftUi({
      view: "contract",
      contract_mark_drafts: drafts,
      contract_mark_composer: composer,
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "完整视觉合同" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("dialog", { name: "合同标记" })).toBeInTheDocument();
    expect(screen.getByText("已恢复的合同草稿")).toBeInTheDocument();
    expect(screen.getByText("S01 · 页面可见文案")).toBeInTheDocument();
    expect(screen.getByLabelText("合同标记意见")).toHaveValue("已恢复的合同输入");
    fireEvent(window, new PageTransitionEvent("pagehide"));

    const storedUi = readVisualDraft(key)?.ui;
    expect(storedUi).toEqual(expectedUi);
    expect(storedUi).not.toHaveProperty("drawer");
    expect(storedUi?.contract_mark_composer).toEqual(expect.objectContaining({
      target_type: "text-range",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "visible_copy",
      selected_text: "页面可见文案 1",
      context_before: "选中文本前文",
      context_after: "选中文本后文",
    }));
  });

  it("[7C C] clears only the contract slice after a strictly closed success and preserves the full seven-field identity", async () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const data = visualData();
    const submittedDraft = contractDraft("仅成功后清理的合同标记", "success-contract-mark");
    const expectedUi = visualDraftUi({
      view: "contract",
      current_anchor_slide_id: "S02",
      anchor_feedback_drafts: [anchorDraft("必须保留的锚点兄弟草稿", "S03", "anchor-sibling")],
      anchor_feedback_composer: anchorComposer("必须保留的锚点兄弟输入", "S03"),
      contract_mark_drafts: [submittedDraft],
      anchor_logical_scroll: { object_id: "S02", offset: 44 },
      contract_logical_scroll: { object_id: "S01", offset: 73 },
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge, callTool } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    const args = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as {
      marks: VisualContractReviewMarkSet["marks"];
    };
    expect(args.marks[0]).toEqual(expect.objectContaining({
      mark_id: "success-contract-mark",
      target_type: "text-range",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "visible_copy",
      selected_text: "页面可见文案 1",
      context_before: "选中文本前文",
      context_after: "选中文本后文",
    }));
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual({
      ...expectedUi,
      contract_mark_drafts: [],
      contract_mark_composer: null,
    });
  });

  it.each([
    [
      "generic failure",
      async () => { throw new Error("save failed"); },
      "合同标记尚未保存；全部草稿仍保留，可直接重试。",
    ],
    [
      "invalid result",
      async () => ({ mark_set_ref: "malformed" }),
      "保存结果未闭合，请刷新/重新打开核对；当前未保存标记和输入未改动。",
    ],
    [
      "unclosed result",
      async () => { throw { code: "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED" }; },
      "保存结果未闭合，请刷新/重新打开核对；当前未保存标记和输入未改动。",
    ],
    [
      "revision conflict",
      async () => { throw { code: "REVISION_CONFLICT" }; },
      "当前视觉版本已变化；本地未保存标记和输入未改动，请刷新后重试。",
    ],
    [
      "stale source",
      async () => { throw { code: "REVIEW_SOURCE_STALE" }; },
      "当前视觉版本已变化；本地未保存标记和输入未改动，请刷新后重试。",
    ],
  ])("[7C C] preserves the complete contract slice after $0", async (_label, respond, expectedMessage) => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("失败后仍保留的合同草稿", "retained-contract-mark")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge, callTool } = host(undefined, respond);

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    expect(screen.getByText("失败后仍保留的合同草稿")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    await waitFor(() => expect(screen.getByText(expectedMessage)).toBeInTheDocument());
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(key)?.ui).toEqual(expectedUi);
  });

  it.each([
    ["review identity", (data: VisualReviewSurfaceData) => { data.review.review_session_id = "visual-session-2"; }],
    ["source version", (data: VisualReviewSurfaceData) => { data.review.source_version = "visual-v2"; }],
    ["source revision", (data: VisualReviewSurfaceData) => {
      data.review.revision = 15;
      data.review.authoritative_revision = 16;
      data.snapshotRevision = 16;
    }],
    ["lineage", (data: VisualReviewSurfaceData) => { data.review.visual_contract_ref = NEXT_VISUAL_CONTRACT_REF; }],
  ])("[7C C] ignores an old pending contract completion after a $0 change", async (_label, mutate) => {
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    const oldViewModel = visualData();
    seedVisualDraft(oldViewModel, visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("旧任务待返回的合同标记", "old-contract-mark")],
    }));
    const oldData = makeRouterValid(oldViewModel);
    const rendered = render(<ReviewSurfaceRouter data={oldData} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    const oldArgs = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as Record<string, unknown>;

    const currentData = visualData();
    mutate(currentData);
    const currentProjection = makeRouterValid(currentData);
    const currentUi = visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("新任务必须保留的合同草稿", "current-contract-mark")],
      contract_mark_composer: contractComposer("新任务必须保留的合同输入"),
    });
    const currentKey = seedVisualDraft(currentData, currentUi);
    rendered.rerender(<ReviewSurfaceRouter data={currentProjection} bridge={bridge} />);
    expect(screen.getByText("新任务必须保留的合同草稿")).toBeInTheDocument();
    expect(screen.getByLabelText("合同标记意见")).toHaveValue("新任务必须保留的合同输入");

    await act(async () => {
      pending.resolve(contractMarkResult(oldArgs));
      await pending.promise;
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readVisualDraft(currentKey)?.ui).toEqual(currentUi);
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
  });

  it("[7C C] keeps the key on review revision and uses the latest same-identity snapshot revision without losing dirty contract work", async () => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("投影增长后仍保留的合同草稿", "grown-contract-mark")],
    });
    const key = seedVisualDraft(data, expectedUi);
    expect(key.endsWith(":visual-session-1:visual-v1:11")).toBe(true);
    const { bridge, callTool } = host(undefined, async () => ({ mark_set_ref: "malformed" }));
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    expect(reviewDraftStorageKey(createReviewDraftContext(grown))).toBe(key);
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);
    expect(await screen.findByText(/· revision 30/)).toBeInTheDocument();
    expect(screen.getByText("投影增长后仍保留的合同草稿")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    const args = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as {
      expectedRevision: number;
      marks: VisualContractReviewMarkSet["marks"];
    };
    expect(args.expectedRevision).toBe(30);
    expect(args.marks.every((mark) => mark.revision === 30)).toBe(true);
    await screen.findByText("保存结果未闭合，请刷新/重新打开核对；当前未保存标记和输入未改动。");
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.contract_mark_drafts).toEqual(expectedUi.contract_mark_drafts);
  });

  it("[7C C] reconciles authoritative contract mark sets monotonically without copying over dirty root drafts", () => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("权威标记集不得覆盖的本地草稿", "dirty-contract-mark")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    grown.review.contract_review_marks = projectedContractMarkSet();
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);

    expect(screen.getByLabelText("合同标记保存事实")).toBeInTheDocument();
    expect(screen.getByText(/· revision 30/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开标记记录" }));
    expect(screen.getByText("已保存 1 条合同标记。")).toBeInTheDocument();

    const receiptGrown = visualData();
    receiptGrown.snapshotRevision = 31;
    receiptGrown.review.authoritative_revision = 31;
    receiptGrown.review.contract_review_marks = projectedContractMarkSet();
    receiptGrown.review.contract_review_marks.host_notification_status = "sent";
    receiptGrown.review.contract_review_marks.ai_receipt_status = "received";
    rendered.rerender(<VisualProfessionalReviewPage initialData={receiptGrown} bridge={bridge} />);
    expect(screen.getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：已接收")).toBeInTheDocument();

    rendered.rerender(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    expect(screen.getByLabelText("合同标记保存事实")).toBeInTheDocument();
    expect(screen.getByText(/· revision 31/)).toBeInTheDocument();
    expect(screen.getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：已接收")).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.contract_mark_drafts).toEqual(expectedUi.contract_mark_drafts);
  });

  it.each([
    ["null authority", () => null],
    ["lower authority revision", (authority: VisualContractReviewMarkSet) => {
      const lower = structuredClone(authority);
      lower.mark_set_id = "higher-snapshot-lower-contract-r19";
      lower.revision = 19;
      lower.marks[0].revision = 19;
      return lower;
    }],
    ["equal-revision immutable conflict", (authority: VisualContractReviewMarkSet) => {
      const conflict = structuredClone(authority);
      conflict.mark_set_id = "higher-snapshot-conflicting-contract-r20";
      return conflict;
    }],
  ] as Array<[
    string,
    (authority: VisualContractReviewMarkSet) => VisualContractReviewMarkSet | null,
  ]>)("uses the observed contract snapshot watermark after a higher snapshot with $0", (_label, higherCandidate) => {
    const snapshot30 = visualData();
    snapshot30.snapshotRevision = 30;
    snapshot30.review.authoritative_revision = 30;
    const authority = projectedContractMarkSet(20);
    authority.mark_set_id = "observed-contract-authority-r20";
    snapshot30.review.contract_review_marks = authority;
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={snapshot30} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "打开标记记录" }));

    const snapshot40 = visualData();
    snapshot40.snapshotRevision = 40;
    snapshot40.review.authoritative_revision = 40;
    snapshot40.review.contract_review_marks = higherCandidate(authority);
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot40} bridge={bridge} />);

    const snapshot35 = visualData();
    snapshot35.snapshotRevision = 35;
    snapshot35.review.authoritative_revision = 35;
    const lowerSnapshotCandidate = structuredClone(authority);
    lowerSnapshotCandidate.mark_set_id = "lower-snapshot-contract-r21";
    lowerSnapshotCandidate.revision = 21;
    lowerSnapshotCandidate.marks[0].revision = 21;
    lowerSnapshotCandidate.marks.push({
      ...lowerSnapshotCandidate.marks[0],
      mark_id: "lower-snapshot-extra-contract-mark",
      comment: "不得安装的低快照合同标记",
    });
    snapshot35.review.contract_review_marks = lowerSnapshotCandidate;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot35} bridge={bridge} />);

    expect(screen.getByText("已保存 1 条合同标记。")).toBeInTheDocument();
    expect(screen.queryByText("已保存 2 条合同标记。")).not.toBeInTheDocument();

    const snapshot40ReceiptRepair = visualData();
    snapshot40ReceiptRepair.snapshotRevision = 40;
    snapshot40ReceiptRepair.review.authoritative_revision = 40;
    const receiptOnly = structuredClone(authority);
    receiptOnly.host_notification_status = "sent";
    receiptOnly.ai_receipt_status = "received";
    snapshot40ReceiptRepair.review.contract_review_marks = receiptOnly;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot40ReceiptRepair} bridge={bridge} />);

    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("AI 接收：已接收")).toBeInTheDocument();
  });

  it("times out a never-settling contract write, retries the exact body, and ignores the original late completion", async () => {
    vi.useFakeTimers();
    const data = visualData();
    seedVisualDraft(data, visualDraftUi({
      view: "contract",
      contract_mark_drafts: [contractDraft("超时后必须保留的合同标记", "deadline-contract-mark")],
    }));
    const original = deferred<unknown>();
    let attempt = 0;
    const { bridge, callTool } = host(undefined, async (args) => {
      attempt += 1;
      return attempt === 1 ? original.promise : contractMarkResult(args);
    });
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    const firstCall = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks");
    expect(firstCall).toBeDefined();
    const firstBody = structuredClone(firstCall![1]);

    await act(async () => {
      vi.advanceTimersByTime(REVIEW_WRITE_DEADLINE_MS);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("保存请求超时；结果尚未确认，全部合同标记草稿仍保留。请使用相同内容重试。")).toBeInTheDocument();
    expect(screen.getByText("超时后必须保留的合同标记")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 1 条合同标记" })).toBeEnabled();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    const writeCalls = callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks");
    expect(writeCalls).toHaveLength(2);
    expect(writeCalls[1][1]).toEqual(firstBody);
    expect(JSON.stringify(writeCalls[1][1])).toBe(JSON.stringify(firstBody));
    expect(screen.getByText("合同标记已保存")).toBeInTheDocument();
    expect(screen.queryByText("超时后必须保留的合同标记")).not.toBeInTheDocument();
    expect(screen.getByText(/visual-v1.*revision 13/)).toBeInTheDocument();

    const late = contractMarkResult(firstBody);
    late.snapshot.revision = 99;
    await act(async () => {
      original.resolve(late);
      await original.promise;
      await Promise.resolve();
    });
    expect(screen.getByText(/visual-v1.*revision 13/)).toBeInTheDocument();
  });

  it.each([
    ["mark-set identity", (markSet: VisualContractReviewMarkSet) => { markSet.mark_set_id = "mutated-contract-marks-r20"; }],
    ["mark identity", (markSet: VisualContractReviewMarkSet) => { markSet.marks[0].mark_id = "mutated-contract-mark-r20"; }],
    ["target key", (markSet: VisualContractReviewMarkSet) => { markSet.marks[0].target_key = "frozen_copy"; }],
    ["mark comment", (markSet: VisualContractReviewMarkSet) => { markSet.marks[0].comment = "同 revision 不可替换的合同意见"; }],
    ["target slide", (markSet: VisualContractReviewMarkSet) => { markSet.marks[0].slide_id = "S02"; }],
    ["save time", (markSet: VisualContractReviewMarkSet) => { markSet.saved_at = "2026-08-17T00:00:00Z"; }],
  ])("rejects equal-revision contract immutable authority mutation: %s without consuming its snapshot for receipt-only authority", (_label, mutate) => {
    const snapshot30 = visualData();
    snapshot30.snapshotRevision = 30;
    snapshot30.review.authoritative_revision = 30;
    const authority = projectedContractMarkSet();
    authority.mark_set_id = "immutable-contract-marks-r20";
    snapshot30.review.contract_review_marks = authority;
    const { bridge } = host();
    const rendered = render(<VisualProfessionalReviewPage initialData={snapshot30} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("宿主通知：未请求")).toBeInTheDocument();
    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("AI 接收：待回执")).toBeInTheDocument();

    const snapshot31Mutated = visualData();
    snapshot31Mutated.snapshotRevision = 31;
    snapshot31Mutated.review.authoritative_revision = 31;
    const mutated = structuredClone(authority);
    mutate(mutated);
    mutated.host_notification_status = "sent";
    mutated.ai_receipt_status = "received";
    snapshot31Mutated.review.contract_review_marks = mutated;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Mutated} bridge={bridge} />);

    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("宿主通知：未请求")).toBeInTheDocument();
    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("AI 接收：待回执")).toBeInTheDocument();

    const snapshot31Receipt = visualData();
    snapshot31Receipt.snapshotRevision = 31;
    snapshot31Receipt.review.authoritative_revision = 31;
    const receiptOnly = structuredClone(authority);
    receiptOnly.host_notification_status = "sent";
    receiptOnly.ai_receipt_status = "received";
    snapshot31Receipt.review.contract_review_marks = receiptOnly;
    rendered.rerender(<VisualProfessionalReviewPage initialData={snapshot31Receipt} bridge={bridge} />);

    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("宿主通知：已送达")).toBeInTheDocument();
    expect(within(screen.getByLabelText("合同标记保存事实")).getByText("AI 接收：已接收")).toBeInTheDocument();
  });

  it("[7C C] releases a pending anchor lock when a newer same-identity revision invalidates the command", async () => {
    mockSlideRect();
    const pending = deferred<unknown>();
    const data = visualData();
    const { bridge, callTool } = host(() => pending.promise);
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    await addRegion("新 revision 中必须保留的锚点反馈");
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1));
    const oldArgs = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as Record<string, unknown>;

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeEnabled());
    expect(screen.getByText("新 revision 中必须保留的锚点反馈")).toBeInTheDocument();
    await act(async () => {
      pending.resolve(closedAnchorResult(oldArgs, data, "invalidated-anchor-batch"));
      await pending.promise;
    });
    expect(screen.queryByText("反馈批次 invalidated-anchor-batch")).not.toBeInTheDocument();
    expect(screen.getByText("新 revision 中必须保留的锚点反馈")).toBeInTheDocument();
    expect(screen.getByText(/· revision 30/)).toBeInTheDocument();
  });

  it("[7C C] releases a pending contract lock when a newer same-identity revision invalidates the command", async () => {
    const pending = deferred<unknown>();
    const data = visualData();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    const rendered = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 核心主张" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "新 revision 中必须保留的合同标记" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    const oldArgs = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as Record<string, unknown>;

    const grown = visualData();
    grown.snapshotRevision = 30;
    grown.review.authoritative_revision = 30;
    rendered.rerender(<VisualProfessionalReviewPage initialData={grown} bridge={bridge} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "保存 1 条合同标记" })).toBeEnabled());
    expect(screen.getByText("新 revision 中必须保留的合同标记")).toBeInTheDocument();
    await act(async () => {
      pending.resolve(contractMarkResult(oldArgs));
      await pending.promise;
    });
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
    expect(screen.getByText("新 revision 中必须保留的合同标记")).toBeInTheDocument();
    expect(screen.getByText(/· revision 30/)).toBeInTheDocument();
  });

  it("shows only the two approved views and no product navigation or gate actions", () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "完整视觉合同" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab", { name: /S0[1-3]/ })).toHaveLength(3);
    expect(screen.queryByRole("navigation", { name: "五空间导航" })).not.toBeInTheDocument();
    expect(screen.queryByText("项目仪表盘")).not.toBeInTheDocument();
    expect(screen.queryByText("聊天记录")).not.toBeInTheDocument();
    expect(screen.queryByText(/确认 G3|下载 PPTX/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^反馈批次 /)).not.toBeInTheDocument();
  });

  it("shows the authoritative compact project header and one global unsaved count", () => {
    const data = visualData();
    seedVisualDraft(data, visualDraftUi({
      anchor_feedback_drafts: [anchorDraft("锚点草稿")],
      anchor_feedback_composer: anchorComposer("锚点输入中"),
      contract_mark_drafts: [contractDraft("合同草稿")],
      contract_mark_composer: contractComposer("合同输入中"),
    }));
    const { bridge } = host();

    const { container } = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    const header = container.querySelector<HTMLElement>(".visual-professional-header")!;
    expect(header).toHaveClass("visual-review-topbar", "visual-professional-topbar");
    expect(header.querySelector(".visual-professional-project-identity")).toBeInTheDocument();
    expect(header.querySelector(".visual-professional-ai-mark")).toHaveTextContent("AI");
    expect(header.querySelector(".visual-professional-review-view-switch")).toHaveAttribute("role", "tablist");
    expect(header.querySelector(".visual-professional-status-ledger")).toBeInTheDocument();
    expect(within(header).getByText("测试项目")).toBeInTheDocument();
    expect(within(header).getByText("visual-v1 · revision 12")).toBeInTheDocument();
    expect(within(header).queryByText(/G1|G2|G3/)).not.toBeInTheDocument();
    expect(within(header).getByLabelText("全局未保存状态")).toHaveTextContent("未保存 4");
  });

  it("keeps source and Gate identity outside the visible visual-contract document", () => {
    const data = visualData();
    data.review.source_version = VISUAL_CONTRACT_REF;
    const { bridge } = host();

    const { container } = render(
      <VisualProfessionalReviewPage initialData={data} bridge={bridge} />,
    );

    const header = container.querySelector<HTMLElement>(".visual-professional-header")!;
    expect(header).toHaveTextContent("视觉合同 aaaaaaaa · revision 12");
    expect(header).not.toHaveTextContent("视觉确认");
    expect(header).not.toHaveTextContent(VISUAL_CONTRACT_REF);
    expect(header).not.toHaveTextContent("user-reviewable");

    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    const titlePage = container.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(titlePage).not.toHaveTextContent("视觉合同 aaaaaaaa");
    expect(titlePage).not.toHaveTextContent(/G1|G2|G3/);
    expect(titlePage).not.toHaveTextContent(VISUAL_CONTRACT_REF);
    expect(titlePage).not.toHaveTextContent("user-reviewable");
    expect(container.querySelectorAll(".visual-contract-page-state")).toHaveLength(0);
    expect(screen.queryByRole("region", { name: "视觉合同摘要" })).not.toBeInTheDocument();
    expect(screen.queryByText("技术信息")).not.toBeInTheDocument();
  });

  it.each([
    ["visual-contract-set", "b", "视觉合同集 bbbbbbbb"],
    ["render-evidence", "c", "视觉制品 render-evidence cccccccc"],
    ["constructor", "d", "视觉制品 constructor dddddddd"],
  ])("shortens every legal artifact source kind: %s", (kind, digestCharacter, expectedLabel) => {
    const data = visualData();
    const artifactSource = `artifact://${kind}/${digestCharacter.repeat(64)}`;
    data.review.source_version = artifactSource;
    const { bridge } = host();

    const { container } = render(
      <VisualProfessionalReviewPage initialData={data} bridge={bridge} />,
    );

    const header = container.querySelector<HTMLElement>(".visual-professional-header")!;
    expect(header).toHaveTextContent(`${expectedLabel} · revision 12`);
    expect(header).not.toHaveTextContent(artifactSource);

    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    const titlePage = container.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(titlePage).not.toHaveTextContent(expectedLabel);
    expect(titlePage).not.toHaveTextContent(artifactSource);
    expect(screen.queryByText("技术信息")).not.toBeInTheDocument();
    expect(screen.queryByText(artifactSource)).not.toBeInTheDocument();
  });

  it("keeps an artifact source raw through anchor and contract writes plus receipt recovery", async () => {
    mockSlideRect();
    const artifactSource = "artifact://render-evidence/" + "9".repeat(64);
    const data = visualData();
    data.review.source_version = artifactSource;
    data.review.host_submission_capability = "available";
    data.review.ai_receipt_capability = "available";
    const retryHost = vi.fn(async (input: Parameters<NonNullable<HostBridge["retryVisualHostNotification"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      hostNotificationStatus: "sent" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const verifyAi = vi.fn(async (input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      aiReceiptStatus: "received" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const { bridge, callTool } = host(async (args) => (
      closedAnchorResult(args, data, "artifact-source-anchor-batch")
    ), async (args) => {
      const result = contractMarkResult(args);
      result.mark_set.source_version = artifactSource;
      result.snapshot.revision = Number(args.expectedRevision) + 1;
      return result;
    }, {
      retryVisualHostNotification: retryHost,
      verifyVisualAiReceipt: verifyAi,
    });

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    await addRegion("artifact source 锚点反馈");
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    expect(await screen.findByText("反馈批次 artifact-source-anchor-batch")).toBeInTheDocument();

    const anchorWrite = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as {
      sourceVersion: string;
      feedback: AnchorFeedbackBatch["items"];
    };
    expect(anchorWrite.sourceVersion).toBe(artifactSource);
    expect(anchorWrite.feedback[0].visual_source_version).toBe(artifactSource);

    fireEvent.click(screen.getByRole("button", { name: "重试宿主通知" }));
    await waitFor(() => expect(retryHost).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));
    await waitFor(() => expect(verifyAi).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "artifact source 合同标记" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();

    const contractWrite = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as {
      sourceVersion: string;
      marks: VisualContractReviewMarkSet["marks"];
    };
    expect(contractWrite.sourceVersion).toBe(artifactSource);
    expect(contractWrite.marks[0].source_version).toBe(artifactSource);

    fireEvent.click(screen.getByRole("button", { name: "重试宿主通知" }));
    await waitFor(() => expect(retryHost).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));
    await waitFor(() => expect(verifyAi).toHaveBeenCalledTimes(2));

    expect(retryHost.mock.calls.map(([input]) => input.sourceVersion)).toEqual([
      artifactSource,
      artifactSource,
    ]);
    expect(verifyAi.mock.calls.map(([input]) => input.sourceVersion)).toEqual([
      artifactSource,
      artifactSource,
    ]);
    const header = document.querySelector<HTMLElement>(".visual-professional-header")!;
    expect(header).toHaveTextContent("视觉制品 render-evidence 99999999");
    expect(header).not.toHaveTextContent(artifactSource);
  });

  it("shows an existing immutable feedback batch id in the inline batch", () => {
    const { bridge } = host();
    const batch = existingAnchorBatch();
    render(<VisualProfessionalReviewPage initialData={visualData({}, batch)} bridge={bridge} />);

    const inlineBatch = screen.getByRole("region", { name: "本轮反馈批次" });
    expect(within(inlineBatch).getByText(`反馈批次 ${batch.batch_id}`)).toBeInTheDocument();
    expect(within(inlineBatch).getByRole("button", { name: "本轮反馈已冻结" })).toBeDisabled();
    expect(within(inlineBatch).queryByText(batch.visual_contract_ref)).not.toBeInTheDocument();
  });

  it.each([
    ["foreign project", (batch: AnchorFeedbackBatch) => { batch.project_id = "foreign-project"; }],
    ["unknown slide", (batch: AnchorFeedbackBatch) => { batch.items[0].anchor_slide_id = "S99"; }],
    ["duplicate feedback id", (batch: AnchorFeedbackBatch) => {
      batch.items.push({ ...batch.items[0], order: 2 });
    }],
    ["wrong order", (batch: AnchorFeedbackBatch) => { batch.items[0].order = 2; }],
  ])("fails closed for an initial batch with %s lineage", (_label, mutate) => {
    const { bridge } = host();
    const batch = structuredClone(existingAnchorBatch());
    mutate(batch);
    render(<VisualProfessionalReviewPage initialData={visualData({}, batch)} bridge={bridge} />);

    expect(screen.getByText("权威视觉审核投影无效，请刷新/重新打开")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /统一提交|本轮反馈已冻结/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeDisabled();
  });

  it("reports all feedback receipt facts as unknown for an invalid initial batch", () => {
    const { bridge } = host();
    const batch = structuredClone(existingAnchorBatch());
    batch.project_id = "foreign-project";
    render(<VisualProfessionalReviewPage initialData={visualData({}, batch)} bridge={bridge} />);

    const facts = screen.getByLabelText("反馈提交事实");
    expect(within(facts).getByText("持久化：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(within(facts).getByText("宿主通知：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(within(facts).getByText("AI 接收：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(facts).not.toHaveTextContent(/尚未提交|尚无批次回执|已保存|已送达|已接收/);
  });

  it("loads exactly three current anchor images from current_asset_ref in projection order", async () => {
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);

    const tabs = screen.getAllByRole("tab", { name: /S0[1-3]/ });
    expect(tabs.map((tab) => tab.textContent)).toEqual(["01 · S01", "02 · S02", "03 · S03"]);
    expect(await screen.findByRole("img", { name: "S01 锚点页成果" })).toBeInTheDocument();
    fireEvent.click(tabs[1]);
    expect(await screen.findByRole("img", { name: "S02 锚点页成果" })).toBeInTheDocument();
    fireEvent.click(tabs[2]);
    expect(await screen.findByRole("img", { name: "S03 锚点页成果" })).toBeInTheDocument();

    const assetCalls = callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset");
    expect(assetCalls.map(([, args]) => (args as { assetRef: string }).assetRef)).toEqual([
      "review-assets/anchors/S01-current.png",
      "review-assets/anchors/S02-current.png",
      "review-assets/anchors/S03-current.png",
    ]);
    expect(assetCalls.every(([, args]) => !("asset_ref" in args))).toBe(true);
  });

  it("removes the empty anchor assistant and reveals a compact inline batch only after feedback is added", async () => {
    mockSlideRect();
    const { bridge } = host();
    const { container } = render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const layout = container.querySelector(".anchor-review-layout")!;
    const main = container.querySelector(".anchor-review-main")!;
    expect(layout.children[0]).toBe(main);
    expect(layout.children).toHaveLength(1);
    expect(container.querySelector(".visual-section-identity")).not.toBeInTheDocument();
    expect(container.querySelector(".anchor-review-assistant")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "本轮反馈记录" })).not.toBeInTheDocument();
    expect(container.querySelector(".anchor-batch-inline")).not.toBeInTheDocument();

    await readyActiveAnchor();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 8, button: 0, clientX: 100, clientY: 100, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 8, clientX: 420, clientY: 280, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 8, clientX: 420, clientY: 280, isPrimary: true });

    expect(canvas.nextElementSibling).toHaveClass("anchor-feedback-composer");
    expect(within(main as HTMLElement).getByLabelText("当前框选区域反馈")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: "降低底部信息权重" } });
    fireEvent.click(screen.getByRole("button", { name: "加入本轮反馈" }));

    const inlineBatch = container.querySelector<HTMLElement>(".anchor-batch-inline")!;
    expect(inlineBatch).toBeInTheDocument();
    expect(within(inlineBatch).getByRole("heading", { name: "本轮反馈" })).toBeInTheDocument();
    expect(within(inlineBatch).getByRole("button", { name: "统一提交 1 条反馈" })).toBeInTheDocument();
    expect(within(inlineBatch).getByText("降低底部信息权重")).toBeInTheDocument();
  });

  it("compares previous and current controlled images in a focus-safe modal and disables first-version comparison", async () => {
    const { bridge, callTool } = host();
    const { container } = render(
      <VisualProfessionalReviewPage
        initialData={visualData({ S01: "review-assets/anchors/S01-previous.png" })}
        bridge={bridge}
      />,
    );
    await screen.findByRole("img", { name: "S01 锚点页成果" });
    const compare = screen.getByRole("button", { name: "与上一版对比" });
    compare.focus();
    fireEvent.click(compare);

    const dialog = await screen.findByRole("dialog", { name: "S01 前后版本对比" });
    expect(screen.getByText("上一版")).toBeInTheDocument();
    expect(screen.getByText("当前版")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "S01 上一版锚点成果" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "S01 当前版锚点成果" })).toBeInTheDocument();
    const close = within(dialog).getByRole("button", { name: "关闭对比" });
    await waitFor(() => expect(close).toHaveFocus());
    expect(container.querySelector(".visual-professional-page")).toHaveAttribute("inert");
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "S01 前后版本对比" })).not.toBeInTheDocument();
    expect(compare).toHaveFocus();

    fireEvent.click(screen.getByRole("tab", { name: /S02/ }));
    const disabledCompare = screen.getByRole("button", { name: "与上一版对比" });
    expect(disabledCompare).toBeDisabled();
    expect(disabledCompare.parentElement).toHaveTextContent("当前为首个可审核版本");
    const assetRefs = callTool.mock.calls
      .filter(([name]) => name === "read_ai_ppt_project_asset")
      .map(([, args]) => (args as { assetRef: string }).assetRef);
    expect(assetRefs).toContain("review-assets/anchors/S01-previous.png");
    expect(assetRefs).not.toContain("");
  });

  it("restores the exact inert state that existed before comparison opened", async () => {
    const { bridge } = host();
    const { container } = render(
      <VisualProfessionalReviewPage
        initialData={visualData({ S01: "review-assets/anchors/S01-previous.png" })}
        bridge={bridge}
      />,
    );
    const background = container.querySelector(".visual-professional-page")!;
    background.setAttribute("inert", "existing");
    await screen.findByRole("img", { name: "S01 锚点页成果" });
    fireEvent.click(screen.getByRole("button", { name: "与上一版对比" }));
    const dialog = await screen.findByRole("dialog", { name: "S01 前后版本对比" });
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(background).toHaveAttribute("inert", "existing");
  });

  it("returns focus to the current anchor view when the comparison trigger is detached", async () => {
    const { bridge } = host();
    render(
      <VisualProfessionalReviewPage
        initialData={visualData({ S01: "review-assets/anchors/S01-previous.png" })}
        bridge={bridge}
      />,
    );
    await screen.findByRole("img", { name: "S01 锚点页成果" });
    const anchorView = screen.getByRole("region", { name: "3 页锚点成果" });
    const compare = screen.getByRole("button", { name: "与上一版对比" });
    compare.focus();
    fireEvent.click(compare);
    const dialog = await screen.findByRole("dialog", { name: "S01 前后版本对比" });
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "关闭对比" })).toHaveFocus());
    compare.remove();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(anchorView).toHaveFocus();
  });

  it("creates rectangles, keeps cross-slide drafts, and submits one immutable batch", async () => {
    mockSlideRect();
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("缩小标题字号");
    fireEvent.click(screen.getByRole("tab", { name: /S02/ }));
    await addRegion("增强因果关系");
    expect(screen.getByText("2 条待提交")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "统一提交 2 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "submit_visual_anchor_feedback_batch")).toBe(true));
    const call = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")!;
    const args = call[1] as { feedback: Array<Record<string, unknown>> };
    expect(args.feedback).toHaveLength(2);
    expect(args.feedback.map((item) => item.anchor_slide_id)).toEqual(["S01", "S02"]);
    expect(args.feedback.map((item) => item.order)).toEqual([1, 2]);
    expect((args.feedback[0].normalized_region as { x: number }).x).toBeCloseTo(0.1);
    expect((args.feedback[0].normalized_region as { width: number }).width).toBeCloseTo(0.32);
    expect(screen.getByText("反馈批次已保存")).toBeInTheDocument();
    expect(screen.getByText("反馈批次 anchor-batch-1")).toBeInTheDocument();
    expect(screen.getByText("宿主通知：不可用")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    expect(screen.getByText("保存反馈不等于 G3 通过")).toBeInTheDocument();
  });

  it("shows an automatic host send immediately after save without offering a duplicate retry", async () => {
    mockSlideRect();
    const { bridge } = host(async (args) => {
      const result = closedAnchorResult(args, visualData(), "auto-notified-anchor-batch");
      result.batch.host_notification_status = "sent";
      result.batch.ai_receipt_status = "pending";
      result.snapshot.revision = Number(args.expectedRevision) + 2;
      return result;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("自动通知成功后直接显示事实");

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));

    expect(await screen.findByText("宿主通知：已送达")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /重试宿主通知/ })).not.toBeInTheDocument();
  });

  it("recovers host notification and AI receipt separately for the exact freshly saved anchor batch", async () => {
    mockSlideRect();
    const data = visualData();
    data.review.host_submission_capability = "available";
    data.review.ai_receipt_capability = "available";
    const retryHost = vi.fn(async (input: Parameters<NonNullable<HostBridge["retryVisualHostNotification"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      hostNotificationStatus: "sent" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const verifyAi = vi.fn(async (input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      aiReceiptStatus: "received" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const { bridge, callTool } = host(undefined, undefined, {
      retryVisualHostNotification: retryHost,
      verifyVisualAiReceipt: verifyAi,
    });
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    await addRegion("保存后独立恢复宿主和 AI 事实");

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    expect(await screen.findByText("宿主通知：不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试宿主通知" }));

    await waitFor(() => expect(retryHost).toHaveBeenCalledOnce());
    expect(retryHost.mock.calls[0][0]).toEqual({
      projectRoot: "/managed/project",
      expectedRevision: 13,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: ANCHOR_FEEDBACK_BATCH_REF,
    });
    expect(await screen.findByText("宿主通知：已送达")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));
    await waitFor(() => expect(verifyAi).toHaveBeenCalledOnce());
    expect(verifyAi.mock.calls[0][0]).toEqual({
      projectRoot: "/managed/project",
      expectedRevision: 14,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: ANCHOR_FEEDBACK_BATCH_REF,
      receiptIdentity: ANCHOR_FEEDBACK_BATCH_REF,
    });
    expect(await screen.findByText("AI 接收：已接收")).toBeInTheDocument();
    expect(screen.getByText("visual-v1 · revision 15")).toBeInTheDocument();
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1);
  });

  it("shows recovery as unavailable when a saved anchor batch has no Browser recovery adapter", () => {
    const batch = { ...existingAnchorBatch(), host_notification_status: "unavailable" as const, ai_receipt_status: "unverified" as const };
    const data = visualData({}, batch);
    data.review.host_submission_capability = "available";
    data.review.ai_receipt_capability = "available";
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    expect(screen.getByText("宿主通知恢复：不可用")).toBeInTheDocument();
    expect(screen.getByText("AI 接收验证：不可用")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /重试宿主通知|验证 AI 接收/ })).not.toBeInTheDocument();
  });

  it.each(["not-requested", "pending"] as const)(
    "does not expose host retry while the saved host notification is %s",
    (hostNotificationStatus) => {
      const batch = {
        ...existingAnchorBatch(),
        host_notification_status: hostNotificationStatus,
        ai_receipt_status: "received" as const,
      };
      const data = visualData({}, batch);
      data.review.host_submission_capability = "available";
      const retryHost = vi.fn(async (input: Parameters<NonNullable<HostBridge["retryVisualHostNotification"]>>[0]) => ({
        savedArtifactRef: input.savedArtifactRef,
        hostNotificationStatus: "sent" as const,
        snapshotRevision: input.expectedRevision + 1,
      }));
      const { bridge } = host(undefined, undefined, {
        retryVisualHostNotification: retryHost,
      });

      render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

      expect(screen.queryByRole("button", { name: "重试宿主通知" })).not.toBeInTheDocument();
      expect(retryHost).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["a verifier failure", async () => { throw new Error("AI receipt rejected"); }],
    ["a wrong artifact reference", async (input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0]) => ({
      savedArtifactRef: "artifact://visual-anchor-feedback-batch/" + "f".repeat(64),
      aiReceiptStatus: "received" as const,
      snapshotRevision: input.expectedRevision + 1,
    })],
    ["a skipped authoritative revision", async (input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      aiReceiptStatus: "received" as const,
      snapshotRevision: input.expectedRevision + 2,
    })],
  ] as Array<[string, NonNullable<HostBridge["verifyVisualAiReceipt"]>]>) (
    "keeps AI unverified and revision unchanged after %s",
    async (_label, verifyAi) => {
      const batch = {
        ...existingAnchorBatch(),
        host_notification_status: "unavailable" as const,
        ai_receipt_status: "unverified" as const,
      };
      const data = visualData({}, batch);
      data.review.ai_receipt_capability = "available";
      const verifier = vi.fn(verifyAi);
      const { bridge } = host(undefined, undefined, {
        verifyVisualAiReceipt: verifier,
      });
      render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

      fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));

      expect(await screen.findByText("AI 接收仍未验证；已保存反馈不受影响，可再次验证。")).toBeInTheDocument();
      expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
      expect(screen.getByText("visual-v1 · revision 12")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "验证 AI 接收" })).toBeEnabled();
      expect(verifier).toHaveBeenCalledOnce();
      expect(verifier.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
    },
  );

  it("ignores a late AI recovery response after projection advances to a newer saved artifact", async () => {
    const pending = deferred<Awaited<ReturnType<NonNullable<HostBridge["verifyVisualAiReceipt"]>>>>();
    const verifyAi = vi.fn((
      _input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0],
      _options?: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[1],
    ) => pending.promise);
    const initial = visualData();
    initial.snapshotRevision = 20;
    initial.review.authoritative_revision = 20;
    initial.review.ai_receipt_capability = "available";
    const artifactA = CONTRACT_MARK_SET_REF;
    const markSetA = projectedContractMarkSet(20);
    markSetA.host_notification_status = "unavailable";
    markSetA.ai_receipt_status = "unverified";
    initial.review.contract_review_marks_ref = artifactA;
    initial.review.contract_review_marks = markSetA;
    const { bridge } = host(undefined, undefined, {
      verifyVisualAiReceipt: verifyAi,
    });
    const rendered = render(<VisualProfessionalReviewPage initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));
    await waitFor(() => expect(verifyAi).toHaveBeenCalledOnce());
    expect(verifyAi.mock.calls[0][0].savedArtifactRef).toBe(artifactA);

    const artifactB = "artifact://visual-contract-review-mark-set/" + "6".repeat(64);
    const projected = visualData();
    projected.snapshotRevision = 21;
    projected.review.authoritative_revision = 21;
    projected.review.ai_receipt_capability = "available";
    const markSetB = projectedContractMarkSet(21);
    markSetB.mark_set_id = "visual-marks-newer-projection";
    markSetB.marks[0].mark_id = "newer-projected-mark";
    markSetB.marks[0].comment = "新权威制品 B";
    markSetB.host_notification_status = "unavailable";
    markSetB.ai_receipt_status = "unverified";
    projected.review.contract_review_marks_ref = artifactB;
    projected.review.contract_review_marks = markSetB;
    rendered.rerender(<VisualProfessionalReviewPage initialData={projected} bridge={bridge} />);
    expect(await screen.findByText("visual-v1 · revision 21")).toBeInTheDocument();

    await act(async () => {
      pending.resolve({
        savedArtifactRef: artifactA,
        aiReceiptStatus: "received",
        snapshotRevision: 21,
      });
      await pending.promise;
      await Promise.resolve();
    });

    expect(screen.getByText("visual-v1 · revision 21")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "验证 AI 接收" })).toBeEnabled();
    expect(screen.queryByText("AI 接收已验证")).not.toBeInTheDocument();
    expect(verifyAi).toHaveBeenCalledOnce();
  });

  it("rejects an anchor save that claims an unverified direct AI receipt and preserves the draft", async () => {
    mockSlideRect();
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("保存后只确认持久化");

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "submit_visual_anchor_feedback_batch")).toBe(true));
    const submitted = (callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as {
      feedback: AnchorFeedbackBatch["items"];
    }).feedback;
    await act(async () => {
      pending.resolve({
        batch_ref: ANCHOR_FEEDBACK_BATCH_REF,
        batch: {
          ...existingAnchorBatch(),
          batch_id: "anchor-batch-receipt-spoof",
          items: submitted,
          host_notification_status: "sent",
          ai_receipt_status: "received",
          submitted_at: new Date().toISOString(),
        },
        snapshot: { revision: 14 },
      });
      await pending.promise;
    });

    expect(await screen.findByText("提交结果未闭合，请刷新/重新打开核对权威批次")).toBeInTheDocument();
    expect(screen.getByText("保存后只确认持久化")).toBeInTheDocument();
    expect(screen.getByText(/revision 12/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeDisabled();
    expect(screen.queryByText("反馈批次 anchor-batch-receipt-spoof")).not.toBeInTheDocument();
    const facts = screen.getByLabelText("反馈提交事实");
    expect(within(facts).getAllByText(/无法确认，请刷新\/重新打开/)).toHaveLength(3);
    expect(facts).not.toHaveTextContent(/已保存|已送达|已接收/);
  });

  it("preserves an uncommitted composer per slide and blocks batch submission until it is resolved", async () => {
    mockSlideRect();
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("已经加入的第一条反馈");

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 21, button: 0, clientX: 120, clientY: 120, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 21, clientX: 520, clientY: 320, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 21, clientX: 520, clientY: 320, isPrimary: true });
    fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: "尚未加入的第二条反馈" } });

    const submit = screen.getByRole("button", { name: "统一提交 1 条反馈" });
    expect(submit).toBeDisabled();
    expect(screen.getByText(/请先加入本轮反馈或放弃当前输入/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /S02/ }));
    fireEvent.click(screen.getByRole("tab", { name: /S01/ }));
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("尚未加入的第二条反馈");
    fireEvent.click(submit);
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(0);
  });

  it("freezes add edit and remove against the submitted snapshot while batch persistence is pending", async () => {
    mockSlideRect();
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("提交快照中的反馈");

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "submit_visual_anchor_feedback_batch")).toBe(true));
    const remove = screen.getByRole("button", { name: "移除" });
    const savedRegion = screen.getByRole("button", { name: "S01 已标注区域 1" });
    expect(remove).toBeDisabled();
    expect(savedRegion).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeDisabled();
    fireEvent.click(remove);
    fireEvent.click(savedRegion);
    expect(screen.getByText("提交快照中的反馈")).toBeInTheDocument();
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();

    const submitted = (callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as {
      feedback: AnchorFeedbackBatch["items"];
    }).feedback;
    await act(async () => {
      pending.resolve({
        batch_ref: ANCHOR_FEEDBACK_BATCH_REF,
        batch: {
          ...existingAnchorBatch(),
          batch_id: "anchor-batch-pending",
          items: submitted,
          submitted_at: new Date().toISOString(),
        },
        snapshot: { revision: 13 },
      });
      await pending.promise;
    });
    expect(screen.getByText("反馈批次 anchor-batch-pending")).toBeInTheDocument();
    expect(screen.getByText("提交快照中的反馈")).toBeInTheDocument();
    expect(screen.getByText("1 条已提交")).toBeInTheDocument();
  });

  it("uses the current revision once and requires recovery after a malformed batch response", async () => {
    mockSlideRect();
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("保留证据但降低视觉重量");

    const submit = screen.getByRole("button", { name: "统一提交 1 条反馈" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1);
    const call = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")!;
    expect(call[1]).toEqual(expect.objectContaining({ expectedRevision: 12 }));

    await act(async () => {
      pending.resolve({
        batch_ref: ANCHOR_FEEDBACK_BATCH_REF,
        batch: { persistence_status: "saved", immutable_after_submit: true },
        snapshot: { revision: 99 },
      });
      await pending.promise;
    });
    expect(screen.getByText("提交结果未闭合，请刷新/重新打开核对权威批次")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeDisabled();
    expect(screen.getByText(/revision 12/)).toBeInTheDocument();
    expect(screen.queryByText("本轮反馈已冻结")).not.toBeInTheDocument();
    const facts = screen.getByLabelText("反馈提交事实");
    expect(within(facts).getByText("持久化：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(within(facts).getByText("宿主通知：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(within(facts).getByText("AI 接收：无法确认，请刷新/重新打开")).toBeInTheDocument();
    expect(facts).not.toHaveTextContent(/尚未提交|尚无批次回执|已保存|已送达|已接收/);
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1);
  });

  it.each(anchorResultAttacks)("rejects hostile anchor result plain data: %s", async (_label, attackResult) => {
    const data = visualData();
    const expectedUi = visualDraftUi({
      current_anchor_slide_id: "S01",
      anchor_feedback_drafts: [anchorDraft("hostile 结果后必须保留的反馈")],
    });
    const key = seedVisualDraft(data, expectedUi);
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.load(await screen.findByRole("img", { name: "S01 锚点页成果" }));

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(
      callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch"),
    ).toHaveLength(1));
    const args = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as Record<string, unknown>;
    const attacked = attackResult(
      closedAnchorResult(args, data, "hostile-anchor-result") as Record<string, unknown>,
    );
    await act(async () => {
      pending.resolve(attacked.result);
      await pending.promise;
    });

    expect(attacked.getterReads()).toBe(0);
    expect(screen.getByText("提交结果未闭合，请刷新/重新打开核对权威批次")).toBeInTheDocument();
    expect(screen.queryByText("反馈批次已保存")).not.toBeInTheDocument();
    expect(screen.queryByText("反馈批次 hostile-anchor-result")).not.toBeInTheDocument();
    expect(screen.getByText("1 条待提交")).toBeInTheDocument();
    expect(screen.getByText("hostile 结果后必须保留的反馈")).toBeInTheDocument();
    expect(screen.getByText(/revision 12/)).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui).toEqual(expectedUi);
  });

  it("fails a closed anchor save result with an unsafe next revision without installing its batch or revision", async () => {
    mockSlideRect();
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(() => pending.promise);
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("不安全后继 revision 也必须保留");

    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "submit_visual_anchor_feedback_batch")).toBe(true));
    const submitted = (callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")![1] as {
      feedback: AnchorFeedbackBatch["items"];
    }).feedback;
    await act(async () => {
      pending.resolve({
        batch_ref: ANCHOR_FEEDBACK_BATCH_REF,
        batch: {
          ...existingAnchorBatch(),
          batch_id: "anchor-batch-unsafe-next",
          items: submitted,
          submitted_at: new Date().toISOString(),
        },
        snapshot: { revision: Number.MAX_SAFE_INTEGER + 1 },
      });
      await pending.promise;
    });

    expect(screen.getByText("提交结果未闭合，请刷新/重新打开核对权威批次")).toBeInTheDocument();
    expect(screen.queryByText("反馈批次已保存")).not.toBeInTheDocument();
    expect(screen.queryByText("反馈批次 anchor-batch-unsafe-next")).not.toBeInTheDocument();
    expect(screen.getByText("1 条待提交")).toBeInTheDocument();
    expect(screen.getByText("不安全后继 revision 也必须保留")).toBeInTheDocument();
    expect(screen.getByText(/revision 12/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "统一提交 1 条反馈" })).toBeDisabled();
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(1);
  });

  it.each([
    ["terminal safe integer", Number.MAX_SAFE_INTEGER],
    ["unsafe integer", Number.MAX_SAFE_INTEGER + 1],
  ])("puts direct anchor feedback into read-only protection at a %s command revision", async (_label, invalidRevision) => {
    mockSlideRect();
    const data = visualData();
    const { bridge, callTool } = host();
    const onRevision = vi.fn();
    const rendered = render(
      <ControlledAnchorResults data={data} bridge={bridge} revision={12} onRevision={onRevision} />,
    );
    await addRegion("无效 revision 时仍保留的本地反馈");

    rendered.rerender(
      <ControlledAnchorResults data={data} bridge={bridge} revision={invalidRevision} onRevision={onRevision} />,
    );

    expect(screen.getByText(/revision 无效.*只读.*重新打开/)).toBeInTheDocument();
    expect(screen.getByText("1 条待提交")).toBeInTheDocument();
    expect(screen.getByText("无效 revision 时仍保留的本地反馈")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "统一提交 1 条反馈" });
    expect(submit).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "移除" })).toBeDisabled();
    fireEvent.click(submit);
    expect(callTool.mock.calls.filter(([name]) => name === "submit_visual_anchor_feedback_batch")).toHaveLength(0);
    expect(onRevision).not.toHaveBeenCalled();
  });

  it("cancels point-like drags instead of creating a feedback marker", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await readyActiveAnchor();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 2, button: 0, clientX: 100, clientY: 100, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 2, clientX: 105, clientY: 105, isPrimary: true });
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("框选范围过小");
  });

  it("clears an in-progress region on lost pointer capture and never exposes its composer", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await readyActiveAnchor();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 31, button: 0, clientX: 100, clientY: 100, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 31, clientX: 420, clientY: 280, isPrimary: true });
    fireEvent.lostPointerCapture(canvas, { pointerId: 31 });
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "加入本轮反馈" })).not.toBeInTheDocument();
  });

  it.each([
    { width: 0, height: 0, label: "zero" },
    { width: Number.NaN, height: 562, label: "non-finite" },
  ])("rejects $label client geometry before starting a region", async ({ width, height }) => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, top: 0, left: 0, right: width, bottom: height,
      width, height, toJSON: () => ({}),
    });
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await readyActiveAnchor();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 32, button: 0, clientX: 0, clientY: 0, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 32, clientX: 300, clientY: 200, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 32, clientX: 300, clientY: 200, isPrimary: true });
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
  });

  it("normalizes reverse drag and releases capture only when still owned", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await readyActiveAnchor();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas") as HTMLDivElement & {
      hasPointerCapture: ReturnType<typeof vi.fn>;
      releasePointerCapture: ReturnType<typeof vi.fn>;
    };
    canvas.hasPointerCapture = vi.fn(() => false);
    canvas.releasePointerCapture = vi.fn();
    fireEvent.pointerDown(canvas, { pointerId: 33, button: 0, clientX: 600, clientY: 400, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 33, clientX: 200, clientY: 100, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 33, clientX: 200, clientY: 100, isPrimary: true });
    expect(screen.getByLabelText("当前框选区域反馈")).toBeInTheDocument();
    expect(canvas.releasePointerCapture).not.toHaveBeenCalled();
  });

  it("gates annotation on actual image load and closes it again after decode failure", async () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const start = screen.getByRole("button", { name: "开始标注" });
    expect(start).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("预览加载完成后可标注");

    const image = await screen.findByRole("img", { name: "S01 锚点页成果" });
    expect(start).toBeDisabled();
    fireEvent.load(image);
    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(start).toHaveTextContent("取消标注");
    fireEvent.error(image);
    expect(start).toBeDisabled();
    expect(start).toHaveTextContent("开始标注");
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("预览加载失败，请重试后再标注");
  });

  it("preserves a persisted composer through image failure until explicit discard", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("已经加入的反馈");

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 81, button: 0, clientX: 120, clientY: 120, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 81, clientX: 520, clientY: 320, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 81, clientX: 520, clientY: 320, isPrimary: true });
    const composer = screen.getByLabelText("当前框选区域反馈");
    fireEvent.change(composer, { target: { value: "图片恢复后仍要保留的意见" } });
    const candidateStyle = document.querySelector<HTMLElement>(".anchor-region.candidate")?.getAttribute("style");
    const submit = screen.getByRole("button", { name: "统一提交 1 条反馈" });
    expect(submit).toBeDisabled();

    fireEvent.error(screen.getByRole("img", { name: "S01 锚点页成果" }));
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("图片恢复后仍要保留的意见");
    expect(screen.getByLabelText("当前框选区域反馈")).toBeDisabled();
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "放弃当前输入" })).toBeEnabled();
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", candidateStyle);
    expect(submit).toBeDisabled();
    expect(screen.getByText(/请先加入本轮反馈或放弃当前输入/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "预览暂不可读，点击重试" }));
    const reloaded = await screen.findByRole("img", { name: "S01 锚点页成果" });
    expect(screen.getByLabelText("当前框选区域反馈")).toBeDisabled();
    fireEvent.load(reloaded);
    expect(screen.getByLabelText("当前框选区域反馈")).toBeEnabled();
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("图片恢复后仍要保留的意见");
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", candidateStyle);
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "放弃当前输入" }));
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(submit).toBeEnabled();
    expect(screen.queryByText(/请先加入本轮反馈或放弃当前输入/)).not.toBeInTheDocument();
  });

  it("blocks a new annotation after retry until the persisted composer is explicitly discarded", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const { candidateStyle, comment } = await recoverPersistedComposer();

    const start = screen.getByRole("button", { name: "开始标注" });
    expect(start).toBeDisabled();
    fireEvent.click(start);
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue(comment);
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", candidateStyle);
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "放弃当前输入" }));
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(start).toHaveTextContent("取消标注");
    fireEvent.click(start);
    expect(start).toHaveTextContent("开始标注");
  });

  it("blocks saved-region editing from overwriting a recovered persisted composer", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const { candidateStyle, comment } = await recoverPersistedComposer();

    const savedRegion = screen.getByRole("button", { name: "S01 已标注区域 1" });
    expect(savedRegion).toBeDisabled();
    fireEvent.click(savedRegion);
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue(comment);
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", candidateStyle);
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "更新本条反馈" })).not.toBeInTheDocument();
  });

  it.each([
    ["pointercancel", (canvas: HTMLElement) => fireEvent.pointerCancel(canvas, { pointerId: 91 })],
    ["lostpointercapture", (canvas: HTMLElement) => fireEvent.lostPointerCapture(canvas, { pointerId: 91 })],
  ])("keeps a recovered persisted composer on %s", async (_eventName, dispatch) => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const { canvas, candidateStyle, comment } = await recoverPersistedComposer();

    dispatch(canvas);
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue(comment);
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", candidateStyle);
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeInTheDocument();
  });

  it("closes annotation and protects saved-region editing without visible presets", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("已保存区域的原意见");

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    expect(screen.queryByRole("group", { name: "预设标注范围" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "S01 已标注区域 1" }));
    expect(screen.getByRole("button", { name: "更新本条反馈" })).toBeInTheDocument();
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("已保存区域的原意见");
    fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: "更新后的已保存意见" } });
    fireEvent.click(screen.getByRole("button", { name: "更新本条反馈" }));
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();

    const start = screen.getByRole("button", { name: "开始标注" });
    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(screen.queryByRole("group", { name: "预设标注范围" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消标注" })).toBeInTheDocument();
  });

  it("prevents active or subsequent drags from overwriting saved-region editing until discard", async () => {
    mockSlideRect();
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("拖动不能覆盖的已保存意见");

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 101, button: 0, clientX: 140, clientY: 130, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 101, clientX: 360, clientY: 260, isPrimary: true });
    fireEvent.click(screen.getByRole("button", { name: "S01 已标注区域 1" }));
    const editingStyle = document.querySelector<HTMLElement>(".anchor-region.candidate")?.getAttribute("style");
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("拖动不能覆盖的已保存意见");

    fireEvent.pointerUp(canvas, { pointerId: 101, clientX: 680, clientY: 420, isPrimary: true });
    fireEvent.pointerDown(canvas, { pointerId: 102, button: 0, clientX: 220, clientY: 180, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 102, clientX: 720, clientY: 450, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 102, clientX: 720, clientY: 450, isPrimary: true });
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveValue("拖动不能覆盖的已保存意见");
    expect(document.querySelector<HTMLElement>(".anchor-region.candidate")).toHaveAttribute("style", editingStyle);
    expect(screen.getByRole("button", { name: "更新本条反馈" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "放弃当前输入" }));
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    fireEvent.pointerDown(canvas, { pointerId: 103, button: 0, clientX: 220, clientY: 180, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 103, clientX: 720, clientY: 450, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 103, clientX: 720, clientY: 450, isPrimary: true });
    expect(screen.getByLabelText("当前框选区域反馈")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入本轮反馈" })).toBeInTheDocument();
  });

  it("keeps pointer-drag feedback as the only formal region path without introducing a chat sidebar", async () => {
    mockSlideRect();
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await readyActiveAnchor();

    const start = screen.getByRole("button", { name: "开始标注" });
    start.focus();
    fireEvent.click(start, { detail: 0 });
    expect(screen.queryByRole("group", { name: "预设标注范围" })).not.toBeInTheDocument();
    for (const preset of ["整页", "上半区", "下半区", "左侧", "右侧"]) {
      expect(screen.queryByRole("button", { name: preset })).not.toBeInTheDocument();
    }

    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 131, button: 0, clientX: 500, clientY: 120, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 131, clientX: 760, clientY: 420, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 131, clientX: 760, clientY: 420, isPrimary: true });
    expect(screen.getByLabelText("当前框选区域反馈")).toHaveFocus();
    fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: "压缩框选区域的证据密度" } });
    fireEvent.click(screen.getByRole("button", { name: "加入本轮反馈" }), { detail: 0 });
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }), { detail: 0 });

    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "submit_visual_anchor_feedback_batch")).toBe(true));
    const call = callTool.mock.calls.find(([name]) => name === "submit_visual_anchor_feedback_batch")!;
    const submitted = (call[1] as { feedback: AnchorFeedbackBatch["items"] }).feedback[0];
    expect(submitted.normalized_region.x).toBeCloseTo(0.5, 10);
    expect(submitted.normalized_region.y).toBeCloseTo(120 / 562, 10);
    expect(submitted.normalized_region.width).toBeCloseTo(0.26, 10);
    expect(submitted.normalized_region.height).toBeCloseTo(300 / 562, 10);
    expect(screen.queryByRole("complementary", { name: /聊天/ })).not.toBeInTheDocument();
  });

  it("uses roving keyboard tabs and linked tabpanels for the two review views", () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const tablist = screen.getByRole("tablist", { name: "视觉专业审核视图" });
    const anchors = within(tablist).getByRole("tab", { name: "3 页锚点成果" });
    const contract = within(tablist).getByRole("tab", { name: "完整视觉合同" });

    expect(anchors).toHaveAttribute("tabindex", "0");
    expect(contract).toHaveAttribute("tabindex", "-1");
    expect(anchors.id).not.toBe("");
    expect(anchors.getAttribute("aria-controls")).not.toBeNull();
    const anchorPanel = document.getElementById(anchors.getAttribute("aria-controls")!);
    expect(anchorPanel).toHaveAttribute("role", "tabpanel");
    expect(anchorPanel).toHaveAttribute("aria-labelledby", anchors.id);

    anchors.focus();
    fireEvent.keyDown(anchors, { key: "ArrowRight" });
    expect(contract).toHaveFocus();
    expect(contract).toHaveAttribute("aria-selected", "true");
    expect(contract).toHaveAttribute("tabindex", "0");
    expect(anchors).toHaveAttribute("tabindex", "-1");
    const contractPanel = document.getElementById(contract.getAttribute("aria-controls")!);
    expect(contractPanel).toHaveAttribute("role", "tabpanel");
    expect(contractPanel).toHaveAttribute("aria-labelledby", contract.id);

    fireEvent.keyDown(contract, { key: "Home" });
    expect(anchors).toHaveFocus();
    expect(anchors).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(anchors, { key: "End" });
    expect(contract).toHaveFocus();
    fireEvent.keyDown(contract, { key: "ArrowRight" });
    expect(anchors).toHaveFocus();
  });

  it("keeps ids, relationships, scrolling, dialogs, and focus isolated across two visual-review instances", async () => {
    const firstData = visualData({ S01: "review-assets/anchors/S01-previous.png" });
    const secondData = structuredClone(firstData);
    secondData.review.project_id = "p2";
    secondData.review.project_name = "第二测试项目";
    secondData.review.review_session_id = "visual-session-2";
    const { bridge } = host();
    const { container } = render(
      <>
        <div data-review-instance="first">
          <VisualProfessionalReviewPage initialData={firstData} bridge={bridge} />
        </div>
        <div data-review-instance="second">
          <VisualProfessionalReviewPage initialData={secondData} bridge={bridge} />
        </div>
      </>,
    );
    const firstInstance = container.querySelector<HTMLElement>('[data-review-instance="first"]')!;
    const secondInstance = container.querySelector<HTMLElement>('[data-review-instance="second"]')!;
    const firstPage = firstInstance.querySelector<HTMLElement>(".visual-professional-page")!;
    const secondPage = secondInstance.querySelector<HTMLElement>(".visual-professional-page")!;
    const firstTabs = within(firstInstance).getByRole("tablist", { name: "视觉专业审核视图" });
    const secondTabs = within(secondInstance).getByRole("tablist", { name: "视觉专业审核视图" });

    fireEvent.click(within(secondTabs).getByRole("tab", { name: "完整视觉合同" }));
    expect(within(firstTabs).getByRole("tab", { name: "3 页锚点成果" })).toHaveAttribute("aria-selected", "true");
    expect(within(secondTabs).getByRole("tab", { name: "完整视觉合同" })).toHaveAttribute("aria-selected", "true");

    const firstDesignSystem = firstInstance.querySelector<HTMLElement>('[data-contract-logical-object="deck-design-system"]')!;
    const secondDesignSystem = secondInstance.querySelector<HTMLElement>('[data-contract-logical-object="deck-design-system"]')!;
    const firstScroll = vi.fn();
    const secondScroll = vi.fn();
    firstDesignSystem.scrollIntoView = firstScroll;
    secondDesignSystem.scrollIntoView = secondScroll;
    fireEvent.click(within(secondInstance).getByRole("button", { name: "打开合同目录" }));
    fireEvent.click(within(secondInstance).getByRole("button", { name: "Deck Design System" }));
    await waitFor(() => expect(secondScroll).toHaveBeenCalled());
    expect.soft(firstScroll).not.toHaveBeenCalled();

    fireEvent.click(within(secondTabs).getByRole("tab", { name: "3 页锚点成果" }));
    const firstCompare = within(firstInstance).getByRole("button", { name: "与上一版对比" });
    const secondCompare = within(secondInstance).getByRole("button", { name: "与上一版对比" });
    firstCompare.focus();
    fireEvent.click(firstCompare);
    secondCompare.focus();
    fireEvent.click(secondCompare);
    const dialogs = await screen.findAllByRole("dialog", { name: "S01 前后版本对比" });
    expect(dialogs).toHaveLength(2);
    expect.soft(firstPage).toHaveAttribute("inert");
    expect.soft(secondPage).toHaveAttribute("inert");
    for (const dialog of dialogs) {
      const labelledBy = dialog.getAttribute("aria-labelledby");
      expect.soft(labelledBy).toBeTruthy();
      expect.soft(Array.from(dialog.querySelectorAll("[id]")).some((node) => node.id === labelledBy)).toBe(true);
    }
    fireEvent.click(within(dialogs[1]).getByRole("button", { name: "关闭对比" }));
    expect(dialogs[0]).toContainElement(document.activeElement as HTMLElement);
    expect(secondCompare).not.toHaveFocus();
    fireEvent.click(within(dialogs[0]).getByRole("button", { name: "关闭对比" }));
    expect(firstCompare).toHaveFocus();

    const allIds = Array.from(document.querySelectorAll<HTMLElement>("[id]")).map((node) => node.id);
    expect.soft(new Set(allIds).size).toBe(allIds.length);
    for (const instance of [firstInstance, secondInstance]) {
      for (const controller of instance.querySelectorAll<HTMLElement>("[aria-controls]")) {
        const target = document.getElementById(controller.getAttribute("aria-controls") || "");
        expect.soft(target).not.toBeNull();
        expect.soft(instance.contains(target)).toBe(true);
      }
      for (const labelled of instance.querySelectorAll<HTMLElement>("[aria-labelledby]")) {
        const label = document.getElementById(labelled.getAttribute("aria-labelledby") || "");
        expect.soft(label).not.toBeNull();
        expect.soft(instance.contains(label)).toBe(true);
      }
    }
  });

  it("keeps the top dialog focused and the document locked when two instance modals close non-LIFO", async () => {
    document.body.style.overflow = "clip";
    const firstData = visualData({ S01: "review-assets/anchors/S01-previous.png" });
    const secondData = secondModalVisualData();
    const { bridge } = host();
    const { container } = render(
      <>
        <div data-review-instance="first-modal">
          <VisualProfessionalReviewPage initialData={firstData} bridge={bridge} />
        </div>
        <div data-review-instance="second-modal">
          <VisualProfessionalReviewPage initialData={secondData} bridge={bridge} />
        </div>
      </>,
    );
    const firstInstance = container.querySelector<HTMLElement>('[data-review-instance="first-modal"]')!;
    const secondInstance = container.querySelector<HTMLElement>('[data-review-instance="second-modal"]')!;
    const firstCompare = within(firstInstance).getByRole("button", { name: "与上一版对比" });
    const secondCompare = within(secondInstance).getByRole("button", { name: "与上一版对比" });

    firstCompare.focus();
    fireEvent.click(firstCompare);
    const firstDialog = await screen.findByRole("dialog", { name: "S01 前后版本对比" });
    secondCompare.focus();
    fireEvent.click(secondCompare);
    const secondDialog = await screen.findByRole("dialog", { name: "S02 前后版本对比" });
    await waitFor(() => expect(within(secondDialog).getByRole("button", { name: "关闭对比" })).toHaveFocus());
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.click(within(firstDialog).getByRole("button", { name: "关闭对比" }));

    expect(screen.queryByRole("dialog", { name: "S01 前后版本对比" })).not.toBeInTheDocument();
    expect(secondDialog).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
    expect(firstCompare).not.toHaveFocus();
    expect(secondDialog).toContainElement(document.activeElement as HTMLElement);

    fireEvent.click(within(secondDialog).getByRole("button", { name: "关闭对比" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("clip");
    expect(secondCompare).toHaveFocus();
  });

  it("hands focus down the modal stack for LIFO close and survives StrictMode cleanup replay", async () => {
    document.body.style.overflow = "scroll";
    const firstData = visualData({ S01: "review-assets/anchors/S01-previous.png" });
    const secondData = secondModalVisualData();
    const { bridge } = host();
    const rendered = render(
      <StrictMode>
        <div data-review-instance="first-lifo-modal">
          <VisualProfessionalReviewPage initialData={firstData} bridge={bridge} />
        </div>
        <div data-review-instance="second-lifo-modal">
          <VisualProfessionalReviewPage initialData={secondData} bridge={bridge} />
        </div>
      </StrictMode>,
    );
    const firstInstance = rendered.container.querySelector<HTMLElement>('[data-review-instance="first-lifo-modal"]')!;
    const secondInstance = rendered.container.querySelector<HTMLElement>('[data-review-instance="second-lifo-modal"]')!;
    const firstCompare = within(firstInstance).getByRole("button", { name: "与上一版对比" });
    const secondCompare = within(secondInstance).getByRole("button", { name: "与上一版对比" });

    firstCompare.focus();
    fireEvent.click(firstCompare);
    const firstDialog = await screen.findByRole("dialog", { name: "S01 前后版本对比" });
    secondCompare.focus();
    fireEvent.click(secondCompare);
    const secondDialog = await screen.findByRole("dialog", { name: "S02 前后版本对比" });
    await waitFor(() => expect(within(secondDialog).getByRole("button", { name: "关闭对比" })).toHaveFocus());

    fireEvent.click(within(secondDialog).getByRole("button", { name: "关闭对比" }));

    expect(document.body.style.overflow).toBe("hidden");
    expect(secondCompare).not.toHaveFocus();
    expect(firstDialog).toContainElement(document.activeElement as HTMLElement);

    fireEvent.click(within(firstDialog).getByRole("button", { name: "关闭对比" }));

    expect(document.body.style.overflow).toBe("scroll");
    expect(firstCompare).toHaveFocus();
    rendered.unmount();
    expect(document.body.style.overflow).toBe("scroll");
  });

  it("uses roving keyboard tabs and a linked panel for the anchor slide set", () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    const tablist = screen.getByRole("tablist", { name: "锚点页切换" });
    const tabs = within(tablist).getAllByRole("tab");

    expect(tabs.map((tab) => tab.getAttribute("tabindex"))).toEqual(["0", "-1", "-1"]);
    expect(tabs[0].id).not.toBe("");
    const firstPanel = document.getElementById(tabs[0].getAttribute("aria-controls")!);
    expect(firstPanel).toHaveAttribute("role", "tabpanel");
    expect(firstPanel).toHaveAttribute("aria-labelledby", tabs[0].id);

    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: "ArrowRight" });
    expect(tabs[1]).toHaveFocus();
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(tabs.map((tab) => tab.getAttribute("tabindex"))).toEqual(["-1", "0", "-1"]);
    const secondPanel = document.getElementById(tabs[1].getAttribute("aria-controls")!);
    expect(secondPanel).toHaveAttribute("role", "tabpanel");
    expect(secondPanel).toHaveAttribute("aria-labelledby", tabs[1].id);

    fireEvent.keyDown(tabs[1], { key: "End" });
    expect(tabs[2]).toHaveFocus();
    fireEvent.keyDown(tabs[2], { key: "Home" });
    expect(tabs[0]).toHaveFocus();
    fireEvent.keyDown(tabs[0], { key: "ArrowLeft" });
    expect(tabs[2]).toHaveFocus();
  });

  it.each([
    {
      identity: "review session",
      mutate: (data: VisualReviewSurfaceData) => { data.review.review_session_id = "visual-session-2"; },
    },
    {
      identity: "source version",
      mutate: (data: VisualReviewSurfaceData) => { data.review.source_version = "visual-v2"; },
    },
    {
      identity: "anchor slide set",
      mutate: (data: VisualReviewSurfaceData) => { data.review.anchor_slide_set_ref = NEXT_ANCHOR_SLIDE_SET_REF; },
    },
  ])("remounts drafts and composer when $identity changes", async ({ mutate }) => {
    mockSlideRect();
    const { bridge } = host();
    const { rerender } = render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("旧身份中的已加入反馈");
    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    fireEvent.pointerDown(canvas, { pointerId: 71, button: 0, clientX: 120, clientY: 120, isPrimary: true });
    fireEvent.pointerMove(canvas, { pointerId: 71, clientX: 520, clientY: 320, isPrimary: true });
    fireEvent.pointerUp(canvas, { pointerId: 71, clientX: 520, clientY: 320, isPrimary: true });
    fireEvent.change(screen.getByLabelText("当前框选区域反馈"), { target: { value: "旧身份中的未加入反馈" } });

    const nextData = visualData();
    mutate(nextData);
    rerender(<VisualProfessionalReviewPage initialData={nextData} bridge={bridge} />);
    expect(screen.queryByText("旧身份中的已加入反馈")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("旧身份中的未加入反馈")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("当前框选区域反馈")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "本轮反馈批次" })).not.toBeInTheDocument();
  });

  it("does not retain a submitted batch across a source identity change", async () => {
    mockSlideRect();
    const { bridge } = host();
    const { rerender } = render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    await addRegion("只属于旧来源的反馈批次");
    fireEvent.click(screen.getByRole("button", { name: "统一提交 1 条反馈" }));
    expect(await screen.findByText("反馈批次 anchor-batch-1")).toBeInTheDocument();

    const nextData = visualData();
    nextData.review.source_version = "visual-v2";
    rerender(<VisualProfessionalReviewPage initialData={nextData} bridge={bridge} />);
    expect(screen.queryByText("反馈批次 anchor-batch-1")).not.toBeInTheDocument();
    expect(screen.queryByText("只属于旧来源的反馈批次")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "本轮反馈批次" })).not.toBeInTheDocument();
  });

  it.each([
    {
      identity: "review session",
      mutate: (data: VisualReviewSurfaceData) => { data.review.review_session_id = "visual-session-2"; },
    },
    {
      identity: "source version",
      mutate: (data: VisualReviewSurfaceData) => { data.review.source_version = "visual-v2"; },
    },
    {
      identity: "visual contract",
      mutate: (data: VisualReviewSurfaceData) => { data.review.visual_contract_ref = NEXT_VISUAL_CONTRACT_REF; },
    },
  ])("remounts contract drafts and composer when $identity changes", ({ mutate }) => {
    const { bridge } = host();
    const { rerender } = render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "旧身份中的合同草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 构图意图" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "旧身份中的合同输入" } });

    const nextData = visualData();
    nextData.snapshotRevision = 30;
    mutate(nextData);
    rerender(<VisualProfessionalReviewPage initialData={nextData} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    expect(screen.queryByText("旧身份中的合同草稿")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("旧身份中的合同输入")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("30");
    expect(screen.getByLabelText("视觉合同操作").querySelector(".visual-contract-command-status")).toHaveTextContent("所有标记已保存");
  });

  it("ignores an old pending contract save after a complete identity change", async () => {
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    const { rerender } = render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "旧身份待返回的标记" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    const oldArgs = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as Record<string, unknown>;

    const nextData = visualData();
    nextData.snapshotRevision = 30;
    nextData.review.review_session_id = "visual-session-2";
    nextData.review.source_version = "visual-v2";
    nextData.review.visual_contract_ref = NEXT_VISUAL_CONTRACT_REF;
    rerender(<VisualProfessionalReviewPage initialData={nextData} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 核心主张" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "新身份中的合同草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 构图意图" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "新身份中的未提交输入" } });

    await act(async () => {
      pending.resolve(contractMarkResult(oldArgs));
      await pending.promise;
    });

    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("30");
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");
    expect(screen.getByText("新身份中的合同草稿")).toBeInTheDocument();
    expect(screen.getByLabelText("合同标记意见")).toHaveValue("新身份中的未提交输入");
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
  });

  it("converges the contract first screen without a technical identity module", () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    expect(screen.getAllByText("完整视觉合同", { exact: true })).toHaveLength(2);
    const document = screen.getByRole("region", { name: "完整视觉合同正文" });
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page");
    expect(titlePage).not.toBeNull();
    expect(within(titlePage as HTMLElement).getByText("Visual Contract · User Review")).toBeInTheDocument();
    expect(within(document).getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(within(document).getByRole("heading", { level: 1, name: "完整视觉合同" })).toBeInTheDocument();
    expect(titlePage).toHaveTextContent("测试项目");
    expect(titlePage).not.toHaveTextContent("visual-v1");
    expect(titlePage).toHaveTextContent("revision 12");
    expect(titlePage).toHaveTextContent("2 页逐页合同");
    expect(titlePage).not.toHaveTextContent(/G1|G2|G3|user-reviewable/);
    expect(screen.queryByRole("region", { name: "视觉合同摘要" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("视觉合同操作").querySelector(".visual-contract-command-status")).toHaveTextContent("所有标记已保存");
    expect(screen.queryByText("技术信息")).not.toBeInTheDocument();
    for (const reference of [
      VISUAL_CONTRACT_REF,
      DECK_DESIGN_SYSTEM_REF,
      ANCHOR_SLIDE_SET_REF,
      "artifact://native-pptx/" + "a".repeat(64),
      "artifact://editability-evidence/" + "c".repeat(64),
      "artifact://preflight-render/" + "d".repeat(64),
    ]) {
      expect(screen.queryByText(reference)).not.toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: reference })).not.toBeInTheDocument();
    }

    expect(screen.getByText(/原生可编辑与预检渲染证据已登记/)).toBeInTheDocument();
    const anchorEvidence = document.querySelector<HTMLElement>('[data-contract-logical-object="anchor-slide-evidence"]');
    expect(anchorEvidence).not.toBeNull();
    expect(within(anchorEvidence as HTMLElement).getByRole("heading", { name: "Anchor Slide Evidence" })).toBeInTheDocument();
    expect(within(anchorEvidence as HTMLElement).getByText("覆盖问题、方案和证据三类页面")).toBeInTheDocument();
    expect(screen.getAllByText("覆盖问题、方案和证据三类页面")).toHaveLength(1);
    expect(anchorEvidence?.querySelector(".visual-contract-footnote")).toHaveTextContent("覆盖问题、方案和证据三类页面");
    expect(screen.getByRole("region", { name: "全部逐页视觉合同" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "首屏摘要测试" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    const commandStatus = screen.getByLabelText("视觉合同操作").querySelector<HTMLElement>(".visual-contract-command-status")!;
    expect(commandStatus).toHaveTextContent("1 条待保存标记");
    expect(commandStatus).toHaveAttribute("aria-live", "polite");
    expect(commandStatus).toHaveAttribute("aria-atomic", "true");

    const commandbar = screen.getByLabelText("视觉合同操作");
    expect(VISUAL_REVIEW_CSS).not.toMatch(/\.visual-contract-commandbar\s*\{[^}]*position:\s*sticky;/s);
    const topSave = within(commandbar).getByRole("button", { name: /保存 .*合同标记/ });
    expect(topSave.compareDocumentPosition(screen.getByText("Deck Design System")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" })).toBeInTheDocument();
    expect(VISUAL_REVIEW_CSS).toMatch(/\.visual-contract-field header button\s*\{[^}]*width:\s*27px;[^}]*height:\s*27px;[^}]*opacity:\s*\.72;/s);
  });

  it("indexes one 120-slide saved mark set without repeated slide scans", () => {
    const data = visualData();
    const template = data.review.slide_visual_contracts[0];
    const slides = Array.from({ length: 120 }, (_, index) => ({
      ...template,
      slide_id: `S${String(index + 1).padStart(3, "0")}`,
      order: index + 1,
      neutral_title: `第 ${index + 1} 页视觉合同`,
      validation_purpose: `页面任务 ${index + 1}`,
      visible_copy: [`冻结正文 ${index + 1}`],
    }));
    let slideFindCalls = 0;
    data.review.slide_visual_contracts = new Proxy(slides, {
      get(target, property, receiver) {
        if (property === "find") slideFindCalls += 1;
        return Reflect.get(target, property, receiver);
      },
    });

    const markSet = projectedContractMarkSet(12);
    markSet.host_notification_status = "unavailable";
    markSet.ai_receipt_status = "unverified";
    let projectedMarkFieldReads = 0;
    markSet.marks = slides.map((slide, index) => new Proxy({
      ...markSet.marks[0],
      mark_id: `saved-contract-mark-${index + 1}`,
      slide_id: slide.slide_id,
      revision: 12,
    }, {
      get(target, property, receiver) {
        if (property === "target_key") projectedMarkFieldReads += 1;
        return Reflect.get(target, property, receiver);
      },
    }));
    const facts = deriveVisualReceiptFacts(markSet);
    expect(facts).not.toBeNull();
    const validated = validateInitialVisualContractMarkSet(markSet, data, facts!);
    expect(validated?.markSet?.marks).toHaveLength(120);
    expect(projectedMarkFieldReads).toBeGreaterThan(0);
    expect(slideFindCalls).toBe(0);
  });

  it.each(["browser-v1", "browser-v2"] as const)(
    "accepts and preserves the %s text-anchor representation version",
    (representation) => {
      const data = visualData();
      const markSet = projectedContractMarkSet(data.snapshotRevision);
      markSet.marks[0].target_type = "text-range";
      markSet.marks[0].selected_text = "证据";
      markSet.marks[0].context_after = "页";
      markSet.marks[0].anchor_representation_version = representation;
      markSet.host_notification_status = "unavailable";
      markSet.ai_receipt_status = "unverified";
      const facts = deriveVisualReceiptFacts(markSet);

      expect(facts).not.toBeNull();
      const validated = validateInitialVisualContractMarkSet(markSet, data, facts!);

      expect(
        validated?.markSet?.marks[0].anchor_representation_version,
      ).toBe(representation);
    },
  );

  it("rejects an unversioned text-anchor projection", () => {
    const data = visualData();
    const markSet = projectedContractMarkSet(data.snapshotRevision);
    markSet.marks[0].target_type = "text-range";
    markSet.marks[0].selected_text = "证据";
    markSet.marks[0].context_after = "页";
    markSet.host_notification_status = "unavailable";
    markSet.ai_receipt_status = "unverified";
    const facts = deriveVisualReceiptFacts(markSet);

    expect(facts).not.toBeNull();
    expect(
      validateInitialVisualContractMarkSet(markSet, data, facts!),
    ).toBeNull();
  });

  it("does not re-read the saved mark set when only the local composer changes", () => {
    const data = visualData();
    let projectedMarkFieldReads = 0;
    const markSet = projectedContractMarkSet(12);
    markSet.marks = markSet.marks.map((mark) => new Proxy(mark, {
      get(target, property, receiver) {
        if (property === "target_key") projectedMarkFieldReads += 1;
        return Reflect.get(target, property, receiver);
      },
    }));
    data.review.contract_review_marks_ref = CONTRACT_MARK_SET_REF;
    data.review.contract_review_marks = markSet;
    const { bridge } = host();

    render(
      <ControlledVisualContract
        data={data}
        bridge={bridge}
        revision={data.snapshotRevision}
        onRevision={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("合同标记保存事实")).toBeInTheDocument();
    expect(projectedMarkFieldReads).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "标记 S01 构图意图" }));
    projectedMarkFieldReads = 0;
    fireEvent.change(screen.getByLabelText("合同标记意见"), {
      target: { value: "只修改本地 composer，不重新扫描权威标记集" },
    });

    expect(projectedMarkFieldReads).toBe(0);
  });

  it("blocks contract save until the outside composer joins the snapshot, then clears only the completed contract slice", async () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    const data = visualData();
    const expectedUi = visualDraftUi({
      view: "contract",
      current_anchor_slide_id: "S02",
      anchor_feedback_drafts: [anchorDraft("成功保存合同后仍保留的锚点反馈", "S02", "save-sibling-anchor")],
      anchor_feedback_composer: anchorComposer("成功保存合同后仍保留的锚点输入", "S02"),
      anchor_logical_scroll: { object_id: "S02", offset: 51 },
      contract_logical_scroll: { object_id: "S01", offset: 82 },
    });
    const key = seedVisualDraft(data, expectedUi);
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "提交快照中的标记" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 构图意图" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "必须先加入快照的 composer" } });

    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("12");
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");

    const blockedSave = screen.getByRole("button", { name: "保存 1 条合同标记" });
    expect(blockedSave).toBeDisabled();
    fireEvent.click(blockedSave);
    expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(0);
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui.contract_mark_composer?.comment).toBe("必须先加入快照的 composer");

    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("2 条待保存标记");
    const save = screen.getByRole("button", { name: "保存 2 条合同标记" });
    expect(save).toBeEnabled();
    await act(async () => {
      save.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      save.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));

    const fieldEntry = screen.getByRole("button", { name: "标记 Deck Design System 设计命题" });
    const edit = screen.getByRole("button", { name: "编辑 提交快照中的标记" });
    const remove = screen.getByRole("button", { name: "移除 提交快照中的标记" });
    for (const control of [fieldEntry, edit, remove]) {
      expect(control).toBeDisabled();
    }

    const saveCall = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")!;
    const snapshotMarks = (saveCall[1] as { marks: VisualContractReviewMarkSet["marks"] }).marks;
    expect(snapshotMarks.map((mark) => mark.comment)).toEqual([
      "提交快照中的标记",
      "必须先加入快照的 composer",
    ]);
    await act(async () => {
      pending.resolve(contractMarkResult(saveCall[1] as Record<string, unknown>));
      await pending.promise;
    });
    await waitFor(() => {
      expect(screen.getByText("合同标记已保存")).toBeInTheDocument();
      expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("13");
      expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("所有标记已保存");
    });
    expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui).toEqual(expectedUi);
  });

  it("blocks an editing composer until it replaces the draft, then clears both after closed save", async () => {
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    const data = visualData();
    const expectedUi = visualDraftUi({ view: "contract" });
    const key = seedVisualDraft(data, expectedUi);
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "原始标记 A" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑 原始标记 A" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "编辑后的标记 A" } });

    const blockedSave = screen.getByRole("button", { name: "保存 1 条合同标记" });
    expect(blockedSave).toBeDisabled();
    fireEvent.click(blockedSave);
    expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    expect(screen.getByText("编辑后的标记 A")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "保存 1 条合同标记" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    const saveArgs = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")![1] as Record<string, unknown>;
    expect((saveArgs.marks as VisualContractReviewMarkSet["marks"])[0].comment).toBe("编辑后的标记 A");
    await act(async () => {
      pending.resolve(contractMarkResult(saveArgs));
      await pending.promise;
    });

    const commandStatus = document.querySelector<HTMLElement>(".visual-contract-command-status")!;
    await waitFor(() => expect(commandStatus).toHaveTextContent("所有标记已保存"));
    expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    expect(screen.queryByText("编辑后的标记 A")).not.toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readVisualDraft(key)?.ui).toEqual(expectedUi);
  });

  it("keeps the contract mark snapshot and count intact when save fails", async () => {
    const pending = deferred<unknown>();
    const { bridge, callTool } = host(undefined, () => pending.promise);
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "失败后必须保留" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));

    const save = screen.getByRole("button", { name: "保存 1 条合同标记" });
    await act(async () => {
      save.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      save.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    await act(async () => {
      pending.reject(new Error("save failed"));
      try { await pending.promise; } catch { /* expected */ }
    });

    expect(screen.getByText("合同标记尚未保存；全部草稿仍保留，可直接重试。")).toBeInTheDocument();
    expect(screen.getByText("失败后必须保留")).toBeInTheDocument();
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");
    expect(screen.getByRole("button", { name: "保存 1 条合同标记" })).toBeEnabled();
  });

  it("accepts a closed contract save after the StrictMode effect replay", async () => {
    const { bridge } = host();
    render(
      <StrictMode>
        <VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />
      </StrictMode>,
    );
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "StrictMode 后仍可保存" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    expect(screen.getByText("持久化：已保存")).toBeInTheDocument();
  });

  it("recovers host notification and AI receipt separately for the exact freshly saved contract mark set", async () => {
    const data = visualData();
    data.review.host_submission_capability = "available";
    data.review.ai_receipt_capability = "available";
    const retryHost = vi.fn(async (input: Parameters<NonNullable<HostBridge["retryVisualHostNotification"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      hostNotificationStatus: "sent" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const verifyAi = vi.fn(async (input: Parameters<NonNullable<HostBridge["verifyVisualAiReceipt"]>>[0]) => ({
      savedArtifactRef: input.savedArtifactRef,
      aiReceiptStatus: "received" as const,
      snapshotRevision: input.expectedRevision + 1,
    }));
    const { bridge, callTool } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      result.snapshot.revision = Number(args.expectedRevision) + 1;
      return result;
    }, {
      retryVisualHostNotification: retryHost,
      verifyVisualAiReceipt: verifyAi,
    });
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "保存后独立恢复合同回执" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText("宿主通知：不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试宿主通知" }));
    await waitFor(() => expect(retryHost).toHaveBeenCalledOnce());
    expect(retryHost.mock.calls[0][0]).toEqual({
      projectRoot: "/managed/project",
      expectedRevision: 13,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: CONTRACT_MARK_SET_REF,
    });
    expect(await screen.findByText("宿主通知：已送达")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "验证 AI 接收" }));
    await waitFor(() => expect(verifyAi).toHaveBeenCalledOnce());
    expect(verifyAi.mock.calls[0][0]).toEqual({
      projectRoot: "/managed/project",
      expectedRevision: 14,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: CONTRACT_MARK_SET_REF,
      receiptIdentity: CONTRACT_MARK_SET_REF,
    });
    expect(await screen.findByText("AI 接收：已接收")).toBeInTheDocument();
    expect(screen.getByText("visual-v1 · revision 15")).toBeInTheDocument();
    expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1);
  });

  it("rejects a contract-mark save that claims an unverified direct AI receipt and preserves the draft", async () => {
    const { bridge } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      return {
        ...result,
        mark_set: {
          ...result.mark_set,
          host_notification_status: "sent" as const,
          ai_receipt_status: "received" as const,
        },
      };
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "保存后只确认持久化" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText(/保存结果未闭合/)).toBeInTheDocument();
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("12");
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");
    expect(screen.getByText("保存后只确认持久化")).toBeInTheDocument();
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 1 条合同标记" })).toBeEnabled();
  });

  it.each([
    ["ordinary-string mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "saved-contract-marks";
    }],
    ["wrong-kind mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "artifact://visual-contract/" + "5".repeat(64);
    }],
    ["HTTP mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "https://example.test/visual-contract-review-mark-set/" + "5".repeat(64);
    }],
    ["non-64 mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "artifact://visual-contract-review-mark-set/abc123";
    }],
    ["uppercase-digest mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "artifact://visual-contract-review-mark-set/" + "A".repeat(64);
    }],
    ["malformed mark-set artifact ref", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set_ref = "artifact:/visual-contract-review-mark-set/" + "5".repeat(64);
    }],
    ["extra result field", (result: ReturnType<typeof contractMarkResult>) => {
      Object.assign(result, { unexpected: true });
    }],
    ["non-enumerable extra result field", (result: ReturnType<typeof contractMarkResult>) => {
      Object.defineProperty(result, "unexpected", { value: true, enumerable: false });
    }],
    ["wrong next revision", (result: ReturnType<typeof contractMarkResult>) => {
      result.snapshot.revision = result.mark_set.revision;
    }],
    ["unsafe snapshot revision", (result: ReturnType<typeof contractMarkResult>) => {
      result.snapshot.revision = Number.MAX_SAFE_INTEGER + 1;
    }],
    ["open mark set", (result: ReturnType<typeof contractMarkResult>) => {
      Object.assign(result.mark_set, { unexpected: true });
    }],
    ["inherited mark-set field plus an extra own key", (result: ReturnType<typeof contractMarkResult>) => {
      const original = result.mark_set;
      const inherited = Object.create({ mark_set_id: original.mark_set_id }) as typeof original & { unexpected: boolean };
      for (const [key, value] of Object.entries(original)) {
        if (key !== "mark_set_id") Object.assign(inherited, { [key]: value });
      }
      inherited.unexpected = true;
      result.mark_set = inherited;
    }],
    ["custom mark-set prototype", (result: ReturnType<typeof contractMarkResult>) => {
      Object.setPrototypeOf(result.mark_set, { poisoned: true });
    }],
    ["foreign mark-set identity", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.review_session_id = "foreign-session";
    }],
    ["timezone-less saved_at", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.saved_at = "2026-08-15T00:00:00";
    }],
    ["non-ISO mark created_at", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-with-non-iso-time",
        revision: result.mark_set.revision - 1,
        created_at: "1Z",
      });
    }],
    ["impossible mark created_at date", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-with-impossible-date",
        revision: result.mark_set.revision - 1,
        created_at: "2026-02-30T00:00:00Z",
      });
    }],
    ["invalid mark created_at offset", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-with-invalid-offset",
        revision: result.mark_set.revision - 1,
        created_at: "2026-08-14T00:00:00+24:00",
      });
    }],
    ["invalid mark created_at hour", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-with-invalid-hour",
        revision: result.mark_set.revision - 1,
        created_at: "2026-08-14T24:00:00Z",
      });
    }],
    ["historical mark created one microsecond after save", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.saved_at = "2026-08-15T23:59:59.000000Z";
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-created-after-save",
        revision: result.mark_set.revision - 1,
        created_at: "2026-08-15T23:59:59.000999Z",
      });
    }],
    ["extra own property on marks array", (result: ReturnType<typeof contractMarkResult>) => {
      Object.assign(result.mark_set.marks, { unexpected: true });
    }],
    ["symbol property on marks array", (result: ReturnType<typeof contractMarkResult>) => {
      Reflect.set(result.mark_set.marks, Symbol("unexpected"), true);
    }],
    ["open mark", (result: ReturnType<typeof contractMarkResult>) => {
      Object.assign(result.mark_set.marks[0], { unexpected: true });
    }],
    ["duplicate mark id", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.push(structuredClone(result.mark_set.marks[0]));
    }],
    ["unsubmitted current-revision mark", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "unsubmitted-current-revision-mark",
        comment: "本次命令未提交的当前 revision 标记",
        revision: result.mark_set.revision,
        created_at: "2026-08-15T23:59:00Z",
      });
    }],
    ["unknown contract target", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks[0].slide_id = "S99";
      result.mark_set.marks[0].deck_section_id = "";
    }],
    ["timezone-less mark created_at", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks[0].created_at = "2026-08-15T00:00:00";
    }],
    ["non-canonical optional mark text", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-mark-with-uncanonical-context",
        revision: result.mark_set.revision - 1,
        context_before: " 未规范化的上下文 ",
      });
    }],
    ["tampered submitted mark", (result: ReturnType<typeof contractMarkResult>) => {
      result.mark_set.marks[0].comment = "权威结果篡改了提交内容";
    }],
  ])("fails closed for a contract mark result with %s", async (_label, mutate) => {
    const { bridge, callTool } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      mutate(result);
      return result;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "无效结果后仍需保留" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    await waitFor(() => expect(callTool.mock.calls.filter(([name]) => name === "save_visual_contract_review_marks")).toHaveLength(1));
    expect(await screen.findByText(/保存结果未闭合/)).toBeInTheDocument();
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent("12");
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");
    expect(screen.getByText("无效结果后仍需保留")).toBeInTheDocument();
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 1 条合同标记" })).toBeEnabled();
  });

  it.each([
    ["terminal safe integer", Number.MAX_SAFE_INTEGER],
    ["unsafe integer", Number.MAX_SAFE_INTEGER + 1],
  ])("rejects a %s contract command revision before any Bridge write and preserves local work", (_label, invalidRevision) => {
    const data = visualData();
    data.snapshotRevision = invalidRevision;
    const { bridge, callTool } = host();
    render(<ControlledVisualContract data={data} bridge={bridge} revision={data.snapshotRevision} onRevision={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "unsafe revision 中的已加入草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 S01 构图意图" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "unsafe revision 中的未加入 composer" } });

    const save = screen.getByRole("button", { name: "保存 1 条合同标记" });
    expect(save).toBeDisabled();
    fireEvent.click(save);

    expect(callTool).not.toHaveBeenCalled();
    expect(screen.getByText(/revision 无效.*请重新打开/)).toBeInTheDocument();
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    expect(within(titlePage).getByText("revision").parentElement).toHaveTextContent(String(invalidRevision));
    expect(document.querySelector(".visual-contract-command-status")).toHaveTextContent("1 条待保存标记");
    expect(screen.getByText("unsafe revision 中的已加入草稿")).toBeInTheDocument();
    expect(screen.getByLabelText("合同标记意见")).toHaveValue("unsafe revision 中的未加入 composer");
    expect(screen.queryByLabelText("合同标记保存事实")).not.toBeInTheDocument();
  });

  it("fails closed without evaluating a getter mutation poison", async () => {
    let getterReads = 0;
    const { bridge } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      Object.defineProperty(result.mark_set, "mark_set_id", {
        configurable: true,
        enumerable: true,
        get() {
          getterReads += 1;
          result.mark_set.marks[0].comment = "getter mutation poison";
          return "visual-marks-1";
        },
      });
      return result;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "getter 不得执行" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText(/保存结果未闭合/)).toBeInTheDocument();
    expect(getterReads).toBe(0);
  });

  it("fails closed without evaluating a mark-array index accessor", async () => {
    let getterReads = 0;
    const { bridge } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      const submittedMark = result.mark_set.marks[0];
      Object.defineProperty(result.mark_set.marks, "0", {
        configurable: true,
        enumerable: true,
        get() {
          getterReads += 1;
          return submittedMark;
        },
      });
      return result;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "array accessor 不得执行" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText(/保存结果未闭合/)).toBeInTheDocument();
    expect(getterReads).toBe(0);
  });

  it("installs a fresh plain mark set instead of retaining the host result object", async () => {
    let hostResult: ReturnType<typeof contractMarkResult> | null = null;
    const { bridge } = host(undefined, async (args) => {
      hostResult = contractMarkResult(args);
      return hostResult;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "必须安装新对象" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();

    const mutableMarkSet = hostResult!.mark_set as unknown as VisualContractReviewMarkSet;
    mutableMarkSet.marks.push({ ...mutableMarkSet.marks[0], mark_id: "post-validation-poison" });
    mutableMarkSet.ai_receipt_status = "received";
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    fireEvent.click(screen.getByRole("button", { name: "打开标记记录" }));

    expect(screen.getByText("已保存 1 条合同标记。")).toBeInTheDocument();
    expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
  });

  it("accepts canonical Z and offset timestamps with microseconds", async () => {
    const toIsoString = vi.spyOn(Date.prototype, "toISOString")
      .mockReturnValue("2026-08-16T09:30:00.123455Z");
    try {
      const { bridge } = host(undefined, async (args) => {
        const result = contractMarkResult(args);
        result.mark_set.saved_at = "2026-08-17T00:00:00.123456+14:30";
        return result;
      });
      render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
      fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
      fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
      fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "canonical timestamp" } });
      fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
      fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

      expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    } finally {
      toIsoString.mockRestore();
    }
  });

  it.each([
    ["exact equality", "2026-08-15T23:59:59.000999Z", "2026-08-15T23:59:59.000999Z"],
    ["one microsecond earlier", "2026-08-15T23:59:59.000998Z", "2026-08-15T23:59:59.000999Z"],
    ["equivalent offset instant", "2026-08-16T14:29:59.000999+14:30", "2026-08-15T23:59:59.000999Z"],
  ])("accepts a historical mark whose created instant is %s", async (_label, createdAt, savedAt) => {
    const toIsoString = vi.spyOn(Date.prototype, "toISOString")
      .mockReturnValue("2026-08-15T00:00:00Z");
    try {
      const { bridge } = host(undefined, async (args) => {
        const result = contractMarkResult(args);
        result.mark_set.saved_at = savedAt;
        result.mark_set.marks.unshift({
          ...structuredClone(result.mark_set.marks[0]),
          mark_id: `historical-${_label}`,
          comment: "历史标记",
          revision: result.mark_set.revision - 1,
          created_at: createdAt,
        });
        return result;
      });
      render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
      fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
      fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
      fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "微秒顺序" } });
      fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
      fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

      expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    } finally {
      toIsoString.mockRestore();
    }
  });

  it("accepts a closed merged mark set that preserves every submitted field", async () => {
    const { bridge } = host(undefined, async (args) => {
      const result = contractMarkResult(args);
      result.mark_set.marks.unshift({
        ...structuredClone(result.mark_set.marks[0]),
        mark_id: "existing-current-source-mark",
        comment: "当前来源中既有的权威标记",
        revision: result.mark_set.revision - 1,
        created_at: "2026-08-14T23:59:00Z",
      });
      return result;
    });
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "本次新增的标记" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开标记记录" }));
    expect(screen.getByText("已保存 2 条合同标记。")).toBeInTheDocument();
  });

  it("uses the confirmed document-first visual contract layout without a summary wall", () => {
    const { bridge } = host();
    const data = visualData();
    Object.assign(data.review.deck_design_system, {
      production_route: "strict-B",
      reading_blueprint_ref: "artifact://reading-blueprint/internal",
      rule_definitions: [{ rule_id: "internal-rule" }],
      visual_brief_ref: "artifact://visual-brief/internal",
    });
    Object.assign(data.review.slide_visual_contracts[0], {
      reading_question: "内部阅读问题",
      material_mode: "material-backed",
      previous_relation: "内部前序关系",
      solution_mapping_refs: ["internal-mapping"],
    });
    const { container } = render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const commandbar = container.querySelector<HTMLElement>(".visual-professional-header .visual-contract-commandbar");
    expect(commandbar).toBeInTheDocument();
    expect(commandbar).toHaveAttribute("aria-label", "视觉合同操作");
    expect(within(commandbar!).queryByRole("heading", { name: "完整视觉合同" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("视觉合同摘要")).not.toBeInTheDocument();

    const document = container.querySelector<HTMLElement>(".visual-contract-document")!;
    const titlePage = document.querySelector<HTMLElement>(".visual-contract-title-page")!;
    const visualBrief = document.querySelector<HTMLElement>("[data-contract-logical-object='visual-brief']")!;
    const designSystem = document.querySelector<HTMLElement>("[data-contract-logical-object='deck-design-system']")!;
    const anchorEvidence = document.querySelector<HTMLElement>("[data-contract-logical-object='anchor-slide-evidence']")!;
    const slideContracts = document.querySelector<HTMLElement>(".visual-slide-contracts")!;
    const documentChildren = Array.from(document.children);

    expect(document.firstElementChild).toBe(titlePage);
    expect(documentChildren.indexOf(titlePage)).toBeLessThan(documentChildren.indexOf(visualBrief));
    expect(documentChildren.indexOf(visualBrief)).toBeLessThan(documentChildren.indexOf(designSystem));
    expect(documentChildren.indexOf(designSystem)).toBeLessThan(documentChildren.indexOf(anchorEvidence));
    expect(documentChildren.indexOf(anchorEvidence)).toBeLessThan(documentChildren.indexOf(slideContracts));
    expect(document.querySelector(".visual-contract-technical")).not.toBeInTheDocument();
    expect(anchorEvidence.querySelectorAll(".visual-anchor-evidence-item")).toHaveLength(3);
    expect(slideContracts.querySelectorAll(".visual-slide-contract")).toHaveLength(2);
    expect(Array.from(slideContracts.querySelectorAll(".visual-contract-column > h4")).filter((heading) => heading.textContent === "冻结内容")).toHaveLength(2);
    expect(Array.from(slideContracts.querySelectorAll(".visual-contract-column > h4")).filter((heading) => heading.textContent === "视觉实现合同")).toHaveLength(2);

    expect(within(visualBrief).getByRole("heading", { level: 2, name: "Visual Brief" })).toBeInTheDocument();
    expect(within(visualBrief).getByText("可信、克制、有清晰视觉焦点")).toBeInTheDocument();
    expect(screen.getAllByText("可信、克制、有清晰视觉焦点")).toHaveLength(1);
    for (const label of ["决策任务", "设计立场", "受众与阅读场景", "情绪边界", "品牌边界", "密度策略", "叙事节奏", "图像总策略", "图示总策略", "PowerPoint 约束", "整套禁止模式", "五秒判断口径", "设计哲学参考"]) {
      expect(within(visualBrief).getByRole("heading", { level: 4, name: label })).toBeInTheDocument();
    }
    expect(within(visualBrief).queryByRole("heading", { level: 4, name: "设计命题" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "标记 Visual Brief 设计命题" })).not.toBeInTheDocument();

    for (const label of ["设计命题", "构图语法", "色彩系统", "字体与层级", "页面家族", "密度节奏", "跨页节奏规则", "强调预算", "图像策略", "图像语言", "图示策略", "图示语言", "表格策略", "可编辑边界", "可访问性", "明确禁止", "五秒判断规则", "锚点规范"]) {
      expect(within(designSystem).getByRole("heading", { level: 4, name: label })).toBeInTheDocument();
    }
    for (const internalLabel of ["production route", "reading blueprint ref", "rule definitions", "visual brief ref"]) {
      expect(within(designSystem).queryByRole("heading", { name: internalLabel })).not.toBeInTheDocument();
    }

    const slideOne = within(slideContracts).getByRole("article", { name: "系统在线，经营仍然断裂" });
    for (const label of ["核心主张", "页面可见文案", "讲解备注", "来源引用", "沟通目标", "构图意图", "信息层级", "阅读顺序", "页面区域", "对象关系", "图示／图表／表格", "图像选择与裁切", "色彩应用", "字体应用", "原生／位图路由", "可编辑要求", "降级策略", "验收标准", "读者五秒判断", "主信息关系", "辅助信息关系", "视觉机制", "视觉重心", "资产角色", "页面禁止模式", "与前页节奏", "与后页节奏", "文字密度预算", "PowerPoint 实现要求", "验收证据计划"]) {
      expect(within(slideOne).getByRole("heading", { level: 4, name: label })).toBeInTheDocument();
    }
    expect(within(slideOne).queryByRole("heading", { name: "页面任务" })).not.toBeInTheDocument();
    expect(within(slideOne).queryByRole("heading", { name: "当前冻结文案" })).not.toBeInTheDocument();

    const palette = within(designSystem).getByTestId("visual-color-palette");
    expect(palette).toHaveClass("visual-palette-line");
    expect(palette.querySelectorAll(".visual-palette-swatch")).toHaveLength(2);
    expect(palette).toHaveTextContent("#1D2421");
    expect(palette).toHaveTextContent("#234B3D");
    for (const internalLabel of ["reading question", "material mode", "previous relation", "solution mapping refs"]) {
      expect(within(slideOne).queryByRole("heading", { name: internalLabel })).not.toBeInTheDocument();
    }
    for (const forbidden of ["VisualCompilationPlan", "visual-compilation-plan", "compiler_version", "technical lineage", "visual/compilation-plan", "技术信息"]) {
      expect(within(document).queryByText(forbidden, { exact: false })).not.toBeInTheDocument();
    }
  });

  it("renders a canonical null secondary relationship as no relationship", () => {
    const { bridge } = host();

    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const secondaryRelationshipField = screen.getByTestId(
      "contract-field-S02-secondary_relationship",
    );
    expect(within(secondaryRelationshipField).getByText("无")).toBeInTheDocument();
    expect(within(secondaryRelationshipField).queryByText(
      "待后端按前端字段合同提供",
    )).not.toBeInTheDocument();
  });

  it("keeps a confirmed frontend contract field markable when the backend projection key is missing", () => {
    const { bridge } = host();
    const data = visualData();
    delete (data.review.slide_visual_contracts[0] as unknown as Record<string, unknown>).core_claim;

    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const coreClaimField = screen.getByTestId("contract-field-S01-core_claim");
    expect(within(coreClaimField).getByText("待后端按前端字段合同提供")).toBeInTheDocument();
    fireEvent.click(within(coreClaimField).getByRole("button", { name: "标记 S01 核心主张" }));

    expect(screen.getByLabelText("合同标记意见")).toBeInTheDocument();
    expect(screen.getByText("S01 · 核心主张")).toBeInTheDocument();
  });

  it("reads the full contract in order and saves field plus selected-text marks once", async () => {
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const document = screen.getByRole("region", { name: "完整视觉合同正文" });
    const headings = within(document).getAllByRole("heading").map((node) => node.textContent);
    expect(headings).toContain("完整视觉合同");
    expect(headings).toContain("Visual Brief");
    expect(headings).toContain("Deck Design System");
    expect(headings).toContain("Anchor Slide Evidence");
    expect(headings.indexOf("完整视觉合同")).toBeLessThan(headings.indexOf("Visual Brief"));
    expect(headings.indexOf("Visual Brief")).toBeLessThan(headings.indexOf("Deck Design System"));
    expect(headings.indexOf("Deck Design System")).toBeLessThan(headings.indexOf("Anchor Slide Evidence"));
    expect(headings.some((text) => text?.includes("系统在线，经营仍然断裂"))).toBe(true);
    expect(headings.indexOf("Anchor Slide Evidence")).toBeLessThan(
      headings.findIndex((text) => text?.includes("系统在线，经营仍然断裂")),
    );
    const slideOne = within(document).getByRole("article", { name: "系统在线，经营仍然断裂" });
    expect(within(slideOne).getByText("问题诊断页 · 第 1 页")).toBeInTheDocument();
    const coreClaimField = within(slideOne).getByTestId("contract-field-S01-core_claim");
    expect(within(coreClaimField).getByText("核心主张")).toBeInTheDocument();
    expect(within(coreClaimField).getByText("核心主张 1")).toBeInTheDocument();
    const slideTwo = within(document).getByRole("article", { name: "一期围绕经营闭环建设" });
    expect(within(slideTwo).getByText("方案设计页 · 第 2 页")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "标记 Visual Brief 决策任务" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "决策任务需要更聚焦" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));

    fireEvent.click(screen.getByRole("button", { name: "标记 Deck Design System 设计命题" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "标题层级更克制" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));

    fireEvent.click(within(coreClaimField).getByRole("button", { name: "标记 S01 核心主张" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "核心主张需要更明确" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));

    const target = screen.getByTestId("contract-field-S01-composition_intent");
    const text = within(target).getByText("左侧事实，右侧因果链").firstChild!;
    const range = window.document.createRange();
    range.selectNodeContents(text);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(target);
    fireEvent.click(screen.getByRole("button", { name: "标记选中文字" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "强调因果链" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));

    fireEvent.click(screen.getByRole("button", { name: "保存 4 条合同标记" }));
    await waitFor(() => expect(callTool.mock.calls.some(([name]) => name === "save_visual_contract_review_marks")).toBe(true));
    const call = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")!;
    const args = call[1] as { marks: Array<Record<string, unknown>> };
    expect(args.marks.map((mark) => mark.target_type)).toEqual(["contract-field", "contract-field", "contract-field", "text-range"]);
    expect(args.marks[0]).toEqual(expect.objectContaining({
      slide_id: "",
      deck_section_id: "visual-brief",
      target_key: "decision_task",
      comment: "决策任务需要更聚焦",
    }));
    expect(args.marks).toContainEqual(expect.objectContaining({
      slide_id: "S01",
      target_key: "core_claim",
      comment: "核心主张需要更明确",
    }));
    expect(args.marks[3]).toEqual(expect.objectContaining({
      slide_id: "S01",
      target_key: "composition_intent",
      selected_text: "左侧事实，右侧因果链",
      visual_contract_ref: VISUAL_CONTRACT_REF,
      source_version: "visual-v1",
      revision: 12,
    }));
    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("宿主通知：不可用")).toBeInTheDocument();
      expect(screen.getByText("AI 接收：未验证")).toBeInTheDocument();
    });
  });

  it("canonicalizes selected-text context before submitting an authoritative echo", async () => {
    const data = visualData();
    (data.review.slide_visual_contracts[0] as unknown as Record<string, unknown>)
      .composition_intent = "Alpha beta gamma";
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const target = screen.getByTestId("contract-field-S01-composition_intent");
    const text = within(target).getByText("Alpha beta gamma").firstChild as Text;
    const range = window.document.createRange();
    range.setStart(text, 6);
    range.setEnd(text, 10);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(target);
    fireEvent.click(screen.getByRole("button", { name: "标记选中文字" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "保留 beta" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    const call = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")!;
    const mark = (call[1] as { marks: VisualContractReviewMarkSet["marks"] }).marks[0];
    expect(mark.selected_text).toBe("beta");
    expect(mark.context_before).toMatch(/Alpha$/);
    expect(mark.context_before).not.toMatch(/^\s|\s$/);
    expect(mark.context_after).toBe("gamma");
  });

  it("anchors duplicate selected text to the actual DOM Range occurrence", async () => {
    const data = visualData();
    (data.review.slide_visual_contracts[0] as unknown as Record<string, unknown>)
      .composition_intent = "alpha beta alpha";
    const { bridge, callTool } = host();
    render(<VisualProfessionalReviewPage initialData={data} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

    const target = screen.getByTestId("contract-field-S01-composition_intent");
    const text = within(target).getByText("alpha beta alpha").firstChild as Text;
    const range = window.document.createRange();
    range.setStart(text, 11);
    range.setEnd(text, 16);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(target);
    fireEvent.click(screen.getByRole("button", { name: "标记选中文字" }));
    fireEvent.change(screen.getByLabelText("合同标记意见"), { target: { value: "标记第二个 alpha" } });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));

    expect(await screen.findByText("合同标记已保存")).toBeInTheDocument();
    const call = callTool.mock.calls.find(([name]) => name === "save_visual_contract_review_marks")!;
    const mark = (call[1] as { marks: VisualContractReviewMarkSet["marks"] }).marks[0];
    expect(mark.selected_text).toBe("alpha");
    expect(mark.context_before).toBe("alpha beta");
    expect(mark.context_after).toBe("");
  });

  it.each(["title", "button", "chrome-to-body"])(
    "rejects a %s selection outside the dedicated contract body",
    (selectionKind) => {
      const { bridge } = host();
      render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
      fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));

      const field = screen.getByTestId("contract-field-S01-composition_intent");
      const title = within(field).getByRole("heading", { name: "构图意图" }).firstChild as Text;
      const button = within(field).getByRole("button", { name: "标记 S01 构图意图" });
      const body = within(field).getByText("左侧事实，右侧因果链").firstChild as Text;
      const range = window.document.createRange();
      if (selectionKind === "title") {
        range.selectNodeContents(title);
      } else if (selectionKind === "button") {
        range.selectNodeContents(button);
      } else {
        range.setStart(title, 0);
        range.setEnd(body, 2);
      }
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      selection.addRange(range);

      fireEvent.mouseUp(field);

      expect(screen.queryByRole("button", { name: "标记选中文字" })).not.toBeInTheDocument();
      expect(screen.queryByLabelText("合同标记意见")).not.toBeInTheDocument();
    },
  );

  it("opens outline and mark review as overlays without replacing the document", () => {
    const { bridge } = host();
    render(<VisualProfessionalReviewPage initialData={visualData()} bridge={bridge} />);
    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    fireEvent.click(screen.getByRole("button", { name: "打开合同目录" }));
    const outline = screen.getByRole("dialog", { name: "视觉合同目录" });
    expect(outline).toHaveAttribute("data-overlay", "true");
    const visualBriefButton = within(outline).getByRole("button", { name: "Visual Brief" });
    const designSystemButton = within(outline).getByRole("button", { name: "Deck Design System" });
    const anchorEvidenceButton = within(outline).getByRole("button", { name: "Anchor Slide Evidence" });
    expect(visualBriefButton).toHaveAttribute("data-index", "00");
    expect(designSystemButton).toHaveAttribute("data-index", "01");
    expect(visualBriefButton.compareDocumentPosition(designSystemButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(designSystemButton.compareDocumentPosition(anchorEvidenceButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(outline).getByRole("button", { name: "Anchor Slide Evidence" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "完整视觉合同正文" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "打开标记记录" }));
    expect(screen.queryByRole("dialog", { name: "视觉合同目录" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "合同标记" })).toBeInTheDocument();
  });
});
