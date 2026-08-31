import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewSurfaceRouter } from "./ReviewSurfaceRouter";
import type { ContentReviewSurfaceData } from "./types/content-review";
import type { HostBridge } from "./types/host";
import type { ReviewSurfaceData } from "./types/host";
import type { VisualReviewSurfaceData } from "./types/visual-review";

afterEach(cleanup);

const bridge: HostBridge = {
  connect: vi.fn(async () => undefined),
  callTool: vi.fn(),
};

function visualSlideContract(overrides: Record<string, unknown> = {}) {
  return {
    slide_id: "S01",
    order: 1,
    neutral_title: "经营协同仍有断点",
    page_family: "问题诊断页",
    anchor_title: "经营协同仍有断点",
    validation_purpose: "说明当前问题",
    core_claim: "业务断点需要被看见",
    visible_copy: ["页面可见文案"],
    speaker_notes: "",
    source_refs: ["source-1"],
    communication_goal: "形成问题共识",
    composition_intent: "左侧事实，右侧因果链",
    information_hierarchy: "标题—事实—建议",
    reading_order: ["标题", "事实", "建议"],
    regions: ["标题区", "正文区"],
    object_relationships: ["事实支持建议"],
    diagram_chart_table_treatment: "因果关系使用原生形状",
    image_selection_and_crop: "无图时保持原生结构",
    color_application: "中性底色配单一强调色",
    typography_application: "标题与正文层级分明",
    native_bitmap_routing: "原生优先",
    editability_requirements: "所有正文与图形可编辑",
    fallbacks: ["缺图时保持原生结构"],
    acceptance_criteria: [{
      criterion_id: "criterion-1",
      level: "must-follow",
      expected_outcome: "阅读顺序清晰且原生可编辑",
    }],
    ...overrides,
  };
}

function deckDesignSystem() {
  return {
    theme_proposition: "克制、可信、阅读优先",
    composition_grammar: "结论先行，证据支撑",
    color_tokens: { accent: "#3157D5" },
    typography_tokens: { title_scale: "32pt" },
    page_families: ["问题诊断页"],
    density_rhythm: "中密度",
    imagery_strategy: "证据优先",
    diagram_strategy: "原生图形优先",
    table_strategy: "少量关键列",
    editability_rules: ["正文与图形可编辑"],
    accessibility_rules: ["保持对比度"],
    forbidden_patterns: ["装饰性堆叠"],
    anchor_specification: "三页锚点覆盖主要页面家族",
    production_route: "strict-B",
  };
}

function visualReviewSurface(anchorCount = 3): VisualReviewSurfaceData {
  const anchors = Array.from({ length: anchorCount }, (_, index) => ({
    slide_id: `S${String(index + 1).padStart(2, "0")}`,
    current_asset_ref: `review-assets/anchors/S${String(index + 1).padStart(2, "0")}-current.png`,
    previous_asset_ref: "",
  }));
  return {
    surface: "review",
    selectedProjectRoot: "/managed/project",
    snapshotRevision: 9,
    review: {
      project_id: "p1",
      project_name: "测试项目",
      review_type: "visual-professional",
      review_session_id: "visual-session-1",
      review_session: {
        review_session_id: "visual-session-1",
        review_type: "visual-professional",
        project_id: "p1",
        target_artifact_ref: "artifact://visual-contract/" + "a".repeat(64),
        source_version: "visual-v1",
        revision: 8,
        status: "ready",
        open_policy: "foreground-if-waiting",
        host_open_status: "not-requested",
        persistence_status: "saved",
        host_notification_status: "not-requested",
        ai_receipt_status: "pending",
        created_at: "2026-08-15T00:00:00Z",
        last_opened_at: null,
        submitted_at: null,
      },
      source_version: "visual-v1",
      revision: 8,
      authoritative_revision: 9,
      visual_contract_ref: "artifact://visual-contract/" + "a".repeat(64),
      deck_design_system_ref: "artifact://deck-design-system/" + "b".repeat(64),
      deck_design_system: deckDesignSystem(),
      anchor_slide_set_ref: "artifact://anchor-slide-set/" + "c".repeat(64),
      anchors,
      anchor_identity: {
        slide_ids: anchors.map((anchor) => anchor.slide_id),
        selection_reason: "覆盖章节、证据和方案页面家族",
        native_first_frozen: true,
      },
      slide_visual_contracts: [visualSlideContract()],
      anchor_feedback_batch_ref: null,
      anchor_feedback_batch: null,
      contract_review_marks_ref: null,
      contract_review_marks: null,
      host_submission_capability: "unavailable",
      ai_receipt_capability: "unavailable",
    },
  };
}

