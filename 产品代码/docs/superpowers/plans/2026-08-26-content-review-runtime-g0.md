# Content Review Runtime and G0 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the accepted content-review frontend to the exact current C0/C1/C2 authority and prove one isolated real-like project can reach `G0=user-reviewable` without synthesizing G0.

**Architecture:** Keep the existing content-review services and frontend projection. Add fail-closed current-authority checks at ReviewSession opening, persisted-session reuse, revision planning, and G0 evaluation; then prove the complete flow with focused real-kernel tests, including a 120-page recovery scenario.

**Tech Stack:** Python 3.11+ standard library, `unittest`, immutable SHA-256 artifact references, `ProjectKernel`, existing Node MCP/Review Bridge and React/Vitest regressions.

---

## File map

| File | Responsibility in this slice |
|---|---|
| `tests/test_v22_content_review_runtime_g0.py` | C3-only RED/GREEN and real-like end-to-end proof |
| `tests/test_v22_review_session.py` | Keep generic public Bridge lifecycle tests independent of the newly enforced content-authority precondition |
| `src/ai_ppt_studio/application/bridge/review.py` | Refuse the public content ReviewSession handoff before exact current C2 acceptance |
| `src/ai_ppt_studio/application/review_session_service.py` | Expose one authoritative publication-revision resolver shared by session creation and C3 reuse validation |
| `src/ai_ppt_studio/application/content_review/_shared.py` | Revalidate persisted current content ReviewSession revision and exact current acceptance context |
| `src/ai_ppt_studio/application/content_review/planning_service.py` | Allow revision plans only for change-request batches and require full-deck rereview scope |
| `src/ai_ppt_studio/application/gate_evaluator.py` | Revalidate current passed gate, session, batch, decision-head and immutable decision-lineage evidence before G0 readiness/confirmation |

Do not modify `widget/`, `application/visual*`, PPTX, delivery, release, installation, content-hard-gate semantics, or legacy framework production code.

### Task 1: Require exact C2 acceptance before content ReviewSession

**Files:**

- Create: `tests/test_v22_content_review_runtime_g0.py`
- Modify: `tests/test_v22_review_session.py`
- Modify: `src/ai_ppt_studio/application/bridge/review.py`
- Modify: `src/ai_ppt_studio/application/review_session_service.py`
- Modify: `src/ai_ppt_studio/application/content_review/_shared.py`

- [ ] **Step 1: Write the failing acceptance-before-session test**

Create a test module with real `ProjectKernel` helpers and this first test:

```python
class ContentReviewRuntimeG0Tests(unittest.TestCase):
    def test_content_session_requires_exact_current_c2_acceptance_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref = build_content(kernel)
            publication_revision = kernel.load().revision
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(GateBlockedError):
                dispatch_v16({
                    "operation": "open-or-resume-review-session",
                    "project_root": str(kernel.project_root),
                    "command_id": "open-before-content-acceptance",
                    "expected_revision": kernel.load().revision,
                    "review_type": "content-full-deck",
                    "target_artifact_ref": blueprint_ref,
                    "source_version": "content-v1",
                    "source_revision": publication_revision,
                    "open_policy": "foreground-if-waiting",
                })

            self.assertEqual(snapshot_bytes(kernel), frozen)
            self.assertNotIn(
                "review/session/content-full-deck", kernel.load().artifact_heads
            )
```

`snapshot_bytes()` must return the current serialized state, sorted event-file bytes, and sorted artifact-file bytes so zero-write assertions detect detached-artifact leakage as well as state changes.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v \
  tests.test_v22_content_review_runtime_g0.ContentReviewRuntimeG0Tests.test_content_session_requires_exact_current_c2_acceptance_zero_write
```

Expected: `FAIL` because the public Review Bridge handler currently creates a content session from the current Blueprint without requiring `content/acceptance`.

- [ ] **Step 3: Add the minimum content-only opening guard**

In `application/bridge/review.py::open_or_resume()`, before calling `ReviewSessionService`, inspect current C2 authority:

```python
if review_type == "content-full-deck":
    readiness = ContentHardGateService(ctx.kernel).inspect()
    if (
        readiness.get("state") != "content-user-reviewable"
        or readiness.get("blueprint_ref") != target_ref
        or readiness.get("source_version") != source_version
        or not readiness.get("acceptance_ref")
    ):
        stop = readiness.get("stop") or {}
        blocker = str(stop.get("code") or "CURRENT_CONTENT_ACCEPTANCE_REQUIRED")
        raise GateBlockedError("content-review", (blocker,))
