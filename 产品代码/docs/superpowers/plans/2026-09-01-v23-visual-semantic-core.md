# v2.3 Visual Semantic Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the three visual contracts and atomically derive one deterministic, immutable `VisualCompilationPlan` that is required by current visual lineage without creating a second design truth.

**Architecture:** Keep user-authored visual meaning in `VisualBrief`, `DeckDesignSystem`, and `VisualContractSet`. Add a pure compiler that copies only validated semantics into a canonical implementation plan; `VisualService.register_visual_contract_set()` computes both refs and writes `visual/contracts` plus `visual/compilation-plan` in one kernel transaction. Gate evaluators require the exact current plan and classify old contracts as `legacy / unassessed-by-v23` rather than silently upgrading them.

**Tech Stack:** Python 3.11+, stdlib `unittest`, immutable JSON artifacts, revision-safe `ProjectKernel`, canonical JSON SHA-256 references.

---

## Execution isolation

- Required integrated predecessor: R0 commit approved and fast-forwarded into `codex/v23-visual-quality-20260831`.
- Execution branch: `codex/v23-semantic-core-20260901`.
- Execution Worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-semantic-core-20260901`.
- Create from the then-current clean integration HEAD only after the user selects R1.
- Do not modify Widget, Skill, MCP schemas, Runtime sample projects, PPTX files, plugin installation, or publication.

## File map

- Modify `src/ai_ppt_studio/domains/visual/contracts.py`: v2.3 field validation, closed nested structures, relationship and asset-role vocabularies, legacy assessment.
- Create `src/ai_ppt_studio/domains/visual/compilation.py`: pure deterministic compiler and compilation-plan validator.
- Modify `src/ai_ppt_studio/domains/visual/__init__.py`: export compiler constants/functions only.
- Create `src/ai_ppt_studio/application/visual_invalidation.py`: one dependency-free current-head invalidation selector shared by visual registration and policy migration.
- Modify `src/ai_ppt_studio/application/visual_service.py`: exact upstream resolution, atomic two-head write, downstream invalidation, final visual-contract plan binding.
- Modify `src/ai_ppt_studio/application/gate_evaluator.py`: require exact current plan in G1, G2, publication, and G3 lineage.
- Modify `src/ai_ppt_studio/application/release_policy_service.py`: invalidate the current compilation-plan head when the policy identity changes.
- Modify `tests/v16_visual_fixtures.py`: make all current visual fixtures v2.3-complete.
- Create `tests/test_v23_visual_semantic_contracts.py`: field vocabulary, frozen-content, closed-schema, optional-philosophy, and legacy tests.
- Create `tests/test_v23_visual_compilation.py`: deterministic derivation, canonical ref, atomicity, and no-second-truth tests.
- Create `tests/test_v23_visual_lineage.py`: invalidation and G1/G2/G3 current-plan lineage tests.
- Verify existing visual, release-policy, project, and delivery tests unchanged except fixture consumption.

### Task 1: Close the v2.3 visual semantic contracts

**Files:**
- Modify: `src/ai_ppt_studio/domains/visual/contracts.py`
- Modify: `tests/v16_visual_fixtures.py`
- Create: `tests/test_v23_visual_semantic_contracts.py`

- [ ] **Step 1: Add RED tests for required Visual Brief fields**

For each required field, remove it from `valid_visual_brief()` and require `ContractValidationError`:

```python
required_brief_fields = (
    "decision_task",
    "design_stance",
    "emotional_boundary",
    "brand_boundary",
    "density_strategy",
    "forbidden_patterns",
    "five_second_test_contract",
)
```

Require `forbidden_patterns` to be a non-empty unique string list. Require `five_second_test_contract` to contain exactly:

```python
{
    "prompt": "五秒后隐藏页面并记录第一判断",
    "expected_judgment": "读者形成与页面合同一致的核心判断",
    "record_fields": [
        "first_noticed_object",
        "perceived_message",
        "perceived_relationship",
        "next_reading_step",
        "misdirection",
    ],
}
```

Require missing `design_philosophy_refs` to pass; if present, it must be a unique string list and must not affect Gate eligibility.

- [ ] **Step 2: Add RED tests for Deck Design System fields**

Require:

```python
required_design_fields = (
    "density_rhythm",
    "cross_slide_rhythm_rules",
    "emphasis_budget",
    "image_language",
    "diagram_language",
    "five_second_test_rules",
)
```

Use an exact `emphasis_budget` shape:

```python
{
    "max_primary_focal_points_per_slide": 1,
    "max_accent_color_roles": 2,
    "consecutive_high_density_slide_limit": 2,
}
```

Reject non-positive integer limits, duplicate rhythm/rule entries, and undeclared keys in `emphasis_budget`.

- [ ] **Step 3: Add RED tests for Slide Visual Contract fields**

For every slide require:

```python
required_slide_text = (
    "reader_judgment",
    "primary_relationship",
    "visual_mechanism",
    "focal_point",
    "previous_rhythm_relation",
    "next_rhythm_relation",
    "text_density_budget",
)
required_slide_values = (
    "secondary_relationship",
    "asset_roles",
    "forbidden_patterns",
    "powerpoint_implementation_requirements",
    "acceptance_evidence_plan",
)
```

`secondary_relationship` must exist and may be `""`. `primary_relationship` and a non-empty secondary value must be different members of:

```python
VISUAL_RELATIONSHIPS = frozenset({
    "comparison", "sequence", "causality", "hierarchy", "network",
    "system-boundary", "cycle", "tension", "evidence-to-judgment",
    "single-focus",
})
```

Require one primary relationship, at most one secondary relationship, a non-empty unique `forbidden_patterns` list, and exact frozen-content equality with the current ReadingDeckBlueprint.

- [ ] **Step 4: Close asset, PowerPoint, and evidence structures**

Use exact nested shapes:

```python
asset_role = {
    "asset_id": "hero-structure",
    "role": "structure",  # evidence | structure | explanation | emotion-context
    "source_ref": "",     # empty allowed for planned/generated non-evidence assets
    "narrative_task": "建立主体、软件边界与责任关系",
    "replaceable": True,
}

