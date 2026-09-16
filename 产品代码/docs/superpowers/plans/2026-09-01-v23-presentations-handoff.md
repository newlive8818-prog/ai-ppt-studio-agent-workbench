# v2.3 Presentations Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `build-native-first` consume only the exact current `VisualCompilationPlan` and deliver a closed, current, PowerPoint-specific ContextPack to Codex Presentations without adding a public MCP tool.

**Architecture:** Keep `request_ai_ppt_agent_action` as the public request surface and `commit_ai_ppt_artifact` as the existing result surface. Python validates that the single task target is `visual/compilation-plan`, resolves its bound current inputs into one governed handoff layer, and requires the resulting `AnchorSlideSet` to bind the same plan. Node MCP remains a fixed 43-tool thin adapter.

**Tech Stack:** Python 3.11+, stdlib `unittest`, Node.js test runner, Zod MCP schemas, Markdown Skill references, immutable ContextPack artifacts.

---

## Execution isolation

- Required integrated predecessor: R1 approved and fast-forwarded into `codex/v23-visual-quality-20260831`.
- Execution branch: `codex/v23-presentations-handoff-20260901`.
- Execution Worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-presentations-handoff-20260901`.
- Create only after the user selects R2 and the integration Worktree is clean.
- Do not modify Widget UI, four baselines, Runtime sample projects, PPTX files, plugin installation, or publication.

## File map

- Modify `src/ai_ppt_studio/application/project_service.py`: exact single-plan target contract for `build-native-first`; result context binding.
- Modify `src/ai_ppt_studio/context_compiler.py`: current-plan resolver, task-bound absolute output paths, exact result revision, authorization scope, and closed `visual_handoff` layer.
- Modify `src/ai_ppt_studio/domains/visual/contracts.py`: require `visual_compilation_plan_ref` on AnchorSlideSet.
- Modify `src/ai_ppt_studio/application/visual_service.py`: require current plan when registering anchors and Image 2 assets.
- Modify `src/ai_ppt_studio/application/gate_evaluator.py`: require anchor/plan identity equality in G2.
- Modify `tests/v16_visual_fixtures.py`: add the current plan ref to anchor fixtures.
- Create `tests/test_v23_presentations_handoff.py`: target, ContextPack, result, staleness, and no-second-tool tests.
- Modify `tests/test_context_compiler_governance.py`: closed handoff layer regression.
- Modify `tests/test_v16_visual_bridge.py`: current task/result binding regression.
- Verify `mcp/tools/project-tools.mjs`: existing action and artifact enums already cover the workflow; no change expected.
- Verify `mcp/tool-catalog.mjs`: public total remains 43.
- Modify `tests/mcp-server.test.mjs`: assert no new public tool and unchanged action routing.
- Modify `skills/ai-ppt-studio/references/visual-workflow.md`: semantic compilation order and anti-pattern boundary.
- Modify `skills/ai-ppt-studio/references/presentations-handoff.md`: exact v2.3 handoff, authoring, rendering, and evidence contract.
- Verify `skills/ai-ppt-studio/SKILL.md`: no second PPTX route or conflicting invocation sequence.

### Task 1: Bind AnchorSlideSet to the current compilation plan

**Files:**
- Modify: `src/ai_ppt_studio/domains/visual/contracts.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `tests/v16_visual_fixtures.py`
- Create: `tests/test_v23_presentations_handoff.py`

- [ ] **Step 1: Add RED AnchorSlideSet contract tests**

Starting from `prepared_g1_anchor()`, require rejection when `visual_compilation_plan_ref` is missing, empty, wrong-kind, unresolvable, or points to a non-current plan. Require a successful anchor payload to contain exactly the current plan ref.

Add a G2 test that replaces the plan head after anchor registration and expects `anchor-compilation-plan-mismatch` or `visual-compilation-plan-missing-or-stale`.

- [ ] **Step 2: Add RED Image 2 lineage tests**

After an anchor is frozen, remove or replace `visual/compilation-plan` and call the Image 2 task precondition. Require failure before any image-asset artifact or revision is written. A frozen native-first flag alone must no longer be enough.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_presentations_handoff
```

Expected: current anchor validators and G2 do not know the compilation-plan ref.

- [ ] **Step 4: Require and normalize the plan ref**

In `validate_anchor_slide_set()` add:

```python
normalized["visual_compilation_plan_ref"] = _text(
    payload, "visual_compilation_plan_ref"
)
```

In `VisualService.register_anchor_set()` resolve it with:

```python
plan = require_exact_ref(
    self.kernel,
    normalized["visual_compilation_plan_ref"],
    "visual/compilation-plan",
    "visual-compilation-plan",
)["payload"]
if plan["visual_contract_set_ref"] != normalized["visual_contract_set_ref"]:
    raise ContractValidationError(
        "AnchorSlideSet compilation plan does not bind its visual contract set"
    )
