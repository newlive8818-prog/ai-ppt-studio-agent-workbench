# Content Hard Gates and Repair Loop Implementation Plan

> **Execution:** Follow TDD task by task in this C2 linked worktree only.

**Goal:** Make two isolated, non-compensatory current-source content hard gates
the only path from a C1 Blueprint to C3 review readiness.

**Parent / rollback point:**
`a923c9735f0610cc36d53ada4fa88ca61f574f3c`.

## File map

- Modify `src/ai_ppt_studio/domains/content/contracts.py` for closed gate rows,
  repair requirements, identities, and timestamps.
- Modify `src/ai_ppt_studio/application/content_hard_gate_service.py` for the
  derived projection, current-chain checks, isolated review execution, replay,
  source/hash binding, gate ordering, and acceptance.
- Modify `tests/test_v22_content_hard_gates.py` for the closed domain contract.
- Create `tests/test_v22_content_hard_gate_service.py` for authority, projection,
  replay, stale source, repair/rerun, and acceptance.
- Modify only shared test fixtures/call sites that must supply the new explicit
  semantic check set; do not change their product assertions.
- Do not modify MCP catalog, Widget/UI, Review Bridge, content-review services,
  visual, PPTX, delivery, release, installation, or experience production code.

## Task 1: Close the record contract

- Add RED tests for unknown root/check/repair fields, hash/timestamp format,
  duplicate/soft checks, invalid applicability/result combinations, wrong
  evidence target shape, mismatched repair requirements, and false independent
  evidence.
- Implement exact normalization and derived `overall_result` without score,
  vote, or compensation.
- Keep archival `independent-agent` validation but reject its runtime creation
  in Task 3.
- Run `tests.test_v22_content_hard_gates`; require GREEN.

## Task 2: Derive the C2 state and current-source authority

- Add RED service tests for exact projection keys and states:
  `content-not-ready`, `evidence-gate-review`, `chief-repair`,
  `presales-reading-gate-review`, `content-user-reviewable`, and governed stop.
- Revalidate all four current C0 heads and Blueprint lineage.
- Require gate type, source version, and input hash to match the exact current
  Blueprint; reject wrong-kind, malformed, historical, and same-version stale
  refs before writes.
- Run C2 service plus C0/C1 focused tests; require GREEN.

## Task 3: Execute isolated reviewers truthfully

- Add RED tests for the complete gate-specific semantic check ids, exact current
  Blueprint evidence refs, deterministic check ids, reviewer role, and Context
  Pack isolation.
- Reject empty/incomplete/duplicate/foreign semantic sets and every runtime
  `independent-agent` claim with zero writes.
- Compile the real bounded Context Pack for `isolated-review-task`; do not create
  or claim an independent AgentTask/output.
- Enforce reviewer write authority in both direct and committed-output paths.
- Run context compiler, role registry, and C2 focused tests; require GREEN.

## Task 4: Add semantic replay and non-compensatory ordering

- Add RED tests for exact replay, changed semantic results, cross-gate command
  reuse, new stale revision, lost receipt, and zero-write rejection.
- Add operation/request fingerprints and return the original artifact ref from
  the command receipt, not whichever gate head is current later.
- Require a current passed evidence gate with exact current Blueprint hash before
  the reading gate. Any applicable hard failure blocks progression.
- Run C2, kernel transaction, and legacy acceptance regressions; require GREEN.

## Task 5: Prove repair, rerun, and exact acceptance

- Add RED integration tests for evidence failure, reading failure, structured
  repair requirements, C1 chief repair, gate invalidation, required rerun, and
  the three-attempt governed stop inherited from C1.
- Create `content/acceptance` only after both current passed records bind the
  exact current Blueprint hash/source.
- Prove historical/passed-but-stale records and legacy acceptance cannot open C3
  or G0.
- Run C0, C1, C2, content acceptance, gate evaluator, and G0 regressions.

## Task 6: Verify, review, and preserve

- Run the C2 focused suite selected above.
- Run full Python tests. Run Node/Widget/typecheck/build only if a shared public
  contract or fixture makes them relevant; otherwise still run the repository
  standard full commands before completion for integration confidence.
- Run `git diff --check`, exact parent diff, staged diff, and clean status.
- Stage only the named C2 files and explicitly required test fixture files;
  never use `git add .`.
- Commit implementation normally; never amend.
- Request independent read-only review. Fix Critical/Important findings with new
  RED tests and additional commits.
- Preserve this branch/worktree. Do not merge, push, release, install, or claim
  G0/user acceptance.
