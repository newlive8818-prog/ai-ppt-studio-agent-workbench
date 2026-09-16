"""Pure repair contract tests; synthetic bytes, no Runtime or provider calls."""
from copy import deepcopy
import base64
import hashlib
from io import BytesIO
import math
import unittest

from PIL import Image
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.domains.visual import image_output
from tests.test_image2_crs_provider import v2_request

REPAIR_VERSION = 'image-led-image2-repair-input/v1'
REPAIR_PROTOCOL = 'image-led-image2-repair-transport/v1'
LOCAL_ONLY = '原图额外标签，仅供本地核对'


def png_bytes(size=(160, 90), color='#385C82'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format='PNG')
    return buffer.getvalue()


def response():
    raw = png_bytes()
    return {'status': 'completed', 'image_base64': base64.b64encode(raw).decode(),
            'image_sha256': hashlib.sha256(raw).hexdigest(), 'image_size': [160, 90],
            'image_mime_type': 'image/png'}


def issues():
    return [{'kind': 'missing-item', 'item_id': 'heading'},
            {'kind': 'replace-item', 'item_id': 'body', 'bbox': [10, 15, 40.5, 12]},
            {'kind': 'remove-extra-text', 'bbox': [90, 40, 30, 10], 'observed_text': LOCAL_ONLY},
            {'kind': 'common-rule', 'rule_key': 'color_tokens', 'bbox': [0, 0, 160, 90]}]


def base_payload(count=0):
    return v2_request('gpt-image-2', count)['payload']


def repair_payload(count=0):
    original = response()
    return {'payload_version': REPAIR_VERSION, 'receiver': 'CRS', 'model': 'gpt-image-2',
        'base_payload': base_payload(count), 'edit_target': {
            'role': 'edit-target', 'image_sha256': original['image_sha256'],
            'data_base64': original['image_base64'], 'mime_type': 'image/png',
            'width': 160, 'height': 90},
        'issues': [{k: v for k, v in issue.items() if k != 'observed_text'} for issue in issues()]}


def diagnostic():
    return {'artifact_type': 'image-led-content-diagnostic',
        'diagnostic_version': 'image-led-content-diagnostic/v1', 'project_id': 'p1',
        'pack_ref': 'artifact://image-led-input-pack/' + 'a' * 64,
        'generation_response_ref': 'artifact://image-led-generation-response/' + 'b' * 64,
        'slide_id': 'slide-1', 'page_order': 1, 'image_sha256': response()['image_sha256'],
        'image_size': [160, 90], 'reviewer_kind': 'engineering',
        'reviewer_role': 'visual-engineering-reviewer',
        'excluded_content_check': {'result': 'passed', 'detail': '仅本地核对原图排除内容'},
        'issues': issues()}