powerpoint_implementation_requirements = {
    "object_plan": [{
        "role": "primary-subject",
        "object_type": "native-shape",
        "layer": "foreground",
        "editability": "native-editable",
    }],
    "connector_semantics": [{
        "from_role": "human",
        "to_role": "ai",
        "meaning": "主要执行责任转移",
        "direction": "forward",
        "crossing_forbidden": True,
    }],
    "layout_constraints": {
        "entry_region": "left",
        "focal_region": "center-right",
        "minimum_clear_space": "one-body-line",
    },
    "native_bitmap_routing": "事实、标签与关系原生；结构图为独立可替换图片层",
    "degradation_strategy": "复杂图像失败时保留原生主体与边界关系",
}

acceptance_evidence_plan = {
    "automated_checks": ["frozen-content", "native-object-routing", "overflow"],
    "human_review_checks": ["five-second-judgment", "anti-pattern-review"],
    "target_powerpoint_checks": ["font", "crop", "connector", "editability"],
    "user_review_question": "五秒内是否先看到执行主体变化与软件治理边界？",
}
```

Reject unknown nested keys, invalid asset roles, missing object roles, connectors with identical endpoints, non-boolean `crossing_forbidden`, empty evidence arrays, and evidence-role assets without a non-empty `source_ref`.

- [ ] **Step 5: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_visual_semantic_contracts
```

Expected: failures show the current validators accept missing v2.3 fields and do not close the new nested structures.

- [ ] **Step 6: Implement minimal validators and fixture data**

Add the vocabulary constants and small helpers to `contracts.py`:

```python
VISUAL_RELATIONSHIPS = frozenset({
    "comparison", "sequence", "causality", "hierarchy", "network",
    "system-boundary", "cycle", "tension", "evidence-to-judgment",
    "single-focus",
})
VISUAL_ASSET_ROLES = frozenset({
    "evidence", "structure", "explanation", "emotion-context",
})

def _exact_keys(
    payload: dict[str, Any],
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    keys = set(payload)
    if not required.issubset(keys) or keys.difference(required | optional):
        raise ContractValidationError("Visual v2.3 fields are not closed")
```

Keep existing root compatibility fields; close only the newly introduced nested records and the compilation plan. Normalize lists without sorting user-declared reading order. Update `valid_visual_brief()`, `valid_design_system()`, and `valid_contract_set()` with concrete v2.3 values so existing tests exercise the current contract.

