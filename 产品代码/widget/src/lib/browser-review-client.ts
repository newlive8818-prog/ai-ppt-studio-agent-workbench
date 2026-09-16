import type {
  BrowserReviewRecoveryBridge,
  HostBridge,
  HostBridgeCallOptions,
  ReviewSurfaceData,
  VisualAiReceiptRecoveryInput,
  VisualArtifactRecoveryScope,
} from "../types/host";
import type { VisualReviewSurfaceData } from "../types/visual-review";
import { isArtifactReference } from "./artifact-reference";
import { clonePlainData } from "./plain-data";
import {
  validateHostOpenEnvelope,
  validateReviewConnectionEnvelope,
  validateReviewSurfaceData,
} from "../review-surface-validation";
import { parseToolOutput } from "../types/tool-contracts";
import type { ToolContractMap } from "../types/tool-contracts";
import { validateAnchorFeedbackToolResult } from "../visual-review/anchor-feedback-validation";
import { validateVisualContractMarkToolResult } from "../visual-review/visual-contract-mark-validation";
import { toVisualReviewPageViewModel } from "../visual-review/visual-review-page-view-model";

interface BrowserReviewClientOptions {
  navigate?: (url: string) => void;
  connectionTimeoutMs?: number;
}

function isVisualReviewSurface(data: ReviewSurfaceData): data is VisualReviewSurfaceData {
  return data.review.review_type === "visual-professional";
}

function isWritableRevision(value: unknown): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && value >= 0
    && value < Number.MAX_SAFE_INTEGER;
}

function invalidRevisionError() {
  const error = new Error("Review revision is invalid; reopen the review session") as Error & { code?: string };
  error.code = "REVIEW_REVISION_INVALID";
  return error;
}

function invalidConnectionError() {
  const error = new Error("Review connection data is invalid; reopen the review session") as Error & { code?: string };
  error.code = "REVIEW_CONNECTION_INVALID";
  return error;
}

function sessionExpiredError(resultUnknown = false) {
  return Object.assign(new Error("Review session expired; reopen the same review from the conversation"), {
    code: resultUnknown ? "REVIEW_SESSION_EXPIRED_RESULT_UNKNOWN" : "REVIEW_SESSION_EXPIRED",
  });
}

function invalidRecoveryError() {
  const error = new Error("视觉审核恢复结果未闭合，请刷新或重新打开审核") as Error & { code?: string };
  error.code = "VISUAL_RECOVERY_RESULT_UNCLOSED";
  return error;
}

function connectionError(
  code: "REVIEW_CONNECTION_TIMEOUT" | "REVIEW_CONNECTION_SUPERSEDED",
  message: string,
) {
  const error = new Error(message) as Error & { code?: string };
  error.code = code;
  return error;
}

function isExactRecord(value: unknown, fields: readonly string[]): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
    return false;
  }
  const expected = new Set(fields);
  const keys = Reflect.ownKeys(value);
  return keys.length === fields.length && keys.every((key) => {
    if (typeof key !== "string" || !expected.has(key)) return false;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(descriptor && "value" in descriptor && descriptor.enumerable);
  });
}

function validateRecoveryEnvelope(
  value: unknown,
  input: VisualArtifactRecoveryScope,
  fact: "host" | "ai",
) {
  const cloned = clonePlainData(value);
  const fields = fact === "host"
    ? ["ok", "savedArtifactRef", "hostNotificationStatus", "snapshotRevision"]
    : ["ok", "savedArtifactRef", "aiReceiptStatus", "snapshotRevision"];
  if (
    !isExactRecord(cloned, fields)
    || cloned.ok !== true
    || cloned.savedArtifactRef !== input.savedArtifactRef
    || !(isArtifactReference(cloned.savedArtifactRef, "visual-anchor-feedback-batch")
      || isArtifactReference(cloned.savedArtifactRef, "visual-contract-review-mark-set"))
    || cloned[fact === "host" ? "hostNotificationStatus" : "aiReceiptStatus"]
      !== (fact === "host" ? "sent" : "received")
    || !isWritableRevision(cloned.snapshotRevision)
    || cloned.snapshotRevision !== input.expectedRevision + 1
  ) throw invalidRecoveryError();
  return cloned as {
    savedArtifactRef: string;
    snapshotRevision: number;
    hostNotificationStatus?: "sent";
    aiReceiptStatus?: "received";
  };
}