```

Use `ctx.kernel`, import `ContentHardGateService` and `GateBlockedError`, and compare against request target/source. Do not apply this guard to `visual-professional` or to direct internal lifecycle tests.

- [ ] **Step 4: Run the focused test and adjacent ReviewSession tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v \
  tests.test_v22_content_review_runtime_g0 \
  tests.test_review_session_authoritative_revision \
  tests.test_v22_review_session
```

Expected: the new test passes and existing generic `ReviewSessionService` lifecycle tests remain unchanged.

- [ ] **Step 5: Write the failing persisted-session revision test**

After creating a valid accepted content session, commit a structurally valid replacement session at the same current slot with `revision` changed to another historical integer. Assert both projection and decision save reject it without writes:

```python
with self.assertRaises(ReviewSourceStaleError):
    ContentReviewProjectionService(kernel).project(session["review_session_id"])
with self.assertRaises(ReviewSourceStaleError):
    ContentDecisionService(kernel).save(
        command_id="save-through-forged-session-revision",
        expected_revision=kernel.load().revision,
        review_session_id=session["review_session_id"],
        source_version="content-v1",
        slide_id="S01",
        decision="approved",
        comment="",
    )
```

- [ ] **Step 6: Run the persisted-session test and verify RED**

Expected: `FAIL` because `_shared.review_context()` currently checks target/source/status but not the authoritative Blueprint publication revision.

- [ ] **Step 7: Extract and reuse the publication-revision resolver**

In `review_session_service.py`, extract the existing `_target_publication_revision` logic to a module-level function:

```python
def authoritative_target_publication_revision(
    kernel: ProjectKernel,
    state: KernelState,
    review_type: str,
    target_ref: str,
) -> int:
    slot = next(
        (
            candidate
            for candidate in SOURCE_SLOTS[review_type]
            if state.artifact_heads.get(candidate) == target_ref
        ),
        "",
    )
    if not slot:
        raise ContractValidationError(
            "Current review target has no authoritative source slot"
        )
    previous_ref = ""
    publication_revision = -1
    for revision in range(1, state.revision + 1):
        event_path = kernel.events_root / f"r{revision:08d}.json"
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
            heads = event["artifact_heads"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ContractValidationError(
                "Review target publication history is unavailable"
            ) from error
        current_ref = str(heads.get(slot) or "")
        if current_ref == target_ref and previous_ref != target_ref:
            publication_revision = revision
        previous_ref = current_ref
    if publication_revision < 0:
        raise ContractValidationError(
            "Review target publication revision cannot be resolved"
        )
    return publication_revision
```

Make the service method delegate to it. In `_shared.review_context()`, require:

```python
authoritative_revision = authoritative_target_publication_revision(
    kernel, state, "content-full-deck", blueprint_ref
)
if session["revision"] != authoritative_revision:
    raise ReviewSourceStaleError(
        str(session["revision"]), str(authoritative_revision)
    )
```

- [ ] **Step 8: Run Task 1 tests and verify GREEN**

Run the focused C3, ReviewSession, content projection, and atomicity modules. Require all to pass.

- [ ] **Step 9: Commit Task 1 precisely**

```bash
git add -- \
  产品代码/tests/test_v22_content_review_runtime_g0.py \
  产品代码/tests/test_v22_review_session.py \
  产品代码/src/ai_ppt_studio/application/bridge/review.py \
  产品代码/src/ai_ppt_studio/application/review_session_service.py \
  产品代码/src/ai_ppt_studio/application/content_review/_shared.py
git diff --cached --check
git commit -m "fix: require current content authority for review sessions"
```

### Task 2: Enforce meaningful whole-deck revision plans

**Files:**

- Modify: `tests/test_v22_content_review_runtime_g0.py`
- Modify: `src/ai_ppt_studio/application/content_review/planning_service.py`

