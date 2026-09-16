/** Data-only faithful native renderer. Preflight never writes. No approval/fidelity claims. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createHash, randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { loadNativeFonts } from './image-led-fonts.mjs';

const SOURCE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');
const H_KEYS = ['handoff_version','compiler_version','project_id','selection_ref','region_inventory_ref','plan_ref','task_id','slides','assets','output_paths'];
const D_KEYS = ['handoff_version','compiler_version','purpose','diagnostic_ref','project_id','selection_ref','region_inventory_ref','task_id','slides','assets','output_paths'];
const sha = x => createHash('sha256').update(x).digest('hex');
const fail = (message, code = 'CONTRACT') => { throw new Error('IMAGE_LED_' + code + ': ' + message); };
const check = (condition, message) => { if (!condition) fail(message); };
const closed = (x, keys, name) => check(x && typeof x === 'object' && !Array.isArray(x) &&
  Object.keys(x).sort().join('\0') === [...keys].sort().join('\0'), name + ' schema is not closed');
const ref = (x, kind) => check(typeof x === 'string' && new RegExp('^artifact://' + kind + '/[0-9a-f]{64}$').test(x), 'Invalid '+kind+' ref');
const hash = x => check(typeof x === 'string' && /^[0-9a-f]{64}$/.test(x), 'Invalid SHA-256');
const position = b => ({ left:b[0],top:b[1],width:b[2],height:b[3] });
function runtimeRequire(options) {
  const modules = options.nodeModulesRoot ?? process.env.C2_RUNTIME_NODE_MODULES;
  if (!modules || !path.isAbsolute(modules)) fail('Absolute bundled nodeModulesRoot is required','CAPABILITY_GAP');
  return createRequire(path.join(modules,'__image_led_runtime__.cjs'));
}
async function paths(h, options) {
  closed(h.output_paths,['directory','pptx'],'output_paths');
  const root = options.projectRoot, {directory,pptx} = h.output_paths;
  check(typeof root === 'string' && path.isAbsolute(root),'Trusted absolute projectRoot required');
  for (const p of [directory,pptx]) {
    check(typeof p === 'string' && path.isAbsolute(p) && path.resolve(p) === p,'Output path must be canonical absolute');
    const rel = path.relative(root,p);
    check(rel && rel !== '..' && !rel.startsWith('../') && !path.isAbsolute(rel),'Output escaped projectRoot');
  }
  check(path.dirname(pptx) === directory && path.extname(pptx) === '.pptx','PPTX must be directly inside its new directory');
  check(path.relative(root,directory).split(path.sep).includes(h.task_id),'Output directory must contain exact task_id');
  const rootReal = await fs.realpath(root);
  let current = root;
  for (const part of path.relative(root,path.dirname(directory)).split(path.sep).filter(Boolean)) {
    current = path.join(current,part);
    const stat = await fs.lstat(current);
    check(!stat.isSymbolicLink() && stat.isDirectory(),'Output parent must be an existing real directory');
  }
  const parent = await fs.realpath(path.dirname(directory));
  check(parent === rootReal || parent.startsWith(rootReal+path.sep),'Output parent escaped physical projectRoot');
  try { await fs.lstat(directory); fail('Output directory already exists'); }
  catch (e) { if (e.code !== 'ENOENT') throw e; }
}
const DOMAIN_SCRIPT = [
  'import json,sys',
  'from ai_ppt_studio.domains.visual.image_led import validate_region_inventory,validate_faithful_objects,handoff_selected_copy',
  'h=json.load(sys.stdin)',
  'diagnostic=h["handoff_version"]=="codex-presentations-image-led-diagnostic/v1"',
  'if diagnostic:',
  ' for s in h["slides"]: validate_faithful_objects(s["regions"],s["objects"],region_version=s.get("region_version"))',
  ' print("validated")',
  ' raise SystemExit(0)',
  'v3=h["handoff_version"]=="codex-presentations-image-led/v3"',
  'selection={"project_id":h["project_id"],"slides":[]}',
  'inventory={"artifact_type":"image-led-region-inventory","selection_ref":h["selection_ref"],"project_id":h["project_id"],"slides":[]}',
  'if v3: inventory["region_version"]=h["slides"][0]["region_version"]',
  'for s in h["slides"]:',
  ' copy=handoff_selected_copy(s,h["handoff_version"])',
  ' selection["slides"].append({"target_binding":s["target_binding"],"selected_copy":copy})',
  ' inventory["slides"].append({k:s[k] for k in ("target_binding","canvas","source_image_size","regions")})',
  'validate_region_inventory(inventory,selection,selection_ref=h["selection_ref"])',
  'for s in h["slides"]: validate_faithful_objects(s["regions"],s["objects"],region_version=s["region_version"] if v3 else None)',
  'print("validated")',
].join('\n');
function domain(h, options) {
  const r=spawnSync(options.pythonExecutable??process.env.C2_RUNTIME_PYTHON??'python3',['-c',DOMAIN_SCRIPT],{
    input:JSON.stringify(h),encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024,
    env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:SOURCE_ROOT},
  });
  if(r.error || r.status!==0 || r.stdout.trim()!=='validated') fail('Domain preflight rejected: '+(r.stderr||r.error?.message||'invalid response').slice(-1800));
}
function exactSide(point,o) {
  if(!o || !['text','shape'].includes(o.kind) || (o.kind==='shape' && o.appearance.geometry!=='rect')) return null;
  const [x,y,w,h]=o.bbox, sites={top:[x+w/2,y],right:[x+w,y+h/2],bottom:[x+w/2,y+h],left:[x,y+h/2]};
  return Object.keys(sites).find(k=>sites[k][0]===point[0] && sites[k][1]===point[1])??null;
}
function support(h,fonts) {
  const used=new Set();
  for(const s of h.slides) {
    const byRegion=new Map(s.objects.map(o=>[o.region_id,o]));
    for(const o of s.objects) {
      const a=o.appearance, styles=o.kind==='text'?(a.fragments?a.fragments.map(f=>f.appearance):[a]):o.kind==='table'?a.cells.map(c=>c.style):[];
      for(const style of styles) for(const run of style.runs) {
        used.add(run.fontFamily);
        if(!fonts.has(run.fontFamily)) fail('Exact font unavailable: '+run.fontFamily,'CAPABILITY_GAP');
      }
      // This SDK exports shadows through inherited theme effectRef styles.
      // That carrier is not independently verified by the current result gate.
      if(o.kind==='shape' && a.shadow!==null)
        fail('Native shadow requires unsupported theme effect verification','CAPABILITY_GAP');
      if(o.kind==='connector') {
        if(!exactSide(a.start,byRegion.get(a.from_region_id)) || !exactSide(a.end,byRegion.get(a.to_region_id)))
          fail('Connector requires exact supported native connection sites','CAPABILITY_GAP');
        const b=[Math.min(a.start[0],a.end[0]),Math.min(a.start[1],a.end[1]),Math.abs(a.end[0]-a.start[0]),Math.abs(a.end[1]-a.start[1])];
        if(!b.every((v,i)=>v===o.bbox[i])) fail('Connector bbox differs from exact endpoint bounds','CAPABILITY_GAP');
      }
    }
  }
  return [...used];
}
export async function preflight(input,options={}) {
  const h=structuredClone(input);
  const diagnostic=h.handoff_version==='codex-presentations-image-led-diagnostic/v1';
  closed(h,diagnostic?D_KEYS:H_KEYS,diagnostic?'diagnostic handoff':'handoff');
  if(diagnostic){
    check(h.compiler_version==='image-led-diagnostic-compiler/v1'&&h.purpose==='region-diagnostic','Invalid diagnostic identity');
    ref(h.diagnostic_ref,'image-led-native-diagnostic-input');
  }
  const v2=h.handoff_version==='codex-presentations-image-led/v2';
  const v3=h.handoff_version==='codex-presentations-image-led/v3';
  check((v3 && h.compiler_version==='image-led-faithful-compiler/v3') ||
    (v2 && h.compiler_version==='image-led-faithful-compiler/v2') ||
    (diagnostic || (h.handoff_version==='codex-presentations-image-led/v1' && h.compiler_version==='image-led-faithful-compiler/v1')),'Unsupported version');
  hash(h.task_id); ref(h.selection_ref,'image-led-selection'); ref(h.region_inventory_ref,'image-led-region-inventory'); if(!diagnostic) ref(h.plan_ref,'visual-compilation-plan');
  check(Array.isArray(h.slides)&&h.slides.length>0,'Missing slides');
  for(const s of h.slides) {
    closed(s,['target_binding','canvas','source_image_size','regions','objects',...(diagnostic?['selected_copy','region_version']:(v2||v3?['selected_copy']:[])),...(v3&&!diagnostic?['region_version']:[])],'slide');
    if(v3) check(s.region_version==='image-led-region-inventory/v3','Unsupported region version');
  }
  await paths(h,options); domain(h,options);
  const first=h.slides[0].canvas;
  check(h.slides.every(s=>s.canvas.width===first.width&&s.canvas.height===first.height),'Deck canvas mismatch');
  check(h.assets&&typeof h.assets==='object'&&!Array.isArray(h.assets),'Invalid assets');
  const used=new Set(),assetBytes=new Map(),imageSizes=new Map();
  for(const s of h.slides) {
    used.add(s.target_binding.target_image_ref);
    for(const o of s.objects) if(['image','decoration'].includes(o.kind)) used.add(o.appearance.asset_ref);
  }
  check(Object.keys(h.assets).every(k=>used.has(k)),'Unused assets in handoff');
  for(const key of used) {
    const a=h.assets[key]; closed(a,['sha256','data_base64','mime_type'],'asset'); hash(a.sha256);
    check(['image/png','image/jpeg'].includes(a.mime_type),'Unsupported image MIME');
    check(typeof a.data_base64==='string'&&/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(a.data_base64),'Invalid base64');
    const bytes=Buffer.from(a.data_base64,'base64');
    check(bytes.length>0&&sha(bytes)===a.sha256,'Actual asset bytes hash mismatch'); assetBytes.set(key,bytes);
  }
  const requireRuntime=runtimeRequire(options),sharp=requireRuntime('sharp');
  for(const [key,bytes] of assetBytes) {
    const decoder=sharp(bytes,{failOn:'error'}), m=await decoder.metadata().catch(e=>fail('Image cannot decode: '+e.message));
    check((m.format==='png'?'image/png':m.format==='jpeg'?'image/jpeg':'')===h.assets[key].mime_type,'Image MIME differs from bytes');
    check((m.pages??1)===1&&!m.orientation,'Animated/oriented images unsupported');
    await decoder.raw().toBuffer().catch(e=>fail('Image pixel decode failed: '+e.message));
    imageSizes.set(key,{width:m.width,height:m.height});
  }
  for(const s of h.slides) {
    const t=s.target_binding,size=imageSizes.get(t.target_image_ref);
    check(h.assets[t.target_image_ref].sha256===t.target_image_sha256,'Target image hash mismatch');
    check(size.width===s.source_image_size.width&&size.height===s.source_image_size.height,'Target dimensions mismatch');
    for(const o of s.objects) if(['image','decoration'].includes(o.kind)) {
      const a=o.appearance,size=imageSizes.get(a.asset_ref);
      if(a.render_source==='selected-image-crop')
        check(a.asset_ref===t.target_image_ref&&a.asset_sha256===t.target_image_sha256,'Selected crop differs from current target');
      check(h.assets[a.asset_ref].sha256===a.asset_sha256,'Object asset hash mismatch');
      if(Math.abs(size.width*a.crop[2]/(size.height*a.crop[3])-o.bbox[2]/o.bbox[3])>1e-12)
        fail('Image crop requires additional cropping or stretching','CAPABILITY_GAP');
    }
  }
  const sdkRequire=createRequire(requireRuntime.resolve('@oai/artifact-tool'));
  const {FontLibrary}=sdkRequire('skia-canvas');
  const fontEvidence=await loadNativeFonts(options);
  const fontFamilies=support(h,new Set(FontLibrary.families));
  return {handoff:h,assetBytes,imageSizes,fontFamilies,fontEvidence,handoff_sha256:sha(JSON.stringify(h))};
}
function fill(a) {
  if(a===null)return 'none';
  if(a.type==='solid')return a.color;
  // Match the existing result verifier's truncated integer OOXML stop units.
  return {type:'gradient',gradientKind:'linear',angleDeg:a.angle,stops:a.stops.map(s=>({offset:Math.trunc(s.offset*100000),color:s.color}))};
}
const line=a=>a===null?{style:'solid',fill:'none',width:0}:{style:{solid:'solid',dash:'dashed',dot:'dotted'}[a.dash],fill:a.color,width:a.width};

/** Copy-on-write source replacement for an exact SDK image object. This returns
 * a new presentation; callers must submit it through the normal binding/review
 * lifecycle. It cannot amend an approved result or its immutable source image.
 * Direct SDK image.replace() is unsafe for shared assets, including after import.
 */
