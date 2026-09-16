import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {render} from '../scripts/image-led-native.mjs';
import {syntheticHandoff,digest} from './fixtures/image-led-synthetic.mjs';

const nodeModulesRoot=process.env.C2_RUNTIME_NODE_MODULES;

test('real renderer deduplicates export resources without changing authoring images', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-export-isolation-'));
  try {
    const h=syntheticHandoff(root);
    for(const slide of h.slides){
      const region=structuredClone(slide.regions.find(r=>r.kind==='image'));
      region.region_id='independent-second-crop';region.bbox=[500,300,60,120];
      region.z_order=6;region.appearance.crop=[0.5,0,0.5,1];
      slide.regions.push(region);
      slide.objects.push({...structuredClone(region),object_id:'o-independent-second-crop',render_mode:'bitmap'});
    }
    const before=structuredClone(h);
    const requireRuntime=createRequire(path.join(nodeModulesRoot,'__isolation_test__.cjs'));
    const sdk=await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
    let authoring,exportSnapshot,authoringProtoBeforeExport;
    const wrappedSdk={...sdk,Presentation:{
      create(options){authoring=sdk.Presentation.create(options);return authoring;},
      load(proto){
        // This is the real render boundary. toProto itself does not deep-clone
        // imageReference, so pre-fix render changed the captured facade refs.
        authoringProtoBeforeExport=structuredClone(authoring.toProto());
        exportSnapshot=structuredClone(proto);
        return sdk.Presentation.load(proto);
      },
    }};
    const result=await render(h,{projectRoot:root,nodeModulesRoot,
      pythonExecutable:process.env.C2_RUNTIME_PYTHON??'python3',loadSdk:async()=>wrappedSdk});
    assert.deepEqual(h,before,'renderer must not rewrite the finalized input');
    assert.equal(result.mapping.filter(r=>r.kind==='image').length,6);
    assert.equal(exportSnapshot.images.length,1,'same-byte export resources should be shared');
    assert.equal(authoringProtoBeforeExport.images.length,6);
    assert.deepEqual(authoring.toProto(),authoringProtoBeforeExport,'export/import must not alter authoring proto');
    const refs=[];
    for(let i=0;i<h.slides.length;i++){
      const images=authoring.slides.items[i].images.items;
      const objects=h.slides[i].objects.filter(o=>o.kind==='image').sort((a,b)=>a.z_order-b.z_order);
      assert.equal(images.length,objects.length);
      for(let j=0;j<images.length;j++){
        const image=images[j],object=objects[j],a=object.appearance,[x,y,w,hh]=a.crop;
        refs.push(image.referenceId);
        assert.equal(image.alt,object.object_id);
        assert.equal(result.mapping.find(r=>r.slide_id===h.slides[i].target_binding.slide_id&&r.object_id===object.object_id).sdk_id,image.id);
        assert.equal(digest(image.bytes),a.asset_sha256,'original source bytes must remain unchanged');
        assert.deepEqual(Buffer.from(image.bytes),Buffer.from(h.assets[a.asset_ref].data_base64,'base64'));
        assert.equal(image.contentType,h.assets[a.asset_ref].mime_type);
        assert.deepEqual(image.frame,{left:object.bbox[0],top:object.bbox[1],width:object.bbox[2],height:object.bbox[3]});
        assert.deepEqual(image.crop,{left:x,top:y,right:1-x-w,bottom:1-y-hh});
        assert.equal(image.fit,'contain');
        assert.equal(image.lockAspectRatio,j===0);
      }
    }
    assert.equal(new Set(refs).size,6,'deduplicating the export must leave all authoring image resources independent');
    assert.equal(new Set(exportSnapshot.slides.flatMap(s=>s.elements.filter(e=>e.imageReference).map(e=>e.imageReference.id))).size,1);
  } finally {
    await fs.rm(root,{recursive:true,force:true});
  }
});
