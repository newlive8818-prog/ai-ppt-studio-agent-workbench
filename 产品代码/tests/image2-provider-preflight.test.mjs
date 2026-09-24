/** Synthetic package + actual isolated MCP -> Python -> known wrapper preflight. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { resolvePythonExecutable } from '../mcp/runtime-bridge/python-runtime.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const KEYS = ['AI_PPT_IMAGE2_ADAPTER_COMMAND', 'AI_PPT_IMAGE2_RECEIVER', 'AI_PPT_IMAGE2_MODEL', 'AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST'];
const RELATIVE_WRAPPER = 'src/ai_ppt_studio/adapters/image2_crs.py';
const NATIVE_SCRIPT = 'scripts/image-led-native.mjs';
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');

function minimalEnvironment() {
  return {
    PATH: process.env.PATH,
    PYTHONDONTWRITEBYTECODE: '1',
    ...(process.env.TMPDIR ? { TMPDIR: process.env.TMPDIR } : {}),
  };
}

async function tree(root) {
  const result = [];
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      result.push([path.relative(root, absolute), entry.isDirectory() ? 'directory' : digest(await readFile(absolute))]);
      if (entry.isDirectory()) await walk(absolute);
    }
  }
  await walk(root);
  return result.sort((a, b) => a[0].localeCompare(b[0]));
}

const RUNNER = `
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const plugin=process.argv[1];
const requirePackage=createRequire(path.join(plugin,'package.json'));
const { Client } = await import(pathToFileURL(requirePackage.resolve('@modelcontextprotocol/sdk/client/index.js')).href);
const { InMemoryTransport } = await import(pathToFileURL(requirePackage.resolve('@modelcontextprotocol/sdk/inMemory.js')).href);
const { createAiPptMcpServer } = await import(pathToFileURL(path.join(plugin,'mcp/server.mjs')).href);
const client = new Client({name:'synthetic-provider-preflight',version:'0.1.0'});
const [left,right] = InMemoryTransport.createLinkedPair();
await Promise.all([client.connect(left),createAiPptMcpServer().connect(right)]);
try {
 const catalog=await client.listTools();
 const schema=catalog.tools.find(t=>t.name==='get_ai_ppt_project_snapshot').inputSchema;
 const result=await client.callTool({name:'get_ai_ppt_project_snapshot',arguments:JSON.parse(process.argv[2])});
 process.stdout.write(JSON.stringify({count:catalog.tools.length,schema,result}));
} finally { await client.close(); }
`;

async function packageFixture(base) {
  const emptyCwd = path.join(base, 'empty-cwd'); await mkdir(emptyCwd);
  const output = path.join(base,'release');
  // Exercise the actual builder and npm ci. A missing offline dependency must
  // fail; source-tree node_modules are never linked into the shipped package.
  const built=spawnSync(process.execPath,[path.join(ROOT,'scripts/build-plugin-release.mjs'),'--output',output,'--runtime-root',path.join(base,'runtime')],{
    cwd:emptyCwd,env:{...minimalEnvironment(),npm_config_offline:'true',npm_config_audit:'false',npm_config_fund:'false',
      ...(process.env.npm_config_cache ? {npm_config_cache:process.env.npm_config_cache} : {})},encoding:'utf8',timeout:180000,
  });
  assert.equal(built.status,0,built.stderr);
  return JSON.parse(built.stdout).pluginRoot;
}

function callMcp(plugin, env, args) {
  const run=spawnSync(process.execPath,['--input-type=module','-e',RUNNER,plugin,JSON.stringify(args)],{
    cwd:path.join(path.dirname(path.dirname(plugin)),'empty-cwd'),env,encoding:'utf8',timeout:30000,maxBuffer:4*1024*1024,
  });
  assert.equal(run.error,undefined,`isolated MCP process: ${run.stdout} ${run.stderr}`);
  assert.equal(run.status,0,run.stderr);
  return JSON.parse(run.stdout);
}

test('portable Skill keeps its wrapper and real offline Plugin includes the exact provider and native scripts', async (t) => {
  const base=await realpath(await mkdtemp(path.join(os.tmpdir(),'image2-provider-packages-')));
  t.after(()=>rm(base,{recursive:true,force:true}));
  let expected;
  try { expected=await readFile(path.join(ROOT,RELATIVE_WRAPPER)); }
  catch { assert.fail('approved provider wrapper is absent from the source packaging input'); }
  const skill=spawnSync(resolvePythonExecutable(),[path.join(ROOT,'scripts/build_skill_bundle.py'),'--output',path.join(base,'skill')],{
    cwd:base,env:minimalEnvironment(),encoding:'utf8',timeout:30000,
  });
  assert.equal(skill.status,0,skill.stderr);
  assert.deepEqual(await readFile(path.join(skill.stdout.trim(),'runtime/ai_ppt_studio/adapters/image2_crs.py')),expected);
  const plugin=await packageFixture(base);
  assert.deepEqual(await readFile(path.join(plugin,RELATIVE_WRAPPER)),expected);
  const manifest=JSON.parse(await readFile(path.join(plugin,'release-manifest.json')));
  assert.equal(manifest.files[RELATIVE_WRAPPER],digest(expected));
  const native=await readFile(path.join(ROOT,NATIVE_SCRIPT));
  assert.equal(manifest.files[NATIVE_SCRIPT],digest(native));
  assert.deepEqual(await readFile(path.join(plugin,NATIVE_SCRIPT)),native);
});

test('manifest declares four Image 2 environment keys without providing values', async () => {
  const manifest=JSON.parse(await readFile(path.join(ROOT,'.mcp.json')));
  const config=manifest.mcpServers.ai_ppt_studio;
  for (const key of KEYS) assert.ok(config.env_vars.includes(key),`missing declared forwarding key: ${key}`);
  assert.equal(config.env,undefined);
});

test('packaged actual MCP process reports only opted-in safe capability and counterfeit paths never run', async (t) => {
  // Python identifies the loaded package by its canonical path, including macOS
  // /var -> /private/var aliases. Configure this fixture with that same identity.
  const base=await realpath(await mkdtemp(path.join(os.tmpdir(),'image2-provider-mcp-')));
  t.after(()=>rm(base,{recursive:true,force:true}));
  const plugin=await packageFixture(base);
  const python=resolvePythonExecutable();
  const runtime=path.join(base,'runtime'), project=path.join(runtime,'projects/p1'), profile=path.join(runtime,'workspace.json');
  const setup=spawnSync(python,['-c',`
import json,sys
from pathlib import Path
from ai_ppt_studio.kernel.transactions import ProjectKernel
base=Path(sys.argv[1]); runtime=base/'runtime'
ProjectKernel.initialize(runtime/'projects/p1',project_id='p1')
(runtime/'workspace.json').write_text(json.dumps({'schema_version':'1.0','runtime_root':str(runtime),
 'source_repo_root':str(base/'protected-source'),'install_root':str(base/'protected-install'),
 'upstream_root':str(base/'protected-upstream'),'protected_roots':[str(base/'protected-source'),str(base/'protected-install'),str(base/'protected-upstream')]}))
`,base],{cwd:path.join(base,'empty-cwd'),env:{...minimalEnvironment(),PYTHONPATH:path.join(plugin,'src')},encoding:'utf8'});
  assert.equal(setup.status,0,setup.stderr);
  const configured={AI_PPT_PYTHON:python,AI_PPT_PYTHONPATH:path.join(plugin,'src'),
    [KEYS[0]]:JSON.stringify([python,path.join(plugin,RELATIVE_WRAPPER)]),[KEYS[1]]:'CRS',[KEYS[2]]:'gpt-image-2',[KEYS[3]]:'[]'};
  // Model launcher forwarding with the packaged manifest; if a key is omitted, it
  // is absent in the actual Node child and therefore in the actual Python child.
  const manifest=JSON.parse(await readFile(path.join(plugin,'.mcp.json')));
  const env={...minimalEnvironment(),AI_PPT_WORKSPACE_CONFIG:profile};
  for (const key of manifest.mcpServers.ai_ppt_studio.env_vars) if (key in configured) env[key]=configured[key];
  const before=await tree(runtime);
  const initial=callMcp(plugin,env,{projectRoot:project});
  assert.equal(initial.count,61);
  assert.equal(initial.schema.properties.includeImage2Preflight?.type,'boolean');
  assert.ok(!initial.schema.required?.includes('includeImage2Preflight'));
  assert.equal(initial.result.isError,undefined);
  assert.deepEqual(Object.keys(initial.result.structuredContent),['snapshot']);
  const explicitFalse=callMcp(plugin,env,{projectRoot:project,includeImage2Preflight:false});
  assert.deepEqual(explicitFalse.result.structuredContent,initial.result.structuredContent);
  const observed=callMcp(plugin,env,{projectRoot:project,includeImage2Preflight:true});
  assert.equal(observed.result.isError,undefined);
  assert.deepEqual(observed.result.structuredContent.snapshot,initial.result.structuredContent.snapshot);
  const safe=observed.result.structuredContent.image2_preflight;
  assert.deepEqual(Object.keys(safe).sort(),['configuration_presence','known_wrapper','protocol_probe','helper_executable','external_connection','wrapper_sha256','probe_nonce'].sort());
  assert.deepEqual(safe.configuration_presence,Object.fromEntries(KEYS.map(k=>[k,true])));
  assert.equal(safe.known_wrapper,true); assert.equal(safe.protocol_probe,'passed');
  assert.equal(typeof safe.helper_executable,'boolean'); assert.equal(safe.external_connection,'not-tested');
  assert.equal(safe.wrapper_sha256,digest(await readFile(path.join(plugin,RELATIVE_WRAPPER))));
  assert.match(safe.probe_nonce,/^[a-f0-9]{32}$/);
  assert.ok(!JSON.stringify(safe).includes(base));
  assert.deepEqual(await tree(runtime),before,'preflight cannot change any Runtime file or directory');
  const sunburst = 'gpt-image-2.5-sunburst';
  const sunburstCommand = [python,path.join(plugin,RELATIVE_WRAPPER),'--model',sunburst];
  const sunburstEnv = {...env,[KEYS[0]]:JSON.stringify(sunburstCommand),[KEYS[2]]:sunburst};
  const sunburstObserved = callMcp(plugin,sunburstEnv,{projectRoot:project,includeImage2Preflight:true});
  assert.equal(sunburstObserved.result.isError,undefined);
  const sunburstSafe = sunburstObserved.result.structuredContent.image2_preflight;
  assert.equal(sunburstSafe.known_wrapper,true); assert.equal(sunburstSafe.protocol_probe,'passed');
  assert.equal(sunburstSafe.external_connection,'not-tested');
  assert.equal(sunburstSafe.wrapper_sha256,safe.wrapper_sha256);
  assert.notEqual(sunburstSafe.probe_nonce,safe.probe_nonce);
  for (const overrides of [{[KEYS[0]]:env[KEYS[0]]}, {[KEYS[2]]:'gpt-image-2'},
    {[KEYS[2]]:'gpt-image-2.5-flare'}, {[KEYS[0]]:JSON.stringify([...sunburstCommand,'extra'])}]) {
    const rejected = callMcp(plugin,{...sunburstEnv,...overrides},{projectRoot:project,includeImage2Preflight:true});
    assert.equal(rejected.result.structuredContent.image2_preflight.known_wrapper,false);
    assert.equal(rejected.result.structuredContent.image2_preflight.protocol_probe,'unsupported');
  }
  assert.deepEqual(await tree(runtime),before,'Sunburst probes and rejected identities cannot write Runtime data');
  const marker=path.join(base,'counterfeit-ran'),counterfeit=path.join(base,'image2_crs.py');
  await writeFile(counterfeit,`from pathlib import Path\nPath(${JSON.stringify(marker)}).touch()\n`);
  const fake=callMcp(plugin,{...env,[KEYS[0]]:JSON.stringify([python,counterfeit])},{projectRoot:project,includeImage2Preflight:true});
  assert.equal(fake.result.structuredContent.image2_preflight.known_wrapper,false);
  assert.equal(fake.result.structuredContent.image2_preflight.protocol_probe,'unsupported');
  await assert.rejects(readFile(marker),{code:'ENOENT'});
  const malformed=callMcp(plugin,env,{projectRoot:project,includeImage2Preflight:'true'});
  assert.equal(malformed.result.isError,true);
  assert.deepEqual(await tree(runtime),before);
});
