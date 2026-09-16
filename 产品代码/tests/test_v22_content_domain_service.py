from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import (
    REF,
    blueprint,
    decision_context,
    evidence_book,
    fit_map,
)

from tests.material_finding_fixtures import source_inventory, bind_findings

EXCLUDED_REF = "artifact://material-finding/" + "b" * 64


def authority_snapshot(kernel: ProjectKernel) -> tuple[object, ...]:
    state = kernel.load()
    return (
        state.revision,
        dict(state.artifact_heads),
        tuple(sorted(path.name for path in kernel.events_root.glob("*.json"))),
        tuple(
            sorted(
                str(path.relative_to(kernel.artifacts.objects_root))
                for path in kernel.artifacts.objects_root.glob("*/*.json")
            )
        ),
    )


class ContentChainFixture:
    def __init__(self, folder: str, *, mode: str = "material-backed") -> None:
        self.kernel = ProjectKernel.initialize(Path(folder), project_id=f"c0-{mode}")
        updates = {
            "mission/confirmation": ("mission-confirmation", {"material_mode": mode})
        }
        if mode != "proposal-led":
            updates["materials"] = (
                "material-inventory",
                source_inventory(self.kernel),
            )
        state = self.kernel.commit(
            command_id="seed",
            expected_revision=0,
            event_type="test.seeded",
            artifact_updates=updates,
        )
        self.service = PresalesContentService(self.kernel)
        evidence = evidence_book(mode)
        evidence["mission_confirmation_ref"] = state.artifact_heads[
            "mission/confirmation"
        ]
        evidence["material_inventory_ref"] = state.artifact_heads.get("materials", "")
        evidence["excluded_material_refs"] = (
            [] if mode == "proposal-led" else [EXCLUDED_REF]
        )
        evidence = bind_findings(self.kernel, evidence)
        self.evidence_payload = evidence
        self.evidence_ref = self.service.build_evidence_book(
            "evidence", self.kernel.load().revision, evidence
        )
        context = decision_context()
        context["evidence_book_ref"] = self.evidence_ref
        self.context_payload = context
        self.context_ref = self.service.build_decision_context(
            "context", self.kernel.load().revision, context
        )

    def valid_fit(self) -> dict:
        value = bind_findings(self.kernel, fit_map(self.evidence_payload["material_mode"]))
        value["evidence_book_ref"] = self.evidence_ref
        value["decision_context_ref"] = self.context_ref
        return value

    def build_fit(self, command_id: str = "fit") -> tuple[dict, str]:
        value = self.valid_fit()
        reference = self.service.build_problem_solution_fit(
            command_id, self.kernel.load().revision, value
        )
        return value, reference

    def valid_blueprint(self, fit_ref: str) -> dict:
        value = bind_findings(self.kernel, blueprint(self.evidence_payload["material_mode"]))
        value["project_id"] = self.kernel.project_id
        value["evidence_book_ref"] = self.evidence_ref
        value["decision_context_ref"] = self.context_ref
        value["problem_solution_fit_ref"] = fit_ref
        return value


