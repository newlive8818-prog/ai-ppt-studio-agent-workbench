import { createHash } from "node:crypto";

export const PUBLIC_TOOL_GROUP_COUNTS = Object.freeze({
  project: 15,
  content: 15,
  review: 4,
  visual: 3,
  "delivery-experience": 6,
});

const DESCRIPTOR_FIELDS = Object.freeze([
  "name",
  "group",
  "handler",
  "operation",
  "schema",
]);
const LOCAL_ASSET_TOOL = "read_ai_ppt_project_asset";

const rows = [
  ["create_ai_ppt_project", "project", "createProject", "create-project"],
  ["get_ai_ppt_project_snapshot", "project", "getSnapshot", "get-project-snapshot"],
  ["get_ai_ppt_project_status", "project", "getUserStatus", "get-project-user-status"],
  ["add_ai_ppt_material", "project", "addMaterial", "add-material"],
  ["save_ai_ppt_mission_draft", "project", "saveMission", "save-mission-draft"],
  ["confirm_ai_ppt_mission", "project", "confirmMission", "confirm-mission"],
  ["request_ai_ppt_agent_action", "project", "requestAgentAction", "request-agent-action"],
  ["submit_ai_ppt_human_decision", "project", "submitHumanDecision", "submit-human-decision"],
  ["commit_ai_ppt_artifact", "project", "commitArtifact", "commit-artifact"],
  ["confirm_ai_ppt_gate", "project", "confirmGate", "confirm-gate"],
  ["close_ai_ppt_project", "project", "closeProject", "close-project"],
  ["abort_ai_ppt_project", "project", "abortProject", "abort-project"],
  ["reopen_ai_ppt_scope", "project", "reopenScope", "reopen-scope"],
  ["set_ai_ppt_release_target_policy", "project", "setReleaseTargetPolicy", "set-release-target-policy"],
  ["read_ai_ppt_project_asset", "project", "readProjectAsset", null],
  ["build_presales_evidence_book", "content", "buildEvidenceBook", "build-presales-evidence-book"],
  ["build_customer_decision_context", "content", "buildDecisionContext", "build-customer-decision-context"],
  ["build_problem_solution_fit", "content", "buildProblemSolutionFit", "build-problem-solution-fit"],
  ["build_reading_deck_blueprint", "content", "buildReadingDeckBlueprint", "build-reading-deck-blueprint"],
  ["run_content_evidence_gate", "content", "runEvidenceGate", "run-content-evidence-gate"],
  ["run_content_presales_reading_gate", "content", "runPresalesReadingGate", "run-content-presales-reading-gate"],
  ["repair_reading_deck_blueprint", "content", "repairReadingDeckBlueprint", "repair-reading-deck-blueprint"],
  ["get_content_review_projection", "content", "getContentReviewProjection", "get-content-review-projection"],
  ["save_content_page_decision", "content", "saveContentPageDecision", "save-content-page-decision"],
  ["submit_content_review_batch", "content", "submitContentReviewBatch", "submit-content-review-batch"],
  ["withdraw_content_review_batch", "content", "withdrawContentReviewBatch", "withdraw-content-review-batch"],
  ["save_content_batch_revision_plan", "content", "saveContentRevisionPlan", "save-content-batch-revision-plan"],
  ["confirm_content_batch_revision_plan", "content", "confirmContentRevisionPlan", "confirm-content-batch-revision-plan"],
  ["create_content_batch_change_set", "content", "createContentChangeSet", "create-content-batch-change-set"],
  ["open_g0_review", "content", "openG0Review", "open-g0-review"],
  ["open_or_resume_review_session", "review", "openOrResumeReviewSession", "open-or-resume-review-session"],
  ["record_review_host_open_receipt", "review", "recordReviewHostOpen", "record-review-host-open"],
  ["record_review_host_notification_receipt", "review", "recordReviewHostNotification", "record-review-host-notification"],
  ["record_review_ai_receipt", "review", "recordReviewAiReceipt", "record-review-ai-receipt"],
  ["get_visual_review_projection", "visual", "getVisualReviewProjection", "get-visual-review-projection"],
  ["submit_visual_anchor_feedback_batch", "visual", "submitVisualAnchorBatch", "submit-visual-anchor-feedback-batch"],
  ["save_visual_contract_review_marks", "visual", "saveVisualContractMarks", "save-visual-contract-review-marks"],
  ["record_internal_gate", "delivery-experience", "recordInternalGate", "record-internal-gate"],
  ["get_delivery_status_projection", "delivery-experience", "getDeliveryStatus", "get-delivery-status-projection"],
  ["record_chat_delivery", "delivery-experience", "recordChatDelivery", "record-chat-delivery"],
  ["recommend_experience", "delivery-experience", "recommendExperience", "recommend-experience"],
  ["record_experience_application", "delivery-experience", "recordExperienceApplication", "record-experience-application"],
  ["summarize_project_experience", "delivery-experience", "summarizeProjectExperience", "summarize-project-experience"],
];

