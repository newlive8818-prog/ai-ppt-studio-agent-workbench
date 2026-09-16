# AI PPT Studio Native Workbench Phases B–D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver project-backed Materials, Content Blueprint, Visual Design, and Production & Delivery spaces with governed Agent intents, G0–G4, real project assets, and an installed end-to-end Codex plugin.

**Architecture:** Python remains the only domain writer and creates sanitized all-space projections. Node exposes revision-safe MCP tools and one app-only asset reader. The responsive React Widget turns projections into decision surfaces and sends persisted Agent intents back to Codex for Image 2 and Presentations execution.

**Tech Stack:** Python 3.11+, Node.js ESM, MCP SDK/ext-apps, React 19, TypeScript, Vite, Vitest, Testing Library, Playwright, Codex Image 2, Codex Presentations.

## Global Constraints

- Use only the managed runtime under `/Users/defei/Documents/AI-PPT-Workspace` for project data.
- Do not modify `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT  web app `.
- AI uses only user-provided project material; it does not search for customer material.
- Content Blueprint must pass G0 before formal visual work.
- Image 2 creates concepts; Presentations is the only PPTX creation/edit/render/check route.
- Every write uses expected revision, immutable artifacts/events, and an honest fallback.
- Widget contains no business localStorage and no second PPT editor.

---

### Task 1: Versioned material findings and uploaded material intake

**Files:**
- Modify: `src/ai_ppt_studio/models.py`
- Modify: `src/ai_ppt_studio/artifact_store.py`
- Modify: `src/ai_ppt_studio/materials.py`
- Test: `tests/test_material_findings.py`

**Interfaces:**
- Produces: `ArtifactKind.MATERIAL_FINDINGS`, `ArtifactKind.ENGINEERING_SAMPLES`, `MaterialIntake.add_bytes(project_root, filename, data, mime_type)`.

- [ ] Write a failing test proving `material-findings` validates provenance, `engineering-samples` validates editable/native evidence, and bytes are copied into a managed upload path with stable hash and safe filename.
- [ ] Run `python3 -m unittest tests.test_material_findings` and confirm failure because the enum and method do not exist.
- [ ] Implement the enum, artifact directory/validation, filename normalization, size boundary, and byte intake.
- [ ] Run the focused test and full Python suite.
- [ ] Commit `feat: add governed material findings and uploads`.

### Task 2: Agent tasks, context packs, and space projections

**Files:**
- Create: `src/ai_ppt_studio/agent_tasks.py`
- Create: `src/ai_ppt_studio/context_compiler.py`
- Create: `src/ai_ppt_studio/space_projection.py`
- Modify: `src/ai_ppt_studio/workbench_models.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Test: `tests/test_agent_tasks.py`
- Test: `tests/test_space_projection.py`

**Interfaces:**
- Produces: `AgentTaskStore.request(action_type, target_refs, instructions, expected_revision)`, `ContextCompiler.compile(...)`, `SpaceProjectionBuilder.build()`, `ProjectSnapshot.space_projections`.

- [ ] Write failing tests for immutable task/context creation, task recovery, honest source status without findings, complete blueprint/visual/delivery summaries, and no embedded binary/long notes.
- [ ] Run both focused test modules and confirm missing-class failures.
- [ ] Implement task files, active-task pointer, minimal context packs, and deterministic projections.
- [ ] Integrate projections into every snapshot and run focused plus full tests.
- [ ] Commit `feat: project BCD spaces and governed agent tasks`.

### Task 3: Revision-safe B–D domain writes and gate evidence

**Files:**
- Modify: `src/ai_ppt_studio/errors.py`
- Modify: `src/ai_ppt_studio/workbench_models.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Create: `src/ai_ppt_studio/gate_evidence.py`
- Test: `tests/test_workbench_bcd_writes.py`

**Interfaces:**
- Produces: `add_material`, `request_agent_action`, `commit_artifact`, `confirm_gate`, `reopen_scope` methods returning refreshed `DecisionResult`-compatible results.

- [ ] Write failing tests for one-revision writes, no partial conflict writes, task completion on artifact commit, G0–G4 missing-evidence errors, sequential passing, and reopen preservation.
- [ ] Run the focused test and confirm expected missing-method failures.
- [ ] Implement the gate evidence checker and the five locked writes.
- [ ] Run focused and full Python tests.
- [ ] Commit `feat: add revision-safe BCD writes and quality gates`.

### Task 4: Extend the machine bridge and MCP tools

**Files:**
- Modify: `src/ai_ppt_studio/workbench_bridge.py`
- Modify: `mcp/server.mjs`
- Create: `mcp/project-asset.mjs`
- Modify: `tests/test_workbench_bridge.py`
- Modify: `tests/mcp-server.test.mjs`
- Create: `tests/project-asset.test.mjs`

**Interfaces:**
- Produces MCP tools `add_ai_ppt_material`, `request_ai_ppt_agent_action`, `commit_ai_ppt_artifact`, `confirm_ai_ppt_gate`, `reopen_ai_ppt_scope`, `read_ai_ppt_project_asset`.

- [ ] Write failing bridge/MCP tests for schemas, stable errors, app-only asset visibility, path containment, MIME, accepted writes, and stale writes.
- [ ] Run focused Python and Node tests and observe missing operations/tools.
- [ ] Implement bridge dispatch, MCP registration, and project asset reader.
- [ ] Run focused and full Node/Python suites.
- [ ] Commit `feat: expose BCD workbench MCP contract`.

