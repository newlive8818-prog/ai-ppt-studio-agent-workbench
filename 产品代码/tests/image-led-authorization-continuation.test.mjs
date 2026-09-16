/** Real MCP -> Python scope registration; synthetic project and host only. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { resolvePythonExecutable } from "../mcp/runtime-bridge/python-runtime.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("real scope registration emits a current reuse-only continuation without a grant or a form", () => {
  const runner = `
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { ElicitRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { createAiPptMcpServer } from './mcp/server.mjs';
const server=createAiPptMcpServer();
const client=new Client({name:'synthetic-authorization-continuation',version:'0.1.0'},
  {capabilities:{elicitation:{form:{}}}});
let forms=0;
client.setRequestHandler(ElicitRequestSchema,async()=>{forms++;return {action:'cancel'};});
const [left,right]=InMemoryTransport.createLinkedPair();
await Promise.all([client.connect(left),server.connect(right)]);
try {
  const registered=await client.callTool({name:'commit_ai_ppt_artifact',arguments:JSON.parse(process.argv[1])});
  assert.equal(registered.isError,undefined,JSON.stringify(registered));
  const receipt=registered.structuredContent;
  const continuation=receipt.authorization_continuation;
  assert.equal(continuation?.status,'requires-verified-message');
  assert.equal(continuation.call.arguments.expectedRevision,receipt.snapshot.revision);
  assert.equal(continuation.call.arguments.projectRoot,receipt.snapshot.project.project_root);
  assert.equal(continuation.call.arguments.targetRef,receipt.artifact_ref);
  assert.equal(continuation.call.arguments.confirmationMode,'verified-message-only');
  const outcome=await client.callTool(continuation.call);
  assert.equal(outcome.structuredContent.error.code,'CAPABILITY_GAP');
  assert.equal(outcome.structuredContent.error.details.reason,'verified-message-adapter-unavailable');
  assert.equal(forms,0);
  process.stdout.write(JSON.stringify({revision:receipt.snapshot.revision,scope:receipt.artifact_ref,forms}));
} finally {await client.close();}
`;
  const fixture = `
import json,subprocess,sys
from tests.test_image_led_execution_entrypoint import ImageLedExecutionEntrypointTests
case=ImageLedExecutionEntrypointTests();case.setUp()
try:
 before=case.kernel.load()
 args={'projectRoot':str(case.project),'expectedRevision':before.revision,'kind':'visual-contract',
       'payload':{'artifact_type':'image-led-authorization-scope','project_id':case.kernel.project_id,
         'receiver':'synthetic-continuation-provider','model':'gpt-image-2','allowed':[],'excluded':[]}}
 run=subprocess.run([sys.argv[1],'--input-type=module','-e',sys.argv[2],json.dumps(args)],
     text=True,capture_output=True,env={**case.env,'AI_PPT_PYTHON':sys.executable},timeout=40)
 assert run.returncode==0,run.stdout+run.stderr
 receipt=json.loads(run.stdout)
 after=case.kernel.load()
 assert after.revision==before.revision+1==receipt['revision']
 assert after.artifact_heads['visual/image-led/scope']==receipt['scope']
 assert after.artifact_heads.get('visual/image-led/authorization')==before.artifact_heads.get('visual/image-led/authorization')
 assert after.artifact_heads.get('kernel/confirmation-consumptions')==before.artifact_heads.get('kernel/confirmation-consumptions')
 assert after.gate_status==before.gate_status
 assert case.calls()==[]
 print(json.dumps({'scope_registration_writes':1,'new_grants':0,'forms':receipt['forms'],'provider_calls':0}))
finally:case.doCleanups()
`;
  const result = spawnSync(resolvePythonExecutable(), ["-c", fixture, process.execPath, runner], {
    cwd: ROOT,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(ROOT, "src"), ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
    encoding: "utf8", timeout: 50000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    scope_registration_writes: 1, new_grants: 0, forms: 0, provider_calls: 0,
  });
});
