import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const moduleUrl = new URL('../scripts/image-led-fonts.mjs', import.meta.url).href;
const nodeModulesRoot = process.env.C2_RUNTIME_NODE_MODULES;
const regular = '/Users/defei/Library/Fonts/AI-PPT-e4b3b9d05875-msyh.ttc';
const bold = '/Users/defei/Library/Fonts/AI-PPT-06e1a30f687a-msyhbd.ttc';
const heiti = '/System/Library/Fonts/STHeiti Light.ttc';
const regularHash = 'e4b3b9d058750fb80899c24f68e35beda606ca92694eff0e9f7f91eec7a846aa';
const boldHash = '06e1a30f687ab7d39f533447b21e84d51e0cecdaa6bfa060c87136b168811bdc';
const execute = promisify(execFile);
async function load(options) {
  const { loadNativeFonts } = await import(moduleUrl);
  return loadNativeFonts(options);
}

test('explicit empty font configuration performs no runtime load or directory scan', async () => {
  assert.deepEqual(await load({fontFiles: [], nodeModulesRoot: '/does-not-exist'}), []);
});

test('real regular and bold files report byte hashes and actual SDK family weights',
  {skip: !nodeModulesRoot || !existsSync(regular) || !existsSync(bold)}, async () => {
    const options = {nodeModulesRoot, fontFiles: [regular, {path: bold, sha256: boldHash}]};
    const before = structuredClone(options);
    const loaded = await load(options);
    assert.deepEqual(options, before);
    assert.deepEqual(loaded.map(f => [f.path, f.sha256]), [[regular, regularHash], [bold, boldHash]]);
    assert.ok(loaded[0].faces.some(f => f.family === 'Microsoft YaHei' && f.weight === 400));
    assert.ok(loaded[1].faces.some(f => f.family === 'Microsoft YaHei' && f.weight === 700));
    assert.ok(loaded.every(f => f.faces.length > 0 && f.faces.every(face =>
      typeof face.family === 'string' && Number.isFinite(face.weight))));
  });

test('font file entries reject alias maps and asserted family overrides', async () => {
  for (const fontFiles of [null, 'Microsoft YaHei', {'Microsoft YaHei': heiti},
    [{path: heiti, alias: 'Microsoft YaHei'}], [{path: heiti, family: 'Microsoft YaHei'}],
    [['Microsoft YaHei', heiti]], [{path: heiti, sha256: regularHash, alias: 'Microsoft YaHei'}]]) {
    await assert.rejects(load({nodeModulesRoot, fontFiles}), /IMAGE_LED_FONT/);
  }
});

test('missing and noncanonical paths fail instead of trying family or glob lookup', async () => {
  for (const file of ['/private/tmp/no-such-image-led-font-20260911.ttf', 'msyh.ttc',
    'Microsoft YaHei', '', 'file:///tmp/font.ttf', '/tmp/../tmp/font.ttf', '/tmp/*.ttc']) {
    await assert.rejects(load({nodeModulesRoot, fontFiles: [file]}), /IMAGE_LED_FONT/);
  }
});

test('nonfont extension, directory and invalid font bytes fail explicitly', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'image-led-font-files-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const txt = path.join(root, 'font.txt'), directory = path.join(root, 'directory.ttf');
  await fs.writeFile(txt, 'not a font'); await fs.mkdir(directory);
  for (const file of [txt, directory])
    await assert.rejects(load({nodeModulesRoot, fontFiles: [file]}), /IMAGE_LED_FONT/);
  if (nodeModulesRoot) {
    const fake = path.join(root, 'fake.ttf'); await fs.writeFile(fake, 'not a font');
    await assert.rejects(load({nodeModulesRoot, fontFiles: [fake]}), /IMAGE_LED_FONT/);
  }
});

test('hash assertions reject malformed or different bytes before SDK font registration',
  {skip: !existsSync(regular)}, async () => {
    for (const sha256 of [null, 'wrong', regularHash.toUpperCase(), '0'.repeat(64)])
      await assert.rejects(load({nodeModulesRoot: '/does-not-exist', fontFiles: [{path: regular, sha256}]}), /IMAGE_LED_FONT/);
  });

