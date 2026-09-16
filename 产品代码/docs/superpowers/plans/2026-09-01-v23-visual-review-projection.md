# v2.3 Visual Review Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved v2.3 Visual Brief, design-system, and slide visual semantics to the existing closed visual-review document without exposing `VisualCompilationPlan` or changing the accepted review layout and interactions.

**Architecture:** Python Runtime projects only user-reviewable visual fields from current immutable artifacts. Exact-field TypeScript validation rejects undeclared data; a pure ViewModel adapter remains the React boundary. The existing `VisualContractView` gains one Visual Brief section and ordered field rows inside the same continuous document, while the one-top-bar, two-view, inline anchor batch, overlay drawers, and contextual marking behavior remain unchanged.

**Tech Stack:** Python 3.11+ `unittest`, TypeScript 5, React 19, Vitest, Testing Library, exact-field projection validation, Vite build.

---

## Execution isolation

- Required integrated predecessor: R2 approved and fast-forwarded into `codex/v23-visual-quality-20260831`.
- Execution branch: `codex/v23-visual-review-projection-20260901`.
- Execution Worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-visual-review-projection-20260901`.
- Create only after the user selects R3 and the integration Worktree is clean.
- Do not modify the accepted content-review page, four baselines, Presentations builder, Runtime sample projects, PPTX files, plugin installation, or publication.

## Current execution and integration status snapshot (2026-09-06)

This implementation plan has been executed and closed in the isolated R3 Worktree. The final source and evidence identities are:

```text
branch: codex/v23-visual-review-projection-20260901
worktree: /Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-visual-review-projection-20260901
implementation: 69e87c140fb53898b5e57dbc97b9f53f055cf06c
HEAD: 97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9
title: docs: close v23 r3 change
status: clean
```

The earlier token-map repair remains recorded in the [R3 token-map historical sub-ledger](../../validation/2026-09-05-v23-r3-token-map-review-ledger.md). The complete final scope, text-anchor alignment, lineage hardening, full verification, and Review B2/C2 evidence are recorded in the [R3 Change exit report](../../validation/2026-09-05-v23-r3-change-exit-report.md). Review B2 and Review C2 both returned `P0=0 / P1=0 / P2=0 / P3=0` for the same frozen source snapshot.

After explicit user approval, the integration Worktree merged source HEAD `97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9` with a normal history-preserving `--no-ff` merge:

```text
integration branch: codex/v23-visual-quality-20260831
pre-merge target: c8ed5e97c99c9e6031300ef5a118ca750ab284f3
merge commit: 21cfe9ed719a313bead71b23b4aea5e6f44f4de2
parents: c8ed5e97c99c9e6031300ef5a118ca750ab284f3 97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9
merge base: 25d04e3438a9268fecd60564f8f0c2f2cd3eb9b5
pre-merge divergence: target-only 2 / source-only 14
```

Fresh verification on the merge candidate passed Python `566/566`, Node `137/137`, Widget `755/755` across 16 files including text-anchor integration `17/17`, MCP projection smoke `1/1`, typecheck, build, and `git diff --check`. The `src`, `mcp`, `tests`, and `widget` tree hashes exactly match source HEAD `97d5b99`.

This snapshot updates E1/E2, Review, and local integration facts only. The v2.3 acceptance ledger remains unchanged and unproven. It does not claim E3 real-sample, E4 target-PowerPoint, E5 user-visual acceptance, G3/G4, release, or R4/R5 execution.

## File map

- Modify `src/ai_ppt_studio/application/visual_review_service.py`: resolve/project current Visual Brief and approved v2.3 fields; support marks on the brief.
- Modify `tests/test_v22_visual_review_service.py`: exact backend projection, mark targeting, lineage, and no-plan-surface assertions.
- Modify `widget/src/types/visual-review.ts`: add only the new projection identities.
- Modify `widget/src/review-surface-validation.ts`: close Visual Brief/design-system/slide field sets.
- Modify `widget/src/visual-review/visual-contract-field-contract.ts`: stable field order and labels input.
- Modify `widget/src/visual-review/visual-review-page-view-model.ts`: closed Visual Brief and new field projection.
- Modify `widget/src/visual-review/VisualContractView.tsx`: render Visual Brief and new rows in source order; preserve structure/interactions.
- Modify `widget/src/visual-review/visual-contract-mark-validation.ts`: accept brief section marks through the same mark set.
- Modify `widget/src/visual-review/visual-review-page-view-model.test.tsx`: exact adapter coverage and backend-extra rejection.
- Modify `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`: rendered labels, outline, mark actions, and layout invariants.
- Modify `widget/src/review-surface-validation.test.tsx` if present; otherwise extend `ReviewSurfaceRouter.test.tsx`: exact-envelope rejection/acceptance.
- Modify `widget/src/__fixtures__/review-projection.visual.json`: one canonical v2.3 projection fixture.
- Verify `widget/src/styles/visual-review.css`: no layout change expected; modify only if new section spacing needs an existing document token.

### Task 1: Project the current Visual Brief and v2.3 semantics from Runtime

**Files:**
- Modify: `src/ai_ppt_studio/application/visual_review_service.py`
- Modify: `tests/test_v22_visual_review_service.py`

- [ ] **Step 1: Add RED exact-field projection tests**

For a current v2.3 visual review, assert the top-level projection adds exactly:

```python
"visual_brief_ref"
"visual_brief"
```

Assert it does not add `visual_compilation_plan_ref`, `visual_compilation_plan`, `gate_status`, raw role runs, raw lineage, or arbitrary backend fields.

Require `visual_brief` to contain exactly:

```python
REVIEWABLE_VISUAL_BRIEF_FIELDS = (
    "design_proposition",
    "audience_fit",
    "decision_task",
    "design_stance",
    "emotional_boundary",
    "brand_boundary",
    "density_strategy",
    "narrative_rhythm",
    "imagery_strategy",
    "diagram_strategy",
    "powerpoint_constraints",
    "forbidden_patterns",
    "five_second_test_contract",
    "design_philosophy_refs",
)
```

The optional philosophy field must project as `[]` when absent; missing optional references must not block the page.

- [ ] **Step 2: Add RED design-system and slide-field tests**

Require the design-system projection to include:

```python
"cross_slide_rhythm_rules"
"emphasis_budget"
"image_language"
"diagram_language"
"five_second_test_rules"
```

Keep existing `density_rhythm`. Require every slide projection to add the exact 12 v2.3 fields:

```python
"reader_judgment"
"primary_relationship"
"secondary_relationship"
"visual_mechanism"
"focal_point"
"asset_roles"
"forbidden_patterns"
"previous_rhythm_relation"
"next_rhythm_relation"
"text_density_budget"
"powerpoint_implementation_requirements"
"acceptance_evidence_plan"
```

Assert no frozen governance fields, raw `powerpoint_implementation_requirements` aliases, or plan-only fields are introduced.

- [ ] **Step 3: Add RED brief mark-target tests**

Save a `contract-field` mark with:

```python
{
    "slide_id": "",
    "deck_section_id": "visual-brief",
    "target_key": "decision_task",
}
```

Require success when `target_key` is one of the rendered Visual Brief rows. `design_proposition` remains the section heading and is not a duplicate row or independent field-mark target. Require rejection for `design_proposition`, `visual-compilation-plan`, `compiler_version`, `lineage`, or any undeclared brief key.

- [ ] **Step 4: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v22_visual_review_service
```

