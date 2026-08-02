import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { DecisionResult, HostBridge, WidgetData } from "./types";


function visualData(overrides: Record<string, unknown> = {}): WidgetData {
  const visual = {
    status: "concept-ready",
    visual_brief: {
      design_challenge: "把多系统连接讲成领导能判断的业务闭环",
      audience: "园区领导与信息化负责人",
      desired_response: "愿意启动一期",
      design_posture: "克制的前瞻感",
      constraints: ["阅读优先", "16:9"],
      visual_prohibitions: ["整页位图", "卡片墙"],
    },
    directions: [
      { id: "A", name: "城市有机体", thesis: "从分散节点汇聚为运营生命体", composition: "中心闭环与宽幅场景", density: "中低密度", image_language: "真实建筑与连接光路", risk: "场景过强可能削弱信息阅读", sample_asset_ref: "renders/concept-a.png", sample_exists: true },
      { id: "B", name: "运营证据链", thesis: "用事实与阶段证据推动决策", composition: "强网格与横向证据路径", density: "中等密度", image_language: "真实截图与工程标注", risk: "情绪张力偏弱", sample_asset_ref: "", sample_exists: false },
    ],
    direction_count: 2,
    recommended_direction: "A",
    selected_direction: "",
    engineering_samples: [],
    engineering_summary: "",
    native_coverage: {},
    engineering_qa_status: "",
    visual_contract: { design_thesis: "", palette: {}, typography: {}, layout_rules: [], image_language: [], editability_rules: [], page_families: [] },
    scene_graph_coverage: 0,
    active_task: null,
    ...overrides,
  };
  return {
    initialSpace: "visual",
    selectedProjectRoot: "/managed/project",
    snapshot: {
      schema_version: "2.0",
      revision: 7,
      updated_at: "now",
      active_space: "visual",
      project: { project_id: "p1", name: "智慧园区解决方案", project_root: "/managed/project" },
      gate_state: { current_gate: "G1", gates: { G0: "passed", G1: "open", G2: "locked", G3: "locked", G4: "locked" } },
      cognition_map: { delivery_goal: "立项", audiences: ["领导"], problem: "系统分散", ai_judgment: "关系优先", facts: [], confirmed_decisions: [], uncertainty: "视觉方向", affected_artifacts: [], outcome_status: "形成视觉构想", dialogue_focus: "选择方向" },
      artifacts: {},
      space_projections: {
        materials: { status: "classified", source_count: 0, summary: "", sources: [], findings: [], conflicts: [], gaps: [], active_task: null },
        blueprint: { status: "ready", title: "", audience: "", goal: "", context: "", narrative_thesis: "", chapters: [], slides: [], slide_count: 0, source_coverage: { available: 0, referenced: 0, unreferenced: 0 }, active_task: null },
        visual,
        delivery: {},
      },
      current_decision: { target_ref: "project://next", status: "available", question: "继续？", options: ["继续"] },
      last_human_decision_id: null,
      allowed_next_actions: [],
    },
  } as unknown as WidgetData;
}

function host(initial: WidgetData) {
  const calls: string[] = [];
  const callTool = vi.fn(async (name: string) => {
    calls.push(name);
    if (name === "read_ai_ppt_project_asset") {
      return { asset: { assetRef: "renders/concept-a.png", mimeType: "image/png", bytes: 3, dataBase64: "cG5n" } };
    }
    return {
      decision: { operation: name, status: "saved" },
      snapshot: { ...initial.snapshot, revision: initial.snapshot.revision + 1 },
      follow_up_message: `continue ${name}`,
      model_context: { project_revision: initial.snapshot.revision + 1 },
      affected_artifacts: [],
    } as DecisionResult;
  });
  const bridge: HostBridge = {
    connect: vi.fn(async () => undefined),
    callTool,
    updateModelContext: vi.fn(async () => { calls.push("context"); }),
    sendFollowUp: vi.fn(async () => { calls.push("message"); }),
    requestDisplayMode: vi.fn(async () => undefined),
    notifySize: vi.fn(),
  };
  return { bridge, callTool, calls };
}

afterEach(cleanup);

describe("Phase C visual workbench", () => {
  it("compares structurally distinct Image 2 concepts without calling them PPT samples", async () => {
    const initial = visualData();
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByRole("heading", { name: "视觉设计" })).toBeInTheDocument();
    expect(screen.getAllByText("Image 2 视觉构想")).toHaveLength(2);
    expect(screen.getByText("城市有机体")).toBeInTheDocument();
    expect(screen.getByText("运营证据链")).toBeInTheDocument();
    expect(screen.getByText("中心闭环与宽幅场景")).toBeInTheDocument();
    expect(screen.queryByText("PPTX 工程样张")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByAltText("城市有机体视觉构想")).toBeInTheDocument());
  });

  it("persists the human direction choice before later Codex execution", async () => {
    const initial = visualData();
    const { bridge, callTool } = host(initial);
    render(<App initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: /选择运营证据链/ }));
    fireEvent.click(screen.getByRole("button", { name: "保存方向 B" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("submit_ai_ppt_human_decision", {
      projectRoot: "/managed/project",
      expectedRevision: 7,
      targetRef: "concept://direction",
      choice: "B",
      feedback: "选择视觉方向：运营证据链",
    }));
    expect(bridge.sendFollowUp).not.toHaveBeenCalled();
  });

  it("labels real editable renders as PPTX engineering samples and exposes implementation risk", () => {
    const initial = visualData({
      selected_direction: "A",
      engineering_samples: [{ sample_id: "E01", slide_refs: ["S03"], render_ref: "renders/engineering.png", render_exists: true, native_element_ratio: 0.94, editable: true, notes: "文字、形状和图片裁切原生可编辑" }],
      engineering_summary: "关键页已完成工程还原",
      native_coverage: { text: true, shape: true, chart: true, whole_slide_bitmap: false },
      engineering_qa_status: "passed",
    });
    initial.snapshot.gate_state = { current_gate: "G2", gates: { G0: "passed", G1: "passed", G2: "open", G3: "locked", G4: "locked" } };
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getAllByText("PPTX 工程样张")).toHaveLength(2);
    expect(screen.getByText("原生元素 94%")).toBeInTheDocument();
    expect(screen.getByText(/整页位图：未使用/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认工程可行性并通过 G2" })).toBeInTheDocument();
  });

  it("advances to G3 only when visual contract and scene graph are present", () => {
    const initial = visualData({
      selected_direction: "A",
      visual_contract: { design_thesis: "深色空间中的连接光路", palette: { ink: "#111827" }, typography: { chinese: "PingFang SC" }, layout_rules: ["一页一个主张"], image_language: ["真实证据"], editability_rules: ["禁止整页位图"], page_families: ["闭环关系"] },
      scene_graph_coverage: 6,
    });
    initial.snapshot.gate_state = { current_gate: "G3", gates: { G0: "passed", G1: "passed", G2: "passed", G3: "open", G4: "locked" } };
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByText("深色空间中的连接光路")).toBeInTheDocument();
    expect(screen.getByText("6 页场景图")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "冻结视觉实现合同并通过 G3" })).toBeInTheDocument();
  });
});
