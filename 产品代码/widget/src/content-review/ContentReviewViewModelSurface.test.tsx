import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { HostBridge } from "../types/host";
import type { ContentReviewPageViewModel } from "./content-review-page-view-model";
import { ContentReviewViewModelSurface } from "./ContentReviewViewModelSurface";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function pageViewModel(): ContentReviewPageViewModel {
  return {
    projectId: "p1",
    projectLabel: "经营一体化方案",
    reviewSessionId: "review-1",
    readingBlueprintRef: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    sourceVersion: "content-v1",
    revision: 7,
    authoritativeRevision: 8,
    progress: { completed: 0, total: 2, remaining: 2, unsaved: 0 },
    sections: [
      { sectionId: "problem", title: "现状判断", slideIds: ["S01"] },
      { sectionId: "solution", title: "方案验证", slideIds: ["S02"] },
    ],
    slides: [{
      slideId: "S01",
      order: 1,
      sectionId: "problem",
      neutralTitle: "当前流程断点与证据边界",
      pageGoal: "确认当前流程断点及证据边界",
      customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
      readingQuestion: "现有材料能否支撑当前判断？",
      draftContent: {
        title: "当前流程断点与证据边界",
        blocks: [
          { blockId: "p-1", type: "paragraph", text: "当前流程存在三个待核实断点。" },
          { blockId: "b-1", type: "bullet", text: "经营口径需要统一。" },
          { blockId: "b-2", type: "bullet", text: "跨系统协同需要验证。" },
        ],
      },
      materialVisuals: [{
        visualId: "S01-M01",
        assetRef: "review-assets/content/S01-M01.png",
        altText: "第 1 页《当前流程断点与证据边界》页面画面 1",
      }],
      savedDecision: null,
      localDraftState: { decision: "", comment: "", dirty: false },
    }, {
      slideId: "S02",
      order: 2,
      sectionId: "solution",
      neutralTitle: "联合方案验证范围",
      pageGoal: "确认联合验证的范围与边界",
      customerJudgment: "客户能够基于明确边界决定是否进入下一步。",
      readingQuestion: "当前范围是否足以支持下一步决策？",
      draftContent: {
        title: "联合方案验证范围",
        blocks: [{ blockId: "p-2", type: "paragraph", text: "一期先验证经营与生产协同链路。" }],
      },
      materialVisuals: [],
      savedDecision: null,
      localDraftState: { decision: "", comment: "", dirty: false },
    }],
    batchState: "open",
    availableActions: { savePageDecision: true, submitReviewBatch: true },
  };
}

function bridge(callTool = vi.fn()): HostBridge {
  return {
    connect: vi.fn(async () => undefined),
    callTool,
  } as unknown as HostBridge;
}

function actionProps() {
  return {
    onDecisionChange: vi.fn(),
    onCommentChange: vi.fn(),
    onSavePageDecision: vi.fn(async () => true),
    onSubmitReviewBatch: vi.fn(async () => undefined),
  };
}

function installIntersectionObserver() {
  const observers: Array<{
    callback: IntersectionObserverCallback;
    targets: Set<Element>;
  }> = [];
  class ControlledIntersectionObserver {
    readonly root = null;
    readonly rootMargin = "320px 0px";
    readonly thresholds = [0];
    readonly targets = new Set<Element>();
    constructor(readonly callback: IntersectionObserverCallback) {
      observers.push({ callback, targets: this.targets });
    }
    observe(target: Element) { this.targets.add(target); }
    unobserve(target: Element) { this.targets.delete(target); }
    disconnect() { this.targets.clear(); }
    takeRecords(): IntersectionObserverEntry[] { return []; }
  }
  vi.stubGlobal("IntersectionObserver", ControlledIntersectionObserver as unknown as typeof IntersectionObserver);
  return {
    intersectAll() {
      for (const observer of observers) {
        for (const target of observer.targets) {
          observer.callback([{
            target,
            isIntersecting: true,
            intersectionRatio: 1,
            boundingClientRect: target.getBoundingClientRect(),
            intersectionRect: target.getBoundingClientRect(),
            rootBounds: null,
            time: 0,
          } as IntersectionObserverEntry], {} as IntersectionObserver);
        }
      }
    },
  };
}

