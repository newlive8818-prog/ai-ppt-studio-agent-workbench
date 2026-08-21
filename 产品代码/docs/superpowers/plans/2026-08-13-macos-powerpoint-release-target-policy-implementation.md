# macOS PowerPoint Release Target Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed four-target v1.6 Gate contract with one project-bound release-target policy whose current required target is only macOS Microsoft PowerPoint, while preserving WPS/Windows profiles as deferred future capabilities and preserving all historical artifacts.

**Architecture:** Keep all four desktop profiles in the presentation domain, add an immutable `ReleaseTargetPolicy` artifact as the single source for required and deferred targets, and make project creation, G2/G4 calculation, context compilation, projections, Skill guidance, and UI consume that policy. Existing projects migrate through one revision-safe public command; the current real project keeps its formal macOS PowerPoint evidence and recalculates G2 without fabricating WPS or Windows results.

**Tech Stack:** Python 3 schema-3 runtime and `unittest`; Node.js MCP SDK and `node:test`; React 19, TypeScript, Vitest and Testing Library; Markdown authoritative baselines; JSON acceptance ledger; AI PPT Studio MCP; real macOS Microsoft PowerPoint desktop evidence.

---

## Implementation guardrails

- Work from the Git root `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`; run source tests from `产品代码/`.
- The worktree already contains unrelated Browser, baseline, Skill, Widget, ledger, and validation changes. Before editing every overlapping file, run `git diff --` followed by that file's exact repository-relative path, preserve all current hunks, and stage only the paths or hunks owned by the current task.
- Never use `git reset`, `git checkout --`, `git clean`, or broad staging such as `git add .`.
- Do not edit project state JSON directly. The real project at `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-final-real-acceptance-proposal-only` may change only through the installed schema-3 runtime/MCP and `expectedRevision`.
- Do not touch the old real project `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案`.
- Do not build the complete 12-page PPTX before G3. Do not record G2 until the current authorized heads and policy-bound acceptance refs match exactly.
- Keep the strict ledger at `37/104` until stable requirement IDs have complete proof kinds under the newly approved baseline.
- Preserve `TargetRenderEvidence` validation strength: formal desktop identity, real application/version, fonts, before/after PPTX hash, export, per-page images, per-slide four-door checks, reviewer attestation, timezone, and non-simulation proof eligibility remain mandatory.

## File responsibility map

### New files

- `产品代码/src/ai_ppt_studio/domains/presentation/release_policy.py`: immutable policy schema, current default policy, supported/required/deferred target helpers.
- `产品代码/src/ai_ppt_studio/application/release_policy_service.py`: project creation payload, revision-safe policy binding, policy resolution, and Gate invalidation rules.
- `产品代码/tests/test_release_target_policy.py`: pure domain contract and target-matrix tests.
- `产品代码/tests/test_v16_release_policy_service.py`: creation, migration, idempotency, revision conflict, and downstream Gate invalidation tests.

### Existing files with focused changes

- Root baselines `00-唯一研发基线索引-v1.0.md`, `01-产品需求基线-v1.0.md`, `02-系统详细设计-v1.0.md`, and `03-UI设计与交互规范-v1.0.md`: replace current four-target release requirements with the approved policy model while preserving historical decisions as historical.
- `产品代码/src/ai_ppt_studio/domains/presentation/targets.py`: distinguish supported profiles from policy-required targets; parameterize matrix validation.
- `产品代码/src/ai_ppt_studio/application/project_service.py`: bind the current default policy in the same project-creation transaction.
- `产品代码/src/ai_ppt_studio/application/v16_bridge.py` and `产品代码/mcp/server.mjs`: expose one revision-safe policy management command/tool.
- `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`, `visual_service.py`, `delivery_service.py`, `gate_confirmation.py`, and `context_compiler.py`: consume the same resolved policy for G2/G3/G4 lineage and target task context.
- `产品代码/src/ai_ppt_studio/domains/visual/contracts.py` and `domains/delivery/contracts.py`: validate policy-bound target lists and package lineage.
- `产品代码/src/ai_ppt_studio/application/workspace_projection.py`, `review_service.py`, and `v16_bridge.py`: project required and deferred rows without inventing compatibility.
- `产品代码/widget/src/types.ts`, `components/CompactWorkspace.tsx`, `components/review/ReviewDocumentSections.tsx`, `ProfessionalReviewApp.tsx`, fixtures, and tests: render current required/deferred policy state.
- `产品代码/scripts/acceptance/verify_target_evidence.py` and `verify_release.py`: retain per-profile validation but calculate completeness from the current policy.
- `产品代码/skills/ai-ppt-studio/SKILL.md` and its presentation/target references: instruct the Agent to read policy before G2/G4 and prohibit ad-hoc scope reduction.
- `产品代码/requirements/v1.6-acceptance-ledger.json`, its authoritative numbered source requirements, and `产品代码/docs/validation/2026-08-11-v16-final-acceptance.md`: preserve 104 stable IDs and truthfully rebase proof contracts.

## Task 1: Synchronize the four authoritative baselines

**Files:**

- Modify: `00-唯一研发基线索引-v1.0.md`
- Modify: `01-产品需求基线-v1.0.md`
- Modify: `02-系统详细设计-v1.0.md`
- Modify: `03-UI设计与交互规范-v1.0.md`
- Reference: `产品代码/docs/superpowers/specs/2026-08-13-macos-powerpoint-release-target-policy-design.md`

- [ ] **Step 1: Audit existing overlapping edits**

Run from the Git root:

```bash
git diff -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
rg -n "四目标|macos-wps|windows-powerpoint|windows-wps|requiredTargetProfiles|PlatformCompatibilityStatus" 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
```

Expected: current Browser/sidecar changes remain visible; all active fixed-four-target statements are enumerated before editing.

- [ ] **Step 2: Update the baseline decision and status text**

Use `apply_patch` to add the 2026-08-13 confirmed decision to all affected decision logs and replace active requirements with these exact meanings:

