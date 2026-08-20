import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createReviewDraftContext,
  createReviewDraftEnvelope,
  reviewDraftStorageKey,
  type ContentReviewDraftUi,
} from "../review-draft/reviewDraftStore";
import type {
  ContentDecisionChoice,
  ContentPageDecision,
  ContentReviewProjection,
  ContentReviewSurfaceData,
} from "../types/content-review";
import type { HostBridge } from "../types/host";
import type { ContentReviewPageViewModel } from "./content-review-page-view-model";
import { toContentReviewPageViewModel } from "./content-review-page-view-model";
import { ContentReviewViewModelController } from "./ContentReviewViewModelController";

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

function projection(count = 2): ContentReviewProjection {
  const slides = Array.from({ length: count }, (_, index) => {
    const order = index + 1;
    const slide = {
      slide_id: `S${String(order).padStart(2, "0")}`,
      order,
      section_id: index === 0 ? "problem" : "solution",
      page_task: `确认第 ${order} 页的目标`,
      reading_question: `第 ${order} 页是否足以支持客户判断？`,
      neutral_title: `第 ${order} 页中性标题`,
      customerJudgment: `客户形成第 ${order} 页的明确判断。`,
      visible_copy_blocks: [{
        block_id: `copy-${order}`,
        text: `第 ${order} 页页面实际文字。`,
      }],
      material_views: [],
    };
    return slide;
  });
  return {
    project_id: "p1",
    review_type: "content-full-deck",
    review_session_id: "content-session-1",
    review_session: { review_session_id: "content-session-1", status: "ready" },
    source_version: "content-v1",
    revision: 7,
    authoritative_revision: 8,
    reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    material_mode: "mixed-evidence",
    section_flow: ["现状判断", "方案验证"],
    slides,
    decisions: [],
    progress: { completed: 0, total: count, remaining: count, unsaved: 0 },
    batch: null,
    revision_plan: null,
    content_acceptance_ref: `artifact://content-acceptance/${"c".repeat(64)}`,
  };
}

function surface(count = 2): ContentReviewSurfaceData {
  return {
    surface: "review",
    selectedProjectRoot: "/managed/project",
    snapshotRevision: 8,
    review: projection(count),
  };
}

function viewModel(data: ContentReviewSurfaceData): ContentReviewPageViewModel {
  return toContentReviewPageViewModel(data.review);
}

function validPageDecision(
  slideId: string,
  decision: ContentDecisionChoice = "approved",
  comment = "",
  overrides: Partial<ContentPageDecision> = {},
): ContentPageDecision {
  const order = Number(slideId.slice(1));
  return {
    page_decision_id: `page-decision-${slideId}`,
    project_id: "p1",
    review_session_id: "content-session-1",
    source_version: "content-v1",
    reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    slide_id: slideId,
    slide_order: order,
    slide_title_snapshot: `第 ${order} 页中性标题`,
    decision,
    comment: decision === "approved" ? "" : comment,
    status: "completed",
    saved_at: "2026-08-20T09:00:00+08:00",
    supersedes_decision_ref: "",
    ...overrides,
  };
}

function reviewBatch(count: number, status: "submitted" | "withdrawn" = "submitted") {
  return {
    batch_id: `batch-${status}`,
    project_id: "p1",
    review_session_id: "content-session-1",
    source_version: "content-v1",
    reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    slide_ids: Array.from({ length: count }, (_, index) => `S${String(index + 1).padStart(2, "0")}`),
    decision_refs: Array.from({ length: count }, (_, index) => (
      `artifact://content-page-decision/${String(index + 1).padStart(64, "0")}`
    )),
    counts: { approved: count, modify: 0, evidence: 0, "merge-or-delete": 0 },
    status,
    immutable_after_submit: true,
    submitted_at: "2026-08-20T09:30:00+08:00",
    withdrawn_at: status === "withdrawn" ? "2026-08-20T10:00:00+08:00" : "",
    supersedes_ref: status === "withdrawn"
      ? `artifact://content-review-batch/${"e".repeat(64)}`
      : "",
  };
}

