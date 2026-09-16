"""Actual bundled SDK evidence for source-mapped text and selected-image crops."""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from tests.test_image_led_results import NODE,MODULES,PYTHON,CODE_ROOT
from ai_ppt_studio.application.image_led_results import inspect_native_pptx,preflight_output
from ai_ppt_studio.application.image_led_ooxml import NS
from ai_ppt_studio.errors import ContractValidationError

FIXTURE_JS=r"""
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {render} from './scripts/image-led-native.mjs';
import {nativeV3Handoff} from './tests/fixtures/image-led-native-v3.mjs';
import {digest} from './tests/fixtures/image-led-synthetic.mjs';
const root=process.argv[1],h=nativeV3Handoff(root),s=h.slides[0];
const require=createRequire(path.join(process.env.C2_RUNTIME_NODE_MODULES,'__fragment_test__.cjs')),sharp=require('sharp');
const target=await sharp({create:{width:16,height:9,channels:3,background:'#3070B0'}})
  .composite([{input:{create:{width:8,height:9,channels:3,background:'#40B080'}},left:8,top:0}]).png().toBuffer();
s.target_binding.target_image_sha256=digest(target);
h.assets[s.target_binding.target_image_ref]={sha256:digest(target),data_base64:target.toString('base64'),mime_type:'image/png'};
const original=s.regions.find(r=>r.region_id==='sample-image');
const role={atom_id:'original-photo',source_ref:'artifact://material-source/'+'e'.repeat(64),content_sha256:original.appearance.asset_sha256,use:'real-material'};
delete h.assets[original.appearance.asset_ref];s.target_binding.material_roles=[structuredClone(role)];
original.material_binding=structuredClone(role);original.bbox=[960,300,160,180];
original.appearance={asset_ref:s.target_binding.target_image_ref,asset_sha256:s.target_binding.target_image_sha256,crop:[0.5,0,0.5,1],render_source:'selected-image-crop'};
const second=structuredClone(original);second.region_id='second-crop';second.z_order=s.regions.length;second.bbox=[1080,60,160,180];second.appearance.crop=[0,0,0.5,1];s.regions.push(second);
const decoration=structuredClone(original);decoration.region_id='legacy-decoration';decoration.kind='decoration';decoration.z_order=s.regions.length;
decoration.bbox=[900,570,160,90];decoration.material_binding=null;decoration.appearance.crop=[0,0.5,0.5,0.5];delete decoration.appearance.render_source;s.regions.push(decoration);
for(const r of s.regions)if(r.kind==='relation-path')r.appearance.relation_binding.target_image_sha256=s.target_binding.target_image_sha256;
const body=s.regions.find(r=>r.region_id==='body-0'),full='Headline😀e\u0301|Body  text',points=Array.from(full);
const cut=points.indexOf('|');body.content.items[0].text=full;body.bbox=[80,180,430,170];
const style=(text,fontSize)=>({runs:[{text,fontFamily:'Arial',fontSize,color:'#183A52',bold:false,italic:false}],alignment:'left',verticalAlignment:'top',insets:[0,0,0,0],lineSpacing:1.2,wrap:'none'});
body.appearance={fragments:[
  {span:[0,cut],bbox:[125,180,385,65],appearance:style(points.slice(0,cut).join(''),28)},
  {span:[cut,cut+1],bbox:[80,180,40,170],appearance:style('|',120)},
  {span:[cut+1,cut+5],bbox:[125,265,80,75],appearance:style('Body',28)},
  {span:[cut+5,cut+7],bbox:[205,265,25,75],appearance:style('  ',28)},
  {span:[cut+7,points.length],bbox:[230,265,100,75],appearance:style('text',28)},
]};
const run=body.appearance.fragments[0].appearance.runs[0];delete run.color;run.fill={type:'linear-gradient',angle:90,stops:[{offset:0,color:'#637F9E'},{offset:1,color:'#B4D8F0'}]};
const binding=s.regions.find(r=>r.region_id==='directed-path').appearance.relation_binding;
delete binding.from_item_id;delete binding.to_item_id;binding.from_region_id='title-0';binding.to_region_id='body-0';
s.selected_copy.items=s.regions.flatMap(r=>structuredClone(r.content.items));
const canonical=x=>JSON.stringify(x&&typeof x==='object'?Array.isArray(x)?x.map(v=>JSON.parse(canonical(v))):Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))])):x);
s.target_binding.selected_copy_sha256=digest(canonical(s.selected_copy));
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,render_mode:['image','decoration'].includes(r.kind)?'bitmap':'native'}));
const options={projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON};
"""


