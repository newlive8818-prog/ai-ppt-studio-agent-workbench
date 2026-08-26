# ReviewSession Consumer Compatibility Design

## 1. Context and defect

The authoritative Python ReviewSession contract now defines:

- host open: `not-requested | pending | opened | failed | unavailable`;
- host notification: `not-requested | pending | sent | failed | unavailable`;
- AI receipt: `pending | received | rejected | unverified`.

The current Widget `validateSession()` still accepts older subsets. A valid `notify-only` session is created with `host_notification_status = pending`; the current Router rejects that projection and renders `审核数据无效，请重新打开审核页。` before the accepted visual page mounts.

This slice aligns consumers with the already completed authority contract. It does not change ReviewSession business behavior or redesign either review page.

## 2. Authority and scope

The Python contract in `src/ai_ppt_studio/domains/review/contracts.py` is authoritative for status vocabulary and receipt requirements. TypeScript validators must accept every authority-issued live-session sub-status while continuing to fail closed for unknown values and impossible receipt combinations.

Allowed files:

- `widget/src/review-surface-validation.ts`;
- focused Router/Browser client validation tests;
- preview/acceptance tests only when needed to reproduce unmodified Python output;
- this design and its implementation plan.

Forbidden files and behavior:

- Python ReviewSession service and domain contracts;
- content and visual page layout, CSS, labels, or interactions;
- MCP public catalog;
- Review Bridge HTTP behavior;
- G0/G3/G4 behavior;
- temporary data normalization in production or preview scripts.

## 3. Validation semantics

### 3.1 Renderable main session states

This compatibility fix keeps the existing main-state rendering policy unchanged: `ready | opened | submitted | superseded`. It does not make `preparing` or detached `expired` sessions render as current review pages. A future product decision may define dedicated preparing/expired UI, but this defect does not authorize that expansion.

### 3.2 Host-open states

Accept the full authority-issued set for a live projection:

```text
not-requested | pending | opened | failed | unavailable
```

Only `opened` requires `last_opened_at` and `host_open_receipt_ref`. `pending`, `failed`, and `unavailable` must not require a success receipt.

### 3.3 Host-notification states

Accept:

```text
not-requested | pending | sent | failed | unavailable
```

Only `sent` requires `host_notification_receipt_ref`. Visual saved-artifact binding maps remain empty unless the session is `sent`; existing anti-spoofing rules remain unchanged.

### 3.4 AI-receipt states

Accept:

```text
pending | received | rejected | unverified
```

Only `received` requires `ai_receipt_ref`. `rejected` is a truthful negative result, not an alias for success or the retired `failed` vocabulary.

### 3.5 Fail-closed behavior

Unknown status strings, success without a receipt, receipt maps without the matching success state, wrong receipt kinds, wrong session identity, stale revision, or unsupported extra fields continue to return `null` from validation. No value is coerced into another state.

## 4. Data flow

```text
Python ReviewSession authority
-> content/visual projection
-> Review Bridge envelope
-> clone and closed validation
-> existing ContentReviewPageViewModel or VisualReviewPageViewModel
-> already accepted page
```

The fix occurs only in the closed validation step. The ViewModels and rendered pages receive the same data shape as before.

## 5. Testing and acceptance

TDD must first reproduce the actual failure with `ready + notify-only + host_notification_status=pending + ai_receipt_status=pending`. Further focused cases cover `host_open_status=pending|unavailable`, `host_notification_status=unavailable`, and `ai_receipt_status=rejected|unverified`.

Negative tests cover unknown values and preserve receipt requirements. The test must fail before the validator is changed and pass afterward.

Engineering exit requires:

1. focused Router/validation tests pass;
2. all Widget tests pass;
3. Node and Python suites pass because the defect crosses the Runtime-to-Widget boundary;
4. TypeScript typecheck and Widget build pass;
5. an unmodified Python-seeded visual preview renders the accepted page in Browser without temporary status replacement;
6. Browser shows both visual tabs, the switch works, and relevant console error/warn output is empty;
7. Git diff contains no page component or CSS changes.

Browser proof remains local engineering evidence. It does not prove real host notification, AI receipt, G3, PowerPoint, delivery, or release.
