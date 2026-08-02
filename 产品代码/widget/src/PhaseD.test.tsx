import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { DecisionResult, HostBridge, WidgetData } from "./types";


function deliveryData(overrides: Record<string, unknown> = {}): WidgetData {
  const delivery = {
    status: "qa-passed",
    gate_state: { current_gate: "G4", gates: { G0: "passed", G1: "passed", G2: "passed", G3: "passed", G4: "open" } },
    pptx_ref: "ppt/智慧园区运营中台解决方案.pptx",
    pptx_exists: true,
    slide_count: 3,
    renders: [
      { asset_ref: "renders/slide-1.png", exists: true },
      { asset_ref: "renders/slide-2.png", exists: true },
      { asset_ref: "renders/slide-3.png", exists: true },
    ],
    render_count: 3,
    qa_status: "passed",
    editable: true,
    whole_slide_bitmap: false,
    validation_ref: "reviews/delivery-validation.json",
    qa_checks: { overflow: "passed", pptx_archive: "passed", whole_slide_bitmap: "not_used" },
    qa_notes: ["事实文字、流程和架构均为 PowerPoint 原生可编辑对象"],
    qa_issues: [],
    source_count: 4,
    active_task: null,
    ...overrides,
  };
  return {
    initialSpace: "delivery",
    selectedProjectRoot: "/managed/project",
    snapshot: {
      schema_version: "2.0",
      revision: 12,
      updated_at: "now",
      active_space: "delivery",
      project: { project_id: "p1", name: "智慧园区解决方案", project_root: "/managed/project" },
      gate_state: delivery.gate_state,
      cognition_map: { delivery_goal: "立项", audiences: ["领导"], problem: "系统分散", ai_judgment: "交付已通过 QA", facts: [], confirmed_decisions: [], uncertainty: "等待验收", affected_artifacts: [], outcome_status: "已形成可交付成果", dialogue_focus: "验收 PPTX" },
      artifacts: {},
      space_projections: {
        materials: { status: "classified", source_count: 0, summary: "", sources: [], findings: [], conflicts: [], gaps: [], active_task: null },
        blueprint: { status: "ready", title: "", audience: "", goal: "", context: "", narrative_thesis: "", chapters: [], slides: [], slide_count: 0, source_coverage: { available: 0, referenced: 0, unreferenced: 0 }, active_task: null },
        visual: { status: "contract-ready", visual_brief: { design_challenge: "", audience: "", desired_response: "", design_posture: "", constraints: [], visual_prohibitions: [] }, directions: [], direction_count: 0, recommended_direction: "", selected_direction: "", engineering_samples: [], engineering_summary: "", native_coverage: {}, engineering_qa_status: "", visual_contract: { design_thesis: "", palette: {}, typography: {}, layout_rules: [], image_language: [], editability_rules: [], page_families: [] }, scene_graph_coverage: 0, active_task: null },
        delivery,
      },
      current_decision: { target_ref: "delivery://current", status: "available", question: "接受？", options: ["接受"] },
      last_human_decision_id: null,
      allowed_next_actions: [],
    },
  } as unknown as WidgetData;
}

function host(initial: WidgetData) {
  const callTool = vi.fn(async (name: string) => {
    if (name === "read_ai_ppt_project_asset") {
      return { asset: { assetRef: "renders/slide.png", mimeType: "image/png", bytes: 3, dataBase64: "cG5n" } };
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
    updateModelContext: vi.fn(async () => undefined),
    sendFollowUp: vi.fn(async () => undefined),
    requestDisplayMode: vi.fn(async () => undefined),
    notifySize: vi.fn(),
  };
  return { bridge, callTool };
}

afterEach(cleanup);

describe("Phase D delivery workbench", () => {
  it("shows G0-G4, real renders, editable PPTX and QA as separate evidence", async () => {
    const initial = deliveryData();
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByRole("heading", { name: "制作与交付" })).toBeInTheDocument();
    expect(screen.getAllByText(/^G[0-4]$/)).toHaveLength(5);
    expect(screen.getByText("可编辑 PPTX")).toBeInTheDocument();
    expect(screen.getAllByText("真实渲染")).toHaveLength(2);
    expect(screen.getByText("QA 已通过")).toBeInTheDocument();
    const bitmapEvidence = screen.getAllByText("整页位图")[0].closest("div");
    expect(bitmapEvidence).toHaveTextContent("未使用");
    expect(screen.getByText("ppt/智慧园区运营中台解决方案.pptx")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByAltText(/第 [1-3] 页渲染/)).toHaveLength(4));
  });

  it("selects a render from the contact sheet without changing project state", async () => {
    const initial = deliveryData();
    const { bridge, callTool } = host(initial);
    render(<App initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "查看第 2 页" }));
    await waitFor(() => expect(screen.getByAltText("第 2 页渲染大图")).toBeInTheDocument());
    expect(callTool.mock.calls.filter(([name]) => name !== "read_ai_ppt_project_asset")).toHaveLength(0);
  });

  it("preserves the last valid build and offers Presentations repair when QA fails", () => {
    const initial = deliveryData({
      status: "built",
      qa_status: "failed",
      qa_issues: ["第 3 页右侧文字溢出"],
      active_task: { task_id: "t1", action_type: "repair-pptx", status: "requested" },
    });
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByText(/上一份有效 PPTX 与已完成渲染已保留/)).toBeInTheDocument();
    expect(screen.getByText("第 3 页右侧文字溢出")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "用 Presentations 修复并重新检查" })).toBeInTheDocument();
  });

  it("passes G4 only through the governed acceptance tool", async () => {
    const initial = deliveryData();
    const { bridge, callTool } = host(initial);
    render(<App initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "验收交付并通过 G4" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("confirm_ai_ppt_gate", {
      projectRoot: "/managed/project",
      expectedRevision: 12,
      gate: "G4",
    }));
  });
});
