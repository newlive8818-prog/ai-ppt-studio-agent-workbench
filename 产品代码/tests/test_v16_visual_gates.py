from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import (
    G2_REVIEW_FORGERY_VARIANTS,
    forge_g2_visual_review,
    passing_visual_review,
    prepared_g1_anchor,
    prepared_visual_contracts,
    rich_target_payload,
)


class V16VisualGateTests(unittest.TestCase):
    def test_register_g2_review_rejects_resolvable_wrong_kind_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp))
            review = forge_g2_visual_review(
                passing_visual_review(
                    refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                ),
                "resolvable-wrong-kind-check-evidence",
                resolvable_wrong_kind_ref=refs["contracts"],
            )
            before = visual.kernel.load()

            with self.assertRaises(ArtifactReferenceError):
                visual.register_visual_review(
                    "reject-resolvable-wrong-kind-at-registration",
                    revision,
                    review,
                )
            self.assertEqual(visual.kernel.load(), before)

    def test_g2_revalidates_raw_current_review_contract_and_evidence(self) -> None:
        for name in G2_REVIEW_FORGERY_VARIANTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                visual, revision, refs = prepared_g1_anchor(Path(temp))
                visual.register_visual_review(
                    f"{name}-g2-aesthetic",
                    revision,
                    passing_visual_review(
                        refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                    ),
                )
                visual.register_visual_review(
                    f"{name}-g2-engineering",
                    revision + 1,
                    passing_visual_review(
                        refs["anchors"],
                        stage="G2",
                        reviewer_kind="engineering",
                        reviewer_role="independent-ppt-engineering-reviewer",
                    ),
                )
                _policy_ref, policy = ReleaseTargetPolicyService(
                    visual.kernel
                ).current()
                visual.register_target_render_evidence(
                    f"{name}-target",
                    revision + 2,
                    rich_target_payload(
                        visual, policy.required_target_ids[0], refs
                    ),
                )
                state = visual.kernel.load()
                review_slot = "visual/review/G2/aesthetic"
                review = visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(state.artifact_heads[review_slot])
                )["payload"]
                forged = forge_g2_visual_review(
                    review,
                    name,
                    resolvable_wrong_kind_ref=refs["contracts"],
                )
                state = visual.kernel.commit(
                    command_id=f"forge-{name}-g2-review",
                    expected_revision=state.revision,
                    event_type="test.raw-g2-review-forged",
                    artifact_updates={
                        review_slot: ("visual-review-record", forged)
                    },
                )

                with self.assertRaises(GateBlockedError) as caught:
                    visual.record_g2(f"reject-{name}-g2", state.revision)
                self.assertEqual(visual.kernel.load(), state)
                expected_blocker = (
                    "independent-aesthetic-review-evidence-invalid:0:0"
                    if name
                    in {
                        "unresolvable-check-evidence",
                        "unresolvable-wrong-kind-check-evidence",
                        "resolvable-wrong-kind-check-evidence",
                    }
                    else "independent-aesthetic-review-invalid"
                )
                self.assertIn(
                    expected_blocker,
                    caught.exception.missing_evidence,
                )

    def test_pass_g2_rejects_resolvable_wrong_kind_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp))
            visual.register_visual_review(
                "direct-g2-aesthetic",
                revision,
                passing_visual_review(
                    refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                ),
            )
            visual.register_visual_review(
                "direct-g2-engineering",
                revision + 1,
                passing_visual_review(
                    refs["anchors"],
                    stage="G2",
                    reviewer_kind="engineering",
                    reviewer_role="independent-ppt-engineering-reviewer",
                ),
            )
            _policy_ref, policy = ReleaseTargetPolicyService(
                visual.kernel
            ).current()
            visual.register_target_render_evidence(
                "direct-g2-target",
                revision + 2,
                rich_target_payload(
                    visual, policy.required_target_ids[0], refs
                ),
            )
            state = visual.kernel.load()
            review_slot = "visual/review/G2/aesthetic"
            review = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(state.artifact_heads[review_slot])
            )["payload"]
            forged = forge_g2_visual_review(
                review,
                "resolvable-wrong-kind-check-evidence",
                resolvable_wrong_kind_ref=refs["contracts"],
            )
            state = visual.kernel.commit(
                command_id="forge-direct-g2-resolvable-wrong-kind",
                expected_revision=state.revision,
                event_type="test.raw-g2-review-forged",
                artifact_updates={
                    review_slot: ("visual-review-record", forged)
                },
            )

            with self.assertRaises(GateBlockedError) as caught:
                GateEvaluator(visual.kernel).pass_g2()
            self.assertEqual(visual.kernel.load(), state)
            self.assertIn(
                "independent-aesthetic-review-evidence-invalid:0:0",
                caught.exception.missing_evidence,
            )

    def test_g2_revalidates_complete_current_anchor_and_target_evidence(self) -> None:
        variants = (
            "native-not-frozen",
            "whole-slide-image",
            "target-slide-order",
            "target-source-pptx",
        )
        for name in variants:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                visual, revision, refs = prepared_g1_anchor(Path(temp))
                state = visual.kernel.load()
                if name in {"native-not-frozen", "whole-slide-image"}:
                    anchor = copy.deepcopy(
                        visual.kernel.artifacts.resolve(
                            ArtifactReference.parse(refs["anchors"])
                        )["payload"]
                    )
                    if name == "native-not-frozen":
                        anchor["native_first_frozen"] = False
                    else:
                        anchor["whole_slide_image_ref"] = (
                            "artifact://whole-slide-image/" + "f" * 64
                        )
                    state = visual.kernel.commit(
                        command_id=f"forge-{name}-anchor",
                        expected_revision=revision,
                        event_type="test.raw-anchor-forged",
                        artifact_updates={
                            "visual/anchors": ("anchor-slide-set", anchor)
                        },
                    )
                    refs["anchors"] = state.artifact_heads["visual/anchors"]

                visual.register_visual_review(
                    f"{name}-g2-aesthetic",
                    state.revision,
                    passing_visual_review(
                        refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                    ),
                )
                visual.register_visual_review(
                    f"{name}-g2-engineering",
                    state.revision + 1,
                    passing_visual_review(
                        refs["anchors"],
                        stage="G2",
                        reviewer_kind="engineering",
                        reviewer_role="independent-ppt-engineering-reviewer",
                    ),
                )
                _policy_ref, policy = ReleaseTargetPolicyService(
                    visual.kernel
                ).current()
                target_id = policy.required_target_ids[0]
                target_ref = visual.register_target_render_evidence(
                    f"{name}-target",
                    state.revision + 2,
                    rich_target_payload(visual, target_id, refs),
                )
                current_revision = state.revision + 3
                if name in {"target-slide-order", "target-source-pptx"}:
                    target = copy.deepcopy(
                        visual.kernel.artifacts.resolve(
                            ArtifactReference.parse(target_ref)
                        )["payload"]
                    )
                    if name == "target-slide-order":
                        target["slide_checks"] = [
                            target["slide_checks"][1],
                            target["slide_checks"][0],
                            target["slide_checks"][2],
                        ]
                    else:
                        target["source_pptx_ref"] = str(
                            visual.kernel.artifacts.put(
                                "native-pptx",
                                {
                                    "pptx_sha256": refs["pptx_sha256"],
                                    "production_route": "strict-B",
                                    "identity": "wrong-current-source",
                                },
                            )
                        )
                    state = visual.kernel.commit(
                        command_id=f"forge-{name}-target",
                        expected_revision=current_revision,
                        event_type="test.raw-target-forged",
                        artifact_updates={
                            f"visual/target-evidence/G2/{target_id}": (
                                "target-render-evidence",
                                target,
                            )
                        },
                    )
                    current_revision = state.revision

                with self.assertRaises(GateBlockedError):
                    visual.record_g2(f"reject-{name}-g2", current_revision)

    def test_g2_revalidates_current_anchor_render_identity(self) -> None:
        variants = {
            "missing-current": lambda assets: assets[1].pop("current_asset_ref"),
            "wrong-order": lambda assets: assets.__setitem__(
                slice(None), [assets[1], assets[0], assets[2]]
            ),
        }
        for name, mutate in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                visual, revision, refs = prepared_g1_anchor(Path(temp))
                anchor = copy.deepcopy(
                    visual.kernel.artifacts.resolve(
                        ArtifactReference.parse(refs["anchors"])
                    )["payload"]
                )
                mutate(anchor["render_assets"])
                state = visual.kernel.commit(
                    command_id=f"forge-{name}-anchor",
                    expected_revision=revision,
                    event_type="test.raw-anchor-forged",
                    artifact_updates={
                        "visual/anchors": ("anchor-slide-set", anchor)
                    },
                )
                refs["anchors"] = state.artifact_heads["visual/anchors"]
                visual.register_visual_review(
                    f"{name}-g2-aesthetic",
                    state.revision,
                    passing_visual_review(
                        refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                    ),
                )
                visual.register_visual_review(
                    f"{name}-g2-engineering",
                    state.revision + 1,
                    passing_visual_review(
                        refs["anchors"],
                        stage="G2",
                        reviewer_kind="engineering",
                        reviewer_role="independent-ppt-engineering-reviewer",
                    ),
                )
                _policy_ref, policy = ReleaseTargetPolicyService(
                    visual.kernel
                ).current()
                visual.register_target_render_evidence(
                    f"{name}-target",
                    state.revision + 2,
                    rich_target_payload(
                        visual, policy.required_target_ids[0], refs
                    ),
                )
                with self.assertRaises(GateBlockedError) as caught:
                    visual.record_g2(f"{name}-g2", state.revision + 3)
                self.assertIn(
                    "anchor-render-assets-invalid",
                    caught.exception.missing_evidence,
                )

    def test_g1_requires_convergence_and_independent_binary_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(Path(temp))
            with self.assertRaises(GateBlockedError):
                visual.record_g1("early-g1", revision)
            convergence = visual.register_convergence(
                "convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "采用经营证据链命题与三类页面节奏",
                    "convergence_status": "passed",
                },
            )
            review = visual.register_visual_review(
                "g1-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            self.assertTrue(convergence.startswith("artifact://visual-convergence/"))
            self.assertTrue(review.startswith("artifact://visual-review-record/"))
            state = visual.record_g1("pass-g1", revision + 2)
            self.assertEqual(state.gate_status["G1"], "passed")
            self.assertEqual(state.gate_status["G2"], "open")

    def test_g1_rejects_scores_self_review_and_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(Path(temp))
            invalid = passing_visual_review(refs["contracts"])
            invalid["score"] = 95
            with self.assertRaises(ContractValidationError):
                visual.register_visual_review("scored", revision, invalid)
            self_review = passing_visual_review(
                refs["contracts"], reviewer_role="visual-art-director"
            )
            with self.assertRaises(ContractValidationError):
                visual.register_visual_review("self", revision, self_review)
            failed = passing_visual_review(refs["contracts"])
            failed["checks"][0].update(
                {
                    "result": "failed",
                    "failure_reason": "视觉层级不成立",
                    "repair_instruction": "重建层级",
                }
            )
            failed["overall_result"] = "failed"
            visual.register_visual_review("failed", revision, failed)
            with self.assertRaises(GateBlockedError):
                visual.record_g1("blocked-g1", revision + 1)

    def test_g2_requires_independent_reviews_and_current_required_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp))
            with self.assertRaises(GateBlockedError):
                visual.record_g2("early-g2", revision)
            visual.register_visual_review(
                "g2-aesthetic",
                revision,
                passing_visual_review(
                    refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                ),
            )
            visual.register_visual_review(
                "g2-engineering",
                revision + 1,
                passing_visual_review(
                    refs["anchors"],
                    stage="G2",
                    reviewer_kind="engineering",
                    reviewer_role="independent-ppt-engineering-reviewer",
                ),
            )
            current_revision = revision + 2
            with self.assertRaises(GateBlockedError):
                visual.record_g2("missing-target-g2", current_revision)
            self.assertEqual(visual.kernel.load().revision, current_revision)
            _policy_ref, policy = ReleaseTargetPolicyService(visual.kernel).current()
            final_target = policy.required_target_ids[0]
            visual.register_target_render_evidence(
                f"target-{final_target}",
                current_revision,
                rich_target_payload(visual, final_target, refs),
            )
            state = visual.record_g2("pass-g2", current_revision + 1)
            self.assertEqual(state.gate_status["G2"], "passed")
            self.assertEqual(state.gate_status["G3"], "locked")


if __name__ == "__main__":
    unittest.main()
