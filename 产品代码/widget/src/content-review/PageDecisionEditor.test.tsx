import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PageDecisionEditor } from "../components/content-review/PageDecisionEditor";
import type { ContentDecisionState } from "../types";

afterEach(cleanup);

const emptyState: ContentDecisionState = {
  selected: "",
  comment: "",
  completed: false,
  saved: false,
  frozen: false,
};

function renderEditor(onSave = vi.fn(async () => undefined), state = emptyState) {
  const onMetaChange = vi.fn();
  render(
    <PageDecisionEditor
      slideId="S01"
      savedState={state}
      onSave={onSave}
      onMetaChange={onMetaChange}
    />,
  );
  return { onSave, onMetaChange };
}

describe("page decision editor", () => {
  it("offers exactly four mutually exclusive decisions and saves approved without a comment", async () => {
    const { onSave } = renderEditor();
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(4);
    expect(screen.getByRole("radio", { name: "认可本页" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "需要修改" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "证据不足" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "考虑删页/合页" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "认可本页" }));
    expect(screen.queryByLabelText("审核意见")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith("S01", "approved", ""));
  });

  it.each([
    ["需要修改", "modify"],
    ["证据不足", "evidence"],
    ["考虑删页/合页", "merge-or-delete"],
  ])("requires an inline comment for %s", async (label, decision) => {
    const { onSave } = renderEditor();
    fireEvent.click(screen.getByRole("radio", { name: label }));
    const textarea = screen.getByLabelText("审核意见");
    expect(textarea).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    expect(await screen.findByText("请输入具体意见后再保存。")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();

    fireEvent.change(textarea, { target: { value: "请补充来源页和使用范围" } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith("S01", decision, "请补充来源页和使用范围"));
  });

  it("counts Unicode code points and rejects 1201 without losing the draft", async () => {
    const { onSave } = renderEditor();
    fireEvent.click(screen.getByRole("radio", { name: "需要修改" }));
    const textarea = screen.getByLabelText("审核意见");
    const value = "😀".repeat(1201);
    fireEvent.change(textarea, { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));
    expect(await screen.findByText("意见最多 1200 个字符。")).toBeInTheDocument();
    expect(textarea).toHaveValue(value);
    expect(onSave).not.toHaveBeenCalled();
  });

  it.each(["CONTENT_REVIEW_SAVE_FAILED", "REVISION_CONFLICT", "CONTENT_REVIEW_CONFLICT"])(
    "retains selection and comment after %s",
    async (code) => {
      const onSave = vi.fn(async () => {
        const error = new Error("save failed") as Error & { code?: string };
        error.code = code;
        throw error;
      });
      renderEditor(onSave);
      fireEvent.click(screen.getByRole("radio", { name: "考虑删页/合页" }));
      const textarea = screen.getByLabelText("审核意见");
      fireEvent.change(textarea, { target: { value: "与下一页合并，保留证据边界" } });
      fireEvent.click(screen.getByRole("button", { name: "保存本页判断" }));

      expect(await screen.findByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: "考虑删页/合页" })).toBeChecked();
      expect(textarea).toHaveValue("与下一页合并，保留证据边界");
      expect(screen.getByRole("button", { name: "保存本页判断" })).toBeEnabled();
    },
  );

  it("shows the complete saved comment and supports editing it", () => {
    renderEditor(vi.fn(async () => undefined), {
      selected: "modify",
      comment: "这是已保存的完整修改意见",
      completed: true,
      saved: true,
      frozen: false,
    });
    expect(screen.getByText("这是已保存的完整修改意见")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "编辑意见" }));
    expect(screen.getByLabelText("审核意见")).toHaveValue("这是已保存的完整修改意见");
  });
});