```markdown
- 当前 v1.6 发布策略仅强制 `macos-powerpoint`（macOS 桌面版 Microsoft PowerPoint）。
- `macos-wps`、`windows-powerpoint`、`windows-wps` 延期，不阻断当前 G2/G4，也不构成通过、失败或兼容声明。
- 系统继续识别四种目标 profile；`ReleaseTargetPolicy.required_target_ids` 是当前 Gate 的唯一必需目标来源。
- 开发预检不能替代当前策略中任一必需目标的真实桌面证据。
```

In the PRD numbered acceptance sections, preserve requirement count and numbering while replacing “固定四目标” with “当前发布策略中的全部必需目标”. In SDD define `ReleaseTargetPolicy`; in UI replace fixed four-row language with required and deferred sections. Keep 2026-08-08 four-target statements in history, marked as superseded by the 2026-08-13 confirmed decision.

- [ ] **Step 3: Verify baseline links, prototype references, isolation, and state labels**

Run:

```bash
rg -o '\]\(\./[^)#]+' 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
find 产品代码/prototypes -maxdepth 1 -type f -print
rg -n "已确认|延期|待验证|待确认|AI-PPT-Workspace|PPT  web app" 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
git diff --check -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
```

Expected: referenced prototype files exist, product/source/runtime/Web spaces remain distinct, and deferred targets are never labeled passed.

- [ ] **Step 4: Run the checked-in ledger source-consistency test and observe the expected failure**

Run from `产品代码/`:

```bash
python3 -m unittest tests.test_acceptance_ledger.AcceptanceLedgerTests.test_checked_in_ledger_matches_authoritative_sources -v
```

Expected: FAIL because authoritative requirement text changed but the generated ledger has not yet been refreshed. This failure is intentionally closed in Task 9.

- [ ] **Step 5: Commit only baseline changes**

```bash
git add -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md
git diff --cached --check
git commit -m "docs: adopt macOS PowerPoint release target policy"
```

## Task 2: Define ReleaseTargetPolicy and parameterized evidence matrices

**Files:**

- Create: `产品代码/src/ai_ppt_studio/domains/presentation/release_policy.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/presentation/targets.py`
- Create: `产品代码/tests/test_release_target_policy.py`
- Modify: `产品代码/tests/test_target_evidence_matrix.py`

- [ ] **Step 1: Write failing policy and matrix tests**

Add tests with these concrete assertions:

```python
import unittest

from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    SUPPORTED_TARGET_IDS,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.domains.presentation.targets import (
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.errors import GateBlockedError


class ReleaseTargetPolicyTests(unittest.TestCase):
    def test_current_policy_requires_only_macos_powerpoint(self) -> None:
        policy = ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY)
        self.assertEqual(policy.required_target_ids, ("macos-powerpoint",))
        self.assertEqual(
            policy.deferred_target_ids,
            ("macos-wps", "windows-powerpoint", "windows-wps"),
        )
        self.assertEqual(
            policy.compatibility_claim_scope, policy.required_target_ids
        )

    def test_policy_partitions_every_supported_profile(self) -> None:
        policy = ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY)
        self.assertTrue(
            set(policy.required_target_ids).isdisjoint(policy.deferred_target_ids)
        )
        self.assertEqual(
            set(policy.required_target_ids + policy.deferred_target_ids),
            set(SUPPORTED_TARGET_IDS),
        )

class TargetEvidenceMatrixTests(unittest.TestCase):
    def test_single_required_target_forms_complete_matrix(self) -> None:
        item = evidence("macos-powerpoint")
        matrix = validate_required_targets([item], ("macos-powerpoint",))
        self.assertEqual(matrix.target_ids, ("macos-powerpoint",))

    def test_deferred_evidence_cannot_replace_required_target(self) -> None:
        with self.assertRaises(GateBlockedError):
            validate_required_targets(
                [evidence("macos-wps")], ("macos-powerpoint",)
            )
```

Place `ReleaseTargetPolicyTests` and its policy imports in the new `test_release_target_policy.py`. Place the two matrix methods in the existing `TargetEvidenceMatrixTests` class in `test_target_evidence_matrix.py`, reusing that file's existing `evidence()` helper and existing `TargetRenderEvidence`/`GateBlockedError` imports; do not duplicate the helper across files.

Also test duplicate IDs, overlap, incomplete partition, empty required list, invalid status/time, mixed hashes, failed required evidence, and legacy WPS/Windows evidence parsing.

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
python3 -m unittest tests.test_release_target_policy tests.test_target_evidence_matrix -v
```

Expected: FAIL with missing `release_policy` module or the old fixed matrix signature.

- [ ] **Step 3: Implement the pure policy contract**

Create `release_policy.py` with the following public surface:

```python
SUPPORTED_TARGET_IDS = (
    "macos-powerpoint",
    "macos-wps",
    "windows-powerpoint",
    "windows-wps",
)

CURRENT_RELEASE_TARGET_POLICY = {
    "policy_id": "v1.6-macos-powerpoint",
    "policy_version": "1.0",
    "status": "active",
    "required_target_ids": ["macos-powerpoint"],
    "deferred_target_ids": [
        "macos-wps",
        "windows-powerpoint",
        "windows-wps",
    ],
    "compatibility_claim_scope": ["macos-powerpoint"],
    "effective_at": "2026-08-13T00:00:00+08:00",
    "decision_source": "explicit-user-confirmation",
    "rationale": "v1.6 当前先保证 macOS Microsoft PowerPoint；WPS 和 Windows 延期。",
}

