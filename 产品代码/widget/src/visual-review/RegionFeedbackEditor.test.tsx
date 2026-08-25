import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AnchorFeedbackComposerState,
  AnchorFeedbackDraftState,
} from "../review-draft/reviewDraftStore";
import type { HostBridge } from "../types/host";
import { RegionFeedbackEditor } from "./RegionFeedbackEditor";

class TestPointerEvent extends MouseEvent {
  pointerId: number;
  isPrimary: boolean;
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
    this.isPrimary = init.isPrimary ?? true;
  }
}

beforeEach(() => {
  Object.defineProperty(window, "PointerEvent", { configurable: true, value: TestPointerEvent });
});

afterEach(() => {
  cleanup();
  Reflect.deleteProperty(window, "PointerEvent");
});

function bridge(): HostBridge {
  return {
    callTool: vi.fn(async () => ({
      asset: { assetRef: "anchor.png", mimeType: "image/png", bytes: 1, dataBase64: "AA==" },
    })),
  } as unknown as HostBridge;
}

function Harness() {
  const [host] = useState(bridge);
  const [drafts, setDrafts] = useState<AnchorFeedbackDraftState[]>([]);
  const [composer, setComposer] = useState<AnchorFeedbackComposerState | null>(null);
  return (
    <>
      <RegionFeedbackEditor
        bridge={host}
        projectRoot="/managed/project"
        slideId="S01"
        assetRef="anchor.png"
        drafts={drafts}
        composer={composer}
        disabled={false}
        onSliceChange={(nextDrafts, nextComposer) => {
          setDrafts(nextDrafts);
          setComposer(nextComposer);
        }}
      />
      <output data-testid="draft-count">{drafts.length}</output>
    </>
  );
}

describe("07 anchor rectangle feedback", () => {
  it("turns pointer drags into normalized numbered regions and multiple batch items", async () => {
    const { container } = render(<Harness />);
    const image = await waitFor(() => {
      const node = container.querySelector("img");
      expect(node).not.toBeNull();
      return node as HTMLImageElement;
    });
    fireEvent.load(image);

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    const canvas = screen.getByTestId("anchor-canvas");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      x: 10,
      y: 20,
      left: 10,
      top: 20,
      right: 1010,
      bottom: 520,
      width: 1000,
      height: 500,
      toJSON: () => ({}),
    });
    fireEvent.pointerDown(canvas, { pointerId: 7, button: 0, isPrimary: true, clientX: 110, clientY: 70 });
    fireEvent.pointerMove(canvas, { pointerId: 7, isPrimary: true, clientX: 510, clientY: 270 });
    fireEvent.pointerUp(canvas, { pointerId: 7, isPrimary: true, clientX: 510, clientY: 270 });

    const candidate = container.querySelector(".anchor-region.candidate") as HTMLElement;
    expect(candidate).not.toBeNull();
    expect(candidate).toHaveStyle({ left: "10%", top: "10%", width: "40%", height: "40%" });
    fireEvent.change(screen.getByRole("textbox", { name: "当前框选区域反馈" }), {
      target: { value: "降低底部信息的视觉权重。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "加入本轮反馈" }));

    expect(screen.getByTestId("draft-count")).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: "S01 已标注区域 1" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "开始标注" }));
    fireEvent.pointerDown(canvas, { pointerId: 8, button: 0, isPrimary: true, clientX: 610, clientY: 120 });
    fireEvent.pointerMove(canvas, { pointerId: 8, isPrimary: true, clientX: 910, clientY: 320 });
    fireEvent.pointerUp(canvas, { pointerId: 8, isPrimary: true, clientX: 910, clientY: 320 });
    fireEvent.change(screen.getByRole("textbox", { name: "当前框选区域反馈" }), {
      target: { value: "第二条反馈独立保留。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "加入本轮反馈" }));

    expect(screen.getByTestId("draft-count")).toHaveTextContent("2");
    expect(screen.getByRole("button", { name: "S01 已标注区域 2" })).toBeInTheDocument();
  });
});
