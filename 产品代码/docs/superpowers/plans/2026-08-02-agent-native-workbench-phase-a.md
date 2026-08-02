# AI PPT Studio Agent Native Workbench Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付第一个可安装、可在 Codex 中打开、可读取真实 AI PPT 项目、可提交一次人工判断并产生新 revision 的 Native Widget 垂直切片。

**Architecture:** 保留 Python 业务运行时为唯一领域写入者；Node MCP Server 负责 Codex/MCP Apps 协议；React Widget 只通过 MCP 工具读写。Phase A 只实现 `UI-00 紧凑视图 + UI-01 项目总览`，但五个稳定认知空间以状态化导航占位，后续 Phase B–D 在同一壳内扩展。

**Tech Stack:** Python 3.11+、Node.js ESM、`@modelcontextprotocol/sdk`、`@modelcontextprotocol/ext-apps`、React、TypeScript、Vite、Vitest、Testing Library、Playwright、Codex Plugin Manifest。

**Authority:** `PRJ-001/003/004/005/006`、`AGT-001/002/004/005`、`CMP-01/02/03/04/05/07/10`、`UI-00/UI-01`、`UI-C01/02/03/04/05/06/09/12/13`。

---

## Phase A acceptance contract

The slice is complete only when all of these are true:

1. `codex plugin list` shows `ai-ppt-studio@personal` installed and enabled.
2. MCP initialize/list-tools/list-resources succeeds over stdio.
3. `render_ai_ppt_workbench` returns a `text/html;profile=mcp-app` resource.
4. The Widget opens the existing smoke project read-only and shows project name, delivery goal, audience, current AI judgment, uncertainty, gate status, artifacts, and one current decision.
5. Compact widths 360/420/480 and fullscreen 1440×1024 render without overflow.
6. Submitting a decision with the current revision creates an immutable decision record, appends an event, increments revision, and returns a refreshed projection.
7. Submitting the same stale revision returns `REVISION_CONFLICT` without overwriting the accepted decision.
8. The Widget first persists the decision, then sends model context/follow-up when supported; unsupported bridge features display an honest saved-state fallback.
9. Reopening the Widget reconstructs state from the project directory, not localStorage.
10. Existing 36 Python tests remain green; new Python, Node, Widget, manifest, and end-to-end checks pass.

## Task 1: Freeze the approved baseline and preserve isolation

**Files:**

- Modify: `../00-唯一研发基线索引-v1.0.md`
- Modify: `../01-产品需求基线-v1.0.md`
- Modify: `../02-系统详细设计-v1.0.md`
- Modify: `../03-UI设计与交互规范-v1.0.md`
- Create: `docs/superpowers/plans/2026-08-02-agent-native-workbench-phase-a.md`

- [x] Record the 2026-08-02 user instruction as RC1 approval; do not change functional scope.
- [x] Verify all Markdown relative links and prototype targets resolve.
- [x] Run the existing Python suite as the pre-change baseline.
- [x] Commit documentation before production implementation.

Verification:

```bash
python3 -m unittest discover -s tests
python3 - <<'PY'
from pathlib import Path
import re
root = Path('..').resolve()
for name in ('00-唯一研发基线索引-v1.0.md','01-产品需求基线-v1.0.md','02-系统详细设计-v1.0.md','03-UI设计与交互规范-v1.0.md'):
    text = (root / name).read_text(encoding='utf-8')
    for target in re.findall(r'\[[^]]+\]\((\./[^)#]+)', text):
        assert (root / target[2:]).exists(), (name, target)
print('BASELINE_LINKS_OK')
PY
```

## Task 2: Define the Phase A project projection and migration

**Files:**

- Create: `src/ai_ppt_studio/workbench_models.py`
- Create: `src/ai_ppt_studio/workbench_store.py`
- Modify: `src/ai_ppt_studio/project_store.py`
- Modify: `src/ai_ppt_studio/errors.py`
- Create: `tests/test_workbench_store.py`

Projection files are additive:

```text
<project>/cognition/map.json
<project>/cognition/decisions.jsonl
<project>/state/workbench.json
```

`state/workbench.json` owns `schema_version`, `revision`, `active_space`, `updated_at`, `last_human_decision_id`, and `current_decision`. Existing `state/state.json` remains the G0–G4 source and is not rewritten by migration.

