"""Synthetic private transactions for exact Image 2 repair; no real visual proof."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ppt_studio.application.image_led_service import ImageLedService, PREFIX
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.materials.image_input_contracts import digest
from ai_ppt_studio.domains.materials.image_input_v2 import visible_copy
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image2_input_boundary import tree_snapshot
from tests.test_image_led_selection import SyntheticTransport, review_candidate
from tests.test_image_led_v2_runtime import v2_input_fixture, exact_crs_environment, OfflineKnownCrsBoundary
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


class RecordingTransport(SyntheticTransport):
    def __init__(self, *, unknown=False, size=None):
        self.payloads = []
        self.unknown = unknown
        self.size = size

    def generate(self, *, request_id, payload):
        self.payloads.append(deepcopy(payload))
        if self.unknown:
            raise TimeoutError('synthetic uncertain response')
        if self.size:
            data = BytesIO()
            Image.new('RGB', self.size).save(data, format='PNG')
            return {'response_id': 'synthetic-' + request_id, 'image_bytes': data.getvalue()}
        return super().generate(request_id=request_id, payload=payload)


class ImageLedRepairRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='c2-repair-runtime-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service, self.policy, self.packs = v2_input_fixture(self.root, include_material=True)
        self.kernel = self.service.kernel
        self.commands = ProjectCommandService(self.kernel)
        self.source_task, self.source_ref = self.generate(self.packs[0], 'source')
        self.source = self.resolve(self.source_ref)
        self.base = self.service.compile_request(self.packs[0])

    def resolve(self, ref):
        return self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']

    def generate(self, target, name, transport=None):
        _, task, _ = self.commands.request_agent_action('queue-' + name, self.kernel.load().revision,
            action_type='generate-slide-images', target_refs=[target],
            instructions='LOCAL-ONLY-DO-NOT-SEND', generation_request_id=name)
        response_ref = self.service.execute_generation(task['task_id'], transport=transport or SyntheticTransport())
        return task, response_ref

    def diagnostic_payload(self, source_ref=None):
        source_ref = source_ref or self.source_ref
        source = self.resolve(source_ref)
        pack = self.resolve(source['pack_ref'])
        return {'artifact_type': 'image-led-content-diagnostic',
            'diagnostic_version': 'image-led-content-diagnostic/v1',
            'project_id': self.kernel.project_id, 'pack_ref': source['pack_ref'],
            'generation_response_ref': source_ref, 'slide_id': pack['slide_id'], 'page_order': pack['page_order'],
            'image_sha256': source['image_sha256'], 'image_size': source['image_size'],
            'reviewer_kind': 'engineering', 'reviewer_role': 'visual-engineering-reviewer',
            'excluded_content_check': {'result': 'passed', 'detail': 'Synthetic source exclusion check only'},
            'issues': [{'kind': 'missing-item', 'item_id': 'b1'},
                {'kind': 'remove-extra-text', 'bbox': [30, 100, 80, 30], 'observed_text': 'LOCAL-OBSERVATION'},
                {'kind': 'common-rule', 'rule_key': 'title_bar', 'bbox': [0, 0, 1280, 100]}]}

    def review_task(self, source_ref=None, name='review'):
        _, task, _ = self.commands.request_agent_action('queue-' + name, self.kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[source_ref or self.source_ref],
            instructions='LOCAL-REVIEW-INSTRUCTIONS')
        return task

    def commit_diagnostic(self, task, value, name='diagnostic'):
        return self.commands.commit_noncontent_agent_result(command_id=name,
            expected_revision=self.kernel.load().revision, task_id=task['task_id'],
            request_kind='visual-contract', raw_request_payload=value)[0]

    def diagnostic(self, *, source_ref=None, result='passed', name='diagnostic'):
        task = self.review_task(source_ref, name=name)
        value = self.diagnostic_payload(source_ref)
        value['excluded_content_check']['result'] = result
        try:
            ref = self.commit_diagnostic(task, value, name)
        except ContractValidationError as error:
            self.fail(f'Governed independent content diagnosis must be registrable: {error}')
        return ref, task

    def candidate(self, task, response_ref, name='candidate'):
        response = self.resolve(response_ref)
        pack = self.resolve(response['pack_ref'])
        return self.commands.commit_noncontent_agent_result(command_id=name,
            expected_revision=self.kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract',
            raw_request_payload={'artifact_type': 'image-led-candidate', 'project_id': self.kernel.project_id,
                'request_id': task['task_id'], 'generation_response_ref': response_ref,
                'pack_ref': response['pack_ref'], 'slide_id': pack['slide_id'], 'page_order': pack['page_order'],
                'selected_copy': visible_copy(pack), 'material_roles': []})[0]

    def assert_rejected_unchanged(self, operation):
        before = tree_snapshot(self.root)
        with self.assertRaises((ContractValidationError, ArtifactReferenceError)):
            operation()
        self.assertEqual(tree_snapshot(self.root), before)

    def test_independent_diagnosis_binds_source_and_preserves_materials_without_candidate(self):
        ref, reviewer = self.diagnostic()
        value = self.resolve(ref)
        self.assertEqual(value['producer_task_id'], 'source')
        self.assertEqual(value['reviewer_task_id'], reviewer['task_id'])
        self.assertEqual(value['context_pack_ref'], reviewer['context_pack_ref'])
        self.assertEqual(value['source_payload_sha256'], digest(self.base))
        self.assertEqual(value['authorization_binding']['authorization_ref'], self.policy['authorization_ref'])
        self.assertFalse(any(k.startswith(PREFIX + 'candidate/') for k in self.kernel.load().artifact_heads))
        payload = self.service.compile_request(ref)
        self.assertEqual(payload['base_payload'], self.base)
        self.assertEqual(payload['edit_target']['data_base64'], self.source['image_base64'])
        self.assertEqual(payload['edit_target']['image_sha256'], self.source['image_sha256'])
        self.assertEqual(payload['issues'][1], {'kind': 'remove-extra-text', 'bbox': [30, 100, 80, 30]})
        self.assertNotIn('LOCAL-OBSERVATION', json.dumps(payload))
        self.assertEqual(payload['base_payload']['materials'], self.base['materials'])

    def test_review_context_is_narrow_and_binds_the_original_image(self):
        task = self.review_task()
        layers = self.resolve(task['context_pack_ref'])['layers']
        self.assertEqual(set(layers), {'role_contract', 'task_contract', 'image_led_diagnostic', 'output_contract'})
        self.assertEqual(layers['image_led_diagnostic']['generation_response_ref'], self.source_ref)
        self.assertEqual(layers['image_led_diagnostic']['image_base64'], self.source['image_base64'])
        self.assertNotIn('LOCAL-REVIEW-INSTRUCTIONS', json.dumps(layers))

    def test_exclusion_failed_or_not_established_is_retained_but_cannot_queue_repair(self):
        for outcome in ('failed', 'not-established'):
            with self.subTest(outcome=outcome):
                ref, _ = self.diagnostic(result=outcome, name=outcome)
                self.assertEqual(self.resolve(ref)['excluded_content_check']['result'], outcome)
                self.assert_rejected_unchanged(lambda: self.generate(ref, 'blocked-' + outcome))

    def test_old_completed_source_is_explicitly_usable_and_superseded_diagnostic_is_not(self):
        first, _ = self.diagnostic(name='first-review')
        self.generate(self.packs[0], 'newer-source')
        self.assertEqual(self.service.compile_request(first)['edit_target']['image_sha256'], self.source['image_sha256'])
        second, _ = self.diagnostic(name='second-review')
        self.assertNotEqual(first, second)
        self.assert_rejected_unchanged(lambda: self.service.compile_request(first))
        self.assertEqual(self.service.compile_request(second)['edit_target']['image_sha256'], self.source['image_sha256'])

    def test_repair_response_and_candidate_keep_lineage_and_need_new_source_review(self):
        diagnostic, _ = self.diagnostic()
        transport = RecordingTransport()
        task, response_ref = self.generate(diagnostic, 'repair-one', transport)
        response = self.resolve(response_ref)
        self.assertEqual(response['status'], 'completed')
        self.assertEqual(response['repair_diagnostic_ref'], diagnostic)
        self.assertEqual(response['source_generation_response_ref'], self.source_ref)
        self.assertEqual(response['pack_ref'], self.packs[0])
        self.assertEqual(response['payload_sha256'], digest(transport.payloads[0]))
        self.assertEqual(len(transport.payloads), 1)
        self.assertNotIn('LOCAL-ONLY-DO-NOT-SEND', json.dumps(transport.payloads[0]))
        ref = self.candidate(task, response_ref)
        candidate = self.resolve(ref)
        self.assertEqual(candidate['generation_response_ref'], response_ref)
        self.assertEqual(candidate['selected_copy'], visible_copy(self.resolve(self.packs[0])))
        self.assertEqual(candidate['material_roles'], [])
        self.assertNotIn(PREFIX + 'source-review/' + ArtifactReference.parse(ref).sha256,
                         self.kernel.load().artifact_heads)
        review_ref = review_candidate(self.service, ref, 'new-repair-review')
        self.assertEqual(self.resolve(review_ref)['target_ref'], ref)
        self.assertNotIn(PREFIX + 'selection', self.kernel.load().artifact_heads)

    def test_repair_output_can_itself_be_diagnosed_and_repaired(self):
        diagnostic, _ = self.diagnostic()
        _, response_ref = self.generate(diagnostic, 'repair-one')
        # Superseding the old diagnosis must not erase the completed lineage.
        self.diagnostic(name='revised-old-diagnosis')
        next_diagnostic, _ = self.diagnostic(source_ref=response_ref, name='next-review')
        payload = self.service.compile_request(next_diagnostic)
        self.assertEqual(payload['base_payload'], self.base)
        self.assertEqual(payload['edit_target']['data_base64'], self.resolve(response_ref)['image_base64'])
        _, next_response_ref = self.generate(next_diagnostic, 'repair-two')
        self.assertEqual(self.resolve(next_response_ref)['status'], 'completed')

    def test_small_repair_is_preserved_but_cannot_bypass_candidate_fitness(self):
        diagnostic, _ = self.diagnostic()
        task, ref = self.generate(diagnostic, 'small-repair', RecordingTransport(size=(32, 18)))
        self.assertEqual(self.resolve(ref)['status'], 'completed')
        self.assertEqual(self.resolve(ref)['output_fitness']['status'], 'needs-revision')
        self.assert_rejected_unchanged(lambda: self.candidate(task, ref))

    def test_unknown_repair_is_recoverable_without_resend_or_rebinding(self):
        diagnostic, _ = self.diagnostic()
        transport = RecordingTransport(unknown=True)
        task, ref = self.generate(diagnostic, 'unknown-repair', transport)
        self.assertEqual(self.resolve(ref)['status'], 'unknown')
        before = tree_snapshot(self.root)
        reply = dispatch_v16({'operation': 'request-agent-action', 'project_root': str(self.root),
            'command_id': 'recover-repair', 'expected_revision': self.kernel.load().revision,
            'action_type': 'generate-slide-images', 'target_refs': [], 'instructions': '',
            'generation_intent': 'recover', 'generation_request_id': task['task_id']})['result']
        self.assertEqual(reply['generation_response_ref'], ref)
        self.assertEqual(tree_snapshot(self.root), before)
        self.assertEqual(len(transport.payloads), 1)
        self.assertNotIn('已收到', reply['follow_up_message'])
        self.assert_rejected_unchanged(lambda: self.service.execute_generation(task['task_id'], transport=transport))
        self.assert_rejected_unchanged(lambda: self.service.generation_intent(target_refs=[self.packs[0]],
            instructions='', intent='new', request_id=task['task_id']))

    def test_revocation_prevents_new_repair_but_preserves_read_only_history(self):
        diagnostic, _ = self.diagnostic()
        task, ref = self.generate(diagnostic, 'repair-before-revoke')
        scope_ref = self.policy['authorization_scope_ref']
        context = self.service.confirmation_context(scope_ref, choice='revoked')
        self.service.confirm('revoke-repair-scope', self.kernel.load().revision, target_ref=scope_ref,
            choice='revoked', **gate_confirmation_kwargs(context, identity_ref='test-host-confirmation://repair-revocation'))
        self.assert_rejected_unchanged(lambda: self.service.compile_request(diagnostic))
        before = tree_snapshot(self.root)
        recovered_ref, response, usability = self.service.generation_receipt(task)
        self.assertEqual(recovered_ref, ref)
        self.assertEqual(response['status'], 'completed')
        self.assertFalse(usability['candidate_eligible'])
        self.assertEqual(tree_snapshot(self.root), before)

    def test_invalid_diagnostic_identity_and_free_fields_fail_without_writes(self):
        task = self.review_task()
        value = self.diagnostic_payload()
        changes = [{'project_id': 'other-project'}, {'pack_ref': self.packs[1]},
            {'slide_id': 'other-page'}, {'page_order': 2}, {'image_sha256': 'f' * 64},
            {'image_size': [1279, 720]}, {'replacement_text': 'new customer fact'},
            {'image_path': '/tmp/arbitrary.png'}, {'producer_task_id': task['task_id']},
            {'issues': [{'kind': 'missing-item', 'item_id': 'not-in-original-copy'}]}]
        for i, changed in enumerate(changes):
            with self.subTest(changed=changed):
                self.assert_rejected_unchanged(lambda: self.commit_diagnostic(task, {**value, **changed}, 'bad-' + str(i)))

    def test_direct_or_generator_diagnostic_cannot_claim_independent_review(self):
        value = self.diagnostic_payload()
        self.assert_rejected_unchanged(lambda: self.service.commit_artifact('direct-diagnostic', self.kernel.load().revision, value))
        self.assert_rejected_unchanged(lambda: self.commit_diagnostic(self.source_task, value, 'self-diagnostic'))

    def test_unknown_source_cannot_even_queue_diagnostic(self):
        _, ref = self.generate(self.packs[0], 'unknown-source', RecordingTransport(unknown=True))
        self.assert_rejected_unchanged(lambda: self.review_task(ref, 'unknown-review'))

    def test_unsupported_wrapper_stops_repair_before_any_queue(self):
        diagnostic, _ = self.diagnostic()
        request = {'operation': 'request-agent-action', 'project_root': str(self.root),
            'command_id': 'unsupported-repair', 'expected_revision': self.kernel.load().revision,
            'action_type': 'generate-slide-images', 'target_refs': [diagnostic], 'instructions': '',
            'generation_intent': 'new', 'generation_request_id': 'unsupported-repair'}
        with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), patch(
            'ai_ppt_studio.adapters.image2_command.image2_preflight', return_value={'protocol_probe': 'failed'}):
            self.assert_rejected_unchanged(lambda: dispatch_v16(request))

    def test_explicit_repair_identity_required_but_completed_old_source_remains_usable(self):
        self.candidate(self.source_task, self.source_ref, 'original-candidate')
        self.generate(self.packs[0], 'newer-original')
        diagnostic, _ = self.diagnostic()
        self.assertEqual(self.service.compile_request(diagnostic)['edit_target']['data_base64'], self.source['image_base64'])
        self.assert_rejected_unchanged(lambda: self.service.generation_intent(
            target_refs=[diagnostic], instructions='arbitrary default'))
        self.assert_rejected_unchanged(lambda: self.commands.request_agent_action('implicit-repair', self.kernel.load().revision,
            action_type='generate-slide-images', target_refs=[diagnostic], instructions=''))

    def test_repair_queued_before_diagnostic_replacement_cannot_execute(self):
        diagnostic, _ = self.diagnostic()
        _, task, _ = self.commands.request_agent_action('queued-repair', self.kernel.load().revision,
            action_type='generate-slide-images', target_refs=[diagnostic], instructions='',
            generation_request_id='queued-repair')
        self.diagnostic(name='replacement-review')
        # Restore only the queued task's active pointer to distinguish stale
        # diagnosis from the separate active-task rejection.
        self.kernel.commit(command_id='synthetic-restore-queued-task', expected_revision=self.kernel.load().revision,
            event_type='synthetic.task-pointer', artifact_updates={'agent/task/active': ('agent-task', task)})
        transport = RecordingTransport()
        self.assert_rejected_unchanged(lambda: self.service.execute_generation(task['task_id'], transport=transport))
        self.assertEqual(transport.payloads, [])

    def test_isolated_response_and_invalid_actual_image_cannot_be_diagnostic_sources(self):
        from ai_ppt_studio.application.image_led_repair import ImageLedRepairService
        repair = ImageLedRepairService(self.kernel)
        for i, change in enumerate(({'image_size': [1279, 720]}, {'image_sha256': 'f' * 64},
                                   {'image_base64': self.source['image_base64'][:-20]})):
            with self.subTest(change=list(change)):
                forged = {**self.source, **change}
                state = self.kernel.commit(command_id='synthetic-bad-image-' + str(i),
                    expected_revision=self.kernel.load().revision, event_type='synthetic.invalid-image',
                    artifact_updates={'project/image-led/request/source': ('image-led-generation-response', forged)})
                bad_ref = state.artifact_heads['project/image-led/request/source']
                self.assert_rejected_unchanged(lambda: repair.source_info(bad_ref))
        self.assert_rejected_unchanged(lambda: repair.source_info(self.source_ref))

    def test_source_context_hash_and_original_authority_are_rechecked(self):
        diagnostic, _ = self.diagnostic()
        context = self.resolve(self.source_task['context_pack_ref'])
        context['layers']['image_led_request']['payload']['page_goal'] = 'UNAUTHORIZED-NEW-GOAL'
        self.kernel.commit(command_id='synthetic-corrupt-source-context', expected_revision=self.kernel.load().revision,
            event_type='synthetic.corrupt-context', artifact_updates={
                'agent/context/source': ('context-pack', context)})
        self.assert_rejected_unchanged(lambda: self.service.compile_request(diagnostic))

    def test_bridge_adapter_wrapper_repair_preserves_full_input_and_returns_new_receipt(self):
        diagnostic, _ = self.diagnostic()
        with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), OfflineKnownCrsBoundary(
                model='gpt-image-2') as boundary:
            reply = dispatch_v16({'operation': 'request-agent-action', 'project_root': str(self.root),
                'command_id': 'bridge-repair', 'expected_revision': self.kernel.load().revision,
                'action_type': 'generate-slide-images', 'target_refs': [diagnostic],
                'instructions': 'LOCAL-ONLY-DO-NOT-SEND',
                'generation_intent': 'new', 'generation_request_id': 'bridge-repair'})['result']
        self.assertEqual(reply['generation_response']['status'], 'completed')
        self.assertEqual(reply['generation_response']['repair_diagnostic_ref'], diagnostic)
        self.assertEqual(reply['generation_response']['source_generation_response_ref'], self.source_ref)
        self.assertTrue(reply['generation_usability']['candidate_eligible'])
        self.assertEqual(len(boundary.generations), 1)
        self.assertEqual(len(boundary.http_calls), 1)
        sent = boundary.generations[0]
        self.assertEqual(sent['protocol'], 'image-led-image2-repair-transport/v1')
        self.assertEqual(sent['payload']['base_payload'], self.base)
        self.assertEqual(sent['payload']['edit_target']['data_base64'], self.source['image_base64'])
        wire = boundary.http_calls[0][0].data
        self.assertIn(b'"repair_context"', wire)
        self.assertNotIn(b'LOCAL-ONLY-DO-NOT-SEND', wire)
        self.assertNotIn(b'LOCAL-OBSERVATION', wire)
        self.assertNotIn(b'Synthetic source exclusion check only', wire)
        self.assertEqual(reply['generation_response']['image_size'], [2048, 1152])


if __name__ == '__main__':
    unittest.main()
