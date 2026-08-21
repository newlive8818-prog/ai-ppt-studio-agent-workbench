import { createHash } from "node:crypto";

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
  ["open_content_evidence_browser", "content", "openContentEvidenceBrowser", "open-content-evidence-browser"],
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

export const PUBLIC_TOOL_CATALOG_SHA256 = createHash("sha256")
  .update(JSON.stringify(PUBLIC_TOOL_CATALOG))
  .digest("hex");

export function registerCatalogGroup(server, group, schemas, handlers) {
  for (const tool of PUBLIC_TOOL_CATALOG.filter((item) => item.group === group)) {
    const schema = schemas[tool.schema];
    const handler = handlers[tool.handler];
    if (!schema || typeof handler !== "function") {
      throw new Error(`Incomplete public tool contract: ${tool.name}`);
    }
    server.registerTool(tool.name, schema, (input, extra) =>
      handler(input, tool.operation, extra));
  }
}
