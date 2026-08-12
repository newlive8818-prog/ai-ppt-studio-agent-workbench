import { vi } from "vitest";

import type {
  DecisionResult,
  HostBridge,
  HostEnvironment,
  ReviewWidgetData,
  WidgetData,
} from "./types";

export function compactWidgetData(initialSpace: WidgetData["initialSpace"] = "overview"): WidgetData {
  return ({
    surface: "workbench",
    initialSpace,
    selectedProjectRoot: "/managed/project",
    snapshot: {
      schema_version: "3.0",
      revision: 12,
      project: {
        project_id: "p1",
        name: "智慧园区解决方案",
        project_root: "/managed/project",
      },
      gate_state: {
        current_gate: "G4",
        gates: { G0: "passed", G1: "passed", G2: "passed", G3: "passed", G4: "user-reviewable" },
      },
      artifacts: {
        "content/acceptance": "artifact://content-acceptance/content",
        "visual/contract": "artifact://visual-contract/visual",
      },
      workspace: {
        active_space: initialSpace || "overview",
        navigation: [
          { space_id: "overview", label: "项目总览", status: "ready", high_impact_count: 0 },
          { space_id: "materials", label: "材料工作台", status: "ready", high_impact_count: 0 },
          { space_id: "blueprint", label: "内容蓝图", status: "passed", high_impact_count: 0 },
          { space_id: "visual", label: "视觉设计", status: "passed", high_impact_count: 0 },
          { space_id: "delivery", label: "制作与交付", status: "user-reviewable", high_impact_count: 0 },
        ],
        overview: {
          status: "ready",
          conclusion: "围绕智慧园区运营中台促成一期立项。",
          focus: "当前焦点：G4 · user-reviewable",
          risk: "暂无任务书级阻断，后续风险以当前质量门为准。",
          affected_artifacts: ["artifact://mission-draft/mission"],
          high_impact_count: 0,
          primary_action: { kind: "continue-chat", label: "继续与 Codex 对话", enabled: true },
          delivery_goal: "让客户确认一期建设路径并启动项目",
          audiences: ["园区管委会领导"],
          topic: "智慧园区运营中台",
        },
        materials: {
          status: "ready",
          conclusion: "已接收 4 份用户提供且可追溯的材料。",
          focus: "材料将按当前任务自动分类并提炼。",
          risk: "缺少一期验收指标。",
          affected_artifacts: ["artifact://material-inventory/materials"],
          high_impact_count: 1,
          primary_action: { kind: "continue-chat", label: "查看 AI 提炼结果", enabled: true },
          source_count: 4,
          parsed_count: 4,
          failed_count: 0,
          authorization_count: 0,
          external_search: false,
        },
        blueprint: {
          status: "passed",
          conclusion: "内容蓝图已通过内部审查，可集中阅读整套论证。",
          focus: "先证明运营断点，再给出低风险建设路径。",
          risk: "当前没有需要用户处理的内容审阅动作。",
          affected_artifacts: ["artifact://content-blueprint/content"],
          high_impact_count: 0,
          primary_action: { kind: "open-content-review", label: "打开内容审阅", enabled: true },
          phase: "passed",
          internal_status: "passed",
          slide_count: 12,
          saved_mark_count: 2,
          review_available: true,
          source_version: "artifact://content-blueprint/content",
        },
        visual: {
          status: "passed",
          conclusion: "整套视觉合同和锚点页已通过 G1 / G2 内部门。",
          focus: "可信的经营证据链。",
          risk: "任一内部硬门或四目标证据不完整时不会开放确认。",
          affected_artifacts: ["artifact://visual-contract/visual"],
          high_impact_count: 0,
          primary_action: { kind: "open-visual-review", label: "打开视觉合同", enabled: true },
          g1_status: "passed",
          g2_status: "passed",
          g3_status: "passed",
          saved_mark_count: 1,
          review_available: true,
          source_version: "artifact://visual-contract/visual",
          production_route: "strict-B",
        },
        delivery: {
          status: "user-reviewable",
          conclusion: "已完成 12/12 页制作与逐页质量检查。",
          focus: "最终 PPTX 已发送到聊天，等待用户明确接受或修改。",
          risk: "当前没有内部阻断项。",
          affected_artifacts: ["artifact://presentation-build/build"],
          high_impact_count: 0,
          primary_action: { kind: "none", label: "", enabled: false },
          phase: "user-reviewable",
          slides: { completed: 12, total: 12 },
          quality_gates: { semantic: "passed", aesthetic: "passed", engineering: "passed", target_render: "passed" },
          highest_blocker: null,
          targets: [
            { target_id: "macos-powerpoint", status: "passed", pptx_sha256: "7".repeat(64) },
            { target_id: "macos-wps", status: "passed", pptx_sha256: "7".repeat(64) },
            { target_id: "windows-powerpoint", status: "passed", pptx_sha256: "7".repeat(64) },
            { target_id: "windows-wps", status: "passed", pptx_sha256: "7".repeat(64) },
          ],
          hash_identity: "7".repeat(64),
          chat_send: { status: "sent", message_ref: "chat://message/pptx-1", sent_at: "2026-08-09T20:00:00+08:00" },
        },
      },
      experience: {
        intake_counts: { total: 0, by_source_type: {}, by_learning_status: {} },
        result_counts: { total: 0, by_result_type: {}, by_status: {} },
        candidates: [], role_slices: [], application_outcomes: [], stable_release_candidates: [],
      },
      allowed_next_actions: [],
    },
  }) as unknown as WidgetData;
}

