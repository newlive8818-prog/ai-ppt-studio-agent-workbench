import { z } from "zod";

export function registerReviewTools(toolContext) {
  const {
    server, invokeBridge, invokeForTool, requestForProject, textResult,
    toolErrorResult, readProjectAssetFn, projectAssetPath,
    browserSurfaceAdapter, startScopedReviewSession,
  } = toolContext;
server.registerTool(
    "open_or_resume_review_session",
    {
      title: "Open or Resume AI PPT Review Session",
      description:
        "Create or resume the one authoritative content-full-deck or visual-professional ReviewSession for an exact artifact source and revision.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        reviewType: z.enum(["content-full-deck", "visual-professional"]),
        targetArtifactRef: z.string().trim().min(1),
        sourceVersion: z.string().trim().min(1),
        targetRevision: z.number().int().nonnegative(),
        openPolicy: z.enum(["foreground-if-waiting", "notify-only"]),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("open-or-resume-review-session", input),
        expected_revision: input.expectedRevision,
        review_type: input.reviewType,
        target_artifact_ref: input.targetArtifactRef,
        source_version: input.sourceVersion,
        target_revision: input.targetRevision,
        open_policy: input.openPolicy,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `审核会话 ${outcome.payload.session.review_session_id} 已创建或恢复。`,
        outcome.payload,
      );
    },
  );

const reviewReceiptTools = [
    {
      name: "record_review_host_open_receipt",
      operation: "record-review-host-open",
      title: "Record Review Host Open Receipt",
      results: ["opened", "failed", "unavailable"],
      message: "宿主打开回执已记录。",
    },
    {
      name: "record_review_host_notification_receipt",
      operation: "record-review-host-notification",
      title: "Record Review Host Notification Receipt",
      results: ["sent", "failed", "unavailable"],
      message: "宿主通知回执已记录。",
    },
    {
      name: "record_review_ai_receipt",
      operation: "record-review-ai-receipt",
      title: "Record Review AI Receipt",
      results: ["received", "failed", "unavailable"],
      message: "AI 接收回执已记录。",
    },
  ];

