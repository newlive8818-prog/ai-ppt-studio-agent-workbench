"""Offline original-output and model observation contracts, never provider proof."""
import base64
from copy import deepcopy
from datetime import datetime
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ppt_studio.adapters import image2_crs
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.materials.image_input_v2 import visible_copy
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests import test_image2_crs_provider as provider_fixtures
from tests.test_image2_crs_provider import PNG, v2_request
from tests.test_image_led_v2_runtime import v2_input_fixture, v2_candidate, v2_selection_fixture, exact_crs_environment, OfflineKnownCrsBoundary
from tests.test_image2_input_boundary import tree_snapshot


class ProviderCompatibilityTests(unittest.TestCase):
    setUp = provider_fixtures.Image2CrsProviderTests.setUp
    invoke = provider_fixtures.Image2CrsProviderTests.invoke
    assert_safe_failure = provider_fixtures.Image2CrsProviderTests.assert_safe_failure

    def test_image2_codex_preserves_requested_route_and_both_raw_origins(self):
        for root_model, item_model in (('gpt-image-2-codex', None),
                                       (None, 'gpt-image-2-codex'),
                                       ('gpt-image-2', 'gpt-image-2-codex')):
            with self.subTest(root=root_model, item=item_model):
                root = {'quality': 'auto', 'size': '1672x941', 'output_format': 'png'}
                item = {'quality': 'high', 'size': '2048x1152', 'output_format': 'png'}
                if root_model is not None: root['model'] = root_model
                if item_model is not None: item['model'] = item_model
                raw = json.dumps({**root, 'data': [{**item, 'b64_json': base64.b64encode(PNG).decode()}]}).encode()
                self.response.read.return_value = raw
                code, out, err = self.invoke(v2_request('gpt-image-2'))
                self.assertEqual((code, err), (0, ''), 'approved Image2Codex route is still rejected')
                result = json.loads(out)
                self.assertEqual(result['model'], 'gpt-image-2')
                observed = result.get('provider_observation')
                self.assertIsInstance(observed, dict, 'raw provider observations were dropped')
                self.assertEqual(observed['reported'], {'response': root, 'image': item})
                self.assertEqual(observed['model_match'], 'compatible-image2-codex')
                self.assertIs(observed['independent_engine_proof'], False)
                self.assertEqual(observed['response_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(datetime.fromisoformat(observed['observed_at_utc']).utcoffset().total_seconds(), 0)
                self.assertEqual(base64.b64decode(result['image_base64']), PNG)

    def test_exact_and_absent_model_remain_distinct_observations(self):
        for reported, match in (({}, 'not-reported'), ({'model': 'gpt-image-2'}, 'exact')):
            self.response.read.return_value = json.dumps({**reported, 'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode()
            code, out, err = self.invoke(v2_request('gpt-image-2'))
            self.assertEqual((code, err), (0, ''))
            observed = json.loads(out).get('provider_observation')
            self.assertIsInstance(observed, dict)
            self.assertEqual(observed['reported'], {'response': reported, 'image': {}})
            self.assertEqual(observed['model_match'], match)
            self.assertIs(observed['independent_engine_proof'], False)

    def test_sunburst_unknown_cross_family_and_invalid_metadata_stay_rejected(self):
        for model, reported in ((image2_crs.SUNBURST_MODEL, 'gpt-image-2-codex'),
                                 (image2_crs.SUNBURST_MODEL, 'gpt-image-2'),
                                 ('gpt-image-2', image2_crs.SUNBURST_MODEL),
                                 ('gpt-image-2', 'unknown'), ('gpt-image-2', None)):
            for location in ('response', 'image'):
                value = {'model': model, 'data': [{'model': model, 'b64_json': base64.b64encode(PNG).decode()}]}
                (value if location == 'response' else value['data'][0])['model'] = reported
                self.response.read.return_value = json.dumps(value).encode()
                self.assert_safe_failure(self.invoke(v2_request(model), [] if model == 'gpt-image-2' else ['--model', model]))
        for key, value in (('quality', None), ('size', {'bad': 'field'}), ('output_format', 'a\nsecret'), ('quality', 'x'*65)):
            response = {'data': [{'b64_json': base64.b64encode(PNG).decode()}], key: value}
            self.response.read.return_value = json.dumps(response).encode()
            self.assert_safe_failure(self.invoke(v2_request('gpt-image-2')))

    def test_system_canvas_is_outside_customer_input_for_json_and_ordered_edits(self):
        from email.parser import BytesParser
        from email.policy import default
        for model in ('gpt-image-2', image2_crs.SUNBURST_MODEL):
            for count in (0, 1, 2):
                original = v2_request(model, count)
                original['payload']['common_rules']['background'] = '三页共用浅色正文基础背景。'
                before = deepcopy(original)
                _, mime, raw = self.wrapper.compile_body(original, model=model)
                if count:
                    msg = BytesParser(policy=default).parsebytes(b'Content-Type: ' + mime.encode() + b'\r\n\r\n' + raw)
                    parts = list(msg.iter_parts())
                    fields = {part.get_param('name', header='content-disposition'): part.get_payload(decode=True)
                              for part in parts if part.get_filename() is None}
                    self.assertEqual([part.get_payload(decode=True) for part in parts if part.get_filename()],
                                     [base64.b64decode(item['data_base64']) for item in original['payload']['materials']])
                    prompt = json.loads(fields['prompt'])
                else:
                    prompt = json.loads(json.loads(raw)['prompt'])
                self.assertEqual(prompt['system_output_requirements']['canvas'], {'aspect_ratio': '16:9'})
                self.assertEqual(prompt['common_rules'], before['payload']['common_rules'])
                self.assertEqual(prompt['page_goal'], before['payload']['page_goal'])
                self.assertEqual([i['text'] for i in prompt['confirmed_visible_copy']['items']],
                                 [i['text'] for i in before['payload']['confirmed_visible_copy']['items']])
                self.assertEqual(original, before)


class ObservedBoundary(OfflineKnownCrsBoundary):
    def __init__(self, dimensions=(1672, 941), mutate=None):
        super().__init__(model='gpt-image-2', upstream_model='gpt-image-2-codex')
        stream = BytesIO()
        Image.new('RGB', dimensions, '#203040').save(stream, format='PNG')
        self.image = stream.getvalue()
        self.mutate = mutate

    def open(self, request, **options):
        response = super().open(request, **options)
        value = json.loads(response.read())
        # Deliberately independent of decoded bytes, to catch relabeling and
        # fitness checks that accidentally trust the provider's reported size.
        value.update(quality='auto', size='1672x941', output_format='png')
        value['data'][0].update(quality='high', size='2048x1152', output_format='webp')
        response.read = lambda: json.dumps(value).encode()
        return response

    def run(self, command, **options):
        result = super().run(command, **options)
        if list(command) == self.command and self.mutate and result.returncode == 0:
            value = json.loads(result.stdout)
            self.mutate(value)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(value).encode())
        return result


def resolve(service, ref):
    return service.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']


def action(service, pack, **changes):
    return {'operation': 'request-agent-action', 'project_root': str(service.kernel.project_root),
        'command_id': 'output-new', 'expected_revision': service.kernel.load().revision,
        'action_type': 'generate-slide-images', 'target_refs': [pack], 'instructions': '',
        'generation_intent': 'new', 'generation_request_id': 'output-request', **changes}


class OutputRuntimeTests(unittest.TestCase):
    def test_injected_legacy_response_cannot_bypass_geometry_by_omitting_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            commands = ProjectCommandService(service.kernel)
            _, task, _ = commands.request_agent_action('injected', service.kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            raw = ObservedBoundary((1536, 1024)).image
            class Transport:
                def generate(self, **kwargs):
                    return {'response_id': 'synthetic-injected', 'image_bytes': raw}
            response_ref = service.execute_generation(task['task_id'], transport=Transport())
            response = resolve(service, response_ref)
            self.assertEqual(response['status'], 'completed')
            self.assertNotIn('provider_observation', response)
            self.assertEqual(response['output_fitness']['status'], 'needs-revision')
            # Eligibility is recomputed from actual dimensions, not an optional
            # stored fitness result, including historical pre-fix responses.
            forged = deepcopy(response)
            forged.pop('output_fitness')
            service.kernel.commit(command_id='synthetic-old-response', expected_revision=service.kernel.load().revision,
                event_type='synthetic.old-response', artifact_updates={
                    'project/image-led/request/' + task['task_id']: ('image-led-generation-response', forged)})
            self.assertFalse(service.generation_receipt(task)[2]['candidate_eligible'])

    def test_existing_candidate_is_rechecked_before_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            candidate_ref, _ = v2_candidate(service, packs[0], 'old-candidate')
            candidate = resolve(service, candidate_ref)
            image = resolve(service, candidate['image_ref'])
            raw = ObservedBoundary((1536, 1024)).image
            image.update(sha256=hashlib.sha256(raw).hexdigest(), data_base64=base64.b64encode(raw).decode(),
                         width=1536, height=1024)
            candidate.update(image_ref=str(service.kernel.artifacts.reference_for('image-led-image', image)),
                             image_sha256=image['sha256'])
            slot = 'visual/image-led/candidate/' + candidate['slide_id']
            state = service.kernel.commit(command_id='synthetic-old-candidate', expected_revision=service.kernel.load().revision,
                event_type='synthetic.old-candidate', artifact_updates={
                    slot: ('image-led-candidate', candidate),
                    'visual/image-led/image/' + candidate['request_id']: ('image-led-image', image)})
            before = tree_snapshot(Path(folder))
            with self.assertRaisesRegex(ContractValidationError, 'OUTPUT_FITNESS'):
                ImageLedSelectionService(service.kernel).current_candidate(state.artifact_heads[slot])
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_native_inventory_preserves_actual_near_widescreen_geometry(self):
        from tests.test_image_led_runtime import inventory_for, register_regions
        raw = ObservedBoundary().image
        class Transport:
            def generate(self, **kwargs):
                return {'response_id': 'synthetic-native', 'image_bytes': raw}
        with tempfile.TemporaryDirectory() as folder, patch('tests.test_image_led_v2_runtime.SyntheticTransport', Transport):
            service, selection_ref = v2_selection_fixture(Path(folder))
            selection = service.current_selection(selection_ref)
            inventory = inventory_for(selection, selection_ref)
            for slide in inventory['slides']:
                slide['source_image_size'] = {'width': 1672, 'height': 941}
                slide['canvas'] = {'width': 1672, 'height': 941, 'dpi': 96}
            distorted = deepcopy(inventory)
            distorted['slides'][0]['canvas'] = {'width': 2048, 'height': 1152, 'dpi': 96}
            before = tree_snapshot(Path(folder))
            with self.assertRaisesRegex(ContractValidationError, 'preserve source image aspect ratio'):
                register_regions(service.kernel, distorted, command='distorted')
            self.assertEqual(tree_snapshot(Path(folder)), before)
            region_ref = register_regions(service.kernel, inventory)
            self.assertEqual(resolve(service, region_ref), inventory)
            for slide in selection['slides']:
                self.assertEqual(slide['target_binding']['target_image_sha256'], hashlib.sha256(raw).hexdigest())

    def test_original_bytes_and_observations_survive_without_reauthorizing(self):
        for dimensions in ((1672, 941), (1280, 720), (1366, 768), (1920, 1080), (2048, 1152)):
            with self.subTest(dimensions=dimensions), tempfile.TemporaryDirectory() as folder:
                service, policy, packs = v2_input_fixture(Path(folder), include_material=True)
                before = {key: resolve(service, policy[key]) for key in
                          ('authorization_scope_ref', 'authorization_ref', 'g0_ref')}
                payload = service.compile_request(packs[0])
                with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), ObservedBoundary(dimensions) as boundary:
                    reply = dispatch_v16(action(service, packs[0]))['result']
                    restored = dispatch_v16(action(service, packs[0], command_id='output-recover', generation_intent='recover'))['result']
                response = reply['generation_response']
                self.assertEqual(response['status'], 'completed')
                self.assertEqual(response['image_size'], list(dimensions))
                self.assertEqual(base64.b64decode(response['image_base64']), boundary.image)
                self.assertEqual(response['image_sha256'], hashlib.sha256(boundary.image).hexdigest())
                self.assertEqual(response['image_mime_type'], 'image/png')
                self.assertEqual(response['provider_observation'], boundary.receipts[0]['provider_observation'])
                self.assertEqual(response['provider_observation']['reported'], {
                    'response': {'model': 'gpt-image-2-codex', 'quality': 'auto', 'size': '1672x941', 'output_format': 'png'},
                    'image': {'quality': 'high', 'size': '2048x1152', 'output_format': 'webp'}})
                self.assertEqual(response['output_fitness']['status'], 'eligible')
                self.assertTrue(reply['generation_usability']['candidate_eligible'])
                self.assertEqual(restored['generation_response_ref'], reply['generation_response_ref'])
                self.assertEqual(len(boundary.http_calls), 1)
                self.assertEqual(service.compile_request(packs[0]), payload)
                self.assertEqual({key: resolve(service, policy[key]) for key in before}, before)

    def test_unsuitable_original_is_preserved_but_candidate_write_is_blocked(self):
        for dimensions, reason in (((1536, 1024), 'aspect-ratio'), ((1672, 942), 'aspect-ratio'),
                                   ((1024, 576), 'minimum-resolution'), ((1279, 720), 'minimum-resolution')):
            with self.subTest(dimensions=dimensions), tempfile.TemporaryDirectory() as folder:
                service, _, packs = v2_input_fixture(Path(folder))
                with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), ObservedBoundary(dimensions) as boundary:
                    reply = dispatch_v16(action(service, packs[0]))['result']
                    dispatch_v16(action(service, packs[0], command_id='output-recover', generation_intent='recover'))
                response = reply['generation_response']
                self.assertEqual(response['status'], 'completed', 'known original must remain recoverable')
                self.assertEqual(response['image_size'], list(dimensions))
                self.assertEqual(base64.b64decode(response['image_base64']), boundary.image)
                self.assertEqual(response['output_fitness']['status'], 'needs-revision')
                self.assertIn(reason, response['output_fitness']['reasons'])
                self.assertEqual(reply['generation_usability']['status'], 'needs-revision')
                self.assertFalse(reply['generation_usability']['candidate_eligible'])
                self.assertIn('尺寸或比例', reply['follow_up_message'])
                self.assertEqual(len(boundary.http_calls), 1)
                pack = resolve(service, packs[0])
                candidate = {'artifact_type': 'image-led-candidate', 'project_id': service.kernel.project_id,
                    'request_id': reply['task']['task_id'], 'generation_response_ref': reply['generation_response_ref'],
                    'pack_ref': packs[0], 'slide_id': pack['slide_id'], 'page_order': pack['page_order'],
                    'selected_copy': visible_copy(pack), 'material_roles': []}
                before = tree_snapshot(Path(folder))
                with self.assertRaisesRegex(ContractValidationError, 'OUTPUT_FITNESS'):
                    ProjectCommandService(service.kernel).commit_noncontent_agent_result(command_id='bad-candidate',
                        expected_revision=service.kernel.load().revision, task_id=reply['task']['task_id'],
                        request_kind='visual-contract', raw_request_payload=candidate)
                self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_transport_observation_missing_forged_or_open_fields_cannot_be_accepted(self):
        mutations = [lambda r: r.pop('provider_observation', None),
            lambda r: r.setdefault('provider_observation', {}).update(independent_engine_proof=True),
            lambda r: r.setdefault('provider_observation', {}).update(model_match='exact'),
            lambda r: r.setdefault('provider_observation', {}).update(secret='untrusted'),
            lambda r: r.setdefault('provider_observation', {}).update(reported={'response': {'model': image2_crs.SUNBURST_MODEL}, 'image': {}})]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                service, _, packs = v2_input_fixture(Path(folder))
                with patch.dict(os.environ, exact_crs_environment('gpt-image-2'), clear=True), ObservedBoundary(mutate=mutate) as boundary:
                    reply = dispatch_v16(action(service, packs[0]))['result']
                    recovered = dispatch_v16(action(service, packs[0], command_id='output-recover', generation_intent='recover'))['result']
                self.assertEqual(reply['generation_response']['status'], 'unknown')
                self.assertFalse(reply['generation_usability']['candidate_eligible'])
                self.assertEqual(recovered['generation_response_ref'], reply['generation_response_ref'])
                self.assertEqual(len(boundary.http_calls), 1)


if __name__ == '__main__':
    unittest.main()
