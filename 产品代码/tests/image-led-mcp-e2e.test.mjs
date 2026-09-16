/** Synthetic host adapter through the default MCP -> Python execution chain. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createAiPptMcpServer } from "../mcp/server.mjs";
import { resolvePythonExecutable } from "../mcp/runtime-bridge/python-runtime.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("the 43-tool catalog accurately marks the externally executing Agent action", async () => {
  const server = createAiPptMcpServer();
  const client = new Client({ name: "image-led-world-boundary", version: "0.1.0" });
  const [left, right] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left), server.connect(right)]);
  try {
    const tools = (await client.listTools()).tools;
    assert.equal(tools.length, 43);
    const action = tools.find((tool) => tool.name === "request_ai_ppt_agent_action");
    assert.equal(action.annotations.openWorldHint, true);
    assert.equal(tools.find((tool) => tool.name === "get_ai_ppt_project_status").annotations.openWorldHint, false);
  } finally { await client.close(); }
});

test("default MCP executes Python and the host adapter once and returns the exact image without selecting it", () => {
  const runner = `
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createAiPptMcpServer } from './mcp/server.mjs';
const server=createAiPptMcpServer();
const client=new Client({name:'image-led-default-mcp-e2e',version:'0.1.0'});
const [left,right]=InMemoryTransport.createLinkedPair();
await Promise.all([client.connect(left),server.connect(right)]);
try {
  const tools=(await client.listTools()).tools;
  const result=await client.callTool({name:'request_ai_ppt_agent_action',arguments:JSON.parse(process.argv[1])});
  process.stdout.write(JSON.stringify({count:tools.length,result}));
} finally {await client.close();}
`;
  // Reuse the existing real authorization/input fixture; only the provider is
  // synthetic. Nothing injects invokeBridge, transport, or an approved selection.
  const fixture = `
import base64,json,subprocess,sys
from tests.test_image_led_execution_entrypoint import ImageLedExecutionEntrypointTests
case=ImageLedExecutionEntrypointTests();case.setUp()
try:
 args={'projectRoot':str(case.project),'expectedRevision':case.kernel.load().revision,
       'actionType':'generate-slide-images','targetRefs':[case.packs[0]],'instructions':'Synthetic e2e only.'}
 run=subprocess.run([sys.argv[1],'--input-type=module','-e',sys.argv[2],json.dumps(args)],
     text=True,capture_output=True,env={**case.env,'AI_PPT_PYTHON':sys.executable},timeout=40)
 assert run.returncode==0,run.stderr
 response=json.loads(run.stdout)
 assert not response['result'].get('isError'),response
 content=response['result']['content']
 images=[item for item in content if item['type']=='image']
 assert len(images)==1
 image=images[0]
 assert base64.b64decode(image['data'])==case.raw_image
 structured=response['result']['structuredContent']
 assert structured['generation_response']['status']=='completed'
 assert 'image_base64' not in structured['generation_response']
 assert 'selected_copy' not in structured['generation_response']
 assert structured['generation_response_ref'].startswith('artifact://image-led-generation-response/')
 state=case.kernel.load()
 assert state.gate_status['G3']=='locked'
 assert 'visual/image-led/selection' not in state.artifact_heads
 assert not any(slot.startswith('visual/image-led/candidate/') for slot in state.artifact_heads)
 assert len(case.calls())==1
 assert not case.calls()[0]['leaked_host_secret']
 print(json.dumps({'tools':response['count'],'exact_image_bytes':True,'adapter_calls':len(case.calls()),
   'mime':image['mimeType'],'candidate_created':False,'selection_created':False,'G3':state.gate_status['G3']}))
finally:
 case.doCleanups()
`;
  const result = spawnSync(resolvePythonExecutable(), ["-c", fixture, process.execPath, runner], {
    cwd: ROOT,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: [path.join(ROOT, "src"), ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
    encoding: "utf8", timeout: 50000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), { tools: 43, exact_image_bytes: true, adapter_calls: 1,
    mime: "image/png", candidate_created: false, selection_created: false, G3: "locked" });
});