class V22ContentDomainServiceTests(unittest.TestCase):
    def assert_zero_write_rejection(
        self,
        fixture: ContentChainFixture,
        operation,
    ) -> None:
        before = authority_snapshot(fixture.kernel)
        with self.assertRaises(ContractValidationError):
            operation()
        self.assertEqual(authority_snapshot(fixture.kernel), before)

    def test_fit_refs_must_be_declared_and_not_excluded(self) -> None:
        for label, invalid_ref in (
            ("undeclared", "artifact://material-finding/" + "c" * 64),
            ("excluded", EXCLUDED_REF),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                value = fixture.valid_fit()
                value["symptoms"][0]["evidence_refs"] = [invalid_ref]
                self.assert_zero_write_rejection(
                    fixture,
                    lambda: fixture.service.build_problem_solution_fit(
                        "invalid-fit", fixture.kernel.load().revision, value
                    ),
                )

    def test_proposal_led_fit_cannot_claim_facts_or_project_evidence(self) -> None:
        for label in ("factual-identity", "project-evidence"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder, mode="proposal-led")
                value = fixture.valid_fit()
                if label == "factual-identity":
                    value["symptoms"][0]["identity"] = "来源事实"
                else:
                    value["symptoms"][0]["evidence_refs"] = [REF]
                self.assert_zero_write_rejection(
                    fixture,
                    lambda: fixture.service.build_problem_solution_fit(
                        "invalid-proposal-fit", fixture.kernel.load().revision, value
                    ),
                )

    def test_material_mode_mapping_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            fixture = ContentChainFixture(folder)
            value = fixture.valid_fit()
            value["mappings"][0]["evidence_refs"] = []
            self.assert_zero_write_rejection(
                fixture,
                lambda: fixture.service.build_problem_solution_fit(
                    "empty-mapping-evidence", fixture.kernel.load().revision, value
                ),
            )

    def test_blueprint_binds_current_source_evidence_and_mapping(self) -> None:
        cases = (
            "stale-source-version",
            "undeclared-binding",
            "excluded-binding",
            "undeclared-material-view",
            "excluded-material-view",
            "unknown-mapping",
        )
        for label in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                _fit_payload, fit_ref = fixture.build_fit()
                value = fixture.valid_blueprint(fit_ref)
                if label == "stale-source-version":
                    value["source_version"] = "content-v0"
                elif label == "undeclared-binding":
                    value["slides"][0]["evidence_bindings"][0]["source_refs"] = [
                        "artifact://material-finding/" + "c" * 64
                    ]
                elif label == "excluded-binding":
                    value["slides"][0]["evidence_bindings"][0]["source_refs"] = [
                        EXCLUDED_REF
                    ]
                elif label == "undeclared-material-view":
                    value["slides"][0]["material_views"][0]["source_ref"] = (
                        "artifact://material-finding/" + "c" * 64
                    )
                elif label == "excluded-material-view":
                    value["slides"][0]["material_views"][0]["source_ref"] = EXCLUDED_REF
                else:
                    value["slides"][0]["solution_mapping_refs"] = ["missing"]
                self.assert_zero_write_rejection(
                    fixture,
                    lambda: fixture.service.build_reading_deck_blueprint(
                        "invalid-blueprint", fixture.kernel.load().revision, value
                    ),
                )

    def test_customer_decision_evidence_is_declared_and_not_excluded(self) -> None:
        for label, invalid_ref in (
            ("undeclared", "artifact://material-finding/" + "c" * 64),
            ("excluded", EXCLUDED_REF),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                _fit_payload, fit_ref = fixture.build_fit()
                value = fixture.valid_blueprint(fit_ref)
                value["slides"][0]["customer_decision_item"] = {
                    "text": "客户材料记录了当前流程断点。",
                    "identity": "来源事实",
                    "evidence_refs": [invalid_ref],
                }
                self.assert_zero_write_rejection(
                    fixture,
                    lambda: fixture.service.build_reading_deck_blueprint(
                        "invalid-customer-decision-evidence",
                        fixture.kernel.load().revision,
                        value,
                    ),
                )

    def test_upstream_replacement_invalidates_only_dependent_current_heads(self) -> None:
        cases = {
            "evidence": (
                "content/evidence-book",
                (
                    "content/decision-context",
                    "content/problem-solution-fit",
                    "content/reading-blueprint",
                ),
            ),
            "context": (
                "content/decision-context",
                ("content/problem-solution-fit", "content/reading-blueprint"),
            ),
            "fit": (
                "content/problem-solution-fit",
                ("content/reading-blueprint",),
            ),
        }
        for operation, (replaced_slot, invalidated_slots) in cases.items():
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                fit_v1, fit_ref_v1 = fixture.build_fit()
                deck_v1 = fixture.valid_blueprint(fit_ref_v1)
                fixture.service.build_reading_deck_blueprint(
                    "deck-v1", fixture.kernel.load().revision, deck_v1
                )
                before_heads = dict(fixture.kernel.load().artifact_heads)
                historical_refs = {
                    slot: before_heads[slot] for slot in invalidated_slots
                }

                if operation == "evidence":
                    value = copy.deepcopy(fixture.evidence_payload)
                    value["generated_at"] = "2026-08-16T00:00:00+08:00"
                    new_ref = fixture.service.build_evidence_book(
                        "evidence-v2", fixture.kernel.load().revision, value
                    )
                elif operation == "context":
                    value = copy.deepcopy(fixture.context_payload)
                    value["current_business_matter"] = "确认第二版业务事项"
                    new_ref = fixture.service.build_decision_context(
                        "context-v2", fixture.kernel.load().revision, value
                    )
                else:
                    value = copy.deepcopy(fit_v1)
                    value["symptoms"][0]["statement"] = "第二版问题陈述"
                    new_ref = fixture.service.build_problem_solution_fit(
                        "fit-v2", fixture.kernel.load().revision, value
                    )

                current = fixture.kernel.load().artifact_heads
                self.assertEqual(current[replaced_slot], new_ref)
                for slot in invalidated_slots:
                    self.assertNotIn(slot, current)
                    old_ref = historical_refs[slot]
                    self.assertEqual(
                        fixture.kernel.artifacts.resolve(
                            ArtifactReference.parse(old_ref)
                        )["kind"],
                        ArtifactReference.parse(old_ref).kind,
                    )
                projection = fixture.service.get_current_content_chain()["objects"]
                output_keys = {
                    "content/decision-context": "decision_context",
                    "content/problem-solution-fit": "problem_solution_fit",
                    "content/reading-blueprint": "reading_blueprint",
                }
                for slot in invalidated_slots:
                    self.assertIsNone(projection[output_keys[slot]])

    def test_mixed_current_lineage_fails_closed_for_reads_and_builds(self) -> None:
        for mismatch in ("evidence-context", "context-fit", "fit-blueprint"):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                fit_v1, fit_ref_v1 = fixture.build_fit()
                deck_v1 = fixture.valid_blueprint(fit_ref_v1)
                fixture.service.build_reading_deck_blueprint(
                    "deck-v1", fixture.kernel.load().revision, deck_v1
                )

                if mismatch == "evidence-context":
                    replacement = copy.deepcopy(fixture.evidence_payload)
                    replacement["generated_at"] = "2026-08-16T00:00:00+08:00"
                    slot = "content/evidence-book"
                    kind = "presales-evidence-book"
                elif mismatch == "context-fit":
                    replacement = copy.deepcopy(fixture.context_payload)
                    replacement["current_business_matter"] = "确认第二版业务事项"
                    slot = "content/decision-context"
                    kind = "customer-decision-context"
                else:
                    replacement = copy.deepcopy(fit_v1)
                    replacement["symptoms"][0]["statement"] = "第二版问题陈述"
                    slot = "content/problem-solution-fit"
                    kind = "problem-solution-fit-map"
                corrupted = fixture.kernel.commit(
                    command_id=f"corrupt-{mismatch}",
                    expected_revision=fixture.kernel.load().revision,
                    event_type="test.mixed-current-lineage",
                    artifact_updates={slot: (kind, replacement)},
                )

                with self.assertRaisesRegex(
                    ContractValidationError, "content chain lineage"
                ):
                    fixture.service.get_current_content_chain()

                before = authority_snapshot(fixture.kernel)
                if mismatch == "evidence-context":
                    value = fixture.valid_fit()
                    value["evidence_book_ref"] = corrupted.artifact_heads[slot]
                    with self.assertRaisesRegex(
                        ContractValidationError, "content chain lineage"
                    ):
                        fixture.service.build_problem_solution_fit(
                            "mixed-fit", fixture.kernel.load().revision, value
                        )
                elif mismatch == "context-fit":
                    value = fixture.valid_blueprint(fit_ref_v1)
                    value["decision_context_ref"] = corrupted.artifact_heads[slot]
                    with self.assertRaisesRegex(
                        ContractValidationError, "content chain lineage"
                    ):
                        fixture.service.build_reading_deck_blueprint(
                            "mixed-blueprint", fixture.kernel.load().revision, value
                        )
                self.assertEqual(authority_snapshot(fixture.kernel), before)

    def test_four_build_operations_replay_original_results_semantically(self) -> None:
        for operation in ("evidence", "context", "fit", "blueprint"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as folder:
                fixture = ContentChainFixture(folder)
                if operation == "evidence":
                    command_id = "evidence"
                    original_payload = copy.deepcopy(fixture.evidence_payload)
                    original_ref = fixture.evidence_ref
                    build = fixture.service.build_evidence_book
                    changed_field = "generated_at"
                    changed_value = "2026-08-16T00:00:00+08:00"
                elif operation == "context":
                    command_id = "context"
                    original_payload = copy.deepcopy(fixture.context_payload)
                    original_ref = fixture.context_ref
                    build = fixture.service.build_decision_context
                    changed_field = "current_business_matter"
                    changed_value = "确认第二版业务事项"
                elif operation == "fit":
                    original_payload, original_ref = fixture.build_fit()
                    command_id = "fit"
                    build = fixture.service.build_problem_solution_fit
                    changed_field = "fit-statement"
                    changed_value = "第二版问题陈述"
                else:
                    _fit_payload, fit_ref = fixture.build_fit()
                    original_payload = fixture.valid_blueprint(fit_ref)
                    command_id = "blueprint"
                    build = fixture.service.build_reading_deck_blueprint
                    original_ref = build(
                        command_id,
                        fixture.kernel.load().revision,
                        original_payload,
                    )
                    changed_field = "speaker-notes"
                    changed_value = "第二版讲稿备注"

                immediate = authority_snapshot(fixture.kernel)
                self.assertEqual(
                    build(command_id, 0, copy.deepcopy(original_payload)),
                    original_ref,
                )
                self.assertEqual(authority_snapshot(fixture.kernel), immediate)

                changed_payload = copy.deepcopy(original_payload)
                if changed_field == "fit-statement":
                    changed_payload["symptoms"][0]["statement"] = changed_value
                elif changed_field == "speaker-notes":
                    changed_payload["slides"][0]["speaker_notes"] = changed_value
                else:
                    changed_payload[changed_field] = changed_value
                before_changed_replay = authority_snapshot(fixture.kernel)
                with self.assertRaisesRegex(
                    ContractValidationError,
                    "Processed command has different semantics",
                ):
                    build(
                        command_id,
                        fixture.kernel.load().revision,
                        changed_payload,
                    )
                self.assertEqual(
                    authority_snapshot(fixture.kernel), before_changed_replay
                )

                replacement_payload = copy.deepcopy(changed_payload)
                replacement_ref = build(
                    f"{command_id}-v2",
                    fixture.kernel.load().revision,
                    replacement_payload,
                )
                self.assertNotEqual(replacement_ref, original_ref)
                after_replacement = authority_snapshot(fixture.kernel)
                self.assertEqual(
                    build(command_id, 0, copy.deepcopy(original_payload)),
                    original_ref,
                )
                self.assertEqual(authority_snapshot(fixture.kernel), after_replacement)

    def test_new_command_with_stale_revision_is_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            fixture = ContentChainFixture(folder)
            payload = fixture.valid_fit()
            before = authority_snapshot(fixture.kernel)
            with self.assertRaises(RevisionConflictError):
                fixture.service.build_problem_solution_fit(
                    "stale-fit",
                    fixture.kernel.load().revision - 1,
                    payload,
                )
            self.assertEqual(authority_snapshot(fixture.kernel), before)

    def test_current_chain_read_is_closed_incremental_and_defensive(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="read-chain")
            seeded = kernel.commit(
                command_id="seed",
                expected_revision=0,
                event_type="test.seeded",
                artifact_updates={
                    "mission/confirmation": (
                        "mission-confirmation",
                        {"material_mode": "material-backed"},
                    ),
                    "materials": (
                        "material-inventory",
                        source_inventory(kernel),
                    ),
                },
            )
            service = PresalesContentService(kernel)

            def expected_objects(**values) -> dict:
                return {
                    "evidence_book": values.get("evidence_book"),
                    "decision_context": values.get("decision_context"),
                    "problem_solution_fit": values.get("problem_solution_fit"),
                    "reading_blueprint": values.get("reading_blueprint"),
                }

            self.assertEqual(
                service.get_current_content_chain(),
                {
                    "project_id": kernel.project_id,
                    "revision": seeded.revision,
                    "objects": expected_objects(),
                },
            )

            evidence = evidence_book()
            evidence["mission_confirmation_ref"] = seeded.artifact_heads[
                "mission/confirmation"
            ]
            evidence["material_inventory_ref"] = seeded.artifact_heads["materials"]
            evidence = bind_findings(kernel, evidence)
            evidence_ref = service.build_evidence_book(
                "evidence", kernel.load().revision, evidence
            )
            evidence_value = {"ref": evidence_ref, "payload": evidence}
            self.assertEqual(
                service.get_current_content_chain()["objects"],
                expected_objects(evidence_book=evidence_value),
            )

            context = decision_context()
            context["evidence_book_ref"] = evidence_ref
            context_ref = service.build_decision_context(
                "context", kernel.load().revision, context
            )
            context_value = {"ref": context_ref, "payload": context}
            self.assertEqual(
                service.get_current_content_chain()["objects"],
                expected_objects(
                    evidence_book=evidence_value,
                    decision_context=context_value,
                ),
            )

            fit = bind_findings(kernel, fit_map())
            fit["evidence_book_ref"] = evidence_ref
            fit["decision_context_ref"] = context_ref
            fit_ref = service.build_problem_solution_fit(
                "fit", kernel.load().revision, fit
            )
            fit_value = {"ref": fit_ref, "payload": fit}
            self.assertEqual(
                service.get_current_content_chain()["objects"],
                expected_objects(
                    evidence_book=evidence_value,
                    decision_context=context_value,
                    problem_solution_fit=fit_value,
                ),
            )

            deck = bind_findings(kernel, blueprint())
            deck["project_id"] = kernel.project_id
            deck["evidence_book_ref"] = evidence_ref
            deck["decision_context_ref"] = context_ref
            deck["problem_solution_fit_ref"] = fit_ref
            deck_ref = service.build_reading_deck_blueprint(
                "deck", kernel.load().revision, deck
            )
            deck_value = {"ref": deck_ref, "payload": deck}
            projection = service.get_current_content_chain()
            self.assertEqual(
                projection,
                {
                    "project_id": kernel.project_id,
                    "revision": kernel.load().revision,
                    "objects": expected_objects(
                        evidence_book=evidence_value,
                        decision_context=context_value,
                        problem_solution_fit=fit_value,
                        reading_blueprint=deck_value,
                    ),
                },
            )
            projection["objects"]["evidence_book"]["payload"]["facts"].clear()
            self.assertEqual(
                service.get_current_content_chain()["objects"]["evidence_book"][
                    "payload"
                ]["facts"],
                evidence["facts"],
            )

    def test_replaced_chain_preserves_immutable_v1_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            fixture = ContentChainFixture(folder)
            fit_v1, fit_ref_v1 = fixture.build_fit()
            deck_v1 = fixture.valid_blueprint(fit_ref_v1)
            deck_ref_v1 = fixture.service.build_reading_deck_blueprint(
                "deck-v1", fixture.kernel.load().revision, deck_v1
            )
            refs_v1 = (
                fixture.evidence_ref,
                fixture.context_ref,
                fit_ref_v1,
                deck_ref_v1,
            )
            v1_bytes = {
                ref: fixture.kernel.artifacts.path_for(
                    ArtifactReference.parse(ref)
                ).read_bytes()
                for ref in refs_v1
            }
            v1_payloads = {
                ref: fixture.kernel.artifacts.resolve(
                    ArtifactReference.parse(ref)
                )["payload"]
                for ref in refs_v1
            }

            evidence_v2 = copy.deepcopy(fixture.evidence_payload)
            evidence_v2["source_version"] = "content-v2"
            evidence_v2["generated_at"] = "2026-08-16T00:00:00+08:00"
            evidence_ref_v2 = fixture.service.build_evidence_book(
                "evidence-v2", fixture.kernel.load().revision, evidence_v2
            )
            context_v2 = copy.deepcopy(fixture.context_payload)
            context_v2["evidence_book_ref"] = evidence_ref_v2
            context_v2["current_business_matter"] = "确认第二版业务事项"
            context_ref_v2 = fixture.service.build_decision_context(
                "context-v2", fixture.kernel.load().revision, context_v2
            )
            fit_v2 = copy.deepcopy(fit_v1)
            fit_v2["evidence_book_ref"] = evidence_ref_v2
            fit_v2["decision_context_ref"] = context_ref_v2
            fit_v2["symptoms"][0]["statement"] = "第二版问题陈述"
            fit_ref_v2 = fixture.service.build_problem_solution_fit(
                "fit-v2", fixture.kernel.load().revision, fit_v2
            )
            deck_v2 = copy.deepcopy(deck_v1)
            deck_v2["source_version"] = "content-v2"
            deck_v2["evidence_book_ref"] = evidence_ref_v2
            deck_v2["decision_context_ref"] = context_ref_v2
            deck_v2["problem_solution_fit_ref"] = fit_ref_v2
            deck_v2["slides"][0]["speaker_notes"] = "第二版讲稿备注"
            deck_ref_v2 = fixture.service.build_reading_deck_blueprint(
                "deck-v2", fixture.kernel.load().revision, deck_v2
            )

            refs_v2 = (
                evidence_ref_v2,
                context_ref_v2,
                fit_ref_v2,
                deck_ref_v2,
            )
            for ref_v1, ref_v2 in zip(refs_v1, refs_v2, strict=True):
                self.assertNotEqual(ref_v1, ref_v2)
                reference = ArtifactReference.parse(ref_v1)
                self.assertEqual(
                    fixture.kernel.artifacts.path_for(reference).read_bytes(),
                    v1_bytes[ref_v1],
                )
                self.assertEqual(
                    fixture.kernel.artifacts.resolve(reference)["payload"],
                    v1_payloads[ref_v1],
                )
            current = fixture.kernel.load().artifact_heads
            self.assertEqual(
                tuple(
                    current[slot]
                    for slot in (
                        "content/evidence-book",
                        "content/decision-context",
                        "content/problem-solution-fit",
                        "content/reading-blueprint",
                    )
                ),
                refs_v2,
            )


if __name__ == "__main__":
    unittest.main()
