import assert from "node:assert/strict";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ElicitRequestSchema } from "@modelcontextprotocol/sdk/types.js";

import { createAiPptMcpServer } from "../mcp/server.mjs";
import { PythonBridgeError } from "../mcp/runtime-bridge/python-runtime.mjs";
import { PUBLIC_TOOL_CATALOG } from "../mcp/tool-catalog.mjs";

const snapshot = {
  schema_version: "3.0",
  revision: 3,
  project: { project_id: "p1", name: "测试项目", project_root: "/managed/project" },
  gate_state: { current_gate: "G0", gates: { G0: "open" } },
  artifacts: {},
  workspace: {
    active_space: "overview",
    navigation: ["overview", "materials", "blueprint", "visual", "delivery"].map((space_id) => ({
      space_id, label: space_id, status: "open", high_impact_count: 0,
    })),
    overview: {}, materials: {}, blueprint: {}, visual: {},
    delivery: {
      targets: ["macos-powerpoint", "macos-wps", "windows-powerpoint", "windows-wps"].map((target_id) => ({
        target_id, status: "pending", pptx_sha256: "",
      })),
    },
  },
  experience: {},
  allowed_next_actions: ["submit-human-decision"],
};

const review = {
  review_type: "visual",
  display_policy: "professional-review",
  project_id: "p1",
  project_name: "测试项目",
  title: "视觉合同专业审阅",
  source_version: "visual-v0001-abc123",
  source_refs: ["visual-contract:v0001:abc123"],
  sections: [{ anchor: "visual-overview", title: "完整视觉合同", value: {} }],
  outline: [{ anchor: "visual-overview", title: "完整视觉合同" }],
  mark_set: { marks: [] },
};

