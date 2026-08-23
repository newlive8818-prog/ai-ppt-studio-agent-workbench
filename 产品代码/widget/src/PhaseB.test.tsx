import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("v1.6 schema 3 compact content projection", () => {
  it("shows content progress and returns the content review action to Codex", async () => {
    const initial = compactWidgetData("blueprint");
    const { bridge, callTool } = hostBridge(initial);
    render(<App initialData={initial} bridge={bridge} />);

    expect(screen.getByRole("heading", { name: "内容蓝图已通过内部审查" })).toBeInTheDocument();
    expect(screen.getByText("12 页内容已形成")).toBeInTheDocument();
    expect(screen.getByText("已判断 2 页")).toBeInTheDocument();
    expect(screen.getByText("剩余 10 页")).toBeInTheDocument();
    expect(screen.queryByText("确认内容蓝图并通过 G0")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "审核完整内容" }));
    await waitFor(() => expect(bridge.sendFollowUp).toHaveBeenCalledWith(
      "继续 AI PPT 项目：先证明运营断点，再给出低风险建设路径。",
    ));
    expect(callTool).not.toHaveBeenCalledWith("open_ai_ppt_browser_review", expect.anything());
  });
});
