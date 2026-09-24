"""The source-only route must be callable through the schema 3 bridge without old Gates."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ArtifactReferenceError
from tests.test_existing_deck_optimization import fixture
from tests.test_existing_deck_selection import RULES
from tests.test_existing_deck_selection import FakeTransport, image


class ExistingDeckBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kernel, self.raw, self.source = fixture(Path(self.tmp.name))

    def invoke(self, operation, **fields):
        return dispatch_v16({'operation': operation, 'project_root': str(self.kernel.project_root),
                             'expected_revision': self.kernel.load().revision, **fields})

    def source_title(self):
        from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
        return ExistingDeckOptimizationService(self.kernel).current_source()['slides'][0]['visible_copy'][0]['item_id']

    def test_source_scope_request_and_readback_do_not_pass_old_gate(self):
        source = self.invoke('optimization-begin', source_id=self.source['source_id'],
            source_pptx_sha256=hashlib.sha256(self.raw).hexdigest(),
            user_message_ref='chat://message/current-optimization-instruction')
        self.assertEqual(source['result']['source_ref'], self.kernel.load().artifact_heads['optimization/source'])
        scope = self.invoke('optimization-external-scope',
            user_message_ref='chat://message/current-crs-authorization',
            allowed_page_orders=[1, 2], excluded_image_sha256=[], excluded_text_item_ids=[])
        self.assertEqual(scope['result']['scope_ref'], self.kernel.load().artifact_heads['optimization/external-use-scope'])
        request = self.invoke('optimization-register-request', slide_id='S0001',
            request_id='once-only-S0001', common_rules=RULES,
            title_item_id=self.source_title())
        self.assertEqual(request['result']['request_ref'], self.kernel.load().artifact_heads['optimization/request/once-only-S0001'])
        readback = self.invoke('optimization-status')
        self.assertEqual(readback['optimization']['source']['page_count'], 2)
        self.assertEqual(readback['optimization']['requests'][0]['status'], 'not-sent')
        self.assertEqual(self.kernel.load().gate_status['G0'], 'open')

    def test_public_recovery_reads_started_claim_without_loading_transport_or_writing(self):
        self.invoke('optimization-begin', source_id=self.source['source_id'],
            source_pptx_sha256=hashlib.sha256(self.raw).hexdigest(),
            user_message_ref='chat://message/current-optimization-instruction')
        self.invoke('optimization-external-scope',
            user_message_ref='chat://message/current-crs-authorization',
            allowed_page_orders=[1, 2], excluded_image_sha256=[], excluded_text_item_ids=[])
        request_id = 'started-recovery'
        request_ref = self.invoke('optimization-register-request', slide_id='S0001',
            request_id=request_id, common_rules=RULES,
            title_item_id=self.source_title())['result']['request_ref']
        from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService
        service = ExistingDeckSelectionService(self.kernel)
        self.kernel.commit(command_id='started-claim', expected_revision=self.kernel.load().revision,
            event_type='optimization.image-request-started',
            artifact_updates={service.RESPONSE + request_id: ('optimization-image-response', {
                'project_id': self.kernel.project_id, 'request_id': request_id,
                'request_ref': request_ref, 'status': 'started'})})
        before = self.kernel.load()
        with patch('ai_ppt_studio.adapters.image2_command.Image2CommandAdapter.from_environment',
                   side_effect=AssertionError('read-only recovery must not load a provider adapter')) as adapter:
            recovered = dispatch_v16({'operation': 'optimization-recover-request',
                'project_root': str(self.kernel.project_root), 'request_id': request_id})['result']
        adapter.assert_not_called()
        self.assertEqual(recovered['request_id'], request_id)
        self.assertEqual(recovered['response_status'], 'started')
        self.assertEqual(recovered['response_ref'], before.artifact_heads[service.RESPONSE + request_id])
        self.assertEqual(self.kernel.load().revision, before.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_no_implicit_switch_or_failed_write(self):
        before = self.kernel.load()
        with self.assertRaises(ArtifactReferenceError):
            self.invoke('optimization-register-request', slide_id='S0001',
                request_id='unsanctioned', common_rules=RULES)
        self.assertEqual(self.kernel.load().revision, before.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_exact_current_response_can_be_previewed_without_a_project_write(self):
        self.invoke('optimization-begin', source_id=self.source['source_id'],
            source_pptx_sha256=hashlib.sha256(self.raw).hexdigest(),
            user_message_ref='chat://message/current-optimization-instruction')
        self.invoke('optimization-external-scope',
            user_message_ref='chat://message/current-crs-authorization',
            allowed_page_orders=[1, 2], excluded_image_sha256=[], excluded_text_item_ids=[])
        self.invoke('optimization-register-request', slide_id='S0001',
            request_id='preview-page', common_rules=RULES, title_item_id=self.source_title())
        with patch('ai_ppt_studio.adapters.image2_command.Image2CommandAdapter.from_environment',
                   return_value=FakeTransport(image('red'))):
            response = self.invoke('optimization-execute-request', request_id='preview-page')['result']
        self.assertEqual(response['response_status'], 'completed')
        self.assertEqual(response['image_sha256'], hashlib.sha256(image('red')).hexdigest())
        before = self.kernel.load()
        preview = self.invoke('optimization-preview-image', request_id='preview-page')['image']
        import base64
        self.assertEqual(base64.b64decode(preview['image_base64']), image('red'))
        self.assertEqual(preview['image_sha256'], hashlib.sha256(image('red')).hexdigest())
        self.assertEqual(preview['slide_id'], 'S0001')
        self.assertEqual(preview['preview_role'], 'provider-design')
        self.assertEqual(self.kernel.load().revision, before.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_public_source_review_atomically_completes_its_governed_task(self):
        self.invoke('optimization-begin', source_id=self.source['source_id'],
            source_pptx_sha256=hashlib.sha256(self.raw).hexdigest(),
            user_message_ref='chat://message/current-optimization-instruction')
        self.invoke('optimization-external-scope',
            user_message_ref='chat://message/current-crs-authorization',
            allowed_page_orders=[1, 2], excluded_image_sha256=[], excluded_text_item_ids=[])
        request_id = 'reviewed-page'
        request_ref = self.invoke('optimization-register-request', slide_id='S0001',
            request_id=request_id, common_rules=RULES,
            title_item_id=self.source_title())['result']['request_ref']
        with patch('ai_ppt_studio.adapters.image2_command.Image2CommandAdapter.from_environment',
                   return_value=FakeTransport(image('blue'))):
            response_ref = self.invoke(
                'optimization-execute-request', request_id=request_id)['result']['response_ref']
        _, task, _ = ProjectCommandService(self.kernel).request_agent_action(
            'source-review-task', self.kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[response_ref],
            instructions='Review the exact provider result')
        before_review_revision = self.kernel.load().revision
        review_ref = self.invoke('optimization-review-response', request_id=request_id,
            reviewer_task_id=task['task_id'], producer_task_id=request_id,
            checks={'visible-copy-transcription': 'passed',
                    'no-unsupported-facts': 'passed',
                    'material-roles': 'passed',
                    'excluded-content': 'passed'})['result']['review_ref']
        reviewer = ProjectCommandService(self.kernel).resolve_agent_task(task['task_id'])
        self.assertEqual(reviewer['status'], 'completed')
        self.assertEqual(reviewer['result_refs'], [review_ref])
        self.assertEqual(reviewer['target_refs'], [response_ref])
        self.assertEqual(self.kernel.load().revision, before_review_revision + 1)
        self.assertEqual(self.kernel.load().artifact_heads[
            'optimization/request/' + request_id], request_ref)
