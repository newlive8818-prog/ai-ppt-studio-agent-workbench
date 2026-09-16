// Synthetic v3 carrier fixture. No customer copy, target image, or acceptance.
import { syntheticHandoff, digest } from './image-led-synthetic.mjs';

const canonical = x => JSON.stringify(x && typeof x === 'object'
  ? Array.isArray(x) ? x.map(v => JSON.parse(canonical(v)))
    : Object.fromEntries(Object.keys(x).sort().map(k => [k, JSON.parse(canonical(x[k]))])) : x);
const contour = points => [{ moveTo: { x: points[0][0], y: points[0][1] } },
  ...points.slice(1).map(([x,y]) => ({ lineTo: { x,y } })), { close: {} }];

export function nativeV3Handoff(root) {
  const h = syntheticHandoff(root), s = h.slides[0];
  h.slides = [s];
  h.handoff_version = 'codex-presentations-image-led/v3';
  h.compiler_version = 'image-led-faithful-compiler/v3';
  s.region_version = 'image-led-region-inventory/v3';
  const text = '① 保留"直引号"与“弯引号”，② 自然换行不能新增换行字符。';
  const body = s.regions.find(r => r.region_id === 'body-0');
  body.content.items[0].text = text;
  body.bbox = [80,180,230,280];
  body.appearance.runs = [
    { ...body.appearance.runs[0], text:'① 保留"直引号"与“弯引号”，', bold:true },
    { ...body.appearance.runs[0], text:'② 自然换行不能新增换行字符。', color:'#204060' },
  ];
  for (const r of s.regions) if (r.kind === 'text') r.appearance.wrap = r === body ? 'square' : 'none';
  const gradient = { type:'linear-gradient', angle:35,
    stops:[{offset:0,color:'#003399'}, {offset:0.425,color:'#00AADD'}, {offset:1,color:'#CCEEFF'}] };
  const outer = contour([[0,0],[150,0],[150,120],[0,120]]);
  const inner = contour([[40,30],[40,90],[110,90],[110,30]]);
  const path = { width:150,height:120,commands:[...outer,...inner] };
  const add = (region_id,kind,bbox,appearance,items=[]) => s.regions.push({
    region_id,kind,bbox,z_order:s.regions.length,content:{items},material_binding:null,appearance,
  });
  add('polygon-hole','shape',[540,300,150,120],{
    geometry:'polygon',corner_radius:0,fill:gradient,line:null,shadow:null,paths:[path],
  });
  add('directed-path','relation-path',[540,150,150,120],{
    paths:[{width:150,height:120,commands:contour([[0,30],[90,30],[90,0],[150,60],[90,120],[90,90],[0,90]])}],
    fill:gradient,line:{color:'#112233',width:1.5,dash:'solid'},
    relation_binding:{origin:'source-image-derived',target_image_sha256:s.target_binding.target_image_sha256,
      kind:'directed-edge',from_item_id:'title-0',to_item_id:'body-0',direction:'forward'},
  });
  add('feedback-path','relation-path',[740,450,150,120],{
    paths:[path],fill:{type:'solid',color:'#2266AA'},line:null,
    relation_binding:{origin:'source-image-derived',target_image_sha256:s.target_binding.target_image_sha256,
      kind:'feedback-symbol',anchor_item_id:'body-0'},
  });
  const cell = {item_id:'cell-0',kind:'table-cell',table_id:'small-table',row:0,column:0,text};
  add('small-table','table',[340,180,160,280],{
    row_heights:[280],column_widths:[160],cells:[{row:0,column:0,item_id:cell.item_id,style:structuredClone(body.appearance)}],
  },[cell]);
  s.selected_copy = {copy_version:'image-led-selected-copy/v2',title_item_id:'title-0',
    items:s.regions.flatMap(r=>structuredClone(r.content.items))};
  s.target_binding.selected_copy_sha256 = digest(canonical(s.selected_copy));
  s.objects = s.regions.map(r=>({...structuredClone(r),object_id:'o-'+r.region_id,
    render_mode:r.kind==='image'?'bitmap':'native'}));
  return h;
}