@dataclass(frozen=True)
class ReleaseTargetPolicy:
    policy_id: str
    policy_version: str
    status: str
    required_target_ids: tuple[str, ...]
    deferred_target_ids: tuple[str, ...]
    compatibility_claim_scope: tuple[str, ...]
    effective_at: str
    decision_source: str
    rationale: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ReleaseTargetPolicy":
        policy = cls(
            policy_id=str(payload.get("policy_id") or ""),
            policy_version=str(payload.get("policy_version") or ""),
            status=str(payload.get("status") or ""),
            required_target_ids=tuple(payload.get("required_target_ids") or ()),
            deferred_target_ids=tuple(payload.get("deferred_target_ids") or ()),
            compatibility_claim_scope=tuple(
                payload.get("compatibility_claim_scope") or ()
            ),
            effective_at=str(payload.get("effective_at") or ""),
            decision_source=str(payload.get("decision_source") or ""),
            rationale=str(payload.get("rationale") or ""),
        )
        policy.validate()
        return policy

    def as_payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "status": self.status,
            "required_target_ids": list(self.required_target_ids),
            "deferred_target_ids": list(self.deferred_target_ids),
            "compatibility_claim_scope": list(self.compatibility_claim_scope),
            "effective_at": self.effective_at,
            "decision_source": self.decision_source,
            "rationale": self.rationale,
        }
```

Implement `validate()` so it rejects an inactive or unidentified policy, duplicate or unsupported IDs, an empty required set, overlap or incomplete partition of `SUPPORTED_TARGET_IDS`, a compatibility scope different from the required sequence, a missing rationale/decision source, and an `effective_at` value that `datetime.fromisoformat()` cannot parse with non-null `tzinfo`. The pure domain object must not read project state.

- [ ] **Step 4: Parameterize target evidence validation**

In `targets.py`:

- validate every individual `TargetRenderEvidence.target_id` against `SUPPORTED_TARGET_IDS`;
- change `validate_required_targets(evidence, required_target_ids)` to reject an empty required tuple, duplicate evidence, missing required rows, failed required rows, extra deferred rows in the Gate matrix, and mixed hashes;
- return the explicit required tuple in `TargetEvidenceMatrix.target_ids`;
- remove fixed-four wording from docstrings without weakening individual evidence checks.

- [ ] **Step 5: Run focused and legacy parsing tests**

```bash
python3 -m unittest tests.test_release_target_policy tests.test_target_evidence_matrix tests.test_v16_target_evidence_import -v
```

Expected: PASS; `windows-wps` evidence still parses, while the current complete matrix contains only `macos-powerpoint`.

- [ ] **Step 6: Commit the domain contract**

```bash
git add -- 产品代码/src/ai_ppt_studio/domains/presentation/release_policy.py 产品代码/src/ai_ppt_studio/domains/presentation/targets.py 产品代码/tests/test_release_target_policy.py 产品代码/tests/test_target_evidence_matrix.py
git diff --cached --check
git commit -m "feat: add release target policy contract"
```

## Task 3: Bind policy on project creation and migrate existing projects safely

**Files:**

- Create: `产品代码/src/ai_ppt_studio/application/release_policy_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/project_service.py`
- Create: `产品代码/tests/test_v16_release_policy_service.py`
- Modify: `产品代码/tests/test_v16_project_service.py`

- [ ] **Step 1: Write failing creation and migration tests**

Add these methods to a `unittest.TestCase` using the repository's existing temporary-project fixture and service setup:

```python
def test_new_project_binds_manifest_and_policy_in_revision_one(self) -> None:
    kernel = self.project_service.create_project(
        "Policy test", project_id="policy-test"
    )
    state = kernel.load()
    self.assertEqual(state.revision, 1)
    self.assertTrue(
        state.artifact_heads["project/manifest"].startswith(
            "artifact://project-manifest/"
        )
    )
    self.assertTrue(
        state.artifact_heads["release/target-policy"].startswith(
            "artifact://release-target-policy/"
        )
    )

def test_existing_project_policy_binding_is_revision_safe_and_idempotent(self) -> None:
    ref, migrated = self.policy_service.bind_current_policy("bind-policy", 1)
    self.assertEqual(migrated.revision, 2)
    self.assertEqual(migrated.artifact_heads["release/target-policy"], ref)
    same_ref, same_state = self.policy_service.bind_current_policy(
        "bind-policy", 1
    )
    self.assertEqual(same_ref, ref)
    self.assertEqual(same_state.revision, 2)

def test_policy_change_reopens_g2_and_locks_downstream(self) -> None:
    current_revision = self.kernel.load().revision
    changed = self.policy_service.bind_policy(
        "expand-policy", current_revision, self.four_target_payload
    )[1]
    self.assertEqual(changed.gate_status["G2"], "open")
    self.assertEqual(changed.gate_status["G3"], "locked")
    self.assertEqual(changed.gate_status["G4"], "locked")
```

Also cover invalid policy rejection without revision growth, revision conflict, no direct state mutation, and preservation of historical artifact heads.

- [ ] **Step 2: Run the tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_release_policy_service tests.test_v16_project_service -v
```

Expected: FAIL because the service/head does not exist and project creation only writes the manifest.

- [ ] **Step 3: Implement project-bound policy service**

Implement:

```python
class ReleaseTargetPolicyService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def current(self) -> tuple[str, ReleaseTargetPolicy]:
        """Resolve and validate the current release/target-policy artifact head."""

    def bind_current_policy(
        self, command_id: str, expected_revision: int
    ) -> tuple[str, KernelState]:
        """Bind CURRENT_RELEASE_TARGET_POLICY through bind_policy()."""

    def bind_policy(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> tuple[str, KernelState]:
        """Commit one validated immutable policy and governed Gate mutation."""
```

`current()` must read `state.artifact_heads["release/target-policy"]`, raise `RELEASE_TARGET_POLICY_MISSING` when absent, parse it with `ArtifactReference`, require kind `release-target-policy`, resolve it through the current kernel artifact store, then return the exact ref with `ReleaseTargetPolicy.from_payload(resolved["payload"])`. `bind_current_policy()` passes the checked-in current payload to `bind_policy()`. `bind_policy()` validates before committing, returns the existing ref/state without revision growth when the same command is retried, commits artifact kind `release-target-policy` plus event `release.target-policy-bound`, and—when policy identity changes after G2 passed—uses the existing governed G2 reopen mutation to set G2 open and G3/G4 locked in that same transaction.

- [ ] **Step 4: Bind the default policy in project creation**

