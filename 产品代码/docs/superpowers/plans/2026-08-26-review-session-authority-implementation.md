# ReviewSession Authority Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Python Runtime ReviewSession authority contract and service on top of the existing hardened recovery implementation, including lifecycle states, independent host/AI facts, stable errors, truthful project status projection, and zero-write/replay tests.

**Architecture:** Keep `ProjectKernel` as the only source of truth and keep the existing `review/session/{review_type}` current heads, event history, trusted artifact references, revision checks, and replay fingerprints. Extend the Python domain/service/bridge boundary only; do not modify the Node typed catalog, Node Review Bridge, Widget, content-review, or visual-review implementation.

**Tech Stack:** Python 3, `unittest`, schema-3 `ProjectKernel`, Python bridge/workbench JSON error boundary, existing Node/Vitest regression scripts.

---

## 0. Execution preflight and isolated worktree

**Files:**
- Read: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/AGENTS.md`
- Read: `00-唯一研发基线索引-v1.0.md`
- Read: `01-产品需求基线-v1.0.md`
- Read: `02-系统详细设计-v1.0.md`
- Read: `03-UI设计与交互规范-v1.0.md`
- Read: `产品代码/docs/validation/2026-08-25-version-quarantine-and-recovery-baseline.md`
- Read: `产品代码/docs/superpowers/specs/2026-08-26-review-session-authority-design.md`

- [ ] **Step 1: Invoke the git-worktree skill before creating the implementation worktree**

Use `superpowers:using-git-worktrees` at execution time. Do not create the implementation worktree while this plan is still awaiting approval.

- [ ] **Step 2: Create the feature branch and linked worktree from the exact recovery HEAD**

The current recovery integration tip includes the approved design and plan documents:

```text
codex/v22-recovery-integration-20260825
72974554fcf766ce5984703162e90d4b0e317858
```

The implementation rollback boundary remains the pre-design code commit:

```text
6c458f7b0c2f81a1f85db3afea9a917a161b1124
```

Run:

```bash
git worktree add -b codex/slice-review-session-authority-20260826 \
  /Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826 \
  codex/v22-recovery-integration-20260825
```

Expected:

- the new worktree is at the exact requested path;
- its branch is `codex/slice-review-session-authority-20260826`;
- its HEAD is `72974554fcf766ce5984703162e90d4b0e317858`;
- the recovery integration worktree remains unchanged;
- the quarantine worktree remains unchanged.

- [ ] **Step 3: Record the feature worktree audit before editing**

Run in the new worktree:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git rev-parse HEAD
git status --short
git log --oneline -5
```

Expected:

- clean status;
- no untracked files introduced by this task;
- no branch switch in the quarantine checkout;
- the only source branch is `codex/v22-recovery-integration-20260825`.

- [ ] **Step 4: Run the fresh baseline gate before changing code**

From `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826/产品代码`, run:

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

Expected: each command exits 0. Record the fresh counts and exit codes. If a real source failure occurs, stop this plan and open the separately governed engineering-gate repair worktree; do not repair the failure inside 2A. Treat dependency, sandbox, loopback, or permission failures as capability evidence rather than source failures.

---

## 1. Complete the ReviewSession domain contract

**Files:**
- Modify: `产品代码/tests/test_v22_review_session.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/review/contracts.py:11-205`

- [ ] **Step 1: Add RED tests for the authoritative state sets**

Add these tests to `ReviewSessionContractTests`:

