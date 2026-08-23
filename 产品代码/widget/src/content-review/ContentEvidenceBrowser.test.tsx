import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "../__fixtures__/content-sidebar-review.json";
import { ContentReviewDocument } from "../components/content-review/ContentReviewDocument";
import { createContentReviewClient } from "../lib/content-review-client";
import type { ContentFullDeckProjection, HostBridge } from "../types";
import { parseToolOutput, type ToolContractMap } from "../types/tool-contracts";

afterEach(cleanup);

function setup() {
  const calls: Array<{ name: string; args: Record<string, unknown> }> = [];
  const bridge: HostBridge = {
    connect: vi.fn(async () => {}),
    callTool: vi.fn(async <K extends keyof ToolContractMap>(
      name: K,
      args: ToolContractMap[K]["input"],
    ) => {
      calls.push({ name, args: args as unknown as Record<string, unknown> });
      if (name === "open_content_evidence_browser") {
        return parseToolOutput(name, {
          opened: true,
          reviewType: "content-evidence",
          ...args,
        });
      }
      if (name === "read_ai_ppt_project_asset") {
        throw new Error("asset preview is not needed for this interaction test");
      }
      throw new Error(`unexpected tool ${name}`);
    }),
    sendFollowUp: vi.fn(async () => {}),
    updateModelContext: vi.fn(async () => {}),
    confirmMission: vi.fn(async () => ({
      artifact_ref: "artifact://mission-confirmation/not-used",
      snapshot: {} as never,
    })),
    getHostEnvironment: vi.fn(),
    notifySize: vi.fn(),
  };
  const projection = structuredClone(fixture) as ContentFullDeckProjection;
  render(
    <ContentReviewDocument
      projection={projection}
      projectRoot="/managed/project"
      bridge={bridge}
      client={createContentReviewClient(bridge)}
      onProjectionChange={vi.fn()}
      onSnapshotChange={vi.fn()}
    />,
  );
  return { calls };
}

describe("read-only content evidence Browser", () => {
  it("opens only the exact slide/material and keeps the unsaved page draft", async () => {
    const { calls } = setup();
    fireEvent.click(screen.getAllByRole("radio", { name: "需要修改" })[0]);
    fireEvent.change(screen.getAllByRole("textbox", { name: "审核意见" })[0], {
      target: { value: "保留这条未保存意见" },
    });

    fireEvent.click(screen.getByRole("button", { name: "放大查看原材料" }));

    expect(await screen.findByText("原材料已在只读 Browser 中打开。" )).toBeInTheDocument();
    expect(calls.at(-1)).toEqual({
      name: "open_content_evidence_browser",
      args: {
        projectRoot: "/managed/project",
        sourceVersion: fixture.source_version,
        slideId: "S01",
        evidenceId: "EV-S01-01",
        materialRef: "artifact://material/chongqing-electromechanical-v5",
      },
    });
    expect(screen.getAllByRole("radio", { name: "需要修改" })[0]).toBeChecked();
    expect(screen.getAllByRole("textbox", { name: "审核意见" })[0]).toHaveValue("保留这条未保存意见");
  });

  it("does not offer a Browser action for an evidence gap without a real asset", () => {
    setup();
    expect(screen.getAllByRole("button", { name: "放大查看原材料" })).toHaveLength(1);
    expect(screen.getByText("明确证据缺口")).toBeInTheDocument();
  });
});
