"""Real SDK sz encoding, preserving exact units without geometric tolerance changes."""
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

# Literal results from Artifact SDK 2.8.59, captured from actual PPTX rPr@sz.
# Neighbor cases distinguish source-order arithmetic from px*75 and ties-to-even.
SIZE_CASES = (
    (44.49999999999999, 3337), (44.5, 3338), (44.50000000000001, 3338),
    (44.499999999, 3337), (44.500000001, 3338),
    (43.49999999999999, 3262), (43.5, 3263), (43.50000000000001, 3263),
    (43.499999999, 3262), (43.500000001, 3263),
    (26.699999999999996, 2002), (26.7, 2002), (26.700000000000003, 2003),
    (26.699999999, 2002), (26.700000001, 2003),
    (16.099999999999998, 1207), (16.1, 1208), (16.100000000000005, 1208),
    (16.099999999, 1207), (16.100000001, 1208),
    (44.459999999999994, 3334), (44.46, 3335), (44.46000000000001, 3335),
    (44.459999999000004, 3334), (44.460000001, 3335),
    (44.419999999999995, 3332), (44.42, 3332), (44.42000000000001, 3332),
    (44.419999999000005, 3331), (44.420000001, 3332),
    (12, 900), (16, 1200), (44, 3300), (72, 5400), (96.02, 7202),
)

SIZE_SETUP = r"""
s.regions.find(r=>r.region_id==='title-0').appearance.runs[0].fontSize=44.5;
s.regions.find(r=>r.region_id==='body-0').appearance.fragments[0].appearance.runs[0].fontSize=43.5;
s.regions.find(r=>r.region_id==='small-table').appearance.cells[0].style.runs[0].fontSize=26.7;
const sizeStyle=structuredClone(s.regions.find(r=>r.region_id==='title-0').appearance);
for(let i=0;i<sizeCases.length;i++){
 const appearance=structuredClone(sizeStyle);appearance.runs=[{...appearance.runs[0],text:'Size '+i,fontSize:sizeCases[i][0]}];
 const id='size-'+i;
 s.regions.push({region_id:id,kind:'text',bbox:[0,0,500,100],z_order:s.regions.length,
   content:{items:[{item_id:id,kind:'text',role:'label',text:'Size '+i}]},material_binding:null,appearance});
}
s.selected_copy.items=s.regions.flatMap(r=>structuredClone(r.content.items));
s.target_binding.selected_copy_sha256=digest(canonical(s.selected_copy));
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,render_mode:['image','decoration'].includes(r.kind)?'bitmap':'native'}));
"""


def named(tree, name):
    return next(e for e in tree.find('p:cSld/p:spTree', NS)
                if any(n.get('name') == name for n in e.findall('.//p:cNvPr', NS)))


@unittest.skipUnless(NODE.exists() and (MODULES / '@oai/artifact-tool').exists(), 'bundled runtime unavailable')
class FontSizeSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-font-size-')
        cls.root = Path(cls.directory.name).resolve()
        try:
            run_js(cls.root, 'const sizeCases=' + json.dumps(SIZE_CASES) + ';\n' + SIZE_SETUP +
                   'const before=structuredClone(h);await render(h,options);assert.deepEqual(h,before);')
        except Exception:
            cls.directory.cleanup()
            raise
        result = next(cls.root.glob('*/result.json'))
        cls.handoff = json.loads((result.parent / 'handoff.json').read_text())
        cls.output = json.loads(result.read_text())
        cls.raw = Path(cls.output['pptx_path']).read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def mutate(self, change):
        target = BytesIO()
        with ZipFile(BytesIO(self.raw)) as source, ZipFile(target, 'w') as dest:
            for entry in source.infolist():
                raw = source.read(entry.filename)
                if entry.filename == 'ppt/slides/slide1.xml':
                    tree = ET.fromstring(raw)
                    change(tree)
                    raw = ET.tostring(tree)
                dest.writestr(entry, raw)
        return target.getvalue()

    def test_actual_sdk_half_and_neighbor_values_match_literal_sz_integers(self):
        with ZipFile(BytesIO(self.raw)) as archive:
            tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
        for i, (px, expected) in enumerate(SIZE_CASES):
            with self.subTest(px=px):
                prop = named(tree, 'o-size-' + str(i)).find('.//a:r/a:rPr', NS)
                self.assertEqual(prop.get('sz'), str(expected))
        for name, expected in (('o-title-0', '3338'), ('o-body-0::fragment:0:11', '3263'), ('o-small-table', '2002')):
            self.assertEqual(named(tree, name).find('.//a:r/a:rPr', NS).get('sz'), expected)

    def test_valid_sz_encoding_passes_full_native_result_intake(self):
        # Regression: the former bbox-scale comparison rejected 44.5 -> 3338.
        try:
            actual = preflight_output(self.output, self.handoff, self.root)
        except ContractValidationError as error:
            self.fail('Actual SDK encoded font sizes were rejected: ' + str(error))
        self.assertEqual(actual, self.output)
        self.assertEqual(len(inspect_native_pptx(self.raw, self.handoff)), 14 + len(SIZE_CASES))

    def test_one_centipoint_change_is_rejected_for_ordinary_fragment_and_table(self):
        for name in ('o-title-0', 'o-body-0::fragment:0:11', 'o-small-table', 'o-size-10'):
            for delta in (-1, 1):
                def change(tree, name=name, delta=delta):
                    prop = named(tree, name).find('.//a:r/a:rPr', NS)
                    prop.set('sz', str(int(prop.get('sz')) + delta))
                with self.subTest(name=name, delta=delta), self.assertRaises(ContractValidationError):
                    inspect_native_pptx(self.mutate(change), self.handoff)

    def test_missing_noninteger_or_unselected_sz_carriers_are_rejected(self):
        for value in (None, '', '3338.0', '3.338e3', 'NaN', 'Infinity', '3337', '3339'):
            def change(tree, value=value):
                prop = named(tree, 'o-title-0').find('.//a:r/a:rPr', NS)
                if value is None:
                    prop.attrib.pop('sz')
                else:
                    prop.set('sz', value)
            with self.subTest(value=value), self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate(change), self.handoff)

    def test_font_encoding_does_not_allow_bbox_or_text_changes(self):
        def change_bbox(tree):
            node = named(tree, 'o-title-0').find('p:spPr/a:xfrm/a:off', NS)
            node.set('x', str(int(node.get('x')) + 2))
        def change_text(tree):
            node = named(tree, 'o-title-0').find('p:txBody/a:p/a:r/a:t', NS)
            node.text += 'unselected'
        for change in (change_bbox, change_text):
            with self.subTest(change=change.__name__), self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate(change), self.handoff)

    def test_sdk_minimum_font_clamp_is_rejected_instead_of_silently_accepted(self):
        with tempfile.TemporaryDirectory(prefix='native-font-clamp-') as folder:
            root = Path(folder).resolve()
            run_js(root, r"""
for(const key of ['regions','objects'])s[key].find(o=>o.region_id==='title-0').appearance.runs[0].fontSize=0.5;
await render(h,options);
""")
            result = next(root.glob('*/result.json'))
            handoff = json.loads((result.parent / 'handoff.json').read_text())
            output = json.loads(result.read_text())
            raw = Path(output['pptx_path']).read_bytes()
            with ZipFile(BytesIO(raw)) as archive:
                tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            self.assertEqual(named(tree, 'o-title-0').find('.//a:r/a:rPr', NS).get('sz'), '100')
            with self.assertRaises(ContractValidationError):
                inspect_native_pptx(raw, handoff)


if __name__ == '__main__':
    unittest.main()
