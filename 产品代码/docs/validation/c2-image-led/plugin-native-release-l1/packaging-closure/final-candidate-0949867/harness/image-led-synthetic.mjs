// Synthetic mechanism fixtures. These contain no customer or Image 2 evidence.
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import path from 'node:path';

export const digest = value => createHash('sha256').update(value).digest('hex');
const canonical = value => JSON.stringify(value && typeof value === 'object'
  ? Array.isArray(value) ? value.map(v => JSON.parse(canonical(v)))
    : Object.fromEntries(Object.keys(value).sort().map(k => [k, JSON.parse(canonical(value[k]))]))
  : value);
const ref = (kind, letter = 'a') => `artifact://${kind}/${letter.repeat(64)}`;

// Uniform RGBA bytes are a size/hash test input, never a claimed finalized design.
function png(width, height, rgba = [255, 255, 255, 255]) {
  const crc = data => {
    let c = 0xffffffff;
    for (const b of data) { c ^= b; for (let i = 0; i < 8; i++) c = (c >>> 1) ^ (c & 1 ? 0xedb88320 : 0); }
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type), data]), header = Buffer.alloc(4), tail = Buffer.alloc(4);
    header.writeUInt32BE(data.length); tail.writeUInt32BE(crc(body));
    return Buffer.concat([header, body, tail]);
  };
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 6;
  const pixels = Buffer.alloc(height * (1 + width * 4));
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) for (let c = 0; c < 4; c++) pixels[y * (1 + width * 4) + 1 + x * 4 + c] = rgba[c];
  return Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), chunk('IHDR', header), chunk('IDAT', deflateSync(pixels)), chunk('IEND', Buffer.alloc(0))]);
}

export function syntheticHandoff(root, variant = 'A') {
  const task = digest(`synthetic-${variant}`), targetBytes = png(16, 9);
  const targetRef = ref('image-led-image', 'b');
  const cropRef = ref('image-led-crop', 'c'), cropBytes = png(8, 8, [25, 110, 170, 255]);
  const handoff = {
    handoff_version: 'codex-presentations-image-led/v1', compiler_version: 'image-led-faithful-compiler/v1',
    project_id: `synthetic-${variant}`, selection_ref: ref('image-led-selection'),
    region_inventory_ref: ref('image-led-region-inventory'), plan_ref: ref('visual-compilation-plan'), task_id: task,
    slides: [], assets: {
      [targetRef]: { sha256: digest(targetBytes), data_base64: targetBytes.toString('base64'), mime_type: 'image/png' },
      [cropRef]: { sha256: digest(cropBytes), data_base64: cropBytes.toString('base64'), mime_type: 'image/png' },
    },
    output_paths: { directory: path.join(root, task), pptx: path.join(root, task, 'native-anchors.pptx') },
  };
  for (let n = 0; n < 3; n++) {
    const shift = variant === 'A' ? n * 12 : 40 + n * 18;
    const items = [
      { item_id: `title-${n}`, kind: 'text', role: 'title', text: `${variant} ${n + 1} Production evidence` },
      { item_id: `body-${n}`, kind: 'text', role: 'body', text: variant === 'A' ? ` Sample ${n + 1}\nCapacity ${40 + n} units ` : ` Dispatch ${n + 1}\nCoverage ${72 + n} sites ` },
    ];
    const textStyle = (text, size = 28) => ({ runs: [{ text, fontFamily: 'Arial', fontSize: size, color: '#183A52', bold: false, italic: false }], alignment: 'left', verticalAlignment: 'top', insets: [0, 0, 0, 0], lineSpacing: 1.2 });
    const regions = items.map((item, i) => ({ region_id: item.item_id, kind: 'text', bbox: i ? [80 + shift, 180, 400, 120] : [80, 40, 900, 90], z_order: i + 1, content: { items: [structuredClone(item)] }, material_binding: null, appearance: textStyle(item.text, i ? 28 : 38) }));
    regions.push({ region_id: 'background', kind: 'shape', bbox: [0, 0, 1280, 720], z_order: 0, content: { items: [] }, material_binding: null, appearance: { geometry: 'rect', corner_radius: 0, fill: { type: 'solid', color: variant === 'A' ? '#FFFFFF' : '#F5F7FA' }, line: null, shadow: null } });
    regions.push({ region_id: 'sample-image', kind: 'image', bbox: [800 + shift, 200, 120, 120], z_order: 3, content: { items: [] }, material_binding: null, appearance: { asset_ref: cropRef, asset_sha256: digest(cropBytes), crop: [0, 0, 1, 1] } });
    if (n > 0 || variant === 'B') {
      regions.push({ region_id: 'metric-shape', kind: 'shape', bbox: [80 + shift, 400, 260 + n * 40, 80], z_order: 4, content: { items: [] }, material_binding: null, appearance: { geometry: 'rect', corner_radius: 0, fill: { type: 'linear-gradient', angle: 0, stops: [{ offset: 0, color: '#D6EAF8' }, { offset: 1, color: '#72B7DC' }] }, line: null, shadow: null } });
    }
    const binding = {
      project_id: handoff.project_id, slide_id: `${variant}-different-${n + 10}`, page_order: n + 1,
      candidate_ref: ref('image-led-candidate'), target_image_ref: targetRef,
      target_image_sha256: digest(targetBytes), selected_copy_sha256: digest(canonical({ items })),
      material_roles: [], common_rules_ref: ref('image-led-input-policy'), accepted_deviations: [],
      design_authority: 'finalized-image', conversion_mode: 'faithful-native',
    };
    handoff.slides.push({ target_binding: binding, canvas: { width: 1280, height: 720, dpi: 96 }, source_image_size: { width: 16, height: 9 }, regions,
      objects: regions.map(r => ({ ...structuredClone(r), object_id: `o-${r.region_id}`, render_mode: r.kind === 'image' ? 'bitmap' : 'native' })) });
  }
  return handoff;
}
