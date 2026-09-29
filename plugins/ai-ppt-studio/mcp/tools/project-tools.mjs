import { z } from "zod";

import { registerCatalogGroup } from "../tool-catalog.mjs";

const projectRoot = { projectRoot: z.string().trim().optional() };
const revision = { ...projectRoot, expectedRevision: z.number().int().nonnegative() };
const contract = (title, inputSchema, readOnly = false, openWorld = false) => ({
  title,
  description: `${title}. Uses the authoritative Python runtime and returns data only.`,
  inputSchema,
  annotations: {
    readOnlyHint: readOnly,
    destructiveHint: false,
    idempotentHint: readOnly,
    openWorldHint: openWorld,
  },
});

const actionTypes = [
  "design-deck-system",
  "design-slide-visuals", "build-native-first", "build-native-diagnostic", "generate-image-assets", "generate-slide-images",
  "review-visual-aesthetic", "review-visual-engineering", "verify-target-render",
  "coordinate-delivery",
];

const schemas = {
  create_ai_ppt_project: contract("Create AI PPT project", {
    name: z.string().trim().min(1),
    projectId: z.string().trim().min(1).optional(),
  }),
  get_ai_ppt_project_snapshot: contract("Get project snapshot", {
    ...projectRoot,
    includeImage2Preflight: z.boolean().optional().describe(
      "Opt in to a read-only local Image 2 protocol probe. Never authenticates or generates an image."),
  }, true),
  get_ai_ppt_project_status: contract("Get project user status", projectRoot, true),
  add_ai_ppt_material: contract("Add project material", z.object({
    ...revision,
    materialType: z.enum(["text", "url", "bytes", "finding"]),
    value: z.string().optional(),
    dataBase64: z.string().optional(),
    label: z.string().optional(),
    filename: z.string().optional(),
    mimeType: z.string().optional(),
    materialInventoryRef: z.string().min(1).optional(),
    sourceId: z.string().min(1).optional(),
    sourceSha256: z.string().regex(/^[0-9a-f]{64}$/).optional(),
    sourceLocation: z.discriminatedUnion("kind", [
      z.object({ kind: z.literal("whole-source") }).strict(),
      z.object({ kind: z.literal("text-range"), start: z.number().int().nonnegative(), end: z.number().int().positive() }).strict(),
      z.object({ kind: z.literal("image-region"), x: z.number().int().nonnegative(), y: z.number().int().nonnegative(), width: z.number().int().positive(), height: z.number().int().positive() }).strict(),
      z.object({ kind: z.literal("page"), page: z.number().int().positive() }).strict(),
      z.object({ kind: z.literal("object"), page: z.number().int().positive(), object_id: z.string().min(1) }).strict(),
      z.object({ kind: z.literal("table-range"), page: z.number().int().positive(), object_id: z.string().min(1), row_start: z.number().int().nonnegative(), row_end: z.number().int().positive(), col_start: z.number().int().nonnegative(), col_end: z.number().int().positive() }).strict(),
    ]).optional(),
    contentKind: z.enum(["text", "image"]).optional(),
    exclusionMode: z.enum(["scope", "image-content"]).optional(),
  }).strict().superRefine((input, context) => {
    const findingFields = ["materialInventoryRef", "sourceId", "sourceSha256", "sourceLocation", "contentKind", "exclusionMode"];
    const importFields = ["value", "dataBase64", "label", "filename", "mimeType"];
    const finding = input.materialType === "finding";
    for (const key of finding ? importFields : findingFields) {
      if (Object.hasOwn(input, key)) context.addIssue({ code: "custom", path: [key], message: "Field belongs to the other material alternative" });
    }
    if (finding) {
      for (const key of ["projectRoot", ...findingFields]) {
        if (input[key] === undefined || input[key] === "") context.addIssue({ code: "custom", path: [key], message: "Finding field is required" });
      }
      if (input.exclusionMode === "image-content" && input.contentKind !== "image") context.addIssue({ code: "custom", path: ["exclusionMode"], message: "image-content requires an image finding" });
      const selector = input.sourceLocation;
      for (const [start, end] of [["start", "end"], ["row_start", "row_end"], ["col_start", "col_end"]]) {
        if (selector && start in selector && selector[start] >= selector[end]) context.addIssue({ code: "custom", path: ["sourceLocation", end], message: "Source range must be nonempty and increasing" });
      }
    }
  })),
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
    generationIntent: z.enum(["new", "recover"]).optional().describe(
      "Image generation only: recover queries the original request without sending; new expresses an explicit new design intent. Omit both generation fields for a stable default request."),
    generationRequestId: z.string().regex(/^(?!active$)[A-Za-z0-9_-]{1,128}$/).optional().describe(
      "Required with new or recover. Reuse the exact ID for retries; use a fresh ID only for an explicitly requested new design. Recovery can use targetRefs=[] and needs no current adapter or authorization."),
  }, false, true),
  submit_ai_ppt_human_decision: contract("Submit human decision", {
    ...revision,
    targetRef: z.string().trim().min(1),
    choice: z.string().trim().min(1),
    feedback: z.string().optional(),
    userMessageRef: z.string().trim().min(1).optional(),
    confirmationMode: z.enum(["verified-message-only", "allow-native"]).optional().describe(
      "Image-led only: verified-message-only never opens a form when a trusted verifier or message is unavailable. The legacy default allow-native is not permission to request another confirmation."),
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
