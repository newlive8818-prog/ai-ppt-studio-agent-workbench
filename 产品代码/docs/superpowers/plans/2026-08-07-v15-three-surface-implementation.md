# v1.5 Three-Surface Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已批准的 v1.5 聊天、轻量 Native Widget 与专业审阅页三表面合同落地为可运行、可保存、可恢复、可测试的本地 Codex 插件垂直切片。

**Architecture:** 保留现有 Python 领域运行时、Node MCP Server 和单文件 React MCP App。Python 新增专业审阅投影、ReviewMarkSet、内部 Gate 记录和聊天交付回执；Node 暴露同一工作台资源的轻量 Widget 与专业审阅入口；React 根据 `surface` 渲染轻量认知投影或内容/视觉专业审阅页，两个表面始终消费同一 project revision。

**Tech Stack:** Python 3.11 标准库与 unittest、Node.js ESM、MCP Apps、React 19、TypeScript、Vite、Vitest、Testing Library、Playwright CLI。

## Global Constraints

- 权威需求只来自父目录四份 v1.5 基线和已批准的聊天/Widget/专业审阅专项设计。
- 运行数据只写入受管项目目录；不写源码目录、原材料目录或并行 Web 产品空间。
- 聊天、Widget 和专业审阅页只投影同一 ProjectWorkspaceState、Artifact 和 revision。
- Widget 不展示完整内容蓝图、视觉合同、联系表、大图质检或交付下载区。
- 专业审阅页只负责连续阅读、精确标记和右上角显式保存；不提供返回聊天、顶部版本历史、样张画廊、Gate 确认或 PPTX 下载。
- G0/G3/G4 只能由 Codex 基于用户聊天中的明确表达确认；G1/G2 只能由内部审查角色记录。
- 保存 ReviewMarkSet 不等于确认 Gate，不直接修改合同或稳定经验。
- 所有写入携带 expectedRevision；冲突不静默覆盖，失败保留用户输入和上一有效版本。
- 正式路线固定为 strict-B；Image 2 不作为整页构图或语义母版。
- 不启用子智能体；在当前 `codex/mvp-skill-app-design` 分支原地内联执行并保护现有未提交基线变更。

---

### Task 1: ProjectWorkspaceState 与专业审阅持久化合同

**Files:**
- Create: `src/ai_ppt_studio/review_surface.py`
- Create: `tests/test_review_surface.py`
- Modify: `src/ai_ppt_studio/workbench_models.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Modify: `src/ai_ppt_studio/errors.py`
- Modify: `tests/test_workbench_store.py`

**Interfaces:**
- Consumes: `ArtifactStore.latest()`, `PathPolicy`, `atomic_write_json()`, `EventStore`, workbench project lock and project revision.
- Produces: `ReviewSurfaceProjector.build(review_type) -> dict`, `ReviewMarkStore.load(review_type, source_version) -> dict`, `WorkbenchStore.save_review_marks(...) -> DecisionResult`, and snapshot fields `active_surface`, `review_projection_state`, `chat_delivery_status`, `delivery_status`.

- [x] **Step 1: Write failing state-upgrade and full-projection tests**

  Add tests proving an existing schema 2.0 workbench file receives additive v1.5 fields without rewriting legacy gate state, and that content/visual projections include every slide title, visible copy item, speaker note, source reference and visual-contract field without truncation.

- [x] **Step 2: Run the focused tests and verify RED**

  Run: `python3 -m unittest tests.test_workbench_store tests.test_review_surface -v`

  Expected: failures name the missing v1.5 snapshot fields and missing `review_surface` module.

- [x] **Step 3: Implement immutable source identity and review projection**

  `ReviewSurfaceProjector` must derive `source_version` from the current artifact kind/version/SHA, create stable section and field anchors, preserve raw values, include saved marks for the exact source version, and reject unsupported review types.

- [x] **Step 4: Write failing ReviewMarkSet save tests**

  Cover page/field/selected-text marks, merge by `mark_id`, `saved -> pending-governance`, refresh recovery, empty comment rejection, stale source rejection and revision conflict with no partial append.

- [x] **Step 5: Implement revision-safe ReviewMarkSet persistence**

  Save under `reviews/mark-sets/<review-type>/<source-version>.json`, atomically replace the merged set, append one event, increment the shared workbench revision once, and expose the new projection in the returned snapshot.

- [x] **Step 6: Run focused tests and verify GREEN**

  Run: `python3 -m unittest tests.test_review_surface tests.test_workbench_store -v`

---

### Task 2: Gate 分工、目标证据与聊天交付回执

**Files:**
- Modify: `src/ai_ppt_studio/models.py`
- Modify: `src/ai_ppt_studio/artifact_store.py`
- Modify: `src/ai_ppt_studio/gate_evidence.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Create: `tests/test_v15_gate_and_chat_delivery.py`
- Modify: `tests/test_workbench_bcd_writes.py`

