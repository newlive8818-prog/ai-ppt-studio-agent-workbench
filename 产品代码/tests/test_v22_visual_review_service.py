from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from unittest import mock
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
from ai_ppt_studio.application.review_commands import fingerprint
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
from tests.v22_hard_gate_fixtures import semantic_checks
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
                semantic_check_results=semantic_checks(
                    "evidence", reading_blueprint_ref
                ),
                reviewer_mode="isolated-review-task",
            )
            hard_gates.run_presales_reading_gate(
                command_id="visual-review-seed-reading-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "presales-reading", reading_blueprint_ref
                ),
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
            "visual_compilation_plan_ref": kernel.load().artifact_heads[
                "visual/compilation-plan"
            ],
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

    def test_projection_exposes_only_closed_v23_visual_brief_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )

            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                set(projection),
                {
                    "project_id",
                    "project_name",
                    "review_type",
                    "review_session_id",
                    "review_session",
                    "source_version",
                    "revision",
                    "authoritative_revision",
                    "visual_contract_ref",
                    "visual_brief_ref",
                    "visual_brief",
                    "deck_design_system_ref",
                    "deck_design_system",
                    "anchor_slide_set_ref",
                    "anchors",
                    "anchor_identity",
                    "slide_visual_contracts",
                    "anchor_feedback_batch",
                    "anchor_feedback_batch_ref",
                    "contract_review_marks",
                    "contract_review_marks_ref",
                    "host_submission_capability",
                    "ai_receipt_capability",
                },
            )
            self.assertEqual(
                projection["visual_brief_ref"],
                state.artifact_heads["visual/brief"],
            )
            self.assertEqual(
                set(projection["visual_brief"]),
                {
                    "design_proposition",
                    "audience_fit",
                    "decision_task",
                    "design_stance",
                    "emotional_boundary",
                    "brand_boundary",
                    "density_strategy",
                    "narrative_rhythm",
                    "imagery_strategy",
                    "diagram_strategy",
                    "powerpoint_constraints",
                    "forbidden_patterns",
                    "five_second_test_contract",
                    "design_philosophy_refs",
                },
            )
            self.assertEqual(
                projection["visual_brief"]["design_philosophy_refs"], []
            )

            for forbidden in (
                "visual_compilation_plan_ref",
                "visual_compilation_plan",
                "compiler_version",
                "gate_status",
                "role_runs",
                "lineage",
                "future_backend_governance",
            ):
                self.assertNotIn(forbidden, projection)

    def test_projection_exposes_only_closed_v23_design_system_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, _state = (
                seed_visual_review(kernel)
            )

            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                set(projection["deck_design_system"]),
                {
                    "theme_proposition",
                    "composition_grammar",
                    "color_tokens",
                    "typography_tokens",
                    "page_families",
                    "density_rhythm",
                    "cross_slide_rhythm_rules",
                    "emphasis_budget",
                    "imagery_strategy",
                    "image_language",
                    "diagram_strategy",
                    "diagram_language",
                    "table_strategy",
                    "editability_rules",
                    "accessibility_rules",
                    "forbidden_patterns",
                    "five_second_test_rules",
                    "anchor_specification",
                    "production_route",
                    "fallback_fonts",
                },
            )

    def test_projection_exposes_only_closed_v23_slide_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, _state = (
                seed_visual_review(kernel)
            )

            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                set(projection["slide_visual_contracts"][0]),
                {
                    "slide_id",
                    "order",
                    "neutral_title",
                    "page_family",
                    "anchor_title",
                    "validation_purpose",
                    "core_claim",
                    "visible_copy",
                    "speaker_notes",
                    "source_refs",
                    "communication_goal",
                    "composition_intent",
                    "information_hierarchy",
                    "reading_order",
                    "regions",
                    "object_relationships",
                    "diagram_chart_table_treatment",
                    "image_selection_and_crop",
                    "color_application",
                    "typography_application",
                    "native_bitmap_routing",
                    "editability_requirements",
                    "fallbacks",
                    "acceptance_criteria",
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
                },
            )

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

    def test_projection_rejects_noncurrent_visual_compilation_plan_without_writes(
        self,
    ) -> None:
        for fault in ("missing", "forged", "wrong-kind", "stale"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
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
                if fault == "missing":
                    contract.pop("visual_compilation_plan_ref")
                elif fault == "wrong-kind":
                    contract["visual_compilation_plan_ref"] = state.artifact_heads[
                        "visual/contracts"
                    ]
                else:
                    current_plan = copy.deepcopy(
                        kernel.artifacts.resolve(
                            ArtifactReference.parse(
                                state.artifact_heads["visual/compilation-plan"]
                            )
                        )["payload"]
                    )
                    if fault == "forged":
                        current_plan["forged_identity"] = "detached-plan"
                    else:
                        current_plan["source_revision"] = max(
                            0, int(current_plan["source_revision"]) - 1
                        )
                    contract["visual_compilation_plan_ref"] = str(
                        kernel.artifacts.put(
                            "visual-compilation-plan", current_plan
                        )
                    )
                rebind_visual_contract(
                    kernel, contract, f"forge-compilation-plan-{fault}"
                )
                before = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )

                after = kernel.load()
                self.assertEqual(after, before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
                )

    def test_mark_save_rejects_noncurrent_visual_compilation_plan_without_writes(
        self,
    ) -> None:
        for fault in ("missing", "forged", "wrong-kind", "stale"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
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
                if fault == "missing":
                    contract.pop("visual_compilation_plan_ref")
                elif fault == "wrong-kind":
                    contract["visual_compilation_plan_ref"] = state.artifact_heads[
                        "visual/contracts"
                    ]
                else:
                    current_plan = copy.deepcopy(
                        kernel.artifacts.resolve(
                            ArtifactReference.parse(
                                state.artifact_heads["visual/compilation-plan"]
                            )
                        )["payload"]
                    )
                    if fault == "forged":
                        current_plan["forged_identity"] = "detached-plan"
                    else:
                        current_plan["source_revision"] = max(
                            0, int(current_plan["source_revision"]) - 1
                        )
                    contract["visual_compilation_plan_ref"] = str(
                        kernel.artifacts.put(
                            "visual-compilation-plan", current_plan
                        )
                    )
                rebind_visual_contract(
                    kernel, contract, f"forge-mark-compilation-plan-{fault}"
                )
                before = kernel.load()
                forged_contract_ref = before.artifact_heads["visual/contract"]
                command_id = f"reject-mark-compilation-plan-{fault}"
                mark = {
                    "mark_id": "mark-plan-lineage",
                    "target_type": "contract-field",
                    "slide_id": "S01",
                    "deck_section_id": "",
                    "target_key": "composition_intent",
                    "selected_text": "",
                    "context_before": "",
                    "context_after": "",
                    "comment": "构图关系需要更明确",
                    "visual_contract_ref": forged_contract_ref,
                    "source_version": "visual-v1",
                    "revision": before.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    VisualReviewService(kernel).save_contract_review_marks(
                        command_id=command_id,
                        expected_revision=before.revision,
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        marks=[mark],
                    )

                after = kernel.load()
                self.assertEqual(after, before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
                )
                self.assertNotIn(command_id, after.processed_commands)
                self.assertNotIn(
                    "visual/contract-review-marks", after.artifact_heads
                )

    def test_mark_save_replay_revalidates_current_visual_compilation_plan_without_writes(
        self,
    ) -> None:
        for fault in ("missing", "forged", "wrong-kind", "stale"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
                (
                    _design_ref,
                    _anchor_ref,
                    contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
                command_id = f"replay-mark-compilation-plan-{fault}"
                mark = {
                    "mark_id": "mark-plan-lineage-replay",
                    "target_type": "contract-field",
                    "slide_id": "S01",
                    "deck_section_id": "",
                    "target_key": "composition_intent",
                    "selected_text": "",
                    "context_before": "",
                    "context_after": "",
                    "comment": "构图关系需要更明确",
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                service = VisualReviewService(kernel)
                service.save_contract_review_marks(
                    command_id=command_id,
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark],
                )

                contract = copy.deepcopy(
                    kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            kernel.load().artifact_heads["visual/contract"]
                        )
                    )["payload"]
                )
                if fault == "missing":
                    contract.pop("visual_compilation_plan_ref")
                elif fault == "wrong-kind":
                    contract["visual_compilation_plan_ref"] = kernel.load().artifact_heads[
                        "visual/contracts"
                    ]
                else:
                    current_plan = copy.deepcopy(
                        kernel.artifacts.resolve(
                            ArtifactReference.parse(
                                kernel.load().artifact_heads[
                                    "visual/compilation-plan"
                                ]
                            )
                        )["payload"]
                    )
                    if fault == "forged":
                        current_plan["forged_identity"] = "detached-plan"
                    else:
                        current_plan["source_revision"] = max(
                            0, int(current_plan["source_revision"]) - 1
                        )
                    contract["visual_compilation_plan_ref"] = str(
                        kernel.artifacts.put(
                            "visual-compilation-plan", current_plan
                        )
                    )
                rebind_visual_contract(
                    kernel, contract, f"forge-replay-compilation-plan-{fault}"
                )
                before = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    service.save_contract_review_marks(
                        command_id=command_id,
                        expected_revision=mark["revision"],
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        marks=[mark],
                    )

                self.assertEqual(kernel.load(), before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
                )

    def test_anchor_batch_replay_revalidates_current_visual_compilation_plan_without_writes(
        self,
    ) -> None:
        for fault in ("missing", "forged", "wrong-kind", "stale"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
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
                command_id = f"replay-anchor-compilation-plan-{fault}"
                feedback = region_feedback(
                    anchor_artifact_ref=anchor_ref,
                    revision=state.revision,
                )
                service = VisualReviewService(kernel)
                service.submit_anchor_feedback_batch(
                    command_id=command_id,
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    feedback=[feedback],
                )

                contract = copy.deepcopy(
                    kernel.artifacts.resolve(
                        ArtifactReference.parse(
                            kernel.load().artifact_heads["visual/contract"]
                        )
                    )["payload"]
                )
                if fault == "missing":
                    contract.pop("visual_compilation_plan_ref")
                elif fault == "wrong-kind":
                    contract["visual_compilation_plan_ref"] = kernel.load().artifact_heads[
                        "visual/contracts"
                    ]
                else:
                    current_plan = copy.deepcopy(
                        kernel.artifacts.resolve(
                            ArtifactReference.parse(
                                kernel.load().artifact_heads[
                                    "visual/compilation-plan"
                                ]
                            )
                        )["payload"]
                    )
                    if fault == "forged":
                        current_plan["forged_identity"] = "detached-plan"
                    else:
                        current_plan["source_revision"] = max(
                            0, int(current_plan["source_revision"]) - 1
                        )
                    contract["visual_compilation_plan_ref"] = str(
                        kernel.artifacts.put(
                            "visual-compilation-plan", current_plan
                        )
                    )
                rebind_visual_contract(
                    kernel, contract, f"forge-replay-anchor-compilation-plan-{fault}"
                )
                before = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    service.submit_anchor_feedback_batch(
                        command_id=command_id,
                        expected_revision=feedback["revision"],
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        feedback=[feedback],
                    )

                self.assertEqual(kernel.load(), before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
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

    def test_duplicate_contract_mark_ids_are_zero_write_and_do_not_consume_command_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            service = VisualReviewService(kernel)
            command_id = "reject-duplicate-contract-mark-ids"
            mark = {
                "mark_id": "duplicate-id",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "first",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
                "anchor_representation_version": "browser-v2",
            }
            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.save_contract_review_marks(
                    command_id=command_id,
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark, {**mark, "comment": "second"}],
                )

            rejected = kernel.load()
            self.assertEqual(rejected, before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            self.assertNotIn(command_id, rejected.processed_commands)
            self.assertNotIn(
                "visual/contract-review-marks",
                rejected.artifact_heads,
            )
            marks_ref, mark_set, committed = service.save_contract_review_marks(
                command_id=command_id,
                expected_revision=before.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[mark],
            )
            self.assertEqual(
                [item["mark_id"] for item in mark_set["marks"]],
                ["duplicate-id"],
            )
            self.assertEqual(mark_set["marks"][0]["comment"], "first")
            self.assertEqual(committed.revision, before.revision + 1)
            self.assertEqual(
                committed.processed_commands[command_id],
                committed.revision,
            )
            self.assertEqual(
                committed.artifact_heads["visual/contract-review-marks"],
                marks_ref,
            )

    def test_projection_rejects_foreign_current_contract_marks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            mark = {
                "mark_id": "mark-1", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "构图关系需要更明确",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            _mark_ref, mark_set, state = VisualReviewService(kernel).save_contract_review_marks(
                command_id="save-contract-marks",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[mark],
            )
            forged = copy.deepcopy(mark_set)
            forged["project_id"] = "foreign-project"
            forged["review_session_id"] = "foreign-session"
            forged["visual_contract_ref"] = "artifact://visual-contract/" + "f" * 64
            forged["marks"][0]["visual_contract_ref"] = forged["visual_contract_ref"]
            kernel.commit(
                command_id="forge-current-contract-marks",
                expected_revision=state.revision,
                event_type="test.raw-contract-review-marks-forgery",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        forged,
                    )
                },
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(Path(folder))): path.read_bytes()
                for path in sorted(Path(folder).rglob("*"))
                if path.is_file()
            }
            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).project(session["review_session_id"])
            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(Path(folder))): path.read_bytes()
                    for path in sorted(Path(folder).rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_projection_rejects_contract_marks_older_than_the_review_session(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            mark = {
                "mark_id": "mark-1", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "构图关系需要更明确",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            _mark_ref, mark_set, state = VisualReviewService(
                kernel
            ).save_contract_review_marks(
                command_id="save-contract-marks-before-stale-forgery",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[mark],
            )
            forged = copy.deepcopy(mark_set)
            stale_revision = max(0, int(session["revision"]) - 1)
            forged["revision"] = stale_revision
            forged["marks"][0]["revision"] = stale_revision
            kernel.commit(
                command_id="forge-stale-current-contract-marks",
                expected_revision=state.revision,
                event_type="test.raw-contract-review-marks-stale-forgery",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        forged,
                    )
                },
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }
            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).project(session["review_session_id"])
            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_current_browser_v2_marks_require_exact_save_event_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            original_mark = {
                "mark_id": "current-browser-v2-mark",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "真实用户意见",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
                "anchor_representation_version": "browser-v2",
            }
            _original_ref, mark_set, committed = (
                service.save_contract_review_marks(
                    command_id="save-current-browser-v2-mark",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[original_mark],
                )
            )
            forged_set = copy.deepcopy(mark_set)
            forged_set["marks"][0]["comment"] = "伪造用户意见"
            forged_ref = str(
                kernel.artifacts.put(
                    "visual-contract-review-mark-set",
                    forged_set,
                )
            )
            event_path = (
                kernel.events_root / f"r{committed.revision:08d}.json"
            )
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["artifact_heads"]["visual/contract-review-marks"] = (
                forged_ref
            )
            event_path.write_text(
                json.dumps(event, ensure_ascii=False),
                encoding="utf-8",
            )
            state_payload = json.loads(
                kernel.state_path.read_text(encoding="utf-8")
            )
            state_payload["artifact_heads"][
                "visual/contract-review-marks"
            ] = forged_ref
            kernel.state_path.write_text(
                json.dumps(state_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            clean_mark = {
                **original_mark,
                "mark_id": "clean-current-mark",
                "target_type": "contract-field",
                "selected_text": "",
                "context_before": "",
                "comment": "新的合法意见",
                "revision": before.revision,
            }
            clean_mark.pop("anchor_representation_version")
            _clean_ref, merged, _clean_state = (
                service.save_contract_review_marks(
                    command_id="save-after-forged-current-provenance",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[clean_mark],
                )
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["clean-current-mark"],
            )

    def test_current_mark_set_id_is_bound_to_the_save_command(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            mark = {
                "mark_id": "mark-with-command-bound-set-id",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "集合身份必须闭合",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            _mark_ref, mark_set, committed = (
                service.save_contract_review_marks(
                    command_id="save-command-bound-mark-set-id",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark],
                )
            )
            changed_set = {
                **copy.deepcopy(mark_set),
                "mark_set_id": "changed-mark-set-id",
            }
            changed_ref = str(
                kernel.artifacts.put(
                    "visual-contract-review-mark-set",
                    changed_set,
                )
            )
            event_path = (
                kernel.events_root / f"r{committed.revision:08d}.json"
            )
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["artifact_heads"]["visual/contract-review-marks"] = (
                changed_ref
            )
            event_path.write_text(
                json.dumps(event, ensure_ascii=False),
                encoding="utf-8",
            )
            state_payload = json.loads(
                kernel.state_path.read_text(encoding="utf-8")
            )
            state_payload["artifact_heads"][
                "visual/contract-review-marks"
            ] = changed_ref
            kernel.state_path.write_text(
                json.dumps(state_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_current_mark_set_binds_historical_marks_to_previous_save(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            historical_mark = {
                "mark_id": "historical-browser-v2-mark",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "可信历史意见",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
                "anchor_representation_version": "browser-v2",
            }
            _first_ref, _first_set, first_state = (
                service.save_contract_review_marks(
                    command_id="save-historical-browser-v2-mark",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[historical_mark],
                )
            )
            latest_mark = {
                **historical_mark,
                "mark_id": "latest-contract-field-mark",
                "target_type": "contract-field",
                "selected_text": "",
                "context_before": "",
                "comment": "可信最新意见",
                "revision": first_state.revision,
            }
            latest_mark.pop("anchor_representation_version")
            _latest_ref, latest_set, latest_state = (
                service.save_contract_review_marks(
                    command_id="save-latest-contract-field-mark",
                    expected_revision=first_state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[latest_mark],
                )
            )

            changed_set = copy.deepcopy(latest_set)
            changed_set["marks"][0]["comment"] = "被改写的历史意见"
            changed_ref = str(
                kernel.artifacts.put(
                    "visual-contract-review-mark-set",
                    changed_set,
                )
            )
            event_path = (
                kernel.events_root / f"r{latest_state.revision:08d}.json"
            )
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["artifact_heads"]["visual/contract-review-marks"] = (
                changed_ref
            )
            event_path.write_text(
                json.dumps(event, ensure_ascii=False),
                encoding="utf-8",
            )
            state_payload = json.loads(
                kernel.state_path.read_text(encoding="utf-8")
            )
            state_payload["artifact_heads"][
                "visual/contract-review-marks"
            ] = changed_ref
            kernel.state_path.write_text(
                json.dumps(state_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            clean_mark = {
                **latest_mark,
                "mark_id": "clean-mark-after-history-check",
                "comment": "下一条合法意见",
                "revision": before.revision,
            }
            _clean_ref, merged, _clean_state = (
                service.save_contract_review_marks(
                    command_id="save-after-changed-historical-mark",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[clean_mark],
                )
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["clean-mark-after-history-check"],
            )
            self.assertEqual(
                [item["comment"] for item in merged["marks"]],
                ["下一条合法意见"],
            )

    def test_current_mark_set_requires_the_latest_previous_head(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)

            mark_a = {
                "mark_id": "mark-A",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "意见 A",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
                "anchor_representation_version": "browser-v2",
            }
            mark_a_ref, _set_a, state_a = (
                service.save_contract_review_marks(
                    command_id="save-mark-A",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_a],
                )
            )
            mark_b = {
                **mark_a,
                "mark_id": "mark-B",
                "target_type": "contract-field",
                "selected_text": "",
                "context_before": "",
                "comment": "意见 B",
                "revision": state_a.revision,
            }
            mark_b.pop("anchor_representation_version")
            _mark_b_ref, _set_b, state_b = (
                service.save_contract_review_marks(
                    command_id="save-mark-B",
                    expected_revision=state_a.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_b],
                )
            )
            mark_c = {
                **mark_b,
                "mark_id": "mark-C",
                "comment": "意见 C",
                "revision": state_b.revision,
            }
            _mark_c_ref, set_c, state_c = (
                service.save_contract_review_marks(
                    command_id="save-mark-C",
                    expected_revision=state_b.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_c],
                )
            )

            previous_event_path = (
                kernel.events_root / f"r{state_b.revision:08d}.json"
            )
            previous_event = json.loads(
                previous_event_path.read_text(encoding="utf-8")
            )
            previous_event["artifact_heads"][
                "visual/contract-review-marks"
            ] = mark_a_ref
            previous_event_path.write_text(
                json.dumps(previous_event, ensure_ascii=False),
                encoding="utf-8",
            )
            changed_set = {
                **copy.deepcopy(set_c),
                "marks": [
                    copy.deepcopy(set_c["marks"][0]),
                    copy.deepcopy(set_c["marks"][2]),
                ],
            }
            changed_ref = str(
                kernel.artifacts.put(
                    "visual-contract-review-mark-set",
                    changed_set,
                )
            )
            current_event_path = (
                kernel.events_root / f"r{state_c.revision:08d}.json"
            )
            current_event = json.loads(
                current_event_path.read_text(encoding="utf-8")
            )
            current_event["artifact_heads"][
                "visual/contract-review-marks"
            ] = changed_ref
            current_event_path.write_text(
                json.dumps(current_event, ensure_ascii=False),
                encoding="utf-8",
            )
            state_payload = json.loads(
                kernel.state_path.read_text(encoding="utf-8")
            )
            state_payload["artifact_heads"][
                "visual/contract-review-marks"
            ] = changed_ref
            kernel.state_path.write_text(
                json.dumps(state_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            mark_d = {
                **mark_b,
                "mark_id": "mark-D",
                "comment": "意见 D",
                "revision": before.revision,
            }
            _mark_d_ref, merged, _state_d = (
                service.save_contract_review_marks(
                    command_id="save-after-previous-head-check",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_d],
                )
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["mark-D"],
            )

    def test_current_mark_set_cannot_reroot_after_invalid_previous_history(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)

            mark_a = {
                "mark_id": "reroot-mark-A",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "意见 A",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            mark_a_ref, _set_a, state_a = (
                service.save_contract_review_marks(
                    command_id="save-reroot-mark-A",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_a],
                )
            )
            mark_b = {
                **mark_a,
                "mark_id": "reroot-mark-B",
                "comment": "意见 B",
                "revision": state_a.revision,
            }
            _mark_b_ref, _set_b, state_b = (
                service.save_contract_review_marks(
                    command_id="save-reroot-mark-B",
                    expected_revision=state_a.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_b],
                )
            )
            mark_c = {
                **mark_b,
                "mark_id": "reroot-mark-C",
                "comment": "意见 C",
                "revision": state_b.revision,
            }
            _mark_c_ref, set_c, state_c = (
                service.save_contract_review_marks(
                    command_id="save-reroot-mark-C",
                    expected_revision=state_b.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_c],
                )
            )

            previous_event_path = (
                kernel.events_root / f"r{state_b.revision:08d}.json"
            )
            previous_event = json.loads(
                previous_event_path.read_text(encoding="utf-8")
            )
            previous_event["artifact_heads"][
                "visual/contract-review-marks"
            ] = mark_a_ref
            previous_event_path.write_text(
                json.dumps(previous_event, ensure_ascii=False),
                encoding="utf-8",
            )
            rerooted_set = {
                **copy.deepcopy(set_c),
                "marks": [copy.deepcopy(set_c["marks"][2])],
            }
            rerooted_ref = str(
                kernel.artifacts.put(
                    "visual-contract-review-mark-set",
                    rerooted_set,
                )
            )
            current_event_path = (
                kernel.events_root / f"r{state_c.revision:08d}.json"
            )
            current_event = json.loads(
                current_event_path.read_text(encoding="utf-8")
            )
            current_event["artifact_heads"][
                "visual/contract-review-marks"
            ] = rerooted_ref
            current_event_path.write_text(
                json.dumps(current_event, ensure_ascii=False),
                encoding="utf-8",
            )
            state_payload = json.loads(
                kernel.state_path.read_text(encoding="utf-8")
            )
            state_payload["artifact_heads"][
                "visual/contract-review-marks"
            ] = rerooted_ref
            kernel.state_path.write_text(
                json.dumps(state_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_current_mark_set_head_must_remain_continuous_after_save(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            mark_a = {
                "mark_id": "continuous-mark-A",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "意见 A",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            _mark_a_ref, set_a, state_a = (
                service.save_contract_review_marks(
                    command_id="save-continuous-mark-A",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_a],
                )
            )
            mark_b = {
                **mark_a,
                "mark_id": "continuous-mark-B",
                "comment": "意见 B",
                "revision": state_a.revision,
            }
            _mark_b_ref, _set_b, state_b = (
                service.save_contract_review_marks(
                    command_id="save-continuous-mark-B",
                    expected_revision=state_a.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_b],
                )
            )
            kernel.commit(
                command_id="restore-earlier-contract-mark-head",
                expected_revision=state_b.revision,
                event_type="test.restore-earlier-contract-mark-head",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        set_a,
                    )
                },
            )

            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            mark_c = {
                **mark_a,
                "mark_id": "continuous-mark-C",
                "comment": "意见 C",
                "revision": before.revision,
            }
            _mark_c_ref, merged, state_c = (
                service.save_contract_review_marks(
                    command_id="save-after-head-continuity-check",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark_c],
                )
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["continuous-mark-C"],
            )
            projection = service.project(session["review_session_id"])
            self.assertEqual(
                projection["contract_review_marks"]["marks"],
                merged["marks"],
            )
            self.assertEqual(state_c.revision, before.revision + 1)

    def test_large_existing_mark_update_uses_semantic_fingerprint_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            initial_marks = [
                {
                    "mark_id": f"mark-{index}",
                    "target_type": "contract-field",
                    "slide_id": "S01",
                    "deck_section_id": "",
                    "target_key": "composition_intent",
                    "selected_text": "",
                    "context_before": "",
                    "context_after": "",
                    "comment": f"初始意见 {index}",
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                for index in range(9)
            ]
            _initial_ref, initial_set, initial_state = (
                service.save_contract_review_marks(
                    command_id="save-nine-initial-marks",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=initial_marks,
                )
            )
            updated_marks = [
                {
                    **item,
                    "comment": f"更新意见 {item['mark_id']}",
                    "revision": initial_state.revision,
                }
                for item in reversed(initial_set["marks"])
            ]
            updated_ref, updated_set, updated_state = (
                service.save_contract_review_marks(
                    command_id="update-nine-marks-in-reverse",
                    expected_revision=initial_state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=updated_marks,
                )
            )

            projection = service.project(session["review_session_id"])

            self.assertEqual(
                [item["mark_id"] for item in updated_set["marks"]],
                [f"mark-{index}" for index in range(9)],
            )
            self.assertEqual(
                projection["contract_review_marks"]["mark_set_id"],
                updated_set["mark_set_id"],
            )
            self.assertEqual(
                projection["contract_review_marks"]["revision"],
                updated_set["revision"],
            )
            self.assertEqual(
                projection["contract_review_marks"]["marks"],
                updated_set["marks"],
            )
            replay_ref, replay_set, replay_state = (
                service.save_contract_review_marks(
                    command_id="update-nine-marks-in-reverse",
                    expected_revision=initial_state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=updated_marks,
                )
            )
            self.assertEqual(
                (replay_ref, replay_set, replay_state.revision),
                (updated_ref, updated_set, updated_state.revision),
            )

    def test_saving_contract_marks_drops_untrusted_current_marks_before_merge(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            first_mark = {
                "mark_id": "old-mark", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "旧意见",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            _mark_ref, mark_set, state = service.save_contract_review_marks(
                command_id="save-old-contract-mark",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[first_mark],
            )
            forged = copy.deepcopy(mark_set)
            forged["review_session_id"] = "foreign-session"
            forged["marks"][0]["visual_contract_ref"] = "artifact://visual-contract/" + "f" * 64
            kernel.commit(
                command_id="forge-current-contract-marks-before-merge",
                expected_revision=state.revision,
                event_type="test.raw-contract-review-marks-forgery-before-merge",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        forged,
                    )
                },
            )
            state = kernel.load()
            second_mark = {
                **first_mark,
                "mark_id": "new-mark",
                "comment": "新意见",
                "revision": state.revision,
            }

            _mark_ref, merged, _state = service.save_contract_review_marks(
                command_id="save-new-contract-mark",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[second_mark],
            )

            self.assertEqual([item["mark_id"] for item in merged["marks"]], ["new-mark"])

    def test_saving_contract_marks_rejects_malformed_current_set_without_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            service = VisualReviewService(kernel)
            first_mark = {
                "mark_id": "old-mark", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "旧意见",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            _mark_ref, mark_set, state = service.save_contract_review_marks(
                command_id="save-old-contract-mark-before-malformation",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[first_mark],
            )
            malformed = copy.deepcopy(mark_set)
            malformed.pop("mark_set_id")
            kernel.commit(
                command_id="malform-current-contract-marks-before-save",
                expected_revision=state.revision,
                event_type="test.raw-contract-review-marks-malformation-before-save",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        malformed,
                    )
                },
            )
            before = kernel.load()
            before_state_bytes = kernel.state_path.read_bytes()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }
            second_mark = {
                **first_mark,
                "mark_id": "new-mark",
                "comment": "新意见",
                "revision": before.revision,
            }

            with self.assertRaises(ContractValidationError):
                service.save_contract_review_marks(
                    command_id="save-after-malformed-current-contract-marks",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[second_mark],
                )

            self.assertEqual(kernel.load(), before)
            self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_saving_contract_marks_preserves_valid_prior_marks_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = seed_visual_review(kernel)
            service = VisualReviewService(kernel)
            first_mark = {
                "mark_id": "old-mark", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "旧意见",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            _mark_ref, _mark_set, state = service.save_contract_review_marks(
                command_id="save-old-contract-mark-for-merge",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[first_mark],
            )
            second_mark = {
                **first_mark,
                "mark_id": "new-mark",
                "comment": "新意见",
                "revision": state.revision,
            }

            _mark_ref, merged, _state = service.save_contract_review_marks(
                command_id="save-new-contract-mark-after-valid-old",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[second_mark],
            )

            self.assertEqual([item["mark_id"] for item in merged["marks"]], ["old-mark", "new-mark"])
            projection = service.project(session["review_session_id"])
            self.assertEqual(
                [item["mark_id"] for item in projection["contract_review_marks"]["marks"]],
                ["old-mark", "new-mark"],
            )

    def test_unversioned_current_text_mark_requires_official_save_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            hostile_mark = {
                "mark_id": "hostile-unversioned-current",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "",
                "context_after": "",
                "comment": "缺少历史来源的当前文字意见",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            hostile_mark_set = {
                "mark_set_id": "hostile-unversioned-current-set",
                "project_id": state.project_id,
                "review_session_id": session["review_session_id"],
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "marks": [hostile_mark],
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "saved_at": "2026-08-15T01:01:00+08:00",
            }
            kernel.commit(
                command_id="inject-unversioned-current-text-mark",
                expected_revision=state.revision,
                event_type="test.raw-contract-review-marks-injected",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        hostile_mark_set,
                    )
                },
            )
            service = VisualReviewService(kernel)
            before = kernel.load()
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )
            valid_mark = {
                **hostile_mark,
                "mark_id": "valid-current-browser-input",
                "context_before": "左事实、",
                "comment": "当前精确文字意见",
                "revision": before.revision,
                "anchor_representation_version": "browser-v2",
            }
            _mark_ref, merged, _committed = service.save_contract_review_marks(
                command_id="save-after-hostile-unversioned-current",
                expected_revision=before.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[valid_mark],
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["valid-current-browser-input"],
            )

    def test_browser_v1_text_anchor_is_read_only_for_new_saves(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            mark = {
                "mark_id": "client-supplied-browser-v1",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "客户端不得新写旧表示",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
                "anchor_representation_version": "browser-v1",
            }
            before_tree = {
                str(path.relative_to(project_root)): path.read_bytes()
                for path in sorted(project_root.rglob("*"))
                if path.is_file()
            }

            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).save_contract_review_marks(
                    command_id="reject-client-browser-v1",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark],
                )

            self.assertEqual(kernel.load(), state)
            self.assertEqual(
                {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                },
                before_tree,
            )

    def test_legacy_anchor_provenance_fails_closed_for_non_object_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            state = kernel.commit(
                command_id="seed-malformed-legacy-receipt",
                expected_revision=0,
                event_type="test.seed-malformed-legacy-receipt",
                artifact_updates={},
            )
            (kernel.events_root / "r00000001.json").write_text(
                "[]",
                encoding="utf-8",
            )

            self.assertFalse(
                VisualReviewService(kernel)._has_legacy_text_anchor_provenance(
                    mark={"revision": 0},
                    state=state,
                    review_session_id="review-session",
                    session_revision=0,
                )
            )

    def test_legacy_anchor_provenance_rejects_foreign_source_mark_set_identity(
        self,
    ) -> None:
        variants = {
            "project_id": "foreign-project",
            "review_session_id": "foreign-session",
            "visual_contract_ref": "artifact://visual-contract/" + "f" * 64,
            "source_version": "foreign-source",
            "revision": 0,
        }
        for field, foreign_value in variants.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
                (
                    _design_ref,
                    _anchor_ref,
                    contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
                legacy_mark = {
                    "mark_id": "legacy-source-identity",
                    "target_type": "text-range",
                    "slide_id": "S01",
                    "deck_section_id": "",
                    "target_key": "composition_intent",
                    "selected_text": "右因果链",
                    "context_before": "左事实、",
                    "context_after": "",
                    "comment": "升级前保存的文字意见",
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                mark_set = {
                    "mark_set_id": "legacy-source-identity-set",
                    "project_id": state.project_id,
                    "review_session_id": session["review_session_id"],
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "marks": [legacy_mark],
                    "persistence_status": "saved",
                    "host_notification_status": "not-requested",
                    "ai_receipt_status": "pending",
                    "saved_at": "2026-08-15T01:01:00+08:00",
                }
                committed = kernel.commit(
                    command_id="save-legacy-source-identity",
                    expected_revision=state.revision,
                    event_type="visual.contract-review-marks-saved",
                    artifact_updates={
                        "visual/contract-review-marks": (
                            "visual-contract-review-mark-set",
                            mark_set,
                        )
                    },
                    command_fingerprint=fingerprint(
                        "save-visual-contract-review-marks",
                        {
                            "review_session_id": mark_set["review_session_id"],
                            "source_version": mark_set["source_version"],
                            "marks": mark_set["marks"],
                        },
                    ),
                )
                foreign_set = {**copy.deepcopy(mark_set), field: foreign_value}
                foreign_ref = str(
                    kernel.artifacts.put(
                        "visual-contract-review-mark-set",
                        foreign_set,
                    )
                )
                event_path = (
                    kernel.events_root / f"r{committed.revision:08d}.json"
                )
                event = json.loads(event_path.read_text(encoding="utf-8"))
                event["artifact_heads"]["visual/contract-review-marks"] = (
                    foreign_ref
                )
                event["command_fingerprint"] = fingerprint(
                    "save-visual-contract-review-marks",
                    {
                        "review_session_id": foreign_set["review_session_id"],
                        "source_version": foreign_set["source_version"],
                        "marks": foreign_set["marks"],
                    },
                )
                event_path.write_text(
                    json.dumps(event, ensure_ascii=False),
                    encoding="utf-8",
                )
                before = kernel.load()
                before_tree = {
                    str(path.relative_to(project_root)): path.read_bytes()
                    for path in sorted(project_root.rglob("*"))
                    if path.is_file()
                }

                with self.assertRaises(ContractValidationError):
                    VisualReviewService(kernel).project(
                        session["review_session_id"]
                    )

                self.assertEqual(kernel.load(), before)
                self.assertEqual(
                    {
                        str(path.relative_to(project_root)): path.read_bytes()
                        for path in sorted(project_root.rglob("*"))
                        if path.is_file()
                    },
                    before_tree,
                )

    def test_formal_head_removal_boundary_resets_legacy_mark_history(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            legacy_mark = {
                "mark_id": "legacy-before-clear",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "旧视觉链意见",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            legacy_mark_set = {
                "mark_set_id": "legacy-before-clear-set",
                "project_id": state.project_id,
                "review_session_id": session["review_session_id"],
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "marks": [legacy_mark],
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "saved_at": "2026-08-15T01:01:00+08:00",
            }
            state = kernel.commit(
                command_id="legacy-before-formal-clear",
                expected_revision=state.revision,
                event_type="visual.contract-review-marks-saved",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        legacy_mark_set,
                    )
                },
                command_fingerprint=fingerprint(
                    "save-visual-contract-review-marks",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v1",
                        "marks": [legacy_mark],
                    },
                ),
            )
            state = VisualService(kernel).reopen_g3(
                "formal-g3-reopen-clears-legacy-head",
                state.revision,
                reason="正式重开视觉生产",
            )
            self.assertNotIn(
                "visual/contract-review-marks",
                state.artifact_heads,
            )
            clear_event_path = (
                kernel.events_root / f"r{state.revision:08d}.json"
            )
            previous_event_path = (
                kernel.events_root / f"r{state.revision - 1:08d}.json"
            )
            clear_event = json.loads(
                clear_event_path.read_text(encoding="utf-8")
            )
            previous_event = json.loads(
                previous_event_path.read_text(encoding="utf-8")
            )
            self.assertEqual(clear_event["event_type"], "gate.G3.reopened")
            self.assertIn(
                "visual/contract-review-marks",
                clear_event["artifact_head_removals"],
            )
            self.assertEqual(
                VisualReviewService(
                    kernel
                )._latest_contract_review_mark_set_before(
                    source_revision=state.revision + 1,
                    state=state,
                ),
                ("none", "", None),
            )
            for corruption in (
                "missing-removal-record",
                "wrong-removed-ref",
                "untrusted-previous-event",
                "ordinary-event-type",
                "missing-gate-mutation",
                "incomplete-visual-lineage-reset",
            ):
                with self.subTest(corruption=corruption):
                    corrupted_clear = copy.deepcopy(clear_event)
                    corrupted_previous = copy.deepcopy(previous_event)
                    if corruption == "missing-removal-record":
                        corrupted_clear["artifact_head_removals"].pop(
                            "visual/contract-review-marks"
                        )
                    elif corruption == "wrong-removed-ref":
                        corrupted_clear["artifact_head_removals"][
                            "visual/contract-review-marks"
                        ] = (
                            "artifact://visual-contract-review-mark-set/"
                            + "f" * 64
                        )
                    elif corruption == "untrusted-previous-event":
                        corrupted_previous["command_id"] = ""
                    elif corruption == "ordinary-event-type":
                        corrupted_clear["event_type"] = (
                            "test.ordinary-maintenance"
                        )
                    elif corruption == "missing-gate-mutation":
                        corrupted_clear["gate_updates"] = {}
                        corrupted_clear["gate_evidence_refs"] = []
                    else:
                        removed_contract_ref = corrupted_clear[
                            "artifact_head_removals"
                        ].pop("visual/contract")
                        corrupted_clear["artifact_heads"][
                            "visual/contract"
                        ] = removed_contract_ref
                    clear_event_path.write_text(
                        json.dumps(corrupted_clear, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    previous_event_path.write_text(
                        json.dumps(corrupted_previous, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    self.assertEqual(
                        VisualReviewService(
                            kernel
                        )._latest_contract_review_mark_set_before(
                            source_revision=state.revision + 1,
                            state=state,
                        ),
                        ("dropped-untrusted", "", None),
                    )
                    clear_event_path.write_text(
                        json.dumps(clear_event, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    previous_event_path.write_text(
                        json.dumps(previous_event, ensure_ascii=False),
                        encoding="utf-8",
                    )

    def test_projection_and_merge_preserve_legacy_text_anchor_representation(
        self,
    ) -> None:
        original_contract_set = valid_contract_set

        def legacy_contract_set(*args, **kwargs):
            value = original_contract_set(*args, **kwargs)
            value["slide_contracts"][0]["fallbacks"] = ["alpha", "beta"]
            return value

        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            with mock.patch(
                f"{__name__}.valid_contract_set",
                side_effect=legacy_contract_set,
            ):
                (
                    _design_ref,
                    _anchor_ref,
                    contract_ref,
                    _session_ref,
                    session,
                    state,
                ) = seed_visual_review(kernel)
            legacy_mark = {
                "mark_id": "legacy-text-mark",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "fallbacks",
                "selected_text": "eta",
                "context_before": "alphab",
                "context_after": "",
                "comment": "升级前保存的合法文字意见",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            legacy_mark_set = {
                "mark_set_id": "legacy-visual-contract-marks",
                "project_id": state.project_id,
                "review_session_id": session["review_session_id"],
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "marks": [legacy_mark],
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "saved_at": "2026-08-15T01:01:00+08:00",
            }
            legacy_committed = kernel.commit(
                command_id="seed-legacy-contract-review-marks",
                expected_revision=state.revision,
                event_type="visual.contract-review-marks-saved",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        legacy_mark_set,
                    )
                },
                command_fingerprint=fingerprint(
                    "save-visual-contract-review-marks",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v1",
                        "marks": [legacy_mark],
                    },
                ),
            )
            service = VisualReviewService(kernel)
            legacy_ref = legacy_committed.artifact_heads[
                "visual/contract-review-marks"
            ]
            replay_ref, replay_set, replay_state = (
                service.save_contract_review_marks(
                    command_id="seed-legacy-contract-review-marks",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[legacy_mark],
                )
            )
            self.assertEqual(replay_ref, legacy_ref)
            self.assertEqual(
                [item["mark_id"] for item in replay_set["marks"]],
                ["legacy-text-mark"],
            )
            self.assertEqual(
                replay_set["marks"][0][
                    "anchor_representation_version"
                ],
                "browser-v1",
            )
            self.assertEqual(
                replay_state.revision,
                legacy_committed.revision,
            )
            before_projection = kernel.load()

            projection = service.project(session["review_session_id"])

            self.assertEqual(kernel.load(), before_projection)
            self.assertEqual(
                [
                    item["mark_id"]
                    for item in projection["contract_review_marks"]["marks"]
                ],
                ["legacy-text-mark"],
            )
            self.assertEqual(
                projection["contract_review_marks"]["marks"][0][
                    "anchor_representation_version"
                ],
                "browser-v1",
            )
            new_mark = {
                **legacy_mark,
                "mark_id": "current-contract-mark",
                "target_type": "text-range",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "comment": "升级后新增的字段意见",
                "revision": before_projection.revision,
            }
            _mark_ref, merged, _committed = service.save_contract_review_marks(
                command_id="save-current-mark-after-legacy-text-mark",
                expected_revision=before_projection.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[new_mark],
            )
            self.assertEqual(
                [item["mark_id"] for item in merged["marks"]],
                ["legacy-text-mark", "current-contract-mark"],
            )
            self.assertEqual(
                merged["marks"][0]["anchor_representation_version"],
                "browser-v1",
            )
            self.assertEqual(
                merged["marks"][1]["anchor_representation_version"],
                "browser-v2",
            )
            merged_projection = service.project(session["review_session_id"])
            self.assertEqual(
                [
                    item["mark_id"]
                    for item in merged_projection["contract_review_marks"]["marks"]
                ],
                ["legacy-text-mark", "current-contract-mark"],
            )
            self.assertEqual(
                [
                    item.get("anchor_representation_version")
                    for item in merged_projection["contract_review_marks"]["marks"]
                ],
                ["browser-v1", "browser-v2"],
            )

    def test_legacy_provenance_accepts_formal_save_with_input_merge_order_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            (
                _design_ref,
                _anchor_ref,
                contract_ref,
                _session_ref,
                session,
                state,
            ) = seed_visual_review(kernel)
            legacy_a = {
                "mark_id": "legacy-A",
                "target_type": "text-range",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "右因果链",
                "context_before": "左事实、",
                "context_after": "",
                "comment": "旧意见 A",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            first_set = {
                "mark_set_id": "legacy-order-first",
                "project_id": state.project_id,
                "review_session_id": session["review_session_id"],
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "marks": [legacy_a],
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "saved_at": "2026-08-15T01:01:00+08:00",
            }
            first_state = kernel.commit(
                command_id="legacy-order-first-save",
                expected_revision=state.revision,
                event_type="visual.contract-review-marks-saved",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        first_set,
                    )
                },
                command_fingerprint=fingerprint(
                    "save-visual-contract-review-marks",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v1",
                        "marks": [legacy_a],
                    },
                ),
            )
            updated_a = {
                **legacy_a,
                "comment": "更新后的旧意见 A",
                "revision": first_state.revision,
            }
            new_b = {
                **updated_a,
                "mark_id": "legacy-B",
                "target_type": "contract-field",
                "selected_text": "",
                "context_before": "",
                "comment": "新增意见 B",
            }
            merged_set = {
                **first_set,
                "mark_set_id": "legacy-order-merged",
                "revision": first_state.revision,
                "marks": [updated_a, new_b],
                "saved_at": "2026-08-15T01:02:00+08:00",
            }
            second_state = kernel.commit(
                command_id="legacy-order-mixed-save",
                expected_revision=first_state.revision,
                event_type="visual.contract-review-marks-saved",
                artifact_updates={
                    "visual/contract-review-marks": (
                        "visual-contract-review-mark-set",
                        merged_set,
                    )
                },
                command_fingerprint=fingerprint(
                    "save-visual-contract-review-marks",
                    {
                        "review_session_id": session["review_session_id"],
                        "source_version": "visual-v1",
                        "marks": [new_b, updated_a],
                    },
                ),
            )

            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                [
                    item["mark_id"]
                    for item in projection["contract_review_marks"]["marks"]
                ],
                ["legacy-A", "legacy-B"],
            )
            self.assertEqual(
                projection["contract_review_marks"]["marks"][0][
                    "anchor_representation_version"
                ],
                "browser-v1",
            )
            previous_event_path = (
                kernel.events_root / f"r{first_state.revision:08d}.json"
            )
            previous_event_bytes = previous_event_path.read_bytes()
            corruptions = {
                "revision-mismatch": {"revision": -999},
                "missing-command-identity": {"command_id": ""},
                "processed-command-revision-mismatch": {
                    "command_id": "legacy-order-mixed-save"
                },
            }
            for name, updates in corruptions.items():
                with self.subTest(previous_event=name):
                    previous_event = json.loads(
                        previous_event_bytes.decode("utf-8")
                    )
                    previous_event.update(updates)
                    previous_event_path.write_text(
                        json.dumps(previous_event, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    before_corrupt_projection = kernel.load()
                    before_corrupt_tree = {
                        str(path.relative_to(Path(folder))): path.read_bytes()
                        for path in sorted(Path(folder).rglob("*"))
                        if path.is_file()
                    }

                    with self.assertRaises(ContractValidationError):
                        VisualReviewService(kernel).project(
                            session["review_session_id"]
                        )

                    self.assertEqual(kernel.load(), before_corrupt_projection)
                    self.assertEqual(
                        {
                            str(path.relative_to(Path(folder))): path.read_bytes()
                            for path in sorted(Path(folder).rglob("*"))
                            if path.is_file()
                        },
                        before_corrupt_tree,
                    )
                    previous_event_path.write_bytes(previous_event_bytes)
            previous_set_corruptions = {
                "foreign-session": {
                    **copy.deepcopy(first_set),
                    "review_session_id": "foreign-review-session",
                },
                "mark-newer-than-set": {
                    **copy.deepcopy(first_set),
                    "marks": [
                        {
                            **legacy_a,
                            "revision": first_set["revision"] + 1,
                        }
                    ],
                },
            }
            for name, previous_set in previous_set_corruptions.items():
                with self.subTest(previous_mark_set=name):
                    previous_ref = str(
                        kernel.artifacts.put(
                            "visual-contract-review-mark-set",
                            previous_set,
                        )
                    )
                    previous_event = json.loads(
                        previous_event_bytes.decode("utf-8")
                    )
                    previous_event["artifact_heads"][
                        "visual/contract-review-marks"
                    ] = previous_ref
                    previous_event_path.write_text(
                        json.dumps(previous_event, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    before_corrupt_projection = kernel.load()
                    before_corrupt_tree = {
                        str(path.relative_to(Path(folder))): path.read_bytes()
                        for path in sorted(Path(folder).rglob("*"))
                        if path.is_file()
                    }

                    with self.assertRaises(ContractValidationError):
                        VisualReviewService(kernel).project(
                            session["review_session_id"]
                        )

                    self.assertEqual(kernel.load(), before_corrupt_projection)
                    self.assertEqual(
                        {
                            str(path.relative_to(Path(folder))): path.read_bytes()
                            for path in sorted(Path(folder).rglob("*"))
                            if path.is_file()
                        },
                        before_corrupt_tree,
                    )
                    previous_event_path.write_bytes(previous_event_bytes)
            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(
                [
                    item["mark_id"]
                    for item in projection["contract_review_marks"]["marks"]
                ],
                ["legacy-A", "legacy-B"],
            )
            event_path = (
                kernel.events_root / f"r{second_state.revision:08d}.json"
            )
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["command_fingerprint"] = "0" * 64
            event_path.write_text(
                json.dumps(event, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(ContractValidationError):
                VisualReviewService(kernel).project(
                    session["review_session_id"]
                )

    def test_contract_text_matches_ecmascript_integer_property_order(self) -> None:
        value = {
            "10": "ten",
            "2": "two",
            "00": "double-zero",
            "4294967295": "not-an-array-index",
            "0": "zero",
            "4294967294": "last-array-index",
            "-0": "minus-zero",
        }

        self.assertEqual(
            VisualReviewService._contract_text(value),
            (
                "zero two ten last-array-index "
                "double-zero not-an-array-index minus-zero"
            ),
        )

    def test_contract_text_treats_oversized_numeric_property_as_ordinary(
        self,
    ) -> None:
        value = {
            "1" * 5000: "business-value",
            "2": "two-value",
            "body": "body-value",
        }

        self.assertEqual(
            VisualReviewService._contract_text(value),
            "two-value business-value body-value",
        )

    def test_contract_anchor_text_uses_the_explicit_ecmascript_whitespace_set(
        self,
    ) -> None:
        whitespace = (
            "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680"
            "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008"
            "\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
        )

        self.assertEqual(
            VisualReviewService._normalized_contract_text(
                f"{whitespace}alpha{whitespace}beta{whitespace}"
            ),
            "alpha beta",
        )
        self.assertEqual(
            VisualReviewService._normalized_contract_text("alpha\u001cbeta"),
            "alpha\u001cbeta",
        )

    def test_projection_trims_ecmascript_edge_whitespace_across_contract_layers(
        self,
    ) -> None:
        original_brief = valid_visual_brief
        original_design = valid_design_system
        original_contract_set = valid_contract_set

        def whitespace_brief(*args, **kwargs):
            value = original_brief(*args, **kwargs)
            value["decision_task"] = "\ufeffalpha\ufeff"
            return value

        def whitespace_design(*args, **kwargs):
            value = original_design(*args, **kwargs)
            value["theme_proposition"] = "\ufefftheme\ufeff"
            return value

        def whitespace_contract_set(*args, **kwargs):
            value = original_contract_set(*args, **kwargs)
            value["slide_contracts"][0]["communication_goal"] = (
                "\ufeffgoal\ufeff"
            )
            return value

        with tempfile.TemporaryDirectory() as folder, mock.patch(
            f"{__name__}.valid_visual_brief",
            side_effect=whitespace_brief,
        ), mock.patch(
            f"{__name__}.valid_design_system",
            side_effect=whitespace_design,
        ), mock.patch(
            f"{__name__}.valid_contract_set",
            side_effect=whitespace_contract_set,
        ):
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, _contract_ref, _session_ref, session, _state = (
                seed_visual_review(kernel)
            )

            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

        self.assertEqual(projection["visual_brief"]["decision_task"], "alpha")
        self.assertEqual(
            projection["deck_design_system"]["theme_proposition"],
            "theme",
        )
        self.assertEqual(
            projection["slide_visual_contracts"][0]["communication_goal"],
            "goal",
        )

    def test_contract_mark_replay_returns_its_original_result_after_a_later_save(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            service = VisualReviewService(kernel)
            first_mark = {
                "mark_id": "first-mark", "target_type": "contract-field", "slide_id": "S01",
                "deck_section_id": "", "target_key": "composition_intent", "selected_text": "",
                "context_before": "", "context_after": "", "comment": "第一条意见",
                "visual_contract_ref": contract_ref, "source_version": "visual-v1",
                "revision": state.revision, "created_at": "2026-08-15T01:00:00+08:00", "created_by": "user",
            }
            first_ref, first_set, state = service.save_contract_review_marks(
                command_id="save-first-contract-mark",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[first_mark],
            )
            second_mark = {
                **first_mark,
                "mark_id": "second-mark",
                "comment": "第二条意见",
                "revision": state.revision,
            }
            service.save_contract_review_marks(
                command_id="save-second-contract-mark",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[second_mark],
            )

            replay_ref, replay_set, replay_state = service.save_contract_review_marks(
                command_id="save-first-contract-mark",
                expected_revision=first_mark["revision"],
                review_session_id=session["review_session_id"],
                source_version="visual-v1",
                marks=[first_mark],
            )

            self.assertEqual((replay_ref, replay_set), (first_ref, first_set))
            self.assertGreater(replay_state.revision, first_set["revision"])

    def test_visual_brief_rows_are_markable_without_exposing_the_heading_as_a_field(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            mark = {
                "mark_id": "brief-mark-1",
                "target_type": "contract-field",
                "slide_id": "",
                "deck_section_id": "visual-brief",
                "target_key": "decision_task",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "决策任务需要更聚焦",
                "visual_contract_ref": contract_ref,
                "source_version": "visual-v1",
                "revision": state.revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }

            try:
                _marks_ref, mark_set, committed = VisualReviewService(
                    kernel
                ).save_contract_review_marks(
                    command_id="save-visual-brief-mark",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="visual-v1",
                    marks=[mark],
                )
            except ContractValidationError as error:
                self.fail(f"Visual Brief row mark should be accepted: {error}")

            self.assertEqual(mark_set["marks"], [mark])
            self.assertEqual(committed.revision, state.revision + 1)

        for target_key in (
            "design_proposition",
            "visual-compilation-plan",
            "compiler_version",
            "lineage",
            "future_backend_governance",
        ):
            with self.subTest(target_key=target_key), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _design_ref, _anchor_ref, contract_ref, _session_ref, session, state = (
                    seed_visual_review(kernel)
                )
                invalid_mark = {
                    "mark_id": f"invalid-brief-{target_key}",
                    "target_type": "contract-field",
                    "slide_id": "",
                    "deck_section_id": "visual-brief",
                    "target_key": target_key,
                    "selected_text": "",
                    "context_before": "",
                    "context_after": "",
                    "comment": "不得保存",
                    "visual_contract_ref": contract_ref,
                    "source_version": "visual-v1",
                    "revision": state.revision,
                    "created_at": "2026-08-15T01:00:00+08:00",
                    "created_by": "user",
                }
                before = kernel.load()

                with self.assertRaises(ContractValidationError):
                    VisualReviewService(kernel).save_contract_review_marks(
                        command_id=f"reject-{target_key}",
                        expected_revision=state.revision,
                        review_session_id=session["review_session_id"],
                        source_version="visual-v1",
                        marks=[invalid_mark],
                    )

                self.assertEqual(kernel.load(), before)

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
            "unanchored-text-occurrence": {
                "target_type": "text-range",
                "selected_text": "右因果链",
                "context_before": "",
                "context_after": "",
            },
            "truncated-context-before": {
                "target_type": "text-range",
                "selected_text": "右因果链",
                "context_before": "事实、",
                "context_after": "",
            },
            "truncated-context-after": {
                "target_type": "text-range",
                "selected_text": "左事实、",
                "context_before": "",
                "context_after": "右",
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
