import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ElicitRequestSchema } from "@modelcontextprotocol/sdk/types.js";

import { createAiPptMcpServer } from "../mcp/server.mjs";
import {
  PUBLIC_TOOL_CATALOG,
  PUBLIC_TOOL_CATALOG_SHA256,
} from "../mcp/tool-catalog.mjs";
import { PythonBridgeError } from "../mcp/runtime-bridge/python-runtime.mjs";

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
  review_type: "content",
  display_policy: "professional-review",
  project_id: "p1",
  project_name: "测试项目",
  title: "内容蓝图专业审阅",
  source_version: "content-v0001-abc123",
  source_refs: ["content-blueprint:v0001:abc123"],
  slides: [{
    slide_id: "S01",
    order: 1,
    section_id: "problem",
    page_task: "确认现状边界",
    reading_question: "现有材料能否支持当前判断？",
    neutral_title: "当前流程断点与证据边界",
    customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
    visible_copy_blocks: [{ block_id: "copy-1", text: "当前流程存在待核实断点。" }],
    material_views: [{ material_view_id: "S01-M01", asset_ref: "review-assets/content/S01-M01.png" }],
  }],
  sections: [{ anchor: "content-overview", title: "整套内容", value: {} }],
  outline: [{ anchor: "content-overview", title: "整套内容" }],
  mark_set: { marks: [] },
};

