import type { ContentReviewClient } from "../../lib/content-review-client";
import type {
  ContentFullDeckProjection,
  ContentSidebarReviewProjection,
  HostBridge,
  ProjectSnapshot,
} from "../../types";
import { ContentReviewDocument } from "./ContentReviewDocument";
import { ContentReviewProgress } from "./ContentReviewProgress";

interface Props {
  loading: boolean;
  projection?: ContentSidebarReviewProjection;
  projectRoot: string;
  bridge: HostBridge;
  client: ContentReviewClient;
  onProjectionChange: (projection: ContentFullDeckProjection) => void;
  onSnapshotChange: (snapshot: ProjectSnapshot) => void;
}

export function ContentReviewPanel({
  loading,
  projection,
  projectRoot,
  bridge,
  client,
  onProjectionChange,
  onSnapshotChange,
}: Props) {
  if (loading && !projection) {
    return (
      <section className="content-review-loading" aria-live="polite">
        <div className="content-review-loading-line" />
        <h2>正在读取完整内容</h2>
        <p>正在同步当前 revision 和 sourceVersion。</p>
      </section>
    );
  }
  if (!projection) return null;
  if (projection.display_policy === "content-sidebar-progress") {
    return <ContentReviewProgress projection={projection} />;
  }
  return (
    <ContentReviewDocument
      projection={projection}
      projectRoot={projectRoot}
      bridge={bridge}
      client={client}
      onProjectionChange={onProjectionChange}
      onSnapshotChange={onSnapshotChange}
    />
  );
}
