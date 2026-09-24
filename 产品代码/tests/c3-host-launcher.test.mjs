import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const PRODUCT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const LAUNCHER = path.join(PRODUCT_ROOT, 'docs/validation/c3-whole-deck/启动-C3当前宿主.command');

test('C3 host launcher activates only the exact Image 2.5 Sunburst route', () => {
  const result = spawnSync('/bin/zsh', [LAUNCHER, '--check'], {
    encoding: 'utf8',
    env: process.env,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /CRS \/ gpt-image-2\.5-sunburst/);
  assert.doesNotMatch(result.stdout, /CRS \/ gpt-image-2(?:\s|$)/);
});
