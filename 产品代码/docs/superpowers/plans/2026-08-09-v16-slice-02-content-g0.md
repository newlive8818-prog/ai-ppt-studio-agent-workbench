# v1.6 Slice 02 Content and G0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one schema 3.0 vertical slice from validated mission and user-provided materials through the isolated five-role content review, complete professional-review projection, governed marks, and chat-only G0 confirmation.

**Architecture:** The schema 3.0 `ProjectKernel` remains the only persistence boundary. Domain contracts validate immutable content artifacts; an application service advances the formal chain only through current content-addressed heads, and an authorized `GateEvaluator` is the only component that can create a gate mutation. Node/MCP remains a thin adapter over a new v1.6 Python bridge facade.

**Tech Stack:** Python 3.11+ standard library, `unittest`, JSON/SHA-256, Node.js MCP adapter contract tests.

---

## File map

- `src/ai_ppt_studio/kernel/gates.py`: unforgeable-in-normal-use gate mutation value and validation.
- `src/ai_ppt_studio/kernel/transactions.py`: gate-aware logical commits without exposing direct status writes.
- `src/ai_ppt_studio/domains/mission/contracts.py`: minimum mission contract.
- `src/ai_ppt_studio/domains/materials/contracts.py`: user-provided material inventory contract.
- `src/ai_ppt_studio/domains/content/contracts.py`: ordered content artifacts, five review roles, checks, and acceptance aggregation.
- `src/ai_ppt_studio/domains/feedback/contracts.py`: F0–F3 governance and change-set prerequisites.
- `src/ai_ppt_studio/application/content_service.py`: revision-safe command facade for the complete content chain.
- `src/ai_ppt_studio/application/gate_evaluator.py`: G0 evidence evaluation and chat confirmation mutation.
- `src/ai_ppt_studio/application/review_service.py`: complete projection plus version-bound mark persistence.
- `src/ai_ppt_studio/application/v16_bridge.py`: JSON operation facade used by the Node adapter.
- `src/ai_ppt_studio/workbench_bridge.py`: delegates schema 3 operations to `v16_bridge`.
- `mcp/server.mjs`: v1.6 content action enums and strict artifact kinds only; no domain logic.
- `tests/test_v16_inputs.py`: mission/material contracts.
- `tests/test_v16_content_chain.py`: ordered artifact lineage.
- `tests/test_v16_content_acceptance.py`: five-role binary hard gate and G0.
- `tests/test_v16_review_marks.py`: complete projection, marks, conflict, and no implicit Gate.
- `tests/test_v16_feedback_governance.py`: governed feedback prerequisite.
- `tests/test_v16_bridge.py`: Python facade operations and error codes.
- `tests/mcp-server.test.mjs`: Node mapping assertions for the new runtime contract.

### Task 1: Authorized gate mutation and project identity checks

**Files:**
- Create: `src/ai_ppt_studio/kernel/gates.py`
- Modify: `src/ai_ppt_studio/kernel/transactions.py`
- Test: `tests/test_kernel_transactions.py`

- [x] **Step 1: Add failing tests**

```python
def test_load_rejects_another_project_and_gate_requires_authorized_mutation(self):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        ProjectKernel.initialize(root, project_id="p1")
        with self.assertRaises(ProjectIdentityError):
            ProjectKernel(root, project_id="p2").load()
        kernel = ProjectKernel(root, project_id="p1")
        with self.assertRaises(GateMutationError):
            kernel.commit(
                command_id="forged",
                expected_revision=0,
                event_type="gate.forged",
                artifact_updates={},
                gate_mutation={"G0": "passed"},
            )
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_kernel_transactions -v`

Expected: FAIL because gate mutation and project identity errors are unavailable.

- [x] **Step 3: Implement the authorized value and kernel integration**

```python
# kernel/gates.py
_AUTHORITY = object()

@dataclass(frozen=True)
class GateMutation:
    updates: dict[str, str]
    evidence_refs: tuple[str, ...]
    authority: object = field(repr=False, compare=False)

def issue_gate_mutation(updates: dict[str, str], evidence_refs: tuple[str, ...]) -> GateMutation:
    return GateMutation(dict(updates), tuple(evidence_refs), _AUTHORITY)

def validate_gate_mutation(value: object) -> GateMutation:
    if not isinstance(value, GateMutation) or value.authority is not _AUTHORITY:
        raise GateMutationError("Gate status can only be changed by GateEvaluator")
    return value
```

