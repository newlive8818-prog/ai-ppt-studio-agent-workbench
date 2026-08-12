import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { hostBridge, reviewWidgetData } from "./test-fixtures";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("professional review surface", () => {
  it("uses one-line review controls and keeps forbidden workflow actions absent", () => {
    const initial = reviewWidgetData("content");
    render(<ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />);

    expect(screen.getAllByRole("banner").find((node) => node.classList.contains("review-header"))).toBeTruthy();
    const contentMode = screen.getByRole("button", { name: "内容审阅" });
    const visualMode = screen.getByRole("button", { name: "视觉合同" });
    expect(contentMode).toHaveAttribute("aria-pressed", "true");
    expect(visualMode).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "目录" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "标记 0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存标记" })).toBeDisabled();
    expect(screen.queryByRole("dialog", { name: "审阅目录" })).not.toBeInTheDocument();

    expect(screen.getByText("完整讲解稿必须原样进入专业审阅页。")).toBeInTheDocument();
    expect(screen.getByText("sources/meeting.json#p3")).toBeInTheDocument();
    expect(screen.queryByText("返回聊天")).not.toBeInTheDocument();
    expect(screen.queryByText("版本历史")).not.toBeInTheDocument();
    expect(screen.queryByText("样张画廊")).not.toBeInTheDocument();
    expect(screen.queryByText(/G0|G3|G4/)).not.toBeInTheDocument();
    expect(screen.queryByText("下载 PPTX")).not.toBeInTheDocument();
  });

  it("requests an independently scoped session when switching review documents", async () => {
    const initial = reviewWidgetData("content");
    const { bridge } = hostBridge(initial);
    const switchReview = vi.fn(async () => undefined);
    (bridge as typeof bridge & { switchReview: typeof switchReview }).switchReview = switchReview;
    render(<ProfessionalReviewApp initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "视觉合同" }));

    await waitFor(() => expect(switchReview).toHaveBeenCalledWith("visual"));
  });

  it("preserves unsaved marks and blocks document switching until they are saved", async () => {
    const initial = reviewWidgetData("content");
    const { bridge } = hostBridge(initial);
    const switchReview = vi.fn(async () => undefined);
    (bridge as typeof bridge & { switchReview: typeof switchReview }).switchReview = switchReview;
    render(<ProfessionalReviewApp initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getAllByRole("button", { name: "为字段 visible_content 添加标记" })[0]);
    fireEvent.change(screen.getByLabelText("标记说明"), { target: { value: "切换前必须保留" } });
    fireEvent.click(screen.getByRole("button", { name: "加入待保存" }));
    fireEvent.click(screen.getByRole("button", { name: "视觉合同" }));

    expect(switchReview).not.toHaveBeenCalled();
    expect(screen.getByText("请先保存当前标记，再切换审阅文档。")).toBeInTheDocument();
    expect(screen.getByText("切换前必须保留")).toBeInTheDocument();
  });

  it("keeps outline and marks drawers mutually exclusive", () => {
    const initial = reviewWidgetData("content");
    render(<ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "目录" }));
    expect(screen.getByRole("dialog", { name: "审阅目录" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "标记 0" }));
    expect(screen.queryByRole("dialog", { name: "审阅目录" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "审阅标记" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "审阅标记" })).not.toBeInTheDocument();
  });

  it("drafts field and selected-text marks and saves exact source plus revision", async () => {
    const initial = reviewWidgetData("content");
    const { bridge, callTool } = hostBridge(initial);
    const selection = vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "三条断点",
    } as Selection);
    render(<ProfessionalReviewApp initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getAllByRole("button", { name: "为字段 visible_content 添加标记" })[0]);
    fireEvent.change(screen.getByLabelText("标记说明"), { target: { value: "补充断点来源" } });
    fireEvent.click(screen.getByRole("button", { name: "加入待保存" }));

    fireEvent.click(screen.getByRole("button", { name: "标记选中文字" }));
    expect(screen.getAllByText("三条断点").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("标记说明"), { target: { value: "选中文字需要强调" } });
    fireEvent.click(screen.getByRole("button", { name: "加入待保存" }));

    fireEvent.click(screen.getByRole("button", { name: "保存标记" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("save_review_marks", expect.objectContaining({
      projectRoot: "/managed/project",
      expectedRevision: 12,
      reviewType: "content",
      sourceVersion: "content-v0001-abc123",
      marks: expect.arrayContaining([
        expect.objectContaining({ field_anchor: "slide-s01-visible-content", comment: "补充断点来源" }),
        expect.objectContaining({ exact_text: "三条断点", comment: "选中文字需要强调" }),
      ]),
    })));
    selection.mockRestore();
  });

  it("captures prefix and suffix for the intended duplicate occurrence", async () => {
    const initial = reviewWidgetData("content");
    initial.review.sections[2].fields[0].value = "第一处 三条断点 中间 第二处 三条断点 结束";
    const { bridge, callTool } = hostBridge(initial);
    render(<ProfessionalReviewApp initialData={initial} bridge={bridge} />);

    const textNode = screen.getByText(/^第一处/).firstChild;
    if (!textNode) throw new Error("duplicate fixture text node missing");
    const fullText = textNode.textContent || "";
    const second = fullText.lastIndexOf("三条断点");
    const range = document.createRange();
    range.setStart(textNode, second);
    range.setEnd(textNode, second + "三条断点".length);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);

    fireEvent.click(screen.getByRole("button", { name: "标记选中内容" }));
    fireEvent.change(screen.getByLabelText("标记说明"), { target: { value: "只批注第二处" } });
    fireEvent.click(screen.getByRole("button", { name: "加入待保存" }));
    fireEvent.click(screen.getByRole("button", { name: "保存标记" }));

    await waitFor(() => expect(callTool).toHaveBeenCalledWith("save_review_marks", expect.objectContaining({
      marks: [expect.objectContaining({
        field_anchor: "slide-s01-visible-content",
        exact_text: "三条断点",
        prefix: expect.stringContaining("中间 第二处 "),
        suffix: expect.stringContaining(" 结束"),
      })],
    })));
  });

  it.each(["REVISION_CONFLICT", "REVIEW_SOURCE_STALE"])("preserves resubmittable drafts after %s", async (code) => {
    const initial = reviewWidgetData("content");
    const { bridge } = hostBridge(initial);
    bridge.callTool = vi.fn(async () => {
      const error = new Error("conflict") as Error & { code?: string };
      error.code = code;
      throw error;
    });
    render(<ProfessionalReviewApp initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getAllByRole("button", { name: "为字段 visible_content 添加标记" })[0]);
    fireEvent.change(screen.getByLabelText("标记说明"), { target: { value: "不要丢失这条" } });
    fireEvent.click(screen.getByRole("button", { name: "加入待保存" }));
    fireEvent.click(screen.getByRole("button", { name: "保存标记" }));
    await waitFor(() => expect(screen.getByText(/\u9879\u76ee\u7248\u672c\u5df2\u66f4\u65b0/)).toBeInTheDocument());
    expect(screen.getByText("不要丢失这条")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存标记" })).toBeEnabled();
  });
});