Modify the existing `project.created` commit so its `artifact_updates` contains both:

```python
"project/manifest": ("project-manifest", manifest_payload),
"release/target-policy": (
    "release-target-policy",
    ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY).as_payload(),
),
```

Project creation must remain exactly one revision and one atomic event.

- [ ] **Step 5: Run creation, migration, kernel, and recovery tests**

```bash
python3 -m unittest tests.test_v16_release_policy_service tests.test_v16_project_service tests.test_v16_kernel tests.test_v16_delivery_recovery -v
```

Expected: PASS; no historical artifact is overwritten.

- [ ] **Step 6: Commit the service and project migration behavior**

```bash
git add -- 产品代码/src/ai_ppt_studio/application/release_policy_service.py 产品代码/src/ai_ppt_studio/application/project_service.py 产品代码/tests/test_v16_release_policy_service.py 产品代码/tests/test_v16_project_service.py
git diff --cached --check
git commit -m "feat: bind release policy to schema3 projects"
```

## Task 4: Expose one revision-safe policy management tool

**Files:**

- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `产品代码/mcp/server.mjs`
- Modify: `产品代码/tests/test_v16_bridge.py`
- Modify: `产品代码/tests/mcp-server.test.mjs`

- [ ] **Step 1: Write failing bridge and MCP tests**

Add a Python bridge test for operation `set-release-target-policy` with `expected_revision`, and a Node MCP test for tool `set_ai_ppt_release_target_policy`. Assert the public input is deliberately narrow:

```js
{
  projectRoot,
  expectedRevision,
  policyId: "v1.6-macos-powerpoint"
}
```

The tool must reject arbitrary required-target arrays. Only a policy ID known to the runtime may be activated through the public MCP; this prevents an Agent from inventing an ad-hoc skip policy.

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_bridge -v
node --test tests/mcp-server.test.mjs
```

Expected: FAIL with unsupported operation/tool.

- [ ] **Step 3: Add the Python bridge operation**

Dispatch `set-release-target-policy` to:

```python
ReleaseTargetPolicyService(kernel).bind_current_policy(
    _command_id(operation, request),
    int(request["expected_revision"]),
)
```

Require `policy_id == "v1.6-macos-powerpoint"`; return `artifact_ref` and the refreshed snapshot.

- [ ] **Step 4: Add the public MCP tool**

Register `set_ai_ppt_release_target_policy` with a Zod schema containing `projectRoot`, nonnegative `expectedRevision`, and literal `policyId`. Its description must say it is a product-version migration command, not a per-project platform-skip preference.

- [ ] **Step 5: Run bridge and Node tests**

```bash
python3 -m unittest tests.test_v16_bridge -v
node --test tests/mcp-server.test.mjs
```

Expected: PASS; a revision conflict returns the existing conflict code, and a repeated command identity is idempotent.

- [ ] **Step 6: Commit the public migration path**

```bash
git add -- 产品代码/src/ai_ppt_studio/application/v16_bridge.py 产品代码/mcp/server.mjs 产品代码/tests/test_v16_bridge.py 产品代码/tests/mcp-server.test.mjs
git diff --cached --check
git commit -m "feat: expose release target policy migration"
```

## Task 5: Make visual G2 and G3 lineage policy-bound

**Files:**

- Modify: `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `产品代码/src/ai_ppt_studio/application/visual_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/gate_confirmation.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/visual/contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Modify: `产品代码/tests/test_v16_visual_gates.py`
- Modify: `产品代码/tests/test_v16_visual_review.py`
- Modify: `产品代码/tests/test_v16_visual_contracts.py`
- Modify: `产品代码/tests/test_context_compiler.py`
- Modify: `产品代码/tests/v16_visual_fixtures.py`

- [ ] **Step 1: Write failing single-target G2 tests**

Change fixtures to bind the current policy and add only `macos-powerpoint` as required evidence. Tests must assert:

```python
with self.assertRaises(GateBlockedError):
    visual.record_g2("g2-without-mac", revision)

mac_ref = visual.register_target_render_evidence(
    "mac-target", revision, rich_target_payload(visual, "macos-powerpoint", refs)
)
passed = visual.record_g2("g2-with-mac", revision + 1)
self.assertEqual(passed.gate_status["G2"], "passed")
self.assertNotIn("visual/target-evidence/G2/macos-wps", passed.artifact_heads)
```

Add negative tests proving deferred WPS evidence cannot substitute for macOS PowerPoint, G2 evidence must bind the current policy ref, and the G3 visual-contract lineage freezes that policy ref plus the required evidence refs only.

- [ ] **Step 2: Run focused visual tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_visual_gates tests.test_v16_visual_review tests.test_v16_visual_contracts tests.test_context_compiler -v
```

Expected: FAIL because the code still loops over fixed `REQUIRED_TARGET_IDS`.

- [ ] **Step 3: Resolve policy once per visual operation**

In `GateEvaluator.pass_g2()` and VisualService publication code:

```python
policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
required_ids = policy.required_target_ids
target_refs = {
    target_id: state.artifact_heads.get(
        f"visual/target-evidence/G2/{target_id}", ""
    )
    for target_id in required_ids
}
```

Call `validate_required_targets(evidence, required_ids)`. Add `policy_ref` to the exact Gate evidence refs and persist `release_target_policy_ref`, `required_target_ids`, and `deferred_target_ids` in the visual-contract publication payload. Do not include deferred evidence in the Gate acceptance set.

- [ ] **Step 4: Make visual contracts and G3 confirmation policy-aware**

Allow deck/visual contract target arrays to contain the policy-required target sequence rather than all supported profiles. In G3 confirmation, compare frozen policy and target refs with the current policy/head; return `TARGET_POLICY_STALE` if they differ.

- [ ] **Step 5: Compile required and deferred targets into Agent context**

Replace fixed context labels such as `internal-binary-four-target` with policy-neutral labels and include:

```json
{
  "release_target_policy_ref": policy_ref,
  "required_target_ids": ["macos-powerpoint"],
  "deferred_target_ids": ["macos-wps", "windows-powerpoint", "windows-wps"]
}
```

