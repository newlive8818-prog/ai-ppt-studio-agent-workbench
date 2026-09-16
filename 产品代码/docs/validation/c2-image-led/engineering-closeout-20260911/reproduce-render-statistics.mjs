// Read-only evidence reproduction: verifies exact retained files, computes RGBA
// differences, and prints a report. Never imports/re-exports a PPTX or writes files.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const evidencePath = process.argv[2] ?? path.join(path.dirname(fileURLToPath(import.meta.url)), 'accepted-render-diff.json');
const evidence = JSON.parse(await fs.readFile(evidencePath, 'utf8'));
async function readExact(identity) {
  assert.ok(path.isAbsolute(identity.path), 'Evidence paths must be absolute');
  const bytes = await fs.readFile(identity.path);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), identity.sha256, identity.path);
  return bytes;
}
await readExact(evidence.input_identity.pptx);
await readExact(evidence.input_identity.handoff);
await readExact(evidence.execution_identity.sharp.package_json);
await readExact(evidence.execution_identity.sharp.entry);
const requireRuntime = createRequire(path.join(evidence.execution_identity.node_modules_root, '__c2_readonly_statistics.cjs'));
const sharp = requireRuntime('sharp');
const results = [];
for (const slide of evidence.slides) {
  const left = await sharp(await readExact(slide.saved_png)).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const right = await sharp(await readExact(slide.rerendered_png)).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  assert.equal(left.info.width, slide.width); assert.equal(left.info.height, slide.height);
  assert.deepEqual(right.info, left.info); assert.equal(left.info.channels, 4);
  let changed = 0, sum = 0, max = 0, minX = slide.width, minY = slide.height, maxX = 0, maxY = 0;
  for (let k = 0; k < left.data.length; k++) {
    const delta = Math.abs(left.data[k] - right.data[k]);
    if (!delta) continue;
    changed++; sum += delta; max = Math.max(max, delta);
    const pixel = Math.floor(k / 4), x = pixel % slide.width, y = Math.floor(pixel / slide.width);
    minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  }
  const actual = { changed_channels: changed, total_channels: left.data.length,
    mean_absolute_error: sum / left.data.length, max_channel_delta: max,
    bbox: changed ? [minX, minY, maxX, maxY] : null };
  for (const key of Object.keys(actual)) assert.deepEqual(actual[key], slide[key], `${slide.slide_id}: ${key}`);
  results.push({ slide_id: slide.slide_id, ...actual });
}
console.log(JSON.stringify({ status: 'passed', scope: 'exact retained PNG statistics only; full preflight remains separate', file_writes: 0, slides: results }, null, 2));
