"""Offline repair provider projection, fixed-command and capability contracts."""
import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_ppt_studio.adapters import image2_command, image2_crs
from ai_ppt_studio.errors import ContractValidationError
from tests import test_image2_crs_provider as fixture
from tests.test_image_led_repair_contracts import (
    REPAIR_PROTOCOL, LOCAL_ONLY, repair_payload, response, issues, png_bytes)


def envelope(count=0):
    return {'protocol': REPAIR_PROTOCOL, 'request_id': 'repair-1', 'payload': repair_payload(count)}


def decoded_body(content_type, body):
    if content_type == 'application/json':
        return json.loads(body), []
    parts = list(BytesParser(policy=default).parsebytes(
        ('Content-Type: ' + content_type + '\r\n\r\n').encode() + body).iter_parts())
    fields = {p.get_param('name', header='content-disposition'): p.get_payload(decode=True).decode()
              for p in parts if not p.get_filename()}
    return fields, [p for p in parts if p.get_filename()]


class RepairProviderTests(unittest.TestCase):
    setUp = fixture.Image2CrsProviderTests.setUp
    invoke = fixture.Image2CrsProviderTests.invoke
    assert_safe_failure = fixture.Image2CrsProviderTests.assert_safe_failure

    def test_exact_edit_target_first_and_original_material_order_roles_and_aliases(self):
        for count in (0, 1, 2):
            value = envelope(count); original = deepcopy(value)
            url, mime, body = self.wrapper.compile_body(value)
            fields, images = decoded_body(mime, body)
            prompt = json.loads(fields['prompt'])
            self.assertEqual(url, self.wrapper.EDITS_URL)
            self.assertEqual([p.get_payload(decode=True) for p in images],
                [base64.b64decode(value['payload']['edit_target']['data_base64'])] +
                [base64.b64decode(m['data_base64']) for m in value['payload']['base_payload']['materials']])
            self.assertEqual([p.get_param('name', header='content-disposition') for p in images],
                             ['image' if count == 0 else 'image[]'] * (count + 1))
            self.assertEqual(fields['stream'], 'true'); self.assertEqual(fields['partial_images'], '1')
            base = value['payload']['base_payload']
            _, base_mime, base_body = self.wrapper.compile_body({
                'protocol': 'image-led-image2-transport/v2', 'request_id': 'base', 'payload': base})
            old_fields, _ = decoded_body(base_mime, base_body); old = json.loads(old_fields['prompt'])
            for key in ('confirmed_visible_copy', 'common_rules', 'page_goal', 'system_output_requirements'):
                self.assertEqual(prompt[key], old[key])
            expected = deepcopy(old['materials'])
            for material in expected:
                if 'image_number' in material: material['image_number'] += 1
            self.assertEqual(prompt['materials'], expected)
            expected_semantics = deepcopy(old['non_visible_semantics'])
            for material in expected_semantics['material_use']:
                if material['image_number'] is not None: material['image_number'] += 1
            self.assertEqual(prompt['non_visible_semantics'], expected_semantics)
            repair = prompt['repair_context']
            self.assertEqual(repair['edit_target'], {'role': 'edit-target', 'image_number': 1,
                                                    'width': 160, 'height': 90})
            operations = [{k: v for k, v in issue.items() if k != 'instruction'}
                          for issue in repair['issues']]
            self.assertEqual(operations[0], {'kind': 'missing-item', 'item_id': 'text-0001'})
            self.assertEqual(repair['issues'][1]['item_id'], 'text-0002')
            self.assertEqual(operations[2], {'kind': 'remove-extra-text', 'bbox': [90, 40, 30, 10]})
            self.assertEqual(repair['issues'][3]['rule_key'], 'color_tokens')
            for hidden in (LOCAL_ONLY, 'internal-atom', 'image_sha256', 'authorization', 'generation_response_ref'):
                self.assertNotIn(hidden, fields['prompt'])
            self.assertEqual(value, original)

    def test_repair_actions_precede_original_context_and_use_matching_public_references(self):
        value = envelope()
        # Mixed/reversed operations must not receive another issue's action or ID.
        value['payload']['issues'].reverse()
        _, mime, body = self.wrapper.compile_body(value)
        fields, _ = decoded_body(mime, body)
        prompt = json.loads(fields['prompt'])
        self.assertEqual(next(iter(prompt)), 'repair_context')
        public = prompt['repair_context']['issues']
        for issue, action, reference in zip(public,
                ('纠正', '删除', '替换', '补回'),
                ('common_rules.color_tokens', 'x=90, y=40', 'text-0002', 'text-0001')):
            command = issue.get('instruction', '')
            self.assertIn(action, command)
            self.assertIn(reference, command)
        self.assertEqual(set(public[0]), {'kind', 'rule_key', 'bbox', 'instruction'})
        self.assertEqual(set(public[1]), {'kind', 'bbox', 'instruction'})
        self.assertEqual(set(public[2]), {'kind', 'item_id', 'bbox', 'instruction'})
        self.assertEqual(set(public[3]), {'kind', 'item_id', 'instruction'})
        for hidden in (LOCAL_ONLY, 'heading', '"body"', 'observed_text'):
            self.assertNotIn(hidden, json.dumps(prompt['repair_context'], ensure_ascii=False))

    def test_each_remove_action_names_source_xywh_without_output_scaling_or_rounding(self):
        value = envelope()
        raw = png_bytes((997, 561))
        value['payload']['edit_target'].update(data_base64=base64.b64encode(raw).decode(),
            image_sha256=hashlib.sha256(raw).hexdigest(), width=997, height=561)
        boxes = [[0, 0, 1, 1], [90, 40, 30, 10], [10.25, 15.5, 40.5, 12.25], [991, 554, 6, 7]]
        value['payload']['issues'] = [{'kind': 'remove-extra-text', 'bbox': b} for b in boxes]
        original = deepcopy(value)
        _, mime, body = self.wrapper.compile_body(value)
        fields, images = decoded_body(mime, body)
        repair = json.loads(fields['prompt'])['repair_context']
        self.assertIn('997×561', repair['requirements']['task'])
        coordinates = repair['requirements']['issue_coordinates']
        for meaning in ('[x, y, width, height]', '左上角', 'x 向右', 'y 向下', '不是右下角', '不规定新图'):
            self.assertIn(meaning, coordinates)
        fragments = ['左上角(x=0, y=0)，宽1像素、高1像素',
                     '左上角(x=90, y=40)，宽30像素、高10像素',
                     '左上角(x=10.25, y=15.5)，宽40.5像素、高12.25像素',
                     '左上角(x=991, y=554)，宽6像素、高7像素']
        for issue, box, fragment in zip(repair['issues'], boxes, fragments):
            self.assertEqual(issue['bbox'], box)
            self.assertIn(fragment, issue.get('instruction', ''))
            self.assertIn('删除', issue['instruction'])
        self.assertEqual(images[0].get_payload(decode=True), raw)
        self.assertEqual(fields['size'], '2048x1152')
        self.assertEqual(value, original)

    def test_remove_occurrence_does_not_remove_identical_words_from_authorized_items(self):
        value = envelope()
        copy = value['payload']['base_payload']['confirmed_visible_copy']
        copy['items'][0]['text'] = '共享词语'
        copy['items'][1]['text'] = '完整句子内的共享词语必须保留。'
        copy['items'].append({'item_id': 'another', 'kind': 'text', 'role': 'body',
                              'text': '完整句子内的共享词语必须保留。'})
        value['payload']['base_payload']['non_visible_semantics']['copy_facts'].append(
            {'item_id': 'another', 'identity': '来源事实', 'limit_ids': ['limit']})
        value['payload']['issues'] = [value['payload']['issues'][2]]
        original = deepcopy(value)
        _, mime, body = self.wrapper.compile_body(value)
        fields, _ = decoded_body(mime, body)
        prompt = json.loads(fields['prompt'])
        self.assertEqual([i['text'] for i in prompt['confirmed_visible_copy']['items']],
                         ['共享词语', '完整句子内的共享词语必须保留。', '完整句子内的共享词语必须保留。'])
        command = prompt['repair_context']['issues'][0].get('instruction', '')
        for meaning in ('这一次', '其他位置', '完整原条目', '不得挪到别处'):
            self.assertIn(meaning, command)
        self.assertNotIn('共享词语', command)
        self.assertEqual(value, original)

    def test_repair_system_requirements_locate_issues_without_restricting_layout_or_auxiliary_colors(self):
        _, mime, body = self.wrapper.compile_body(envelope())
        fields, _ = decoded_body(mime, body)
        fixed = json.loads(fields['prompt'])['repair_context']['requirements']
        self.assertIn('定位', fixed['issue_coordinates'])
        self.assertIn('自主构图', fixed['design_freedom'])
        self.assertIn('排他色板', fixed['common_rules'])
        self.assertNotIn(LOCAL_ONLY, json.dumps(fixed, ensure_ascii=False))

    def test_text_material_between_images_keeps_null_semantic_image_number(self):
        value = envelope(2)
        base = value['payload']['base_payload']
        words = ' 原材料文字\n原样保留 '
        base['materials'].insert(1, {'atom_id': 'internal-text-material', 'type': 'text',
            'use': 'content-source', 'content_sha256': hashlib.sha256(words.encode()).hexdigest(), 'text': words})
        base['non_visible_semantics']['material_use'].insert(1, {
            'material_id': 'internal-text-material', 'image_number': None, 'use': 'content-source',
            'presence': 'optional', 'purpose': '', 'identity': '来源事实', 'limitations': []})
        original = deepcopy(value)
        _, mime, body = self.wrapper.compile_body(value)
        fields, images = decoded_body(mime, body)
        prompt = json.loads(fields['prompt'])
        self.assertEqual(len(images), 3)
        self.assertEqual([m['image_number'] for m in prompt['non_visible_semantics']['material_use']], [2, None, 3])
        self.assertEqual([m.get('image_number') for m in prompt['materials']], [2, None, 3])
        self.assertEqual([m['material_id'] for m in prompt['materials']],
                         ['material-0001', 'material-0002', 'material-0003'])
        self.assertEqual(prompt['materials'][1]['text'], words)
        self.assertEqual(value, original)

    def test_generation_preserves_repair_protocol_and_uses_one_edit_request(self):
        raw = base64.b64decode(response()['image_base64'])
        wire = b'data: ' + json.dumps({'type': 'image_edit.completed',
            'b64_json': base64.b64encode(raw).decode()}).encode() + b'\n\ndata: [DONE]\n\n'
        from io import BytesIO
        self.response.headers = {'Content-Type': 'text/event-stream'}
        self.response.readline.side_effect = BytesIO(wire).readline
        code, out, err = self.invoke(envelope(2))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['protocol'], REPAIR_PROTOCOL)
        self.assertEqual(base64.b64decode(json.loads(out)['image_base64']), raw)
        self.opener.open.assert_called_once(); self.auth.assert_called_once()
        self.assertEqual(self.opener.open.call_args.args[0].full_url, self.wrapper.EDITS_URL)

    def test_wrapper_rejects_untrusted_notes_wrong_versions_and_targets_before_auth(self):
        changes = [lambda v: v['payload']['issues'][2].update(observed_text=LOCAL_ONLY),
            lambda v: v['payload']['issues'][2].update(instruction='arbitrary instruction'),
            lambda v: v['payload'].update(instructions='free channel'),
            lambda v: v['payload']['edit_target'].update(image_sha256='0' * 64),
            lambda v: v.update(protocol='image-led-image2-transport/v2'),
            lambda v: v['payload'].update(model='gpt-image-2.5-sunburst')]
        for mutate in changes:
            value = envelope(); mutate(value)
            self.assert_safe_failure(self.invoke(value))
        self.auth.assert_not_called(); self.opener.open.assert_not_called()

    def test_repair_failure_is_one_post_and_does_not_expose_local_notes(self):
        from io import BytesIO
        wire = b'data: {"type":"error","error":"unsafe upstream text"}\n\n'
        self.response.headers = {'Content-Type': 'text/event-stream'}
        self.response.readline.side_effect = BytesIO(wire).readline
        result = self.invoke(envelope())
        self.assert_safe_failure(result)
        self.assertNotIn('unsafe upstream text', result[1] + result[2])
        self.opener.open.assert_called_once()


