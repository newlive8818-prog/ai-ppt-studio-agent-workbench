# ReviewSession Consumer Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Widget accept every authoritative live ReviewSession sub-status emitted by Python while preserving closed validation, success-receipt requirements, and the already accepted content and visual pages.

**Architecture:** Python remains the status-vocabulary authority. The Widget Router continues to clone and validate a closed projection before adapting it to the existing page ViewModels; this slice changes only the three sub-status allowlists in that validation boundary and proves the change with focused Router tests plus an unmodified Python-seeded Browser preview.

**Tech Stack:** TypeScript, React 19, Vitest, Testing Library, Node.js, Python unittest, Vite, local Review Bridge preview.

---

## Fixed boundary and file map

| File | Responsibility in this slice |
|---|---|
| `widget/src/ReviewSurfaceRouter.test.tsx` | Reproduce authority-issued status combinations through the real active Router and preserve fail-closed receipt rules. |
| `widget/src/review-surface-validation.ts` | Accept the authoritative host-open, host-notification, and AI-receipt sub-status vocabularies. |
| `docs/superpowers/specs/2026-08-26-review-session-consumer-compatibility-design.md` | Approved design and scope boundary; already committed in `f833581`. |
| `docs/superpowers/plans/2026-08-26-review-session-consumer-compatibility.md` | This implementation and verification plan. |

No Python ReviewSession file, page component, CSS file, MCP catalog, Review Bridge behavior, preview normalization, or Gate behavior may change.

The main renderable session states stay `ready | opened | submitted | superseded`.

The three authority-owned sub-status sets are:

```text
host_open_status:
not-requested | pending | opened | failed | unavailable

host_notification_status:
not-requested | pending | sent | failed | unavailable

ai_receipt_status:
pending | received | rejected | unverified
```

Receipt requirements stay unchanged: `opened` requires the open timestamp and receipt, `sent` requires a notification receipt, and `received` requires an AI receipt. Unknown values, wrong receipt kinds, mismatched identities, stale revisions, success without receipts, and non-empty binding maps for non-success states remain invalid.

### Task 1: Establish the isolated baseline

**Files:**

- Read: `package.json`
- Read: `package-lock.json`
- Read: `widget/src/ReviewSurfaceRouter.test.tsx`
- Read: `widget/src/review-surface-validation.ts`

- [ ] **Step 1: Verify the linked-worktree identity and cleanliness**

Run from the R1 worktree root:

```bash
pwd -P
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git rev-parse HEAD
git status --short --branch
```

Expected: branch `codex/slice-review-session-consumer-compat-20260826`, HEAD contains design commit `f833581`, and no unplanned change exists except this plan.

- [ ] **Step 2: Install locked dependencies**

```bash
cd 产品代码
npm ci
```

Expected: exit 0 using `package-lock.json`; the lockfile does not change.

- [ ] **Step 3: Run the focused pre-change baseline**

```bash
cd 产品代码
npm run test:widget -- widget/src/ReviewSurfaceRouter.test.tsx
```

Expected: the existing Router suite passes before new tests. If not, stop and record the pre-existing failure.

- [ ] **Step 4: Commit only this plan**

```bash
git add 产品代码/docs/superpowers/plans/2026-08-26-review-session-consumer-compatibility.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: plan ReviewSession consumer compatibility"
```

Expected: one documentation-only commit.

### Task 2: RED — reproduce authority-issued live statuses

**Files:**