async function connectedClient(options = {}) {
  const calls = [];
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-content-review-projection") {
      return {
        ok: true,
        review: {
          ...review,
          review_type: "content-full-deck",
          review_session_id: request.review_session_id,
        },
        snapshot_revision: 3,
      };
    }
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        review: {
          project_id: "p1",
          review_type: "visual-professional",
          review_session_id: request.review_session_id,
          source_version: "visual-v0001-abc123",
          revision: 3,
          authoritative_revision: 3,
          visual_contract_ref: "visual-contract:v0001:abc123",
          deck_design_system_ref: "deck-design-system:v0001:def456",
          deck_design_system: {},
          anchor_slide_set_ref: "anchor-slide-set:v0001:fed654",
          anchors: [],
          anchor_identity: {},
          slide_visual_contracts: [],
          anchor_feedback_batch: null,
          contract_review_marks: null,
          gate_status: { G1: "passed", G2: "passed", G3: "locked" },
          host_submission_capability: "unknown",
          ai_receipt_capability: "unknown",
        },
        snapshot_revision: 3,
      };
    }
    if (request.operation === "submit-visual-anchor-feedback-batch") {
      return {
        ok: true,
        result: {
          batch_ref: "visual-anchor-feedback-batch:v0001:abc123",
          batch: { items: request.feedback },
          snapshot: { ...snapshot, revision: 4 },
        },
      };
    }
    if (request.operation === "save-visual-contract-review-marks") {
      return {
        ok: true,
        result: {
          mark_set_ref: "visual-contract-review-mark-set:v0001:abc123",
          mark_set: { marks: request.marks },
          snapshot: { ...snapshot, revision: 4 },
        },
      };
    }
    if (request.operation === "get-review-projection") {
      return { ok: true, review: { ...review, review_type: request.review_type }, snapshot_revision: 3 };
    }
    if (request.operation === "get-delivery-status-projection") {
      return { ok: true, delivery: { status: "qa-passed", chat_delivery: {} }, snapshot_revision: 3 };
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
    assert.equal(
      new Set(PUBLIC_TOOL_CATALOG.map((tool) => tool.name)).size,
      PUBLIC_TOOL_CATALOG.length,
    );
    assert.ok(PUBLIC_TOOL_CATALOG.every((tool) => tool.schema && tool.handler));
    assert.match(PUBLIC_TOOL_CATALOG_SHA256, /^[0-9a-f]{64}$/);
    const readTool = tools.tools.find((tool) => tool.name === "get_ai_ppt_project_snapshot");
    assert.equal(readTool._meta?.ui?.resourceUri, undefined);
    const saveTool = tools.tools.find(
      (tool) => tool.name === "save_visual_contract_review_marks",
    );
    assert.equal(saveTool._meta?.ui?.resourceUri, undefined);
    assert.deepEqual(Object.keys(saveTool.inputSchema.properties.marks.items.properties).sort(), [
      "comment", "context_after", "context_before", "created_at", "created_by",
      "deck_section_id", "mark_id", "revision", "selected_text", "slide_id",
      "source_version", "target_key", "target_type", "visual_contract_ref",
    ]);
    assert.deepEqual(
      saveTool.inputSchema.properties.marks.items.properties.target_type.enum,
      ["contract-field", "text-range"],
    );
    assert.equal("field_anchor" in saveTool.inputSchema.properties.marks.items.properties, false);
    const anchorTool = tools.tools.find(
      (tool) => tool.name === "submit_visual_anchor_feedback_batch",
    );
    assert.deepEqual(Object.keys(anchorTool.inputSchema.properties.feedback.items.properties).sort(), [
      "anchor_artifact_ref", "anchor_slide_id", "comment", "created_at", "created_by",
      "feedback_id", "normalized_region", "order", "revision", "visual_source_version",
    ]);
    assert.equal(
      anchorTool.inputSchema.properties.feedback.items.properties.created_by.const,
      "user",
    );
    assert.equal(
      anchorTool.inputSchema.properties.feedback.items.properties.created_at.format,
      "date-time",
    );
    assert.deepEqual(
      Object.keys(anchorTool.inputSchema.properties.feedback.items.properties.normalized_region.properties).sort(),
      ["height", "width", "x", "y"],
    );
    const actionTool = tools.tools.find((tool) => tool.name === "request_ai_ppt_agent_action");
    assert.deepEqual(actionTool.inputSchema.properties.actionType.enum, [
      "design-deck-system",
      "design-slide-visuals",
      "build-native-first",
      "generate-image-assets",
      "review-visual-aesthetic",
      "review-visual-engineering",
      "verify-target-render",
      "coordinate-delivery",
    ]);
    for (const name of [
      "open_g0_review",
      "close_ai_ppt_project",
      "abort_ai_ppt_project",
    ]) assert.ok(tools.tools.some((tool) => tool.name === name), name);
    const policyTool = tools.tools.find(
      (tool) => tool.name === "set_ai_ppt_release_target_policy",
    );
    assert.equal(
      policyTool.inputSchema.properties.policyId.const,
      "v1.6-macos-powerpoint",
    );
    assert.equal(policyTool.inputSchema.properties.requiredTargetIds, undefined);
    const recommendTool = tools.tools.find((tool) => tool.name === "recommend_experience");
    assert.deepEqual(Object.keys(recommendTool.inputSchema.properties).sort(), [
      "applicability", "domain", "projectRoot", "topN", "typeSignature",
    ]);
    const applicationTool = tools.tools.find(
      (tool) => tool.name === "record_experience_application",
    );
    assert.deepEqual(Object.keys(applicationTool.inputSchema.properties).sort(), [
      "appliedAt", "context", "evidenceRefs", "expectedRevision",
      "experienceRef", "explicitValidation", "projectRoot", "targetProjectId",
      "targetTypeSignature",
    ]);
    const retrospectiveTool = tools.tools.find(
      (tool) => tool.name === "summarize_project_experience",
    );
    assert.deepEqual(Object.keys(retrospectiveTool.inputSchema.properties).sort(), [
      "expectedRevision", "finishedAt", "payload", "projectRoot", "retryable",
      "startedAt", "terminalStatus",
    ]);
    const artifactTool = tools.tools.find((tool) => tool.name === "commit_ai_ppt_artifact");
    assert.deepEqual(artifactTool.inputSchema.properties.kind.enum, [
      "visual-brief",
      "concept-set",
      "visual-contract",
      "native-anchor-set",
      "delivery",
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

  } finally {
    await client.close();
  }
});

