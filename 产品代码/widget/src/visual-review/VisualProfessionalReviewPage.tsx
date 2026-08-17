import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import {
  createReviewDraftContext,
  reviewDraftPageIdentity,
  type LogicalReviewScroll,
  type VisualReviewDraftContext,
  type VisualReviewDraftUi,
} from "../review-draft/reviewDraftStore";
import { useReviewDraft } from "../review-draft/useReviewDraft";
import type { HostBridge } from "../types/host";
import type { VisualReviewSurfaceData } from "../types/visual-review";
import "../styles/visual-review.css";
import { AnchorResultsView } from "./AnchorResultsView";
import {
  VisualContractView,
  visualConfirmationLabel,
  visualSourceVersionLabel,
} from "./VisualContractView";

interface Props {
  initialData: VisualReviewSurfaceData;
  bridge: HostBridge;
}

type ReviewView = "anchors" | "contract";

const reviewViews: ReviewView[] = ["anchors", "contract"];

function visualLogicalOrigin(root: HTMLElement | null): number {
  const header = root?.querySelector<HTMLElement>(".visual-professional-header");
  if (!header || window.getComputedStyle(header).position !== "sticky") return 0;
  return header.getBoundingClientRect().bottom;
}

function logicalElements(root: HTMLElement | null, view: ReviewView): HTMLElement[] {
  const panel = root?.querySelector<HTMLElement>(`[data-visual-review-panel="${view}"]`);
  if (!panel) return [];
  const attribute = view === "anchors"
    ? "[data-anchor-logical-object]"
    : "[data-contract-logical-object]";
  return Array.from(panel.querySelectorAll<HTMLElement>(attribute));
}

function logicalObjectId(element: HTMLElement, view: ReviewView): string {
  return view === "anchors"
    ? element.dataset.anchorLogicalObject || ""
    : element.dataset.contractLogicalObject || "";
}

function scrollToVisualLogicalPosition(
  root: HTMLElement | null,
  view: ReviewView,
  position: LogicalReviewScroll,
) {
  const target = logicalElements(root, view).find((element) => logicalObjectId(element, view) === position.object_id);
  if (!target) return;
  const origin = visualLogicalOrigin(root);
  window.scrollTo({
    behavior: "auto",
    left: window.scrollX,
    top: window.scrollY + target.getBoundingClientRect().top - origin + position.offset,
  });
}

interface RootProps extends Props {
  reviewDraftContext: VisualReviewDraftContext;
  pageIdentity: string;
}

export function VisualProfessionalReviewPage({ initialData, bridge }: Props) {
  const reviewDraftContext = createReviewDraftContext(initialData);
  const pageIdentity = reviewDraftPageIdentity(reviewDraftContext);
  return (
    <VisualProfessionalReviewRoot
      key={pageIdentity}
      initialData={initialData}
      bridge={bridge}
      reviewDraftContext={reviewDraftContext}
      pageIdentity={pageIdentity}
    />
  );
}

