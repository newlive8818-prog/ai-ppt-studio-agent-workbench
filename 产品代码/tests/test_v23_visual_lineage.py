from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.release_policy_service import (  # noqa: E402
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator  # noqa: E402
from ai_ppt_studio.application.visual_service import VisualService  # noqa: E402
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError  # noqa: E402
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.domains.visual.contracts import (  # noqa: E402
    assess_visual_contract_set_v23,
)
from tests.v16_visual_fixtures import (  # noqa: E402
    confirmed_g0,
    passing_visual_review,
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)
from tests.test_v22_visual_review_service import seed_visual_review  # noqa: E402


DOWNSTREAM_SLOTS = (
    "visual/convergence",
    "visual/review/G1/aesthetic",
    "visual/anchors",
    "visual/target-evidence/G2/macos-powerpoint",
    "visual/contract",
    "review/session/visual-professional",
    "delivery/pptx",
)
SYSTEM_REF = "artifact://deck-design-system/" + "c" * 64
BLUEPRINT_REF = "artifact://reading-deck-blueprint/" + "b" * 64


def _seed_downstream_heads(kernel, slots: tuple[str, ...] = DOWNSTREAM_SLOTS) -> None:
    state = kernel.load()
    updates = {
        slot: ("probe", {"slot": slot, "seed": "v23"}) for slot in slots
    }
    kernel.commit(
        command_id="v23-seed-downstream",
        expected_revision=state.revision,
        event_type="test.v23-downstream-seeded",
        artifact_updates=updates,
    )


def _prepared(folder: str):
    content, revision, blueprint_ref = confirmed_g0(Path(folder))
    visual = VisualService(content.kernel)
    brief_ref = visual.register_visual_brief(
        "v23-lineage-brief",
        revision,
        valid_visual_brief(blueprint_ref),
    )
    design_ref = visual.register_design_system(
        "v23-lineage-design",
        content.kernel.load().revision,
        valid_design_system(brief_ref, blueprint_ref),
    )
    blueprint = content.kernel.artifacts.resolve(
        ArtifactReference.parse(blueprint_ref)
    )["payload"]
    contracts = valid_contract_set(design_ref, blueprint_ref, blueprint["slides"])
    return content.kernel, visual, blueprint_ref, brief_ref, design_ref, contracts


class V23VisualLineageTests(unittest.TestCase):
    def _seed_g1_evidence(self, kernel, visual, contract_ref: str) -> None:
        visual.register_convergence(
            "v23-g1-convergence",
            kernel.load().revision,
            {
                "production_route": "strict-B",
                "visual_contract_set_ref": contract_ref,
                "producer_role": "visual-art-director",
                "decision_summary": "合同关系已形成独立审美复核闭环",
                "convergence_status": "passed",
            },
        )
        visual.register_visual_review(
            "v23-g1-review",
            kernel.load().revision,
            passing_visual_review(contract_ref),
        )

    def test_g1_requires_a_current_compilation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, _blueprint_ref, _brief_ref, _design_ref, contracts = _prepared(folder)
            contract_ref = visual.register_visual_contract_set(
                "v23-g1-plan-required",
                kernel.load().revision,
                contracts,
            )
            self._seed_g1_evidence(kernel, visual, contract_ref)
            state = kernel.load()
            kernel.commit(
                command_id="v23-remove-current-plan",
                expected_revision=state.revision,
                event_type="test.v23-remove-plan",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            with self.assertRaises(GateBlockedError) as error:
                GateEvaluator(kernel).pass_g1()
            self.assertIn(
                "visual-compilation-plan-missing-or-stale",
                error.exception.missing_evidence,
            )

    def test_g1_rejects_wrong_kind_or_forged_publication_revision(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, _blueprint_ref, _brief_ref, _design_ref, contracts = _prepared(folder)
            contract_ref = visual.register_visual_contract_set(
                "v23-g1-plan-corruption",
                kernel.load().revision,
                contracts,
            )
            self._seed_g1_evidence(kernel, visual, contract_ref)
            plan_ref = kernel.load().artifact_heads["visual/compilation-plan"]
            wrong_kind_ref = str(kernel.artifacts.put("probe", {"identity": "wrong-kind"}))
            state = kernel.load()
            kernel.commit(
                command_id="v23-forge-plan-kind",
                expected_revision=state.revision,
                event_type="test.v23-forge-plan-kind",
                artifact_updates={"visual/compilation-plan": ("probe", {"identity": "wrong-kind"})},
            )
            with self.assertRaises(GateBlockedError) as wrong_kind:
                GateEvaluator(kernel).pass_g1()
            self.assertIn(
                "visual-compilation-plan-missing-or-stale",
                wrong_kind.exception.missing_evidence,
            )
            self.assertEqual(kernel.load().artifact_heads["visual/compilation-plan"], wrong_kind_ref)

            # Restore the valid plan, then forge a source revision that has no atomic event receipt.
            state = kernel.load()
            valid_plan = kernel.artifacts.resolve(ArtifactReference.parse(plan_ref))["payload"]
            kernel.commit(
                command_id="v23-restore-valid-plan",
                expected_revision=state.revision,
                event_type="test.v23-restore-plan",
                artifact_updates={
                    "visual/compilation-plan": ("visual-compilation-plan", valid_plan)
                },
            )
            forged = copy.deepcopy(valid_plan)
            forged["source_revision"] = valid_plan["source_revision"] + 100
            state = kernel.load()
            kernel.commit(
                command_id="v23-forge-plan-revision",
                expected_revision=state.revision,
                event_type="test.v23-forge-plan-revision",
                artifact_updates={
                    "visual/compilation-plan": ("visual-compilation-plan", forged)
                },
            )
            with self.assertRaises(GateBlockedError) as forged_revision:
                GateEvaluator(kernel).pass_g1()
            self.assertIn(
                "visual-compilation-plan-missing-or-stale",
                forged_revision.exception.missing_evidence,
            )

    def test_legacy_contract_sets_remain_readable_but_unassessed(self) -> None:
        payload = valid_contract_set(SYSTEM_REF, BLUEPRINT_REF)
        legacy_fields = {
            "reader_judgment",
            "primary_relationship",
            "secondary_relationship",
            "visual_mechanism",
            "focal_point",
            "asset_roles",
            "forbidden_patterns",
            "previous_rhythm_relation",
            "next_rhythm_relation",
            "text_density_budget",
            "powerpoint_implementation_requirements",
            "acceptance_evidence_plan",
        }
        for slide in payload["slide_contracts"]:
            for field in legacy_fields:
                slide.pop(field, None)
        self.assertEqual(
            assess_visual_contract_set_v23(payload),
            "legacy / unassessed-by-v23",
        )
        self.assertEqual(payload["slide_contracts"][0]["neutral_title"], "当前流程断点与证据边界")

    def test_published_visual_contract_binds_the_current_compilation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            kernel = ProjectKernel.initialize(Path(folder), project_id="v23-publish")
            _design_ref, _anchor_ref, contract_ref, _session_ref, _session, state = seed_visual_review(kernel)
            visual_contract = kernel.artifacts.resolve(
                ArtifactReference.parse(contract_ref)
            )["payload"]
            self.assertEqual(
                visual_contract["visual_compilation_plan_ref"],
                state.artifact_heads["visual/compilation-plan"],
            )

    def test_visual_user_reviewable_and_g3_evidence_reject_a_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            kernel = ProjectKernel.initialize(Path(folder), project_id="v23-stale-plan")
            _design_ref, _anchor_ref, contract_ref, _session_ref, _session, state = seed_visual_review(kernel)
            kernel.commit(
                command_id="v23-remove-published-plan",
                expected_revision=state.revision,
                event_type="test.v23-remove-published-plan",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            with self.assertRaises(GateBlockedError):
                GateEvaluator(kernel).visual_user_reviewable(contract_ref)
            with self.assertRaises(GateBlockedError):
                GateEvaluator(kernel).current_g3_confirmation_evidence()

    def test_unrelated_commit_does_not_stale_a_current_compilation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            kernel = ProjectKernel.initialize(Path(folder), project_id="v23-unrelated")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, _session, state = seed_visual_review(kernel)
            plan_ref = state.artifact_heads["visual/compilation-plan"]
            kernel.commit(
                command_id="v23-unrelated-commit",
                expected_revision=state.revision,
                event_type="test.v23-unrelated-commit",
                artifact_updates={"unrelated": ("probe", {"identity": "unrelated"})},
            )
            self.assertEqual(
                GateEvaluator(kernel).validate_current_g2_evidence()["compilation_plan_ref"],
                plan_ref,
            )

    def test_register_contracts_writes_contract_and_plan_in_one_revision(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, blueprint_ref, _brief_ref, design_ref, contracts = _prepared(folder)
            before = kernel.load()
            contract_ref = visual.register_visual_contract_set(
                "v23-atomic-contracts",
                before.revision,
                contracts,
            )
            committed = kernel.load()
            self.assertEqual(committed.revision, before.revision + 1)
            self.assertEqual(committed.artifact_heads["visual/contracts"], contract_ref)
            plan_ref = committed.artifact_heads.get("visual/compilation-plan", "")
            self.assertTrue(plan_ref.startswith("artifact://visual-compilation-plan/"))
            plan = kernel.artifacts.resolve(ArtifactReference.parse(plan_ref))["payload"]
            self.assertEqual(plan["visual_contract_set_ref"], contract_ref)
            self.assertEqual(plan["source_revision"], committed.revision)
            self.assertEqual(plan["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(plan["deck_design_system_ref"], design_ref)

    def test_atomic_failure_preserves_state_events_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, _blueprint_ref, _brief_ref, _design_ref, contracts = _prepared(folder)
            before_state = kernel.load()
            before_files = sorted(
                str(path.relative_to(Path(folder)))
                for path in Path(folder).rglob("*.json")
            )
            with patch.object(kernel, "commit", side_effect=RuntimeError("blocked commit")):
                with self.assertRaises(RuntimeError):
                    visual.register_visual_contract_set(
                        "v23-atomic-failure",
                        before_state.revision,
                        contracts,
                    )
            after_state = kernel.load()
            after_files = sorted(
                str(path.relative_to(Path(folder)))
                for path in Path(folder).rglob("*.json")
            )
            self.assertEqual(after_state.revision, before_state.revision)
            self.assertEqual(after_state.artifact_heads, before_state.artifact_heads)
            self.assertEqual(after_files, before_files)

    def test_new_brief_invalidates_all_visual_downstream_heads(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, blueprint_ref, brief_ref, design_ref, contracts = _prepared(folder)
            state = kernel.load()
            contract_ref = visual.register_visual_contract_set(
                "v23-brief-invalidation-contracts", state.revision, contracts
            )
            old_plan_ref = kernel.load().artifact_heads["visual/compilation-plan"]
            _seed_downstream_heads(kernel)
            changed_brief = valid_visual_brief(blueprint_ref)
            changed_brief["decision_task"] += "，并先恢复目录阅读焦点"
            visual.register_visual_brief(
                "v23-brief-invalidation",
                kernel.load().revision,
                changed_brief,
            )
            state = kernel.load()
            self.assertNotEqual(state.artifact_heads["visual/brief"], brief_ref)
            for slot in (
                "visual/design-system",
                "visual/contracts",
                "visual/compilation-plan",
                *DOWNSTREAM_SLOTS,
            ):
                self.assertNotIn(slot, state.artifact_heads)
            self.assertNotEqual(contract_ref, state.artifact_heads.get("visual/contracts"))
            kernel.artifacts.resolve(ArtifactReference.parse(old_plan_ref))

    def test_new_design_system_keeps_brief_but_invalidates_contract_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, blueprint_ref, brief_ref, design_ref, contracts = _prepared(folder)
            state = kernel.load()
            visual.register_visual_contract_set(
                "v23-design-invalidation-contracts", state.revision, contracts
            )
            _seed_downstream_heads(kernel)
            changed_design = valid_design_system(brief_ref, blueprint_ref)
            changed_design["theme_proposition"] = "编辑化工程叙事"
            new_design_ref = visual.register_design_system(
                "v23-design-invalidation",
                kernel.load().revision,
                changed_design,
            )
            state = kernel.load()
            self.assertEqual(state.artifact_heads["visual/brief"], brief_ref)
            self.assertEqual(state.artifact_heads["visual/design-system"], new_design_ref)
            self.assertNotEqual(new_design_ref, design_ref)
            for slot in ("visual/contracts", "visual/compilation-plan", *DOWNSTREAM_SLOTS):
                self.assertNotIn(slot, state.artifact_heads)

    def test_policy_change_invalidates_plan_and_derived_outputs_but_preserves_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, _blueprint_ref, brief_ref, design_ref, contracts = _prepared(folder)
            state = kernel.load()
            contract_ref = visual.register_visual_contract_set(
                "v23-policy-invalidation-contracts", state.revision, contracts
            )
            old_plan_ref = kernel.load().artifact_heads["visual/compilation-plan"]
            _seed_downstream_heads(kernel)
            policy_service = ReleaseTargetPolicyService(kernel)
            policy_ref, policy = policy_service.current()
            changed_policy = policy.as_payload()
            changed_policy["policy_id"] = "v23-policy-invalidation"
            changed_policy["policy_version"] = "1.1"
            new_policy_ref, _state = policy_service.bind_policy(
                "v23-policy-invalidation",
                kernel.load().revision,
                changed_policy,
            )
            state = kernel.load()
            self.assertNotEqual(new_policy_ref, policy_ref)
            self.assertEqual(state.artifact_heads["visual/brief"], brief_ref)
            self.assertEqual(state.artifact_heads["visual/design-system"], design_ref)
            self.assertEqual(state.artifact_heads["visual/contracts"], contract_ref)
            for slot in ("visual/compilation-plan", *DOWNSTREAM_SLOTS):
                self.assertNotIn(slot, state.artifact_heads)
            kernel.artifacts.resolve(ArtifactReference.parse(old_plan_ref))

    def test_exact_contract_command_replays_without_revision_but_changed_semantics_fail(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel, visual, _blueprint_ref, _brief_ref, _design_ref, contracts = _prepared(folder)
            state = kernel.load()
            first_ref = visual.register_visual_contract_set(
                "v23-contract-replay", state.revision, contracts
            )
            first_state = kernel.load()
            first_plan_ref = first_state.artifact_heads["visual/compilation-plan"]
            second_ref = visual.register_visual_contract_set(
                "v23-contract-replay", first_state.revision, copy.deepcopy(contracts)
            )
            second_state = kernel.load()
            self.assertEqual(second_ref, first_ref)
            self.assertEqual(second_state.revision, first_state.revision)
            self.assertEqual(
                second_state.artifact_heads["visual/compilation-plan"], first_plan_ref
            )

            changed = copy.deepcopy(contracts)
            changed["slide_contracts"][0]["visual_mechanism"] = "改用不等权路径"
            with self.assertRaises(ContractValidationError):
                visual.register_visual_contract_set(
                    "v23-contract-replay",
                    second_state.revision,
                    changed,
                )
            self.assertEqual(kernel.load().revision, second_state.revision)


if __name__ == "__main__":
    unittest.main()