```

Update fixture anchor payloads with the exact current plan ref. Do not synthesize it from the contract-set ref inside the validator.

- [ ] **Step 5: Bind G2 and Image 2 to the same plan**

In `GateEvaluator.validate_current_g2_evidence()` compare `anchors["visual_compilation_plan_ref"]` to the exact current plan ref returned by the R1 current-plan helper. In `ContextCompiler._require_frozen_native_first()` require both `native_first_frozen is True` and current plan identity equality.

- [ ] **Step 6: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_presentations_handoff \
    tests.test_v16_visual_contracts \
    tests.test_v16_visual_gates
```

Expected: all selected tests pass.

### Task 2: Restrict `build-native-first` to one current plan target

**Files:**
- Modify: `src/ai_ppt_studio/application/project_service.py`
- Modify: `tests/test_v23_presentations_handoff.py`
- Modify: `tests/test_v16_visual_bridge.py`

- [ ] **Step 1: Add RED request tests**

At G1 passed, call `request_agent_action(action_type="build-native-first", ...)` with each invalid target set:

```python
invalid_targets = (
    [],
    [refs["contracts"]],
    [refs["plan"], refs["contracts"]],
    [old_plan_ref],
)
```

Require zero writes and stable error `build-native-first requires the exact current visual compilation plan`. Require `[current_plan_ref]` to create one task whose `target_refs` remains that single ref.

- [ ] **Step 2: Add RED result-binding tests**

Create a valid task, then replace the current plan before `commit_noncontent_agent_result()`. Require rejection even if the result payload contains the old plan ref. Also require rejection if the result anchor payload plan ref differs from the task target.

- [ ] **Step 3: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_presentations_handoff \
    tests.test_v16_visual_bridge
```

Expected: current task logic accepts any unique current head list.

- [ ] **Step 4: Implement the exact request contract**

Immediately after current-state loading and before context compilation:

```python
if action == "build-native-first":
    current_plan_ref = state.artifact_heads.get("visual/compilation-plan", "")
    if target_refs != [current_plan_ref] or not current_plan_ref:
        raise ContractValidationError(
            "build-native-first requires the exact current visual compilation plan"
        )
```

Keep the existing G1 requirement. Do not add an action type, role, public tool, or new artifact commit kind.

- [ ] **Step 5: Implement result preflight identity**

During non-content result preflight, for `build-native-first` require:

```python
task["target_refs"] == [current_plan_ref]
payload["visual_compilation_plan_ref"] == current_plan_ref
context["layers"]["visual_handoff"]["visual_compilation_plan_ref"] == current_plan_ref
context["layers"]["visual_handoff"]["task_id"] == task["task_id"]
context["layers"]["visual_handoff"]["result_expected_revision"] == expected_revision
```

Also require every declared output path to remain below the current project root and contain the exact task ID. Failure must occur in read-only preparation before artifact persistence or task completion.

- [ ] **Step 6: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_presentations_handoff \
    tests.test_v16_visual_bridge
```

Expected: all target and result identity tests pass.

### Task 3: Compile the closed Codex Presentations handoff layer

**Files:**
- Modify: `src/ai_ppt_studio/context_compiler.py`
- Modify: `tests/test_context_compiler_governance.py`
- Modify: `tests/test_v23_presentations_handoff.py`

- [ ] **Step 1: Add RED exact-shape tests**

For a valid `build-native-first` task, assert `layers.visual_handoff` has exactly:

```python
VISUAL_HANDOFF_FIELDS = {
    "task_id",
    "handoff_version",
    "compiler_version",
    "visual_compilation_plan_ref",
    "reading_blueprint_ref",
    "visual_brief_ref",
    "deck_design_system_ref",
    "visual_contract_set_ref",
    "release_target_policy_ref",
    "source_version",
    "source_revision",
    "reading_blueprint",
    "visual_brief",
    "deck_design_system",
    "slide_visual_contracts",
    "compilation_slides",
    "required_target_ids",
    "deferred_target_ids",
    "output_paths",
    "result_expected_revision",
    "authorization_scope",
    "authoring_contract",
    "evidence_contract",
}
```

Require no hidden reasoning, old plan, sibling review, raw experience workspace, or unrelated visual head payload.

Require the output and authority structures to equal:

