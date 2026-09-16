# Host-native Mission Confirmation Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This plan is executed inline because the user did not request delegation. Do not create a Git commit before the v1.6 ledger reaches 104/104.

**Goal:** Remove the production MissionConfirmation deadlock by using MCP host-native form elicitation as the trusted confirmation fallback while preserving explicit-user-action, current-revision, material-mode, and proposal-only governance.

**Architecture:** Keep Python as the only business writer and keep existing host-verifier adapters valid. The Node MCP layer first accepts a verified sidebar/message reference when a real adapter exists; otherwise it checks the connected MCP client's elicitation capability, asks the host to display a mission-bound confirmation summary, and calls Python only when the host returns `action=accept` with `confirmed=true`. Chat words such as `OK / 确认 / 采纳 / 继续` remain agent-level intent triggers and are never persisted as evidence.

**Tech Stack:** Node.js ESM, `@modelcontextprotocol/sdk` McpServer elicitation API, Zod, Node test runner, Python schema 3 runtime, unittest, deterministic plugin release scripts.

## Execution status — 2026-08-13

- Tasks 1–6 are implemented and freshly verified: Python 136/136, Node 32/32, Widget 38/38, including native accept/decline/cancel/false/unavailable and verifier compatibility paths.
- Task 7 release, verification, install, cache probe, and evidence documentation are complete for `0.4.0+codex.20260813010800`; the installed probe exposes 17 data-only tools, zero chat UI templates, host-native fallback, and the complete mission summary.
- The real Codex host dialog remains intentionally unverified in this task because its MCP tool schema was loaded before the corrected plugin. It must be tested in a new task and cannot be replaced by automation evidence.
- The real revision-51 project and anchor PPTX remain unchanged; the acceptance ledger remains 37/104, and no commit is authorized before 104/104.

---

## File map

- Modify `mcp/server.mjs`: add one bounded host-confirmation helper and route `confirm_ai_ppt_mission` through verifier-or-elicitation without weakening Python validation.
- Modify `tests/mcp-server.test.mjs`: cover production startup behavior, accepted native confirmation, decline/cancel, unavailable capability, and verifier compatibility.
- Modify `skills/ai-ppt-studio/SKILL.md`: teach the agent that the approved confirmation words trigger the tool only in a current mission-confirmation context.
- Modify `skills/ai-ppt-studio/references/runtime-workflow.md`: document the verifier/native-confirmation fallback and stable failure behavior.
- Modify `skills/ai-ppt-studio/references/native-workbench.md`: align sidebar/chat behavior and prohibit treating intent text as evidence.
- Modify `tests/test_skill_workflow.py`: prevent contract drift for confirmation intent and host-native confirmation.
- Modify applicable baseline status text only after implementation and verification evidence exists.
- Rebuild and reinstall the plugin with the existing deterministic release path; do not modify PPTX or the revision-51/51 real project while validating the confirmation integration.

### Task 1: Reproduce the production startup deadlock

- [ ] Add a Node integration test that creates `createAiPptMcpServer()` without an injected `confirmationVerifier`, connects a client declaring form elicitation, handles `elicitation/create`, calls `confirm_ai_ppt_mission`, and expects the Python bridge to receive exactly one `confirm-mission` request after host acceptance.
- [ ] Assert the elicitation message contains the current mission identity, audience/action summary supplied to the tool, material mode, and proposal-only warning for `no-materials-confirmed`.
- [ ] Run only this test and verify RED: Python is not reached because current production code returns `MISSION_NOT_CONFIRMED` when `confirmationVerifier` is absent.

Run:

```bash
node --test --test-name-pattern='production startup uses host-native mission confirmation' tests/mcp-server.test.mjs
```

Expected before implementation: FAIL because `confirm-mission` is never forwarded.

### Task 2: Implement accepted host-native confirmation

- [ ] Add optional `missionSummary` fields to the tool input for the already displayed current card: `topic`, `primaryAudience`, `desiredJudgmentOrAction`, and `materialSummary`. These values are presentation-only and never replace the authoritative `missionDraftRef` or Python checks.
- [ ] Add `requestHostMissionConfirmation(server, input)` that checks `server.server.getClientCapabilities()?.elicitation`, calls `server.server.elicitInput()` with a boolean `confirmed` field and a mission-bound message, and returns a newly generated `host-elicitation://<opaque-id>` action identity only for `action=accept` plus `content.confirmed===true`.
- [ ] Preserve the injected `confirmationVerifier` route for a real sidebar action or real message verifier. If it verifies, forward its original reference unchanged; if no verifier exists, use native elicitation.
- [ ] Forward the host-generated action identity to Python as `user_action_ref`; never forward `OK`, `确认`, `采纳`, `继续`, or other intent text as a reference.
- [ ] Run the focused test and verify GREEN.

