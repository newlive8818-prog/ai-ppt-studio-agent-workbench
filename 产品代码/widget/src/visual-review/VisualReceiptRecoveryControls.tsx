import { useEffect, useRef, useState } from "react";

import type { HostBridge } from "../types/host";
import {
  isReviewWriteTimeout,
  withReviewWriteDeadline,
} from "./review-write-deadline";

type HostStatus = "not-requested" | "pending" | "sent" | "failed" | "unavailable";
type AiStatus = "pending" | "received" | "rejected" | "unverified";
type Capability = "available" | "unavailable" | "unknown";

interface Props {
  bridge: HostBridge;
  commandIdentity: string;
  projectRoot: string;
  reviewSessionId: string;
  sourceVersion: string;
  revision: number;
  savedArtifactRef: string | null;
  hostStatus: HostStatus;
  aiStatus: AiStatus;
  hostCapability: Capability;
  aiCapability: Capability;
  onHostSent: (revision: number) => void;
  onAiReceived: (revision: number) => void;
}

function isSafeSuccessor(value: unknown, revision: number): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && value >= 0
    && value < Number.MAX_SAFE_INTEGER
    && value === revision + 1;
}

function unavailableLabel(capability: Capability, hasAdapter: boolean) {
  if (!hasAdapter || capability === "unavailable") return "不可用";
  return capability === "unknown" ? "待验证" : "可用";
}

export function VisualReceiptRecoveryControls({
  bridge,
  commandIdentity,
  projectRoot,
  reviewSessionId,
  sourceVersion,
  revision,
  savedArtifactRef,
  hostStatus,
  aiStatus,
  hostCapability,
  aiCapability,
  onHostSent,
  onAiReceived,
}: Props) {
  const [pending, setPending] = useState<"host" | "ai" | null>(null);
  const [message, setMessage] = useState("");
  const generation = useRef(0);
  const mounted = useRef(true);
  const scopeRef = useRef({ commandIdentity, revision, savedArtifactRef });
  scopeRef.current = { commandIdentity, revision, savedArtifactRef };

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    generation.current += 1;
    setPending(null);
    setMessage("");
  }, [commandIdentity, revision, savedArtifactRef]);

  if (!savedArtifactRef) return null;

  const hostAdapter = bridge.retryVisualHostNotification;
  const aiAdapter = bridge.verifyVisualAiReceipt;
  const hostAvailable = hostCapability === "available" && typeof hostAdapter === "function";
  const aiAvailable = aiCapability === "available" && typeof aiAdapter === "function";
  const hostRetryEligible = hostStatus === "failed" || hostStatus === "unavailable";
  const aiVerifyEligible = aiStatus !== "received";

  const scopeIsCurrent = (generationId: number, expectedRevision: number, artifactRef: string) => (
    mounted.current
    && generation.current === generationId
    && scopeRef.current.commandIdentity === commandIdentity
    && scopeRef.current.revision === expectedRevision
    && scopeRef.current.savedArtifactRef === artifactRef
  );

  const retryHost = async () => {
    if (!hostAvailable || !hostRetryEligible || pending || !hostAdapter) return;
    const artifactRef = savedArtifactRef;
    const expectedRevision = revision;
    const generationId = ++generation.current;
    setPending("host");
    setMessage("正在重试宿主通知…");
    try {
      const result = await withReviewWriteDeadline((signal) => hostAdapter({
        projectRoot,
        expectedRevision,
        reviewSessionId,
        sourceVersion,
        savedArtifactRef: artifactRef,
      }, { signal }));
      if (!scopeIsCurrent(generationId, expectedRevision, artifactRef)) return;
      if (
        result.savedArtifactRef !== artifactRef
        || result.hostNotificationStatus !== "sent"
        || !isSafeSuccessor(result.snapshotRevision, expectedRevision)
      ) throw new Error("VISUAL_HOST_RECOVERY_RESULT_UNCLOSED");
      onHostSent(result.snapshotRevision);
      setMessage("宿主通知已送达");
    } catch (error) {
      if (!scopeIsCurrent(generationId, expectedRevision, artifactRef)) return;
      setMessage(isReviewWriteTimeout(error)
        ? "宿主通知重试超时；已保存反馈不受影响，可再次重试。"
        : "宿主通知仍未送达；已保存反馈不受影响，可再次重试。");
    } finally {
      if (scopeIsCurrent(generationId, expectedRevision, artifactRef)) setPending(null);
    }
  };

  const verifyAi = async () => {
    if (!aiAvailable || !aiVerifyEligible || pending || !aiAdapter) return;
    const artifactRef = savedArtifactRef;
    const expectedRevision = revision;
    const generationId = ++generation.current;
    setPending("ai");
    setMessage("正在验证 AI 接收…");
    try {
      const result = await withReviewWriteDeadline((signal) => aiAdapter({
        projectRoot,
        expectedRevision,
        reviewSessionId,
        sourceVersion,
        savedArtifactRef: artifactRef,
        receiptIdentity: artifactRef,
      }, { signal }));
      if (!scopeIsCurrent(generationId, expectedRevision, artifactRef)) return;
      if (
        result.savedArtifactRef !== artifactRef
        || result.aiReceiptStatus !== "received"
        || !isSafeSuccessor(result.snapshotRevision, expectedRevision)
      ) throw new Error("VISUAL_AI_RECOVERY_RESULT_UNCLOSED");
      onAiReceived(result.snapshotRevision);
      setMessage("AI 接收已验证");
    } catch (error) {
      if (!scopeIsCurrent(generationId, expectedRevision, artifactRef)) return;
      setMessage(isReviewWriteTimeout(error)
        ? "AI 接收验证超时；当前仍为未验证，可再次验证。"
        : "AI 接收仍未验证；已保存反馈不受影响，可再次验证。");
    } finally {
      if (scopeIsCurrent(generationId, expectedRevision, artifactRef)) setPending(null);
    }
  };

  return (
    <section className="visual-recovery-actions" aria-label="保存后独立恢复">
      {hostRetryEligible ? hostAvailable ? (
        <button type="button" disabled={pending !== null} onClick={retryHost}>
          {pending === "host" ? "正在重试宿主通知…" : "重试宿主通知"}
        </button>
      ) : <span>宿主通知恢复：{unavailableLabel(hostCapability, Boolean(hostAdapter))}</span> : null}
      {aiVerifyEligible ? aiAvailable ? (
        <button type="button" disabled={pending !== null} onClick={verifyAi}>
          {pending === "ai" ? "正在验证 AI 接收…" : "验证 AI 接收"}
        </button>
      ) : <span>AI 接收验证：{unavailableLabel(aiCapability, Boolean(aiAdapter))}</span> : null}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
