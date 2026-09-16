# AI PPT Studio Full Product Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留 v1.5 三表面垂直切片和现有本地运行时的前提下，完整实现已批准 v1.1–v1.5 产品合同，形成可安装、可恢复、可审计、可通过真实宿主验收的 AI PPT Studio Agent 原生工作台。

**Architecture:** 继续采用 Python 领域运行时 + Node MCP Server + React MCP App + 版本化 Skill。新增独立的领域产物合同、引用完整性校验、中文角色注册表、内容/视觉/反馈/经验治理服务；Context Compiler 只编译角色隔离的最小充分上下文，AgentTask 只保存不可变任务与结果引用，Workbench/MCP/Widget 只投影同一项目 revision。正式生产固定 strict-B，Presentations 原生首版先于可选 Image 2 非语义资产，PowerPoint 目标渲染证据是 G2/G4 放行前置。

**Tech Stack:** Python 3.11 标准库与 unittest、Node.js ESM、MCP Apps、React 19、TypeScript、Vite、Vitest、Testing Library、Playwright、Codex Presentations、Microsoft PowerPoint for macOS。

## Global Constraints

- 权威需求只来自项目根目录四份 v1.5 基线和六份已批准专项设计。
- 当前分支为 `codex/mvp-skill-app-design`；原地续接现有未提交 v1.5 改动，不 reset、不覆盖、不新建 worktree。
- 运行数据只写入受管项目根或临时隔离目录；不写入源码目录、原材料目录或 `../../PPT  web app `。
- 用户不需要中途审批；只有基线规定的真实业务歧义、关键证据缺失、不可逆外部动作或无法收敛才进入 needs-user。
- 不主动提交、推送或创建 PR；所有代码、测试和交付物保持可检查状态。
- 每个生产行为必须执行 RED → 确认预期失败 → GREEN → 聚焦回归 → 全量回归；不为文档纯文本编写 change-detector 测试。
- 智能体之间只通过不可变、带版本和 SHA-256 的结构产物协作；生产角色不能自我放行，审查角色不直接改稿。
- 所有用户可见正式角色名称使用中文；稳定英文 `roleId` 只允许存在于内部代码和 Schema。
- 内容先于视觉；G0 未通过前不得形成正式视觉结论。
- G0/G3/G4 只能由 Codex 基于用户聊天明确表达确认；G1/G2 是内部二元硬质量门。
- 正式路线固定 `strict-B`；A/C 只允许显式隔离实验，不能污染正式 Context Pack、产物或审查。
- Image 2 只在 Presentations 原生首版冻结后生成无文字、数字、业务关系和真实证据冒充的非语义资产。
- Presentations 是唯一 PPTX 读取、创建、编辑和开发预检路线；PowerPoint 桌面版实机导出是 G2/G4 目标渲染真相源。
- 用户反馈必须先形成 `FeedbackGovernanceRecord`；项目执行链与经验进化链必须分开持久化。
- 三表面共享同一 ProjectWorkspaceState、Artifact、Gate 和 revision；Widget/HTML/聊天均不是第二真相源。

---

## Requirement Coverage Matrix

| 子系统 | 需求 ID | 实施任务 |
|---|---|---|
| 项目与三表面 | PRJ-001–PRJ-007 | Task 2、6、7、9 |
| 材料 | MAT-001–MAT-006 | Task 2、3、6、9 |
| 内容蓝图 | BPT-001–BPT-016 | Task 1、2、3、6、7、9 |
| 视觉设计 | VIS-001–VIS-021 | Task 1、2、4、6、7、9 |
| 制作与交付 | DEL-001–DEL-012 | Task 1、4、6、7、9 |
| Agent 原生交互 | AGT-001–AGT-007 | Task 2、6、7、8、9 |
| 反馈与经验 | MEM-001–MEM-011 | Task 1、2、5、6、7、8、9 |

全部 80 个需求 ID 已进入至少一个实现任务；Task 9 以逐项验收矩阵验证不是仅有测试覆盖、而是具备真实可观察行为和边界证据。

---

### Task 1: 正式领域产物与引用证据合同

**Requirements:** BPT-008–BPT-016、VIS-004–VIS-019、DEL-003–DEL-010、MEM-005、MEM-008–MEM-009。

