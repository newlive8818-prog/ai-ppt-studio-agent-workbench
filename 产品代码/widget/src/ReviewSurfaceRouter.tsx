import { toContentReviewPageViewModel } from "./content-review/content-review-page-view-model";
import { ContentReviewViewModelController } from "./content-review/ContentReviewViewModelController";
import { VisualProfessionalReviewPage } from "./visual-review/VisualProfessionalReviewPage";
import { toVisualReviewPageViewModel } from "./visual-review/visual-review-page-view-model";
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
    return (
      <ContentReviewViewModelController
        key={pageKey}
        initialData={validated}
        initialViewModel={toContentReviewPageViewModel(validated.review)}
        bridge={bridge}
      />
    );
  }
  const initialViewModel = toVisualReviewPageViewModel(validated);
  const pageKey = reviewDraftPageIdentity(createReviewDraftContext(initialViewModel));
  return (
    <VisualProfessionalReviewPage
      key={pageKey}
      initialViewModel={initialViewModel}
      bridge={bridge}
    />
  );
}

function isContentReviewSurface(data: ReviewSurfaceData): data is ContentReviewSurfaceData {
  return data.review.review_type === "content-full-deck";
}
