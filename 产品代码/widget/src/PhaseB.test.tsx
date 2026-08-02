import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { DecisionResult, HostBridge, WidgetData } from "./types";


function data(initialSpace: "materials" | "blueprint"): WidgetData {
  return {
    initialSpace,
    selectedProjectRoot: "/managed/project",
    snapshot: {
      schema_version: "2.0",
      revision: 3,
      updated_at: "now",
      active_space: initialSpace,
      project: { project_id: "p1", name: "智慧园区解决方案", project_root: "/managed/project" },
      gate_state: { current_gate: "G0", gates: { G0: "open", G1: "locked", G2: "locked", G3: "locked", G4: "locked" } },
      cognition_map: {
        delivery_goal: "促成一期立项",
        audiences: ["园区领导"],
        problem: "系统分散",
        ai_judgment: "先确认内容",
        facts: [],
        confirmed_decisions: [],
        uncertainty: "无",
        affected_artifacts: [],
        outcome_status: "成果正在形成中",
        dialogue_focus: "确认内容蓝图",
      },
      artifacts: {},
      space_projections: {
        materials: {
          status: "classified",
          source_count: 3,
          summary: "已识别客户需求和建设依据",
          sources: [
            { source_id: "s1", source_ref: "sources/s1.json", name: "需求说明.pdf", kind: "file", mode: "copy", size_bytes: 2048, classification: "客户需求材料", purposes: ["customer-needs"], status: "usable" },
            { source_id: "s2", source_ref: "sources/s2.json", name: "会议纪要链接", kind: "url", mode: "reference", size_bytes: null, classification: "会议结论", purposes: ["evidence"], status: "partial" },
            { source_id: "s3", source_ref: "sources/s3.json", name: "建设目标.txt", kind: "file", mode: "copy", size_bytes: 128, classification: "建设目标", purposes: ["roadmap"], status: "classified" },
          ],
          findings: [{ finding_id: "F1", finding_type: "fact", content: "九月完成一期上线", source_ref: "sources/s1.json", locator: "第 3 页", fact_status: "source-fact", purposes: ["customer-needs"] }],
          conflicts: [],
          gaps: ["缺少验收指标"],
          active_task: null,
        },
        blueprint: {
          status: "ready",
          title: "智慧园区运营中台解决方案",
          audience: "园区领导",
          goal: "确认一期建设路径",
          context: "阅读优先售前汇报",
          narrative_thesis: "先证明运营断点，再给出低风险建设路径",
          chapters: [{ title: "为什么现在建设", slide_ids: ["S01"] }],
          slides: [{ slide_id: "S01", title: "系统在线，运营仍然断裂", role: "现状诊断", purpose: "建立紧迫性", claim: "分散系统阻碍协同", visible_content: ["五套系统", "电话协调"], speaker_notes: "引用会议纪要", source_refs: ["sources/s1.json"], material_refs: ["s1"], fact_status: "source-fact" }],
          slide_count: 1,
          source_coverage: { available: 2, referenced: 1, unreferenced: 1 },
          active_task: null,
        },
        visual: {},
        delivery: {},
      },
      current_decision: { target_ref: "project://next", status: "available", question: "继续？", options: ["继续"] },
      last_human_decision_id: null,
      allowed_next_actions: [],
    },
  } as unknown as WidgetData;
}

function host(initial: WidgetData) {
  let revision = initial.snapshot.revision;
  const callTool = vi.fn(async (name: string) => {
    revision += 1;
    return {
      decision: { operation: name, task_id: "task-1", status: "requested" },
      snapshot: { ...initial.snapshot, revision },
      follow_up_message: `continue ${name}`,
      model_context: { project_revision: revision },
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

describe("Phase B native workbench", () => {
  it("uses one flexible material entrance and shows AI classifications", () => {
    const initial = data("materials");
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByRole("heading", { name: "材料工作台" })).toBeInTheDocument();
    expect(screen.getByText(/文件、图片、文字和链接都从这里进入/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择文件" })).toBeInTheDocument();
    expect(screen.getByText("客户需求材料")).toBeInTheDocument();
    expect(screen.getByText("已提炼")).toBeInTheDocument();
    expect(screen.getByText("缺少验收指标")).toBeInTheDocument();
    expect(screen.getByText(/AI 只使用你提供的材料/)).toBeInTheDocument();
    expect(screen.queryByText("必须上传客户需求材料")).not.toBeInTheDocument();
  });

  it("persists material before creating the automatic classification task", async () => {
    const initial = data("materials");
    const { bridge, callTool } = host(initial);
    render(<App initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "粘贴文字或链接" }));
    fireEvent.change(screen.getByLabelText("补充材料"), { target: { value: "客户要求九月上线" } });
    fireEvent.click(screen.getByRole("button", { name: "添加并自动提炼" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(2));
    expect(callTool.mock.calls[0][0]).toBe("add_ai_ppt_material");
    expect(callTool.mock.calls[1][0]).toBe("request_ai_ppt_agent_action");
    expect(callTool.mock.calls[1][1]).toMatchObject({ expectedRevision: 4, actionType: "classify-materials" });
    expect(bridge.sendFollowUp).toHaveBeenCalledTimes(1);
  });

  it("shows narrative and page content before any visual decision", () => {
    const initial = data("blueprint");
    render(<App initialData={initial} bridge={host(initial).bridge} />);
    expect(screen.getByRole("heading", { name: "内容蓝图" })).toBeInTheDocument();
    expect(screen.getByText("先证明运营断点，再给出低风险建设路径")).toBeInTheDocument();
    expect(screen.getByText("为什么现在建设")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /S01.*系统在线/ })).toBeInTheDocument();
    expect(screen.getByText(/本阶段只确认内容、证据与叙事/)).toBeInTheDocument();
    expect(screen.queryByText("视觉评分")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认内容蓝图并通过 G0" })).toBeInTheDocument();
  });

  it("confirms G0 through the governed gate tool", async () => {
    const initial = data("blueprint");
    const { bridge, callTool } = host(initial);
    render(<App initialData={initial} bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "确认内容蓝图并通过 G0" }));
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(callTool).toHaveBeenCalledWith("confirm_ai_ppt_gate", {
      projectRoot: "/managed/project",
      expectedRevision: 3,
      gate: "G0",
    });
  });
});
