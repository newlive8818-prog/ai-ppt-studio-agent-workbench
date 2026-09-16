# v1.6 Slice 05 Experience Intake and Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the schema 3 experience chain that separates project execution from learning, extracts three distinct learning result types, compiles isolated role-specific slices, records matched cross-project outcomes, supports governed personal-experience evolution, and prevents runtime mutation of stable capabilities.

**Architecture:** Project evidence remains immutable in the existing `ProjectKernel`; `ExperienceService` writes only content-addressed intake, learning result, application, evaluation, evolution, and slice artifacts. Personal promotion is never triggered by a raw feedback or a fixed hard-coded threshold: an explicit versioned evolution policy and governance decision must authorize a transition. Stable Prompt, role contract, and scenario-pack releases stop at a runtime release-candidate artifact and require an external version-governance pipeline to publish.

**Tech Stack:** Python standard library, `unittest`, schema 3 `ProjectKernel`, existing `RoleRegistry`, existing Node MCP thin adapter.

---

## File map

- Create `src/ai_ppt_studio/domains/experience/__init__.py`: public experience contract exports.
- Create `src/ai_ppt_studio/domains/experience/contracts.py`: Experience Intake, three learning result, qualification, application/evaluation, evolution-policy, transition, release-candidate, and role-slice validators.
- Create `src/ai_ppt_studio/application/experience_service.py`: revision-safe schema 3 commands and lineage checks.
- Modify `src/ai_ppt_studio/context_compiler.py`: accept one exact role-specific experience slice reference and use schema 3 reference syntax.
- Modify `src/ai_ppt_studio/application/visual_service.py`: route the existing generic `commit-artifact` operation for `kind=experience`.
- Modify `src/ai_ppt_studio/application/v16_bridge.py`: expose compact experience intake reads through the current schema 3 bridge without moving rules into Node.
- Modify `mcp/server.mjs`: add `experience` to the existing `commit_ai_ppt_artifact` kind enum; do not add a v16-specific tool name.
- Create `tests/v16_experience_fixtures.py`: simulated contract fixtures labeled non-real.
- Create `tests/test_v16_experience_intake.py`: intake and three result contracts.
- Create `tests/test_v16_experience_slices.py`: qualification ordering and role isolation.
- Create `tests/test_v16_experience_evolution.py`: match, evaluation, promotion, demotion, disable, rollback, and stable-release isolation.
- Create `tests/test_v16_experience_bridge.py`: existing public bridge routing and compact projection.

### Task 1: Experience Intake and three independent learning results

**Files:**
- Create: `src/ai_ppt_studio/domains/experience/__init__.py`
- Create: `src/ai_ppt_studio/domains/experience/contracts.py`
- Create: `src/ai_ppt_studio/application/experience_service.py`
- Create: `tests/v16_experience_fixtures.py`
- Create: `tests/test_v16_experience_intake.py`

- [x] **Step 1: Write failing intake tests**

Exercise this API and reject a missing source version, unresolved source/evidence reference, unsupported source type, missing privacy boundary, or attempt to set `learning_status=personal|stable` at intake time:

```python
intake_ref = experience.register_intake(
    "intake-preferred-example",
    revision,
    {
        "intake_id": "intake-preferred-example",
        "source_type": "preferred-example",
        "source_project_id": project_id,
        "source_version": "preferred-example-v1",
        "source_refs": [example_ref],
        "target_refs": [visual_contract_ref],
        "evidence_refs": [analysis_ref],
        "privacy_boundary": "sanitized-no-client-identifiers",
        "user_label": "用户明确优选",
        "execution_status": "source-registered",
        "learning_status": "intake-only",
    },
)
```

