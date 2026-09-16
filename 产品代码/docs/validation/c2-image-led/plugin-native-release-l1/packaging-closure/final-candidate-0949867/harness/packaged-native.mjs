
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [plugin, fixture, base, modules, python] = process.argv.slice(2);
const { preflight, render, verifyOutputSnapshots } = await import(pathToFileURL(path.join(plugin, 'scripts/image-led-native.mjs')).href);
const { syntheticHandoff, digest } = await import(pathToFileURL(fixture).href);
assert.equal(process.env.PYTHONPATH, undefined);
assert.equal(process.env.PYTHONHOME, undefined);
assert.deepEqual(await fs.readdir(process.cwd()), []);
const root = await fs.realpath(await fs.mkdir(path.join(base, 'native-project'), { recursive: true }).then(() => path.join(base, 'native-project')));
const options = { projectRoot: root, nodeModulesRoot: modules, pythonExecutable: python };
const valid = syntheticHandoff(root);
const checked = await preflight(valid, options);
assert.equal(checked.handoff.slides.length, 3);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
const negatives = [
  ['finalized text mutation', h => { h.slides[0].objects[0].content.items[0].text = 'unauthorized mutation'; }],
  ['selected copy hash', h => { h.slides[0].target_binding.selected_copy_sha256 = 'f'.repeat(64); }],
  ['target image hash', h => { h.slides[0].target_binding.target_image_sha256 = 'f'.repeat(64); }],
  ['page identity', h => { h.slides[1].target_binding.page_order = 1; }],
  ['missing region mapping', h => { h.slides[0].objects.pop(); }],
  ['output escapes project', h => { h.output_paths.directory = path.join(base, h.task_id); h.output_paths.pptx = path.join(h.output_paths.directory, 'native-anchors.pptx'); }],
];
for (const [label, mutate] of negatives) {
  const invalid = structuredClone(valid); mutate(invalid); let loads = 0;
  await assert.rejects(render(invalid, { ...options, loadSdk: async () => { loads++; throw new Error('unexpected authoring SDK load'); } }), /IMAGE_LED_/, label);
  assert.equal(loads, 0, label);
  await assert.rejects(fs.stat(invalid.output_paths.directory), { code: 'ENOENT' }, label);
  await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' }, label);
}
// A sacrificial complete package cannot recover its removed domain module from
// the source repo, the parent test's PYTHONPATH, or the working directory.
const missingDomain = path.join(base, 'missing-domain-plugin');
await fs.cp(plugin, missingDomain, { recursive: true });
await fs.rm(path.join(missingDomain, 'src/ai_ppt_studio/domains/visual/image_led.py'));
const broken = await import(pathToFileURL(path.join(missingDomain, 'scripts/image-led-native.mjs')).href);
let domainLoads = 0;
await assert.rejects(broken.render(valid, { ...options, loadSdk: async () => { domainLoads++; throw new Error('unexpected authoring SDK load'); } }), /Domain preflight rejected:[\s\S]*ModuleNotFoundError[\s\S]*ai_ppt_studio\.domains\.visual\.image_led/);
assert.equal(domainLoads, 0);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
// Keep the real image dependency available while removing only the external
// authoring SDK from an isolated resolution root. Never stub SDK behavior.
const missingSdk = path.join(base, 'missing-sdk', 'node_modules');
await fs.mkdir(missingSdk, { recursive: true });
await fs.symlink(await fs.realpath(path.join(modules, 'sharp')), path.join(missingSdk, 'sharp'), 'dir');
let sdkLoads = 0;
await assert.rejects(render(valid, { ...options, nodeModulesRoot: missingSdk, loadSdk: async () => { sdkLoads++; throw new Error('unexpected authoring SDK load'); } }), error => error.code === 'MODULE_NOT_FOUND' && /@oai\/artifact-tool/.test(error.message));
assert.equal(sdkLoads, 0);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
// Existing outputs are byte-preserved, including nested and binary content.
await fs.mkdir(path.join(valid.output_paths.directory, 'nested'), { recursive: true });
const preserved = Buffer.from([0, 255, 13, 10, 42]);
const preservedPath = path.join(valid.output_paths.directory, 'nested', 'accepted.bin');
await fs.writeFile(preservedPath, preserved);
let existingLoads = 0;
await assert.rejects(render(valid, { ...options, loadSdk: async () => { existingLoads++; throw new Error('unexpected authoring SDK load'); } }), /Output directory already exists/);
assert.equal(existingLoads, 0);
assert.deepEqual(await fs.readdir(valid.output_paths.directory), ['nested']);
assert.deepEqual(await fs.readdir(path.dirname(preservedPath)), ['accepted.bin']);
assert.deepEqual(await fs.readFile(preservedPath), preserved);
// Render into a different fresh synthetic project; do not remove the preserved output.
const renderRoot = path.join(base, 'render-project'); await fs.mkdir(renderRoot);
const handoff = syntheticHandoff(renderRoot);
const result = await render(handoff, { ...options, projectRoot: renderRoot });
assert.equal(result.status, 'engineering-output-unassessed');
for (const key of ['visual_fidelity', 'user_acceptance', 'target_powerpoint']) assert.equal(result[key], 'not-established');
assert.equal(result.renders.length, 3); assert.equal(result.comparisons.length, 3);
assert.equal(digest(await fs.readFile(result.pptx_path)), result.pptx_sha256);
for (const row of [...result.renders, ...result.comparisons.flatMap(c => [c.side_by_side, c.overlay, c.region_differences])]) {
  assert.equal(digest(await fs.readFile(row.path)), row.sha256);
}
const encode = async p => (await fs.readFile(p)).toString('base64');
const snapshots = { pptx_base64: await encode(result.pptx_path), handoff,
  renders: await Promise.all(result.renders.map(r => encode(r.path))),
  comparisons: await Promise.all(result.comparisons.map(async c => ({ side_by_side: await encode(c.side_by_side.path), overlay: await encode(c.overlay.path), region_differences: JSON.parse(await fs.readFile(c.region_differences.path, 'utf8')) }))) };
const verified = await verifyOutputSnapshots(snapshots, { nodeModulesRoot: modules });
assert.equal(verified.pptx_sha256, result.pptx_sha256); assert.equal(verified.verified_pages, 3);
assert.deepEqual(await fs.readFile(preservedPath), preserved);
await fs.writeFile(path.join(base, 'packaged-native-result.json'), JSON.stringify({ packaged_native: 'PASS', preflight: 'read-only', counterexamples: [...negatives.map(([label]) => label), 'missing package domain', 'missing external SDK', 'existing output bytes preserved'], ...verified, user_acceptance: result.user_acceptance, target_powerpoint: result.target_powerpoint }), { flag: 'wx' });
