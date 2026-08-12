import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { compactWidgetData, hostBridge } from "./test-fixtures";

afterEach(cleanup);

describe("v1.6 schema 3 compact visual projection", () => {
  it("projects G1/G2 status without visual direction or user gate controls", async () => {
    const initial = compactWidgetData("visual");
    const { bridge, callTool } = hostBridge(initial);
    render(<App initialData={initial} bridge={bridge} />);

    expect(screen.getByRole("heading", { name: "整套视觉合同已通过 G1 / G2" })).toBeInTheDocument();
    expect(screen.getByText("可信的经营证据链。")).toBeInTheDocument();
    expect(screen.queryByText(/Image 2 视觉构想/)).not.toBeInTheDocument();
    expect(screen.queryByText(/G1.*确认|G2.*确认|保存方向/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "打开视觉合同" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("open_ai_ppt_browser_review", {
      projectRoot: "/managed/project",
      reviewType: "visual",
      sourceVersion: "artifact://visual-contract/visual",
    }));
  });
});
