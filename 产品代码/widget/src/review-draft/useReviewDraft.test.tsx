import { StrictMode } from "react";
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createReviewDraftEnvelope,
  reviewDraftStorageKey,
  type ContentReviewDraftContext,
  type ContentReviewDraftUi,
  type ReviewDraftStorage,
} from "./reviewDraftStore";
import { useReviewDraft } from "./useReviewDraft";

function contentContext(): ContentReviewDraftContext {
  return {
    reviewType: "content",
    projectId: "project:/ 中文",
    reviewSessionId: "content/session:1",
    sourceVersion: "content v1/版本",
    sourceRevision: 7,
    lineage: { readingBlueprintRef: `artifact://reading-deck-blueprint/${"a".repeat(64)}` },
    slideIds: ["S01", "S02"],
  };
}

function initialUi(): ContentReviewDraftUi {
  return {
    view: "document",
    current_slide_id: "S01",
    page_drafts: [],
    logical_scroll: { object_id: "S01", offset: 0 },
  };
}

function uiWithComment(comment: string): ContentReviewDraftUi {
  return {
    ...initialUi(),
    page_drafts: [{ slide_id: "S01", decision: "modify", comment }],
  };
}

function upsertPage(comment: string, slideId = "S01") {
  return {
    type: "upsert-page-draft" as const,
    draft: { slide_id: slideId, decision: "modify" as const, comment },
  };
}

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const storage: ReviewDraftStorage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
    removeItem: vi.fn((key: string) => { values.delete(key); }),
  };
  return { storage, values };
}