async function connectedClient(options = {}) {
  const calls = [];
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-review-projection") {
      return { ok: true, review: { ...review, review_type: request.review_type }, snapshot_revision: 3 };
    }
    if (request.operation === "get-delivery-status-projection") {
      return { ok: true, delivery: { status: "qa-passed", chat_delivery: {} }, snapshot_revision: 3 };
    }
    if (request.operation === "get-project-user-status") {
      return {
        ok: true,
        status: { status: "成果已可查看", reason: "审核对象已准备" },
        selected_project_root: "/managed/project",
      };
    }
    if (request.operation === "open-or-resume-review-session") {
      return {
        ok: true,
        session: {
          review_session_id: "review-session-1",
          review_type: request.review_type,
          source_version: request.source_version,
        },
        snapshot_revision: request.expected_revision + 1,
        selected_project_root: "/managed/project",
      };
    }
    if ([
      "record-review-host-open",
      "record-review-host-notification",
      "record-review-ai-receipt",
    ].includes(request.operation)) {
      return {
        ok: true,
        session: {
          review_session_id: request.review_session_id,
          receipt_ref: request.receipt_ref,
        },
        snapshot_revision: request.expected_revision + 1,
        selected_project_root: "/managed/project",
      };
    }
    if (request.operation === "get-gate-confirmation-context") {
      const gate = request.gate;
      return {
        ok: true,
        confirmation_context: {
          project_id: "p1",
          gate,
          source_version: `artifact://${gate === "G0" ? "content-blueprint" : gate === "G3" ? "visual-contract" : "delivery-package"}/${"a".repeat(64)}`,
          evidence_refs: [`artifact://test-evidence/${"b".repeat(64)}`],
          challenge_id: `challenge-${gate}-revision-3`,
          challenge_revision: 3,
          review_summary: `${gate} 当前完整审阅源。`,
        },
      };
    }
    if (request.operation !== "get-project-snapshot") {
      return {
        ok: true,
        result: {
          decision: {
            decision_id: "d1",
            choice: request.choice,
            task_id: "task-1",
            status: "requested",
          },
          snapshot: { ...snapshot, revision: 4 },
          follow_up_message: "继续处理",
          model_context: { project_revision: 4 },
          affected_artifacts: ["project"],
        },
      };
    }
    return { ok: true, snapshot };
  };
  const server = createAiPptMcpServer({
    invokeBridge,
    reviewBridgeFactory: () => ({
      async start() {
        return {
          url: "http://127.0.0.1:43123/#token=short-lived-token",
          expiresAt: 123456,
        };
      },
      async stop() {},
    }),
    confirmationVerifier: {
      async verify() {
        return true;
      },
    },
    ...options,
  });
  const client = new Client({ name: "ai-ppt-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  return { client, server, calls };
}

test("MCP exposes data contracts without rendering a Widget in chat", async () => {
  const { client, calls } = await connectedClient();
  try {
    const tools = await client.listTools();
    assert.deepEqual(
      tools.tools.map((tool) => tool.name).sort(),
      PUBLIC_TOOL_CATALOG.map((tool) => tool.name).sort(),
    );
    const readTool = tools.tools.find((tool) => tool.name === "get_ai_ppt_project_snapshot");
    assert.equal(readTool._meta?.ui?.resourceUri, undefined);
    const saveTool = tools.tools.find((tool) => tool.name === "save_review_marks");
    assert.equal(saveTool._meta?.ui?.resourceUri, undefined);
    assert.deepEqual(Object.keys(saveTool.inputSchema.properties.marks.items.properties).sort(), [
      "comment", "exact_text", "field_anchor", "mark_id", "prefix", "suffix",
    ]);
    const policyTool = tools.tools.find(
      (tool) => tool.name === "set_ai_ppt_release_target_policy",
    );
    assert.deepEqual(Object.keys(policyTool.inputSchema.properties).sort(), [
      "expectedRevision", "policyId", "projectRoot",
    ]);
    assert.equal(policyTool.inputSchema.properties.policyId.const, "v1.6-macos-powerpoint");
    assert.match(policyTool.description, /product-version|产品版本/);
    const actionTool = tools.tools.find((tool) => tool.name === "request_ai_ppt_agent_action");
    assert.deepEqual(actionTool.inputSchema.properties.actionType.enum, [
      "build-presales-strategy",
      "build-claim-evidence-map",
      "build-deck-argument-map",
      "build-slide-draft-set",
      "repair-content",
      "review-content-presales",
      "review-content-decision-maker",
      "review-content-evidence",
      "review-content-narrative",
      "review-content-editorial",
      "aggregate-content-reviews",
      "design-deck-system",
      "design-slide-visuals",
      "build-native-first",
      "generate-image-assets",
      "review-visual-aesthetic",
      "review-visual-engineering",
      "verify-target-render",
      "govern-feedback",
      "curate-experience",
      "evaluate-experience",
      "coordinate-delivery",
    ]);
    const artifactTool = tools.tools.find((tool) => tool.name === "commit_ai_ppt_artifact");
    assert.deepEqual(artifactTool.inputSchema.properties.kind.enum, [
      "mission",
      "content-blueprint",
      "content-acceptance",
      "visual-brief",
      "concept-set",
      "visual-contract",
      "native-anchor-set",
      "feedback",
      "delivery",
      "experience",
      "target-render-evidence",
    ]);

    await assert.rejects(
      client.listResources(),
      (error) => error.code === -32601,
    );

    const result = await client.callTool({
      name: "get_ai_ppt_project_snapshot",
      arguments: { projectRoot: "/managed/project" },
    });
    assert.equal(result.structuredContent.snapshot.project.name, "测试项目");
    assert.equal(result._meta?.widgetData, undefined);
    assert.equal("space_projections" in result.structuredContent.snapshot, false);
    assert.deepEqual(
      result.structuredContent.snapshot.workspace.delivery.targets.map((item) => item.target_id),
      ["macos-powerpoint", "macos-wps", "windows-powerpoint", "windows-wps"],
    );
    assert.equal(result._meta?.["openai/outputTemplate"], undefined);
    assert.equal(calls[0].operation, "get-project-snapshot");

    const sidebarResult = await client.callTool({
      name: "get_ai_ppt_sidebar_projection",
      arguments: { projectRoot: "/managed/project", initialSpace: "overview" },
    });
    assert.equal(sidebarResult.isError, true);
    assert.equal(
      sidebarResult.structuredContent.error.code,
      "HOST_SIDEBAR_UNAVAILABLE",
    );
    assert.equal(
      sidebarResult.structuredContent.error.details.projection.project.name,
      "测试项目",
    );
    assert.equal(sidebarResult._meta?.["openai/outputTemplate"], undefined);

    const browserResult = await client.callTool({
      name: "open_ai_ppt_browser_review",
      arguments: {
        projectRoot: "/managed/project",
        reviewType: "visual",
        sourceVersion: "visual-v0001-abc123",
      },
    });
    assert.equal(browserResult.isError, undefined);
    assert.equal(browserResult.structuredContent.status, "review-session-ready");
    assert.equal(browserResult.structuredContent.opened, false);
    assert.equal(browserResult.structuredContent.openMode, "agent-browser");
    assert.equal(browserResult.structuredContent.browserAction, "open-scoped-url");
    assert.match(
      browserResult.structuredContent.url,
      /^http:\/\/127\.0\.0\.1:\d+\/#token=/,
    );
    assert.equal(browserResult._meta?.["openai/outputTemplate"], undefined);
  } finally {
    await client.close();
  }
});

test("authoritative ReviewSession tools map exact public fields to Python operations", async () => {
  const { client, server, calls } = await connectedClient();
  try {
    const status = await client.callTool({
      name: "get_ai_ppt_project_status",
      arguments: { projectRoot: "/managed/project" },
    });
    assert.equal(status.structuredContent.status.status, "成果已可查看");

    const opened = await client.callTool({
      name: "open_or_resume_review_session",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewType: "content-full-deck",
        targetArtifactRef: "artifact://reading-deck-blueprint/abc",
        sourceVersion: "content-v1",
        targetRevision: 3,
        openPolicy: "foreground-if-waiting",
      },
    });
    assert.equal(opened.structuredContent.session.review_session_id, "review-session-1");

    const receiptCases = [
      ["record_review_host_open_receipt", "opened", "host-receipt://open/1"],
      ["record_review_host_notification_receipt", "sent", "host-receipt://notification/1"],
      ["record_review_ai_receipt", "received", "ai-receipt://1"],
    ];
    let expectedRevision = 4;
    for (const [name, result, receiptRef] of receiptCases) {
      const receipt = await client.callTool({
        name,
        arguments: {
          projectRoot: "/managed/project",
          expectedRevision,
          reviewSessionId: "review-session-1",
          result,
          receiptRef,
        },
      });
      assert.equal(receipt.structuredContent.session.receipt_ref, receiptRef);
      expectedRevision += 1;
    }

    assert.deepEqual(
      calls.slice(-5).map((request) => request.operation),
      [
        "get-project-user-status",
        "open-or-resume-review-session",
        "record-review-host-open",
        "record-review-host-notification",
        "record-review-ai-receipt",
      ],
    );
    assert.deepEqual(calls.at(-4), {
      operation: "open-or-resume-review-session",
      project_root: "/managed/project",
      expected_revision: 3,
      review_type: "content-full-deck",
      target_artifact_ref: "artifact://reading-deck-blueprint/abc",
      source_version: "content-v1",
      target_revision: 3,
      open_policy: "foreground-if-waiting",
    });
  } finally {
    await client.close();
    await server.close();
  }
});