The target-render task must instruct the role to verify only required targets and never claim deferred compatibility.

- [ ] **Step 6: Run all visual and context tests**

```bash
python3 -m unittest tests.test_v16_visual_gates tests.test_v16_visual_review tests.test_v16_visual_contracts tests.test_context_compiler tests.test_v16_agent_governance -v
```

Expected: PASS; G2 acceptance refs contain the policy, two review refs, design/contract/anchor refs, and one macOS PowerPoint evidence ref.

- [ ] **Step 7: Commit G2/G3 policy lineage**

```bash
git add -- 产品代码/src/ai_ppt_studio/application/gate_evaluator.py 产品代码/src/ai_ppt_studio/application/visual_service.py 产品代码/src/ai_ppt_studio/application/gate_confirmation.py 产品代码/src/ai_ppt_studio/domains/visual/contracts.py 产品代码/src/ai_ppt_studio/context_compiler.py 产品代码/tests/test_v16_visual_gates.py 产品代码/tests/test_v16_visual_review.py 产品代码/tests/test_v16_visual_contracts.py 产品代码/tests/test_context_compiler.py 产品代码/tests/v16_visual_fixtures.py
git diff --cached --check
git commit -m "feat: evaluate visual gates from release policy"
```

## Task 6: Make delivery G4 policy-bound

**Files:**

- Modify: `产品代码/src/ai_ppt_studio/application/delivery_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/delivery/contracts.py`
- Modify: `产品代码/tests/test_v16_delivery_g4.py`
- Modify: `产品代码/tests/test_v16_delivery_recovery.py`
- Modify: `产品代码/tests/test_v16_final_acceptance_verifier.py`
- Modify: `产品代码/tests/v16_delivery_fixtures.py`

- [ ] **Step 1: Write failing G4 policy tests**

Update delivery fixtures to build a final PPTX with only the required `macos-powerpoint` G4 target evidence. Add tests that require:

- missing/failed macOS PowerPoint blocks delivery readiness;
- missing WPS/Windows does not block;
- font/platform report has `targets == ["macos-powerpoint"]`, three `deferred_targets`, and the current policy ref;
- delivery package binds policy ref, final PPTX hash, exact required target refs, report, and build;
- G2 anchor evidence cannot be reused as G4 final evidence;
- policy change after package creation makes package and G4 confirmation stale.

- [ ] **Step 2: Run delivery tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_delivery_g4 tests.test_v16_delivery_recovery tests.test_v16_final_acceptance_verifier -v
```

Expected: FAIL on fixed-four loops and report validation.

- [ ] **Step 3: Resolve policy for G4 evidence and packages**

In DeliveryService and GateEvaluator, resolve the same `release/target-policy` head. Build `target_refs` only from `required_target_ids`, validate them against the final build SHA-256, and require the font/platform report payload:

```json
{
  "release_target_policy_ref": policy_ref,
  "targets": ["macos-powerpoint"],
  "deferred_targets": [
    "macos-wps",
    "windows-powerpoint",
    "windows-wps"
  ]
}
```

Persist the same policy ref in `delivery-package` and require it in G4 user-reviewable/confirmation lineage.

- [ ] **Step 4: Rename policy-neutral blockers**

Replace `four-target-evidence-incomplete-or-failed` with `required-target-evidence-incomplete-or-failed`. Keep old event/artifact payloads readable; only new projections use the neutral blocker.

- [ ] **Step 5: Run delivery and recovery tests**

```bash
python3 -m unittest tests.test_v16_delivery_g4 tests.test_v16_delivery_recovery tests.test_v16_final_acceptance_verifier tests.test_v16_delivery_bridge -v
```

Expected: PASS; G4 still requires a new final-deck macOS PowerPoint record, delivery package, chat receipt, and user confirmation.

- [ ] **Step 6: Commit G4 policy lineage**

```bash
git add -- 产品代码/src/ai_ppt_studio/application/delivery_service.py 产品代码/src/ai_ppt_studio/application/gate_evaluator.py 产品代码/src/ai_ppt_studio/domains/delivery/contracts.py 产品代码/tests/test_v16_delivery_g4.py 产品代码/tests/test_v16_delivery_recovery.py 产品代码/tests/test_v16_final_acceptance_verifier.py 产品代码/tests/v16_delivery_fixtures.py
git diff --cached --check
git commit -m "feat: evaluate delivery gates from release policy"
```

## Task 7: Project required and deferred targets accurately in every UI

**Files:**

- Modify: `产品代码/src/ai_ppt_studio/application/workspace_projection.py`
- Modify: `产品代码/src/ai_ppt_studio/application/review_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `产品代码/tests/test_v16_workspace_projection.py`
- Modify: `产品代码/tests/test_v16_visual_review.py`
- Modify: `产品代码/widget/src/types.ts`
- Modify: `产品代码/widget/src/components/CompactWorkspace.tsx`
- Modify: `产品代码/widget/src/components/review/ReviewDocumentSections.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewApp.tsx`
- Modify: `产品代码/widget/src/test-fixtures.ts`
- Modify: `产品代码/widget/src/__fixtures__/review-projection.visual.json`
- Modify: `产品代码/widget/src/PhaseD.test.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewApp.test.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewLongDocument.test.tsx`

- [ ] **Step 1: Write failing projection and component tests**

Python projection assertion:

```python
self.assertEqual(
    projection["release_target_policy"]["required_target_ids"],
    ["macos-powerpoint"],
)
self.assertEqual(
    [row["status"] for row in projection["targets"]],
    ["passed", "deferred", "deferred", "deferred"],
)
```

React assertions:

```tsx
expect(screen.getByRole("heading", { name: "当前发布目标证据" })).toBeInTheDocument();
expect(screen.getByText("macOS PowerPoint")).toBeInTheDocument();
expect(screen.getAllByText("延期 · 当前版本不验收")).toHaveLength(3);
expect(screen.queryByText("四目标桌面实机证据")).not.toBeInTheDocument();
expect(screen.queryByText("跨平台通过")).not.toBeInTheDocument();
```