export function reviewWidgetData(reviewType: "content" | "visual" = "content"): ReviewWidgetData {
  // Sections mirror the schema 3 ReviewService anchors:
  // content => content-overview + content-structure(optional) + slide-*;
  // visual  => visual-framework + deck-design-system + visual-slide-*.
  const sections =
    reviewType === "content"
      ? [
          {
            anchor: "content-overview",
            title: "整套内容与售前策略",
            fields: [
              { anchor: "content-overview-title", label: "title", value: "智慧园区解决方案" },
              { anchor: "content-overview-goal", label: "goal", value: "启动一期建设" },
              {
                anchor: "content-overview-narrative-thesis",
                label: "narrative_thesis",
                value: "先证明运营断点，再给出低风险建设路径",
              },
            ],
          },
          {
            anchor: "content-structure",
            title: "章节与整套论证结构",
            fields: [
              {
                anchor: "content-structure-content",
                label: "content",
                value: [{ title: "为什么现在必须建设", slide_ids: ["S01", "S02"] }],
              },
            ],
          },
          {
            anchor: "slide-s01",
            title: "第 1 页 · 为什么现在必须建设",
            fields: [
              { anchor: "slide-s01-visible-content", label: "visible_content", value: ["五套系统", "三条断点", "一个经营闭环"] },
              { anchor: "slide-s01-speaker-notes", label: "speaker_notes", value: "完整讲解稿必须原样进入专业审阅页。" },
              { anchor: "slide-s01-source-refs", label: "source_refs", value: ["sources/meeting.json#p3"] },
            ],
          },
          {
            anchor: "slide-s02",
            title: "第 2 页 · 建设路径",
            fields: [
              { anchor: "slide-s02-visible-content", label: "visible_content", value: ["一期聚焦", "联合工作组"] },
              { anchor: "slide-s02-speaker-notes", label: "speaker_notes", value: "逐页讲解稿完整保留。" },
            ],
          },
        ]
      : [
          {
            anchor: "visual-framework",
            title: "整套视觉框架",
            fields: [
              { anchor: "visual-framework-design-thesis", label: "design_thesis", value: "可信的经营证据链" },
              {
                anchor: "visual-framework-palette",
                label: "palette",
                value: { ink: "#172033", accent: "#5B3DF5" },
              },
            ],
          },
          {
            anchor: "deck-design-system",
            title: "Deck Design System",
            fields: [
              { anchor: "deck-design-system-theme-proposition", label: "theme_proposition", value: "可信的经营证据链" },
              { anchor: "deck-design-system-page-families", label: "page_families", value: ["决策封面", "证据页"] },
            ],
          },
          {
            anchor: "visual-slide-s01",
            title: "第 1 页视觉合同 · 系统在线，经营仍然断裂",
            fields: [
              { anchor: "visual-slide-s01-visible-copy", label: "visible_copy", value: ["五套系统", "三条断点", "一个经营闭环"] },
              { anchor: "visual-slide-s01-speaker-notes", label: "speaker_notes", value: "视觉合同仍需保留完整内容讲解稿。" },
              { anchor: "visual-slide-s01-source-refs", label: "source_refs", value: ["sources/meeting.json#p3"] },
              { anchor: "visual-slide-s01-page-family", label: "page_family", value: "证据页" },
              { anchor: "visual-slide-s01-composition-intent", label: "composition_intent", value: "左侧事实，右侧因果链" },
              { anchor: "visual-slide-s01-acceptance-criteria", label: "acceptance_criteria", value: ["业务关系可读", "文字原生可编辑"] },
            ],
          },
        ];

  return {
    surface: "review",
    selectedProjectRoot: "/managed/project",
    snapshotRevision: 12,
    review: {
      review_type: reviewType,
      display_policy: "professional-review",
      project_id: "p1",
      project_name: "智慧园区解决方案",
      title: reviewType === "content" ? "智慧园区内容蓝图" : "可信的经营证据链",
      revision: 12,
      status: "user-reviewable",
      gate_status: reviewType === "content"
        ? { G0: "user-reviewable" }
        : { G1: "passed", G2: "passed", G3: "user-reviewable" },
      source_version: `${reviewType}-v0001-abc123`,
      source_refs: [`${reviewType}:v0001:abc123`],
      generated_at: "2026-08-07T08:30:00+08:00",
      outline: sections.map((s) => ({ anchor: s.anchor, title: s.title })),
      sections,
      mark_set: {
        mark_set_id: "",
        status: "draft",
        marks: [],
      },
    },
  };
}