Expected: current projection has no Visual Brief and current mark targeting recognizes only design-system/slide sections.

- [ ] **Step 5: Implement the closed backend projection**

Add `REVIEWABLE_VISUAL_BRIEF_FIELDS` and extend the existing design/slide field tuples with the exact fields above. Define `MARKABLE_VISUAL_BRIEF_FIELDS` as the same tuple without `design_proposition`, because that field is rendered only as the section heading. Resolve the current brief from the final visual contract's `visual_brief_ref`, require it to equal `state.artifact_heads["visual/brief"]`, and validate it against the current policy.

Project:

```python
"visual_brief_ref": brief_ref,
"visual_brief": {
    key: copy.deepcopy(brief.get(key, [] if key == "design_philosophy_refs" else None))
    for key in REVIEWABLE_VISUAL_BRIEF_FIELDS
},
```

Keep `visual_compilation_plan_ref` internal for lineage only. Do not expose the plan payload.

- [ ] **Step 6: Extend mark target resolution**

In `_contract_mark_target_value()`, accept `deck_section_id == "visual-brief"` and only keys in `MARKABLE_VISUAL_BRIEF_FIELDS`; preserve existing `deck-design-system` and slide behavior. Marks still bind the final `visual_contract_ref`, source version, and revision.

- [ ] **Step 7: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v22_visual_review_service \
    tests.test_v22_visual_review_contracts
