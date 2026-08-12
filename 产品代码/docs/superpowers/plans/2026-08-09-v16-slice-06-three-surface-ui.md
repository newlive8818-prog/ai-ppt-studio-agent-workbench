# v1.6 Slice 06 Three-Surface UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per the user's explicit instruction, execute inline without subagents or a worktree and make one unified commit only after final acceptance.

**Goal:** Connect the schema 3.0 authoritative runtime to a 360–480px Native Widget and one 760/1000/1440px professional-review application, including host-aware routing, exact review marks, long-document performance, conflict recovery, accessibility, and deterministic visual evidence.

**Architecture:** A new Python `WorkspaceProjectionService` derives the compact five-space projection solely from current schema 3.0 artifact heads and gate state. Node stays a thin adapter, React consumes only this formal projection, and content/visual review continue to share `ReviewService`, `ReviewProjection`, `ProfessionalReviewApp`, and `save_review_marks`. Host context selects inline review only at supported widths and otherwise requests the same review resource in fullscreen/independent form; UI state never becomes a second business truth source.

**Tech Stack:** Python 3.0 kernel/application services and unittest; Node.js ESM, Zod, and MCP Apps; React 19, TypeScript, Vitest, Testing Library, CSS; Playwright from the bundled Codex runtime.

**Requirement coverage:** PRJ-003/004/006/007, BPT-005/014/016, VIS-008/009/020/021, DEL-011, AGT-001/002/004/006, UI-00–UI-05, UI-C01/UI-C02/UI-C16/UI-C23/UI-C33–UI-C38, PRD 17.1.1–17.1.6 and 17.5.1–17.5.7, SDD 19.1 and 21.4, UI baseline 23.2.1–23.2.25 and 23.4.

---

### Task 1: Schema 3.0 authoritative Widget projection

**Files:**
- Create: `src/ai_ppt_studio/application/workspace_projection.py`
- Create: `tests/test_v16_workspace_projection.py`
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `tests/test_v16_bridge.py`

- [x] **Step 1: Write failing projection contract tests**

Create a schema 3.0 project from the existing v1.6 fixtures and assert that `get-project-snapshot` returns this stable top-level shape:

```python
self.assertEqual(snapshot["schema_version"], "3.0")
self.assertEqual(
    set(snapshot["workspace"]),
    {"active_space", "navigation", "overview", "materials", "blueprint", "visual", "delivery"},
)
self.assertEqual([item["space_id"] for item in snapshot["workspace"]["navigation"]], [
    "overview", "materials", "blueprint", "visual", "delivery",
])
self.assertNotIn("space_projections", snapshot)
self.assertNotIn("score", json.dumps(snapshot, ensure_ascii=False).lower())
```

Assert that content/visual review availability is computed from the current formal source head plus Gate state, that four target rows come from `DeliveryService.delivery_status_projection()`, and that an absent or stale artifact never becomes `passed` merely because a slot name exists.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.test_v16_workspace_projection tests.test_v16_bridge -v`

Expected: FAIL because `snapshot["workspace"]` and `WorkspaceProjectionService` do not exist.

- [x] **Step 3: Implement the projection service**

Implement a read-only service that resolves only current content-addressed heads and emits compact, display-ready values:

```python
class WorkspaceProjectionService:
    SPACE_IDS = ("overview", "materials", "blueprint", "visual", "delivery")

    def project(self) -> dict[str, Any]:
        state = self.kernel.load()
        delivery = DeliveryService(self.kernel).delivery_status_projection()
        return {
            "active_space": self._active_space(state),
            "navigation": self._navigation(state, delivery),
            "overview": self._overview(state),
            "materials": self._materials(state),
            "blueprint": self._blueprint(state),
            "visual": self._visual(state),
            "delivery": delivery,
        }
