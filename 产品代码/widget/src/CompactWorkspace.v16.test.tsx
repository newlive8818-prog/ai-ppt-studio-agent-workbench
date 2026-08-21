import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";
import type { SpaceId } from "./types";

afterEach(cleanup);

const orderedSteps = ["conclusion", "focus-risk", "artifacts", "judgment", "action"];

describe("v1.6 compact five-space reading line", () => {
  it("renders the complete unconfirmed mission card and confirms only through the sidebar host", async () => {
    const initial = compactWidgetData("overview");
    initial.snapshot.revision = 3;
    initial.snapshot.missionDraftRef = "artifact://mission-draft/draft-1";
    initial.snapshot.missionConfirmationRef = "";
    initial.snapshot.materialMode = "unconfirmed";
    initial.snapshot.contentIdentityMode = "blocked";
    initial.snapshot.artifacts = {
      "mission/draft": "artifact://mission-draft/draft-1",
    };
    initial.snapshot.workspace.overview = {
      ...initial.snapshot.workspace.overview,
      status: "needs-input",
      conclusion: "任务字段已齐全，等待用户显式确认。",
      risk: "任务卡未获得真实用户确认，不能开始正式内容生产。",
      mission_status: "confirmable",
      mission_draft_ref: "artifact://mission-draft/draft-1",
      mission_confirmation_ref: "",
      material_mode: "unconfirmed",
      content_identity_mode: "blocked",
      mission_card: {
        topic: "经营一体化方案",
        primary_audience: "客户经营与数字化决策团队",
        desired_judgment_or_action: "确认一期范围并进入联合验证",
        material_state: "no-materials",
        material_inventory_ref: "",
        materials: [],
        background: ["客户尚未提供现状材料"],
        constraints: ["阅读优先"],
        red_lines: ["不虚构客户事实"],
        unknowns: ["当前系统边界待联合确认"],
      },
      primary_action: {
        kind: "confirm-mission",
        label: "确认任务并开始内容策划",
        enabled: true,
      },
    };
    const host = hostBridge(initial);
    render(<App initialData={initial} bridge={host.bridge} />);

    expect(screen.getByRole("heading", { name: "请确认本次汇报任务" })).toBeInTheDocument();
    expect(screen.getByText("客户经营与数字化决策团队")).toBeInTheDocument();
    expect(screen.getByText("确认一期范围并进入联合验证")).toBeInTheDocument();
    expect(screen.getByText("客户尚未提供现状材料")).toBeInTheDocument();
    expect(screen.getByText("阅读优先")).toBeInTheDocument();
    expect(screen.getByText("不虚构客户事实")).toBeInTheDocument();
    expect(screen.getByText("当前系统边界待联合确认")).toBeInTheDocument();
    expect(screen.getByText("当前明确无材料")).toBeInTheDocument();
    expect(screen.getByText("将以方案建议模式继续")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "确认任务并开始内容策划" }));

    await waitFor(() => expect(host.confirmMission).toHaveBeenCalledWith({
      projectRoot: "/managed/project",
      expectedRevision: 3,
      missionDraftRef: "artifact://mission-draft/draft-1",
      materialMode: "no-materials-confirmed",
      materialInventoryRef: "",
    }));
    expect(host.callTool).not.toHaveBeenCalledWith(
      "confirm_ai_ppt_mission",
      expect.anything(),
    );
    expect(host.bridge.sendFollowUp).not.toHaveBeenCalled();
  });

  for (const space of ["overview", "materials", "visual"] satisfies SpaceId[]) {
    it(`renders ${space} in the formal cognition order with one strongest action`, () => {
      const initial = compactWidgetData(space);
      const { container } = render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

      expect(
        Array.from(container.querySelectorAll("[data-cognition-step]"), (node) =>
          node.getAttribute("data-cognition-step"),
        ),
      ).toEqual(orderedSteps);
      expect(container.querySelectorAll(".compact-primary-action")).toHaveLength(1);
      expect(screen.getByText(initial.snapshot.workspace[space].affected_artifacts[0])).toBeInTheDocument();
    });
  }

  it("does not invent an action while content review is unavailable", () => {
    const initial = compactWidgetData("blueprint");
    initial.snapshot.workspace.blueprint = {
      ...initial.snapshot.workspace.blueprint,
      status: "open",
      internal_status: "pending",
      review_available: false,
      primary_action: { kind: "none", label: "", enabled: false },
    };
    const { container } = render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

    expect(container.querySelectorAll(".compact-primary-action")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "打开内容审阅" })).not.toBeInTheDocument();
  });

  it("binds only current required evidence to the PPTX identity", () => {
    const initial = compactWidgetData("delivery");
    const { container } = render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

    expect(container.querySelectorAll('[data-testid^="binary-gate-"]')).toHaveLength(4);
    expect(container.querySelectorAll('[data-testid^="target-"]')).toHaveLength(4);
    for (const target of initial.snapshot.workspace.delivery.targets) {
      const row = screen.getByTestId(`target-${target.target_id}`);
      if (initial.snapshot.workspace.delivery.release_target_policy.required_target_ids.includes(target.target_id)) {
        expect(row).toHaveAttribute(
          "data-pptx-sha256",
          initial.snapshot.workspace.delivery.hash_identity,
        );
      } else {
        expect(row).not.toHaveAttribute("data-pptx-sha256");
        expect(row).toHaveTextContent("延期 · 当前版本不验收");
      }
    }
    expect(screen.getAllByTestId("delivery-blocker")).toHaveLength(1);
    expect(container.querySelectorAll(".compact-primary-action")).toHaveLength(0);
    expect(container).not.toHaveTextContent("联系表");
    expect(container).not.toHaveTextContent("下载 PPTX");
    expect(container).not.toHaveTextContent("机器日志");
  });

  it("keeps all five projected navigation items in authoritative order", () => {
    const initial = compactWidgetData("overview");
    render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

    expect(
      screen.getAllByRole("button", { name: /项目总览|材料工作台|内容蓝图|视觉设计|制作与交付/ })
        .map((button) => button.textContent?.replace(/ready|passed|user-reviewable/g, "")),
    ).toEqual(["项目总览", "材料工作台", "内容蓝图", "视觉设计", "制作与交付"]);
  });
});
