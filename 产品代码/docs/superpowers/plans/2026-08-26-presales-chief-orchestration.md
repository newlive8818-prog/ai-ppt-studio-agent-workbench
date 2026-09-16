# Presales Chief Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one derived chief state machine that advances a trusted Mission through the four C0 content objects or returns an exact governed stop.

**Architecture:** `PresalesChiefOrchestrator` derives state from `MissionReadinessPolicy`, `PresalesContentService.get_current_content_chain()`, and current failed-gate refs. AI supplies semantic payloads; Python selects the only legal step, delegates persistence to C0, derives repair count from Blueprint history, and reports consultant absence without fake execution.

**Tech Stack:** Python 3.12+, `unittest`, schema 3 `ProjectKernel`, C0 content service/contracts, Mission readiness, immutable artifacts.

---

## File map

- Create `src/ai_ppt_studio/application/presales_chief_orchestrator.py` for projection, one-step advance, bounded repair, and consultant capability.
- Create `tests/test_v22_presales_chief_orchestrator.py` for state, three modes, authority, replay, zero-write, repair, and capability gaps.
- Modify `tests/test_v22_presales_chief.py` only if a trusted Mission fixture must be extracted.
- Do not modify MCP, Widget/UI, Review Bridge, content-review services, hard-gate evaluators, visual, delivery, or release files.

### Task 1: Derive one closed production state

**Files:**
- Create: `tests/test_v22_presales_chief_orchestrator.py`
- Create: `src/ai_ppt_studio/application/presales_chief_orchestrator.py`

- [ ] Write failing tests for exact projection keys and states `mission-not-ready`, `reconstructing-evidence`, `building-decision-context`, `diagnosing-problem-solution-fit`, `drafting-reading-deck`, and `ready-for-independent-gates`.
- [ ] Assert each incomplete state exposes only its exact C0 next operation and that a complete state claims no Gate, review, host, AI, visual, PPTX, delivery, or release result.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_presales_chief_orchestrator -v
```

Expected RED: the orchestrator module does not exist.

- [ ] Implement `NORMAL_STEPS` and `inspect()` using `MissionReadinessPolicy.require_ready()` plus `PresalesContentService.get_current_content_chain()`. Convert Mission readiness exceptions to closed stop objects; propagate inconsistent-chain failure as a truthful stop.
- [ ] Re-run the Task 1 command. Expected GREEN.

### Task 2: Advance exactly one trusted step

**Files:**
- Modify: `tests/test_v22_presales_chief_orchestrator.py`
- Modify: `src/ai_ppt_studio/application/presales_chief_orchestrator.py`

- [ ] Add failing tests that traverse all four steps for `material-backed`, `mixed-evidence`, and `proposal-led` without supplying an operation name.
- [ ] After each call assert the created ref kind, one revision advance, exact next state, and consistent C0 chain.
- [ ] Add zero-write tests for absent Mission, wrong mode, stale revision, later-object payload, and advancing after completion.
- [ ] Run orchestrator tests. Expected RED: `advance()` is absent.
- [ ] Implement exact dispatch:

```python
BUILDERS = {
    "build-presales-evidence-book": "build_evidence_book",
    "build-customer-decision-context": "build_decision_context",
    "build-problem-solution-fit": "build_problem_solution_fit",
    "build-reading-deck-blueprint": "build_reading_deck_blueprint",
}
```

- [ ] On the evidence step require `MissionReadinessPolicy.v22_material_mode(has_evidence_gaps=bool(payload["evidence_gaps"]))` to equal the payload mode. Delegate all other validation/replay to C0.
- [ ] Return exactly `operation`, `created_ref`, and a fresh `projection`; run orchestrator plus unchanged `tests.test_v22_presales_chief`. Expected GREEN.

### Task 3: Bound repair without implementing C2 reviewers

**Files:**
- Modify: `tests/test_v22_presales_chief_orchestrator.py`
- Modify: `src/ai_ppt_studio/application/presales_chief_orchestrator.py`

- [ ] Build a complete chain, seed a current failed `content-hard-gate-record`, and add RED tests for `chief-repair`, current `failure_refs`, and attempts remaining.
- [ ] Test attempts 0-2 with a new repair-history entry bound to the current failure. At attempt 3 require `governed-stop`, `REPAIR_ATTEMPTS_EXHAUSTED`, and zero writes.
- [ ] Reject repair without a failed gate, missing/repeated attempt identity, history not binding a current failure, and any attempt to write a gate result.
- [ ] Implement `MAX_REPAIR_ATTEMPTS = 3` and current failed slots `content/gate/evidence` and `content/gate/presales-reading`; derive count from current Blueprint history and delegate only to `PresalesContentService.repair_reading_deck_blueprint()`.
- [ ] Run orchestrator, C0 service, and existing content repair-loop tests. Expected GREEN with no Gate passed mutation.

### Task 4: Report consultant capability truthfully

**Files:**
- Modify: `tests/test_v22_presales_chief_orchestrator.py`
- Modify: `src/ai_ppt_studio/application/presales_chief_orchestrator.py`

- [ ] Add RED tests proving consultants never appear in the fixed path and a valid request returns `CONSULTANT_RUNTIME_UNAVAILABLE`, wildcard risk role, `write_authority=none`, and zero writes.
- [ ] Reject invalid risk areas, blank or over-500-character questions, duplicate refs, non-current refs, and malformed refs with zero writes.
- [ ] Normalize risk area to ASCII `[a-z0-9-]`, resolve unique current target refs, and return the closed unavailable result without AgentTask/artifact/event creation.
- [ ] Run orchestrator tests. Expected GREEN.

### Task 5: Verify, commit, review, and preserve

**Files:**
- Verify exact C1 scope only.

- [ ] Run focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_presales_chief_orchestrator \
  tests.test_v22_presales_chief \
  tests.test_v22_content_domain_service \
  tests.test_v22_content_repair_loop \
  tests.test_context_compiler_governance \
  tests.test_role_registry -v
```

- [ ] Run `npm run typecheck`, `npm run build`, `npm run test:node`, `npm run test:widget`, and `npm run test:python`; require every command to exit 0.
- [ ] Run `git diff --check`, `git status --short`, `git diff --name-only a2dba38a449ab86ad7b9a3c8a13a6bc5b75c277a...HEAD`, and `git diff --name-only`. Reject any MCP/UI/Review Bridge/content-review/hard-gate evaluator/visual/delivery/release edit.
- [ ] Stage only the new orchestrator and named test with exact `git add` paths; never use `git add .`.
- [ ] Commit implementation as `feat: orchestrate presales chief production`.
- [ ] Repeat focused/full verification post-commit and require a clean worktree.
- [ ] Request independent read-only review against the spec and plan. Fix Critical/Important items through a new RED test and additional commit; never amend.
- [ ] Preserve branch `codex/slice-presales-chief-orchestration-20260826` and its worktree. Do not merge, push, release, install, or claim user acceptance.
