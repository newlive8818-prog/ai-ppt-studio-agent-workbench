from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_evidence_browser_service import (
    ContentEvidenceBrowserService,
)
from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError, ReviewSourceStaleError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import (
    REF,
    blueprint,
    decision_context,
    evidence_book,
    fit_map,
)


def replace_ref(value, old: str, new: str):
    if isinstance(value, list):
        return [replace_ref(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_ref(item, old, new) for key, item in value.items()}
    return new if value == old else value


def evidence_review(kernel: ProjectKernel, source_url: str = "https://example.com/evidence"):
    evidence_ref = str(
        kernel.artifacts.put(
            "material-finding",
            {
                "source_url": source_url,
                "title": "用户提供材料的只读来源",
                "read_only": True,
            },
        )
    )
    state = kernel.commit(
        command_id="seed",
        expected_revision=0,
        event_type="test.seeded",
        artifact_updates={
            "mission/confirmation": (
                "mission-confirmation",
                {"material_mode": "materials-provided"},
            ),
            "materials": (
                "material-inventory",
                {"sources": [{"source_id": "source-1"}]},
            ),
        },
    )
    service = PresalesContentService(kernel)
    evidence = replace_ref(evidence_book(), REF, evidence_ref)
    evidence["mission_confirmation_ref"] = state.artifact_heads[
        "mission/confirmation"
    ]
    evidence["material_inventory_ref"] = state.artifact_heads["materials"]
    book_ref = service.build_evidence_book("book", state.revision, evidence)
    context = decision_context()
    context["evidence_book_ref"] = book_ref
    context_ref = service.build_decision_context(
        "context", kernel.load().revision, context
    )
    mapping = replace_ref(fit_map(), REF, evidence_ref)
    mapping["evidence_book_ref"] = book_ref
    mapping["decision_context_ref"] = context_ref
    mapping_ref = service.build_problem_solution_fit(
        "mapping", kernel.load().revision, mapping
    )
    deck = replace_ref(blueprint(), REF, evidence_ref)
    deck.update(
        project_id=kernel.project_id,
        evidence_book_ref=book_ref,
        decision_context_ref=context_ref,
        problem_solution_fit_ref=mapping_ref,
    )
    deck_ref = service.build_reading_deck_blueprint(
        "deck", kernel.load().revision, deck
    )
    gates = ContentHardGateService(kernel)
    gates.run_evidence_gate(
        command_id="evidence-gate",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    gates.run_presales_reading_gate(
        command_id="reading-gate",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    state = kernel.load()
    _session_ref, session, _state = ReviewSessionService(kernel).open_or_resume(
        command_id="open-review",
        expected_revision=state.revision,
        review_type="content-full-deck",
        target_artifact_ref=deck_ref,
        source_version="content-v1",
        source_revision=state.revision,
        open_policy="foreground-if-waiting",
    )
    return evidence_ref, session


class ContentEvidenceBrowserTests(unittest.TestCase):
    def test_returns_only_a_current_session_bound_https_read_only_url(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            evidence_ref, session = evidence_review(kernel)
            before = kernel.load()
            result = ContentEvidenceBrowserService(kernel).open(
                review_session_id=session["review_session_id"],
                evidence_ref=evidence_ref,
            )
            self.assertEqual(result["url"], "https://example.com/evidence")
            self.assertTrue(result["read_only"])
            self.assertFalse(result["proof_eligible"])
            self.assertFalse(result["real_browser_evidence"])
            self.assertEqual(kernel.load(), before)

    def test_unbound_ref_or_wrong_session_fails_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            evidence_ref, session = evidence_review(kernel)
            unrelated = str(
                kernel.artifacts.put(
                    "material-finding",
                    {"source_url": "https://example.com/unrelated"},
                )
            )
            before = kernel.load()
            for session_id, ref, error in (
                ("wrong-session", evidence_ref, ReviewSourceStaleError),
                (session["review_session_id"], unrelated, ContractValidationError),
            ):
                with self.subTest(session=session_id, ref=ref), self.assertRaises(error):
                    ContentEvidenceBrowserService(kernel).open(
                        review_session_id=session_id,
                        evidence_ref=ref,
                    )
            self.assertEqual(kernel.load(), before)

    def test_non_https_or_unresolvable_source_reports_a_stable_capability_gap(self) -> None:
        for source_url in ("file:///tmp/material.txt", "http://example.com/evidence", ""):
            with self.subTest(source_url=source_url), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                evidence_ref, session = evidence_review(kernel, source_url)
                before = kernel.load()
                with self.assertRaisesRegex(
                    ContractValidationError,
                    "CONTENT_EVIDENCE_BROWSER_UNAVAILABLE",
                ):
                    ContentEvidenceBrowserService(kernel).open(
                        review_session_id=session["review_session_id"],
                        evidence_ref=evidence_ref,
                    )
                self.assertEqual(kernel.load(), before)

    def test_bridge_exposes_the_read_only_result_without_writing_a_second_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            kernel = ProjectKernel.initialize(project, project_id="p1")
            evidence_ref, session = evidence_review(kernel)
            before = kernel.load()
            result = dispatch_v16(
                {
                    "operation": "open-content-evidence-browser",
                    "project_root": str(project),
                    "review_session_id": session["review_session_id"],
                    "evidence_ref": evidence_ref,
                }
            )
            self.assertEqual(result["url"], "https://example.com/evidence")
            self.assertNotIn("decision", result)
            self.assertEqual(kernel.load(), before)


if __name__ == "__main__":
    unittest.main()
