"""Durable generation recovery through real bridge processes and synthetic adapters.

All confirmations and image responses here are test fixtures, not user acceptance
or real provider evidence.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from threading import Barrier, local
import time
import unittest
from unittest.mock import patch

from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests import test_image_led_execution_entrypoint as entrypoint
from tests import v16_visual_fixtures
from tests.host_confirmation_fixtures import TEST_HOST_CONFIRMATION_SECRET, gate_confirmation_kwargs
from tests.test_image2_input_boundary import tree_snapshot


class ImageLedGenerationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = entrypoint.ImageLedExecutionEntrypointTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.release_dir = self.case.base / "adapter-releases"
        self.release_dir.mkdir()
        script = self.case.script.read_text()
        script = script.replace(
            'if sys.argv[2] == "unknown":',
            'import time\n'
            f'release = Path({str(self.release_dir)!r}) / request["request_id"]\n'
            'deadline = time.monotonic() + 20\n'
            'while not release.exists():\n'
            '    if time.monotonic() >= deadline: raise TimeoutError("fixture release missing")\n'
            '    time.sleep(0.01)\n'
            'if sys.argv[2] == "unknown":',
        )
        script = script.replace(
            '"response_id": "synthetic-response"',
            '"response_id": "synthetic-response-" + request["request_id"]',
        )
        self.case.script.write_text(script)

    def wait_for_calls(self, count):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                calls = self.case.calls()
            except json.JSONDecodeError:
                # A separate adapter process may still be finishing its JSONL write.
                calls = []
            if len(calls) >= count:
                return calls
            time.sleep(0.01)
        self.fail(f"synthetic adapter did not record {count} calls")

    def release_all(self):
        for call in self.case.calls():
            (self.release_dir / call["request"]["request_id"]).touch()

    def stored_response(self, task_id):
        slot = "project/image-led/request/" + task_id
        ref = self.case.kernel.load().artifact_heads[slot]
        payload = self.case.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]
        return ref, payload

    def candidate_payload(self, task_id, response_ref, pack_ref):
        pack = self.case.kernel.artifacts.resolve(ArtifactReference.parse(pack_ref))["payload"]
        copy = pack["confirmed_visible_copy"]
        return {"artifact_type": "image-led-candidate", "project_id": "p1",
            "request_id": task_id, "generation_response_ref": response_ref,
            "pack_ref": pack_ref, "slide_id": pack["slide_id"], "page_order": pack["page_order"],
            "selected_copy": {"items": [
                {"item_id": "title", "kind": "text", "role": "title", "text": copy["title"]},
                *[{"item_id": b["block_id"], "kind": "text", "role": "body", "text": b["text"]}
                  for b in copy["blocks"]],
            ]}, "material_roles": []}

    def assert_candidate_rejected_without_writes(self, task_id, response_ref, pack_ref):
        case = self.case
        before = tree_snapshot(case.project)
        process, reply = case.bridge({"operation": "commit-artifact",
            "command_id": "recovery-rejected-candidate", "task_id": task_id,
            "expected_revision": case.kernel.load().revision, "kind": "visual-contract",
            "payload": self.candidate_payload(task_id, response_ref, pack_ref)})
        self.assertNotEqual(process.returncode, 0, reply)
        self.assertEqual(tree_snapshot(case.project), before,
            "preserving the raw response must not make revoked or stale input eligible")
        self.assertFalse(any(slot.startswith("visual/image-led/candidate/")
                             for slot in case.kernel.load().artifact_heads))

    def assert_exact_response(self, task_id, original_claim, pack_ref):
        ref, response = self.stored_response(task_id)
        self.assertEqual(response["status"], "completed",
            "a returned image must survive unrelated revisions in its original request slot")
        self.assertEqual(response["project_id"], "p1")
        self.assertEqual(response["request_id"], task_id)
        self.assertEqual(response["claim_id"], original_claim["claim_id"])
        self.assertEqual(response["pack_ref"], pack_ref)
        self.assertEqual(response["payload_sha256"], original_claim["payload_sha256"])
        self.assertEqual(response["response_id"], "synthetic-response-" + task_id)
        self.assertEqual(base64.b64decode(response["image_base64"], validate=True), self.case.raw_image)
        self.assertEqual(response["image_sha256"], hashlib.sha256(self.case.raw_image).hexdigest())
        self.assertEqual(response["image_size"], [32, 18])
        self.assertEqual(response["image_mime_type"], "image/png")
        return ref, response

    def synthetic_terminal_response(self, started):
        """The exact legal return emitted by this fixture's blocked adapter."""
        return {**deepcopy(started), "status": "completed",
            "response_id": "synthetic-response-" + started["request_id"],
            "image_sha256": hashlib.sha256(self.case.raw_image).hexdigest(),
            "image_base64": base64.b64encode(self.case.raw_image).decode(),
            "image_size": [32, 18], "image_mime_type": "image/png"}

    def terminal_events(self):
        return [event for path in self.case.kernel.events_root.glob("*.json")
                if (event := json.loads(path.read_text()))["event_type"] == "image-led.request-returned"]

    def test_unrelated_public_decision_during_adapter_wait_preserves_exact_response(self):
        case = self.case
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(case.action, "recovery-unrelated")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, original_claim = self.stored_response(task_id)
                process, decision = case.bridge({
                    "operation": "submit-human-decision",
                    "command_id": "recovery-unrelated-decision",
                    "expected_revision": case.kernel.load().revision,
                    "target_ref": case.kernel.load().artifact_heads["content/reading-blueprint"],
                    "choice": "记录说明",
                    "feedback": "Synthetic unrelated decision while adapter waits",
                })
                self.assertEqual(process.returncode, 0, decision)
                decision_ref = case.kernel.load().artifact_heads["human/decision/latest"]
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        self.assert_exact_response(task_id, original_claim, case.packs[0])
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(case.kernel.load().artifact_heads["human/decision/latest"], decision_ref,
            "saving the response must not overwrite the concurrent human decision")
        self.assertEqual(len(case.calls()), 1)

    def test_public_scope_revocation_during_wait_preserves_response_but_rejects_candidate(self):
        case = self.case
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(case.action, "recovery-revocation")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, original_claim = self.stored_response(task_id)
                scope = case.policy["authorization_scope_ref"]
                process, context_reply = case.bridge({
                    "operation": "get-image-led-confirmation-context",
                    "target_ref": scope, "choice": "revoked"})
                self.assertEqual(process.returncode, 0, context_reply)
                fields = gate_confirmation_kwargs(context_reply["confirmation_context"],
                    identity_ref="test-host-confirmation://recovery-revocation")
                case.env["AI_PPT_HOST_CONFIRMATION_SECRET"] = TEST_HOST_CONFIRMATION_SECRET
                process, revoked = case.bridge({"operation": "submit-human-decision",
                    "command_id": "recovery-scope-revoked", "target_ref": scope,
                    "choice": "revoked", "expected_revision": case.kernel.load().revision, **fields})
                self.assertEqual(process.returncode, 0, revoked)
                revocation_ref = case.kernel.load().artifact_heads["visual/image-led/revocation"]
                gate_status = dict(case.kernel.load().gate_status)
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        response_ref, _ = self.assert_exact_response(task_id, original_claim, case.packs[0])
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(case.kernel.load().artifact_heads["visual/image-led/revocation"], revocation_ref)
        self.assertEqual(case.kernel.load().gate_status, gate_status)
        self.assert_candidate_rejected_without_writes(task_id, response_ref, case.packs[0])
        self.assertEqual(len(case.calls()), 1)

    def test_public_material_change_during_wait_preserves_response_but_rejects_candidate(self):
        case = self.case
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(case.action, "recovery-source-change")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, original_claim = self.stored_response(task_id)
                process, changed = case.bridge({"operation": "add-material",
                    "command_id": "recovery-new-source", "expected_revision": case.kernel.load().revision,
                    "material_type": "text", "value": "Synthetic changed source while provider waits",
                    "label": "Synthetic source update"})
                self.assertEqual(process.returncode, 0, changed)
                material_ref = case.kernel.load().artifact_heads["materials"]
                self.assertNotEqual(material_ref, case.policy["material_inventory_ref"])
                gate_status = dict(case.kernel.load().gate_status)
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        response_ref, _ = self.assert_exact_response(task_id, original_claim, case.packs[0])
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(case.kernel.load().artifact_heads["materials"], material_ref)
        self.assertEqual(case.kernel.load().gate_status, gate_status)
        self.assert_candidate_rejected_without_writes(task_id, response_ref, case.packs[0])
        self.assertEqual(len(case.calls()), 1)

    def test_different_requests_return_concurrently_without_losing_either_response(self):
        case = self.case
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(case.action, "recovery-page-one")
            pending = [first]
            try:
                first_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, first_claim = self.stored_response(first_id)
                second = pool.submit(case.action, "recovery-page-two", target_refs=[case.packs[1]])
                pending.append(second)
                calls = self.wait_for_calls(2)
                second_id = calls[1]["request"]["request_id"]
                self.assertNotEqual(first_id, second_id)
                _, second_claim = self.stored_response(second_id)
                active_ref = case.kernel.load().artifact_heads["agent/task/active"]
            finally:
                self.release_all()
            outcomes = [future.result(timeout=30) for future in pending]
        first_ref, first_response = self.assert_exact_response(first_id, first_claim, case.packs[0])
        second_ref, second_response = self.assert_exact_response(second_id, second_claim, case.packs[1])
        self.assertNotEqual(first_ref, second_ref)
        self.assertNotEqual(first_response["response_id"], second_response["response_id"])
        for process, reply in outcomes:
            self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(case.kernel.load().artifact_heads["agent/task/active"], active_ref)
        self.assertEqual(len(case.calls()), 2)
        before = tree_snapshot(case.project)
        self.assertEqual(case.service.preserve_generation_response(deepcopy(first_response)), first_ref)
        self.assertEqual(case.service.preserve_generation_response(deepcopy(second_response)), second_ref)
        self.assertEqual(tree_snapshot(case.project), before,
            "replaying one claim must not overwrite the other request or the active task")
        self.assertEqual(len(case.calls()), 2)

    def completed_response(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.case.action, "recovery-completed")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, claim = self.stored_response(task_id)
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        self.assertEqual(process.returncode, 0, reply)
        return task_id, self.assert_exact_response(task_id, claim, self.case.packs[0])

    def test_completed_claim_public_resume_and_local_replay_do_not_write_or_resend(self):
        case = self.case
        task_id, (response_ref, response) = self.completed_response()
        before = tree_snapshot(case.project)
        process, reply = case.bridge({"operation": "execute-image-led-generation",
            "expected_revision": case.kernel.load().revision, "task_id": task_id})
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(reply["result"]["generation_response_ref"], response_ref)
        self.assertEqual(reply["result"]["generation_response"], response)
        self.assertEqual(case.service.preserve_generation_response(deepcopy(response)), response_ref)
        self.assertEqual(case.service.preserve_generation_response(deepcopy(response)), response_ref)
        self.assertEqual(tree_snapshot(case.project), before)
        self.assertEqual(len(case.calls()), 1)

    def test_changed_claim_or_conflicting_terminal_response_cannot_overwrite_saved_response(self):
        case = self.case
        task_id, (response_ref, response) = self.completed_response()
        for changes in (
            {"project_id": "another-project"}, {"request_id": "another-request"},
            {"claim_id": "another-claim"}, {"pack_ref": case.packs[1]},
            {"payload_sha256": "0" * 64}, {"response_id": "different-provider-response"},
            {"status": "unknown", "error_category": "TimeoutError"},
            {"image_base64": base64.b64encode(b"different returned bytes").decode()},
        ):
            with self.subTest(changes=changes):
                before = tree_snapshot(case.project)
                with self.assertRaises(ContractValidationError):
                    case.service.preserve_generation_response({**deepcopy(response), **changes})
                self.assertEqual(tree_snapshot(case.project), before)
                self.assertEqual(self.stored_response(task_id), (response_ref, response))
        self.assertEqual(len(case.calls()), 1)

    def test_two_real_revision_conflicts_retry_only_local_preservation(self):
        case = self.case
        original_commit = case.kernel.commit
        attempts = []
        conflicts = []
        concurrent_decisions = []

        def commit_with_concurrent_decisions(**kwargs):
            if kwargs["event_type"] == "image-led.request-returned":
                attempts.append(kwargs["expected_revision"])
                if len(attempts) <= 2:
                    # This performs a real independent public/kernel transaction;
                    # the following original commit must detect its stale revision.
                    process, decision = case.bridge({"operation": "submit-human-decision",
                        "command_id": f"recovery-cas-decision-{len(attempts)}",
                        "expected_revision": case.kernel.load().revision,
                        "target_ref": case.kernel.load().artifact_heads["content/reading-blueprint"],
                        "choice": "记录说明", "feedback": f"Synthetic CAS race {len(attempts)}"})
                    self.assertEqual(process.returncode, 0, decision)
                    concurrent_decisions.append(case.kernel.load().artifact_heads["human/decision/latest"])
            try:
                return original_commit(**kwargs)
            except RevisionConflictError as error:
                conflicts.append(error)
                raise

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(case.action, "recovery-two-cas-conflicts")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, started = self.stored_response(task_id)
                response = self.synthetic_terminal_response(started)
                with patch.object(case.kernel, "commit", commit_with_concurrent_decisions):
                    reference = case.service.preserve_generation_response(response)
                self.assertEqual(len(attempts), 3, "two real conflicts must lead to a third local CAS")
                self.assertEqual(len(conflicts), 2)
                self.assertEqual(attempts, sorted(set(attempts)), "each retry must read the new revision")
                self.assertEqual(case.kernel.load().artifact_heads["human/decision/latest"], concurrent_decisions[-1])
                self.assertEqual(len(self.terminal_events()), 1)
                before_adapter_replay = tree_snapshot(case.project)
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(reply["result"]["generation_response_ref"], reference)
        self.assert_exact_response(task_id, started, case.packs[0])
        self.assertEqual(tree_snapshot(case.project), before_adapter_replay,
            "the original adapter return must replay the already preserved exact result")
        self.assertEqual(len(case.calls()), 1)

    def run_concurrent_preservation(self, *, conflicting):
        case = self.case
        barrier = Barrier(2)
        thread_state = local()
        original_commit = case.kernel.commit

        def commit_after_both_read_started(**kwargs):
            if kwargs["event_type"] == "image-led.request-returned" and not getattr(thread_state, "waited", False):
                thread_state.waited = True
                barrier.wait(timeout=10)
            return original_commit(**kwargs)

        def preserve(response):
            try:
                return "saved", case.service.preserve_generation_response(response)
            except ContractValidationError as error:
                return "rejected", error

        with ThreadPoolExecutor(max_workers=1) as adapter_pool:
            pending = adapter_pool.submit(case.action, "recovery-concurrent-preservation")
            try:
                task_id = self.wait_for_calls(1)[0]["request"]["request_id"]
                _, started = self.stored_response(task_id)
                first = self.synthetic_terminal_response(started)
                second = deepcopy(first)
                if conflicting:
                    second["response_id"] += "-conflicting-return"
                self.assertEqual(self.terminal_events(), [])
                with patch.object(case.kernel, "commit", commit_after_both_read_started):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(preserve, response) for response in (first, second)]
                        outcomes = [future.result(timeout=15) for future in futures]
                reference, saved = self.stored_response(task_id)
                successes = [value for status, value in outcomes if status == "saved"]
                rejections = [value for status, value in outcomes if status == "rejected"]
                self.assertEqual(len(successes), 1 if conflicting else 2)
                self.assertEqual(successes, [reference] * len(successes))
                self.assertEqual(len(rejections), 1 if conflicting else 0)
                self.assertIn(saved, [first, second])
                self.assertEqual(len(self.terminal_events()), 1,
                    "one started claim may publish only one terminal event")
                before_adapter_replay = tree_snapshot(case.project)
            finally:
                self.release_all()
            process, reply = pending.result(timeout=30)
        if saved == first:
            self.assertEqual(process.returncode, 0, reply)
            self.assertEqual(reply["result"]["generation_response_ref"], reference)
        else:
            self.assertNotEqual(process.returncode, 0, reply)
            self.assertIn("RESPONSE_CONFLICT", reply["error"]["message"])
        self.assertEqual(self.stored_response(task_id), (reference, saved))
        self.assertEqual(tree_snapshot(case.project), before_adapter_replay)
        self.assertEqual(len(self.terminal_events()), 1)
        self.assertEqual(len(case.calls()), 1)

    def test_same_started_claim_concurrent_exact_returns_publish_one_terminal_event(self):
        self.run_concurrent_preservation(conflicting=False)

    def test_same_started_claim_concurrent_conflicting_returns_preserve_only_one(self):
        self.run_concurrent_preservation(conflicting=True)


if __name__ == "__main__":
    unittest.main()