```

Expected: backend projection and mark tests pass.

### Task 2: Close the TypeScript projection and ViewModel

**Files:**
- Modify: `widget/src/types/visual-review.ts`
- Modify: `widget/src/review-surface-validation.ts`
- Modify: `widget/src/visual-review/visual-contract-field-contract.ts`
- Modify: `widget/src/visual-review/visual-review-page-view-model.ts`
- Modify: `widget/src/visual-review/visual-review-page-view-model.test.tsx`
- Modify: `widget/src/__fixtures__/review-projection.visual.json`
- Modify: `widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: Add RED adapter tests**

Create a projection containing all approved v2.3 fields plus deliberate backend extras:

```typescript
future_backend_governance: { must_not_render: true },
visual_compilation_plan: { must_not_render: true },
```

Assert the ViewModel includes the approved fields, normalizes absent `design_philosophy_refs` to `[]`, and excludes both extras, `review_session`, `gate_status`, and all compilation-plan data.

- [ ] **Step 2: Add RED exact-envelope tests**

Require validation success for the new exact projection. Then add one unexpected Visual Brief, design-system, or slide key at a time and require `validateReviewConnectionEnvelope()` to return `null`. Remove each required field and require `null` except optional brief philosophy refs, which Runtime must materialize as `[]` before the envelope reaches Widget.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
npx vitest run --configLoader runner \
  widget/src/visual-review/visual-review-page-view-model.test.tsx \
  widget/src/ReviewSurfaceRouter.test.tsx
```

Expected: type/validation tests fail because current field arrays do not allow the new projection.

- [ ] **Step 4: Define the exact TypeScript contracts**

Add `visual_brief_ref` and `visual_brief` to `VisualReviewProjection`. Define:

```typescript
export interface VisualReviewPageVisualBrief {
  design_proposition: unknown;
  audience_fit: unknown;
  decision_task: unknown;
  design_stance: unknown;
  emotional_boundary: unknown;
  brand_boundary: unknown;
  density_strategy: unknown;
  narrative_rhythm: unknown;
  imagery_strategy: unknown;
  diagram_strategy: unknown;
  powerpoint_constraints: unknown;
  forbidden_patterns: unknown;
  five_second_test_contract: unknown;
  design_philosophy_refs: unknown;
}
```

Extend `VisualReviewPageDeckDesignSystem` and `VisualReviewPageSlideContract` with the registered fields only. Keep `VisualCompilationPlan` absent from all user-surface types.

- [ ] **Step 5: Update exact validation arrays**

Add the two top-level fields to `visualFields`, create `visualBriefFields` with the exact 14 keys, and extend design/slide arrays. Validate roots with `hasExactDataFields`; do not loosen to `z.record`, index signatures, or arbitrary keys.

- [ ] **Step 6: Update ViewModel and field order**

Add:

```typescript
export const VISUAL_BRIEF_FIELD_ORDER = [
  "decision_task",
  "design_stance",
  "audience_fit",
  "emotional_boundary",
  "brand_boundary",
  "density_strategy",
  "narrative_rhythm",
  "imagery_strategy",
  "diagram_strategy",
  "powerpoint_constraints",
  "forbidden_patterns",
  "five_second_test_contract",
  "design_philosophy_refs",
] as const;
```

Keep `design_proposition` as the brief section heading, not a duplicate row and not an independent field-comment target. Extend design and slide orders with the new fields in the same semantic sequence as the approved design.

- [ ] **Step 7: Run GREEN**

```bash
cd 产品代码
npx vitest run --configLoader runner \
  widget/src/visual-review/visual-review-page-view-model.test.tsx \
  widget/src/ReviewSurfaceRouter.test.tsx
