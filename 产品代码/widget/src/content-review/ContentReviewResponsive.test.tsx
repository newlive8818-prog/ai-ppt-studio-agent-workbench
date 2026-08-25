import { describe, expect, it } from "vitest";

declare const __AI_PPT_CONTENT_REVIEW_CSS__: string;

const css = __AI_PPT_CONTENT_REVIEW_CSS__;

describe("maximum-width content review responsive contract", () => {
  it("uses the entire sidebar width and never centers the document in a max-width wrapper", () => {
    expect(css).toMatch(/\.compact-main-content-review\s*\{[^}]*padding:\s*0/s);
    expect(css).toMatch(/\.content-review-document\s*\{[^}]*width:\s*100%[^}]*min-width:\s*0/s);
    expect(css).not.toMatch(/\.content-review-document\s*\{[^}]*max-width/s);
    expect(css).not.toMatch(/\.content-review-document\s*\{[^}]*margin:\s*0\s+auto/s);
  });

  it("provides wide copy/evidence columns, a below-900 single column, and long-list rendering containment", () => {
    expect(css).toMatch(/\.content-slide-reading-grid\s*\{[^}]*grid-template-columns:\s*minmax\(340px,\s*\.9fr\)\s+minmax\(500px,\s*1\.1fr\)/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*899px\)[\s\S]*\.content-slide-reading-grid\s*\{[^}]*grid-template-columns:\s*1fr/s);
    expect(css).toMatch(/\.content-slide-section\s*\{[^}]*content-visibility:\s*auto[^}]*contain-intrinsic-size:/s);
    expect(css).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it("keeps decision targets at least 42px and uses a non-color 2x2 selected layout below 380px", () => {
    expect(css).toMatch(/\.page-decision-editor fieldset label\s*\{[^}]*min-height:\s*42px/s);
    expect(css).toMatch(/\.decision-save-button,[\s\S]*?min-height:\s*42px/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*379px\)[\s\S]*?\.page-decision-options\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/s);
    expect(css).toMatch(/\.page-decision-editor fieldset label\.selected\s*\{[^}]*box-shadow:/s);
  });

  it.each([480, 900, 1200, 1440])("keeps the %ipx contract represented without horizontal document overflow", (width) => {
    expect([480, 900, 1200, 1440]).toContain(width);
    expect(css).toMatch(/\.content-review-document\s*\{[^}]*overflow-x:\s*clip/s);
    expect(css).toMatch(/\.content-slide-reading-grid\s*>\s*\*\s*\{[^}]*min-width:\s*0/s);
  });
});