```

Every space must contain one conclusion, one highest risk/focus, affected artifact identity, a typed primary action (`continue-chat|handle-decision|open-content-review|open-visual-review|none`), and evidence/state counts only. Resolve `mission`, `materials`, `content/blueprint`, `content/acceptance`, `visual/contract`, review-mark heads, and delivery artifacts through `ArtifactReference`; do not copy full contracts or silently fall back to v1.5 projection rules.

- [x] **Step 4: Wire the service into the v1.6 bridge**

Replace the ad-hoc schema 3 snapshot assembly with the formal projection while retaining `project`, `gate_state`, `artifacts`, `experience`, and `revision`. The bridge remains JSON-only and contains no display/Gate inference.

- [x] **Step 5: Verify GREEN and full Python regression**

Run: `python3 -m unittest tests.test_v16_workspace_projection tests.test_v16_bridge tests.test_v16_delivery_bridge -v`

Expected: all focused tests PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all Python tests PASS with no warning/error output.

### Task 2: Replace the v1.5 Widget data contract with the formal schema 3 projection

**Files:**
- Modify: `widget/src/types.ts`
- Modify: `widget/src/test-fixtures.ts`
- Modify: `widget/src/App.test.tsx`
- Modify: `widget/src/PhaseB.test.tsx`
- Modify: `widget/src/PhaseC.test.tsx`
- Modify: `widget/src/PhaseD.test.tsx`
- Modify: `tests/mcp-server.test.mjs`

- [x] **Step 1: Write failing TypeScript and MCP contract tests**

Change fixtures to `schema_version: "3.0"` and a `workspace` object. Add assertions that the Widget fixture and rendered MCP `_meta.widgetData` do not expose `space_projections`, legacy visual directions, contact sheets, download fields, or a single-target `target_render` summary. Assert the delivery projection contains exactly the four target IDs:

```ts
expect(initial.snapshot.workspace.delivery.targets.map((item) => item.target_id)).toEqual([
  "macos-powerpoint", "macos-wps", "windows-powerpoint", "windows-wps",
]);
expect(JSON.stringify(initial.snapshot)).not.toContain("space_projections");
```

- [x] **Step 2: Run tests and verify RED**

Run: `npm run test:widget -- --reporter=dot && npm run test:node`

Expected: Widget tests FAIL because production types/components still require v1.5 `space_projections`.

- [x] **Step 3: Define the schema 3 UI types**

Replace the legacy projection types with `WorkspaceProjection`, `WorkspaceSpaceProjection`, `WorkspacePrimaryAction`, `DeliveryStatusProjection`, `TargetStatusProjection`, and exact `GateStatus` unions. Keep `ProjectSnapshot` limited to authoritative schema 3 fields and make incompatible payloads fail TypeScript compilation instead of being guessed at runtime.

- [x] **Step 4: Update deterministic fixtures and MCP assertions**

Build fixtures from the same formal shape returned by Task 1. Preserve only data needed by Widget/review tests. Verify Node returns the Python projection unchanged in both `structuredContent` and `_meta.widgetData`.

- [x] **Step 5: Verify GREEN**

Run: `npm run test:widget -- --reporter=dot && npm run test:node`

Expected: all Widget and Node tests PASS.

### Task 3: 360/420/480px compact five-space Widget

**Files:**
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/components/CompactWorkspace.tsx`
- Modify: `widget/src/components/StableNavigation.tsx`
- Modify: `widget/src/styles.css`
- Create: `widget/src/CompactWorkspace.v16.test.tsx`

- [x] **Step 1: Write failing behavior tests for all five spaces**

For each space, assert the order `结论 → 风险/焦点 → 受影响成果 → 当前判断/下一步 → 主操作`, exactly one strongest action when actionable, and no false action while a review is unavailable. Delivery must render four binary quality gates, four separate target rows, one highest blocker, hash identity, and chat-send state without contact sheets, large images, machine logs, or downloads.

- [x] **Step 2: Verify RED**

Run: `npm run test:widget -- --run widget/src/CompactWorkspace.v16.test.tsx --reporter=dot`

Expected: FAIL because `CompactWorkspace` still consumes legacy projections and collapses desktop evidence into one PowerPoint row.

- [x] **Step 3: Implement the formal compact reading line**

Render `snapshot.workspace[activeSpace]` directly. Use one shared `CompactCognitionLine` and specialized compact evidence rows only where the formal projection requires them. Route primary action exclusively from `primary_action.kind`; do not infer review/Gate readiness in React.

- [x] **Step 4: Implement responsive and accessible compact CSS**

At 360/420/480px keep five icon navigation targets at least 40×40px, visible focus, wrapping project titles, no horizontal scrolling of the page, one continuous surface rather than nested cards, and reduced-motion support. Evidence may collapse, but conclusion and action remain visible.

- [x] **Step 5: Verify GREEN**

Run: `npm run test:widget -- --run widget/src/CompactWorkspace.v16.test.tsx widget/src/App.test.tsx widget/src/PhaseB.test.tsx widget/src/PhaseC.test.tsx widget/src/PhaseD.test.tsx --reporter=dot`

Expected: all compact Widget tests PASS.

### Task 4: Exact review-mark contract and conflict-safe drafts

**Files:**
- Modify: `src/ai_ppt_studio/application/review_service.py`
- Modify: `tests/test_v16_review_marks.py`
- Modify: `tests/test_v16_bridge.py`
- Modify: `mcp/server.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/ProfessionalReviewApp.tsx`
- Modify: `widget/src/ProfessionalReviewApp.test.tsx`

- [x] **Step 1: Write failing exact-quote and conflict tests**