**Files:**
- Create: `src/ai_ppt_studio/governance_contracts.py`
- Create: `src/ai_ppt_studio/artifact_references.py`
- Create: `tests/test_governance_contracts.py`
- Create: `tests/test_artifact_references.py`
- Modify: `src/ai_ppt_studio/models.py`
- Modify: `src/ai_ppt_studio/artifact_store.py`
- Modify: `src/ai_ppt_studio/errors.py`
- Modify: `tests/test_artifact_store.py`

**Interfaces:**
- Produces: expanded `ArtifactKind`; `validate_governance_artifact(kind, payload)`; `ArtifactReference.parse(value)`; `ArtifactStore.resolve(ref, expected_kind=None, expected_sha256=None)`; `ArtifactStore.verify_refs(payload, contracts)`.
- Consumes: immutable `ArtifactVersion`, project-relative paths, latest pointers and SHA-256 metadata.
- Invariant: a formal reference is valid only when path exists inside the same managed project, kind/version match the envelope, and the stored payload hash equals both envelope SHA and optional expected SHA.

- [ ] **Step 1: Write failing artifact-kind and validator tests**

  Add literal fixtures for all approved formal objects: PresalesScenarioPack, PresalesContentStrategy, ClaimEvidenceMap, DeckArgumentMap, SlideDraftSet, ContentReviewRecord, ContentRepairPlan, ContentAcceptanceRecord, ContentChangeSet, CreativeDeliberationRecord, DeckDesignSystem, SlideVisualContract, AnchorSlideSet, AestheticAcceptanceRecord, NativeVisualDesignBrief, ImageAssetPromptPack, AnchorSlideEngineeringBrief, VisualRepairInstruction, VisualChangeSet, NativeFirstBuild, ImageAssetPack, PresentationBuild, TargetRenderEvidence, FeedbackGovernanceRecord, PreferenceSignal, ProfessionalMechanismCandidate, AntiPatternCandidate and RoleSpecificExperienceSlice.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_governance_contracts tests.test_artifact_references -v`

  Expected: import/enum failures for the missing contract modules and artifact kinds.

- [ ] **Step 3: Implement focused contract validators**

  Each validator checks required fields, enum values, non-empty collections, forbidden score/vote fields, strict-B boundaries, no semantic Image 2 assets, binary gate aggregation, source identity and stable version fields. Keep validators in focused functions selected by artifact kind; `artifact_store.py` remains storage orchestration.

- [ ] **Step 4: Write failing reference-integrity tests**

  Prove nonexistent refs, wrong artifact kinds, stale versions, path escapes, tampered payloads and SHA mismatches are rejected. Prove a valid immutable ref resolves to the exact envelope without relying on `latest.json` after version creation.

- [ ] **Step 5: Implement reference resolver and ArtifactStore integration**

  Use project-relative `artifact://<kind>/vNNNN#sha256=<digest>` references for new objects while accepting legacy project-relative file refs as read-only migration input. Never treat free-form `review://role-name` strings as evidence.

- [ ] **Step 6: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_governance_contracts tests.test_artifact_references tests.test_artifact_store tests.test_v15_gate_and_chat_delivery -v`

---

### Task 2: 中文角色注册表、任务生命周期与分层 Context Compiler

**Requirements:** PRJ-003–PRJ-005、MAT-002–MAT-005、BPT-008–BPT-013、VIS-002–VIS-017、AGT-003–AGT-005、MEM-009、MEM-011。

**Files:**
- Create: `src/ai_ppt_studio/role_registry.py`
- Create: `src/ai_ppt_studio/scenario_packs.py`
- Create: `tests/test_role_registry.py`
- Modify: `src/ai_ppt_studio/agent_tasks.py`
- Modify: `src/ai_ppt_studio/context_compiler.py`
- Modify: `tests/test_agent_tasks.py`
- Create: `tests/test_context_compiler_governance.py`

**Interfaces:**
- Produces: `RoleContract`; `RoleRegistry.get(role_id)`; `ScenarioPackRegistry.resolve(scene, task_type)`; expanded action types from the approved `AgentTask.type` union; resumable statuses `queued|running|needs-user|partial|failed|cancelled|completed`; `ContextCompiler.compile_role_task(...)`.
- Context layers: stable governance → scene pack → project facts → role contract → task contract → tool contract → role-specific experience slice → optional repair instruction → output/write-back contract → explicit exclusions.

- [ ] **Step 1: Write failing role/action/status tests**

  Assert every approved content, visual, feedback, experience and target-render role has a Chinese display name, a stable internal roleId, a declared producer/reviewer authority and isolation group. Assert old user-direction actions are no longer normal production actions.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_role_registry tests.test_agent_tasks tests.test_context_compiler_governance -v`

