/** Closed public finding schema and unchanged 43-tool surface. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createAiPptMcpServer } from '../mcp/server.mjs';

test('finding is a closed alternative of the existing 43-tool material entry', async () => {
  const calls=[];
  const server=createAiPptMcpServer({invokeBridge:async request => {calls.push(request); return {ok:true,result:{artifact_ref:'artifact://material-finding/'+ 'a'.repeat(64)}};}});
  const client=new Client({name:'finding-schema',version:'1'});
  const [left,right]=InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left),server.connect(right)]);
  try {
    assert.equal((await client.listTools()).tools.length,43);
    const good={projectRoot:'/synthetic/project',expectedRevision:1,materialType:'finding',
      materialInventoryRef:'artifact://material-inventory/'+ 'b'.repeat(64), sourceId:'source-one',
      sourceSha256:'c'.repeat(64),sourceLocation:{kind:'object',page:1,object_id:'39'},contentKind:'image',exclusionMode:'image-content'};
    const result=await client.callTool({name:'add_ai_ppt_material',arguments:good});
    assert.ok(!result.isError,JSON.stringify(result));
    assert.equal(calls.length,1);
    assert.equal(calls[0].operation,'add-material');
    assert.deepEqual(calls[0].source_location,good.sourceLocation);
    for(const [key,value] of Object.entries({value:'',dataBase64:'',label:'',filename:'',mimeType:'',payload:{},kind:'material-finding',contentSha256:'d'.repeat(64),unexpected:true,commandId:'caller'})) {
      const before=calls.length;
      const result=await client.callTool({name:'add_ai_ppt_material',arguments:{...good,[key]:value}});
      assert.ok(result.isError,key);
      assert.equal(calls.length,before,key);
    }
    for(const key of ['projectRoot','materialInventoryRef','sourceId','sourceSha256','sourceLocation','contentKind','exclusionMode']) {
      const missing={...good}; delete missing[key];
      assert.ok((await client.callTool({name:'add_ai_ppt_material',arguments:missing})).isError,key);
      if(key !== 'projectRoot') assert.ok((await client.callTool({name:'add_ai_ppt_material',arguments:{projectRoot:good.projectRoot,expectedRevision:1,materialType:'text',value:'kept',[key]:good[key]}})).isError,key);
    }
    assert.ok((await client.callTool({name:'add_ai_ppt_material',arguments:{...good,contentKind:'text'}})).isError);
    assert.equal(calls.length,1);
  } finally {await client.close();}
});

import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolvePythonExecutable } from '../mcp/runtime-bridge/python-runtime.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function fixture(mode,root,...args) {
  const result=spawnSync(resolvePythonExecutable(),['-m','tests.material_finding_mcp_e2e',mode,root,...args],{
    cwd:ROOT,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:[path.join(ROOT,'src'),ROOT,process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)}});
  assert.equal(result.status,0,result.stdout+result.stderr);
  return JSON.parse(result.stdout);
}

test('public MCP finding reaches content gates, synthetic trusted G0, and exact-byte input pack',async()=>{
  const root=mkdtempSync(path.join(os.tmpdir(),'c2-public-finding-'));
  const seed=fixture('bootstrap',root);
  const previousConfig=process.env.AI_PPT_WORKSPACE_CONFIG;
  process.env.AI_PPT_WORKSPACE_CONFIG=seed.config;
  let revision=seed.revision;
  const client=new Client({name:'finding-real-python-chain',version:'1'});
  const server=createAiPptMcpServer();
  const [left,right]=InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left),server.connect(right)]);
  const call=async(name,values)=>{
    const result=await client.callTool({name,arguments:{projectRoot:seed.projectRoot,expectedRevision:revision,...values}});
    assert.ok(!result.isError,JSON.stringify(result));
    const data=result.structuredContent;
    revision=data.snapshot.revision;
    return data;
  };
  try {
    assert.equal((await client.listTools()).tools.length,43);
    const finding=(await call('add_ai_ppt_material',{materialType:'finding',materialInventoryRef:seed.inventory,
      sourceId:seed.sourceId,sourceSha256:seed.sourceSha256,sourceLocation:{kind:'whole-source'},contentKind:'text',exclusionMode:'scope'})).artifact_ref;
    const bind=value=>JSON.parse(JSON.stringify(value).replaceAll('artifact://material-finding/'+ 'a'.repeat(64),finding));
    const evidence=bind(seed.evidence); evidence.material_inventory_ref=seed.inventory;evidence.mission_confirmation_ref=seed.confirmation;
    const evidenceRef=(await call('build_presales_evidence_book',{payload:evidence})).artifact_ref;
    const context=seed.context;context.evidence_book_ref=evidenceRef;
    const contextRef=(await call('build_customer_decision_context',{payload:context})).artifact_ref;
    const fit=bind(seed.fit);fit.evidence_book_ref=evidenceRef;fit.decision_context_ref=contextRef;
    const fitRef=(await call('build_problem_solution_fit',{payload:fit})).artifact_ref;
    const deck=bind(seed.blueprint);deck.project_id='public-finding-e2e';deck.evidence_book_ref=evidenceRef;
    deck.decision_context_ref=contextRef;deck.problem_solution_fit_ref=fitRef;deck.slides[0].material_views=[];
    const deckRef=(await call('build_reading_deck_blueprint',{payload:deck})).artifact_ref;
    for(const [name,ids] of [
      ['run_content_evidence_gate',['selective-evidence-risk','unsupported-causality','unsupported-capability-result-commitment']],
      ['run_content_presales_reading_gate',['customer-decision-position','problem-completeness','whole-deck-coherence-and-repetition','boundary-risk-validation-next-step']]]) {
      await call(name,{sourceVersion:'content-v1',reviewerMode:'isolated-review-task',semanticCheckResults:ids.map(check_id=>({
        check_id,applicability:'applicable',result:'passed',hard:true,evidence_refs:[deckRef],failure_reason:''}))});
    }
    const result=fixture('finish',seed.projectRoot,finding);
    assert.equal(result.G0,'passed');assert.equal(result.exact_source_bytes,true);
    assert.equal(result.finding_public_ingress,true);assert.equal(result.adapter_calls,0);
    assert.equal(result.synthetic_host_only,true);
    assert.match(result.pack_ref,/^artifact:\/\/image-led-input-pack\//);
  } finally {await client.close(); if(previousConfig===undefined)delete process.env.AI_PPT_WORKSPACE_CONFIG;else process.env.AI_PPT_WORKSPACE_CONFIG=previousConfig;rmSync(root,{recursive:true,force:true});}
});