function VisualProfessionalReviewRoot({
  initialData,
  bridge,
  reviewDraftContext,
  pageIdentity,
}: RootProps) {
  const defaultReviewDraftUi = useMemo<VisualReviewDraftUi>(() => ({
    view: "anchors",
    current_anchor_slide_id: null,
    anchor_feedback_drafts: [],
    anchor_feedback_composer: null,
    contract_mark_drafts: [],
    contract_mark_composer: null,
    anchor_logical_scroll: null,
    contract_logical_scroll: null,
  }), [pageIdentity]);
  const beforeFinalDraftFlushRef = useRef<() => void>(() => undefined);
  const reviewDraft = useReviewDraft({
    context: reviewDraftContext,
    initialUi: defaultReviewDraftUi,
    beforeFinalFlush: () => beforeFinalDraftFlushRef.current(),
  });
  const view = reviewDraft.ui.view;
  const contractIdentity = `${initialData.review.review_session_id}:${initialData.review.source_version}:${initialData.review.visual_contract_ref}`;
  const [revisionState, setRevisionState] = useState(() => ({
    identity: contractIdentity,
    revision: initialData.snapshotRevision,
  }));
  const revision = revisionState.identity === contractIdentity
    ? revisionState.revision
    : initialData.snapshotRevision;
  const tabRefs = useRef<Record<ReviewView, HTMLButtonElement | null>>({ anchors: null, contract: null });
  const rootRef = useRef<HTMLElement | null>(null);
  const instanceId = useId();
  const anchorsTabId = `${instanceId}-visual-review-tab-anchors`;
  const contractTabId = `${instanceId}-visual-review-tab-contract`;
  const anchorsPanelId = `${instanceId}-visual-review-panel-anchors`;
  const contractPanelId = `${instanceId}-visual-review-panel-contract`;
  const logicalPositionsRef = useRef<Record<ReviewView, LogicalReviewScroll | null>>({
    anchors: reviewDraft.ui.anchor_logical_scroll,
    contract: reviewDraft.ui.contract_logical_scroll,
  });
  const viewRef = useRef(view);
  const scrollActivityRef = useRef<Record<ReviewView, boolean>>({ anchors: false, contract: false });
  const pendingScrollFrameRef = useRef<{ id: number; view: ReviewView } | null>(null);

  viewRef.current = view;
  logicalPositionsRef.current.anchors = reviewDraft.ui.anchor_logical_scroll;
  logicalPositionsRef.current.contract = reviewDraft.ui.contract_logical_scroll;

  useEffect(() => {
    setRevisionState((current) => {
      if (current.identity !== contractIdentity) {
        return { identity: contractIdentity, revision: initialData.snapshotRevision };
      }
      return initialData.snapshotRevision > current.revision
        ? { ...current, revision: initialData.snapshotRevision }
        : current;
    });
  }, [contractIdentity, initialData.snapshotRevision]);

  const updateRevision = (nextRevision: number) => {
    setRevisionState((current) => current.identity === contractIdentity
      ? { identity: contractIdentity, revision: Math.max(current.revision, nextRevision) }
      : current);
  };

  const recordLogicalPosition = (targetView: ReviewView, objectId: string, offset: number) => {
    const roundedOffset = Number.isFinite(offset) ? Math.max(0, Math.round(offset)) : 0;
    const previous = logicalPositionsRef.current[targetView];
    if (previous?.object_id === objectId && previous.offset === roundedOffset) return;
    const update = targetView === "anchors"
      ? { type: "set-anchor-logical-scroll" as const, scroll: { object_id: objectId, offset: roundedOffset } }
      : { type: "set-contract-logical-scroll" as const, scroll: { object_id: objectId, offset: roundedOffset } };
    if (reviewDraft.updateDraft(update)) {
      logicalPositionsRef.current[targetView] = { object_id: objectId, offset: roundedOffset };
    }
  };

  const captureLogicalPosition = (targetView: ReviewView) => {
    const elements = logicalElements(rootRef.current, targetView);
    if (!elements.length) return;
    const origin = visualLogicalOrigin(rootRef.current);
    let selected = elements[0];
    let selectedRect = selected.getBoundingClientRect();
    for (const element of elements) {
      const rect = element.getBoundingClientRect();
      if (rect.top <= origin) {
        selected = element;
        selectedRect = rect;
      }
    }
    const objectId = logicalObjectId(selected, targetView);
    if (!objectId) return;
    recordLogicalPosition(targetView, objectId, Math.max(0, origin - selectedRect.top));
  };

  beforeFinalDraftFlushRef.current = () => {
    const pendingFrame = pendingScrollFrameRef.current;
    if (pendingFrame !== null) {
      window.cancelAnimationFrame(pendingFrame.id);
      pendingScrollFrameRef.current = null;
    }
    const targetView = viewRef.current;
    if (scrollActivityRef.current[targetView]) captureLogicalPosition(targetView);
    scrollActivityRef.current[targetView] = false;
  };

  useLayoutEffect(() => () => {
    beforeFinalDraftFlushRef.current();
  }, []);

  const selectView = (nextView: ReviewView) => {
    if (nextView === view) return;
    const pendingFrame = pendingScrollFrameRef.current;
    if (pendingFrame !== null) {
      window.cancelAnimationFrame(pendingFrame.id);
      pendingScrollFrameRef.current = null;
    }
    if (scrollActivityRef.current[view]) captureLogicalPosition(view);
    scrollActivityRef.current[view] = false;
    reviewDraft.updateDraft({ type: "set-visual-view", view: nextView });
  };

  useEffect(() => {
    const position = logicalPositionsRef.current[view];
    scrollActivityRef.current[view] = false;
    if (position) scrollToVisualLogicalPosition(rootRef.current, view, position);
  }, [pageIdentity, view]);

  useEffect(() => {
    const handleScroll = () => {
      const targetView = viewRef.current;
      scrollActivityRef.current[targetView] = true;
      if (pendingScrollFrameRef.current !== null) return;
      const id = window.requestAnimationFrame(() => {
        if (pendingScrollFrameRef.current?.id !== id) return;
        pendingScrollFrameRef.current = null;
        captureLogicalPosition(targetView);
      });
      pendingScrollFrameRef.current = { id, view: targetView };
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      const pendingFrame = pendingScrollFrameRef.current;
      if (pendingFrame !== null) {
        window.cancelAnimationFrame(pendingFrame.id);
        pendingScrollFrameRef.current = null;
      }
    };
  }, [reviewDraft.updateDraft]);

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, currentView: ReviewView) => {
    const currentIndex = reviewViews.indexOf(currentView);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % reviewViews.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + reviewViews.length) % reviewViews.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = reviewViews.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextView = reviewViews[nextIndex];
    selectView(nextView);
    tabRefs.current[nextView]?.focus();
  };

  const unsavedCount = reviewDraft.ui.anchor_feedback_drafts.length
    + (reviewDraft.ui.anchor_feedback_composer ? 1 : 0)
    + reviewDraft.ui.contract_mark_drafts.length
    + (reviewDraft.ui.contract_mark_composer ? 1 : 0);
  const visibleSourceVersion = visualSourceVersionLabel(initialData.review.source_version);
  const visibleConfirmation = visualConfirmationLabel(initialData.review.gate_status.G3);

  return (
    <main ref={rootRef} className="visual-professional-page">
      <header className="visual-professional-header visual-review-topbar visual-professional-topbar">
        <div className="visual-professional-project visual-professional-project-identity">
          <span className="visual-professional-ai-mark" aria-hidden="true">AI</span>
          <div className="visual-professional-project-copy">
            <strong>{initialData.review.project_name}</strong>
            <span>{visibleSourceVersion} · revision {revision}</span>
          </div>
        </div>
        <div className="visual-professional-view-tabs visual-professional-review-view-switch" role="tablist" aria-label="视觉专业审核视图">
          <button
            ref={(node) => { tabRefs.current.anchors = node; }}
            id={anchorsTabId}
            role="tab"
            aria-controls={anchorsPanelId}
            aria-selected={view === "anchors"}
            tabIndex={view === "anchors" ? 0 : -1}
            onKeyDown={(event) => handleTabKeyDown(event, "anchors")}
            onClick={() => selectView("anchors")}
          >3 页锚点成果</button>
          <button
            ref={(node) => { tabRefs.current.contract = node; }}
            id={contractTabId}
            role="tab"
            aria-controls={contractPanelId}
            aria-selected={view === "contract"}
            tabIndex={view === "contract" ? 0 : -1}
            onKeyDown={(event) => handleTabKeyDown(event, "contract")}
            onClick={() => selectView("contract")}
          >完整视觉合同</button>
        </div>
        <div className="visual-professional-gates visual-professional-compact-status">
          <span>G1 {initialData.review.gate_status.G1}</span>
          <span>G2 {initialData.review.gate_status.G2}</span>
          <span>视觉确认 {visibleConfirmation}</span>
          <strong aria-label="全局未保存状态">
            {unsavedCount ? `未保存 ${unsavedCount}` : "已保存"}
          </strong>
        </div>
      </header>
      <div
        id={anchorsPanelId}
        role="tabpanel"
        aria-labelledby={anchorsTabId}
        data-visual-review-panel="anchors"
        hidden={view !== "anchors"}
        aria-hidden={view !== "anchors"}
      >
        <AnchorResultsView
          key={pageIdentity}
          data={initialData}
          bridge={bridge}
          revision={revision}
          onRevision={updateRevision}
          commandIdentity={pageIdentity}
          drafts={reviewDraft.ui.anchor_feedback_drafts}
          composer={reviewDraft.ui.anchor_feedback_composer}
          onSliceChange={(drafts, composer) => reviewDraft.updateDraft({
            type: "replace-anchor-slice",
            drafts,
            composer,
          })}
          onClearSlice={() => reviewDraft.updateDraft({ type: "clear-anchor-slice" })}
          currentSlideId={reviewDraft.ui.current_anchor_slide_id ?? initialData.review.anchors[0]?.slide_id ?? ""}
          onCurrentSlideChange={(slideId) => reviewDraft.updateDraft({
            type: "set-current-anchor-slide",
            slideId,
          })}
        />
      </div>
      <div
        id={contractPanelId}
        role="tabpanel"
        aria-labelledby={contractTabId}
        data-visual-review-panel="contract"
        hidden={view !== "contract"}
        aria-hidden={view !== "contract"}
      >
        <VisualContractView
          key={contractIdentity}
          data={initialData}
          bridge={bridge}
          revision={revision}
          onRevision={updateRevision}
          commandIdentity={pageIdentity}
          drafts={reviewDraft.ui.contract_mark_drafts}
          composer={reviewDraft.ui.contract_mark_composer}
          onSliceChange={(drafts, composer) => reviewDraft.updateDraft({
            type: "replace-contract-slice",
            drafts,
            composer,
          })}
          onClearSlice={() => reviewDraft.updateDraft({ type: "clear-contract-slice" })}
        />
      </div>
    </main>
  );
}