export async function replaceImageSource(presentation,input,options={}) {
  closed(input,['slideId','objectId','expectedSourceSha256','bytes','contentType'],'image replacement');
  check(typeof input.slideId==='string'&&input.slideId.length>0&&typeof input.objectId==='string'&&input.objectId.length>0,'Exact slide and object ids required');
  hash(input.expectedSourceSha256);
  check(input.bytes instanceof Uint8Array&&input.bytes.length>0,'Replacement needs actual embedded bytes');
  check(['image/png','image/jpeg'].includes(input.contentType),'Unsupported replacement MIME');
  // toProto shares nested references with live SDK facades: deep isolation is
  // required before changing even a single imageReference.
  const proto=structuredClone(presentation.toProto());
  const slides=proto.slides.filter(s=>s.id===input.slideId);
  check(slides.length===1,'Replacement slide identity is missing or ambiguous');
  const elements=slides[0].elements.filter(e=>e.id===input.objectId);
  check(elements.length===1&&elements[0].imageReference,'Replacement image identity is missing or ambiguous');
  const target=elements[0],oldId=target.imageReference.id;
  const assets=proto.images.filter(a=>a.id===oldId);
  check(assets.length===1&&assets[0].data instanceof Uint8Array&&assets[0].data.length>0&&!assets[0].uri,'Replacement source is missing or ambiguous');
  const source=assets[0];
  check(sha(source.data)===input.expectedSourceSha256,'Replacement source identity changed');
  if(target.fill?.imageReference)check(target.fill.imageReference.id===oldId,'Replacement picture fill identity differs');
  const bytes=new Uint8Array(input.bytes),sharp=runtimeRequire(options)('sharp');
  const decode=async(data,mime)=>{
    try{
      const decoder=sharp(data,{failOn:'error'}),m=await decoder.metadata();
      check((m.format==='png'?'image/png':m.format==='jpeg'?'image/jpeg':'')===mime,'Replacement image MIME differs from bytes');
      check((m.pages??1)===1&&!m.orientation,'Animated/oriented replacement unsupported');
      await decoder.raw().toBuffer();return m;
    }catch(error){fail('Replacement image cannot decode: '+error.message);}
  };
  const previous=await decode(source.data,source.contentType),next=await decode(bytes,input.contentType);
  check(previous.width===next.width&&previous.height===next.height,'Replacement dimensions would change crop semantics');
  let id;do{id=randomUUID();}while(proto.images.some(a=>a.id===id));
  proto.images.push({id,contentType:input.contentType,data:bytes});
  target.imageReference.id=id;
  // PPTX import carries the same reference in picture fill as well.
  if(target.fill?.imageReference)target.fill.imageReference.id=id;
  const {Presentation}=await import(pathToFileURL(runtimeRequire(options).resolve('@oai/artifact-tool')).href);
  const replacement=Presentation.load(proto);
  // Some live SDK facade metadata is absent from its public proto. Refuse such
  // lossy round trips on any image, including unchanged images on other pages.
  const properties=['alt','prompt','borderRadius','geometry','crop','frame','fit','lockAspectRatio','rotation','flipHorizontal','flipVertical'];
  for(const slide of presentation.slides.items){
    const nextSlides=replacement.slides.items.filter(s=>s.id===slide.id);
    check(nextSlides.length===1,'Replacement lost slide identity');
    const nextImages=nextSlides[0].images.items;
    check(nextImages.length===slide.images.items.length,'Replacement changed image count');
    for(const image of slide.images.items){
      const matches=nextImages.filter(i=>i.id===image.id);
      check(matches.length===1,'Replacement lost image identity');
      for(const key of properties)if(!isDeepStrictEqual(image[key],matches[0][key]))
        fail('SDK proto cannot preserve image property: '+key,'CAPABILITY_GAP');
    }
  }
  return replacement;
}

