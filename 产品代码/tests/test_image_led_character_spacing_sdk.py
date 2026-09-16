"""Actual SDK carrier and byte-backed acceptance for explicit character spacing."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from tests.test_image_led_results import NODE, MODULES
from tests.test_image_led_text_fragments_sdk import run_js
from ai_ppt_studio.application.image_led_results import inspect_native_pptx, preflight_output
from ai_ppt_studio.application.image_led_ooxml import NS
from ai_ppt_studio.errors import ContractValidationError

SPACING_SETUP = r"""
s.regions.find(r=>r.region_id==='title-0').appearance.runs[0].characterSpacing=-277;
const spacingBody=s.regions.find(r=>r.region_id==='body-0');
spacingBody.appearance.fragments[0].appearance.runs[0].characterSpacing=75;
spacingBody.appearance.fragments[2].appearance.runs[0].characterSpacing=-100;
spacingBody.appearance.fragments[3].appearance.runs[0].characterSpacing=0;
s.regions.find(r=>r.region_id==='small-table').appearance.cells[0].style.runs[0].characterSpacing=150;
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,
  render_mode:['image','decoration'].includes(r.kind)?'bitmap':'native'}));
"""
EXPECTED_SPACING = {'o-title-0': -277, 'o-body-0::fragment:0:11': 75,
                    'o-body-0::fragment:12:16': -100, 'o-body-0::fragment:16:18': 0,
                    'o-small-table': 150}


def render_spacing_fixture(root):
    run_js(root, SPACING_SETUP + "const spacingBefore=structuredClone(h);await render(h,options);assert.deepEqual(h,spacingBefore);")
    file = next(root.glob('*/result.json'))
    return json.loads((file.parent / 'handoff.json').read_text()), json.loads(file.read_text())


def named(tree, name):
    return next(e for e in tree.find('p:cSld/p:spTree', NS)
                if any(n.get('name') == name for n in e.findall('.//p:cNvPr', NS)))


@unittest.skipUnless(NODE.exists() and (MODULES / '@oai/artifact-tool').exists(), 'bundled runtime unavailable')
class CharacterSpacingSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path('/private/tmp/c2-character-spacing-20260911').mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(prefix='spacing-sdk-', dir='/private/tmp/c2-character-spacing-20260911')
        cls.root = Path(cls.directory.name).resolve()
        cls.ready = False

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def ensure_fixture(self):
        cls = type(self)
        if not cls.ready:
            try:
                cls.handoff, cls.output = render_spacing_fixture(cls.root)
            except Exception as error:
                self.fail('Explicit spacing SDK build failed: ' + str(error))
            cls.raw = Path(cls.output['pptx_path']).read_bytes()
            cls.ready = True

    def test_spacing_roundtrips_in_ordinary_fragment_gradient_and_table_runs(self):
        self.ensure_fixture()
        self.assertEqual(preflight_output(self.output, self.handoff, self.root), self.output)
        self.assertEqual(len(inspect_native_pptx(self.raw, self.handoff)), 14)
        with ZipFile(BytesIO(self.raw)) as archive:
            tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            for name, spacing in EXPECTED_SPACING.items():
                props = named(tree, name).find('.//a:r/a:rPr', NS)
                self.assertEqual(props.get('spc'), str(spacing))
            fragments = [named(tree, 'o-body-0::fragment:' + span) for span in ('0:11', '11:12', '12:16', '16:18', '18:22')]
            self.assertEqual(''.join(t.text or '' for node in fragments for t in node.findall('.//a:r/a:t', NS)), 'Headline😀e\u0301|Body  text')
        directory = Path(self.output['pptx_path']).parent
        for filename in ('authoring.proto.json', 'reimport.proto.json'):
            proto = json.loads((directory / filename).read_text())
            elements = {e['name']: e for e in proto['slides'][0]['elements']}
            for name, spacing in EXPECTED_SPACING.items():
                if name == 'o-small-table':
                    run = elements[name]['table']['rows'][0]['cells'][0]['paragraphs'][0]['runs'][0]
                else:
                    run = elements[name]['paragraphs'][0]['runs'][0]
                self.assertEqual(run['textStyle']['characterSpacing'], spacing)

    def test_unselected_run_stays_without_spacing_and_noautofit_is_preserved(self):
        self.ensure_fixture()
        with ZipFile(BytesIO(self.raw)) as archive:
            tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            node = named(tree, 'o-body-0::fragment:11:12')
            self.assertNotIn('spc', node.find('p:txBody/a:p/a:r/a:rPr', NS).attrib)
            for body in tree.findall('.//p:txBody', NS) + tree.findall('.//a:tc/a:txBody', NS):
                self.assertIsNotNone(body.find('a:bodyPr/a:noAutofit', NS))
                self.assertIsNone(body.find('a:bodyPr/a:normAutofit', NS))
                self.assertIsNone(body.find('a:bodyPr/a:spAutoFit', NS))

    def mutate(self, change):
        target = BytesIO()
        with ZipFile(BytesIO(self.raw)) as source, ZipFile(target, 'w') as dest:
            for entry in source.infolist():
                raw = source.read(entry.filename)
                if entry.filename == 'ppt/slides/slide1.xml':
                    tree = ET.fromstring(raw); change(tree); raw = ET.tostring(tree)
                dest.writestr(entry, raw)
        return target.getvalue()

    def test_actual_pptx_rejects_missing_changed_or_noninteger_selected_spacing(self):
        self.ensure_fixture()
        def prop(tree):
            return named(tree, 'o-title-0').find('p:txBody/a:p/a:r/a:rPr', NS)
        for value in (None, '-276', '-277.0', '-2.77e2', ''):
            def change(tree, value=value):
                if value is None:
                    prop(tree).attrib.pop('spc')
                else:
                    prop(tree).set('spc', value)
            with self.subTest(value=value), self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate(change), self.handoff)

    def test_actual_pptx_rejects_zero_spacing_injected_into_old_run(self):
        self.ensure_fixture()
        def change(tree):
            named(tree, 'o-body-0::fragment:11:12').find('p:txBody/a:p/a:r/a:rPr', NS).set('spc', '0')
        with self.assertRaises(ContractValidationError):
            inspect_native_pptx(self.mutate(change), self.handoff)

    def test_explicit_zero_may_not_be_omitted_and_fragment_table_values_are_bound(self):
        self.ensure_fixture()
        for name in ('o-body-0::fragment:16:18', 'o-body-0::fragment:0:11', 'o-small-table'):
            def change(tree, name=name):
                named(tree, name).find('.//a:r/a:rPr', NS).attrib.pop('spc')
            with self.subTest(name=name), self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate(change), self.handoff)

    def test_spacing_does_not_authorize_original_text_or_font_size_changes(self):
        self.ensure_fixture()
        def change_text(tree):
            node = named(tree, 'o-title-0').find('p:txBody/a:p/a:r/a:t', NS)
            node.text += 'extra'
        def change_size(tree):
            props = named(tree, 'o-title-0').find('p:txBody/a:p/a:r/a:rPr', NS)
            props.set('sz', str(int(props.get('sz')) + 1))
        for change in (change_text, change_size):
            with self.subTest(change=change), self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate(change), self.handoff)

    def test_invalid_spacing_fails_before_sdk_loading_and_output_directory(self):
        with tempfile.TemporaryDirectory(prefix='spacing-reject-', dir='/private/tmp/c2-character-spacing-20260911') as folder:
            run_js(Path(folder).resolve(), SPACING_SETUP + r"""
for(const bad of [true,false,0.5,'-277',null,-400001,400001]){
 const value=structuredClone(h);for(const key of ['regions','objects'])value.slides[0][key].find(o=>o.region_id==='title-0').appearance.runs[0].characterSpacing=bad;
 let loads=0;await assert.rejects(render(value,{...options,loadSdk:async()=>{loads++;throw Error('unexpected SDK');}}),/IMAGE_LED_/);
 assert.equal(loads,0);await assert.rejects(fs.stat(value.output_paths.directory),{code:'ENOENT'});
}
""")


if __name__ == '__main__':
    unittest.main()