it("renders the accepted continuous review contract from ViewModel fields only", () => {
  const { container } = render(
    <ContentReviewViewModelSurface
      viewModel={pageViewModel()}
      bridge={bridge()}
      projectRoot="/managed/project"
      {...actionProps()}
    />,
  );

  expect(screen.getByRole("heading", { name: "经营一体化方案" })).toBeInTheDocument();
  expect(screen.getAllByText("这一页的目标")).toHaveLength(2);
  expect(screen.getAllByText("希望客户形成的判断")).toHaveLength(2);
  expect(screen.getAllByText("页面实际文字")).toHaveLength(2);
  expect(screen.getAllByText("文字与图片材料一起审核")).toHaveLength(1);
  expect(screen.queryByText("本页暂无可审核的页面画面。")).not.toBeInTheDocument();
  expect(screen.getByText("当前流程存在三个待核实断点。")).toBeInTheDocument();
  expect(screen.getByText("经营口径需要统一。")).toBeInTheDocument();
  expect(screen.getByText("跨系统协同需要验证。")).toBeInTheDocument();
  expect(screen.getByText("客户确认现状边界后，再判断是否进入联合方案验证。")).toBeInTheDocument();
  expect(container.querySelectorAll("[data-content-review-vm-slide]")).toHaveLength(2);
  expect(Array.from(container.querySelectorAll("[data-content-review-vm-slide]")).map((node) => node.id)).toEqual([
    "content-vm-S01",
    "content-vm-S02",
  ]);
  expect(within(screen.getByLabelText("S01 页面实际文字")).getAllByRole("listitem")).toHaveLength(2);

  const firstPage = screen.getByLabelText("S01 内容审核");
  const secondPage = screen.getByLabelText("S02 内容审核");
  expect(within(firstPage).getByRole("region", {
    name: "S01 文字与图片材料一起审核",
  })).toBeInTheDocument();
  expect(within(secondPage).queryByRole("region", {
    name: "S02 文字与图片材料一起审核",
  })).not.toBeInTheDocument();
  expect(within(secondPage).getByRole("region", {
    name: "S02 页面实际文字",
  })).toBeInTheDocument();
  expect(within(secondPage).getByText("本页阅读判断：")).toBeInTheDocument();
  expect(within(secondPage).getAllByRole("radio")).toHaveLength(4);

  const grids = container.querySelectorAll(".content-review-vm-reading-grid");
  expect(grids[0]).toHaveClass("content-review-vm-reading-grid--with-visuals");
  expect(grids[1]).toHaveClass("content-review-vm-reading-grid--text-only");

  for (const rejected of [
    "完整可见文字",
    "分析、假设与建议",
    "完整演讲备注",
    "证据与身份",
    "查看来源证据",
    "问题—方案映射",
    "跨页关系",
    "阅读质量",
    "用途",
    "处理方式",
    "证据身份",
  ]) expect(container).not.toHaveTextContent(rejected);
});

