import { z } from "zod";

const contentReviewCommentSchema = z.string().refine(
  (value) => Array.from(value).length <= 1200,
  { message: "comment must not exceed 1200 Unicode code points" },
);

export function registerContentTools(toolContext) {
  const {
    server, projectSchema, invokeBridge, invokeForTool, requestForProject,
    textResult, invokeScopedContentWrite,
  } = toolContext;
server.registerTool(
    "get_content_sidebar_review_projection",
    {
      title: "Get Content Sidebar Review Projection",
      description:
        "Read the authoritative production-progress or complete full-deck sidebar projection without starting a model turn.",
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
        requestForProject("get-content-sidebar-review-projection", input),
      );
      if (!outcome.ok) return outcome.result;
      return textResult(
        `已读取内容侧边栏投影，revision ${outcome.payload.snapshot_revision}。`,
        outcome.payload.review,
      );
    },
  );

server.registerTool(
    "get_content_full_deck_review_projection",
    {
      title: "Get Content Full-Deck Review Projection",
      description:
        "Read the authoritative v2.2 content-full-deck projection for one exact current ReviewSession.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        reviewSessionId: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeForTool(invokeBridge, {
        ...requestForProject("get-content-full-deck-review-projection", input),
        review_session_id: input.reviewSessionId,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `已读取当前内容全稿审核会话，revision ${outcome.payload.snapshot_revision}。`,
        outcome.payload.review,
      );
    },
  );

server.registerTool(
    "save_content_full_deck_page_decision",
    {
      title: "Save Content Full-Deck Page Decision",
      description:
        "Save one v2.2 PageDecision for the exact current ReviewSession without changing content, starting AI work, or affecting G0.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        reviewSessionId: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        decision: z.enum(["approved", "modify", "evidence", "merge-or-delete"]),
        comment: contentReviewCommentSchema,
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
        ...requestForProject("save-content-full-deck-page-decision", input),
        expected_revision: input.expectedRevision,
        review_session_id: input.reviewSessionId,
        review_batch_id: input.reviewBatchId,
        slide_id: input.slideId,
        decision: input.decision,
        comment: input.comment,
      });
      if (!outcome.ok) return outcome.result;
      return textResult("本页判断已持久化；内容、AI 和 G0 均未改变。", outcome.payload.result);
    },
  );

server.registerTool(
    "submit_content_full_deck_review_batch",
    {
      title: "Submit Content Full-Deck Review Batch",
      description:
        "Obtain trusted host confirmation, freeze every saved v2.2 PageDecision, and persist one immutable ContentReviewBatch.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        reviewSessionId: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-full-deck-review-batch-submission-context",
        contextFields: {
          review_session_id: input.reviewSessionId,
          review_batch_id: input.reviewBatchId,
        },
        writeOperation: "submit-content-full-deck-review-batch",
        writeFields: {
          review_session_id: input.reviewSessionId,
          review_batch_id: input.reviewBatchId,
        },
        actionLabel: "冻结并提交当前内容全稿审核批次",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套审核判断已冻结并持久化。", outcome.payload.result);
    },
  );

server.registerTool(
    "save_content_page_decision",
    {
      title: "Save Content Page Decision",
      description:
        "Silently save one page decision and comment. This never starts Codex processing or changes content/Gate state.",
      inputSchema: {
        projectRoot: z.string().trim().optional(),
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        slideId: z.string().trim().min(1),
        decision: z.enum([
          "approved",
          "modify",
          "evidence",
          "merge-or-delete",
        ]),
        comment: contentReviewCommentSchema,
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
        ...requestForProject("save-content-page-decision", input),
        expected_revision: input.expectedRevision,
        source_version: input.sourceVersion,
        review_batch_id: input.reviewBatchId,
        slide_id: input.slideId,
        decision: input.decision,
        comment: input.comment,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "本页判断已保存；尚未触发集中处理。",
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "submit_content_review_batch",
    {
      title: "Submit Complete Content Review Batch",
      description:
        "Freeze and submit all page decisions, then return one follow-up instruction for Codex to prepare a whole-deck revision plan.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
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
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-review-batch-submission-context",
        contextFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        writeOperation: "submit-content-review-batch",
        writeFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        actionLabel: "提交整套逐页内容审核判断",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套审核判断已冻结并提交。", outcome.payload.result);
    },
  );

server.registerTool(
    "withdraw_content_review_batch",
    {
      title: "Withdraw Submitted Content Review Batch",
      description:
        "Withdraw an exact submitted pre-plan batch, preserve history, and create a new editable draft batch without starting Codex processing.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        sourceVersion: z.string().trim().min(1),
        reviewBatchId: z.string().trim().min(1),
        reason: z.string().trim().min(1),
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
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-review-batch-withdrawal-context",
        contextFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
        },
        writeOperation: "withdraw-content-review-batch",
        writeFields: {
          source_version: input.sourceVersion,
          review_batch_id: input.reviewBatchId,
          reason: input.reason,
        },
        actionLabel: "撤回已提交的整套审核批次",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "批次已撤回并创建新的可编辑审核批次。",
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "save_content_batch_revision_plan",
    {
      title: "Save Whole-Deck Content Revision Plan",
      description:
        "Save Codex's whole-deck revision plan for the exact frozen review batch without applying it.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        revisionPlan: z.record(z.string(), z.unknown()),
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
        ...requestForProject("save-content-batch-revision-plan", input),
        expected_revision: input.expectedRevision,
        payload: input.revisionPlan,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "整套修改方案已保存，等待用户确认。",
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "confirm_content_batch_revision_plan",
    {
      title: "Confirm Whole-Deck Content Revision Plan",
      description:
        "Confirm one exact whole-deck revision plan before governance or content changes can be created.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        reviewBatchId: z.string().trim().min(1),
        planRef: z.string().trim().min(1),
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
      const outcome = await invokeScopedContentWrite({
        input,
        contextOperation: "get-content-batch-plan-confirmation-context",
        contextFields: {
          review_batch_id: input.reviewBatchId,
          plan_ref: input.planRef,
        },
        writeOperation: "confirm-content-batch-revision-plan",
        writeFields: {
          review_batch_id: input.reviewBatchId,
          plan_ref: input.planRef,
        },
        actionLabel: "确认整套内容修改方案",
      });
      if (!outcome.ok) return outcome.result;
      return textResult("整套修改方案已确认。", outcome.payload.result);
    },
  );

server.registerTool(
    "create_content_batch_change_set",
    {
      title: "Create Governed Content Batch Change Set",
      description:
        "Create governance and a ContentChangeSet only from the exact confirmed whole-deck plan.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        planConfirmationRef: z.string().trim().min(1),
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
        ...requestForProject("create-content-batch-change-set", input),
        expected_revision: input.expectedRevision,
        plan_confirmation_ref: input.planConfirmationRef,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        "已按确认方案创建治理记录与修改集。",
        outcome.payload.result,
      );
    },
  );
}
