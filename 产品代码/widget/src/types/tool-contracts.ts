import type { ContentReviewProjection } from "./content-review";
import type {
  AnchorFeedbackBatch,
  AnchorRegionFeedback,
  VisualContractReviewMark,
  VisualContractReviewMarkSet,
  VisualReviewProjection,
} from "./visual-review";

export interface ProjectUserStatus {
  status: "AI 正在处理" | "需要你处理" | "成果已可查看" | "任务受阻";
  object_type:
    | "content-review"
    | "visual-review"
    | "project-experience-retrospective"
    | "gate"
    | "delivery"
    | "runtime-task";
  object_ref: string;
  reason: string;
  next_action: string;
  revision: number;
}

export interface ToolContractMap {
  get_ai_ppt_project_status: {
    input: { projectRoot: string };
    output: { status: ProjectUserStatus };
  };
  read_ai_ppt_project_asset: {
    input: { projectRoot: string; assetRef: string };
    output: { asset: { assetRef: string; mimeType: string; dataBase64: string } };
  };
  open_or_resume_review_session: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      reviewType: "content-full-deck" | "visual-professional";
      targetArtifactRef: string;
      sourceVersion: string;
      sourceRevision: number;
      openPolicy: "foreground-if-waiting" | "notify-only";
    };
    output: {
      session_ref: string;
      session: Record<string, unknown>;
      snapshot: { revision: number };
    };
  };
  get_content_review_projection: {
    input: { projectRoot: string; reviewSessionId: string };
    output: { review: ContentReviewProjection };
  };
  get_visual_review_projection: {
    input: { projectRoot: string; reviewSessionId: string };
    output: { review: VisualReviewProjection };
  };
  save_content_page_decision: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewSessionId: string;
      slideId: string;
      decision: "approved" | "modify" | "evidence" | "merge-or-delete";
      comment: string;
    };
    output: {
      decision_ref: string;
      decision: Record<string, unknown>;
      snapshot: { revision: number };
    };
  };
  submit_content_review_batch: {
    input: {
      projectRoot: string;
      expectedRevision: number;
      sourceVersion: string;
      reviewSessionId: string;
    };
    output: {
      batch_ref: string;
      batch: Record<string, unknown>;
      snapshot: { revision: number };
    };
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
}

export function parseToolOutput<K extends keyof ToolContractMap>(
  _name: K,
  value: unknown,
): ToolContractMap[K]["output"] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Host tool returned an invalid object payload");
  }
  return value as ToolContractMap[K]["output"];
}