- [ ] **Step 3: Implement registries and immutable task lifecycle**

  Keep task request/context immutable; write status checkpoints and final result as separate append-only records. Validate result artifact refs through Task 1 before marking completed. `partial` and `failed` retain `last_valid_result_refs` and retry policy.

- [ ] **Step 4: Write failing isolation and context-layer tests**

  Production content roles cannot see review records; independent reviewers cannot see producer self-evaluation or sibling reviews; only the independent editor may aggregate content reviews. Formal visual tasks receive `productionRoute=strict-B`; Presentations tasks exclude A/C and whole-slide Image 2 results; image-asset tasks require a frozen native-first ref. Reviewer slices contain anti-patterns while producer slices contain qualified mechanisms/preferences.

- [ ] **Step 5: Implement layered compilation**

  Compile only target-linked project facts and exact artifact versions. Save layer versions and exclusions in the Context Pack. Reject stale project revision, missing role contract, scenario mismatch, raw feedback injected into production, or stable capability mutation instructions.

- [ ] **Step 6: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_role_registry tests.test_agent_tasks tests.test_context_compiler_governance tests.test_workbench_decisions -v`

---

### Task 3: 内容多智能体生产、独立审查、返工与 G0 放行

**Requirements:** MAT-001–MAT-006、BPT-001–BPT-016、AGT-003–AGT-005。

**Files:**
- Create: `src/ai_ppt_studio/content_governance.py`
- Create: `tests/test_content_governance.py`
- Modify: `src/ai_ppt_studio/gate_evidence.py`
- Modify: `src/ai_ppt_studio/space_projection.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Modify: `tests/test_space_projection.py`
- Modify: `tests/test_v15_gate_and_chat_delivery.py`

**Interfaces:**
- Produces: `ContentGovernanceService.plan_next(project_revision)`; `register_role_result(task_id, artifact_ref)`; `aggregate_reviews(target_ref, review_refs)`; `build_repair_plan(...)`; `mark_user_reviewable(acceptance_ref)`; risk routes `editorial-local|content-local|structural|high-impact`.
- State machine: strategy-building → evidence-mapping → narrative-structuring → slide-drafting → multi-agent-review → repairing/re-reviewing → internally-passed → user-reviewable → G0.

- [ ] **Step 1: Write failing happy-path orchestration test**

  Drive one deterministic project through strategy, evidence, argument map, complete slide draft, five isolated review records and independent-editor acceptance. Assert each next task consumes only Task 2-approved refs and the first user-reviewable projection contains a passed ContentAcceptanceRecord.

- [ ] **Step 2: Write failing hard-gate/repair tests**

  One applicable must-follow or minimum-content-quality failure must prevent acceptance, create a targeted ContentRepairPlan with preserveRefs, send the task to the owning producer, re-run the original reviewer and deck-coherence review, and keep the previous valid blueprint.

- [ ] **Step 3: Run RED**

  Run: `python3 -m unittest tests.test_content_governance -v`

- [ ] **Step 4: Implement content governance service**

  Persist orchestration state under `state/content-governance.json`; derive state only from verified artifact/task records; never synthesize missing historical reviews for migrated projects. Build the user ContentBlueprint only from internally passed component versions.

- [ ] **Step 5: Write failing change-risk and G0 tests**

  Assert a ContentChangeSet cannot be created without a governed feedback ref; editorial/content/structural/high-impact changes route different roles; internal failed versions cannot pass G0; a passed acceptance with fake role refs or tampered refs is rejected.

- [ ] **Step 6: Implement projections and gate evidence**

  Widget projects phase, role display names, binary status, repair summary and one user exception. Professional review exposes complete strategy/evidence/argument/full-slide content without visual conclusions. G0 evidence verifies actual five review artifacts, role isolation and content acceptance hashes.

