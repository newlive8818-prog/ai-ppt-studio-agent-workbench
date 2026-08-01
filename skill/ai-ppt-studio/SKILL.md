---
name: ai-ppt-studio
description: Create, resume, review, edit, render, and deliver isolated high-design editable PowerPoint projects in Codex, initially for reading-first sales-solution presentations. Use when a user asks to make, redesign, continue, inspect, revise, or deliver a PPT/PPTX through AI PPT Studio.
---

# AI PPT Studio

Treat AI as the principal presentation strategist and maker. Let the user concentrate on audience, facts, decisions, visual direction, and final acceptance—not implementation choices.

## Required startup

1. Read isolation-policy.md before any file write, using `references/isolation-policy.md`.
2. Read `references/runtime-workflow.md` before creating or resuming a project.
3. Run `python3 scripts/ai_ppt_runtime.py preflight`; it discovers the managed workspace profile automatically.
4. Initialize or resume a project under the managed runtime root. Never write into the current working directory unless it is that managed project.
5. After mission context is known, run `experience-recommend --input CONTEXT.json`. Inspect scope, evidence level, and match reasons; a recommendation is not silent permission to apply it.
6. When a recommendation materially influences work, record the exact version with `experience-apply --project PROJECT --experience ID --input CONTEXT.json`.
7. Treat user-provided originals as read-only. Copy before OCR, conversion, crop, annotation, or transformation.
8. Use only sources the user provides. Do not search the internet for customer-project material.

## Capability routing

- GPT performs audience understanding, narrative, content synthesis, visual reasoning, critique, and scoped revision.
- Image 2 is the visual concept collaborator. No separate Image 2 privacy gate exists in this product; user-provided materials may be used when the visual task needs them.
- Codex Presentations is the sole execution route for every PPTX read, create, edit, render, and inspection operation. Do not build or use a second PPTX editor or compiler. Never use `python-pptx`.
- Offline HTML pages support concentrated decisions; versioned project artifacts remain authoritative.
- `my-ppt-master`, local examples, courses, and outside references are inspiration only, never decision dependencies.

## G0–G4 workflow

### 1. Mission and materials

Establish who will read or hear the deck, what decision it should influence, the work context, known concerns, and available user-provided materials. Import materials through the runtime; let AI classify and extract useful facts, cases, screenshots, and images. Ask only one high-impact missing requirement at a time.

### 2. Content before visual design — G0

Read `references/content-workflow.md`. Produce the complete narrative, chapters, every slide's purpose/claim/visible wording/speaker notes, and exact material/source references. Keep facts, source-derived inference, and AI-authored connective content distinguishable. Generate the content review HTML. Freeze G0 only after concentrated user confirmation. Do not discuss style before G0.

### 3. Visual conception — G1

Read `references/visual-workflow.md`. Create the Visual Brief and two or three structurally different concept directions. Use Image 2 when a high-quality concept or sample materially improves the decision; do not treat its raster result as the final editable slide model. Generate the concept comparison HTML. Pass G1 after the main direction is selected or deliberately revised.

### 4. Engineering samples — G2

Read `references/presentations-handoff.md`. Create a minimal Slide Scene Graph and a visual-contract candidate. Use Codex Presentations to build one visually difficult page and one content-complex page as real editable PPTX slides. Render both, inspect them at full size, compare concept intention against editable output, fix all unintended overlaps/clipping/wrapping, and generate the engineering comparison HTML. Pass G2 only when beauty, facts, and business editability survive.

### 5. Visual contract and full deck — G3 and G4

Freeze the Visual Contract at G3 after concentrated human approval. Then use Codex Presentations to create or edit the complete PPTX. Keep fact text, numbers, charts, tables, diagrams, relationships, and brand content native editable; complex art may be a separate replaceable/croppable image layer. Never use a whole-slide bitmap. Render and inspect every slide, run overflow checks, generate the delivery review HTML, and pass G4 only after defects and source notes are resolved.

### 6. Revision and learning

Read `references/review-and-feedback.md` for scoped changes and `references/experience-evolution.md` before promoting any learning. Preserve old versions. Reopen only affected gates. Record raw feedback separately from model interpretation. After the user accepts, rejects, or materially revises experience-influenced work, run `experience-evaluate --application ID --input EVALUATION.json`. A single reaction never changes the stable Skill core.

## User interaction rule

Work autonomously between concentrated decisions. The normal user checkpoints are content blueprint, visual direction, engineering sample plus visual contract, and final rendered deck. Interrupt earlier only for a fact conflict, missing decision objective, unreadable critical source, or ambiguous high-impact request. Never ask the user to choose implementation technology.