- [ ] **Step 2: Run focused tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_workspace_projection tests.test_v16_visual_review -v
npx vitest run widget/src/PhaseD.test.tsx widget/src/ProfessionalReviewApp.test.tsx widget/src/ProfessionalReviewLongDocument.test.tsx
```

Expected: FAIL because projections and headings remain fixed to four targets.

- [ ] **Step 3: Add explicit policy projection fields**

Return:

```ts
type ReleaseTargetPolicyProjection = {
  policy_ref: string;
  policy_id: string;
  required_target_ids: TargetId[];
  deferred_target_ids: TargetId[];
  compatibility_claim_scope: TargetId[];
};

type TargetStatus = "pending" | "passed" | "failed" | "stale" | "deferred";
```

All four supported rows may be shown for transparency, but only required rows affect Gate summaries. Deferred rows contain no PPTX hash or green pass state.

- [ ] **Step 4: Replace fixed-four copy and fixtures**

Use these user-facing strings:

- heading: `当前发布目标证据`;
- required summary: `已验证：macOS Microsoft PowerPoint` when passed;
- deferred badge: `延期 · 当前版本不验收`;
- missing blocker: `必需目标桌面证据尚未完成`;
- never emit `四目标已通过`, `跨平台通过`, or `Windows/WPS 兼容`.

Preserve all current Browser-review changes in overlapping Widget files.

- [ ] **Step 5: Run Python, Widget, and responsive UI acceptance**

```bash
python3 -m unittest tests.test_v16_workspace_projection tests.test_v16_visual_review -v
npm run build
npm run test:widget
npm run accept:v16-ui
```

Expected: PASS; 360–480px compact projection and 760/1000/1440px review page show required/deferred state without horizontal overflow.

- [ ] **Step 6: Commit projection and UI changes**

```bash
git add -- 产品代码/src/ai_ppt_studio/application/workspace_projection.py 产品代码/src/ai_ppt_studio/application/review_service.py 产品代码/src/ai_ppt_studio/application/v16_bridge.py 产品代码/tests/test_v16_workspace_projection.py 产品代码/tests/test_v16_visual_review.py 产品代码/widget/src/types.ts 产品代码/widget/src/components/CompactWorkspace.tsx 产品代码/widget/src/components/review/ReviewDocumentSections.tsx 产品代码/widget/src/ProfessionalReviewApp.tsx 产品代码/widget/src/test-fixtures.ts 产品代码/widget/src/__fixtures__/review-projection.visual.json 产品代码/widget/src/PhaseD.test.tsx 产品代码/widget/src/ProfessionalReviewApp.test.tsx 产品代码/widget/src/ProfessionalReviewLongDocument.test.tsx
git diff --cached --check
git commit -m "feat: show required and deferred release targets"
```

## Task 8: Update verification scripts and AI PPT Studio workflow

**Files:**

- Modify: `产品代码/scripts/acceptance/verify_target_evidence.py`
- Modify: `产品代码/scripts/acceptance/verify_release.py`
- Modify: `产品代码/tests/test_v16_target_evidence_import.py`
- Modify: `产品代码/tests/test_v16_final_acceptance_verifier.py`
- Modify: `产品代码/skills/ai-ppt-studio/SKILL.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/four-target-acceptance.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/visual-workflow.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/presentations-handoff.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/review-and-feedback.md`
- Modify: `产品代码/tests/test_skill_workflow.py`

- [ ] **Step 1: Write failing verifier and Skill contract tests**

Keep `verify_target_evidence.py` profile-specific: it must still accept any supported target when genuine evidence is supplied. Update `verify_release.py` tests so completeness is resolved from `release/target-policy` and require `policy_ref` in its output.

Update the Skill static test to require all of these phrases or equivalent exact contracts:

```text
ReleaseTargetPolicy
macos-powerpoint
deferred
do not claim WPS or Windows compatibility
preflight-only output cannot replace desktop evidence
G4 requires a new final-PPTX macOS PowerPoint record
```

Remove the assertion that the current workflow requires `macos-wps`, `windows-powerpoint`, and `windows-wps` evidence.

- [ ] **Step 2: Run focused tests and verify they fail**

```bash
python3 -m unittest tests.test_v16_target_evidence_import tests.test_v16_final_acceptance_verifier tests.test_skill_workflow -v
```

Expected: FAIL on fixed-four release verification and old Skill text.

- [ ] **Step 3: Make release verification policy-aware**

In `verify_release.py`, resolve `release/target-policy`, validate it, iterate `required_target_ids`, and include these fields in the immutable proof output:

```json
{
  "release_target_policy_ref": policy_ref,
  "required_target_ids": ["macos-powerpoint"],
  "deferred_target_ids": ["macos-wps", "windows-powerpoint", "windows-wps"],
  "compatibility_claim_scope": ["macos-powerpoint"]
}
```

Do not weaken `verify_target_evidence.py`; only replace its import of fixed required IDs with supported profile IDs.

- [ ] **Step 4: Rewrite Skill target workflow around policy**

Keep the existing filename `four-target-acceptance.md` as a compatibility entry point, but place a supersession notice at the top and make the active instructions policy-driven. Rename headings in the main Skill to `release-target G2` and `release-target G4`. State that the public Agent cannot shrink policy and that current v1.6 required target is macOS PowerPoint only.

- [ ] **Step 5: Run verifier, Skill, and support-script tests**

```bash
python3 -m unittest tests.test_v16_target_evidence_import tests.test_v16_final_acceptance_verifier tests.test_skill_workflow tests.test_v16_support_scripts -v
```

Expected: PASS; WPS/Windows target packages remain independently verifiable but are not current Gate requirements.

- [ ] **Step 6: Commit verifier and workflow changes**

```bash
git add -- 产品代码/scripts/acceptance/verify_target_evidence.py 产品代码/scripts/acceptance/verify_release.py 产品代码/tests/test_v16_target_evidence_import.py 产品代码/tests/test_v16_final_acceptance_verifier.py 产品代码/skills/ai-ppt-studio/SKILL.md 产品代码/skills/ai-ppt-studio/references/four-target-acceptance.md 产品代码/skills/ai-ppt-studio/references/visual-workflow.md 产品代码/skills/ai-ppt-studio/references/presentations-handoff.md 产品代码/skills/ai-ppt-studio/references/review-and-feedback.md 产品代码/tests/test_skill_workflow.py
git diff --cached --check
git commit -m "docs: make AI PPT acceptance policy driven"
```

## Task 9: Rebase the stable 104-item ledger without inflating acceptance

**Files:**

- Modify: `产品代码/requirements/v1.6-acceptance-ledger.json`
- Modify only if proof mappings genuinely change: `产品代码/requirements/v1.6-evidence.json`
- Modify: `产品代码/src/ai_ppt_studio/acceptance/ledger.py`
- Modify: `产品代码/tests/test_acceptance_ledger.py`
- Modify: `产品代码/docs/validation/2026-08-11-v16-final-acceptance.md`

- [ ] **Step 1: Audit changed stable IDs and current proof kinds**

Run:

```bash
python3 -m unittest tests.test_acceptance_ledger.AcceptanceLedgerTests.test_checked_in_ledger_matches_authoritative_sources -v
rg -n '四目标|macOS/Windows|PowerPoint/WPS|target-evidence' requirements/v1.6-acceptance-ledger.json requirements/v1.6-evidence.json docs/validation/2026-08-11-v16-final-acceptance.md
```

Expected: the source-consistency test still fails until ledger regeneration; the IDs affected by the new wording are explicit.

- [ ] **Step 2: Write failing ledger semantic tests**

Add assertions that:

```python
self.assertEqual(len(ledger.requirements), 104)
self.assertIn("当前发布策略", by_id["PRD-17.3-01"].text)
self.assertNotIn("四目标始终是一期强制", by_id["SDD-21.3-03"].text)
self.assertEqual(
    sum(item.status == "passed" for item in ledger.requirements),
    37,
)
```

Keep target-evidence requirements unproven until the real policy artifact, automated tests, runtime evidence, real project, and macOS PowerPoint target evidence are all indexed for that exact ID.

- [ ] **Step 3: Regenerate requirement text from the approved baselines**

Use the repository's ledger generation path, or add a narrowly scoped script entry if no generation command exists, to rewrite the JSON deterministically from PRD section 17, SDD section 21, and UI section 23. Do not manually renumber IDs and do not reduce the count.

- [ ] **Step 4: Update the validation report without rewriting history**

Add a dated scope-change section stating:

```markdown
2026-08-13：用户批准 v1.6 当前发布目标仅为 macOS Microsoft PowerPoint；WPS 与 Windows 延期，不作为当前 G2/G4 阻断项，也不构成兼容通过。旧 37/104 数字在新 proof contract 逐项登记完成前保持不变。
```

Record the real G2 macOS PowerPoint evidence ref only after Task 10 revalidates it under the new policy. Do not yet claim G2 passed in this task.

- [ ] **Step 5: Run ledger tests and verify exactly 104 requirements and 37 passes**

```bash
python3 -m unittest tests.test_acceptance_ledger -v
python3 -m ai_ppt_studio.acceptance.cli summary --ledger requirements/v1.6-acceptance-ledger.json
```

Expected: PASS; summary reports `104` total and `37` passed until new immutable proof mappings are added.

- [ ] **Step 6: Commit ledger rebaselining**

```bash
git add -- 产品代码/requirements/v1.6-acceptance-ledger.json 产品代码/src/ai_ppt_studio/acceptance/ledger.py 产品代码/tests/test_acceptance_ledger.py 产品代码/docs/validation/2026-08-11-v16-final-acceptance.md
git diff --cached --check
git commit -m "test: rebase v1.6 acceptance target policy"
```

If `requirements/v1.6-evidence.json` genuinely changes, stage it explicitly only after verifying every referenced file hash.

## Task 10: Full regression, plugin installation, and real-project G2 verification

**Files:**

- Verify: all files changed in Tasks 1–9
- Runtime project: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-final-real-acceptance-proposal-only`
- Verify/update after evidence mapping: `产品代码/docs/validation/2026-08-11-v16-final-acceptance.md`
- Verify/update after evidence mapping: `产品代码/requirements/v1.6-evidence.json`
- Verify/update after evidence mapping: `产品代码/requirements/v1.6-acceptance-ledger.json`

