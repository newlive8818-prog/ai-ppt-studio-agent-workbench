import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { preflight, render } from '../scripts/image-led-native.mjs';
import { nativeV3Handoff } from './fixtures/image-led-native-v3.mjs';

const nodeModulesRoot=process.env.C2_RUNTIME_NODE_MODULES;
const pythonExecutable=process.env.C2_RUNTIME_PYTHON??'python3';
const options=root=>({projectRoot:root,nodeModulesRoot,pythonExecutable});

test('v3 preflight preserves exact copy, wrapped text and source-bound paths without writing', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-native-v3-preflight-'));
  try {
    const h=nativeV3Handoff(root),before=structuredClone(h);
    const p=await preflight(h,options(root));
    assert.deepEqual(p.handoff,before);
    assert.deepEqual(h,before);
    assert.equal(p.handoff.slides[0].objects.filter(o=>o.kind==='relation-path').length,2);
    assert.equal(p.handoff.slides[0].selected_copy.items.some(i=>i.kind==='relation'),false);
    await assert.rejects(fs.stat(h.output_paths.directory),{code:'ENOENT'});
  } finally {await fs.rm(root,{recursive:true,force:true});}
});

test('v3 rejects unsupported versions, geometry, binding and wrapping before SDK/output', async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-native-v3-negative-'));
  try {
    const both=(h,id,change)=>{for(const list of [h.slides[0].regions,h.slides[0].objects]) change(list.find(o=>o.region_id===id));};
    const changes=[
      h=>{h.compiler_version='image-led-faithful-compiler/v2';},
      h=>{delete h.slides[0].region_version;},
      h=>{h.slides[0].region_version='image-led-region-inventory/v2';},
      h=>{h.handoff_version='codex-presentations-image-led/v2';h.compiler_version='image-led-faithful-compiler/v2';},
      h=>both(h,'body-0',r=>{delete r.appearance.wrap;}),
      h=>both(h,'body-0',r=>{r.appearance.wrap='shrinkText';}),
      h=>both(h,'body-0',r=>{r.appearance.autoFit='shrinkText';}),
      h=>both(h,'body-0',r=>{r.appearance.runs[0].text+='\n';}),
      h=>both(h,'directed-path',r=>{r.appearance.paths[0].commands.pop();}),
      h=>both(h,'directed-path',r=>{r.appearance.paths[0].commands[0]={cubicBezTo:{}};}),
      h=>both(h,'directed-path',r=>{r.appearance.relation_binding.target_image_sha256='f'.repeat(64);}),
      h=>both(h,'directed-path',r=>{r.appearance.relation_binding.to_item_id='unknown';}),
      h=>both(h,'polygon-hole',r=>{r.appearance.corner_radius=2;}),
      h=>{h.slides[0].objects.find(r=>r.region_id==='directed-path').render_mode='bitmap';},
      h=>{h.slides[0].objects.find(r=>r.region_id==='directed-path').appearance.paths[0].commands[0].moveTo.x=1;},
    ];
    for(const change of changes) {
      const h=nativeV3Handoff(root);change(h);let loads=0;
      await assert.rejects(render(h,{...options(root),loadSdk:async()=>{loads++;throw Error('unexpected SDK');}}),/IMAGE_LED_/);
      assert.equal(loads,0);
      await assert.rejects(fs.stat(h.output_paths.directory),{code:'ENOENT'});
    }
  } finally {await fs.rm(root,{recursive:true,force:true});}
});