function validateVisualWriteEnvelope(
  value: unknown,
  kind: "anchor" | "marks",
  expectedRevision: number,
): Record<string, unknown> | null {
  const cloned = clonePlainData(value);
  const fields = kind === "anchor"
    ? ["ok", "snapshotRevision", "batchRef", "batch", "hostNotificationStatus", "aiReceiptStatus"]
    : ["ok", "snapshotRevision", "markSetRef", "markSet", "hostNotificationStatus", "aiReceiptStatus"];
  if (!isExactRecord(cloned, fields) || cloned.ok !== true) return null;
  const savedRef = cloned[kind === "anchor" ? "batchRef" : "markSetRef"];
  const saved = cloned[kind === "anchor" ? "batch" : "markSet"];
  const hostStatus = cloned.hostNotificationStatus;
  if (
    !isArtifactReference(
      savedRef,
      kind === "anchor"
        ? "visual-anchor-feedback-batch"
        : "visual-contract-review-mark-set",
    )
    || !saved
    || typeof saved !== "object"
    || Array.isArray(saved)
    || Object.getPrototypeOf(saved) !== Object.prototype
    || !["sent", "failed", "unavailable"].includes(String(hostStatus))
    || cloned.aiReceiptStatus !== "unverified"
    || !isWritableRevision(cloned.snapshotRevision)
    || cloned.snapshotRevision !== expectedRevision + (hostStatus === "sent" ? 2 : 1)
  ) return null;
  return cloned;
}

function tokenFromFragment(): string {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("token") || "";
  if (!token) throw new Error("Review session token is missing");
  window.history.replaceState(
    null,
    document.title,
    `${window.location.pathname}${window.location.search}`,
  );
  return token;
}

async function jsonOrError(response: Response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const details = payload as { error?: { code?: string; message?: string } };
    const error = new Error(
      details.error?.message || "Browser Review request failed",
    ) as Error & { code?: string };
    error.code = details.error?.code;
    throw error;
  }
  return payload;
}

