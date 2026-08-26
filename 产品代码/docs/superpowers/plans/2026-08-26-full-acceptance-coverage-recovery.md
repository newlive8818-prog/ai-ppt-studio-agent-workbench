# Full Acceptance Coverage Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate deterministic 120-mark complexity coverage from environment-sensitive full-DOM rendering, and publish truthful measurement-only evidence for the existing 120-slide Chromium acceptance probe.

**Architecture:** Pure validation tests own indexing complexity, a small React fixture owns composer update isolation, and the existing local Playwright runner owns long-document DOM completeness. Acceptance helpers validate timing and environment measurements but never turn them into real-host, Gate, or user-acceptance proof.

**Tech Stack:** TypeScript, React 19, Vitest, Node test runner, Playwright Chromium, existing schema 3 preview generator.

---

## Scope and rollback

- Source/rollback: `b6f6fa4cbf6ae99977b88469efdb8e9d59967afe`
- Design commit: `84bb5cc`
- No production React, Runtime, MCP, Review Bridge, Gate, release, or installer change.
- Do not increase the 30-second timeout and do not claim local Playwright as Codex Browser or host proof.

### Task 1: Add RED measurement-evidence contracts

**Files:**

- Modify: `tests/v22-ui-acceptance-evidence.test.mjs`
- Modify: `tests/v22-prototype-fidelity.test.mjs`
- Test: `tests/v22-ui-acceptance-evidence.test.mjs`
- Test: `tests/v22-prototype-fidelity.test.mjs`

- [ ] **Step 1: Write failing helper tests**

Import `assertLongReviewMeasurement` and `assertAcceptanceEnvironment` from `scripts/v22-ui-acceptance-evidence.mjs`. Assert that this long-review result is accepted:

```js
{
  reviewType: "visual",
  count: 120,
  viewport: { width: 1000, height: 900 },
  navigationToReadyMs: 1250.5,
  finalObjectAccessMs: 220.25,
  measurementMode: "local-playwright-measurement-only",
  complete: true,
  finalObjectPresent: true,
  noHorizontalOverflow: true,
  consoleErrorCount: 0,
}
```

Reject negative, infinite, missing, string, or boolean durations; a wrong measurement mode; non-positive count/viewport; incomplete/final-missing/overflow/error results. Accept an environment with non-empty `nodeVersion`, `chromiumVersion`, `platform`, `release`, `architecture`, and `runId`; reject each missing or blank field.

- [ ] **Step 2: Lock runner ownership**

In `v22-prototype-fidelity.test.mjs`, assert the runner source contains:

```js
assertLongReviewMeasurement
assertAcceptanceEnvironment
performance.now()
chromiumVersion
longReviewMeasurements
local-playwright-measurement-only
```

and still contains the 10/24/60 content and 120 visual calls.

- [ ] **Step 3: Run RED**

Run:

```bash
node --test tests/v22-ui-acceptance-evidence.test.mjs tests/v22-prototype-fidelity.test.mjs
```

Expected: fail because the two helper exports and runner measurement fields do not exist.

### Task 2: Implement closed measurement helpers

**Files:**

- Modify: `scripts/v22-ui-acceptance-evidence.mjs`
- Test: `tests/v22-ui-acceptance-evidence.test.mjs`

- [ ] **Step 1: Add strict finite-duration validation**

Implement:

```js
function finiteNonNegativeDuration(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error(`${label} must be a finite non-negative number.`);
  }
  return value;
}
```

- [ ] **Step 2: Add the long-review evidence validator**

Export `assertLongReviewMeasurement(value)`. Require exactly the semantic fields in Task 1, `reviewType` of `content|visual`, positive safe-integer `count`, a finite positive viewport, both finite non-negative durations, the exact measurement mode, all four success facts, and zero console errors. Return a plain normalized object without adding a performance verdict.

- [ ] **Step 3: Add the run-environment validator**

Export `assertAcceptanceEnvironment(value)`. Require the six non-empty trimmed strings in Task 1 and return a normalized plain object.

- [ ] **Step 4: Run helper GREEN**

Run the Task 1 Node test command. Expected: helper tests pass; runner source-contract test remains RED until Task 4.

### Task 3: Split the flaky 120-slide Widget test

**Files:**

