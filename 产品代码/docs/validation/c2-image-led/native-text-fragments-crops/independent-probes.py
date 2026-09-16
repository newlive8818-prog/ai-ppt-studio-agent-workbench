"""Independent frozen-source and actual-PPTX review; synthetic retained artifacts only."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from copy import deepcopy
from io import BytesIO
import base64
import hashlib
import importlib.util
import json
import posixpath
import shutil
import socket
import subprocess
import unicodedata
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image

ROOT=Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
SOURCE=ROOT/'产品代码'; BASE=Path('/private/tmp/c2-text-fragments')
MANIFEST=json.loads((BASE/'package-source-manifest.json').read_text())
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha((BASE/'package-source-manifest.json').read_bytes())=='28bd83b11eb3dab6383cbfd110f295773e226742853a57e58d31617f9d2523a7'
for rel,digest in MANIFEST['files'].items():
    assert sha((BASE/'frozen-source'/rel).read_bytes())==digest
    assert sha((SOURCE/rel).read_bytes())==digest
sys.path[:0]=[str(SOURCE/'src'),str(SOURCE),str(SOURCE/'tests')]
def load_frozen(name,rel):
    spec=importlib.util.spec_from_file_location(name,BASE/'frozen-source'/rel)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
domain=load_frozen('ai_ppt_studio.domains.visual.image_led','src/ai_ppt_studio/domains/visual/image_led.py')
results=load_frozen('ai_ppt_studio.application.image_led_results','src/ai_ppt_studio/application/image_led_results.py')
from ai_ppt_studio.application.image_led_ooxml import NS
from ai_ppt_studio.errors import ContractValidationError
from test_image_led_text_fragments import fragment_fixture,selected_crop_fixture
from test_image_led_contracts import objects_for
SDK=json.loads((BASE/'sdk-evidence-report.json').read_text())
SDKDIR=Path(SDK['pptx']).parent
RAW=Path(SDK['pptx']).read_bytes();assert sha(RAW)=='7f53bf00c14d3735fb7e6a4561d668520200d72005a838cb3617d46485f2f606'
HANDOFF=json.loads((SDKDIR/'handoff.json').read_text());OUTPUT=json.loads((SDKDIR/'result.json').read_text())
ORIGINAL={p.name:sha(p.read_bytes()) for p in SDKDIR.iterdir() if p.is_file()}
MUTANTS=BASE/'independent-mutants';MUTANTS.mkdir(exist_ok=True)
EVIDENCE={'mutations':[],'baseline':{},'mapping_mutations':[],'boundary_rejections':[]}

def node_named(tree,name):
    return next(e for e in tree.find('p:cSld/p:spTree',NS) if any(n.get('name')==name for n in e.findall('.//p:cNvPr',NS)))
def pptx_mutation(name,change):
    output=BytesIO()
    with ZipFile(BytesIO(RAW)) as src,ZipFile(output,'w') as dst:
        for entry in src.infolist():
            raw=src.read(entry.filename)
            if entry.filename=='ppt/slides/slide1.xml':
                tree=ET.fromstring(raw);change(tree);raw=ET.tostring(tree)
            dst.writestr(entry,raw)
    raw=output.getvalue();file=MUTANTS/(name+'.pptx');file.write_bytes(raw)
    try:results.inspect_native_pptx(raw,HANDOFF)
    except ContractValidationError as error:
        EVIDENCE['mutations'].append({'name':name,'path':str(file),'sha256':sha(raw),'reason':str(error),'status':'REJECTED'})
    else:raise AssertionError('Unexpected accepted PPTX mutation: '+name)

def clone_result():
    root=BASE/'independent-result-copy-final';root.mkdir(exist_ok=True)
    directory=root/HANDOFF['task_id']
    assert not directory.exists(), 'independent output must be new'
    shutil.copytree(SDKDIR,directory)
    def remap(value):
        if isinstance(value,str) and value.startswith(str(SDKDIR)):return str(directory)+value[len(str(SDKDIR)):]
        if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        return value
    h=remap(HANDOFF);out=remap(OUTPUT)
    encoded=json.dumps(h,ensure_ascii=False,indent=2).encode();(directory/'handoff.json').write_bytes(encoded)
    out['files']['handoff.json']['sha256']=out['handoff_sha256']=sha(encoded)
    (directory/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    return root,h,out

class FrozenNativeReview(unittest.TestCase):
    def test_frozen_seven_files_match_and_retained_input_unchanged(self):
        for rel,digest in MANIFEST['files'].items():
            self.assertEqual(sha((BASE/'frozen-source'/rel).read_bytes()),digest)
            self.assertEqual(sha((SOURCE/rel).read_bytes()),digest)
        self.assertEqual({p.name:sha(p.read_bytes()) for p in SDKDIR.iterdir() if p.is_file()},ORIGINAL)

    def test_actual_pptx_and_output_gate_then_independent_codepoint_reassembly(self):
        self.assertEqual(results.preflight_output(OUTPUT,HANDOFF,SDKDIR.parent),OUTPUT)
        rows=results.inspect_native_pptx(RAW,HANDOFF)
        fragments=[r for r in rows if 'span' in r]
        self.assertEqual(len(rows),14);self.assertEqual(len(fragments),5)
        with ZipFile(BytesIO(RAW)) as z:
            tree=ET.fromstring(z.read('ppt/slides/slide1.xml'))
            actual=[]
            for row in fragments:
                node=node_named(tree,row['object_id'])
                self.assertEqual(node.tag,'{'+NS['p']+'}sp')
                actual.append(''.join(t.text or '' for t in node.findall('p:txBody/a:p/a:r/a:t',NS)))
            self.assertEqual(''.join(actual),'Headline😀e\u0301|Body  text')
            self.assertEqual(actual[3],'  ')
            self.assertEqual(len(''.join(actual)),22)
            self.assertNotEqual(''.join(actual),unicodedata.normalize('NFC',''.join(actual)))
        EVIDENCE['baseline'].update(native_count=14,fragment_count=5,actual_fragment_text=actual,spans=[r['span'] for r in fragments],pptx_sha256=sha(RAW),preflight_output='PASS')

    def test_actual_crop_rectangles_embedded_target_and_pixels(self):
        s=HANDOFF['slides'][0];target=s['target_binding']; expected={o['object_id']:o for o in s['objects']}
        with ZipFile(BytesIO(RAW)) as z:
            tree=ET.fromstring(z.read('ppt/slides/slide1.xml'))
            rels=ET.fromstring(z.read('ppt/slides/_rels/slide1.xml.rels'))
            refs={r.get('Id'):r.get('Target') for r in rels}
            for name in ['o-sample-image','o-second-crop','o-legacy-decoration']:
                node=node_named(tree,name);obj=expected[name];a=obj['appearance']
                transform=node.find('p:spPr/a:xfrm',NS)
                actual_box=[int(transform.find('a:off',NS).get(k))/9525 for k in ['x','y']]+[int(transform.find('a:ext',NS).get(k))/9525 for k in ['cx','cy']]
                self.assertEqual(actual_box,obj['bbox'])
                crop=node.find('p:blipFill/a:srcRect',NS);x,y,w,h=a['crop']
                self.assertEqual([int(crop.get(k,'0')) for k in ['l','t','r','b']],[round(v*100000) for v in [x,y,1-x-w,1-y-h]])
                blip=node.find('p:blipFill/a:blip',NS);rel=refs[blip.get('{'+NS['r']+'}embed')]
                image_part=rel.lstrip('/') if rel.startswith('/') else posixpath.normpath(posixpath.join('ppt/slides',rel))
                self.assertTrue(image_part.startswith('ppt/media/'))
                self.assertEqual(sha(z.read(image_part)),target['target_image_sha256'])
                if name=='o-legacy-decoration':self.assertNotIn('render_source',a);self.assertIsNone(obj['material_binding'])
                else:self.assertEqual(obj['material_binding'],target['material_roles'][0]);self.assertEqual(a['render_source'],'selected-image-crop')
        with Image.open(OUTPUT['renders'][0]['path']) as image:
            rgb=image.convert('RGB')
            self.assertEqual(rgb.getpixel((1040,390)),(64,176,128))
            self.assertEqual(rgb.getpixel((1160,150)),(48,112,176))
            self.assertEqual(rgb.getpixel((980,615)),(48,112,176))
        EVIDENCE['baseline']['independent_crop_geometry_media_pixels']='PASS'

    def test_actual_unicode_normalization_and_blank_replacement_are_rejected(self):
        def normalize(tree):
            t=node_named(tree,'o-body-0::fragment:0:11').find('p:txBody/a:p/a:r/a:t',NS);t.text=unicodedata.normalize('NFC',t.text)
        pptx_mutation('nfc-normalized-fragment',normalize)
        def nbsp(tree):node_named(tree,'o-body-0::fragment:16:18').find('p:txBody/a:p/a:r/a:t',NS).text='\u00a0\u00a0'
        pptx_mutation('double-space-replaced-with-nbsp',nbsp)

    def test_actual_gradient_and_stack_tampering_are_rejected(self):
        def gradient(tree):node_named(tree,'o-body-0::fragment:0:11').find('.//a:gradFill/a:gsLst/a:gs/a:srgbClr',NS).set('val','AABBCC')
        pptx_mutation('fragment-gradient-color-changed',gradient)
        def reorder(tree):
            parent=tree.find('p:cSld/p:spTree',NS);a=node_named(tree,'o-body-0::fragment:11:12');b=node_named(tree,'o-body-0::fragment:12:16')
            index=list(parent).index(a);parent.remove(b);parent.insert(index,b)
        pptx_mutation('fragment-native-stacking-swapped',reorder)

    def test_actual_same_asset_crops_and_legacy_frame_tampering_are_rejected(self):
        def swap_crop(tree):
            a=node_named(tree,'o-sample-image').find('p:blipFill/a:srcRect',NS);b=node_named(tree,'o-second-crop').find('p:blipFill/a:srcRect',NS)
            old=dict(a.attrib);a.attrib.clear();a.attrib.update(b.attrib);b.attrib.clear();b.attrib.update(old)
        pptx_mutation('same-material-crops-exchanged',swap_crop)
        def move_frame(tree):node_named(tree,'o-legacy-decoration').find('p:spPr/a:xfrm/a:off',NS).set('x',str(901*9525))
        pptx_mutation('ordinary-decoration-frame-moved',move_frame)

    def test_rehashed_mapping_rejects_boolean_span_and_fake_ordinary_span(self):
        root,h,out=clone_result();self.assertEqual(results.preflight_output(out,h,root),out)
        mapping=Path(out['files']['mapping.json']['path']);saved=mapping.read_bytes()
        mutations={
            'boolean-span':lambda rows:next(r for r in rows if 'span' in r)['span'].__setitem__(0,False),
            'ordinary-row-fake-span':lambda rows:next(r for r in rows if r['kind']=='shape').update(span=[0,1]),
            'span-reassigned':lambda rows:next(r for r in rows if 'span' in r)['span'].__setitem__(1,12),
        }
        for name,change in mutations.items():
            bad=deepcopy(out);change(bad['mapping']);raw=json.dumps(bad['mapping']).encode();mapping.write_bytes(raw)
            bad['files']['mapping.json']['sha256']=sha(raw)
            try:
                results.preflight_output(bad,h,root)
            except ContractValidationError as error:
                EVIDENCE['mapping_mutations'].append({'name':name,'rehashed':True,'sha256':sha(raw),'reason':str(error),'status':'REJECTED'})
                (MUTANTS/(name+'.mapping.json')).write_bytes(raw)
            else:self.fail('Mapping mutation accepted: '+name)
            finally:mapping.write_bytes(saved)
        self.assertEqual(mapping.read_bytes(),saved)

    def test_closed_contract_codepoint_type_role_and_identity_boundaries(self):
        for value in ([0.0,4],[0,4.0],[0,True],[0,5]):
            selected,inventory=fragment_fixture();inventory['slides'][0]['regions'][0]['appearance']['fragments'][0]['span']=value
            with self.assertRaises(ContractValidationError):domain.validate_region_inventory(inventory,selected)
        selected,inventory=fragment_fixture();objects=objects_for(inventory['slides'][0]['regions']);objects[1]['object_id']=objects[0]['object_id']+'::fragment:0:4'
        with self.assertRaises(ContractValidationError):domain.validate_faithful_objects(inventory['slides'][0]['regions'],objects,region_version=domain.REGION_VERSION_V3)
        for field,value in [('asset_ref','artifact://image-led-image/'+'1'*64),('asset_sha256','2'*64)]:
            selected,inventory=selected_crop_fixture();inventory['slides'][0]['regions'][-1]['appearance'][field]=value
            with self.assertRaises(ContractValidationError):domain.validate_region_inventory(inventory,selected)
        selected,inventory=selected_crop_fixture();inventory['slides'][0]['regions'][-1]['material_binding']['source_ref']='artifact://material-source/'+'3'*64
        with self.assertRaises(ContractValidationError):domain.validate_region_inventory(inventory,selected)
        EVIDENCE['boundary_rejections']=['floating/bool/UTF16-like spans','expanded object collision','wrong selected asset ref with correct hash','wrong asset hash with correct ref','wrong original source role']

REAL_RUN=subprocess.run
SDK_CALLS=[]
def guarded_run(argv,**kwargs):
    expected_node='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
    expected_script=str(BASE/'frozen-source/scripts/image-led-native.mjs')
    assert len(argv)==6 and argv[0]==expected_node and argv[1:3]==['--input-type=module','-e'] and argv[4]==expected_script and 'verifyOutputSnapshots' in argv[3], 'unexpected process forbidden'
    assert sha(Path(argv[4]).read_bytes())==MANIFEST['files']['scripts/image-led-native.mjs']
    SDK_CALLS.append({'node':argv[0],'script':argv[4],'script_sha256':sha(Path(argv[4]).read_bytes()),'operation':'offline import/render snapshot verification'})
    return REAL_RUN(argv,**kwargs)

if __name__=='__main__':
    with patch.object(socket,'socket',side_effect=AssertionError('network forbidden')) as socket_guard,patch.object(subprocess,'run',side_effect=guarded_run):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrozenNativeReview))
        socket_guard.assert_not_called()
    assert {p.name:sha(p.read_bytes()) for p in SDKDIR.iterdir() if p.is_file()}==ORIGINAL
    for rel,digest in MANIFEST['files'].items():assert sha((SOURCE/rel).read_bytes())==digest
    EVIDENCE.update(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),source_hashes=MANIFEST['files'],retained_original_unchanged=True,sdk_export='NotRun; reused retained real SDK artifact',sdk_reimport_snapshot_verifications=SDK_CALLS,customer_runtime='NotAccessed',network_calls=0,helper_calls=0)
    (BASE/'independent-probe-evidence.json').write_text(json.dumps(EVIDENCE,ensure_ascii=False,indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