**Interfaces:**
- Consumes: `StateStore.pass_gate()`, immutable artifact references, current project revision and saved review projections.
- Produces: `CONTENT_ACCEPTANCE` and `TARGET_RENDER_EVIDENCE` artifacts; `record_internal_gate(...)`; `record_chat_delivery(...)`; user-only `confirm_gate(..., user_message_ref)`.

- [x] **Step 1: Write failing Gate authority tests**

  Verify `confirm_gate` rejects G1/G2 and missing `user_message_ref`; `record_internal_gate` rejects G0/G3/G4; G2 does not pass until independent aesthetic and PPT engineering records plus passed target-render evidence exist.

- [x] **Step 2: Write failing chat delivery tests**

  Verify a visual sample or PPTX receipt records message/artifact/version identity, updates the same revision, supports retry linkage, and a failed message path does not rebuild or replace the delivery artifact.

- [x] **Step 3: Run the focused tests and verify RED**

  Run: `python3 -m unittest tests.test_v15_gate_and_chat_delivery -v`

- [x] **Step 4: Implement Gate authority separation**

  Add stable internal-gate records under `reviews/internal-gate-records.jsonl`; G1 needs the independent aesthetic role, G2 needs both independent aesthetic and PPT engineering roles plus passed target-render evidence. User checkpoints require a non-empty Codex chat message reference.

- [x] **Step 5: Harden G0/G3/G4 evidence**

  G0 requires a passed ContentAcceptanceRecord; G3 requires the complete visual-contract/scene-graph projection identity; G4 requires editable delivery, passed target-render evidence and a successful PPTX ChatDeliveryReceipt. Legacy projects that already passed a Gate stay readable; newly passing a Gate must satisfy v1.5 evidence.

- [x] **Step 6: Implement ChatDeliveryReceipt persistence**

  Append receipts to `reviews/chat-delivery-receipts.jsonl`, store only message/artifact references and user outcome, update lightweight delivery status, and keep the underlying artifact immutable.

- [x] **Step 7: Run focused and existing Python tests**

  Run: `python3 -m unittest tests.test_v15_gate_and_chat_delivery tests.test_workbench_bcd_writes tests.test_state_store -v`

---

### Task 3: MCP 双资源与 v1.5 工具契约

**Files:**
- Modify: `src/ai_ppt_studio/workbench_bridge.py`
- Modify: `mcp/server.mjs`
- Modify: `mcp/widget-resource.mjs`
- Modify: `tests/test_workbench_bridge.py`
- Modify: `tests/mcp-server.test.mjs`

**Interfaces:**
- Consumes: Task 1/2 Python operations.
- Produces: `render_ai_ppt_review`, `save_review_marks`, `get_delivery_status_projection`, `record_chat_delivery`, `record_internal_gate`, and restricted `confirm_ai_ppt_gate`.

- [x] **Step 1: Write failing Python bridge contract tests**

  Assert stable JSON for `get-review-projection`, `save-review-marks`, `get-delivery-status-projection`, `record-chat-delivery`, `record-internal-gate`, including `REVIEW_SOURCE_STALE`, `REVISION_CONFLICT` and validation errors.

- [x] **Step 2: Write failing Node MCP tests**

  Assert two app resources, the five new v1.5 tools, app-only review-save visibility, user/internal Gate schemas, and matching `structuredContent`/`widgetData` revisions.

- [x] **Step 3: Run focused tests and verify RED**

  Run: `python3 -m unittest tests.test_workbench_bridge -v && node --test tests/mcp-server.test.mjs`

- [x] **Step 4: Implement bridge operations and stable errors**

  Map snake_case process requests to the new store methods, keep one JSON object on stdout, and add `REVIEW_SOURCE_STALE`, `REVIEW_MARK_SAVE_FAILED`, `CHAT_DELIVERY_FAILED` without leaking tracebacks.

- [x] **Step 5: Register workbench and professional-review resources**

  Both URIs return the same self-contained React build, but use distinct metadata and `surface` widgetData. The review tool returns exact project, review type, source version, projection, saved marks and snapshot revision.

- [x] **Step 6: Implement MCP tools and rerun focused tests**

  Run: `python3 -m unittest tests.test_workbench_bridge -v && node --test tests/mcp-server.test.mjs`

---

### Task 4: 收口为轻量 Native Widget