- [x] Write failing tests for schema-1.0 project migration, repeatable reopen, latest-artifact projection, current gate projection, and protected paths.
- [x] Add `cognition` to new project directories without changing existing directory contracts.
- [x] Implement an additive, idempotent `WorkbenchStore.ensure()` migration.
- [x] Derive an honest default cognition map from Mission, Content Blueprint, project sources, artifacts, and G0–G4 state. Missing data must become explicit uncertainty, never invented facts.
- [x] Return a compact, JSON-serializable `ProjectSnapshot`; do not expose whole materials or hidden reasoning.
- [x] Run the focused tests, then the full Python suite.

## Task 3: Implement revision-safe human decisions

**Files:**

- Modify: `src/ai_ppt_studio/workbench_models.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Create: `tests/test_workbench_decisions.py`

Write contract:

```json
{
  "project_root": "/managed/project",
  "expected_revision": 0,
  "target_ref": "decision://current",
  "choice": "confirm|reject|revise",
  "feedback": "optional user wording"
}
```

- [x] Write failing tests for accepted write, append-only decision/event, revision increment, stale write conflict, empty choice, and reopen persistence.
- [x] Implement a per-project lock and atomic `workbench.json` replacement.
- [x] Append the human decision only after revision validation.
- [x] Return `follow_up_message`, `model_context`, `affected_artifacts`, and refreshed snapshot.
- [x] Guarantee a conflict has no partial decision or event append.

## Task 4: Expose a machine-only Python bridge

**Files:**

- Create: `src/ai_ppt_studio/workbench_bridge.py`
- Create: `tests/test_workbench_bridge.py`

Bridge operations:

- `list-projects`
- `get-project-snapshot`
- `submit-human-decision`

The bridge reads one JSON request from stdin and writes exactly one JSON result to stdout. Errors use stable codes: `PROJECT_NOT_FOUND`, `PATH_PROTECTED`, `REVISION_CONFLICT`, `VALIDATION_ERROR`, `INTERNAL_ERROR`.

- [x] Write subprocess tests first and confirm they fail.
- [x] Implement JSON request validation and runtime configuration loading.
- [x] Select the latest managed project only when no explicit project root is given; always return the selected root.
- [x] Keep diagnostics on stderr and never print secrets or free-form tracebacks to stdout.

## Task 5: Scaffold and validate the Codex plugin package

**Files:**

- Create: `.codex-plugin/plugin.json`
- Create: `.mcp.json`
- Create: `package.json`
- Create: `package-lock.json`
- Create: `scripts/start-mcp.mjs`
- Create: `scripts/install-plugin.mjs`
- Create: `tests/plugin-shape.test.mjs`
- Consolidate: `skill/ai-ppt-studio/` → `skills/ai-ppt-studio/`

- [ ] Write a failing Node shape test for manifest, `.mcp.json`, server entry, built Widget resource, and one authoritative Skill source.
- [ ] Add a strict semver manifest with interface metadata and local brand assets.
- [ ] Configure stdio MCP startup using relative plugin paths.
- [ ] Move the authoritative Skill source to `skills/`; update Python bundle/install tests and scripts so legacy skill installation is generated from it.
- [ ] Run the official `plugin-creator` validator.

## Task 6: Implement MCP data tools and UI resource

**Files:**

- Create: `mcp/runtime-bridge/python-runtime.mjs`
- Create: `mcp/widget-resource.mjs`
- Create: `mcp/server.mjs`
- Create: `tests/mcp-runtime-bridge.test.mjs`
- Create: `tests/mcp-server.test.mjs`

Tools:

1. `get_ai_ppt_project_snapshot` — headless read tool.
2. `submit_ai_ppt_human_decision` — headless write tool.
3. `render_ai_ppt_workbench` — render tool owning `ui://ai-ppt-studio/workbench.html`.

- [ ] Write failing Node tests for Python process invocation, stable error mapping, tool schemas, structured content, Widget metadata, and MIME type.
- [ ] Implement the Python bridge runner without shell interpolation.
- [ ] Register the three tools and one app resource using MCP SDK/ext-apps.
- [ ] Keep data tools usable without UI; only the render tool owns `_meta.ui.resourceUri`.
- [ ] Return minimal model-visible content and richer Widget data without full material bodies.

