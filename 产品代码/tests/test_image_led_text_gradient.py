"""V3 text fill must survive as editable native run fill, never flattened color."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile
from tests.test_image_led_results import NODE, MODULES, PYTHON, CODE_ROOT
from ai_ppt_studio.application.image_led_results import inspect_native_pptx, preflight_output
from ai_ppt_studio.application.image_led_ooxml import NS, A
import unittest
import xml.etree.ElementTree as ET

from test_image_led_contracts import objects_for, text_style
from test_image_led_native_v3_contracts import VERSION, v3_fixture
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory,validate_faithful_objects
from ai_ppt_studio.application.image_led_results import _text_check
from ai_ppt_studio.errors import ContractValidationError

GRADIENT={'type':'linear-gradient','angle':90,'stops':[
    {'offset':0,'color':'#637F9E'},{'offset':1,'color':'#B4D8F0'}]}


def gradient_fixture():
    selection,inventory=v3_fixture()
    run=inventory['slides'][0]['regions'][0]['appearance']['runs'][0]
    run.pop('color');run['fill']=deepcopy(GRADIENT)
    return selection,inventory


def native_text_body(fill_xml):
    return ET.fromstring('''<p:txBody xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <a:bodyPr wrap="none" tIns="0" rIns="0" bIns="0" lIns="0" anchor="t"><a:noAutofit/></a:bodyPr><a:lstStyle/>
      <a:p><a:pPr algn="l"><a:lnSpc><a:spcPct val="120000"/></a:lnSpc><a:buNone/></a:pPr>
      <a:r><a:rPr sz="1800" b="0" i="0">'''+fill_xml+'''
        <a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:rPr><a:t>12</a:t></a:r></a:p></p:txBody>''')

GRADIENT_XML='''<a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="637F9E"/></a:gs>
    <a:gs pos="100000"><a:srgbClr val="B4D8F0"/></a:gs></a:gsLst><a:lin ang="5400000"/></a:gradFill>'''


class TextGradientContractTests(unittest.TestCase):
    def test_v3_gradient_run_preserves_selected_copy_and_exact_fill(self):
        selection,inventory=gradient_fixture();before=deepcopy(inventory)
        try:result=validate_region_inventory(inventory,selection)
        except ContractValidationError as error:self.fail('Explicit V3 text gradient rejected: '+str(error))
        self.assertEqual(result,before)
        regions=inventory['slides'][0]['regions'];objects=objects_for(regions)
        self.assertEqual(validate_faithful_objects(regions,objects,region_version=VERSION),objects)

    def test_v3_solid_fill_alias_preserves_legacy_color_runs(self):
        selection,inventory=gradient_fixture()
        inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['fill']={'type':'solid','color':'#637F9E'}
        try:self.assertEqual(validate_region_inventory(inventory,selection),inventory)
        except ContractValidationError as error:self.fail('Explicit V3 solid fill rejected: '+str(error))
        old_selection,old_inventory=v3_fixture()
        self.assertEqual(validate_region_inventory(old_inventory,old_selection),old_inventory)

    def test_fill_and_color_are_exclusive_and_v3_only(self):
        for change in (
            lambda i:i['slides'][0]['regions'][0]['appearance']['runs'][0].update(color='#637F9E'),
            lambda i:i['slides'][0]['regions'][0]['appearance']['runs'][0].pop('fill'),
            lambda i:i.pop('region_version'),
        ):
            selection,inventory=gradient_fixture();change(inventory)
            with self.subTest(change=change),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_fill_rejects_missing_nonfinite_or_unsupported_gradient_data(self):
        for fill in (None,{},'blue',{'type':'path-gradient'},
            {**GRADIENT,'angle':float('nan')},{**GRADIENT,'angle':360},
            {**GRADIENT,'stops':[{'offset':0,'color':'#637F9E'}]},
            {**GRADIENT,'stops':[{'offset':0,'color':'#637F9E'},{'offset':True,'color':'#B4D8F0'}]},
            {**GRADIENT,'stops':[{'offset':0,'color':'#637F9E'},{'offset':1,'color':'transparent'}]}):
            selection,inventory=gradient_fixture();inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['fill']=fill
            with self.subTest(fill=fill),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_faithful_objects_cannot_flatten_gradient_to_color_or_change_stop(self):
        _,inventory=gradient_fixture();regions=inventory['slides'][0]['regions'];objects=objects_for(regions)
        for kind in ('solid','stop'):
            bad=deepcopy(objects);run=bad[0]['appearance']['runs'][0]
            if kind=='solid':run.pop('fill');run['color']='#637F9E'
            else:run['fill']['stops'][1]['color']='#B4D8F1'
            with self.subTest(kind=kind),self.assertRaises(ContractValidationError):validate_faithful_objects(regions,bad,region_version=VERSION)

    def test_new_text_stop_must_be_exact_sdk_integer_before_registration(self):
        selection,inventory=gradient_fixture()
        inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['fill']['stops'].insert(
            1,{'offset':0.12345678,'color':'#87A0BC'})
        before=deepcopy(inventory)
        with self.assertRaisesRegex(ContractValidationError,'CapabilityGap'):
            validate_region_inventory(inventory,selection)
        self.assertEqual(inventory,before)

    def test_new_text_stop_accepts_exact_sdk_integer_without_rounding(self):
        selection,inventory=gradient_fixture()
        inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['fill']['stops'].insert(
            1,{'offset':0.12345,'color':'#87A0BC'})
        self.assertEqual(validate_region_inventory(inventory,selection),inventory)


class TextGradientOoxmlTests(unittest.TestCase):
    def style(self):
        value=text_style('12');value['wrap']='none';value['runs'][0].pop('color');value['runs'][0]['fill']=deepcopy(GRADIENT)
        return value

    def test_native_run_gradient_matches_angle_stops_and_text(self):
        try:_text_check(native_text_body(GRADIENT_XML),self.style())
        except ContractValidationError as error:self.fail('Exact editable native text gradient rejected: '+str(error))

    def test_native_run_rejects_color_fallback_and_gradient_tampering(self):
        for raw in ('<a:solidFill><a:srgbClr val="637F9E"/></a:solidFill>',
            GRADIENT_XML.replace('5400000','0'),GRADIENT_XML.replace('5400000','5400001'),
            GRADIENT_XML.replace('B4D8F0','B4D8F1'),GRADIENT_XML.replace('100000','99999'),
            GRADIENT_XML.replace('100000','90000'),GRADIENT_XML.replace('<a:lin ang="5400000"/>','<a:path path="circle"/>'),
            GRADIENT_XML+'<a:solidFill><a:srgbClr val="637F9E"/></a:solidFill>'):
            with self.subTest(raw=raw):
                try:
                    with self.assertRaises(ContractValidationError):_text_check(native_text_body(raw),self.style())
                except KeyError as error:
                    self.fail('Gradient fallback must be rejected by the contract, not a missing old color field: '+str(error))

    def test_legacy_native_solid_text_remains_accepted(self):
        _text_check(native_text_body('<a:solidFill><a:srgbClr val="123456"/></a:solidFill>'),text_style('12'))

    def test_fractional_angle_uses_verified_sdk_integer_units(self):
        style=self.style();style['runs'][0]['fill']['angle']=12.345678
        _text_check(native_text_body(GRADIENT_XML.replace('5400000','740740')),style)
        with self.assertRaises(ContractValidationError):
            _text_check(native_text_body(GRADIENT_XML.replace('5400000','740741')),style)


# Real bundled SDK tests are synthetic capability evidence, never customer-page
# fidelity, PowerPoint-host evidence, or user acceptance.

NATIVE_INCREMENT_RUNNER = r"""
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const code=process.cwd(),root=process.argv[1];
const {render}=await import(pathToFileURL(path.join(code,'scripts/image-led-native.mjs')));
const {nativeV3Handoff}=await import(pathToFileURL(path.join(code,'tests/fixtures/image-led-native-v3.mjs')));
const {digest}=await import(pathToFileURL(path.join(code,'tests/fixtures/image-led-synthetic.mjs')));
const canonical=x=>JSON.stringify(x&&typeof x==='object'?Array.isArray(x)?x.map(v=>JSON.parse(canonical(v))):Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))])):x);
const h=nativeV3Handoff(root),s=h.slides[0];
const gradient={type:'linear-gradient',angle:90,stops:[{offset:0,color:'#637F9E'},{offset:1,color:'#B4D8F0'}]};
const add=(region_id,kind,bbox,appearance,items=[])=>s.regions.push({region_id,kind,bbox,z_order:s.regions.length,content:{items},material_binding:null,appearance});
const style=text=>({runs:[{text,fontFamily:'Arial',fontSize:18,color:'#183A52',bold:false,italic:false}],alignment:'left',verticalAlignment:'top',insets:[0,0,0,0],lineSpacing:1.2,wrap:'none'});
const addText=(id,text,bbox)=>add(id,'text',bbox,style(text),[{item_id:id,kind:'text',role:'body',text}]);
add('common-bar','shape',[40,530,650,40],{geometry:'rect',corner_radius:0,fill:{type:'solid',color:'#CCE4F5'},line:null,shadow:null});
addText('service-audience','Service audience',[55,535,240,30]);
addText('shared-entry','Shared entry',[350,535,240,30]);
for(let n=0;n<4;n++) {
  addText('domain-'+n,'Domain '+n,[40+165*n,620,150,35]);
  const points=[[8,0],[22,0],[22,24],[30,24],[15,40],[0,24],[8,24]];
  add('down-arrow-'+n,'relation-path',[100+165*n,575,30,40],{
    paths:[{width:30,height:40,commands:[{moveTo:{x:points[0][0],y:points[0][1]}},...points.slice(1).map(([x,y])=>({lineTo:{x,y}})),{close:{}}]}],
    fill:{type:'solid',color:'#637F9E'},line:null,
    relation_binding:{origin:'source-image-derived',target_image_sha256:s.target_binding.target_image_sha256,kind:'directed-edge',from_region_id:'common-bar',to_region_id:'domain-'+n,direction:'forward'}
  });
}
addText('page-number','12',[1020,470,200,160]);
const page=s.regions.at(-1);page.appearance.runs[0].fontSize=120;page.appearance.runs[0].bold=true;
delete page.appearance.runs[0].color;page.appearance.runs[0].fill=gradient;
const solid=s.regions.find(r=>r.region_id==='service-audience').appearance.runs[0];
solid.fill={type:'solid',color:solid.color};delete solid.color;
const cell=s.regions.find(r=>r.region_id==='small-table').appearance.cells[0].style.runs[0];
cell.fill=structuredClone(gradient);delete cell.color;
s.selected_copy.items=s.regions.flatMap(r=>structuredClone(r.content.items));
s.target_binding.selected_copy_sha256=digest(canonical(s.selected_copy));
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,render_mode:r.kind==='image'?'bitmap':'native'}));
const before=structuredClone(h);
const result=await render(h,{projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON});
if(canonical(before)!==canonical(h))throw Error('Renderer mutated the frozen handoff');
console.log(JSON.stringify({output:result.pptx_path,result:path.join(h.output_paths.directory,'result.json'),objectCount:s.objects.length}));
"""


def render_increment_fixture(root):
    result = subprocess.run([str(NODE), '--input-type=module', '-e', NATIVE_INCREMENT_RUNNER, str(root)],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=90,
        env={**os.environ, 'C2_RUNTIME_NODE_MODULES':str(MODULES), 'C2_RUNTIME_PYTHON':str(PYTHON)})
    if result.returncode:
        raise AssertionError('Native increment synthetic renderer failed: '+result.stderr)
    result_file = next(root.glob('*/result.json'))
    return (json.loads((result_file.parent/'handoff.json').read_text()), json.loads(result_file.read_text()))


@unittest.skipUnless(NODE.exists() and (MODULES/'@oai/artifact-tool').exists(), 'bundled renderer runtime unavailable')
class NativeIncrementSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-region-gradient-')
        cls.root = Path(cls.directory.name).resolve()
        cls.handoff, cls.output = render_increment_fixture(cls.root)
        cls.raw = Path(cls.output['pptx_path']).read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_result_retains_four_region_paths_and_all_native_objects(self):
        self.assertEqual(preflight_output(self.output,self.handoff,self.root),self.output)
        self.assertEqual(len(inspect_native_pptx(self.raw,self.handoff)),20)
        slide=self.handoff['slides'][0]
        arrows=[o for o in slide['objects'] if o['region_id'].startswith('down-arrow-')]
        self.assertEqual(len(arrows),4)
        for index,arrow in enumerate(arrows):
            self.assertEqual(arrow['appearance']['relation_binding'],{
                'origin':'source-image-derived','target_image_sha256':slide['target_binding']['target_image_sha256'],
                'kind':'directed-edge','from_region_id':'common-bar','to_region_id':'domain-'+str(index),'direction':'forward'})
            self.assertEqual(arrow['render_mode'],'native')
        self.assertEqual(self.output['user_acceptance'],'not-established')
        self.assertEqual(self.output['target_powerpoint'],'not-established')

    def test_export_and_reimport_preserve_editable_text_gradient(self):
        directory=Path(self.output['pptx_path']).parent
        fills=[]
        for filename in ('authoring.proto.json','reimport.proto.json'):
            proto=json.loads((directory/filename).read_text())
            page=next(e for e in proto['slides'][0]['elements'] if e['name']=='o-page-number')
            runs=page['paragraphs'][0]['runs'];self.assertEqual([r['text'] for r in runs],['12'])
            fill=runs[0]['textStyle']['fill'];fills.append(fill)
            self.assertEqual((fill['type'],fill['gradientKind'],fill['angleDeg']),(2,1,90))
            self.assertEqual([(s['position'],s['color']['value']) for s in fill['gradientStops']],
                             [(0,'637F9E'),(100000,'B4D8F0')])
        self.assertEqual(fills[0],fills[1])
        with ZipFile(BytesIO(self.raw)) as z:tree=ET.fromstring(z.read('ppt/slides/slide1.xml'))
        page=next(p for p in tree.findall('.//p:sp',NS) if p.find('p:nvSpPr/p:cNvPr',NS).get('name')=='o-page-number')
        props=page.find('p:txBody/a:p/a:r/a:rPr',NS)
        self.assertEqual(page.findtext('p:txBody/a:p/a:r/a:t','',NS),'12')
        self.assertIsNone(props.find('a:solidFill',NS))
        self.assertEqual(props.find('a:gradFill/a:lin',NS).get('ang'),'5400000')
        self.assertEqual([(s.get('pos'),s[0].get('val')) for s in props.findall('a:gradFill/a:gsLst/a:gs',NS)],
                         [('0','637F9E'),('100000','B4D8F0')])

    def test_actual_pptx_rejects_gradient_flattening_and_stop_angle_changes(self):
        def solid(props):
            props.remove(props.find('a:gradFill',NS))
            node=ET.SubElement(props,'{'+A+'}solidFill')
            ET.SubElement(node,'{'+A+'}srgbClr',{'val':'637F9E'})
        mutations={
            'solid-fallback':solid,
            'angle':lambda p:p.find('a:gradFill/a:lin',NS).set('ang','5400001'),
            'stop-position':lambda p:p.findall('a:gradFill/a:gsLst/a:gs',NS)[1].set('pos','99999'),
            'stop-color':lambda p:p.findall('a:gradFill/a:gsLst/a:gs/a:srgbClr',NS)[1].set('val','B4D8F1'),
        }
        for name,change in mutations.items():
            with self.subTest(name=name):
                result=BytesIO()
                with ZipFile(BytesIO(self.raw)) as src,ZipFile(result,'w') as dst:
                    for entry in src.infolist():
                        raw=src.read(entry.filename)
                        if entry.filename=='ppt/slides/slide1.xml':
                            tree=ET.fromstring(raw)
                            page=next(p for p in tree.findall('.//p:sp',NS) if p.find('p:nvSpPr/p:cNvPr',NS).get('name')=='o-page-number')
                            change(page.find('p:txBody/a:p/a:r/a:rPr',NS));raw=ET.tostring(tree)
                        dst.writestr(entry,raw)
                with self.assertRaises(ContractValidationError):inspect_native_pptx(result.getvalue(),self.handoff)


if __name__ == '__main__':unittest.main()