**Files:**
- Create: `widget/src/components/CompactWorkspace.tsx`
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/styles.css`
- Modify: `widget/src/App.test.tsx`
- Modify: `widget/src/PhaseB.test.tsx`
- Modify: `widget/src/PhaseC.test.tsx`
- Modify: `widget/src/PhaseD.test.tsx`

**Interfaces:**
- Consumes: compact snapshot space projections and `render_ai_ppt_review`.
- Produces: a 360–480px five-space status Widget with one primary action and no full blueprint/visual/delivery workspace.

- [x] **Step 1: Replace old expectations with failing v1.5 UI tests**

  Assert five space tabs remain; blueprint/visual use `打开内容审阅`/`打开视觉合同`; delivery displays phase, four binary gates, one blocker, target platform and chat-send status; forbidden contact sheet, full contract, download, `展开完整工作台`, G1/G2 user confirmation and G4 button text are absent.

- [x] **Step 2: Run Widget tests and verify RED**

  Run: `npm run test:widget -- --run widget/src/App.test.tsx widget/src/PhaseB.test.tsx widget/src/PhaseC.test.tsx widget/src/PhaseD.test.tsx`

- [x] **Step 3: Implement the compact information hierarchy**

  Preserve project/sync identity, conclusion → risk → outcome → one action order, fact/inference/decision state language, explicit host fallback and revision conflict recovery. Do not render legacy complete workspace components.

- [x] **Step 4: Implement professional-review opening**

  Call `render_ai_ppt_review`, keep the same revision, switch the MCP App to review surface, and request the widest available display mode without treating capability failure as data failure.

- [x] **Step 5: Run focused Widget tests and verify GREEN**

  Run: `npm run test:widget -- --run widget/src/App.test.tsx widget/src/PhaseB.test.tsx widget/src/PhaseC.test.tsx widget/src/PhaseD.test.tsx`

---

### Task 5: 内容/视觉共用专业审阅页

**Files:**
- Create: `widget/src/ProfessionalReviewApp.tsx`
- Create: `widget/src/ProfessionalReviewApp.test.tsx`
- Modify: `widget/src/main.tsx`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/styles.css`

**Interfaces:**
- Consumes: `ReviewWidgetData`, `save_review_marks`, and content/visual mode switches from `render_ai_ppt_review`.
- Produces: continuous review document, overlay outline, mutually exclusive mark drawer, field and selected-text marks, explicit batch save and conflict-safe drafts.

- [x] **Step 1: Write failing review-page behavior tests**

  Assert a single-line Header has brand, content/visual switch, outline, marks and `保存标记`; outline starts closed; content is continuous; no return chat/version history/sample gallery/Gate/PPTX controls exist; field and selected-text marks can be drafted; save sends sourceVersion and expectedRevision; save failure/conflict keeps drafts.

- [x] **Step 2: Run focused review tests and verify RED**

  Run: `npm run test:widget -- --run widget/src/ProfessionalReviewApp.test.tsx`

- [x] **Step 3: Implement semantic continuous document rendering**

  Render all projector sections and nested values without ellipsis or line clamping. Add stable anchors, accessible status text, long-word wrapping and visible source/version identity in the document body, not as a version-history control.

- [x] **Step 4: Implement outline and mark interactions**

  The left outline and right mark drawer are fixed overlays and mutually exclusive; Escape/backdrop closes; outline navigation closes after focusing the target. Header remains one line and approximately 64px at all supported widths.

- [x] **Step 5: Implement explicit save and recovery**

  Save only unsaved drafts, update to `saved/pending-governance`, preserve drafts on error/conflict, warn before unloading unsaved drafts, and never call Gate tools.

- [x] **Step 6: Run focused review tests and verify GREEN**

  Run: `npm run test:widget -- --run widget/src/ProfessionalReviewApp.test.tsx`

---

### Task 6: 构建、真实浏览器、多视口和项目收口

**Files:**
- Modify: `scripts/create-widget-preview.mjs`
- Create: `scripts/create-review-preview.mjs`
- Create: `docs/v1.5-three-surface-acceptance.md`
- Modify only if implementation status changes: `../00-唯一研发基线索引-v1.0.md`

**Interfaces:**
- Consumes: self-contained Vite build, managed smoke project, Playwright CLI and baseline relative links.
- Produces: reproducible Widget/review previews, 360/420/480 Widget screenshots, 760/1000/1440 content/visual review screenshots and a machine-readable acceptance summary.

- [x] **Step 1: Build and run all automated tests**

  Run: `npm test`, `python3 -m unittest discover -s tests -p 'test_*.py' -v`, `npm run probe:mcp`, and `npm run accept:bcd`.

- [x] **Step 2: Create deterministic previews from a temporary managed project**

  Seed mission, content acceptance, full blueprint, visual contract, scene graph, target render and delivery status in an isolated temporary runtime; do not modify `/Users/defei/Documents/AI-PPT-Workspace` unless explicitly using an existing read-only smoke project.

- [x] **Step 3: Run Playwright UI acceptance**

  Check 360/420/480px Widget and 760/1000/1440px content/visual review. Verify no horizontal overflow, one primary action, 64px single-line Header, default-closed outline, fixed document geometry when drawers open, mutual exclusion, focus return, full long content, save persistence and conflict/error recovery.

- [x] **Step 4: Capture screenshots and inspect them**

  Save under `output/playwright/`; inspect every image, not only DOM geometry. Record console errors, overflow measurements and screenshot paths in the acceptance document.

- [x] **Step 5: Validate repository boundaries and links**

  Run `git diff --check`; verify all four baseline relative links and referenced prototypes exist; confirm no file was written to the parallel Web product or source-material paths.

- [x] **Step 6: Fresh final verification**

  Re-run the full Python, Node, Widget, build, MCP probe and acceptance commands after all fixes. Only then update the index implementation status and report completion or exact remaining external capability gaps.
