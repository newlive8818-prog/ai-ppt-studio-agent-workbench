import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "widget/src/styles/visual-review.css"), "utf8");

describe("visual anchor review responsive contracts", () => {
  it("uses one white project topbar with a segmented review switch and a contract action slot", () => {
    expect(css).toMatch(/\.visual-professional-header\.visual-review-topbar\s*\{[^}]*border-bottom:\s*1px solid[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*\.96\)/s);
    expect(css).toMatch(/\.visual-professional-ai-mark\s*\{[^}]*display:\s*grid[^}]*place-items:\s*center/s);
    expect(css).toMatch(/\.visual-professional-review-view-switch\s*\{[^}]*border:\s*1px solid[^}]*border-radius:\s*9px[^}]*background:/s);
    expect(css).toMatch(/\.visual-professional-view-tabs button\s*\{[^}]*white-space:\s*nowrap/s);
    expect(css).toMatch(/\.visual-professional-review-view-switch button\[aria-selected="true"\]\s*\{[^}]*background:\s*#fff/s);
    expect(css).toMatch(/\.visual-professional-contract-tools\s*\{[^}]*display:\s*flex/s);
    expect(css).not.toMatch(/\.visual-professional-compact-status\s*\{/s);
  });

  it("centers a single-column anchor workbench without an empty assistant", () => {
    expect(css).toMatch(/\.anchor-results-view\s*\{[^}]*max-width:\s*1120px/s);
    expect(css).toMatch(/\.anchor-review-layout\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
    expect(css).toMatch(/\.anchor-review-main\s*\{[^}]*min-width:\s*0/s);
    expect(css).not.toMatch(/\.anchor-review-assistant\s*\{/s);
    expect(css).not.toMatch(/\.anchor-review-layout button\s*\{[^}]*min-height:\s*42px/s);
  });

  it("preserves the anchor tabs and canvas at 360px", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*900px\)[\s\S]*?\.visual-professional-header\.visual-review-topbar\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*480px\)[\s\S]*?\.visual-professional-header\.visual-review-topbar\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/s);
    expect(css).toMatch(/\.anchor-tabs\s*\{[^}]*max-width:\s*100%[^}]*overflow-x:\s*auto/s);
    expect(css).toMatch(/\.anchor-canvas\s*\{[^}]*max-width:\s*100%/s);
  });

  it("keeps compact tab labels and readable feedback rows without document overflow", () => {
    expect(css).toMatch(/\.anchor-tabs button\s*\{[^}]*min-width:\s*0[^}]*flex:\s*1 1 0[^}]*overflow:\s*hidden/s);
    expect(css).toMatch(/\.anchor-draft-list li\s*\{[^}]*min-width:\s*0[^}]*padding:/s);
    expect(css).toMatch(/\.anchor-draft-item-head\s*\{[^}]*display:\s*flex/s);
    expect(css).toMatch(/\.anchor-draft-marker\s*\{[^}]*flex:\s*0 0 auto/s);
    expect(css).toMatch(/\.anchor-draft-target\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).toMatch(/\.visual-contract-page-id\s*\{[^}]*overflow:\s*hidden[^}]*text-overflow:\s*ellipsis/s);
    expect(css).toMatch(/\.visual-contract-slide-key\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).not.toMatch(/\.anchor-review-layout button\s*\{[^}]*min-height:\s*42px/s);
  });

  it("keeps contract actions inside the topbar and collapses contract columns on narrow screens", () => {
    expect(css).toMatch(/\.visual-professional-contract-tools\s+\.visual-contract-commandbar\s*\{[^}]*display:\s*flex/s);
    expect(css).not.toMatch(/\.visual-contract-commandbar\s*\{[^}]*position:\s*sticky/s);
    expect(css).toMatch(/\.visual-contract-document\s*\{[^}]*width:\s*min\(1180px,/s);
    expect(css).toMatch(/\.visual-anchor-evidence-strip\s*\{[^}]*grid-template-columns:\s*repeat\(3,/s);
    expect(css).toMatch(/\.visual-slide-contract\s*\{[^}]*contain-intrinsic-inline-size:\s*none;[^}]*contain-intrinsic-block-size:\s*auto\s+860px;/s);
    expect(css).not.toMatch(/\.visual-slide-contract\s*\{[^}]*contain-intrinsic-size:\s*auto\s+860px;/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*900px\)[\s\S]*?\.visual-contract-columns\s*\{[^}]*grid-template-columns:\s*1fr/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*720px\)[\s\S]*?\.visual-anchor-evidence-strip\s*\{[^}]*grid-template-columns:\s*1fr/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*480px\)[\s\S]*?\.visual-contract-section,\s*\.visual-slide-contract\s*\{[^}]*scroll-margin-top:\s*80px/s);
  });
});