```python
def test_authoritative_statuses_and_expired_timestamp_are_valid(self) -> None:
    base = {
        "review_session_id": "session-01",
        "review_type": "content-full-deck",
        "project_id": "project-01",
        "target_artifact_ref": "artifact://reading-deck-blueprint/" + "a" * 64,
        "source_version": "content-v3",
        "revision": 17,
        "status": "ready",
        "open_policy": "notify-only",
        "host_open_status": "not-requested",
        "persistence_status": "saved",
        "host_notification_status": "not-requested",
        "ai_receipt_status": "pending",
        "created_at": NOW,
        "last_opened_at": None,
        "submitted_at": None,
    }
    for status in ("preparing", "ready", "opened", "submitted", "superseded", "expired"):
        payload = {**base, "status": status}
        if status == "opened":
            payload.update({
                "host_open_status": "opened",
                "last_opened_at": NOW,
                "host_open_receipt_ref": "artifact://review-host-open-receipt/" + "b" * 64,
            })
        if status == "submitted":
            payload["submitted_at"] = NOW
        if status == "superseded":
            payload["superseded_at"] = NOW
        if status == "expired":
            payload["expired_at"] = NOW
        validate_review_session(payload, trusted_receipts=True)

def test_expired_session_requires_expired_at(self) -> None:
    payload = valid_session_payload(status="expired")
    with self.assertRaises(ContractValidationError):
        validate_review_session(payload, trusted_receipts=True)

def test_contract_accepts_unavailable_and_unverified_facts_only_in_trusted_context(self) -> None:
    payload = valid_session_payload(
        host_open_status="unavailable",
        host_notification_status="pending",
        ai_receipt_status="unverified",
    )
    with self.assertRaises(ContractValidationError):
        validate_review_session(payload)
    validate_review_session(payload, trusted_receipts=True)

def test_review_session_persistence_is_always_saved(self) -> None:
    payload = valid_session_payload(persistence_status="failed")
    with self.assertRaises(ContractValidationError):
        validate_review_session(payload)
```

The test helper `valid_session_payload` should return a complete independent dictionary so each test can mutate it without sharing state.

- [ ] **Step 2: Run only the new contract tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session.ReviewSessionContractTests -v
```

Expected: FAIL because the current constants omit `preparing`, `expired`, `pending`, `unavailable`, `rejected`, and `unverified`, and `expired_at` is not accepted.

- [ ] **Step 3: Expand the contract constants and optional fields minimally**

In `contracts.py`, change only the contract declarations and validation branches needed by the RED tests:

```python
SESSION_STATUSES = frozenset(
    {"preparing", "ready", "opened", "submitted", "superseded", "expired"}
)
HOST_OPEN_STATUSES = frozenset(
    {"not-requested", "pending", "opened", "failed", "unavailable"}
)
HOST_NOTIFICATION_STATUSES = frozenset(
    {"not-requested", "pending", "sent", "failed", "unavailable"}
)
AI_RECEIPT_STATUSES = frozenset(
    {"pending", "received", "rejected", "unverified"}
)
OPTIONAL_FIELDS = frozenset(
    {
        "host_open_receipt_ref",
        "host_notification_receipt_ref",
        "host_notification_receipts",
        "ai_receipt_ref",
        "ai_receipts",
        "superseded_at",
        "expired_at",
    }
)
```

Keep `persistence_status == "saved"` as an invariant. Parse `expired_at` through the existing timezone-aware timestamp helper. Require `superseded_at` only for `superseded` and `expired_at` only for `expired`. Do not require receipts for failed, unavailable, rejected, or unverified facts; retain receipt requirements for opened, sent, and received.

- [ ] **Step 4: Run the contract tests and the existing ReviewSession tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session.ReviewSessionContractTests \
  tests.test_v22_review_session.ReviewSessionServiceTests -v
```

Expected: all contract and existing service tests pass. If an existing test expects the old `not-requested` initialization, leave the test unchanged until Task 2 updates the service initialization and its assertions together.

- [ ] **Step 5: Commit the contract-only result**

Run:

```bash
git add -- \
  产品代码/src/ai_ppt_studio/domains/review/contracts.py \
  产品代码/tests/test_v22_review_session.py
git diff --cached --check
git commit -m "feat: complete ReviewSession status contract"
```

Expected: the commit contains only the contract and its Python tests.

---

