import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("content conversation and visual Browser routing", () => {
  it("keeps content review out of the professional Browser route", async () => {
    const initial = compactWidgetData("blueprint");
    const host = hostBridge(initial);
    render(<App initialData={initial} bridge={host.bridge} />);

    fireEvent.click(screen.getByRole("button", { name: "审核完整内容" }));
    await waitFor(() => expect(host.bridge.sendFollowUp).toHaveBeenCalledWith(
      "继续 AI PPT 项目：先证明运营断点，再给出低风险建设路径。",
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

});