class RepairContractTests(unittest.TestCase):
    def setUp(self):
        from ai_ppt_studio.domains.visual import image_repair
        self.contract = image_repair

    def test_diagnostic_is_closed_deepcopy_and_keeps_failed_exclusion_for_recording(self):
        for result in ('passed', 'failed', 'not-established'):
            value = diagnostic(); value['excluded_content_check']['result'] = result
            original = deepcopy(value)
            checked = self.contract.validate_diagnostic(value, 'p1')
            self.assertEqual(checked, original)
            checked['issues'][1]['bbox'][0] = 4
            self.assertEqual(value, original)

    def test_diagnostic_rejects_forged_server_bindings_and_wrong_identity(self):
        cases = [('project_id', 'other'), ('artifact_type', 'other'),
                 ('diagnostic_version', 'other'), ('pack_ref', '/tmp/pptx'),
                 ('generation_response_ref', 'artifact://image-led-candidate/' + 'b' * 64),
                 ('slide_id', '../slide'), ('page_order', True), ('image_sha256', 'x' * 64),
                 ('image_size', [160, False]), ('reviewer_kind', 'human'),
                 ('reviewer_role', 'image-asset-producer'), ('authorization_binding', {}),
                 ('reviewer_task_id', 'fake-review'), ('instructions', 'send arbitrary text')]
        for key, value in cases:
            bad = diagnostic(); bad[key] = value
            with self.subTest(field=key), self.assertRaises(ContractValidationError):
                self.contract.validate_diagnostic(bad, 'p1')
        for check in ({'result': 'passed'}, {'result': 'approved', 'detail': 'x'},
                      {'result': 'passed', 'detail': ' '}, {'result': 'passed', 'detail': 'x' * 2001}):
            bad = diagnostic(); bad['excluded_content_check'] = check
            with self.assertRaises(ContractValidationError):
                self.contract.validate_diagnostic(bad, 'p1')

    def test_issues_bind_original_items_and_rules_without_mutation(self):
        copy = base_payload()['confirmed_visible_copy']
        value = issues(); original = deepcopy(value)
        self.assertEqual(self.contract.validate_issues(value, copy, [160, 90]), value)
        self.assertEqual(value, original)
        for key in ('typography_tokens', 'color_tokens', 'fallback_fonts', 'title_bar', 'background'):
            self.contract.validate_issues([{'kind': 'common-rule', 'rule_key': key,
                'bbox': [0, 0, 160, 90]}], copy, [160, 90])

    def test_invalid_issue_unions_references_duplicates_and_local_text_fail(self):
        copy = base_payload()['confirmed_visible_copy']
        bad_rows = [[], issues() * 33, [{'kind': 'other'}],
            [{'kind': 'missing-item', 'item_id': 'other'}],
            [{'kind': 'missing-item', 'item_id': 'heading', 'replacement_text': 'new'}],
            [{'kind': 'replace-item', 'item_id': 'body', 'bbox': [0, 0, 10, 10], 'text': 'new'}],
            [{'kind': 'common-rule', 'rule_key': 'new-color', 'bbox': [0, 0, 10, 10]}],
            [{'kind': 'remove-extra-text', 'bbox': [0, 0, 10, 10], 'observed_text': ''}],
            [{'kind': 'remove-extra-text', 'bbox': [0, 0, 10, 10], 'observed_text': 'x' * 2001}],
            [issues()[0], issues()[0]],
            [issues()[0], {'kind': 'replace-item', 'item_id': 'heading', 'bbox': [0, 0, 10, 10]}],
            [{'kind': 'replace-item', 'item_id': 'heading', 'bbox': [0, 0, 10, 10]},
             {'kind': 'replace-item', 'item_id': 'body', 'bbox': [0, 0, 10, 10]}],
            [issues()[2], {**issues()[2], 'observed_text': 'different local description'}],
            [issues()[3], issues()[3]]]
        for index, value in enumerate(bad_rows):
            with self.subTest(index=index), self.assertRaises(ContractValidationError):
                self.contract.validate_issues(value, copy, [160, 90])

    def test_operation_count_upper_boundary_and_source_header_checks(self):
        many = [{'kind': 'common-rule', 'rule_key': 'background', 'bbox': [x, 0, 1, 1]}
                for x in range(128)]
        self.assertEqual(self.contract.validate_issues(many, base_payload()['confirmed_visible_copy'], [160, 90]), many)
        raw = bytearray(png_bytes()); raw[29] ^= 1
        bad = repair_payload()
        bad['edit_target'].update(data_base64=base64.b64encode(raw).decode(), image_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ContractValidationError):
            self.contract.validate_repair_payload(bad)

    def test_boxes_are_finite_original_pixel_regions_not_boolean_or_outside(self):
        for bbox in ([True, 0, 10, 10], [0, 0, False, 10], [-1, 0, 10, 10],
                     [0, 0, 0, 10], [150, 0, 11, 10], [0, 80, 10, 11],
                     [math.nan, 0, 10, 10], [0, 0, math.inf, 10], [0, 0, 10],
                     ['0', 0, 10, 10], [10**400, 0, 10, 10]):
            with self.subTest(bbox=repr(bbox)), self.assertRaises(ContractValidationError):
                self.contract.validate_issues([{'kind': 'replace-item', 'item_id': 'body', 'bbox': bbox}],
                                              base_payload()['confirmed_visible_copy'], [160, 90])

    def test_external_remove_operation_rejects_observed_text_and_accepts_coordinates_only(self):
        value = repair_payload()['issues']
        self.assertEqual(self.contract.validate_issues(value, base_payload()['confirmed_visible_copy'],
                                                      [160, 90], external=True), value)
        with self.assertRaises(ContractValidationError):
            self.contract.validate_issues(issues(), base_payload()['confirmed_visible_copy'], [160, 90], external=True)

    def test_factory_uses_actual_response_size_and_removes_all_local_notes(self):
        base, source, local = base_payload(2), response(), issues()
        originals = deepcopy((base, source, local))
        checked = self.contract.build_repair_payload(base, source, local)
        self.assertEqual(checked, repair_payload(2))
        self.assertEqual((base, source, local), originals)
        checked['base_payload']['confirmed_visible_copy']['items'][0]['text'] = 'changed'
        self.assertEqual((base, source, local), originals)
        for mutation in ({'status': 'unknown'}, {'image_size': [320, 180]},
                         {'image_mime_type': 'image/jpeg'}, {'image_sha256': '0' * 64}):
            bad = {**source, **mutation}
            with self.assertRaises(ContractValidationError):
                self.contract.build_repair_payload(base, bad, local)
        bad = deepcopy(source); bad.pop('image_size'); bad.update(image_width=160, image_height=90)
        with self.assertRaises(ContractValidationError):
            self.contract.build_repair_payload(base, bad, local)

    def test_repair_payload_rejects_schema_target_and_base_identity_bypasses(self):
        value = repair_payload(2)
        self.assertEqual(self.contract.validate_repair_payload(value), value)
        mutators = [lambda p: p.update(instructions='free text'),
            lambda p: p.update(model='gpt-image-2.5-sunburst'),
            lambda p: p.update(receiver='other'),
            lambda p: p['base_payload'].update(payload_version='legacy'),
            lambda p: p['base_payload'].update(model='other'),
            lambda p: p['base_payload'].update(instructions='new channel'),
            lambda p: p['base_payload']['materials'][0].update(content_sha256='0' * 64),
            lambda p: p['edit_target'].update(role='style-reference'),
            lambda p: p['edit_target'].update(image_sha256='0' * 64),
            lambda p: p['edit_target'].update(width=320),
            lambda p: p['edit_target'].update(mime_type='image/jpeg'),
            lambda p: p['edit_target'].update(path='/tmp/other.png'),
            lambda p: p['edit_target'].update(data_base64='@@'),
            lambda p: p['issues'][2].update(observed_text=LOCAL_ONLY)]
        for index, mutate in enumerate(mutators):
            bad = deepcopy(value); mutate(bad)
            with self.subTest(index=index), self.assertRaises(ContractValidationError):
                self.contract.validate_repair_payload(bad)

    def test_fitness_unwraps_repair_base_and_never_silently_skips_it(self):
        payload = repair_payload()
        self.assertEqual(image_output.output_fitness(payload, [160, 90])['status'], 'needs-revision')
        self.assertEqual(image_output.output_fitness(payload, [1672, 941])['status'], 'eligible')
        self.assertIn('aspect-ratio', image_output.output_fitness(payload, [1600, 1200])['reasons'])
        payload['base_payload']['model'] = 'other'
        with self.assertRaises(ContractValidationError):
            image_output.output_fitness(payload, [1672, 941])


if __name__ == '__main__':
    unittest.main()