function contentSlide(slideId: string, order: number, sectionId: string) {
  return {
    slide_id: slideId,
    order,
    section_id: sectionId,
    page_task: `页面任务 ${order}`,
    reading_question: `阅读问题 ${order}`,
    neutral_title: `中立标题 ${order}`,
    customerJudgment: `客户形成第 ${order} 页的明确判断。`,
    visible_copy_blocks: [{
      block_id: `copy-${order}`,
      text: `第 ${order} 页页面实际文字。`,
    }],
    material_views: [],
  };
}

function contentReviewSurface(
  slides: ReturnType<typeof contentSlide>[] = [contentSlide("S01", 1, "opening")],
): ContentReviewSurfaceData {
  const sectionFlow = [...new Set(slides.map((slide) => slide.section_id))];
  return {
    surface: "review",
    selectedProjectRoot: "/managed/project",
    snapshotRevision: 9,
    review: {
      project_id: "p1",
      review_type: "content-full-deck",
      review_session_id: "session-1",
      review_session: {
        review_session_id: "session-1",
        review_type: "content-full-deck",
        project_id: "p1",
        target_artifact_ref: "artifact://reading-deck-blueprint/" + "a".repeat(64),
        source_version: "content-v1",
        revision: 8,
        status: "ready",
        open_policy: "foreground-if-waiting",
        host_open_status: "not-requested",
        persistence_status: "saved",
        host_notification_status: "not-requested",
        ai_receipt_status: "pending",
        created_at: "2026-08-15T00:00:00Z",
        last_opened_at: null,
        submitted_at: null,
      },
      source_version: "content-v1",
      revision: 8,
      authoritative_revision: 9,
      reading_blueprint_ref:
        "artifact://reading-deck-blueprint/" + "a".repeat(64),
      material_mode: "proposal-led",
      section_flow: sectionFlow.length ? sectionFlow : ["开篇"],
      slides,
      decisions: [],
      progress: {
        completed: 0,
        total: slides.length,
        remaining: slides.length,
        unsaved: 0,
      },
      batch: null,
      revision_plan: null,
      content_acceptance_ref:
        "artifact://content-acceptance/" + "b".repeat(64),
    },
  };
}

type ContentIdentityMutation = (data: ContentReviewSurfaceData) => void;

const contentIdentityMutations: Array<[string, ContentIdentityMutation]> = [
  ["project", (data) => {
    data.review.project_id = "p2";
    data.review.review_session.project_id = "p2";
  }],
  ["review session", (data) => {
    data.review.review_session_id = "session-2";
    data.review.review_session.review_session_id = "session-2";
  }],
  ["source version", (data) => {
    data.review.source_version = "content-v2";
    data.review.review_session.source_version = "content-v2";
  }],
  ["immutable source revision", (data) => {
    data.review.revision = 9;
    data.review.review_session.revision = 9;
  }],
];

type VisualLineageMutation = (data: VisualReviewSurfaceData) => void;

const visualLineageMutations: Array<[string, VisualLineageMutation]> = [
  ["visual_contract_ref", (data) => {
    const next = "artifact://visual-contract/" + "2".repeat(64);
    data.review.visual_contract_ref = next;
    data.review.review_session.target_artifact_ref = next;
  }],
  ["anchor_slide_set_ref", (data) => {
    data.review.anchor_slide_set_ref = "artifact://anchor-slide-set/" + "3".repeat(64);
  }],
  ["deck_design_system_ref", (data) => {
    data.review.deck_design_system_ref = "artifact://deck-design-system/" + "4".repeat(64);
  }],
];

function expectVisualReviewPage() {
  expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "完整视觉合同" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
}

