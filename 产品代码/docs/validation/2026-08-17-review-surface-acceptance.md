# Review Surface Prototype Fidelity and Acceptance Record

## 1. Record identity

- Implementation plan: `docs/superpowers/plans/2026-08-17-review-surface-prototype-fidelity-and-acceptance.md`
- Validation date: 2026-08-18
- Isolated worktree: `/private/tmp/ai-ppt-v22-TmBomR`
- Branch: `codex/review-surface-v22`
- Task 7 base commit: `95cea89 feat: restore full visual contract document`
- Local report: `output/playwright/v22-ui/v22-ui-acceptance.json`

This record closes the deterministic Task 7 acceptance gaps. It does not convert local preview, test, fixture, screenshot, or local HTTP evidence into Codex Browser, Review Bridge host, AI receipt, G0, G3, G4, or user-acceptance evidence.

## 2. Evidence boundary

The local report is required to contain this fixed evidence identity:

```json
{
  "evidenceScope": "local-development-preview",
  "proofEligible": false,
  "realHostEvidence": false
}
```

`LOCAL_PREVIEW_EVIDENCE` is frozen in code. The runner has no flag or environment variable that can promote either boolean to `true`.

| Evidence class | Current result | What it proves | What it does not prove |
|---|---|---|---|
| Automated logic evidence | Passed | Projection, UI behavior, structure-count, interaction-state coverage, Review Bridge protocol logic, type and build contracts | A real host opened the review page or sent/received a receipt |
| Local deterministic browser and screenshot evidence | Passed | Current built Widget renders and behaves under local headless Chromium at the tested viewports and fixtures | Codex Browser, real Review Bridge host integration, AI receipt, G3, or user acceptance |
| Real Browser / Review Bridge evidence | Not obtained | Nothing in this run | Host opening, host notification, AI receipt, close/reopen restoration, or a real review transaction |
| Unverified CapabilityGap | Open | The remaining boundary is explicit | It must not be described as passed until real host receipts exist |

## 3. Automated logic evidence

Commands and observed results:

```text
node --test tests/v22-prototype-fidelity.test.mjs
5 passed / 5 total

npm run test:node
92 passed / 92 total

npm run test:widget -- --reporter=dot
12 test files passed
515 passed / 515 total

npm run typecheck
passed

npm run build
passed

git diff --check
passed
```

The new acceptance contracts fail closed when a required prototype selector count is zero, require every approved interaction state exactly once, reject formal or real-host claims in local preview evidence, and guard the browser runner against page-wide repeated slide-contract readability queries.

The contract readability check now treats the title page and Anchor Slide Evidence once as document-level content, then queries every `.visual-slide-contract` only through:

```js
contract.locator(slideReadableSelector)
```

The stale `.visual-contract-title-page code` selector is no longer used.

## 4. Local deterministic browser and screenshot evidence

Command:

```text
npm run accept:v22-ui
```

The normal macOS sandbox launch was blocked by Chromium before page execution:

```text
bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer
Permission denied (1100)
```

The same acceptance command was then run in the approved controlled environment and passed. This permission difference is an execution-environment constraint; it is not a product failure and is not real-host evidence.

Observed report result:

- `ok = true`;
- content and visual surfaces each checked at 360, 760, 1000, and 1440 CSS px;
- 8 responsive results total;
- 0 horizontal-overflow results;
- 0 console errors across all 8 results;
- content long-document check: 60 slides;
- visual-contract long-document check: 120 slide contracts;
- content material assets loaded without placeholder fallback;
- all 3 anchor assets and comparison assets loaded;
- PageDecision target height and 360 px 2×2 layout checked;
- wide/narrow anchor layout, 760 px sticky assistant, rectangle geometry, directory jump, contract readability, and anchor/contract draft isolation checked;
- `proofEligible = false`;
- `realHostEvidence = false`.

### 4.1 Structural fidelity counts

The runner counts the semantic selectors emitted by the built React surface and passes them through `assertPrototypeFidelityCounts`.

- Content review: head, progress, chapter navigation, deck intro, chapter nodes, slide nodes, and review summary all present; 3 current slides.
- Visual anchor: white topbar contract, project identity, AI mark, segmented view switch, compact status, workbench, main area, assistant, composer, and status record all present after a real pointer drag; exactly 3 current anchors.
- Visual contract: title page, Deck Design System, Anchor Slide Evidence, all 3 current slide contracts, outline, and overlay drawer all present.

### 4.2 Required interaction screenshots

The report contains each state exactly once:

| State | Local capture meaning |
|---|---|
| `content-before-feedback` | Current content page before a non-approved PageDecision draft |
| `content-after-non-approved-feedback` | Same page after selecting `需要修改` and entering the local draft comment |
| `anchor-before-rectangle-feedback` | Current anchor editor before annotation |
| `anchor-after-rectangle-feedback` | Pointer-drag candidate rectangle plus the filled composer below the slide |
| `contract-with-anchor-slide-evidence` | Current-version Anchor Slide Evidence section in the continuous contract |
| `contract-directory-drawer` | Overlay contract directory |
| `contract-mark-drawer` | Overlay mark record drawer |
| `saved-unverified-receipt` | Local projection fixture showing saved persistence, unavailable host notification, and unverified AI receipt |

Screenshots are local visual-comparison evidence only. The `saved-unverified-receipt` fixture modifies only the preview payload and is intentionally read-only. It proves that the UI can render separate facts:

```text
持久化：已保存
宿主通知：不可用
AI 接收：未验证
```

It is not a host notification, not an AI receipt, and not proof that the real host accepted or processed a contract mark.

## 5. Real Browser / Review Bridge evidence

No real Codex Browser or approved host review session was opened during this validation run. No real Review Bridge host-open callback, host-notification send receipt, or AI receipt was produced.

The passing Review Bridge Node tests exercise local protocol and state-transition logic, including loopback HTTP behavior. They do not establish that the Codex host injected the adapter, opened the current ReviewSession, restored a closed page, sent a notification, or delivered feedback to an AI process.

The following real-host checks therefore remain unverified:

1. Open the current content and visual ReviewSession through the approved host path.
2. Close and reopen the same session and prove restoration of view, logical scroll, PageDecision/feedback drafts, and current source/revision.
3. Save an AnchorFeedbackBatch and a VisualContractReviewMarkSet through the real Review Bridge.
4. Obtain a real host-notification receipt bound to the exact saved artifact.
5. Obtain a real AI receipt bound to the same current artifact, sourceVersion, revision, and ReviewSession.
6. Reject stale source/revision writes without losing the user draft.

## 6. CapabilityGap disposition

Current disposition:

```text
implemented-and-tested + real-host-capability-gap
```

- Deterministic implementation and local validation are passed.
- Real host opening, notification, AI receipt, and close/reopen recovery are still a `CapabilityGap` for this record.
- No local test, local Playwright run, local fixture, screenshot, installed plugin state, or historic evidence may change that disposition.
- G3 remains a separate trusted user confirmation in the Codex conversation and is not implied by saved feedback or marks.

## 7. Acceptance conclusion

Task 7 deterministic acceptance is passed: selectors are semantic and scoped, required regions fail closed, all eight interaction states are captured exactly once, long documents and four responsive widths pass, and the report preserves the local-only evidence boundary.

Stage 8 real-host acceptance is not passed. The branch may remain as an independently reviewable implementation branch, but it must not be described as fully host-verified or release-ready until the open CapabilityGap is resolved with current real receipts.
