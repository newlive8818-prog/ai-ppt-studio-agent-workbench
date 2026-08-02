# Codex Presentations handoff

Codex Presentations is mandatory for all PPTX work. Do not create another general slide compiler and do not use `python-pptx`.

## Before PPTX work

Load the Codex `Presentations` skill and follow its current instructions. Read its required `style_guidelines.md`, `artifact_tool_docs/API_QUICK_START.md`, and `artifact_tool_docs/api/API_DOCS.md`. If a user supplies a PPTX/template/reference deck, also load the template-following guidance and preserve master-layout-slide hierarchy.

## Presentation handoff object

Provide Presentations with:

- latest frozen content-blueprint reference;
- selected concept-set and frozen visual-contract reference;
- slide-scene-graph reference;
- real local assets and their source records;
- output PPTX path inside the managed project;
- render directory inside the managed project;
- source-note record;
- change scope: whole deck, chapter, slide, or element;
- gate and revision that authorize the work.

## Editability contract

Business-semantic editability is mandatory:

- native: titles, body text, labels, facts, numbers, tables, charts, simple diagrams, arrows, relationships, logos, and page markers;
- separate replaceable image layers: photos, screenshots, complex illustration, texture, atmospheric background, or Image 2 art;
- prohibited: whole-slide raster output, baked factual text, untraceable numbers, and decorative image layers that prevent normal content editing.

## Engineering samples

Build one visually difficult slide and one content-complex slide first. Render at full slide size and compare concept intent, scene structure, real PPT output, and editability. Fix every unintended overlap, clip, title wrap, crop error, font mismatch, broken connector, and source-note defect before G2.

## Full-deck QA

Use Presentations to generate or modify the whole deck only after G3. Include `[Sources]` blocks in speaker notes for non-trivial claims and external assets. Render every final slide, inspect each individually, use a montage only for deck rhythm, and run the Presentations overflow test. G4 requires clean renders, coherent narrative, source coverage, and editable business content.