def run_js(root,ending):
    result=subprocess.run([str(NODE),'--input-type=module','-e',FIXTURE_JS+ending,str(root)],cwd=CODE_ROOT,
        env={**os.environ,'C2_RUNTIME_NODE_MODULES':str(MODULES),'C2_RUNTIME_PYTHON':str(PYTHON)},
        capture_output=True,text=True,timeout=90)
    if result.returncode:raise AssertionError('Source-mapped SDK run failed: '+result.stderr[-4000:])
    return result


def render_source_mapped_fixture(root):
    run_js(root,"const before=structuredClone(h);await render(h,options);assert.deepEqual(h,before);")
    file=next(root.glob('*/result.json'))
    return json.loads((file.parent/'handoff.json').read_text()),json.loads(file.read_text())


@unittest.skipUnless(NODE.exists() and (MODULES/'@oai/artifact-tool').exists(),'bundled runtime unavailable')
class SourceMappedSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='native-source-mapped-');cls.root=Path(cls.directory.name).resolve()
        try:cls.handoff,cls.output=render_source_mapped_fixture(cls.root)
        except Exception:
            cls.directory.cleanup();raise
        cls.raw=Path(cls.output['pptx_path']).read_bytes()

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_native_fragments_and_crops_pass_actual_result_gate(self):
        self.assertEqual(preflight_output(self.output,self.handoff,self.root),self.output)
        evidence=inspect_native_pptx(self.raw,self.handoff)
        self.assertEqual(len(evidence),14)
        rows=[r for r in evidence if r['region_id']=='body-0']
        self.assertEqual([r['span'] for r in rows],[[0,11],[11,12],[12,16],[16,18],[18,22]])
        self.assertEqual([r['object_id'] for r in rows],['o-body-0::fragment:0:11','o-body-0::fragment:11:12',
            'o-body-0::fragment:12:16','o-body-0::fragment:16:18','o-body-0::fragment:18:22'])
        directory=Path(self.output['pptx_path']).parent
        for filename in ['authoring.proto.json','reimport.proto.json']:
            proto=json.loads((directory/filename).read_text())
            bodies=[e for e in proto['slides'][0]['elements'] if e['name'].startswith('o-body-0::fragment:')]
            self.assertEqual(len(bodies),5)
            self.assertEqual(''.join(r['text'] for e in bodies for p in e['paragraphs'] for r in p['runs']),'Headline😀e\u0301|Body  text')
            self.assertEqual(bodies[3]['paragraphs'][0]['runs'][0]['text'],'  ')
            self.assertEqual(bodies[0]['paragraphs'][0]['runs'][0]['textStyle']['fill']['angleDeg'],90)
        self.assertEqual(self.output['user_acceptance'],'not-established')

    def test_selected_crop_pixels_and_embedded_bytes_are_from_exact_selected_image(self):
        run_js(self.root,"""
const result=JSON.parse(await fs.readFile(path.join(h.output_paths.directory,'result.json'),'utf8'));
const {data,info}=await sharp(result.renders[0].path).removeAlpha().raw().toBuffer({resolveWithObject:true});
const pixel=(x,y)=>[...data.subarray((y*info.width+x)*info.channels,(y*info.width+x)*info.channels+3)];
assert.deepEqual(pixel(1040,390),[64,176,128]);assert.deepEqual(pixel(1160,150),[48,112,176]);
""")
        # The original role hash is untouched while the full selected PNG is embedded.
        photo=next(o for o in self.handoff['slides'][0]['objects'] if o['region_id']=='sample-image')
        self.assertNotEqual(photo['material_binding']['content_sha256'],photo['appearance']['asset_sha256'])
        self.assertEqual(photo['material_binding'],self.handoff['slides'][0]['target_binding']['material_roles'][0])

    def test_legacy_partial_decoration_preserves_explicit_crop_and_frame(self):
        self.assertEqual(len(inspect_native_pptx(self.raw,self.handoff)),14)
        run_js(self.root,"""
const result=JSON.parse(await fs.readFile(path.join(h.output_paths.directory,'result.json'),'utf8'));
const {data,info}=await sharp(result.renders[0].path).removeAlpha().raw().toBuffer({resolveWithObject:true});
const pixel=[...data.subarray((615*info.width+980)*info.channels,(615*info.width+980)*info.channels+3)];
assert.deepEqual(pixel,[48,112,176]);
""")

    def mutate(self,change):
        target=BytesIO()
        with ZipFile(BytesIO(self.raw)) as src,ZipFile(target,'w') as dst:
            for entry in src.infolist():
                raw=src.read(entry.filename)
                if entry.filename=='ppt/slides/slide1.xml':
                    tree=ET.fromstring(raw);change(tree);raw=ET.tostring(tree)
                dst.writestr(entry,raw)
        return target.getvalue()

    def test_actual_pptx_rejects_missing_duplicate_hidden_reworded_and_moved_fragments(self):
        def fragment(tree):return next(s for s in tree.findall('.//p:sp',NS) if s.find('p:nvSpPr/p:cNvPr',NS).get('name')=='o-body-0::fragment:11:12')
        changes={
            'missing':lambda t:t.find('p:cSld/p:spTree',NS).remove(fragment(t)),
            'duplicate':lambda t:t.find('p:cSld/p:spTree',NS).append(deepcopy(fragment(t))),
            'hidden':lambda t:fragment(t).find('p:nvSpPr/p:cNvPr',NS).set('hidden','1'),
            'text':lambda t:setattr(fragment(t).find('p:txBody/a:p/a:r/a:t',NS),'text',''),
            'moved':lambda t:fragment(t).find('p:spPr/a:xfrm/a:off',NS).set('x','1'),
            'identity':lambda t:fragment(t).find('p:nvSpPr/p:cNvPr',NS).set('name','o-body-0::fragment:11:13'),
            'crop':lambda t:t.find('.//p:pic/p:blipFill/a:srcRect',NS).set('l','0'),
        }
        for name,change in changes.items():
            with self.subTest(name=name),self.assertRaises(ContractValidationError):inspect_native_pptx(self.mutate(change),self.handoff)

    def test_mapping_cannot_omit_duplicate_or_relabel_fragment_span(self):
        for change in [lambda rows:rows.pop(2),lambda rows:rows.append(deepcopy(rows[2])),lambda rows:rows.__setitem__(2,None),
                       lambda rows:next(r for r in rows if 'span' in r)['span'].__setitem__(1,12),
                       lambda rows:next(r for r in rows if 'span' in r)['span'].__setitem__(0,False)]:
            payload=deepcopy(self.output);change(payload['mapping'])
            file=Path(payload['files']['mapping.json']['path']);before=file.read_bytes()
            raw=json.dumps(payload['mapping']).encode();file.write_bytes(raw)
            payload['files']['mapping.json']['sha256']=hashlib.sha256(raw).hexdigest()
            try:
                with self.subTest(change=change),self.assertRaises(ContractValidationError):preflight_output(payload,self.handoff,self.root)
            finally:file.write_bytes(before)

    def test_actual_embedded_selected_image_cannot_be_replaced(self):
        target=BytesIO();changed=False
        with ZipFile(BytesIO(self.raw)) as src,ZipFile(target,'w') as dst:
            for entry in src.infolist():
                raw=src.read(entry.filename)
                if entry.filename.startswith('ppt/media/'):
                    raw=raw[:-1]+bytes([raw[-1]^1]);changed=True
                dst.writestr(entry,raw)
        self.assertTrue(changed)
        with self.assertRaises(ContractValidationError):inspect_native_pptx(target.getvalue(),self.handoff)

    def test_invalid_fragment_or_selected_crop_fails_before_sdk_or_output(self):
        with tempfile.TemporaryDirectory(prefix='source-map-preflight-') as folder:
            run_js(Path(folder).resolve(),"""
for(const change of [
  x=>x.appearance.fragments[1].span=[12,13],
  x=>x.appearance.fragments[1].appearance.runs[0].text='',
]){
 const value=structuredClone(h);for(const key of ['regions','objects'])change(value.slides[0][key].find(o=>o.region_id==='body-0'));
 let loads=0;await assert.rejects(render(value,{...options,loadSdk:async()=>{loads++;throw Error('unexpected SDK');}}),/IMAGE_LED_/);
 assert.equal(loads,0);await assert.rejects(fs.stat(value.output_paths.directory),{code:'ENOENT'});
}
const value=structuredClone(h);for(const key of ['regions','objects'])value.slides[0][key].find(o=>o.region_id==='sample-image').appearance.asset_ref='artifact://image-led-crop/'+'f'.repeat(64);
let loads=0;await assert.rejects(render(value,{...options,loadSdk:async()=>{loads++;throw Error('unexpected SDK');}}),/IMAGE_LED_/);
assert.equal(loads,0);await assert.rejects(fs.stat(value.output_paths.directory),{code:'ENOENT'});
""")


if __name__=='__main__':unittest.main()
