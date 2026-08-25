import type { ContentReviewClient } from "../../lib/content-review-client";
import type { HostBridge } from "../../types";
import type { ContentFullDeckReviewProjection } from "../../types/content-review";
import { ContentReviewDocument } from "./ContentReviewDocument";

interface Props {
  projection: ContentFullDeckReviewProjection;
  projectRoot: string;
  bridge: HostBridge;
  client: ContentReviewClient;
  onProjectionChange: (projection: ContentFullDeckReviewProjection) => void;
}

export function ContentReviewPanel(props: Props) {
  return <ContentReviewDocument {...props} />;
}