### Task 3: Reject decline, cancel, and unsupported hosts without writes

- [ ] Add tests for host `decline` and `cancel`; assert `HOST_CONFIRMATION_DECLINED`, zero Python calls, and unchanged project revision/state.
- [ ] Add a test for a client without elicitation capability; assert `HOST_CONFIRMATION_UNAVAILABLE`, zero Python calls, and a message that does not request more materials or recommend bypassing AI PPT Studio.
- [ ] Add a test for `action=accept` with `confirmed=false`; treat it as declined and make no write.
- [ ] Implement the minimal stable error mapping and run all mission-confirmation Node tests.

Run:

```bash
node --test --test-name-pattern='mission confirmation|host-native mission confirmation' tests/mcp-server.test.mjs
```

Expected: all matching tests pass.

### Task 4: Preserve explicit verifier compatibility and security boundaries

- [ ] Extend the existing verifier test to prove a verified host message bypasses elicitation and retains its exact `userMessageRef`.
- [ ] Add a verifier-rejection test proving a present verifier that rejects a supplied reference does not silently fall back and reinterpret the same untrusted string as native confirmation.
- [ ] Add a repeat-call/current-revision assertion: each confirmation attempt elicits separately and Python still owns revision conflict detection.
- [ ] Run the complete MCP server test file.

Run:

```bash
node --test tests/mcp-server.test.mjs
```

Expected: PASS with no skipped mission-confirmation coverage.

### Task 5: Align Skill wording and contract tests

- [ ] Update the Skill and runtime/native-workbench references: after showing a current confirmable task card, the agent may treat `OK / 确认 / 采纳 / 继续` and clear equivalents as confirmation intent and call `confirm_ai_ppt_mission`; the MCP host must still ask for native confirmation when there is no verified message/sidebar reference.
- [ ] State that ordinary conversation, unrelated adoption, or a non-current task card must not trigger mission confirmation.
- [ ] State that native confirmation decline/unavailability preserves the task and asks for retry, never for extra material and never for a Presentations bypass.
- [ ] Add Python contract assertions for all four intent words, host-native confirmation, proposal-only, and the prohibition on storing intent text as evidence.
- [ ] Run Skill workflow/package tests.

Run:

```bash
python3 -m unittest tests.test_skill_workflow tests.test_skill_bundle tests.test_package_shape
```

Expected: PASS.

### Task 6: Regression verification

- [ ] Run Python mission readiness and proposal-only tests to prove no-material content still works only after MissionConfirmation.
- [ ] Run the complete Node and Python test suites required by the package.
- [ ] Rebuild the Widget/Skill/release artifacts through existing scripts and verify the release contains the corrected server and Skill hashes.
- [ ] Confirm no PPTX, revision-51/51 project data, target-render evidence, or 104-ledger acceptance status was fabricated or changed by this fix.

Focused commands:

```bash
python3 -m unittest tests.test_v16_mission_readiness tests.test_v16_proposal_only
npm test
```

Expected: all tests pass; the ledger remains below 104/104 until real-host and four-target evidence is obtained.

### Task 7: Deterministic install and live capability probe

- [ ] Build a new timestamped deterministic plugin release using `scripts/build-plugin-release.mjs`.
- [ ] Verify the release using `scripts/verify-plugin-release.mjs`.
- [ ] Install it using `scripts/install-plugin.mjs` and the approved local plugin target.
- [ ] Start a fresh MCP probe and verify the installed `confirm_ai_ppt_mission` schema exposes mission summary inputs and no chat UI template.
- [ ] If the current Codex host advertises form elicitation, execute a non-destructive confirmation fixture/project check; if it does not, record `HOST_CONFIRMATION_UNAVAILABLE` honestly and do not claim real-host acceptance.
- [ ] Update implementation-status documentation and evidence only for checks actually observed. Do not commit before 104/104.

## Self-review

- Spec coverage: accepted native confirmation, four approved intent words, false-positive prevention, decline/cancel, capability absence, verifier compatibility, proposal-only, installation, and non-fabrication are each mapped to a task.
- Placeholder scan: no TBD/TODO or deferred implementation instruction remains.
- Type consistency: MCP camelCase inputs map to Python snake_case request fields; trusted native results become `user_action_ref`, while verified chat references remain `user_message_ref`.
- Scope: no sidebar implementation, Browser implementation, PPTX change, real-project rewrite, Gate confirmation change, or unrelated refactor is included.