```python
output_paths = {
    "pptx": str(project_root / "delivery" / "anchors" / task_id / "native-anchors.pptx"),
    "render_dir": str(project_root / "renders" / "anchors" / task_id),
    "montage": str(project_root / "renders" / "anchors" / task_id / "montage.png"),
}
authorization_scope = {
    "action_type": "build-native-first",
    "allowed_result_kind": "native-anchor-set",
    "required_anchor_count": 3,
    "authorizing_gate": "G1-passed",
    "whole_deck_build_forbidden": True,
    "gate_advance_forbidden": True,
}
```

Every output path must be absolute, resolve below the managed project root, include the exact immutable task ID, and be absent before authoring begins. `result_expected_revision` must equal `project_revision + 1`, the revision produced by the task-request commit. If any other write advances the project before result commit, the result is stale and a new task is required; the implementation must not silently rewrite the expected revision.

- [ ] **Step 2: Add RED current-binding tests**

Corrupt each plan-bound ref or policy identity and require context compilation to fail before task creation. Require `source_revision` to equal the immutable event revision where the current contract and plan heads were published atomically, and require it to be no greater than the current project revision. Later unrelated revisions must not invalidate the handoff.

- [ ] **Step 3: Define the exact authoring and evidence contracts**

Assert:

```python
authoring_contract = {
    "pptx_tool": "Codex Presentations only",
    "implementation": "@oai/artifact-tool JavaScript ES module",
    "semantic_objects_native": True,
    "whole_slide_bitmap_forbidden": True,
    "baked_factual_text_forbidden": True,
    "connectors_before_nodes": True,
    "separate_replaceable_image_layers": True,
    "target_application": "macos-powerpoint",
    "source_notes": "[Sources] blocks required in speaker notes",
}
evidence_contract = {
    "render_every_slide": True,
    "inspect_every_slide_full_size": True,
    "montage_is_rhythm_only": True,
    "overflow_check_required": True,
    "editability_check_required": True,
    "target_powerpoint_check_separate": True,
    "user_visual_judgment_separate": True,
}
```

- [ ] **Step 4: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_context_compiler_governance \
    tests.test_v23_presentations_handoff
```

Expected: `visual_handoff` is absent.

- [ ] **Step 5: Pass the immutable task identity into context compilation**

Extend `ContextCompiler.compile_role_task()` with a `task_id: str = ""` keyword. In `ProjectService.request_agent_action()`, compute `task_id` before compilation as it does today and pass it explicitly. For `build-native-first`, reject an empty or malformed task identity unless it is exactly 64 lowercase hexadecimal characters. Existing non-visual callers keep the default and their ContextPack shape unchanged.

- [ ] **Step 6: Implement `_compile_visual_handoff()`**

Resolve the exact plan ref/kind, validate the plan, then resolve every bound ref by exact slot and kind. Compare every ref with current state, compare the policy payload with the current `ReleaseTargetPolicyService.current()` result, and prove from event history that contracts and plan share the recorded atomic publication revision. Derive the three absolute output paths from `self.kernel.project_root` and the exact task ID, reject any resolved path outside the project, set `result_expected_revision = project_revision + 1`, and attach the closed authorization scope above. Deep-copy only the registered fields into the closed layer.

For non-`build-native-first` tasks, omit `visual_handoff` unless the existing task contract explicitly consumes it. Do not expose the compilation plan through a new read tool.

- [ ] **Step 7: Run GREEN**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_context_compiler_governance \
    tests.test_v23_presentations_handoff
```

Expected: exact-shape, current-binding, exclusion, and immutability tests pass.

### Task 4: Preserve the 43-tool MCP contract and update Skill handoff guidance