test("Browser review opens a scoped loopback session only through a host adapter", async () => {
  const calls = [];
  const opened = [];
  const stopped = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review,
        snapshot_revision: 3,
      };
    },
    browserSurfaceAdapter: {
      canOpen: true,
      canSave: true,
      async openUrl(url) {
        opened.push(url);
        return { opened: true };
      },
    },
    reviewBridgeFactory: (scope) => ({
      async start() {
        assert.equal(scope.reviewType, "visual");
        assert.equal(scope.sourceVersion, "visual-v0001-abc123");
        assert.equal(scope.expectedRevision, 3);
        return {
          url: "http://127.0.0.1:43123/#token=short-lived-token",
          expiresAt: 123456,
          host: "127.0.0.1",
          port: 43123,
        };
      },
      async stop() {
        stopped.push(true);
      },
    }),
  });
  const client = new Client({ name: "browser-review-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "open_ai_ppt_browser_review",
      arguments: {
        projectRoot: "/managed/project",
        reviewType: "visual",
        sourceVersion: "visual-v0001-abc123",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(result.structuredContent.opened, true);
    assert.equal(result.structuredContent.reviewType, "visual");
    assert.equal(result.structuredContent.sourceVersion, "visual-v0001-abc123");
    assert.equal(result.structuredContent.revision, 3);
    assert.equal(result.structuredContent.expiresAt, 123456);
    assert.deepEqual(opened, [
      "http://127.0.0.1:43123/#token=short-lived-token",
    ]);
    assert.equal(calls.at(-1).operation, "get-review-projection");
    assert.equal(result._meta?.["openai/outputTemplate"], undefined);
    assert.deepEqual(stopped, []);
  } finally {
    await client.close();
  }
});

