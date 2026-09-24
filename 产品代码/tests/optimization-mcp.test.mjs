import assert from 'node:assert/strict';
import test from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createAiPptMcpServer } from '../mcp/server.mjs';

async function clientWithBridge() {
  const requests = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      requests.push(request);
      return { ok: true, operation: request.operation,
        result: { received: request, snapshot: { revision: request.expected_revision + 1 } },
        optimization: { source: { page_count: 2 }, delivery_status: 'not-established' },
        handoff: { handoff_version: 'existing-deck/v1' } };
    },
  });
  const client = new Client({ name: 'optimization-test', version: '1.0.0' });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await server.connect(a);
  await client.connect(b);
  return { client, requests, async close() { await client.close(); await server.close(); } };
}

const toolNames = [
  'begin_existing_deck_optimization', 'set_existing_deck_external_scope',
  'register_existing_deck_image_request', 'register_existing_deck_historical_design',
  'execute_existing_deck_image_request', 'recover_existing_deck_image_request',
  'withdraw_existing_deck_unsent_request', 'supersede_existing_deck_response',
  'register_existing_deck_local_media_composition', 'review_existing_deck_image_response',
  'select_existing_deck_images_internal', 'register_existing_deck_native_plan',
  'compile_existing_deck_native_handoff', 'register_existing_deck_native_result',
  'register_existing_deck_target_evidence', 'register_existing_deck_full_deck_qa',
  'get_existing_deck_optimization_status',
  'preview_existing_deck_design_image',
];

test('publishes the complete, explicit existing-deck operation set', async () => {
  const host = await clientWithBridge();
  try {
    const tools = await host.client.listTools();
    assert.deepEqual(tools.tools.map(tool => tool.name).filter(name => toolNames.includes(name)), toolNames);
    const old = tools.tools.find(tool => tool.name === 'get_ai_ppt_project_snapshot');
    assert.ok(old, 'the original project path remains public');
  } finally { await host.close(); }
});


test('recovers the original existing-deck request identity without an execution revision', async () => {
  const host = await clientWithBridge();
  try {
    const result = await host.client.callTool({ name: 'recover_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', requestId: 'started-p12',
    } });
    assert.equal(result.isError, undefined);
    assert.deepEqual(host.requests.at(-1), {
      operation: 'optimization-recover-request', project_root: '/managed/source-project',
      request_id: 'started-p12',
    });
  } finally { await host.close(); }
});

test('maps exact historical design bytes and provenance to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const imageDataBase64 = Buffer.from('historical-image-bytes').toString('base64');
    const result = await host.client.callTool({ name: 'register_existing_deck_historical_design', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 59,
      requestId: 'historical-p13', slideId: 'S0013', titleItemId: 'source-object-2',
      commonRules: { title_bar: 'fixed' }, imageDataBase64, imageSha256: 'a'.repeat(64),
      sourcePptxSha256: 'b'.repeat(64), pageOrder: 13,
      historicalRequestId: 'old-p13', historicalRequestSha256: 'c'.repeat(64),
      historicalResponseSha256: 'd'.repeat(64), historicalReceiver: 'CRS',
      historicalModel: 'gpt-image-2', historicalQuality: 'medium',
    } });
    assert.equal(result.isError, undefined);
    assert.deepEqual(host.requests.at(-1), {
      operation: 'optimization-register-historical-design',
      project_root: '/managed/source-project', expected_revision: 59,
      request_id: 'historical-p13', slide_id: 'S0013', title_item_id: 'source-object-2',
      common_rules: { title_bar: 'fixed' }, image_base64: imageDataBase64,
      image_sha256: 'a'.repeat(64), provenance: {
        source_pptx_sha256: 'b'.repeat(64), page_order: 13,
        historical_request_id: 'old-p13', historical_request_sha256: 'c'.repeat(64),
        historical_response_sha256: 'd'.repeat(64), historical_receiver: 'CRS',
        historical_model: 'gpt-image-2', historical_quality: 'medium',
      },
    });
  } finally { await host.close(); }
});

test('rejects malformed historical identity before calling the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const before = host.requests.length;
    const result = await host.client.callTool({ name: 'register_existing_deck_historical_design', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 59,
      requestId: 'historical-p13', slideId: 'S0013', titleItemId: 'source-object-2',
      commonRules: { title_bar: 'fixed' }, imageDataBase64: 'not-base64', imageSha256: 'a'.repeat(64),
      sourcePptxSha256: 'b'.repeat(64), pageOrder: 13, historicalRequestId: 'old-p13',
      historicalRequestSha256: 'broken', historicalResponseSha256: 'd'.repeat(64),
      historicalReceiver: 'CRS', historicalModel: 'latest', historicalQuality: 'medium',
    } });
    assert.equal(result.isError, true);
    assert.equal(host.requests.length, before);
  } finally { await host.close(); }
});

test('passes exact source and result identity to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const begin = await host.client.callTool({ name: toolNames[0], arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 46,
      sourceId: 'source-1', sourcePptxSha256: 'a'.repeat(64),
      userMessageRef: 'chat://message/current-instruction',
    } });
    assert.equal(begin.isError, undefined);
    assert.deepEqual(host.requests.at(-1), {
      operation: 'optimization-begin', project_root: '/managed/source-project',
      expected_revision: 46, source_id: 'source-1',
      source_pptx_sha256: 'a'.repeat(64),
      user_message_ref: 'chat://message/current-instruction',
    });
    const status = await host.client.callTool({ name: 'get_existing_deck_optimization_status', arguments: {
      projectRoot: '/managed/source-project',
    } });
    assert.deepEqual(status.structuredContent.source, { page_count: 2 });
    assert.equal(host.requests.at(-1).operation, 'optimization-status');
  } finally { await host.close(); }
});