## Task 7: Build UI-00 and UI-01 as one responsive Widget

**Files:**

- Create: `widget/index.html`
- Create: `widget/src/main.tsx`
- Create: `widget/src/App.tsx`
- Create: `widget/src/styles.css`
- Create: `widget/src/types.ts`
- Create: `widget/src/lib/mcp-app-client.ts`
- Create: `widget/src/components/*`
- Create: `widget/src/App.test.tsx`
- Create: `widget/vite.config.ts`
- Create: `widget/tsconfig.json`

- [ ] Write failing component tests for conclusion-first order, one primary action, fact/inference/decision/uncertainty labels, decision save-before-follow-up, fallback messaging, and compact/fullscreen navigation.
- [ ] Implement ProjectHeader, StableNavigation, ConclusionStrip, cognition map, ContextInspector, DecisionPanel, GateIndicator, and CodexBridgeAction.
- [ ] At 360–480px render the compact vertical cognition thread; at ≥1080px render the full navigation/main/inspector shell.
- [ ] Use shared MCP Apps methods for tool calls, model context, messages, display mode, and size notifications; feature-detect optional host capabilities.
- [ ] Do not store business state in localStorage; remount must fetch a fresh snapshot.
- [ ] Use system fonts, semantic text plus color, visible focus, and one strongest primary action.

## Task 8: Bundle the Widget into the MCP App resource

**Files:**

- Create: `scripts/build-widget.mjs`
- Modify: `mcp/widget-resource.mjs`
- Modify: `package.json`
- Create: `tests/widget-bundle.test.mjs`

- [ ] Write a failing test requiring a single self-contained HTML resource with no external scripts, stylesheets, or web-font dependency.
- [ ] Build React/CSS, inline assets, and escape `</script>` safely.
- [ ] Add CSP/resource metadata and descriptive Widget metadata.
- [ ] Make `npm test` build before MCP resource tests.

## Task 9: Verify responsive UI and real MCP behavior

**Files:**

- Create: `scripts/probe-mcp.mjs`
- Create: `scripts/preview-widget.mjs`
- Create: `tests/e2e/workbench.spec.ts`
- Create: `artifacts/phase-a/` outputs during verification

- [ ] Create a dedicated managed Phase A acceptance project; keep the existing smoke and user projects read-only during write-path verification.
- [ ] Probe MCP initialize, tools/list, resources/list, render, snapshot, accepted decision, and stale-revision conflict over stdio.
- [ ] Render the real smoke project at 420×900 and 1440×1024 with Playwright.
- [ ] Check console errors, horizontal overflow, decision persistence, remount recovery, and fullscreen capability fallback.
- [ ] Save screenshots and a machine-readable acceptance report under `artifacts/phase-a/`.
- [ ] Run all Python and Node tests plus plugin validation.

## Task 10: Install the personal plugin and prove Codex readiness

**Files:**

- Runtime install: `/Users/defei/plugins/ai-ppt-studio`
- Marketplace: managed via plugin-creator scaffold/update tooling, not manual JSON editing

- [ ] Build a clean plugin bundle and copy it to the personal plugin root without moving project source.
- [ ] Add/update `ai-ppt-studio` in the personal marketplace through the supported scaffold/update script.
- [ ] Run `codex plugin add ai-ppt-studio@personal` and confirm enabled status.
- [ ] Re-run the MCP probe from the installed bundle, not only source.
- [ ] Confirm reinstall does not alter `/Users/defei/Documents/AI-PPT-Workspace` project data.
- [ ] Record that an already-open Codex task may need a new task to load the new MCP schema; this is host lifecycle behavior, not a product-data failure.

## Final verification commands

```bash
python3 -m unittest discover -s tests
npm ci
npm test
npm run build
python3 /Users/defei/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
node scripts/probe-mcp.mjs
codex plugin list
git status --short
```

Expected handoff artifacts:

- installed and enabled `ai-ppt-studio@personal`;
- source plugin and Widget in `产品代码/`;
- compact and fullscreen screenshots;
- `artifacts/phase-a/acceptance-report.json`;
- a decision written to the dedicated Phase A acceptance project with an incremented revision and conflict proof;
- all test and validator outputs green.
