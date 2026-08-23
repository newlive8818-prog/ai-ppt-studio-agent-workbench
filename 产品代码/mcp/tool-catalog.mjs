const entries = [
  ["create_ai_ppt_project", "project", "createProjectSchema", "createProject"],
  ["get_ai_ppt_project_snapshot", "project", "projectSchema", "getSnapshot"],
  ["get_ai_ppt_project_status", "project", "projectSchema", "getUserStatus"],
  ["get_ai_ppt_sidebar_projection", "project", "sidebarProjectionSchema", "getSidebarProjection"],
  ["add_ai_ppt_material", "project", "addMaterialSchema", "addMaterial"],
  ["save_ai_ppt_mission_draft", "project", "missionDraftSchema", "saveMissionDraft"],
  ["confirm_ai_ppt_mission", "project", "missionConfirmationSchema", "confirmMission"],
  ["request_ai_ppt_agent_action", "project", "agentActionSchema", "requestAgentAction"],
  ["submit_ai_ppt_human_decision", "project", "humanDecisionSchema", "submitHumanDecision"],
  ["commit_ai_ppt_artifact", "project", "artifactSchema", "commitArtifact"],
  ["confirm_ai_ppt_gate", "project", "gateConfirmationSchema", "confirmGate"],
  ["reopen_ai_ppt_scope", "project", "reopenScopeSchema", "reopenScope"],
  ["record_internal_gate", "project", "internalGateSchema", "recordInternalGate"],
  ["read_ai_ppt_project_asset", "project", "projectAssetSchema", "readProjectAsset"],
  ["get_content_sidebar_review_projection", "content", "projectSchema", "getLegacyContentReviewProjection"],
  ["save_content_page_decision", "content", "pageDecisionSchema", "savePageDecision"],
  ["submit_content_review_batch", "content", "contentReviewBatchSchema", "submitReviewBatch"],
  ["withdraw_content_review_batch", "content", "withdrawReviewBatchSchema", "withdrawReviewBatch"],
  ["save_content_batch_revision_plan", "content", "contentRevisionPlanSchema", "saveRevisionPlan"],
  ["confirm_content_batch_revision_plan", "content", "confirmRevisionPlanSchema", "confirmRevisionPlan"],
  ["create_content_batch_change_set", "content", "contentChangeSetSchema", "createChangeSet"],
  ["open_ai_ppt_browser_review", "review", "legacyBrowserReviewSchema", "openLegacyBrowserReview"],
  ["open_or_resume_review_session", "review", "reviewSessionSchema", "openOrResumeReviewSession"],
  ["record_review_host_open_receipt", "review", "reviewReceiptSchema", "recordHostOpenReceipt"],
  ["record_review_host_notification_receipt", "review", "reviewReceiptSchema", "recordHostNotificationReceipt"],
  ["record_review_ai_receipt", "review", "reviewReceiptSchema", "recordAiReceipt"],
  ["open_content_evidence_browser", "review", "contentEvidenceSchema", "openContentEvidence"],
  ["save_review_marks", "visual", "legacyReviewMarksSchema", "saveLegacyReviewMarks"],
  ["get_delivery_status_projection", "delivery-experience", "projectSchema", "getDeliveryStatus"],
  ["record_chat_delivery", "delivery-experience", "chatDeliverySchema", "recordChatDelivery"],
  ["set_ai_ppt_release_target_policy", "delivery-experience", "releasePolicySchema", "setReleasePolicy"],
];

export const PUBLIC_TOOL_CATALOG = Object.freeze(
  entries.map(([name, group, schema, handler]) =>
    Object.freeze({ name, group, schema, handler }),
  ),
);

export const PUBLIC_TOOL_NAMES = Object.freeze(
  PUBLIC_TOOL_CATALOG.map((tool) => tool.name),
);
