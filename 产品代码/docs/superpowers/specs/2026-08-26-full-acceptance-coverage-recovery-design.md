# Full Acceptance Coverage Recovery Design

## Identity and boundary

- Date: 2026-08-26
- Slice: 9, complete acceptance-coverage recovery
- Branch: `codex/slice-full-acceptance-coverage-20260826`
- Source and rollback commit: `b6f6fa4cbf6ae99977b88469efdb8e9d59967afe`
- Status: approved under the user's delegated intermediate engineering-acceptance authority

This Slice changes acceptance tests, acceptance evidence helpers, the local Browser acceptance runner, and their documentation only. It does not change the accepted content-review or visual-review production UI, Runtime business contracts, Review Bridge writes, Gate semantics, release packaging, installation, or the quarantine checkout.

Local fixtures, JSDOM, generated previews, Playwright, screenshots, and timing measurements remain engineering evidence. They cannot prove a real Codex Browser handoff, host notification, AI receipt, G3, PowerPoint behavior, release, or user acceptance.

## Problem

The full Widget run currently contains a 120-slide visual-contract test whose deterministic purpose is to prove that validation indexes slides once and that a local composer edit does not re-read the saved mark set. The same test also mounts the full 120-slide React document in JSDOM and uses a fixed 30-second wall-clock timeout.

On Node 25.8.2 at the same clean HEAD, the test completed in about 28.5 seconds in one run and timed out at about 31.2 seconds in another. Its assertions confirmed that `slides.find` was never called and that composer changes did not re-read the projected mark set. The failure therefore does not identify an algorithm regression; it identifies a test that mixes a deterministic complexity contract with environment-sensitive full-DOM cost.

The existing Chromium acceptance runner already creates and opens a 120-slide visual contract, verifies all slide nodes and the final page, checks horizontal overflow and console errors, and keeps its evidence explicitly local and non-formal. It does not currently publish duration or execution-environment measurements for the long-review checks.

## Considered approaches

### A. Increase the Vitest timeout

Rejected. It would hide threshold flakiness without separating the two claims. A green result would still not prove real Browser performance.

### B. Optimize or virtualize the accepted production React surface

Rejected for this Slice. There is no fresh Browser evidence of a product regression, and production UI changes would reopen a different rollback and acceptance unit.

### C. Layer deterministic and Browser evidence

Selected. Keep algorithmic complexity and React update isolation deterministic and fast, while the existing Chromium runner owns the 120-page DOM completeness probe and records measurement-only timing evidence.

## Architecture

Acceptance coverage is divided into four explicit layers:

1. **Pure validation contract**: create 120 slide contracts and 120 saved marks, call the authoritative initial mark-set validator directly, and prove that slide targets are indexed without `Array.find` scans.
2. **React update isolation**: mount a small representative contract, open a composer, edit its comment, and prove that the saved projected mark set is not re-read. This protects the component memoization/update boundary without using a wall-clock performance assertion.
3. **Local Chromium long-review probe**: open 10/24/60-page content reviews and a 120-slide visual review, verify completeness, final-page reachability, mixed material behavior, overflow, and console state, then record navigation-to-ready and final-page-access durations plus the actual Node, browser, platform, architecture, viewport, and sample identity.
4. **Formal host/release acceptance**: remains outside this Slice. The report must keep `proofEligible=false` and all real-host/Gate claims false.

No universal millisecond budget is introduced because the authoritative product baselines do not define one. Timing is published as `measurement-only`; a future approved performance budget can consume repeated measurements with a controlled host and percentile rule.

## Data contract

Each long-review result records:

```json
{
  "reviewType": "visual",
  "count": 120,
  "viewport": { "width": 1000, "height": 900 },
  "navigationToReadyMs": 0,
  "finalObjectAccessMs": 0,
  "measurementMode": "local-playwright-measurement-only",
  "complete": true,
  "finalObjectPresent": true,
  "noHorizontalOverflow": true,
  "consoleErrorCount": 0
}
```

The run-level environment records Node version, Playwright Chromium version, OS platform/release, process architecture, run identity, and the existing local-preview disclaimer. Numeric durations must be finite and non-negative. Missing or malformed measurements fail report validation; timing alone never passes or fails user-perceived performance.

## Failure handling

- A pure validation or small React assertion failure is a deterministic source/test failure.
- Browser launch denial, missing bundled Playwright, or macOS sandbox denial is a `CapabilityGap`; no successful Browser claim or current report is published.
- Incomplete node count, missing final page, overflow, console error, or malformed measurement fails the local Browser acceptance run.
- The report is published atomically only after all checks complete.
- A previous successful report is not overwritten by a failed current run.
- The 120-slide JSDOM test timeout is not increased and production React is not changed in this Slice.

## Files

- Modify `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx` to separate pure 120-mark validation from small React composer update isolation.
- Modify `scripts/v22-ui-acceptance-evidence.mjs` to validate measurement-only long-review evidence and environment identity.
- Modify `scripts/run-v22-ui-acceptance.mjs` to collect and publish the long-review measurements.
- Modify `tests/v22-ui-acceptance-evidence.test.mjs` and `tests/v22-prototype-fidelity.test.mjs` to lock the evidence and runner contracts.
- Add the Slice implementation plan under `docs/superpowers/plans/`.

No production source, Runtime, MCP, content-review UI, visual-review UI, release, installer, or baseline requirement file is a target unless a test exposes a direct contradiction with this approved design.

## Verification and exit criteria

The Slice exits only when:

- the pure 120-slide/120-mark validation test passes without any slide `find` call;
- the small React composer test passes without re-reading the projected saved mark set;
- the previously flaky isolated test no longer depends on a 30-second full-DOM mount;
- evidence-helper and runner-contract tests pass;
- focused visual Widget tests, typecheck, build, Python, Node, and full Widget tests pass, with exact counts reported;
- the local Chromium acceptance run either passes and publishes measurement-only evidence, or is reported as an exact CapabilityGap without a false report;
- `git diff --check` is clean and only Slice 9 files changed;
- independent read-only review reports no Critical or Important finding.

Completion means implemented, locally verified, and independently reviewed on this feature branch. It does not mean merged, pushed, released, installed, host-verified, Gate-passed, or user-accepted.