function text(target,a) {
  target.set([a.runs.map(r=>({run:r.text,textStyle:{typeface:r.fontFamily,fontSize:r.fontSize+'px',
    ...(Object.hasOwn(r,'fill')?{fill:fill(r.fill)}:{color:r.color}),bold:r.bold,italic:r.italic,
    ...(Object.hasOwn(r,'characterSpacing')?{characterSpacing:r.characterSpacing}:{}),
    ...(Object.hasOwn(r,'outline')?{outline:{style:'solid',fill:r.outline.color,width:r.outline.width}}:{})}}))]);
  target.style={alignment:a.alignment,verticalAlignment:a.verticalAlignment,autoFit:'none',wrap:a.wrap??'none',lineSpacing:a.lineSpacing,
    insets:Object.fromEntries(['top','right','bottom','left'].map((k,i)=>[k,a.insets[i]]))};
}
function nativeObjects(objects) {
  return [...objects].sort((a,b)=>a.z_order-b.z_order).flatMap(o=>{
    if(o.kind!=='text'||!o.appearance.fragments)return [o];
    const source=Array.from(o.content.items[0].text); // Unicode codepoints, never UTF-16 offsets.
    return o.appearance.fragments.map(f=>{
      const [start,end]=f.span;
      check(f.appearance.runs.map(r=>r.text).join('')===source.slice(start,end).join(''),'Fragment differs from original source span');
      return {...o,object_id:o.object_id+'::fragment:'+start+':'+end,span:f.span,bbox:f.bbox,appearance:f.appearance};
    });
  });
}
function add(slide,o,p,facades) {
  const a=o.appearance; let f;
  if(o.kind==='text') {
    f=slide.shapes.add({geometry:'textbox',name:o.object_id,position:position(o.bbox),fill:'none',line:line(null)}); text(f.text,a);
  } else if(o.kind==='shape') {
    f=slide.shapes.add({geometry:a.geometry==='polygon'?'custom':a.geometry==='round-rect'?'roundRect':a.geometry,name:o.object_id,position:position(o.bbox),
      ...(a.geometry==='polygon'?{customPaths:a.paths}:a.geometry==='round-rect'?{borderRadius:a.corner_radius}:{}),
      fill:fill(a.fill),line:line(a.line),
      shadow:a.shadow===null?'shadow-none':a.shadow.offset_x+'px '+a.shadow.offset_y+'px '+a.shadow.blur+'px '+a.shadow.color+'/'+a.shadow.opacity*100});
  } else if(o.kind==='relation-path') {
    // Preserve the frozen contours and winding; never infer an arrow or layout.
    f=slide.shapes.add({geometry:'custom',name:o.object_id,position:position(o.bbox),
      customPaths:a.paths,fill:fill(a.fill),line:line(a.line)});
  } else if(['image','decoration'].includes(o.kind)) {
    const [x,y,w,h]=a.crop;
    f=slide.images.add({blob:new Uint8Array(p.assetBytes.get(a.asset_ref)),contentType:p.handoff.assets[a.asset_ref].mime_type,
      alt:o.object_id,fit:'contain',position:position(o.bbox),crop:{left:x,top:y,right:1-x-w,bottom:1-y-h}});
    // SDK automatic aspect fitting rewrites the frame/crop from the full image.
    // Preflight already proves the selected crop aspect equals this exact bbox.
    if(a.render_source==='selected-image-crop'||x!==0||y!==0||w!==1||h!==1)f.lockAspectRatio=false;
  } else if(o.kind==='table') {
    f=slide.tables.add({rows:a.row_heights.length,columns:a.column_widths.length,left:o.bbox[0],top:o.bbox[1],width:o.bbox[2],height:o.bbox[3],
      columnWidths:a.column_widths,values:a.row_heights.map(()=>a.column_widths.map(()=>''))});
    f.styleOptions={headerRow:false,totalRow:false,firstColumn:false,lastColumn:false,bandedRows:false,bandedColumns:false};
    f.borders.assign({fill:'none',width:0,style:'solid'});
    a.row_heights.forEach((height,i)=>{f.rows[i].height=height;});
    for(const c of a.cells){
      const target=f.getCell(c.row,c.column);target.fill='none';text(target.text,c.style);
      // Native table cells have their own margins/anchor in addition to txBody.
      f.cells.block({row:c.row,column:c.column,rowCount:1,columnCount:1}).assign({
        margins:Object.fromEntries(['top','right','bottom','left'].map((k,i)=>[k,c.style.insets[i]])),
        anchor:c.style.verticalAlignment,
      });
    }
  } else if(o.kind==='connector') {
    const byRegion=new Map(p.currentSlide.objects.map(x=>[x.region_id,x]));
    check(facades.has(a.from_region_id)&&facades.has(a.to_region_id),'Unresolved connector endpoints');
    f=slide.shapes.connect(facades.get(a.from_region_id),facades.get(a.to_region_id),{
      kind:'straight',fromSide:exactSide(a.start,byRegion.get(a.from_region_id)),toSide:exactSide(a.end,byRegion.get(a.to_region_id)),line:line(a.line),
      head:{type:['backward','both'].includes(a.arrow)?'triangle':'none',width:'med',length:'med'},
      tail:{type:['forward','both'].includes(a.arrow)?'triangle':'none',width:'med',length:'med'},
    });
  } else fail('Unsupported object kind','CAPABILITY_GAP');
  f.zIndex=o.z_order;
  if(!Object.hasOwn(o,'span'))facades.set(o.region_id,f);
  return f;
}
async function comparisonBytes(data,targetImage,png,sharp) {
  const {width,height}=data.canvas;
  const target=await sharp(targetImage).resize(width,height,{fit:'fill'}).toColourspace('srgb').removeAlpha().raw().toBuffer();
  const native=await sharp(png).toColourspace('srgb').removeAlpha().raw().toBuffer();
  check(target.length===width*height*3&&native.length===target.length,'Comparison dimensions changed');
  const side=await sharp({create:{width:width*2,height,channels:3,background:'#ffffff'}})
    .composite([{input:target,raw:{width,height,channels:3},left:0,top:0},{input:native,raw:{width,height,channels:3},left:width,top:0}]).png().toBuffer();
  const blended=Buffer.alloc(target.length);for(let j=0;j<target.length;j++)blended[j]=Math.round((target[j]+native[j])/2);
  const overlay=await sharp(blended,{raw:{width,height,channels:3}}).png().toBuffer();
  const regions=data.regions.map(r=>{
    const [x,y,w,hh]=r.bbox,l=Math.floor(x),t=Math.floor(y),right=Math.min(width,Math.ceil(x+w)),bottom=Math.min(height,Math.ceil(y+hh));let delta=0,count=0;
    for(let yy=t;yy<bottom;yy++)for(let xx=l;xx<right;xx++)for(let c=0;c<3;c++){const k=(yy*width+xx)*3+c;delta+=Math.abs(target[k]-native[k]);count++;}
    return {region_id:r.region_id,bbox:r.bbox,mean_absolute_error:delta/count};
  });
  return {side_by_side:side,overlay,region_differences:{status:'unassessed',target_image_sha256:data.target_binding.target_image_sha256,render_sha256:sha(png),regions}};
}

