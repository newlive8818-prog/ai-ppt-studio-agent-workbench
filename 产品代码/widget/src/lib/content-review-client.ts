import type {
  ContentFullDeckProjection,
  ContentPageDecision,
  ContentReviewProgress,
  ContentSidebarReviewProjection,
  HostBridge,
  ProjectSnapshot,
} from "../types";

export interface SavedContentPageDecision {
  artifact_ref: string;
  page_completion: {
    slide_id: string;
    completed: boolean;
  };
  review_progress: ContentReviewProgress;
  snapshot: ProjectSnapshot;
}

export interface SubmittedContentReviewBatch {
  artifact_ref: string;
  follow_up_message: string;
  snapshot: ProjectSnapshot;
}

export interface WithdrawnContentReviewBatch {
  artifact_ref: string;
  replacement_review_batch_id: string;
  snapshot: ProjectSnapshot;
}

export interface OpenedContentEvidenceBrowser {
  opened: true;
  reviewType: "content-evidence";
  sourceVersion: string;
  slideId: string;
  evidenceId: string;
  materialRef: string;
}

export interface ContentReviewClient {
  load(projectRoot: string): Promise<ContentSidebarReviewProjection>;
  saveDecision(input: {
    projectRoot: string;
    expectedRevision: number;
    sourceVersion: string;
    reviewBatchId: string;
    slideId: string;
    decision: ContentPageDecision;
    comment: string;
  }): Promise<SavedContentPageDecision>;
  submitBatch(input: {
    projectRoot: string;
    expectedRevision: number;
    sourceVersion: string;
    reviewBatchId: string;
  }): Promise<SubmittedContentReviewBatch>;
  withdrawBatch(input: {
    projectRoot: string;
    expectedRevision: number;
    sourceVersion: string;
    reviewBatchId: string;
    reason: string;
  }): Promise<WithdrawnContentReviewBatch>;
  openEvidenceBrowser(input: {
    projectRoot: string;
    sourceVersion: string;
    slideId: string;
    evidenceId: string;
    materialRef: string;
  }): Promise<OpenedContentEvidenceBrowser>;
  isReviewReady(
    projection: ContentSidebarReviewProjection,
  ): projection is ContentFullDeckProjection;
}

export function createContentReviewClient(bridge: HostBridge): ContentReviewClient {
  return {
    load(projectRoot: string) {
      return bridge.callTool<ContentSidebarReviewProjection>(
        "get_content_sidebar_review_projection",
        { projectRoot },
      );
    },

    saveDecision(input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewBatchId: string;
      slideId: string;
      decision: ContentPageDecision;
      comment: string;
    }) {
      return bridge.callTool<SavedContentPageDecision>(
        "save_content_page_decision",
        input,
      );
    },

    submitBatch(input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewBatchId: string;
    }) {
      return bridge.callTool<SubmittedContentReviewBatch>(
        "submit_content_review_batch",
        input,
      );
    },

    withdrawBatch(input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewBatchId: string;
      reason: string;
    }) {
      return bridge.callTool<WithdrawnContentReviewBatch>(
        "withdraw_content_review_batch",
        input,
      );
    },

    openEvidenceBrowser(input: {
      projectRoot: string;
      sourceVersion: string;
      slideId: string;
      evidenceId: string;
      materialRef: string;
    }) {
      return bridge.callTool<OpenedContentEvidenceBrowser>(
        "open_content_evidence_browser",
        input,
      );
    },

    isReviewReady(
      projection: ContentSidebarReviewProjection,
    ): projection is ContentFullDeckProjection {
      return projection.display_policy === "content-sidebar-full-deck";
    },
  };
}
