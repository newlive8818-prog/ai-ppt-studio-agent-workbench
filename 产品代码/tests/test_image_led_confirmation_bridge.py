"""Synthetic bridge confirmations; no real user or host acceptance evidence."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContentWorkflowError, ContractValidationError, GateBlockedError
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_image2_input_boundary import tree_snapshot
from tests.v16_visual_fixtures import confirmed_g0


class ImageLedConfirmationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        content, revision, _ = confirmed_g0(self.root)
        self.kernel = content.kernel
        self.scope = VisualService(self.kernel).commit_public_artifact("scope", revision,
            kind="visual-contract", payload={
                "artifact_type": "image-led-authorization-scope", "project_id": "p1",
                "receiver": "test-provider", "model": "gpt-image-2", "allowed": [], "excluded": []})

    def dispatch(self, operation, **values):
        return dispatch_v16({"operation": operation, "project_root": str(self.root), **values})

    def test_read_context_is_resolved_current_and_zero_write(self):
        before = tree_snapshot(self.root)
        try:
            result = self.dispatch("get-image-led-confirmation-context", target_ref=self.scope, choice="approved")
        except ContractValidationError as error:
            self.fail(f"Read-only Image-led dispatch should be available: {error}")
        context = result["confirmation_context"]
        self.assertTrue(result["image_led"])
        self.assertEqual(context["scope_id"], self.scope)
        self.assertEqual(context["target_ref"], self.scope)
        self.assertEqual(context["choice"], "approved")
        self.assertIn("test-provider", context["review_summary"])
        self.assertEqual(tree_snapshot(self.root), before)

    def test_non_image_context_keeps_generic_decision(self):
        target = self.kernel.load().artifact_heads["content/reading-blueprint"]
        result = self.dispatch("get-image-led-confirmation-context", target_ref=target, choice="继续")
        self.assertFalse(result["image_led"])
        result = self.dispatch("submit-human-decision", target_ref=target, choice="继续",
                               expected_revision=self.kernel.load().revision)
        self.assertEqual(result["result"]["snapshot"]["revision"], self.kernel.load().revision)
        self.assertIn("human/decision/latest", self.kernel.load().artifact_heads)

    def test_signed_internal_fields_reach_scoped_confirmation_and_ledger(self):
        context = ImageLedService(self.kernel).confirmation_context(self.scope)
        identity = "test-host-confirmation://bridge-scope"
        try:
            result = self.dispatch("submit-human-decision", target_ref=self.scope, choice="approved",
                expected_revision=self.kernel.load().revision,
                **gate_confirmation_kwargs(context, identity_ref=identity))
        except ContractValidationError as error:
            self.fail(f"Signed Image-led confirmation must cross bridge: {error}")
        decision_ref = result["result"]["decision_ref"]
        self.assertEqual(self.kernel.confirmation_artifact_binding(identity), decision_ref)
        self.assertEqual(self.kernel.confirmation_owner(identity), "image-led-authorization:" + self.scope)

    def test_forged_and_opposite_choice_assertions_are_zero_write(self):
        context = ImageLedService(self.kernel).confirmation_context(self.scope)
        for choice, fields in [
            ("approved", {"host_confirmation_assertion": "forged"}),
            ("approved", {"user_message_ref": "chat://fabricated", "approved": True}),
            ("approved", {"image_led_confirmation": {"approved": True}}),
            ("revoked", gate_confirmation_kwargs(context)),
        ]:
            before = tree_snapshot(self.root)
            with self.assertRaises((ContentWorkflowError, ContractValidationError, GateBlockedError)):
                self.dispatch("submit-human-decision", target_ref=self.scope, choice=choice,
                    expected_revision=self.kernel.load().revision, **fields)
            self.assertEqual(tree_snapshot(self.root), before)


if __name__ == "__main__":
    unittest.main()
