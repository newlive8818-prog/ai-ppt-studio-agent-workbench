"""Independent frozen-source repair review; temporary synthetic Runtime only."""
from pathlib import Path
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
import base64, hashlib, json, os, subprocess, sys, unittest, urllib.request

from PIL import Image
from ai_ppt_studio.application.image_led_repair import ImageLedRepairService
from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.image_led_service import PREFIX
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.materials.image_input_contracts import digest
from ai_ppt_studio.domains.visual.image_repair import validate_repair_payload, build_repair_payload
from ai_ppt_studio.adapters import image2_command, image2_crs
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.errors import ContractValidationError, ArtifactReferenceError
from tests import test_image_led_repair_runtime as fx
from tests.test_image2_input_boundary import tree_snapshot
from tests.test_image_led_selection import review_candidate
from tests.test_image_led_v2_runtime import exact_crs_environment
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_image2_repair_transport import decoded_body
from tests.test_image_led_repair_contracts import repair_payload

OUT = Path('/private/tmp/c2-repair-feedback')
FROZEN = OUT / 'frozen-source'

def png(color, size=(1280, 720)):
    out = BytesIO(); Image.new('RGB', size, color).save(out, format='PNG'); return out.getvalue()

class DistinctTransport:
    def __init__(self, color, size=(1280, 720)):
        self.raw = png(color, size); self.payloads = []
    def generate(self, *, request_id, payload):
        self.payloads.append(deepcopy(payload))
        return {'response_id': 'independent-' + request_id, 'image_bytes': self.raw}

