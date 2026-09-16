from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContractValidationError, ReviewSourceStaleError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_visual_review_service import seed_visual_review
from tests.v16_visual_fixtures import (
    confirmed_g0,
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


TOP_LEVEL_FIELDS = {
    "project_id", "project_name", "review_type", "review_session_id",
    "review_session", "source_version", "revision", "authoritative_revision",
    "visual_contract_ref", "visual_brief_ref", "visual_brief",
    "deck_design_system_ref", "deck_design_system", "anchor_slide_set_ref",
    "anchors", "anchor_identity", "slide_visual_contracts",
    "anchor_feedback_batch", "anchor_feedback_batch_ref",
    "contract_review_marks", "contract_review_marks_ref",
    "host_submission_capability", "ai_receipt_capability",
}
VISUAL_BRIEF_FIELDS = {
    "design_proposition", "audience_fit", "decision_task", "design_stance",
    "emotional_boundary", "brand_boundary", "density_strategy",
    "narrative_rhythm", "imagery_strategy", "diagram_strategy",
    "powerpoint_constraints", "forbidden_patterns", "five_second_test_contract",
    "design_philosophy_refs",
}
DECK_DESIGN_SYSTEM_FIELDS = {
    "theme_proposition", "composition_grammar", "color_tokens",
    "typography_tokens", "page_families", "density_rhythm",
    "cross_slide_rhythm_rules", "emphasis_budget", "imagery_strategy",
    "image_language", "diagram_strategy", "diagram_language", "table_strategy",
    "editability_rules", "accessibility_rules", "forbidden_patterns",
    "five_second_test_rules", "anchor_specification", "production_route",
    "fallback_fonts",
}
SLIDE_VISUAL_CONTRACT_FIELDS = {
    "slide_id", "order", "neutral_title", "page_family", "anchor_title",
    "validation_purpose", "core_claim", "visible_copy", "speaker_notes",
    "source_refs", "communication_goal", "composition_intent",
    "information_hierarchy", "reading_order", "regions",
    "object_relationships", "diagram_chart_table_treatment",
    "image_selection_and_crop", "color_application", "typography_application",
    "native_bitmap_routing", "editability_requirements", "fallbacks",
    "acceptance_criteria", "reader_judgment", "primary_relationship",
    "secondary_relationship", "visual_mechanism", "focal_point", "asset_roles",
    "forbidden_patterns", "previous_rhythm_relation", "next_rhythm_relation",
    "text_density_budget", "powerpoint_implementation_requirements",
    "acceptance_evidence_plan",
}
FORBIDDEN_PROJECTION_FIELDS = {
    "visual_compilation_plan_ref", "visual_compilation_plan", "compiler",
    "compiler_version", "handoff_protocol_version", "role_runs",
    "release_target_policy_ref", "target_evidence_refs",
    "target_evidence_identities", "internal_review_refs", "gate_status",
    "gate_state", "artifact_heads", "processed_commands", "last_transaction_id",
    "lineage", "future_backend_governance", "material_inventory",
    "material_details", "audit_log", "internal_process_state",
    "tool_execution", "tool_calls",
}


def project_tree_bytes(project_root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(project_root)): path.read_bytes()
        for path in sorted(project_root.rglob("*"))
        if path.is_file()
    }