npm run typecheck
```

Expected: exact projection, adapter, fixture, Router, and type checks pass.

### Task 3: Render the Visual Brief and new semantics without changing structure

**Files:**
- Modify: `widget/src/visual-review/VisualContractView.tsx`
- Modify: `widget/src/visual-review/visual-contract-mark-validation.ts`
- Modify: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`
- Verify or minimally modify: `widget/src/styles/visual-review.css`

- [ ] **Step 1: Add RED DOM and outline tests**

Require the complete contract view to render sections in this order:

```text
Visual Brief
Deck Design System
Anchor Slide Evidence
S01 ... Sn Slide Visual Contract
```

Require visible labels:

```text
决策任务
设计立场
情绪边界
品牌边界
密度策略
五秒判断口径
跨页节奏规则
强调预算
图像语言
图示语言
读者五秒判断
主信息关系
辅助信息关系
视觉机制
视觉重心
资产角色
页面禁止模式
与前页节奏
与后页节奏
文字密度预算
PowerPoint 实现要求
验收证据计划
```

Assert `VisualCompilationPlan`, `compiler_version`, `visual/compilation-plan`, G1, G2, revision, and generic “技术信息” do not appear in the visible document.

- [ ] **Step 2: Add RED interaction-preservation tests**

Keep existing assertions for:

- one compact top bar and no second sticky bar;
- direct two-view switch;
- left outline overlay and right marks overlay;
- no project badge or persistent right panel;
- text-range action appears only after a real same-field selection;
- field comment icon creates a draft;
- Visual Brief field mark uses `deck_section_id: "visual-brief"`;
- `design_proposition` renders once as the section heading and has no duplicate field-comment control;
- saved brief/design/slide marks remain one `VisualContractReviewMarkSet`.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
npx vitest run --configLoader runner \
  widget/src/visual-review/VisualProfessionalReviewPage.test.tsx
```

Expected: Visual Brief/new labels are absent.

- [ ] **Step 4: Add stable labels and section rendering**

Add label maps:

```typescript
const BRIEF_LABELS = {
  decision_task: "决策任务",
  design_stance: "设计立场",
  audience_fit: "受众与阅读场景",
  emotional_boundary: "情绪边界",
  brand_boundary: "品牌边界",
  density_strategy: "密度策略",
  narrative_rhythm: "叙事节奏",
  imagery_strategy: "图像总策略",
  diagram_strategy: "图示总策略",
  powerpoint_constraints: "PowerPoint 约束",
  forbidden_patterns: "整套禁止模式",
  five_second_test_contract: "五秒判断口径",
  design_philosophy_refs: "设计哲学参考",
} as const;
```

Extend `DESIGN_LABELS` and `SLIDE_LABELS` with the exact Chinese labels from Step 1. Render the brief as the first contract article, use `design_proposition` once as its heading/subtitle, and reuse the existing `ContractValue`, field-comment action, selection anchoring, and drawer model for the ordered brief rows only.

- [ ] **Step 5: Add outline and mark identity**

Add the Visual Brief outline entry before Deck Design System. Update `markTargetLabel()` so `visual-brief` uses `BRIEF_LABELS`, `deck-design-system` uses `DESIGN_LABELS`, and slides use `SLIDE_LABELS`. Do not introduce a third drawer or another toolbar.

- [ ] **Step 6: Preserve visual CSS geometry**

Use existing contract article/row classes. If spacing is required, add only a section modifier that does not change header height, document max width, drawer direction, anchor canvas geometry, or responsive breakpoints. No new cards, pills, badges, tabs, fixed sidebar, or dashboard grid.

- [ ] **Step 7: Run GREEN and responsive regression**

```bash
cd 产品代码
npx vitest run --configLoader runner \
  widget/src/visual-review/VisualProfessionalReviewPage.test.tsx \
  widget/src/visual-review/VisualReviewResponsive.test.tsx \
  widget/src/visual-review/visual-review-page-view-model.test.tsx
