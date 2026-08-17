import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "widget/src/styles/content-review.css"), "utf8");

describe("content review responsive contracts", () => {
  it("keeps complete copy and 16:9 material together in the wide reading grid", () => {
    expect(css).toMatch(/\.content-slide-reading-grid\s*\{[^}]*grid-template-columns:\s*minmax\(340px,\s*\.9fr\)\s+minmax\(500px,\s*1\.1fr\)/s);
    expect(css).toMatch(/\.content-material-image\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*900px\)[\s\S]*?\.content-slide-reading-grid\s*\{[^}]*grid-template-columns:\s*1fr/s);
  });

  it("keeps 42px decision targets in a two-by-two non-wrapping grid at 360px", () => {
    expect(css).toMatch(/\.page-decision-option\s*\{[^}]*min-height:\s*42px/s);
    expect(css).toMatch(/\.page-decision-option\.is-selected\s*\{[^}]*border[^}]*background[^}]*font-weight/s);
    expect(css).toMatch(/\.page-decision-option\.is-selected::before\s*\{[^}]*border-radius:\s*50%/s);
    expect(css).toMatch(/\.page-decision-option:has\(input:focus-visible\)\s*\{[^}]*outline:/s);
    expect(css).toMatch(/\.page-decision-option:where\(:not\(:has\(input:disabled\)\)\):hover\s*\{[^}]*border[^}]*background[^}]*color[^}]*box-shadow[^}]*transform:\s*translateY\(-1px\)/s);
    expect(css).toMatch(/\.page-decision-option:where\(:not\(:has\(input:disabled\)\)\):active\s*\{[^}]*box-shadow[^}]*transform:\s*translateY\(0\)\s*scale\(\.99\)/s);
    expect(css).toMatch(/\.page-decision-option:has\(input:disabled\)\s*\{[^}]*cursor:\s*not-allowed/s);
    expect(css).toMatch(/\.page-decision-option--approved\.is-selected[\s\S]*\.page-decision-option--modify\.is-selected[\s\S]*\.page-decision-option--evidence\.is-selected[\s\S]*\.page-decision-option--merge-or-delete\.is-selected/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*380px\)[\s\S]*?\.page-decision-options\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*380px\)[\s\S]*?\.page-decision-option\s*\{[^}]*white-space:\s*nowrap/s);
  });
});
