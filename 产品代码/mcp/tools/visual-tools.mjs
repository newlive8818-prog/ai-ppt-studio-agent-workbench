import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const base = {
  projectRoot: z.string().trim().min(1),
  expectedRevision: z.number().int().nonnegative(),
  sourceVersion: z.string().trim().min(1),
};
const contract = (title, inputSchema, readOnly = false) => ({
  title,
  description: title,
  inputSchema,
  annotations: { readOnlyHint: readOnly, destructiveHint: false, idempotentHint: readOnly, openWorldHint: false },
});
const normalizedRegion = z.object({
  x: z.number().min(0).max(1),
  y: z.number().min(0).max(1),
  width: z.number().min(0.02).max(1),
  height: z.number().min(0.02).max(1),
}).strict().superRefine((region, issue) => {
  if (region.x + region.width > 1 || region.y + region.height > 1) {
    issue.addIssue({ code: "custom", message: "Region must stay inside the slide" });
  }
});
const feedback = z.object({
  feedback_id: z.string().trim().min(1),
  anchor_slide_id: z.string().trim().min(1),
  anchor_artifact_ref: z.string().trim().min(1),
  normalized_region: normalizedRegion,
  comment: z.string().trim().min(1),
  order: z.number().int().positive(),
  visual_source_version: z.string().trim().min(1),
  revision: z.number().int().nonnegative(),
  created_at: z.string().datetime({ offset: true }),
  created_by: z.literal("user"),
}).strict();
const mark = z.object({
  mark_id: z.string().trim().min(1),
  target_type: z.enum(["contract-field", "text-range"]),
  slide_id: z.string(),
  deck_section_id: z.string(),
  target_key: z.string().trim().min(1),
  selected_text: z.string(),
  context_before: z.string(),
  context_after: z.string(),
  comment: z.string().trim().min(1),
  visual_contract_ref: z.string().trim().min(1),
  source_version: z.string().trim().min(1),
  revision: z.number().int().nonnegative(),
  created_at: z.string().trim().min(1),
  created_by: z.string().trim().min(1),
}).strict().superRefine((value, issue) => {
  if (!value.slide_id.trim() && !value.deck_section_id.trim()) {
    issue.addIssue({ code: "custom", message: "A mark needs a slide or deck section" });
  }
  if (value.target_type === "text-range" && !value.selected_text.trim()) {
    issue.addIssue({ code: "custom", message: "Text-range marks need selected text" });
  }
});
const schemas = {
  get_visual_review_projection: contract("Get visual review projection", {
    projectRoot: z.string().trim().min(1),
    reviewSessionId: z.string().trim().min(1),
  }, true),
  submit_visual_anchor_feedback_batch: contract("Submit visual anchor feedback batch", {
    ...base,
    reviewSessionId: z.string().trim().min(1),
    feedback: z.array(feedback).min(1),
  }),
  save_visual_contract_review_marks: contract("Save visual contract review marks", {
    ...base,
    reviewSessionId: z.string().trim().min(1),
    marks: z.array(mark).min(1),
  }),
};

export function registerVisualTools(server, handlers) {
  registerCatalogGroup(server, "visual", schemas, handlers);
}