/** Read-only verification of immutable in-memory snapshots, no output paths. */
export async function verifyOutputSnapshots(input,options={}) {
  closed(input,['pptx_base64','handoff','renders','comparisons'],'verification snapshots');
  const h=input.handoff,requireRuntime=runtimeRequire(options),sharp=requireRuntime('sharp');
  await loadNativeFonts(options);
  const {FontLibrary}=createRequire(requireRuntime.resolve('@oai/artifact-tool'))('skia-canvas');
  support(h,new Set(FontLibrary.families));
  const {PresentationFile,FileBlob}=await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
  const pptx=Buffer.from(input.pptx_base64,'base64');
  const imported=await PresentationFile.importPptx(new FileBlob(new Uint8Array(pptx),
    'application/vnd.openxmlformats-officedocument.presentationml.presentation'));
  check(imported.slides.items.length===h.slides.length,'Current PPTX page count changed');
  const pixels=async bytes=>sharp(bytes,{failOn:'error'}).toColourspace('srgb').ensureAlpha().raw().toBuffer();
  const canonical=value=>JSON.stringify(value&&typeof value==='object'?Array.isArray(value)?value.map(v=>JSON.parse(canonical(v))):Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])):value);
  for(let i=0;i<h.slides.length;i++) {
    const data=h.slides[i],slide=imported.slides.items[i];
    const rerender=Buffer.from(await(await imported.export({slide,format:'png',scale:1})).arrayBuffer());
    const submitted=Buffer.from(input.renders[i],'base64');
    check((await pixels(rerender)).equals(await pixels(submitted)),'Submitted render is not the current PPTX rendering');
    const target=h.assets[data.target_binding.target_image_ref];
    check(sha(Buffer.from(target.data_base64,'base64'))===data.target_binding.target_image_sha256,'Comparison target bytes changed');
    const expected=await comparisonBytes(data,Buffer.from(target.data_base64,'base64'),submitted,sharp);
    for(const key of ['side_by_side','overlay'])
      check((await pixels(expected[key])).equals(await pixels(Buffer.from(input.comparisons[i][key],'base64'))),'Comparison pixels are not derived from current target and render');
    check(canonical(expected.region_differences)===canonical(input.comparisons[i].region_differences),'Region differences are not derived from current target and render');
  }
  return {pptx_sha256:sha(pptx),verified_pages:h.slides.length};
}