export const PUBLIC_TOOL_CATALOG = Object.freeze(
  rows.map(([name, group, handler, operation]) =>
    Object.freeze({ name, group, handler, operation, schema: name })),
);

export function assertPublicToolCatalog(catalog) {
  if (!Array.isArray(catalog) || !Object.isFrozen(catalog)) {
    throw new Error("Public tool catalog must be frozen");
  }
  const expectedTotal = Object.values(PUBLIC_TOOL_GROUP_COUNTS)
    .reduce((total, count) => total + count, 0);
  if (catalog.length !== expectedTotal) {
    throw new Error(
      `Public tool catalog group count mismatch: expected ${expectedTotal}, received ${catalog.length}`,
    );
  }

  const names = new Set();
  const handlers = new Set();
  const operations = new Set();
  const nullOperationTools = [];
  const groupCounts = Object.fromEntries(
    Object.keys(PUBLIC_TOOL_GROUP_COUNTS).map((group) => [group, 0]),
  );

  for (const descriptor of catalog) {
    if (!descriptor || !Object.isFrozen(descriptor)) {
      throw new Error("Every public tool descriptor must be frozen");
    }
    if (JSON.stringify(Object.keys(descriptor)) !== JSON.stringify(DESCRIPTOR_FIELDS)) {
      throw new Error("Public tool descriptor fields do not match the fixed contract");
    }
    if (typeof descriptor.name !== "string" || !descriptor.name.trim()) {
      throw new Error("Public tool name must be a non-empty string");
    }
    if (names.has(descriptor.name)) {
      throw new Error(`Public tool catalog has duplicate tool name: ${descriptor.name}`);
    }
    names.add(descriptor.name);

    if (!Object.hasOwn(PUBLIC_TOOL_GROUP_COUNTS, descriptor.group)) {
      throw new Error(`Public tool catalog has unsupported group: ${descriptor.group}`);
    }
    groupCounts[descriptor.group] += 1;

    if (descriptor.schema !== descriptor.name) {
      throw new Error(`Public tool schema identity mismatch: ${descriptor.name}`);
    }
    if (typeof descriptor.handler !== "string" || !descriptor.handler.trim()) {
      throw new Error(`Public tool handler identity is invalid: ${descriptor.name}`);
    }
    if (handlers.has(descriptor.handler)) {
      throw new Error(`Public tool catalog has duplicate handler: ${descriptor.handler}`);
    }
    handlers.add(descriptor.handler);

    if (descriptor.operation === null) {
      if (descriptor.name !== LOCAL_ASSET_TOOL) {
        throw new Error(`Only the local-asset operation may be null: ${descriptor.name}`);
      }
      nullOperationTools.push(descriptor.name);
      continue;
    }
    if (typeof descriptor.operation !== "string" || !descriptor.operation.trim()) {
      throw new Error(`Public tool operation identity is invalid: ${descriptor.name}`);
    }
    if (operations.has(descriptor.operation)) {
      throw new Error(`Public tool catalog has duplicate operation: ${descriptor.operation}`);
    }
    operations.add(descriptor.operation);
  }

  for (const [group, expectedCount] of Object.entries(PUBLIC_TOOL_GROUP_COUNTS)) {
    if (groupCounts[group] !== expectedCount) {
      throw new Error(
        `Public tool catalog group count mismatch for ${group}: expected ${expectedCount}, received ${groupCounts[group]}`,
      );
    }
  }
  if (
    nullOperationTools.length !== 1
    || nullOperationTools[0] !== LOCAL_ASSET_TOOL
  ) {
    throw new Error("Public tool catalog local-asset operation contract is incomplete");
  }
  return catalog;
}

assertPublicToolCatalog(PUBLIC_TOOL_CATALOG);

export const PUBLIC_TOOL_CATALOG_SHA256 = createHash("sha256")
  .update(JSON.stringify(PUBLIC_TOOL_CATALOG))
  .digest("hex");

export function registerCatalogGroup(server, group, schemas, handlers) {
  if (!Object.hasOwn(PUBLIC_TOOL_GROUP_COUNTS, group)) {
    throw new Error(`Unknown public tool group: ${group}`);
  }
  const tools = PUBLIC_TOOL_CATALOG.filter((item) => item.group === group);
  const expectedSchemas = tools.map((tool) => tool.schema).sort();
  const actualSchemas = Object.keys(schemas).sort();
  if (JSON.stringify(actualSchemas) !== JSON.stringify(expectedSchemas)) {
    throw new Error(
      `Schema contract mismatch for ${group}: expected ${expectedSchemas.join(", ")}; received ${actualSchemas.join(", ")}`,
    );
  }
  for (const tool of tools) {
    const schema = schemas[tool.schema];
    const handler = handlers[tool.handler];
    if (!schema || typeof handler !== "function") {
      throw new Error(`Incomplete public tool contract: ${tool.name}`);
    }
    server.registerTool(tool.name, schema, (input, extra) =>
      handler(input, tool.operation, extra));
  }
}