test('all configured files are validated before any font becomes registered',
  {skip: !nodeModulesRoot || !existsSync(regular)}, async () => {
    const script = `
      import assert from 'node:assert/strict';import {createRequire} from 'node:module';import path from 'node:path';
      const {loadNativeFonts}=await import(process.argv[1]);
      const options=JSON.parse(process.argv[2]);
      const req=createRequire(path.join(options.nodeModulesRoot,'__font_test__.cjs'));
      const {FontLibrary}=createRequire(req.resolve('@oai/artifact-tool'))('skia-canvas');
      const before=FontLibrary.families;
      await assert.rejects(loadNativeFonts(options),/IMAGE_LED_FONT.*SHA-256/);
      assert.deepEqual(FontLibrary.families,before);
      console.log('validated-before-registering');
    `;
    const {stdout} = await execute(process.execPath, ['--input-type=module', '-e', script, moduleUrl,
      JSON.stringify({nodeModulesRoot, fontFiles: [regular, {path: regular, sha256: '0'.repeat(64)}]})]);
    assert.equal(stdout.trim(), 'validated-before-registering');
  });

test('environment JSON is inherited by a fresh process and explicit options override it',
  {skip: !nodeModulesRoot || !existsSync(regular)}, async () => {
    const script = `
      const {loadNativeFonts}=await import(process.argv[1]);
      console.log(JSON.stringify(await loadNativeFonts({nodeModulesRoot:process.argv[2]})));
    `;
    const {stdout} = await execute(process.execPath, ['--input-type=module', '-e', script, moduleUrl, nodeModulesRoot],
      {env: {...process.env, C2_RUNTIME_FONT_FILES: JSON.stringify([regular])}});
    assert.equal(JSON.parse(stdout)[0].sha256, regularHash);
    const overrideScript = `
      const {loadNativeFonts}=await import(process.argv[1]);
      console.log(JSON.stringify(await loadNativeFonts({fontFiles:[]})));
    `;
    const overridden = await execute(process.execPath, ['--input-type=module', '-e', overrideScript, moduleUrl],
      {env: {...process.env, C2_RUNTIME_FONT_FILES: 'invalid-json'}});
    assert.deepEqual(JSON.parse(overridden.stdout), []);
  });

test('malformed environment configuration cannot silently fall back to system fonts', async () => {
  const script = `
    import assert from 'node:assert/strict';
    const {loadNativeFonts}=await import(process.argv[1]);
    await assert.rejects(loadNativeFonts({}),/IMAGE_LED_FONT/);
  `;
  for (const value of ['not-json', '{}', 'null', '[{"alias":"Microsoft YaHei"}]'])
    await execute(process.execPath, ['--input-type=module', '-e', script, moduleUrl],
      {env: {...process.env, C2_RUNTIME_FONT_FILES: value}});
});

test('a Heiti file named YaHei registers its real family, never an invented YaHei alias',
  {skip: !nodeModulesRoot || !existsSync(heiti)}, async t => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'image-led-font-identity-'));
    t.after(() => fs.rm(root, {recursive: true, force: true}));
    const heitiBytes = await fs.readFile(heiti);
    const heitiHash = createHash('sha256').update(heitiBytes).digest('hex');
    const misleading = path.join(root, 'Microsoft YaHei.ttc'); await fs.writeFile(misleading, heitiBytes);
    const script = `
      import assert from 'node:assert/strict';import path from 'node:path';import {createRequire} from 'node:module';
      const {loadNativeFonts}=await import(process.argv[1]), options=JSON.parse(process.argv[2]);
      const req=createRequire(path.join(options.nodeModulesRoot,'__font_identity__.cjs'));
      const {FontLibrary}=createRequire(req.resolve('@oai/artifact-tool'))('skia-canvas');
      const hadYaHei=FontLibrary.has('Microsoft YaHei');
      const loaded=await loadNativeFonts(options);
      assert.equal(FontLibrary.has('Microsoft YaHei'),hadYaHei);
      assert.ok(loaded[0].faces.some(face=>face.family.startsWith('Heiti')));
      assert.ok(loaded[0].faces.every(face=>face.family!=='Microsoft YaHei'));
      console.log(JSON.stringify(loaded));
    `;
    const {stdout} = await execute(process.execPath, ['--input-type=module', '-e', script, moduleUrl,
      JSON.stringify({nodeModulesRoot, fontFiles: [misleading]})]);
    assert.equal(JSON.parse(stdout)[0].sha256, heitiHash);
  });
