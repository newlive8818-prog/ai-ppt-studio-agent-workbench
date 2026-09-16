import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const [plugin,project,output]=process.argv.slice(2);
const req=createRequire(path.join(plugin,'package.json'));
const {Client}=await import(pathToFileURL(req.resolve('@modelcontextprotocol/sdk/client/index.js')).href);
const {StdioClientTransport}=await import(pathToFileURL(req.resolve('@modelcontextprotocol/sdk/client/stdio.js')).href);
const {PUBLIC_TOOL_CATALOG,PUBLIC_TOOL_CATALOG_SHA256}=await import(pathToFileURL(path.join(plugin,'mcp/tool-catalog.mjs')).href);
const env={...process.env};
const client=new Client({name:'c2-392642f-package-stdio',version:'1.0'});
const transport=new StdioClientTransport({command:process.execPath,args:[path.join(plugin,'scripts/start-mcp.mjs')],cwd:process.cwd(),env,stderr:'pipe'});
let stderr='';if(transport.stderr)transport.stderr.on('data',x=>stderr+=x);
const hash=x=>createHash('sha256').update(x).digest('hex');
async function tree(root){const out={};async function walk(p){for(const e of await fs.readdir(p,{withFileTypes:true})){const q=path.join(p,e.name);if(e.isDirectory())await walk(q);else out[path.relative(root,q)]=hash(await fs.readFile(q));}}await walk(root);return out;}
const runtime=path.dirname(path.dirname(project));const before=await tree(runtime);
await client.connect(transport);
try{
 const tools=(await client.listTools()).tools.sort((a,b)=>a.name.localeCompare(b.name));
 assert.equal(tools.length,43);assert.deepEqual(tools.map(t=>t.name),PUBLIC_TOOL_CATALOG.map(t=>t.name).sort((a,b)=>a.localeCompare(b)));
 const schemaHash=hash(JSON.stringify(tools.map(({name,inputSchema})=>({name,inputSchema}))));
 assert.equal(schemaHash,'4e7d91f5da614f67e2f2b1d6c09ef7a68044070397d40e18952014582180c9ea');
 const auth=tools.find(t=>t.name==='submit_ai_ppt_human_decision').inputSchema;
 assert.deepEqual(auth.properties.confirmationMode.enum,['verified-message-only','allow-native']);assert.ok(!auth.required.includes('confirmationMode'));
 const snap=tools.find(t=>t.name==='get_ai_ppt_project_snapshot').inputSchema;assert.equal(snap.properties.includeImage2Preflight.type,'boolean');
 const call=async args=>{const r=await client.callTool({name:'get_ai_ppt_project_snapshot',arguments:{projectRoot:project,...args}});assert.ok(!r.isError,JSON.stringify(r));return r.structuredContent;};
 const initial=await call({}),off=await call({includeImage2Preflight:false}),p1=await call({includeImage2Preflight:true}),p2=await call({includeImage2Preflight:true});
 assert.deepEqual(off,initial);assert.deepEqual(p1.snapshot,initial.snapshot);assert.deepEqual(p2.snapshot,initial.snapshot);
 for(const x of [p1,p2]){assert.equal(x.image2_preflight.known_wrapper,true);assert.equal(x.image2_preflight.protocol_probe,'passed');assert.equal(x.image2_preflight.external_connection,'not-tested');assert.equal(x.image2_preflight.wrapper_sha256,hash(await fs.readFile(path.join(plugin,'src/ai_ppt_studio/adapters/image2_crs.py'))));}
 assert.notEqual(p1.image2_preflight.probe_nonce,p2.image2_preflight.probe_nonce);
 assert.deepEqual(await tree(runtime),before);
 const report={status:'PASS',configured_model:env.AI_PPT_IMAGE2_MODEL,configured_argv:JSON.parse(env.AI_PPT_IMAGE2_ADAPTER_COMMAND),transport:'actual-stdio-child-process-of-isolated-probe',plugin_root:plugin,tool_count:43,input_schema_sha256:schemaHash,tool_catalog_sha256:PUBLIC_TOOL_CATALOG_SHA256,confirmation_modes:auth.properties.confirmationMode.enum,preflight_default_snapshot_unchanged:true,preflights:[p1.image2_preflight,p2.image2_preflight],synthetic_runtime_files:Object.keys(before).length,synthetic_runtime_unchanged:true,customer_runtime_access:false,host_installation:false,real_host_loading:false,provider_authentication:'not-tested',stderr_empty:stderr==='',v2_boundary:'Public snapshot checks default preflight; separate packaged adapter and wrapper probes check explicit v2 generation protocol.'};
 await fs.writeFile(output,JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify(report)+'\n');
}finally{await client.close();}