test("visual Browser review rejects switching to the content review surface", async () => {
  let createReviewSession;
  const server = createAiPptMcpServer({
    invokeBridge: async () => ({
      ok: true,
      selected_project_root: "/managed/project",
      review,
      snapshot_revision: 3,
    }),
    browserSurfaceAdapter: {
      canOpen: true,
      canSave: true,
      async openUrl() {
        return { opened: true };
      },
    },
    reviewBridgeFactory: (scope) => {
      createReviewSession = scope.createReviewSession;
      return {
        async start() {
          return {
            url: "http://127.0.0.1:43124/#token=visual-token",
            expiresAt: 123456,
            reviewType: scope.reviewType,
            sourceVersion: scope.sourceVersion,
            expectedRevision: scope.expectedRevision,
          };
        },
        async stop() {},
      };
    },
  });
  const client = new Client({ name: "browser-switch-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const opened = await client.callTool({
      name: "open_ai_ppt_browser_review",
      arguments: {
        projectRoot: "/managed/project",
        reviewType: "visual",
        sourceVersion: "visual-v0001-abc123",
      },
    });
    assert.equal(opened.isError, undefined);
    assert.equal(typeof createReviewSession, "function");

    await assert.rejects(
      createReviewSession({
        projectRoot: "/managed/project",
        reviewType: "content",
      }),
      (error) => error.code === "INVALID_REVIEW_SWITCH",
    );
  } finally {
    await client.close();
  }
});

