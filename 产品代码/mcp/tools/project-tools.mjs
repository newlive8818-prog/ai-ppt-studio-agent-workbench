import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const projectRoot = { projectRoot: z.string().trim().optional() };
const revision = { ...projectRoot, expectedRevision: z.number().int().nonnegative() };
const contract = (title, inputSchema, readOnly = false) => ({
  title,
  description: `${title}. Uses the authoritative Python runtime and returns data only.`,
  inputSchema,
  annotations: {
    readOnlyHint: readOnly,
    destructiveHint: false,
    idempotentHint: readOnly,
    openWorldHint: false,
  },
});

const actionTypes = [
  "design-deck-system",
  "design-slide-visuals", "build-native-first", "generate-image-assets",
  "review-visual-aesthetic", "review-visual-engineering", "verify-target-render",
  "coordinate-delivery",
];

const schemas = {
  create_ai_ppt_project: contract("Create AI PPT project", {
    name: z.string().trim().min(1),
    projectId: z.string().trim().min(1).optional(),
  }),
  get_ai_ppt_project_snapshot: contract("Get project snapshot", projectRoot, true),
  get_ai_ppt_project_status: contract("Get project user status", projectRoot, true),
  add_ai_ppt_material: contract("Add project material", {
    ...revision,
    materialType: z.enum(["text", "url", "bytes"]),
    value: z.string().optional(),
    dataBase64: z.string().optional(),
    label: z.string().optional(),
    filename: z.string().optional(),
    mimeType: z.string().optional(),
  }),
  save_ai_ppt_mission_draft: contract("Save Mission draft", {
    ...revision,
    missionDraft: z.record(z.string(), z.unknown()),
  }),
  confirm_ai_ppt_mission: contract("Confirm Mission", {
    ...revision,
    missionDraftRef: z.string().trim().min(1),
    materialMode: z.enum(["materials-provided", "no-materials-confirmed"]),
    materialInventoryRef: z.string().trim().optional(),
    userActionRef: z.string().trim().optional(),
    userMessageRef: z.string().trim().optional(),
    missionSummary: z.object({
      topic: z.string().trim().min(1),
      primaryAudience: z.string().trim().min(1),
      desiredJudgmentOrAction: z.string().trim().min(1),
      materialSummary: z.string().trim().min(1),
    }).optional(),
  }),
  request_ai_ppt_agent_action: contract("Request governed Agent action", {
    ...revision,
    actionType: z.enum(actionTypes),
    targetRefs: z.array(z.string().trim().min(1)),
    instructions: z.string().optional(),
  }),
  submit_ai_ppt_human_decision: contract("Submit human decision", {
    ...revision,
    targetRef: z.string().trim().min(1),
    choice: z.string().trim().min(1),
    feedback: z.string().optional(),
  }),
  commit_ai_ppt_artifact: contract("Commit governed non-content artifact", {
    ...revision,
    commandId: z.string().trim().optional(),
    taskId: z.string().trim().optional(),
    kind: z.enum([
      "visual-brief", "concept-set", "visual-contract", "native-anchor-set",
      "delivery", "target-render-evidence",
    ]),
    payload: z.record(z.string(), z.unknown()),
  }),
  confirm_ai_ppt_gate: contract("Confirm user gate", {
    ...revision,
    gate: z.enum(["G0", "G3", "G4"]),
    userMessageRef: z.string().trim().min(1).optional(),
  }),
  close_ai_ppt_project: contract("Close AI PPT project", {
    ...revision,
    userMessageRef: z.string().trim().min(1),
    completedAt: z.string().trim().min(1),
  }),
  abort_ai_ppt_project: contract("Abort AI PPT project", {
    ...revision,
    userMessageRef: z.string().trim().min(1),
    reason: z.string().trim().min(1),
    completedAt: z.string().trim().min(1),
  }),
  reopen_ai_ppt_scope: contract("Reopen governed scope", {
    ...revision,
    gate: z.enum(["G0", "G1", "G2", "G3", "G4"]),
    reason: z.string().trim().min(1),
  }),
  set_ai_ppt_release_target_policy: contract("Set release target policy", {
    ...revision,
    policyId: z.literal("v1.6-macos-powerpoint"),
  }),
  read_ai_ppt_project_asset: contract("Read project asset", {
    projectRoot: z.string().trim().min(1),
    assetRef: z.string().trim().min(1),
  }, true),
};

export function registerProjectTools(server, handlers) {
  registerCatalogGroup(server, "project", schemas, handlers);
}