- [ ] **Step 7: Run GREEN and existing contract regression**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_visual_semantic_contracts \
    tests.test_v16_visual_contracts \
    tests.test_v22_visual_lineage
```

Expected: all selected tests pass.

### Task 2: Build the pure deterministic VisualCompilationPlan compiler

**Files:**
- Create: `src/ai_ppt_studio/domains/visual/compilation.py`
- Modify: `src/ai_ppt_studio/domains/visual/__init__.py`
- Create: `tests/test_v23_visual_compilation.py`

- [ ] **Step 1: Add RED tests for the exact plan shape**

Call the not-yet-existing `derive_visual_compilation_plan()` with normalized brief, design system, contract set, current refs, policy ref, revision, and compiler/handoff versions. Assert the root has exactly:

```python
PLAN_ROOT_FIELDS = {
    "artifact_type", "compiler_version", "handoff_version", "production_route",
    "reading_blueprint_ref", "visual_brief_ref", "deck_design_system_ref",
    "visual_contract_set_ref", "release_target_policy_ref", "source_version",
    "source_revision", "role_runs", "experience_refs", "slides",
}
```

Assert every page has exactly the 13 fields registered in the R&D map and preserves slide order.

- [ ] **Step 2: Add RED determinism and no-second-truth tests**

Prove:

1. two deep-copied equal inputs produce equal payloads;
2. `ArtifactRepository.reference_for("visual-compilation-plan", payload)` produces the same ref;
3. dictionary insertion order differences do not change canonical ref;
4. changing `visual_mechanism`, policy ref, source revision, or compiler version changes the ref;
5. changing frozen copy in a plan input is rejected before derivation;
6. the plan contains no `visible_copy_blocks`, `speaker_notes`, facts, data, source text, or independent `core_claim` field.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_visual_compilation
```

Expected: import/function failures because the compiler module does not exist.

- [ ] **Step 4: Implement the pure compiler**

Create:

```python
COMPILER_VERSION = "visual-semantic-compiler/v1"
HANDOFF_VERSION = "codex-presentations-handoff/v23-v1"

def derive_visual_compilation_plan(
    *,
    reading_blueprint_ref: str,
    visual_brief_ref: str,
    deck_design_system_ref: str,
    visual_contract_set_ref: str,
    release_target_policy_ref: str,
    source_version: str,
    source_revision: int,
    visual_brief: dict[str, Any],
    design_system: dict[str, Any],
    contract_set: dict[str, Any],
) -> dict[str, Any]:
    if (
        visual_brief["reading_blueprint_ref"] != reading_blueprint_ref
        or design_system["reading_blueprint_ref"] != reading_blueprint_ref
        or design_system["visual_brief_ref"] != visual_brief_ref
        or contract_set["reading_blueprint_ref"] != reading_blueprint_ref
        or contract_set["deck_design_system_ref"] != deck_design_system_ref
    ):
        raise ContractValidationError(
            "Visual compilation inputs do not bind the supplied current refs"
        )
    slides = []
    for contract in contract_set["slide_contracts"]:
        implementation = contract["powerpoint_implementation_requirements"]
        slides.append({
            "slide_id": contract["slide_id"],
            "primary_relationship": contract["primary_relationship"],
            "visual_mechanism": contract["visual_mechanism"],
            "focal_point": contract["focal_point"],
            "reading_path": deepcopy(contract["reading_order"]),
            "object_plan": deepcopy(implementation["object_plan"]),
            "connector_semantics": deepcopy(implementation["connector_semantics"]),
            "asset_plan": deepcopy(contract["asset_roles"]),
            "layout_constraints": deepcopy(implementation["layout_constraints"]),
            "native_bitmap_routing": implementation["native_bitmap_routing"],
            "powerpoint_constraints": {
                "deck": visual_brief["powerpoint_constraints"],
                "slide": implementation["degradation_strategy"],
            },
            "anti_pattern_checks": deepcopy(contract["forbidden_patterns"]),
            "acceptance_evidence_plan": deepcopy(contract["acceptance_evidence_plan"]),
        })
    role_runs = deepcopy(contract_set["role_runs"])
    experience_refs = list(dict.fromkeys(
        str(run["experience_slice_ref"])
        for run in role_runs
        if isinstance(run, dict) and run.get("experience_slice_ref")
    ))
    plan = {
        "artifact_type": "visual-compilation-plan",
        "compiler_version": COMPILER_VERSION,
        "handoff_version": HANDOFF_VERSION,
        "production_route": "strict-B",
        "reading_blueprint_ref": reading_blueprint_ref,
        "visual_brief_ref": visual_brief_ref,
        "deck_design_system_ref": deck_design_system_ref,
        "visual_contract_set_ref": visual_contract_set_ref,
        "release_target_policy_ref": release_target_policy_ref,
        "source_version": source_version,
        "source_revision": source_revision,
        "role_runs": role_runs,
        "experience_refs": experience_refs,
        "slides": slides,
    }
    return validate_visual_compilation_plan(plan, contract_set=contract_set)
```