function renderContentDraft(
  storage: ReviewDraftStorage,
  options: { throttleMs?: number; strict?: boolean } = {},
) {
  return renderHook(() => useReviewDraft({
    context: contentContext(),
    initialUi: initialUi(),
    storage,
    throttleMs: options.throttleMs ?? 100,
    now: () => "2026-08-15T00:00:00.123456Z",
  }), options.strict ? { wrapper: StrictMode } : undefined);
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("useReviewDraft", () => {
  it("falls back to authoritative initial UI when storage is invalid", () => {
    const context = contentContext();
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: JSON.stringify({ schema_version: 1 }) });

    const { result } = renderContentDraft(storage);

    expect(result.current.ui).toEqual(initialUi());
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("contains storage exceptions and keeps local UI dirty when discard removal fails", () => {
    vi.useFakeTimers();
    const storage: ReviewDraftStorage = {
      getItem: vi.fn(() => { throw new Error("get denied"); }),
      setItem: vi.fn(() => { throw new Error("set denied"); }),
      removeItem: vi.fn(() => { throw new Error("remove denied"); }),
    };

    const { result } = renderContentDraft(storage);
    expect(result.current.ui).toEqual(initialUi());
    expect(() => act(() => {
      result.current.updateDraft(upsertPage("保留 UI"));
      vi.advanceTimersByTime(100);
    })).not.toThrow();
    let discarded = true;
    expect(() => act(() => { discarded = result.current.discardDraft(); })).not.toThrow();
    expect(discarded).toBe(false);
    expect(result.current.ui.page_drafts[0]?.comment).toBe("保留 UI");
  });

  it("persists only the latest rapid typed update after one throttle window", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage);

    act(() => {
      result.current.updateDraft(upsertPage("first"));
      result.current.updateDraft(upsertPage("latest"));
    });
    expect(result.current.ui.page_drafts[0]?.comment).toBe("latest");

    act(() => vi.advanceTimersByTime(100));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    const [key, raw] = vi.mocked(storage.setItem).mock.calls[0];
    expect(key).toBe(reviewDraftStorageKey(contentContext()));
    expect(JSON.parse(raw).ui.page_drafts[0].comment).toBe("latest");
  });

  it("has the scheduled timer read latestRef instead of its first-render snapshot", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage);

    act(() => result.current.updateDraft(upsertPage("scheduled first")));
    act(() => vi.advanceTimersByTime(50));
    act(() => result.current.updateDraft(upsertPage("changed before flush")));
    act(() => vi.advanceTimersByTime(50));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    const raw = vi.mocked(storage.setItem).mock.calls[0][1];
    expect(JSON.parse(raw).ui.page_drafts[0].comment).toBe("changed before flush");
  });

  it("flushes the last UI synchronously to the exact key on unmount", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const hook = renderContentDraft(storage, { throttleMs: 1_000 });

    act(() => hook.result.current.updateDraft(upsertPage("unmount latest")));
    hook.unmount();

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    const [key, raw] = vi.mocked(storage.setItem).mock.calls[0];
    expect(key).toBe(reviewDraftStorageKey(contentContext()));
    expect(JSON.parse(raw).ui.page_drafts[0].comment).toBe("unmount latest");
  });

  it("flushes synchronously on pagehide", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage, { throttleMs: 1_000 });
    act(() => result.current.updateDraft(upsertPage("pagehide latest")));

    act(() => window.dispatchEvent(new Event("pagehide")));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(vi.mocked(storage.setItem).mock.calls[0][1]).ui.page_drafts[0].comment)
      .toBe("pagehide latest");
  });

  it("flushes synchronously when visibility changes to hidden", () => {
    vi.useFakeTimers();
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage, { throttleMs: 1_000 });
    act(() => result.current.updateDraft(upsertPage("hidden latest")));

    act(() => document.dispatchEvent(new Event("visibilitychange")));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(vi.mocked(storage.setItem).mock.calls[0][1]).ui.page_drafts[0].comment)
      .toBe("hidden latest");
  });

  it("discards the whole envelope only after removal succeeds and cancels stale writes", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage, { throttleMs: 1_000 });

    act(() => result.current.updateDraft(upsertPage("must not return")));
    let discarded = false;
    act(() => { discarded = result.current.discardDraft(); });
    expect(discarded).toBe(true);
    expect(result.current.ui).toEqual(initialUi());
    expect(storage.removeItem).toHaveBeenCalledWith(reviewDraftStorageKey(contentContext()));

    act(() => vi.advanceTimersByTime(1_000));

    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("cancels the old timer and writes a newly cleared content-page envelope", () => {
    vi.useFakeTimers();
    const { storage } = memoryStorage();
    const { result } = renderContentDraft(storage, { throttleMs: 100 });

    act(() => {
      result.current.updateDraft(upsertPage("clear this", "S01"));
      result.current.updateDraft(upsertPage("keep this", "S02"));
    });
    act(() => vi.advanceTimersByTime(50));
    act(() => result.current.updateDraft({ type: "clear-page-draft", slideId: "S01" }));
    act(() => vi.advanceTimersByTime(50));
    expect(storage.setItem).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(50));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(vi.mocked(storage.setItem).mock.calls[0][1]).ui.page_drafts).toEqual([
      { slide_id: "S02", decision: "modify", comment: "keep this" },
    ]);
  });

  it("uses sessionStorage by default for load and save without touching localStorage", () => {
    vi.useFakeTimers();
    const context = contentContext();
    const key = reviewDraftStorageKey(context);
    window.sessionStorage.setItem(key, JSON.stringify(createReviewDraftEnvelope(
      context,
      uiWithComment("loaded from session"),
      "2026-08-15T00:00:00Z",
    )));
    const localStorageAccess = vi.spyOn(window, "localStorage", "get");

    const { result } = renderHook(() => useReviewDraft({
      context,
      initialUi: initialUi(),
      throttleMs: 100,
      now: () => "2026-08-15T00:00:01Z",
    }));

    expect(result.current.ui.page_drafts[0]?.comment).toBe("loaded from session");
    act(() => result.current.updateDraft(upsertPage("written to session")));
    act(() => vi.advanceTimersByTime(100));
    expect(JSON.parse(window.sessionStorage.getItem(key) || "null").ui.page_drafts[0].comment)
      .toBe("written to session");
    expect(localStorageAccess).not.toHaveBeenCalled();
  });

  it("keeps one active lifecycle listener and writes once after StrictMode replay", () => {
    vi.useFakeTimers();
    const activePagehide = new Set<EventListenerOrEventListenerObject>();
    const activeVisibility = new Set<EventListenerOrEventListenerObject>();
    const addWindow = window.addEventListener.bind(window);
    const removeWindow = window.removeEventListener.bind(window);
    const addDocument = document.addEventListener.bind(document);
    const removeDocument = document.removeEventListener.bind(document);
    vi.spyOn(window, "addEventListener").mockImplementation(((
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions,
    ) => {
      if (type === "pagehide") activePagehide.add(listener);
      addWindow(type, listener, options);
    }) as typeof window.addEventListener);
    vi.spyOn(window, "removeEventListener").mockImplementation(((
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | EventListenerOptions,
    ) => {
      if (type === "pagehide") activePagehide.delete(listener);
      removeWindow(type, listener, options);
    }) as typeof window.removeEventListener);
    vi.spyOn(document, "addEventListener").mockImplementation(((
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions,
    ) => {
      if (type === "visibilitychange") activeVisibility.add(listener);
      addDocument(type, listener, options);
    }) as typeof document.addEventListener);
    vi.spyOn(document, "removeEventListener").mockImplementation(((
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | EventListenerOptions,
    ) => {
      if (type === "visibilitychange") activeVisibility.delete(listener);
      removeDocument(type, listener, options);
    }) as typeof document.removeEventListener);
    const { storage } = memoryStorage();

    const hook = renderContentDraft(storage, { throttleMs: 1_000, strict: true });
    expect(activePagehide).toHaveLength(1);
    expect(activeVisibility).toHaveLength(1);
    act(() => hook.result.current.updateDraft(upsertPage("StrictMode latest")));

    act(() => window.dispatchEvent(new Event("pagehide")));

    expect(storage.setItem).toHaveBeenCalledTimes(1);
    hook.unmount();
    expect(activePagehide).toHaveLength(0);
    expect(activeVisibility).toHaveLength(0);
    expect(storage.setItem).toHaveBeenCalledTimes(1);
  });
});
