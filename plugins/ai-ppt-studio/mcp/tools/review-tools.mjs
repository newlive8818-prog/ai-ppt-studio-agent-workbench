import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const base = {
  projectRoot: z.string().trim().min(1),
  expectedRevision: z.number().int().nonnegative(),
  reviewType: z.enum(["content-full-deck", "visual-professional"]),
};
const receipt = (title) => ({
  title,
  description: `${title}. The receipt must already exist in the authoritative runtime.`,
  inputSchema: { ...base, receiptRef: z.string().trim().min(1) },
  annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
});
const artifactReference = (kind) => z.string().trim().regex(
  new RegExp(`^artifact://${kind}/[a-f0-9]{64}$`),
);
const savedVisualArtifactRef = z.union([
  artifactReference("visual-anchor-feedback-batch"),
  artifactReference("visual-contract-review-mark-set"),
]);
const boundReceipt = (title, receiptKind) => ({
  title,
  description: `${title}. Visual review receipts must bind the exact current ReviewSession, source version, and saved visual artifact.`,
  inputSchema: {
    ...base,
    reviewSessionId: z.string().trim().min(1).optional(),
    sourceVersion: z.string().trim().min(1).optional(),
    savedArtifactRef: savedVisualArtifactRef.optional(),
    receiptRef: artifactReference(receiptKind),
  },
  annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
});
const schemas = {
  open_or_resume_review_session: {
    title: "Open or resume review session",
    description: "Create or resume the only current source-bound professional ReviewSession.",
    inputSchema: {
      ...base,
      targetArtifactRef: z.string().trim().min(1),
      sourceVersion: z.string().trim().min(1),
      sourceRevision: z.number().int().nonnegative(),
      openPolicy: z.enum(["foreground-if-waiting", "notify-only"]),
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  record_review_host_open_receipt: receipt("Record review host-open receipt"),
  record_review_host_notification_receipt: boundReceipt(
    "Record review notification receipt",
    "review-host-notification-receipt",
  ),
  record_review_ai_receipt: boundReceipt(
    "Record review AI receipt",
    "review-ai-receipt",
  ),
};

export function registerReviewTools(server, handlers) {
  registerCatalogGroup(server, "review", schemas, handlers);
}