Implement `validate_visual_compilation_plan(payload: dict[str, Any], *, contract_set: dict[str, Any]) -> dict[str, Any]`. It receives the source contract set only to verify one-to-one semantic copying and returns a deep normalized plan containing exactly `PLAN_ROOT_FIELDS`. Do not call the model, filesystem, clock, random generator, or artifact repository inside the compiler.

- [ ] **Step 5: Implement the closed plan validator**

`validate_visual_compilation_plan()` must validate artifact refs/kinds, positive integer source revision, exact compiler/handoff literals, unique ordered slide IDs, exact nested fields, one-to-one semantic copying from the contract set, and absence of frozen content. It must return a deep normalized copy.

- [ ] **Step 6: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_visual_compilation
```

Expected: all compiler and canonical-ref tests pass.

### Task 3: Atomically register contracts and compilation plan

**Files:**
- Create: `src/ai_ppt_studio/application/visual_invalidation.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/application/release_policy_service.py`
- Modify: `tests/test_v23_visual_compilation.py`
- Create: `tests/test_v23_visual_lineage.py`

- [ ] **Step 1: Add RED atomic-write tests**

Assert a successful `register_visual_contract_set()` advances revision once and writes both heads:

```python
state.artifact_heads["visual/contracts"] == contract_ref
state.artifact_heads["visual/compilation-plan"].startswith(
    "artifact://visual-compilation-plan/"
)
```

Resolve the plan and assert its `visual_contract_set_ref` equals the exact contract ref computed in the same transaction.

Assert `plan["source_revision"] == before.revision + 1 == committed.revision`. Later unrelated commits may advance `state.revision`; they must not make the plan stale while all bound refs remain current.

Patch `ProjectKernel.commit` to raise before persistence and assert revision, heads, event filenames, and artifact-object filenames remain unchanged; `reference_for()` must not create an object file.

- [ ] **Step 2: Add RED stale-upstream tests**

Prove:

- registering a new brief removes current design system, contracts, plan, convergence, visual reviews, anchors, target evidence, final visual contract, visual ReviewSession, and delivery heads;
- registering a new design system keeps current brief but removes downstream heads including the plan;
- registering a new contract set writes new contracts/plan and removes old convergence, reviews, anchors, target evidence, final visual contract, visual ReviewSession, and delivery heads;
- changing ReleaseTargetPolicy removes the current plan head and keeps immutable old artifacts resolvable;
- command replay returns the original contract and plan refs without a new revision.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_visual_compilation \
    tests.test_v23_visual_lineage
```

Expected: current service writes only `visual/contracts`, has no current plan head, and leaves stale downstream heads.

- [ ] **Step 4: Implement the atomic two-head write**

In `register_visual_contract_set()`:

```python
brief_ref = self.kernel.load().artifact_heads.get("visual/brief", "")
brief = require_exact_ref(self.kernel, brief_ref, "visual/brief", "visual-brief")["payload"]
design = require_exact_ref(
    self.kernel, str(payload.get("deck_design_system_ref") or ""),
    "visual/design-system", "deck-design-system",
)["payload"]
policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
normalized = validate_visual_contract_set(payload, content)
contracts_ref = str(
    self.kernel.artifacts.reference_for("visual-contract-set", normalized)
)
plan = derive_visual_compilation_plan(
    reading_blueprint_ref=normalized["reading_blueprint_ref"],
    visual_brief_ref=brief_ref,
    deck_design_system_ref=normalized["deck_design_system_ref"],
    visual_contract_set_ref=contracts_ref,
    release_target_policy_ref=policy_ref,
    source_version=str(normalized.get("source_version") or content["source_version"]),
    source_revision=expected_revision + 1,
    visual_brief=brief,
    design_system=design,
    contract_set=normalized,
)
```

