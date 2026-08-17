import { cleanup, render, screen } from "@testing-library/react";
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
    page_task: "问题诊断",
    reading_question: "为何现在行动",
    neutral_title: "经营协同仍有断点",
    visible_copy_blocks: [],
    identity_labels: ["方案建议"],
    evidence_bindings: [],
    analysis_or_proposal_blocks: [],
    solution_mapping_refs: [],
    previous_relation: "",
    next_relation: "进入一期方案",
    speaker_notes: "",
    reading_quality: {
      independently_readable: true,
      information_density: "medium",
      review_note: "",
    },
    material_mode: "proposal-led",
    page_family: "问题诊断页",
    information_hierarchy: "标题—事实—建议",
    composition_intent: "左侧事实，右侧因果链",
    image_selection_and_crop: "无图时保持原生结构",
    typography_application: "标题与正文层级分明",
    color_application: "中性底色配单一强调色",
    diagram_chart_table_treatment: "因果关系使用原生形状",
    native_bitmap_routing: "原生优先",
    editability_requirements: "所有正文与图形可编辑",
    regions: ["标题区", "正文区"],
    object_relationships: ["事实支持建议"],
    reading_order: ["标题", "事实", "建议"],
    fallbacks: ["缺图时保持原生结构"],
    acceptance_criteria: [{
      criterion_id: "criterion-1",
      level: "must-follow",
      expected_outcome: "阅读顺序清晰且原生可编辑",
    }],
    allowed_exceptions: [],
    future_extension: { renderer_hint: "native-shapes" },
    ...overrides,
  };
}

function visualReviewSurface(): VisualReviewSurfaceData {
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
      deck_design_system: {},
      anchor_slide_set_ref: "artifact://anchor-slide-set/" + "c".repeat(64),
      anchors: [],
      anchor_identity: {
        visual_contract_set_ref: "artifact://visual-contract-set/" + "9".repeat(64),
        slide_ids: [],
        selection_reason: "覆盖章节、证据和方案页面家族",
        native_first_frozen: true,
        native_first_pptx_ref: "artifact://native-pptx/" + "d".repeat(64),
        pptx_sha256: "e".repeat(64),
        editability_evidence_refs: ["artifact://editability-evidence/" + "f".repeat(64)],
        preflight_render_refs: ["artifact://preflight-render/" + "1".repeat(64)],
        render_assets: [],
      },
      slide_visual_contracts: [visualSlideContract()],
      anchor_feedback_batch_ref: null,
      anchor_feedback_batch: null,
      contract_review_marks_ref: null,
      contract_review_marks: null,
      gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
      host_submission_capability: "unavailable",
      ai_receipt_capability: "unavailable",
    },
  };
}

function contentReviewSurface(): ContentReviewSurfaceData {
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
      section_flow: ["开篇"],
      slides: [],
      decisions: [],
      progress: {
        completed: 0,
        total: 0,
        remaining: 0,
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

describe("on-demand professional-review routing", () => {
  it("routes content-full-deck without product navigation", () => {
    const content = contentReviewSurface();

    render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

    expect(
      screen.getByRole("heading", { name: "完整售前阅读稿" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "五空间导航" }),
    ).not.toBeInTheDocument();
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

  it("accepts the closed Python anchor identity with its visual-contract-set lineage", () => {
    const visual = visualReviewSurface();

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([
    ["wrong kind", "artifact://anchor-slide-set/" + "9".repeat(64)],
    ["malformed reference", "artifact://visual-contract-set/not-a-digest"],
  ])("rejects a Python anchor identity with a %s visual-contract-set lineage", (_label, reference) => {
    const visual = visualReviewSurface();
    Object.assign(visual.review.anchor_identity, { visual_contract_set_ref: reference });

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
        deck_design_system: {},
        anchor_slide_set_ref: "anchor-slide-set:v1",
        anchors: [],
        anchor_identity: {},
        slide_visual_contracts: [],
        anchor_feedback_batch_ref: null,
        anchor_feedback_batch: null,
        contract_review_marks_ref: null,
        contract_review_marks: null,
        gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
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
    Object.assign(visual.review.gate_status, {
      unexpected: { nested: { value: true } },
    });

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
