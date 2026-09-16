# Content Review Frontend Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two remaining accepted content-review frontend contract gaps: locate the next page without a saved current decision, and expose perceptible hover/active feedback on the four PageDecision controls.

**Architecture:** Keep the active `ReviewSurfaceRouter → ContentReviewViewModelController → ContentReviewViewModelSurface` route unchanged. Derive the next incomplete slide exclusively from the existing ViewModel (`savedDecision === null || localDraftState.dirty`) and perform a local DOM scroll with no Runtime write; keep interaction styling local to the active ViewModel stylesheet.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, CSS.

---

### Task 1: Add next-incomplete navigation to the active ViewModel surface

**Files:**
- Modify: `widget/src/content-review/ContentReviewViewModelSurface.test.tsx`
- Modify: `widget/src/content-review/ContentReviewViewModelSurface.tsx`

- [ ] **Step 1: Write the failing navigation tests**

Add one test that gives page S01 a valid `savedDecision`, leaves S02 unsaved, clicks `定位下一页未判断`, and expects only `#content-vm-S02.scrollIntoView({ behavior: "smooth", block: "start" })`. Add a second assertion that the control reads `全部页面已完成判断` and is disabled when every slide has a saved decision and no dirty draft.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
npm run test:widget -- --run widget/src/content-review/ContentReviewViewModelSurface.test.tsx
```

Expected: FAIL because the active ViewModel surface has no next-incomplete control.

- [ ] **Step 3: Implement the smallest navigation behavior**

In `ContentReviewViewModelSurface`, derive:

```ts
const nextIncompleteSlide = viewModel.slides.find(
  (slide) => !slide.savedDecision || slide.localDraftState.dirty,
);
```

Render a secondary header button. When enabled, resolve `content-vm-${nextIncompleteSlide.slideId}` and call:

```ts
target?.scrollIntoView({ behavior: "smooth", block: "start" });
```

The control must not call `bridge`, `onSavePageDecision`, or `onSubmitReviewBatch`.

- [ ] **Step 4: Re-run the focused test and verify GREEN**

Run the Step 2 command. Expected: the file passes with zero failures.

### Task 2: Add hover and active feedback to active PageDecision controls

**Files:**
- Modify: `widget/src/content-review/ContentReviewViewModelResponsive.test.tsx`
- Modify: `widget/src/styles/content-review-view-model.css`

- [ ] **Step 1: Write the failing CSS contract test**

Require `.page-decision-option:hover` to change border/background and `.page-decision-option:active` to produce a perceptible pressed transform without removing the existing `focus-visible` or selected-state rules.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
npm run test:widget -- --run widget/src/content-review/ContentReviewViewModelResponsive.test.tsx
```

Expected: FAIL because the active stylesheet has no hover or active selectors.

- [ ] **Step 3: Implement the smallest interaction styles**

Add active-surface-only rules:

```css
.page-decision-option:hover { border-color: #8192ad; background: #f8fafc; }
.page-decision-option:active { transform: translateY(1px); }
```

Do not import legacy `content-review.css` and do not copy quarantine components.

- [ ] **Step 4: Re-run the focused test and verify GREEN**

Run the Step 2 command. Expected: the file passes with zero failures.

### Task 3: Verify the complete Slice 6 boundary

**Files:**
- Verify only; no additional product changes unless a regression is attributable to Tasks 1–2.

- [ ] **Step 1: Run TypeScript and focused activity-chain tests**

```bash
npm run typecheck
npm run test:widget -- --run \
  widget/src/ReviewSurfaceRouter.test.tsx \
  widget/src/content-review/ContentReviewViewModelController.test.tsx \
  widget/src/content-review/ContentReviewViewModelSurface.test.tsx \
  widget/src/content-review/ContentReviewViewModelResponsive.test.tsx \
  widget/src/content-review/content-review-page-view-model.test.tsx \
  widget/src/content-review/ContentFullDeckReviewPage.test.tsx \
  widget/src/BrowserReviewClient.test.tsx
```

Expected: typecheck exits 0 and all selected tests pass.

- [ ] **Step 2: Run the full Widget suite and spatial-contract tests**

```bash
npm run test:widget
node --test tests/v22-prototype-fidelity.test.mjs
```

Expected: both commands exit 0 with zero failures.

- [ ] **Step 3: Verify repository boundaries**

```bash
git diff --check
git status --short --branch
git diff --name-only 69bff699073039e56b707734a8c4b5e093502890...HEAD
```

Expected: no whitespace errors; only this plan, the active Surface/test, and active CSS/test are changed. Quarantine remains untouched.

- [ ] **Step 4: Request an independent read-only code review**

The reviewer must report Critical, Important, and Minor findings and explicitly state whether the slice is ready for an engineering merge decision. Local tests do not prove real host open, host notification, AI receipt, G0, release, install, merge, push, or user acceptance.
