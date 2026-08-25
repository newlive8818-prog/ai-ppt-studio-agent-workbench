import { ImageOff, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import type { HostBridge } from "../types/host";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  assetRef: string;
  alt: string;
  className?: string;
  onReady?: () => void;
  onUnavailable?: () => void;
}

interface AssetPayload {
  assetRef: string;
  mimeType: string;
  dataBase64: string;
}

const maximumConcurrentReads = 4;
interface AssetReadJob {
  key: string;
  interests: number;
  started: boolean;
  settled: boolean;
  read: () => Promise<AssetPayload>;
  promise: Promise<AssetPayload>;
  resolve: (asset: AssetPayload) => void;
  reject: (reason: unknown) => void;
}

interface BridgeReadState {
  activeReads: number;
  pendingReads: AssetReadJob[];
  inFlight: Map<string, AssetReadJob>;
}

interface AssetReadSubscription {
  promise: Promise<AssetPayload>;
  release: () => void;
}

const readsByBridge = new WeakMap<HostBridge, BridgeReadState>();

function bridgeReadState(bridge: HostBridge): BridgeReadState {
  let state = readsByBridge.get(bridge);
  if (!state) {
    state = { activeReads: 0, pendingReads: [], inFlight: new Map() };
    readsByBridge.set(bridge, state);
  }
  return state;
}

function removeInFlight(state: BridgeReadState, job: AssetReadJob) {
  if (state.inFlight.get(job.key) === job) state.inFlight.delete(job.key);
}

function rejectCancelledJob(state: BridgeReadState, job: AssetReadJob) {
  if (job.started || job.settled || job.interests > 0) return;
  job.settled = true;
  removeInFlight(state, job);
  job.reject(new Error("Project asset read cancelled before dispatch"));
}

function dispatchPendingReads(state: BridgeReadState) {
  while (state.activeReads < maximumConcurrentReads && state.pendingReads.length) {
    const job = state.pendingReads.shift();
    if (!job || job.settled) continue;
    if (job.interests === 0) {
      rejectCancelledJob(state, job);
      continue;
    }
    job.started = true;
    state.activeReads += 1;
    Promise.resolve().then(job.read).then(job.resolve, job.reject).finally(() => {
      job.settled = true;
      state.activeReads -= 1;
      removeInFlight(state, job);
      dispatchPendingReads(state);
    });
  }
}

function subscribeProjectAsset(bridge: HostBridge, projectRoot: string, assetRef: string): AssetReadSubscription {
  const state = bridgeReadState(bridge);
  const key = `${projectRoot}\u0000${assetRef}`;
  let job = state.inFlight.get(key);
  if (!job) {
    let resolve!: (asset: AssetPayload) => void;
    let reject!: (reason: unknown) => void;
    const promise = new Promise<AssetPayload>((onResolve, onReject) => {
      resolve = onResolve;
      reject = onReject;
    });
    job = {
      key,
      interests: 0,
      started: false,
      settled: false,
      read: async () => {
        const result = await bridge.callTool("read_ai_ppt_project_asset", { projectRoot, assetRef });
        return result.asset;
      },
      promise,
      resolve,
      reject,
    };
    state.inFlight.set(key, job);
    state.pendingReads.push(job);
  }
  job.interests += 1;
  dispatchPendingReads(state);
  let released = false;
  return {
    promise: job.promise,
    release: () => {
      if (released) return;
      released = true;
      job!.interests = Math.max(0, job!.interests - 1);
      if (!job!.started && job!.interests === 0) {
        const index = state.pendingReads.indexOf(job!);
        if (index >= 0) state.pendingReads.splice(index, 1);
        rejectCancelledJob(state, job!);
      }
    },
  };
}

export function ProjectAssetImage({
  bridge,
  projectRoot,
  assetRef,
  alt,
  className = "",
  onReady,
  onUnavailable,
}: Props) {
  const [source, setSource] = useState("");
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setSource("");
    setFailed(false);
    if (!assetRef) {
      onUnavailable?.();
      return () => { active = false; };
    }
    const subscription = subscribeProjectAsset(bridge, projectRoot, assetRef);
    subscription.promise.then((asset) => {
      if (active) setSource(`data:${asset.mimeType};base64,${asset.dataBase64}`);
    }).catch(() => {
      if (active) {
        setFailed(true);
        onUnavailable?.();
      }
    });
    return () => {
      active = false;
      subscription.release();
    };
  }, [assetRef, attempt, bridge, onUnavailable, projectRoot]);

  if (!assetRef) return <div className={`asset-placeholder ${className}`} onPointerDown={(event) => event.stopPropagation()}><ImageOff size={20} /><span>预览未登记</span></div>;
  if (failed) return <button type="button" className={`asset-placeholder ${className}`} onPointerDown={(event) => event.stopPropagation()} onClick={() => setAttempt((current) => current + 1)}><ImageOff size={20} /><span>预览暂不可读，点击重试</span></button>;
  if (!source) return <div className={`asset-placeholder ${className}`} onPointerDown={(event) => event.stopPropagation()}><LoaderCircle size={20} /><span>读取项目预览</span></div>;
  return (
    <img
      className={className}
      src={source}
      alt={alt}
      loading="lazy"
      onLoad={onReady}
      onError={() => {
        setFailed(true);
        onUnavailable?.();
      }}
    />
  );
}
