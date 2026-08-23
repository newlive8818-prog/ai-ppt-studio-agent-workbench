import type {
  ContentFullDeckProjection,
  ContentPageDecision,
  ContentSidebarReviewProjection,
  HostBridge,
} from "../types";
import type {
  OpenedContentEvidenceBrowser,
  SavedContentPageDecision,
  SubmittedContentReviewBatch,
  WithdrawnContentReviewBatch,
} from "../types/tool-contracts";

export type {
  OpenedContentEvidenceBrowser,
  SavedContentPageDecision,
  SubmittedContentReviewBatch,
  WithdrawnContentReviewBatch,
} from "../types/tool-contracts";

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
      return bridge.callTool(
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
      return bridge.callTool(
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
      return bridge.callTool(
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
      return bridge.callTool(
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
      return bridge.callTool(
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