Commit both artifacts in one call. `source_revision` is their shared atomic publication revision, not a snapshot-equals-current assertion. After commit, assert the returned `visual/contracts` ref equals the precomputed `contracts_ref`; if the invariant fails, report the already-committed invariant violation and stop without any compensating or destructive write.

- [ ] **Step 5: Implement deterministic downstream removals**

Create the dependency-free shared helper so both services use the same slot contract without a circular import:

```python
VISUAL_REVIEW_SESSION_SLOT = "review/session/visual-professional"

def visual_downstream_slots(
    heads: dict[str, str], *, keep: set[str]
) -> tuple[str, ...]:
    return tuple(sorted(
        slot for slot in heads
        if (
            slot.startswith("visual/")
            or slot.startswith("delivery/")
            or slot == VISUAL_REVIEW_SESSION_SLOT
        )
        and slot not in keep
    ))
```

Pass the already loaded current `artifact_heads` and explicit keep sets for brief, design system, and contracts+plan. Do not delete artifacts from the store. In `ReleaseTargetPolicyService.bind_policy()`, when policy identity changes, remove `visual/compilation-plan` and heads derived from it, including convergence, reviews, anchors, target evidence, final visual contract, `review/session/visual-professional`, and delivery heads; preserve `visual/brief`, `visual/design-system`, `visual/contracts`, immutable artifacts, and the existing policy Gate mutation semantics.

- [ ] **Step 6: Add semantic command replay**

Fingerprint normalized contract input plus current brief, design-system, policy and reading-blueprint refs. Replaying the exact command returns the original contracts ref and leaves the original plan current only when its bound inputs are still current; changed semantics must raise and write nothing.

- [ ] **Step 7: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_visual_compilation \
    tests.test_v23_visual_lineage \
    tests.test_v16_release_policy_service \
    tests.test_v22_release_target_policy
```

Expected: all selected tests pass.

### Task 4: Bind G1, G2, final visual contract, and legacy status

**Files:**
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/domains/visual/contracts.py`
- Modify: `tests/test_v23_visual_lineage.py`
- Verify: `tests/test_v16_visual_gates.py`
- Verify: `tests/test_v22_visual_review_service.py`

- [ ] **Step 1: Add RED Gate-lineage tests**

Require G1 to fail with `visual-compilation-plan-missing-or-stale` when the plan head is absent, wrong-kind, or bound to a non-current contract/policy/brief/system/blueprint ref. Require G2 current evidence to fail under the same corruption. Require final `visual/contract` publication to include:

```python
{
    "visual_brief_ref": current_brief_ref,
    "visual_compilation_plan_ref": current_plan_ref,
}
```

Require `visual_user_reviewable()` and `current_g3_confirmation_evidence()` to reject a final contract whose plan ref no longer matches current state.

Require the plan's `source_revision` to equal the authoritative event revision where `visual/contracts` and `visual/compilation-plan` simultaneously became their current refs. A later unrelated commit must remain valid; a forged future, earlier, or single-head publication revision must fail.

- [ ] **Step 2: Add RED legacy tests**

Create a valid v2.2-style contract set by removing the v2.3 fields. Assert it remains resolvable as immutable JSON, but:

```python
assess_visual_contract_set_v23(payload) == "legacy / unassessed-by-v23"
```

Assert G1/G2 cannot treat it as current v2.3 evidence and no default values are synthesized.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_visual_lineage
```

Expected: current Gate tuples do not include the plan and no legacy assessment exists.

- [ ] **Step 4: Implement the reusable current-plan check**

Add a private GateEvaluator helper that resolves `visual/compilation-plan`, validates it, compares all bound refs, policy ref and source version, then walks immutable event history to verify that `source_revision` is the shared atomic publication revision of the current contracts and plan refs. Do not compare it to the later mutable `state.revision`. Return the plan payload/ref on success; append only stable blocker names on failure.

Add the plan ref to:

- G1 `refs` and passed Gate evidence;
- G2 current lineage and passed Gate evidence;
- `validate_current_g2_evidence()` return payload;
- final `visual/contract` refs;
- user-reviewable and current G3 evidence identity checks.

- [ ] **Step 5: Implement explicit legacy assessment**

Add:

```python
V23_SLIDE_FIELDS = frozenset({...all 12 required v2.3 keys...})