class VisualReviewProjectionTests(unittest.TestCase):
    def assert_no_internal_visual_fields(self, value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                self.assertNotIn(key, FORBIDDEN_PROJECTION_FIELDS, f"{path}.{key}")
                self.assertFalse(
                    key.startswith("visual_compilation_plan"), f"{path}.{key}"
                )
                self.assert_no_internal_visual_fields(nested, f"{path}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                self.assert_no_internal_visual_fields(nested, f"{path}[{index}]")

    def test_contract_registration_atomically_publishes_contract_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            content, _revision, blueprint_ref = confirmed_g0(
                project_root, slide_count=3
            )
            kernel = content.kernel
            visual = VisualService(kernel)
            brief_ref = visual.register_visual_brief(
                "projection-atomic-brief", kernel.load().revision,
                valid_visual_brief(blueprint_ref),
            )
            design_ref = visual.register_design_system(
                "projection-atomic-design", kernel.load().revision,
                valid_design_system(brief_ref, blueprint_ref),
            )
            blueprint = kernel.artifacts.resolve(
                ArtifactReference.parse(blueprint_ref)
            )["payload"]
            before = kernel.load()
            contract_ref = visual.register_visual_contract_set(
                "projection-atomic-contracts", before.revision,
                valid_contract_set(design_ref, blueprint_ref, blueprint["slides"]),
            )

            committed = kernel.load()
            plan_ref = committed.artifact_heads["visual/compilation-plan"]
            plan = kernel.artifacts.resolve(ArtifactReference.parse(plan_ref))["payload"]
            event = json.loads(
                (kernel.events_root / f"r{committed.revision:08d}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(committed.revision, before.revision + 1)
            self.assertEqual(event["revision"], committed.revision)
            self.assertEqual(event["artifact_heads"]["visual/contracts"], contract_ref)
            self.assertEqual(event["artifact_heads"]["visual/compilation-plan"], plan_ref)
            self.assertEqual(plan["visual_contract_set_ref"], contract_ref)
            self.assertEqual(plan["source_revision"], committed.revision)

    def test_visual_service_rejects_internal_governance_keys_in_visible_token_maps(
        self,
    ) -> None:
        for field in ("color_tokens", "typography_tokens", "fallback_fonts"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                content, _revision, blueprint_ref = confirmed_g0(
                    project_root, slide_count=3
                )
                kernel = content.kernel
                visual = VisualService(kernel)
                brief_ref = visual.register_visual_brief(
                    f"projection-token-map-brief-{field}",
                    kernel.load().revision,
                    valid_visual_brief(blueprint_ref),
                )
                design = valid_design_system(brief_ref, blueprint_ref)
                design[field]["future_backend_governance"] = "must-not-project"

                before = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = project_tree_bytes(project_root)
                with self.assertRaises(ContractValidationError):
                    visual.register_design_system(
                        f"projection-token-map-design-{field}",
                        kernel.load().revision,
                        design,
                    )
                self.assertEqual(kernel.load(), before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(project_tree_bytes(project_root), before_tree)

    def test_projection_is_a_closed_v23_user_review_document(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            design_ref, anchor_ref, contract_ref, _session_ref, session, state = (
                seed_visual_review(kernel)
            )
            projection = VisualReviewService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(set(projection), TOP_LEVEL_FIELDS)
            self.assertEqual(projection["visual_contract_ref"], contract_ref)
            self.assertEqual(projection["visual_brief_ref"], state.artifact_heads["visual/brief"])
            self.assertEqual(projection["deck_design_system_ref"], design_ref)
            self.assertEqual(projection["anchor_slide_set_ref"], anchor_ref)
            self.assertEqual(set(projection["visual_brief"]), VISUAL_BRIEF_FIELDS)
            self.assertEqual(set(projection["deck_design_system"]), DECK_DESIGN_SYSTEM_FIELDS)
            self.assertTrue(projection["slide_visual_contracts"])
            for slide in projection["slide_visual_contracts"]:
                self.assertEqual(set(slide), SLIDE_VISUAL_CONTRACT_FIELDS)
            self.assertEqual(projection["visual_brief"]["design_philosophy_refs"], [])
            self.assertEqual(projection["revision"], session["revision"])
            self.assertEqual(projection["authoritative_revision"], state.revision)
            self.assertEqual(
                projection["review_session"]["review_status"],
                {"gate": "G3", "status": "user-reviewable"},
            )
            self.assert_no_internal_visual_fields(projection)

    def test_projection_rejects_mismatched_session_identity_source_and_revision_without_writes(
        self,
    ) -> None:
        for fault in ("session-id", "source-version", "revision"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                project_root = Path(folder)
                kernel = ProjectKernel.initialize(project_root, project_id="p1")
                _design, _anchor, _contract, _session_ref, session, state = (
                    seed_visual_review(kernel)
                )
                requested_session_id = session["review_session_id"]
                if fault == "session-id":
                    requested_session_id = "foreign-visual-review-session"
                else:
                    session_ref = state.review_session_ref("visual-professional")
                    forged = copy.deepcopy(
                        kernel.artifacts.resolve(ArtifactReference.parse(session_ref))["payload"]
                    )
                    if fault == "source-version":
                        forged["source_version"] = "visual-stale"
                    else:
                        forged["revision"] = max(0, int(forged["revision"]) - 1)
                    kernel.commit(
                        command_id=f"forge-projection-session-{fault}",
                        expected_revision=state.revision,
                        event_type="test.raw-review-session-forged",
                        artifact_updates={
                            "review/session/visual-professional": (
                                "review-session", forged,
                            )
                        },
                    )

                before = kernel.load()
                before_state_bytes = kernel.state_path.read_bytes()
                before_tree = project_tree_bytes(project_root)
                with self.assertRaises(ReviewSourceStaleError):
                    VisualReviewService(kernel).project(requested_session_id)
                self.assertEqual(kernel.load(), before)
                self.assertEqual(kernel.state_path.read_bytes(), before_state_bytes)
                self.assertEqual(project_tree_bytes(project_root), before_tree)


if __name__ == "__main__":
    unittest.main()