export function createBrowserReviewClient(
  options: BrowserReviewClientOptions = {},
): HostBridge & BrowserReviewRecoveryBridge & { switchReview(reviewType: "content" | "visual"): Promise<void> } {
  let token = "";
  let data: ReviewSurfaceData | undefined;
  let heartbeatTimer: number | undefined;
  let sessionExpiresAt: number | undefined;
  let sessionExpired = false;
  let connectionGeneration = 0;
  let activeConnection: {
    generation: number;
    abortController: AbortController;
    terminal: Promise<never>;
    cancel(error: Error): void;
    dispose(): void;
  } | undefined;
  const connectionTimeoutMs = Math.max(1, Number(options.connectionTimeoutMs || 8_000));
  const navigate = options.navigate || ((url: string) => window.location.assign(url));

  function isSessionExpired() {
    if (sessionExpiresAt !== undefined && Date.now() > sessionExpiresAt) sessionExpired = true;
    return sessionExpired;
  }

  async function authorizedFetch(
    path: string,
    init: RequestInit = {},
    authorizationToken = token,
    checkExpiry = true,
  ) {
    if (checkExpiry && isSessionExpired()) throw sessionExpiredError();
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${authorizationToken}`);
    try {
      return await fetch(path, { ...init, headers: Object.fromEntries(headers.entries()) });
    } catch (error) {
      // The hard TTL can close the listener before it can send an HTTP 410.
      if (checkExpiry && isSessionExpired()) {
        // A dispatched write may have committed even if its response was lost.
        throw sessionExpiredError(init.method === "POST" && path !== "/api/heartbeat");
      }
      throw error;
    }
  }

  function beginConnection() {
    if (heartbeatTimer !== undefined) {
      window.clearInterval(heartbeatTimer);
      heartbeatTimer = undefined;
    }
    activeConnection?.cancel(connectionError(
      "REVIEW_CONNECTION_SUPERSEDED",
      "A newer Browser Review connection superseded this attempt",
    ));
    const generation = ++connectionGeneration;
    const abortController = new AbortController();
    let rejectTerminal!: (error: Error) => void;
    let terminal = false;
    const terminalPromise = new Promise<never>((_resolve, reject) => {
      rejectTerminal = reject;
    });
    const timeout = window.setTimeout(() => {
      if (terminal) return;
      terminal = true;
      rejectTerminal(connectionError(
        "REVIEW_CONNECTION_TIMEOUT",
        "Browser Review connection timed out",
      ));
      abortController.abort();
    }, connectionTimeoutMs);
    const attempt = {
      generation,
      abortController,
      terminal: terminalPromise,
      cancel(error: Error) {
        if (terminal) return;
        terminal = true;
        rejectTerminal(error);
        abortController.abort();
      },
      dispose() {
        terminal = true;
        window.clearTimeout(timeout);
      },
    };
    activeConnection = attempt;
    return attempt;
  }

  function requireCurrentConnection(generation: number) {
    if (generation !== connectionGeneration) {
      throw connectionError(
        "REVIEW_CONNECTION_SUPERSEDED",
        "A newer Browser Review connection superseded this attempt",
      );
    }
  }

  function startHeartbeat() {
    if (heartbeatTimer !== undefined) return;
    const generation = connectionGeneration;
    heartbeatTimer = window.setInterval(() => {
      void authorizedFetch("/api/heartbeat", { method: "POST" }).then(jsonOrError).catch((error) => {
        if (generation !== connectionGeneration || error?.code !== "REVIEW_SESSION_EXPIRED") return;
        sessionExpired = true;
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = undefined;
      });
    }, 15_000);
  }

  function visualRecoveryData(input: VisualArtifactRecoveryScope) {
    if (!data || !isVisualReviewSurface(data)) {
      throw new Error("Visual review recovery is outside the connected review scope");
    }
    if (!isWritableRevision(data.snapshotRevision) || !isWritableRevision(input.expectedRevision)) {
      throw invalidRevisionError();
    }
    const savedArtifactMatches = (
      input.savedArtifactRef === data.review.anchor_feedback_batch_ref
      && data.review.anchor_feedback_batch !== null
    ) || (
      input.savedArtifactRef === data.review.contract_review_marks_ref
      && data.review.contract_review_marks !== null
    );
    if (
      input.projectRoot !== data.selectedProjectRoot
      || input.reviewSessionId !== data.review.review_session_id
      || input.sourceVersion !== data.review.source_version
      || input.expectedRevision !== data.snapshotRevision
      || !savedArtifactMatches
    ) throw new Error("Visual review recovery is outside the connected saved artifact scope");
    return data;
  }

  function installRecoveryFact(
    visualData: VisualReviewSurfaceData,
    savedArtifactRef: string,
    fact: "host" | "ai",
    snapshotRevision: number,
  ) {
    const anchor = savedArtifactRef === visualData.review.anchor_feedback_batch_ref
      && visualData.review.anchor_feedback_batch
      ? {
          ...visualData.review.anchor_feedback_batch,
          ...(fact === "host"
            ? { host_notification_status: "sent" as const }
            : { ai_receipt_status: "received" as const }),
        }
      : visualData.review.anchor_feedback_batch;
    const marks = savedArtifactRef === visualData.review.contract_review_marks_ref
      && visualData.review.contract_review_marks
      ? {
          ...visualData.review.contract_review_marks,
          ...(fact === "host"
            ? { host_notification_status: "sent" as const }
            : { ai_receipt_status: "received" as const }),
        }
      : visualData.review.contract_review_marks;
    data = {
      ...visualData,
      snapshotRevision,
      review: {
        ...visualData.review,
        authoritative_revision: snapshotRevision,
        anchor_feedback_batch: anchor,
        contract_review_marks: marks,
      },
    };
  }

  return {
    async connect(onData?: (incoming: ReviewSurfaceData) => void) {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      if (fragment.has("token") || !token) token = tokenFromFragment();
      const connectionToken = token;
      const attempt = beginConnection();
      const connectionFetch = (path: string, init: RequestInit = {}) => Promise.race([
        authorizedFetch(path, {
          ...init,
          signal: attempt.abortController.signal,
        }, connectionToken, false),
        attempt.terminal,
      ]);
      try {
        const response = await connectionFetch("/api/review");
        requireCurrentConnection(attempt.generation);
        const payload = validateReviewConnectionEnvelope(await jsonOrError(response));
        if (!payload) throw invalidConnectionError();
        if (!isWritableRevision(payload.expectedRevision)) throw invalidRevisionError();
        requireCurrentConnection(attempt.generation);
        const opened = await connectionFetch("/api/host-open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expectedRevision: payload.expectedRevision,
            bridgeSessionId: payload.bridgeSessionId,
          }),
        });
        requireCurrentConnection(attempt.generation);
        const openReceipt = validateHostOpenEnvelope(
          await jsonOrError(opened),
          payload.expectedRevision,
        );
        if (!openReceipt) throw invalidConnectionError();
        if (!isWritableRevision(openReceipt.snapshotRevision)) throw invalidRevisionError();
        const refreshedResponse = await connectionFetch("/api/review");
        requireCurrentConnection(attempt.generation);
        const refreshed = validateReviewConnectionEnvelope(
          await jsonOrError(refreshedResponse),
        );
        if (
          !refreshed
          || refreshed.projectRoot !== payload.projectRoot
          || refreshed.review.review_type !== payload.review.review_type
          || refreshed.review.source_version !== payload.review.source_version
          || refreshed.bridgeSessionId !== payload.bridgeSessionId
          || refreshed.sessionExpiresAt !== payload.sessionExpiresAt
          || refreshed.expectedRevision !== openReceipt.snapshotRevision
          || refreshed.review.review_session_id !== payload.review.review_session_id
        ) throw invalidConnectionError();
        const connected = validateReviewSurfaceData({
          surface: "review" as const,
          selectedProjectRoot: refreshed.projectRoot,
          snapshotRevision: openReceipt.snapshotRevision,
          review: refreshed.review,
        });
        if (!connected) throw invalidConnectionError();
        requireCurrentConnection(attempt.generation);
        sessionExpiresAt = refreshed.sessionExpiresAt;
        sessionExpired = false;
        data = connected;
        onData?.(connected);
        startHeartbeat();
      } finally {
        attempt.dispose();
        if (activeConnection === attempt) activeConnection = undefined;
      }
    },
    async retryVisualHostNotification(input, callOptions) {
      const visualData = visualRecoveryData(input);
      const response = await authorizedFetch("/api/host-notification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(callOptions?.signal ? { signal: callOptions.signal } : {}),
        body: JSON.stringify({
          expectedRevision: input.expectedRevision,
          reviewSessionId: input.reviewSessionId,
          sourceVersion: input.sourceVersion,
          savedArtifactRef: input.savedArtifactRef,
        }),
      });
      const payload = validateRecoveryEnvelope(
        await jsonOrError(response),
        input,
        "host",
      );
      installRecoveryFact(
        visualData,
        payload.savedArtifactRef,
        "host",
        payload.snapshotRevision,
      );
      return {
        savedArtifactRef: payload.savedArtifactRef,
        hostNotificationStatus: "sent",
        snapshotRevision: payload.snapshotRevision,
      };
    },
    async verifyVisualAiReceipt(input: VisualAiReceiptRecoveryInput, callOptions) {
      if (input.receiptIdentity !== input.savedArtifactRef) {
        throw new Error("Visual AI receipt identity does not match the connected saved artifact");
      }
      const visualData = visualRecoveryData(input);
      const response = await authorizedFetch("/api/ai-receipt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(callOptions?.signal ? { signal: callOptions.signal } : {}),
        body: JSON.stringify({
          expectedRevision: input.expectedRevision,
          reviewSessionId: input.reviewSessionId,
          sourceVersion: input.sourceVersion,
          savedArtifactRef: input.savedArtifactRef,
          receiptIdentity: input.receiptIdentity,
        }),
      });
      const payload = validateRecoveryEnvelope(
        await jsonOrError(response),
        input,
        "ai",
      );
      installRecoveryFact(
        visualData,
        payload.savedArtifactRef,
        "ai",
        payload.snapshotRevision,
      );
      return {
        savedArtifactRef: payload.savedArtifactRef,
        aiReceiptStatus: "received",
        snapshotRevision: payload.snapshotRevision,
      };
    },
    async callTool<K extends keyof ToolContractMap>(
      name: K,
      args: ToolContractMap[K]["input"],
      callOptions?: HostBridgeCallOptions,
    ) {
      if (!data) {
        throw new Error("Browser Review tool is unavailable");
      }
      if (name === "read_ai_ppt_project_asset") {
        const input = args as ToolContractMap["read_ai_ppt_project_asset"]["input"];
        if (input.projectRoot !== data.selectedProjectRoot) {
          throw new Error("Project asset request is outside the review scope");
        }
        const response = await authorizedFetch(
          `/api/asset?assetRef=${encodeURIComponent(input.assetRef)}`,
        );
        const payload = (await jsonOrError(response)) as {
          asset: ToolContractMap["read_ai_ppt_project_asset"]["output"]["asset"];
        };
        return parseToolOutput(name, { asset: payload.asset });
      }
      if (name === "save_content_page_decision") {
        const input = args as ToolContractMap["save_content_page_decision"]["input"];
        if (!isWritableRevision(data.snapshotRevision) || !isWritableRevision(input.expectedRevision)) {
          throw invalidRevisionError();
        }
        const response = await authorizedFetch("/api/content/decision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expectedRevision: input.expectedRevision,
            reviewSessionId: input.reviewSessionId,
            sourceVersion: input.sourceVersion,
            slideId: input.slideId,
            decision: input.decision,
            comment: input.comment,
          }),
        });
        const payload = (await jsonOrError(response)) as {
          snapshotRevision: number;
          decisionRef: string;
          decision: Record<string, unknown>;
        };
        data = { ...data, snapshotRevision: payload.snapshotRevision };
        return parseToolOutput(name, {
          decision_ref: payload.decisionRef,
          decision: payload.decision,
          snapshot: { revision: payload.snapshotRevision },
        });
      }
      if (name === "submit_content_review_batch") {
        const input = args as ToolContractMap["submit_content_review_batch"]["input"];
        if (!isWritableRevision(data.snapshotRevision) || !isWritableRevision(input.expectedRevision)) {
          throw invalidRevisionError();
        }
        const response = await authorizedFetch("/api/content/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expectedRevision: input.expectedRevision,
            reviewSessionId: input.reviewSessionId,
            sourceVersion: input.sourceVersion,
          }),
        });
        const payload = (await jsonOrError(response)) as {
          snapshotRevision: number;
          batchRef: string;
          batch: Record<string, unknown>;
        };
        data = { ...data, snapshotRevision: payload.snapshotRevision };
        return parseToolOutput(name, {
          batch_ref: payload.batchRef,
          batch: payload.batch,
          snapshot: { revision: payload.snapshotRevision },
        });
      }
      if (name === "submit_visual_anchor_feedback_batch") {
        const input = args as ToolContractMap["submit_visual_anchor_feedback_batch"]["input"];
        if (!isVisualReviewSurface(data)) {
          throw new Error("Visual feedback request is outside the connected review scope");
        }
        const visualData = data;
        if (!isWritableRevision(visualData.snapshotRevision) || !isWritableRevision(input.expectedRevision)) {
          throw invalidRevisionError();
        }
        if (
          input.projectRoot !== visualData.selectedProjectRoot
          || input.reviewSessionId !== visualData.review.review_session_id
          || input.sourceVersion !== visualData.review.source_version
        ) throw new Error("Visual feedback request is outside the connected review scope");
        if (input.expectedRevision !== visualData.snapshotRevision) {
          throw new Error(`Visual feedback revision ${input.expectedRevision} does not match current revision ${visualData.snapshotRevision}`);
        }
        const response = await authorizedFetch("/api/visual/anchor-feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          ...(callOptions?.signal ? { signal: callOptions.signal } : {}),
          body: JSON.stringify({
            expectedRevision: input.expectedRevision,
            sourceVersion: input.sourceVersion,
            reviewSessionId: input.reviewSessionId,
            feedback: input.feedback,
          }),
        });
        const payload = validateVisualWriteEnvelope(
          await jsonOrError(response),
          "anchor",
          input.expectedRevision,
        ) as {
          snapshotRevision: number;
          batchRef: string;
          batch: ToolContractMap["submit_visual_anchor_feedback_batch"]["output"]["batch"];
          hostNotificationStatus: ToolContractMap["submit_visual_anchor_feedback_batch"]["output"]["batch"]["host_notification_status"];
          aiReceiptStatus: ToolContractMap["submit_visual_anchor_feedback_batch"]["output"]["batch"]["ai_receipt_status"];
        } | null;
        if (!payload) {
          const error = new Error("提交结果未闭合，请刷新/重新打开核对权威批次") as Error & { code?: string };
          error.code = "VISUAL_ANCHOR_FEEDBACK_RESULT_UNCLOSED";
          throw error;
        }
        const candidate = {
          batch_ref: payload.batchRef,
          batch: {
            ...payload.batch,
            host_notification_status: payload.hostNotificationStatus,
            ai_receipt_status: payload.aiReceiptStatus,
          },
          snapshot: { revision: payload.snapshotRevision },
        };
        const validated = validateAnchorFeedbackToolResult(
          candidate,
          toVisualReviewPageViewModel(visualData),
          input.feedback,
          input.expectedRevision,
        );
        if (!validated) {
          const error = new Error("提交结果未闭合，请刷新/重新打开核对权威批次") as Error & { code?: string };
          error.code = "VISUAL_ANCHOR_FEEDBACK_RESULT_UNCLOSED";
          throw error;
        }
        data = {
          ...visualData,
          snapshotRevision: validated.revision,
          review: {
            ...visualData.review,
            authoritative_revision: validated.revision,
            anchor_feedback_batch_ref: validated.batchRef,
            anchor_feedback_batch: validated.batch,
          },
        };
        return parseToolOutput(name, {
          batch_ref: validated.batchRef,
          batch: validated.batch,
          snapshot: { revision: validated.revision },
        });
      }
      if (name !== "save_visual_contract_review_marks") {
        throw new Error("Browser Review tool is unavailable");
      }
      const input = args as ToolContractMap["save_visual_contract_review_marks"]["input"];
      if (!isVisualReviewSurface(data)) {
        throw new Error("Visual contract mark request is outside the connected review scope");
      }
      const visualData = data;
      if (!isWritableRevision(visualData.snapshotRevision) || !isWritableRevision(input.expectedRevision)) {
        throw invalidRevisionError();
      }
      if (
        input.projectRoot !== visualData.selectedProjectRoot
        || input.reviewSessionId !== visualData.review.review_session_id
        || input.sourceVersion !== visualData.review.source_version
      ) throw new Error("Visual contract mark request is outside the connected review scope");
      if (input.expectedRevision !== visualData.snapshotRevision) {
        throw new Error(`Visual contract mark revision ${input.expectedRevision} does not match current revision ${visualData.snapshotRevision}`);
      }
      const response = await authorizedFetch("/api/visual/marks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(callOptions?.signal ? { signal: callOptions.signal } : {}),
        body: JSON.stringify({
          expectedRevision: input.expectedRevision,
          sourceVersion: input.sourceVersion,
          reviewSessionId: input.reviewSessionId,
          marks: input.marks,
        }),
      });
      const payload = validateVisualWriteEnvelope(
        await jsonOrError(response),
        "marks",
        input.expectedRevision,
      ) as {
        snapshotRevision: number;
        markSetRef: string;
        markSet: ToolContractMap["save_visual_contract_review_marks"]["output"]["mark_set"];
        hostNotificationStatus: ToolContractMap["save_visual_contract_review_marks"]["output"]["mark_set"]["host_notification_status"];
        aiReceiptStatus: ToolContractMap["save_visual_contract_review_marks"]["output"]["mark_set"]["ai_receipt_status"];
      } | null;
      if (!payload) {
        const error = new Error("合同标记保存结果未闭合，请刷新/重新打开核对权威状态") as Error & { code?: string };
        error.code = "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED";
        throw error;
      }
      const candidate = {
        mark_set_ref: payload.markSetRef,
        mark_set: {
          ...payload.markSet,
          host_notification_status: payload.hostNotificationStatus,
          ai_receipt_status: payload.aiReceiptStatus,
        },
        snapshot: { revision: payload.snapshotRevision },
      };
      const validated = validateVisualContractMarkToolResult(
        candidate,
        toVisualReviewPageViewModel(visualData),
        input.marks,
        input.expectedRevision,
      );
      if (!validated) {
        const error = new Error("合同标记保存结果未闭合，请刷新/重新打开核对权威状态") as Error & { code?: string };
        error.code = "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED";
        throw error;
      }
      data = {
        ...visualData,
        snapshotRevision: validated.revision,
        review: {
          ...visualData.review,
          authoritative_revision: validated.revision,
          contract_review_marks_ref: validated.markSetRef,
          contract_review_marks: validated.markSet,
        },
      };
      return parseToolOutput(name, {
        mark_set_ref: validated.markSetRef,
        mark_set: validated.markSet,
        snapshot: { revision: validated.revision },
      });
    },
    async switchReview(reviewType) {
      if (!data) throw new Error("Browser Review session is not connected");
      const currentReviewType = data.review.review_type.includes("content")
        ? "content"
        : "visual";
      if (reviewType === currentReviewType) return;
      const response = await authorizedFetch("/api/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewType }),
      });
      const payload = (await jsonOrError(response)) as {
        url: string;
        reviewType: "content" | "visual";
      };
      if (payload.reviewType !== reviewType) {
        throw new Error("Browser Review switch returned the wrong review type");
      }
      const target = new URL(payload.url);
      const targetToken = new URLSearchParams(target.hash.slice(1)).get("token");
      if (
        target.protocol !== "http:" ||
        target.hostname !== "127.0.0.1" ||
        target.username ||
        target.password ||
        target.pathname !== "/" ||
        target.search ||
        !targetToken
      ) {
        throw new Error("Browser Review switch returned an invalid scoped URL");
      }
      navigate(target.toString());
    },
  };
}
