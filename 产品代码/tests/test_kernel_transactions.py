from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateMutationError,
    ProjectIdentityError,
    RevisionConflictError,
    TransactionRollbackError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def object_files(kernel: ProjectKernel) -> tuple[str, ...]:
    root = kernel.artifacts.objects_root
    return tuple(
        sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
        )
    )


def event_files(kernel: ProjectKernel) -> tuple[str, ...]:
    if not kernel.events_root.exists():
        return ()
    return tuple(
        sorted(
            path.name
            for path in kernel.events_root.iterdir()
            if path.is_file()
        )
    )


class ProjectKernelTests(unittest.TestCase):
    def test_load_rejects_another_project_and_gate_requires_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ProjectKernel.initialize(root, project_id="p1")
            with self.assertRaises(ProjectIdentityError):
                ProjectKernel(root, project_id="p2").load()

            kernel = ProjectKernel(root, project_id="p1")
            with self.assertRaises(GateMutationError):
                kernel.commit(
                    command_id="forged",
                    expected_revision=0,
                    event_type="gate.forged",
                    artifact_updates={},
                    gate_mutation={"G0": "passed"},
                )

    def test_commit_advances_revision_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            first = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={
                    "mission": ("mission-brief", {"goal": "通过方案"})
                },
            )
            repeated = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={
                    "mission": ("mission-brief", {"goal": "通过方案"})
                },
            )
            self.assertEqual(first.revision, 1)
            self.assertEqual(repeated.revision, 1)
            self.assertEqual(first.artifact_heads, repeated.artifact_heads)
            with self.assertRaises(RevisionConflictError):
                kernel.commit(
                    command_id="cmd-2",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={},
                )

    def test_fingerprinted_command_replay_rejects_different_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            first = kernel.commit(
                command_id="fingerprinted",
                expected_revision=0,
                event_type="agent.content-result-committed",
                artifact_updates={"result": ("result", {"value": 1})},
                command_fingerprint="a" * 64,
            )
            repeated = kernel.commit(
                command_id="fingerprinted",
                expected_revision=0,
                event_type="agent.content-result-committed",
                artifact_updates={"result": ("result", {"value": 1})},
                command_fingerprint="a" * 64,
            )
            self.assertEqual(repeated, first)
            with self.assertRaises(ContractValidationError):
                kernel.commit(
                    command_id="fingerprinted",
                    expected_revision=0,
                    event_type="agent.content-result-committed",
                    artifact_updates={"result": ("result", {"value": 2})},
                    command_fingerprint="b" * 64,
                )
            self.assertEqual(kernel.load(), first)

    def test_concurrent_fingerprinted_command_collision_has_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            barrier = threading.Barrier(2)

            def commit(value: int) -> tuple[str, int]:
                barrier.wait()
                try:
                    state = kernel.commit(
                        command_id="concurrent-result",
                        expected_revision=0,
                        event_type="agent.content-result-committed",
                        artifact_updates={"result": ("result", {"value": value})},
                        command_fingerprint=str(value) * 64,
                    )
                    return "success", state.revision
                except ContractValidationError:
                    return "conflict", kernel.load().revision

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(commit, (1, 2)))
            self.assertEqual(sorted(status for status, _ in outcomes), [
                "conflict", "success"
            ])
            self.assertEqual(kernel.load().revision, 1)
            self.assertEqual(len(tuple(kernel.events_root.iterdir())), 1)

    def test_failed_state_write_rolls_back_the_entire_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = ProjectKernel.initialize(root, project_id="p1")
            real_write = __import__(
                "ai_ppt_studio.kernel.transactions",
                fromlist=["atomic_write_json"],
            ).atomic_write_json

            def fail_state(path: Path, payload: dict[str, object]) -> None:
                if path.name == "state.json":
                    raise OSError("simulated state failure")
                real_write(path, payload)

            with patch(
                "ai_ppt_studio.kernel.transactions.atomic_write_json",
                side_effect=fail_state,
            ), self.assertRaises(OSError):
                kernel.commit(
                    command_id="cmd-1",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={
                        "mission": ("mission-brief", {"goal": "通过方案"})
                    },
                )
            self.assertEqual(kernel.load().revision, 0)
            self.assertEqual(object_files(kernel), ())
            self.assertEqual(event_files(kernel), ())

    def test_detached_artifacts_are_atomic_audited_and_never_become_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            detached_payload = {"full_copy": ["第一段", "第二段"]}
            detached_ref = str(
                kernel.artifacts.reference_for(
                    "content-visible-copy-snapshot", detached_payload
                )
            )
            committed = kernel.commit(
                command_id="detached-success",
                expected_revision=0,
                event_type="content.page-decision-saved",
                artifact_updates={
                    "content/page-decisions": (
                        "content-page-decision-set",
                        {"decision_refs": [detached_ref]},
                    )
                },
                detached_artifacts=(
                    ("content-visible-copy-snapshot", detached_payload),
                ),
            )
            self.assertNotIn(detached_ref, committed.artifact_heads.values())
            self.assertEqual(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(detached_ref)
                )["payload"],
                detached_payload,
            )
            event = json.loads(
                (kernel.events_root / "r00000001.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(event["detached_artifact_refs"], [detached_ref])

    def test_detached_revision_conflict_writes_no_objects_events_or_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            kernel.commit(
                command_id="advance",
                expected_revision=0,
                event_type="test.advance",
                artifact_updates={},
            )
            before_state = kernel.state_path.read_bytes()
            before_objects = object_files(kernel)
            before_events = event_files(kernel)
            with self.assertRaises(RevisionConflictError):
                kernel.commit(
                    command_id="stale-detached",
                    expected_revision=0,
                    event_type="test.detached",
                    artifact_updates={
                        "head": ("head-artifact", {"value": "new"})
                    },
                    detached_artifacts=(
                        ("detached-artifact", {"value": "new"}),
                    ),
                )
            self.assertEqual(kernel.state_path.read_bytes(), before_state)
            self.assertEqual(object_files(kernel), before_objects)
            self.assertEqual(event_files(kernel), before_events)

    def test_transaction_failure_rolls_back_only_new_objects_event_and_state(self) -> None:
        for failure_target in ("event", "state"):
            with self.subTest(failure_target=failure_target), tempfile.TemporaryDirectory() as temp:
                kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
                preexisting_payload = {"value": "already-present"}
                preexisting_ref = str(
                    kernel.artifacts.put(
                        "detached-artifact", preexisting_payload
                    )
                )
                before_state = kernel.state_path.read_bytes()
                before_objects = object_files(kernel)
                before_events = event_files(kernel)
                real_write = __import__(
                    "ai_ppt_studio.kernel.transactions",
                    fromlist=["atomic_write_json"],
                ).atomic_write_json

                def fail_after_write(path: Path, payload: dict[str, object]) -> None:
                    real_write(path, payload)
                    if (
                        failure_target == "event"
                        and path.name == "r00000001.json"
                    ) or (
                        failure_target == "state" and path.name == "state.json"
                    ):
                        raise OSError(f"simulated {failure_target} failure")

                with patch(
                    "ai_ppt_studio.kernel.transactions.atomic_write_json",
                    side_effect=fail_after_write,
                ), self.assertRaises(OSError):
                    kernel.commit(
                        command_id=f"rollback-{failure_target}",
                        expected_revision=0,
                        event_type="test.rollback",
                        artifact_updates={
                            "head": ("head-artifact", {"value": "new"})
                        },
                        detached_artifacts=(
                            ("detached-artifact", preexisting_payload),
                            ("detached-artifact", {"value": "new"}),
                        ),
                    )
                self.assertEqual(kernel.state_path.read_bytes(), before_state)
                self.assertEqual(object_files(kernel), before_objects)
                self.assertEqual(event_files(kernel), before_events)
                self.assertTrue(
                    kernel.artifacts.path_for(
                        ArtifactReference.parse(preexisting_ref)
                    ).exists()
                )

    def test_rollback_cleanup_failures_preserve_authority_and_original_cause(self) -> None:
        for cleanup_target in ("object", "event", "object-and-event"):
            with self.subTest(cleanup_target=cleanup_target), tempfile.TemporaryDirectory() as temp:
                kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
                before_state = kernel.state_path.read_bytes()
                real_write = __import__(
                    "ai_ppt_studio.kernel.transactions",
                    fromlist=["atomic_write_json"],
                ).atomic_write_json
                real_unlink = Path.unlink
                attempted: list[str] = []

                def fail_after_state_write(
                    path: Path, payload: dict[str, object]
                ) -> None:
                    real_write(path, payload)
                    if path.name == "state.json":
                        raise OSError("original state-write failure")

                def selective_unlink(
                    path: Path, *args: object, **kwargs: object
                ) -> None:
                    is_event = path.name == "r00000001.json"
                    is_object = path.suffix == ".json" and "objects" in path.parts
                    if is_event:
                        attempted.append("event")
                    if is_object:
                        attempted.append("object")
                    if (
                        cleanup_target in {"event", "object-and-event"}
                        and is_event
                    ) or (
                        cleanup_target in {"object", "object-and-event"}
                        and is_object
                    ):
                        raise OSError(f"cleanup {cleanup_target} failure")
                    real_unlink(path, *args, **kwargs)

                with patch(
                    "ai_ppt_studio.kernel.transactions.atomic_write_json",
                    side_effect=fail_after_state_write,
                ), patch.object(Path, "unlink", autospec=True, side_effect=selective_unlink):
                    with self.assertRaises(TransactionRollbackError) as caught:
                        kernel.commit(
                            command_id=f"cleanup-{cleanup_target}",
                            expected_revision=0,
                            event_type="test.rollback-cleanup",
                            artifact_updates={
                                "head": ("head-artifact", {"value": "new"})
                            },
                            detached_artifacts=(
                                ("detached-artifact", {"value": "new"}),
                            ),
                        )
                self.assertIsInstance(caught.exception.__cause__, OSError)
                self.assertIn(
                    "original state-write failure",
                    str(caught.exception.__cause__),
                )
                self.assertTrue(caught.exception.state_restored)
                self.assertFalse(
                    caught.exception.preserved_exposed_transaction
                )
                self.assertEqual(kernel.state_path.read_bytes(), before_state)
                self.assertIn("event", attempted)
                self.assertGreaterEqual(attempted.count("object"), 2)
                self.assertTrue(caught.exception.rollback_errors)

    def test_state_restore_failure_preserves_exposed_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            cleanup_attempts: list[str] = []
            real_unlink = Path.unlink
            real_write = __import__(
                "ai_ppt_studio.kernel.transactions",
                fromlist=["atomic_write_json"],
            ).atomic_write_json

            def fail_after_state_write(
                path: Path, payload: dict[str, object]
            ) -> None:
                real_write(path, payload)
                if path.name == "state.json":
                    raise OSError("original state-write failure")

            def reject_exposed_cleanup(
                path: Path, *args: object, **kwargs: object
            ) -> None:
                if path.name == "r00000001.json" or (
                    "objects" in path.parts and path.suffix == ".json"
                ):
                    cleanup_attempts.append(str(path))
                    raise OSError("exposed transaction must be preserved")
                real_unlink(path, *args, **kwargs)

            with patch(
                "ai_ppt_studio.kernel.transactions.atomic_write_json",
                side_effect=fail_after_state_write,
            ), patch.object(
                kernel,
                "_restore_bytes",
                side_effect=OSError("state restore failure"),
            ), patch.object(
                Path,
                "unlink",
                autospec=True,
                side_effect=reject_exposed_cleanup,
            ), self.assertRaises(TransactionRollbackError) as caught:
                kernel.commit(
                    command_id="restore-failure",
                    expected_revision=0,
                    event_type="test.restore-failure",
                    artifact_updates={
                        "head": ("head-artifact", {"value": "new"})
                    },
                    detached_artifacts=(
                        ("detached-artifact", {"value": "new"}),
                    ),
                )
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertIn(
                "original state-write failure", str(caught.exception.__cause__)
            )
            self.assertFalse(caught.exception.state_restored)
            self.assertTrue(caught.exception.preserved_exposed_transaction)
            self.assertEqual(cleanup_attempts, [])
            exposed = kernel.load()
            self.assertEqual(exposed.revision, 1)
            self.assertEqual(
                exposed.last_transaction_id,
                json.loads(
                    (kernel.events_root / "r00000001.json").read_text(
                        encoding="utf-8"
                    )
                )["transaction_id"],
            )
            for reference in exposed.artifact_heads.values():
                kernel.artifacts.resolve(ArtifactReference.parse(reference))
            self.assertEqual(len(object_files(kernel)), 2)

    def test_preflight_rejects_corrupt_existing_candidates_before_any_write(self) -> None:
        cases = ("detached", "later-detached", "head")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
                corrupt_kind = (
                    "head-artifact" if case == "head" else "detached-artifact"
                )
                corrupt_payload = {"value": f"corrupt-{case}"}
                corrupt_ref = kernel.artifacts.reference_for(
                    corrupt_kind, corrupt_payload
                )
                corrupt_path = kernel.artifacts.path_for(corrupt_ref)
                corrupt_path.parent.mkdir(parents=True, exist_ok=True)
                corrupt_path.write_text("{not-json", encoding="utf-8")
                before_state = kernel.state_path.read_bytes()
                before_objects = object_files(kernel)
                before_events = event_files(kernel)
                updates = (
                    {"head": (corrupt_kind, corrupt_payload)}
                    if case == "head"
                    else {
                        "head": ("head-artifact", {"value": "new-head"})
                    }
                )
                detached = (
                    ()
                    if case == "head"
                    else (
                        *(
                            (("detached-artifact", {"value": "new-first"}),)
                            if case == "later-detached"
                            else ()
                        ),
                        (corrupt_kind, corrupt_payload),
                    )
                )
                with self.assertRaises(ArtifactReferenceError):
                    kernel.commit(
                        command_id=f"corrupt-existing-{case}",
                        expected_revision=0,
                        event_type="test.corrupt-existing",
                        artifact_updates=updates,
                        detached_artifacts=detached,
                    )
                self.assertEqual(kernel.state_path.read_bytes(), before_state)
                self.assertEqual(object_files(kernel), before_objects)
                self.assertEqual(event_files(kernel), before_events)
                self.assertEqual(
                    corrupt_path.read_text(encoding="utf-8"), "{not-json"
                )


if __name__ == "__main__":
    unittest.main()