`ProjectKernel.load()` must compare the persisted `project_id` with the constructor value. `commit()` accepts `gate_mutation: object | None`; when present it calls `validate_gate_mutation`, merges only the returned updates, and records the evidence refs in the revision event.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_kernel_transactions -v`

Expected: all transaction tests PASS.

### Task 2: Mission and user-provided material contracts

**Files:**
- Create: `src/ai_ppt_studio/domains/mission/__init__.py`
- Create: `src/ai_ppt_studio/domains/mission/contracts.py`
- Create: `src/ai_ppt_studio/domains/materials/__init__.py`
- Create: `src/ai_ppt_studio/domains/materials/contracts.py`
- Test: `tests/test_v16_inputs.py`

- [x] **Step 1: Write failing contract tests**

```python
class V16InputContractTests(unittest.TestCase):
    def test_mission_requires_audience_topic_and_desired_action(self):
        mission = validate_mission({
            "topic": "经营一体化方案",
            "primary_audience": "客户决策者",
            "desired_judgment_or_action": "批准一期立项",
        })
        self.assertEqual(mission["status"], "confirmed")
        with self.assertRaises(ContractValidationError):
            validate_mission({"topic": "经营一体化方案"})

    def test_material_inventory_rejects_non_user_origin_and_missing_locator(self):
        item = validate_material_inventory({"sources": [{
            "source_id": "s1", "origin": "user-provided", "kind": "text",
            "locator": "chat://message/material-1", "sha256": "a" * 64,
        }]})
        self.assertEqual(len(item["sources"]), 1)
        with self.assertRaises(ContractValidationError):
            validate_material_inventory({"sources": [{"origin": "web-search"}]})
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_inputs -v`

Expected: FAIL because the contracts do not exist.

- [x] **Step 3: Implement strict validators**

`validate_mission` returns a copied payload with `status="confirmed"` only when all three required non-empty fields are present. `validate_material_inventory` requires a non-empty `sources` array and, for every source, `source_id`, `origin="user-provided"`, `kind` in `file|directory|url|text|image`, a locator, and a lowercase SHA-256. Invalid input raises `ContractValidationError` without writing a revision.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_v16_inputs -v`

Expected: 2 tests PASS.

### Task 3: Ordered, reference-verified content production chain

**Files:**
- Create: `src/ai_ppt_studio/application/__init__.py`
- Create: `src/ai_ppt_studio/domains/content/__init__.py`
- Create: `src/ai_ppt_studio/domains/content/contracts.py`
- Create: `src/ai_ppt_studio/application/content_service.py`
- Test: `tests/test_v16_content_chain.py`

- [x] **Step 1: Write failing lineage tests**

```python
def test_content_chain_requires_current_verified_upstream_heads(self):
    with tempfile.TemporaryDirectory() as temp:
        service = ContentService.initialize(Path(temp), project_id="p1")
        mission = service.register_mission("c1", 0, valid_mission())
        materials = service.register_materials("c2", 1, valid_materials())
        strategy = service.register_content_stage("c3", 2, "strategy", {
            "mission_ref": mission, "material_inventory_ref": materials,
            "decision_stage": "立项", "core_tension": "系统割裂",
        })
        claim_map = service.register_content_stage("c4", 3, "claim-map", {
            "strategy_ref": strategy, "claims": [{"claim_id": "c1", "status": "supported", "evidence_refs": [materials]}],
        })
        argument = service.register_content_stage("c5", 4, "argument-map", {
            "strategy_ref": strategy, "claim_evidence_map_ref": claim_map,
            "chapters": [{"chapter_id": "ch1", "task": "建立问题共识"}],
        })
        draft = service.register_content_stage("c6", 5, "slide-draft-set", {
            "argument_map_ref": argument, "slides": [{
                "slide_id": "s1", "title": "为什么现在必须改变",
                "communication_goal": "建立紧迫性", "core_claim": "割裂阻碍经营",
                "visible_copy": ["五套系统", "三条断点"], "speaker_notes": "解释来源",
                "source_refs": [materials],
            }],
        })
        self.assertTrue(draft.startswith("artifact://slide-draft-set/"))
        with self.assertRaises(ArtifactReferenceError):
            service.register_content_stage("bad", 6, "argument-map", {
                "strategy_ref": "artifact://presales-content-strategy/" + "f" * 64,
                "claim_evidence_map_ref": claim_map, "chapters": [{"chapter_id": "x", "task": "x"}],
            })
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_content_chain -v`

Expected: FAIL because `ContentService` does not exist.

- [x] **Step 3: Implement ordered stage registration**

`ContentService` maps `strategy`, `claim-map`, `argument-map`, and `slide-draft-set` to formal kinds and head slots. Before every commit it parses each upstream reference, resolves it through `ArtifactRepository`, verifies its expected kind, and requires equality with the current head. Stage validators require the fields exercised above and reject empty slide text, notes, or sources.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_v16_content_chain -v`

Expected: the lineage test PASS.

### Task 4: Five-role binary acceptance and chat-only G0

**Files:**
- Modify: `src/ai_ppt_studio/domains/content/contracts.py`
- Create: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `src/ai_ppt_studio/application/content_service.py`
- Test: `tests/test_v16_content_acceptance.py`

- [x] **Step 1: Write failing acceptance tests**

```python
REQUIRED = (
    "presales-reviewer", "decision-maker-reviewer", "evidence-reviewer",
    "narrative-reviewer", "editorial-reviewer",
)

