import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "../__fixtures__/content-sidebar-review.json";
import { ContentReviewDocument } from "../components/content-review/ContentReviewDocument";
import type { ContentReviewClient } from "../lib/content-review-client";
import type { HostBridge } from "../types";
import type { ContentFullDeckReviewProjection } from "../types/content-review";

afterEach(cleanup);

function setup(withTypedMaterial: boolean) {
  const projection = structuredClone(fixture) as ContentFullDeckReviewProjection;
  if (withTypedMaterial) {
    projection.slides[0].evidence_bindings[0].material_ref =
      "artifact://material/chongqing-electromechanical-v5";
  } else {
    delete projection.slides[0].evidence_bindings[0].material_ref;
  }
  const contentClient: ContentReviewClient = {
    load: vi.fn(async () => projection),
    saveDecision: vi.fn(),
    submitBatch: vi.fn(),
    openEvidenceBrowser: vi.fn(async (input) => ({
      status: "review-session-ready",
      opened: false,
      reviewType: "content-evidence",
      ...input,
      url: "http://127.0.0.1/scoped-evidence",
    })),
  };
  const bridge: HostBridge = {
    connect: vi.fn(async () => {}),
    callTool: vi.fn(),
    sendFollowUp: vi.fn(async () => {}),
    updateModelContext: vi.fn(async () => {}),
    confirmMission: vi.fn(),
    getHostEnvironment: vi.fn(),
    notifySize: vi.fn(),
  };
  render(
    <ContentReviewDocument
      projection={projection}
      projectRoot="/managed/project"
      bridge={bridge}
      client={contentClient}
      onProjectionChange={vi.fn()}
    />,
  );
  return { client: contentClient, projection };
}

describe("read-only content evidence Browser", () => {
  it("binds a typed material to the parent ReviewSession and keeps the unsaved page draft", async () => {
    const { client, projection } = setup(true);
    fireEvent.click(screen.getAllByRole("radio", { name: "需要修改" })[0]);
    fireEvent.change(screen.getAllByRole("textbox", { name: "审核意见" })[0], {
      target: { value: "保留这条未保存意见" },
    });

    fireEvent.click(screen.getByRole("button", { name: "放大查看原材料" }));

    expect(await screen.findByText("只读证据会话已准备，请在 Browser 打开。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "在 Browser 打开只读证据" })).toHaveAttribute(
      "href",
      "http://127.0.0.1/scoped-evidence",
    );
    expect(screen.queryByText("原材料已在只读 Browser 中打开。")).not.toBeInTheDocument();
    expect(client.openEvidenceBrowser).toHaveBeenCalledWith({
      projectRoot: "/managed/project",
      reviewSessionId: projection.review_session.review_session_id,
      sourceVersion: projection.source_version,
      slideId: "S01",
      evidenceId: "EV-S01-01",
      materialRef: "artifact://material/chongqing-electromechanical-v5",
    });
    expect(screen.getAllByRole("radio", { name: "需要修改" })[0]).toBeChecked();
    expect(screen.getAllByRole("textbox", { name: "审核意见" })[0]).toHaveValue("保留这条未保存意见");
  });

  it("never promotes a source ref into a material ref when the typed field is absent", () => {
    const { projection } = setup(false);
    expect(screen.queryByRole("button", { name: "放大查看原材料" })).not.toBeInTheDocument();
    expect(screen.getAllByText(/没有类型化 material_ref/)).toHaveLength(
      projection.slides.filter((slide) =>
        slide.evidence_bindings.some((binding) => !binding.material_ref),
      ).length,
    );
  });
});