- [ ] **Step 7: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_content_governance tests.test_space_projection tests.test_review_surface tests.test_v15_gate_and_chat_delivery -v`

---

### Task 4: 视觉多智能体、strict-B、四重硬门与自动返工

**Requirements:** VIS-001–VIS-021、DEL-001–DEL-010、AGT-003–AGT-005。

**Files:**
- Create: `src/ai_ppt_studio/visual_governance.py`
- Create: `tests/test_visual_governance.py`
- Create: `tests/test_strict_b_production.py`
- Modify: `src/ai_ppt_studio/gate_evidence.py`
- Modify: `src/ai_ppt_studio/space_projection.py`
- Modify: `src/ai_ppt_studio/workbench_store.py`

**Interfaces:**
- Produces: `VisualGovernanceService`; dynamic page-specialist routing; isolated divergence/convergence role runs; `compile_native_visual_design_brief`; `authorize_image_asset_pack`; `aggregate_four_gates`; `create_visual_repair_instruction`; G1/G2 internal records.
- Strict route: complete contract → Presentations native-first → full-slide preflight/freeze → optional nonsemantic Image 2 assets → controlled integration → PowerPoint target export → semantic/aesthetic/engineering/target-render gates.

- [ ] **Step 1: Write failing visual-team and G1 tests**

  Prove fixed producer/reviewer roles are isolated, dynamic experts run only for matching page families, convergence yields one VisualBrief/DeckDesignSystem/all SlideVisualContracts, and G1 never creates a user direction-choice task.

- [ ] **Step 2: Write failing strict-B tests**

  Prove formal context excludes A/C; native-first exists and is frozen before Image 2; ImageAssetPromptPack without native-first evidence or containing text/numbers/relationships is rejected; asset failure leaves native-first usable; removing assets preserves slide semantics.

- [ ] **Step 3: Run RED**

  Run: `python3 -m unittest tests.test_visual_governance tests.test_strict_b_production -v`

- [ ] **Step 4: Implement visual governance and strict-B state**

  Persist role runs, candidate refs, externalized decision summary, evidence, iteration and convergence status without hidden reasoning. Persist A/C experiments under isolated experiment namespaces not readable by formal resolvers.

- [ ] **Step 5: Write failing four-gate, target-render and repair tests**

  Any applicable semantic/aesthetic/engineering/target-render failure rejects the build, preserves lastValidBuildRef, targets only affected slides/objects, and requires the original reviewer plus a fresh PowerPoint export. Development renders marked preflight-only cannot satisfy TargetRenderEvidence; unverified Windows/WPS claims fail.

- [ ] **Step 6: Implement G2/G4 evidence aggregation**

  Verify target application/platform/version/font inventory/substitution plan/PPTX before-after hash/export refs/per-slide four-gate records. G2 requires 2–3 anchor slides; G4 requires the entire current build. No scores, averages, conditional pass or compatibility inference.

- [ ] **Step 7: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_visual_governance tests.test_strict_b_production tests.test_v15_gate_and_chat_delivery tests.test_artifact_store -v`

---

### Task 5: F0–F3 反馈治理、Experience Intake 与三速进化

**Requirements:** BPT-015–BPT-016、VIS-018–VIS-021、MEM-001–MEM-011。

**Files:**
- Create: `src/ai_ppt_studio/feedback_governance.py`
- Create: `src/ai_ppt_studio/experience_intake.py`
- Create: `tests/test_feedback_governance.py`
- Create: `tests/test_experience_intake.py`
- Modify: `src/ai_ppt_studio/experience_models.py`
- Modify: `src/ai_ppt_studio/experience_store.py`
- Modify: `tests/test_experience_store.py`

**Interfaces:**
- Produces: `FeedbackGovernanceService.capture/review/decide/apply/validate/close`; `ExperienceIntake.register`; extraction of PreferenceSignal, ProfessionalMechanismCandidate and AntiPatternCandidate; `ExperienceStore.compile_role_slice` and stable capability release candidates.
- Separate states: project execution status versus experience evolution status.

- [ ] **Step 1: Write failing F0–F3 tests**

  F0/F1 become executable only after diagnosis, scope, preserve refs and professional route exist. F2/F3 require the fixed three-choice user decision before expansion. User insistence becomes project-only. Raw feedback cannot create ContentChangeSet/VisualChangeSet or stable rules.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_feedback_governance tests.test_experience_intake -v`

- [ ] **Step 3: Implement feedback state machine**

  Persist immutable versions from captured through closed, including raw input, diagnosis, counterexamples, AI recommendation, decision, change-set refs, professional validation, user outcome and learning eligibility. Restore creates a new version and keeps the original.

- [ ] **Step 4: Write failing intake/extraction/slice tests**

  Register governed feedback, preferred/reference exemplars, accepted/failed deliverables and internal failures. Extract the three approved result kinds without copying a whole exemplar. Compile different producer/reviewer slices with source/version/scope/match/exclusion evidence; reject scene/role/task mismatch.

- [ ] **Step 5: Implement qualified preference and three-speed evolution**

  Preferences rank only already qualified candidates. Project learning applies immediately and reversibly; personal experience still requires real matched applications and accepted professional outcomes; stable prompt/role/scenario changes only create release candidates and never mutate runtime files.

- [ ] **Step 6: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_feedback_governance tests.test_experience_intake tests.test_experience_store tests.test_experience_cli -v`