test("Browser review save capability belongs to the Review Bridge, not the open adapter", async () => {
  const server = createAiPptMcpServer({
    invokeBridge: async () => ({
      ok: true,
      selected_project_root: "/managed/project",
      review,
      snapshot_revision: 3,
    }),
    browserSurfaceAdapter: {
      canOpen: true,
      canSave: false,
      async openUrl() {
        return { opened: true };
      },
    },
    reviewBridgeFactory: () => ({
      async start() {
        return {
          url: "http://127.0.0.1:43123/#token=short-lived-token",
          expiresAt: 123456,
        };
      },
      async stop() {},
    }),
  });
  const client = new Client({ name: "browser-save-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "open_ai_ppt_browser_review",
      arguments: {
        projectRoot: "/managed/project",
        reviewType: "visual",
        sourceVersion: "visual-v0001-abc123",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(result.structuredContent.status, "opened");
    assert.equal(result.structuredContent.opened, true);
    assert.equal(result.structuredContent.openMode, "host-adapter");
  } finally {
    await client.close();
  }
});

test("Browser adapter failure keeps the scoped session ready for Agent Browser handoff", async () => {
  const stopped = [];
  const server = createAiPptMcpServer({
    invokeBridge: async () => ({
      ok: true,
      selected_project_root: "/managed/project",
      review,
      snapshot_revision: 3,
    }),
    browserSurfaceAdapter: {
      canOpen: true,
      async openUrl() {
        return { opened: false };
      },
    },
    reviewBridgeFactory: () => ({
      async start() {
        return {
          url: "http://127.0.0.1:43123/#token=short-lived-token",
          expiresAt: 123456,
        };
      },
      async stop() {
        stopped.push(true);
      },
    }),
  });
  const client = new Client({ name: "browser-handoff-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "open_ai_ppt_browser_review",
      arguments: {
        projectRoot: "/managed/project",
        reviewType: "visual",
        sourceVersion: "visual-v0001-abc123",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(result.structuredContent.status, "review-session-ready");
    assert.equal(result.structuredContent.opened, false);
    assert.equal(result.structuredContent.openMode, "agent-browser");
    assert.equal(result.structuredContent.browserAction, "open-scoped-url");
    assert.equal(
      result.structuredContent.url,
      "http://127.0.0.1:43123/#token=short-lived-token",
    );
    assert.deepEqual(stopped, []);
  } finally {
    await client.close();
  }
});

test("mission confirmation reports native confirmation unavailable without a verifier or host capability", async () => {
  const server = createAiPptMcpServer({
    invokeBridge: async () => {
      throw new Error("must not reach Python");
    },
  });
  const client = new Client({ name: "mission-verifier-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        userMessageRef: "model-invented-reference",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(
      result.structuredContent.error.code,
      "HOST_CONFIRMATION_UNAVAILABLE",
    );
    assert.doesNotMatch(result.structuredContent.error.message, /补充.*材料/);
    assert.doesNotMatch(result.structuredContent.error.message, /绕开|绕过|Presentations/);
  } finally {
    await client.close();
  }
});

test("production startup uses host-native mission confirmation", async () => {
  const calls = [];
  const elicitations = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      return {
        ok: true,
        result: { snapshot: { ...snapshot, revision: 4 } },
      };
    },
  });
  const client = new Client(
    { name: "native-confirmation-client", version: "0.1.0" },
    { capabilities: { elicitation: { form: {} } } },
  );
  client.setRequestHandler(ElicitRequestSchema, async (request) => {
    elicitations.push(request.params);
    return { action: "accept", content: { confirmed: true } };
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        missionSummary: {
          topic: "经营一体化方案",
          primaryAudience: "客户经营与数字化决策团队",
          desiredJudgmentOrAction: "确认一期范围并进入联合验证",
          materialSummary: "当前明确无材料",
        },
      },
    });

    assert.equal(result.isError, undefined);
    assert.equal(elicitations.length, 1);
    assert.match(elicitations[0].message, /经营一体化方案/);
    assert.match(elicitations[0].message, /客户经营与数字化决策团队/);
    assert.match(elicitations[0].message, /确认一期范围并进入联合验证/);
    assert.match(elicitations[0].message, /当前明确无材料/);
    assert.match(elicitations[0].message, /方案建议/);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].operation, "confirm-mission");
    assert.match(calls[0].user_action_ref, /^host-elicitation:\/\//);
    assert.equal(calls[0].user_message_ref, "");
  } finally {
    await client.close();
  }
});

test("verified host message confirmation bypasses elicitation and preserves its reference", async () => {
  const { client, calls } = await connectedClient();
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        userMessageRef: "host-message-reference-preserved",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(calls.at(-1).user_message_ref, "host-message-reference-preserved");
    assert.equal(calls.at(-1).user_action_ref, "");
  } finally {
    await client.close();
  }
});

test("a rejecting host verifier never falls back to native confirmation", async () => {
  const calls = [];
  let elicitationCount = 0;
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      throw new Error("must not reach Python");
    },
    confirmationVerifier: {
      async verify() {
        return false;
      },
    },
  });
  const client = new Client(
    { name: "rejecting-verifier-client", version: "0.1.0" },
    { capabilities: { elicitation: { form: {} } } },
  );
  client.setRequestHandler(ElicitRequestSchema, async () => {
    elicitationCount += 1;
    return { action: "accept", content: { confirmed: true } };
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        userMessageRef: "untrusted-model-string",
        missionSummary: {
          topic: "经营一体化方案",
          primaryAudience: "客户决策团队",
          desiredJudgmentOrAction: "确认一期范围",
          materialSummary: "当前明确无材料",
        },
      },
    });
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent.error.code, "MISSION_NOT_CONFIRMED");
    assert.equal(elicitationCount, 0);
    assert.equal(calls.length, 0);
  } finally {
    await client.close();
  }
});

