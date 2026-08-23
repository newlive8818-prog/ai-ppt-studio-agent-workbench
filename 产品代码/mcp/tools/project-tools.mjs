import { z } from "zod";

export function registerProjectTools(toolContext) {
  const {
    server, projectSchema, invokeBridge, invokeForTool, requestForProject,
    textResult, toolErrorResult, readProjectAssetFn, hostSidebarAdapter,
    confirmationAuthority, confirmationVerifier, requestHostMissionConfirmation,
    requestHostGateConfirmation,
  } = toolContext;
server.registerTool(
    "create_ai_ppt_project",
    {
      title: "Create AI PPT Project",
      description:
        "Create one managed schema 3 reading-first presales project. Project files are written only below the configured AI-PPT-Workspace runtime root.",
      inputSchema: {
        name: z.string().trim().min(1),
        projectId: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        operation: "create-project",
        name: input.name,
        project_id: input.projectId || "",
      });
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      return textResult(
        `已创建 schema 3 项目“${payload.snapshot.project.name}”，revision ${payload.snapshot.revision}。`,
        { snapshot: payload.snapshot },
      );
    },
  );

server.registerTool(
    "get_ai_ppt_project_snapshot",
    {
      title: "Get AI PPT Project Snapshot",
      description:
        "Read the latest compact project cognition, gate, artifact, and decision projection. Omit projectRoot to use the most recently created managed project.",
      inputSchema: projectSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-snapshot", input),
      );
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      const snapshot = payload.snapshot;
      return textResult(
        `已读取 AI PPT 项目“${snapshot.project.name}”，revision ${snapshot.revision}。`,
        { snapshot },
      );
    },
  );

server.registerTool(
    "get_ai_ppt_project_status",
    {
      title: "Get AI PPT Project User Status",
      description:
        "Read the single authoritative user-facing project status without creating or modifying a review session.",
      inputSchema: { projectRoot: z.string().trim().min(1) },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-user-status", input),
      );
      if (!outcome.ok) return outcome.result;
      return textResult(
        `当前项目状态：${outcome.payload.status.status}。`,
        outcome.payload,
      );
    },
  );

