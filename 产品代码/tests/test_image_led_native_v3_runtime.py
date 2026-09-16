"""V3 formal chain and actual bytes; synthetic data, never visual acceptance."""
from copy import deepcopy
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ai_ppt_studio.application.image_led_native import ImageLedNativeService, REGION_CHECKS
from ai_ppt_studio.application.image_led_results import inspect_native_pptx, preflight_output
from ai_ppt_studio.application.image_led_ooxml import NS, A
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image_led_native_v3_contracts import v3_fixture, VERSION
from tests.test_image_led_compilation import fixture_for, compile_plan
from tests.test_image_led_v2_runtime import v2_selection_fixture
from tests.test_image_led_results import render_runtime_fixture, NODE, MODULES
from tests.test_image2_input_boundary import tree_snapshot
from tests import test_image_led_runtime as fixtures

V3_CHECKS = REGION_CHECKS | {'source-image-derived-relations'}
BASE_INVENTORY = fixtures.inventory_for


def runtime_inventory(selection, selection_ref):
    inventory = BASE_INVENTORY(selection, selection_ref)
    inventory['region_version'] = VERSION
    template = v3_fixture()[1]['slides'][0]['regions'][-1]
    for slide, selected in zip(inventory['slides'], selection['slides']):
        for region in slide['regions']:
            region['appearance']['wrap'] = 'square'
        items = selected['selected_copy']['items']
        flow = deepcopy(template)
        flow['bbox'] = [40, 420, 100, 80]
        flow['z_order'] = len(slide['regions'])
        flow['appearance']['relation_binding'].update(
            target_image_sha256=slide['target_binding']['target_image_sha256'],
            from_item_id=items[0]['item_id'], to_item_id=items[1]['item_id'])
        feedback = deepcopy(flow)
        feedback.update(region_id='feedback', bbox=[240, 420, 100, 80], z_order=flow['z_order'] + 1)
        feedback['appearance']['relation_binding'] = {
            'origin': 'source-image-derived', 'target_image_sha256': slide['target_binding']['target_image_sha256'],
            'kind': 'feedback-symbol', 'anchor_item_id': items[1]['item_id']}
        feedback['appearance']['paths'][0]['commands'] = [
            {'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 100, 'y': 0}},
            {'lineTo': {'x': 100, 'y': 80}}, {'lineTo': {'x': 0, 'y': 80}}, {'close': {}},
            {'moveTo': {'x': 20, 'y': 20}}, {'lineTo': {'x': 20, 'y': 60}},
            {'lineTo': {'x': 80, 'y': 60}}, {'lineTo': {'x': 80, 'y': 20}}, {'close': {}}]
        polygon = deepcopy(feedback)
        polygon.update(region_id='polygon', kind='shape', bbox=[440, 420, 100, 80], z_order=flow['z_order'] + 2)
        polygon['appearance'].pop('relation_binding')
        polygon['appearance'].update(geometry='polygon', corner_radius=0, shadow=None)
        slide['regions'].extend([flow, feedback, polygon])
    return inventory


class NativeV3RuntimeContractTests(unittest.TestCase):
    def test_compiler_versions_and_exact_objects_follow_inventory(self):
        selection, inventory = v3_fixture()
        _, brief, design, contract = fixture_for(selection, inventory)
        plan = compile_plan(contract, selection, inventory, brief, design)
        self.assertEqual(plan['compiler_version'], 'image-led-faithful-compiler/v3')
        self.assertEqual(plan['handoff_version'], 'codex-presentations-image-led/v3')
        self.assertEqual(plan['slides'][0]['region_version'], VERSION)
        self.assertEqual(plan['slides'][0]['selected_copy'], selection['slides'][0]['selected_copy'])
        self.assertEqual(plan['slides'][0]['regions'], inventory['slides'][0]['regions'])

    def test_v3_region_review_requires_explicit_relation_assessment(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = v2_selection_fixture(Path(folder))
            inventory = runtime_inventory(service.current_selection(ref), ref)
            region_ref = fixtures.register_regions(service.kernel, inventory)
            before = tree_snapshot(Path(folder))
            # Direct pure review validation establishes the missing dimension.
            payload = {'checks': [{'criterion': c, 'result': 'passed', 'detail': 'Synthetic'}
                                   for c in sorted(REGION_CHECKS)]}
            with self.assertRaises(ContractValidationError):
                ImageLedNativeService._review_checks(payload, region_version=VERSION)
            self.assertEqual(tree_snapshot(Path(folder)), before)
            with patch.object(fixtures, 'REGION_CHECKS', V3_CHECKS):
                fixtures.region_review(service.kernel, region_ref)
            ImageLedNativeService(service.kernel).current_regions()


@unittest.skipUnless(NODE.exists() and (MODULES / '@oai/artifact-tool').exists(), 'bundled runtime unavailable')
class NativeV3ByteChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-v3-result-')
        cls.root = Path(cls.directory.name).resolve()
        with ExitStack() as stack:
            stack.enter_context(patch.object(fixtures, 'selection_fixture', v2_selection_fixture))
            stack.enter_context(patch.object(fixtures, 'inventory_for', runtime_inventory))
            stack.enter_context(patch.object(fixtures, 'REGION_CHECKS', V3_CHECKS))
            cls.kernel, cls.task, cls.handoff, cls.output = render_runtime_fixture(cls.root)
        cls.raw = Path(cls.output['pptx_path']).read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_three_page_paths_wrap_and_formal_result_commit(self):
        self.assertEqual(preflight_output(self.output, self.handoff, self.root), self.output)
        for slide in self.handoff['slides']:
            self.assertEqual(slide['region_version'], VERSION)
            self.assertTrue(all(i['kind'] == 'text' for i in slide['selected_copy']['items']))
            self.assertEqual([i for r in slide['regions'] for i in r['content']['items']], slide['selected_copy']['items'])
        payload = {'artifact_type': 'image-led-build-result', 'project_id': self.kernel.project_id, 'output': self.output}
        result_ref, _ = ProjectCommandService(self.kernel).commit_noncontent_agent_result(
            command_id='v3-result', expected_revision=self.kernel.load().revision, task_id=self.task['task_id'],
            request_kind='visual-contract', raw_request_payload=payload)
        value = self.kernel.artifacts.resolve(ArtifactReference.parse(result_ref))['payload']
        self.assertEqual(value['output'], self.output)
        self.assertEqual(value['output']['user_acceptance'], 'not-established')
        self.assertNotIn('visual/anchors', self.kernel.load().artifact_heads)
        self.assertNotEqual(self.kernel.load().gate_status['G3'], 'passed')

    def test_xml_changes_reject_paths_gradient_hole_and_wrap(self):
        self.assertEqual(len(inspect_native_pptx(self.raw, self.handoff)), len(self.output['mapping']))
        mutations = {
            'path-point': lambda t: t.find('.//a:custGeom/a:pathLst/a:path/a:lnTo/a:pt', NS).set('x', '1'),
            'path-viewport': lambda t: t.find('.//a:custGeom/a:pathLst/a:path', NS).set('w', '1'),
            'unclosed': lambda t: t.find('.//a:custGeom/a:pathLst/a:path', NS).remove(t.find('.//a:custGeom/a:pathLst/a:path/a:close', NS)),
            'arbitrary-path': lambda t: ET.SubElement(t.find('.//a:custGeom/a:pathLst/a:path', NS), '{' + A + '}arcTo'),
            'formula': lambda t: t.find('.//a:custGeom/a:pathLst/a:path/a:moveTo/a:pt', NS).set('x', 'wd2'),
            'gradient': lambda t: t.find('.//a:gradFill/a:gsLst/a:gs', NS).set('pos', '1234'),
            'gradient-angle-extra': lambda t: t.find('.//a:gradFill/a:lin', NS).set('scaled', '0'),
            'wrap': lambda t: t.find('.//p:txBody/a:bodyPr', NS).set('wrap', 'none'),
            'autofit': lambda t: ET.SubElement(t.find('.//p:txBody/a:bodyPr', NS), '{' + A + '}spAutoFit'),
            'text': lambda t: setattr(t.find('.//p:txBody/a:p/a:r/a:t', NS), 'text', 'Changed copy'),
        }
        with ZipFile(BytesIO(self.raw)) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        before = tree_snapshot(self.root)
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                tree = ET.fromstring(members['ppt/slides/slide1.xml']); mutate(tree)
                stream = BytesIO()
                with ZipFile(stream, 'w') as archive:
                    for name, raw in members.items():
                        archive.writestr(name, ET.tostring(tree) if name == 'ppt/slides/slide1.xml' else raw)
                with self.assertRaises(ContractValidationError):
                    inspect_native_pptx(stream.getvalue(), self.handoff)
        self.assertEqual(tree_snapshot(self.root), before)


if __name__ == '__main__':
    unittest.main()
