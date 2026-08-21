import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("v1.6 schema 3 compact delivery projection", () => {
  it("shows the current required target and three explicitly deferred profiles", () => {
    const initial = compactWidgetData("delivery");
    render(<App initialData={initial} bridge={hostBridge(initial).bridge} />);

    expect(screen.getByText("制作阶段 · 等待 G4 聊天验收")).toBeInTheDocument();
    for (const label of ["业务语义", "视觉完成度", "排版工程", "目标软件渲染"]) {
      expect(screen.getByTestId(`binary-gate-${label}`)).toHaveTextContent("通过");
    }
    expect(screen.getAllByTestId("delivery-blocker")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "当前发布目标证据" })).toBeInTheDocument();
    for (const label of ["macOS PowerPoint", "macOS WPS", "Windows PowerPoint", "Windows WPS"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByTestId("target-macos-powerpoint")).toHaveTextContent("已验证：macOS Microsoft PowerPoint");
    expect(screen.getAllByText("延期 · 当前版本不验收")).toHaveLength(3);
    expect(screen.queryByText("跨平台通过")).not.toBeInTheDocument();
    expect(screen.queryByText("Windows/WPS 兼容")).not.toBeInTheDocument();
    expect(screen.getByText("7".repeat(64))).toBeInTheDocument();
    expect(screen.getByText("聊天发送：已发送")).toBeInTheDocument();

    expect(screen.queryByText("联系表")).not.toBeInTheDocument();
    expect(screen.queryByText("下载 PPTX")).not.toBeInTheDocument();
    expect(screen.queryByText("验收交付并通过 G4")).not.toBeInTheDocument();
  });
});