class RepairCommandTests(unittest.TestCase):
    def configured(self):
        wrapper = Path(image2_command.__file__).with_name('image2_crs.py')
        return {'AI_PPT_IMAGE2_ADAPTER_COMMAND': json.dumps([sys.executable, str(wrapper)]),
                'AI_PPT_IMAGE2_RECEIVER': 'CRS', 'AI_PPT_IMAGE2_MODEL': 'gpt-image-2'}

    def test_real_stat_only_preflight_explicitly_reports_repair_protocol(self):
        with patch.dict(os.environ, self.configured(), clear=True):
            value = image2_command.image2_preflight(generation_protocol=REPAIR_PROTOCOL)
        self.assertEqual(value['protocol_probe'], 'passed')
        self.assertEqual(value['external_connection'], 'not-tested')
        self.assertEqual(image2_command.generation_protocol(repair_payload()), REPAIR_PROTOCOL)

    def test_repair_compilation_runs_in_real_no_site_packages_interpreter(self):
        script = (
            'import json,sys\n'
            'from ai_ppt_studio.adapters import image2_crs\n'
            'url,mime,body=image2_crs.compile_body(json.load(sys.stdin))\n'
            'assert "PIL" not in sys.modules\n'
            'assert url==image2_crs.EDITS_URL and mime.startswith("multipart/form-data")\n'
            'print("stdlib-repair-compile-pass")\n'
        )
        completed = fixture.REAL_RUN([sys.executable, '-S', '-c', script],
            input=json.dumps(envelope(2)).encode(), capture_output=True,
            env={'PYTHONPATH': str(fixture.ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'},
            timeout=10, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout.strip(), b'stdlib-repair-compile-pass')

    def test_wrong_or_old_probe_does_not_authorize_repair(self):
        def old_probe(command, **kwargs):
            sent = json.loads(kwargs['input'])
            self.assertEqual(sent['generation_protocol'], REPAIR_PROTOCOL)
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                'protocol': 'image-led-image2-preflight/v2', 'request_id': sent['request_id'],
                'receiver': 'CRS', 'model': 'gpt-image-2', 'helper_executable': True,
                'external_connection': 'not-tested',
                'generation_protocol': 'image-led-image2-transport/v2'}).encode())
        with patch.dict(os.environ, self.configured(), clear=True), \
                patch.object(image2_command.subprocess, 'run', side_effect=old_probe) as run:
            adapter = image2_command.Image2CommandAdapter.from_environment()
            with self.assertRaises(ContractValidationError):
                adapter.preflight(repair_payload())
            run.assert_called_once()

    def test_adapter_sends_only_full_repair_payload_once_and_checks_receipt_protocol(self):
        payload = repair_payload(); original = deepcopy(payload)
        raw = base64.b64decode(response()['image_base64'])
        observation = image2_crs.provider_observation({}, {}, b'offline', model='gpt-image-2')
        receipt = {'protocol': REPAIR_PROTOCOL, 'request_id': 'repair-1', 'receiver': 'CRS',
            'model': 'gpt-image-2', 'response_id': 'synthetic-repair',
            'image_base64': base64.b64encode(raw).decode(), 'provider_observation': observation}
        with patch.dict(os.environ, self.configured(), clear=True):
            adapter = image2_command.Image2CommandAdapter.from_environment()
        with patch.object(adapter, 'preflight') as preflight, \
                patch.object(image2_command.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps(receipt).encode())) as run:
            result = adapter.generate(request_id='repair-1', payload=payload)
            self.assertEqual(result['image_bytes'], raw)
            self.assertEqual(json.loads(run.call_args.kwargs['input']), envelope())
            run.assert_called_once(); preflight.assert_called_once_with(payload)
        self.assertEqual(payload, original)
        receipt['protocol'] = 'image-led-image2-transport/v2'
        with patch.object(adapter, 'preflight'), patch.object(image2_command.subprocess, 'run',
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(receipt).encode())) as run:
            with self.assertRaises((ContractValidationError, RuntimeError)):
                adapter.generate(request_id='repair-1', payload=payload)
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
