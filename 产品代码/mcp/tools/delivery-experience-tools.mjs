import { z } from "zod";

export function registerDeliveryExperienceTools(toolContext) {
  const {
    server, projectSchema, invokeBridge, invokeForTool, requestForProject,
    textResult,
  } = toolContext;
server.registerTool(
    "get_delivery_status_projection",
    {
      title: "Get AI PPT Delivery Status",
      description:
        "Read the lightweight production and delivery projection, including gates, blocker, target PowerPoint evidence, and chat-send status.",
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
        requestForProject("get-delivery-status-projection", input),
      );
      if (!outcome.ok) return outcome.result;
      const payload = outcome.payload;
      const projection = {
        surface: "workbench",
        selectedProjectRoot: payload.selected_project_root,
        snapshotRevision: payload.snapshot_revision,
        delivery: payload.delivery,
      };
      return textResult(
        `已读取制作与交付状态，revision ${payload.snapshot_revision}。`,
        projection,
      );
    },
  );

server.registerTool(
    "set_ai_ppt_release_target_policy",
    {
      title: "Set AI PPT Release Target Policy",
      description:
        "Activate the known product-version release target policy for an existing schema 3 project. This migration tool cannot accept arbitrary target arrays or act as a per-project platform-skip preference.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        policyId: z.literal("v1.6-macos-powerpoint"),
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
        operation: "set-release-target-policy",
        project_root: input.projectRoot,
        expected_revision: input.expectedRevision,
        policy_id: input.policyId,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `发布目标策略已绑定，项目进入 revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );

server.registerTool(
    "record_chat_delivery",
    {
      title: "Record AI PPT Chat Delivery",
      description:
        "Persist a Codex chat message receipt for a visual sample, comparison, PPTX, preview, or delivery note without rebuilding the referenced artifact.",
      inputSchema: {
        ...projectSchema,
        expectedRevision: z.number().int().nonnegative(),
        deliveryType: z.enum([
          "visual-sample",
          "comparison",
          "pptx",
          "preview",
          "delivery-note",
        ]),
        artifactRefs: z.array(z.string().trim().min(1)).min(1),
        messageRef: z.string().trim().min(1),
        sendStatus: z.enum(["sent", "failed"]),
        retryOf: z.string().trim().optional(),
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
        ...requestForProject("record-chat-delivery", input),
        expected_revision: input.expectedRevision,
        delivery_type: input.deliveryType,
        artifact_refs: input.artifactRefs,
        message_ref: input.messageRef,
        send_status: input.sendStatus,
        retry_of: input.retryOf || "",
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `聊天交付回执已记录，revision ${outcome.payload.result.snapshot.revision}。`,
        outcome.payload.result,
      );
    },
  );
}
