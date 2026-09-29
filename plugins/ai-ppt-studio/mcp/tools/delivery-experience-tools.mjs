import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const base = { projectRoot: z.string().trim().min(1) };
const revision = { ...base, expectedRevision: z.number().int().nonnegative() };
const contract = (title, inputSchema, readOnly = false) => ({
  title,
  description: title,
  inputSchema,
  annotations: { readOnlyHint: readOnly, destructiveHint: false, idempotentHint: readOnly, openWorldHint: false },
});
const schemas = {
  record_internal_gate: contract("Record internal gate", {
    ...revision,
    gate: z.enum(["G1", "G2"]),
    reviewerRole: z.string().trim().min(1),
    acceptanceRecordRefs: z.array(z.string().trim().min(1)).min(1),
  }),
  get_delivery_status_projection: contract("Get delivery status", base, true),
  record_chat_delivery: contract("Record chat delivery", {
    ...revision,
    deliveryType: z.literal("pptx"),
    artifactRefs: z.array(z.string().trim().min(1)).min(1),
    messageRef: z.string().trim().min(1),
    sendStatus: z.enum(["sent", "failed"]),
    retryOf: z.string().trim().optional(),
  }),
  recommend_experience: contract("Recommend experience", {
    ...base,
    typeSignature: z.string().trim().min(1),
    domain: z.enum(["content", "visual"]),
    applicability: z.record(z.string(), z.unknown()),
    topN: z.number().int().positive().optional(),
  }, true),
  record_experience_application: contract("Record experience application", {
    ...revision,
    experienceRef: z.string().trim().min(1),
    targetProjectId: z.string().trim().min(1),
    targetTypeSignature: z.string().trim().min(1),
    context: z.record(z.string(), z.unknown()),
    evidenceRefs: z.array(z.string().trim().min(1)),
    appliedAt: z.string().trim().min(1),
    explicitValidation: z.boolean().optional(),
  }),
  summarize_project_experience: contract("Summarize project experience", {
    ...revision,
    terminalStatus: z.enum(["completed", "closed", "aborted"]),
    payload: z.record(z.string(), z.unknown()),
    startedAt: z.string().trim().min(1),
    finishedAt: z.string().trim().min(1),
    retryable: z.boolean().optional(),
  }),
};

export function registerDeliveryExperienceTools(server, handlers) {
  registerCatalogGroup(server, "delivery-experience", schemas, handlers);
}
