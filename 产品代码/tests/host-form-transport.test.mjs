import assert from "node:assert/strict";
import test from "node:test";

import { createOpenAIFormCompatibleTransport } from "../mcp/host-form-transport.mjs";

class RecordingTransport {
  constructor() {
    this.sent = [];
    this.started = 0;
    this.closed = 0;
    this.failNextSend = false;
    this.sessionId = "session-1";
    this.protocolVersions = [];
  }

  async start() {
    this.started += 1;
  }

  async send(message, options) {
    if (this.failNextSend) {
      this.failNextSend = false;
      throw new Error("send failed");
    }
    this.sent.push({ message, options });
  }

  async close() {
    this.closed += 1;
    this.onclose?.();
  }

  setProtocolVersion(version) {
    this.protocolVersions.push(version);
  }

  receive(message, extra) {
    this.onmessage?.(message, extra);
  }
}

function openAIFormRequest(id = 7) {
  return {
    jsonrpc: "2.0",
    id,
    method: "openai/form",
    params: {
      message: "Confirm",
      requestedSchema: { type: "object" },
    },
  };
}

function nullableSuccess(id = 7) {
  return {
    jsonrpc: "2.0",
    id,
    result: {
      action: "accept",
      content: { confirmed: true, _meta: null },
      _meta: null,
    },
  };
}

test("normalizes nullable metadata only for a tracked openai/form success response", async () => {
  const inner = new RecordingTransport();
  const received = [];
  const transport = createOpenAIFormCompatibleTransport(inner);
  transport.onmessage = (message) => received.push(message);

  await transport.start();
  await transport.send(openAIFormRequest());
  inner.receive(nullableSuccess());

  assert.equal(inner.started, 1);
  assert.deepEqual(inner.sent.map(({ message }) => message), [openAIFormRequest()]);
  assert.deepEqual(received, [{
    jsonrpc: "2.0",
    id: 7,
    result: {
      action: "accept",
      content: { confirmed: true, _meta: null },
    },
  }]);
});

test("forwards untracked, object metadata, and error responses unchanged", async () => {
  const inner = new RecordingTransport();
  const received = [];
  const transport = createOpenAIFormCompatibleTransport(inner);
  transport.onmessage = (message) => received.push(message);
  await transport.start();

  const untracked = nullableSuccess(99);
  await transport.send(openAIFormRequest(8));
  const objectMeta = {
    jsonrpc: "2.0",
    id: 8,
    result: {
      action: "accept",
      content: { confirmed: true },
      _meta: { source: "host" },
    },
  };
  await transport.send(openAIFormRequest(9));
  const error = {
    jsonrpc: "2.0",
    id: 9,
    error: { code: -32603, message: "host failed" },
  };

  inner.receive(untracked);
  inner.receive(objectMeta);
  inner.receive(error);

  assert.deepEqual(received, [untracked, objectMeta, error]);
});

test("clears a tracked id after its first result", async () => {
  const inner = new RecordingTransport();
  const received = [];
  const transport = createOpenAIFormCompatibleTransport(inner);
  transport.onmessage = (message) => received.push(message);
  await transport.start();
  await transport.send(openAIFormRequest());

  inner.receive(nullableSuccess());
  inner.receive(nullableSuccess());

  assert.equal(received[0].result._meta, undefined);
  assert.equal(received[1].result._meta, null);
});

test("clears a tracked id after cancellation, failed send, and close", async () => {
  const inner = new RecordingTransport();
  const received = [];
  const transport = createOpenAIFormCompatibleTransport(inner);
  transport.onmessage = (message) => received.push(message);
  await transport.start();

  await transport.send(openAIFormRequest(10));
  await transport.send({
    jsonrpc: "2.0",
    method: "notifications/cancelled",
    params: { requestId: 10, reason: "test" },
  });
  inner.receive(nullableSuccess(10));

  inner.failNextSend = true;
  await assert.rejects(
    transport.send(openAIFormRequest(11)),
    /send failed/,
  );
  inner.receive(nullableSuccess(11));

  await transport.send(openAIFormRequest(12));
  await transport.close();
  inner.receive(nullableSuccess(12));

  assert.deepEqual(
    received.map((message) => message.result._meta),
    [null, null, null],
  );
  assert.equal(inner.closed, 1);
});

test("delegates session, protocol version, callbacks, and send options", async () => {
  const inner = new RecordingTransport();
  const transport = createOpenAIFormCompatibleTransport(inner);
  const errors = [];
  let closes = 0;
  transport.onerror = (error) => errors.push(error.message);
  transport.onclose = () => {
    closes += 1;
  };

  assert.equal(transport.sessionId, "session-1");
  transport.setProtocolVersion("2025-11-25");
  await transport.start();
  await transport.send(
    { jsonrpc: "2.0", method: "notifications/initialized" },
    { relatedRequestId: 4 },
  );
  inner.onerror?.(new Error("inner error"));
  await transport.close();

  assert.deepEqual(inner.protocolVersions, ["2025-11-25"]);
  assert.deepEqual(inner.sent[0].options, { relatedRequestId: 4 });
  assert.deepEqual(errors, ["inner error"]);
  assert.equal(closes, 1);
});
