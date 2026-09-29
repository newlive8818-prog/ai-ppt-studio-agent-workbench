/** Load only explicitly configured real fonts into the renderer's own Skia runtime. */
import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

const fail = message => { throw new Error('IMAGE_LED_FONT: ' + message); };
const check = (condition, message) => { if (!condition) fail(message); };

function configuration(options) {
  let files;
  if (Object.hasOwn(options, 'fontFiles')) files = options.fontFiles;
  else if (process.env.C2_RUNTIME_FONT_FILES !== undefined) {
    try { files = JSON.parse(process.env.C2_RUNTIME_FONT_FILES); }
    catch { fail('C2_RUNTIME_FONT_FILES must be a JSON array of exact font paths'); }
  } else files = [];
  check(Array.isArray(files), 'fontFiles must be an array; family aliases are forbidden');
  return files.map(entry => {
    if (typeof entry === 'string') entry = {path: entry};
    check(entry && typeof entry === 'object' && !Array.isArray(entry) &&
      Object.keys(entry).every(key => ['path', 'sha256'].includes(key)) && Object.hasOwn(entry, 'path'),
      'Font entries accept only path and optional sha256; aliases are forbidden');
    check(typeof entry.path === 'string' && path.isAbsolute(entry.path) && path.resolve(entry.path) === entry.path &&
      !/[\0*?\[\]{}]/.test(entry.path) && /\.(ttf|otf|ttc)$/i.test(entry.path),
      'Font path must be an exact canonical absolute TTF, OTF or TTC file');
    if (Object.hasOwn(entry, 'sha256'))
      check(typeof entry.sha256 === 'string' && /^[0-9a-f]{64}$/.test(entry.sha256), 'Invalid font SHA-256');
    return {...entry};
  });
}

async function fileHash(file) {
  try {
    check((await fs.stat(file)).isFile(), 'Configured font must be a regular file');
    const hash = createHash('sha256');
    for await (const chunk of createReadStream(file)) hash.update(chunk);
    return hash.digest('hex');
  } catch (error) {
    if (error.message.startsWith('IMAGE_LED_FONT:')) throw error;
    fail('Configured font cannot be read: ' + file);
  }
}

/** Host-only options; never take font paths or family aliases from a handoff. */
export async function loadNativeFonts(options = {}) {
  const files = configuration(options);
  if (!files.length) return [];
  // Validate the whole input before any process-global font registration.
  for (const file of files) {
    const actual = await fileHash(file.path);
    check(file.sha256 === undefined || file.sha256 === actual, 'Font SHA-256 does not match actual bytes: ' + file.path);
    file.sha256 = actual;
  }
  const modules = options.nodeModulesRoot ?? process.env.C2_RUNTIME_NODE_MODULES;
  check(typeof modules === 'string' && path.isAbsolute(modules), 'Absolute bundled nodeModulesRoot is required');
  let FontLibrary;
  try {
    const runtime = createRequire(path.join(modules, '__image_led_fonts__.cjs'));
    ({FontLibrary} = createRequire(runtime.resolve('@oai/artifact-tool'))('skia-canvas'));
  } catch { fail('The renderer Skia font runtime is unavailable'); }
  const evidence = [];
  for (const file of files) {
    let loaded;
    try { loaded = FontLibrary.use(file.path); } // One path argument: no alias overload.
    catch { fail('Skia could not load the configured font: ' + file.path); }
    check(Array.isArray(loaded) && loaded.length > 0 && loaded.every(face =>
      typeof face.family === 'string' && face.family.length > 0 && Number.isFinite(face.weight)),
      'Skia did not report real font family and weight metadata');
    check(await fileHash(file.path) === file.sha256, 'Font bytes changed during registration: ' + file.path);
    evidence.push({path: file.path, sha256: file.sha256, faces: loaded.map(face => ({
      family: face.family, weight: face.weight, style: face.style, width: face.width,
    }))});
  }
  return evidence;
}
