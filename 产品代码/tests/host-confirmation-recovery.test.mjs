import assert from 'node:assert/strict';
import test from 'node:test';
import { setTimeout as delay, setImmediate as nextTurn } from 'node:timers/promises';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { ElicitRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { createAiPptMcpServer } from '../mcp/server.mjs';
import { createOpenAIFormCompatibleTransport } from '../mcp/host-form-transport.mjs';

// Isolated protocol fixtures only. No customer project, real host, or user receipt.
const ref = (kind) => `artifact://${kind}/${'a'.repeat(64)}`;
const missionInput = {
  projectRoot: '/synthetic/project', expectedRevision: 3,
  missionDraftRef: ref('mission-draft'), materialMode: 'materials-provided',
  materialInventoryRef: ref('material-inventory'),
  missionSummary: { topic: 'Synthetic mission', primaryAudience: 'Fixture audience',
    desiredJudgmentOrAction: 'Fixture action', materialSummary: 'Fixture materials' },
};
const context = {
  project_id: 'synthetic', project_root: '/synthetic/project',
  source_version: 'synthetic-v1', evidence_refs: [ref('test-evidence')],
  challenge_id: 'b'.repeat(64), challenge_revision: 3, review_summary: 'Synthetic review',
};
const targets = {
  mission: { name: 'confirm_ai_ppt_mission', arguments: missionInput },
  gate: { name: 'confirm_ai_ppt_gate', arguments: { projectRoot: '/synthetic/project', expectedRevision: 3, gate: 'G0' } },
  plan: { name: 'confirm_content_batch_revision_plan', arguments: {
    projectRoot: '/synthetic/project', expectedRevision: 3, planRef: ref('content-batch-revision-plan'), sourceVersion: 'synthetic-v1' } },
  image: { name: 'submit_ai_ppt_human_decision', arguments: {
    projectRoot: '/synthetic/project', expectedRevision: 3, targetRef: ref('image-led-authorization-scope'), choice: 'approved' } },
};
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function setup({ hostResult, options = {}, standard = false } = {}) {
  const calls = [], frames = [], forms = [], verifierCalls = [];
  const server = createAiPptMcpServer({
    ...options,
    ...(options.verifier ? { confirmationVerifier: { verify: async (request) => {
      verifierCalls.push(request); return options.verifier(request);
    } } } : {}),
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === 'get-gate-confirmation-context') return {
        ok: true, confirmation_context: { ...context, gate: 'G0', scope_kind: 'gate', scope_id: 'G0' },
      };
      if (request.operation === 'get-content-revision-plan-confirmation-context') return {
        ok: true, confirmation_context: { ...context, scope_kind: 'content-revision-plan', scope_id: ref('content-batch-revision-plan') },
      };
      if (request.operation === 'get-image-led-confirmation-context') return {
        ok: true, image_led: true, confirmation_context: { ...context,
          scope_kind: 'image-led-authorization', scope_id: ref('image-led-authorization-scope'),
          target_ref: ref('image-led-authorization-scope'), choice: 'approved',
          evidence_refs: [ref('image-led-authorization-scope')] },
      };
      return { ok: true, result: { synthetic: true } };
    },
  });
  const client = new Client({ name: 'synthetic-confirmation-recovery', version: '1' }, {
    capabilities: standard ? { elicitation: { form: {} } } :
      { extensions: { 'openai/form': {} }, elicitation: { form: {} } },
  });
  let fallbackCount = 0;
  client.setRequestHandler(ElicitRequestSchema, async (request) => {
    fallbackCount += 1;
    return typeof hostResult === 'function' ? hostResult(request) : hostResult;
  });
  const [left, right] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left), server.connect(createOpenAIFormCompatibleTransport(right))]);
  const forwarded = left.onmessage;
  const sentResponses = [];
  left.onmessage = (message, extra) => {
    frames.push(message);
    if (message.method !== 'openai/form') { forwarded?.(message, extra); return; }
    forms.push(message);
    const response = Promise.resolve().then(() => typeof hostResult === 'function' ? hostResult(message) : hostResult)
      .then((result) => left.send({ jsonrpc: '2.0', id: message.id, result }))
      .catch((error) => left.send({ jsonrpc: '2.0', id: message.id,
        error: { code: error.code ?? -32603, message: error.message } }));
    sentResponses.push(response);
  };
  return { calls, forms, frames, verifierCalls, client, server,
    fallbackCount: () => fallbackCount,
    writes: () => calls.filter((r) => !r.operation.startsWith('get-')),
    invoke: (target = targets.mission, requestOptions) => client.callTool(target, undefined, requestOptions),
    close: async () => { await Promise.all(sentResponses); await client.close(); await server.close(); },
  };
}