function expectContentReviewPage() {
  expect(screen.getByRole("heading", { name: "p1" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
}

describe("on-demand professional-review routing", () => {
  it("routes content-full-deck through the accepted ViewModel surface without legacy backend modules", () => {
    const content = contentReviewSurface();

    const { container } = render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("heading", { name: "p1" })).toBeInTheDocument();
    expect(screen.getByText("这一页的目标")).toBeInTheDocument();
    expect(screen.getByText("页面任务 1")).toBeInTheDocument();
    expect(screen.getByText("客户决策事项")).toBeInTheDocument();
    expect(screen.queryByText("希望客户形成的判断")).not.toBeInTheDocument();
    expect(screen.getByText("客户形成第 1 页的明确判断。")).toBeInTheDocument();
    expect(screen.getByText("页面实际文字")).toBeInTheDocument();
    expect(screen.getByText("第 1 页页面实际文字。")).toBeInTheDocument();
    expect(screen.queryByText("文字与图片材料一起审核")).not.toBeInTheDocument();
    expect(screen.queryByText("本页暂无可审核的页面画面。")).not.toBeInTheDocument();
    expect(
      container.querySelector(".content-review-vm-reading-grid--text-only"),
    ).toBeInTheDocument();
    expect(screen.getByText("本页阅读判断：")).toBeInTheDocument();
    expect(screen.getByText("阅读问题 1")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "需要修改" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "证据不足" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "考虑删页/合页" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll("[data-content-review-vm-slide]")).toHaveLength(1);
    expect(container.querySelector("[data-content-slide]")).not.toBeInTheDocument();
    for (const legacyTitle of [
      "完整可见文字",
      "分析、假设与建议",
      "完整演讲备注",
      "证据与身份",
      "查看来源证据",
      "问题—方案映射",
      "跨页关系",
      "阅读质量",
    ]) {
      expect(screen.queryByText(legacyTitle)).not.toBeInTheDocument();
    }
    expect(
      screen.queryByRole("navigation", { name: "五空间导航" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    "identity_labels",
    "evidence_bindings",
    "analysis_or_proposal_blocks",
    "solution_mapping_refs",
    "previous_relation",
    "next_relation",
    "speaker_notes",
    "reading_quality",
    "material_mode",
  ])("rejects content projection slide governance field %s", (field) => {
    const content = contentReviewSurface();
    (content.review.slides[0] as unknown as Record<string, unknown>)[field] =
      field === "previous_relation" || field === "next_relation" || field === "speaker_notes"
        ? "internal"
        : [];

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects content projection block identity metadata", () => {
    const content = contentReviewSurface();
    (content.review.slides[0].visible_copy_blocks[0] as Record<string, unknown>).identity =
      "来源事实";

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it.each([
    "source_ref",
    "source_file_name",
    "page_number",
    "region_label",
    "purpose",
    "treatment",
    "evidence_identity",
  ])("rejects content projection material metadata field %s", (field) => {
    const content = contentReviewSurface();
    const slide = content.review.slides[0] as unknown as {
      material_views: Array<Record<string, unknown>>;
    };
    slide.material_views = [{
      material_view_id: "S01-M01",
      asset_ref: "review-assets/content/S01-M01.png",
    }];
    slide.material_views[0][field] = field === "page_number" ? 1 : "internal";

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("routes visual-professional to the confirmed dual-view surface", () => {
    const visual = visualReviewSurface();

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(
      screen.getByRole("tab", { name: "3 页锚点成果" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "完整视觉合同" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "五空间导航" }),
    ).not.toBeInTheDocument();
  });

  it("keeps long semantic anchor ids out of fixed-width visual review labels", () => {
    const visual = visualReviewSurface();
    const anchors = visual.review.anchors;
    Object.assign(anchors[0], { slide_id: "oa-standardization-01-inventory" });
    Object.assign(anchors[1], { slide_id: "oa-standardization-02-service-system" });
    Object.assign(anchors[2], { slide_id: "oa-standardization-03-package-structure" });
    Object.assign(visual.review.anchor_identity, { slide_ids: anchors.map((anchor) => anchor.slide_id) });
    Object.assign(visual.review, { slide_visual_contracts: anchors.map((anchor, index) => visualSlideContract({
      slide_id: anchor.slide_id,
      order: index + 1,
      neutral_title: `页面 ${index + 1}`,
    })) });

    const { container } = render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);
    const tabs = Array.from(container.querySelectorAll<HTMLButtonElement>(".anchor-tabs button"));
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "01 · inventory",
      "02 · service-system",
      "03 · package-structure",
    ]);
    expect(tabs[0]).toHaveAttribute("title", "oa-standardization-01-inventory 锚点页");
    expect(tabs[0]).toHaveAccessibleName("oa-standardization-01-inventory 锚点页");

    fireEvent.click(screen.getByRole("tab", { name: "完整视觉合同" }));
    const pageIds = Array.from(container.querySelectorAll<HTMLElement>(".visual-contract-page-id"));
    expect(pageIds.map((pageId) => pageId.textContent)).toEqual(["01", "02", "03"]);
    expect(pageIds[0]).toHaveAttribute("title", "oa-standardization-01-inventory");
    expect(container.querySelectorAll(".visual-contract-slide-key")).toHaveLength(3);
  });

  it("renders a ready notify-only visual session while host notification is pending", () => {
    const visual = visualReviewSurface();
    visual.review.review_session.open_policy = "notify-only";
    visual.review.review_session.host_notification_status = "pending";

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expectVisualReviewPage();
  });

  it("renders a ready notify-only content session while host notification is pending", () => {
    const content = contentReviewSurface();
    content.review.review_session.open_policy = "notify-only";
    content.review.review_session.host_notification_status = "pending";

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expectContentReviewPage();
  });

  it("renders a ready foreground visual session while host opening is pending", () => {
    const visual = visualReviewSurface();
    visual.review.review_session.host_open_status = "pending";

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expectVisualReviewPage();
  });

  it.each([
    ["host open unavailable", (data: VisualReviewSurfaceData) => {
      data.review.review_session.host_open_status = "unavailable";
    }],
    ["host notification unavailable", (data: VisualReviewSurfaceData) => {
      data.review.review_session.host_notification_status = "unavailable";
    }],
    ["AI receipt rejected", (data: VisualReviewSurfaceData) => {
      data.review.review_session.ai_receipt_status = "rejected";
    }],
    ["AI receipt unverified", (data: VisualReviewSurfaceData) => {
      data.review.review_session.ai_receipt_status = "unverified";
    }],
  ] as Array<[string, (data: VisualReviewSurfaceData) => void]>) (
    "renders a visual review for authoritative %s status",
    (_label, mutate) => {
      const visual = visualReviewSurface();
      mutate(visual);

      render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

      expectVisualReviewPage();
    },
  );

  it.each([
    ["host_open_status", "opening"],
    ["host_notification_status", "queued"],
    ["ai_receipt_status", "failed"],
  ])("rejects unknown ReviewSession %s value", (field, status) => {
    const visual = visualReviewSurface();
    visual.review.review_session[field] = status;

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects opened host status without its success receipt", () => {
    const visual = visualReviewSurface();
    visual.review.review_session.host_open_status = "opened";
    visual.review.review_session.last_opened_at = "2026-08-15T00:01:00Z";

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects sent notification status without its success receipt", () => {
    const visual = visualReviewSurface();
    visual.review.review_session.host_notification_status = "sent";

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects received AI status without its success receipt", () => {
    const visual = visualReviewSurface();
    visual.review.review_session.ai_receipt_status = "received";

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("accepts the closed Python anchor identity", () => {
    const visual = visualReviewSurface();

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([2, 4])("rejects a visual projection with %i anchors", (anchorCount) => {
    const visual = visualReviewSurface(anchorCount);

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
    expect(screen.queryByRole("tab", { name: "3 页锚点成果" })).not.toBeInTheDocument();
  });

  it("rejects duplicate content slide IDs", () => {
    const content = contentReviewSurface([
      contentSlide("S01", 1, "开篇"),
      contentSlide("S01", 2, "开篇"),
    ]);

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("accepts stable section IDs paired positionally with human-readable section flow", () => {
    const content = contentReviewSurface([
      contentSlide("S01", 1, "problem"),
      contentSlide("S02", 2, "solution"),
    ]);
    content.review.section_flow = ["客户业务事项", "问题与验证方案"];

    const { container } = render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("heading", { name: "p1" })).toBeInTheDocument();
    expect(container.querySelectorAll("[data-content-review-vm-slide]")).toHaveLength(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([
    ["missing", (slide: ReturnType<typeof contentSlide>) => {
      delete (slide as unknown as Record<string, unknown>).customerJudgment;
    }],
    ["blank", (slide: ReturnType<typeof contentSlide>) => {
      slide.customerJudgment = "";
    }],
    ["unnormalized", (slide: ReturnType<typeof contentSlide>) => {
      slide.customerJudgment = "  客户先核实现状  ";
    }],
  ])("rejects a content projection with %s customerJudgment without using legacy text as fallback", (_label, mutate) => {
    const slide = contentSlide("S01", 1, "problem");
    mutate(slide);
    const content = contentReviewSurface([slide]);

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
    expect(screen.queryByText(slide.neutral_title)).not.toBeInTheDocument();
    expect(screen.queryByText(slide.reading_question)).not.toBeInTheDocument();
    expect(screen.queryByText(slide.page_task)).not.toBeInTheDocument();
  });

  it.each([
    ["non-consecutive slide order", [contentSlide("S01", 2, "opening")], ["开篇"]],
    ["non-contiguous section reentry", [
      contentSlide("S01", 1, "problem"),
      contentSlide("S02", 2, "solution"),
      contentSlide("S03", 3, "problem"),
    ], ["客户业务事项", "问题与验证方案"]],
    ["more section groups than section flow", [
      contentSlide("S01", 1, "problem"),
      contentSlide("S02", 2, "solution"),
    ], ["客户业务事项"]],
    ["duplicate section flow", [contentSlide("S01", 1, "opening")], ["开篇", "开篇"]],
  ])("rejects content projection with %s", (_label, slides, sectionFlow) => {
    const content = contentReviewSurface(slides);
    content.review.section_flow = sectionFlow;

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects an extra field in the closed Python anchor identity", () => {
    const visual = visualReviewSurface();
    Object.assign(visual.review.anchor_identity, {
      visual_contract_set_ref: "artifact://visual-contract-set/" + "9".repeat(64),
    });

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it.each([
    ["ordinary string", "visual-contract-saved"],
    ["wrong kind", "artifact://anchor-slide-set/" + "a".repeat(64)],
    ["HTTP URL", "https://example.test/visual-contract/" + "a".repeat(64)],
    ["non-64 digest", "artifact://visual-contract/abc123"],
    ["uppercase digest", "artifact://visual-contract/" + "A".repeat(64)],
    ["malformed URI", "artifact:/visual-contract/" + "a".repeat(64)],
  ])("rejects a visual projection with a %s visual-contract artifact ref even when the session target matches", (_label, reference) => {
    const visual = visualReviewSurface();
    visual.review.visual_contract_ref = reference;
    visual.review.review_session.target_artifact_ref = reference;

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it.each([
    ["visual contract", (visual: VisualReviewSurfaceData) => {
      const wrong = "artifact://deck-design-system/" + "a".repeat(64);
      visual.review.visual_contract_ref = wrong;
      visual.review.review_session.target_artifact_ref = wrong;
    }],
    ["deck design system", (visual: VisualReviewSurfaceData) => {
      visual.review.deck_design_system_ref = "artifact://visual-contract/" + "b".repeat(64);
    }],
    ["anchor slide set", (visual: VisualReviewSurfaceData) => {
      visual.review.anchor_slide_set_ref = "artifact://visual-contract/" + "c".repeat(64);
    }],
  ])("rejects a visual projection whose %s reference has the wrong artifact kind", (_label, mutate) => {
    const visual = visualReviewSurface();
    mutate(visual);

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects a content projection whose blueprint and matching session target use the wrong artifact kind", () => {
    const content = contentReviewSurface();
    const wrong = "artifact://visual-contract/" + "a".repeat(64);
    content.review.reading_blueprint_ref = wrong;
    content.review.review_session.target_artifact_ref = wrong;

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it.each([
    ["empty", (visual: VisualReviewSurfaceData) => {
      visual.review.slide_visual_contracts = [];
    }],
    ["duplicate", (visual: VisualReviewSurfaceData) => {
      visual.review.slide_visual_contracts.push(visualSlideContract({ order: 2 }));
    }],
    ["only-slide-id incomplete", (visual: VisualReviewSurfaceData) => {
      visual.review.slide_visual_contracts = [{ slide_id: "S01" }];
    }],
  ])("fails closed for %s slide visual contracts", (_label, mutate) => {
    const visual = visualReviewSurface();
    mutate(visual);

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
    expect(screen.queryByRole("tab", { name: "完整视觉合同" })).not.toBeInTheDocument();
  });

  it("rejects an extra field inside a visual acceptance criterion", () => {
    const visual = visualReviewSurface();
    const contract = visual.review.slide_visual_contracts[0] as Record<string, unknown>;
    const criterion = (contract.acceptance_criteria as Array<Record<string, unknown>>)[0];
    Object.assign(criterion, {
      future_backend_governance: "must be handled by the backend",
    });

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("fails closed for a typed-looking but open review projection", () => {
    const spoofed = {
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: {
        project_id: "p1",
        project_name: "测试项目",
        review_type: "visual-professional",
        review_session_id: "visual-session-1",
        review_session: {},
        source_version: "visual-v1",
        revision: 8,
        authoritative_revision: 9,
        visual_contract_ref: "visual-contract:v1",
        deck_design_system_ref: "deck-design-system:v1",
        deck_design_system: deckDesignSystem(),
        anchor_slide_set_ref: "anchor-slide-set:v1",
        anchors: [],
        anchor_identity: {},
        slide_visual_contracts: [],
        anchor_feedback_batch_ref: null,
        anchor_feedback_batch: null,
        contract_review_marks_ref: null,
        contract_review_marks: null,
        host_submission_capability: "unavailable",
        ai_receipt_capability: "unavailable",
        unexpected: true,
      },
    } as unknown as ReviewSurfaceData;

    render(<ReviewSurfaceRouter data={spoofed} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
    expect(screen.queryByRole("tab", { name: "完整视觉合同" })).not.toBeInTheDocument();
  });

  it.each([
    ["cyclic nested value", () => {
      const visual = visualReviewSurface();
      const cyclic: Record<string, unknown> = {};
      cyclic.self = cyclic;
      visual.review.deck_design_system = { cyclic };
      return visual as unknown as ReviewSurfaceData;
    }],
    ["throwing prototype trap", () => {
      const visual = visualReviewSurface();
      visual.review = new Proxy(visual.review, {
        getPrototypeOf() {
          throw new Error("host prototype trap");
        },
      });
      return visual as unknown as ReviewSurfaceData;
    }],
  ])("renders controlled invalid-data recovery for a %s projection", (_label, factory) => {
    const hostile = factory();

    expect(() => render(<ReviewSurfaceRouter data={hostile} bridge={bridge} />)).not.toThrow();
    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it("rejects a projection with an extra field deep inside a closed nested record", () => {
    const visual = visualReviewSurface();
    Object.assign(visual.review, { unexpected: { nested: { value: true } } });

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
  });

  it.each([
    ["content", contentReviewSurface],
    ["visual", visualReviewSurface],
  ] as Array<[string, () => ReviewSurfaceData]>) (
    "preserves the %s page root as snapshot and authoritative revision grow",
    (_label, factory) => {
      const data = factory();
      const { container, rerender } = render(<ReviewSurfaceRouter data={data} bridge={bridge} />);
      const firstRoot = container.firstElementChild;
      const grown = structuredClone(data);
      grown.snapshotRevision += 1;
      grown.review.authoritative_revision += 1;

      rerender(<ReviewSurfaceRouter data={grown} bridge={bridge} />);

      expect(container.firstElementChild).toBe(firstRoot);
    },
  );

  it.each(contentIdentityMutations)("remounts the content page root when %s changes", (_label, mutate) => {
    const data = contentReviewSurface();
    const { container, rerender } = render(<ReviewSurfaceRouter data={data} bridge={bridge} />);
    const firstRoot = container.firstElementChild;
    const changed = structuredClone(data);
    mutate(changed);

    rerender(<ReviewSurfaceRouter data={changed} bridge={bridge} />);

    expect(container.firstElementChild).not.toBe(firstRoot);
  });

  it("remounts the complete page root when review type changes", () => {
    const { container, rerender } = render(
      <ReviewSurfaceRouter data={contentReviewSurface()} bridge={bridge} />,
    );
    const firstRoot = container.firstElementChild;

    rerender(<ReviewSurfaceRouter data={visualReviewSurface()} bridge={bridge} />);

    expect(container.firstElementChild).not.toBe(firstRoot);
  });

  it("remounts the content page root when reading_blueprint_ref changes", () => {
    const data = contentReviewSurface();
    const { container, rerender } = render(<ReviewSurfaceRouter data={data} bridge={bridge} />);
    const firstRoot = container.firstElementChild;
    const changed = structuredClone(data);
    const next = "artifact://reading-deck-blueprint/" + "5".repeat(64);
    changed.review.reading_blueprint_ref = next;
    changed.review.review_session.target_artifact_ref = next;

    rerender(<ReviewSurfaceRouter data={changed} bridge={bridge} />);

    expect(container.firstElementChild).not.toBe(firstRoot);
  });

  it.each(visualLineageMutations)("remounts the visual page root when %s changes", (_label, mutate) => {
    const data = visualReviewSurface();
    const { container, rerender } = render(<ReviewSurfaceRouter data={data} bridge={bridge} />);
    const firstRoot = container.firstElementChild;
    const changed = structuredClone(data);
    mutate(changed);

    rerender(<ReviewSurfaceRouter data={changed} bridge={bridge} />);

    expect(container.firstElementChild).not.toBe(firstRoot);
  });
});