Require every saved mark to use the formal fields `field_anchor`, `exact_text`, `prefix`, `suffix`, `comment`, and `source_version`. Add a test that selecting duplicated text saves enough prefix/suffix context to bind the intended occurrence. Add revision/source-version conflict tests that keep all drafts visible and resubmittable after the backend returns `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`.

- [x] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_v16_review_marks tests.test_v16_bridge -v`

Run: `npm run test:widget -- --run widget/src/ProfessionalReviewApp.test.tsx --reporter=dot && npm run test:node`

Expected: FAIL because MCP and React still submit the v1.5 `target_anchor/selected_text` shape and selected-text context is absent.

- [x] **Step 3: Make Python and MCP use one formal mark schema**

Return `project_name`, `title`, `revision`, current status, exact source identity, and formal marks from `ReviewService`. Update `save_review_marks` Zod input and bridge forwarding to formal field names; reject unknown legacy-only shapes in schema 3.0 rather than maintaining a second public truth contract.

- [x] **Step 4: Capture exact selection context in React**

Resolve the containing `[data-field-anchor]`, derive the exact selected text plus bounded prefix/suffix from the field text, and stage a formal `ReviewMark`. Saving sends a stable idempotency key/mark ID with `expectedRevision` and `sourceVersion`. On success merge by mark ID and advance the returned revision; on conflict keep drafts, composer text, and source-version warning.

- [x] **Step 5: Verify GREEN**

Run the focused Python, Node, and Widget commands from Step 2.

Expected: all focused tests PASS; saving marks still cannot call G0/G3/G4.

### Task 5: One professional-review application at 760/1000/1440px

**Files:**
- Modify: `widget/src/ProfessionalReviewApp.tsx`
- Modify: `widget/src/styles.css`
- Create: `widget/src/ProfessionalReviewResponsive.test.tsx`

- [x] **Step 1: Write failing review interaction tests**

Assert one 64px banner line, persistent content/visual switch, outline, mark count, and save action; outline starts closed; outline and marks drawers are mutually exclusive; background/close/Escape close drawers; focus enters an opened drawer and returns to the trigger; selecting an outline item closes the drawer and targets the stable anchor without changing document geometry. Assert forbidden labels and controls remain absent.

- [x] **Step 2: Verify RED**

Run: `npm run test:widget -- --run widget/src/ProfessionalReviewResponsive.test.tsx --reporter=dot`

Expected: at least focus-trap/return-focus and formal responsive-state assertions FAIL.

- [x] **Step 3: Refactor the existing review application around stable boundaries**

Keep one `ProfessionalReviewApp`, but extract local focused units for header, document, outline drawer, marks drawer, and field/selection mark composition when the file would otherwise remain over 900 lines. Both content and visual modes must consume the same `ReviewProjection`/save interface and preserve one continuous DOM document.

- [x] **Step 4: Complete 760/1000/1440 responsive behavior**

At 1440px allow the current wide contract columns; at 1000px and 760px use a single readable column. Use overlay drawers with no layout reflow, `overflow-wrap:anywhere`, `min-width:0`, visible focus, 40px pointer targets, `aria-modal`, labelled live save states, and `content-visibility:auto` plus intrinsic size on long page sections. Never add a permanent sidebar, horizontal contract scroller, drag-wider prompt, or a second narrow review UI.

- [x] **Step 5: Verify GREEN**

Run: `npm run test:widget -- --run widget/src/ProfessionalReviewApp.test.tsx widget/src/ProfessionalReviewApp.e2e.test.tsx widget/src/ProfessionalReviewResponsive.test.tsx --reporter=dot`

Expected: all professional-review component tests PASS.

### Task 6: Host-aware review surface routing and graceful capability degradation

**Files:**
- Modify: `widget/src/types.ts`
- Modify: `widget/src/lib/mcp-app-client.ts`
- Modify: `widget/src/App.tsx`
- Create: `widget/src/ReviewSurfaceRouter.test.tsx`
- Modify: `tests/mcp-server.test.mjs`

- [x] **Step 1: Write failing routing tests**

Model host context with `containerDimensions`, `availableDisplayModes`, and bridge capabilities. Assert a host width of at least 760 can render the same review resource in the supported host mode, while a width below 760 requests fullscreen before `render_ai_ppt_review`. If fullscreen/capability calls fail, the project remains unchanged and the Widget shows the approved explicit continuation notice; it must never render a compressed review view or a fake “返回聊天” button.

- [x] **Step 2: Verify RED**

Run: `npm run test:widget -- --run widget/src/ReviewSurfaceRouter.test.tsx --reporter=dot`

Expected: FAIL because `HostBridge` exposes neither host context/capabilities nor a width-aware review route.

- [x] **Step 3: Expose read-only host context through the bridge**

After `McpApp.connect()`, return normalized `containerWidth`, `availableDisplayModes`, `canSendMessage`, and `canUpdateModelContext` from `getHostContext()`/`getHostCapabilities()`. Keep capability values ephemeral; do not persist them in project state or localStorage.

- [x] **Step 4: Implement the router policy**

Use a pure `chooseReviewDisplay(host)` function. Width `<760`, absent persistent side region, or explicit inline-only degradation must request the same review tool/resource in fullscreen; widths `>=760` use the best host-supported mode. `render_ai_ppt_review` always receives the same project, review type, source service, and save contract.

- [x] **Step 5: Verify GREEN**

Run: `npm run test:widget -- --run widget/src/ReviewSurfaceRouter.test.tsx widget/src/App.test.tsx --reporter=dot && npm run test:node`

Expected: routing and MCP tests PASS.

### Task 7: 60/120-page performance, keyboard, 200% zoom, and deterministic visual evidence

**Files:**
- Create: `widget/src/ProfessionalReviewLongDocument.test.tsx`
- Modify: `scripts/create-widget-preview.mjs`
- Modify: `scripts/create-review-preview.mjs`
- Create: `scripts/run-v16-ui-acceptance.mjs`
- Modify: `package.json`

- [x] **Step 1: Write failing 60/120-page completeness tests**

Generate schema 3 content and visual projections with 60 and 120 slide sections. Assert every stable page anchor exists once, complete long Chinese/filenames/unbroken text remain present, outline count matches page count, and initial render completes within the locally measured 2-second product budget without truncation or pagination dependence.

- [x] **Step 2: Verify RED**

Run: `npm run test:widget -- --run widget/src/ProfessionalReviewLongDocument.test.tsx --reporter=dot`

Expected: FAIL on the new explicit performance/accessibility contract until progressive rendering CSS and stable long-document helpers are present.

- [x] **Step 3: Add the v1.6 Playwright acceptance runner**

Build deterministic previews from schema 3 data, then inspect Widget 360/420/480 and content/visual review 760/1000/1440. For every viewport assert no document/body horizontal overflow, exactly one primary action, one 64px review header line, default-closed outline, overlay geometry stability, mutually exclusive drawers, Escape/focus behavior, absence of forbidden controls, full content presence, and zero console errors.

Run the review views again at 200% browser zoom (`deviceScaleFactor`/CSS zoom plus viewport checks) and assert the switch, outline, marks, and save controls remain reachable. Record performance timings and write screenshots plus a JSON report under `output/playwright/v16-ui/`.

- [x] **Step 4: Verify GREEN in components and Chromium**

Run: `npm run build`

Run: `npm run accept:v16-ui`

Expected: 3 Widget screenshots + 6 normal review screenshots + 6 zoom/accessibility review screenshots and one passing JSON report; all viewports have no horizontal overflow or console errors.

### Task 8: Slice 06 regression, ledger evidence, and plan closure

**Files:**
- Modify: `acceptance/requirements-v1.6.json` or the existing generated ledger source used by `ai_ppt_studio.acceptance.ledger`
- Create: `docs/validation/2026-08-09-v16-slice-06-ui-acceptance.md`
- Modify: `docs/superpowers/plans/2026-08-09-v16-slice-06-three-surface-ui.md`
- Modify: `docs/superpowers/plans/2026-08-08-v16-slice-01-authoritative-kernel.md`

- [x] **Step 1: Run the complete automated suite**

Run: `python3 -m unittest discover -s tests`

Run: `npm run test:node`

Run: `npm run test:widget -- --reporter=dot`

Run: `npm run build`

Run: `npm run accept:v16-ui`

Expected: every command exits 0 with no warning/error output attributable to product code.

- [x] **Step 2: Validate the acceptance ledger and repository hygiene**

Run the existing deterministic ledger generator/check and assert it still contains exactly 104 stable requirements. Record Slice 06 automation as contract/UI evidence only; do not mark real-host capability, four-target desktop evidence, or true-project acceptance as passed.

Run: `git diff --check`

Expected: no whitespace errors.

- [x] **Step 3: Write the Slice 06 validation record**

Document exact commands, pass counts, screenshot/report paths, measured 60/120-page timings, supported viewports, capability degradation behavior, and remaining `待实机/待真实项目` evidence. Explicitly state that browser automation does not prove macOS/Windows PowerPoint/WPS compatibility.

- [x] **Step 4: Check links and referenced prototypes**

Verify all four baseline relative links and every referenced `产品代码/prototypes/` file exist. Confirm no source/runtime data was written to the parallel Web product or default PPT workspace during deterministic UI tests.

- [x] **Step 5: Mark Slice 06 plan items complete and continue directly to Slice 07**

Check every completed box only after the corresponding command has passed. Do not create an intermediate commit; continue to packaging hardening, build-residue cleanup, real-project execution, four-target evidence, and final unified submission as already authorized by the user.
