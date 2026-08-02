# Runtime workflow

AI PPT Studio is a Codex-native project workflow for high-quality, editable sales-solution presentations.

## Startup

1. Run `ai-ppt-studio preflight` and use its configured managed runtime root.
2. Create or resume a managed project; never initialize state in the caller's current directory.
3. Import only materials the user provides: files, directories, pasted text, images, or URLs. The production workflow does not search the internet on its own.
4. Let the runtime copy and classify inputs automatically. Uploaded materials are useful by default; resolve content changes later in the concentrated blueprint review.

## Content before visual design

First establish who the presentation is for, what decision it should influence, the reporting context, available evidence, and constraints. Produce and review a content blueprint containing:

- narrative structure and chapters;
- each slide's communication goal, key claim, supporting facts, cases, screenshots, and source citations;
- content gaps or model-assisted additions clearly separated from source facts;
- presenter notes or full wording where needed.

Pass G0 only after structure, per-slide claims, and real material use are frozen. Do not discuss visual styling during this content phase.

## Visual conception and implementation

After G0, create a Visual Brief and two or three meaningfully different concept directions. Use Image 2 as a visual collaborator for concepts and samples, not as the final editable object model. Translate the selected direction into a Visual Contract and Slide Scene Graph constrained by PowerPoint primitives.

Build two difficult engineering samples in real editable PPTX form, render them, and compare them to the concept before freezing the system. Compile the full deck only after G1–G3 pass. Run full-deck fact, layout, font, source, and editability checks before G4.

## State gates

- G0: content frozen; unlock visual conception.
- G1: concept direction approved; unlock engineering samples.
- G2: engineering samples preserve beauty, facts, and editability; unlock final visual contract.
- G3: visual contract frozen with explicit approval; unlock full-deck compilation.
- G4: full rendered deck accepted; unlock delivery and experience capture.

A failed gate reopens only the affected scope. Never silently rewrite previously approved material.

## Review surfaces

Generate disposable, offline HTML pages from project state for concentrated review of content, concepts, engineering samples, and final delivery. The project object files remain authoritative.
