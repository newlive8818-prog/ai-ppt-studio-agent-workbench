import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("v1.6 schema 3 compact AI PPT workbench", () => {
  it("keeps five spaces and a conclusion-risk-outcome hierarchy", () => {
    const initial = compactWidgetData("overview");
    expect(initial.snapshot.schema_version).toBe("3.0");
    expect(JSON.stringify(initial.snapshot)).not.toContain("space_projections");
    render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

    for (const label of ["项目总览", "材料工作台", "内容蓝图", "视觉设计", "制作与交付"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
    }
    const headings = screen.getAllByRole("heading").map((node) => node.textContent);
    expect(headings.indexOf("AI 当前结论")).toBeLessThan(headings.indexOf("当前风险"));
    expect(headings.indexOf("当前风险")).toBeLessThan(headings.indexOf("当前成果"));
    expect(screen.getAllByRole("button", { name: "继续与 Codex 对话" })).toHaveLength(1);
  });

  it("does not expose the legacy full-workbench expansion or gate actions", () => {
    const initial = compactWidgetData("overview");
    render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);
    expect(screen.queryByText("展开完整工作台")).not.toBeInTheDocument();
    expect(screen.queryByText(/G1.*确认|G2.*确认|G4.*验收/)).not.toBeInTheDocument();
    expect(screen.queryByText("下载 PPTX")).not.toBeInTheDocument();
  });
});
