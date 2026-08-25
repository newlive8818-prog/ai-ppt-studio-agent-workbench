import type {
  ContentPageDecision,
  ContentReviewProgress,
  ContentSidebarReviewProjection,
  ProjectSnapshot,
  ReviewMark,
} from "../types";
import type {
  ContentFullDeckReviewProjection,
  ContentPageDecision as V22ContentPageDecision,
  ContentReviewProgress as V22ContentReviewProgress,
} from "./content-review";
import type {
  AnchorFeedbackBatch,
  AnchorRegionFeedback,
  VisualContractReviewMark,
  VisualContractReviewMarkSet,
} from "./visual-review";

export interface BrowserReviewOpenResult {
  status?: "opened" | "review-session-ready";
  opened?: boolean;
  openMode?: "host-adapter" | "agent-browser";
  browserAction?: "open-scoped-url";
  url?: string;
}

export interface SavedContentPageDecision {
  artifact_ref: string;
  page_completion: { slide_id: string; completed: boolean };
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

interface OpenedContentEvidenceBrowserBase {
  status: "opened" | "review-session-ready";
  opened: boolean;
  reviewType: "content-evidence";
  sourceVersion: string;
  slideId: string;
  evidenceId: string;
  materialRef: string;
  url?: string;
}

export type OpenedLegacyContentEvidenceBrowser = OpenedContentEvidenceBrowserBase;

export interface OpenedContentFullDeckEvidenceBrowser
  extends OpenedContentEvidenceBrowserBase {
  reviewSessionId: string;
}

export interface ReviewSessionResult {
  session: Record<string, unknown> & { review_session_id: string };
  snapshot_revision: number;
  selected_project_root: string;
}

export interface ToolContractMap {
  open_ai_ppt_browser_review: {
    input: { projectRoot: string; reviewType: "content" | "visual"; sourceVersion: string };
    output: BrowserReviewOpenResult;
  };
  get_content_sidebar_review_projection: {
    input: { projectRoot: string };
    output: ContentSidebarReviewProjection;
  };
  get_content_full_deck_review_projection: {
    input: { projectRoot: string; reviewSessionId: string };
    output: ContentFullDeckReviewProjection;
  };
  save_content_full_deck_page_decision: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      reviewSessionId: string;
      reviewBatchId: string;
      slideId: string;
      decision: V22ContentPageDecision;
      comment: string;
    };
    output: {
      page_completion: { slide_id: string; completed: boolean };
      review_progress: V22ContentReviewProgress;
      revision: number;
    };
  };
  submit_content_full_deck_review_batch: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      reviewSessionId: string;
      reviewBatchId: string;
    };
    output: {
      artifact_ref: string;
      follow_up_message: string;
      revision: number;
    };
  };
  save_content_page_decision: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewBatchId: string;
      slideId: string;
      decision: ContentPageDecision;
      comment: string;
    };
    output: SavedContentPageDecision;
  };
  submit_content_review_batch: {
    input: { projectRoot: string; expectedRevision: number; sourceVersion: string; reviewBatchId: string };
    output: SubmittedContentReviewBatch;
  };
  withdraw_content_review_batch: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewBatchId: string;
      reason: string;
    };
    output: WithdrawnContentReviewBatch;
  };
  open_content_evidence_browser: {
    input: {
      projectRoot: string;
      sourceVersion: string;
      slideId: string;
      evidenceId: string;
      materialRef: string;
    };
    output: OpenedLegacyContentEvidenceBrowser;
  };
  open_content_full_deck_evidence_browser: {
    input: {
      projectRoot: string;
      reviewSessionId: string;
      sourceVersion: string;
      slideId: string;
      evidenceId: string;
      materialRef: string;
    };
    output: OpenedContentFullDeckEvidenceBrowser;
  };
  save_review_marks: {
    input: {
      projectRoot?: string;
      expectedRevision: number;
      reviewType?: "content" | "visual";
      sourceVersion: string;
      marks: ReviewMark[];
    };
    output: { snapshot: { revision: number } };
  };
  submit_visual_anchor_feedback_batch: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewSessionId: string;
      feedback: AnchorRegionFeedback[];
    };
    output: {
      batch_ref: string;
      batch: AnchorFeedbackBatch;
      snapshot: { revision: number };
    };
  };
  save_visual_contract_review_marks: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewSessionId: string;
      marks: VisualContractReviewMark[];
    };
    output: {
      mark_set_ref: string;
      mark_set: VisualContractReviewMarkSet;
      snapshot: { revision: number };
    };
  };
  read_ai_ppt_project_asset: {
    input: { projectRoot: string; assetRef: string };
    output: {
      asset: { assetRef: string; mimeType: string; bytes: number; dataBase64: string };
    };
  };
  get_ai_ppt_project_status: {
    input: { projectRoot: string };
    output: { status: Record<string, unknown> & { status: string } };
  };
  open_or_resume_review_session: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      reviewType: "content-full-deck" | "visual-professional";
      targetArtifactRef: string;
      sourceVersion: string;
      targetRevision: number;
      openPolicy: "foreground-if-waiting" | "notify-only";
    };
    output: ReviewSessionResult;
  };
  record_review_host_open_receipt: {
    input: ReviewReceiptInput<"opened" | "failed" | "unavailable">;
    output: ReviewSessionResult;
  };
  record_review_host_notification_receipt: {
    input: ReviewReceiptInput<"sent" | "failed" | "unavailable">;
    output: ReviewSessionResult;
  };
  record_review_ai_receipt: {
    input: ReviewReceiptInput<"received" | "failed" | "unavailable">;
    output: ReviewSessionResult;
  };
}

interface ReviewReceiptInput<Result extends string> {
  projectRoot: string;
  expectedRevision: number;
  reviewSessionId: string;
  result: Result;
  receiptRef: string;
}

export function parseToolOutput<K extends keyof ToolContractMap>(
  name: K,
  value: unknown,
): ToolContractMap[K]["output"] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Host tool ${name} returned an invalid payload`);
  }
  return value as ToolContractMap[K]["output"];
}
