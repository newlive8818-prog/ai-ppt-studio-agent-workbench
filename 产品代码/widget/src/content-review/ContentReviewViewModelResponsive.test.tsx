import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "widget/src/styles/content-review-view-model.css"), "utf8");

describe("accepted content review ViewModel responsive contract", () => {
  it("uses the full host width and keeps text with the page visual on wide screens", () => {
    expect(css).toMatch(/\.content-review-vm-page\s*\{[^}]*width:\s*100%/s);
    expect(css).not.toMatch(/\.content-review-vm-page\s*\{[^}]*max-width:/s);
    expect(css).toMatch(/\.content-review-vm-reading-grid\s*\{[^}]*grid-template-columns:\s*minmax\(340px,\s*\.9fr\)\s+minmax\(500px,\s*1\.1fr\)/s);
    expect(css).toMatch(/\.content-review-vm-image\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9/s);
  });

  it("falls back to one reading column and one purpose column at the approved widths", () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*860px\)[\s\S]*?\.content-review-vm-reading-grid\s*\{[^}]*grid-template-columns:\s*1fr/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*380px\)[\s\S]*?\.content-review-vm-purpose\s*\{[^}]*grid-template-columns:\s*1fr/s);
  });

  it("keeps visible 42px decisions and a two-by-two narrow layout", () => {
    expect(css).toMatch(/\.page-decision-option\s*\{[^}]*min-height:\s*42px/s);
    expect(css).toMatch(/\.page-decision-option\.is-selected\s*\{[^}]*border[^}]*background[^}]*font-weight/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*380px\)[\s\S]*?\.page-decision-options\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*380px\)[\s\S]*?\.page-decision-option\s*\{[^}]*white-space:\s*nowrap/s);
  });

  it("keeps perceptible hover and active feedback on decision controls", () => {
    expect(css).toMatch(/\.page-decision-option:not\(:has\(input:disabled\)\):hover\s*\{[^}]*border-color:[^}]*background:/s);
    expect(css).toMatch(/\.page-decision-option:not\(:has\(input:disabled\)\):active\s*\{[^}]*transform:\s*translateY\(1px\)/s);
    expect(css).toMatch(/\.page-decision-option:has\(input:disabled\)\s*\{[^}]*cursor:\s*not-allowed[^}]*opacity:/s);
    expect(css).not.toMatch(/\.page-decision-option:(?:hover|active)\s*\{/s);
  });
});