def assess_visual_contract_set_v23(payload: dict[str, Any]) -> str:
    slides = payload.get("slide_contracts")
    if not isinstance(slides, list) or not slides:
        return "legacy / unassessed-by-v23"
    return (
        "v23-assessed"
        if all(V23_SLIDE_FIELDS.issubset(slide) for slide in slides if isinstance(slide, dict))
        and len(slides) == sum(isinstance(slide, dict) for slide in slides)
        else "legacy / unassessed-by-v23"
    )
```

New writes still use the strict validator. Legacy read status never means passed, migrated, or accepted.

- [ ] **Step 6: Run GREEN and existing visual Gate regression**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_visual_lineage \
    tests.test_v16_visual_gates \
    tests.test_v22_visual_review_service \
    tests.test_v16_visual_review
```

Expected: all selected tests pass.

### Task 5: Full verification, self-review, and commit

**Files:**
- Verify all R1 files and unchanged public interfaces

- [ ] **Step 1: Run focused complete R1 suite**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_visual_semantic_contracts \
    tests.test_v23_visual_compilation \
    tests.test_v23_visual_lineage \
    tests.test_v16_visual_contracts \
    tests.test_v16_visual_gates \
    tests.test_v22_visual_lineage \
    tests.test_v22_visual_review_service \
    tests.test_v16_release_policy_service \
    tests.test_v22_release_target_policy
```

Expected: zero failures.

- [ ] **Step 2: Run the full unchanged product regression**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm run test:node
npm run test:widget -- --configLoader runner
npm run build
```

Expected: all available suites pass. A platform denial must be reported as `CapabilityGap` with exact output and cannot be reclassified as product success.

- [ ] **Step 3: Self-review specification coverage and placeholders**

```bash
rg -n 'TODO|TBD|适当处理|后续补充|pass\s+#|NotImplemented' \
  src/ai_ppt_studio/domains/visual \
  src/ai_ppt_studio/application/visual_service.py \
  src/ai_ppt_studio/application/gate_evaluator.py \
  src/ai_ppt_studio/application/release_policy_service.py \
  tests/test_v23_visual_*.py
rg -n 'visual-compilation-plan|visual/compilation-plan|visual-semantic-compiler/v1|legacy / unassessed-by-v23' \
  src tests
git diff --check
git status --short
```

Expected: no placeholders or whitespace errors; every new identifier is spelled consistently; only R1-scoped files changed.

- [ ] **Step 4: Commit small rollback units**

Commit after each green task:

```bash
git add src/ai_ppt_studio/domains/visual/contracts.py tests/v16_visual_fixtures.py tests/test_v23_visual_semantic_contracts.py
git commit -m "feat: define v2.3 visual semantic contracts"

git add src/ai_ppt_studio/domains/visual/compilation.py src/ai_ppt_studio/domains/visual/__init__.py tests/test_v23_visual_compilation.py
git commit -m "feat: derive deterministic visual compilation plans"

git add src/ai_ppt_studio/application/visual_invalidation.py src/ai_ppt_studio/application/visual_service.py src/ai_ppt_studio/application/release_policy_service.py tests/test_v23_visual_compilation.py tests/test_v23_visual_lineage.py
git commit -m "feat: register visual compilation lineage atomically"

git add src/ai_ppt_studio/application/gate_evaluator.py src/ai_ppt_studio/application/visual_service.py src/ai_ppt_studio/domains/visual/contracts.py tests/test_v23_visual_lineage.py
git commit -m "feat: bind visual gates to current compilation plans"
```

Expected: four non-amended local commits; no merge, push, plugin install, Runtime sample write, PPTX generation, or publication.

## R1 exit report

Report separately:

```text
visual semantic contracts: implemented / not implemented
VisualCompilationPlan atomic derivation: implemented / not implemented
automated verification: exact commands and counts
real PPT samples: not run
target PowerPoint: not checked
user visual acceptance: not requested
integration into codex/v23-visual-quality-20260831: awaiting user decision
```
