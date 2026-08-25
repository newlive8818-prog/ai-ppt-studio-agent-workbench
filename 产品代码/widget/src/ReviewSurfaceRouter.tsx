import { App } from "./App";
import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { ContentFullDeckReviewPage } from "./content-review/ContentFullDeckReviewPage";
import { createContentReviewClient, type ContentReviewClient } from "./lib/content-review-client";
import type { HostBridge, SurfaceData } from "./types";
import { VisualProfessionalReviewPage } from "./visual-review/VisualProfessionalReviewPage";
import { legacyVisualReviewToPageViewModel } from "./visual-review/legacy-visual-review-adapter";

interface Props {
  initialData: SurfaceData;
  projectRoot?: string;
  bridge: HostBridge;
  contentReviewClient?: ContentReviewClient;
  managedConnection?: boolean;
}

export function ReviewSurfaceRouter({
  initialData,
  projectRoot,
  bridge,
  contentReviewClient,
  managedConnection = true,
}: Props) {
  if (initialData.surface === "content-full-deck") {
    if (!projectRoot) {
      return (
        <main className="review-capability-gap" role="alert">
          <h1>内容审核页暂时无法写回</h1>
          <p>当前宿主没有提供该 ReviewSession 对应的受管项目路径；内容和审核状态未被修改。</p>
        </main>
      );
    }
    return (
      <ContentFullDeckReviewPage
        initialProjection={initialData}
        projectRoot={projectRoot}
        bridge={bridge}
        client={contentReviewClient || createContentReviewClient(bridge)}
      />
    );
  }
  if (initialData.surface === "review") {
    if (initialData.review.review_type === "visual") {
      return (
        <VisualProfessionalReviewPage
          initialViewModel={legacyVisualReviewToPageViewModel(initialData)}
          bridge={bridge}
        />
      );
    }
    return <ProfessionalReviewApp initialData={initialData} bridge={bridge} managedConnection={managedConnection} />;
  }
  return <App initialData={initialData} bridge={bridge} managedConnection={managedConnection} />;
}