- Modify: `widget/src/ReviewSurfaceRouter.test.tsx`
- Test: `widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: Add valid-page assertions near the existing fixture helpers**

```tsx
function expectVisualReviewPage() {
  expect(screen.getByRole("tab", { name: "3 页锚点成果" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "完整视觉合同" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
}

function expectContentReviewPage() {
  expect(screen.getByRole("heading", { name: "p1" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
}
```

These assertions exercise the active Router; do not export or call the private validator.

- [ ] **Step 2: Add the actual notify-only pending regressions**

```tsx
it("renders a ready notify-only visual session while host notification is pending", () => {
  const visual = visualReviewSurface();
  visual.review.review_session.open_policy = "notify-only";
  visual.review.review_session.host_notification_status = "pending";

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expectVisualReviewPage();
});

it("renders a ready notify-only content session while host notification is pending", () => {
  const content = contentReviewSurface();
  content.review.review_session.open_policy = "notify-only";
  content.review.review_session.host_notification_status = "pending";

  render(<ReviewSurfaceRouter data={content} bridge={bridge} />);

  expectContentReviewPage();
});
```

- [ ] **Step 3: Add foreground host-open pending coverage**

```tsx
it("renders a ready foreground visual session while host opening is pending", () => {
  const visual = visualReviewSurface();
  visual.review.review_session.host_open_status = "pending";

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expectVisualReviewPage();
});
```

- [ ] **Step 4: Add unavailable and truthful AI negative-state coverage**

```tsx
it.each([
  ["host open unavailable", (data: VisualReviewSurfaceData) => {
    data.review.review_session.host_open_status = "unavailable";
  }],
  ["host notification unavailable", (data: VisualReviewSurfaceData) => {
    data.review.review_session.host_notification_status = "unavailable";
  }],
  ["AI receipt rejected", (data: VisualReviewSurfaceData) => {
    data.review.review_session.ai_receipt_status = "rejected";
  }],
  ["AI receipt unverified", (data: VisualReviewSurfaceData) => {
    data.review.review_session.ai_receipt_status = "unverified";
  }],
] as Array<[string, (data: VisualReviewSurfaceData) => void]>) (
  "renders a visual review for authoritative %s status",
  (_label, mutate) => {
    const visual = visualReviewSurface();
    mutate(visual);

    render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

    expectVisualReviewPage();
  },
);
```

- [ ] **Step 5: Add fail-closed unknown-value tests**

```tsx
it.each([
  ["host_open_status", "opening"],
  ["host_notification_status", "queued"],
  ["ai_receipt_status", "failed"],
])("rejects unknown ReviewSession %s value", (field, status) => {
  const visual = visualReviewSurface();
  (visual.review.review_session as unknown as Record<string, unknown>)[field] = status;

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
});
```

The retired AI value `failed` must remain invalid; `rejected` must not be coerced into it.

- [ ] **Step 6: Preserve success-receipt requirements**

Add or retain explicit Router cases proving that:

```tsx
it("rejects opened host status without its success receipt", () => {
  const visual = visualReviewSurface();
  visual.review.review_session.host_open_status = "opened";
  visual.review.review_session.last_opened_at = "2026-08-15T00:01:00Z";

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
});

it("rejects sent notification status without its success receipt", () => {
  const visual = visualReviewSurface();
  visual.review.review_session.host_notification_status = "sent";

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
});

it("rejects received AI status without its success receipt", () => {
  const visual = visualReviewSurface();
  visual.review.review_session.ai_receipt_status = "received";

  render(<ReviewSurfaceRouter data={visual} bridge={bridge} />);

  expect(screen.getByRole("alert")).toHaveTextContent(/审核数据无效.*重新打开/);
});
```

Avoid duplicate tests when equivalent cases already exist.

- [ ] **Step 7: Run RED and inspect the failure reason**

```bash
cd 产品代码
npm run test:widget -- widget/src/ReviewSurfaceRouter.test.tsx
```

Expected: only the new legal-status acceptance cases fail because the Router renders invalid-data recovery. Unknown and missing-receipt tests still pass. Do not edit production code before observing this.

### Task 3: GREEN — minimally align three allowlists

**Files:**

- Modify: `widget/src/review-surface-validation.ts`
- Test: `widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: Replace only three stale allowlists**

Replace:

```ts
|| !["not-requested", "opened", "failed"].includes(String(value.host_open_status))
|| value.persistence_status !== "saved"
|| !["not-requested", "sent", "failed"].includes(String(value.host_notification_status))
|| !["pending", "received", "failed"].includes(String(value.ai_receipt_status))
```

with:

```ts
|| !["not-requested", "pending", "opened", "failed", "unavailable"].includes(String(value.host_open_status))
|| value.persistence_status !== "saved"
|| !["not-requested", "pending", "sent", "failed", "unavailable"].includes(String(value.host_notification_status))
|| !["pending", "received", "rejected", "unverified"].includes(String(value.ai_receipt_status))
```

Do not change the main `status` allowlist or any receipt checks.

- [ ] **Step 2: Run GREEN**

```bash
cd 产品代码
npm run test:widget -- widget/src/ReviewSurfaceRouter.test.tsx
```

Expected: focused Router suite passes.

- [ ] **Step 3: Inspect the production diff**

```bash
git diff -- 产品代码/widget/src/review-surface-validation.ts
```

Expected: exactly three allowlist edits.

### Task 4: Run complete engineering verification

- [ ] **Step 1: Run all Widget tests**

```bash
cd 产品代码
npm run test:widget
```

- [ ] **Step 2: Run typecheck and build**

```bash
cd 产品代码
npm run typecheck
npm run build
```

- [ ] **Step 3: Run Node and Python suites**

```bash
cd 产品代码
npm run test:node
npm run test:python
```

Record fresh counts. Do not reuse recovery-baseline counts.

- [ ] **Step 4: Check whitespace and scope**

```bash
git diff --check
git status --short
git diff --name-only b7759b326b1ab22957616f66c7a179014a71e9db...HEAD
git diff --name-only
```

Expected uncommitted implementation files only:

```text
产品代码/widget/src/ReviewSurfaceRouter.test.tsx
产品代码/widget/src/review-surface-validation.ts
```

Branch history may additionally contain only the R1 design and plan documents.

### Task 5: Prove the raw Python-to-Widget path

**Files:**

- Execute: `scripts/seed-v16-ui-project.py`
- Execute: `scripts/create-review-preview.mjs`
- Read: generated disposable preview and Browser DOM/console

- [ ] **Step 1: Seed a disposable current-Runtime project**

Run the supported seed from `产品代码` and capture its `project_root`, `workspace_config`, and visual ReviewSession id. The generated session must retain its authority-issued pending host sub-status. Do not rewrite the session or preview.

- [ ] **Step 2: Build and generate the raw visual preview**

```bash
npm run build
node scripts/create-review-preview.mjs <project_root> <workspace_config> visual <visual_review_session_id>
```

Expected: generation exits 0 from the unmodified Python projection.

- [ ] **Step 3: Verify in the in-app Browser**

Serve only the disposable preview directory on loopback and open the generated visual HTML without string replacement or status normalization. Verify both visual tabs exist, switching works, the DOM lacks `审核数据无效`, and relevant console error/warn output is empty.

This is local engineering evidence only. It does not prove a real host-open receipt, host notification, AI receipt, G3, PowerPoint, delivery, release, or new UI acceptance.

### Task 6: Commit the isolated R1 implementation

- [ ] **Step 1: Review the final delta**

```bash
git diff --stat b7759b326b1ab22957616f66c7a179014a71e9db...HEAD
git diff -- 产品代码/widget/src/ReviewSurfaceRouter.test.tsx 产品代码/widget/src/review-surface-validation.ts
git status --short
```

No page component, CSS, Python service/domain, MCP catalog, Review Bridge, content-hard-gate, visual-production, delivery, or experience file may change.

- [ ] **Step 2: Stage exact files**

```bash
git add 产品代码/widget/src/ReviewSurfaceRouter.test.tsx 产品代码/widget/src/review-surface-validation.ts
git diff --cached --check
git diff --cached --name-only
```

Expected: exactly two implementation files. Never use `git add .`.

- [ ] **Step 3: Commit**

```bash
git commit -m "fix: accept authoritative ReviewSession statuses"
```

- [ ] **Step 4: Run fresh verification from committed HEAD**

```bash
cd 产品代码
npm run typecheck
npm run build
npm run test:node
npm run test:widget
npm run test:python
cd ..
git diff --check
git status --short --branch
git log --oneline -4
```

Expected: every command exits 0 and R1 is clean on its own feature branch.

## Exit decision and next worktree boundary

R1 is engineering-complete only when Tasks 1–6 have fresh evidence. Its resulting feature HEAD is the only valid parent for dependent R2 typed MCP catalog unless the user later authorizes integration first.

The existing clean worktree `slice-mcp-typed-catalog-20260826` is stale because it was created at pre-R1 HEAD `b7759b3`. Do not implement R2 there and do not remove it without a separate safe cleanup decision. Create a new R2 branch/worktree from verified R1 HEAD, or recreate the old empty branch/worktree only after explicit safe cleanup authorization.

Do not merge, amend, push, install a plugin, publish, or send anything externally as part of this plan.
