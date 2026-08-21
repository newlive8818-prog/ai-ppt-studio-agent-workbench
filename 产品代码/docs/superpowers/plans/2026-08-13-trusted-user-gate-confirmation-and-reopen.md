# Trusted User Gate Confirmation and G0 Reopen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This task is executed inline because the user did not request delegation. Do not commit or overwrite unrelated dirty-worktree changes.

**Goal:** Prevent a mission-confirmation message or any model-supplied reference from passing G0/G3/G4, bind each user checkpoint to the current review source, and make G0 reopen atomically invalidate all downstream current state.

**Architecture:** Node MCP resolves the authoritative current Gate context before every user confirmation. It accepts a reference only through an injected host verifier; otherwise it obtains a fresh host-native elicitation. Python remains the only business writer and validates the project, Gate, exact current source, challenge revision/identity, one-time confirmation identity, and current upstream lineage before an atomic commit. Kernel transactions gain explicit current-head removals and confirmation-consumption tracking so a G0 reopen can lock G1–G4 and remove downstream heads without deleting immutable artifacts.

**Tech Stack:** Python 3 standard library/unittest, Node.js ESM, MCP SDK elicitation, Zod, schema 3 immutable artifact kernel.

---

### Task 1: Lock the replay bug with failing Python and Node tests

**Files:**
- Create: `tests/test_v16_gate_confirmation.py`
- Modify: `tests/test_v16_content_acceptance.py`
- Modify: `tests/mcp-server.test.mjs`

- [ ] Add a Python test whose mission confirmation uses `chat://message/item-35`, publishes a G0 blueprint, then tries the same identity for G0; expect `GateBlockedError`, no revision change, and G0 still `user-reviewable`.
- [ ] Add Python tests for a stale source/challenge, reuse across checkpoints, and missing trusted action/message identity.
- [ ] Add a Node test proving a model-supplied message reference never reaches Python without a verifier and instead requires a new host-native confirmation.
- [ ] Run the focused tests and record RED failures caused by the existing prefix-only implementation.

### Task 2: Add authoritative Gate confirmation contexts and one-time consumption

**Files:**
- Create: `src/ai_ppt_studio/application/gate_confirmation.py`
- Modify: `src/ai_ppt_studio/kernel/state.py`
- Modify: `src/ai_ppt_studio/kernel/transactions.py`
- Modify: `src/ai_ppt_studio/application/content_service.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`

- [ ] Implement `GateConfirmationPolicy.context(gate)` for G0/G3/G4 with project ID, exact source/evidence refs, current revision, review summary, and deterministic challenge identity.
- [ ] Implement confirmation validation that requires exactly one trusted host action or verified user message, current source/challenge/revision, and an unused identity; also detect identities already stored in the current MissionConfirmation for backward compatibility.
- [ ] Persist confirmation consumption in the same kernel transaction as the confirmation artifact and Gate mutation.
- [ ] Bind G0 to current content acceptance/blueprint, G3 to current visual contract/G1/G2 evidence, and G4 to current build/package/chat receipt/PPTX hash.
- [ ] Run the focused Python tests to GREEN.

### Task 3: Require host verification or native elicitation in MCP

**Files:**
- Modify: `mcp/server.mjs`
- Modify: `tests/mcp-server.test.mjs`

- [ ] Make `confirm_ai_ppt_gate` first read `get-gate-confirmation-context` and reject an expected-revision mismatch before prompting.
- [ ] Pass a supplied reference only after the injected verifier validates project, Gate, current source, challenge, revision, author, timing, intent, and non-reuse context.
- [ ] Without a verifier, ignore model-supplied references and require a fresh host-native form confirmation; decline/cancel/unavailable must perform zero business writes.
- [ ] Forward the exact context and trusted identity to Python; make `userMessageRef` optional in the public schema.
- [ ] Run all MCP server tests to GREEN.

### Task 4: Make G0 reopen an atomic downstream invalidation

**Files:**
- Modify: `src/ai_ppt_studio/kernel/transactions.py`
- Modify: `src/ai_ppt_studio/application/content_service.py`
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `tests/test_v16_gate_confirmation.py`
- Modify: `tests/test_v16_bridge.py`

- [ ] Add transaction-level `artifact_removals` that records removed current heads in the event but never deletes artifact objects.
- [ ] Reopen G0 to `user-reviewable` when the current internally accepted content is still valid, otherwise `open`; lock G1–G4 in the same mutation.
- [ ] Remove current G0 confirmation plus all visual, anchor, visual-review, delivery, chat-delivery, downstream Gate, and visual mark heads; invalidate/remove the current downstream Agent task while preserving its immutable history.
- [ ] Route public `reopen_ai_ppt_scope(G0)` through this transaction and keep the existing G4 route.
- [ ] Assert one revision/event, locked downstream Gates, absent downstream current heads, retained artifact object files, and no active downstream task.

### Task 5: Add visual-write defense in depth and align contracts

**Files:**
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `tests/test_v16_visual_contracts.py`
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `tests/test_skill_workflow.py`

- [ ] Require a passed G0 confirmation bound to the current content blueprint at every visual write entry, not only Visual Brief.
- [ ] Assert design system, contracts, convergence, reviews, anchors, evidence, and published visual contract stay on the same frozen content lineage.
- [ ] State that one confirmation belongs to exactly one current checkpoint, MissionConfirmation never confirms a Gate, no single Agent turn crosses a later user Gate without a new host result, and unavailable confirmation preserves state.
- [ ] Run focused visual and Skill contract tests.

### Task 6: Full verification and real-project recovery

**Files:**
- Runtime project only after code verification: `/Users/defei/Documents/AI-PPT-Workspace/projects/mianyang-oa-pricing-leadership-brief-20260813`

- [ ] Run focused Python Gate/content/visual/bridge/recovery tests.
- [ ] Run `python3 -m unittest discover -s tests` and `npm test`, read full exit results, and inspect `git diff --check` plus the scoped diff.
- [ ] Invoke the verified source runtime against the real project with `reopen-scope(G0)` and its current expected revision, using the authoritative transaction rather than editing JSON.
- [ ] Verify the real project has G0 `user-reviewable`, G1–G4 `locked`, no current visual/anchor/delivery heads, no active downstream task, one new recovery event, and unchanged historical artifact objects.
- [ ] Report exact test counts and distinguish code repair from real-project recovery. Do not create Word, commit, install, or publish unless separately requested.

## Self-review

- Spec coverage: mission-to-G0 replay, fabricated/non-user/stale references, cross-Gate reuse, source-version binding, long-turn crossing, G0 atomic rollback, active-task invalidation, historical preservation, visual defense, G3/G4 symmetry, and real-project recovery are mapped above.
- Placeholder scan: no deferred implementation placeholder remains; every task has concrete files, behavior, and verification.
- Type consistency: MCP camelCase context maps to Python snake_case; `source_version`, `challenge_id`, and `challenge_revision` have one meaning across all three user Gates.
- Dirty-worktree safety: all edits are scoped; no reset, checkout, cleanup, automatic commit, or baseline rewrite is authorized.