class IndependentRepairReview(unittest.TestCase):
    setUp = fx.ImageLedRepairRuntimeTests.setUp
    resolve = fx.ImageLedRepairRuntimeTests.resolve
    generate = fx.ImageLedRepairRuntimeTests.generate
    diagnostic_payload = fx.ImageLedRepairRuntimeTests.diagnostic_payload
    review_task = fx.ImageLedRepairRuntimeTests.review_task
    commit_diagnostic = fx.ImageLedRepairRuntimeTests.commit_diagnostic
    diagnostic = fx.ImageLedRepairRuntimeTests.diagnostic
    candidate = fx.ImageLedRepairRuntimeTests.candidate
    assert_rejected_unchanged = fx.ImageLedRepairRuntimeTests.assert_rejected_unchanged

    def action(self, diagnostic, identity):
        return {'operation': 'request-agent-action', 'project_root': str(self.root),
            'command_id': identity, 'expected_revision': self.kernel.load().revision,
            'action_type': 'generate-slide-images', 'target_refs': [diagnostic],
            'instructions': 'INDEPENDENT-PRIVATE-INSTRUCTIONS',
            'generation_intent': 'new', 'generation_request_id': identity}

    def revoke(self):
        scope = self.policy['authorization_scope_ref']
        context = self.service.confirmation_context(scope, choice='revoked')
        self.service.confirm('independent-revoke', self.kernel.load().revision, target_ref=scope,
            choice='revoked', **gate_confirmation_kwargs(context,
                identity_ref='test-host-confirmation://independent-repair-revoke'))

    def update(self, name, updates):
        return self.kernel.commit(command_id='independent-' + name,
            expected_revision=self.kernel.load().revision, event_type='synthetic.independent-audit',
            artifact_updates=updates)

    def test_frozen_package_hashes_and_loaded_modules(self):
        raw = (OUT / 'source-manifest.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '7dd2e700730465d0af0344228d159fa6c305cb84f1615624c79495cfc4bb3af3')
        for relative, expected in json.loads(raw)['files'].items():
            self.assertEqual(hashlib.sha256((FROZEN / relative).read_bytes()).hexdigest(), expected, relative)
        for module in (image2_command, image2_crs, fx):
            self.assertTrue(Path(module.__file__).is_relative_to(FROZEN), module.__file__)

    def test_distinct_old_completed_source_never_becomes_newest_source(self):
        self.candidate(self.source_task, self.source_ref, 'old-completed-candidate')
        newer = DistinctTransport('#b02090')
        _, newer_ref = self.generate(self.packs[0], 'newer-distinct', newer)
        self.assertNotEqual(self.resolve(newer_ref)['image_sha256'], self.source['image_sha256'])
        diagnostic, _ = self.diagnostic(name='old-source-review')
        payload = self.service.compile_request(diagnostic)
        self.assertEqual(payload['edit_target']['data_base64'], self.source['image_base64'])
        self.assertNotEqual(payload['edit_target']['data_base64'], self.resolve(newer_ref)['image_base64'])

    def test_three_distinct_generations_use_immediate_parent_and_flat_original_base(self):
        d0, _ = self.diagnostic(name='original-review')
        t1 = DistinctTransport('#ed8030')
        task1, r1 = self.generate(d0, 'round-one', t1)
        self.assertNotEqual(self.source['image_sha256'], self.resolve(r1)['image_sha256'])
        self.candidate(task1, r1, 'round-one-candidate')
        # This invalidates only future edits using old-source diagnosis d0.
        d0new, _ = self.diagnostic(result='failed', name='ancestor-now-failed')
        self.assert_rejected_unchanged(lambda: self.service.compile_request(d0))
        self.assert_rejected_unchanged(lambda: self.service.compile_request(d0new))
        d1, _ = self.diagnostic(source_ref=r1, name='round-one-own-review')
        p2 = self.service.compile_request(d1)
        self.assertEqual(p2['base_payload'], self.base)
        self.assertNotIn('base_payload', p2['base_payload'])
        self.assertEqual(p2['edit_target']['data_base64'], base64.b64encode(t1.raw).decode())
        self.assertEqual(self.resolve(d1)['source_payload_sha256'], digest(t1.payloads[0]))
        self.assertNotEqual(self.resolve(d1)['source_payload_sha256'], digest(self.base))
        t2 = DistinctTransport('#208090')
        _, r2 = self.generate(d1, 'round-two', t2)
        d2, _ = self.diagnostic(source_ref=r2, name='round-two-own-review')
        p3 = self.service.compile_request(d2)
        self.assertEqual(p3['edit_target']['data_base64'], base64.b64encode(t2.raw).decode())
        self.assertEqual(p3['base_payload']['materials'], self.base['materials'])
        _, mime, wire = image2_crs.compile_body({'protocol': 'image-led-image2-repair-transport/v1',
            'request_id': 'wire-only-round-three', 'payload': p3})
        _, images = decoded_body(mime, wire)
        self.assertEqual(images[0].get_payload(decode=True), t2.raw)
        self.assertEqual(len(images), 1 + sum(m['type'] == 'image' for m in self.base['materials']))

    def test_failed_and_unestablished_exclusion_stop_public_action_before_preflight_or_writes(self):
        for status in ('failed', 'not-established'):
            d, _ = self.diagnostic(result=status, name='exclude-' + status)
            with patch.object(image2_command.Image2CommandAdapter, 'from_environment') as config:
                self.assert_rejected_unchanged(lambda: dispatch_v16(self.action(d, 'blocked-' + status)))
                config.assert_not_called()

    def test_revocation_after_queue_blocks_transport_without_a_started_claim(self):
        d, _ = self.diagnostic()
        _, task, _ = self.commands.request_agent_action('queue-before-revoke', self.kernel.load().revision,
            action_type='generate-slide-images', target_refs=[d], instructions='', generation_request_id='queued-revoke')
        self.revoke()
        transport = DistinctTransport('#003388')
        self.assert_rejected_unchanged(lambda: self.service.execute_generation(task['task_id'], transport=transport))
        self.assertEqual(transport.payloads, [])
        self.assertNotIn('project/image-led/request/' + task['task_id'], self.kernel.load().artifact_heads)

    def test_unknown_recover_after_new_diagnosis_and_revocation_is_read_only_without_environment(self):
        d, _ = self.diagnostic()
        transport = fx.RecordingTransport(unknown=True)
        task, ref = self.generate(d, 'uncertain-independent', transport)
        original = self.resolve(ref)
        self.diagnostic(name='new-diagnostic-after-unknown')
        self.revoke()
        before = tree_snapshot(self.root)
        request = self.action(d, 'recover-after-revoke')
        request.update(target_refs=[], instructions='', generation_intent='recover',
            generation_request_id=task['task_id'], expected_revision=self.kernel.load().revision)
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(image2_command.Image2CommandAdapter, 'from_environment') as config:
            result = dispatch_v16(request)['result']
            config.assert_not_called()
        self.assertEqual(result['generation_response_ref'], ref)
        self.assertEqual(result['generation_response'], original)
        self.assertEqual(tree_snapshot(self.root), before)
        self.assertEqual(len(transport.payloads), 1)
        self.assertFalse(result['generation_usability']['candidate_eligible'])

    def test_source_with_consistent_forged_hashes_cannot_replace_current_original_authority(self):
        context = self.resolve(self.source_task['context_pack_ref'])
        request = context['layers']['image_led_request']
        request['payload']['page_goal'] = 'UNAUTHORIZED-BUT-SELF-CONSISTENT-GOAL'
        request['payload']['non_visible_semantics']['relationship_summary'] = request['payload']['page_goal']
        request['payload_sha256'] = digest(request['payload'])
        context_ref = str(self.kernel.artifacts.reference_for('context-pack', context))
        task = {**self.source_task, 'context_pack_ref': context_ref}
        response = {**self.source, 'payload_sha256': request['payload_sha256']}
        state = self.update('consistent-fake-source', {
            'agent/context/source': ('context-pack', context), 'agent/task/source': ('agent-task', task),
            'agent/task/active': ('agent-task', task),
            'project/image-led/request/source': ('image-led-generation-response', response)})
        fake_ref = state.artifact_heads['project/image-led/request/source']
        self.assert_rejected_unchanged(lambda: ImageLedRepairService(self.kernel).source_info(fake_ref))

    def test_diagnostic_cannot_use_a_substituted_reviewer_context_or_result(self):
        d, reviewer = self.diagnostic()
        context = self.resolve(reviewer['context_pack_ref'])
        context['layers']['image_led_diagnostic']['image_base64'] = base64.b64encode(png('#77bb44')).decode()
        context_ref = str(self.kernel.artifacts.reference_for('context-pack', context))
        completed = self.commands.resolve_agent_task(reviewer['task_id'])
        completed['context_pack_ref'] = context_ref
        self.update('substitute-reviewer-context', {
            'agent/context/' + reviewer['task_id']: ('context-pack', context),
            'agent/task/' + reviewer['task_id']: ('agent-task', completed)})
        self.assert_rejected_unchanged(lambda: self.service.compile_request(d))

    def test_png_header_acceptance_does_not_replace_full_runtime_or_frame_checks(self):
        original = repair_payload()
        raw = base64.b64decode(original['edit_target']['data_base64'])[:33]
        original['edit_target'].update(data_base64=base64.b64encode(raw).decode(), image_sha256=hashlib.sha256(raw).hexdigest())
        validate_repair_payload(original)  # Explicitly header-only provider boundary.
        target = original['edit_target']
        response = {'image_base64': target['data_base64'], 'image_sha256': target['image_sha256'],
            'image_mime_type': 'image/png', 'image_size': [target['width'], target['height']]}
        with self.assertRaises(ContractValidationError): ImageLedRepairService._image(response)
        frames = BytesIO()
        Image.new('RGB', (160, 90), 'red').save(frames, format='PNG', save_all=True,
            append_images=[Image.new('RGB', (160, 90), 'blue')], duration=100, loop=0)
        raw = frames.getvalue()
        response.update(image_base64=base64.b64encode(raw).decode(), image_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ContractValidationError): ImageLedRepairService._image(response)

    def test_wrong_aspect_ratio_completed_repair_is_not_eligible_for_candidate(self):
        d, _ = self.diagnostic()
        task, ref = self.generate(d, 'wrong-aspect', DistinctTransport('#408080', (1280, 800)))
        response = self.resolve(ref)
        self.assertEqual(response['status'], 'completed')
        self.assertEqual(response['output_fitness']['reasons'], ['aspect-ratio'])
        _, recovered, usability = self.service.generation_receipt(task)
        self.assertEqual(recovered, response)
        self.assertFalse(usability['candidate_eligible'])
        self.assertEqual(usability['status'], 'needs-revision')
        self.assert_rejected_unchanged(lambda: self.candidate(task, ref, 'ineligible-candidate'))

    def test_new_candidate_cannot_use_old_source_review_or_selection(self):
        old_candidate = self.candidate(self.source_task, self.source_ref, 'old-candidate')
        old_review = review_candidate(self.service, old_candidate, 'old-image-review')
        d, _ = self.diagnostic()
        task, ref = self.generate(d, 'different-new-image', DistinctTransport('#fa6020'))
        new_candidate = self.candidate(task, ref, 'new-candidate')
        self.assertNotEqual(self.resolve(new_candidate)['image_sha256'], self.resolve(old_candidate)['image_sha256'])
        self.assert_rejected_unchanged(lambda: ImageLedSelectionService(self.kernel).current_source_review(new_candidate, old_review))
        heads = self.kernel.load().artifact_heads
        self.assertNotIn(PREFIX + 'source-review/' + ArtifactReference.parse(new_candidate).sha256, heads)
        for slot in ('selection', 'regions', 'native-pptx'):
            self.assertNotIn(PREFIX + slot, heads)

    def test_closed_provider_text_and_old_protocol_probe_cannot_queue_repair(self):
        reviewer = self.review_task(name='private-note-review')
        value = self.diagnostic_payload()
        value['excluded_content_check']['detail'] = 'PRIVATE-EXCLUSION-DETAIL'
        value['issues'][1]['observed_text'] = 'PRIVATE-OBSERVED-TEXT'
        d = self.commit_diagnostic(reviewer, value, 'private-note-diagnostic')
        payload = self.service.compile_request(d)
        _, mime, raw = image2_crs.compile_body({'protocol': 'image-led-image2-repair-transport/v1',
            'request_id': 'pure-compile', 'payload': payload})
        fields, images = decoded_body(mime, raw)
        for forbidden in ('PRIVATE-EXCLUSION-DETAIL', 'PRIVATE-OBSERVED-TEXT',
                'INDEPENDENT-PRIVATE-INSTRUCTIONS', 'authorization_binding', 'source_payload_sha256'):
            self.assertNotIn(forbidden, fields['prompt'])
        self.assertEqual(images[0].get_payload(decode=True), base64.b64decode(self.source['image_base64']))
        calls = []
        def old_probe(command, **kwargs):
            sent = json.loads(kwargs['input']); calls.append(sent)
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                'protocol': 'image-led-image2-preflight/v2', 'request_id': sent['request_id'],
                'receiver': 'CRS', 'model': 'gpt-image-2', 'helper_executable': True,
                'external_connection': 'not-tested', 'generation_protocol': 'image-led-image2-transport/v2'}).encode())
        with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), \
                patch.object(image2_command.subprocess, 'run', side_effect=old_probe):
            self.assert_rejected_unchanged(lambda: dispatch_v16(self.action(d, 'old-protocol-no-queue')))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['generation_protocol'], 'image-led-image2-repair-transport/v1')

if __name__ == '__main__':
    with patch.object(subprocess, 'Popen', side_effect=AssertionError('real subprocess forbidden in independent review')), \
            patch.object(urllib.request.OpenerDirector, 'open', side_effect=AssertionError('real HTTP forbidden in independent review')):
        unittest.main(verbosity=2)
