import unittest
from copy import deepcopy

from ai_ppt_studio.domains.visual.diagnostic import (
    DIAGNOSTIC_HANDOFF_VERSION,
    DIAGNOSTIC_INPUT_VERSION,
    DIAGNOSTIC_INPUT_KIND,
    DIAGNOSTIC_RESULT_KIND,
    validate_diagnostic_review_admission,
    diagnostic_projection,
)


class DiagnosticContractTests(unittest.TestCase):
    def _review(self, *results):
        names = [
            'visible-copy-transcription', 'complete-region-coverage',
            'material-roles', 'source-image-derived-relations',
            'faithful-geometry-appearance',
        ]
        return {'checks': [
            {'criterion': n, 'result': r, 'detail': 'evidence'}
            for n, r in zip(names, results)
        ]}

    def test_admission_accepts_four_passed_and_appearance_not_established(self):
        value = validate_diagnostic_review_admission(self._review(
            'passed', 'passed', 'passed', 'passed', 'not-established'))
        self.assertEqual(value['appearance_result'], 'not-established')

    def test_admission_rejects_any_required_failure_or_other_unknown(self):
        for values in [
            ('failed', 'passed', 'passed', 'passed', 'not-established'),
            ('passed', 'passed', 'passed', 'passed', 'failed'),
            ('passed', 'passed', 'passed', 'not-established', 'passed'),
        ]:
            with self.subTest(values=values), self.assertRaises(Exception):
                validate_diagnostic_review_admission(self._review(*values))

    def test_projection_copies_regions_and_adds_only_native_identity(self):
        region = {'region_id': 'r1', 'kind': 'text', 'bbox': [0, 0, 10, 10],
                  'z_order': 0, 'content': {'items': [{'text': 'x'}]},
                  'appearance': {'runs': []}}
        slide = {'slide_id': 'S01', 'regions': [region], 'canvas': {'width': 10, 'height': 10}}
        result = diagnostic_projection({'slides': [slide]}, task_id='t')
        self.assertEqual(result['slides'][0]['objects'][0]['object_id'], 'object-r1')
        self.assertEqual(result['slides'][0]['objects'][0]['render_mode'], 'native')
        self.assertEqual(result['slides'][0]['objects'][0]['bbox'], region['bbox'])
        self.assertEqual(result['diagnostic_version'], DIAGNOSTIC_INPUT_VERSION)
        self.assertEqual(DIAGNOSTIC_INPUT_KIND, 'image-led-native-diagnostic-input')
        self.assertEqual(DIAGNOSTIC_RESULT_KIND, 'image-led-native-diagnostic-result')


if __name__ == '__main__':
    unittest.main()

class DiagnosticTaskContractTests(unittest.TestCase):
    def test_action_uses_native_role_and_diagnostic_result_kind(self):
        from ai_ppt_studio.application.project_service import ACTION_ROLES, NONCONTENT_RESULT_CONTRACTS
        self.assertEqual(ACTION_ROLES['build-native-diagnostic'], 'native-first-engineer')
        self.assertIn(('visual-contract', 'image-led-native-diagnostic-result'),
                      NONCONTENT_RESULT_CONTRACTS['build-native-diagnostic'])

    def test_handoff_rejects_formal_plan_reference(self):
        from ai_ppt_studio.domains.visual.diagnostic import validate_diagnostic_handoff
        value = {
            'handoff_version': 'codex-presentations-image-led-diagnostic/v1',
            'compiler_version': 'image-led-diagnostic-compiler/v1',
            'purpose': 'region-diagnostic', 'diagnostic_ref': 'artifact://x/' + 'a'*64,
            'project_id': 'p', 'selection_ref': 'artifact://x/' + 'b'*64,
            'region_inventory_ref': 'artifact://x/' + 'c'*64, 'task_id': 't',
            'slides': [], 'assets': {}, 'output_paths': {}, 'plan_ref': 'forbidden',
        }
        with self.assertRaises(Exception): validate_diagnostic_handoff(value)
