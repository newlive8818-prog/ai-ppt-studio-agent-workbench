import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "widget/src/styles/visual-review.css"), "utf8");

describe("visual anchor review responsive contracts", () => {
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