- [ ] **Step 1: Write two failing plan-semantics tests**

Add:

```python
def test_all_approved_batch_cannot_start_revision_plan_zero_write(self) -> None:
    kernel, _blueprint_ref, session, batch_ref = reviewed_project(
        decisions={"S01": ("approved", "")}
    )
    frozen = snapshot_bytes(kernel)
    with self.assertRaises(ContractValidationError):
        ContentRevisionPlanningService(kernel).save_plan(
            command_id="reject-plan-for-all-approved",
            expected_revision=kernel.load().revision,
            batch_ref=batch_ref,
            source_version="content-v1",
            plan=revision_plan(["all"]),
        )
    self.assertEqual(snapshot_bytes(kernel), frozen)

def test_revision_plan_requires_full_deck_rereview_scope_zero_write(self) -> None:
    kernel, _blueprint_ref, session, batch_ref = reviewed_project(
        decisions={"S01": ("modify", "请调整本页")}
    )
    frozen = snapshot_bytes(kernel)
    with self.assertRaises(ContractValidationError):
        ContentRevisionPlanningService(kernel).save_plan(
            command_id="reject-partial-rereview",
            expected_revision=kernel.load().revision,
            batch_ref=batch_ref,
            source_version="content-v1",
            plan=revision_plan(["S01"]),
        )
    self.assertEqual(snapshot_bytes(kernel), frozen)
```

- [ ] **Step 2: Run both tests and verify RED**

Expected: both fail because the current service accepts an all-approved Batch and any non-empty `rereview_scope`.

- [ ] **Step 3: Add one persisted-plan semantic validator**

In `ContentRevisionPlanningService` add:

```python
@staticmethod
def _require_plan_semantics(plan: dict[str, Any], batch: dict[str, Any]) -> None:
    requested = sum(
        batch["counts"][choice]
        for choice in ("modify", "evidence", "merge-or-delete")
    )
    if requested == 0:
        raise ContractValidationError(
            "Revision plan requires at least one non-approved PageDecision"
        )
    if plan["plan"]["rereview_scope"] != ["all"]:
        raise ContractValidationError(
            "Revision plan must require complete full-deck rereview"
        )
```

Call it after normalizing a new plan and again inside `_current_plan_lineage()` after resolving a persisted plan and Batch. This prevents a direct malformed current plan artifact from bypassing change-set creation or Blueprint application.

- [ ] **Step 4: Run C3 plan tests plus current projection/atomicity tests**

Expected: all pass. Existing plan fixtures must already use a change-request Batch and `['all']`; update only tests whose old expectation conflicts with the approved v2.8 contract.

- [ ] **Step 5: Commit Task 2 precisely**

```bash
git add -- \
  产品代码/tests/test_v22_content_review_runtime_g0.py \
  产品代码/src/ai_ppt_studio/application/content_review/planning_service.py
git diff --cached --check
git commit -m "fix: require full-deck content revision plans"
```

### Task 3: Revalidate complete current evidence at G0 readiness

**Files:**

- Modify: `tests/test_v22_content_review_runtime_g0.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`

- [ ] **Step 1: Write table-driven failing G0 lineage tests**

Create an all-approved submitted project, then for each case commit one structurally valid but semantically foreign current artifact and assert `open_g0_review()` fails with identical pre/post bytes:

```python
cases = (
    ("foreign-session", forge_current_session),
    ("historical-session-revision", forge_session_revision),
    ("foreign-decision-project", forge_decision_project),
    ("foreign-decision-session", forge_decision_session),
    ("changed-slide-order", forge_decision_order),
    ("changed-title-snapshot", forge_decision_title),
    ("non-current-decision-head", replace_current_decision_head),
    ("cross-slide-supersedes-lineage", forge_decision_predecessor),
    ("failed-current-gate", replace_current_gate_and_acceptance),
)
for label, mutate in cases:
    with self.subTest(label=label):
        kernel = all_approved_submitted_project()
        mutate(kernel)
        frozen = snapshot_bytes(kernel)
        with self.assertRaises(GateBlockedError):
            PresalesContentService(kernel).open_g0_review(
                command_id=f"reject-{label}",
                expected_revision=kernel.load().revision,
            )
        self.assertEqual(snapshot_bytes(kernel), frozen)
```