export async function render(input,options={}) {
  const p=await preflight(input,options),h=p.handoff;
  const diagnostic=h.handoff_version==='codex-presentations-image-led-diagnostic/v1';
  const sdk=options.loadSdk?await options.loadSdk():await import(pathToFileURL(runtimeRequire(options).resolve('@oai/artifact-tool')).href);
  const {Presentation,PresentationFile,FileBlob}=sdk;
  await paths(h,options); await fs.mkdir(h.output_paths.directory,{recursive:false});
  const dir=h.output_paths.directory,write=(name,bytes)=>fs.writeFile(path.join(dir,name),bytes,{flag:'wx'});
  try {
    const first=h.slides[0].canvas,pres=Presentation.create({slideSize:{width:first.width,height:first.height}}),mapping=[];
    for(const data of h.slides) {
      const slide=pres.slides.add(),facades=new Map();slide.background.fill='none';p.currentSlide=data;
      const ordered=nativeObjects(data.objects);
      for(const o of [...ordered.filter(x=>x.kind!=='connector'),...ordered.filter(x=>x.kind==='connector')]) {
        const f=add(slide,o,p,facades);
        mapping.push({slide_id:data.target_binding.slide_id,region_id:o.region_id,object_id:o.object_id,sdk_id:f.id,kind:o.kind,
          ...(Object.hasOwn(o,'span')?{span:o.span}:{})});
      }
    }
    // SDK facade ids are not exported native ids. Persist explicit region/object
    // identity in the public proto and retain the finalized object stacking order.
    const proto=structuredClone(pres.toProto());
    for(let i=0;i<h.slides.length;i++) {
      const data=h.slides[i],rows=mapping.filter(r=>r.slide_id===data.target_binding.slide_id);
      const byId=new Map(rows.map(r=>[String(r.sdk_id),r]));
      const order=new Map(nativeObjects(data.objects).map((o,i)=>[o.object_id,i]));
      check(proto.slides[i].elements.length===rows.length,'SDK dropped or added an authored object');
      for(const element of proto.slides[i].elements) {
        const row=byId.get(String(element.id));check(row,'SDK object identity is missing');element.name=row.object_id;
      }
      proto.slides[i].elements.sort((a,b)=>order.get(a.name)-order.get(b.name));
    }
    // Consolidate only source bytes in the public export proto. Every image
    // element keeps its own id, crop, frame, z-order and material identity.
    // The authoring facades remain independent; no SDK dependency is patched.
    const imageRefs=new Map(),uniqueImages=new Map();
    for(const asset of proto.images) {
      check(asset.data instanceof Uint8Array&&asset.data.length>0&&!asset.uri,'Export image must contain embedded bytes');
      const identity=asset.contentType+':'+sha(asset.data);
      const first=uniqueImages.get(identity);
      if(first) check(Buffer.from(first.data).equals(Buffer.from(asset.data)),'Image digest collision');
      else uniqueImages.set(identity,asset);
      imageRefs.set(asset.id,(first??asset).id);
    }
    for(const slide of proto.slides) for(const element of slide.elements) if(element.imageReference) {
      const id=imageRefs.get(element.imageReference.id);
      check(id,'Unresolved export image reference');element.imageReference.id=id;
    }
    proto.images=[...uniqueImages.values()];
    const exportPresentation=Presentation.load(proto);
    await write('handoff.json',JSON.stringify(h,null,2));await write('mapping.json',JSON.stringify(mapping,null,2));
    await(await PresentationFile.exportPptx(exportPresentation)).save(h.output_paths.pptx);
    const bytes=await fs.readFile(h.output_paths.pptx),imported=await PresentationFile.importPptx(await FileBlob.load(h.output_paths.pptx));
    const snapshot=await imported.inspect({kind:'slide,textbox,shape,image,table,chart,layout',maxChars:10000000});
    await write('inspect.ndjson',snapshot.ndjson);await write('authoring.proto.json',JSON.stringify(proto,null,2));
    await write('reimport.proto.json',JSON.stringify(imported.toProto(),null,2));
    const renders=[],comparisons=[];
    const sharp=runtimeRequire(options)('sharp');
    for(let i=0;i<h.slides.length;i++){
      const slide=imported.slides.items[i],png=Buffer.from(await(await imported.export({slide,format:'png',scale:1})).arrayBuffer());
      const layout=await slide.export({format:'layout'}),name='slide-'+(i+1)+'.png';
      await write(name,png);await write('slide-'+(i+1)+'.layout.json',await layout.text());
      renders.push({slide_id:h.slides[i].target_binding.slide_id,path:path.join(dir,name),sha256:sha(png)});
      const data=h.slides[i],compared=await comparisonBytes(data,p.assetBytes.get(data.target_binding.target_image_ref),png,sharp);
      const difference=Buffer.from(JSON.stringify(compared.region_differences,null,2));
      const comparison={slide_id:data.target_binding.slide_id};
      for(const [key,suffix,raw] of [['side_by_side','side-by-side.png',compared.side_by_side],['overlay','overlay.png',compared.overlay],['region_differences','regions.json',difference]]){
        const filename='compare-'+(i+1)+'-'+suffix;await write(filename,raw);comparison[key]={path:path.join(dir,filename),sha256:sha(raw)};
      }
      comparisons.push(comparison);
    }
    const files={};
    for(const name of ['handoff.json','mapping.json','inspect.ndjson','authoring.proto.json','reimport.proto.json',
      ...h.slides.map((_,i)=>'slide-'+(i+1)+'.layout.json')]) {
      const filename=path.join(dir,name),raw=await fs.readFile(filename);files[name]={path:filename,sha256:sha(raw)};
    }
      const result=diagnostic ? {artifact_type:'image-led-native-diagnostic-result',purpose:'region-diagnostic',status:'engineering-output-unassessed',project_id:h.project_id,selection_ref:h.selection_ref,
      region_inventory_ref:h.region_inventory_ref,diagnostic_ref:h.diagnostic_ref,task_id:h.task_id,handoff_sha256:files['handoff.json'].sha256,
      pptx_path:h.output_paths.pptx,pptx_sha256:sha(bytes),renders,mapping,files,comparisons,visual_fidelity:'not-established',user_acceptance:'not-established',target_powerpoint:'not-established'} : {status:'engineering-output-unassessed',project_id:h.project_id,selection_ref:h.selection_ref,
      region_inventory_ref:h.region_inventory_ref,plan_ref:h.plan_ref,task_id:h.task_id,handoff_sha256:files['handoff.json'].sha256,
      pptx_path:h.output_paths.pptx,pptx_sha256:sha(bytes),renders,mapping,files,comparisons,visual_fidelity:'not-established',
      user_acceptance:'not-established',target_powerpoint:'not-established'};
    await write('result.json',JSON.stringify(result,null,2));return result;
  }catch(error){
    await write('failure.json',JSON.stringify({status:'failed-unpublishable',task_id:h.task_id,handoff_sha256:p.handoff_sha256,reason:String(error.message)},null,2)).catch(()=>{});
    throw error;
  }
}