- [ ] **Step 1: Run all source regressions**

From `产品代码/`:

```bash
python3 -m unittest discover -s tests
npm run build
npm run test:node
npm run test:widget
npm run accept:v16-ui
npm run probe:mcp
```

Expected: every command exits zero; no fixed-four current-release assertion remains outside explicitly historical tests/docs.

- [ ] **Step 2: Run static contradiction and hygiene scans**

```bash
rg -n "REQUIRED_TARGET_IDS|four-target-evidence-incomplete|四目标始终是一期强制|四目标桌面实机证据" src tests mcp widget/src skills requirements docs
rg -n "macos-wps|windows-powerpoint|windows-wps" src widget/src skills
git diff --check
git status --short
```

Expected: old identifiers occur only in compatibility aliases, supported-profile definitions, deferred projections, legacy parsing tests, or historical notes; there is no active fixed-four Gate loop and no unrelated file is staged.

- [ ] **Step 3: Build, verify, and install a new plugin release**

```bash
AI_PPT_RELEASE_OUTPUT="$(mktemp -d /private/tmp/ai-ppt-v16-release.XXXXXX)"
npm run release -- --output "$AI_PPT_RELEASE_OUTPUT"
AI_PPT_RELEASE_DIR="$AI_PPT_RELEASE_OUTPUT/ai-ppt-studio"
test -f "$AI_PPT_RELEASE_DIR/release-manifest.json"
npm run verify:release -- --release "$AI_PPT_RELEASE_DIR"
node scripts/install-plugin.mjs --release "$AI_PPT_RELEASE_DIR" --target /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
codex plugin list
```

