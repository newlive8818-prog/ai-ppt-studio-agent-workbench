import type { AnchorFeedbackBatch, VisualContractReviewMarkSet } from "../types/visual-review";

export interface VisualReceiptFacts {
  readonly hostNotificationStatus: AnchorFeedbackBatch["host_notification_status"] & VisualContractReviewMarkSet["host_notification_status"];
  readonly aiReceiptStatus: AnchorFeedbackBatch["ai_receipt_status"] & VisualContractReviewMarkSet["ai_receipt_status"];
}

export const PERSISTENCE_ONLY_VISUAL_SAVE_FACTS: VisualReceiptFacts = Object.freeze({
  hostNotificationStatus: "unavailable",
  aiReceiptStatus: "unverified",
});

export function deriveVisualReceiptFacts(value: {
  host_notification_status: unknown;
  ai_receipt_status: unknown;
}): VisualReceiptFacts | null {
  const hostNotificationStatus = value.host_notification_status === "sent"
    ? "sent"
    : value.host_notification_status === "failed"
      ? "failed"
      : value.host_notification_status === "not-requested" || value.host_notification_status === "unavailable"
        ? "unavailable"
        : null;
  const aiReceiptStatus = value.ai_receipt_status === "received"
    ? "received"
    : value.ai_receipt_status === "failed"
      ? "rejected"
      : value.ai_receipt_status === "pending" || value.ai_receipt_status === "unverified"
        ? "unverified"
        : null;
  return hostNotificationStatus && aiReceiptStatus
    ? { hostNotificationStatus, aiReceiptStatus }
    : null;
}