Supported source types are exactly `governed-feedback`, `preferred-example`, `reference-example`, `accepted-delivery`, `rejected-delivery`, `internal-review-failure`, and `engineering-degradation`. Persist each immutable intake at `experience/intake/<intake_id>` and keep project execution status separate from `learning_status`.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_experience_intake -v`

Expected: FAIL because `ExperienceService` and experience contracts do not exist.

- [x] **Step 3: Add failing result-type tests**

Require one intake to produce zero or more separately addressable results through:

```python
preference_ref = experience.register_learning_result(
    "preference-result",
    revision,
    {
        "result_type": "preference-signal",
        "result_id": "pref-reading-density",
        "intake_ref": intake_ref,
        "source_refs": [example_ref],
        "positive_or_negative": "positive",
        "preference_statement": "在合格方案中优先选择阅读路径更清晰的页面",
        "scope": "slide-family",
        "conditions": ["reading-first", "executive-audience"],
        "counterexamples": ["不允许牺牲证据完整性"],
        "confidence_inputs": [analysis_ref],
        "version": 1,
    },
)
```

`professional-mechanism-candidate` additionally requires mechanism, scenes, audiences, slide tasks, conditions, evidence, counterexamples, failure conditions, and sanitized privacy boundary. `anti-pattern-candidate` requires pattern, symptoms, root causes, scopes, negative evidence, repair mechanisms, and exceptions. Reject copying a whole case as one rule, customer-identifying content, numeric score fields, or a result that claims `personal`/`stable` status.

- [x] **Step 4: Implement and run GREEN**

Implement `validate_experience_intake`, `validate_preference_signal`, `validate_professional_mechanism_candidate`, `validate_anti_pattern_candidate`, plus `ExperienceService.register_intake` and `register_learning_result`. Resolve every formal reference, require the current intake head, and persist slots at `experience/result/<result_type>/<result_id>`.

Run: `python3 -m unittest tests.test_v16_experience_intake tests.test_v16_feedback_governance -v`

Expected: PASS; a raw feedback head alone cannot create a learning result and no Gate changes.

### Task 2: Professional qualification before preference and isolated role slices

**Files:**
- Modify: `src/ai_ppt_studio/domains/experience/contracts.py`
- Modify: `src/ai_ppt_studio/application/experience_service.py`
- Modify: `src/ai_ppt_studio/context_compiler.py`
- Create: `tests/test_v16_experience_slices.py`

- [x] **Step 1: Write failing qualification tests**

Register an option qualification artifact where every option has binary `fact_result`, `content_result`, `aesthetic_result`, and `engineering_result`. Assert any failed or missing applicable hard gate rejects preference selection; score, weight, average, vote, and conditional-pass fields are forbidden.

```python
selection_ref = experience.register_qualified_selection(
    "qualified-selection",
    revision,
    {
        "option_refs": [option_a_ref, option_b_ref],
        "qualification_results": [
            {
                "option_ref": option_a_ref,
                "fact_result": "passed",
                "content_result": "passed",
                "aesthetic_result": "passed",
                "engineering_result": "passed",
            },
            {
                "option_ref": option_b_ref,
                "fact_result": "passed",
                "content_result": "passed",
                "aesthetic_result": "passed",
                "engineering_result": "passed",
            },
        ],
        "preference_signal_refs": [preference_ref],
        "selected_option_ref": option_b_ref,
        "selection_reason": "两个方案均合格后按已声明偏好择优",
    },
)
```

- [x] **Step 2: Run qualification RED, implement, and run GREEN**

Run the new test and observe the missing API. Implement `validate_qualified_selection` and `ExperienceService.register_qualified_selection`; resolve all option and preference refs and store `experience/qualified-selection` as `qualified-experience-selection`.

Run: `python3 -m unittest tests.test_v16_experience_slices.V16ExperienceSliceTests.test_preference_can_rank_only_fully_qualified_options -v`

Expected: PASS.

- [x] **Step 3: Write failing role-slice tests**

Compile two slices from the same current result heads:

```python
producer_ref = experience.compile_role_slice(
    "producer-slice",
    revision,
    role_id="deck-designer",
    task_type="deliberate-design",
    target_context={
        "scene": "presales",
        "audience": "executive",
        "slide_task": "solution-overview",
        "conditions": ["reading-first", "strict-B"],
    },
    experience_version_refs=[mechanism_ref, preference_ref],
)