for (const [name, target] of Object.entries(targets)) {
  test(`${name}: unchecked accepted form is incomplete, not a decline or approval`, async () => {
    const fixture = await setup({ hostResult: { action: 'accept', content: { confirmed: false }, _meta: null } });
    try {
      const result = await fixture.invoke(target);
      assert.equal(result.isError, true);
      assert.equal(result.structuredContent.error.code, 'HOST_CONFIRMATION_NOT_COMPLETED');
      assert.equal(result.structuredContent.error.details.action, 'accept');
      assert.equal(result.structuredContent.error.details.confirmed, false);
      assert.doesNotMatch(result.structuredContent.error.message, /已取消|拒绝|撤销/);
      assert.equal(fixture.forms.length, 1);
      assert.equal(fixture.fallbackCount(), 0);
      assert.equal(fixture.writes().length, 0);
    } finally { await fixture.close(); }
  });
}

test('form timeout cancels its request and ignores a late accept without retry or write', async () => {
  const fixture = await setup({ options: { hostConfirmationTimeoutMs: 40 },
    hostResult: async () => { await delay(120); return { action: 'accept', content: { confirmed: true }, _meta: null }; } });
  try {
    const result = await fixture.invoke();
    assert.equal(result.isError, true);
    const error = result.structuredContent.error;
    assert.equal(error.code, 'HOST_CONFIRMATION_UNAVAILABLE');
    assert.equal(error.details.reason, 'timeout');
    assert.equal(error.details.timeout_ms, 40);
    assert.equal(error.details.error_code, -32001);
    assert.ok(error.details.elapsed_ms >= 30);
    assert.match(error.details.attempt_id, /^[0-9a-f-]{36}$/);
    await delay(150);
    assert.ok(fixture.frames.some((r) => r.method === 'notifications/cancelled' && r.params.requestId === fixture.forms[0].id));
    assert.equal(fixture.writes().length, 0);
    assert.equal(fixture.forms.length, 1);
    assert.equal(fixture.fallbackCount(), 0);
  } finally { await fixture.close(); }
});

test('cancelling the parent tool cancels its pending form and prevents a late confirmation write', async () => {
  const started = deferred(), respond = deferred();
  const fixture = await setup({ hostResult: async () => {
    started.resolve(); await respond.promise;
    return { action: 'accept', content: { confirmed: true } };
  } });
  try {
    const controller = new AbortController();
    const pending = fixture.invoke(targets.mission, { signal: controller.signal });
    await started.promise;
    controller.abort();
    await assert.rejects(pending);
    await nextTurn(); await nextTurn();
    respond.resolve();
    await delay(20);
    assert.ok(fixture.frames.some((r) => r.method === 'notifications/cancelled' && r.params.requestId === fixture.forms[0].id));
    assert.equal(fixture.writes().length, 0);
    assert.equal(fixture.forms.length, 1);
  } finally { respond.resolve(); await fixture.close(); }
});

test('protocol diagnostics preserve safe code and timing without leaking host error text', async () => {
  const fixture = await setup({ hostResult: () => { throw new Error('secret customer content and credential'); } });
  try {
    const result = await fixture.invoke();
    const details = result.structuredContent.error.details;
    assert.equal(details.phase, 'host-form-response');
    assert.equal(details.transport, 'openai-form');
    assert.equal(details.reason, 'transport-error');
    assert.equal(details.error_code, -32603);
    assert.equal(details.error_name, 'McpError');
    assert.ok(Number.isFinite(details.elapsed_ms));
    assert.doesNotMatch(JSON.stringify(result), /secret|credential|customer content/);
    assert.equal(fixture.forms.length, 1);
    assert.equal(fixture.fallbackCount(), 0);
    assert.equal(fixture.writes().length, 0);
  } finally { await fixture.close(); }
});

test('malformed host response is classified safely as invalid-response', async () => {
  const fixture = await setup({ hostResult: {
    action: 'private-provider-payload', content: { confirmed: 'secret customer content' },
  } });
  try {
    const result = await fixture.invoke();
    assert.equal(result.isError, true);
    const error = result.structuredContent.error;
    assert.equal(error.code, 'HOST_CONFIRMATION_UNAVAILABLE');
    assert.equal(error.details.reason, 'invalid-response');
    assert.equal(error.details.error_name, 'ZodError');
    assert.equal(error.details.error_code, null);
    assert.doesNotMatch(JSON.stringify(result), /private-provider|secret|customer content/);
    assert.equal(fixture.forms.length, 1);
    assert.equal(fixture.fallbackCount(), 0);
    assert.equal(fixture.writes().length, 0);
  } finally { await fixture.close(); }
});