describe("review surface matches backend projection structure", () => {
  it("treats content-structure as a standing section, not a slide page", () => {
    const initial = reviewWidgetData("content");
    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />
    );
    const pageSheets = container.querySelectorAll('article.review-sheet[id^="slide-"]');
    // 2 slide pages (slide-s01, slide-s02); content-structure must NOT be a page sheet.
    expect(pageSheets.length).toBe(2);
    expect(container.querySelector('article.review-sheet[id="content-structure"]')).toBeNull();
    // The page count chip reflects only slide pages (also echoed in the outline).
    expect(screen.getAllByText("2 页").length).toBeGreaterThan(0);
    // content-structure still renders as its own standing section.
    expect(container.querySelector('section.review-doc-section[id="content-structure"]')).toBeTruthy();
  });

  it("renders visual framework + design system once and only visual-slide-* as pages", () => {
    const initial = reviewWidgetData("visual");
    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />
    );
    const pageSheets = container.querySelectorAll('article.review-sheet[id^="visual-slide-"]');
    expect(pageSheets.length).toBe(1);
    // deck-design-system is a standing section, rendered exactly once (no double render).
    expect(container.querySelectorAll('[id="deck-design-system"]').length).toBe(1);
    expect(screen.getAllByText("1 页").length).toBeGreaterThan(0);
    // visible_copy (frozen text) appears in the frozen-content column, not lost.
    expect(screen.getAllByText("五套系统").length).toBeGreaterThan(0);
    // page_family routes to the visual implementation contract column.
    expect(screen.getAllByText("页面家族").length).toBeGreaterThan(0);
    expect(screen.getAllByText("证据页").length).toBeGreaterThan(0);
  });

  it("renders Gate and four-target evidence from the formal projection instead of hard-coded pass copy", () => {
    const initial = reviewWidgetData("visual");
    initial.review.gate_status = { G1: "passed", G2: "failed", G3: "locked" };
    initial.review.sections[0].fields.push(
      {
        anchor: "visual-framework-anchor-identity",
        label: "anchor_identity",
        value: "artifact://anchor-slide-set/" + "a".repeat(64),
      },
      {
        anchor: "visual-framework-target-evidence-identities",
        label: "target_evidence_identities",
        value: [
          {
            target_id: "macos-powerpoint",
            operating_system: "macOS",
            operating_system_version: "15.6",
            application: "Microsoft PowerPoint",
            application_version: "16.111.2",
            pptx_sha256: "7".repeat(64),
            overall_result: "passed",
            evidence_ref: "artifact://target-render-capture/" + "1".repeat(64),
          },
          {
            target_id: "macos-wps",
            operating_system: "macOS",
            operating_system_version: "15.6",
            application: "WPS Office",
            application_version: "12.1",
            pptx_sha256: "7".repeat(64),
            overall_result: "passed",
            evidence_ref: "artifact://target-render-capture/" + "2".repeat(64),
          },
          {
            target_id: "windows-powerpoint",
            operating_system: "Windows 11",
            operating_system_version: "24H2",
            application: "Microsoft PowerPoint",
            application_version: "2507",
            pptx_sha256: "7".repeat(64),
            overall_result: "failed",
            evidence_ref: "artifact://target-render-capture/" + "3".repeat(64),
          },
          {
            target_id: "windows-wps",
            operating_system: "Windows 11",
            operating_system_version: "24H2",
            application: "WPS Office",
            application_version: "12.1",
            pptx_sha256: "7".repeat(64),
            overall_result: "missing",
            evidence_ref: "artifact://target-render-capture/" + "4".repeat(64),
          },
        ],
      },
    );

    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />
    );

    expect(screen.getByText("G1 概念收敛：通过")).toBeInTheDocument();
    expect(screen.getByText("G2 工程与实机验证：未通过")).toBeInTheDocument();
    expect(screen.queryByText(/工程与实机验证通过/)).not.toBeInTheDocument();
    expect(screen.queryByText(/目标软件渲染：全部通过/)).not.toBeInTheDocument();
    expect(screen.queryByText("合同通过")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "四目标桌面实机证据" })).toBeInTheDocument();
    expect(screen.getByText("macOS · Microsoft PowerPoint")).toBeInTheDocument();
    expect(screen.getByText("macOS · WPS Office")).toBeInTheDocument();
    expect(screen.getByText("Windows 11 · Microsoft PowerPoint")).toBeInTheDocument();
    expect(screen.getByText("Windows 11 · WPS Office")).toBeInTheDocument();
    expect(container).toHaveTextContent("7".repeat(64));
    expect(container).toHaveTextContent("artifact://anchor-slide-set/" + "a".repeat(64));
    expect(container).not.toHaveTextContent("target_evidence_identities");
  });
});