test("content review tools use exact v2.2 session-bound operations", async () => {
  const { client, calls } = await connectedClient();
  try {
    const tools = await client.listTools();
    const save = tools.tools.find((tool) => tool.name === "save_content_page_decision");
    assert.ok(save.inputSchema.properties.reviewSessionId);
    assert.equal(save.inputSchema.properties.reviewBatchId, undefined);
    const result = await client.callTool({
      name: "get_content_review_projection",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "content-full-deck-session-1",
      },
    });
    assert.equal(result.structuredContent.review.review_type, "content-full-deck");
    assert.equal(
      result.structuredContent.review.slides[0].customerJudgment,
      "客户确认现状边界后，再判断是否进入联合方案验证。",
    );
    assert.deepEqual(Object.keys(result.structuredContent.review.slides[0]), [
      "slide_id",
      "order",
      "section_id",
      "page_task",
      "reading_question",
      "neutral_title",
      "customerJudgment",
      "visible_copy_blocks",
      "material_views",
    ]);
    assert.deepEqual(
      Object.keys(result.structuredContent.review.slides[0].visible_copy_blocks[0]),
      ["block_id", "text"],
    );
    assert.deepEqual(
      Object.keys(result.structuredContent.review.slides[0].material_views[0]),
      ["material_view_id", "asset_ref"],
    );
    assert.equal(calls.at(-1).operation, "get-content-review-projection");
    assert.equal(calls.at(-1).review_session_id, "content-full-deck-session-1");
  } finally {
    await client.close();
  }
});

