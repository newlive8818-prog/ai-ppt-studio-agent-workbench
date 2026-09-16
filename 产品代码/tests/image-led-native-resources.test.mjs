import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {render, preflight} from '../scripts/image-led-native.mjs';
import {syntheticHandoff} from './fixtures/image-led-synthetic.mjs';

const nodeModulesRoot=process.env.C2_RUNTIME_NODE_MODULES;
const pythonExecutable=process.env.C2_RUNTIME_PYTHON??'python3';
const options=root=>({projectRoot:root,nodeModulesRoot,pythonExecutable});
const checkPptx=(h,script)=>{
  const result=spawnSync(pythonExecutable,['-c',script],{input:JSON.stringify(h),encoding:'utf8',timeout:30000});
  assert.equal(result.status,0,result.stderr);
};
const header=String.raw`
import sys,json,zipfile,hashlib,xml.etree.ElementTree as E
h=json.load(sys.stdin)
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
z=zipfile.ZipFile(h['output_paths']['pptx'])
`;

test('repeated image crops preserve independent objects without duplicate embedded media', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-resource-'));
  try{
    const h=syntheticHandoff(root);
    for(const s of h.slides){
      const extra=structuredClone(s.regions.find(r=>r.kind==='image'));
      extra.region_id='second-crop';extra.bbox=[500,300,60,120];extra.z_order=6;extra.appearance.crop=[0.5,0,0.5,1];
      s.regions.push(extra);s.objects.push({...structuredClone(extra),object_id:'o-second-crop',render_mode:'bitmap'});
    }
    const before=structuredClone(h),r=await render(h,options(root));
    assert.deepEqual(h,before);
    assert.equal(r.mapping.filter(x=>x.kind==='image').length,6);
    checkPptx(h,header+String.raw`
media=[n for n in z.namelist() if n.startswith('ppt/media/')]
assert len(media)==1, 'same image bytes were embedded once per object: '+str(len(media))
expected=next(a['sha256'] for k,a in h['assets'].items() if k.startswith('artifact://image-led-crop/'))
assert hashlib.sha256(z.read(media[0])).hexdigest()==expected
for i in range(1,4):
 xml=E.fromstring(z.read(f'ppt/slides/slide{i}.xml'));pics=xml.findall('.//p:pic',ns)
 assert len(pics)==2
 byname={p.find('p:nvPicPr/p:cNvPr',ns).get('name'):p for p in pics}
 assert set(byname)=={'o-sample-image','o-second-crop'}
 crop=byname['o-second-crop'].find('p:blipFill/a:srcRect',ns)
 assert crop.get('l')=='50000' and crop.get('r')=='0'
 full=byname['o-sample-image'].find('p:blipFill/a:srcRect',ns)
 assert full is None or all(int(full.get(k,'0'))==0 for k in ('l','t','r','b'))
`);
    const proto=JSON.parse(await fs.readFile(path.join(h.output_paths.directory,'authoring.proto.json'),'utf8'));
    assert.equal(proto.images.length,1);
    assert.equal(r.renders.length,3);
  }finally{await fs.rm(root,{recursive:true,force:true});}
});

test('ellipse omits unsupported rectangle radius while preserving its native geometry', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-ellipse-'));
  try{
    const h=syntheticHandoff(root);h.slides=h.slides.slice(0,1);
    for(const list of [h.slides[0].regions,h.slides[0].objects])list.find(r=>r.region_id==='background').appearance.geometry='ellipse';
    await render(h,options(root));
    checkPptx(h,header+String.raw`
xml=E.fromstring(z.read('ppt/slides/slide1.xml'))
p=next(s for s in xml.findall('.//p:sp',ns) if s.find('p:nvSpPr/p:cNvPr',ns).get('name')=='o-background')
assert p.find('p:spPr/a:prstGeom',ns).get('prst')=='ellipse'
`);
  }finally{await fs.rm(root,{recursive:true,force:true});}
});

test('fractional gradient offsets use the existing truncated OOXML fill units', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-gradient-'));
  try{
    const h=syntheticHandoff(root);h.slides=h.slides.slice(0,1);
    for(const list of [h.slides[0].regions,h.slides[0].objects])list.find(r=>r.region_id==='background').appearance.fill={type:'linear-gradient',angle:0,stops:[{offset:0,color:'#112233'},{offset:0.33666667,color:'#778899'},{offset:1,color:'#ABCDEF'}]};
    await render(h,options(root));
    checkPptx(h,header+String.raw`
xml=E.fromstring(z.read('ppt/slides/slide1.xml'))
p=next(s for s in xml.findall('.//p:sp',ns) if s.find('p:nvSpPr/p:cNvPr',ns).get('name')=='o-background')
assert [n.get('pos') for n in p.findall('p:spPr/a:gradFill/a:gsLst/a:gs',ns)]==['0','33666','100000']
`);
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
