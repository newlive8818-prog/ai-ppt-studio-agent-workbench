import assert from "node:assert/strict";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { createAiPptMcpServer } from "../server.mjs";


const runtimeReview = {
  project_id: "p1",
  project_name: "集团经营一体化方案",
  review_type: "visual-professional",
  review_session_id: "visual-review-session-1",
  review_session: {
    review_session_id: "visual-review-session-1",
    target_artifact_ref: `artifact://visual-contract/${"a".repeat(64)}`,
    source_version: "visual-v23",
    revision: 28,
  },
  source_version: "visual-v23",
  revision: 28,
  authoritative_revision: 29,
  visual_contract_ref: `artifact://visual-contract/${"a".repeat(64)}`,
  visual_brief_ref: `artifact://visual-brief/${"b".repeat(64)}`,
  visual_brief: {
    design_proposition: "可信的经营证据链",
    audience_fit: "决策者先看结论，评审者下钻证据",
    decision_task: "判断一期建设范围",
    design_stance: "编辑化、技术可信、克制",
    emotional_boundary: "理性、清晰",
    brand_boundary: "中性墨色与单一冷色强调",
    density_strategy: "章节低密度，证据中密度",
    narrative_rhythm: "问题、证据、方案、行动",
    imagery_strategy: "图片只承担结构和语境任务",
    diagram_strategy: "关系使用原生对象",
    powerpoint_constraints: "文字和关系保持原生可编辑",
    forbidden_patterns: ["整页位图"],
    five_second_test_contract: { expected_judgment: "先看到执行主体变化" },
    design_philosophy_refs: [],
  },
  deck_design_system_ref: `artifact://deck-design-system/${"c".repeat(64)}`,
  deck_design_system: {
    cross_slide_rhythm_rules: ["章节页承担阅读重置"],
    emphasis_budget: { max_primary_focal_points_per_slide: 1 },
    image_language: "可追溯、可替换",
    diagram_language: "原生形状和语义连接器",
    five_second_test_rules: ["记录第一视觉重心"],
  },
  anchor_slide_set_ref: `artifact://anchor-slide-set/${"d".repeat(64)}`,
  anchors: [],
  anchor_identity: {
    slide_ids: ["S01", "S02", "S03"],
    selection_reason: "覆盖关键页面家族",
    native_first_frozen: true,
  },
  slide_visual_contracts: [{
    slide_id: "S01",
    reader_judgment: "先看到执行主体变化与治理边界",
    primary_relationship: "causality",
    secondary_relationship: "system-boundary",
    visual_mechanism: "主体转移图与边界线",
    focal_point: "center-right-primary-subject",
    asset_roles: [],
    forbidden_patterns: ["三张等权卡片"],
    previous_rhythm_relation: "从章节停顿进入主体关系",
    next_rhythm_relation: "为证据页增加关系密度",
    text_density_budget: { max_body_lines: 8 },
    powerpoint_implementation_requirements: { native_bitmap_routing: "原生优先" },
    acceptance_evidence_plan: { automated_checks: ["overflow"] },
  }],
  anchor_feedback_batch: null,
  anchor_feedback_batch_ref: null,
  contract_review_marks: null,
  contract_review_marks_ref: null,
  host_submission_capability: "unknown",
  ai_receipt_capability: "unknown",
};


test("get_visual_review_projection forwards the exact closed Runtime projection", async () => {
  const calls = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      return { ok: true, review: runtimeReview, snapshot_revision: 29 };
    },
  });
  const client = new Client({ name: "visual-projection-test", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([
    client.connect(clientTransport),
    server.connect(serverTransport),
  ]);

  try {
    const result = await client.callTool({
      name: "get_visual_review_projection",
      arguments: {
        projectRoot: "/managed/project",
        reviewSessionId: "visual-review-session-1",
      },
    });

    assert.deepEqual(calls, [{
      operation: "get-visual-review-projection",
      project_root: "/managed/project",
      review_session_id: "visual-review-session-1",
    }]);
    assert.deepEqual(result.structuredContent, { review: runtimeReview });
    assert.deepEqual(result.structuredContent.review, runtimeReview);
    assert.doesNotMatch(
      JSON.stringify(result.structuredContent.review),
      /visual_compilation_plan|compiler_version|role_runs|gate_status/,
    );
  } finally {
    await client.close();
  }
});