Expected: the release command prints JSON whose `pluginRoot` equals the exact absolute value of `AI_PPT_RELEASE_DIR`; the manifest check and release verification pass, installation reports the new cache-busted build, and Codex lists the installed AI PPT Studio plugin. Preserve that printed path in the evidence record and do not reuse an older cache directory.

- [ ] **Step 4: Read the real project and bind policy with expectedRevision 56**

First call `get_ai_ppt_project_snapshot` and require revision `56`, G0/G1 passed, G2 open, and current macOS PowerPoint evidence:

```text
artifact://target-render-evidence/b3ca6578acc9978d9cbaa37fa018448a8b60ec57b8c95acd1099951f4298b081
```

Then call:

```json
{
  "tool": "set_ai_ppt_release_target_policy",
  "projectRoot": "/Users/defei/Documents/AI-PPT-Workspace/projects/v16-final-real-acceptance-proposal-only",
  "expectedRevision": 56,
  "policyId": "v1.6-macos-powerpoint"
}
```

Expected: revision `56 -> 57`, new `release/target-policy` head, all prior artifact heads preserved, G2 still open, and no WPS/Windows target evidence created.

- [ ] **Step 5: Re-verify the existing macOS PowerPoint artifact and source hash**

Run the formal verifier again against the preserved evidence directory and source PPTX. Require:

```text
simulation=false
proof_eligible=true
overall_result=passed
pptx_sha256=1aa97f42c41adc0cf9f6eb4f989d88586598f8cf9cc0d9c7c510459e54e07de3
```

Recompute the source SHA-256 and resolve every support artifact ref inside the project. Do not regenerate evidence if the existing immutable record still validates.

- [ ] **Step 6: Attempt G2 with the exact current authorized refs**

Read the current G2 authorized heads after policy binding. The acceptance refs must contain exactly:

```text
artifact head: visual/design-system
artifact head: visual/contracts
artifact head: visual/anchors
artifact://visual-review-record/aec5f8991db0a403f7047b85d68710c3737a96e426e54ebfa3b58f18c125f5ee
artifact://visual-review-record/6fd6077d318ce2245f3e6590e4fb5f050f5d57455bb02a73a4e1ae0c89ee58bf
artifact head: release/target-policy
artifact://target-render-evidence/b3ca6578acc9978d9cbaa37fa018448a8b60ec57b8c95acd1099951f4298b081
```

Resolve each named artifact head to its current full `artifact://` ref and require the set to equal the seven refs authorized by the updated Gate evaluator: design system, visual contracts, anchors, G2 aesthetic review, G2 engineering review, release policy, and G2 macOS PowerPoint evidence. If the runtime returns a different authorized set, stop and treat it as an implementation defect instead of guessing. Call `record_internal_gate` for G2 with `PPT 工程审查智能体` only after exact-match verification.

Expected: G2 becomes `passed`, G3 becomes available only through the existing visual publication flow, and G4 remains locked.

- [ ] **Step 7: Verify the real projections and deferred claims**

Read project snapshot, sidebar projection, visual review projection, and delivery status. Require:

```text
required target: macos-powerpoint = passed
macos-wps = deferred
windows-powerpoint = deferred
windows-wps = deferred
compatibility claim scope = macos-powerpoint only
```

Confirm no projection says WPS/Windows/cross-platform passed and no G3 user confirmation was manufactured.

- [ ] **Step 8: Map only newly complete stable IDs and recompute the ledger**

Create privacy-safe immutable proof records for the policy artifact, focused/full regressions, installed plugin identity, real project revision, G2 event, and macOS PowerPoint target evidence. Add only requirement IDs whose every required proof kind now resolves. Rebuild the ledger and report the evidence-backed new numerator; do not assume it is `104`.

- [ ] **Step 9: Update validation report with exact results**

Record:

- installed plugin identity;
- policy artifact ref;
- policy-bound project revision;
- exact G2 event/evidence refs;
- macOS PowerPoint application/OS versions and PPTX SHA-256;
- WPS/Windows deferred status;
- remaining real sidebar, G3, full 12-page run, G4, or host-native confirmation gaps;
- recalculated strict ledger count.

- [ ] **Step 10: Run verification-before-completion checks**

Use `superpowers:verification-before-completion`, then run:

```bash
python3 -m unittest discover -s tests
npm test
npm run accept:v16-ui
npm run probe:mcp
git diff --check
git status --short
```

Expected: all relevant commands pass; existing unrelated dirty work remains intact and explicitly listed.

- [ ] **Step 11: Commit only final evidence-index/report changes**

```bash
git add -- 产品代码/requirements/v1.6-evidence.json 产品代码/requirements/v1.6-acceptance-ledger.json 产品代码/docs/validation/2026-08-11-v16-final-acceptance.md
git diff --cached --check
git commit -m "test: record policy-bound macOS PowerPoint G2 evidence"
```

Do not stage unrelated Browser, Widget, `.workbuddy`, duplicate validation, or pre-existing untracked files.

## Final completion criteria

- The four root baselines identify `v1.6-macos-powerpoint` as current and WPS/Windows as deferred.
- New projects bind a policy atomically; existing projects migrate through a public revision-safe command.
- Individual evidence still supports all four profiles, but G2/G4 matrix completeness is calculated from the current policy.
- G2 accepts only the existing genuine macOS PowerPoint evidence plus current visual/review/policy lineage; no deferred record is fabricated.
- G4 remains strict for the final PPTX and requires a fresh macOS PowerPoint desktop record, chat delivery receipt, and explicit user confirmation.
- UI and Skill distinguish required, deferred, preflight, and compatibility claims.
- Historical artifacts and old projects remain readable and are never rewritten.
- The requirement count remains 104 and the final reported numerator comes only from complete proof mappings.
- No claim is made that WPS, Windows, cross-platform compatibility, G3, full-deck G4, or final `104/104` has passed without its actual evidence.