**Files:**
- Verify: `mcp/tools/project-tools.mjs`
- Verify: `mcp/tool-catalog.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Modify: `skills/ai-ppt-studio/references/visual-workflow.md`
- Modify: `skills/ai-ppt-studio/references/presentations-handoff.md`
- Verify: `skills/ai-ppt-studio/SKILL.md`

- [ ] **Step 1: Add MCP catalog regression**

In `tests/mcp-server.test.mjs`, assert:

```javascript
assert.equal(PUBLIC_TOOL_CATALOG.length, 43);
assert.equal(
  PUBLIC_TOOL_CATALOG.filter((tool) => tool.group === "project").length,
  15,
);
assert.equal(
  PUBLIC_TOOL_CATALOG.some((tool) => tool.name.includes("compilation_plan")),
  false,
);
```

Also assert `request_ai_ppt_agent_action` still accepts `build-native-first` and `commit_ai_ppt_artifact` still accepts `native-anchor-set`.

- [ ] **Step 2: Run the catalog test before documentation changes**

```bash
cd 产品代码
node --test tests/mcp-server.test.mjs
```

Expected: the existing 43-tool contract passes; no product schema change is required. If it fails, stop and investigate the existing public catalog rather than adding a tool.

- [ ] **Step 3: Update `visual-workflow.md`**

Insert the exact workflow:

```text
ReadingDeckBlueprint
-> Visual Brief
-> Deck Design System
-> Slide Visual Contract
-> atomic VisualCompilationPlan
-> build-native-first ContextPack
-> Codex Presentations
-> automated / human / target PowerPoint / user evidence
```

Document the primary/secondary relationship limit, asset roles, anti-pattern evidence, non-forced design philosophy, and the rule that old visual artifacts are `legacy / unassessed-by-v23`.

- [ ] **Step 4: Update `presentations-handoff.md`**

Require the exact current plan ref and resolved current inputs; preserve frozen content; require `@oai/artifact-tool` in JavaScript ES modules; prohibit `python-pptx`, old Python artifact APIs, whole-slide bitmaps, baked factual text, untraceable data, decorative connectors, and silent template fallback. Require full-slide render inspection, overflow checks, editability evidence, target macOS PowerPoint evidence, and separate user judgment.

- [ ] **Step 5: Verify Skill references contain no conflicting route**

```bash
cd 产品代码
rg -n 'python-pptx|PptxGenJS|visual-compilation-plan|build-native-first|Codex Presentations|whole-slide' \
  skills/ai-ppt-studio/SKILL.md \
  skills/ai-ppt-studio/references/visual-workflow.md \
  skills/ai-ppt-studio/references/presentations-handoff.md
```

Expected: `python-pptx` and whole-slide bitmap mentions are prohibitions; compilation and build order are consistent; only Codex Presentations is authorized.

### Task 5: Full verification and commit

**Files:**
- Verify all R2 files and public catalog

- [ ] **Step 1: Run focused Python and Node suites**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_v23_presentations_handoff \
    tests.test_context_compiler_governance \
    tests.test_v16_visual_bridge \
    tests.test_v16_visual_contracts \
    tests.test_v16_visual_gates
node --test tests/mcp-server.test.mjs
```

Expected: zero failures.

- [ ] **Step 2: Run full regression and bundle checks**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm run test:node
npm run test:widget -- --configLoader runner
npm run build
```

Expected: all available suites pass. No plugin release or install command is authorized.

- [ ] **Step 3: Scan scope, identifiers, and placeholders**

```bash
cd 产品代码
rg -n 'TODO|TBD|适当处理|后续补充|NotImplemented' \
  src/ai_ppt_studio/application/project_service.py \
  src/ai_ppt_studio/context_compiler.py \
  src/ai_ppt_studio/domains/visual/contracts.py \
  src/ai_ppt_studio/application/visual_service.py \
  src/ai_ppt_studio/application/gate_evaluator.py \
  tests/test_v23_presentations_handoff.py \
  skills/ai-ppt-studio/references
rg -n 'codex-presentations-handoff/v23-v1|visual_compilation_plan_ref|visual_handoff' src tests skills
git diff --check
git status --short
```

Expected: no placeholders or whitespace errors; no MCP catalog/schema source changes unless a verified pre-existing mismatch required an approved plan change; only R2-scoped files changed.

- [ ] **Step 4: Commit rollback units**

```bash
git add \
  src/ai_ppt_studio/domains/visual/contracts.py \
  src/ai_ppt_studio/application/visual_service.py \
  src/ai_ppt_studio/application/gate_evaluator.py \
  tests/v16_visual_fixtures.py \
  tests/test_v23_presentations_handoff.py
git commit -m "feat: bind native anchors to visual compilation plans"

git add \
  src/ai_ppt_studio/application/project_service.py \
  src/ai_ppt_studio/context_compiler.py \
  tests/test_context_compiler_governance.py \
  tests/test_v16_visual_bridge.py \
  tests/test_v23_presentations_handoff.py
git commit -m "feat: compile governed presentations handoffs"

git add \
  tests/mcp-server.test.mjs \
  skills/ai-ppt-studio/references/visual-workflow.md \
  skills/ai-ppt-studio/references/presentations-handoff.md
git commit -m "docs: align visual workflow with compilation handoff"
```

Expected: three non-amended local commits; no merge, push, Worktree deletion, Runtime experiment, PPTX generation, plugin install, or publication.

## R2 exit report

Report separately:

```text
current-plan task restriction: implemented / not implemented
ContextPack and AnchorSlideSet binding: implemented / not implemented
public MCP tool count: 43 / mismatch
automated verification: exact commands and counts
real PPT samples: not run
target PowerPoint: not checked
user visual acceptance: not requested
integration into codex/v23-visual-quality-20260831: awaiting user decision
```
