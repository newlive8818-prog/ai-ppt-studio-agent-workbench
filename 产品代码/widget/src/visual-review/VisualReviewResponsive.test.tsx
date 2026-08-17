import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "widget/src/styles/visual-review.css"), "utf8");

describe("visual anchor review responsive contracts", () => {
  it("uses a white project topbar with a segmented review switch and compact status", () => {
    expect(css).toMatch(/\.visual-professional-header\.visual-review-topbar\s*\{[^}]*border-bottom:\s*1px solid[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*\.96\)/s);
    expect(css).toMatch(/\.visual-professional-ai-mark\s*\{[^}]*display:\s*grid[^}]*place-items:\s*center/s);
    expect(css).toMatch(/\.visual-professional-review-view-switch\s*\{[^}]*border:\s*1px solid[^}]*border-radius:\s*9px[^}]*background:/s);
    expect(css).toMatch(/\.visual-professional-review-view-switch button\[aria-selected="true"\]\s*\{[^}]*background:\s*#fff/s);
    expect(css).toMatch(/\.visual-professional-compact-status\s*\{[^}]*display:\s*flex/s);
  });

  it("uses a bounded assistant column without shrinking the primary slide workbench", () => {
    expect(css).toMatch(/\.anchor-review-layout\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(300px,\s*360px\)/s);
    expect(css).toMatch(/\.anchor-review-main\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.anchor-review-assistant\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.anchor-review-layout button\s*\{[^}]*min-height:\s*42px/s);
  });

  it("puts the assistant after the main column and preserves all tabs at 360px", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*720px\)[\s\S]*?\.anchor-review-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*720px\)[\s\S]*?\.anchor-review-main\s*\{[^}]*grid-column:\s*1[^}]*grid-row:\s*1/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*720px\)[\s\S]*?\.anchor-review-assistant\s*\{[^}]*grid-column:\s*1[^}]*grid-row:\s*2/s);
    expect(css).toMatch(/\.anchor-tabs\s*\{[^}]*max-width:\s*100%[^}]*overflow-x:\s*auto/s);
    expect(css).toMatch(/\.anchor-canvas\s*\{[^}]*max-width:\s*100%/s);
  });

  it("offsets the medium-width sticky assistant below the taller header", () => {
    expect(css).toMatch(
      /@media\s*\(max-width:\s*900px\)[\s\S]*?\.anchor-review-assistant\s*\{[^}]*top:\s*116px[^}]*max-height:\s*calc\(100vh\s*-\s*136px\)/s,
    );
  });
});