async function callNativeMissionConfirmation(hostResult) {
  const calls = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      return {
        ok: true,
        result: { snapshot: { ...snapshot, revision: 4 } },
      };
    },
  });
  const client = new Client(
    { name: "native-confirmation-result-client", version: "0.1.0" },
    { capabilities: { elicitation: { form: {} } } },
  );
  client.setRequestHandler(ElicitRequestSchema, async () => hostResult);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        missionSummary: {
          topic: "经营一体化方案",
          primaryAudience: "客户决策团队",
          desiredJudgmentOrAction: "确认一期范围",
          materialSummary: "当前明确无材料",
        },
      },
    });
    return { result, calls };
  } finally {
    await client.close();
  }
}

test("model-supplied Gate message requires a fresh host-native version-bound confirmation", async () => {
  const calls = [];
  const prompts = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-gate-confirmation-context") {
        return {
          ok: true,
          confirmation_context: {
            project_id: "p1",
            gate: "G0",
            source_version: "artifact://content-blueprint/" + "a".repeat(64),
            evidence_refs: [
              "artifact://content-acceptance/" + "b".repeat(64),
              "artifact://content-blueprint/" + "a".repeat(64),
            ],
            challenge_id: "gate-challenge-current",
            challenge_revision: 33,
            review_summary: "完整内容蓝图，共 7 页，内部内容审核已通过。",
          },
        };
      }
      return {
        ok: true,
        result: { snapshot: { ...snapshot, revision: 34 } },
      };
    },
  });
  const client = new Client(
    { name: "native-gate-confirmation-client", version: "0.1.0" },
    { capabilities: { elicitation: { form: {} } } },
  );
  client.setRequestHandler(ElicitRequestSchema, async (request) => {
    prompts.push(request.params);
    return { action: "accept", content: { confirmed: true } };
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 33,
        gate: "G0",
        userMessageRef: "chat://message/item-35",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(prompts.length, 1);
    assert.match(prompts[0].message, /G0/);
    assert.match(prompts[0].message, /7 页/);
    assert.deepEqual(calls.map((call) => call.operation), [
      "get-gate-confirmation-context",
      "confirm-gate",
    ]);
    assert.equal(calls[1].user_message_ref, "");
    assert.equal(calls[1].user_action_ref, "");
    assert.match(calls[1].host_confirmation_assertion, /^v1\./);
    assert.equal(calls[1].source_version, "artifact://content-blueprint/" + "a".repeat(64));
    assert.equal(calls[1].challenge_id, "gate-challenge-current");
    assert.equal(calls[1].challenge_revision, 33);
  } finally {
    await client.close();
  }
});

test("verified Gate message becomes the only asserted confirmation identity", async () => {
  const { client, calls } = await connectedClient();
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G0",
        userMessageRef: "chat://message/verified-g0-acceptance",
      },
    });
    assert.equal(result.isError, undefined);
    const request = calls.at(-1);
    assert.equal(request.operation, "confirm-gate");
    assert.equal(request.user_action_ref, "");
    assert.equal(request.user_message_ref, "");
    const [, payloadSegment] = request.host_confirmation_assertion.split(".");
    const payload = JSON.parse(
      Buffer.from(payloadSegment, "base64url").toString("utf8"),
    );
    assert.equal(payload.identity_type, "verified-message");
    assert.equal(payload.identity_ref, "chat://message/verified-g0-acceptance");
  } finally {
    await client.close();
  }
});

for (const hostResult of [
  { action: "decline" },
  { action: "cancel" },
  { action: "accept", content: { confirmed: false } },
]) {
  test(`host-native Gate confirmation makes no business write for ${JSON.stringify(hostResult)}`, async () => {
    const calls = [];
    const server = createAiPptMcpServer({
      invokeBridge: async (request) => {
        calls.push(request);
        if (request.operation !== "get-gate-confirmation-context") {
          throw new Error("must not reach Gate write");
        }
        return {
          ok: true,
          confirmation_context: {
            project_id: "p1",
            gate: "G0",
            source_version: "artifact://content-blueprint/" + "a".repeat(64),
            evidence_refs: ["artifact://content-acceptance/" + "b".repeat(64)],
            challenge_id: "gate-decline-challenge",
            challenge_revision: 33,
            review_summary: "完整内容蓝图，共 7 页。",
          },
        };
      },
    });
    const client = new Client(
      { name: "native-gate-decline-client", version: "0.1.0" },
      { capabilities: { elicitation: { form: {} } } },
    );
    client.setRequestHandler(ElicitRequestSchema, async () => hostResult);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
    try {
      const result = await client.callTool({
        name: "confirm_ai_ppt_gate",
        arguments: {
          projectRoot: "/managed/project",
          expectedRevision: 33,
          gate: "G0",
        },
      });
      assert.equal(result.isError, true);
      assert.equal(result.structuredContent.error.code, "HOST_CONFIRMATION_DECLINED");
      assert.deepEqual(calls.map((call) => call.operation), [
        "get-gate-confirmation-context",
      ]);
    } finally {
      await client.close();
    }
  });
}

