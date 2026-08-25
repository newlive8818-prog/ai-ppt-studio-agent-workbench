import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "../__fixtures__/content-sidebar-review.json";
import { ContentReviewDocument } from "../components/content-review/ContentReviewDocument";
import type { ContentReviewClient } from "../lib/content-review-client";
import { compactWidgetData, hostBridge } from "../test-fixtures";
import type { ContentFullDeckReviewProjection } from "../types/content-review";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

function projection(): ContentFullDeckReviewProjection {
  return structuredClone(fixture) as ContentFullDeckReviewProjection;
}

function client(): ContentReviewClient {
  return {
    load: vi.fn(async () => projection()),
    saveDecision: vi.fn(),
    submitBatch: vi.fn(),
    openEvidenceBrowser: vi.fn(),
  };
}

describe("complete continuous content-review document", () => {
  it("keeps the accepted 08 prototype reading structure instead of a runtime governance dashboard", () => {
    const data = projection();
    const host = hostBridge(compactWidgetData("blueprint"));
    const { container } = render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={client()}
        onProjectionChange={vi.fn()}
      />,
    );

    expect(container.querySelector(".content-review-header")).not.toBeNull();
    expect(container.querySelector(".content-review-progress-track")).not.toBeNull();
    expect(container.querySelector(".content-review-chapter-nav")).not.toBeNull();
    expect(container.querySelector(".content-review-deck-intro")).not.toBeNull();
    expect(container.querySelectorAll("[data-content-chapter]")).toHaveLength(1);
    expect(container.querySelectorAll("[data-content-slide]")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll("article.page")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".page-head")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".page-body")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".page-text")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".purpose")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".visible-copy")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".visual-evidence")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll("details.full-script")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".quality")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".decision-question")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".actions")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".content-slide-reading-grid")).toHaveLength(data.slides.length);
    expect(container.querySelectorAll(".page-decision-options")).toHaveLength(data.slides.length);
    expect(container).toHaveTextContent("这一页的目标");
    expect(container).toHaveTextContent("阅读问题");
    expect(container).toHaveTextContent("页面实际文字");
    expect(container).toHaveTextContent("图片与材料");
    expect(container).toHaveTextContent("完整逐字稿");
    expect(container).not.toHaveTextContent("希望客户形成的判断");
    expect(container.querySelector(".content-review-session-summary")).toBeNull();
  });

  it("renders every review field and real evidence without truncation or paging", () => {
    const data = projection();
    const host = hostBridge(compactWidgetData("blueprint"));
    host.callTool.mockResolvedValue({ asset: { assetRef: "a", mimeType: "image/png", bytes: 1, dataBase64: "AA==" } });
    const { container } = render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={client()}
        onProjectionChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "完整内容审核" })).toBeInTheDocument();
    expect(screen.getByLabelText("审核回执状态")).toHaveTextContent("宿主打开opened");
    expect(screen.getByText("智能制造业务范围与系统现状")).toBeInTheDocument();
    expect(screen.getByText("说明当前业务事项、系统范围和经营协同边界。")).toBeInTheDocument();
    expect(screen.getByText("当前制造与经营协同主要涉及哪些业务环节与系统？")).toBeInTheDocument();
    expect(container).toHaveTextContent("本页不对断点数量、损失规模或建设收益作未经验证的定量承诺。");
    expect(container).toHaveTextContent("artifact://material/chongqing-electromechanical-v5#page=3&region=业务范围图");
    expect(container).toHaveTextContent("S01-C01、S01-C02");
    expect(container).toHaveTextContent("证据缺口");
    expect(container).toHaveTextContent("当前未绑定可定位来源");
    expect(container).toHaveTextContent("AI 分析");
    expect(container).toHaveTextContent("现状-S01 → 要求-R01");
    expect(container).toHaveTextContent("逐字稿：这一页先不急着得出建设结论");
    expect(container).toHaveTextContent("正文可独立理解，没有依赖逐字稿补全核心逻辑。");
    expect(container).toHaveTextContent("从封面与任务进入客户当前业务事项。");
    expect(container).toHaveTextContent("在现状边界上进一步识别跨系统协同问题。");

    expect(container.querySelectorAll("article.content-slide-section")).toHaveLength(2);
    expect(container.querySelectorAll("#content-slide-S01")).toHaveLength(1);
    expect(container.querySelectorAll("#content-slide-S02")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "目录定位" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "定位下一页未判断" })).toBeInTheDocument();
    expect(container).not.toHaveTextContent("加载更多");
    expect(container).not.toHaveTextContent("下一页内容");
    expect(container).not.toHaveTextContent("希望客户形成的判断");
    expect(container.querySelector("[class*='clamp']")).toBeNull();
  });

  it("renders an explicitly bound key-evidence image as a large lazy-loaded figure", async () => {
    const data = projection();
    data.slides[0].evidence_bindings[0] = {
      ...data.slides[0].evidence_bindings[0],
      asset_ref: "review-assets/content-evidence-page.jpg",
      caption: "真实成稿 P02",
      material_kind: "image",
    };
    const host = hostBridge(compactWidgetData("blueprint"));
    host.callTool.mockResolvedValue({
      asset: {
        assetRef: "review-assets/content-evidence-page.jpg",
        mimeType: "image/jpeg",
        bytes: 1,
        dataBase64: "AA==",
      },
    });

    render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={client()}
        onProjectionChange={vi.fn()}
      />,
    );

    const image = await screen.findByRole("img", { name: "真实成稿 P02" });
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveClass("content-evidence-image");
    expect(screen.getByText("真实成稿 P02")).toBeInTheDocument();
  });

  it("uses an overlay directory only for navigation", () => {
    const data = projection();
    const host = hostBridge(compactWidgetData("blueprint"));
    render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={client()}
        onProjectionChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "目录定位" }));
    expect(screen.getByRole("dialog", { name: "全稿目录" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /S02.*跨系统协同问题/ }));
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "全稿目录" })).not.toBeInTheDocument();
  });

  it("submits one immutable batch and retries only a failed follow-up message", async () => {
    const data = projection();
    data.slides = data.slides.map((slide) => ({
      ...slide,
      decision_state: { selected: "approved", comment: "", completed: true, saved: true, frozen: false },
    }));
    data.review_progress = {
      total: 2,
      completed: 2,
      remaining: 0,
      saved_comment_count: 0,
      counts: { approved: 2, modify: 0, evidence: 0, merge_or_delete: 0 },
    };
    const submitted = structuredClone(data);
    submitted.review_session.status = "submitted";
    submitted.review_session.submitted_at = "2026-08-24T10:05:00Z";
    submitted.slides = submitted.slides.map((slide) => ({
      ...slide,
      decision_state: { ...slide.decision_state, frozen: true },
    }));

    const host = hostBridge(compactWidgetData("blueprint"));
    host.bridge.sendFollowUp = vi.fn()
      .mockRejectedValueOnce(new Error("message unavailable"))
      .mockResolvedValueOnce(undefined);
    const contentClient = client();
    contentClient.submitBatch = vi.fn(async () => ({
      artifact_ref: "artifact://content-review-batch/submitted-v3",
      follow_up_message: "请集中处理整套内容审核意见",
      revision: 43,
    }));
    contentClient.load = vi.fn(async () => submitted);
    const onProjectionChange = vi.fn();
    render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={contentClient}
        onProjectionChange={onProjectionChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
    await waitFor(() => expect(contentClient.submitBatch).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(host.bridge.sendFollowUp).toHaveBeenCalledTimes(1));
    expect(contentClient.submitBatch).toHaveBeenCalledWith({
      projectRoot: "/managed/project",
      expectedRevision: 42,
      reviewSessionId: "review-session-content-v3",
      reviewBatchId: "content-review-batch:review-session-content-v3",
    });
    expect(onProjectionChange).toHaveBeenCalledWith(submitted);
    expect(await screen.findByText("审核批次已持久化；Codex 后续消息尚未发送。")).toBeInTheDocument();
    expect(screen.getByText("持久化回执 artifact://content-review-batch/submitted-v3")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重试发送给 Codex" }));
    await waitFor(() => expect(host.bridge.sendFollowUp).toHaveBeenCalledTimes(2));
    expect(contentClient.submitBatch).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("已提交，等待整套修改方案。")).toBeInTheDocument();
  });
});