- Modify: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`
- Test: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

- [ ] **Step 1: Import the authoritative initial validator**

Add:

```ts
import { validateInitialVisualContractMarkSet } from "./visual-contract-mark-validation";
import { deriveVisualReceiptFacts } from "./visual-receipt-facts";
```

- [ ] **Step 2: Replace the mixed 120-slide test with two tests**

The pure test builds the existing 120 slides and 120 proxied marks, calls:

```ts
const facts = deriveVisualReceiptFacts(markSet);
expect(facts).not.toBeNull();
const validated = validateInitialVisualContractMarkSet(markSet, data, facts!);
expect(validated?.markSet?.marks).toHaveLength(120);
expect(projectedMarkFieldReads).toBeGreaterThan(0);
expect(slideFindCalls).toBe(0);
```

It does not render React and has no custom wall-clock timeout.

The React test uses the normal small `visualData()` fixture with an existing projected mark set, renders `ControlledVisualContract`, opens `S01 构图意图`, edits the composer comment, and asserts projected mark field reads remain zero after the local change. It must not create 120 DOM slide contracts.

- [ ] **Step 3: Verify focused GREEN and repeatability**

Run the two tests three times with Vitest `--repeat=3` or three explicit invocations. Expected: every run passes comfortably below the old 30-second boundary and retains zero repeated scans/reads.

### Task 4: Record local Chromium long-review measurements

**Files:**

- Modify: `scripts/run-v22-ui-acceptance.mjs`
- Modify: `tests/v22-prototype-fidelity.test.mjs`
- Test: `tests/v22-prototype-fidelity.test.mjs`

- [ ] **Step 1: Import platform and evidence validators**

Use `node:os` for platform/release and import both new validators. Create `longReviewMeasurements = []`.

- [ ] **Step 2: Measure the two Browser phases**

In `checkLongReview`, measure with `performance.now()`:

1. immediately before `openPage` through first successful selector/count readiness;
2. immediately before locating/scrolling the final object through confirmation that its text includes the final page identity.

After completeness, overflow, and console assertions, normalize and push one `assertLongReviewMeasurement(...)` result. Do not add a time budget.

- [ ] **Step 3: Bind environment identity**

After Chromium launches, collect:

```js
const acceptanceEnvironment = assertAcceptanceEnvironment({
  nodeVersion: process.version,
  chromiumVersion: browser.version(),
  platform: os.platform(),
  release: os.release(),
  architecture: os.arch(),
  runId,
});
```

- [ ] **Step 4: Publish only after complete coverage**

Before report return, assert exactly four long-review measurements with identities `content:10`, `content:24`, `content:60`, `visual:120`. Add `acceptanceEnvironment` and `longReviewMeasurements` to the atomically published report, preserving `LOCAL_PREVIEW_EVIDENCE` and the disclaimer.

- [ ] **Step 5: Run runner-contract GREEN**

Run the two Node evidence test files. Expected: all pass.

### Task 5: Full verification and local commits

**Files:**

- Modify only the five implementation/test files above and this plan.

- [ ] **Step 1: Run focused checks**

```bash
node --test tests/v22-ui-acceptance-evidence.test.mjs tests/v22-prototype-fidelity.test.mjs
npm run test:widget -- --configLoader runner --run widget/src/visual-review/VisualProfessionalReviewPage.test.tsx -t 'indexes one 120-slide|does not re-read the saved mark set'
npm run typecheck
npm run build
```

Expected: zero failures.

- [ ] **Step 2: Run full engineering checks**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src python3 -m unittest discover -s tests
npm run test:node
npm run test:widget -- --configLoader runner
```

Expected: zero failures. Report exact counts; do not hide unrelated failures.

- [ ] **Step 3: Run local Browser acceptance when capability exists**

```bash
CODEX_NODE_MODULES=<bundled-node-modules> npm run accept:v22-ui
```

Expected: exit 0, atomically published report, exactly four validated measurement-only long-review entries, and all existing interaction evidence. If Chromium is denied by the macOS sandbox, record the exact CapabilityGap and verify no current report was falsely published.

- [ ] **Step 4: Verify Git boundary**

```bash
git diff --check
git status --short --branch
git diff --name-only b6f6fa4..HEAD
```

Expected: only Slice 9 design/plan and acceptance-test files; no production UI, Runtime, MCP, release, installer, quarantine, content-review business, or visual-review business change.

- [ ] **Step 5: Commit atomic rollback units**

Use exact `git add` paths only:

```bash
git add 产品代码/docs/superpowers/plans/2026-08-26-full-acceptance-coverage-recovery.md \
  产品代码/scripts/v22-ui-acceptance-evidence.mjs \
  产品代码/tests/v22-ui-acceptance-evidence.test.mjs \
  产品代码/tests/v22-prototype-fidelity.test.mjs
git commit -m "test: record long review acceptance measurements"

git add 产品代码/widget/src/visual-review/VisualProfessionalReviewPage.test.tsx
git commit -m "test: separate visual validation from DOM timing"
```

No amend, merge, push, release, or install.

## Self-review

- Spec coverage: deterministic complexity, React update isolation, Browser long-review completeness, truthful environment/timing evidence, atomic report behavior, and proof boundaries all map to a task.
- Placeholder scan: no deferred implementation placeholder or unspecified test command remains.
- Type consistency: helper names and report fields are identical across Tasks 1, 2, and 4.
- Scope: all changes remain acceptance-only; production behavior is explicitly excluded.