### Task 5: Phase B Materials and Blueprint Widget

**Files:**
- Modify: `widget/src/types.ts`
- Create: `widget/src/components/MaterialsWorkspace.tsx`
- Create: `widget/src/components/BlueprintWorkspace.tsx`
- Create: `widget/src/components/SpaceConclusion.tsx`
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/lib/mcp-app-client.ts`
- Modify: `widget/src/styles.css`
- Create: `widget/src/PhaseB.test.tsx`

**Interfaces:**
- Consumes `space_projections.materials`, `space_projections.blueprint`, and the new MCP write results.

- [ ] Write failing component tests for unified material input, automatic-task messaging, dense source list, content-before-visual rule, chapter/slide selection, and G0 action.
- [ ] Run `npx vitest run widget/src/PhaseB.test.tsx` and confirm missing components.
- [ ] Implement the two workspaces, host bridge calls, save-before-follow-up behavior, and responsive styles.
- [ ] Run Widget tests, typecheck, and build.
- [ ] Commit `feat: connect materials and content blueprint workspaces`.

### Task 6: Phase C Visual Widget

**Files:**
- Create: `widget/src/components/VisualWorkspace.tsx`
- Create: `widget/src/components/ProjectAssetImage.tsx`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/styles.css`
- Create: `widget/src/PhaseC.test.tsx`

**Interfaces:**
- Consumes visual projection, asset reader, human decision, Agent action, and gate tools.

- [ ] Write failing tests for structural direction comparison, honest Image 2/PPTX labels, selection persistence ordering, editability risk, and G1–G3 action changes.
- [ ] Run the focused test and confirm missing-component failures.
- [ ] Implement direction list, selected preview, engineering evidence, Visual Contract inspector, and dynamic primary action.
- [ ] Run Widget tests, typecheck, and build.
- [ ] Commit `feat: connect visual concept and engineering workspace`.

### Task 7: Phase D Delivery Widget

**Files:**
- Create: `widget/src/components/DeliveryWorkspace.tsx`
- Create: `widget/src/components/GateStrip.tsx`
- Create: `widget/src/components/SlideContactSheet.tsx`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/styles.css`
- Create: `widget/src/PhaseD.test.tsx`

**Interfaces:**
- Consumes delivery projection, asset reader, Agent action, gate confirmation, and local file refs.

- [ ] Write failing tests for G0–G4 state, real editable/QA labels, contact sheet, selected render, preserved last build, delivery files, and G4 action blocking.
- [ ] Run the focused test and confirm missing-component failures.
- [ ] Implement delivery conclusion, gate strip, contact sheet, QA inspector, recovery action, and final acceptance action.
- [ ] Run Widget tests, typecheck, and build.
- [ ] Commit `feat: connect production QA and delivery workspace`.

### Task 8: Skill routing, package version, and installed plugin

**Files:**
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Create: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `scripts/install-plugin.mjs`
- Modify: `scripts/probe-mcp.mjs`
- Modify: `tests/plugin-shape.test.mjs`

**Interfaces:**
- Produces a versioned personal plugin whose Skill teaches Codex to resume tasks, use Image 2/Presentations, and commit artifacts/results.

- [ ] Write failing shape/probe assertions for the B–D tool set and Skill router reference.
- [ ] Run Node shape tests and confirm failure.
- [ ] Update Skill, package version, installer, and probe.
- [ ] Run plugin validation and source stdio probe.
- [ ] Install through the personal marketplace and probe the cached installed bundle.
- [ ] Commit `release: install complete AI PPT Studio workbench`.

### Task 9: End-to-end acceptance with the existing real project

**Files:**
- Modify: `scripts/create-widget-preview.mjs`
- Create: `scripts/create-bcd-acceptance-report.mjs`
- Create local ignored outputs: `output/playwright/bcd-*`
- Create: `docs/phases-bcd-acceptance.md`

**Interfaces:**
- Uses `/Users/defei/Documents/AI-PPT-Workspace/projects/ai-ppt-studio-智慧园区冒烟项目-c8a82730` read-only for all-space visual evidence and a dedicated acceptance project for write/conflict/gate tests.

- [ ] Verify the real PPTX with Presentations archive/render checks and verify every declared render path.
- [ ] Start a local preview server and screenshot all five spaces at 1440×1024 plus compact 360/420/480 views.
- [ ] Assert no console errors, no horizontal overflow, one strongest action, and real project content in every space.
- [ ] Run accepted/stale write and gate probes on the dedicated acceptance project.
- [ ] Generate the machine-readable report and acceptance document.
- [ ] Run the complete Python, Node, Widget, type, plugin, MCP, PPTX, and installed-bundle verification matrix.
- [ ] Commit `test: accept AI PPT Studio phases B through D`.

## Plan self-review

- Every PRD P0 item for MAT, BPT, VIS, DEL, AGT, and G0–G4 has an implementation or acceptance task.
- All production behaviors start with focused failing tests.
- Artifact/tool/type names are consistent across Python, MCP, and Widget tasks.
- No independent Web app, cloud queue, second PPT engine, or direct Widget model call is introduced.
- End-to-end acceptance separates read-only real-project visual evidence from dedicated write-path tests.
