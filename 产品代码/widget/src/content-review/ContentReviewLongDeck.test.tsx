import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "../__fixtures__/content-sidebar-review.json";
import { ContentReviewDocument } from "../components/content-review/ContentReviewDocument";
import type { ContentReviewClient } from "../lib/content-review-client";
import { compactWidgetData, hostBridge } from "../test-fixtures";
import type { ContentFullDeckReviewProjection, ContentReviewSlide } from "../types/content-review";

afterEach(cleanup);

function longProjection(count: number): ContentFullDeckReviewProjection {
  const base = structuredClone(fixture) as ContentFullDeckReviewProjection;
  const template = base.slides[0];
  base.slides = Array.from({ length: count }, (_, index): ContentReviewSlide => ({
    ...structuredClone(template),
    slide_id: `LONG-${index + 1}`,
    order: index + 1,
    neutral_title: `第 ${index + 1} 页完整中立标题`,
    visible_copy_blocks: template.visible_copy_blocks.map((block) => ({
      ...block,
      block_id: `${block.block_id}-${index}`,
      text: `${block.text}·第 ${index + 1} 页`,
    })),
    decision_state: { selected: "", comment: "", completed: false, saved: false, frozen: false },
  }));
  base.review_progress = {
    total: count,
    completed: 0,
    remaining: count,
    saved_comment_count: 0,
    counts: { approved: 0, modify: 0, evidence: 0, merge_or_delete: 0 },
  };
  return base;
}

function client(projection: ContentFullDeckReviewProjection): ContentReviewClient {
  return {
    load: vi.fn(async () => projection),
    saveDecision: vi.fn(),
    submitBatch: vi.fn(),
    openEvidenceBrowser: vi.fn(),
  };
}

describe("content review long-deck contract", () => {
  it.each([10, 24, 60])("renders all %i pages once in one continuous document", (count) => {
    const data = longProjection(count);
    const host = hostBridge(compactWidgetData("blueprint"));
    const started = performance.now();
    const { container } = render(
      <ContentReviewDocument
        projection={data}
        projectRoot="/managed/project"
        bridge={host.bridge}
        client={client(data)}
        onProjectionChange={vi.fn()}
      />,
    );
    const elapsed = performance.now() - started;

    expect(container.querySelectorAll("article.content-slide-section")).toHaveLength(count);
    expect(container.querySelectorAll("[id^='content-slide-LONG-']")).toHaveLength(count);
    expect(new Set(Array.from(container.querySelectorAll("article.content-slide-section")).map((node) => node.id)).size).toBe(count);
    expect(container).toHaveTextContent(`第 ${count} 页完整中立标题`);
    expect(container.querySelector(".content-review-document")).toHaveAttribute("data-slide-count", String(count));
    expect(elapsed).toBeLessThan(2_000);
  });
});
