"""Synthetic host adapter through real public bridge and CLI subprocesses."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image_led_requests import input_fixture
from tests.test_image2_input_boundary import confirm_scope, tree_snapshot

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "image-led-image2-transport/v1"


class ImageLedExecutionEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        roots = [self.base / name for name in ("runtime", "source", "install", "upstream")]
        for root in roots:
            root.mkdir()
        self.config = RuntimeConfig.create(*roots)
        self.profile = roots[0] / "workspace.json"
        self.config.save(self.profile)
        self.project = roots[0] / "projects" / "p1"
        self.service, self.policy, self.packs = input_fixture(self.project)
        self.kernel = self.service.kernel
        stream = BytesIO()
        Image.new("RGB", (32, 18), "#203040").save(stream, format="PNG")
        self.raw_image = stream.getvalue()
        self.record = self.base / "adapter-calls.jsonl"
        self.script = self.base / "synthetic-adapter.py"
        self.script.write_text('''import base64, json, os, sys
from pathlib import Path
request = json.load(sys.stdin)
with Path(sys.argv[1]).open("a") as stream:
    stream.write(json.dumps({"request": request, "leaked_host_secret": "AI_PPT_HOST_CONFIRMATION_SECRET" in os.environ}) + "\\n")
if sys.argv[2] == "unknown":
    sys.stderr.write("synthetic provider uncertainty; must not be surfaced or retried")
    raise SystemExit(7)
json.dump({"protocol": request["protocol"], "receiver": request["payload"]["receiver"],
    "model": request["payload"]["model"], "request_id": request["request_id"],
    "response_id": "synthetic-response", "image_base64": sys.argv[3]}, sys.stdout)
''')
        self.env = {**os.environ, "AI_PPT_WORKSPACE_CONFIG": str(self.profile),
            "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1", "AI_PPT_HOST_CONFIRMATION_SECRET": "synthetic-secret-not-for-adapter",
            "AI_PPT_IMAGE2_RECEIVER": self.policy["receiver"], "AI_PPT_IMAGE2_MODEL": self.policy["model"]}
        self.configure_adapter()

    def configure_adapter(self, mode="completed"):
        self.env["AI_PPT_IMAGE2_ADAPTER_COMMAND"] = json.dumps([
            sys.executable, str(self.script), str(self.record), mode,
            base64.b64encode(self.raw_image).decode(),
        ])

    def bridge(self, request):
        process = subprocess.run([sys.executable, "-m", "ai_ppt_studio.workbench_bridge"],
            input=json.dumps({"project_root": str(self.project), **request}),
            text=True, capture_output=True, env=self.env, cwd=ROOT, timeout=30)
        return process, json.loads(process.stdout)

    def action(self, command="image-action", **changes):
        return self.bridge({"operation": "request-agent-action", "command_id": command,
            "expected_revision": self.kernel.load().revision, "action_type": "generate-slide-images",
            "target_refs": [self.packs[0]], "instructions": "Synthetic test only", **changes})

    def calls(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()] if self.record.exists() else []

    def test_public_action_executes_host_adapter_and_public_result_accepts_exact_response(self):
        process, reply = self.action()
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(len(self.calls()), 1, "public action only queued; no production adapter ran")
        generated = reply["result"]["generation_response"]
        self.assertEqual(generated["status"], "completed")
        self.assertEqual(base64.b64decode(generated["image_base64"]), self.raw_image)
        self.assertEqual(generated["image_sha256"], hashlib.sha256(self.raw_image).hexdigest())
        self.assertFalse(self.calls()[0]["leaked_host_secret"])
        sent = self.calls()[0]["request"]
        self.assertEqual(sent["protocol"], PROTOCOL)
        self.assertEqual(sent["payload"], self.service.compile_request(self.packs[0]))
        self.assertNotIn(str(self.project), json.dumps(sent))
        task = reply["result"]["task"]
        pack = self.kernel.artifacts.resolve(ArtifactReference.parse(self.packs[0]))["payload"]
        copy = pack["confirmed_visible_copy"]
        candidate = {"artifact_type": "image-led-candidate", "project_id": "p1",
            "request_id": task["task_id"], "generation_response_ref": reply["result"]["generation_response_ref"],
            "pack_ref": self.packs[0], "slide_id": pack["slide_id"], "page_order": pack["page_order"],
            "selected_copy": {"items": [{"item_id": "title", "kind": "text", "role": "title", "text": copy["title"]}]
                + [{"item_id": b["block_id"], "kind": "text", "role": "body", "text": b["text"]} for b in copy["blocks"]]},
            "material_roles": []}
        process, accepted = self.bridge({"operation": "commit-artifact", "command_id": "submit-candidate",
            "expected_revision": self.kernel.load().revision, "task_id": task["task_id"],
            "kind": "visual-contract", "payload": candidate})
        self.assertEqual(process.returncode, 0, accepted)
        self.assertEqual(self.kernel.load().artifact_heads["visual/image-led/candidate/" + pack["slide_id"]],
                         accepted["result"]["artifact_ref"])
        self.assertEqual(self.kernel.load().gate_status["G3"], "locked")
        self.assertEqual(len(self.calls()), 1)

    def test_missing_or_wrong_adapter_configuration_fails_before_queue(self):
        for changes in ({"AI_PPT_IMAGE2_ADAPTER_COMMAND": ""}, {"AI_PPT_IMAGE2_RECEIVER": "unapproved-provider"}):
            with self.subTest(changes=changes):
                original = dict(self.env); self.env.update(changes)
                before = tree_snapshot(self.project)
                process, reply = self.action()
                self.assertNotEqual(process.returncode, 0, "missing host adapter must not silently queue")
                self.assertIn("IMAGE_LED_", reply["error"]["message"])
                self.assertEqual(tree_snapshot(self.project), before)
                self.assertEqual(self.calls(), [])
                self.env = original

    def test_bridge_normalizes_image_action_before_adapter_preflight(self):
        self.env["AI_PPT_IMAGE2_ADAPTER_COMMAND"] = ""
        before = tree_snapshot(self.project)
        process, reply = self.action(action_type=" generate-slide-images ")
        self.assertNotEqual(process.returncode, 0, "action whitespace must not bypass the production adapter")
        self.assertIn("CAPABILITY_GAP", reply["error"]["message"])
        self.assertEqual(tree_snapshot(self.project), before)
        self.configure_adapter()
        process, reply = self.action(action_type=" generate-slide-images ")
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(reply["result"]["generation_response"]["status"], "completed")
        self.assertEqual(len(self.calls()), 1)

    def test_revoked_scope_and_public_adapter_injection_never_execute_or_write(self):
        confirm_scope(self.kernel, self.policy["authorization_scope_ref"], "revoked", "entry-revoke")
        before = tree_snapshot(self.project)
        process, _ = self.action(adapter_command=["unsafe"], receiver="unapproved-provider")
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(tree_snapshot(self.project), before)
        self.assertEqual(self.calls(), [])

    def test_unknown_public_action_response_does_not_retry_child_process(self):
        self.configure_adapter("unknown")
        process, reply = self.action("unknown-entry")
        self.assertEqual(process.returncode, 0, reply)
        self.assertEqual(len(self.calls()), 1, "public action must invoke the configured adapter")
        self.assertEqual(reply["result"]["generation_response"]["status"], "unknown")
        before = tree_snapshot(self.project)
        process, rejected = self.bridge({"operation": "execute-image-led-generation",
            "expected_revision": self.kernel.load().revision, "task_id": reply["result"]["task"]["task_id"]})
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("REQUEST_UNKNOWN", rejected["error"]["message"])
        self.assertEqual(tree_snapshot(self.project), before)
        self.assertEqual(len(self.calls()), 1)

    def test_cli_resumes_existing_queued_task_via_same_adapter_and_claim(self):
        _, task, _ = ProjectCommandService(self.kernel).request_agent_action("queued-cli", self.kernel.load().revision,
            action_type="generate-slide-images", target_refs=[self.packs[0]], instructions="Synthetic queued task")
        process = subprocess.run([sys.executable, "-m", "ai_ppt_studio", "--workspace-config", str(self.profile),
            "execute-image-led-generation", "--project", str(self.project), "--task-id", task["task_id"],
            "--expected-revision", str(self.kernel.load().revision)],
            text=True, capture_output=True, env=self.env, cwd=ROOT, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        reply = json.loads(process.stdout)
        self.assertEqual(reply["result"]["generation_response"]["status"], "completed")
        self.assertEqual(len(self.calls()), 1)

    def test_concurrent_bridge_resumes_send_the_queued_request_once(self):
        _, task, _ = ProjectCommandService(self.kernel).request_agent_action("queued-concurrent", self.kernel.load().revision,
            action_type="generate-slide-images", target_refs=[self.packs[0]], instructions="Synthetic queued task")
        request = {"operation": "execute-image-led-generation", "task_id": task["task_id"],
            "expected_revision": self.kernel.load().revision}
        start = Barrier(2)

        def resume():
            start.wait(timeout=10)
            return self.bridge(request)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(resume) for _ in range(2)]
            outcomes = [future.result(timeout=30) for future in futures]
        self.assertTrue(any(process.returncode == 0 for process, _ in outcomes), outcomes)
        self.assertEqual(len(self.calls()), 1, "concurrent public bridge processes must share one durable claim")
        for process, reply in outcomes:
            if process.returncode == 0:
                self.assertEqual(reply["result"]["generation_response"]["status"], "completed")
            else:
                self.assertTrue(reply["error"]["code"] == "REVISION_CONFLICT"
                    or "REQUEST_UNKNOWN" in reply["error"]["message"]
                    or "REQUEST_DUPLICATE" in reply["error"]["message"], reply)


if __name__ == "__main__":
    unittest.main()