it("reports controlled page decisions, inline comments, saves, and full-deck submit without writing through the bridge", async () => {
  const hostCall = vi.fn();
  const host = bridge(hostCall);
  const actions = actionProps();
  const initial = pageViewModel();
  const { rerender } = render(
    <ContentReviewViewModelSurface
      viewModel={initial}
      bridge={host}
      projectRoot="/managed/project"
      {...actions}
    />,
  );
  const firstPage = screen.getByLabelText("S01 内容审核");
  expect(within(firstPage).getAllByRole("radio")).toHaveLength(4);
  fireEvent.click(within(firstPage).getByRole("radio", { name: "需要修改" }));
  expect(actions.onDecisionChange).toHaveBeenCalledWith("S01", "modify");

  const dirty = {
    ...initial,
    progress: { ...initial.progress, unsaved: 1 },
    slides: initial.slides.map((slide) => slide.slideId === "S01" ? {
      ...slide,
      localDraftState: { decision: "modify" as const, comment: "请补充现状依据。", dirty: true as const },
    } : slide),
  } satisfies ContentReviewPageViewModel;
  rerender(
    <ContentReviewViewModelSurface
      viewModel={dirty}
      bridge={host}
      projectRoot="/managed/project"
      {...actions}
    />,
  );
  const comment = screen.getByRole("textbox", { name: "S01 审核意见" });
  fireEvent.change(comment, { target: { value: "请补充客户现状依据。" } });
  expect(actions.onCommentChange).toHaveBeenCalledWith("S01", "请补充客户现状依据。");
  fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
  await waitFor(() => expect(actions.onSavePageDecision).toHaveBeenCalledWith("S01"));

  const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
  expect(submit).toBeDisabled();
  const complete = {
    ...initial,
    progress: { completed: 2, total: 2, remaining: 0, unsaved: 0 },
  } satisfies ContentReviewPageViewModel;
  rerender(
    <ContentReviewViewModelSurface
      viewModel={complete}
      bridge={host}
      projectRoot="/managed/project"
      {...actions}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
  expect(actions.onSubmitReviewBatch).toHaveBeenCalledTimes(1);
  expect(hostCall).not.toHaveBeenCalled();
});

it("reads only the ViewModel asset after viewport activation and renders its alt text", async () => {
  const intersections = installIntersectionObserver();
  const callTool = vi.fn(async () => ({
    asset: {
      assetRef: "review-assets/content/S01-M01.png",
      mimeType: "image/png",
      dataBase64: "iVBORw0KGgo=",
    },
  }));
  render(
    <ContentReviewViewModelSurface
      viewModel={pageViewModel()}
      bridge={bridge(callTool)}
      projectRoot="/managed/project"
      {...actionProps()}
    />,
  );
  expect(callTool).not.toHaveBeenCalled();
  act(() => intersections.intersectAll());
  await waitFor(() => expect(callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
    projectRoot: "/managed/project",
    assetRef: "review-assets/content/S01-M01.png",
  }));
  expect(await screen.findByRole("img", {
    name: "第 1 页《当前流程断点与证据边界》页面画面 1",
  })).toBeInTheDocument();
  expect(screen.getByLabelText("S01 文字与图片材料一起审核")).not.toHaveTextContent("客户材料");
  expect(screen.getByLabelText("S01 文字与图片材料一起审核")).not.toHaveTextContent("第 3 页");
  expect(callTool).toHaveBeenCalledTimes(1);
  expect(screen.queryByLabelText("S02 文字与图片材料一起审核")).not.toBeInTheDocument();
});

it("keeps PageDecision unchanged when an existing material image fails", async () => {
  const intersections = installIntersectionObserver();
  const initial = pageViewModel();
  const viewModel = {
    ...initial,
    slides: initial.slides.map((slide, index) => index === 0 ? {
      ...slide,
      localDraftState: {
        decision: "modify" as const,
        comment: "保留当前修改判断。",
        dirty: true,
      },
    } : slide),
  } satisfies ContentReviewPageViewModel;
  const callTool = vi.fn(async () => {
    throw new Error("material image unavailable");
  });
  render(
    <ContentReviewViewModelSurface
      viewModel={viewModel}
      bridge={bridge(callTool)}
      projectRoot="/managed/project"
      {...actionProps()}
    />,
  );

  act(() => intersections.intersectAll());

  const firstPage = screen.getByLabelText("S01 内容审核");
  expect(await within(firstPage).findByRole("button", {
    name: /预览暂不可读，点击重试/,
  })).toBeInTheDocument();
  expect(within(firstPage).getByRole("radio", { name: "需要修改" })).toBeChecked();
  expect(within(firstPage).getByRole("radio", { name: "证据不足" })).not.toBeChecked();
});
