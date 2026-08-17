import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContentFullDeckReviewPage } from "./ContentFullDeckReviewPage";
import type {
  ContentDecisionChoice,
  ContentPageDecision,
  ContentReviewProjection,
  ContentReviewSurfaceData,
} from "../types/content-review";
import type { HostBridge } from "../types/host";
import {
  createReviewDraftContext,
  createReviewDraftEnvelope,
  reviewDraftStorageKey,
  type ContentReviewDraftUi,
} from "../review-draft/reviewDraftStore";

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

function installIntersectionObserver() {
  const observers: Array<{
    callback: IntersectionObserverCallback;
    targets: Set<Element>;
  }> = [];
  class ControlledIntersectionObserver {
    readonly root = null;
    readonly rootMargin = "0px";
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
    intersect(container: Element) {
      for (const observer of observers) {
        for (const target of observer.targets) {
          if (target === container || container.contains(target)) {
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
      }
    },
  };
}

function projection(count = 2): ContentReviewProjection {
  return {
    project_id: "p1",
    review_type: "content-full-deck",
    review_session_id: "content-session-1",
    review_session: {
      review_session_id: "content-session-1",
      status: "ready",
      persistence_status: "saved",
    },
    source_version: "content-v1",
    revision: 7,
    authoritative_revision: 8,
    reading_blueprint_ref: "artifact://reading-deck-blueprint/" + "a".repeat(64),
    material_mode: "mixed-evidence",
    section_flow: ["客户业务事项", "验证方案"],
    slides: Array.from({ length: count }, (_, index) => ({
      slide_id: `S${String(index + 1).padStart(2, "0")}`,
      order: index + 1,
      section_id: index ? "solution" : "problem",
      page_task: `完整页面任务 ${index + 1}`,
      reading_question: `阅读问题 ${index + 1}`,
      neutral_title: `当前业务事项 ${index + 1}`,
      visible_copy_blocks: [{
        block_id: `copy-${index + 1}`,
        text: `完整可见正文 ${index + 1}，不使用摘要或省略号。`,
        identity: "来源事实",
      }],
      identity_labels: ["来源事实", "方案建议"],
      evidence_bindings: [{
        content_ref: `copy-${index + 1}`,
        source_refs: [`artifact://material-finding/${"b".repeat(64)}`],
        location: `材料第 ${index + 1} 页`,
        purpose: "证明当前事实边界",
      }],
      material_views: [{
        material_view_id: `material-view-${index + 1}`,
        source_ref: `artifact://source-material/${"f".repeat(64)}`,
        asset_ref: `review-assets/content/S${String(index + 1).padStart(2, "0")}-M01.png`,
        source_file_name: `客户材料-${index + 1}.pdf`,
        page_number: index + 3,
        region_label: `第 ${index + 1} 页关键区域`,
        purpose: `用于核对正文 ${index + 1}`,
        treatment: "原页截图与原文对照",
        evidence_identity: "来源事实",
      }, ...(index === 0 ? [{
        material_view_id: "material-view-1-secondary",
        source_ref: `artifact://source-material/${"9".repeat(64)}`,
        asset_ref: "review-assets/content/S01-M02.png",
        source_file_name: "客户附件-1.png",
        page_number: 9,
        region_label: "补充证据图",
        purpose: "用于核对补充证据",
        treatment: "保留原图比例",
        evidence_identity: "材料推断",
      }] : [])],
      analysis_or_proposal_blocks: [{
        block_id: `analysis-${index + 1}`,
        text: `方案建议 ${index + 1}`,
        identity: "方案建议",
      }],
      solution_mapping_refs: [`mapping-${index + 1}`],
      previous_relation: index ? "承接上一页" : "开篇",
      next_relation: index === count - 1 ? "进入下一步" : "继续诊断",
      speaker_notes: `完整演讲备注 ${index + 1}`,
      reading_quality: {
        independently_readable: true,
        information_density: "moderate",
        review_note: "事实与建议分开",
      },
      material_mode: "mixed-evidence",
    })),
    decisions: [],
    progress: { completed: 0, total: count, remaining: count, unsaved: 0 },
    batch: null,
    revision_plan: null,
    content_acceptance_ref: "artifact://content-acceptance/" + "c".repeat(64),
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

function validPageDecision(
  slideId: string,
  decision: ContentDecisionChoice = "approved",
  comment = "",
  overrides: Partial<ContentPageDecision> = {},
): ContentPageDecision {
  const slideOrder = Number(slideId.slice(1));
  return {
    page_decision_id: `page-decision-${slideId}`,
    project_id: "p1",
    review_session_id: "content-session-1",
    source_version: "content-v1",
    reading_blueprint_ref: "artifact://reading-deck-blueprint/" + "a".repeat(64),
    slide_id: slideId,
    slide_order: slideOrder,
    slide_title_snapshot: `当前业务事项 ${slideOrder}`,
    decision,
    comment: decision === "approved" ? "" : comment,
    status: "completed",
    saved_at: "2026-08-15T09:30:00+08:00",
    supersedes_decision_ref: "",
    ...overrides,
  };
}

function withoutDecisionField(
  decision: ContentPageDecision,
  field: keyof ContentPageDecision,
): Record<string, unknown> {
  const candidate: Record<string, unknown> = { ...decision };
  delete candidate[field];
  return candidate;
}

function reviewBatch(status: "submitted" | "withdrawn", count = 1) {
  return {
    batch_id: `batch-${status}`,
    project_id: "p1",
    review_session_id: "content-session-1",
    source_version: "content-v1",
    reading_blueprint_ref: "artifact://reading-deck-blueprint/" + "a".repeat(64),
    slide_ids: Array.from({ length: count }, (_, index) => `S${String(index + 1).padStart(2, "0")}`),
    decision_refs: Array.from({ length: count }, (_, index) => (
      `artifact://content-page-decision/${String(index + 1).padStart(64, "0")}`
    )),
    counts: { approved: count, modify: 0, evidence: 0, "merge-or-delete": 0 },
    status,
    immutable_after_submit: true,
    submitted_at: "2026-08-15T09:00:00+08:00",
    withdrawn_at: status === "withdrawn" ? "2026-08-15T10:00:00+08:00" : "",
    supersedes_ref: status === "withdrawn"
      ? `artifact://content-review-batch/${"e".repeat(64)}`
      : "",
  };
}

function bridge(batchSlideCount = 2) {
  let revision = 8;
  let rejectNextSave = false;
  const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
    if (name === "read_ai_ppt_project_asset") {
      return {
        asset: {
          assetRef: args.assetRef,
          mimeType: "image/png",
          dataBase64: "iVBORw0KGgo=",
        },
      };
    }
    if (name === "save_content_page_decision") {
      if (args.expectedRevision !== revision) {
        throw Object.assign(new Error(`expected revision ${revision}`), { code: "REVISION_CONFLICT" });
      }
      if (rejectNextSave) {
        rejectNextSave = false;
        throw Object.assign(new Error("stale"), { code: "REVISION_CONFLICT" });
      }
      revision += 1;
      return {
        decision_ref: `artifact://content-page-decision/${"d".repeat(64)}`,
        decision: validPageDecision(
          String(args.slideId),
          args.decision as ContentDecisionChoice,
          String(args.comment),
        ),
        snapshot: { revision },
      };
    }
    if (args.expectedRevision !== revision) {
      throw Object.assign(new Error(`expected revision ${revision}`), { code: "REVISION_CONFLICT" });
    }
    revision += 1;
    return {
      batch_ref: `artifact://content-review-batch/${"e".repeat(64)}`,
      batch: reviewBatch("submitted", batchSlideCount),
      snapshot: { revision },
    };
  });
  return {
    callTool,
    failNextSave: () => { rejectNextSave = true; },
    value: {
      connect: vi.fn(), callTool, updateModelContext: vi.fn(), sendFollowUp: vi.fn(),
      confirmMission: vi.fn(), getHostEnvironment: vi.fn(), notifySize: vi.fn(),
    } as unknown as HostBridge,
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

function customPrototypeRecord(value: Record<string, unknown>): Record<string, unknown> {
  return Object.assign(Object.create({ custom: true }), value);
}

function inheritedRequiredRecord(
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
  Object.defineProperty(copy, Symbol("unexpected"), {
    enumerable: true,
    value: true,
  });
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

type StrictResultAttack = (valid: Record<string, unknown>) => {
  result: unknown;
  getterReads: () => number;
};

const noGetterReads = () => 0;

const pageResultAttacks: Array<[string, StrictResultAttack]> = [
  ["custom-prototype decision", (valid) => ({
    result: {
      ...valid,
      decision: customPrototypeRecord({ ...(valid.decision as ContentPageDecision) }),
    },
    getterReads: noGetterReads,
  })],
  ["inherited required decision field", (valid) => ({
    result: {
      ...valid,
      decision: inheritedRequiredRecord(
        { ...(valid.decision as ContentPageDecision) },
        "saved_at",
      ),
    },
    getterReads: noGetterReads,
  })],
  ["accessor-backed decision", (valid) => {
    const attacked = accessorRecord({ ...(valid.decision as ContentPageDecision) }, "saved_at");
    return { result: { ...valid, decision: attacked.value }, getterReads: attacked.getterReads };
  }],
  ["symbol-keyed decision extra", (valid) => ({
    result: {
      ...valid,
      decision: symbolExtraRecord({ ...(valid.decision as ContentPageDecision) }),
    },
    getterReads: noGetterReads,
  })],
  ["calendar-impossible saved_at", (valid) => ({
    result: {
      ...valid,
      decision: { ...(valid.decision as ContentPageDecision), saved_at: "2026-02-30T00:00:00Z" },
    },
    getterReads: noGetterReads,
  })],
  ["host-envelope extra", (valid) => ({
    result: { ...valid, unexpected: true },
    getterReads: noGetterReads,
  })],
  ["host-envelope accessor", (valid) => {
    const attacked = accessorRecord(valid, "decision");
    return { result: attacked.value, getterReads: attacked.getterReads };
  }],
  ["snapshot extra", (valid) => ({
    result: { ...valid, snapshot: { ...(valid.snapshot as object), unexpected: true } },
    getterReads: noGetterReads,
  })],
  ["snapshot accessor", (valid) => {
    const attacked = accessorRecord({ ...(valid.snapshot as object) }, "revision");
    return { result: { ...valid, snapshot: attacked.value }, getterReads: attacked.getterReads };
  }],
];

const batchResultAttacks: Array<[string, StrictResultAttack]> = [
  ["sparse decision_refs", (valid) => ({
    result: {
      ...valid,
      batch: { ...(valid.batch as object), decision_refs: new Array(1) },
    },
    getterReads: noGetterReads,
  })],
  ["sparse slide_ids", (valid) => {
    const slideIds = ["S01"];
    delete slideIds[0];
    return {
      result: { ...valid, batch: { ...(valid.batch as object), slide_ids: slideIds } },
      getterReads: noGetterReads,
    };
  }],
  ["accessor-backed decision_refs", (valid) => {
    const attacked = accessorArray(`artifact://content-page-decision/${"1".repeat(64)}`);
    return {
      result: { ...valid, batch: { ...(valid.batch as object), decision_refs: attacked.value } },
      getterReads: attacked.getterReads,
    };
  }],
  ["custom-prototype batch", (valid) => ({
    result: {
      ...valid,
      batch: customPrototypeRecord({ ...(valid.batch as object) }),
    },
    getterReads: noGetterReads,
  })],
  ["inherited required batch field", (valid) => ({
    result: {
      ...valid,
      batch: inheritedRequiredRecord({ ...(valid.batch as object) }, "submitted_at"),
    },
    getterReads: noGetterReads,
  })],
  ["accessor-backed batch", (valid) => {
    const attacked = accessorRecord({ ...(valid.batch as object) }, "submitted_at");
    return { result: { ...valid, batch: attacked.value }, getterReads: attacked.getterReads };
  }],
  ["symbol-keyed batch extra", (valid) => ({
    result: {
      ...valid,
      batch: symbolExtraRecord({ ...(valid.batch as object) }),
    },
    getterReads: noGetterReads,
  })],
  ["calendar-impossible submitted_at", (valid) => ({
    result: {
      ...valid,
      batch: { ...(valid.batch as object), submitted_at: "2026-02-30T00:00:00Z" },
    },
    getterReads: noGetterReads,
  })],
  ["custom-prototype counts", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    return {
      result: {
        ...valid,
        batch: {
          ...batch,
          counts: customPrototypeRecord({ ...(batch.counts as object) }),
        },
      },
      getterReads: noGetterReads,
    };
  }],
  ["inherited required counts field", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    return {
      result: {
        ...valid,
        batch: {
          ...batch,
          counts: inheritedRequiredRecord({ ...(batch.counts as object) }, "approved"),
        },
      },
      getterReads: noGetterReads,
    };
  }],
  ["accessor-backed counts", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    const attacked = accessorRecord({ ...(batch.counts as object) }, "approved");
    return {
      result: { ...valid, batch: { ...batch, counts: attacked.value } },
      getterReads: attacked.getterReads,
    };
  }],
  ["symbol-keyed counts extra", (valid) => {
    const batch = valid.batch as Record<string, unknown>;
    return {
      result: {
        ...valid,
        batch: {
          ...batch,
          counts: symbolExtraRecord({ ...(batch.counts as object) }),
        },
      },
      getterReads: noGetterReads,
    };
  }],
  ["host-envelope extra", (valid) => ({
    result: { ...valid, unexpected: true },
    getterReads: noGetterReads,
  })],
  ["host-envelope accessor", (valid) => {
    const attacked = accessorRecord(valid, "batch");
    return { result: attacked.value, getterReads: attacked.getterReads };
  }],
];

function seedContentDraft(data: ContentReviewSurfaceData, ui: ContentReviewDraftUi) {
  const context = createReviewDraftContext(data);
  const key = reviewDraftStorageKey(context);
  window.sessionStorage.setItem(key, JSON.stringify(
    createReviewDraftEnvelope(context, ui, "2026-08-15T00:00:00Z"),
  ));
  return key;
}

function readContentDraft(key: string) {
  return JSON.parse(window.sessionStorage.getItem(key) || "null") as {
    source_revision: number;
    ui: ContentReviewDraftUi;
  } | null;
}

function installMemorySessionStorage() {
  const values = new Map<string, string>();
  const storage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
    removeItem: vi.fn((key: string) => { values.delete(key); }),
    clear: vi.fn(() => values.clear()),
    key: vi.fn((index: number) => Array.from(values.keys())[index] ?? null),
    get length() { return values.size; },
  } as unknown as Storage;
  vi.spyOn(window, "sessionStorage", "get").mockReturnValue(storage);
  return storage;
}

function domRect(top: number, bottom = top + 100): DOMRect {
  return {
    top, bottom, left: 0, right: 100, width: 100, height: bottom - top,
    x: 0, y: top, toJSON: () => ({}),
  } as DOMRect;
}

function mockHeaderPosition(position: "sticky" | "static") {
  const getComputedStyle = window.getComputedStyle.bind(window);
  return vi.spyOn(window, "getComputedStyle").mockImplementation((element, pseudoElt) => {
    const style = getComputedStyle(element, pseudoElt);
    if (!(element instanceof HTMLElement) || !element.classList.contains("content-review-header")) {
      return style;
    }
    return new Proxy(style, {
      get(target, property) {
        if (property === "position") return position;
        const value = Reflect.get(target, property, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    });
  });
}

describe("ContentFullDeckReviewPage", () => {
  it("keeps a validated submitted batch locked", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.batch = reviewBatch("submitted");
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();
  });

  it("recovers a validated withdrawn batch for editing and re-submission", async () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.batch = reviewBatch("withdrawn");
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByText("上一批次已撤回")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "需要修改" })).toBeEnabled();
    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    expect(await screen.findByText("已提交，等待整套修改方案")).toBeInTheDocument();
    expect(host.callTool).toHaveBeenCalledWith("submit_content_review_batch", expect.objectContaining({
      expectedRevision: 8,
    }));
  });

  it("keeps an absent authoritative batch editable without showing projection corruption", () => {
    const host = bridge(1);
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    expect(screen.queryByText(/权威审核投影无效/)).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();
  });

  it("atomically adopts a newer same-identity decision and submitted batch without allowing an older projection to roll it back", async () => {
    const data = surface(1);
    const host = bridge(1);
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host.value} />,
    );

    const grown = surface(1);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    grown.review.decisions = [validPageDecision("S01")];
    grown.review.batch = reviewBatch("submitted");
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host.value} />);

    await waitFor(() => expect(screen.getByText(/revision 9$/)).toBeInTheDocument());
    expect(screen.getByText("1/1")).toBeInTheDocument();
    expect(screen.getByText("认可本页 1")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();

    rerender(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);
    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    expect(screen.getByText("1/1")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(host.callTool).not.toHaveBeenCalledWith("save_content_page_decision", expect.anything());
  });

  it("preserves a dirty local choice and comment while adopting its newer saved authority", async () => {
    const data = surface(1);
    const host = bridge(1);
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host.value} />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    fireEvent.change(screen.getByLabelText("S01 审核意见"), {
      target: { value: "保留当前未保存意见" },
    });

    const grown = surface(1);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    grown.review.decisions = [validPageDecision("S01", "evidence", "最新权威意见")];
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host.value} />);

    await waitFor(() => expect(screen.getByText(/revision 9$/)).toBeInTheDocument());
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByText("证据不足 1")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "需要修改" })).toBeChecked();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("保留当前未保存意见");
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
  });

  it.each([
    ["withdrawn", reviewBatch("withdrawn"), true],
    ["absent", null, false],
  ] as const)("adopts a newer %s batch and does not restore an older submitted lock", async (
    _label,
    latestBatch,
    showsWithdrawn,
  ) => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.batch = reviewBatch("submitted");
    const host = bridge(1);
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host.value} />,
    );

    const grown = surface(1);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    grown.review.decisions = [validPageDecision("S01")];
    grown.review.batch = latestBatch;
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host.value} />);

    await waitFor(() => expect(screen.getByText(/revision 9$/)).toBeInTheDocument());
    if (showsWithdrawn) {
      expect(screen.getByText("上一批次已撤回")).toBeInTheDocument();
    } else {
      expect(screen.queryByText("上一批次已撤回")).not.toBeInTheDocument();
    }
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeEnabled();

    rerender(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);
    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    if (showsWithdrawn) {
      expect(screen.getByText("上一批次已撤回")).toBeInTheDocument();
    } else {
      expect(screen.queryByText("上一批次已撤回")).not.toBeInTheDocument();
    }
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeEnabled();
  });

  it("fails closed when a non-null authoritative batch belongs to another project", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.batch = { ...reviewBatch("submitted"), project_id: "foreign-project" };
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByText(/权威审核投影无效，请刷新\/重新打开/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前业务事项 1" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();
    expect(host.callTool).not.toHaveBeenCalled();
  });

  it("fails closed for an authoritative withdrawn batch with a calendar-impossible withdrawn_at", () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    data.review.batch = {
      ...reviewBatch("withdrawn"),
      withdrawn_at: "2026-02-30T00:00:00Z",
    };
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByText(/权威审核投影无效，请刷新\/重新打开/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前业务事项 1" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();
    expect(host.callTool).not.toHaveBeenCalled();
  });

  it.each([
    ["foreign identity", [{ ...validPageDecision("S01"), review_session_id: "foreign-session" }]],
    ["duplicate slide identity", [validPageDecision("S01"), {
      ...validPageDecision("S01"),
      page_decision_id: "page-decision-S01-duplicate",
    }]],
    ["unknown slide identity", [{
      ...validPageDecision("S01"),
      slide_id: "S99",
      slide_order: 99,
      slide_title_snapshot: "外部页面",
    }]],
    ["missing closed field", [withoutDecisionField(validPageDecision("S01"), "saved_at")]],
    ["missing slide identity", [withoutDecisionField(validPageDecision("S01"), "slide_id")]],
  ])("fails closed for an invalid initial PageDecision: %s", (_label, decisions) => {
    const data = surface(1);
    data.review.decisions = decisions as unknown as ContentPageDecision[];
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByText(/权威审核投影无效，请刷新\/重新打开/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前业务事项 1" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();
    expect(host.callTool).not.toHaveBeenCalled();
  });

  it("renders the entire neutral-title deck without old product chrome", () => {
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={surface()} bridge={host.value} />);
    expect(screen.getByRole("heading", { name: "当前业务事项 1" })).toBeInTheDocument();
    expect(screen.getByText("完整可见正文 2，不使用摘要或省略号。")).toBeInTheDocument();
    expect(screen.getByText("完整演讲备注 2")).toBeInTheDocument();
    expect(screen.getByText("继续诊断")).toBeInTheDocument();
    expect(screen.queryByText("五个空间")).not.toBeInTheDocument();
    expect(screen.queryByText("项目仪表盘")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /确认 G0/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/desired customer judgment/i)).not.toBeInTheDocument();
  });

  it("renders complete copy and the controlled project material image in the same reading grid", async () => {
    const intersections = installIntersectionObserver();
    const host = bridge();
    const { container } = render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    intersections.intersect(screen.getByText("客户材料-1.pdf").closest("figure") as HTMLElement);
    intersections.intersect(screen.getByText("客户附件-1.png").closest("figure") as HTMLElement);

    const image = await screen.findByRole("img", { name: "S01 材料画面 1" });
    const secondImage = await screen.findByRole("img", { name: "S01 材料画面 2" });
    const readingGrid = image.closest(".content-slide-reading-grid");
    expect(readingGrid).not.toBeNull();
    expect(secondImage.closest(".content-slide-reading-grid")).toBe(readingGrid);
    expect(within(readingGrid as HTMLElement).getByText("完整可见正文 1，不使用摘要或省略号。")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("完整演讲备注 1")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("客户材料-1.pdf")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("第 3 页 · 第 1 页关键区域")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("用于核对正文 1")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("原页截图与原文对照")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("客户附件-1.png")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("第 9 页 · 补充证据图")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("用于核对补充证据")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("保留原图比例")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getByText("材料推断")).toBeInTheDocument();
    expect(within(readingGrid as HTMLElement).getAllByText("来源事实").length).toBeGreaterThanOrEqual(2);
    expect(host.callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S01-M01.png",
    });
    expect(host.callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S01-M02.png",
    });
    expect(container.querySelector("[src^='file:'], [src^='asset:']")).toBeNull();
  });

  it("defers a 60-page material deck until a page approaches the viewport", async () => {
    const intersections = installIntersectionObserver();
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={surface(60)} bridge={host.value} />);

    expect(host.callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset").length).toBeLessThan(10);
    const page30Card = screen.getByText("客户材料-30.pdf").closest("figure");
    expect(page30Card).not.toBeNull();
    intersections.intersect(page30Card as HTMLElement);

    expect(await screen.findByRole("img", { name: "S30 材料画面 1" })).toBeInTheDocument();
    expect(host.callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset")).toHaveLength(1);
    expect(host.callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S30-M01.png",
    });
  });

  it("ignores accidental material views on a proposal-led page", () => {
    installIntersectionObserver();
    const data = surface(1);
    data.review.slides[0].material_mode = "proposal-led";
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByText("本页为 proposal-led 内容，没有可展示的项目材料画面。")).toBeInTheDocument();
    expect(screen.queryByText("客户材料-1.pdf")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /读取本条材料/ })).not.toBeInTheDocument();
    expect(host.callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset")).toHaveLength(0);
  });

  it("manually activates only the selected material when IntersectionObserver is unavailable", async () => {
    const host = bridge(1);
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    expect(screen.getAllByText("当前环境不支持视口检测；项目材料未自动读取")).toHaveLength(2);
    expect(host.callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset")).toHaveLength(0);
    const activate = screen.getAllByRole("button", { name: /读取本条材料/ });
    expect(activate).toHaveLength(2);
    fireEvent.click(activate[0]);

    expect(await screen.findByRole("img", { name: "S01 材料画面 1" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "S01 材料画面 2" })).not.toBeInTheDocument();
    expect(host.callTool.mock.calls.filter(([name]) => name === "read_ai_ppt_project_asset")).toHaveLength(1);
    expect(host.callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S01-M01.png",
    });
  });

  it("shows the selected material's honest read failure without activating its siblings", async () => {
    const data = surface(1);
    const callTool = vi.fn(async (name: string) => {
      if (name === "read_ai_ppt_project_asset") throw new Error("asset unavailable");
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getAllByRole("button", { name: /读取本条材料/ })[1]);

    expect(await screen.findByRole("button", { name: /预览暂不可读，点击重试/ })).toBeInTheDocument();
    expect(callTool).toHaveBeenCalledTimes(1);
    expect(callTool).toHaveBeenCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S01-M02.png",
    });
    expect(screen.getByRole("button", { name: /读取本条材料：S01 材料画面 1/ })).toBeInTheDocument();
  });

  it("deduplicates duplicate project material reads after viewport activation", async () => {
    const intersections = installIntersectionObserver();
    const data = surface(1);
    const duplicateAssetRef = data.review.slides[0].material_views[0].asset_ref;
    data.review.slides[0] = {
      ...data.review.slides[0],
      material_views: data.review.slides[0].material_views.map((material) => ({
        ...material,
        asset_ref: duplicateAssetRef,
      })),
    };
    const readRequest = deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>();
    const callTool = vi.fn((name: string) => {
      if (name === "read_ai_ppt_project_asset") return readRequest.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    for (const sourceName of ["客户材料-1.pdf", "客户附件-1.png"]) {
      intersections.intersect(screen.getByText(sourceName).closest("figure") as HTMLElement);
    }
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(1));
    await act(async () => {
      readRequest.resolve({ asset: { assetRef: "review-assets/content/S01-M01.png", mimeType: "image/png", dataBase64: "iVBORw0KGgo=" } });
      await readRequest.promise;
    });
    expect(await screen.findByRole("img", { name: "S01 材料画面 1" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "S01 材料画面 2" })).toBeInTheDocument();
  });

  it("exposes four semantic radio decisions with a distinct selected state", () => {
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    const labels = ["认可本页", "需要修改", "证据不足", "考虑删页/合页"];
    for (const label of labels) {
      const radio = screen.getByRole("radio", { name: label });
      expect(radio).toHaveAttribute("type", "radio");
      expect(radio.closest("label")).toHaveClass("page-decision-option");
    }

    const modify = screen.getByRole("radio", { name: "需要修改" });
    fireEvent.click(modify);
    expect(modify).toBeChecked();
    expect(modify.closest("label")).toHaveClass("is-selected", "page-decision-option--modify");
  });

  it("collapses a saved non-approved comment and restores its full draft for editing", async () => {
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    const comment = screen.getByLabelText("S01 审核意见");
    fireEvent.change(comment, { target: { value: "第一行意见\n第二行仍需完整保留" } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText((_, element) => (
      element?.tagName === "P" && element.textContent === "第一行意见\n第二行仍需完整保留"
    ))).toBeInTheDocument();
    expect(screen.queryByLabelText("S01 审核意见")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "编辑意见" }));
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("第一行意见\n第二行仍需完整保留");
  });

  it("locates the first page without a saved decision and does not count a dirty choice", async () => {
    const host = bridge();
    mockHeaderPosition("static");
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      if (this.id === "content-S01") return domRect(100, 700);
      if (this.id === "content-S02") return domRect(200, 800);
      return domRect(0);
    });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    vi.spyOn(window, "scrollX", "get").mockReturnValue(0);
    vi.spyOn(window, "scrollY", "get").mockReturnValue(0);
    render(<ContentFullDeckReviewPage initialData={surface(2)} bridge={host.value} />);

    fireEvent.click(screen.getAllByRole("radio", { name: "认可本页" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "定位下一页未判断" }));
    expect(scrollTo).toHaveBeenNthCalledWith(1, { behavior: "smooth", left: 0, top: 100 });

    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
    await screen.findByText("1/2");
    fireEvent.click(screen.getByRole("button", { name: "定位下一页未判断" }));
    expect(scrollTo).toHaveBeenNthCalledWith(2, { behavior: "smooth", left: 0, top: 200 });

    fireEvent.click(screen.getAllByRole("radio", { name: "认可本页" })[1]);
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[1]);
    expect(await screen.findByRole("button", { name: "全部页面已完成判断" })).toBeDisabled();
  });

  it("locks a page draft while its atomic save is pending", async () => {
    const saveRequest = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const callTool = vi.fn((name: string, args: Record<string, unknown>) => {
      if (name === "read_ai_ppt_project_asset") {
        return Promise.resolve({ asset: { assetRef: args.assetRef, mimeType: "image/png", dataBase64: "iVBORw0KGgo=" } });
      }
      if (name === "save_content_page_decision") return saveRequest.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    const comment = screen.getByLabelText("S01 审核意见");
    fireEvent.change(comment, { target: { value: "保存请求中不能被新输入覆盖" } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    await waitFor(() => expect(screen.getByText("正在保存…")).toBeInTheDocument());
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
    expect(comment).toBeDisabled();

    await act(async () => {
      saveRequest.resolve({
        decision_ref: `artifact://content-page-decision/${"7".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "保存请求中不能被新输入覆盖"),
        snapshot: { revision: 9 },
      });
      await saveRequest.promise;
    });
    expect(await screen.findByRole("button", { name: "编辑意见" })).toBeEnabled();
  });

  it("serializes page saves while keeping other page drafts editable", async () => {
    const firstSave = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const saveCalls: Array<Record<string, unknown>> = [];
    const callTool = vi.fn((name: string, args: Record<string, unknown>) => {
      if (name === "read_ai_ppt_project_asset") {
        return Promise.resolve({ asset: { assetRef: args.assetRef, mimeType: "image/png", dataBase64: "iVBORw0KGgo=" } });
      }
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      saveCalls.push(args);
      if (saveCalls.length === 1) return firstSave.promise;
      if (args.expectedRevision !== 9) throw Object.assign(new Error("revision conflict"), { code: "REVISION_CONFLICT" });
      return Promise.resolve({
        decision_ref: `artifact://content-page-decision/${"6".repeat(64)}`,
        decision: validPageDecision("S02", "modify", "第二页仍可编辑"),
        snapshot: { revision: 10 },
      });
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(2)} bridge={host} />);

    fireEvent.click(screen.getAllByRole("radio", { name: "认可本页" })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
    await screen.findByText("正在保存…");

    const secondModify = screen.getAllByRole("radio", { name: "需要修改" })[1];
    expect(secondModify).toBeEnabled();
    fireEvent.click(secondModify);
    const secondComment = screen.getByLabelText("S02 审核意见");
    expect(secondComment).toBeEnabled();
    fireEvent.change(secondComment, { target: { value: "第二页仍可编辑" } });
    expect(screen.getAllByRole("button", { name: "保存本页判断" })[1]).toBeDisabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();

    await act(async () => {
      firstSave.resolve({
        decision_ref: `artifact://content-page-decision/${"5".repeat(64)}`,
        decision: validPageDecision("S01"),
        snapshot: { revision: 9 },
      });
      await firstSave.promise;
    });

    const secondSave = screen.getAllByRole("button", { name: "保存本页判断" })[1];
    expect(secondSave).toBeEnabled();
    fireEvent.click(secondSave);
    await screen.findByText("2/2");
    expect(saveCalls.map((args) => args.expectedRevision)).toEqual([8, 9]);
  });

  it("rejects rapid duplicate page-save activation before React rerenders", async () => {
    const saveRequest = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const callTool = vi.fn((name: string) => {
      if (name === "read_ai_ppt_project_asset") {
        return Promise.resolve({ asset: { assetRef: "asset", mimeType: "image/png", dataBase64: "iVBORw0KGgo=" } });
      }
      if (name === "save_content_page_decision") return saveRequest.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    const save = screen.getByRole("button", { name: "保存本页判断" });
    act(() => {
      save.click();
      save.click();
    });

    expect(callTool.mock.calls.filter(([name]) => name === "save_content_page_decision")).toHaveLength(1);
    await act(async () => {
      saveRequest.resolve({
        decision_ref: `artifact://content-page-decision/${"4".repeat(64)}`,
        decision: validPageDecision("S01"),
        snapshot: { revision: 9 },
      });
      await saveRequest.promise;
    });
  });

  it("uses the saved revision for the immediately eligible batch submission", async () => {
    const expectedRevisions: unknown[] = [];
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      expectedRevisions.push(args.expectedRevision);
      if (name === "save_content_page_decision") {
        if (args.expectedRevision !== 8) throw Object.assign(new Error("revision conflict"), { code: "REVISION_CONFLICT" });
        return {
          decision_ref: `artifact://content-page-decision/${"0".repeat(64)}`,
          decision: validPageDecision("S01"),
          snapshot: { revision: 9 },
        };
      }
      if (name === "submit_content_review_batch") {
        if (args.expectedRevision !== 9) throw Object.assign(new Error("revision conflict"), { code: "REVISION_CONFLICT" });
        return {
          batch_ref: `artifact://content-review-batch/${"9".repeat(64)}`,
          batch: reviewBatch("submitted"),
          snapshot: { revision: 10 },
        };
      }
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);

    expect(await screen.findByText("已提交，等待整套修改方案")).toBeInTheDocument();
    expect(expectedRevisions).toEqual([8, 9]);
  });

  it.each([
    ["non-increasing revision", { snapshot: { revision: 8 } }],
    ["non-integer revision", { snapshot: { revision: 9.5 } }],
    ["wrong slide", { decision: { slide_id: "S99", decision: "approved", comment: "", status: "completed" } }],
    ["unknown decision", { decision: { slide_id: "S01", decision: "other", comment: "", status: "completed" } }],
    ["incomplete status", { decision: { slide_id: "S01", decision: "approved", comment: "", status: "pending" } }],
    ["non-string comment", { decision: { slide_id: "S01", decision: "approved", comment: 7, status: "completed" } }],
    ["approved comment", { decision: { slide_id: "S01", decision: "approved", comment: "must be empty", status: "completed" } }],
    ["empty non-approved comment", { decision: { slide_id: "S01", decision: "modify", comment: "   ", status: "completed" } }],
  ])("rejects an invalid page-decision runtime result: %s", async (_label, override) => {
    const baseResult = {
      decision_ref: `artifact://content-page-decision/${"3".repeat(64)}`,
      decision: validPageDecision("S01"),
      snapshot: { revision: 9 },
    };
    const result = { ...baseResult, ...override };
    const callTool = vi.fn(async (name: string) => {
      if (name === "save_content_page_decision") return result;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeChecked();
  });

  it.each([
    ["foreign project", { ...validPageDecision("S01"), project_id: "foreign-project" }],
    ["foreign review session", { ...validPageDecision("S01"), review_session_id: "foreign-session" }],
    ["foreign source version", { ...validPageDecision("S01"), source_version: "content-v0" }],
    ["foreign blueprint", {
      ...validPageDecision("S01"),
      reading_blueprint_ref: `artifact://reading-deck-blueprint/${"b".repeat(64)}`,
    }],
    ["foreign slide order", { ...validPageDecision("S01"), slide_order: 2 }],
    ["foreign slide title", { ...validPageDecision("S01"), slide_title_snapshot: "外部标题" }],
    ["extra field", { ...validPageDecision("S01"), unexpected_field: "must fail closed" }],
    ["missing field", withoutDecisionField(validPageDecision("S01"), "saved_at")],
    ["empty page decision id", { ...validPageDecision("S01"), page_decision_id: "   " }],
    ["timezone-free saved timestamp", { ...validPageDecision("S01"), saved_at: "2026-08-15T09:30:00" }],
    ["wrong-kind supersedes reference", {
      ...validPageDecision("S01"),
      supersedes_decision_ref: `artifact://content-review-batch/${"f".repeat(64)}`,
    }],
    ["comment beyond 1200 code points", validPageDecision("S01", "modify", "界".repeat(1201))],
  ])("rejects a closed-shape but stale PageDecision response: %s", async (_label, returnedDecision) => {
    const callTool = vi.fn(async (name: string) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      return {
        decision_ref: `artifact://content-page-decision/${"b".repeat(64)}`,
        decision: returnedDecision,
        snapshot: { revision: 9 },
      };
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeChecked();
  });

  it.each([
    ["decision", "approved", "", validPageDecision("S01", "modify", "Runtime changed the choice")],
    ["comment", "modify", "用户原始意见", validPageDecision("S01", "modify", "Runtime 篡改后的意见")],
  ] as const)("rejects a response whose %s does not equal the save command", async (
    _label,
    commandDecision,
    commandComment,
    returnedDecision,
  ) => {
    const callTool = vi.fn(async (name: string) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      return {
        decision_ref: `artifact://content-page-decision/${"c".repeat(64)}`,
        decision: returnedDecision,
        snapshot: { revision: 9 },
      };
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", {
      name: commandDecision === "approved" ? "认可本页" : "需要修改",
    }));
    if (commandDecision === "modify") {
      fireEvent.change(screen.getByLabelText("S01 审核意见"), { target: { value: commandComment } });
    }
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
  });

  it.each([
    ["missing", undefined],
    ["malformed", "content-page-decision:not-an-artifact-reference"],
    ["wrong kind", `artifact://content-review-batch/${"a".repeat(64)}`],
    ["non-64 lowercase hex", `artifact://content-page-decision/${"A".repeat(63)}`],
  ])("rejects a %s decision_ref without advancing or clearing the draft", async (_label, decisionRef) => {
    const result: Record<string, unknown> = {
      decision: validPageDecision("S01"),
      snapshot: { revision: 9 },
    };
    if (decisionRef !== undefined) result.decision_ref = decisionRef;
    const callTool = vi.fn(async (name: string) => {
      if (name === "save_content_page_decision") return result;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeChecked();
  });

  it("retries after an invalid decision result with the unchanged authoritative revision", async () => {
    const expectedRevisions: unknown[] = [];
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      expectedRevisions.push(args.expectedRevision);
      return {
        decision_ref: `artifact://content-page-decision/${"2".repeat(64)}`,
        decision: validPageDecision("S01"),
        snapshot: { revision: expectedRevisions.length === 1 ? 8 : 9 },
      };
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText(/Runtime 返回无效结果/);
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("1/1");
    expect(expectedRevisions).toEqual([8, 8]);
  });

  it.each([
    ["candidate beyond Number.MAX_SAFE_INTEGER", Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER + 1],
    ["non-safe current revision", 8.5, 9],
  ])("rejects a next revision with an unsafe integer boundary: %s", async (
    _label,
    currentRevision,
    returnedRevision,
  ) => {
    const data = surface(1);
    data.snapshotRevision = currentRevision;
    data.review.authoritative_revision = currentRevision;
    const callTool = vi.fn(async (name: string) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      return {
        decision_ref: `artifact://content-page-decision/${"8".repeat(64)}`,
        decision: validPageDecision("S01"),
        snapshot: { revision: returnedRevision },
      };
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`revision ${String(currentRevision)}$`))).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
  });

  it("accepts the first positive revision after a nonnegative revision zero", async () => {
    const data = surface(1);
    data.snapshotRevision = 0;
    data.review.authoritative_revision = 0;
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      expect(args.expectedRevision).toBe(0);
      return {
        decision_ref: `artifact://content-page-decision/${"9".repeat(64)}`,
        decision: validPageDecision("S01"),
        snapshot: { revision: 1 },
      };
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText("1/1")).toBeInTheDocument();
    expect(screen.getByText(/revision 1$/)).toBeInTheDocument();
    expect(screen.getByText("已保存")).toBeInTheDocument();
  });

  it.each(pageResultAttacks)("fails closed for a strict page-save result with %s", async (
    _label,
    attack,
  ) => {
    const data = surface(1);
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "approved", comment: "" }],
      logical_scroll: null,
    });
    const rawBefore = window.sessionStorage.getItem(key);
    const attacked = attack({
      decision_ref: `artifact://content-page-decision/${"8".repeat(64)}`,
      decision: validPageDecision("S01"),
      snapshot: { revision: 9 },
    });
    const callTool = vi.fn(async (name: string) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      return attacked.result;
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(attacked.getterReads()).toBe(0);
    expect(window.sessionStorage.getItem(key)).toBe(rawBefore);
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
  });

  it.each([
    ["non-increasing revision", reviewBatch("submitted"), 8],
    ["withdrawn status", reviewBatch("withdrawn"), 9],
    ["wrong review identity", { ...reviewBatch("submitted"), review_session_id: "other-session" }, 9],
  ])("rejects an invalid batch runtime result: %s", async (_label, returnedBatch, returnedRevision) => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    const callTool = vi.fn(async (name: string) => {
      if (name !== "submit_content_review_batch") throw new Error(`Unexpected tool ${name}`);
      return {
        batch_ref: `artifact://content-review-batch/${"1".repeat(64)}`,
        batch: returnedBatch,
        snapshot: { revision: returnedRevision },
      };
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    fireEvent.click(submit);

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(submit).toBeEnabled();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeEnabled();
  });

  it.each(batchResultAttacks)("fails closed for a strict batch result with %s", async (
    _label,
    attack,
  ) => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [],
      logical_scroll: { object_id: "S01", offset: 0 },
    });
    const rawBefore = window.sessionStorage.getItem(key);
    const attacked = attack({
      batch_ref: `artifact://content-review-batch/${"7".repeat(64)}`,
      batch: reviewBatch("submitted"),
      snapshot: { revision: 9 },
    });
    const callTool = vi.fn(async (name: string) => {
      if (name !== "submit_content_review_batch") throw new Error(`Unexpected tool ${name}`);
      return attacked.result;
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));

    expect(await screen.findByText(/Runtime 返回无效结果/)).toBeInTheDocument();
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(attacked.getterReads()).toBe(0);
    expect(window.sessionStorage.getItem(key)).toBe(rawBefore);
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.queryByText("已提交，等待整套修改方案")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeEnabled();
  });

  it("locks every page decision while an eligible batch submission is pending", async () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01", "modify", "已保存意见")];
    const batchRequest = deferred<{
      batch_ref: string;
      batch: Record<string, unknown>;
      snapshot: { revision: number };
    }>();
    const callTool = vi.fn((name: string, args: Record<string, unknown>) => {
      if (name === "read_ai_ppt_project_asset") {
        return Promise.resolve({ asset: { assetRef: args.assetRef, mimeType: "image/png", dataBase64: "iVBORw0KGgo=" } });
      }
      if (name === "submit_content_review_batch") return batchRequest.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;
    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);

    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "正在提交…" })).toBeDisabled());
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
    expect(screen.getByRole("button", { name: "编辑意见" })).toBeDisabled();

    await act(async () => {
      batchRequest.resolve({
        batch_ref: `artifact://content-review-batch/${"8".repeat(64)}`,
        batch: reviewBatch("submitted"),
        snapshot: { revision: 9 },
      });
      await batchRequest.promise;
    });
    expect(await screen.findByText("已提交，等待整套修改方案")).toBeInTheDocument();
  });

  it("keeps a failed comment draft and submits only after every page is saved", async () => {
    const host = bridge();
    host.failNextSave();
    render(<ContentFullDeckReviewPage initialData={surface()} bridge={host.value} />);
    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getAllByRole("radio", { name: "需要修改" })[0]);
    const firstComment = screen.getByLabelText("S01 审核意见");
    fireEvent.change(firstComment, { target: { value: "保留这条未保存意见" } });
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
    await screen.findByText("版本已变化；草稿仍保留，请刷新后重试。", {}, { timeout: 2000 });
    expect(firstComment).toHaveValue("保留这条未保存意见");
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
    await screen.findByRole("button", { name: "编辑意见" });

    fireEvent.click(screen.getAllByRole("radio", { name: "认可本页" })[1]);
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[1]);
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);
    await screen.findByText("已提交，等待整套修改方案");
    expect(screen.getByRole("heading", { name: "当前业务事项 1" })).toBeInTheDocument();
    expect(host.callTool).toHaveBeenLastCalledWith("submit_content_review_batch", {
      projectRoot: "/managed/project",
      expectedRevision: 10,
      reviewSessionId: "content-session-1",
      sourceVersion: "content-v1",
    });
  });

  it("opens evidence as a read-only auxiliary layer", () => {
    const host = bridge();
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);
    fireEvent.click(screen.getByRole("button", { name: "查看 S01 来源证据" }));
    const dialog = screen.getByRole("dialog", { name: "S01 来源证据" });
    expect(dialog).toHaveTextContent("材料第 1 页");
    expect(dialog.querySelector("textarea")).toBeNull();
    expect(withinDialogButton(dialog, "关闭证据")).toBeTruthy();
  });

  it("traps modal focus, closes on Escape, and restores the evidence trigger", async () => {
    const host = bridge(1);
    const { container } = render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);
    const trigger = screen.getByRole("button", { name: "查看 S01 来源证据" });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "S01 来源证据" });
    const close = screen.getByRole("button", { name: "关闭证据" });
    expect(close).toHaveFocus();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(container.querySelector(".content-review-page")).toHaveAttribute("inert");

    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(close).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("limits comments by Unicode code points and names the page-specific decision group", () => {
    const host = bridge(1);
    render(<ContentFullDeckReviewPage initialData={surface(1)} bridge={host.value} />);

    expect(screen.getByRole("group", { name: "本页审核判断 · S01" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    const comment = screen.getByLabelText("S01 审核意见");
    fireEvent.change(comment, { target: { value: "😀".repeat(1201) } });

    expect([...(comment as HTMLTextAreaElement).value]).toHaveLength(1200);
    const counter = screen.getByText("1200/1200");
    expect(counter).toHaveAttribute("id");
    expect(comment).toHaveAttribute("aria-describedby", counter.id);
    expect(comment).not.toHaveAttribute("maxlength");
  });
});

describe("content review draft persistence", () => {
  it.each([
    ["project", (data: ContentReviewSurfaceData) => { data.review.project_id = "p2"; }],
    ["session", (data: ContentReviewSurfaceData) => {
      data.review.review_session_id = "content-session-2";
      data.review.review_session.review_session_id = "content-session-2";
    }],
    ["source version", (data: ContentReviewSurfaceData) => { data.review.source_version = "content-v2"; }],
    ["source revision", (data: ContentReviewSurfaceData) => { data.review.revision = 8; }],
    ["reading blueprint lineage", (data: ContentReviewSurfaceData) => {
      data.review.reading_blueprint_ref = `artifact://reading-deck-blueprint/${"9".repeat(64)}`;
    }],
  ])("does not restore a draft from a different %s", (_label, mutateIdentity) => {
    const current = surface(1);
    const foreign = surface(1);
    mutateIdentity(foreign);
    seedContentDraft(foreign, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "不得跨身份恢复" }],
      logical_scroll: null,
    });

    render(<ContentFullDeckReviewPage initialData={current} bridge={bridge(1).value} />);

    expect(screen.getByRole("radio", { name: "需要修改" })).not.toBeChecked();
    expect(screen.queryByLabelText("S01 审核意见")).not.toBeInTheDocument();
    expect(screen.getByText("尚未判断")).toBeInTheDocument();
  });

  it("restores across authoritative snapshot growth when source revision is unchanged", () => {
    const seeded = surface(1);
    seedContentDraft(seeded, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "evidence", comment: "snapshot 增长不应丢失" }],
      logical_scroll: null,
    });
    const grown = surface(1);
    grown.snapshotRevision = 99;
    grown.review.authoritative_revision = 99;

    render(<ContentFullDeckReviewPage initialData={grown} bridge={bridge(1).value} />);

    expect(screen.getByRole("radio", { name: "证据不足" })).toBeChecked();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("snapshot 增长不应丢失");
  });

  it("restores the current slide from one sticky-header logical origin with one scroll", async () => {
    const data = surface(2);
    seedContentDraft(data, {
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 40 },
    });
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    mockHeaderPosition("sticky");
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains("content-review-header")) return domRect(0, 126);
      if (this.id === "content-S02") return domRect(300, 900);
      return domRect(-500, -100);
    });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    vi.spyOn(window, "scrollX", "get").mockReturnValue(23);
    vi.spyOn(window, "scrollY", "get").mockReturnValue(300);

    render(<ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({
      behavior: "auto",
      left: 23,
      top: 514,
    }));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("restores with origin zero when the responsive header is not sticky", async () => {
    const data = surface(2);
    seedContentDraft(data, {
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 40 },
    });
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    mockHeaderPosition("static");
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains("content-review-header")) return domRect(0, 126);
      if (this.id === "content-S02") return domRect(300, 900);
      return domRect(-500, -100);
    });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    vi.spyOn(window, "scrollX", "get").mockReturnValue(23);
    vi.spyOn(window, "scrollY", "get").mockReturnValue(300);

    render(<ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({
      behavior: "auto",
      left: 23,
      top: 640,
    }));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("uses the same sticky-header origin for outline and next-incomplete navigation", () => {
    const data = surface(2);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    mockHeaderPosition("sticky");
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains("content-review-header")) return domRect(0, 126);
      if (this.id === "content-S02") return domRect(300, 900);
      return domRect(80, 280);
    });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    vi.spyOn(window, "scrollX", "get").mockReturnValue(23);
    vi.spyOn(window, "scrollY", "get").mockReturnValue(300);
    render(<ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />);

    fireEvent.click(screen.getByRole("link", { name: "2" }));
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readContentDraft(key)?.ui).toEqual({
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 0 },
    });

    fireEvent.click(screen.getByRole("button", { name: "定位下一页未判断" }));
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readContentDraft(key)?.ui).toEqual({
      view: "document",
      current_slide_id: "S01",
      page_drafts: [],
      logical_scroll: { object_id: "S01", offset: 0 },
    });
    expect(scrollTo).toHaveBeenNthCalledWith(1, {
      behavior: "smooth",
      left: 23,
      top: 474,
    });
    expect(scrollTo).toHaveBeenNthCalledWith(2, {
      behavior: "smooth",
      left: 23,
      top: 254,
    });
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("records the visible slide and in-slide offset from origin zero for a non-sticky header", () => {
    const data = surface(2);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    mockHeaderPosition("static");
    const { container } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />,
    );
    const articles = container.querySelectorAll<HTMLElement>("[data-content-slide]");
    vi.spyOn(articles[0], "getBoundingClientRect").mockReturnValue({
      top: -800, bottom: -100, left: 0, right: 100, width: 100, height: 700,
      x: 0, y: -800, toJSON: () => ({}),
    } as DOMRect);
    vi.spyOn(articles[1], "getBoundingClientRect").mockReturnValue({
      top: -40, bottom: 560, left: 0, right: 100, width: 100, height: 600,
      x: 0, y: -40, toJSON: () => ({}),
    } as DOMRect);

    fireEvent.scroll(window);
    act(() => frames[0](16));
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readContentDraft(key)?.ui).toEqual({
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 40 },
    });
  });

  it("captures the last slide at the sticky-header origin with zero offset", () => {
    const data = surface(2);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    mockHeaderPosition("sticky");
    const { container } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />,
    );
    const header = container.querySelector<HTMLElement>(".content-review-header");
    const articles = container.querySelectorAll<HTMLElement>("[data-content-slide]");
    vi.spyOn(header!, "getBoundingClientRect").mockReturnValue(domRect(0, 126));
    vi.spyOn(articles[0], "getBoundingClientRect").mockReturnValue(domRect(-500, -100));
    vi.spyOn(articles[1], "getBoundingClientRect").mockReturnValue(domRect(126, 726));

    fireEvent.scroll(window);
    act(() => frames[0](16));
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readContentDraft(key)?.ui.logical_scroll).toEqual({ object_id: "S02", offset: 0 });
  });

  it("persists one rounded logical position from one animation frame", () => {
    vi.useFakeTimers();
    const data = surface(2);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    mockHeaderPosition("static");
    const storage = installMemorySessionStorage();
    const { container } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />,
    );
    const articles = container.querySelectorAll<HTMLElement>("[data-content-slide]");
    vi.spyOn(articles[0], "getBoundingClientRect").mockReturnValue(domRect(-800, -100));
    vi.spyOn(articles[1], "getBoundingClientRect").mockReturnValue(domRect(-40.4, 560));

    fireEvent.scroll(window);
    act(() => frames[0](16));
    expect(storage.setItem).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(300));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    expect(readContentDraft(key)?.ui).toEqual({
      view: "document",
      current_slide_id: "S02",
      page_drafts: [],
      logical_scroll: { object_id: "S02", offset: 40 },
    });
  });

  it("does not persist an unchanged second-frame position in a 60-page review", () => {
    vi.useFakeTimers();
    const data = surface(60);
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    mockHeaderPosition("static");
    const storage = installMemorySessionStorage();
    const { container } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={bridge(60).value} />,
    );
    const articles = container.querySelectorAll<HTMLElement>("[data-content-slide]");
    articles.forEach((article, index) => {
      vi.spyOn(article, "getBoundingClientRect").mockReturnValue(
        index === articles.length - 1 ? domRect(-40, 560) : domRect(-1_000 - index, -900 - index),
      );
    });

    fireEvent.scroll(window);
    act(() => frames[0](16));
    act(() => vi.advanceTimersByTime(300));
    expect(storage.setItem).toHaveBeenCalledTimes(1);

    fireEvent.scroll(window);
    act(() => frames[1](32));
    act(() => vi.advanceTimersByTime(300));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
  });

  it("coalesces repeated scroll events into one frame and cancels a pending capture on unmount", () => {
    const data = surface(2);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    const frames: FrameRequestCallback[] = [];
    const requestFrame = vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    const cancelFrame = vi.fn();
    vi.stubGlobal("requestAnimationFrame", requestFrame);
    vi.stubGlobal("cancelAnimationFrame", cancelFrame);
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const { container, unmount } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={bridge(2).value} />,
    );
    const articles = container.querySelectorAll<HTMLElement>("[data-content-slide]");
    const firstRect = vi.spyOn(articles[0], "getBoundingClientRect").mockReturnValue({
      top: -800, bottom: -100, left: 0, right: 100, width: 100, height: 700,
      x: 0, y: -800, toJSON: () => ({}),
    } as DOMRect);
    const secondRect = vi.spyOn(articles[1], "getBoundingClientRect").mockReturnValue({
      top: -40, bottom: 560, left: 0, right: 100, width: 100, height: 600,
      x: 0, y: -40, toJSON: () => ({}),
    } as DOMRect);

    fireEvent.scroll(window);
    fireEvent.scroll(window);
    expect(requestFrame).toHaveBeenCalledTimes(1);
    expect(firstRect).not.toHaveBeenCalled();
    expect(secondRect).not.toHaveBeenCalled();

    act(() => frames[0](16));
    expect(firstRect).toHaveBeenCalledTimes(1);
    expect(secondRect).toHaveBeenCalledTimes(1);
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readContentDraft(key)?.ui.logical_scroll).toEqual({ object_id: "S02", offset: 40 });

    fireEvent.scroll(window);
    expect(requestFrame).toHaveBeenCalledTimes(2);
    unmount();
    expect(cancelFrame).toHaveBeenCalledWith(2);
  });

  it("flushes the final decision and comment synchronously on pagehide", () => {
    const data = surface(1);
    const key = reviewDraftStorageKey(createReviewDraftContext(data));
    render(<ContentFullDeckReviewPage initialData={data} bridge={bridge(1).value} />);

    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    const comment = screen.getByLabelText("S01 审核意见");
    fireEvent.change(comment, { target: { value: "第一个中间值" } });
    fireEvent.change(comment, { target: { value: "最后一个输入值" } });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readContentDraft(key)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "最后一个输入值" },
    ]);
    expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
  });

  it("restores a same-session page draft without treating it as authoritative saved state", async () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "恢复后继续修改" }],
      logical_scroll: null,
    });
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);

    expect(screen.getByRole("radio", { name: "需要修改" })).toBeChecked();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("恢复后继续修改");
    expect(screen.getByText("已恢复，尚未保存")).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("已保存");
    expect(host.callTool).toHaveBeenCalledWith("save_content_page_decision", expect.objectContaining({
      slideId: "S01",
      decision: "modify",
      comment: "恢复后继续修改",
    }));
    fireEvent(window, new PageTransitionEvent("pagehide"));
    expect(readContentDraft(key)?.ui.page_drafts).toEqual([]);
  });

  it("clears only the successfully saved page draft and preserves the other page and navigation slices", async () => {
    const data = surface(2);
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S02",
      page_drafts: [
        { slide_id: "S01", decision: "modify", comment: "第一页草稿" },
        { slide_id: "S02", decision: "evidence", comment: "第二页草稿" },
      ],
      logical_scroll: { object_id: "S02", offset: 64 },
    });
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const host = bridge(2);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);
    fireEvent.click(screen.getAllByRole("button", { name: "保存本页判断" })[0]);
    await waitFor(() => expect(screen.getAllByText("已保存")).toHaveLength(1));
    fireEvent(window, new PageTransitionEvent("pagehide"));

    const stored = readContentDraft(key);
    expect(stored?.source_revision).toBe(7);
    expect(stored?.ui).toEqual({
      view: "document",
      current_slide_id: "S02",
      page_drafts: [{ slide_id: "S02", decision: "evidence", comment: "第二页草稿" }],
      logical_scroll: { object_id: "S02", offset: 64 },
    });
    expect(JSON.parse(window.sessionStorage.getItem(key) || "null")).toEqual({
      schema_version: 1,
      project_id: "p1",
      review_type: "content",
      review_session_id: "content-session-1",
      source_version: "content-v1",
      source_revision: 7,
      updated_at: expect.any(String),
      lineage: {
        reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
      },
      ui: {
        view: "document",
        current_slide_id: "S02",
        page_drafts: [{ slide_id: "S02", decision: "evidence", comment: "第二页草稿" }],
        logical_scroll: { object_id: "S02", offset: 64 },
      },
    });
    expect(screen.getByLabelText("S02 审核意见")).toHaveValue("第二页草稿");
  });

  it("clears the content page-draft slice after a validated batch succeeds", async () => {
    const data = surface(1);
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "approved", comment: "" }],
      logical_scroll: { object_id: "S01", offset: 12 },
    });
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const host = bridge(1);

    render(<ContentFullDeckReviewPage initialData={data} bridge={host.value} />);
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    const submit = screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);
    await screen.findByText("已提交，等待整套修改方案");
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readContentDraft(key)?.ui).toEqual({
      view: "document",
      current_slide_id: "S01",
      page_drafts: [],
      logical_scroll: { object_id: "S01", offset: 12 },
    });
  });

  it("keeps the recovered page draft when the Runtime save fails", async () => {
    const data = surface(1);
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "失败后不能丢" }],
      logical_scroll: null,
    });
    const callTool = vi.fn(async (name: string) => {
      if (name === "save_content_page_decision") throw new Error("offline");
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = { connect: vi.fn(async () => undefined), callTool: callTool as HostBridge["callTool"] } satisfies HostBridge;

    render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("保存失败；草稿仍保留，可直接重试。");
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("失败后不能丢");
    expect(readContentDraft(key)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "失败后不能丢" },
    ]);
  });

  it.each(["invalid-result", "revision-conflict", "source-stale"] as const)(
    "keeps the recovered page draft after %s",
    async (mode) => {
      const data = surface(1);
      const key = seedContentDraft(data, {
        view: "document",
        current_slide_id: "S01",
        page_drafts: [{ slide_id: "S01", decision: "modify", comment: "失败分支草稿" }],
        logical_scroll: null,
      });
      const callTool = vi.fn(async (name: string) => {
        if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
        if (mode === "invalid-result") {
          return {
            decision_ref: "invalid-ref",
            decision: validPageDecision("S01", "modify", "失败分支草稿"),
            snapshot: { revision: 9 },
          };
        }
        throw Object.assign(new Error(mode), {
          code: mode === "revision-conflict" ? "REVISION_CONFLICT" : "REVIEW_SOURCE_STALE",
        });
      });
      const host = {
        connect: vi.fn(async () => undefined),
        callTool: callTool as HostBridge["callTool"],
      } satisfies HostBridge;

      render(<ContentFullDeckReviewPage initialData={data} bridge={host} />);
      fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
      if (mode === "invalid-result") {
        await screen.findByText(/Runtime 返回无效结果/);
      } else {
        await screen.findByText("版本已变化；草稿仍保留，请刷新后重试。");
      }
      fireEvent(window, new PageTransitionEvent("pagehide"));

      expect(readContentDraft(key)?.ui.page_drafts).toEqual([
        { slide_id: "S01", decision: "modify", comment: "失败分支草稿" },
      ]);
    },
  );

  it("reconciles same-identity snapshot growth before the next page save without losing the draft", async () => {
    const data = surface(1);
    const expectedRevisions: unknown[] = [];
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      if (name !== "save_content_page_decision") throw new Error(`Unexpected tool ${name}`);
      expectedRevisions.push(args.expectedRevision);
      return {
        decision_ref: `artifact://content-page-decision/${"6".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "snapshot 增长后仍保留"),
        snapshot: { revision: 10 },
      };
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host} />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    fireEvent.change(screen.getByLabelText("S01 审核意见"), {
      target: { value: "snapshot 增长后仍保留" },
    });

    const grown = surface(1);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host} />);

    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("snapshot 增长后仍保留");
    rerender(<ContentFullDeckReviewPage initialData={data} bridge={host} />);
    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("snapshot 增长后仍保留");
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("已保存");
    expect(expectedRevisions).toEqual([9]);
  });

  it("reconciles same-identity snapshot growth before an eligible batch submission", async () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    const expectedRevisions: unknown[] = [];
    const callTool = vi.fn(async (name: string, args: Record<string, unknown>) => {
      if (name !== "submit_content_review_batch") throw new Error(`Unexpected tool ${name}`);
      expectedRevisions.push(args.expectedRevision);
      return {
        batch_ref: `artifact://content-review-batch/${"5".repeat(64)}`,
        batch: reviewBatch("submitted"),
        snapshot: { revision: 10 },
      };
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host} />,
    );
    const grown = surface(1);
    grown.review.decisions = [validPageDecision("S01")];
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host} />);

    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
    await screen.findByText("已提交，等待整套修改方案");
    expect(expectedRevisions).toEqual([9]);
  });

  it("keeps a pending page-save draft when the same identity grows before the old result returns", async () => {
    const data = surface(1);
    const key = seedContentDraft(data, {
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
    const callTool = vi.fn((name: string) => {
      if (name === "save_content_page_decision") return pending.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("正在保存…");

    const grown = surface(1);
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host} />);
    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();

    await act(async () => {
      pending.resolve({
        decision_ref: `artifact://content-page-decision/${"4".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "pending 期间增长"),
        snapshot: { revision: 10 },
      });
      await pending.promise;
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("pending 期间增长");
    expect(readContentDraft(key)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "pending 期间增长" },
    ]);
  });

  it("ignores a pending batch result when the same identity grows before it returns", async () => {
    const data = surface(1);
    data.review.decisions = [validPageDecision("S01")];
    const key = seedContentDraft(data, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [],
      logical_scroll: { object_id: "S01", offset: 0 },
    });
    const pending = deferred<{
      batch_ref: string;
      batch: Record<string, unknown>;
      snapshot: { revision: number };
    }>();
    const callTool = vi.fn((name: string) => {
      if (name === "submit_content_review_batch") return pending.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const host = {
      connect: vi.fn(async () => undefined),
      callTool: callTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const { rerender } = render(
      <ContentFullDeckReviewPage initialData={data} bridge={host} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
    await screen.findByRole("button", { name: "正在提交…" });

    const grown = surface(1);
    grown.review.decisions = [validPageDecision("S01")];
    grown.snapshotRevision = 9;
    grown.review.authoritative_revision = 9;
    rerender(<ContentFullDeckReviewPage initialData={grown} bridge={host} />);
    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    const rawBeforeCompletion = window.sessionStorage.getItem(key);

    await act(async () => {
      pending.resolve({
        batch_ref: `artifact://content-review-batch/${"2".repeat(64)}`,
        batch: reviewBatch("submitted"),
        snapshot: { revision: 10 },
      });
      await pending.promise;
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    expect(screen.getByText(/revision 9$/)).toBeInTheDocument();
    expect(screen.getByText("当前版本已变化；所有本地输入仍保留，请刷新后重试。")).toBeInTheDocument();
    expect(screen.queryByText("已提交，等待整套修改方案")).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem(key)).toBe(rawBeforeCompletion);
  });

  it("ignores an old page save that completes after a new review identity mounts", async () => {
    const oldData = surface(1);
    const oldKey = seedContentDraft(oldData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "旧会话草稿" }],
      logical_scroll: null,
    });
    const newData = surface(1);
    newData.review.review_session_id = "content-session-2";
    newData.review.review_session.review_session_id = "content-session-2";
    const newKey = seedContentDraft(newData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "evidence", comment: "新会话草稿" }],
      logical_scroll: null,
    });
    const oldSave = deferred<{
      decision_ref: string;
      decision: ContentPageDecision;
      snapshot: { revision: number };
    }>();
    const oldCallTool = vi.fn((name: string) => {
      if (name === "save_content_page_decision") return oldSave.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const oldHost = {
      connect: vi.fn(async () => undefined),
      callTool: oldCallTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const newHost = bridge(1);
    const { rerender } = render(
      <ContentFullDeckReviewPage key="old" initialData={oldData} bridge={oldHost} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await screen.findByText("正在保存…");
    rerender(<ContentFullDeckReviewPage key="new" initialData={newData} bridge={newHost.value} />);
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("新会话草稿");

    await act(async () => {
      oldSave.resolve({
        decision_ref: `artifact://content-page-decision/${"7".repeat(64)}`,
        decision: validPageDecision("S01", "modify", "旧会话草稿"),
        snapshot: { revision: 9 },
      });
      await oldSave.promise;
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(readContentDraft(oldKey)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "旧会话草稿" },
    ]);
    expect(readContentDraft(newKey)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "evidence", comment: "新会话草稿" },
    ]);
    expect(screen.getByText(/revision 8$/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("新会话草稿");
    expect(screen.queryByText(/^已保存$/)).not.toBeInTheDocument();
  });

  it("ignores an old batch completion after a new review identity mounts", async () => {
    const oldData = surface(1);
    oldData.review.decisions = [validPageDecision("S01")];
    const oldKey = seedContentDraft(oldData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [],
      logical_scroll: { object_id: "S01", offset: 0 },
    });
    const oldBatch = deferred<{
      batch_ref: string;
      batch: Record<string, unknown>;
      snapshot: { revision: number };
    }>();
    const oldCallTool = vi.fn((name: string) => {
      if (name === "submit_content_review_batch") return oldBatch.promise;
      throw new Error(`Unexpected tool ${name}`);
    });
    const oldHost = {
      connect: vi.fn(async () => undefined),
      callTool: oldCallTool as HostBridge["callTool"],
    } satisfies HostBridge;
    const newData = surface(1);
    newData.snapshotRevision = 20;
    newData.review.authoritative_revision = 20;
    newData.review.review_session_id = "content-session-2";
    newData.review.review_session.review_session_id = "content-session-2";
    const newKey = seedContentDraft(newData, {
      view: "document",
      current_slide_id: "S01",
      page_drafts: [{ slide_id: "S01", decision: "modify", comment: "新会话未提交草稿" }],
      logical_scroll: null,
    });
    const { rerender } = render(
      <ContentFullDeckReviewPage key="old" initialData={oldData} bridge={oldHost} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }));
    await screen.findByRole("button", { name: "正在提交…" });
    rerender(<ContentFullDeckReviewPage key="new" initialData={newData} bridge={bridge(1).value} />);
    const oldRawBeforeCompletion = window.sessionStorage.getItem(oldKey);
    expect(screen.getByText(/revision 20$/)).toBeInTheDocument();

    await act(async () => {
      oldBatch.resolve({
        batch_ref: `artifact://content-review-batch/${"3".repeat(64)}`,
        batch: reviewBatch("submitted"),
        snapshot: { revision: 9 },
      });
      await oldBatch.promise;
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    fireEvent(window, new PageTransitionEvent("pagehide"));

    expect(window.sessionStorage.getItem(oldKey)).toBe(oldRawBeforeCompletion);
    expect(readContentDraft(newKey)?.ui.page_drafts).toEqual([
      { slide_id: "S01", decision: "modify", comment: "新会话未提交草稿" },
    ]);
    expect(screen.getByText(/revision 20$/)).toBeInTheDocument();
    expect(screen.getByLabelText("S01 审核意见")).toHaveValue("新会话未提交草稿");
    expect(screen.queryByText("已提交，等待整套修改方案")).not.toBeInTheDocument();
  });
});

function withinDialogButton(dialog: HTMLElement, name: string) {
  return Array.from(dialog.querySelectorAll("button")).find((button) => button.textContent === name);
}