test('accepts the governed source-media-guided layout mode', async () => {
  const host = await clientWithBridge();
  try {
    const result = await host.client.callTool({ name: 'register_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 51,
      requestId: 'guided-p01', slideId: 'S0001', titleItemId: 'source-object-3',
      commonRules: { title_bar: 'fixed' }, layoutMode: 'source-media-guided',
    } });
    assert.equal(result.isError, undefined);
    assert.equal(host.requests.at(-1).layout_mode, 'source-media-guided');
  } finally { await host.close(); }
});

test('passes the exact single-main-screenshot focus identity to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const result = await host.client.callTool({ name: 'register_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 55,
      requestId: 'main-screen-p37', slideId: 'S0037', titleItemId: 'source-object-3',
      commonRules: { title_bar: 'fixed' }, layoutMode: 'single-main-screenshot-focus',
      mainSourcePictureObjectId: '161',
    } });
    assert.equal(result.isError, undefined);
    assert.equal(host.requests.at(-1).layout_mode, 'single-main-screenshot-focus');
    assert.equal(host.requests.at(-1).main_source_picture_object_id, '161');
  } finally { await host.close(); }
});

test('passes exact source-visible revision requirements to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const result = await host.client.callTool({ name: 'register_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 52,
      requestId: 'revision-p12', slideId: 'S0012', titleItemId: 'source-object-3',
      commonRules: { title_bar: 'fixed' }, layoutMode: 'source-media-guided',
      requiredVisibleItemIds: ['source-object-65', 'source-object-29', 'source-object-33'],
    } });
    assert.equal(result.isError, undefined);
    assert.deepEqual(host.requests.at(-1).required_visible_item_ids,
      ['source-object-65', 'source-object-29', 'source-object-33']);
  } finally { await host.close(); }
});

test('passes exact source-media role bindings to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const sourceMediaRoleBindings = [{
      picture_object_id: '9', text_item_ids: ['source-object-12'],
    }, {
      picture_object_id: '20', text_item_ids: ['source-object-16'],
    }];
    const result = await host.client.callTool({ name: 'register_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 54,
      requestId: 'media-role-p19', slideId: 'S0019', titleItemId: 'source-object-2',
      commonRules: { title_bar: 'fixed' }, layoutMode: 'source-media-guided',
      sourceMediaRoleBindings,
    } });
    assert.equal(result.isError, undefined);
    assert.deepEqual(host.requests.at(-1).source_media_role_bindings, sourceMediaRoleBindings);
  } finally { await host.close(); }
});

test('passes exact source relationship constraints to the Python bridge', async () => {
  const host = await clientWithBridge();
  try {
    const relationshipConstraints = [{
      kind: 'belongs-to',
      source_item_ids: ['source-object-29', 'source-object-36'],
      target_item_ids: ['source-object-25'],
    }];
    const result = await host.client.callTool({ name: 'register_existing_deck_image_request', arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 53,
      requestId: 'relationship-p20', slideId: 'S0020', titleItemId: 'source-object-2',
      commonRules: { title_bar: 'fixed' },
      relationshipConstraints,
    } });
    assert.equal(result.isError, undefined);
    assert.deepEqual(host.requests.at(-1).relationship_constraints, relationshipConstraints);
  } finally { await host.close(); }
});

test('rejects missing target identities at the public boundary without a Python write', async () => {
  const host = await clientWithBridge();
  try {
    const bad = await host.client.callTool({ name: toolNames[3], arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 46,
    } });
    assert.equal(bad.isError, true);
    assert.deepEqual(host.requests, []);
    const invalid = await host.client.callTool({ name: toolNames[8], arguments: {
      projectRoot: '/managed/source-project', expectedRevision: 46,
      reviewerTaskId: 'reviewer', selections: [{}],
    } });
    assert.equal(invalid.isError, true);
    assert.deepEqual(host.requests, []);
  } finally { await host.close(); }
});

test('renders the exact current design in MCP image content without duplicating base64 in metadata', async () => {
  const requests = [];
  const server = createAiPptMcpServer({ invokeBridge: async request => {
    requests.push(request);
    return { ok: true, image: { slide_id: 'S0001', page_order: 1,
      image_sha256: 'f'.repeat(64), image_mime_type: 'image/png',
      preview_role: 'provider-design', image_base64: 'iVBORw0KGgo=' } };
  } });
  const client = new Client({ name: 'preview-test', version: '1.0.0' });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await server.connect(a);
  await client.connect(b);
  try {
    const result = await client.callTool({ name: 'preview_existing_deck_design_image',
      arguments: { projectRoot: '/managed/source-project', requestId: 'page-1' } });
    assert.equal(result.isError, undefined);
    assert.equal(result.content.at(-1).type, 'image');
    assert.equal(result.content.at(-1).data, 'iVBORw0KGgo=');
    assert.equal(result.structuredContent.preview_role, 'provider-design');
    assert.equal(Object.hasOwn(result.structuredContent, 'image_base64'), false);
    assert.equal(requests[0].operation, 'optimization-preview-image');
  } finally { await client.close(); await server.close(); }
});