for (const name of ['mission', 'gate', 'plan']) {
  test(`${name}: truthy verifier output cannot authorize or open a fallback form`, async () => {
    const fixture = await setup({ options: { verifier: () => ({ approved: true }) }, hostResult: { action: 'accept', content: { confirmed: true } } });
    try {
      const target = targets[name];
      const result = await fixture.invoke({ ...target, arguments: { ...target.arguments, userMessageRef: 'synthetic://not-a-real-user-receipt' } });
      assert.equal(result.isError, true);
      assert.equal(fixture.verifierCalls.length, 1);
      assert.equal(fixture.writes().length, 0);
      assert.equal(fixture.forms.length, 0);
    } finally { await fixture.close(); }
  });
}

test('Mission passes exact material inventory and revision to an injected verifier', async () => {
  const fixture = await setup({ options: { verifier: () => true } });
  try {
    const result = await fixture.invoke({ ...targets.mission, arguments: { ...missionInput, userMessageRef: 'synthetic://message' } });
    assert.equal(result.isError, undefined);
    assert.equal(fixture.verifierCalls[0].expectedRevision, 3);
    assert.equal(fixture.verifierCalls[0].materialInventoryRef, missionInput.materialInventoryRef);
    assert.equal(fixture.forms.length, 0);
  } finally { await fixture.close(); }
});

for (const name of ['mission', 'gate', 'plan', 'image']) {
  test(`${name}: cancelled request cannot consume a later verifier success`, async () => {
    const started = deferred(), respond = deferred();
    const fixture = await setup({ options: { verifier: async () => {
      started.resolve(); await respond.promise; return true;
    } } });
    try {
      const controller = new AbortController();
      const target = targets[name];
      const pending = fixture.invoke({ ...target, arguments: { ...target.arguments, userMessageRef: 'synthetic://message' } }, { signal: controller.signal });
      await started.promise;
      controller.abort();
      await assert.rejects(pending);
      await nextTurn(); await nextTurn();
      respond.resolve();
      await delay(20);
      assert.equal(fixture.writes().length, 0);
      assert.equal(fixture.forms.length, 0);
    } finally { respond.resolve(); await fixture.close(); }
  });
}

for (const name of ['mission', 'gate', 'plan']) {
  test(`${name}: verifier failure returns a safe capability error and does not open a form`, async () => {
    const fixture = await setup({ options: { verifier: () => { throw new Error('secret provider credential'); } } });
    try {
      const target = targets[name];
      const result = await fixture.invoke({ ...target, arguments: { ...target.arguments, userMessageRef: 'synthetic://message' } });
      assert.equal(result.isError, true);
      assert.equal(result.structuredContent?.error.code, 'HOST_CONFIRMATION_UNAVAILABLE');
      assert.equal(result.structuredContent.error.details.phase, 'host-message-verification');
      assert.doesNotMatch(JSON.stringify(result), /secret|credential/);
      assert.equal(fixture.writes().length, 0);
      assert.equal(fixture.forms.length, 0);
    } finally { await fixture.close(); }
  });
}

test('standard elicitation preserves unchecked submission semantics and caller timeout', async () => {
  const fixture = await setup({ standard: true, options: { hostConfirmationTimeoutMs: 40 },
    hostResult: { action: 'accept', content: { confirmed: false } } });
  try {
    const result = await fixture.invoke();
    assert.equal(result.structuredContent.error.code, 'HOST_CONFIRMATION_NOT_COMPLETED');
    assert.equal(fixture.fallbackCount(), 1);
    assert.equal(fixture.forms.length, 0);
    assert.equal(fixture.writes().length, 0);
  } finally { await fixture.close(); }
  const slow = await setup({ standard: true, options: { hostConfirmationTimeoutMs: 40 },
    hostResult: async () => { await delay(120); return { action: 'accept', content: { confirmed: true } }; } });
  try {
    const result = await slow.invoke();
    assert.equal(result.structuredContent.error.details.reason, 'timeout');
    assert.equal(result.structuredContent.error.details.transport, 'standard-elicitation');
    await delay(150);
    assert.equal(slow.writes().length, 0);
    assert.equal(slow.fallbackCount(), 1);
    assert.equal(slow.forms.length, 0);
  } finally { await slow.close(); }
});
