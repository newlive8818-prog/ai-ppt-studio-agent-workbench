"""No old Gate, source-page count, or unassessed renderer output can publish a deck."""
import tempfile
import unittest
from pathlib import Path

from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.image_led_results import ExistingDeckResultService
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError, GateBlockedError
from tests.test_existing_deck_selection import ExistingDeckSelectionTests


class ExistingDeckDeliveryTests(ExistingDeckSelectionTests):
    def test_existing_deck_cannot_take_old_g4_delivery_shortcut(self):
        state = self.kernel.load()
        with self.assertRaisesRegex(GateBlockedError, 'existing-deck'):
            GateEvaluator(self.kernel).delivery_ready()
        with self.assertRaisesRegex(GateBlockedError, 'existing-deck'):
            DeliveryService(self.kernel).register_delivery_package('forged', state.revision, {})
        with self.assertRaisesRegex(GateBlockedError, 'existing-deck'):
            DeliveryService(self.kernel).record_public_chat_delivery('fake-chat', state.revision,
                delivery_type='pptx', artifact_refs=['artifact://final-pptx/'+'a'*64],
                message_ref='chat://message/fake', send_status='sent', retry_of='')
        self.assertEqual(self.kernel.load().artifact_heads, state.artifact_heads)
        self.assertEqual(self.kernel.load().gate_status, state.gate_status)

    def test_unassessed_native_output_cannot_register_as_qa_or_delivery(self):
        self.complete_selection()
        state = self.kernel.load()
        results = ExistingDeckResultService(self.kernel)
        with self.assertRaises((ArtifactReferenceError, ContractValidationError, GateBlockedError)):
            results.register_result('fake', state.revision, task_id='a'*64,
                plan_ref='artifact://visual-compilation-plan/'+'b'*64,
                output={'status': 'passed', 'pptx_sha256': 'c'*64})
        with self.assertRaises((ArtifactReferenceError, ContractValidationError, GateBlockedError)):
            results.register_qa('fake-qa', state.revision, result_ref='',
                reviewer_task_id='reviewer', pages=[], target_environment={})
        self.assertEqual(self.kernel.load().artifact_heads, state.artifact_heads)


if __name__ == '__main__':
    unittest.main()
