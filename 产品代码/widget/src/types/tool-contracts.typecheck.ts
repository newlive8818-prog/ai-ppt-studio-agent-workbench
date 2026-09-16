import type { ToolContractMap } from "./tool-contracts";

type Assert<T extends true> = T;
type Extends<Actual, Expected> = Actual extends Expected ? true : false;

type VisualProjectionOutput = ToolContractMap["get_visual_review_projection"]["output"];
type AnchorFeedbackInput = ToolContractMap["submit_visual_anchor_feedback_batch"]["input"]["feedback"][number];
type AnchorFeedbackOutput = ToolContractMap["submit_visual_anchor_feedback_batch"]["output"];
type ContractMarkInput = ToolContractMap["save_visual_contract_review_marks"]["input"]["marks"][number];
type ContractMarkOutput = ToolContractMap["save_visual_contract_review_marks"]["output"];

export type ProjectionIsProfessional = Assert<Extends<
  VisualProjectionOutput,
  { review: { review_type: "visual-professional"; anchors: readonly unknown[] } }
>>;
export type FeedbackIsRectangle = Assert<Extends<
  AnchorFeedbackInput,
  { normalized_region: { x: number; y: number; width: number; height: number } }
>>;
export type FeedbackReturnsBatch = Assert<Extends<
  AnchorFeedbackOutput,
  { batch_ref: string; batch: unknown; snapshot: { revision: number } }
>>;
export type MarkTargetsContract = Assert<Extends<
  ContractMarkInput,
  { target_type: "contract-field" | "text-range"; target_key: string; selected_text: string }
>>;
export type MarkReturnsSet = Assert<Extends<
  ContractMarkOutput,
  { mark_set_ref: string; mark_set: unknown; snapshot: { revision: number } }
>>;
