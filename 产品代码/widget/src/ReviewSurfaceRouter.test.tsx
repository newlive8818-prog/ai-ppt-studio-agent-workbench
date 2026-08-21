import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("content sidebar and visual Browser routing", () => {
  it("loads content through its sidebar projection rather than professional Browser", async () => {
    const initial = compactWidgetData("blueprint");
    const host = hostBridge(initial);
    host.callTool.mockResolvedValue({
      display_policy: "content-sidebar-progress",
      phase: "content-producing",
      project_id: "p1",
      revision: 12,
      mission_summary: {},
      next_action: "continue-content-production",
    });
    render(<App initialData={initial} bridge={host.bridge} />);

    await waitFor(() => expect(host.callTool).toHaveBeenCalledWith(
      "get_content_sidebar_review_projection",
      { projectRoot: "/managed/project" },
    ));
    expect(host.callTool).not.toHaveBeenCalledWith(
      "open_ai_ppt_browser_review",
      expect.anything(),
    );
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

  it("keeps the current snapshot when the content projection cannot load", async () => {
    const initial = compactWidgetData("blueprint");
    const host = hostBridge(initial);
    host.callTool.mockRejectedValue(Object.assign(new Error("unavailable"), {
      code: "CONTENT_REVIEW_CONFLICT",
    }));
    render(<App initialData={initial} bridge={host.bridge} />);

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("内容审核数据未能加载"));
    expect(host.callTool).toHaveBeenCalledOnce();
    expect(screen.getByText("revision 12")).toBeInTheDocument();
  });
});