## 2. Add current-session lifecycle recovery

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/review_session_service.py:51-270`
- Modify: `产品代码/src/ai_ppt_studio/application/bridge/review.py:1-101`
- Modify: `产品代码/src/ai_ppt_studio/errors.py:110-155`
- Modify: `产品代码/tests/test_v22_review_session.py`

- [ ] **Step 1: Add RED tests for policy-specific initialization and incompatible current sessions**

Add tests:

```python
def test_open_policy_initializes_independent_pending_facts(self) -> None:
    _, foreground, _ = self.open_with_policy("foreground-if-waiting")
    self.assertEqual(foreground["host_open_status"], "pending")
    self.assertEqual(foreground["host_notification_status"], "not-requested")

    published = publish_source(
        self.kernel,
        command_id="source-next",
        slot="content/reading-blueprint",
        kind="reading-deck-blueprint",
        source_version="content-v4",
    )
    next_ref = published.artifact_heads["content/reading-blueprint"]
    _, background, _ = self.service.open_or_resume(
        command_id="open-v4-background",
        expected_revision=published.revision,
        review_type="content-full-deck",
        target_artifact_ref=next_ref,
        source_version="content-v4",
        source_revision=published.revision,
        open_policy="notify-only",
    )
    self.assertEqual(background["host_open_status"], "not-requested")
    self.assertEqual(background["host_notification_status"], "pending")

def test_incompatible_open_policy_does_not_create_a_second_current(self) -> None:
    first_ref, first, state = self.open_with_policy("notify-only")
    with self.assertRaises(ReviewSessionAlreadyCurrentError) as caught:
        self.service.open_or_resume(
            command_id="same-identity-different-policy",
            expected_revision=state.revision,
            review_type="content-full-deck",
            target_artifact_ref=self.source_ref,
            source_version="content-v3",
            source_revision=1,
            open_policy="foreground-if-waiting",
        )
    self.assertEqual(caught.exception.code, "REVIEW_SESSION_ALREADY_CURRENT")
    self.assertEqual(self.kernel.load(), state)
    self.assertEqual(
        self.kernel.load().artifact_heads["review/session/content-full-deck"],
        first_ref,
    )
    self.assertEqual(first["open_policy"], "notify-only")
```

Add an `open_with_policy` test helper that passes the requested policy to the existing `open_or_resume` call.

- [ ] **Step 2: Run the lifecycle RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session.ReviewSessionServiceTests.test_open_policy_initializes_independent_pending_facts \
  tests.test_v22_review_session.ReviewSessionServiceTests.test_incompatible_open_policy_does_not_create_a_second_current -v
```

Expected: FAIL because the service initializes both dimensions as `not-requested` and has no stable already-current exception.

- [ ] **Step 3: Add the stable stale/already-current exception types**

In `errors.py`, add:

```python
class ReviewSessionStaleError(AiPptError):
    def __init__(self, expected: str, actual: str) -> None:
        self.code = "REVIEW_SESSION_STALE"
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"ReviewSession source {expected} is stale; current source is {actual}"
        )

class ReviewSessionAlreadyCurrentError(AiPptError):
    code = "REVIEW_SESSION_ALREADY_CURRENT"

    def __init__(self, review_type: str, review_session_id: str) -> None:
        self.review_type = review_type
        self.review_session_id = review_session_id
        self.details = {
            "review_type": review_type,
            "review_session_id": review_session_id,
        }
        super().__init__("A compatible current ReviewSession already exists")
```

Keep the existing `ReviewSourceStaleError` unchanged for other domains. The service must use `ReviewSessionStaleError` only for session identity/source lifecycle failures.

- [ ] **Step 4: Implement policy initialization and same-identity conflict handling**

In `open_or_resume`:

```python
if current and (
    current["target_artifact_ref"],
    current["source_version"],
    current["revision"],
) == identity:
    if current["open_policy"] != open_policy:
        raise ReviewSessionAlreadyCurrentError(
            review_type, current["review_session_id"]
        )
    return current_ref, current, state

host_open_status = (
    "pending" if open_policy == "foreground-if-waiting" else "not-requested"
)
host_notification_status = (
    "pending" if open_policy == "notify-only" else "not-requested"
)
```

Use these values in the newly validated session. Preserve deterministic identity, current slot, atomic supersede, and all existing revision checks.

- [ ] **Step 5: Add RED tests for explicit expiry**

Add:

```python
def test_expire_current_detaches_current_and_preserves_history(self) -> None:
    first_ref, first, opened = self.open_with_policy("notify-only")
    expired_ref, expired, committed = self.service.expire_current(
        command_id="expire-session",
        expected_revision=opened.revision,
        review_type="content-full-deck",
    )
    self.assertEqual(expired["status"], "expired")
    self.assertEqual(expired["expired_at"], NOW)
    self.assertEqual(expired["review_session_id"], first["review_session_id"])
    self.assertNotIn(
        "review/session/content-full-deck",
        committed.artifact_heads,
    )
    self.assertNotEqual(expired_ref, first_ref)
    self.assertEqual(
        self.kernel.artifacts.resolve(
            ArtifactReference.parse(expired_ref)
        )["payload"]["status"],
        "expired",
    )
```

Inject a clock into `ReviewSessionService` only if the current implementation pattern can do so without changing unrelated callers; otherwise use a timezone-aware assertion that checks presence and parseability rather than the exact string.

- [ ] **Step 6: Implement `expire_current` as one atomic commit**

Add a service method with this signature:

```python
def expire_current(
    self,
    *,
    command_id: str,
    expected_revision: int,
    review_type: str,
) -> tuple[str, dict[str, Any], KernelState]:
```

Implementation requirements:

1. load and validate the expected revision;
2. require the current session;
3. validate the session with `status="expired"` and `expired_at`;
4. compute the immutable artifact reference before commit;
5. write it as a detached artifact;
6. remove the current slot in the same commit;
7. return the detached reference, expired payload, and committed state;
8. never mutate the old artifact in place.

- [ ] **Step 7: Expose explicit expiry through the Python review bridge**

Add `expire_review_session` in `application/bridge/review.py` and register:

```python
"expire-review-session": expire_review_session,
```

The handler must require `expected_revision` and `review_type`, call `expire_current`, and return the detached expired session plus the new snapshot without exposing raw Kernel state.

- [ ] **Step 8: Run lifecycle tests and commit**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session \
  tests.test_review_session_authoritative_revision -v
```

Expected: all existing and new lifecycle tests pass.

Commit:

```bash
git add -- \
  产品代码/src/ai_ppt_studio/application/review_session_service.py \
  产品代码/src/ai_ppt_studio/application/bridge/review.py \
  产品代码/src/ai_ppt_studio/errors.py \
  产品代码/tests/test_v22_review_session.py
git diff --cached --check
git commit -m "feat: add ReviewSession lifecycle recovery"
```

---

## 3. Persist independent host and AI outcome facts

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/review_session_service.py:141-450`
- Modify: `产品代码/src/ai_ppt_studio/domains/review/contracts.py:46-205`
- Modify: `产品代码/src/ai_ppt_studio/errors.py:110-180`
- Modify: `产品代码/src/ai_ppt_studio/application/bridge/review.py:35-101`
- Modify: `产品代码/tests/test_v22_review_session.py`

- [ ] **Step 1: Add RED tests for host-open failure facts**

Add tests using the existing `open_with_policy("foreground-if-waiting")` helper:

```python
def test_host_open_unavailable_is_persisted_without_success_receipt(self) -> None:
    _, session, state = self.open_with_policy("foreground-if-waiting")
    ref, updated, committed = self.service.record_host_open_outcome(
        command_id="host-open-unavailable",
        expected_revision=state.revision,
        review_type="content-full-deck",
        review_session_id=session["review_session_id"],
        outcome="unavailable",
        recorded_at=NOW,
    )
    self.assertEqual(updated["host_open_status"], "unavailable")
    self.assertNotIn("host_open_receipt_ref", updated)
    self.assertGreater(committed.revision, state.revision)
    self.assertEqual(
        self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"],
        updated,
    )

def test_host_open_failed_is_persisted_and_not_projected_as_opened(self) -> None:
    _, session, state = self.open_with_policy("foreground-if-waiting")
    _, updated, _ = self.service.record_host_open_outcome(
        command_id="host-open-failed",
        expected_revision=state.revision,
        review_type="content-full-deck",
        review_session_id=session["review_session_id"],
        outcome="failed",
        recorded_at=NOW,
    )
    self.assertEqual(updated["host_open_status"], "failed")
    self.assertNotEqual(updated["status"], "opened")
```

- [ ] **Step 2: Add RED tests for notification and AI outcomes**

Add:

```python
def test_notification_pending_can_be_sent_failed_or_unavailable(self) -> None:
    _, session, state = self.open_with_policy("notify-only")
    self.assertEqual(session["host_notification_status"], "pending")
    _, failed, failed_state = self.service.record_host_notification_outcome(
        command_id="notification-failed",
        expected_revision=state.revision,
        review_type="content-full-deck",
        review_session_id=session["review_session_id"],
        outcome="failed",
        recorded_at=NOW,
    )
    self.assertEqual(failed["host_notification_status"], "failed")
    _, unavailable, _ = self.service.record_host_notification_outcome(
        command_id="notification-unavailable",
        expected_revision=failed_state.revision,
        review_type="content-full-deck",
        review_session_id=failed["review_session_id"],
        outcome="unavailable",
        recorded_at=NOW,
    )
    self.assertEqual(unavailable["host_notification_status"], "unavailable")

def test_ai_unverified_and_rejected_never_become_received(self) -> None:
    _, session, state = self.open_with_policy("notify-only")
    _, unverified, unverified_state = self.service.record_ai_outcome(
        command_id="ai-unverified",
        expected_revision=state.revision,
        review_type="content-full-deck",
        review_session_id=session["review_session_id"],
        outcome="unverified",
        recorded_at=NOW,
    )
    self.assertEqual(unverified["ai_receipt_status"], "unverified")
    _, rejected, _ = self.service.record_ai_outcome(
        command_id="ai-rejected",
        expected_revision=unverified_state.revision,
        review_type="content-full-deck",
        review_session_id=session["review_session_id"],
        outcome="rejected",
        recorded_at=NOW,
    )
    self.assertEqual(rejected["ai_receipt_status"], "rejected")
```

- [ ] **Step 3: Run the outcome RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session.ReviewSessionServiceTests.test_host_open_unavailable_is_persisted_without_success_receipt \
  tests.test_v22_review_session.ReviewSessionServiceTests.test_notification_pending_can_be_sent_failed_or_unavailable \
  tests.test_v22_review_session.ReviewSessionServiceTests.test_ai_unverified_and_rejected_never_become_received -v
```

Expected: FAIL because the service only accepts success receipt references and has no outcome methods.

- [ ] **Step 4: Add explicit outcome method signatures**

Add these methods to `ReviewSessionService`:

```python
def record_host_open_outcome(
    self,
    *,
    command_id: str,
    expected_revision: int,
    review_type: str,
    review_session_id: str,
    outcome: str,
    recorded_at: str,
    receipt_ref: str = "",
) -> tuple[str, dict[str, Any], KernelState]:

def record_host_notification_outcome(
    self,
    *,
    command_id: str,
    expected_revision: int,
    review_type: str,
    review_session_id: str,
    outcome: str,
    recorded_at: str,
    receipt_ref: str = "",
) -> tuple[str, dict[str, Any], KernelState]:

def record_ai_outcome(
    self,
    *,
    command_id: str,
    expected_revision: int,
    review_type: str,
    review_session_id: str,
    outcome: str,
    recorded_at: str,
    receipt_ref: str = "",
) -> tuple[str, dict[str, Any], KernelState]:
```

Allowed outcomes:

- host open: `opened`, `failed`, `unavailable`;
- host notification: `sent`, `failed`, `unavailable`;
- AI: `received`, `rejected`, `unverified`.

For `opened`, `sent`, and `received`, reuse the existing trusted artifact validation and require the correct receipt kind. For failed, unavailable, rejected, and unverified outcomes, do not create a success receipt reference. Every outcome must still require current session identity, expected revision, and command fingerprint.

- [ ] **Step 5: Implement outcome updates through one revision-safe helper**

Use a private helper with this shape:

```python
def _commit_session_update(
    self,
    *,
    command_id: str,
    expected_revision: int,
    review_type: str,
    updated: dict[str, Any],
    event_type: str,
    command_fingerprint: str,
    detached_artifacts: tuple[tuple[str, dict[str, Any]], ...] = (),
) -> tuple[str, dict[str, Any], KernelState]:
```

The helper must:

1. validate the expected revision;
2. require the current session;
3. validate the trusted updated payload;
4. commit only the current session slot and explicitly supplied receipts;
5. preserve idempotent replay behavior;
6. return the current session reference and committed state.

Do not duplicate revision, replay, or current-session checks in three separate outcome methods.

- [ ] **Step 6: Add stable error types for outcome failures**

In `errors.py`, add error classes carrying a stable `code` and serialized details:

```python
class ReviewHostOpenUnavailableError(AiPptError):
    code = "REVIEW_HOST_OPEN_UNAVAILABLE"