def test_acceptance_requires_exact_five_roles_and_all_hard_checks(self):
    service, revision, draft_ref = ready_draft()
    for index, role in enumerate(REQUIRED):
        service.register_review(f"r{index}", revision + index, {
            "target_ref": draft_ref, "reviewer_role": role,
            "checks": [{"criterion_id": "hard", "level": "must-follow", "applicability": "applicable", "result": "passed", "evidence_refs": [draft_ref]}],
            "overall_result": "passed",
        })
    accepted = service.accept_content("accept", revision + 5)
    self.assertEqual(accepted.state.gate_status["G0"], "user-reviewable")
    self.assertEqual(accepted.state.gate_status["G1"], "locked")

def test_failed_or_missing_review_blocks_acceptance_and_g0_needs_chat_message(self):
    service, revision, draft_ref = ready_draft()
    register_only_four_reviews(service, revision, draft_ref)
    with self.assertRaises(GateBlockedError):
        service.accept_content("accept", revision + 4)
    with self.assertRaises(GateBlockedError):
        service.confirm_g0("g0", revision + 4, user_message_ref="")
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_content_acceptance -v`

Expected: FAIL because review aggregation and G0 evaluation are absent.

- [x] **Step 3: Implement reviews, acceptance, blueprint, and GateEvaluator**

Each review must use exactly one of the five stable role IDs, target the current draft, contain only `must-follow|minimum-content-quality|reference-implementation`, and use `passed|failed|not-applicable`. `accept_content` requires exactly one current review per role and rejects any failed applicable hard check. On success one transaction writes `content-acceptance` and the complete `content-blueprint`, then applies an authorized `G0=user-reviewable` mutation. `confirm_g0` requires `chat://message/<id>`, the current passing acceptance and blueprint, writes `g0-confirmation`, sets `G0=passed`, and unlocks `G1=open`.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_v16_content_acceptance -v`

Expected: acceptance and blocking tests PASS.

### Task 5: Complete professional review projection and safe marks

**Files:**
- Create: `src/ai_ppt_studio/application/review_service.py`
- Test: `tests/test_v16_review_marks.py`

- [x] **Step 1: Write failing projection and mark tests**

```python
def test_projection_is_complete_and_marks_never_confirm_g0(self):
    service, revision, blueprint_ref = accepted_content()
    review = ReviewService(service.kernel).content_projection()
    text = json.dumps(review, ensure_ascii=False)
    for literal in ("五套系统", "三条断点", "解释来源"):
        self.assertIn(literal, text)
    self.assertNotIn("…", text)
    saved = ReviewService(service.kernel).save_marks(
        command_id="marks", expected_revision=revision,
        source_version=blueprint_ref,
        marks=[{"mark_id": "m1", "field_anchor": "slide-s1-visible-copy", "exact_text": "三条断点", "prefix": "五套系统", "suffix": "", "comment": "补充来源"}],
    )
    self.assertEqual(saved.gate_status["G0"], "user-reviewable")

def test_stale_source_or_revision_preserves_previous_mark_head(self):
    service, revision, blueprint_ref = accepted_content()
    review_service = ReviewService(service.kernel)
    before = service.kernel.load().artifact_heads.get("review-marks/content")
    with self.assertRaises(ReviewSourceStaleError):
        review_service.save_marks("stale", revision, "artifact://content-blueprint/" + "f" * 64, valid_marks())
    self.assertEqual(service.kernel.load().artifact_heads.get("review-marks/content"), before)
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_review_marks -v`

Expected: FAIL because `ReviewService` does not exist.

- [x] **Step 3: Implement projection and marks**