function bridge(callTool = vi.fn(async () => {
  throw new Error("Unexpected tool call");
})): HostBridge {
  return {
    connect: vi.fn(async () => undefined),
    callTool: callTool as HostBridge["callTool"],
  };
}

function seedDraft(data: ContentReviewSurfaceData, ui: ContentReviewDraftUi): string {
  const context = createReviewDraftContext(data);
  const key = reviewDraftStorageKey(context);
  window.sessionStorage.setItem(key, JSON.stringify(createReviewDraftEnvelope(
    context,
    ui,
    "2026-08-20T08:00:00+08:00",
  )));
  return key;
}

function readDraft(key: string): ContentReviewDraftUi | null {
  const raw = window.sessionStorage.getItem(key);
  return raw ? (JSON.parse(raw).ui as ContentReviewDraftUi) : null;
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

function markAllSaved(data: ContentReviewSurfaceData) {
  data.review.decisions = data.review.slides.map((slide) => validPageDecision(slide.slide_id));
  data.review.progress = {
    completed: data.review.slides.length,
    total: data.review.slides.length,
    remaining: 0,
    unsaved: 0,
  };
}

describe("ContentReviewViewModelController", () => {
  it("fails closed when the ViewModel and write identity do not match", () => {
    const data = surface(1);
    const mismatched = { ...viewModel(data), reviewSessionId: "another-session" };
    const callTool = vi.fn();

    const { container } = render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={mismatched}
        bridge={bridge(callTool)}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("审核页面与写入会话不一致");
    expect(container.querySelector(".content-review-vm-page")).toBeNull();
    expect(callTool).not.toHaveBeenCalled();
  });

  it("fails closed when the final page order contains duplicate slide identities", () => {
    const data = surface(2);
    data.review.slides[1].slide_id = "S01";
    const callTool = vi.fn();

    const { container } = render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("审核页面与写入会话不一致");
    expect(container.querySelector(".content-review-vm-page")).toBeNull();
    expect(callTool).not.toHaveBeenCalled();
  });

  it("fails closed when a submitted batch count contradicts authoritative decisions", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01", "modify", "已保存修改")];
    data.review.progress = { completed: 1, total: 1, remaining: 0, unsaved: 0 };
    data.review.batch = reviewBatch(1);
    const callTool = vi.fn();

    const { container } = render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("审核页面与写入会话不一致");
    expect(container.querySelector(".content-review-vm-page")).toBeNull();
    expect(callTool).not.toHaveBeenCalled();
  });

  it("initializes a validated authoritative PageDecision as clean saved state", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01", "modify", "已保存的修改意见")];
    data.review.progress = { completed: 1, total: 1, remaining: 0, unsaved: 0 };

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge()}
      />,
    );

    expect(screen.getByRole("radio", { name: "需要修改" })).toBeChecked();
    expect(screen.getByText("已保存的修改意见")).toBeInTheDocument();
    expect(screen.getAllByText("已保存")).not.toHaveLength(0);
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
  });

  it("restores a same-session local draft as dirty without impersonating saved state", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.progress = { completed: 1, total: 1, remaining: 0, unsaved: 0 };
    seedDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "恢复后继续修改" }],
      logical_scroll: null,
    });

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge()}
      />,
    );

    expect(screen.getByRole("radio", { name: "需要修改" })).toBeChecked();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("恢复后继续修改");
    expect(screen.getByText("尚未保存")).toBeInTheDocument();
    expect(screen.getByText("0 / 1")).toBeInTheDocument();
  });

  it("sends the exact page-save command and advances revision, progress, and draft state", async () => {
    const data = surface(1);
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected ${name}`);
      return {
        decision_ref: `artifact://content-page-decision/${"d".repeat(64)}`,
        decision: validPageDecision(String(args.slideId), args.decision as ContentDecisionChoice, String(args.comment)),
        snapshot: { revision: 9 },
      };
    });

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    fireEvent.change(screen.getByLabelText("S01 审核意见"), {
      target: { value: "  请补充客户现状依据。  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    await waitFor(() => expect(callTool).toHaveBeenCalledWith("save_content_page_decision", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      reviewSessionId: "content-session-1",
      sourceVersion: "content-v1",
      slideId: "S01",
      decision: "modify",
      comment: "请补充客户现状依据。",
    }));
    expect(await screen.findByText(/revision 9/)).toBeInTheDocument();
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
    expect(screen.getAllByText("已保存")).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
  });

  it.each(["REVISION_CONFLICT", "REVIEW_SOURCE_STALE"])(
    "keeps the local draft and completed count after %s",
    async (code) => {
      const data = surface(1);
      const key = seedDraft(data, {
        view: "document",
        current_slide_id: "S01",
        page_drafts: [{ slide_id: "S01", decision: "modify", comment: "冲突后保留" }],
        logical_scroll: null,
      });
      const callTool = vi.fn(async () => {
        throw Object.assign(new Error(code), { code });
      });

      render(
        <ContentReviewViewModelController
          initialData={data}
          initialViewModel={viewModel(data)}
          bridge={bridge(callTool)}
        />,
      );
      fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

      expect(await screen.findByText("版本已变化；草稿仍保留，请刷新后重试。")).toBeInTheDocument();
      expect(screen.getByLabelText("S01 审核意见")).toHaveValue("冲突后保留");
      expect(screen.getByText("0 / 1")).toBeInTheDocument();
      fireEvent(window, new PageTransitionEvent("pagehide"));
      expect(readDraft(key)?.page_drafts).toEqual([
        { slide_id: "S01", decision: "modify", comment: "冲突后保留" },
      ]);
    },
  );

  it.each([
    ["wrong slide", { slide_id: "S99" }, 9],
    ["wrong title", { slide_title_snapshot: "错误标题" }, 9],
    ["wrong source", { source_version: "content-v0" }, 9],
    ["non-growing revision", {}, 8],
  ])("rejects a malformed page-save result: %s", async (_label, overrides, returnedRevision) => {
    const data = surface(1);
    const callTool = vi.fn(async () => ({
      decision_ref: `artifact://content-page-decision/${"d".repeat(64)}`,
      decision: validPageDecision("S01", "modify", "不能丢失", overrides as Partial<ContentPageDecision>),
      snapshot: { revision: returnedRevision },
    }));

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    fireEvent.change(screen.getByLabelText("S01 审核意见"), { target: { value: "不能丢失" } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText("Runtime 返回无效结果；草稿仍保留，可直接重试。")).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("不能丢失");
    expect(screen.getByText("0 / 1")).toBeInTheDocument();
  });

  it("enables full-deck submit only for complete clean decisions and freezes writes after success", async () => {
    const data = surface(2);
    markAllSaved(data);
    const callTool = vi.fn(async (name: string) => {
      if (name !== "submit_content_review_batch") throw new Error(`Unexpected ${name}`);
      return {
        batch_ref: `artifact://content-review-batch/${"e".repeat(64)}`,
        batch: reviewBatch(2),
        snapshot: { revision: 9 },
      };
    });

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );
    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(callTool).toHaveBeenCalledWith("submit_content_review_batch", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      reviewSessionId: "content-session-1",
      sourceVersion: "content-v1",
    }));
    expect(await screen.findByText("已提交，等待整套修改方案")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "本轮审核已提交" })).toBeDisabled();
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
  });

  it("keeps all decisions available for retry when batch submission fails", async () => {
    const data = surface(2);
    markAllSaved(data);
    const callTool = vi.fn(async () => {
      throw Object.assign(new Error("stale"), { code: "REVISION_CONFLICT" });
    });

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge(callTool)}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));

    expect(await screen.findByText("当前版本已变化；所有本地输入仍保留，请刷新后重试。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeEnabled();
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });

  it("ignores a pending page-save result after the same identity receives a newer revision", async () => {
    const data = surface(1);
    const key = seedDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "pending 期间增长" }],
      logical_scroll: null,
    });
    const pending = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const callTool = vi.fn(() => pending.promise);
    const host = bridge(callTool);
    const { rerender } = render(
      <ContentReviewViewModelController initialData={data} initialViewModel={viewModel(data)} bridge={host} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("正在保存…");

    const grown = structuredClone(data);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    rerender(
      <ContentReviewViewModelController initialData={grown} initialViewModel={viewModel(grown)} bridge={host} />,
    );
    expect(screen.getByText(/revision 9/)).toBeInTheDocument();

    await act(async () => {
      pending.resolve({
        decision_ref: `artifact://content-page-decision/${"d".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "pending 期间增长"),
        snapshot: { revision: 10 },
      });
      await pending.promise;
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(screen.getByText(/revision 9/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("pending 期间增长");
    expect(readDraft(key)?.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "pending 期间增长" },
    ]);
  });

  it("isolates an old pending result when a new review identity mounts", async () => {
    const oldData = surface(1);
    seedDraft(oldData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "旧会话草稿" }],
      logical_scroll: null,
    });
    const oldPending = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const oldHost = bridge(vi.fn(() => oldPending.promise));
    const newData = surface(1);
    newData.review.review_session_id = "content-session-2";
    newData.review.review_session = { review_session_id: "content-session-2" };
    const newKey = seedDraft(newData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "evidence", comment: "新会话草稿" }],
      logical_scroll: null,
    });
    const { rerender } = render(
      <ContentReviewViewModelController
        initialData={oldData}
        initialViewModel={viewModel(oldData)}
        bridge={oldHost}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("正在保存…");

    rerender(
      <ContentReviewViewModelController
        initialData={newData}
        initialViewModel={viewModel(newData)}
        bridge={bridge()}
      />,
    );
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("新会话草稿");

    await act(async () => {
      oldPending.resolve({
        decision_ref: `artifact://content-page-decision/${"d".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "旧会话草稿"),
        snapshot: { revision: 9 },
      });
      await oldPending.promise;
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("新会话草稿");
    expect(readDraft(newKey)?.page_drafts).toEqual([
      { slide_id: "S01", decision: "evidence", comment: "新会话草稿" },
    ]);
  });

  it("restores logical scroll against the new ViewModel header and slide ids", async () => {
    const data = surface(2);
    seedDraft(data, {
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 40 },
    });
    vi.spyOn(window, "getComputedStyle").mockReturnValue({ position: "sticky" } as CSSStyleDeclaration);
    vi.spyOn(window, "scrollX", "get").mockReturnValue(23);
    vi.spyOn(window, "scrollY", "get").mockReturnValue(300);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function rect(this: HTMLElement) {
      if (this.classList.contains("content-review-vm-header")) {
        return { top: 0, bottom: 100, left: 0, right: 100, width: 100, height: 100, x: 0, y: 0, toJSON: () => ({}) };
      }
      if (this.id === "content-vm-S02") {
        return { top: 240, bottom: 840, left: 0, right: 100, width: 100, height: 600, x: 0, y: 240, toJSON: () => ({}) };
      }
      return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) };
    });

    render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge()}
      />,
    );

    await waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith({
      behavior: "auto",
      left: 23,
      top: 480,
    }));
  });

  it("preserves final order for 60 pages and never renders backend governance fields", () => {
    const data = surface(60);
    const { container } = render(
      <ContentReviewViewModelController
        initialData={data}
        initialViewModel={viewModel(data)}
        bridge={bridge()}
      />,
    );

    const pages = Array.from(container.querySelectorAll("[data-content-review-vm-slide]"));
    expect(pages).toHaveLength(60);
    expect(pages.map((page) => page.id)).toEqual(
      Array.from({ length: 60 }, (_, index) => `content-vm-S${String(index + 1).padStart(2, "0")}`),
    );
    for (const hidden of ["后台身份字段", "后台证据", "后台分析", "后台映射", "后台演讲备注", "后台质量记录"]) {
      expect(container).not.toHaveTextContent(hidden);
    }
  });
});
