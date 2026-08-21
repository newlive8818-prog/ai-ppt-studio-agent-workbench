from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import (
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_review_projection import accepted_review
from tests.test_v22_visual_review_contracts import region_feedback
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.v16_visual_fixtures import (
    G2_REVIEW_FORGERY_VARIANTS,
    forge_g2_visual_review,
    passing_visual_review,
    rich_target_payload,
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


def visual_slide_contract(frozen: dict) -> dict:
    slide_id = frozen["slide_id"]
    index = frozen["order"]
    return {
        "slide_id": slide_id,
        "order": index,
        "page_family": "证据页",
        "page_task": frozen["page_task"],
        "reading_question": frozen["reading_question"],
        "neutral_title": frozen["neutral_title"],
        "visible_copy_blocks": copy.deepcopy(frozen["visible_copy_blocks"]),
        "identity_labels": copy.deepcopy(frozen["identity_labels"]),
        "evidence_bindings": copy.deepcopy(frozen["evidence_bindings"]),
        "analysis_or_proposal_blocks": copy.deepcopy(
            frozen["analysis_or_proposal_blocks"]
        ),
        "solution_mapping_refs": copy.deepcopy(
            frozen["solution_mapping_refs"]
        ),
        "previous_relation": frozen["previous_relation"],
        "next_relation": frozen["next_relation"],
        "speaker_notes": frozen["speaker_notes"],
        "reading_quality": copy.deepcopy(frozen["reading_quality"]),
        "material_mode": frozen["material_mode"],
        "information_hierarchy": "标题—事实—建议",
        "composition_intent": "形成清晰阅读顺序",
        "regions": [{"region_id": "body", "purpose": "呈现事实"}],
        "object_relationships": ["事实支持建议"],
        "reading_order": ["标题", "事实", "建议"],
        "image_selection_and_crop": "不使用语义图片",
        "typography_application": "标题 28pt，正文 16pt",
        "color_application": "强调色只表达当前焦点",
        "diagram_chart_table_treatment": "业务关系使用原生对象",
        "native_bitmap_routing": "全部语义对象原生",
        "editability_requirements": "文字、数据和关系可编辑",
        "fallbacks": ["图片缺失时保留原生结构"],
        "allowed_exceptions": [],
        "acceptance_criteria": [
            {
                "criterion_id": "editable",
                "level": "must-follow",
                "expected_outcome": "原生可编辑",
            }
        ],
    }


def seed_visual_review(kernel: ProjectKernel):
    state = kernel.load()
    if not state.artifact_heads.get("release/target-policy"):
        _policy_ref, state = ReleaseTargetPolicyService(
            kernel
        ).bind_current_policy("visual-review-seed-policy", state.revision)

    reading_blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
    if reading_blueprint_ref:
        reading_blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(reading_blueprint_ref)
        )["payload"]
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        acceptance = (
            kernel.artifacts.resolve(ArtifactReference.parse(acceptance_ref))["payload"]
            if acceptance_ref
            else {}
        )
        if acceptance.get("reading_blueprint_ref") != reading_blueprint_ref:
            hard_gates = ContentHardGateService(kernel)
            hard_gates.run_evidence_gate(
                command_id="visual-review-seed-evidence-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            hard_gates.run_presales_reading_gate(
                command_id="visual-review-seed-reading-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
        state = kernel.load()
        content_session_ref = state.review_session_ref("content-full-deck")
        if content_session_ref:
            content_session = kernel.artifacts.resolve(
                ArtifactReference.parse(content_session_ref)
            )["payload"]
        else:
            publication_revision = ReviewSessionService(
                kernel
            )._target_publication_revision(
                state,
                "content-full-deck",
                reading_blueprint_ref,
            )
            content_session_ref, content_session, state = ReviewSessionService(
                kernel
            ).open_or_resume(
                command_id="visual-review-seed-open-content-review",
                expected_revision=state.revision,
                review_type="content-full-deck",
                target_artifact_ref=reading_blueprint_ref,
                source_version=reading_blueprint["source_version"],
                source_revision=publication_revision,
                open_policy="foreground-if-waiting",
            )
    else:
        (
            reading_blueprint_ref,
            content_session_ref,
            content_session,
            state,
        ) = accepted_review(kernel, slide_count=4)

    reading_blueprint = kernel.artifacts.resolve(
        ArtifactReference.parse(reading_blueprint_ref)
    )["payload"]
    frozen_slides = reading_blueprint["slides"]
    if len(frozen_slides) < 3:
        raise ContractValidationError(
            "Visual review fixture requires at least three frozen slides"
        )
    current_batch_ref = kernel.load().artifact_heads.get("content/review-batch", "")
    current_batch = (
        kernel.artifacts.resolve(ArtifactReference.parse(current_batch_ref))["payload"]
        if current_batch_ref
        else {}
    )
    if (
        current_batch.get("status") != "submitted"
        or current_batch.get("reading_blueprint_ref") != reading_blueprint_ref
    ):
        decisions = ContentDecisionService(kernel)
        for slide in frozen_slides:
            decisions.save(
                command_id=f"visual-review-seed-approve-{slide['slide_id']}",
                expected_revision=kernel.load().revision,
                review_session_id=content_session["review_session_id"],
                source_version=reading_blueprint["source_version"],
                slide_id=slide["slide_id"],
                decision="approved",
                comment="",
            )
        ContentReviewBatchService(kernel).submit(
            command_id="visual-review-seed-submit-content-review",
            expected_revision=kernel.load().revision,
            review_session_id=content_session["review_session_id"],
            source_version=reading_blueprint["source_version"],
        )

    content = PresalesContentService(kernel)
    state = kernel.load()
    if state.gate_status.get("G0") == "locked":
        state = content.open_g0_review(
            command_id="visual-review-seed-open-g0",
            expected_revision=state.revision,
        )
    if state.gate_status.get("G0") != "passed":
        context = content.gate_confirmation_context()
        state = content.confirm_g0(
            command_id="visual-review-seed-confirm-g0",
            expected_revision=state.revision,
            **gate_confirmation_kwargs(context),
        )

    visual = VisualService(kernel)
    visual_source_version = "visual-v1"
    brief_ref = visual.register_visual_brief(
        "visual-review-seed-brief",
        state.revision,
        {
            **valid_visual_brief(reading_blueprint_ref),
            "source_version": visual_source_version,
        },
    )
    design_ref = visual.register_design_system(
        "visual-review-seed-design-system",
        kernel.load().revision,
        {
            **valid_design_system(brief_ref, reading_blueprint_ref),
            "source_version": visual_source_version,
        },
    )
    contract_set_ref = visual.register_visual_contract_set(
        "visual-review-seed-contract-set",
        kernel.load().revision,
        {
            **valid_contract_set(design_ref, reading_blueprint_ref, frozen_slides),
            "source_version": visual_source_version,
        },
    )
    visual.register_convergence(
        "visual-review-seed-convergence",
        kernel.load().revision,
        {
            "production_route": "strict-B",
            "visual_contract_set_ref": contract_set_ref,
            "producer_role": "visual-art-director",
            "decision_summary": "三页锚点覆盖章节、证据和方案页面家族",
            "convergence_status": "passed",
        },
    )
    visual.register_visual_review(
        "visual-review-seed-g1-aesthetic",
        kernel.load().revision,
        passing_visual_review(contract_set_ref),
    )
    visual.record_g1("visual-review-seed-pass-g1", kernel.load().revision)

    sha256 = "d" * 64
    pptx_ref = str(
        kernel.artifacts.put(
            "native-pptx",
            {"pptx_sha256": sha256, "production_route": "strict-B"},
        )
    )
    editability_ref = str(
        kernel.artifacts.put(
            "editability-evidence", {"semantic_objects_editable": True}
        )
    )
    preflight_ref = str(
        kernel.artifacts.put("preflight-render", {"identity": "preflight-only"})
    )
    slide_ids = [slide["slide_id"] for slide in frozen_slides[:3]]
    anchor_ref = visual.register_anchor_set(
        "visual-review-seed-anchors",
        kernel.load().revision,
        {
            "source_version": visual_source_version,
            "visual_contract_set_ref": contract_set_ref,
            "slide_ids": slide_ids,
            "selection_reason": "覆盖章节、证据和方案三类关键页面家族",
            "render_assets": [
                {
                    "slide_id": slide_id,
                    "current_asset_ref": f"review-assets/anchors/{slide_id}-current.png",
                    "previous_asset_ref": (
                        ""
                        if index == 1
                        else f"review-assets/anchors/{slide_id}-previous.png"
                    ),
                }
                for index, slide_id in enumerate(slide_ids, start=1)
            ],
            "native_first_pptx_ref": pptx_ref,
            "pptx_sha256": sha256,
            "native_first_frozen": True,
            "editability_evidence_refs": [editability_ref],
            "preflight_render_refs": [preflight_ref],
        },
    )
    visual.register_visual_review(
        "visual-review-seed-g2-aesthetic",
        kernel.load().revision,
        passing_visual_review(
            anchor_ref, stage="G2", reviewer_kind="aesthetic"
        ),
    )
    visual.register_visual_review(
        "visual-review-seed-g2-engineering",
        kernel.load().revision,
        passing_visual_review(
            anchor_ref,
            stage="G2",
            reviewer_kind="engineering",
            reviewer_role="independent-ppt-engineering-reviewer",
        ),
    )
    refs = {
        "anchors": anchor_ref,
        "pptx": pptx_ref,
        "pptx_sha256": sha256,
        "slide_ids": slide_ids,
    }
    _policy_ref, policy = ReleaseTargetPolicyService(kernel).current()
    for target_id in policy.required_target_ids:
        visual.register_target_render_evidence(
            f"visual-review-seed-target-{target_id}",
            kernel.load().revision,
            rich_target_payload(visual, target_id, refs),
        )
    visual.record_g2("visual-review-seed-pass-g2", kernel.load().revision)
    state = visual.publish_visual_review(
        "visual-review-seed-publish", kernel.load().revision
    )
    contract_ref = state.artifact_heads["visual/contract"]
    contract = kernel.artifacts.resolve(ArtifactReference.parse(contract_ref))["payload"]
    source_version = str(contract.get("source_version") or contract_ref)
    session_ref, session, state = ReviewSessionService(kernel).open_or_resume(
        command_id="visual-review-seed-session",
        expected_revision=state.revision,
        review_type="visual-professional",
        target_artifact_ref=contract_ref,
        source_version=source_version,
        source_revision=state.revision,
        open_policy="foreground-if-waiting",
    )
    return design_ref, anchor_ref, contract_ref, session_ref, session, state


def rebind_visual_contract(
    kernel: ProjectKernel, contract: dict, command_prefix: str
):
    state = kernel.load()
    contract_ref = str(kernel.artifacts.reference_for("visual-contract", contract))
    state = kernel.commit(
        command_id=f"{command_prefix}-contract",
        expected_revision=state.revision,
        event_type="test.raw-contract-forged",
        artifact_updates={"visual/contract": ("visual-contract", contract)},
    )
    session_payload = kernel.artifacts.resolve(
        ArtifactReference.parse(state.review_session_ref("visual-professional"))
    )["payload"]
    session_payload["target_artifact_ref"] = contract_ref
    return kernel.commit(
        command_id=f"{command_prefix}-session",
        expected_revision=state.revision,
        event_type="test.raw-session-rebound",
        artifact_updates={
            "review/session/visual-professional": (
                "review-session",
                session_payload,
            )
        },
    )


class VisualReviewServiceTests(unittest.TestCase):
    def test_projection_revalidates_raw_post_g2_review_contract_and_evidence(
        self,
    ) -> None:
        for name in G2_REVIEW_FORGERY_VARIANTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                (
                    _design_ref,
                    _anchor_ref,
                    _contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
                review_slot = "visual/review/G2/aesthetic"
                review = kernel.artifacts.resolve(
                    ArtifactReference.parse(state.artifact_heads[review_slot])
                )["payload"]
                forged = forge_g2_visual_review(
                    review,
                    name,
                    resolvable_wrong_kind_ref=state.artifact_heads[
                        "visual/contracts"
                    ],
                )
                state = kernel.commit(
                    command_id=f"forge-post-g2-review-{name}",
                    expected_revision=state.revision,
                    event_type="test.raw-g2-review-forged-after-g2",
                    artifact_updates={
                        review_slot: ("visual-review-record", forged)
                    },
                )
                contract = copy.deepcopy(
                    kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                )
                contract["internal_review_refs"] = [
                    state.artifact_heads[review_slot],
                    state.artifact_heads["visual/review/G2/engineering"],
                ]
                rebind_visual_contract(
                    kernel, contract, f"rebind-post-g2-review-{name}"
                )

                with self.assertRaises(GateBlockedError) as caught:
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )
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

    def test_seed_uses_formal_publish_session_project_chain(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                design_ref,
                anchor_ref,
                contract_ref,
                session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            self.assertEqual(state.gate_status["G1"], "passed")
            self.assertEqual(state.gate_status["G2"], "passed")
            self.assertEqual(state.gate_status["G3"], "user-reviewable")
            self.assertEqual(state.artifact_heads["visual/design-system"], design_ref)
            self.assertEqual(state.artifact_heads["visual/anchors"], anchor_ref)
            self.assertEqual(state.artifact_heads["visual/contract"], contract_ref)
            self.assertEqual(
                state.artifact_heads["review/session/visual-professional"],
                session_ref,
            )
            for slot in (
                "release/target-policy",
                "visual/brief",
                "visual/contracts",
                "visual/convergence",
                "visual/review/G1/aesthetic",
                "visual/review/G2/aesthetic",
                "visual/review/G2/engineering",
                "visual/target-evidence/G2/macos-powerpoint",
            ):
                self.assertIn(slot, state.artifact_heads)
            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(
                projection["anchor_identity"]["selection_reason"],
                "覆盖章节、证据和方案三类关键页面家族",
            )

    def test_seed_reuses_current_content_blueprint_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, content_session, _state = accepted_review(
                kernel, slide_count=4
            )
            seed_visual_review(kernel)
            state = kernel.load()
            self.assertEqual(
                state.artifact_heads["content/reading-blueprint"], blueprint_ref
            )
            current_session = kernel.artifacts.resolve(
                ArtifactReference.parse(
                    state.artifact_heads["review/session/content-full-deck"]
                )
            )["payload"]
            self.assertEqual(
                current_session["review_session_id"],
                content_session["review_session_id"],
            )

    def test_python_bridge_uses_exact_visual_review_operations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, _state = seed_visual_review(kernel)
            result = dispatch_v16({
                "operation": "get-visual-review-projection",
                "project_root": str(project_root),
                "review_session_id": session["review_session_id"],
            })
            self.assertEqual(result["review"]["review_type"], "visual-professional")

    def test_projection_has_two_views_from_one_current_visual_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            design_ref, anchor_ref, contract_ref, _session_ref, session, _state = seed_visual_review(kernel)
            projection = VisualReviewService(kernel).project(session["review_session_id"])
            self.assertEqual(projection["visual_contract_ref"], contract_ref)
            self.assertEqual(projection["deck_design_system_ref"], design_ref)
            self.assertEqual(projection["anchor_slide_set_ref"], anchor_ref)
            self.assertEqual(
                projection["anchors"],
                [
                    {
                        "slide_id": "S01",
                        "current_asset_ref": "review-assets/anchors/S01-current.png",
                        "previous_asset_ref": "",
                    },
                    {
                        "slide_id": "S02",
                        "current_asset_ref": "review-assets/anchors/S02-current.png",
                        "previous_asset_ref": "review-assets/anchors/S02-previous.png",
                    },
                    {
                        "slide_id": "S03",
                        "current_asset_ref": "review-assets/anchors/S03-current.png",
                        "previous_asset_ref": "review-assets/anchors/S03-previous.png",
                    },
                ],
            )
            self.assertEqual(len(projection["slide_visual_contracts"]), 4)
            self.assertEqual(projection["host_submission_capability"], "unknown")
            self.assertEqual(projection["ai_receipt_capability"], "unknown")
            self.assertEqual(projection["project_name"], "p1")
            self.assertNotIn("gate_status", projection)
            self.assertEqual(
                set(projection["anchor_identity"]),
                {"slide_ids", "selection_reason", "native_first_frozen"},
            )
            self.assertNotIn(
                "identity_labels", projection["slide_visual_contracts"][0]
            )
            self.assertNotIn(
                "analysis_or_proposal_blocks",
                projection["slide_visual_contracts"][0],
            )
            self.assertIn("visible_copy", projection["slide_visual_contracts"][0])
            self.assertIn("source_refs", projection["slide_visual_contracts"][0])

    def test_projection_keeps_explicit_empty_visible_copy_ahead_of_legacy_fallback(self) -> None:
        projected = VisualReviewService._project_slide_contract(
            {
                "slide_id": "S01",
                "visible_copy": [],
                "visible_copy_blocks": [{"text": "legacy block"}],
                "frozen_copy": "legacy frozen copy",
            }
        )

        self.assertEqual(projected["visible_copy"], [])

    def test_projection_keeps_explicit_empty_visible_copy_blocks_ahead_of_legacy_fallback(self) -> None:
        projected = VisualReviewService._project_slide_contract(
            {
                "slide_id": "S01",
                "visible_copy_blocks": [],
                "frozen_copy": ["legacy"],
            }
        )

        self.assertEqual(projected["visible_copy"], [])

    def test_projection_project_name_prefers_current_mission_topic(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            state = kernel.load()
            kernel.commit(
                command_id="seed-mission-topic",
                expected_revision=state.revision,
                event_type="test.mission-topic-seeded",
                artifact_updates={
                    "mission/draft": (
                        "mission-draft",
                        {"topic": "集团经营一体化方案"},
                    )
                },
            )
            _design, _anchor, _contract, _session_ref, session, _state = (
                seed_visual_review(kernel)
            )
            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(projection["project_name"], "集团经营一体化方案")

    def test_projection_rejects_raw_contract_page_order_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, _state = seed_visual_review(kernel)
            state = kernel.load()
            contract = kernel.artifacts.resolve(
                ArtifactReference.parse(state.artifact_heads["visual/contract"])
            )["payload"]
            contract["slide_contracts"][1]["order"] = 3
            forged_ref = str(kernel.artifacts.reference_for("visual-contract", contract))
            state = kernel.commit(
                command_id="forge-contract-order",
                expected_revision=state.revision,
                event_type="test.raw-contract-forged",
                artifact_updates={"visual/contract": ("visual-contract", contract)},
            )
            session_payload = kernel.artifacts.resolve(
                ArtifactReference.parse(
                    state.review_session_ref("visual-professional")
                )
            )["payload"]
            session_payload["target_artifact_ref"] = forged_ref
            kernel.commit(
                command_id="rebind-forged-contract-session",
                expected_revision=state.revision,
                event_type="test.raw-session-rebound",
                artifact_updates={
                    "review/session/visual-professional": (
                        "review-session",
                        session_payload,
                    )
                },
            )
            with self.assertRaises((ContractValidationError, GateBlockedError)):
                VisualReviewService(kernel).project(session["review_session_id"])

    def test_projection_rejects_missing_or_stale_complete_lineage(self) -> None:
        final_fields = (
            (
                "reading_blueprint_ref",
                "content/reading-blueprint",
                "reading-deck-blueprint",
            ),
            (
                "visual_contract_set_ref",
                "visual/contracts",
                "visual-contract-set",
            ),
        )
        for field, slot, kind in final_fields:
            for fault in ("missing", "stale"):
                with (
                    self.subTest(field=field, fault=fault),
                    tempfile.TemporaryDirectory() as folder,
                ):
                    kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                    _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                    contract = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                    if fault == "missing":
                        contract.pop(field)
                    else:
                        current_payload = kernel.artifacts.resolve(
                            ArtifactReference.parse(state.artifact_heads[slot])
                        )["payload"]
                        contract[field] = str(
                            kernel.artifacts.put(
                                kind,
                                {
                                    **current_payload,
                                    "source_version": "visual-v1",
                                    "detached_identity": field,
                                },
                            )
                        )
                    rebind_visual_contract(
                        kernel, contract, f"forge-{field}-{fault}"
                    )
                    with self.assertRaises(
                        (ContractValidationError, GateBlockedError)
                    ):
                        VisualReviewService(kernel).project(
                            session["review_session_id"]
                        )

        for fault in ("missing", "stale"):
            with (
                self.subTest(field="anchor.visual_contract_set_ref", fault=fault),
                tempfile.TemporaryDirectory() as folder,
            ):
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                anchors = kernel.artifacts.resolve(
                    ArtifactReference.parse(state.artifact_heads["visual/anchors"])
                )["payload"]
                if fault == "missing":
                    anchors.pop("visual_contract_set_ref")
                else:
                    current_set = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contracts"]
                        )
                    )["payload"]
                    anchors["visual_contract_set_ref"] = str(
                        kernel.artifacts.put(
                            "visual-contract-set",
                            {
                                **current_set,
                                "source_version": "visual-v1",
                                "detached_identity": "anchor-contract-set",
                            },
                        )
                    )
                state = kernel.commit(
                    command_id=f"forge-anchor-lineage-{fault}",
                    expected_revision=state.revision,
                    event_type="test.raw-anchor-forged",
                    artifact_updates={
                        "visual/anchors": ("anchor-slide-set", anchors)
                    },
                )
                contract = kernel.artifacts.resolve(
                    ArtifactReference.parse(
                        state.artifact_heads["visual/contract"]
                    )
                )["payload"]
                contract["anchor_slide_set_ref"] = state.artifact_heads[
                    "visual/anchors"
                ]
                rebind_visual_contract(
                    kernel, contract, f"rebind-anchor-lineage-{fault}"
                )
                with self.assertRaises((ContractValidationError, GateBlockedError)):
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )

    def test_projection_rejects_forged_embedded_and_g2_lineage(self) -> None:
        def forged_neutral_title(contract: dict) -> None:
            contract["slide_contracts"][0]["neutral_title"] = "伪造结论标题"

        def forged_anchor_reason(contract: dict) -> None:
            contract["anchor_identity"]["selection_reason"] = "伪造选择理由"

        def deleted_reading_deck(contract: dict) -> None:
            contract.pop("reading_deck")

        def partial_embedded_design(contract: dict) -> None:
            contract["deck_design_system"] = {
                "theme_proposition": contract["deck_design_system"][
                    "theme_proposition"
                ]
            }

        def stale_target_refs(contract: dict) -> None:
            contract["target_evidence_refs"] = []

        def stale_target_identities(contract: dict) -> None:
            contract["target_evidence_identities"][0][
                "application_version"
            ] = "forged-version"

        def stale_internal_reviews(contract: dict) -> None:
            contract["internal_review_refs"] = list(
                reversed(contract["internal_review_refs"])
            )

        variants = {
            "neutral-title": forged_neutral_title,
            "anchor-selection-reason": forged_anchor_reason,
            "deleted-reading-deck": deleted_reading_deck,
            "partial-embedded-design": partial_embedded_design,
            "stale-target-refs": stale_target_refs,
            "stale-target-identities": stale_target_identities,
            "stale-internal-review-refs": stale_internal_reviews,
        }
        for name, mutate in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                (
                    _design_ref,
                    _anchor_ref,
                    _contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
                contract = copy.deepcopy(
                    kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                )
                mutate(contract)
                rebind_visual_contract(kernel, contract, f"forge-lineage-{name}")
                with self.assertRaises((ContractValidationError, GateBlockedError)):
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )

    def test_projection_revalidates_post_g2_raw_target_head_drift(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                _contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            target_slot = "visual/target-evidence/G2/macos-powerpoint"
            target = copy.deepcopy(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(state.artifact_heads[target_slot])
                )["payload"]
            )
            target["source_pptx_ref"] = str(
                kernel.artifacts.put(
                    "native-pptx",
                    {
                        "pptx_sha256": target["pptx_sha256"],
                        "production_route": "strict-B",
                        "identity": "post-g2-forged-source",
                    },
                )
            )
            kernel.commit(
                command_id="forge-post-g2-target-head",
                expected_revision=state.revision,
                event_type="test.raw-target-forged-after-g2",
                artifact_updates={
                    target_slot: ("target-render-evidence", target)
                },
            )
            with self.assertRaises(GateBlockedError):
                VisualReviewService(kernel).project(session["review_session_id"])

    def test_projection_rejects_incomplete_reviewable_contract_shape(self) -> None:
        def missing_anchor_identity(contract: dict) -> None:
            contract.pop("anchor_identity")

        def empty_anchor_identity(contract: dict) -> None:
            contract["anchor_identity"] = {}

        def missing_anchor_slide_ids(contract: dict) -> None:
            contract["anchor_identity"].pop("slide_ids")

        def minimal_slide_contract(contract: dict) -> None:
            contract["slide_contracts"][0] = {"slide_id": "S01", "order": 1}

        def missing_required_text(contract: dict) -> None:
            contract["slide_contracts"][0].pop("page_family")

        def missing_required_container(contract: dict) -> None:
            contract["slide_contracts"][0]["visible_copy_blocks"] = []

        def wrong_optional_list_type(contract: dict) -> None:
            contract["slide_contracts"][0]["evidence_bindings"] = {}

        def missing_boundary_text(contract: dict) -> None:
            contract["slide_contracts"][0]["speaker_notes"] = ""

        def illegal_material_mode(contract: dict) -> None:
            contract["slide_contracts"][0]["material_mode"] = "unknown"

        variants = {
            "missing-anchor-identity": missing_anchor_identity,
            "empty-anchor-identity": empty_anchor_identity,
            "missing-anchor-slide-ids": missing_anchor_slide_ids,
            "minimal-slide-contract": minimal_slide_contract,
            "missing-required-text": missing_required_text,
            "missing-required-container": missing_required_container,
            "wrong-optional-list-type": wrong_optional_list_type,
            "missing-boundary-text": missing_boundary_text,
            "illegal-material-mode": illegal_material_mode,
        }
        for name, mutate in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                contract = kernel.artifacts.resolve(
                    ArtifactReference.parse(
                        state.artifact_heads["visual/contract"]
                    )
                )["payload"]
                mutate(contract)
                rebind_visual_contract(kernel, contract, f"forge-shape-{name}")
                with self.assertRaises((ContractValidationError, GateBlockedError)):
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )

    def test_projection_rejects_reading_deck_and_design_projection_gaps(self) -> None:
        for name in ("reading-deck", "design-system"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                if name == "reading-deck":
                    contract = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                    contract["reading_deck"] = {
                        "slides": [
                            {"slide_id": "S01", "order": 1},
                            {"slide_id": "S02", "order": 2},
                            {"slide_id": "S03", "order": 3},
                        ]
                    }
                    rebind_visual_contract(kernel, contract, "forge-reading-deck")
                else:
                    design = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/design-system"]
                        )
                    )["payload"]
                    design["theme_proposition"] = ""
                    state = kernel.commit(
                        command_id="forge-incomplete-design",
                        expected_revision=state.revision,
                        event_type="test.raw-design-forged",
                        artifact_updates={
                            "visual/design-system": (
                                "deck-design-system",
                                design,
                            )
                        },
                    )
                    contract = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                    contract["deck_design_system_ref"] = state.artifact_heads[
                        "visual/design-system"
                    ]
                    rebind_visual_contract(kernel, contract, "forge-design-lineage")
                with self.assertRaises((ContractValidationError, GateBlockedError)):
                    VisualReviewService(kernel).project(session["review_session_id"])

    def test_projection_rejects_anchor_identity_and_render_mismatch(self) -> None:
        for name in ("anchor-identity", "render-order"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                if name == "anchor-identity":
                    contract = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                    contract["anchor_identity"]["slide_ids"] = ["S01", "S02", "S04"]
                    contract_ref = str(kernel.artifacts.reference_for("visual-contract", contract))
                    state = kernel.commit(
                        command_id="forge-anchor-identity",
                        expected_revision=state.revision,
                        event_type="test.raw-anchor-identity-forged",
                        artifact_updates={"visual/contract": ("visual-contract", contract)},
                    )
                    session_payload = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.review_session_ref("visual-professional")
                        )
                    )["payload"]
                    session_payload["target_artifact_ref"] = contract_ref
                    kernel.commit(
                        command_id="rebind-anchor-identity-session",
                        expected_revision=state.revision,
                        event_type="test.raw-session-rebound",
                        artifact_updates={
                            "review/session/visual-professional": (
                                "review-session",
                                session_payload,
                            )
                        },
                    )
                else:
                    anchors = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/anchors"]
                        )
                    )["payload"]
                    anchors["render_assets"] = [
                        anchors["render_assets"][1],
                        anchors["render_assets"][0],
                        anchors["render_assets"][2],
                    ]
                    state = kernel.commit(
                        command_id="forge-anchor-render-order",
                        expected_revision=state.revision,
                        event_type="test.raw-anchor-render-forged",
                        artifact_updates={"visual/anchors": ("anchor-slide-set", anchors)},
                    )
                    contract = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.artifact_heads["visual/contract"]
                        )
                    )["payload"]
                    contract["anchor_slide_set_ref"] = state.artifact_heads[
                        "visual/anchors"
                    ]
                    contract_ref = str(
                        kernel.artifacts.reference_for("visual-contract", contract)
                    )
                    state = kernel.commit(
                        command_id="rebind-render-contract",
                        expected_revision=state.revision,
                        event_type="test.raw-contract-rebound",
                        artifact_updates={
                            "visual/contract": ("visual-contract", contract)
                        },
                    )
                    session_payload = kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            state.review_session_ref("visual-professional")
                        )
                    )["payload"]
                    session_payload["target_artifact_ref"] = contract_ref
                    kernel.commit(
                        command_id="rebind-render-session",
                        expected_revision=state.revision,
                        event_type="test.raw-session-rebound",
                        artifact_updates={
                            "review/session/visual-professional": (
                                "review-session",
                                session_payload,
                            )
                        },
                    )
                with self.assertRaises((ContractValidationError, GateBlockedError)):
                    VisualReviewService(kernel).project(session["review_session_id"])

    def test_projection_does_not_present_missing_receipts_as_pending_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            review = VisualReviewService(kernel)
            feedback = region_feedback(
                anchor_artifact_ref=anchor_ref,
                revision=state.revision,
            )
            _, _, state = review.submit_anchor_feedback_batch(
                command_id="submit-anchor-feedback",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                feedback=[feedback],
            )
            mark = {
                "mark_id": "mark-1", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "构图关系需要更明确",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            review.save_contract_review_marks(
                command_id="save-contract-marks", expected_revision=state.revision,
                review_session_id=session["review_session_id"], source_version="visual-v1", marks=[mark],
            )

            projection = review.project(session["review_session_id"])
            for saved in (
                projection["anchor_feedback_batch"],
                projection["contract_review_marks"],
            ):
                self.assertEqual(saved["host_notification_status"], "unavailable")
                self.assertEqual(saved["ai_receipt_status"], "unverified")

    def test_receipt_facts_are_bound_to_the_exact_saved_visual_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                _design_ref,
                anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            review = VisualReviewService(kernel)
            feedback = region_feedback(
                anchor_artifact_ref=anchor_ref,
                revision=state.revision,
            )
            batch_ref, _batch, state = review.submit_anchor_feedback_batch(
                command_id="submit-bound-anchor-feedback",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                feedback=[feedback],
            )

            def bound_receipt(
                kind: str,
                status: str,
                command: str,
                saved_artifact_ref: str,
            ) -> str:
                current = kernel.load()
                receipt_state = kernel.commit(
                    command_id=command,
                    expected_revision=current.revision,
                    event_type="test.bound-review-receipt-created",
                    artifact_updates={
                        f"test/receipt/{command}": (
                            kind,
                            {
                                "project_id": current.project_id,
                                "review_type": "visual-professional",
                                "review_session_id": session["review_session_id"],
                                "source_version": "visual-v1",
                                "saved_artifact_ref": saved_artifact_ref,
                                "status": status,
                                "recorded_at": "2026-08-15T02:00:00+08:00",
                            },
                        )
                    },
                )
                return receipt_state.artifact_heads[f"test/receipt/{command}"]

            host_receipt_ref = bound_receipt(
                "review-host-notification-receipt",
                "sent",
                "bound-anchor-host-receipt",
                batch_ref,
            )
            ReviewSessionService(kernel).record_host_notification_receipt(
                command_id="record-bound-anchor-host-receipt",
                expected_revision=kernel.load().revision,
                review_type="visual-professional",
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                saved_artifact_ref=batch_ref,
                receipt_ref=host_receipt_ref,
            )
            ai_receipt_ref = bound_receipt(
                "review-ai-receipt",
                "received",
                "bound-anchor-ai-receipt",
                batch_ref,
            )
            ReviewSessionService(kernel).record_ai_receipt(
                command_id="record-bound-anchor-ai-receipt",
                expected_revision=kernel.load().revision,
                review_type="visual-professional",
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                saved_artifact_ref=batch_ref,
                receipt_ref=ai_receipt_ref,
            )

            mark_revision = kernel.load().revision
            mark = {
                "mark_id": "mark-after-anchor-receipt",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "新标记不得继承旧锚点批次回执",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": mark_revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            mark_set_ref, _mark_set, _state = review.save_contract_review_marks(
                command_id="save-mark-after-anchor-receipt",
                expected_revision=mark_revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[mark],
            )

            projection = review.project(session["review_session_id"])
            self.assertEqual(projection["anchor_feedback_batch_ref"], batch_ref)
            self.assertEqual(projection["contract_review_marks_ref"], mark_set_ref)
            self.assertEqual(
                projection["anchor_feedback_batch"]["host_notification_status"],
                "sent",
            )
            self.assertEqual(
                projection["anchor_feedback_batch"]["ai_receipt_status"],
                "received",
            )
            self.assertEqual(
                projection["contract_review_marks"]["host_notification_status"],
                "unavailable",
            )
            self.assertEqual(
                projection["contract_review_marks"]["ai_receipt_status"],
                "unverified",
            )

            with self.assertRaises(ContractValidationError):
                ReviewSessionService(kernel).record_host_notification_receipt(
                    command_id="misbind-anchor-receipt-to-mark-set",
                    expected_revision=kernel.load().revision,
                    review_type="visual-professional",
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    saved_artifact_ref=mark_set_ref,
                    receipt_ref=host_receipt_ref,
                )

            for command_id, binding in (
                (
                    "reject-wrong-session-for-mark-set",
                    {
                        "review_session_id": "foreign-session",
                        "source_version": "visual-v1",
                        "saved_artifact_ref": mark_set_ref,
                    },
                ),
                (
                    "reject-wrong-source-for-mark-set",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v2",
                        "saved_artifact_ref": mark_set_ref,
                    },
                ),
                (
                    "reject-wrong-artifact-for-mark-set",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v1",
                        "saved_artifact_ref": contract_ref,
                    },
                ),
            ):
                with self.subTest(command_id=command_id):
                    with self.assertRaises(ContractValidationError):
                        ReviewSessionService(kernel).record_host_notification_receipt(
                            command_id=command_id,
                            expected_revision=kernel.load().revision,
                            review_type="visual-professional",
                            receipt_ref=host_receipt_ref,
                            **binding,
                        )

            mark_host_receipt_ref = bound_receipt(
                "review-host-notification-receipt",
                "sent",
                "bound-mark-host-receipt",
                mark_set_ref,
            )
            ReviewSessionService(kernel).record_host_notification_receipt(
                command_id="record-bound-mark-host-receipt",
                expected_revision=kernel.load().revision,
                review_type="visual-professional",
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                saved_artifact_ref=mark_set_ref,
                receipt_ref=mark_host_receipt_ref,
            )
            mark_ai_receipt_ref = bound_receipt(
                "review-ai-receipt",
                "received",
                "bound-mark-ai-receipt",
                mark_set_ref,
            )
            ReviewSessionService(kernel).record_ai_receipt(
                command_id="record-bound-mark-ai-receipt",
                expected_revision=kernel.load().revision,
                review_type="visual-professional",
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                saved_artifact_ref=mark_set_ref,
                receipt_ref=mark_ai_receipt_ref,
            )

            final_projection = review.project(session["review_session_id"])
            for saved in (
                final_projection["anchor_feedback_batch"],
                final_projection["contract_review_marks"],
            ):
                self.assertEqual(saved["host_notification_status"], "sent")
                self.assertEqual(saved["ai_receipt_status"], "received")
            projected_session = final_projection["review_session"]
            self.assertEqual(
                projected_session["host_notification_receipts"],
                {
                    batch_ref: host_receipt_ref,
                    mark_set_ref: mark_host_receipt_ref,
                },
            )
            self.assertEqual(
                projected_session["ai_receipts"],
                {
                    batch_ref: ai_receipt_ref,
                    mark_set_ref: mark_ai_receipt_ref,
                },
            )

    def test_projection_fails_closed_for_noncanonical_current_anchor_batch(self) -> None:
        def foreign_project(batch: dict) -> None:
            batch["project_id"] = "foreign-project"

        def foreign_session(batch: dict) -> None:
            batch["review_session_id"] = "foreign-session"

        def stale_contract(batch: dict) -> None:
            batch["visual_contract_ref"] = "visual-contract:v9999:foreign"

        def stale_design(batch: dict) -> None:
            batch["deck_design_system_ref"] = "deck-design-system:v9999:foreign"

        def stale_anchor_set(batch: dict) -> None:
            batch["anchor_slide_set_ref"] = "anchor-slide-set:v9999:foreign"

        def unknown_slide(batch: dict) -> None:
            batch["items"][0]["anchor_slide_id"] = "S99"

        def stale_item_ref(batch: dict) -> None:
            batch["items"][0]["anchor_artifact_ref"] = "anchor-slide-set:v9999:foreign"

        def stale_item_source(batch: dict) -> None:
            batch["items"][0]["visual_source_version"] = "visual-v0"

        def mismatched_item_revision(batch: dict) -> None:
            batch["items"][0]["revision"] = batch["revision"] + 1

        def non_user_creator(batch: dict) -> None:
            batch["items"][0]["created_by"] = "agent"

        def invalid_time(batch: dict) -> None:
            batch["submitted_at"] = "not-a-timestamp"

        variants = {
            "foreign-project": foreign_project,
            "foreign-session": foreign_session,
            "stale-contract": stale_contract,
            "stale-design": stale_design,
            "stale-anchor-set": stale_anchor_set,
            "unknown-slide": unknown_slide,
            "stale-item-ref": stale_item_ref,
            "stale-item-source": stale_item_source,
            "mismatched-item-revision": mismatched_item_revision,
            "non-user-creator": non_user_creator,
            "invalid-time": invalid_time,
        }
        for name, mutate in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                feedback = region_feedback(anchor_artifact_ref=anchor_ref, revision=state.revision)
                _batch_ref, batch, state = VisualReviewService(kernel).submit_anchor_feedback_batch(
                    command_id="submit-anchor-feedback",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    feedback=[feedback],
                )
                forged = copy.deepcopy(batch)
                mutate(forged)
                kernel.commit(
                    command_id=f"forge-anchor-batch-{name}",
                    expected_revision=state.revision,
                    event_type="test.raw-anchor-batch-forged",
                    artifact_updates={
                        "visual/anchor-feedback-batch": (
                            "visual-anchor-feedback-batch",
                            forged,
                        )
                    },
                )
                with self.assertRaises(ContractValidationError):
                    VisualReviewService(kernel).project(session["review_session_id"])

    def test_invalid_anchor_feedback_is_zero_write_and_does_not_consume_command_identity(
        self,
    ) -> None:
        variants = {
            "non-user-creator": {"created_by": "agent"},
            "invalid-timestamp": {"created_at": "not-a-timestamp"},
            "future-timestamp": {"created_at": "2999-01-01T00:00:00Z"},
            "timestamp-without-offset": {"created_at": "2026-08-15T00:00:00"},
        }
        for name, updates in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
                (
                    _design_ref,
                    anchor_ref,
                    _contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
                service = VisualReviewService(kernel)
                command_id = f"invalid-anchor-feedback-{name}"
                invalid = region_feedback(
                    anchor_artifact_ref=anchor_ref,
                    revision=state.revision,
                    **updates,
                )
                before_state = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_events = {
                    path.name: path.read_bytes()
                    for path in sorted(kernel.events_root.glob("*.json"))
                }
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    service.submit_anchor_feedback_batch(
                        command_id=command_id,
                        expected_revision=before_state.revision,
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        feedback=[invalid],
                    )

                rejected_state = kernel.load()
                self.assertEqual(rejected_state, before_state)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(
                    {
                        path.name: path.read_bytes()
                        for path in sorted(kernel.events_root.glob("*.json"))
                    },
                    before_events,
                )
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
                )
                self.assertNotIn(command_id, rejected_state.processed_commands)
                self.assertNotIn(
                    "visual/anchor-feedback-batch", rejected_state.artifact_heads
                )

                batch_ref, batch, committed = service.submit_anchor_feedback_batch(
                    command_id=command_id,
                    expected_revision=before_state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    feedback=[
                        region_feedback(
                            anchor_artifact_ref=anchor_ref,
                            revision=before_state.revision,
                            created_at="2000-01-01T00:00:00Z",
                            created_by="user",
                        )
                    ],
                )
                self.assertEqual(committed.revision, before_state.revision + 1)
                self.assertEqual(
                    committed.artifact_heads["visual/anchor-feedback-batch"],
                    batch_ref,
                )
                self.assertEqual(committed.processed_commands[command_id], committed.revision)
                self.assertEqual(batch["items"][0]["created_by"], "user")

    def test_anchor_batch_is_immutable_source_bound_and_does_not_change_g3(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, anchor_ref, _contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            feedback = region_feedback(
                anchor_artifact_ref=anchor_ref,
                revision=state.revision,
            )
            before_gates = dict(state.gate_status)
            batch_ref, batch, state = VisualReviewService(kernel).submit_anchor_feedback_batch(
                command_id="submit-anchor-feedback",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                feedback=[feedback, {**feedback, "feedback_id": "feedback-2", "order": 2, "comment": "第二条意见"}],
            )
            self.assertTrue(batch["immutable_after_submit"])
            self.assertEqual(batch["persistence_status"], "saved")
            self.assertEqual(batch["host_notification_status"], "not-requested")
            self.assertEqual(batch["ai_receipt_status"], "pending")
            self.assertEqual(state.gate_status, before_gates)
            replay_ref, replay_batch, replay_state = VisualReviewService(kernel).submit_anchor_feedback_batch(
                command_id="submit-anchor-feedback",
                expected_revision=feedback["revision"],
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                feedback=[feedback, {**feedback, "feedback_id": "feedback-2", "order": 2, "comment": "第二条意见"}],
            )
            self.assertEqual((replay_ref, replay_batch), (batch_ref, batch))
            self.assertEqual(replay_state.revision, state.revision)
            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).submit_anchor_feedback_batch(
                    command_id="submit-anchor-feedback",
                    expected_revision=feedback["revision"],
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    feedback=[{**feedback, "comment": "同一命令不能改变语义"}],
                )
            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).submit_anchor_feedback_batch(
                    command_id="second-anchor-batch",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    feedback=[feedback],
                )
            self.assertEqual(kernel.load().artifact_heads["visual/anchor-feedback-batch"], batch_ref)

    def test_contract_marks_use_an_independent_slot_and_stale_writes_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            mark = {
                "mark_id": "mark-1", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "构图关系需要更明确",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            marks_ref, marks, state = service.save_contract_review_marks(
                command_id="save-contract-marks", expected_revision=state.revision,
                review_session_id=session["review_session_id"], source_version="visual-v1", marks=[mark],
            )
            self.assertEqual(marks["marks"][0]["mark_id"], "mark-1")
            self.assertEqual(state.artifact_heads["visual/contract-review-marks"], marks_ref)
            self.assertNotIn("visual/anchor-feedback-batch", state.artifact_heads)
            replay_ref, replay_marks, replay_state = service.save_contract_review_marks(
                command_id="save-contract-marks", expected_revision=mark["revision"],
                review_session_id=session["review_session_id"], source_version="visual-v1", marks=[mark],
            )
            self.assertEqual((replay_ref, replay_marks), (marks_ref, marks))
            self.assertEqual(replay_state.revision, state.revision)
            with self.assertRaises(ContractValidationError):
                service.save_contract_review_marks(
                    command_id="save-contract-marks", expected_revision=mark["revision"],
                    review_session_id=session["review_session_id"], source_version="visual-v1",
                    marks=[{**mark, "comment": "同一命令不能改变语义"}],
                )
            frozen = kernel.load()
            with self.assertRaises(ReviewSourceStaleError):
                service.save_contract_review_marks(
                    command_id="stale-marks", expected_revision=frozen.revision,
                    review_session_id=session["review_session_id"], source_version="visual-v0", marks=[mark],
                )
            self.assertEqual(kernel.load(), frozen)

    def test_invalid_contract_marks_are_zero_write_and_do_not_consume_command_identity(self) -> None:
        variants = {
            "dual-target": {"deck_section_id": "deck-design-system"},
            "unknown-slide": {"slide_id": "S99"},
            "unknown-slide-field": {"target_key": "future_backend_field"},
            "unknown-deck-field": {
                "slide_id": "",
                "deck_section_id": "deck-design-system",
                "target_key": "future_backend_field",
            },
            "forged-author": {"created_by": "agent"},
            "invalid-time": {"created_at": "not-a-timestamp"},
            "future-time": {"created_at": "2999-01-01T00:00:00Z"},
            "fabricated-text-anchor": {
                "target_type": "text-range",
                "selected_text": "不存在于当前构图意图",
                "context_before": "伪造前文",
                "context_after": "伪造后文",
            },
        }
        for name, updates in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
                service = VisualReviewService(kernel)
                command_id = f"invalid-contract-mark-{name}"
                base = {
                    "mark_id": "mark-invalid",
                    "target_type": "contract-field",
                    "slide_id": "S01",
                    "deck_section_id": "",
                    "target_key": "composition_intent",
                    "selected_text": "",
                    "context_before": "",
                    "context_after": "",
                    "comment": "需要修改",
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                invalid = {**base, **updates}
                before = kernel.load()

                with self.assertRaises((ContractValidationError, ReviewSourceStaleError)):
                    service.save_contract_review_marks(
                        command_id=command_id,
                        expected_revision=before.revision,
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        marks=[invalid],
                    )

                rejected = kernel.load()
                self.assertEqual(rejected, before)
                self.assertNotIn(command_id, rejected.processed_commands)
                self.assertNotIn("visual/contract-review-marks", rejected.artifact_heads)

                valid = {
                    **base,
                    "target_type": "text-range",
                    "selected_text": "右因果链",
                    "context_before": "左事实、",
                    "context_after": "",
                }
                _ref, mark_set, committed = service.save_contract_review_marks(
                    command_id=command_id,
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[valid],
                )
                self.assertEqual(committed.revision, before.revision + 1)
                self.assertEqual(mark_set["marks"][0]["created_by"], "user")


if __name__ == "__main__":
    unittest.main()