server.registerTool(
    "get_ai_ppt_sidebar_projection",
    {
      title: "Get AI PPT Sidebar Projection",
      description:
        "Read the compact five-space projection for a real Codex sidebar host. This is a pure data tool and never attaches a chat UI template.",
      inputSchema: {
        ...projectSchema,
        initialSpace: z
          .enum(["overview", "materials", "blueprint", "visual", "delivery"])
          .optional(),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input = {}) => {
      const outcome = await invokeForTool(
        invokeBridge,
        requestForProject("get-project-snapshot", input),
      );
      if (!outcome.ok) return outcome.result;
      const projection = {
        project: outcome.payload.snapshot.project,
        revision: outcome.payload.snapshot.revision,
        initialSpace: input.initialSpace || "overview",
        workspace: outcome.payload.snapshot.workspace,
        missionDraftRef: outcome.payload.snapshot.missionDraftRef || "",
        missionConfirmationRef:
          outcome.payload.snapshot.missionConfirmationRef || "",
        materialMode: outcome.payload.snapshot.materialMode || "unconfirmed",
        contentIdentityMode:
          outcome.payload.snapshot.contentIdentityMode || "blocked",
      };
      if (!hostSidebarAdapter) {
        return toolErrorResult({
          code: "HOST_SIDEBAR_UNAVAILABLE",
          message:
            "当前 Codex 宿主未提供可验证的持久侧边栏入口；聊天不会渲染替代 Widget。",
          details: { projection },
        });
      }
      return textResult(
        `已读取“${projection.project.name}”的侧边栏投影，revision ${projection.revision}。`,
        { projection },
      );
    },
  );

server.registerTool(
    "save_ai_ppt_mission_draft",
    {
      title: "Save AI PPT Mission Draft",
      description:
        "Save an AI-authored MissionDraft. Complete required fields become confirmable but this tool never confirms the mission.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        missionDraft: z.record(z.string(), z.unknown()),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("save-mission-draft", input),
        expected_revision: input.expectedRevision,
        payload: input.missionDraft,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `任务草稿已保存，项目进入 revision ${outcome.payload.result.snapshot.revision}；尚未生成用户确认。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "confirm_ai_ppt_mission",
    {
      title: "Confirm AI PPT Mission",
      description:
        "Create one immutable MissionConfirmation bound to the current draft, material identity, revision, and a real user action or host message reference.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        missionDraftRef: z.string().trim().min(1),
        materialMode: z.enum([
          "materials-provided",
          "no-materials-confirmed",
        ]),
        materialInventoryRef: z.string().trim().optional(),
        userActionRef: z.string().trim().optional(),
        userMessageRef: z.string().trim().optional(),
        missionSummary: z
          .object({
            topic: z.string().trim().min(1),
            primaryAudience: z.string().trim().min(1),
            desiredJudgmentOrAction: z.string().trim().min(1),
            materialSummary: z.string().trim().min(1),
          })
          .optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      let userActionRef = input.userActionRef || "";
      const userMessageRef = input.userMessageRef || "";
      if (userActionRef || userMessageRef) {
        if (!confirmationVerifier) {
          const native = await requestHostMissionConfirmation(server, input);
          if (!native.ok) return toolErrorResult(native.error);
          userActionRef = native.userActionRef;
        } else {
          const verified = await confirmationVerifier.verify({
            projectRoot: input.projectRoot || "",
            missionDraftRef: input.missionDraftRef,
            materialMode: input.materialMode,
            userActionRef,
            userMessageRef,
          });
          if (!verified) {
            return toolErrorResult({
              code: "MISSION_NOT_CONFIRMED",
              message: "用户确认凭据未通过宿主验证。",
              details: {},
            });
          }
        }
      } else {
        const native = await requestHostMissionConfirmation(server, input);
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("confirm-mission", input),
        expected_revision: input.expectedRevision,
        mission_draft_ref: input.missionDraftRef,
        material_mode: input.materialMode,
        material_inventory_ref: input.materialInventoryRef || "",
        user_action_ref: userActionRef,
        user_message_ref: confirmationVerifier ? userMessageRef : "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `任务已由用户显式确认，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "submit_ai_ppt_human_decision",
    {
      title: "Submit AI PPT Human Decision",
      description:
        "Persist one explicit human choice or feedback against the current project revision. Returns a follow-up message for Codex and a refreshed project projection.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        targetRef: z.string().trim().min(1),
        choice: z.string().trim().min(1),
        feedback: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const request = {
        ...requestForProject("submit-human-decision", input),
        expected_revision: input.expectedRevision,
        target_ref: input.targetRef,
        choice: input.choice,
        feedback: input.feedback || "",
      };
      const outcome = await invokeForTool(invokeBridge, request);
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      return textResult(
        `已保存用户判断，项目进入 revision ${payload.result.snapshot.revision}。`,
        payload.result,
      );
    },
  );

server.registerTool(
    "add_ai_ppt_material",
    {
      title: "Add AI PPT Material",
      description:
        "Persist one user-provided text, URL, or bounded base64 file into the managed project. This never searches or fetches external customer material.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        materialType: z.enum(["text", "url", "bytes"]),
        value: z.string().optional(),
        dataBase64: z.string().optional(),
        label: z.string().optional(),
        filename: z.string().optional(),
        mimeType: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const request = {
        ...requestForProject("add-material", input),
        expected_revision: input.expectedRevision,
        material_type: input.materialType,
        value: input.value || "",
        data_base64: input.dataBase64 || "",
        label: input.label || "",
        filename: input.filename || "",
        mime_type: input.mimeType || "",
      };
      const outcome = await invokeForTool(invokeBridge, request);
      if (!outcome.ok) return outcome.result;
      return textResult(
        `材料已写入项目，revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "request_ai_ppt_agent_action",
    {
      title: "Request AI PPT Agent Action",
      description:
        "Persist a governed AI task and bounded context pack before Codex uses reasoning, Image 2, or Presentations.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        actionType: z.enum([
          "build-presales-strategy",
          "build-claim-evidence-map",
          "build-deck-argument-map",
          "build-slide-draft-set",
          "repair-content",
          "review-content-presales",
          "review-content-decision-maker",
          "review-content-evidence",
          "review-content-narrative",
          "review-content-editorial",
          "aggregate-content-reviews",
          "design-deck-system",
          "design-slide-visuals",
          "build-native-first",
          "generate-image-assets",
          "review-visual-aesthetic",
          "review-visual-engineering",
          "verify-target-render",
          "govern-feedback",
          "curate-experience",
          "evaluate-experience",
          "coordinate-delivery",
        ]),
        targetRefs: z.array(z.string().trim().min(1)).min(1),
        instructions: z.string().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("request-agent-action", input),
        expected_revision: input.expectedRevision,
        action_type: input.actionType,
        target_refs: input.targetRefs,
        instructions: input.instructions || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `Agent 任务已保存，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "commit_ai_ppt_artifact",
    {
      title: "Commit AI PPT Artifact",
      description:
        "Validate and save one immutable material, blueprint, visual, scene, handoff, or delivery artifact and optionally complete its Agent task.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        kind: z.enum([
          "mission",
          "content-blueprint",
          "content-acceptance",
          "visual-brief",
          "concept-set",
          "visual-contract",
          "native-anchor-set",
          "feedback",
          "delivery",
          "experience",
          "target-render-evidence",
        ]),
        payload: z.record(z.string(), z.unknown()),
        taskId: z.string().trim().optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("commit-artifact", input),
        expected_revision: input.expectedRevision,
        kind: input.kind,
        payload: input.payload,
        task_id: input.taskId || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.kind} 已回写，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "confirm_ai_ppt_gate",
    {
      title: "Confirm AI PPT Quality Gate",
      description:
        "Confirm the exact current G0, G3, or G4 review source through a host-verified user message/action or fresh host-native confirmation. A MissionConfirmation or reused message never confirms a Gate.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G3", "G4"]),
        userMessageRef: z.string().trim().min(1).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const contextOutcome = await invokeForTool(invokeBridge, {
        ...requestForProject("get-gate-confirmation-context", input),
        gate: input.gate,
      });
      if (!contextOutcome.ok) return contextOutcome.result;
      const rawContext = contextOutcome.payload.confirmation_context;
      const context = rawContext
        ? {
            ...rawContext,
            project_root:
              rawContext.project_root ||
              contextOutcome.payload.selected_project_root ||
              input.projectRoot ||
              "",
          }
        : rawContext;
      if (
        !context ||
        context.gate !== input.gate ||
        context.challenge_revision !== input.expectedRevision
      ) {
        return toolErrorResult({
          code: "REVISION_CONFLICT",
          message: "当前 Gate 审阅版本或项目 revision 已变化，请刷新后重试。",
          details: {
            expectedRevision: input.expectedRevision,
            actualRevision: context?.challenge_revision,
          },
        });
      }
      let userActionRef = "";
      let userMessageRef = input.userMessageRef || "";
      let identityType = "";
      let identityRef = "";
      if (confirmationVerifier && userMessageRef) {
        const verified = await confirmationVerifier.verify({
          projectRoot: input.projectRoot || "",
          projectId: context.project_id,
          gate: input.gate,
          sourceVersion: context.source_version,
          evidenceRefs: context.evidence_refs,
          challengeId: context.challenge_id,
          challengeRevision: context.challenge_revision,
          userMessageRef,
        });
        if (!verified) {
          return toolErrorResult({
            code: "GATE_NOT_CONFIRMED",
            message: "用户 Gate 确认凭据未通过宿主验证。",
            details: { gate: input.gate },
          });
        }
        identityType = "verified-message";
        identityRef = userMessageRef;
      } else {
        const native = await requestHostGateConfirmation(server, context);
        if (!native.ok) return toolErrorResult(native.error);
        userActionRef = native.userActionRef;
        userMessageRef = native.userMessageRef;
        identityType = "host-action";
        identityRef = userActionRef;
      }
      let hostConfirmationAssertion;
      try {
        hostConfirmationAssertion = confirmationAuthority.issue(context, {
          identityType,
          identityRef,
        });
      } catch (_error) {
        return toolErrorResult({
          code: "HOST_CONFIRMATION_UNAVAILABLE",
          message: "宿主无法签发当前 Gate 的版本绑定确认断言；项目状态未改变。",
          details: { gate: input.gate },
        });
      }
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("confirm-gate", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        host_confirmation_assertion: hostConfirmationAssertion,
        user_action_ref: "",
        user_message_ref: "",
        source_version: context.source_version,
        challenge_id: context.challenge_id,
        challenge_revision: context.challenge_revision,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 已确认，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "record_internal_gate",
    {
      title: "Record AI PPT Internal Gate",
      description:
        "Record an authorized binary internal review for G1 or G2. G2 passes only after independent aesthetic and PPT engineering reviews plus target PowerPoint evidence.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G1", "G2"]),
        reviewerRole: z.enum(["独立审美审查智能体", "PPT 工程审查智能体"]),
        acceptanceRecordRefs: z.array(z.string().trim().min(1)).min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("record-internal-gate", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        reviewer_role: input.reviewerRole,
        acceptance_record_refs: input.acceptanceRecordRefs,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 内部审查已记录，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "reopen_ai_ppt_scope",
    {
      title: "Reopen AI PPT Scope",
      description:
        "Reopen one quality gate with a human reason, lock downstream gates, and preserve all historical artifacts.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        gate: z.enum(["G0", "G3", "G4"]),
        reason: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("reopen-scope", input),
        expected_revision: input.expectedRevision,
        gate: input.gate,
        reason: input.reason,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `${input.gate} 已重新打开，历史成果保留。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "read_ai_ppt_project_asset",
    {
      title: "Read AI PPT Project Asset",
      description:
        "Read one bounded image or text preview from inside the selected managed project.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        assetRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      try {
        const asset = readProjectAssetFn({
          projectRoot: input.projectRoot,
          assetRef: input.assetRef,
        });
        return textResult(`已读取项目资源 ${asset.assetRef}。`, { asset });
      } catch (error) {
        return toolErrorResult({
          code: "SOURCE_UNREADABLE",
          message: error instanceof Error ? error.message : "项目资源无法读取。",
          details: { assetRef: input.assetRef },
        });
      }
    },
  );
}
