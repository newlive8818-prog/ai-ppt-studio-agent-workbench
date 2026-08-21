import type {
  ContentDecisionChoice,
  ContentPageDecision,
  ContentReviewProjection,
  ContentReviewSlide,
} from "../types/content-review";

export type ContentReviewDraftBlockType = "paragraph" | "bullet";
export type ContentReviewBatchState = "open" | "submitted" | "withdrawn";

export interface ContentReviewDraftBlockViewModel {
  readonly blockId: string;
  readonly type: ContentReviewDraftBlockType;
  readonly text: string;
}

export interface ContentReviewDraftContentViewModel {
  readonly title: string;
  readonly blocks: readonly ContentReviewDraftBlockViewModel[];
}

export interface ContentReviewMaterialVisualViewModel {
  readonly visualId: string;
  readonly assetRef: string;
  readonly altText: string;
}

export interface ContentReviewLocalDraftStateViewModel {
  readonly decision: ContentDecisionChoice | "";
  readonly comment: string;
  readonly dirty: boolean;
}

export interface ContentReviewSlideViewModel {
  readonly slideId: string;
  readonly order: number;
  readonly sectionId: string;
  readonly neutralTitle: string;
  readonly pageGoal: string;
  readonly customerJudgment: string;
  readonly readingQuestion: string;
  readonly draftContent: ContentReviewDraftContentViewModel;
  readonly materialVisuals: readonly ContentReviewMaterialVisualViewModel[];
  readonly savedDecision: ContentPageDecision | null;
  readonly localDraftState: ContentReviewLocalDraftStateViewModel;
}

export interface ContentReviewSectionViewModel {
  readonly sectionId: string;
  readonly title: string;
  readonly slideIds: readonly string[];
}

export interface ContentReviewPageViewModel {
  readonly projectId: string;
  readonly projectLabel: string;
  readonly reviewSessionId: string;
  readonly readingBlueprintRef: string;
  readonly sourceVersion: string;
  readonly revision: number;
  readonly authoritativeRevision: number;
  readonly progress: Readonly<ContentReviewProjection["progress"]>;
  readonly sections: readonly ContentReviewSectionViewModel[];
  readonly slides: readonly ContentReviewSlideViewModel[];
  readonly batchState: ContentReviewBatchState;
  readonly availableActions: Readonly<{
    savePageDecision: boolean;
    submitReviewBatch: boolean;
  }>;
}

export class ContentReviewPageViewModelAdapterError extends Error {
  readonly code = "CONTENT_REVIEW_CUSTOMER_JUDGMENT_MISSING" as const;

  constructor(readonly slideId: string, readonly fieldPath: string) {
    super(`Content review projection is missing authoritative ${fieldPath} for slide ${slideId}.`);
    this.name = "ContentReviewPageViewModelAdapterError";
  }
}

function customerJudgmentOf(slide: ContentReviewSlide, index: number): string {
  const value = slide.customerJudgment;
  if (typeof value !== "string" || !value || value !== value.trim()) {
    throw new ContentReviewPageViewModelAdapterError(
      slide.slide_id,
      `slides[${index}].customerJudgment`,
    );
  }
  return value;
}

function batchStateOf(batch: ContentReviewProjection["batch"]): ContentReviewBatchState {
  if (batch?.status === "submitted") return "submitted";
  if (batch?.status === "withdrawn") return "withdrawn";
  return "open";
}

function sectionsOf(projection: ContentReviewProjection): ContentReviewSectionViewModel[] {
  const sections: Array<{ sectionId: string; title: string; slideIds: string[] }> = [];
  for (const slide of projection.slides) {
    const current = sections.at(-1);
    if (current?.sectionId === slide.section_id) {
      current.slideIds.push(slide.slide_id);
      continue;
    }
    sections.push({
      sectionId: slide.section_id,
      title: projection.section_flow[sections.length] ?? slide.section_id,
      slideIds: [slide.slide_id],
    });
  }
  return sections;
}

function cloneDecision(decision: ContentPageDecision | undefined): ContentPageDecision | null {
  return decision ? { ...decision } : null;
}

export function toContentReviewPageViewModel(
  projection: ContentReviewProjection,
): ContentReviewPageViewModel {
  const decisions = new Map(projection.decisions.map((decision) => [decision.slide_id, decision]));
  const batchState = batchStateOf(projection.batch);
  const slides = projection.slides.map((slide, slideIndex): ContentReviewSlideViewModel => {
    const savedDecision = cloneDecision(decisions.get(slide.slide_id));
    return {
      slideId: slide.slide_id,
      order: slide.order,
      sectionId: slide.section_id,
      neutralTitle: slide.neutral_title,
      pageGoal: slide.page_task,
      customerJudgment: customerJudgmentOf(slide, slideIndex),
      readingQuestion: slide.reading_question,
      draftContent: {
        title: slide.neutral_title,
        blocks: slide.visible_copy_blocks.map((block) => ({
          blockId: block.block_id,
          type: "paragraph",
          text: block.text,
        })),
      },
      materialVisuals: slide.material_views.map((material, materialIndex) => ({
        visualId: material.material_view_id,
        assetRef: material.asset_ref,
        altText: `第 ${slide.order} 页《${slide.neutral_title}》页面画面 ${materialIndex + 1}`,
      })),
      savedDecision,
      localDraftState: {
        decision: savedDecision?.decision ?? "",
        comment: savedDecision?.comment ?? "",
        dirty: false,
      },
    };
  });
  return {
    projectId: projection.project_id,
    projectLabel: projection.project_id,
    reviewSessionId: projection.review_session_id,
    readingBlueprintRef: projection.reading_blueprint_ref,
    sourceVersion: projection.source_version,
    revision: projection.revision,
    authoritativeRevision: projection.authoritative_revision,
    progress: { ...projection.progress },
    sections: sectionsOf(projection),
    slides,
    batchState,
    availableActions: {
      savePageDecision: batchState !== "submitted",
      submitReviewBatch: batchState !== "submitted",
    },
  };
}
