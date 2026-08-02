# Native workbench protocol

Use the Widget as a project-backed AI cognition map, not as a second chat transcript. The four spaces are stable; their content and next questions are generated from the current project state.

## Operating loop

1. Call `render_ai_ppt_workbench` or `get_ai_ppt_project_snapshot` and keep its `revision`.
2. Read the active space, open gate, active task, evidence, uncertainty, and allowed actions.
3. For user input, call the matching governed write with `expectedRevision`. Refresh after every successful write; never reuse a stale revision.
4. For AI work, call `request_ai_ppt_agent_action`. Treat the returned task context as the bounded execution brief.
5. Do the requested reasoning or tool work in Codex. Use only task-listed targets and project material.
6. Call `commit_ai_ppt_artifact` with the task ID, artifact kind, structured payload, exact sources, and the task's requested revision.
7. Re-render the workbench. Ask the user only for the concentrated decision shown by the current space.
8. Call `confirm_ai_ppt_gate` only after the user explicitly accepts and the gate evidence checker permits it.

The Widget may request work, but it does not execute model reasoning inside the browser. Codex owns execution; the project store owns durable truth.

## Four spaces

| Space | Agent responsibility | Human responsibility | Gate |
|---|---|---|---|
| 材料空间 | Accept files, pasted text, and links; auto-classify; extract facts, cases, screenshots, images, gaps, and provenance | Correct only material misunderstandings that affect the deck | input to G0 |
| 内容蓝图 | Produce chapters and every slide's objective, claim, visible wording, notes, sources, cases, and asset intentions; do not design visuals | Review the whole narrative and request revisions in natural language | G0 |
| 视觉设计 | Produce structurally distinct concept directions with Image 2, then build difficult and content-complex editable samples with Codex Presentations; freeze the Visual Contract and Scene Graph | Select/revise direction and accept engineering fidelity | G1–G3 |
| 制作与交付 | Build the full editable PPTX with Codex Presentations, render every slide, inspect, repair, and package evidence | Accept the rendered result and editable file | G4 |

## Tool routing

- `add_ai_ppt_material`: one unified inlet for file, text, or user-supplied link. Do not force the user to classify first.
- `request_ai_ppt_agent_action`: create immutable work for classify-materials, generate/revise-blueprint, generate-visual-concepts, build-engineering-samples, build-pptx, qa-render, or repair-pptx.
- `commit_ai_ppt_artifact`: commit only the artifact requested by the active task and keep source references exact.
- `submit_ai_ppt_human_decision`: record user choice or natural-language feedback; do not manufacture a human decision.
- `confirm_ai_ppt_gate`: human confirmation plus machine-checkable evidence.
- `reopen_ai_ppt_scope`: reopen the earliest affected gate for a material change; preserve all prior versions.
- `read_ai_ppt_project_asset`: preview only bounded files inside the managed project.

## Visual and PPTX boundary

- Image 2 creates visual concepts and sample imagery. Its raster output is a design reference or replaceable image layer, never a whole-slide editable implementation.
- Codex Presentations is the only PPTX creation, edit, render, and inspection route.
- G2 requires real editable engineering samples and rendered comparisons before the full deck.
- G4 requires an existing PPTX, real slide renders, passed QA, native business content, and `whole_slide_bitmap=false`.

## Failure and revision behavior

- On `REVISION_CONFLICT`, refresh and re-evaluate; do not retry blindly.
- A failed build or QA run must not overwrite the last valid PPTX or passed artifact.
- Report blocking fact conflicts in the workbench. Make ordinary implementation decisions autonomously.
- A user revision targets the smallest affected artifact. Reopen downstream gates only when the change invalidates their evidence.
