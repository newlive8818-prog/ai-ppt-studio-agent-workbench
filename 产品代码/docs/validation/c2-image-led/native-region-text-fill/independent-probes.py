"""Independent Native increment probes; retained synthetic PPTX, no provider calls."""
from pathlib import Path
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile
import hashlib,json,subprocess,unittest,urllib.request
from unittest.mock import patch
import xml.etree.ElementTree as ET

from ai_ppt_studio.application.image_led_results import inspect_native_pptx, _text_check
from ai_ppt_studio.application.image_led_ooxml import NS,A
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory,validate_faithful_objects
from ai_ppt_studio.errors import ContractValidationError
from test_image_led_region_endpoints import container_fixture
from test_image_led_text_gradient import gradient_fixture,native_text_body,GRADIENT_XML,GRADIENT
from test_image_led_contracts import objects_for,text_style

OUT=Path('/private/tmp/c2-region-endpoints')
PROOF=OUT/'sdk-proof/b4698dbd327f6ffb328d6d6cf82c471e0b7051cb739d518d90cc70c640d8fa79'
VERSION='image-led-region-inventory/v3'

class IndependentNativeIncrement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(PROOF/'native-anchors.pptx').read_bytes()
        cls.handoff=json.loads((PROOF/'handoff.json').read_text())

    def test_five_frozen_files_and_retained_sdk_artifact_hashes_match(self):
        for row in json.loads((OUT/'native-increment-manifest.json').read_text())['files']:
            self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'],row['path'])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
            '4487b9bfcc9e78c3cd5c0a6f49cc69f36d055ee40e6ef77d5fe259b4f42922fc')

    def test_retained_sdk_has_twenty_native_objects_and_editable_page_gradient(self):
        self.assertEqual(len(inspect_native_pptx(self.raw,self.handoff)),20)
        with ZipFile(BytesIO(self.raw)) as archive: tree=ET.fromstring(archive.read('ppt/slides/slide1.xml'))
        page=next(p for p in tree.findall('.//p:sp',NS)
            if p.find('p:nvSpPr/p:cNvPr',NS).get('name')=='o-page-number')
        self.assertEqual(page.findtext('p:txBody/a:p/a:r/a:t','',NS),'12')
        gradient=page.find('p:txBody/a:p/a:r/a:rPr/a:gradFill',NS)
        self.assertIsNotNone(gradient)
        self.assertEqual(gradient.find('a:lin',NS).get('ang'),'5400000')
        fills=[]
        for filename in ('authoring.proto.json','reimport.proto.json'):
            proto=json.loads((PROOF/filename).read_text())
            page=next(e for e in proto['slides'][0]['elements'] if e['name']=='o-page-number')
            self.assertEqual([r['text'] for r in page['paragraphs'][0]['runs']],['12'])
            fills.append(page['paragraphs'][0]['runs'][0]['textStyle']['fill'])
        self.assertEqual(fills[0],fills[1])
        self.assertEqual([(s['position'],s['color']['value']) for s in fills[0]['gradientStops']],
            [(0,'637F9E'),(100000,'B4D8F0')])

    def mutate_pptx(self,change):
        result=BytesIO()
        with ZipFile(BytesIO(self.raw)) as src,ZipFile(result,'w') as dst:
            for entry in src.infolist():
                data=src.read(entry.filename)
                if entry.filename=='ppt/slides/slide1.xml':
                    tree=ET.fromstring(data)
                    page=next(p for p in tree.findall('.//p:sp',NS)
                        if p.find('p:nvSpPr/p:cNvPr',NS).get('name')=='o-page-number')
                    props=page.find('p:txBody/a:p/a:r/a:rPr',NS)
                    change(tree,props);data=ET.tostring(tree)
                dst.writestr(entry,data)
        return result.getvalue()

    def test_actual_sdk_pptx_rejects_subgeometry_unit_and_hidden_gradient_changes(self):
        def reorder(tree,props):
            stops=props.find('a:gradFill/a:gsLst',NS);stops[:]=list(reversed(stops))
        def alpha(tree,props):
            color=props.find('a:gradFill/a:gsLst/a:gs/a:srgbClr',NS)
            ET.SubElement(color,'{'+A+'}alpha',{'val':'99999'})
        def duplicate(tree,props):props.append(deepcopy(props.find('a:gradFill',NS)))
        changes=[
            lambda t,p:p.find('a:gradFill/a:lin',NS).set('ang','5399999'),
            lambda t,p:p.find('a:gradFill/a:lin',NS).set('ang','5400001'),
            lambda t,p:p.find('a:gradFill/a:lin',NS).set('ang','5400000.0'),
            lambda t,p:p.find('a:gradFill/a:gsLst/a:gs',NS).set('pos','1'),
            lambda t,p:p.findall('a:gradFill/a:gsLst/a:gs',NS)[1].set('pos','99999'),
            lambda t,p:p.find('a:gradFill/a:gsLst/a:gs/a:srgbClr',NS).set('val','637F9F'),
            lambda t,p:p.find('a:gradFill',NS).set('rotWithShape','0'),
            lambda t,p:p.remove(p.find('a:gradFill',NS)),reorder,alpha,duplicate]
        for index,change in enumerate(changes):
            with self.subTest(case=index),self.assertRaises(ContractValidationError):
                inspect_native_pptx(self.mutate_pptx(change),self.handoff)

    def test_gradient_text_accepts_exact_stop_units_but_rejects_fractional_units_before_sdk(self):
        selection,inventory=gradient_fixture()
        gradient=inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['fill']
        for offset in (0.00001,0.12345,0.99999):
            gradient['stops']=[GRADIENT['stops'][0],{'offset':offset,'color':'#7890AB'},GRADIENT['stops'][1]]
            self.assertEqual(validate_region_inventory(inventory,selection),inventory)
        for offset in (0.000005,0.1234501,0.999999):
            gradient['stops']=[GRADIENT['stops'][0],{'offset':offset,'color':'#7890AB'},GRADIENT['stops'][1]]
            with self.subTest(offset=offset),self.assertRaisesRegex(ContractValidationError,'CapabilityGap'):
                validate_region_inventory(inventory,selection)

    def test_v3_run_fill_is_exact_in_object_mapping_and_rejects_legacy_version(self):
        selection,inventory=gradient_fixture();regions=inventory['slides'][0]['regions']
        original=deepcopy(regions);objects=objects_for(regions)
        self.assertEqual(validate_faithful_objects(regions,objects,region_version=VERSION),objects)
        self.assertEqual(regions,original)
        for variant in ('color-plus-fill','changed-angle','flattened','bitmap'):
            bad=deepcopy(objects);run=bad[0]['appearance']['runs'][0]
            if variant=='color-plus-fill':run['color']='#637F9E'
            elif variant=='changed-angle':run['fill']['angle']=90.00001
            elif variant=='flattened':run.pop('fill');run['color']='#637F9E'
            else:bad[0]['render_mode']='bitmap'
            with self.subTest(variant=variant),self.assertRaises(ContractValidationError):
                validate_faithful_objects(regions,bad,region_version=VERSION)
        inventory.pop('region_version')
        with self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_region_endpoints_keep_original_paths_and_content_without_inferring_membership(self):
        selection,inventory=container_fixture();before=deepcopy(inventory)
        self.assertEqual(validate_region_inventory(inventory,selection),before)
        regions=inventory['slides'][0]['regions'];objects=objects_for(regions)
        self.assertEqual(validate_faithful_objects(regions,objects,region_version=VERSION),objects)
        self.assertEqual(inventory,before)
        for variant in ('mixed-items','missing-pair','self','relation-endpoint','wrong-image','invisible-shape'):
            bad=deepcopy(inventory);rs=bad['slides'][0]['regions'];binding=rs[-1]['appearance']['relation_binding']
            if variant=='mixed-items':binding.update(from_item_id='title',to_item_id='domain-0')
            elif variant=='missing-pair':binding.pop('to_region_id')
            elif variant=='self':binding['to_region_id']=binding['from_region_id']
            elif variant=='relation-endpoint':binding['to_region_id']='arrow-0'
            elif variant=='wrong-image':binding['target_image_sha256']='9'*64
            else:next(r for r in rs if r['region_id']=='common-bar')['appearance'].update(fill=None,line=None)
            with self.subTest(variant=variant),self.assertRaises(ContractValidationError):validate_region_inventory(bad,selection)

    def test_existing_region_on_another_page_does_not_satisfy_endpoint_and_path_edits_reject(self):
        selection,inventory=container_fixture()
        second=deepcopy(inventory['slides'][0]);second_selection=deepcopy(selection['slides'][0])
        for target in (second['target_binding'],second_selection['target_binding']):
            target.update(slide_id='other',page_order=2)
        next(r for r in second['regions'] if r['region_id']=='common-bar')['region_id']='other-real-bar'
        for region in second['regions'][-4:]:region['appearance']['relation_binding']['from_region_id']='other-real-bar'
        inventory['slides'].append(second);selection['slides'].append(second_selection)
        inventory['slides'][0]['regions'][-1]['appearance']['relation_binding']['from_region_id']='other-real-bar'
        with self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)
        _,clean=container_fixture();regions=clean['slides'][0]['regions'];objects=objects_for(regions)
        objects[-1]['appearance']['paths'][0]['commands'][0]['moveTo']['x']+=0.25
        with self.assertRaises(ContractValidationError):validate_faithful_objects(regions,objects,region_version=VERSION)

if __name__=='__main__':
    with patch.object(subprocess,'Popen',side_effect=AssertionError('subprocess forbidden in independent Native review')), \
         patch.object(urllib.request.OpenerDirector,'open',side_effect=AssertionError('HTTP forbidden in independent Native review')):
        unittest.main(verbosity=2)