---

### Task 6: Workbench、MCP 与完整 P0 工具闭环

**Requirements:** PRJ-001–PRJ-007、MAT-001–MAT-006、BPT-005–BPT-016、VIS-008–VIS-021、DEL-011–DEL-012、AGT-001–AGT-007、MEM-004–MEM-011。

**Files:**
- Modify: `src/ai_ppt_studio/workbench_store.py`
- Modify: `src/ai_ppt_studio/workbench_bridge.py`
- Modify: `mcp/server.mjs`
- Modify: `tests/test_workbench_bcd_writes.py`
- Modify: `tests/test_workbench_bridge.py`
- Modify: `tests/mcp-server.test.mjs`
- Create: `tests/test_full_product_mcp_contract.py`

**Interfaces:**
- Adds governed read projections for content, visual, delivery, feedback and experience intake.
- Adds write operations for governed feedback, feedback decisions, experience sources/evaluations, target render evidence, task checkpoint/cancel/retry and artifact version restore.
- Every response includes one revision, event cursor, allowed next actions and stable conflict/user-attention objects.

- [ ] **Step 1: Write failing bridge/MCP schema tests**

  Assert all baseline P0 read/write contracts exist, tool inputs map to exact Python operations, app-only save tools remain restricted, and structuredContent/widgetData share revision and project identity. Assert tool descriptions use current G0/G3/G4 and strict-B language.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_full_product_mcp_contract tests.test_workbench_bridge -v && node --test tests/mcp-server.test.mjs`

- [ ] **Step 3: Implement runtime methods and stable errors**

  Reuse Task 3–5 services, project lock, expectedRevision, atomic writes and event append. Add SCENARIO_PACK_MISMATCH, CONTENT_REVIEW_INCOMPLETE, CONTENT_QUALITY_GATE_FAILED, FEEDBACK_GOVERNANCE_REQUIRED, FEEDBACK_USER_DECISION_REQUIRED, EXPERIENCE_SCOPE_MISMATCH, STABLE_CAPABILITY_RELEASE_BLOCKED, TARGET_RENDER_EVIDENCE_MISSING and compatibility errors.

- [ ] **Step 4: Register MCP tools and bounded projections**

  Widget tools return summaries, not full documents or large images. Review resource remains complete and source-version fixed. Task and chat receipts reference immutable artifacts rather than embedding chat history as state.

- [ ] **Step 5: Run GREEN and regression**

  Run: `python3 -m unittest tests.test_full_product_mcp_contract tests.test_workbench_bridge tests.test_workbench_bcd_writes -v && node --test tests/mcp-server.test.mjs`

---

### Task 7: 三表面 UI 完整投影、专业文案与长文性能

**Requirements:** PRJ-003–PRJ-007、BPT-005–BPT-016、VIS-008–VIS-021、DEL-011–DEL-012、AGT-001–AGT-007、MEM-004–MEM-010。

**Files:**
- Modify: `src/ai_ppt_studio/review_surface.py`
- Modify: `src/ai_ppt_studio/space_projection.py`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/components/CompactWorkspace.tsx`
- Modify: `widget/src/ProfessionalReviewApp.tsx`
- Modify: `widget/src/styles.css`
- Modify: `widget/src/test-fixtures.ts`
- Modify: `widget/src/ProfessionalReviewApp.test.tsx`
- Create: `widget/src/FullProductProjection.test.tsx`
- Modify: `scripts/run-v15-playwright-acceptance.mjs`

**Interfaces:**
- Consumes: bounded Widget projection and complete ReviewProjection from Task 6.
- Produces: Chinese professional field labels, content production progress, feedback governance receipts, binary gates, target platform evidence identity, role names, scalable continuous review document and lightweight delivery projection.

