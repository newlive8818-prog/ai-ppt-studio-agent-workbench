import tempfile
import unittest
from pathlib import Path
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from tests.test_image_led_runtime import g1_fixture

class UnstartedNativeTaskCancellationTests(unittest.TestCase):
    def test_cancel_keeps_visuals_and_gates_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            service = ProjectCommandService(kernel)
            _, task, state = service.request_agent_action("queued-native", kernel.load().revision,
                action_type="build-native-first",
                target_refs=[kernel.load().artifact_heads["visual/compilation-plan"]], instructions="")
            old = dict(state.artifact_heads)
            with self.assertRaises(RevisionConflictError):
                service.cancel_unstarted_native_task("cancel-native", state.revision - 1,
                    task_id=task["task_id"], reason="wrong entry")
            after = service.cancel_unstarted_native_task("cancel-native", state.revision,
                task_id=task["task_id"], reason="wrong entry")
            self.assertEqual(after.gate_status, state.gate_status)
            self.assertNotIn("agent/task/active", after.artifact_heads)
            for slot, ref in old.items():
                if slot not in {"agent/task/active", "agent/task/" + task["task_id"]}:
                    self.assertEqual(after.artifact_heads[slot], ref)
            self.assertEqual(service.resolve_agent_task(task["task_id"])["status"], "cancelled")
            self.assertEqual(service.cancel_unstarted_native_task("cancel-native", state.revision,
                task_id=task["task_id"], reason="wrong entry"), after)
    def test_rejects_a_build_with_output_already_present(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            service = ProjectCommandService(kernel)
            _, task, state = service.request_agent_action("queued-native", kernel.load().revision,
                action_type="build-native-first",
                target_refs=[kernel.load().artifact_heads["visual/compilation-plan"]], instructions="")
            (kernel.project_root / task["task_id"]).mkdir()
            with self.assertRaises(ContractValidationError):
                service.cancel_unstarted_native_task("cancel-native", state.revision,
                    task_id=task["task_id"], reason="already started")
            self.assertEqual(kernel.load(), state)