const DEFAULT_HOST_ENVIRONMENT: HostEnvironment = {
  containerWidth: 480,
  canSendMessage: true,
  canUpdateModelContext: true,
};

export function hostBridge(
  initial: WidgetData | ReviewWidgetData,
  environment: HostEnvironment = DEFAULT_HOST_ENVIRONMENT,
) {
  const callTool = vi.fn(async (name: string) => {
    const widget = "snapshot" in initial ? initial : compactWidgetData();
    return {
      decision: { operation: name, status: "saved" },
      snapshot: { ...widget.snapshot, revision: widget.snapshot.revision + 1 },
      follow_up_message: `continue ${name}`,
      model_context: { project_revision: widget.snapshot.revision + 1 },
      affected_artifacts: [],
    } as DecisionResult;
  });
  const confirmMission = vi.fn(async () => {
    const widget = "snapshot" in initial ? initial : compactWidgetData();
    return {
      artifact_ref: "artifact://mission-confirmation/confirmed-1",
      snapshot: {
        ...widget.snapshot,
        revision: widget.snapshot.revision + 1,
        missionConfirmationRef:
          "artifact://mission-confirmation/confirmed-1",
      },
    };
  });
  const bridge: HostBridge = {
    connect: vi.fn(async () => undefined),
    callTool: callTool as HostBridge["callTool"],
    updateModelContext: vi.fn(async () => undefined),
    sendFollowUp: vi.fn(async () => undefined),
    confirmMission,
    getHostEnvironment: vi.fn(() => environment),
    notifySize: vi.fn(),
  };
  return { bridge, callTool, confirmMission };
}
