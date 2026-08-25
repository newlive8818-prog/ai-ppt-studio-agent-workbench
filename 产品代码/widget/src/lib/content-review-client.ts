import type { HostBridge } from "../types";
import type {
  ContentFullDeckReviewProjection,
  ContentPageDecision,
  ContentReviewProgress,
} from "../types/content-review";

export interface SavedContentPageDecision {
  page_completion: { slide_id: string; completed: boolean };
  review_progress: ContentReviewProgress;
  revision: number;
}

export interface SubmittedContentReviewBatch {
  artifact_ref: string;
  follow_up_message: string;
  revision: number;
}

export interface OpenedContentEvidenceBrowser {
  status: "opened" | "review-session-ready";
  opened: boolean;
  reviewType: "content-evidence";
  reviewSessionId: string;
  sourceVersion: string;
  slideId: string;
  evidenceId: string;
  materialRef: string;
  url?: string;
}

export interface ContentReviewClient {
  load(projectRoot: string, reviewSessionId: string): Promise<ContentFullDeckReviewProjection>;
  saveDecision(input: {
    projectRoot: string;
    expectedRevision: number;
    reviewSessionId: string;
    reviewBatchId: string;
    slideId: string;
    decision: ContentPageDecision;
    comment: string;
  }): Promise<SavedContentPageDecision>;
  submitBatch(input: {
    projectRoot: string;
    expectedRevision: number;
    reviewSessionId: string;
    reviewBatchId: string;
  }): Promise<SubmittedContentReviewBatch>;
  openEvidenceBrowser(input: {
    projectRoot: string;
    reviewSessionId: string;
    sourceVersion: string;
    slideId: string;
    evidenceId: string;
    materialRef: string;
  }): Promise<OpenedContentEvidenceBrowser>;
}

export function createContentReviewClient(bridge: HostBridge): ContentReviewClient {
  return {
    load(projectRoot, reviewSessionId) {
      return bridge.callTool("get_content_full_deck_review_projection", {
        projectRoot,
        reviewSessionId,
      });
    },

    saveDecision(input) {
      return bridge.callTool("save_content_full_deck_page_decision", input);
    },

    submitBatch(input) {
      return bridge.callTool("submit_content_full_deck_review_batch", input);
    },

    openEvidenceBrowser(input) {
      return bridge.callTool("open_content_full_deck_evidence_browser", input);
    },
  };
}
