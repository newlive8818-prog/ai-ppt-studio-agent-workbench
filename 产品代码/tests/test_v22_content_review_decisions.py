from __future__ import annotations

import copy
import importlib
import json
import sys
import unittest
from typing import Any


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_v22_content_review_projection import (  # noqa: E402
    projection_service_type,
    review_ready_kernel,
)
from ai_ppt_studio.errors import (  # noqa: E402
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402


def decision_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_review.decision_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 content page-decision service") from exc
    candidate = getattr(module, "ContentPageDecisionService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing ContentPageDecisionService")
    return candidate


class ContentPageDecisionServiceTests(unittest.TestCase):
    def test_save_rejects_empty_command_id_without_writes(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        service = decision_service_type()(kernel)

        for command_id in ("", "   "):
            with self.subTest(command_id=repr(command_id)):
                before = kernel.load()
                before_events = len(list(kernel.events_root.glob("r*.json")))

                with self.assertRaisesRegex(
                    ContractValidationError, "command_id is required"
                ):
                    service.save(
                        command_id=command_id,
                        expected_revision=before.revision,
                        review_session_id=str(session["review_session_id"]),
                        review_batch_id="v22-empty-command-batch",
                        slide_id=str(blueprint["slides"][0]["slide_id"]),
                        decision="approved",
                        comment="",
                    )

                self.assertEqual(kernel.load().revision, before.revision)
                self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
                self.assertNotIn("", kernel.load().processed_commands)
                self.assertEqual(
                    len(list(kernel.events_root.glob("r*.json"))), before_events
                )

    def test_save_v22_page_decision_is_source_bound_and_has_no_gate_side_effects(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        before = kernel.load()
        before_heads = dict(before.artifact_heads)
        blueprint = kernel.artifacts.resolve(
            __import__("ai_ppt_studio.kernel.references", fromlist=["ArtifactReference"])
            .ArtifactReference.parse(blueprint_ref)
        )["payload"]
        target = blueprint["slides"][0]

        page, progress, state = decision_service_type()(kernel).save(
            command_id="save-v22-page-decision",
            expected_revision=before.revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="v22-current-batch",
            slide_id=str(target["slide_id"]),
            decision="modify",
            comment="  请把来源和诊断假设的边界写清楚。  ",
        )

        changed = {
            slot
            for slot in set(before_heads) | set(state.artifact_heads)
            if before_heads.get(slot) != state.artifact_heads.get(slot)
        }
        self.assertEqual(changed, {"content/page-decisions"})
        self.assertEqual(state.artifact_heads["content/reading-deck-blueprint"], blueprint_ref)
        self.assertEqual(
            state.artifact_heads["content/gate/evidence"],
            before_heads["content/gate/evidence"],
        )
        self.assertEqual(
            state.artifact_heads["content/gate/presales-reading"],
            before_heads["content/gate/presales-reading"],
        )
        self.assertEqual(
            state.artifact_heads["content/acceptance"],
            before_heads["content/acceptance"],
        )
        self.assertEqual(page["decision"], "modify")
        self.assertEqual(page["comment"], "请把来源和诊断假设的边界写清楚。")
        self.assertTrue(page["completed"])
        self.assertEqual(progress["completed"], 1)
        self.assertEqual(progress["counts"]["modify"], 1)

    def test_same_command_replays_its_original_page_decision(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            __import__("ai_ppt_studio.kernel.references", fromlist=["ArtifactReference"])
            .ArtifactReference.parse(blueprint_ref)
        )["payload"]
        slide_id = str(blueprint["slides"][0]["slide_id"])
        service = decision_service_type()(kernel)
        revision = kernel.load().revision
        first_page, first_progress, first_state = service.save(
            command_id="replay-page-decision",
            expected_revision=revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="v22-replay-batch",
            slide_id=slide_id,
            decision="evidence",
            comment="需要补充可定位的来源。",
        )
        self.assertGreater(first_state.revision, revision)

        replayed_page, replayed_progress, replayed_state = service.save(
            command_id="replay-page-decision",
            expected_revision=revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="v22-replay-batch",
            slide_id=slide_id,
            decision="evidence",
            comment="需要补充可定位的来源。",
        )

        self.assertEqual(replayed_page, first_page)
        self.assertEqual(replayed_progress, first_progress)
        self.assertEqual(replayed_state.revision, first_state.revision)

    def test_page_decision_replay_rejects_a_same_value_receipt_from_another_source(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        slide_id = str(blueprint["slides"][0]["slide_id"])
        service = decision_service_type()(kernel)
        arguments = {
            "command_id": "replay-page-decision-cross-source-receipt",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "v22-cross-source-replay-batch",
            "slide_id": slide_id,
            "decision": "approved",
            "comment": "",
        }
        service.save(**arguments)
        decision_set_ref = str(kernel.load().artifact_heads["content/page-decisions"])
        decision_set = copy.deepcopy(
            kernel.artifacts.resolve(ArtifactReference.parse(decision_set_ref))["payload"]
        )
        row = decision_set["decision_refs"][0]
        decision = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(str(row["decision_ref"]))
            )["payload"]
        )
        foreign_source_ref = "artifact://reading-deck-blueprint/" + "0" * 64
        decision["source_version"] = foreign_source_ref
        wrong_decision_ref = str(
            kernel.artifacts.reference_for("content-page-decision", decision)
        )
        decision_set["source_version"] = foreign_source_ref
        decision_set["decision_refs"][0]["decision_ref"] = wrong_decision_ref
        state = kernel.load()
        kernel.commit(
            command_id="install-page-decision-replay-cross-source-receipt",
            expected_revision=state.revision,
            event_type="test.page-decision-replay-cross-source-receipt",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
            detached_artifacts=(("content-page-decision", decision),),
        )
        revision = kernel.load().processed_commands[arguments["command_id"]]
        event_path = kernel.events_root / f"r{revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["artifact_heads"]["content/page-decisions"] = str(
            kernel.load().artifact_heads["content/page-decisions"]
        )
        event_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaisesRegex(
            ContractValidationError,
            "Processed page-decision command has different semantics",
        ):
            service.save(**arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_page_decision_replay_normalizes_a_missing_artifact_reference(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        arguments = {
            "command_id": "replay-page-decision-missing-artifact",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "v22-missing-artifact-replay-batch",
            "slide_id": str(blueprint["slides"][0]["slide_id"]),
            "decision": "approved",
            "comment": "",
        }
        service = decision_service_type()(kernel)
        service.save(**arguments)
        revision = kernel.load().processed_commands[arguments["command_id"]]
        event_path = kernel.events_root / f"r{revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["artifact_heads"]["content/page-decisions"] = (
            "artifact://content-page-decision-set/" + "0" * 64
        )
        event_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaisesRegex(
            ContractValidationError,
            "Processed page-decision command has different semantics",
        ):
            service.save(**arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_save_prioritizes_revision_conflict_before_current_projection(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        stale_revision = kernel.load().revision
        malformed = {**copy.deepcopy(session), "review_type": "visual-professional"}
        kernel.commit(
            command_id="install-invalid-current-session-after-stale-revision",
            expected_revision=stale_revision,
            event_type="test.invalid-current-content-session",
            artifact_updates={
                "review/session/current/content-full-deck": (
                    "review-session",
                    malformed,
                )
            },
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaises(RevisionConflictError):
            decision_service_type()(kernel).save(
                command_id="reject-v22-stale-decision-before-projection",
                expected_revision=stale_revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="v22-stale-revision-batch",
                slide_id=str(blueprint["slides"][0]["slide_id"]),
                decision="approved",
                comment="",
            )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_page_decision_replay_rejects_a_row_with_the_wrong_slide_order(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        target = blueprint["slides"][0]
        service = decision_service_type()(kernel)
        arguments = {
            "command_id": "replay-page-decision-row-order-receipt",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "v22-row-order-replay-batch",
            "slide_id": str(target["slide_id"]),
            "decision": "approved",
            "comment": "",
        }
        service.save(**arguments)
        decision_set_ref = str(kernel.load().artifact_heads["content/page-decisions"])
        decision_set = copy.deepcopy(
            kernel.artifacts.resolve(ArtifactReference.parse(decision_set_ref))["payload"]
        )
        decision_set["decision_refs"][0]["slide_order"] = int(
            target["order"]
        ) + 1
        state = kernel.load()
        kernel.commit(
            command_id="install-page-decision-replay-row-order-receipt",
            expected_revision=state.revision,
            event_type="test.page-decision-replay-row-order-receipt",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
        )
        revision = kernel.load().processed_commands[arguments["command_id"]]
        event_path = kernel.events_root / f"r{revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["artifact_heads"]["content/page-decisions"] = str(
            kernel.load().artifact_heads["content/page-decisions"]
        )
        event_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaisesRegex(
            ContractValidationError,
            "Processed page-decision command has different semantics",
        ):
            service.save(**arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_page_decision_replay_rejects_a_snapshot_with_the_wrong_title(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        target = blueprint["slides"][0]
        service = decision_service_type()(kernel)
        arguments = {
            "command_id": "replay-page-decision-snapshot-receipt",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "v22-snapshot-replay-batch",
            "slide_id": str(target["slide_id"]),
            "decision": "approved",
            "comment": "",
        }
        service.save(**arguments)
        decision_set_ref = str(kernel.load().artifact_heads["content/page-decisions"])
        decision_set = copy.deepcopy(
            kernel.artifacts.resolve(ArtifactReference.parse(decision_set_ref))["payload"]
        )
        row = decision_set["decision_refs"][0]
        decision = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(str(row["decision_ref"]))
            )["payload"]
        )
        snapshot = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(
                    str(decision["visible_copy_snapshot_ref"])
                )
            )["payload"]
        )
        snapshot["slide_title_snapshot"] = "不匹配的历史页标题"
        wrong_snapshot_ref = str(
            kernel.artifacts.reference_for(
                "content-visible-copy-snapshot", snapshot
            )
        )
        decision["visible_copy_snapshot_ref"] = wrong_snapshot_ref
        wrong_decision_ref = str(
            kernel.artifacts.reference_for("content-page-decision", decision)
        )
        decision_set["decision_refs"][0]["decision_ref"] = wrong_decision_ref
        state = kernel.load()
        kernel.commit(
            command_id="install-page-decision-replay-snapshot-receipt",
            expected_revision=state.revision,
            event_type="test.page-decision-replay-snapshot-receipt",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
            detached_artifacts=(
                ("content-visible-copy-snapshot", snapshot),
                ("content-page-decision", decision),
            ),
        )
        revision = kernel.load().processed_commands[arguments["command_id"]]
        event_path = kernel.events_root / f"r{revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["artifact_heads"]["content/page-decisions"] = str(
            kernel.load().artifact_heads["content/page-decisions"]
        )
        event_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaisesRegex(
            ContractValidationError,
            "Processed page-decision command has different semantics",
        ):
            service.save(**arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_projection_restores_saved_page_decision_from_authoritative_state(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            __import__("ai_ppt_studio.kernel.references", fromlist=["ArtifactReference"])
            .ArtifactReference.parse(blueprint_ref)
        )["payload"]
        slide_id = str(blueprint["slides"][0]["slide_id"])
        decision_service_type()(kernel).save(
            command_id="save-for-projection",
            expected_revision=kernel.load().revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="v22-projection-batch",
            slide_id=slide_id,
            decision="merge-or-delete",
            comment="与后一页合并，避免重复说明。",
        )

        projection = projection_service_type()(kernel).project(
            review_session_id=str(session["review_session_id"])
        )
        projected_slide = next(
            slide for slide in projection["slides"] if slide["slide_id"] == slide_id
        )

        self.assertEqual(
            projected_slide["decision_state"]["selected"], "merge-or-delete"
        )
        self.assertEqual(
            projected_slide["decision_state"]["comment"], "与后一页合并，避免重复说明。"
        )
        self.assertTrue(projected_slide["decision_state"]["saved"])
        self.assertTrue(projected_slide["decision_state"]["completed"])
        self.assertEqual(projection["review_progress"]["completed"], 1)
        self.assertEqual(projection["review_progress"]["counts"]["merge_or_delete"], 1)


if __name__ == "__main__":
    unittest.main()
