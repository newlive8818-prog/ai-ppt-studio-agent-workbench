"""Provider request contracts; offline checks do not prove model compliance."""
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import base64
import json
from pathlib import Path
import tempfile
import unittest

from ai_ppt_studio.adapters import image2_crs
from ai_ppt_studio.application.project_service import ProjectCommandService
from tests.test_image2_crs_provider import request, v2_request
from tests.test_image_led_v2_runtime import v2_input_fixture


def provider_prompt(envelope):
    _, mime, raw = image2_crs.compile_body(envelope, model=envelope['payload']['model'])
    if mime == 'application/json':
        return json.loads(json.loads(raw)['prompt']), []
    message = BytesParser(policy=default).parsebytes(
        b'Content-Type: ' + mime.encode() + b'\r\n\r\n' + raw)
    parts = list(message.iter_parts())
    prompt = next(part.get_payload(decode=True) for part in parts
                  if part.get_param('name', header='content-disposition') == 'prompt')
    return json.loads(prompt), [part.get_payload(decode=True) for part in parts if part.get_filename()]


class ProviderContentAuthorityTests(unittest.TestCase):
    def test_all_routes_send_content_authority_separately_from_unchanged_customer_input(self):
        # Catches missing requirements on either JSON/edits or either input/model route.
        for model in ('gpt-image-2', image2_crs.SUNBURST_MODEL):
            for version in (1, 2):
                for count in (0, 1, 2):
                    with self.subTest(model=model, version=version, images=count):
                        value = v2_request(model, count)
                        if version == 1:
                            value = request()
                            value['payload']['model'] = model
                            value['payload']['materials'] = v2_request(model, count)['payload']['materials']
                        before = deepcopy(value)
                        prompt, images = provider_prompt(value)
                        requirements = prompt['system_output_requirements']
                        self.assertEqual(requirements['canvas'], {'aspect_ratio': '16:9'})
                        for field, clauses in {
                            'visible_copy': ['confirmed_visible_copy', '逐项', 'Unicode', '重复次数', '标语', '数字', '标签'],
                            'title_bar': ['title_item_id', 'role=title', '标题栏内', '章节标签不能替代'],
                            'non_visible_context': ['non_visible_semantics', 'page_goal', '不得作为新增可见文案'],
                            'design_freedom': ['字体', '配色', '标题栏', '背景', '自主', '自然折行'],
                            'self_check': ['遗漏', '新增', '重复', '标点'],
                        }.items():
                            self.assertIn(field, requirements)
                            for clause in clauses:
                                self.assertIn(clause, requirements[field])
                        self.assertEqual(requirements['version'], 'image-led-system-output/v2')
                        self.assertEqual(prompt['common_rules'], before['payload']['common_rules'])
                        self.assertEqual(prompt['page_goal'], before['payload']['page_goal'])
                        self.assertEqual(images, [base64.b64decode(i['data_base64']) for i in before['payload']['materials']])
                        self.assertEqual(value, before)

    def test_legacy_material_use_is_required_while_v2_pool_stays_optional(self):
        # Catches applying the v2 optional pool semantics to legacy v1 all-atoms.
        legacy = request()
        legacy['payload']['materials'] = v2_request('gpt-image-2', 1)['payload']['materials']
        for value, expected, forbidden in (
            (legacy, '全部材料', '素材池为可选'),
            (v2_request('gpt-image-2', 1), '素材池为可选', '全部材料'),
        ):
            prompt, _ = provider_prompt(value)
            rule = prompt['system_output_requirements']['non_visible_context']
            self.assertIn(expected, rule)
            self.assertNotIn(forbidden, rule)
            self.assertIn('真实素材内原有文字', rule)
            self.assertIn('不属于新增文案', rule)

    def test_title_reference_and_equal_text_items_preserve_unicode_and_occurrences(self):
        # Catches text deduplication, quote/number normalization, or a second title copy.
        value = v2_request('gpt-image-2')
        copy = value['payload']['confirmed_visible_copy']
        copy['items'][0]['text'] = '① "同文"  \n② 数据'
        copy['items'][1]['text'] = '① "同文"  \n② 数据'
        prompt, _ = provider_prompt(value)
        public = prompt['confirmed_visible_copy']
        self.assertEqual([i['text'] for i in public['items']], ['① "同文"  \n② 数据'] * 2)
        self.assertEqual(len({i['item_id'] for i in public['items']}), 2)
        self.assertEqual(public['title_item_id'], public['items'][0]['item_id'])
        self.assertNotIn('title', public)
        self.assertIn('不同 item_id', prompt['system_output_requirements'].get('visible_copy', ''))
        self.assertIn('引用', prompt['system_output_requirements'].get('title_bar', ''))

    def test_caller_cannot_supply_system_rules_or_unvalidated_revision_feedback(self):
        for version in (1, 2):
            for field in ('system_output_requirements', 'instructions', 'revision_feedback'):
                value = request() if version == 1 else v2_request('gpt-image-2')
                value['payload'][field] = 'UNAUTHORIZED-FEEDBACK'
                with self.subTest(version=version, field=field), self.assertRaises(image2_crs.InvalidTransport):
                    provider_prompt(value)

    def test_internal_task_instructions_are_not_an_unchecked_provider_feedback_channel(self):
        # Characterizes the existing authorization boundary, not a new feedback feature.
        sentinel = 'INTERNAL-ONLY: do not export this task note'
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            _, task, _ = ProjectCommandService(service.kernel).request_agent_action(
                'local-instructions', service.kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions=sentinel)
            self.assertEqual(task['instructions'], sentinel)
            _, request_binding, payload = service.generation_context(task['task_id'])
            self.assertNotIn(sentinel, json.dumps(payload))
            prompt, _ = provider_prompt({'protocol': 'image-led-image2-transport/v2',
                'request_id': request_binding['request_id'], 'payload': payload})
            self.assertNotIn(sentinel, json.dumps(prompt))
            self.assertEqual(prompt['system_output_requirements']['version'], 'image-led-system-output/v2')


if __name__ == '__main__':
    unittest.main()
