import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {replaceImageSource} from '../scripts/image-led-native.mjs';

const nodeModulesRoot=process.env.C2_RUNTIME_NODE_MODULES;
const digest=b=>createHash('sha256').update(b).digest('hex');

test('shared image replacement preserves every other object and source before and after PPTX import', {skip:!nodeModulesRoot}, async()=>{
  const require=createRequire(path.join(nodeModulesRoot,'__replacement__.cjs'));
  const sharp=require('sharp');
  const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-replacement-'));
  const colorA=[[255,0,0],[0,255,0],[0,0,255],[255,255,0]],colorB=[[0,255,255],[255,0,255],[255,255,255],[0,0,0]];
  const strip=async colors=>{
    const raw=Buffer.alloc(400*100*3);
    for(let y=0;y<100;y++)for(let x=0;x<400;x++)for(let c=0;c<3;c++)raw[(y*400+x)*3+c]=colors[Math.floor(x/100)][c];
    return sharp(raw,{raw:{width:400,height:100,channels:3}}).png().toBuffer();
  };
  const a=await strip(colorA),b=await strip(colorB);
  const p=Presentation.create({slideSize:{width:260,height:140}});
  for(let i=0;i<2;i++){
    const s=p.slides.add();
    for(let j=0;j<2;j++){
      const k=i*2+j;
      const im=s.images.add({blob:a,contentType:'image/png',alt:'crop-'+k,position:{left:10+j*120,top:20,width:100,height:100},fit:'contain'});
      im.lockAspectRatio=false;im.crop={left:k/4,top:0,right:(3-k)/4,bottom:0};
    }
  }
  const proto=structuredClone(p.toProto());
  for(const s of proto.slides)for(const e of s.elements)e.imageReference.id=proto.images[0].id;
  proto.images=proto.images.slice(0,1);
  const shared=Presentation.load(proto);
  const roundtrip=async(p,name)=>{
    const file=path.join(root,name+'.pptx');
    await(await PresentationFile.exportPptx(p)).save(file);
    return PresentationFile.importPptx(await FileBlob.load(file));
  };
  try{
    const imported=await roundtrip(shared,'baseline');
    for(const [stage,current] of [['authoring',shared],['reimport',imported]]){
      const before=structuredClone(current.toProto()),s=before.slides[0],target=s.elements[1];
      const request={slideId:s.id,objectId:target.id,expectedSourceSha256:digest(a),bytes:b,contentType:'image/png'};
      const changed=await replaceImageSource(current,request,{nodeModulesRoot});
      assert.deepEqual(current.toProto(),before,'input presentation was mutated');
      const after=structuredClone(changed.toProto()),newRef=after.slides[0].elements[1].imageReference.id;
      assert.notEqual(newRef,target.imageReference.id);
      const expected=structuredClone(before);
      expected.slides[0].elements[1].imageReference.id=newRef;
      if(expected.slides[0].elements[1].fill?.imageReference)expected.slides[0].elements[1].fill.imageReference.id=newRef;
      expected.images.push(after.images.find(x=>x.id===newRef));
      assert.deepEqual(after,expected,'non-target properties or original resources changed');
      assert.equal(digest(after.images.at(-1).data),digest(b));
      const q=await roundtrip(changed,stage+'-replacement');
      const elements=q.slides.items.flatMap(slide=>slide.images.items);
      for(let k=0;k<4;k++){
        assert.equal(digest(elements[k].bytes),digest(k===1?b:a));
        assert.deepEqual(elements[k].crop,{left:k/4,top:0,right:(3-k)/4,bottom:0});
        assert.deepEqual(elements[k].frame,{left:10+(k%2)*120,top:20,width:100,height:100});
        assert.equal(elements[k].lockAspectRatio,false);
      }
      for(let si=0;si<2;si++){
        const png=await(await q.export({slide:q.slides.items[si],format:'png',scale:1})).arrayBuffer();
        const {data,info}=await sharp(Buffer.from(png)).removeAlpha().raw().toBuffer({resolveWithObject:true});
        for(let j=0;j<2;j++){
          const k=si*2+j,at=(70*info.width+60+j*120)*3;
          assert.deepEqual([...data.subarray(at,at+3)],(k===1?colorB:colorA)[k]);
        }
      }
      const badSize=await sharp(b).resize(200,50).png().toBuffer();
      for(const bad of [
        {...request,slideId:'missing'}, {...request,objectId:'missing'},
        {...request,expectedSourceSha256:'f'.repeat(64)}, {...request,bytes:Buffer.from('bad')},
        {...request,bytes:badSize}, {...request,contentType:'image/jpeg'},
      ]){
        await assert.rejects(replaceImageSource(current,bad,{nodeModulesRoot}),/IMAGE_LED_/);
        assert.deepEqual(current.toProto(),before,'failure mutated original presentation');
      }
      // SDK public proto omits some live facade metadata. Refuse to discard it,
      // including when the metadata belongs to an image on another page.
      for(const [si,ii,field,value] of [[0,1,'alt','exact alt'],[1,0,'alt','other page alt'],[0,1,'prompt','source prompt'],[1,0,'prompt','other prompt']]){
        const decorated=Presentation.load(structuredClone(before));
        decorated.slides.items[si].images.items[ii][field]=value;
        const saved=structuredClone(decorated.toProto());
        await assert.rejects(replaceImageSource(decorated,request,{nodeModulesRoot}),/CAPABILITY_GAP/);
        assert.equal(decorated.slides.items[si].images.items[ii][field],value);
        assert.deepEqual(decorated.toProto(),saved);
      }
    }
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
