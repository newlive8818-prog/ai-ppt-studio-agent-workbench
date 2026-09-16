import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  applyReviewDraftUpdate,
  discardReviewDraft,
  isReviewDraftSliceClear,
  loadReviewDraft,
  reviewDraftStorageKey,
  saveReviewDraft,
  type ContentReviewDraftContext,
  type ContentReviewDraftUpdate,
  type ContentReviewDraftUi,
  type ReviewDraftUpdate,
  type ReviewDraftStorage,
  type VisualReviewDraftContext,
  type VisualReviewDraftUpdate,
  type VisualReviewDraftUi,
} from "./reviewDraftStore";

interface ReviewDraftHookOptions<Context, Ui> {
  context: Context;
  initialUi: Ui;
  storage?: ReviewDraftStorage | null;
  throttleMs?: number;
  now?: () => string;
  beforeFinalFlush?: () => void;
}

export type ContentReviewDraftHookOptions = ReviewDraftHookOptions<
  ContentReviewDraftContext,
  ContentReviewDraftUi
>;

export type VisualReviewDraftHookOptions = ReviewDraftHookOptions<
  VisualReviewDraftContext,
  VisualReviewDraftUi
>;

export interface UseReviewDraftResult<Ui, Update> {
  ui: Ui;
  updateDraft: (update: Update) => boolean;
  discardDraft: () => boolean;
  flushDraft: () => boolean;
  storageKey: string;
}

type DraftUi = ContentReviewDraftUi | VisualReviewDraftUi;
type DraftOptions = ContentReviewDraftHookOptions | VisualReviewDraftHookOptions;
type DraftResult =
  | UseReviewDraftResult<ContentReviewDraftUi, ContentReviewDraftUpdate>
  | UseReviewDraftResult<VisualReviewDraftUi, VisualReviewDraftUpdate>;

function browserStorage(): ReviewDraftStorage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function normalizedThrottleMs(value: number | undefined): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 300;
}

export function useReviewDraft(
  options: ContentReviewDraftHookOptions,
): UseReviewDraftResult<ContentReviewDraftUi, ContentReviewDraftUpdate>;
export function useReviewDraft(
  options: VisualReviewDraftHookOptions,
): UseReviewDraftResult<VisualReviewDraftUi, VisualReviewDraftUpdate>;
export function useReviewDraft(options: DraftOptions): DraftResult {
  const context = options.context;
  const initialUi = options.initialUi as DraftUi;
  const storageRef = useRef<ReviewDraftStorage | null | undefined>(undefined);
  if (storageRef.current === undefined) {
    storageRef.current = options.storage === undefined ? browserStorage() : options.storage;
  }
  const storage = storageRef.current;
  const initialUiRef = useRef(initialUi);
  const [ui, setUiState] = useState<DraftUi>(() => {
    if (!storage) return initialUiRef.current;
    const loaded = context.reviewType === "content"
      ? loadReviewDraft(storage, context)
      : loadReviewDraft(storage, context);
    return loaded?.ui ?? initialUiRef.current;
  });
  const latestRef = useRef(ui);
  const dirtyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushRef = useRef<() => boolean>(() => false);
  const beforeFinalFlushRef = useRef(options.beforeFinalFlush);
  const throttleMs = normalizedThrottleMs(options.throttleMs);
  const nowRef = useRef(options.now ?? (() => new Date().toISOString()));
  nowRef.current = options.now ?? nowRef.current;
  beforeFinalFlushRef.current = options.beforeFinalFlush;

  const cancelTimer = useCallback(() => {
    if (timerRef.current === null) return;
    clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const flushDraft = useCallback(() => {
    cancelTimer();
    if (!dirtyRef.current || !storage) return false;
    let updatedAt: string;
    try {
      updatedAt = nowRef.current();
    } catch {
      return false;
    }
    const saved = context.reviewType === "content"
      ? saveReviewDraft(storage, context, latestRef.current as ContentReviewDraftUi, updatedAt)
      : saveReviewDraft(storage, context, latestRef.current as VisualReviewDraftUi, updatedAt);
    if (saved) dirtyRef.current = false;
    return saved;
  }, [cancelTimer, context, storage]);
  flushRef.current = flushDraft;

  const scheduleFlush = useCallback((restart: boolean) => {
    if (restart) cancelTimer();
    if (timerRef.current !== null) return;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      flushRef.current();
    }, throttleMs);
  }, [cancelTimer, throttleMs]);

  const updateDraft = useCallback((update: ReviewDraftUpdate) => {
    const next = context.reviewType === "content"
      ? applyReviewDraftUpdate(
          context,
          latestRef.current as ContentReviewDraftUi,
          update as ContentReviewDraftUpdate,
        )
      : applyReviewDraftUpdate(
          context,
          latestRef.current as VisualReviewDraftUi,
          update as VisualReviewDraftUpdate,
        );
    if (!next) return false;
    latestRef.current = next;
    dirtyRef.current = true;
    setUiState(next);
    scheduleFlush(isReviewDraftSliceClear(update));
    return true;
  }, [context, scheduleFlush]);

  const discardDraft = useCallback(() => {
    if (!storage || !discardReviewDraft(storage, context)) return false;
    cancelTimer();
    dirtyRef.current = false;
    latestRef.current = initialUiRef.current;
    setUiState(initialUiRef.current);
    return true;
  }, [cancelTimer, context, storage]);

  useEffect(() => {
    const finalFlush = () => {
      try {
        beforeFinalFlushRef.current?.();
      } finally {
        flushRef.current();
      }
    };
    const handlePageHide = () => {
      finalFlush();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") finalFlush();
    };
    window.addEventListener("pagehide", handlePageHide);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      finalFlush();
    };
  }, []);

  return {
    ui,
    updateDraft: updateDraft as ((update: ContentReviewDraftUpdate) => boolean)
      | ((update: VisualReviewDraftUpdate) => boolean),
    discardDraft,
    flushDraft,
    storageKey: reviewDraftStorageKey(context),
  } as DraftResult;
}
