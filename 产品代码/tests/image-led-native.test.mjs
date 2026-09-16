import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { preflight, render } from '../scripts/image-led-native.mjs';
import { syntheticHandoff, digest } from './fixtures/image-led-synthetic.mjs';

const nodeModulesRoot = process.env.C2_RUNTIME_NODE_MODULES;
const pythonExecutable = process.env.C2_RUNTIME_PYTHON ?? 'python3';
const options = root => ({ projectRoot: root, nodeModulesRoot, pythonExecutable });
const canonical = x => JSON.stringify(x && typeof x === 'object'
  ? Array.isArray(x) ? x.map(v=>JSON.parse(canonical(v)))
    : Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))])) : x);

function v2Handoff(root) {
  const h=syntheticHandoff(root);
  h.compiler_version='image-led-faithful-compiler/v2'; h.handoff_version='codex-presentations-image-led/v2';
  for(const s of h.slides) {
    // Preserve actual finalized geometry while exercising a non-first title.
    [s.regions[0],s.regions[1]]=[s.regions[1],s.regions[0]];
    [s.objects[0],s.objects[1]]=[s.objects[1],s.objects[0]];
    const items=s.regions.flatMap(r=>r.content.items);
    s.selected_copy={copy_version:'image-led-selected-copy/v2',title_item_id:items[1].item_id,items};
    s.target_binding.selected_copy_sha256=digest(canonical(s.selected_copy));
  }
  return h;
}

test('v2 preflight retains non-first title and rejects lost copy metadata before output', {skip:!nodeModulesRoot}, async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'image-led-v2-'));
  const h=v2Handoff(root), result=await preflight(h,options(root));
  assert.equal(result.handoff.slides[0].selected_copy.items[1].role,'title');
  for(const change of [
    h=>{delete h.slides[0].selected_copy;},
    h=>{delete h.slides[0].selected_copy.copy_version;},
    h=>{h.slides[0].selected_copy.title_item_id=h.slides[0].selected_copy.items[0].item_id;},
    h=>{h.slides[0].selected_copy.items[0].text='changed';},
    h=>{h.handoff_version='codex-presentations-image-led/v1';},
  ]) {
    const bad=structuredClone(h);change(bad);let loads=0;
    await assert.rejects(render(bad,{...options(root),loadSdk:async()=>{loads++;throw Error('must not load');}}),/IMAGE_LED_/);
    assert.equal(loads,0);await assert.rejects(fs.stat(bad.output_paths.directory),{code:'ENOENT'});
  }
});

test('invalid handoffs fail before any SDK load or output directory', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'image-led-preflight-'));
  const changes = [
    h => { h.slides[0].objects[0].content.items[0].text = 'changed title'; },
    h => { h.slides[0].objects.pop(); h.slides[0].regions.pop(); h.slides[0].objects.shift(); h.slides[0].regions.shift(); },
    h => { h.slides[1].target_binding.page_order = 1; },
    h => { h.slides[0].objects[0].bbox[0] += 2; },
    h => { h.slides[0].regions[0].appearance.autoFit = 'shrink'; h.slides[0].objects[0].appearance.autoFit = 'shrink'; },
    h => { h.slides[0].objects[0].render_mode = 'bitmap'; },
    h => { h.assets[h.slides[0].target_binding.target_image_ref].sha256 = 'f'.repeat(64); },
    h => { h.output_paths.pptx = path.join(root, 'outside.pptx'); },
    h => { h.output_paths.directory = path.join(root, '..', h.task_id); },
    h => { h.extra_layout = 'redesign'; },
  ];
  for (const change of changes) {
    const h = syntheticHandoff(root); change(h); let loads = 0;
    await assert.rejects(render(h, { ...options(root), loadSdk: async () => { loads++; throw new Error('SDK must not load'); } }), /IMAGE_LED_/);
    assert.equal(loads, 0); await assert.rejects(fs.stat(h.output_paths.directory), { code: 'ENOENT' });
  }
});

test('preflight refuses existing output and symlink parents', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'image-led-output-'));
  const h = syntheticHandoff(root); await fs.mkdir(h.output_paths.directory);
  await assert.rejects(preflight(h, options(root)), /IMAGE_LED_/);
  await fs.writeFile(path.join(h.output_paths.directory, 'preserved'), 'keep');
  assert.equal(await fs.readFile(path.join(h.output_paths.directory, 'preserved'), 'utf8'), 'keep');
  const link = path.join(root, 'link'); await fs.symlink(root, link);
  h.output_paths.directory = path.join(link, h.task_id); h.output_paths.pptx = path.join(h.output_paths.directory, 'native-anchors.pptx');
  await assert.rejects(preflight(h, options(root)), /IMAGE_LED_/);
});

test('valid complete handoff preflight is read-only and returns isolated data', { skip: !nodeModulesRoot }, async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'image-led-valid-'));
  const h = syntheticHandoff(root);
  const result = await preflight(h, options(root));
  assert.equal(result.handoff.slides.length, 3); assert.ok(result.assetBytes.size >= 2);
  h.slides[0].objects[0].bbox[0] = 1;
  assert.notEqual(result.handoff.slides[0].objects[0].bbox[0], 1);
  await assert.rejects(fs.stat(h.output_paths.directory), { code: 'ENOENT' });
});
