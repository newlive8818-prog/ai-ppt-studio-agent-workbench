import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const base = {
  projectRoot: z.string().trim().min(1),
  expectedRevision: z.number().int().nonnegative(),
};
const source = { ...base, sourceVersion: z.string().trim().min(1) };
const contract = (title, inputSchema, readOnly = false) => ({
  title,
  description: `${title}. Uses one evidence-first v2.2 content contract.`,
  inputSchema,
  annotations: { readOnlyHint: readOnly, destructiveHint: false, idempotentHint: readOnly, openWorldHint: false },
});
const build = (title) => contract(title, {
  ...base,
  inputRefs: z.array(z.string().trim().min(1)).optional(),
  instructions: z.string().optional(),
  payload: z.record(z.string(), z.unknown()),
});

const schemas = {
  build_presales_evidence_book: build("Build presales evidence book"),
  build_customer_decision_context: build("Build customer decision context"),
  build_problem_solution_fit: build("Build problem solution fit"),
  build_reading_deck_blueprint: build("Build reading deck blueprint"),
  run_content_evidence_gate: contract("Run content evidence gate", {
    ...source,
    semanticCheckResults: z.array(z.record(z.string(), z.unknown())),
    reviewerMode: z.enum(["independent-agent", "isolated-review-task"]),
    independentAgentInstanceId: z.string().trim().optional(),
    outputRef: z.string().trim().optional(),
  }),
  run_content_presales_reading_gate: contract("Run presales reading gate", {
    ...source,
    semanticCheckResults: z.array(z.record(z.string(), z.unknown())),
    reviewerMode: z.enum(["independent-agent", "isolated-review-task"]),
    independentAgentInstanceId: z.string().trim().optional(),
    outputRef: z.string().trim().optional(),
  }),
  repair_reading_deck_blueprint: contract("Repair reading deck blueprint", {
    ...source,
    repairRequirements: z.array(z.record(z.string(), z.unknown())).min(1),
    payload: z.record(z.string(), z.unknown()),
  }),
  get_content_review_projection: contract("Get content review projection", {
    projectRoot: z.string().trim().min(1),
    reviewSessionId: z.string().trim().min(1),
  }, true),
  save_content_page_decision: contract("Save content page decision", {
    ...source,
    reviewSessionId: z.string().trim().min(1),
    slideId: z.string().trim().min(1),
    decision: z.enum(["approved", "modify", "evidence", "merge-or-delete"]),
    comment: z.string(),
  }),
  submit_content_review_batch: contract("Submit content review batch", {
    ...source,
    reviewSessionId: z.string().trim().min(1),
  }),
  withdraw_content_review_batch: contract("Withdraw content review batch", {
    ...source,
    reviewSessionId: z.string().trim().min(1),
  }),
  save_content_batch_revision_plan: contract("Save content revision plan", {
    ...source,
    batchRef: z.string().trim().min(1),
    plan: z.record(z.string(), z.unknown()),
  }),
  confirm_content_batch_revision_plan: contract("Confirm content revision plan", {
    ...source,
    planRef: z.string().trim().min(1),
    userMessageRef: z.string().trim().min(1),
  }),
  create_content_batch_change_set: contract("Create content change set", {
    ...source,
    planRef: z.string().trim().min(1),
    confirmationRef: z.string().trim().min(1),
  }),
  open_content_evidence_browser: contract("Open content evidence browser", {
    projectRoot: z.string().trim().min(1),
    reviewSessionId: z.string().trim().min(1),
    evidenceRef: z.string().trim().min(1),
  }, true),
  open_g0_review: contract("Open G0 content review", base),
};

export function registerContentTools(server, handlers) {
  registerCatalogGroup(server, "content", schemas, handlers);
}
