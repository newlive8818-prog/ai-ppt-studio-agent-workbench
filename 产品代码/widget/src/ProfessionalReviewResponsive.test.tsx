import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { hostBridge, reviewWidgetData } from "./test-fixtures";

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("one professional review application at 760/1000/1440", () => {
  it("keeps one 64px header contract and all persistent review controls", () => {
    const initial = reviewWidgetData("content");
    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />,
    );

    expect(container.querySelectorAll('[data-review-header-line="64"]')).toHaveLength(1);
    expect(screen.getByRole("button", { name: "内容审阅" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "视觉合同" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "目录" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "标记 0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存标记" })).toBeInTheDocument();
  });

  it("moves focus into mutually exclusive drawers and returns it on Escape", async () => {
    const initial = reviewWidgetData("content");
    render(<ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />);
    const outlineTrigger = screen.getByRole("button", { name: "目录" });
    const marksTrigger = screen.getByRole("button", { name: "标记 0" });

    outlineTrigger.focus();
    fireEvent.click(outlineTrigger);
    const outline = screen.getByRole("dialog", { name: "审阅目录" });
    await waitFor(() => expect(outline).toContainElement(document.activeElement as HTMLElement));

    fireEvent.click(marksTrigger);
    expect(screen.queryByRole("dialog", { name: "审阅目录" })).not.toBeInTheDocument();
    const marks = screen.getByRole("dialog", { name: "审阅标记" });
    await waitFor(() => expect(marks).toContainElement(document.activeElement as HTMLElement));

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(marksTrigger));
  });

  it("closes on backdrop and outline navigation focuses the stable anchor", async () => {
    const initial = reviewWidgetData("content");
    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />,
    );
    const outlineTrigger = screen.getByRole("button", { name: "目录" });
    fireEvent.click(outlineTrigger);
    fireEvent.click(screen.getByRole("button", { name: /S01.*第 1 页/ }));
    await waitFor(() => expect(document.activeElement).toBe(container.querySelector("#slide-s01")));
    expect(screen.queryByRole("dialog", { name: "审阅目录" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "标记 0" }));
    fireEvent.click(container.querySelector(".review-drawer-backdrop.open") as HTMLElement);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "标记 0" })));
  });

  it("marks drawers as modal overlays without adding forbidden permanent UI", () => {
    const initial = reviewWidgetData("visual");
    const { container } = render(
      <ProfessionalReviewApp initialData={initial} bridge={hostBridge(initial).bridge} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "目录" }));
    expect(screen.getByRole("dialog", { name: "审阅目录" })).toHaveAttribute("aria-modal", "true");
    expect(container).not.toHaveTextContent("拖动加宽");
    expect(container).not.toHaveTextContent("返回聊天");
    expect(container).not.toHaveTextContent("版本历史");
  });
});
