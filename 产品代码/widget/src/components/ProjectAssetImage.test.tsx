import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach } from "vitest";
import { describe, expect, it, vi } from "vitest";

import type { HostBridge } from "../types/host";
import { ProjectAssetImage } from "./ProjectAssetImage";

afterEach(cleanup);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

describe("ProjectAssetImage", () => {
  it("shows an honest unavailable state instead of loading forever when no asset is registered", () => {
    const callTool = vi.fn();
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    render(<ProjectAssetImage bridge={bridge} projectRoot="/managed" assetRef="" alt="S01 锚点页成果" />);
    expect(screen.getByText("预览未登记")).toBeInTheDocument();
    expect(callTool).not.toHaveBeenCalled();
  });

  it("limits concurrent project asset reads to four", async () => {
    const requests: Array<ReturnType<typeof deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>>> = [];
    const callTool = vi.fn((_name: string, args: Record<string, unknown>) => {
      const request = deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>();
      requests.push(request);
      return request.promise.then((result) => ({
        asset: { ...result.asset, assetRef: String(args.assetRef) },
      }));
    });
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    render(<>{Array.from({ length: 6 }, (_, index) => (
      <ProjectAssetImage
        key={index}
        bridge={bridge}
        projectRoot="/managed"
        assetRef={`asset-${index + 1}`}
        alt={`材料 ${index + 1}`}
      />
    ))}</>);

    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(4));
    await act(async () => {
      requests[0].resolve({ asset: { assetRef: "asset-1", mimeType: "image/png", dataBase64: "MQ==" } });
      await requests[0].promise;
    });
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(5));
    await act(async () => {
      requests[1].resolve({ asset: { assetRef: "asset-2", mimeType: "image/png", dataBase64: "Mg==" } });
      await requests[1].promise;
    });
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(6));
    await act(async () => {
      for (let index = 2; index < requests.length; index += 1) {
        requests[index].resolve({ asset: { assetRef: `asset-${index + 1}`, mimeType: "image/png", dataBase64: "Mw==" } });
      }
      await Promise.all(requests.slice(2).map((request) => request.promise));
    });
  });

  it("cancels queued reads when their final consumers unmount", async () => {
    const blockers = Array.from({ length: 4 }, () => (
      deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>()
    ));
    const callTool = vi.fn((_name: string, args: Record<string, unknown>) => {
      const callIndex = callTool.mock.calls.length - 1;
      if (callIndex < blockers.length) return blockers[callIndex].promise;
      return Promise.resolve({
        asset: { assetRef: String(args.assetRef), mimeType: "image/png", dataBase64: "Ng==" },
      });
    });
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    const view = render(<>{Array.from({ length: 6 }, (_, index) => (
      <ProjectAssetImage
        key={index}
        bridge={bridge}
        projectRoot="/managed"
        assetRef={`cancel-${index + 1}`}
        alt={`取消材料 ${index + 1}`}
      />
    ))}</>);

    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(4));
    view.unmount();
    await act(async () => {
      blockers.forEach((request, index) => request.resolve({
        asset: { assetRef: `cancel-${index + 1}`, mimeType: "image/png", dataBase64: "Nw==" },
      }));
      await Promise.all(blockers.map((request) => request.promise));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(callTool).toHaveBeenCalledTimes(4);
  });

  it("starts a queued shared read while one consumer remains mounted", async () => {
    const blockers = Array.from({ length: 4 }, () => (
      deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>()
    ));
    const shared = deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>();
    const callTool = vi.fn((_name: string, args: Record<string, unknown>) => {
      const assetRef = String(args.assetRef);
      if (assetRef === "queued-shared") return shared.promise;
      return blockers[Number(assetRef.slice(-1)) - 1].promise;
    });
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    const blockerView = render(<>{blockers.map((_request, index) => (
      <ProjectAssetImage
        key={index}
        bridge={bridge}
        projectRoot="/managed"
        assetRef={`blocker-${index + 1}`}
        alt={`阻塞材料 ${index + 1}`}
      />
    ))}</>);
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(4));
    const firstConsumer = render(
      <ProjectAssetImage bridge={bridge} projectRoot="/managed" assetRef="queued-shared" alt="共享材料一" />,
    );
    const secondConsumer = render(
      <ProjectAssetImage bridge={bridge} projectRoot="/managed" assetRef="queued-shared" alt="共享材料二" />,
    );
    firstConsumer.unmount();

    await act(async () => {
      blockers[0].resolve({ asset: { assetRef: "blocker-1", mimeType: "image/png", dataBase64: "OA==" } });
      await blockers[0].promise;
    });
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(5));
    expect(callTool).toHaveBeenLastCalledWith("read_ai_ppt_project_asset", {
      projectRoot: "/managed",
      assetRef: "queued-shared",
    });

    await act(async () => {
      shared.resolve({ asset: { assetRef: "queued-shared", mimeType: "image/png", dataBase64: "OQ==" } });
      blockers.slice(1).forEach((request, index) => request.resolve({
        asset: { assetRef: `blocker-${index + 2}`, mimeType: "image/png", dataBase64: "MTA=" },
      }));
      await Promise.all([shared.promise, ...blockers.slice(1).map((request) => request.promise)]);
    });
    expect(await secondConsumer.findByRole("img", { name: "共享材料二" })).toBeInTheDocument();
    blockerView.unmount();
    secondConsumer.unmount();
  });

  it("scopes the four-read scheduler independently per bridge", async () => {
    const blockers = Array.from({ length: 4 }, () => (
      deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>()
    ));
    const firstCallTool = vi.fn((_name: string, args: Record<string, unknown>) => (
      blockers[Number(String(args.assetRef).slice(-1)) - 1].promise
    ));
    const secondCallTool = vi.fn(async (_name: string, args: Record<string, unknown>) => ({
      asset: { assetRef: String(args.assetRef), mimeType: "image/png", dataBase64: "MTE=" },
    }));
    const firstBridge = { connect: vi.fn(), callTool: firstCallTool } as unknown as HostBridge;
    const secondBridge = { connect: vi.fn(), callTool: secondCallTool } as unknown as HostBridge;
    const firstView = render(<>{blockers.map((_request, index) => (
      <ProjectAssetImage
        key={index}
        bridge={firstBridge}
        projectRoot="/managed-a"
        assetRef={`bridge-a-${index + 1}`}
        alt={`桥 A 材料 ${index + 1}`}
      />
    ))}</>);
    await waitFor(() => expect(firstCallTool).toHaveBeenCalledTimes(4));

    const secondView = render(
      <ProjectAssetImage bridge={secondBridge} projectRoot="/managed-b" assetRef="bridge-b-1" alt="桥 B 材料" />,
    );
    expect(await secondView.findByRole("img", { name: "桥 B 材料" })).toBeInTheDocument();
    expect(secondCallTool).toHaveBeenCalledTimes(1);

    await act(async () => {
      blockers.forEach((request, index) => request.resolve({
        asset: { assetRef: `bridge-a-${index + 1}`, mimeType: "image/png", dataBase64: "MTI=" },
      }));
      await Promise.all(blockers.map((request) => request.promise));
    });
    firstView.unmount();
    secondView.unmount();
  });

  it("retries a failed read instead of caching the error", async () => {
    let attempt = 0;
    const callTool = vi.fn(async () => {
      attempt += 1;
      if (attempt === 1) throw new Error("temporary read failure");
      return { asset: { assetRef: "asset-retry", mimeType: "image/png", dataBase64: "NA==" } };
    });
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    render(<ProjectAssetImage bridge={bridge} projectRoot="/managed" assetRef="asset-retry" alt="可重试材料" />);

    fireEvent.click(await screen.findByRole("button", { name: /预览暂不可读，点击重试/ }));
    expect(await screen.findByRole("img", { name: "可重试材料" })).toBeInTheDocument();
    expect(callTool).toHaveBeenCalledTimes(2);
  });

  it("does not publish a completed asset after unmount", async () => {
    const request = deferred<{ asset: { assetRef: string; mimeType: string; dataBase64: string } }>();
    const callTool = vi.fn(() => request.promise);
    const bridge = { connect: vi.fn(), callTool } as unknown as HostBridge;
    const { unmount } = render(<ProjectAssetImage bridge={bridge} projectRoot="/managed" assetRef="asset-late" alt="已卸载材料" />);
    unmount();

    await act(async () => {
      request.resolve({ asset: { assetRef: "asset-late", mimeType: "image/png", dataBase64: "NQ==" } });
      await request.promise;
    });
    expect(screen.queryByRole("img", { name: "已卸载材料" })).not.toBeInTheDocument();
  });

  it("stops placeholder and retry pointer gestures from reaching an annotation parent", async () => {
    const onPointerDown = vi.fn();
    const missingBridge = { connect: vi.fn(), callTool: vi.fn() } as unknown as HostBridge;
    const missing = render(
      <div onPointerDown={onPointerDown}>
        <ProjectAssetImage bridge={missingBridge} projectRoot="/managed" assetRef="" alt="未登记材料" />
      </div>,
    );
    fireEvent.pointerDown(screen.getByText("预览未登记"));
    expect(onPointerDown).not.toHaveBeenCalled();
    missing.unmount();

    const failedBridge = {
      connect: vi.fn(),
      callTool: vi.fn(async () => { throw new Error("read failed"); }),
    } as unknown as HostBridge;
    render(
      <div onPointerDown={onPointerDown}>
        <ProjectAssetImage bridge={failedBridge} projectRoot="/managed" assetRef="failed" alt="失败材料" />
      </div>,
    );
    fireEvent.pointerDown(await screen.findByRole("button", { name: /预览暂不可读，点击重试/ }));
    expect(onPointerDown).not.toHaveBeenCalled();
  });
});