const OOXML_CHECK=String.raw`
import sys,json,zipfile,xml.etree.ElementTree as E
h=json.load(sys.stdin);s=h['slides'][0];ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with zipfile.ZipFile(h['output_paths']['pptx']) as z: xml=E.fromstring(z.read('ppt/slides/slide1.xml'))
shapes={sp.find('p:nvSpPr/p:cNvPr',ns).get('name'):sp for sp in xml.findall('.//p:sp',ns)}
for o in s['objects']:
 if o['kind']=='relation-path' or o['appearance'].get('geometry')=='polygon':
  sp=shapes[o['object_id']];paths=sp.findall('p:spPr/a:custGeom/a:pathLst/a:path',ns)
  assert len(paths)==len(o['appearance']['paths'])
  for actual,expected in zip(paths,o['appearance']['paths']):
   assert actual.attrib=={'w':str(round(expected['width']*9525)),'h':str(round(expected['height']*9525))}
   assert len(actual)==len(expected['commands'])
   for a,c in zip(actual,expected['commands']):
    k=next(iter(c));assert a.tag.rsplit('}',1)[-1]=={'moveTo':'moveTo','lineTo':'lnTo','close':'close'}[k]
    if k!='close':assert a[0].attrib=={t:str(round(c[k][t]*9525)) for t in ('x','y')}
  fill=o['appearance']['fill']
  if fill['type']=='linear-gradient':
   grad=sp.find('p:spPr/a:gradFill',ns);assert grad.find('a:lin',ns).get('ang')==str(round(fill['angle']*60000))
   assert [(g.get('pos'),g[0].get('val')) for g in grad.find('a:gsLst',ns)]==[(str(round(t['offset']*100000)),t['color'][1:]) for t in fill['stops']]
for o in s['objects']:
 if o['kind']=='text':targets=[(shapes[o['object_id']].find('p:txBody',ns),o['appearance'])]
 elif o['kind']=='table':targets=[(xml.find('.//a:tc/a:txBody',ns),o['appearance']['cells'][0]['style'])]
 else:continue
 for tx,a in targets:
  b=tx.find('a:bodyPr',ns);assert b.get('wrap')==a['wrap'];assert b.find('a:noAutofit',ns) is not None
  assert b.find('a:normAutofit',ns) is None and b.find('a:spAutoFit',ns) is None
  assert [t.text for t in tx.findall('.//a:t',ns)]==[r['text'] for r in a['runs']]
  assert len(tx.findall('a:p',ns))==1 and not tx.findall('.//a:br',ns)
  assert [p.get('sz') for p in tx.findall('.//a:r/a:rPr',ns)]==[str(round(r['fontSize']*75)) for r in a['runs']]
print('verified')
`;

test('v3 actual renderer exports native paths, true hole and natural wrapped Unicode without redesign', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-native-v3-render-'));
  try {
    const h=nativeV3Handoff(root),result=await render(h,options(root));
    assert.equal(result.status,'engineering-output-unassessed');
    assert.equal(result.user_acceptance,'not-established');
    assert.deepEqual(JSON.parse(await fs.readFile(path.join(h.output_paths.directory,'handoff.json'),'utf8')),h);
    assert.equal(result.mapping.filter(r=>r.kind==='relation-path').length,2);
    const checked=spawnSync(pythonExecutable,['-c',OOXML_CHECK],{input:JSON.stringify(h),encoding:'utf8',timeout:30000});
    assert.equal(checked.status,0,checked.stderr);
    assert.equal(checked.stdout.trim(),'verified');
    const layout=JSON.parse(await fs.readFile(path.join(h.output_paths.directory,'slide-1.layout.json'),'utf8'));
    const body=layout.elements.find(e=>e.name==='o-body-0');
    assert.equal(body.text,h.slides[0].regions.find(r=>r.region_id==='body-0').content.items[0].text);
    const require=createRequire(path.join(nodeModulesRoot,'__v3_test__.cjs')),sharp=require('sharp');
    const {data,info}=await sharp(result.renders[0].path).removeAlpha().raw().toBuffer({resolveWithObject:true});
    const pixel=(x,y)=>[...data.subarray((y*info.width+x)*info.channels,(y*info.width+x)*info.channels+3)];
    const inkRows=[];
    for(let y=Math.floor(body.position.top);y<Math.ceil(body.position.top+body.position.height);y++) {
      let ink=0;
      for(let x=Math.floor(body.position.left);x<Math.ceil(body.position.left+body.position.width);x++) {
        if(pixel(x,y).some(channel=>channel<245)) ink++;
      }
      if(ink>=4) inkRows.push(y);
    }
    const lineBands=[];
    for(const y of inkRows) {
      if(!lineBands.length||y>lineBands.at(-1).end+1) lineBands.push({start:y,end:y});
      else lineBands.at(-1).end=y;
    }
    assert.ok(lineBands.length>1,`expected naturally wrapped raster text, got ${lineBands.length} ink band(s)`);
    assert.deepEqual(pixel(615,360),[255,255,255]);
    assert.notDeepEqual(pixel(550,360),[255,255,255]);
  } finally {await fs.rm(root,{recursive:true,force:true});}
});