reviewer_ref = experience.compile_role_slice(
    "reviewer-slice",
    revision,
    role_id="visual-aesthetic-reviewer",
    task_type="review-aesthetic",
    target_context={...},
    experience_version_refs=[anti_pattern_ref, preference_ref],
)
```

Assert the producer slice cannot include raw feedback, review notes, or an anti-pattern-only ref outside its role contract; the reviewer slice cannot include producer self-evaluation and cannot receive a result type outside `RoleRegistry.experience_access`. Both slices must expose source, version, scope, match reasons, application outcomes, excluded refs, compiled time, and project revision.

- [x] **Step 4: Implement role slices and Context Compiler binding**

Implement `validate_role_specific_slice` and `ExperienceService.compile_role_slice`. Update `ContextCompiler.compile_role_task(..., experience_slice_ref="artifact://role-specific-experience-slice/<sha>")` so the experience layer contains the exact slice ref and schema 3 reference format; it must not inline raw intake or evaluation notes.

Run: `python3 -m unittest tests.test_v16_experience_slices tests.test_context_compiler_governance -v`

Expected: PASS with distinct producer/reviewer slices.

### Task 3: Matched application and professional/user evaluation

**Files:**
- Modify: `src/ai_ppt_studio/domains/experience/contracts.py`
- Modify: `src/ai_ppt_studio/application/experience_service.py`
- Test: `tests/test_v16_experience_evolution.py`

- [x] **Step 1: Write failing application tests**

Create a personal-experience candidate from a current mechanism or anti-pattern result, then record an application binding the exact candidate version and context. Reject a scene, audience, slide-task, or condition mismatch before the application is considered valid.

```python
application_ref = experience.record_application(
    "apply-candidate",
    revision,
    {
        "candidate_ref": candidate_ref,
        "application_project_id": "real-project-b",
        "target_context": {
            "scene": "presales",
            "audience": "executive",
            "slide_task": "solution-overview",
            "conditions": ["reading-first", "strict-B"],
        },
        "match_reasons": ["scene", "audience", "slide-task", "conditions"],
        "match_result": "matched",
        "runtime_evidence_ref": runtime_evidence_ref,
    },
)
```

- [x] **Step 2: Run application RED and implement GREEN**

Implement `validate_experience_candidate`, `validate_experience_application`, `ExperienceService.register_candidate`, and `record_application`. Store current candidates at `experience/candidate/<candidate_id>` and applications at `experience/application/<application_id>`.

Run the focused application test; expected PASS and mismatches never enter promotion statistics.

- [x] **Step 3: Write failing evaluation tests**

Require an exact current matched application, non-empty professional review refs, binary review pass, explicit user outcome, evidence refs, and application result. Only `professional_result=passed`, `user_outcome=accepted`, and `application_result=success` can become accepted success evidence. Simulation-only or wrong-context evidence must remain ineligible.

- [x] **Step 4: Implement and run GREEN**

Implement `validate_experience_evaluation` and `ExperienceService.evaluate_application`; persist `experience/evaluation/<application_id>` without mutating the source result or stable capability files.

Run: `python3 -m unittest tests.test_v16_experience_evolution -v`

Expected: application/evaluation tests PASS.

### Task 4: Configurable promotion, demotion, disable, and immutable rollback

**Files:**
- Modify: `src/ai_ppt_studio/domains/experience/contracts.py`
- Modify: `src/ai_ppt_studio/application/experience_service.py`
- Test: `tests/test_v16_experience_evolution.py`

- [x] **Step 1: Write failing evolution-policy tests**

Register an explicit versioned policy rather than a code constant:

```python
policy_ref = experience.register_evolution_policy(
    "experience-policy",
    revision,
    {
        "policy_version": "personal-experience-policy/test-v1",
        "threshold_status": "configurable-pending-real-validation",
        "minimum_distinct_accepted_projects": 2,
        "minimum_failure_projects_for_demotion": 2,
        "requires_professional_review": True,
        "requires_user_acceptance": True,
        "simulation_evidence_forbidden": True,
    },
)
```

The numeric values are a versioned test policy, not a frozen product baseline. Reject automatic promotion without a current policy and an explicit `experience-evolution-decision` artifact.

- [x] **Step 2: Write transition and rollback RED tests**

Assert promotion requires the policy-defined count of distinct matched projects with accepted professional/user outcomes. Demotion and disable require current failure evidence plus a governance reason. Rollback creates a new candidate artifact containing `restored_from` and `previous_version_ref`; historical objects remain unchanged.

- [x] **Step 3: Implement governed transitions**

Implement `validate_evolution_policy`, `validate_evolution_decision`, and `ExperienceService.evolve_candidate(action="promote|demote|disable")` plus `rollback_candidate`. Never infer promotion from a single feedback record, a test-only capture, or a user-specific project override.

- [x] **Step 4: Run GREEN and idempotency checks**

Run: `python3 -m unittest tests.test_v16_experience_evolution -v`

Expected: PASS; stale revision, repeated command id, mismatched evidence, and rollback leave current valid heads auditable.

### Task 5: Stable capability release isolation

**Files:**
- Modify: `src/ai_ppt_studio/domains/experience/contracts.py`
- Modify: `src/ai_ppt_studio/application/experience_service.py`
- Test: `tests/test_v16_experience_evolution.py`

- [x] **Step 1: Write failing release-isolation tests**

Allow a personal experience to create only a `stable-capability-release-candidate` containing source experience refs, positive/negative regressions, cross-role review refs, scope, counterexamples, failure boundaries, and proposed versions. Assert payload fields such as `publish=true`, `released_version`, `rewrite_prompt`, `rewrite_role_contract`, or `rewrite_scenario_pack` are rejected.

- [x] **Step 2: Run RED and implement candidate-only runtime path**

Implement `validate_stable_release_candidate` and `ExperienceService.propose_stable_release_candidate`; persist `experience/stable-release-candidate/<candidate_id>`. Do not expose a runtime publish method and do not modify Skill files, Prompt templates, `RoleRegistry`, or scenario packs.

- [x] **Step 3: Run GREEN and filesystem immutability assertion**

Hash `skills/ai-ppt-studio/SKILL.md`, `src/ai_ppt_studio/role_registry.py`, and `src/ai_ppt_studio/scenario_packs.py` before the runtime test and assert their hashes are unchanged afterward.

Run: `python3 -m unittest tests.test_v16_experience_evolution -v`

Expected: PASS.

### Task 6: Existing public bridge and compact experience projection

**Files:**
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `mcp/server.mjs`
- Create: `tests/test_v16_experience_bridge.py`
- Modify: `tests/mcp-server.test.mjs`

- [x] **Step 1: Write failing bridge tests**

Use only the existing `commit-artifact` public operation with `kind=experience` and a recognized `artifact_type` to register intake, learning results, applications, evaluations, transitions, and release candidates. Read the compact experience projection from the existing `get-project-snapshot` operation under `snapshot.experience`. Assert unsupported legacy writes fail explicitly and no tool named with `v16` is exposed.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_experience_bridge -v`