- [ ] **Step 1: Write failing translation/content tests**

  Assert no internal keys such as `narrative thesis`, `fact status`, roleId, snake_case or English gate jargon leak into the UI. Assert all formal sections show Chinese names, binary status, version/evidence identity and one primary action.

- [ ] **Step 2: Write failing 60/120-page rendering tests**

  Render large deterministic content and visual contracts, preserve every source field, stable anchors and saved marks, while the initial DOM uses progressive chunks/virtualized section activation without losing search/navigation targets.

- [ ] **Step 3: Run RED**

  Run: `npm run test:widget -- --run widget/src/ProfessionalReviewApp.test.tsx widget/src/FullProductProjection.test.tsx`

- [ ] **Step 4: Implement professional label registry and progressive rendering**

  Map known fields explicitly; unknown fields use safe Chinese title conversion and never expose raw snake_case as the primary label. Keep full data in the review payload, render the current/nearby chunks, and materialize a target section before focus/navigation. Preserve 64px header, default-closed overlay outline, drawer mutual exclusion and no horizontal overflow.

- [ ] **Step 5: Implement governance/progress projections**

  Compact Widget shows only conclusion, maximum risk, result status and one action. Review document shows full content/contract, review identity and governed feedback. Delivery shows four gates, platform evidence and chat-send status only.

- [ ] **Step 6: Run GREEN and Playwright regression**

  Run: `npm run test:widget && node scripts/run-v15-playwright-acceptance.mjs`

---

### Task 8: Skill 工作流升级与可验证行为

**Requirements:** BPT-007–BPT-016、VIS-001–VIS-021、DEL-001–DEL-012、AGT-002–AGT-007、MEM-001–MEM-011。

**Files:**
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `skills/ai-ppt-studio/references/visual-workflow.md`
- Modify: `skills/ai-ppt-studio/references/presentations-handoff.md`
- Modify: `skills/ai-ppt-studio/references/review-and-feedback.md`
- Modify: `skills/ai-ppt-studio/references/experience-evolution.md`
- Modify: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `skills/ai-ppt-studio/agents/openai.yaml`
- Modify: `tests/test_skill_workflow.py`
- Create: `tests/test_skill_pressure_scenarios.py`

**Interfaces:**
- Skill instructs Codex to use formal role tasks and artifact refs, not simulate unrecorded multi-agent discussion.
- User checkpoints become only G0/G3/G4; G1/G2 are internal.
- Formal visual route becomes complete contract → Presentations native-first → optional nonsemantic Image 2 → target PowerPoint evidence.
- Feedback/experience references enforce F0–F3 and project/personal/stable separation.

