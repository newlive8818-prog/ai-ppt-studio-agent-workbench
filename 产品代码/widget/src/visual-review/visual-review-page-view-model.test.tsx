import { describe, expect, it } from "vitest";

import type { VisualReviewProjection } from "../types/visual-review";
import { toVisualReviewPageViewModel } from "./visual-review-page-view-model";

function projection(): VisualReviewProjection {
  return {
    project_id: "p1",
    project_name: "测试项目",
    review_type: "visual-professional",
    review_session_id: "visual-session-1",
    review_session: { internal_only: "must-not-reach-react" },
    source_version: "visual-v1",
    revision: 8,
    authoritative_revision: 9,
    visual_contract_ref: "artifact://visual-contract/" + "a".repeat(64),
    visual_brief_ref: "artifact://visual-brief/" + "9".repeat(64),
    visual_brief: {
      design_proposition: "可信、克制、有清晰视觉焦点",
      audience_fit: "面向经营与数字化决策者的阅读优先汇报",
      decision_task: "判断是否进入一期联合验证",
      design_stance: "证据优先，关系驱动，不用装饰制造专业感",
      emotional_boundary: "冷静、可信，不煽情",
      brand_boundary: "尊重客户品牌，不使用泛科技蓝紫模板",
      density_strategy: "关键结论疏，证据页中密度",
      narrative_rhythm: "章节聚焦—证据展开—方案收束",
      imagery_strategy: "图片必须承担证据或语境任务",
      diagram_strategy: "关系语义决定图示，不套固定图形",
      powerpoint_constraints: "事实文字、关系和数字保持原生可编辑",
      forbidden_patterns: ["平均卡片墙", "无意义科技装饰"],
      five_second_test_contract: {
        prompt: "五秒后隐藏页面并记录第一判断",
        expected_judgment: "读者形成与页面合同一致的核心判断",
        record_fields: [
          "first_noticed_object",
          "perceived_message",
          "perceived_relationship",
          "next_reading_step",
          "misdirection",
        ],
      },
      future_backend_governance: { must_not_render: true },
    },
    deck_design_system_ref: "artifact://deck-design-system/" + "b".repeat(64),
    deck_design_system: {
      production_route: "strict-B",
      theme_proposition: "克制、证据清楚",
      color_tokens: { accent: "#234B3D" },
      typography_tokens: { title: "32pt" },
      cross_slide_rhythm_rules: ["章节页留白，证据页提高密度"],
      emphasis_budget: {
        max_primary_focal_points_per_slide: 1,
        max_accent_color_roles: 2,
        consecutive_high_density_slide_limit: 2,
      },
      image_language: "只使用承担证据或语境任务的图片",
      diagram_language: "连接器必须表达明确业务语义",
      five_second_test_rules: ["第一眼能识别页面主关系"],
      future_backend_governance: { must_not_render: true },
    },
    anchor_slide_set_ref: "artifact://anchor-slide-set/" + "c".repeat(64),
    anchors: ["S01", "S02", "S03"].map((slide_id) => ({
      slide_id,
      current_asset_ref: `review-assets/anchors/${slide_id}.png`,
      previous_asset_ref: "",
    })),
    anchor_identity: {
      visual_contract_set_ref: "artifact://visual-contract-set/" + "d".repeat(64),
      slide_ids: ["S01", "S02", "S03"],
      selection_reason: "覆盖问题、方案和证据页",
      native_first_frozen: true,
      native_first_pptx_ref: "artifact://native-pptx/" + "e".repeat(64),
      pptx_sha256: "f".repeat(64),
      editability_evidence_refs: ["artifact://editability-evidence/" + "1".repeat(64)],
      preflight_render_refs: ["artifact://preflight-render/" + "2".repeat(64)],
      render_assets: ["S01", "S02", "S03"].map((slide_id) => ({
        slide_id,
        current_asset_ref: `review-assets/anchors/${slide_id}.png`,
        previous_asset_ref: "",
      })),
    },
    slide_visual_contracts: [{
      slide_id: "S01",
      order: 1,
      neutral_title: "经营协同仍有断点",
      page_family: "问题诊断页",
      page_task: "说明当前问题",
      core_claim: "业务断点需要被看见",
      visible_copy_blocks: [{ block_id: "B01", text: "页面可见文案" }],
      speaker_notes: "讲解备注",
      evidence_bindings: [{ source_ref: "source-1" }],
      communication_goal: "建立问题共识",
      composition_intent: "左事实、右因果链",
      information_hierarchy: "标题—事实—建议",
      reading_order: ["标题", "事实", "建议"],
      regions: ["标题区", "正文区"],
      object_relationships: ["事实支持建议"],
      diagram_chart_table_treatment: "原生对象",
      image_selection_and_crop: "无图",
      color_application: "单一强调色",
      typography_application: "层级清晰",
      native_bitmap_routing: "原生优先",
      editability_requirements: "可编辑",
      fallbacks: ["保留原生结构"],
      acceptance_criteria: ["无溢出"],
      reader_judgment: "当前经营协同存在需要联合验证的断点",
      primary_relationship: "causality",
      secondary_relationship: "system-boundary",
      visual_mechanism: "证据对象与因果链形成主次对照",
      focal_point: "经营断点",
      asset_roles: [{
        asset_id: "fact-evidence",
        role: "evidence",
        source_ref: "source-1",
        narrative_task: "用事实数据支持经营断点判断",
        replaceable: false,
      }],
      forbidden_patterns: ["平均卡片阵列"],
      previous_rhythm_relation: "承接章节聚焦，进入中密度证据",
      next_rhythm_relation: "为方案收束建立问题依据",
      text_density_budget: {
        max_body_lines: 8,
        max_text_blocks: 3,
        reduction_strategy: "先删解释性重复句",
      },
      powerpoint_implementation_requirements: {
        object_plan: [{
          role: "primary-subject",
          object_type: "native-shape",
          layer: "foreground",
          editability: "native-editable",
        }],
        connector_semantics: [{
          from_role: "facts",
          to_role: "judgment",
          meaning: "事实支持问题判断",
          direction: "forward",
          crossing_forbidden: true,
        }],
        layout_constraints: {
          entry_region: "left",
          focal_region: "center-right",
          minimum_clear_space: "one-body-line",
        },
        native_bitmap_routing: "事实、标签与关系原生",
        degradation_strategy: "复杂图像失败时保留原生主体与边界关系",
      },
      acceptance_evidence_plan: {
        automated_checks: ["native-object-routing", "overflow"],
        human_review_checks: ["five-second-judgment", "anti-pattern-review"],
        target_powerpoint_checks: ["font", "connector", "editability"],
        user_review_question: "五秒内是否先看到经营断点与事实支持关系？",
      },
      identity_labels: ["方案建议"],
      analysis_or_proposal_blocks: [{ internal: true }],
      solution_mapping_refs: ["mapping-1"],
      reading_quality: { internal: true },
      material_mode: "proposal-led",
      future_backend_governance: { must_not_render: true },
    }],
    anchor_feedback_batch_ref: null,
    anchor_feedback_batch: null,
    contract_review_marks_ref: null,
    contract_review_marks: null,
    gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
    visual_compilation_plan: { must_not_render: true },
    future_backend_governance: { must_not_render: true },
    host_submission_capability: "unknown",
    ai_receipt_capability: "unknown",
  } as unknown as VisualReviewProjection;
}