test("unverified Gate message stays blocked when host confirmation is unavailable", async () => {
  const calls = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      return {
        ok: true,
        confirmation_context: {
          project_id: "p1",
          gate: "G0",
          source_version: "artifact://content-blueprint/" + "a".repeat(64),
          evidence_refs: ["artifact://content-acceptance/" + "b".repeat(64)],
          challenge_id: "gate-unavailable-challenge",
          challenge_revision: 33,
          review_summary: "完整内容蓝图，共 7 页。",
        },
      };
    },
  });
  const client = new Client({ name: "gate-unavailable-client", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 33,
        gate: "G0",
        userMessageRef: "chat://message/item-35",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent.error.code, "HOST_CONFIRMATION_UNAVAILABLE");
    assert.equal(calls.length, 1);
  } finally {
    await client.close();
  }
});

for (const hostResult of [
  { action: "decline" },
  { action: "cancel" },
  { action: "accept", content: { confirmed: false } },
]) {
  test(`host-native mission confirmation makes no write for ${JSON.stringify(hostResult)}`, async () => {
    const { result, calls } = await callNativeMissionConfirmation(hostResult);
    assert.equal(result.isError, true);
    assert.equal(
      result.structuredContent.error.code,
      "HOST_CONFIRMATION_DECLINED",
    );
    assert.equal(calls.length, 0);
    assert.match(result.structuredContent.error.message, /项目状态未改变/);
  });
}

test("BCD tools map governed inputs to bridge operations", async () => {
  const { client, calls } = await connectedClient();
  try {
    const material = await client.callTool({
      name: "add_ai_ppt_material",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        materialType: "text",
        value: "客户确认九月上线",
        label: "会议纪要",
      },
    });
    assert.equal(material.structuredContent.snapshot.revision, 4);
    assert.equal(calls.at(-1).operation, "add-material");

    const mission = await client.callTool({
      name: "save_ai_ppt_mission_draft",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraft: {
          topic: "经营一体化方案",
          primary_audience: "客户决策者",
          desired_judgment_or_action: "批准一期立项",
        },
      },
    });
    assert.equal(mission.structuredContent.snapshot.revision, 4);
    assert.equal(calls.at(-1).operation, "save-mission-draft");

    const confirmation = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "no-materials-confirmed",
        userMessageRef: "host-message-reference-1",
      },
    });
    assert.equal(confirmation.structuredContent.snapshot.revision, 4);
    assert.equal(calls.at(-1).operation, "confirm-mission");
    assert.equal(calls.at(-1).user_message_ref, "host-message-reference-1");
    assert.equal(calls.at(-1).user_action_ref, "");

    await client.callTool({
      name: "commit_ai_ppt_artifact",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        kind: "experience",
        payload: {
          artifact_type: "experience-intake",
          intake_id: "intake-public-contract",
        },
      },
    });
    assert.equal(calls.at(-1).operation, "commit-artifact");
    assert.equal(calls.at(-1).kind, "experience");

    const requested = await client.callTool({
      name: "request_ai_ppt_agent_action",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        actionType: "build-presales-strategy",
        targetRefs: ["artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
        instructions: "生成内容蓝图",
      },
    });
    assert.equal(requested.structuredContent.decision.task_id, "task-1");
    assert.equal(calls.at(-1).operation, "request-agent-action");

    const gate = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G0",
        userMessageRef: "chat://message/g0-accepted",
      },
    });
    assert.equal(gate.structuredContent.snapshot.revision, 4);
    assert.equal(calls.at(-1).operation, "confirm-gate");
    assert.equal(calls.at(-1).user_message_ref, "");
    assert.equal(calls.at(-1).user_action_ref, "");
    assert.match(calls.at(-1).host_confirmation_assertion, /^v1\./);
  } finally {
    await client.close();
  }
});