```

Expected: all tests pass and accepted layout/interaction assertions remain unchanged.

### Task 4: Full product verification and commit

**Files:**
- Verify all R3 source, fixtures, and tests

- [ ] **Step 1: Run focused backend and Widget suites**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v22_visual_review_service \
    tests.test_v22_visual_review_contracts \
    tests.test_v23_visual_lineage
npx vitest run --configLoader runner \
  widget/src/visual-review/visual-review-page-view-model.test.tsx \
  widget/src/visual-review/VisualProfessionalReviewPage.test.tsx \
  widget/src/visual-review/VisualReviewResponsive.test.tsx \
  widget/src/ReviewSurfaceRouter.test.tsx
npm run typecheck
npm run build
```

Expected: zero failures.

- [ ] **Step 2: Run full regression**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm run test:node
npm run test:widget -- --configLoader runner
npm run build
```

Expected: all available suites pass. This is E2 automation only, not a new UI acceptance or visual-quality acceptance.

- [ ] **Step 3: Scan forbidden surfaces, placeholders, and scope**

```bash
cd 产品代码
rg -n 'TODO|TBD|适当处理|后续补充|NotImplemented' \
  src/ai_ppt_studio/application/visual_review_service.py \
  widget/src/visual-review \
  widget/src/review-surface-validation.ts \
  widget/src/types/visual-review.ts
rg -n 'VisualCompilationPlan|visual-compilation-plan|compiler_version|技术信息' \
  widget/src/visual-review widget/src/types/visual-review.ts
git diff --check
git status --short
```

Expected: no placeholders; plan identifiers appear only in negative tests if needed, not production UI types or rendered copy; only R3-scoped files changed.

- [ ] **Step 4: Commit rollback units**

```bash
git add \
  src/ai_ppt_studio/application/visual_review_service.py \
  tests/test_v22_visual_review_service.py
git commit -m "feat: project v2.3 visual review semantics"

git add \
  widget/src/types/visual-review.ts \
  widget/src/review-surface-validation.ts \
  widget/src/visual-review/visual-contract-field-contract.ts \
  widget/src/visual-review/visual-review-page-view-model.ts \
  widget/src/visual-review/visual-review-page-view-model.test.tsx \
  widget/src/__fixtures__/review-projection.visual.json \
  widget/src/ReviewSurfaceRouter.test.tsx
git commit -m "feat: close v2.3 visual review view model"

git add \
  widget/src/visual-review/VisualContractView.tsx \
  widget/src/visual-review/visual-contract-mark-validation.ts \
  widget/src/visual-review/VisualProfessionalReviewPage.test.tsx \
  widget/src/visual-review/VisualReviewResponsive.test.tsx \
  widget/src/styles/visual-review.css
git commit -m "feat: render v2.3 visual contract semantics"
```

If CSS is unchanged, omit it from the final `git add`. Expected: three non-amended local commits; no merge, push, install, Runtime sample write, PPTX generation, or publication.

## R3 exit report

The current R3 exit report is:

```text
backend projection and closed ViewModel: implemented in R3 source HEAD 97d5b99; implementation tip 69e87c1
text anchors, token maps, lineage, replay, and formal G3 reset boundary: implemented and source-reviewed
existing accepted UI structure: unchanged; R3 does not reopen the prior UI acceptance
automated verification on merge candidate 21cfe9e: Python 566/566; Node 137/137; Widget 755/755 (16 files, text-anchor integration 17/17); MCP 1/1; typecheck/build/diff-check passed
Review B2: P0=0 / P1=0 / P2=0 / P3=0
Review C2: P0=0 / P1=0 / P2=0 / P3=0
real PPT samples: not run
target PowerPoint: not checked
user visual acceptance: not established
integration into codex/v23-visual-quality-20260831: completed locally by merge commit 21cfe9e after explicit user approval
push / plugin install / publication / R4 / R5: not performed
```
