import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewSurfaceRouter } from "./ReviewSurfaceRouter";
import visualFixture from "./__fixtures__/review-projection.visual.json";
import type { ContentReviewClient } from "./lib/content-review-client";
import type { ContentFullDeckReviewProjection } from "./types/content-review";
import type { HostBridge, ReviewWidgetData } from "./types";

afterEach(cleanup);

const projection: ContentFullDeckReviewProjection = {
  surface: "content-full-deck",
  project_id: "project-v22",
  revision: 18,
  source_version: "artifact://reading-deck-blueprint/v22",
  gate_status: "content-review-ready",
  review_session: {
    review_session_id: "review-session-current-v22",
    review_type: "content-full-deck",
    project_id: "project-v22",
    target_artifact_ref: "artifact://reading-deck-blueprint/v22",
    source_version: "reading-v22",
    revision: 17,
    status: "opened",
    open_policy: "foreground-if-waiting",
    host_open_status: "opened",
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    created_at: "2026-08-24T10:00:00Z",
    last_opened_at: "2026-08-24T10:01:00Z",
    submitted_at: "",
  },
  review_progress: {
    total: 1,
    completed: 0,
    remaining: 1,
    saved_comment_count: 0,
    counts: { approved: 0, modify: 0, evidence: 0, merge_or_delete: 0 },
  },
  slides: [{
    slide_id: "S01",
    order: 1,
    neutral_title: "客户当前业务事项与材料边界",
    page_task: "说明当前业务事项与材料边界。",
    reading_question: "哪些内容是来源事实，哪些仍待联合验证？",
    visible_copy_blocks: [{ block_id: "copy-1", role: "body", text: "完整可见正文，不截断。" }],
    identity_labels: ["来源事实", "待联合验证"],
    evidence_bindings: [],
    analysis_or_proposal_blocks: [{ block_id: "analysis-1", identity: "待联合验证", text: "量化范围仍需联合确认。" }],
    solution_mapping_refs: ["事实-F01 → 要求-R01"],
    speaker_notes: "完整演讲备注。",
    reading_quality: { standalone_readable: true, density: "适中" },
    previous_relation: "当前是本稿第一页。",
    next_relation: "进入问题诊断。",
    decision_state: { selected: "", comment: "", completed: false, saved: false, frozen: false },
  }],
};

function bridge(): HostBridge {
  return {
    connect: vi.fn(async () => {}),
    callTool: vi.fn(),
    updateModelContext: vi.fn(async () => {}),
    sendFollowUp: vi.fn(async () => {}),
    confirmMission: vi.fn(),
    getHostEnvironment: vi.fn(),
    notifySize: vi.fn(),
  };
}

function client(): ContentReviewClient {
  return {
    load: vi.fn(async () => structuredClone(projection)),
    saveDecision: vi.fn(),
    submitBatch: vi.fn(),
    openEvidenceBrowser: vi.fn(),
  };
}

describe("v2.2 review surface routing", () => {
  it("routes visual review to the independent accepted 07 surface", () => {
    const visualData: ReviewWidgetData = {
      surface: "review",
      selectedProjectRoot: "/managed/project-v22",
      snapshotRevision: 27,
      review: structuredClone(visualFixture) as ReviewWidgetData["review"],
    };
    const { container } = render(
      <ReviewSurfaceRouter initialData={visualData} bridge={bridge()} />,
    );

    expect(container.querySelector(".visual-professional-page")).not.toBeNull();
    expect(container.querySelector(".visual-professional-review-view-switch")).not.toBeNull();
    expect(container.querySelectorAll("[data-anchor-tab]")).toHaveLength(3);
    expect(container.querySelector(".anchor-workbench")).not.toBeNull();
    expect(container.querySelector(".anchor-canvas")).not.toBeNull();
    expect(container.querySelector(".region-feedback-editor")).not.toBeNull();
    expect(container.querySelector(".anchor-feedback-composer")).not.toBeNull();
    expect(container.querySelector(".feedback-panel")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "审核视觉锚点成果" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "与上一版对比" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始标注" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "提交本轮反馈" })).toBeInTheDocument();
    const contractTab = screen.getByRole("tab", { name: "完整视觉合同" });
    expect(contractTab).toBeInTheDocument();
    expect(container).not.toHaveTextContent("内容审核");
    expect(container).not.toHaveTextContent("内容蓝图");
    expect(container).not.toHaveTextContent("通用审阅工作台");

    fireEvent.click(contractTab);
    expect(container.querySelector(".contract-document-head")).not.toBeNull();
    expect(container.querySelector(".anchor-evidence-strip")).not.toBeNull();
    expect(container.querySelector(".visual-contract-list")).not.toBeNull();
    expect(container.querySelector(".contract-page")).not.toBeNull();
    expect(container.querySelector(".field-mark-button")).not.toBeNull();
    expect(container.querySelectorAll("[data-contract-section]").length).toBeGreaterThan(2);
    fireEvent.click(screen.getByRole("button", { name: "目录" }));
    expect(screen.getByRole("dialog", { name: "视觉合同目录" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("关闭视觉合同目录"));

    const firstFieldMark = container.querySelector(".field-mark-button") as HTMLButtonElement;
    fireEvent.click(firstFieldMark);
    expect(screen.getByRole("dialog", { name: "合同标记" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "合同标记意见" }), {
      target: { value: "该字段需要进一步明确。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
    expect(screen.getByText("该字段需要进一步明确。")).toBeInTheDocument();
    expect(container.querySelector(".feedback-panel")).not.toHaveTextContent("该字段需要进一步明确。");
  });

  it("renders the current content-full-deck session without any retired workbench shell", () => {
    const { container } = render(
      <ReviewSurfaceRouter
        initialData={projection}
        projectRoot="/managed/project-v22"
        bridge={bridge()}
        contentReviewClient={client()}
      />,
    );

    expect(screen.getByRole("heading", { name: "完整内容审核" })).toBeInTheDocument();
    expect(screen.getByText("客户当前业务事项与材料边界")).toBeInTheDocument();
    expect(container).toHaveTextContent("完整可见正文，不截断。");
    expect(container).not.toHaveTextContent("review-session-current-v22");

    for (const forbidden of [
      "项目总览",
      "材料工作台",
      "内容蓝图",
      "视觉设计空间",
      "制作与交付",
      "希望客户形成的判断",
      "确认 G0",
    ]) {
      expect(container).not.toHaveTextContent(forbidden);
    }
    expect(container.querySelector(".workspace-sidebar")).toBeNull();
    expect(container.querySelector(".compact-navigation")).toBeNull();
  });

  it("shows the Runtime-owned host-open receipt without inferring opened from session status", () => {
    const withoutOpenReceipt = structuredClone(projection);
    withoutOpenReceipt.review_session.status = "opened";
    withoutOpenReceipt.review_session.host_open_status = "not-requested";
    render(
      <ReviewSurfaceRouter
        initialData={withoutOpenReceipt}
        projectRoot="/managed/project-v22"
        bridge={bridge()}
        contentReviewClient={client()}
      />,
    );

    const receipts = screen.getByLabelText("审核回执状态");
    expect(receipts).toHaveTextContent("宿主打开not-requested");
    expect(receipts).not.toHaveTextContent("宿主打开opened");
  });
});
