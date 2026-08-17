import { ContentFullDeckReviewPage } from "./content-review/ContentFullDeckReviewPage";
import { VisualProfessionalReviewPage } from "./visual-review/VisualProfessionalReviewPage";
import type { HostBridge, ReviewSurfaceData } from "./types/host";
import type { ContentReviewSurfaceData } from "./types/content-review";
import { validateReviewSurfaceData } from "./review-surface-validation";
import { createReviewDraftContext, reviewDraftPageIdentity } from "./review-draft/reviewDraftStore";

interface Props {
  data: ReviewSurfaceData;
  bridge: HostBridge;
}

export function ReviewSurfaceRouter({ data, bridge }: Props) {
  const validated = validateReviewSurfaceData(data);
  if (!validated) {
    return <main className="review-recovery" role="alert">审核数据无效，请重新打开审核页。</main>;
  }
  if (isContentReviewSurface(validated)) {
    const pageKey = reviewDraftPageIdentity(createReviewDraftContext(validated));
    return <ContentFullDeckReviewPage key={pageKey} initialData={validated} bridge={bridge} />;
  }
  const pageKey = reviewDraftPageIdentity(createReviewDraftContext(validated));
  return <VisualProfessionalReviewPage key={pageKey} initialData={validated} bridge={bridge} />;
}

function isContentReviewSurface(data: ReviewSurfaceData): data is ContentReviewSurfaceData {
  return data.review.review_type === "content-full-deck";
}