class ReviewHostOpenFailedError(AiPptError):
    code = "REVIEW_HOST_OPEN_FAILED"

class ReviewAiReceiptUnverifiedError(AiPptError):
    code = "REVIEW_AI_RECEIPT_UNVERIFIED"
```

Their constructors must accept `session_ref`, `session`, and `revision`, store:

```python
self.details = {
    "session_ref": session_ref,
    "session": session,
    "revision": revision,
}
```

The service returns the persisted outcome tuple. The bridge handler raises the corresponding error only after the outcome commit has succeeded, so an external failure is both persisted as a fact and returned as a non-success envelope. Validation failures before commit still leave the project byte-identical.

- [ ] **Step 7: Expose the outcome methods through the Python bridge**

Add bridge handlers that accept `outcome`, `recorded_at`, and optional `receipt_ref`. The bridge must:

- call the matching service method;
- raise `ReviewHostOpenUnavailableError` for host-open `unavailable`;
- raise `ReviewHostOpenFailedError` for host-open `failed`;
- raise `ReviewAiReceiptUnverifiedError` for AI `unverified`;
- return the normal result for successful/safely-recorded notification, rejected AI, or success receipt facts;
- never return `ok: true` for host-open or AI unverified outcomes.

Register only Python bridge operations; do not edit Node catalog or Node Review Bridge in this task.

- [ ] **Step 8: Run outcome tests and commit**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session \
  tests.test_review_session_authoritative_revision -v
```

Expected: all service outcome, receipt binding, stale, replay, and existing tests pass.

Commit:

```bash
git add -- \
  产品代码/src/ai_ppt_studio/domains/review/contracts.py \
  产品代码/src/ai_ppt_studio/application/review_session_service.py \
  产品代码/src/ai_ppt_studio/application/bridge/review.py \
  产品代码/src/ai_ppt_studio/errors.py \
  产品代码/tests/test_v22_review_session.py
git diff --cached --check
git commit -m "feat: persist ReviewSession outcome facts"
```

---

## 4. Align project status projection and bridge error serialization

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/project_status_projection.py:11-174`
- Modify: `产品代码/src/ai_ppt_studio/workbench_bridge.py:80-163`
- Modify: `产品代码/tests/test_v22_project_status_projection.py`
- Modify: `产品代码/tests/test_v16_bridge.py`

- [ ] **Step 1: Add RED projection tests for all new facts**

Add tests:

```python
def test_failed_or_unavailable_host_open_is_blocked(self) -> None:
    row = {
        **candidate("需要你处理", "content-review"),
        "open_policy": "foreground-if-waiting",
        "host_open_status": "unavailable",
        "host_notification_status": "not-requested",
    }
    self.assertEqual(select_user_status([row], revision=7)["status"], "任务受阻")
    row["host_open_status"] = "failed"
    self.assertEqual(select_user_status([row], revision=8)["status"], "任务受阻")

def test_unverified_or_rejected_ai_receipt_is_blocked(self) -> None:
    row = {
        **candidate("AI 正在处理", "content-review"),
        "open_policy": "notify-only",
        "host_notification_status": "sent",
        "ai_receipt_status": "unverified",
    }
    self.assertEqual(select_user_status([row], revision=7)["status"], "任务受阻")
    row["ai_receipt_status"] = "rejected"
    self.assertEqual(select_user_status([row], revision=8)["status"], "任务受阻")

def test_pending_policy_facts_do_not_claim_a_completed_result(self) -> None:
    row = {
        **candidate("需要你处理", "content-review"),
        "open_policy": "notify-only",
        "host_notification_status": "pending",
        "ai_receipt_status": "pending",
    }
    self.assertEqual(select_user_status([row], revision=7)["status"], "AI 正在处理")
```

- [ ] **Step 2: Run projection RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_project_status_projection -v
```

Expected: FAIL because the current projection only checks `failed` and treats notify-only without sent notification as processing without distinguishing unavailable/AI unverified.