Mutation helpers must create real immutable artifacts through `kernel.commit()`; do not mock validators or the Gate evaluator.

- [ ] **Step 2: Run the table and verify RED cases**

Record which cases already fail and which currently pass. Only cases that currently pass justify production changes; passing characterization cases remain as proof but are not counted as a TDD RED.

- [ ] **Step 3: Harden `_validate_g0_review_evidence()` minimally**

Use existing domain validators before semantic checks:

```python
acceptance = self._resolve(acceptance_ref, "content-acceptance")["payload"]
blueprint = validate_reading_deck_blueprint(
    self._resolve(blueprint_ref, "reading-deck-blueprint")["payload"]
)
batch = validate_content_review_batch(
    self._resolve(review_batch_ref, "content-review-batch")["payload"]
)
current_session_ref = state.review_session_ref("content-full-deck")
session = validate_review_session(
    self._resolve(current_session_ref, "review-session")["payload"],
    trusted_receipts=True,
)
```

Validate both hard-gate records and their exact Blueprint hash/sourceVersion/result. Require the current ReviewSession to match project, type, target, source, authoritative publication revision, submitted status, and Batch session id.

For each Blueprint slide require the Batch decision ref to equal the current slot head, normalize it with `validate_page_decision()`, and compare:

```python
expected_identity = {
    "project_id": state.project_id,
    "review_session_id": session["review_session_id"],
    "source_version": blueprint["source_version"],
    "reading_blueprint_ref": blueprint_ref,
    "slide_id": slide["slide_id"],
    "slide_order": slide["order"],
    "slide_title_snapshot": slide["neutral_title"],
    "status": "completed",
    "decision": "approved",
}
```

Walk `supersedes_decision_ref` to empty with a seen set and require the same immutable identity fields at every predecessor. Append stable blocker codes; do not mutate state.

- [ ] **Step 4: Run the table and all G0 tests until GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v \
  tests.test_v22_content_review_runtime_g0 \
  tests.test_v22_content_review_projection \
  tests.test_v16_content_acceptance \
  tests.test_v16_framework_discussion
```

Expected: all pass, including trusted-G0 fixture tests; no test may claim a real user confirmation occurred.

- [ ] **Step 5: Commit Task 3 precisely**

```bash
git add -- \
  产品代码/tests/test_v22_content_review_runtime_g0.py \
  产品代码/src/ai_ppt_studio/application/gate_evaluator.py
git diff --cached --check
git commit -m "fix: validate exact current evidence before G0"
```

### Task 4: Prove long-document recovery and fact separation

**Files:**

- Modify: `tests/test_v22_content_review_runtime_g0.py`

- [ ] **Step 1: Add the 120-page real-like proof**

Build a 120-page mixed Blueprint with every fifth page using `material_views=[]` and selected pages using two ordered material refs. Run both hard gates, open one content session, and assert the first projection preserves all slide and material order.

Save 60 decisions. Attempt page 61 with the pre-save stale revision and assert `RevisionConflictError` plus identical bytes. Refresh, project again, prove the first 60 decisions remain, then finish all 120 as approved and submit one Batch.

Assert:

```python
self.assertEqual(batch["slide_ids"], [f"S{i:02d}" for i in range(1, 121)])
self.assertEqual(batch["counts"]["approved"], 120)
self.assertEqual(len(batch["decision_refs"]), 120)
self.assertEqual(kernel.load().gate_status["G0"], "locked")
ready = PresalesContentService(kernel).open_g0_review(
    command_id="open-real-like-g0",
    expected_revision=kernel.load().revision,
)
self.assertEqual(ready.gate_status["G0"], "user-reviewable")
self.assertNotIn("gate/G0/confirmation", ready.artifact_heads)
```

- [ ] **Step 2: Run the long-document test**

Expected: it may already pass after Tasks 1–3. If it exposes a production defect, stop and add a separate minimal RED test for that defect before changing production code.

- [ ] **Step 3: Add fact-separation proof**

On a submitted content session assert:

- persistence is saved;
- submitting the Batch does not set Host open, Host notification, or AI received;
- wrong-kind or foreign-session receipts are zero-write failures;
- `unavailable` Host outcome and `unverified` AI outcome persist as non-success facts;
- no fixture receipt is described as real Host or AI evidence.

- [ ] **Step 4: Add legacy non-bypass proof**

Seed valid legacy framework confirmation and expansion authorization artifacts without C2 acceptance or without a C3 submitted Batch. Assert content ReviewSession opening and G0 readiness remain blocked with zero writes.

- [ ] **Step 5: Run the complete focused C3 module**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v \
  tests.test_v22_content_review_runtime_g0
```

