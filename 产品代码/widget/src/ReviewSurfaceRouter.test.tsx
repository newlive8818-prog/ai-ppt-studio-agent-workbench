import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("Codex Browser professional-review routing", () => {
  it("opens the exact content source through the Browser tool", async () => {
    const initial = compactWidgetData("blueprint");
    const { bridge, callTool } = hostBridge(initial);
    render(<App initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "打开内容审阅" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("open_ai_ppt_browser_review", {
      projectRoot: "/managed/project",
      reviewType: "content",
      sourceVersion: "artifact://content-blueprint/content",
    }));
  });

  it("opens the exact visual source through the Browser tool", async () => {
    const initial = compactWidgetData("visual");
    const { bridge, callTool } = hostBridge(initial);
    render(<App initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "打开视觉合同" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("open_ai_ppt_browser_review", {
      projectRoot: "/managed/project",
      reviewType: "visual",
      sourceVersion: "artifact://visual-contract/visual",
    }));
  });

  it("keeps project state unchanged when Browser open fails", async () => {
    const initial = compactWidgetData("blueprint");
    const { bridge, callTool } = hostBridge(initial);
    callTool.mockRejectedValueOnce(Object.assign(new Error("unavailable"), {
      code: "BROWSER_REVIEW_UNAVAILABLE",
    }));
    render(<App initialData={initial} bridge={bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "打开内容审阅" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Codex 内置 Browser 专业审阅暂未打开"));
    expect(callTool).toHaveBeenCalledOnce();
    expect(screen.getByText("revision 12")).toBeInTheDocument();
    expect(screen.queryByText("返回聊天")).not.toBeInTheDocument();
  });
});