test("content evidence browser rejects unavailable host capability before Python", async () => {
  let pythonCalled = false;
  const { client } = await connectedClient({
    invokeBridge: async () => {
      pythonCalled = true;
      throw new Error("must not reach Python without a Browser adapter");
    },
  });
  try {
    const result = await client.callTool({
      name: "open_content_evidence_browser",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "content-full-deck-session-1",
        evidenceRef: "artifact://material-source/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(
      result.structuredContent.error.code,
      "CONTENT_EVIDENCE_BROWSER_UNAVAILABLE",
    );
    assert.equal(pythonCalled, false);
  } finally {
    await client.close();
  }
});

test("content evidence browser opens only the Runtime-approved URL and reports real host open", async () => {
  const calls = [];
  const openedUrls = [];
  const approvedUrl = "https://example.com/evidence/source-7";
  const { client } = await connectedClient({
    invokeBridge: async (request) => {
      calls.push(request);
      return {
        ok: true,
        url: approvedUrl,
        read_only: true,
        proof_eligible: false,
        real_browser_evidence: false,
      };
    },
    browserSurfaceAdapter: {
      canOpen: true,
      async openUrl(url) {
        openedUrls.push(url);
        return { opened: true };
      },
    },
  });
  try {
    const result = await client.callTool({
      name: "open_content_evidence_browser",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "content-full-deck-session-1",
        evidenceRef: "artifact://material-source/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(result.structuredContent.opened, true);
    assert.equal(result.structuredContent.url, approvedUrl);
    assert.deepEqual(openedUrls, [approvedUrl]);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].operation, "open-content-evidence-browser");
    assert.equal(calls[0].review_session_id, "content-full-deck-session-1");
    assert.equal(
      calls[0].evidence_ref,
      "artifact://material-source/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
  } finally {
    await client.close();
  }
});

test("content evidence browser returns a stable capability gap when host open fails", async () => {
  const approvedUrl = "https://example.com/evidence/source-7";
  const { client } = await connectedClient({
    invokeBridge: async () => ({
      ok: true,
      url: approvedUrl,
      read_only: true,
      proof_eligible: false,
      real_browser_evidence: false,
    }),
    browserSurfaceAdapter: {
      canOpen: true,
      async openUrl(url) {
        assert.equal(url, approvedUrl);
        return { opened: false };
      },
    },
  });
  try {
    const result = await client.callTool({
      name: "open_content_evidence_browser",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "content-full-deck-session-1",
        evidenceRef: "artifact://material-source/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(
      result.structuredContent.error.code,
      "CONTENT_EVIDENCE_BROWSER_UNAVAILABLE",
    );
    assert.doesNotMatch(result.content[0].text, /已打开/);
  } finally {
    await client.close();
  }
});

test("server and probe consume the catalog instead of maintaining tool arrays", () => {
  const serverSource = readFileSync(new URL("../mcp/server.mjs", import.meta.url), "utf8");
  const probeSource = readFileSync(new URL("../scripts/probe-mcp.mjs", import.meta.url), "utf8");
  for (const register of [
    "registerProjectTools",
    "registerContentTools",
    "registerReviewTools",
    "registerVisualTools",
    "registerDeliveryExperienceTools",
  ]) assert.match(serverSource, new RegExp(register));
  assert.match(probeSource, /PUBLIC_TOOL_CATALOG/);
  assert.doesNotMatch(probeSource, /requiredTools/);
  assert.doesNotMatch(probeSource, /Expected \d+ pure-data tools/);
});

test("ReviewSession tools map source-bound requests and receipts to exact operations", async () => {
  const { client, calls } = await connectedClient();
  try {
    await client.callTool({
      name: "open_or_resume_review_session",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewType: "content-full-deck",
        targetArtifactRef: "artifact://reading-deck-blueprint/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        sourceVersion: "content-v0001-abc123",
        sourceRevision: 3,
        openPolicy: "foreground-if-waiting",
      },
    });
    assert.equal(calls.at(-1).operation, "open-or-resume-review-session");
    assert.equal(calls.at(-1).review_type, "content-full-deck");
    assert.equal(calls.at(-1).source_revision, 3);

    await client.callTool({
      name: "record_review_host_open_receipt",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewType: "content-full-deck",
        receiptRef: "artifact://review-host-open-receipt/" + "b".repeat(64),
      },
    });
    assert.equal(calls.at(-1).operation, "record-review-host-open");

    for (const [name, operation, receiptRef] of [
      [
        "record_review_host_notification_receipt",
        "record-review-host-notification",
        "artifact://review-host-notification-receipt/" + "c".repeat(64),
      ],
      [
        "record_review_ai_receipt",
        "record-review-ai-receipt",
        "artifact://review-ai-receipt/" + "d".repeat(64),
      ],
    ]) {
      await client.callTool({
        name,
        arguments: {
          projectRoot: "/managed/project",
          expectedRevision: 3,
          reviewType: "visual-professional",
          reviewSessionId: "visual-session-1",
          sourceVersion: "visual-v1",
          savedArtifactRef: "artifact://visual-anchor-feedback-batch/" + "a".repeat(64),
          receiptRef,
        },
      });
      assert.equal(calls.at(-1).operation, operation);
      assert.equal(calls.at(-1).review_session_id, "visual-session-1");
      assert.equal(calls.at(-1).source_version, "visual-v1");
      assert.equal(
        calls.at(-1).saved_artifact_ref,
        "artifact://visual-anchor-feedback-batch/" + "a".repeat(64),
      );
    }
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

    const materialsResult = await client.callTool({
      name: "confirm_ai_ppt_mission",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 4,
        missionDraftRef:
          "artifact://mission-draft/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        materialMode: "materials-provided",
        materialInventoryRef:
          "artifact://material-inventory/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        missionSummary: {
          topic: "经营一体化方案",
          primaryAudience: "客户经营与数字化决策团队",
          desiredJudgmentOrAction: "确认一期范围并进入联合验证",
          materialSummary: "已登记会议纪要与客户需求",
        },
      },
    });
    assert.equal(materialsResult.isError, undefined);
    assert.equal(elicitations.length, 2);
    assert.doesNotMatch(elicitations[1].message, /进入 material-backed 内容链/);
    assert.match(elicitations[1].message, /证据盘点/);
    assert.match(elicitations[1].message, /material-backed.*mixed-evidence/);
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
        kind: "visual-brief",
        payload: {
          artifact_type: "visual-brief",
          visual_brief_id: "visual-brief-public-contract",
        },
      },
    });
    assert.equal(calls.at(-1).operation, "commit-artifact");
    assert.equal(calls.at(-1).kind, "visual-brief");

    const requested = await client.callTool({
      name: "request_ai_ppt_agent_action",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        actionType: "design-deck-system",
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
    assert.equal(calls.at(-1).user_message_ref, "chat://message/g0-accepted");
  } finally {
    await client.close();
  }
});