The projection deep-copies every blueprint field into stable overview, structure, and per-slide anchors, uses the exact blueprint reference as `source_version`, and never truncates strings. Mark saving validates the current source head, non-empty anchor/comment, exact selection context, idempotency command, and expected revision; it writes one `review-mark-set` artifact and does not issue a gate mutation.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_v16_review_marks -v`

Expected: projection, stale-source, revision, and Gate-isolation tests PASS.

### Task 6: Feedback governance before ContentChangeSet

**Files:**
- Create: `src/ai_ppt_studio/domains/feedback/__init__.py`
- Create: `src/ai_ppt_studio/domains/feedback/contracts.py`
- Modify: `src/ai_ppt_studio/application/content_service.py`
- Test: `tests/test_v16_feedback_governance.py`

- [x] **Step 1: Write failing governance tests**

```python
def test_raw_feedback_cannot_become_change_set_and_f2_requires_decision(self):
    service, revision, blueprint_ref = accepted_content()
    raw = service.capture_feedback("f1", revision, {
        "raw_feedback": "所有页面都改成大标题", "target_refs": [blueprint_ref]
    })
    with self.assertRaises(FeedbackGovernanceError):
        service.create_content_change_set("c1", revision + 1, raw)
    governed = service.govern_feedback("f2", revision + 1, {
        "raw_feedback_ref": raw, "feedback_level": "F2",
        "diagnosis": "局部阅读负担被扩大成整套规则", "counterexamples": ["证据页需要信息密度"],
        "ai_recommendation": "只调整章节页", "preserve_refs": [blueprint_ref],
    })
    with self.assertRaises(FeedbackGovernanceError):
        service.create_content_change_set("c2", revision + 2, governed)
    decided = service.decide_feedback("f3", revision + 2, governed, "follow-ai-recommendation")
    change = service.create_content_change_set("c3", revision + 3, decided)
    self.assertTrue(change.startswith("artifact://content-change-set/"))
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_feedback_governance -v`

Expected: FAIL because governed feedback APIs do not exist.

- [x] **Step 3: Implement F0–F3 prerequisites**

Raw feedback is stored separately. Governance requires diagnosis, scope, counterexamples, AI recommendation, and preserve refs. F0/F1 become executable after governance; F2/F3 remain `needs-user` until one of `follow-ai-recommendation|follow-user-instruction|supplement` is persisted. `ContentChangeSet` accepts only a current governed/decided record and records target, preserve refs, required role runs, and review route.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_v16_feedback_governance -v`

Expected: governance tests PASS.

### Task 7: v1.6 Python bridge and thin MCP mapping

**Files:**
- Create: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `src/ai_ppt_studio/workbench_bridge.py`
- Modify: `mcp/server.mjs`
- Test: `tests/test_v16_bridge.py`
- Test: `tests/mcp-server.test.mjs`

- [x] **Step 1: Write failing bridge and MCP tests**

```python
def test_bridge_exposes_v16_content_projection_and_chat_g0(self):
    result = dispatch_v16({"operation": "v16-get-content-review", "project_root": str(project)})
    self.assertEqual(result["review"]["source_version"], blueprint_ref)
    confirmed = dispatch_v16({
        "operation": "v16-confirm-g0", "project_root": str(project),
        "expected_revision": revision, "command_id": "g0",
        "user_message_ref": "chat://message/g0-accepted",
    })
    self.assertEqual(confirmed["state"]["gate_status"]["G0"], "passed")
```

```javascript
assert.ok(tools.tools.some((tool) => tool.name === "get_content_review_v16"));
assert.ok(tools.tools.some((tool) => tool.name === "confirm_content_g0_v16"));
assert.equal(calls.at(-1).operation, "v16-confirm-g0");
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_bridge -v && node --test tests/mcp-server.test.mjs`

Expected: FAIL because the v1.6 operations/tools are absent.

- [x] **Step 3: Implement thin mapping**

`dispatch_v16` validates JSON shape, resolves the schema 3 project root, invokes only `ContentService`, `ReviewService`, or `GateEvaluator`, and returns state/projection dictionaries. `workbench_bridge.dispatch` delegates `v16-*` operations before constructing any v1.x store. MCP adds Zod schemas and maps camelCase input to those operations; it performs no stage, review, Gate, or evidence calculation.

- [x] **Step 4: Run focused GREEN**

Run: `python3 -m unittest tests.test_v16_inputs tests.test_v16_content_chain tests.test_v16_content_acceptance tests.test_v16_review_marks tests.test_v16_feedback_governance tests.test_v16_bridge -v && node --test tests/mcp-server.test.mjs`

Expected: all Slice 02 and MCP tests PASS.

### Task 8: Slice verification

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-v16-slice-02-content-g0.md`

- [x] **Step 1: Run all Python tests**

Run: `python3 -m unittest discover -s tests`

Expected: zero failures and errors.

- [x] **Step 2: Run complete Node and Widget regression**

Run: `npm test`

Expected: build, Node tests, and Widget tests all PASS.

- [x] **Step 3: Verify baseline links and repository hygiene**

Run: `python3 scripts/build_acceptance_ledger.py && git diff --check && git status --short`

Expected: ledger generation remains deterministic; no whitespace failures; only intentional work remains dirty.

- [x] **Step 4: Mark checkboxes complete**

Update only steps backed by fresh command evidence. Per the user's instruction, defer Git submission until the overall approved rebuild is complete.