- [ ] **Step 3: Implement the explicit projection table**

In `ProjectStatusProjectionService._review_candidate` and `select_user_status`, apply this order:

```python
if session["host_open_status"] in {"failed", "unavailable"}:
    return blocked("专业审核宿主打开失败或不可用", "检查宿主能力并重试")
if session["host_notification_status"] in {"failed", "unavailable"}:
    return blocked("专业审核宿主通知失败或不可用", "检查通知能力并重试")
if session["ai_receipt_status"] in {"rejected", "unverified"}:
    return blocked("AI 回执被拒绝或未验证", "检查回执并重试")
if session["status"] == "submitted" and session["ai_receipt_status"] == "pending":
    return processing("审核已提交，等待 AI 接收回执", "等待 AI 接收回执")
if session["open_policy"] == "notify-only":
    if session["host_notification_status"] == "sent":
        return result("审核成果已保存并已通知", "打开审核成果")
    return processing("审核成果已保存，等待宿主通知", "发送成果可查看通知")
if session["host_open_status"] == "pending":
    return needs_user("审核已准备，等待当前用户打开", "打开或继续审核")
return needs_user("专业审核成果已保存", "完成专业审核")
```

Keep the existing global priority order and current revision binding. Do not add new user-facing status names.

- [ ] **Step 4: Add RED bridge error boundary tests**

In `test_v16_bridge.py`, invoke the public workbench boundary with a stale session and with an outcome error. Assert:

```python
self.assertFalse(payload["ok"])
self.assertEqual(payload["error"]["code"], "REVIEW_SESSION_STALE")
self.assertIn("details", payload["error"])
```

For an already-persisted host-open unavailable outcome, assert the error code is `REVIEW_HOST_OPEN_UNAVAILABLE` and the details contain `session_ref`, `session`, and `revision`.

- [ ] **Step 5: Run bridge RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v16_bridge -v
```

Expected: FAIL because `workbench_bridge._error_payload` currently maps these exceptions to generic validation or internal errors.

- [ ] **Step 6: Implement stable workbench serialization**

In `workbench_bridge.py`, add stable branches before the generic validation branch:

```python
if isinstance(exc, ReviewSessionStaleError):
    return 2, {
        "ok": False,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": {
                "expected": exc.expected,
                "actual": exc.actual,
            },
        },
    }
if isinstance(exc, ReviewSessionAlreadyCurrentError):
    return 2, {
        "ok": False,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        },
    }
if isinstance(
    exc,
    (
        ReviewHostOpenUnavailableError,
        ReviewHostOpenFailedError,
        ReviewAiReceiptUnverifiedError,
    ),
):
    return 2, {
        "ok": False,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        },
    }
```

Import these classes explicitly. Keep `ReviewSourceStaleError -> REVIEW_SOURCE_STALE` unchanged for non-ReviewSession flows.

- [ ] **Step 7: Run projection, bridge, and full Python tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_project_status_projection \
  tests.test_v22_review_session \
  tests.test_review_session_authoritative_revision \
  tests.test_v16_bridge
```

Expected: all focused Python tests pass.

- [ ] **Step 8: Commit the projection and error-boundary result**

Run:

```bash
git add -- \
  产品代码/src/ai_ppt_studio/application/project_status_projection.py \
  产品代码/src/ai_ppt_studio/workbench_bridge.py \
  产品代码/tests/test_v22_project_status_projection.py \
  产品代码/tests/test_v16_bridge.py
git diff --cached --check
git commit -m "feat: expose truthful ReviewSession status errors"
```

---

## 5. Verify the complete 2A boundary

**Files:**
- Read-only verification: all files changed by Tasks 1-4
- Read-only verification: `产品代码/mcp/`
- Read-only verification: `产品代码/widget/`
- Read-only verification: quarantine worktree

- [ ] **Step 1: Run the full Python regression**

Run:

```bash
cd /Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826/产品代码
npm run test:python
```

Expected: exit 0. Record the fresh passed/failed counts.

- [ ] **Step 2: Run the cross-layer engineering gate**

Run serially:

```bash
npm run typecheck
npm run test:node
npm run test:widget
npm run build
```