for (const receiptTool of reviewReceiptTools) {
    server.registerTool(
      receiptTool.name,
      {
        title: receiptTool.title,
        description:
          "Persist one real receipt against an existing authoritative ReviewSession. The client cannot infer or fabricate Runtime-owned status.",
        inputSchema: {
          projectRoot: z.string().trim().min(1),
          expectedRevision: z.number().int().nonnegative(),
          reviewSessionId: z.string().trim().min(1),
          result: z.enum(receiptTool.results),
          receiptRef: z.string().trim().min(1),
        },
        annotations: {
          readOnlyHint: false,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
      },
      async (input) => {
        const outcome = await invokeForTool(invokeBridge, {
          ...requestForProject(receiptTool.operation, input),
          expected_revision: input.expectedRevision,
          review_session_id: input.reviewSessionId,
          result: input.result,
          receipt_ref: input.receiptRef,
        });
        if (!outcome.ok) return outcome.result;
        return textResult(receiptTool.message, outcome.payload);
      },
    );
  }

server.registerTool(
    "open_ai_ppt_browser_review",
    {
      title: "Open AI PPT Browser Review",
      description:
        "Prepare the fixed G3 visual review through a short-lived loopback Review Bridge. Content review stays in the sidebar; a directly connected host adapter may open the session, otherwise the Agent opens its scoped URL with the Codex in-app Browser.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        reviewType: z.literal("visual"),
        sourceVersion: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const projection = await invokeForTool(invokeBridge, {
        ...requestForProject("get-review-projection", input),
        review_type: input.reviewType,
      });
      if (!projection.ok) return projection.result;
      const payload = projection.payload;
      if (payload.review?.source_version !== input.sourceVersion) {
        return toolErrorResult({
          code: "REVIEW_SOURCE_STALE",
          message: "请求的专业审阅版本已经变化，请刷新后重试。",
          details: {
            expected_source: input.sourceVersion,
            actual_source: payload.review?.source_version || "",
          },
        });
      }
      let bridge;
      let session;
      try {
        ({ bridge, session } = await startScopedReviewSession({
          projectRoot: payload.selected_project_root || input.projectRoot,
          reviewType: input.reviewType,
          sourceVersion: input.sourceVersion,
          expectedRevision: payload.snapshot_revision,
        }));
      } catch (error) {
        if (bridge) await bridge.stop();
        return toolErrorResult({
          code:
            typeof error?.code === "string"
              ? error.code
              : "BROWSER_REVIEW_SAVE_UNAVAILABLE",
          message:
            error instanceof Error && error.message
              ? error.message
              : "专业审阅的读取与保存会话暂时无法建立。",
          details: {
            reviewType: input.reviewType,
            sourceVersion: input.sourceVersion,
          },
        });
      }

      let opened = false;
      if (browserSurfaceAdapter?.canOpen) {
        try {
          opened = Boolean((await browserSurfaceAdapter.openUrl(session.url))?.opened);
        } catch (_error) {
          opened = false;
        }
      }

      const common = {
        projectRoot: payload.selected_project_root || input.projectRoot,
        reviewType: input.reviewType,
        sourceVersion: input.sourceVersion,
        revision: payload.snapshot_revision,
        expiresAt: session.expiresAt,
      };
      if (!opened) {
        return textResult(
          `“${payload.review.project_name}”的专业审阅会话已准备；请立即使用 Codex 内置 Browser 打开返回的短时地址。`,
          {
            status: "review-session-ready",
            opened: false,
            openMode: "agent-browser",
            browserAction: "open-scoped-url",
            url: session.url,
            ...common,
          },
        );
      }
      return textResult(
        `已在 Codex 内置 Browser 打开“${payload.review.project_name}”的专业审阅。`,
        {
          status: "opened",
          opened: true,
          openMode: "host-adapter",
          ...common,
        },
      );
    },
  );

server.registerTool(
    "open_content_full_deck_evidence_browser",
    {
      title: "Open Content Full-Deck Evidence Browser",
      description:
        "Open one typed read-only material binding for an exact parent content-full-deck ReviewSession. This never creates another decision.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        reviewSessionId: z.string().trim().min(1),
        sourceVersion: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        evidenceId: z.string().trim().min(1),
        materialRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const projection = await invokeForTool(invokeBridge, {
        ...requestForProject("get-content-full-deck-review-projection", input),
        review_session_id: input.reviewSessionId,
      });
      if (!projection.ok) return projection.result;
      const payload = projection.payload;
      if (
        payload.review?.surface !== "content-full-deck"
        || payload.review?.source_version !== input.sourceVersion
        || payload.review?.review_session?.review_session_id !== input.reviewSessionId
      ) {
        return toolErrorResult({
          code: "REVIEW_SOURCE_STALE",
          message: "请求的内容审核会话或来源版本已经变化，请刷新后重试。",
          details: {
            reviewSessionId: input.reviewSessionId,
            expectedSource: input.sourceVersion,
            actualSource: payload.review?.source_version || "",
          },
        });
      }
      const slides = Array.isArray(payload.review?.slides) ? payload.review.slides : [];
      const slide = slides.find((item) => String(item?.slide_id || "") === input.slideId);
      const bindings = Array.isArray(slide?.evidence_bindings) ? slide.evidence_bindings : [];
      const binding = bindings.find((item) =>
        String(item?.binding_id || "") === input.evidenceId
        && String(item?.material_ref || "") === input.materialRef
      );
      if (!slide || !binding) {
        return toolErrorResult({
          code: "CONTENT_EVIDENCE_SCOPE_INVALID",
          message: "请求的页面与类型化材料绑定不再匹配，请刷新后重试。",
          details: {
            reviewSessionId: input.reviewSessionId,
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
          },
        });
      }
      const selectedProjectRoot = payload.selected_project_root || input.projectRoot;
      let bridge;
      let session;
      try {
        ({ bridge, session } = await startScopedReviewSession({
          projectRoot: selectedProjectRoot,
          reviewType: "content-evidence",
          sourceVersion: input.sourceVersion,
          expectedRevision: payload.snapshot_revision,
          evidenceScope: {
            parentReviewSessionId: input.reviewSessionId,
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
          },
        }));
      } catch (error) {
        if (bridge) await bridge.stop();
        return toolErrorResult({
          code: typeof error?.code === "string" ? error.code : "BROWSER_REVIEW_UNAVAILABLE",
          message: error instanceof Error ? error.message : "内容证据会话暂时无法建立。",
          details: {},
        });
      }
      let opened = false;
      if (browserSurfaceAdapter?.canOpen) {
        try {
          opened = Boolean((await browserSurfaceAdapter.openUrl(session.url))?.opened);
        } catch (_error) {
          opened = false;
        }
      }
      const common = {
        reviewType: "content-evidence",
        reviewSessionId: input.reviewSessionId,
        sourceVersion: input.sourceVersion,
        revision: payload.snapshot_revision,
        expiresAt: session.expiresAt,
        slideId: input.slideId,
        evidenceId: input.evidenceId,
        materialRef: input.materialRef,
      };
      if (!opened) {
        return textResult(
          "只读内容证据会话已准备；请立即使用 Codex 内置 Browser 打开返回的短时地址。",
          {
            status: "review-session-ready",
            opened: false,
            openMode: "agent-browser",
            browserAction: "open-scoped-url",
            url: session.url,
            ...common,
          },
        );
      }
      return textResult("已在 Codex 内置 Browser 打开只读内容证据。", {
        status: "opened",
        opened: true,
        openMode: "host-adapter",
        ...common,
      });
    },
  );

server.registerTool(
    "open_content_evidence_browser",
    {
      title: "Open Content Evidence Browser",
      description:
        "Prepare one exact read-only content evidence scope in the Codex built-in Browser. Page decisions remain in the maximum-width sidebar.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        sourceVersion: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        evidenceId: z.string().trim().min(1),
        materialRef: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const projection = await invokeForTool(invokeBridge, {
        ...requestForProject("get-content-sidebar-review-projection", input),
      });
      if (!projection.ok) return projection.result;
      const payload = projection.payload;
      if (payload.review?.source_version !== input.sourceVersion) {
        return toolErrorResult({
          code: "REVIEW_SOURCE_STALE",
          message: "请求的内容证据版本已经变化，请刷新内容审核后重试。",
          details: {
            expected_source: input.sourceVersion,
            actual_source: payload.review?.source_version || "",
          },
        });
      }
      const slides = Array.isArray(payload.review?.slides)
        ? payload.review.slides
        : [];
      const slide = slides.find(
        (item) => String(item?.slide_id || "") === input.slideId,
      );
      const evidenceItems = Array.isArray(slide?.evidence_items)
        ? slide.evidence_items
        : [];
      const evidence = evidenceItems.find(
        (item) =>
          String(item?.evidence_id || "") === input.evidenceId &&
          String(item?.material_ref || "") === input.materialRef,
      );
      if (!slide || !evidence || !String(evidence.asset_ref || "").trim()) {
        return toolErrorResult({
          code: "CONTENT_EVIDENCE_SCOPE_INVALID",
          message: "请求的页面与材料证据不再匹配，请刷新内容审核后重试。",
          details: {
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
          },
        });
      }
      const selectedProjectRoot =
        payload.selected_project_root || input.projectRoot;
      let evidenceAsset;
      try {
        evidenceAsset = readProjectAssetFn({
          projectRoot: selectedProjectRoot,
          assetRef: projectAssetPath(evidence.asset_ref),
        });
      } catch (error) {
        return toolErrorResult({
          code: "SOURCE_UNREADABLE",
          message:
            error instanceof Error ? error.message : "项目证据无法读取。",
          details: { assetRef: evidence.asset_ref },
        });
      }
      let bridge;
      let session;
      try {
        ({ bridge, session } = await startScopedReviewSession({
          projectRoot: selectedProjectRoot,
          reviewType: "content-evidence",
          sourceVersion: input.sourceVersion,
          expectedRevision: payload.snapshot_revision,
          evidenceScope: {
            slideId: input.slideId,
            evidenceId: input.evidenceId,
            materialRef: input.materialRef,
            assetRef: evidence.asset_ref,
          },
          evidenceAsset,
        }));
      } catch (error) {
        if (bridge) await bridge.stop();
        return toolErrorResult({
          code:
            typeof error?.code === "string"
              ? error.code
              : "BROWSER_REVIEW_UNAVAILABLE",
          message:
            error instanceof Error && error.message
              ? error.message
              : "内容证据会话暂时无法建立。",
          details: {},
        });
      }
      let opened = false;
      if (browserSurfaceAdapter?.canOpen) {
        try {
          opened = Boolean(
            (await browserSurfaceAdapter.openUrl(session.url))?.opened,
          );
        } catch (_error) {
          opened = false;
        }
      }
      const common = {
        reviewType: "content-evidence",
        sourceVersion: input.sourceVersion,
        revision: payload.snapshot_revision,
        expiresAt: session.expiresAt,
        slideId: input.slideId,
        evidenceId: input.evidenceId,
        materialRef: input.materialRef,
      };
      if (!opened) {
        return textResult(
          "只读内容证据会话已准备；请立即使用 Codex 内置 Browser 打开返回的短时地址。",
          {
            status: "review-session-ready",
            opened: false,
            openMode: "agent-browser",
            browserAction: "open-scoped-url",
            url: session.url,
            ...common,
          },
        );
      }
      return textResult("已在 Codex 内置 Browser 打开只读内容证据。", {
        status: "opened",
        opened: true,
        openMode: "host-adapter",
        ...common,
      });
    },
  );
}