test("G0, project lifecycle, release policy, and experience tools map exact v2.2 inputs", async () => {
  const { client, calls } = await connectedClient();
  try {
    const cases = [
      ["open_g0_review", { projectRoot: "/managed/project", expectedRevision: 3 }, "open-g0-review"],
      ["close_ai_ppt_project", {
        projectRoot: "/managed/project", expectedRevision: 3,
        userMessageRef: "chat://message/close", completedAt: "2026-08-15T10:00:00+08:00",
      }, "close-project"],
      ["abort_ai_ppt_project", {
        projectRoot: "/managed/project", expectedRevision: 3,
        userMessageRef: "chat://message/abort", reason: "客户终止本轮",
        completedAt: "2026-08-15T10:00:00+08:00",
      }, "abort-project"],
      ["set_ai_ppt_release_target_policy", {
        projectRoot: "/managed/project", expectedRevision: 3,
        policyId: "v1.6-macos-powerpoint",
      }, "set-release-target-policy"],
      ["recommend_experience", {
        projectRoot: "/managed/project", domain: "visual",
        typeSignature: "presales:transport:reading-first",
        applicability: { conditions: ["reading-first"] }, topN: 5,
      }, "recommend-experience"],
      ["record_experience_application", {
        projectRoot: "/managed/project", expectedRevision: 3,
        experienceRef: "artifact://experience-item/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        targetProjectId: "p1", targetTypeSignature: "presales:transport:reading-first",
        context: { phase: "visual" }, evidenceRefs: [],
        appliedAt: "2026-08-15T10:01:00+08:00", explicitValidation: false,
      }, "record-experience-application"],
      ["summarize_project_experience", {
        projectRoot: "/managed/project", expectedRevision: 3, terminalStatus: "closed",
        payload: { completion_kind: "closed" },
        startedAt: "2026-08-15T10:02:00+08:00",
        finishedAt: "2026-08-15T10:03:00+08:00", retryable: true,
      }, "summarize-project-experience"],
    ];
    for (const [name, arguments_, operation] of cases) {
      await client.callTool({ name, arguments: arguments_ });
      assert.equal(calls.at(-1).operation, operation);
    }
    assert.equal(calls.at(-4).policy_id, "v1.6-macos-powerpoint");
    assert.deepEqual(calls.at(-3).applicability, { conditions: ["reading-first"] });
    assert.equal(calls.at(-3).top_n, 5);
    assert.equal(calls.at(-2).target_project_id, "p1");
    assert.deepEqual(calls.at(-2).evidence_refs, []);
    assert.equal(calls.at(-1).terminal_status, "closed");
    assert.equal(calls.at(-1).retryable, true);
  } finally {
    await client.close();
  }
});