Expected: FAIL because schema 3 generic bridge routing does not recognize experience artifacts.

- [x] **Step 3: Implement thin routing**

Route `kind=experience` from `VisualService.commit_public_artifact` to `ExperienceService.commit_public_artifact`. Keep all result-type, match, qualification, transition, policy, and stable-release rules in Python. Extend `_snapshot` with `experience` containing only intake counts by source/result/status, current candidate versions, role-slice identities, latest application outcomes, and stable release-candidate status—never raw feedback, hidden diagnosis, or complete case content.

- [x] **Step 4: Run GREEN**

Run Python bridge tests and `node --test tests/mcp-server.test.mjs`.

Expected: all public names remain stable; only the existing commit kind enum expands to `experience`.

### Task 7: Slice verification and honest evidence labeling

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-v16-slice-05-experience-evolution.md`

- [x] **Step 1: Run focused Slice 05 tests**

Run all four v1.6 experience test modules with `-v`; expected zero failures.

- [x] **Step 2: Run full regressions**

Run: `python3 -m unittest discover -s tests -v` and `npm test`.

Expected: Python, Node, Widget, and build suites pass.

- [x] **Step 3: Verify ledger and hygiene**

Run: `python3 scripts/build_acceptance_ledger.py`, count exactly 104 requirements, and run `git diff --check`.

- [x] **Step 4: Mark proof scope honestly**

Mark automated contract enforcement as proven in this plan. Do not call simulated fixture applications “real cross-project validation,” do not freeze numeric evolution thresholds, and do not mark runtime or real-project evidence rows passed without genuine evidence.

No intermediate commit is made because the user explicitly requested one unified commit only after the full v1.6 acceptance scope is complete.

## Verification evidence (2026-08-09)

- Focused Slice 05 Python suite: 11 tests passed.
- Full Python regression: 179 tests passed.
- Node MCP suite: 11 tests passed.
- Widget suite: 13 tests passed across 6 files.
- Acceptance ledger generator: exactly 104 deterministic requirements.
- `git diff --check`: passed.
- Automated fixtures prove contract enforcement only. They are not genuine cross-project runtime applications, do not validate the configurable numeric policy values as final product thresholds, and do not prove stable capability maturity.
- The existing 27 files under `widget/.dist-raw-*` remain deferred to Slice 07 cleanup and must not enter the final commit.
