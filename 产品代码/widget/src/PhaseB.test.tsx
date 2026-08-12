import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("v1.6 schema 3 compact content projection", () => {
  it("shows only content status and opens the professional review", async () => {
    const initial = compactWidgetData("blueprint");
    const { bridge, callTool } = hostBridge(initial);
    render(<App initialData={initial} bridge={bridge} />);

    expect(screen.getByRole("heading", { name: "内容蓝图已通过内部审查" })).toBeInTheDocument();
    expect(screen.getByText("12 页内容已形成")).toBeInTheDocument();
    expect(screen.getByText("已保存 2 条标记")).toBeInTheDocument();
    expect(screen.queryByText("确认内容蓝图并通过 G0")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "打开内容审阅" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("open_ai_ppt_browser_review", {
      projectRoot: "/managed/project",
      reviewType: "content",
      sourceVersion: "artifact://content-blueprint/content",
    }));
  });
});