Expected: all exit 0. These are regression evidence only; do not describe them as real host or product acceptance.

- [ ] **Step 3: Verify invalid operations are byte-level zero-write**

Create a temporary schema-3 project in a Python test or a one-off read-only verification script. For a current session:

1. save `kernel/state.json` bytes;
2. save the current event directory listing;
3. invoke a stale source revision, wrong session ID, wrong receipt kind, and incompatible duplicate open;
4. compare state bytes, revision, current head, and event listing;
5. assert all are unchanged.

Use the existing test pattern:

```python
before_bytes = (project_root / "kernel" / "state.json").read_bytes()
before_state = kernel.load()
before_events = sorted(kernel.events_root.glob("r*.json"))
with self.assertRaises(ContractValidationError):
    service.open_or_resume(...)
self.assertEqual((project_root / "kernel" / "state.json").read_bytes(), before_bytes)
self.assertEqual(kernel.load(), before_state)
self.assertEqual(sorted(kernel.events_root.glob("r*.json")), before_events)
```

- [ ] **Step 4: Verify failure facts are persisted without success claims**

In a temporary project:

1. open a `foreground-if-waiting` session;
2. record host-open `unavailable`;
3. assert a new revision and `host_open_status="unavailable"`;
4. call the public bridge boundary;
5. assert `ok=false`, `code=REVIEW_HOST_OPEN_UNAVAILABLE`, and no `host_open_receipt_ref`;
6. repeat for AI `unverified`;
7. assert `ai_receipt_status="unverified"` and no `received` claim.

- [ ] **Step 5: Verify exact source scope**

Run:

```bash
git status --short
git diff --check
git diff --name-only codex/v22-recovery-integration-20260825...HEAD
```

Expected changed files are limited to:

```text
产品代码/src/ai_ppt_studio/domains/review/contracts.py
产品代码/src/ai_ppt_studio/application/review_session_service.py
产品代码/src/ai_ppt_studio/application/project_status_projection.py
产品代码/src/ai_ppt_studio/application/bridge/review.py
产品代码/src/ai_ppt_studio/errors.py
产品代码/src/ai_ppt_studio/workbench_bridge.py
产品代码/tests/test_v22_review_session.py
产品代码/tests/test_review_session_authoritative_revision.py
产品代码/tests/test_v22_project_status_projection.py
产品代码/tests/test_v16_bridge.py
```

If any `mcp/`, `widget/`, content-review, visual-review, or baseline file appears, stop and remove the unapproved scope through a new user-approved decision; do not silently continue.

- [ ] **Step 6: Verify the quarantine worktree was not modified**

Run:

```bash
git -C /Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app \
  status --short
git -C /Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app \
  branch --show-current
git -C /Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app \
  rev-parse HEAD
```

Expected:

```text
branch: codex/quarantine-mixed-worktree-20260825
HEAD: 8c794fa85f015c1afa9c3db2f9145e6a749ed952
status: ?? .superpowers/ ?? .workbuddy/ ?? 分享材料/
```

Do not clean or stage those existing user-owned files.

- [ ] **Step 7: Run the final feature-worktree audit**

Run:

```bash
git status --short
git log --oneline --decorate -8
git diff HEAD~4 HEAD --check
git worktree list --porcelain
```

Expected:

- feature worktree is clean;
- all implementation commits are present;
- no merge commit was introduced;
- the feature branch still points to its own commits;
- recovery integration HEAD has not moved;
- no push occurred.

---

## 6. Handoff and integration gate

- [ ] **Step 1: Report separate delivery states**

Report, without conflation:

```text
已设计：b00f8945...
已计划：the plan commit
已实现：feature commits only after code work
已验证：fresh focused/full regression evidence
已集成：否，等待用户授权
已发布：否
已验收：否
```

- [ ] **Step 2: Do not merge or push**

Stop at the feature branch after verification. Do not run `git merge`, `git rebase`, `git push`, `git reset --hard`, `git clean`, or `git commit --amend`.

- [ ] **Step 3: Request explicit integration authorization**

Ask the user whether to fast-forward the recovery integration branch from the verified feature branch. Only after explicit authorization may the integration worktree move from `6c458f7b...` to the feature branch tip.
