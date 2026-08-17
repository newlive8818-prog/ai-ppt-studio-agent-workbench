import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ContentFullDeckReviewPage } from "./ContentFullDeckReviewPage";
import type { HostBridge } from "../types/host";
import type { ContentReviewSurfaceData } from "../types/content-review";

afterEach(cleanup);

it("keeps all 60 slides in the continuous document", () => {
  const slides = Array.from({ length: 60 }, (_, index) => ({
    slide_id: `S${index + 1}`,
    order: index + 1,
    section_id: "section",
    page_task: `任务 ${index + 1}`,
    reading_question: `问题 ${index + 1}`,
    neutral_title: `中立标题 ${index + 1}`,
    visible_copy_blocks: [{ block_id: `b${index}`, text: `完整正文 ${index + 1}`, identity: "来源事实" }],
    identity_labels: ["来源事实"], evidence_bindings: [], analysis_or_proposal_blocks: [],
    material_views: [],
    solution_mapping_refs: [`m${index}`], previous_relation: "上一页", next_relation: "下一页",
    speaker_notes: `备注 ${index + 1}`,
    reading_quality: { independently_readable: true, information_density: "moderate", review_note: "可读" },
    material_mode: "proposal-led" as const,
  }));
  const data = {
    surface: "review", selectedProjectRoot: "/managed", snapshotRevision: 1,
    review: {
      project_id: "p", review_type: "content-full-deck", review_session_id: "s", review_session: {},
      source_version: "v", revision: 1, authoritative_revision: 1,
      reading_blueprint_ref: "artifact://reading-deck-blueprint/" + "a".repeat(64),
      material_mode: "proposal-led", section_flow: ["section"], slides, decisions: [],
      progress: { completed: 0, total: 60, remaining: 60, unsaved: 0 }, batch: null,
      revision_plan: null, content_acceptance_ref: "artifact://content-acceptance/" + "b".repeat(64),
    },
  } as ContentReviewSurfaceData;
  const bridge = {
    callTool: vi.fn(), connect: vi.fn(), updateModelContext: vi.fn(), sendFollowUp: vi.fn(),
    confirmMission: vi.fn(), getHostEnvironment: vi.fn(), notifySize: vi.fn(),
  } as unknown as HostBridge;
  const { container } = render(<ContentFullDeckReviewPage initialData={data} bridge={bridge} />);
  expect(screen.getByRole("heading", { name: "中立标题 60" })).toBeInTheDocument();
  expect(container.querySelectorAll("[data-content-slide]")).toHaveLength(60);
  expect(container.textContent).not.toContain("...");
  expect(screen.getAllByText("本页为 proposal-led 内容，没有可展示的项目材料画面。")).toHaveLength(60);
  expect(bridge.callTool).not.toHaveBeenCalled();
});