test("v1.6 tools map formal review marks, internal gates, and chat delivery inputs", async () => {
  const { client, calls } = await connectedClient();
  try {
    const tools = await client.listTools();
    const gateTool = tools.tools.find((tool) => tool.name === "confirm_ai_ppt_gate");
    assert.deepEqual(gateTool.inputSchema.properties.gate.enum, ["G0", "G3", "G4"]);
    assert.ok(!gateTool.inputSchema.required.includes("userMessageRef"));
    const reopenTool = tools.tools.find((tool) => tool.name === "reopen_ai_ppt_scope");
    assert.deepEqual(reopenTool.inputSchema.properties.gate.enum, ["G0", "G3", "G4"]);

    const saved = await client.callTool({
      name: "save_review_marks",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewType: "content",
        sourceVersion: "content-v0001-abc123",
        marks: [{
          mark_id: "m1",
          field_anchor: "content-overview",
          exact_text: "",
          prefix: "",
          suffix: "",
          comment: "补充证据",
        }],
      },
    });
    assert.equal(saved.structuredContent.snapshot.revision, 4);
    assert.equal(calls.at(-1).operation, "save-review-marks");
    assert.equal(calls.at(-1).source_version, "content-v0001-abc123");
    assert.deepEqual(calls.at(-1).marks[0], {
      mark_id: "m1",
      field_anchor: "content-overview",
      exact_text: "",
      prefix: "",
      suffix: "",
      comment: "补充证据",
    });

    const rejectedLegacy = await client.callTool({
      name: "save_review_marks",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewType: "content",
        sourceVersion: "content-v0001-abc123",
        marks: [{ mark_id: "legacy", target_anchor: "content-overview", comment: "旧合同" }],
      },
    });
    assert.equal(rejectedLegacy.isError, true);

    await client.callTool({
      name: "record_internal_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G2",
        reviewerRole: "PPT 工程审查智能体",
        acceptanceRecordRefs: ["reviews/target-render-evidence/v0001.json"],
      },
    });
    assert.equal(calls.at(-1).operation, "record-internal-gate");

    await client.callTool({
      name: "set_ai_ppt_release_target_policy",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        policyId: "v1.6-macos-powerpoint",
      },
    });
    assert.deepEqual(calls.at(-1), {
      operation: "set-release-target-policy",
      project_root: "/managed/project",
      expected_revision: 3,
      policy_id: "v1.6-macos-powerpoint",
    });

    const rejectedPolicy = await client.callTool({
      name: "set_ai_ppt_release_target_policy",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        policyId: "ad-hoc-skip-windows",
        requiredTargetIds: ["macos-powerpoint"],
      },
    });
    assert.equal(rejectedPolicy.isError, true);

    await client.callTool({
      name: "record_chat_delivery",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        deliveryType: "pptx",
        artifactRefs: ["reviews/delivery/v0001.json"],
        messageRef: "chat://message/pptx-1",
        sendStatus: "sent",
      },
    });
    assert.equal(calls.at(-1).operation, "record-chat-delivery");

    const delivery = await client.callTool({
      name: "get_delivery_status_projection",
      arguments: { projectRoot: "/managed/project" },
    });
    assert.equal(delivery.structuredContent.snapshotRevision, 3);
    assert.equal(delivery._meta?.widgetData, undefined);
    assert.equal(calls.at(-1).operation, "get-delivery-status-projection");

    await client.callTool({
      name: "reopen_ai_ppt_scope",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G3",
        reason: "用户要求调整视觉合同",
      },
    });
    assert.equal(calls.at(-1).operation, "reopen-scope");
    assert.equal(calls.at(-1).gate, "G3");
    assert.equal(calls.at(-1).reason, "用户要求调整视觉合同");
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
    assert.equal(result._meta?.widgetData, undefined);
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