test("visual review projection and writes use exact v2.2 operations and closed schemas", async () => {
  const { client, calls } = await connectedClient();
  try {
    const tools = await client.listTools();
    const gateTool = tools.tools.find((tool) => tool.name === "confirm_ai_ppt_gate");
    assert.deepEqual(gateTool.inputSchema.properties.gate.enum, ["G0", "G3", "G4"]);
    assert.ok(gateTool.inputSchema.required.includes("userMessageRef"));

    const projection = await client.callTool({
      name: "get_visual_review_projection",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "visual-review-session-1",
      },
    });
    assert.equal(projection.structuredContent.review.review_type, "visual-professional");
    assert.equal(calls.at(-1).operation, "get-visual-review-projection");
    assert.equal(calls.at(-1).review_session_id, "visual-review-session-1");

    const feedback = {
      feedback_id: "f1",
      anchor_slide_id: "slide-01",
      anchor_artifact_ref: "anchor-slide-set:v0001:fed654",
      normalized_region: { x: 0.1, y: 0.2, width: 0.3, height: 0.25 },
      comment: "缩小标题字号",
      order: 1,
      visual_source_version: "visual-v0001-abc123",
      revision: 3,
      created_at: "2026-08-15T00:00:00Z",
      created_by: "user",
    };
    const submitted = await client.callTool({
      name: "submit_visual_anchor_feedback_batch",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewSessionId: "visual-review-session-1",
        sourceVersion: "visual-v0001-abc123",
        feedback: [feedback],
      },
    });
    assert.equal(submitted.structuredContent.batch_ref, "visual-anchor-feedback-batch:v0001:abc123");
    assert.equal(calls.at(-1).operation, "submit-visual-anchor-feedback-batch");
    assert.deepEqual(calls.at(-1).feedback, [feedback]);

    const mark = {
      mark_id: "m1",
      target_type: "contract-field",
      slide_id: "",
      deck_section_id: "deck-design-system",
      target_key: "typography.title_scale",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "调整层级",
      visual_contract_ref: "visual-contract:v0001:abc123",
      source_version: "visual-v0001-abc123",
      revision: 3,
      created_at: "2026-08-15T00:00:00Z",
      created_by: "user",
    };
    const saved = await client.callTool({
      name: "save_visual_contract_review_marks",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewSessionId: "visual-review-session-1",
        sourceVersion: "visual-v0001-abc123",
        marks: [mark],
      },
    });
    assert.equal(saved.structuredContent.mark_set_ref, "visual-contract-review-mark-set:v0001:abc123");
    assert.equal(calls.at(-1).operation, "save-visual-contract-review-marks");
    assert.equal(calls.at(-1).source_version, "visual-v0001-abc123");
    assert.deepEqual(calls.at(-1).marks, [mark]);

    const rejectedLegacy = await client.callTool({
      name: "save_visual_contract_review_marks",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        reviewSessionId: "visual-review-session-1",
        sourceVersion: "visual-v0001-abc123",
        marks: [{
          mark_id: "legacy",
          field_anchor: "design-system.typography",
          exact_text: "",
          prefix: "",
          suffix: "",
          comment: "旧合同",
        }],
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
    assert.equal(delivery.structuredContent.snapshot_revision, 3);
    assert.equal(delivery._meta?.widgetData, undefined);
    assert.equal(calls.at(-1).operation, "get-delivery-status-projection");
  } finally {
    await client.close();
  }
});

test("visual anchor feedback rejects forged authorship and malformed timestamps before the bridge", async () => {
  const { client, calls } = await connectedClient();
  const feedback = {
    feedback_id: "f1",
    anchor_slide_id: "slide-01",
    anchor_artifact_ref: "anchor-slide-set:v0001:fed654",
    normalized_region: { x: 0.1, y: 0.2, width: 0.3, height: 0.25 },
    comment: "缩小标题字号",
    order: 1,
    visual_source_version: "visual-v0001-abc123",
    revision: 3,
    created_at: "2026-08-15T00:00:00Z",
    created_by: "user",
  };
  const submit = (item) => client.callTool({
    name: "submit_visual_anchor_feedback_batch",
    arguments: {
      projectRoot: "/managed/project",
      expectedRevision: 3,
      reviewSessionId: "visual-review-session-1",
      sourceVersion: "visual-v0001-abc123",
      feedback: [item],
    },
  });
  try {
    for (const invalid of [
      { ...feedback, created_by: "agent" },
      { ...feedback, created_at: "not-a-timestamp" },
      { ...feedback, created_at: "2026-08-15T00:00:00" },
    ]) {
      const callCount = calls.length;
      const rejected = await submit(invalid);
      assert.equal(rejected.isError, true);
      assert.equal(calls.length, callCount);
    }

    for (const createdAt of [
      "2026-08-15T00:00:00Z",
      "2026-08-15T08:00:00+08:00",
      "2999-01-01T00:00:00Z",
    ]) {
      const callCount = calls.length;
      const accepted = await submit({ ...feedback, created_at: createdAt });
      assert.equal(accepted.isError, undefined);
      assert.equal(calls.length, callCount + 1);
      assert.equal(calls.at(-1).feedback[0].created_at, createdAt);
    }
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
