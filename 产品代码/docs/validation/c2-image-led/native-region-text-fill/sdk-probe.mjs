import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const code=process.argv[2],root=process.argv[3];
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
s.selected_copy.items=s.regions.flatMap(r=>structuredClone(r.content.items));
s.target_binding.selected_copy_sha256=digest(canonical(s.selected_copy));
s.objects=s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,render_mode:r.kind==='image'?'bitmap':'native'}));
const before=structuredClone(h);
const result=await render(h,{projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON});
if(canonical(before)!==canonical(h))throw Error('Renderer mutated the frozen handoff');
console.log(JSON.stringify({output:result.pptx_path,result:path.join(h.output_paths.directory,'result.json'),objectCount:s.objects.length}));
