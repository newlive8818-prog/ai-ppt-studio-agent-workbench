# AI PPT Studio Cross-Project Experience Evolution Implementation Plan

> **Execution:** Use `superpowers:executing-plans` task-by-task. Every runtime behavior follows red-green-refactor TDD.

**Goal:** Implement a local, versioned, cross-project personal experience store that records applications and outcomes, recommends bounded experience in later projects, and supports evidence-based promotion, demotion, disablement, and rollback.

**Architecture:** Add a standard-library Python `ExperienceStore` below the managed runtime root. Keep project feedback as source evidence, personal experience as a separate persistent data plane, and stable Skill behavior release-managed. Expose the system through JSON-only CLI commands and document when AI PPT Studio must recommend, apply, and evaluate experience.

**Tech Stack:** Python 3.11+ standard library, JSON/JSONL, `unittest`, existing PathPolicy and atomic JSON helpers.

---

### Task 1: Define the experience contract and persistence behavior

**Files:**

- Create: `src/ai_ppt_studio/experience_models.py`
- Create: `src/ai_ppt_studio/experience_store.py`
- Test: `tests/test_experience_store.py`

- [ ] Write failing tests for candidate creation, immutable versions, runtime isolation, listing, and retrieval.
- [ ] Run `python3 -m unittest tests/test_experience_store.py -v` and confirm failure.
- [ ] Implement validated models, directory initialization, index persistence, immutable version files, and latest pointers.
- [ ] Run focused tests and refactor without changing behavior.

### Task 2: Implement matching, application records, and evaluation governance

**Files:**

- Modify: `src/ai_ppt_studio/experience_models.py`
- Modify: `src/ai_ppt_studio/experience_store.py`
- Modify: `tests/test_experience_store.py`

- [ ] Write failing tests for cross-project recommendation and match reasons.
- [ ] Write failing tests for append-only applications and evaluations.
- [ ] Write failing tests for two-project promotion, failure-based demotion, disablement, manual transitions, and rollback.
- [ ] Implement deterministic matching, transparent confidence, governance decisions, and new-version state updates.
- [ ] Run focused tests.

### Task 3: Expose a machine-readable CLI and truthful preflight

**Files:**

- Modify: `src/ai_ppt_studio/cli.py`
- Create: `tests/test_experience_cli.py`
- Modify: `tests/test_skill_bundle.py`

- [ ] Write failing end-to-end CLI tests for create/list/recommend/apply/evaluate/set-level/rollback.
- [ ] Replace the hardcoded preflight experience flag with an `ExperienceStore.capability_status()` probe and evidence.
- [ ] Implement CLI parsing, JSON file loading, dispatch, and structured errors.
- [ ] Run CLI and bundle tests.

### Task 4: Update the portable Skill contract

**Files:**

- Modify: `skill/ai-ppt-studio/SKILL.md`
- Modify: `skill/ai-ppt-studio/references/experience-evolution.md`
- Modify: `skill/ai-ppt-studio/assets/project-schema.json`
- Modify: version metadata if present
- Test: `tests/test_skill_workflow.py`

- [ ] Add workflow tests requiring recommend-before-relevant-work and evaluate-after-feedback guidance.
- [ ] Document exact commands, storage boundary, promotion rules, privacy, and proof loop.
- [ ] Build and validate the portable bundle.

### Task 5: Migrate Huaxi feedback and demonstrate cross-project learning

**Runtime writes only:**

- Create three candidate experiences from Huaxi feedback: alignment mechanics, case problem/build/outcome narrative, and real-evidence case composition.
- Use sanitized mechanisms with private local source references.
- Recommend the candidates in two separate target-project contexts.
- Record applications and accepted outcomes in a temporary verification runtime so automatic promotion is demonstrated without falsifying real customer outcomes.
- Keep the real Huaxi candidates at `candidate` until actual later-project outcomes exist.

### Task 6: Complete verification and installation

- [ ] Run the focused experience tests.
- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Validate the built Skill with the official validator.
- [ ] Install the updated Skill safely.
- [ ] Run installed `preflight`, list the real Huaxi candidates, and confirm source/install/upstream roots remain unmodified except the authorized Skill installation.
- [ ] Inspect git diff and status; commit implementation on the feature branch.
