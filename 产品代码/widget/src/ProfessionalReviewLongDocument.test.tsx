import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { hostBridge, reviewWidgetData } from "./test-fixtures";
import type { ReviewSection, ReviewWidgetData } from "./types";

afterEach(cleanup);

const LONG_CHINESE = "这是一段用于验证连续专业审阅完整性的超长中文内容，所有事实、讲解稿、来源与视觉合同都必须原样保留，不得截断、分页隐藏或改写。";
const LONG_UNBROKEN = `customer-proof-${"x".repeat(180)}.source.json#paragraph-999`;

function pageSection(type: "content" | "visual", index: number): ReviewSection {
  const serial = String(index + 1).padStart(3, "0");
  const prefix = type === "content" ? `slide-s${serial}` : `visual-slide-s${serial}`;
  const common = [
    { anchor: `${prefix}-visible-copy`, label: type === "content" ? "visible_content" : "visible_copy", value: [`第 ${index + 1} 页完整正文`, `${LONG_CHINESE}${serial}`] },
    { anchor: `${prefix}-speaker-notes`, label: "speaker_notes", value: `第 ${index + 1} 页讲解稿：${LONG_CHINESE.repeat(2)}` },
    { anchor: `${prefix}-source-refs`, label: "source_refs", value: [`sources/${serial}/${LONG_UNBROKEN}`] },
  ];
  return {
    anchor: prefix,
    title: `第 ${index + 1} 页·${LONG_CHINESE}${serial}`,
    fields: type === "content"
      ? common
      : [
          ...common,
          { anchor: `${prefix}-page-family`, label: "page_family", value: "阅读优先证据页" },
          { anchor: `${prefix}-composition-intent`, label: "composition_intent", value: `${LONG_CHINESE}${LONG_UNBROKEN}` },
          { anchor: `${prefix}-acceptance-criteria`, label: "acceptance_criteria", value: ["业务关系完整", "文字原生可编辑", "四目标同一哈希"] },
        ],
  };
}

function longReviewData(type: "content" | "visual", pageCount: number): ReviewWidgetData {
  const data = reviewWidgetData(type);
  const standing = data.review.sections.filter((section) =>
    type === "content"
      ? section.anchor === "content-overview" || section.anchor === "content-structure"
      : section.anchor === "visual-framework" || section.anchor === "deck-design-system",
  );
  const pages = Array.from({ length: pageCount }, (_, index) => pageSection(type, index));
  data.review.sections = [...standing, ...pages];
  data.review.outline = data.review.sections.map(({ anchor, title }) => ({ anchor, title }));
  data.review.title = `${pageCount} 页${type === "content" ? "内容蓝图" : "视觉合同"}`;
  return data;
}

function expectCompleteLongDocument(data: ReviewWidgetData, pageCount: number, elapsedMs: number, container: HTMLElement) {
  const pagePrefix = data.review.review_type === "content" ? "slide-" : "visual-slide-";
  const expectedAnchors = data.review.sections
    .filter((section) => section.anchor.startsWith(pagePrefix))
    .map((section) => section.anchor);
  const pages = Array.from(container.querySelectorAll<HTMLElement>("article.review-sheet"));

  expect(elapsedMs).toBeLessThan(2_000);
  expect(pages).toHaveLength(pageCount);
  expect(container.querySelector(".review-sheet-list")).toHaveAttribute("data-review-page-count", String(pageCount));
  expect(pages.map((page) => page.dataset.reviewPageAnchor)).toEqual(expectedAnchors);
  for (const anchor of expectedAnchors) {
    expect(container.querySelectorAll(`[id="${anchor}"]`)).toHaveLength(1);
  }
  expect(new Set(pages.map((page) => page.id)).size).toBe(pageCount);
  expect(container.querySelectorAll(".review-outline-link")).toHaveLength(pageCount + 1);
  expect(container).toHaveTextContent(`第 ${pageCount} 页`);
  expect(container).toHaveTextContent(LONG_UNBROKEN);
  expect(container).not.toHaveTextContent("加载更多");
  expect(container).not.toHaveTextContent("下一页");
  expect(screen.getByRole("button", { name: "目录" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存标记" })).toBeInTheDocument();
}

describe("professional review long-document contract", () => {
  it("renders all 60 content pages with one stable DOM anchor each within budget", () => {
    const data = longReviewData("content", 60);
    const started = performance.now();
    const { container } = render(<ProfessionalReviewApp initialData={data} bridge={hostBridge(data).bridge} />);
    expectCompleteLongDocument(data, 60, performance.now() - started, container);
  });

  it("renders all 120 visual-contract pages without truncation or pagination within budget", () => {
    const data = longReviewData("visual", 120);
    const started = performance.now();
    const { container } = render(<ProfessionalReviewApp initialData={data} bridge={hostBridge(data).bridge} />);
    expectCompleteLongDocument(data, 120, performance.now() - started, container);
  });
});