- [ ] **Step 1: Build RED behavior fixtures before editing Skill**

  Use existing Skill tests plus executable workflow-policy fixtures that feed representative task/gate states into the runtime helper. Prove the current Skill contract still asks users to choose G1 direction/approve G2 samples, treats Image 2 as the concept master, omits formal role tasks and bypasses FeedbackGovernanceRecord.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_skill_workflow tests.test_skill_pressure_scenarios -v`

- [ ] **Step 3: Rewrite the Skill as a concise router**

  Keep SKILL.md under 220 lines; move detailed role/state/object contracts to focused references. Remove old G1/G2 user selection and four-review-page language. Require verified write-back after every consequential role/tool result and explicit last-valid-version preservation.

- [ ] **Step 4: Update focused references and UI metadata**

  Each reference owns one responsibility and includes current tool/action names, formal output types and stop conditions. Regenerate/validate `agents/openai.yaml` against the revised Skill.

- [ ] **Step 5: Run GREEN and skill validation**

  Run: `python3 -m unittest tests.test_skill_workflow tests.test_skill_pressure_scenarios -v`

  Run: `python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ai-ppt-studio`

---

### Task 9: 插件打包安装、真实宿主与端到端验收

**Requirements:** PRJ-001–PRJ-007、MAT-001–MAT-006、BPT-001–BPT-016、VIS-001–VIS-021、DEL-001–DEL-012、AGT-001–AGT-007、MEM-001–MEM-011。

**Files:**
- Create: `tests/test_full_product_acceptance.py`
- Create: `scripts/seed-full-product-smoke-project.py`
- Create: `scripts/run-full-product-acceptance.mjs`
- Modify: `scripts/run-bcd-acceptance.mjs`
- Modify: `scripts/probe-mcp.mjs`
- Create: `docs/full-product-requirement-coverage.md`
- Create: `docs/full-product-acceptance.md`
- Modify: `00-唯一研发基线索引-v1.0.md` only after fresh evidence changes implementation status.

**Interfaces:**
- Produces: deterministic isolated smoke project; machine-readable 80-requirement evidence matrix; source plugin validation; clean package/archive; fresh extraction; non-destructive workspace initialization; installed plugin/new-task tool discovery; native Widget/review/chat/PPTX/PowerPoint evidence.

- [ ] **Step 1: Write failing full-product acceptance test**

  Assert one project can progress from mission/material findings through governed content, G0, governed visual strict-B, G1/G2, G3, full build/PowerPoint target evidence/chat receipt and G4; include F0/F2 feedback and separate experience intake/slice evidence. Assert every requirement ID has a code/test/manual-evidence status.

- [ ] **Step 2: Run RED**

  Run: `python3 -m unittest tests.test_full_product_acceptance -v`

- [ ] **Step 3: Implement deterministic smoke and acceptance scripts**

  Use a temporary managed workspace. The smoke records real immutable artifacts and role/task boundaries; it does not pretend model-generated content quality or PowerPoint target evidence exists unless actual files/environment evidence are supplied.

- [ ] **Step 4: Run all automated verification fresh**

  Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

  Run: `npm test`

  Run: `npm run probe:mcp`

  Run: `npm run accept:bcd`

  Run: `node scripts/run-full-product-acceptance.mjs`

  Run: `git diff --check`

- [ ] **Step 5: Run browser and large-document acceptance**

  Verify 360/420/480px Widget and 760/1000/1440px content/visual review; test 60/120-page navigation, full-field integrity, mark save/reload/conflict, no forbidden controls, one primary action, console errors and overflow. Inspect every captured screenshot.

- [ ] **Step 6: Run real PowerPoint for macOS target export**

  Use Codex Presentations for the smoke PPTX, then export through the installed Microsoft PowerPoint desktop app. Record OS/app versions, font inventory/substitution plan, source hash, PDF/PNG refs and per-slide four-gate conclusions. If UI automation or app capability is unavailable, retain this exact item as external `待真实环境验证`; do not downgrade it to a simulated pass.

- [ ] **Step 7: Build and validate the plugin package**

  Include Skill, MCP, Widget dist, Python runtime, runtime dependencies and non-destructive workspace profile. Validate source and extracted copy, `unzip -t`, archive content allowlist, SHA-256, package-local symlinks and fresh workspace initialization without secrets or caches.

- [ ] **Step 8: Install and reload in a new Codex task**

  Install the built plugin through the supported local marketplace/plugin path, create or reload a new Codex task as required by current host behavior, verify the upgraded Skill text is discovered, compare installed MCP tool count/names with repository source, open the Native Widget and professional review resource, and record chat file-delivery behavior.

- [ ] **Step 9: Self-audit all 80 requirements and update status**

  For each ID, cite exact code, automated test and real/manual evidence. Classify only as `已实现并验证`、`已实现待真实环境验证` or `未实现`. Do not call the product complete while any P0 item remains `未实现`; do not call host/PowerPoint/chat capability verified without current evidence.

- [ ] **Step 10: Validate repository boundaries and baseline links**

  Verify all four baseline relative links, six approved design links and referenced prototypes exist; confirm no writes occurred in the parallel Web product or source-material roots; confirm no `待验证` conclusion was rewritten as confirmed fact.

---

## Plan Self-Review

- Spec coverage: all 80 PRJ/MAT/BPT/VIS/DEL/AGT/MEM IDs appear in the coverage matrix and final acceptance.
- Type consistency: formal objects use the exact CamelCase names from the v1.5 baselines; Python artifact enum values remain kebab-case; user-visible role names remain Chinese.
- Gate consistency: G0/G3/G4 user-only, G1/G2 internal-only; ReviewMarkSet save never passes a Gate.
- Route consistency: formal production is strict-B, Presentations native-first precedes Image 2, PowerPoint target evidence precedes G2/G4.
- State consistency: project execution and experience evolution are separate; all UI surfaces share one revision.
- Placeholder scan: no TBD/TODO/implement-later placeholder is used as an implementation instruction. Items that genuinely depend on current host/PowerPoint capability are explicit real-environment acceptance steps and must retain `待真实环境验证` if unavailable.
- Scope: no independent Web app, cloud account, multi-user, billing, remote queue, parallel PPTX engine or stable Prompt auto-mutation is introduced.
