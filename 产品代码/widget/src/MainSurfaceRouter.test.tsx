import { act, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
  window.history.replaceState(null, "", "/");
});

it("leaves initial loading for a recoverable terminal state when Browser connection times out", async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="root"></div>';
  window.history.replaceState(null, "", "/#token=short-lived-token");
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => (
    new Promise<Response>((_resolve, reject) => {
      (init?.signal as AbortSignal | undefined)?.addEventListener("abort", () => {
        reject(new DOMException("aborted", "AbortError"));
      });
    })
  ));

  await import("./main");
  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByText("正在同步同一 project revision…")).toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10_000);
  });

  expect(screen.getByText("无法连接专业审核会话，项目数据未被修改。")).toBeInTheDocument();
  expect(screen.queryByText("正在同步同一 project revision…")).not.toBeInTheDocument();
});
