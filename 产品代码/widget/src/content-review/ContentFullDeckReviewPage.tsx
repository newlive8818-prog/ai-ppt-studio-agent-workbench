import { useState } from "react";

import { ContentReviewDocument } from "../components/content-review/ContentReviewDocument";
import type { ContentReviewClient } from "../lib/content-review-client";
import type { HostBridge } from "../types";
import type { ContentFullDeckReviewProjection } from "../types/content-review";

interface Props {
  initialProjection: ContentFullDeckReviewProjection;
  projectRoot: string;
  bridge: HostBridge;
  client: ContentReviewClient;
}

export function ContentFullDeckReviewPage({ initialProjection, projectRoot, bridge, client }: Props) {
  const [projection, setProjection] = useState(initialProjection);

  return (
    <main className="content-full-deck-review-page">
      <ContentReviewDocument
        projection={projection}
        projectRoot={projectRoot}
        bridge={bridge}
        client={client}
        onProjectionChange={setProjection}
      />
    </main>
  );
}
