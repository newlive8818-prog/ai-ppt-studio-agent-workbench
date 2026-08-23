import { z } from "zod";

export function registerVisualTools(toolContext) {
  const { server, invokeBridge, invokeForTool, requestForProject, textResult } = toolContext;
server.registerTool(
    "save_review_marks",
    {
      title: "Save AI PPT Review Marks",
      description:
        "Save content or visual review marks against one exact source version. This never confirms G0 or G3.",
      inputSchema: {
        projectRoot: z.string().trim().min(1),
        expectedRevision: z.number().int().nonnegative(),
        reviewType: z.enum(["content", "visual"]),
        sourceVersion: z.string().trim().min(1),
        marks: z.array(
          z.object({
            mark_id: z.string().trim().min(1),
            field_anchor: z.string().trim().min(1),
            exact_text: z.string(),
            prefix: z.string(),
            suffix: z.string(),
            comment: z.string().trim().min(1),
          }).strict(),
        ).min(1),
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
        ...requestForProject("save-review-marks", input),
        expected_revision: input.expectedRevision,
        review_type: input.reviewType,
        source_version: input.sourceVersion,
        marks: input.marks,
      });
      if (!outcome.ok) return outcome.result;
      return textResult(
        `标记已保存，revision ${outcome.payload.result.snapshot.revision}；保存不等于 Gate 确认。`,
        outcome.payload.result,
      );
    },
  );
}