describe("VisualReviewPageViewModel", () => {
  it("preserves a formal visual region whose purpose is explicitly null", () => {
    const input = projection();
    (input.slide_visual_contracts[0] as unknown as Record<string, unknown>).regions = [{
      region_id: "formal-region",
      purpose: null,
    }];
    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });
    expect(viewModel.review.slide_visual_contracts[0].regions).toEqual([{
      region_id: "formal-region",
      purpose: null,
    }]);
  });

  it("closes the React contract and normalizes compatibility fields", () => {
    const input = projection();
    Object.assign(
      input.deck_design_system.color_tokens as Record<string, unknown>,
      { compiler_version: "must-not-reach-react" },
    );
    (input.slide_visual_contracts[0] as unknown as Record<string, unknown>).regions = [{
      region_id: "body",
      purpose: "呈现事实",
      technical_lineage: "must-not-reach-react",
    }];
    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    expect(viewModel.review).not.toHaveProperty("review_session");
    expect(viewModel.review).not.toHaveProperty("gate_status");
    expect(viewModel.review).not.toHaveProperty("visual_compilation_plan");
    expect(viewModel.review).not.toHaveProperty("future_backend_governance");
    expect(viewModel.review.visual_brief_ref).toBe(
      "artifact://visual-brief/" + "9".repeat(64),
    );
    expect(viewModel.review.visual_brief).toEqual({
      design_proposition: "可信、克制、有清晰视觉焦点",
      audience_fit: "面向经营与数字化决策者的阅读优先汇报",
      decision_task: "判断是否进入一期联合验证",
      design_stance: "证据优先，关系驱动，不用装饰制造专业感",
      emotional_boundary: "冷静、可信，不煽情",
      brand_boundary: "尊重客户品牌，不使用泛科技蓝紫模板",
      density_strategy: "关键结论疏，证据页中密度",
      narrative_rhythm: "章节聚焦—证据展开—方案收束",
      imagery_strategy: "图片必须承担证据或语境任务",
      diagram_strategy: "关系语义决定图示，不套固定图形",
      powerpoint_constraints: "事实文字、关系和数字保持原生可编辑",
      forbidden_patterns: ["平均卡片墙", "无意义科技装饰"],
      five_second_test_contract: {
        prompt: "五秒后隐藏页面并记录第一判断",
        expected_judgment: "读者形成与页面合同一致的核心判断",
        record_fields: [
          "first_noticed_object",
          "perceived_message",
          "perceived_relationship",
          "next_reading_step",
          "misdirection",
        ],
      },
      design_philosophy_refs: [],
    });
    expect(viewModel.review.visual_brief).not.toHaveProperty("future_backend_governance");
    expect(viewModel.review.deck_design_system).not.toHaveProperty("future_backend_governance");
    expect(viewModel.review.deck_design_system.color_tokens).not.toHaveProperty("compiler_version");
    expect(viewModel.review.deck_design_system).toMatchObject({
      cross_slide_rhythm_rules: ["章节页留白，证据页提高密度"],
      emphasis_budget: {
        max_primary_focal_points_per_slide: 1,
        max_accent_color_roles: 2,
        consecutive_high_density_slide_limit: 2,
      },
      image_language: "只使用承担证据或语境任务的图片",
      diagram_language: "连接器必须表达明确业务语义",
      five_second_test_rules: ["第一眼能识别页面主关系"],
    });
    expect(viewModel.review.anchor_identity).toEqual({
      slide_ids: ["S01", "S02", "S03"],
      selection_reason: "覆盖问题、方案和证据页",
      native_first_frozen: true,
    });
    expect(viewModel.review.slide_visual_contracts[0]).toMatchObject({
      core_claim: "业务断点需要被看见",
      visible_copy: ["页面可见文案"],
      source_refs: ["source-1"],
      anchor_title: "经营协同仍有断点",
      validation_purpose: "说明当前问题",
      reader_judgment: "当前经营协同存在需要联合验证的断点",
      primary_relationship: "causality",
      secondary_relationship: "system-boundary",
      visual_mechanism: "证据对象与因果链形成主次对照",
      focal_point: "经营断点",
      asset_roles: [{
        asset_id: "fact-evidence",
        role: "evidence",
        source_ref: "source-1",
        narrative_task: "用事实数据支持经营断点判断",
        replaceable: false,
      }],
      forbidden_patterns: ["平均卡片阵列"],
      previous_rhythm_relation: "承接章节聚焦，进入中密度证据",
      next_rhythm_relation: "为方案收束建立问题依据",
      text_density_budget: {
        max_body_lines: 8,
        max_text_blocks: 3,
        reduction_strategy: "先删解释性重复句",
      },
      powerpoint_implementation_requirements: {
        object_plan: [{
          role: "primary-subject",
          object_type: "native-shape",
          layer: "foreground",
          editability: "native-editable",
        }],
        connector_semantics: [{
          from_role: "facts",
          to_role: "judgment",
          meaning: "事实支持问题判断",
          direction: "forward",
          crossing_forbidden: true,
        }],
        layout_constraints: {
          entry_region: "left",
          focal_region: "center-right",
          minimum_clear_space: "one-body-line",
        },
        native_bitmap_routing: "事实、标签与关系原生",
        degradation_strategy: "复杂图像失败时保留原生主体与边界关系",
      },
      acceptance_evidence_plan: {
        automated_checks: ["native-object-routing", "overflow"],
        human_review_checks: ["five-second-judgment", "anti-pattern-review"],
        target_powerpoint_checks: ["font", "connector", "editability"],
        user_review_question: "五秒内是否先看到经营断点与事实支持关系？",
      },
    });
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("identity_labels");
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("analysis_or_proposal_blocks");
    expect(viewModel.review.slide_visual_contracts[0]).not.toHaveProperty("future_backend_governance");
    expect(viewModel.review.slide_visual_contracts[0].regions).toEqual([{
      region_id: "body",
      purpose: "呈现事实",
    }]);
  });

  it("removes reserved camel-case and Pascal-case keys from every visible token map", () => {
    const input = projection();
    const reservedKeys = [
      "compiler",
      "compiler_version",
      "compiler-version",
      "compilerVersion",
      "CompilerVersion",
      "handoffProtocolVersion",
      "roleRuns",
      "releaseTargetPolicyRef",
      "targetEvidenceRefs",
      "targetEvidenceIdentities",
      "internalReviewRefs",
      "rawLineage",
      "raw_lineage",
      "raw-lineage",
      "RawLineage",
      "VisualCompilationPlan",
      "visual_compilation_plan",
      "visual-compilation-plan",
      "visualCompilationPlanRef",
      "technicalLedger",
      "technical_ledger",
      "technical-ledger",
      "TechnicalLedger",
      "headRef",
      "head_ref",
      "head-ref",
      "HeadRef",
      "gateStatus",
      "gate_status",
      "gate-status",
      "GateStatus",
      "gateState",
      "artifactHeads",
      "processedCommands",
      "lastTransactionId",
      "lineage",
      "futureBackendGovernance",
      "future_backend_governance",
      "future-backend-governance",
      "FutureBackendGovernance",
      "materialInventory",
      "materialDetails",
      "auditLog",
      "internalProcessState",
      "toolExecution",
      "toolCalls",
      "compilerversion",
      "rawlineage",
      "visualcompilationplan",
      "technicalledger",
      "headref",
      "gatestatus",
    ] as const;
    const injected = Object.fromEntries(
      reservedKeys.map((key) => [key, "must-not-reach-react"]),
    );
    Object.assign(
      input.deck_design_system.color_tokens as Record<string, unknown>,
      injected,
    );
    Object.assign(
      input.deck_design_system.typography_tokens as Record<string, unknown>,
      { headline: "40pt", ...injected },
    );
    Object.assign(input.deck_design_system, {
      fallback_fonts: {
        macOS: "PingFang SC",
        ...injected,
      },
    });

    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    const visibleMaps = [
      viewModel.review.deck_design_system.color_tokens,
      viewModel.review.deck_design_system.typography_tokens,
      viewModel.review.deck_design_system.fallback_fonts,
    ];
    for (const map of visibleMaps) {
      for (const key of reservedKeys) {
        expect(map).not.toHaveProperty(key);
      }
    }
    expect(viewModel.review.deck_design_system.typography_tokens).toHaveProperty(
      "headline",
      "40pt",
    );
  });

  it("preserves business token keys across all visible maps", () => {
    const input = projection();
    const longKey = "x".repeat(65);
    Object.assign(input.deck_design_system.color_tokens as Record<string, unknown>, {
      plan_accent: "#3157D5",
      "technical_diagram_font": "Aptos",
      "customer-plan-accent": "#5B3DF5",
      "技术图示字体": "苹方",
      "1stLevel": "32pt",
      [longKey]: "#ABCDEF",
    });
    Object.assign(input.deck_design_system.typography_tokens as Record<string, unknown>, {
      plan_accent: "32pt",
      "technical_diagram_font": "Aptos",
      "customer-plan-accent": "32pt",
      "技术图示字体": "苹方",
      "1stLevel": "32pt",
      [longKey]: "40pt",
    });
    Object.assign(input.deck_design_system, {
      fallback_fonts: {
        macOS: "PingFang SC",
        plan_accent: "PingFang SC",
        "technical_diagram_font": "Aptos",
        "customer-plan-accent": "Microsoft YaHei",
        "技术图示字体": "苹方",
        "1stLevel": "Microsoft YaHei",
        [longKey]: "Aptos",
      },
    });

    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    for (const map of [
      viewModel.review.deck_design_system.color_tokens,
      viewModel.review.deck_design_system.typography_tokens,
      viewModel.review.deck_design_system.fallback_fonts,
    ]) {
      expect(map).toHaveProperty("plan_accent");
      expect(map).toHaveProperty("technical_diagram_font");
      expect(map).toHaveProperty("customer-plan-accent");
      expect(map).toHaveProperty("技术图示字体");
      expect(map).toHaveProperty("1stLevel");
      expect(map).toHaveProperty(longKey);
    }
  });

  it("keeps explicit empty visible-copy blocks ahead of the legacy frozen-copy fallback", () => {
    const input = projection();
    Object.assign(
      input.slide_visual_contracts[0] as unknown as Record<string, unknown>,
      {
      visible_copy_blocks: [],
      frozen_copy: ["legacy"],
      },
    );

    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    expect(viewModel.review.slide_visual_contracts[0].visible_copy).toEqual([]);
  });

  it("preserves a canonical null secondary relationship", () => {
    const input = projection();
    (input.slide_visual_contracts[0] as unknown as Record<string, unknown>)
      .secondary_relationship = null;

    const viewModel = toVisualReviewPageViewModel({
      surface: "review",
      selectedProjectRoot: "/managed/project",
      snapshotRevision: 9,
      review: input,
    });

    expect(viewModel.review.slide_visual_contracts[0].secondary_relationship).toBeNull();
  });
});