Expected: all tests pass with an explicit assertion that the real-like project stops at `G0=user-reviewable`.

- [ ] **Step 6: Commit Task 4 precisely**

```bash
git add -- 产品代码/tests/test_v22_content_review_runtime_g0.py
git diff --cached --check
git commit -m "test: prove content review recovery and G0 readiness"
```

### Task 5: Complete slice verification and independent review

**Files:**

- Verify only; modify only when a failing test proves a C3 regression

- [ ] **Step 1: Run C0/C1/C2/C3 adjacent focused tests**

Run the new C3 module plus content contracts, chief orchestration, hard gates, repair loop, review projection/atomicity, ReviewSession, legacy content acceptance, decisions, batches, and framework discussion modules. Record exact test count and duration.

- [ ] **Step 2: Run the full Python suite**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -v
```

Expected: all tests pass.

- [ ] **Step 3: Make Node dependencies available without installing**

If `node_modules` is absent, use the already verified adjacent C2/C1 dependency directory only through a temporary worktree-local symlink. Do not run install. Record the real resolved target and remove the symlink after verification.

- [ ] **Step 4: Run typecheck and build**

```bash
npm run typecheck
npm run build
```

Expected: both exit 0. Generated tracked build output must be inspected; do not commit unrelated Widget changes.

- [ ] **Step 5: Run complete Node and Widget suites sequentially**

```bash
npm run test:node
npm run test:widget -- --reporter=dot
```

Expected: all tests pass. Do not change Widget timeouts or visual code for load-related performance variance; rerun the isolated performance test after system load falls if necessary.

- [ ] **Step 6: Run repository hygiene checks**

```bash
git diff --check
git status --short --branch
git log -6 --oneline --decorate
```

Require no unexpected generated files, no dependency symlink, no staged leftovers, and no quarantine changes.

- [ ] **Step 7: Request independent read-only code review**

Review the complete diff from `5a4cb36712d29bff911a8d4f1ddf6ad5ee4da470` to C3 HEAD against this design and the v2.8 baselines. Report `Critical`, `Important`, and `Minor` separately.

- [ ] **Step 8: Fix Critical/Important findings by a fresh TDD cycle**

For every validated finding: add a focused failing test, observe RED, apply the minimum fix, rerun focused and full relevant suites, and create a new ordinary commit. Never amend.

- [ ] **Step 9: Re-review and finalize clean HEAD**

Require `Critical=0`, `Important=0`, all final tests green, `git diff --check` clean, and worktree clean. Record separately:

```yaml
implemented: true
committed: true
verified: true
reviewed: true
worktreeClean: true
merged: false
pushed: false
released: false
installed: false
realG0Confirmed: false
userAcceptedBackend: false
```

Do not create V0 until this verified C3 HEAD exists. Creating the next stacked V0 worktree is a separate post-exit action; it must use this exact verified HEAD as its rollback parent.

## Plan self-review

- Every production change is preceded by a named failing test and an observed RED result.
- Current-source acceptance, ReviewSession revision, plan semantics, G0 lineage, long-document recovery, receipt separation, legacy non-bypass, and exit-state truthfulness each have an explicit task.
- Method and field names match the current source contracts.
- The only planned product edits are C3 backend files; Widget and visual files are verification-only.
- Exact `git add -- <paths>` is used; `git add .`, amend, merge, push, release, and install are absent.
- No step can convert fixtures or engineering success into real G0, Host/AI evidence, release, or user acceptance.
