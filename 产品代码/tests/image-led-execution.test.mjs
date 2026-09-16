import assert from "node:assert/strict";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createAiPptMcpServer } from "../mcp/server.mjs";

test("existing image generation action displays returned exact image and keeps result references", async () => {
  const data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==";
  const calls = [];
  const server = createAiPptMcpServer({ invokeBridge: async (request) => {
    calls.push(request);
    return { ok: true, result: {
      task: { task_id: "synthetic-task", status: "queued" },
      generation_response_ref: "artifact://image-led-generation-response/" + "a".repeat(64),
      generation_response: { status: "completed", image_base64: data,
        image_mime_type: "image/png", image_size: [1, 1], image_sha256: "b".repeat(64) },
      follow_up_message: "Synthetic image returned; transcription still required.",
    } };
  } });
  const client = new Client({ name: "image-generation-entry", version: "0.1.0" });
  const [left, right] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left), server.connect(right)]);
  try {
    const result = await client.callTool({ name: "request_ai_ppt_agent_action", arguments: {
      projectRoot: "/managed/synthetic", expectedRevision: 5, actionType: "generate-slide-images",
      targetRefs: ["artifact://image-led-input-pack/" + "c".repeat(64)], instructions: "test only",
    } });
    assert.equal(calls[0].operation, "request-agent-action");
    assert.equal(calls[0].action_type, "generate-slide-images");
    assert.deepEqual(result.content.find((item) => item.type === "image"), {
      type: "image", data, mimeType: "image/png",
    });
    assert.match(result.structuredContent.generation_response_ref, /^artifact:\/\//);
    assert.equal(result.structuredContent.generation_response.image_base64, undefined);
    assert.equal((await client.listTools()).tools.length, 43);
  } finally { await client.close(); }
});

test("unknown image generation reports uncertainty without an image or duplicate payload", async () => {
  const response = { status: "unknown", request_id: "original-request", image_base64: "must-not-display" };
  const server = createAiPptMcpServer({ invokeBridge: async () => ({ ok: true, result: {
    generation_response_ref: "artifact://image-led-generation-response/" + "d".repeat(64),
    generation_response: response,
    follow_up_message: "生成结果未知；查询原请求，不可重新发起相同任务。",
  } }) });
  const client = new Client({ name: "image-generation-unknown", version: "0.1.0" });
  const [left, right] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(left), server.connect(right)]);
  try {
    const result = await client.callTool({ name: "request_ai_ppt_agent_action", arguments: {
      projectRoot: "/managed/synthetic", expectedRevision: 5, actionType: "generate-slide-images",
      targetRefs: ["artifact://image-led-input-pack/" + "c".repeat(64)], instructions: "test only",
    } });
    assert.equal(result.content.length, 1);
    assert.match(result.content[0].text, /生成结果未知/);
    assert.equal(result.structuredContent.generation_response.status, "unknown");
    assert.equal(result.structuredContent.generation_response.request_id, "original-request");
    assert.equal(result.structuredContent.generation_response.image_base64, undefined);
    assert.equal(response.image_base64, "must-not-display", "display must not mutate the bridge response");
  } finally { await client.close(); }
});
