import assert from "node:assert/strict";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import {
  AI_PPT_WIDGET_URI,
  createAiPptMcpServer,
} from "../mcp/server.mjs";
import { PythonBridgeError } from "../mcp/runtime-bridge/python-runtime.mjs";

const snapshot = {
  schema_version: "2.0",
  revision: 3,
  updated_at: "2026-08-02T00:00:00Z",
  active_space: "overview",
  project: { project_id: "p1", name: "测试项目", project_root: "/managed/project" },
  gate_state: { current_gate: "G0", gates: { G0: "open" } },
  cognition_map: {
    delivery_goal: "促成一期立项",
    audiences: ["客户领导"],
    problem: "确认建设路径",
    ai_judgment: "先形成内容蓝图",
    facts: [],
    confirmed_decisions: [],
    uncertainty: "案例证据仍需补充",
    affected_artifacts: [],
    outcome_status: "成果正在形成中",
    dialogue_focus: "案例证据仍需补充",
  },
  artifacts: {},
  current_decision: {
    target_ref: "project://next-focus",
    status: "available",
    question: "是否继续？",
    options: ["继续推进", "提出修改"],
  },
  last_human_decision_id: null,
  allowed_next_actions: ["submit-human-decision"],
};

async function connectedClient() {
  const calls = [];
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "submit-human-decision") {
      return {
        ok: true,
        result: {
          decision: { decision_id: "d1", choice: request.choice },
          snapshot: { ...snapshot, revision: 4 },
          follow_up_message: "继续处理",
          model_context: { project_revision: 4 },
          affected_artifacts: ["project"],
        },
      };
    }
    return { ok: true, snapshot };
  };
  const server = createAiPptMcpServer({ invokeBridge });
  const client = new Client({ name: "ai-ppt-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  return { client, server, calls };
}

test("MCP exposes decoupled data tools and one render tool", async () => {
  const { client, calls } = await connectedClient();
  try {
    const tools = await client.listTools();
    assert.deepEqual(
      tools.tools.map((tool) => tool.name).sort(),
      [
        "get_ai_ppt_project_snapshot",
        "render_ai_ppt_workbench",
        "submit_ai_ppt_human_decision",
      ],
    );
    const readTool = tools.tools.find((tool) => tool.name === "get_ai_ppt_project_snapshot");
    const renderTool = tools.tools.find((tool) => tool.name === "render_ai_ppt_workbench");
    assert.equal(readTool._meta?.ui?.resourceUri, undefined);
    assert.equal(renderTool._meta?.ui?.resourceUri, AI_PPT_WIDGET_URI);

    const result = await client.callTool({
      name: "render_ai_ppt_workbench",
      arguments: { projectRoot: "/managed/project", requestedDisplayMode: "inline" },
    });
    assert.equal(result.structuredContent.snapshot.project.name, "测试项目");
    assert.equal(result._meta.widgetData.snapshot.revision, 3);
    assert.equal(result._meta["openai/outputTemplate"], AI_PPT_WIDGET_URI);
    assert.equal(calls[0].operation, "get-project-snapshot");
  } finally {
    await client.close();
  }
});

test("decision tool returns follow-up intent and refreshed projection", async () => {
  const { client } = await connectedClient();
  try {
    const result = await client.callTool({
      name: "submit_ai_ppt_human_decision",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        targetRef: "project://next-focus",
        choice: "继续推进",
        feedback: "",
      },
    });
    assert.equal(result.structuredContent.snapshot.revision, 4);
    assert.equal(result.structuredContent.follow_up_message, "继续处理");
    assert.equal(result._meta.widgetData.snapshot.revision, 4);
  } finally {
    await client.close();
  }
});

test("decision tool exposes revision conflicts as stable structured tool errors", async () => {
  const server = createAiPptMcpServer({
    invokeBridge: async () => {
      throw new PythonBridgeError(
        {
          error: {
            code: "REVISION_CONFLICT",
            message: "项目状态已更新，请刷新后重试。",
            details: { expected_revision: 2, actual_revision: 3 },
          },
        },
        1,
      );
    },
  });
  const client = new Client({ name: "ai-ppt-error-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "submit_ai_ppt_human_decision",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 2,
        targetRef: "project://next-focus",
        choice: "继续推进",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent.error.code, "REVISION_CONFLICT");
    assert.deepEqual(result.structuredContent.error.details, {
      expected_revision: 2,
      actual_revision: 3,
    });
    assert.match(result.content[0].text, /状态已更新/);
    assert.doesNotMatch(result.content[0].text, /PythonBridgeError|at /);
  } finally {
    await client.close();
  }
});
