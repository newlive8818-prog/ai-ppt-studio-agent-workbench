"""Actual SDK carrier and byte-backed acceptance for explicit text outlines."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from tests.test_image_led_results import NODE, MODULES
from tests.test_image_led_text_fragments_sdk import run_js
from tests.test_image_led_character_spacing_sdk import SPACING_SETUP
from ai_ppt_studio.application.image_led_results import inspect_native_pptx, preflight_output
from ai_ppt_studio.application.image_led_ooxml import NS
from ai_ppt_studio.errors import ContractValidationError

OUTLINE_SETUP = SPACING_SETUP + r"""
for (const r of s.regions.flatMap(r=>r.appearance.fragments ? r.appearance.fragments.flatMap(f=>f.appearance.runs) : r.appearance.runs ?? []))
  r.outline={color:'#003060',width:10.8};
for (const r of s.regions) if (r.kind==='table') for (const c of r.appearance.cells) for (const run of c.style.runs) run.outline={color:'#003060',width:10.8};
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,render_mode:['image','decoration'].includes(r.kind)?'bitmap':'native'}));
"""


def render_fixture(root):
    run_js(root, OUTLINE_SETUP + "const before=structuredClone(h);await render(h,options);assert.deepEqual(h,before);")
    file = next(root.glob('*/result.json'))
    return json.loads((file.parent / 'handoff.json').read_text()), json.loads(file.read_text())


def named(tree, name):
    return next(e for e in tree.find('p:cSld/p:spTree', NS)
                if any(n.get('name') == name for n in e.findall('.//p:cNvPr', NS)))


@unittest.skipUnless(NODE.exists() and (MODULES / '@oai/artifact-tool').exists(), 'bundled runtime unavailable')
class TextOutlineSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path('/private/tmp/c2-text-outline-20260911').mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(prefix='outline-sdk-', dir='/private/tmp/c2-text-outline-20260911')
        cls.root = Path(cls.directory.name).resolve()
        cls.handoff, cls.output = render_fixture(cls.root)
        cls.raw = Path(cls.output['pptx_path']).read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_outline_roundtrips_on_ordinary_fragment_and_table_runs(self):
        self.assertEqual(preflight_output(self.output, self.handoff, self.root), self.output)
        self.assertEqual(len(inspect_native_pptx(self.raw, self.handoff)), 14)
        with ZipFile(BytesIO(self.raw)) as archive:
            tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            for name in ('o-title-0', 'o-body-0::fragment:0:11', 'o-body-0::fragment:12:16', 'o-body-0::fragment:16:18'):
                line = named(tree, name).find('.//a:r/a:rPr/a:ln', NS)
                self.assertIsNotNone(line)
                self.assertEqual(line.get('w'), '102870')
                self.assertEqual(line.find('a:prstDash', NS).get('val'), 'solid')
                self.assertEqual(line.find('a:solidFill/a:srgbClr', NS).get('val'), '003060')
            table_line = named(tree, 'o-small-table').find('.//a:r/a:rPr/a:ln', NS)
            self.assertEqual(table_line.get('w'), '102870')
        directory = Path(self.output['pptx_path']).parent
        for filename in ('authoring.proto.json', 'reimport.proto.json'):
            proto = json.loads((directory / filename).read_text())
            elements = {e['name']: e for e in proto['slides'][0]['elements']}
            self.assertEqual(elements['o-title-0']['paragraphs'][0]['runs'][0]['textStyle']['outline']['widthEmu'], 102870)
            self.assertEqual(elements['o-small-table']['table']['rows'][0]['cells'][0]['paragraphs'][0]['runs'][0]['textStyle']['outline']['widthEmu'], 102870)

    def test_adding_outline_to_old_run_is_rejected(self):
        with ZipFile(BytesIO(self.raw)) as source:
            target = BytesIO()
            with ZipFile(target, 'w') as dest:
                for entry in source.infolist():
                    raw = source.read(entry.filename)
                    if entry.filename == 'ppt/slides/slide1.xml':
                        tree = ET.fromstring(raw)
                        old = named(tree, 'o-body-0::fragment:11:12').find('.//a:r/a:rPr', NS)
                        ET.SubElement(old, '{%s}ln' % NS['a'], {'w': '102870'})
                        raw = ET.tostring(tree)
                    dest.writestr(entry, raw)
        with self.assertRaises(ContractValidationError):
            inspect_native_pptx(target.getvalue(), self.handoff)


if __name__ == '__main__':
    unittest.main()
