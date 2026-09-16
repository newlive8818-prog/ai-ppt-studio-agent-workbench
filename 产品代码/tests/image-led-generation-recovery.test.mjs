/** Durable generation intent through the default MCP -> Python -> host adapter. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { resolvePythonExecutable } from "../mcp/runtime-bridge/python-runtime.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MCP_RUNNER = `
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createAiPptMcpServer } from './mcp/server.mjs';
const client=new Client({name:'image-led-durable-recovery',version:'0.1.0'});
const [left,right]=InMemoryTransport.createLinkedPair();
await Promise.all([client.connect(left),createAiPptMcpServer().connect(right)]);
try {
 const call=JSON.parse(process.argv[1]);
 const result=await client.callTool(call);
 process.stdout.write(JSON.stringify(result));
} finally {await client.close();}
`;

// Each call starts a fresh default server. Only the provider and host decisions
// are synthetic; no invokeBridge, transport, Runtime or response is mocked.
const FIXTURE = `
import base64,json,subprocess,sys
from copy import deepcopy
from tests.test_image_led_execution_entrypoint import ImageLedExecutionEntrypointTests
from tests.test_image2_input_boundary import confirm_scope,tree_snapshot
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.kernel.references import ArtifactReference
case=ImageLedExecutionEntrypointTests();case.setUp()
def rpc(name,args):
 run=subprocess.run([sys.argv[1],'--input-type=module','-e',sys.argv[2],json.dumps({'name':name,'arguments':args})],
     text=True,capture_output=True,env={**case.env,'AI_PPT_PYTHON':sys.executable},timeout=40)
 assert run.returncode==0,run.stdout+run.stderr
 return json.loads(run.stdout)
def action(**changes):
 args={'projectRoot':str(case.project),'expectedRevision':case.kernel.load().revision,
       'actionType':'generate-slide-images','targetRefs':[case.packs[0]],'instructions':'Synthetic single design request'}
 args.update(changes)
 return rpc('request_ai_ppt_agent_action',args)
def ok(reply):
 assert not reply.get('isError'),reply
 return reply['structuredContent']
def no_promotion():
 heads=case.kernel.load().artifact_heads
 assert not any(k.startswith('visual/image-led/candidate/') for k in heads)
 assert 'visual/image-led/selection' not in heads
 assert case.kernel.load().gate_status['G3']=='locked'
`;

function runScenario(body) {
  const fixture = `${FIXTURE}\ntry:\n${body.split("\n").filter(Boolean).map((line) => ` ${line}`).join("\n")}\nfinally:\n case.doCleanups()\n`;
  const result = spawnSync(resolvePythonExecutable(), ["-c", fixture, process.execPath, MCP_RUNNER], {
    cwd: ROOT,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: [path.join(ROOT, "src"), ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
    encoding: "utf8", timeout: 120000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return JSON.parse(result.stdout);
}

test("default unknown generation retry refreshes revision without a second request or adapter call", () => {
  const result = runScenario(`
case.configure_adapter('unknown')
first=ok(action())
assert first['generation_response']['status']=='unknown'
before=tree_snapshot(case.project)
second=ok(action())
assert len(case.calls())==1,{'adapter_calls':len(case.calls()),'expected':1,'first_request':first['generation_response']['request_id'],'retry_request':second['generation_response']['request_id']}
assert second['generation_response']['request_id']==first['generation_response']['request_id']
assert second['generation_response_ref']==first['generation_response_ref']
assert second['generation_response']['status']=='unknown'
assert tree_snapshot(case.project)==before,'same-intent recovery must be read-only'
no_promotion()
print(json.dumps({'adapter_calls':len(case.calls()),'same_request':True,'read_only':True}))
`);
  assert.deepEqual(result, { adapter_calls: 1, same_request: true, read_only: true });
});

test("explicit new IDs permit the same pack again while replay and ID conflicts cannot send", () => {
  const result = runScenario(`
grant=case.kernel.load().artifact_heads['kernel/confirmation-consumptions']
first=ok(action(generationIntent='new',generationRequestId='design-A'))
second=ok(action(generationIntent='new',generationRequestId='design-B'))
assert first['generation_response']['request_id']=='design-A'
assert second['generation_response']['request_id']=='design-B'
assert len(case.calls())==2,'a new intentional design must not be permanently deduplicated by pack'
assert case.calls()[0]['request']['payload']==case.calls()[1]['request']['payload']
before=tree_snapshot(case.project)
replayed=ok(action(generationIntent='new',generationRequestId='design-B'))
assert replayed['generation_response_ref']==second['generation_response_ref']
assert len(case.calls())==2,'replaying an explicit request id must not send again'
assert tree_snapshot(case.project)==before
for change in ({'instructions':'Different design intent'}, {'targetRefs':[case.packs[1]]}):
 rejected=action(generationIntent='new',generationRequestId='design-B',**change)
 assert rejected.get('isError'),'one persistent request ID cannot be rebound to another input'
 assert tree_snapshot(case.project)==before
 assert len(case.calls())==2
assert case.kernel.load().artifact_heads['kernel/confirmation-consumptions']==grant,'same authorized pack must not consume another user grant'
no_promotion()
print(json.dumps({'adapter_calls':len(case.calls()),'new_same_pack':True,'replay_read_only':True,'conflicts_rejected':2}))
`);
  assert.deepEqual(result, { adapter_calls: 2, new_same_pack: true, replay_read_only: true, conflicts_rejected: 2 });
});

test("explicit new without a persistent request ID fails before queue or provider execution", () => {
  const result = runScenario(`
before=tree_snapshot(case.project)
reply=action(generationIntent='new')
assert reply.get('isError'),'explicit new requires a caller-held persistent request id'
assert tree_snapshot(case.project)==before
assert len(case.calls())==0
print(json.dumps({'rejected':True,'adapter_calls':0,'read_only':True}))
`);
  assert.deepEqual(result, { rejected: true, adapter_calls: 0, read_only: true });
});

test("reserved active request ID is rejected before any write or provider execution", () => {
  const result = runScenario(`
before=tree_snapshot(case.project)
reply=action(generationIntent='new',generationRequestId='active')
assert reply.get('isError'),{'reason':'the active task slot cannot be a generation request identity',
 'adapter_calls':len(case.calls()),'tree_unchanged':tree_snapshot(case.project)==before}
assert tree_snapshot(case.project)==before,'a reserved request identity must fail before queueing or writing'
assert len(case.calls())==0,'a reserved request identity must never reach the provider'
no_promotion()
print(json.dumps({'rejected':True,'adapter_calls':0,'read_only':True}))
`);
  assert.deepEqual(result, { rejected: true, adapter_calls: 0, read_only: true });
});

test("ordinary short request ID remains recoverable after another explicit new design", () => {
  const result = runScenario(`
first=ok(action(generationIntent='new',generationRequestId='a'))
second=ok(action(generationIntent='new',generationRequestId='b'))
assert first['generation_response']['request_id']=='a'
assert second['generation_response']['request_id']=='b'
assert len(case.calls())==2,'ordinary short IDs must remain valid for intentional new designs'
for key in ('AI_PPT_IMAGE2_ADAPTER_COMMAND','AI_PPT_IMAGE2_RECEIVER','AI_PPT_IMAGE2_MODEL'):
 case.env.pop(key,None)
before=tree_snapshot(case.project)
reply=action(generationIntent='recover',generationRequestId='a',targetRefs=[],instructions='',expectedRevision=0)
recovered=ok(reply)
assert recovered['task']['task_id']=='a'
assert recovered['generation_response']['request_id']=='a'
assert recovered['generation_response_ref']==first['generation_response_ref']
assert recovered['generation_response']['status']=='completed'
assert recovered['generation_usability']['candidate_eligible'] is False
assert recovered['generation_usability']['status']=='stale'
images=[item for item in reply['content'] if item['type']=='image']
assert len(images)==1 and base64.b64decode(images[0]['data'])==case.raw_image
assert tree_snapshot(case.project)==before,'recovering the earlier short ID must not replace the active task'
assert len(case.calls())==2,'recovering an ordinary short ID must not send again'
no_promotion()
print(json.dumps({'adapter_calls':2,'original_request':'a','exact_image':True,'read_only':True}))
`);
  assert.deepEqual(result, { adapter_calls: 2, original_request: "a", exact_image: true, read_only: true });
});

test("original unknown request can be recovered without an adapter and never becomes a new send", () => {
  const result = runScenario(`
case.configure_adapter('unknown')
first=ok(action())
for key in ('AI_PPT_IMAGE2_ADAPTER_COMMAND','AI_PPT_IMAGE2_RECEIVER','AI_PPT_IMAGE2_MODEL'):
 case.env.pop(key,None)
before=tree_snapshot(case.project)
reply=action(generationIntent='recover',generationRequestId=first['generation_response']['request_id'],
 targetRefs=[],instructions='',expectedRevision=0)
recovered=ok(reply)
assert recovered['generation_response']['status']=='unknown'
assert recovered['generation_usability']['candidate_eligible'] is False
assert recovered['generation_usability']['status']=='unavailable'
assert recovered['generation_response_ref']==first['generation_response_ref']
assert recovered['generation_response']['request_id']==first['generation_response']['request_id']
assert not any(c['type']=='image' for c in reply['content'])
assert tree_snapshot(case.project)==before
assert len(case.calls())==1
no_promotion()
print(json.dumps({'status':'unknown','adapter_calls':1,'read_only':True}))
`);
  assert.deepEqual(result, { status: "unknown", adapter_calls: 1, read_only: true });
});

for (const change of ["stale-pack", "revoked-scope", "replaced-active-task"]) {
  test(`original completed request remains read-only recoverable after ${change} without an adapter`, () => {
    const result = runScenario(`
first=ok(action())
request_id=first['generation_response']['request_id']
old_revision=first['snapshot']['revision']
change=${JSON.stringify(change)}
if change=='stale-pack':
 policy=deepcopy(case.policy);policy['common_rules']['typography_tokens']['title']='Another confirmed font'
 case.service.commit_artifact('replace-input-policy',case.kernel.load().revision,policy)
elif change=='revoked-scope':
 confirm_scope(case.kernel,case.policy['authorization_scope_ref'],'revoked','recover-after-revocation')
else:
 ProjectCommandService(case.kernel).request_agent_action('replace-active-task',case.kernel.load().revision,
   action_type='generate-slide-images',target_refs=[case.packs[1]],instructions='Different queued design')
for key in ('AI_PPT_IMAGE2_ADAPTER_COMMAND','AI_PPT_IMAGE2_RECEIVER','AI_PPT_IMAGE2_MODEL'):
 case.env.pop(key,None)
before=tree_snapshot(case.project)
reply=action(generationIntent='recover',generationRequestId=request_id,targetRefs=[],instructions='',expectedRevision=old_revision)
recovered=ok(reply)
assert recovered['generation_response']['request_id']==request_id
assert recovered['generation_response_ref']==first['generation_response_ref']
assert recovered['generation_response']['status']=='completed'
assert recovered['generation_usability']['candidate_eligible'] is False
assert recovered['generation_usability']['status']=='stale'
assert recovered['generation_usability']['checked_revision']==case.kernel.load().revision
images=[item for item in reply['content'] if item['type']=='image']
assert len(images)==1 and base64.b64decode(images[0]['data'])==case.raw_image,'recovery must return the original exact image'
assert tree_snapshot(case.project)==before,'recovery must not reactivate or replace any current task'
assert len(case.calls())==1
pack=case.kernel.artifacts.resolve(ArtifactReference.parse(case.packs[0]))['payload']
copy=pack['confirmed_visible_copy']
candidate={'artifact_type':'image-led-candidate','project_id':'p1','request_id':request_id,
 'generation_response_ref':first['generation_response_ref'],'pack_ref':case.packs[0],
 'slide_id':pack['slide_id'],'page_order':pack['page_order'],'material_roles':[],
 'selected_copy':{'items':[{'item_id':'title','kind':'text','role':'title','text':copy['title']}]
  +[{'item_id':b['block_id'],'kind':'text','role':'body','text':b['text']} for b in copy['blocks']]}}
rejected=rpc('commit_ai_ppt_artifact',{'projectRoot':str(case.project),'expectedRevision':case.kernel.load().revision,
 'commandId':'no-historical-promotion','taskId':first['task']['task_id'],'kind':'visual-contract','payload':candidate})
assert rejected.get('isError'),'a historical response must not bypass current promotion dependencies'
assert tree_snapshot(case.project)==before
assert len(case.calls())==1
no_promotion()
print(json.dumps({'adapter_calls':1,'original_completed_response':True,'read_only':True,'promotion_rejected':True}))
`);
    assert.deepEqual(result, { adapter_calls: 1, original_completed_response: true, read_only: true, promotion_rejected: true });
  });
}

test("recovering an unexecuted queued task reports pending without loading the adapter or sending", () => {
  const result = runScenario(`
_,queued,_=ProjectCommandService(case.kernel).request_agent_action('queued-only',case.kernel.load().revision,
 action_type='generate-slide-images',target_refs=[case.packs[0]],instructions='Queued but never sent')
for key in ('AI_PPT_IMAGE2_ADAPTER_COMMAND','AI_PPT_IMAGE2_RECEIVER','AI_PPT_IMAGE2_MODEL'):
 case.env.pop(key,None)
before=tree_snapshot(case.project)
reply=ok(action(generationIntent='recover',generationRequestId=queued['task_id'],targetRefs=[],instructions='',expectedRevision=0))
assert reply['generation_response']['request_id']==queued['task_id']
assert reply['generation_response']['status']=='pending'
assert reply['generation_usability']['candidate_eligible'] is False
assert tree_snapshot(case.project)==before
assert len(case.calls())==0
no_promotion()
print(json.dumps({'status':'pending','adapter_calls':0,'read_only':True}))
`);
  assert.deepEqual(result, { status: "pending", adapter_calls: 0, read_only: true });
});

test("concurrent new intents cannot bind one request ID to different instructions", () => {
  const result = runScenario(`
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
revision=case.kernel.load().revision
barrier=Barrier(2)
def submit(instructions):
 barrier.wait(timeout=10)
 return action(generationIntent='new',generationRequestId='one-concurrent-intent',
   instructions=instructions,expectedRevision=revision)
with ThreadPoolExecutor(max_workers=2) as pool:
 jobs=[pool.submit(submit,instructions) for instructions in ('Intent A','Intent B')]
 replies=[job.result(timeout=50) for job in jobs]
passed=[reply for reply in replies if not reply.get('isError')]
assert len(passed)==1,{'successful_requests':len(passed),'errors':[r.get('isError') for r in replies]}
assert len(case.calls())==1,{'adapter_calls':len(case.calls()),'expected':1}
winner=ok(passed[0])
assert winner['generation_response']['request_id']=='one-concurrent-intent'
losing_instructions='Intent B' if winner['task']['instructions']=='Intent A' else 'Intent A'
before=tree_snapshot(case.project)
loser=action(generationIntent='new',generationRequestId='one-concurrent-intent',instructions=losing_instructions)
assert loser.get('isError'),'a concurrent losing intent cannot replace the winner later'
assert tree_snapshot(case.project)==before
assert len(case.calls())==1
no_promotion()
print(json.dumps({'winner_count':1,'adapter_calls':1,'conflict_read_only':True}))
`);
  assert.deepEqual(result, { winner_count: 1, adapter_calls: 1, conflict_read_only: true });
});
