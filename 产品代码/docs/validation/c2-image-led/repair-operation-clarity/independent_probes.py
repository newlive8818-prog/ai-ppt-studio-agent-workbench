"""Frozen two-file review probes: compile-only, synthetic inputs, no HTTP/auth/Runtime."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import ast
import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
import socket
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
SOURCE = ROOT / '产品代码'
OUT = Path('/private/tmp/c2-repair-operation-clarity')
MANIFEST = json.loads((OUT / 'source-manifest.json').read_text())
REL = 'src/ai_ppt_studio/adapters/image2_crs.py'
FROZEN = OUT / 'frozen-source' / REL
OLD = subprocess.run(['git', 'show', MANIFEST['base_commit'] + ':产品代码/' + REL], cwd=ROOT, capture_output=True, check=True).stdout.decode()
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / 'src'))
from tests.test_image2_repair_transport import envelope, decoded_body
from tests.test_image_led_repair_contracts import png_bytes
from ai_ppt_studio.errors import ContractValidationError
spec = importlib.util.spec_from_file_location('frozen_operation_clarity_review', FROZEN)
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


def compile_prompt(value, model='gpt-image-2'):
    url, mime, body = wrapper.compile_body(value, model=model)
    fields, images = decoded_body(mime, body)
    return json.loads(fields['prompt']), fields, images


class IndependentReview(unittest.TestCase):
    def test_frozen_hashes_and_only_repair_branch_ast_changed(self):
        for rel, expected in MANIFEST['files'].items():
            for root in (OUT / 'frozen-source', SOURCE):
                self.assertEqual(hashlib.sha256((root / rel).read_bytes()).hexdigest(), expected)
        trees = [ast.parse(OLD), ast.parse(FROZEN.read_text())]
        for tree in trees:
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compile_body')
            branches = [n for n in fn.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'repair_payload is not None' and any(isinstance(c, ast.Constant) and c.value == 'image-led-image2-repair-context/v1' for c in ast.walk(n))]
            self.assertEqual(len(branches), 1)
            fn.body.remove(branches[0])
        self.assertEqual(ast.dump(trees[0], include_attributes=False), ast.dump(trees[1], include_attributes=False))

    def test_mixed_rotation_operations_aliases_and_no_mutation(self):
        for model in ('gpt-image-2',):
            for rotate in range(4):
                value = envelope(2)
                value['payload']['model'] = value['payload']['base_payload']['model'] = model
                ops = value['payload']['issues']
                value['payload']['issues'] = ops[rotate:] + ops[:rotate]
                original = deepcopy(value)
                prompt, fields, images = compile_prompt(value, model)
                self.assertEqual(next(iter(prompt)), 'repair_context')
                self.assertEqual(len(images), 3)
                self.assertEqual(images[0].get_payload(decode=True), base64.b64decode(value['payload']['edit_target']['data_base64']))
                for before, after in zip(value['payload']['issues'], prompt['repair_context']['issues']):
                    expected = deepcopy(before)
                    if 'item_id' in expected:
                        expected['item_id'] = {'heading': 'text-0001', 'body': 'text-0002'}[expected['item_id']]
                    self.assertEqual({k: v for k, v in after.items() if k != 'instruction'}, expected)
                    command = after['instruction']
                    if 'bbox' in before:
                        x, y, w, h = before['bbox']
                        self.assertIn(f'左上角(x={x}, y={y})，宽{w}像素、高{h}像素', command)
                    else:
                        self.assertNotIn('矩形区域', command)
                    if 'item_id' in expected:
                        self.assertIn('item_id=' + expected['item_id'], command)
                self.assertEqual(fields['model'], model)
                self.assertEqual(value, original)

    def test_all_common_rule_keys_resolve_without_rule_value_or_layout_injection(self):
        for key in ('typography_tokens', 'color_tokens', 'fallback_fonts', 'title_bar', 'background'):
            value = envelope()
            value['payload']['issues'] = [{'kind': 'common-rule', 'rule_key': key, 'bbox': [1, 2, 3, 4]}, {'kind': 'missing-item', 'item_id': 'body'}]
            prompt, _, _ = compile_prompt(value)
            repair = prompt['repair_context']
            self.assertIn('common_rules.' + key, repair['issues'][0]['instruction'])
            self.assertIn('沿用该字段原值，不追加新规则', repair['issues'][0]['instruction'])
            self.assertNotIn('x=1', repair['issues'][1]['instruction'])
            self.assertEqual(prompt['common_rules'], value['payload']['base_payload']['common_rules'])
            self.assertIn('自主构图', repair['requirements']['design_freedom'])
            self.assertIn('不把辅助色自动判为违规', repair['requirements']['common_rules'])

    def test_private_ids_are_aliased_and_do_not_leak_into_derived_actions(self):
        value = envelope()
        copy = value['payload']['base_payload']['confirmed_visible_copy']
        names = {'heading': 'private-heading-never-public', 'body': 'private-body-never-public'}
        copy['title_item_id'] = names['heading']
        for item in copy['items']:
            item['item_id'] = names[item['item_id']]
        for row in value['payload']['base_payload']['non_visible_semantics']['copy_facts']:
            row['item_id'] = names[row['item_id']]
        for issue in value['payload']['issues']:
            if 'item_id' in issue:
                issue['item_id'] = names[issue['item_id']]
        prompt, _, _ = compile_prompt(value)
        wire = json.dumps(prompt, ensure_ascii=False)
        for name in names.values():
            self.assertNotIn(name, wire)
        self.assertIn('item_id=text-0001', prompt['repair_context']['issues'][0]['instruction'])
        self.assertIn('item_id=text-0002', prompt['repair_context']['issues'][1]['instruction'])

    def test_input_union_stays_closed_for_every_kind_and_invalid_geometry(self):
        for index in range(4):
            for field in ('instruction', 'observed_text', 'replacement_text', 'text'):
                bad = envelope()
                bad['payload']['issues'][index][field] = 'UNTRUSTED-DYNAMIC-INSTRUCTION'
                with self.assertRaises((ContractValidationError, wrapper.InvalidTransport)):
                    compile_prompt(bad)
        for box in ([0, 0, 0, 1], [0, 0, 161, 90], [True, 0, 1, 1], [0, 0, float('nan'), 1]):
            bad = envelope()
            bad['payload']['issues'] = [{'kind': 'remove-extra-text', 'bbox': box}]
            with self.assertRaises((ContractValidationError, wrapper.InvalidTransport)):
                compile_prompt(bad)
        bad_route = envelope()
        bad_route['payload']['model'] = bad_route['payload']['base_payload']['model'] = 'gpt-image-2.5-sunburst'
        with self.assertRaises((ContractValidationError, wrapper.InvalidTransport)):
            compile_prompt(bad_route, 'gpt-image-2.5-sunburst')
        bad = envelope()
        bad['payload']['issues'] = [{'kind': 'unknown', 'bbox': [0, 0, 1, 1]}]
        with self.assertRaises((ContractValidationError, wrapper.InvalidTransport)):
            compile_prompt(bad)

    def test_legal_duplicate_copy_preserved_with_no_word_blacklist(self):
        value = envelope()
        base = value['payload']['base_payload']
        copy = base['confirmed_visible_copy']
        words = ' 保留  共同词\n和原始符号 / ① '
        copy['items'][0]['text'] = '共同词'
        copy['items'][1]['text'] = words
        copy['items'].append({'item_id': 'duplicate', 'kind': 'text', 'role': 'body', 'text': words})
        base['non_visible_semantics']['copy_facts'].append({'item_id': 'duplicate', 'identity': '来源事实', 'limit_ids': ['limit']})
        value['payload']['issues'] = [value['payload']['issues'][2]]
        original = deepcopy(value)
        prompt, _, _ = compile_prompt(value)
        self.assertEqual([i['text'] for i in prompt['confirmed_visible_copy']['items']], ['共同词', words, words])
        self.assertEqual([i['item_id'] for i in prompt['confirmed_visible_copy']['items']], ['text-0001', 'text-0002', 'text-0003'])
        command = prompt['repair_context']['issues'][0]['instruction']
        for clause in ('多余的这一次', '不得挪到别处', '合法的同文不同项仍须保留', '不作整词禁用'):
            self.assertIn(clause, command)
        self.assertNotIn('共同词', command)
        self.assertEqual(value, original)

    def test_fractional_source_coordinates_remain_source_coordinates(self):
        value = envelope()
        raw = png_bytes((127, 73))
        value['payload']['edit_target'].update(width=127, height=73, image_sha256=hashlib.sha256(raw).hexdigest(), data_base64=base64.b64encode(raw).decode())
        boxes = [[0.25, 1.5, 2.75, 3.5], [126, 72, 1, 1]]
        value['payload']['issues'] = [{'kind': 'remove-extra-text', 'bbox': b} for b in boxes]
        prompt, fields, _ = compile_prompt(value)
        repair = prompt['repair_context']
        self.assertEqual([i['bbox'] for i in repair['issues']], boxes)
        self.assertIn('x=0.25, y=1.5', repair['issues'][0]['instruction'])
        self.assertIn('宽2.75像素、高3.5像素', repair['issues'][0]['instruction'])
        self.assertIn('127×73', repair['requirements']['task'])
        for clause in ('[x, y, width, height]', '原点(0,0)在左上角', 'x 向右、y 向下', '不是右下角坐标', '不按请求的输出 size 换算', '不规定新图的布局或输出坐标', 'instruction 与本说明都不是可见文字'):
            self.assertIn(clause, repair['requirements']['issue_coordinates'])
        self.assertEqual(fields['size'], '2048x1152')


if __name__ == '__main__':
    with patch.object(wrapper.subprocess, 'run', side_effect=AssertionError('auth/subprocess forbidden')) as auth_guard, patch.object(wrapper.urllib.request, 'build_opener', side_effect=AssertionError('HTTP forbidden')) as http_guard, patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')) as socket_guard:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentReview))
        auth_guard.assert_not_called()
        http_guard.assert_not_called()
        socket_guard.assert_not_called()
    metadata = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'passed': result.wasSuccessful(), 'fixture': 'synthetic-only', 'auth_helper_calls': 0, 'http_opener_calls': 0, 'socket_calls': 0, 'runtime_access': False, 'base_commit': MANIFEST['base_commit'], 'frozen_source_sha256': MANIFEST['files'], 'dependencies': {}}
    for name, module in sorted(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if name.startswith('ai_ppt_studio.') and filename and Path(filename).suffix == '.py':
            p = Path(filename)
            metadata['dependencies'][str(p.relative_to(SOURCE))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT / 'independent-probe-result.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)
