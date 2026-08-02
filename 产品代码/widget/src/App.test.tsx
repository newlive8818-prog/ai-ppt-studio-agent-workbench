import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { HostBridge, WidgetData } from "./types";

const widgetData: WidgetData = {
  initialSpace: "overview",
  requestedDisplayMode: "inline",
  selectedProjectRoot: "/managed/project",
  snapshot: {
    schema_version: "2.0",
    revision: 3,
    updated_at: "2026-08-02T08:30:00+08:00",
    active_space: "overview",
    project: {
      project_id: "p1",
      name: "智慧园区解决方案",
      project_root: "/managed/project",
    },
    gate_state: {
      current_gate: "G0",
      gates: { G0: "open", G1: "locked", G2: "locked", G3: "locked", G4: "locked" },
    },
    cognition_map: {
      delivery_goal: "让客户确认一期建设路径并启动项目",
      audiences: ["园区管委会领导", "信息化负责人"],
      problem: "如何保护既有投资并形成运营闭环",
      ai_judgment: "先用业务闭环建立共识，再解释四层架构。",
      facts: [{ summary: "用户已提供 4 份可追溯材料", source_count: 4 }],
      confirmed_decisions: [{ decision_id: "d0", choice: "内容先于视觉" }],
      uncertainty: "首批落地场景的优先级仍需确认",
      affected_artifacts: ["content-blueprint", "visual-brief"],
      outcome_status: "成果正在形成中",
      dialogue_focus: "确认首批落地场景",
    },
    artifacts: {
      mission: { kind: "mission", version: 1, path: "mission.json", sha256: "x", created_at: "now" },
    },
    current_decision: {
      target_ref: "project://next-focus",
      status: "available",
      question: "是否按 AI 当前判断继续推进？",
      why_now: "继续前需要确认主线没有偏离。",
      options: ["继续推进", "提出修改", "暂不处理"],
      recommended_choice: "继续推进",
      reversible: true,
    },
    last_human_decision_id: null,
    allowed_next_actions: ["submit-human-decision"],
  },
};

function bridge(overrides: Partial<HostBridge> = {}): HostBridge {
  return {
    connect: vi.fn(async () => undefined),
    callTool: vi.fn(async () => ({
      decision: { decision_id: "d1", choice: "继续推进" },
      snapshot: { ...widgetData.snapshot, revision: 4 },
      follow_up_message: "继续处理下一项工作",
      model_context: { project_revision: 4 },
      affected_artifacts: ["content-blueprint"],
    })),
    updateModelContext: vi.fn(async () => undefined),
    sendFollowUp: vi.fn(async () => undefined),
    requestDisplayMode: vi.fn(async () => undefined),
    notifySize: vi.fn(),
    ...overrides,
  };
}

afterEach(cleanup);

describe("AI PPT Studio workbench", () => {
  it("renders the conclusion-first cognition path with distinct state semantics", () => {
    render(<App initialData={widgetData} bridge={bridge()} />);
    const headings = screen.getAllByRole("heading").map((node) => node.textContent);
    expect(headings.indexOf("交付目标")).toBeLessThan(headings.indexOf("AI 当前判断"));
    expect(headings.indexOf("AI 当前判断")).toBeLessThan(headings.indexOf("当前不确定性"));
    expect(screen.getByText("事实")).toBeInTheDocument();
    expect(screen.getByText("AI 推论")).toBeInTheDocument();
    expect(screen.getByText("已确认")).toBeInTheDocument();
    expect(screen.getByText("待澄清")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "提交当前判断" })).toHaveLength(1);
  });

  it("persists before updating context and sending a follow-up", async () => {
    const events: string[] = [];
    const host = bridge({
      callTool: vi.fn(async () => {
        events.push("save");
        return {
          decision: { decision_id: "d1", choice: "继续推进" },
          snapshot: { ...widgetData.snapshot, revision: 4 },
          follow_up_message: "继续处理下一项工作",
          model_context: { project_revision: 4 },
          affected_artifacts: ["content-blueprint"],
        };
      }),
      updateModelContext: vi.fn(async () => { events.push("context"); }),
      sendFollowUp: vi.fn(async () => { events.push("message"); }),
    });
    render(<App initialData={widgetData} bridge={host} />);
    fireEvent.click(screen.getByRole("radio", { name: /继续推进/ }));
    fireEvent.click(screen.getByRole("button", { name: "提交当前判断" }));
    await waitFor(() => expect(screen.getByText(/已保存为 revision 4/)).toBeInTheDocument());
    expect(events).toEqual(["save", "context", "message"]);
  });

  it("honestly reports host fallback after the project decision was saved", async () => {
    const host = bridge({
      sendFollowUp: vi.fn(async () => { throw new Error("unsupported"); }),
    });
    render(<App initialData={widgetData} bridge={host} />);
    fireEvent.click(screen.getByRole("radio", { name: /继续推进/ }));
    fireEvent.click(screen.getByRole("button", { name: "提交当前判断" }));
    await waitFor(() => expect(screen.getByText(/判断已保存，但宿主未自动发起后续对话/)).toBeInTheDocument());
  });

  it("requests fullscreen as a secondary action", async () => {
    const host = bridge();
    render(<App initialData={widgetData} bridge={host} />);
    fireEvent.click(screen.getByRole("button", { name: "展开完整工作台" }));
    await waitFor(() => expect(host.requestDisplayMode).toHaveBeenCalledWith("fullscreen"));
  });
});
