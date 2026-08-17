import { randomBytes } from "node:crypto";
import http from "node:http";

const LOOPBACK_HOST = "127.0.0.1";
const MAX_BODY_BYTES = 2 * 1024 * 1024;
const MAX_ASSET_BYTES = 12 * 1024 * 1024;
const MAX_VISUAL_WRITE_REPLAYS = 8;
const MAX_RECOVERY_WRITE_REPLAYS = 8;
const ARTIFACT_REFERENCE_PATTERN = /^artifact:\/\/([a-z0-9-]+)\/([a-f0-9]{64})$/;
const IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
const PROJECTION_OPERATIONS = Object.freeze({
  "content-full-deck": "get-content-review-projection",
  "visual-professional": "get-visual-review-projection",
});
const SWITCH_REVIEW_TYPES = Object.freeze({
  content: "content-full-deck",
  visual: "visual-professional",
});
const API_METHODS = Object.freeze({
  "/api/review": "GET",
  "/api/asset": "GET",
  "/api/content/decision": "POST",
  "/api/content/batch": "POST",
  "/api/visual/anchor-feedback": "POST",
  "/api/visual/marks": "POST",
  "/api/host-open": "POST",
  "/api/host-notification": "POST",
  "/api/ai-receipt": "POST",
  "/api/switch": "POST",
  "/api/heartbeat": "POST",
});
const AUTHORITATIVE_WRITE_PATHS = new Set([
  "/api/content/decision",
  "/api/content/batch",
  "/api/visual/anchor-feedback",
  "/api/visual/marks",
  "/api/host-open",
  "/api/host-notification",
  "/api/ai-receipt",
]);
const SECURITY_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
});

function apiCsp() {
  return "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; connect-src 'self'";
}

function jsonResponse(response, status, payload, extraHeaders = {}) {
  if (response.destroyed || response.writableEnded) return;
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    ...SECURITY_HEADERS,
    "Content-Security-Policy": apiCsp(),
    ...extraHeaders,
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
  });
  response.end(body);
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => (
      `${JSON.stringify(key)}:${canonicalJson(value[key])}`
    )).join(",")}}`;
  }
  return JSON.stringify(value);
}

function exactArtifactReference(value, expectedKind) {
  if (typeof value !== "string") return "";
  const text = value.trim();
  const match = ARTIFACT_REFERENCE_PATTERN.exec(text);
  return match?.[1] === expectedKind ? text : "";
}

function htmlResponse(response, html, nonce) {
  response.writeHead(200, {
    ...SECURITY_HEADERS,
    "Content-Security-Policy": [
      "default-src 'none'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'none'",
      "connect-src 'self'",
      `script-src 'nonce-${nonce}'`,
      `style-src 'nonce-${nonce}'`,
      "img-src data: blob:",
      "font-src data:",
    ].join("; "),
    "Content-Type": "text/html; charset=utf-8",
    "Content-Length": Buffer.byteLength(html),
  });
  response.end(html);
}

function nonceReviewHtml(html, nonce) {
  return html
    .replace(/<script(?![^>]*\bnonce=)/gi, `<script nonce="${nonce}"`)
    .replace(/<style(?![^>]*\bnonce=)/gi, `<style nonce="${nonce}"`);
}

export function collectProjectionAssetRefs(review) {
  const refs = new Set();
  const add = (value) => {
    if (typeof value !== "string") return;
    const ref = value.trim();
    if (ref) refs.add(ref);
  };

  for (const slide of Array.isArray(review?.slides) ? review.slides : []) {
    for (const materialView of Array.isArray(slide?.material_views) ? slide.material_views : []) {
      add(materialView?.asset_ref);
    }
  }
  for (const anchor of Array.isArray(review?.anchors) ? review.anchors : []) {
    add(anchor?.asset_ref);
    add(anchor?.current_asset_ref);
    add(anchor?.previous_asset_ref);
  }
  return refs;
}

function statusForBridgeError(error) {
  if (
    error?.code === "REVISION_CONFLICT" ||
    error?.code === "REVIEW_SOURCE_STALE" ||
    error?.code === "REVIEW_SESSION_STALE"
  ) {
    return 409;
  }
  if (error?.code === "VALIDATION_ERROR") return 422;
  return 502;
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const error = new Error("Request body is too large");
      error.status = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  try {
    const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new TypeError("Body must be an object");
    }
    return payload;
  } catch (cause) {
    const error = new Error("Request body must be valid JSON");
    error.status = 400;
    error.cause = cause;
    throw error;
  }
}

export function createReviewBridge(options) {
  if (!options || typeof options.invokeBridge !== "function") {
    throw new TypeError("Review Bridge requires invokeBridge");
  }
  const projectRoot = String(options.projectRoot || "").trim();
  const reviewType = String(options.reviewType || "").trim();
  const reviewSessionId = String(options.reviewSessionId || "").trim();
  const sourceVersion = String(options.sourceVersion || "").trim();
  const expectedRevision = Number(options.expectedRevision);
  if (
    !projectRoot ||
    !PROJECTION_OPERATIONS[reviewType] ||
    !reviewSessionId ||
    !sourceVersion ||
    !Number.isSafeInteger(expectedRevision) ||
    expectedRevision < 0
  ) {
    throw new TypeError("Review Bridge scope is invalid");
  }
  const invokeBridge = options.invokeBridge;
  const readReviewHtml = options.readReviewHtml;
  const createReviewSession = options.createReviewSession;
  const notifyHost = options.notifyHost;
  const verifyAiReceipt = options.verifyAiReceipt;
  const readProjectAsset = options.readProjectAsset;
  const now = options.now || Date.now;
  const notificationTimeoutMs = Math.max(1, Number(options.notificationTimeoutMs || 5_000));
  const projectionTimeoutMs = Math.max(1, Number(options.projectionTimeoutMs || 8_000));
  const ttlMs = Math.max(1, Number(options.ttlMs || 5 * 60_000));
  const leaseMs = Math.max(1, Number(options.leaseMs || 30_000));
  const token = randomBytes(32).toString("base64url");
  const bridgeSessionId = randomBytes(24).toString("base64url");
  const createdAt = now();
  const expiresAt = createdAt + ttlMs;
  let leaseUntil = createdAt + leaseMs;
  let server = null;
  let port = 0;
  let origin = "";
  let stopped = false;
  let sweepTimer = null;
  let scopedRevision = expectedRevision;
  let projectionRead = false;
  let allowedAssetRefs = new Set();
  let projectionGeneration = 0;
  const visualWriteReplays = new Map();
  const recoveryWriteReplays = new Map();
  let currentVisualArtifacts = new Map();

  function snapshotRevision(payload) {
    const revision = exactSuccessorRevision(payload, scopedRevision);
    scopedRevision = revision;
    return revision;
  }

  function exactSuccessorRevision(payload, startingRevision) {
    const revision = payload?.result?.snapshot?.revision;
    if (
      !Number.isSafeInteger(revision)
      || revision < 0
      || startingRevision >= Number.MAX_SAFE_INTEGER
      || revision !== startingRevision + 1
    ) {
      const error = new Error("Runtime did not return the exact authoritative successor revision");
      error.code = "INVALID_RUNTIME_RESULT";
      throw error;
    }
    return revision;
  }

  function scopeMatches(body, { source = true, session = true } = {}) {
    return (
      body.expectedRevision === scopedRevision &&
      (!source || body.sourceVersion === sourceVersion) &&
      (!session || body.reviewSessionId === reviewSessionId)
    );
  }

  function visualWriteIdentity(pathname, body) {
    return `${pathname}\n${canonicalJson(body)}`;
  }

  function rememberRecoveryWrite(pathname, body, payload) {
    const identity = visualWriteIdentity(pathname, body);
    recoveryWriteReplays.set(identity, payload);
    while (recoveryWriteReplays.size > MAX_RECOVERY_WRITE_REPLAYS) {
      recoveryWriteReplays.delete(recoveryWriteReplays.keys().next().value);
    }
  }

  function replayedRecoveryWrite(pathname, body) {
    return recoveryWriteReplays.get(visualWriteIdentity(pathname, body)) || null;
  }

  function installCurrentVisualArtifact(record) {
    for (const [reference, candidate] of currentVisualArtifacts) {
      if (candidate.artifactType === record.artifactType && reference !== record.savedArtifactRef) {
        currentVisualArtifacts.delete(reference);
      }
    }
    currentVisualArtifacts.set(record.savedArtifactRef, record);
  }

  function projectedVisualArtifactRecord({ artifactType, savedArtifactRef, savedResult, saved }) {
    const existing = currentVisualArtifacts.get(savedArtifactRef);
    const projected = {
      artifactType,
      savedArtifactRef,
      savedResult,
      persistenceRevision: scopedRevision,
      responseRevision: scopedRevision,
      hostNotificationStatus:
        saved?.host_notification_status === "sent"
          ? "sent"
          : saved?.host_notification_status === "failed"
            ? "failed"
            : existing?.hostNotificationStatus || "unavailable",
      aiReceiptStatus:
        saved?.ai_receipt_status === "received"
          ? "received"
          : existing?.aiReceiptStatus || "unverified",
    };
    if (existing) {
      Object.assign(existing, projected);
      return existing;
    }
    return {
      ...projected,
      notificationGeneration: 0,
      notificationInFlight: false,
      aiReceiptGeneration: 0,
      aiReceiptInFlight: false,
    };
  }

  function installProjectedVisualArtifacts(review) {
    const projected = new Map();
    const anchorRef = exactArtifactReference(
      review?.anchor_feedback_batch_ref,
      "visual-anchor-feedback-batch",
    );
    if (anchorRef && review?.anchor_feedback_batch && typeof review.anchor_feedback_batch === "object") {
      const record = projectedVisualArtifactRecord({
        artifactType: "anchor",
        savedArtifactRef: anchorRef,
        savedResult: {
          batch_ref: anchorRef,
          batch: review.anchor_feedback_batch,
        },
        saved: review.anchor_feedback_batch,
      });
      projected.set(anchorRef, record);
    }
    const markSetRef = exactArtifactReference(
      review?.contract_review_marks_ref,
      "visual-contract-review-mark-set",
    );
    if (markSetRef && review?.contract_review_marks && typeof review.contract_review_marks === "object") {
      const record = projectedVisualArtifactRecord({
        artifactType: "marks",
        savedArtifactRef: markSetRef,
        savedResult: {
          mark_set_ref: markSetRef,
          mark_set: review.contract_review_marks,
        },
        saved: review.contract_review_marks,
      });
      projected.set(markSetRef, record);
    }
    currentVisualArtifacts = projected;
  }

  function rememberVisualWrite(pathname, body, result, persistenceRevision) {
    const anchor = pathname === "/api/visual/anchor-feedback";
    const savedArtifactRef = exactArtifactReference(
      anchor ? result?.batch_ref : result?.mark_set_ref,
      anchor ? "visual-anchor-feedback-batch" : "visual-contract-review-mark-set",
    );
    const saved = anchor ? result?.batch : result?.mark_set;
    if (!savedArtifactRef || !saved || typeof saved !== "object" || Array.isArray(saved)) {
      const error = new Error("Runtime returned an invalid saved visual artifact reference");
      error.code = "INVALID_RUNTIME_RESULT";
      throw error;
    }
    const identity = visualWriteIdentity(pathname, body);
    const record = {
      identity,
      pathname,
      body,
      result,
      artifactType: anchor ? "anchor" : "marks",
      savedArtifactRef,
      savedResult: anchor
        ? { batch_ref: savedArtifactRef, batch: saved }
        : { mark_set_ref: savedArtifactRef, mark_set: saved },
      persistenceRevision,
      responseRevision: persistenceRevision,
      hostNotificationStatus:
        typeof notifyHost === "function" ? "pending" : "unavailable",
      aiReceiptStatus: "unverified",
      notificationGeneration: 0,
      notificationInFlight: false,
      aiReceiptGeneration: 0,
      aiReceiptInFlight: false,
    };
    visualWriteReplays.set(identity, record);
    while (visualWriteReplays.size > MAX_VISUAL_WRITE_REPLAYS) {
      visualWriteReplays.delete(visualWriteReplays.keys().next().value);
    }
    installCurrentVisualArtifact(record);
    return record;
  }

  function replayedVisualWrite(pathname, body) {
    return visualWriteReplays.get(visualWriteIdentity(pathname, body)) || null;
  }

  function visualWriteResponse(response, record) {
    const anchor = record.pathname === "/api/visual/anchor-feedback";
    jsonResponse(response, 200, {
      ok: true,
      ...(anchor
        ? { batchRef: record.result.batch_ref, batch: record.result.batch }
        : { markSetRef: record.result.mark_set_ref, markSet: record.result.mark_set }),
      snapshotRevision: record.responseRevision,
      hostNotificationStatus: record.hostNotificationStatus,
      aiReceiptStatus: record.aiReceiptStatus,
    });
  }

  function createHostRecording(record, generation, startingRevision, recordingInput, recoveryBody) {
    let resolveCompletion;
    const completion = new Promise((resolve) => {
      resolveCompletion = resolve;
    });
    return {
      record,
      generation,
      startingRevision,
      recordingInput,
      recoveryBody,
      completion,
      resolveCompletion,
      settled: null,
    };
  }

  function settleHostRecording(operation, payload) {
    if (operation.settled) return operation.settled;
    const { record } = operation;
    let revision;
    try {
      revision = exactSuccessorRevision(payload, operation.startingRevision);
    } catch {
      return { kind: "failed" };
    }
    let outcome;
    if (
      record.notificationRecording !== operation
      || operation.generation !== record.notificationGeneration
      || currentVisualArtifacts.get(record.savedArtifactRef) !== record
      || (
        scopedRevision !== operation.startingRevision
        && scopedRevision !== revision
      )
    ) {
      outcome = { kind: "stale" };
      record.hostNotificationStatus = "failed";
    } else {
      if (scopedRevision === operation.startingRevision) scopedRevision = revision;
      record.responseRevision = revision;
      record.hostNotificationStatus = "sent";
      outcome = { kind: "sent", snapshotRevision: revision };
      if (operation.recoveryBody) {
        rememberRecoveryWrite("/api/host-notification", operation.recoveryBody, {
          ok: true,
          savedArtifactRef: record.savedArtifactRef,
          hostNotificationStatus: "sent",
          snapshotRevision: revision,
        });
      }
    }
    operation.settled = outcome;
    operation.resolveCompletion(outcome);
    return outcome;
  }

  function attemptHostRecording(operation, deadline) {
    if (operation.settled) return Promise.resolve(operation.settled);
    const transport = Promise.resolve()
      .then(() => invokeBridge(operation.recordingInput))
      .then(
        (payload) => settleHostRecording(operation, payload),
        () => ({ kind: "failed" }),
      );
    return Promise.race([transport, operation.completion, deadline]);
  }

  function createAiRecording(record, generation, startingRevision, recordingInput, recoveryBody) {
    let resolveCompletion;
    const completion = new Promise((resolve) => {
      resolveCompletion = resolve;
    });
    return {
      record,
      generation,
      startingRevision,
      recordingInput,
      recoveryBody,
      completion,
      resolveCompletion,
      settled: null,
    };
  }

  function settleAiRecording(operation, payload) {
    if (operation.settled) return operation.settled;
    const { record } = operation;
    let revision;
    try {
      revision = exactSuccessorRevision(payload, operation.startingRevision);
    } catch {
      return { kind: "failed" };
    }
    let outcome;
    if (
      record.aiReceiptRecording !== operation
      || operation.generation !== record.aiReceiptGeneration
      || currentVisualArtifacts.get(record.savedArtifactRef) !== record
      || (
        scopedRevision !== operation.startingRevision
        && scopedRevision !== revision
      )
    ) {
      outcome = { kind: "stale" };
    } else {
      if (scopedRevision === operation.startingRevision) scopedRevision = revision;
      record.responseRevision = revision;
      record.aiReceiptStatus = "received";
      outcome = { kind: "received", snapshotRevision: revision };
      if (operation.recoveryBody) {
        rememberRecoveryWrite("/api/ai-receipt", operation.recoveryBody, {
          ok: true,
          savedArtifactRef: record.savedArtifactRef,
          aiReceiptStatus: "received",
          snapshotRevision: revision,
        });
      }
    }
    operation.settled = outcome;
    operation.resolveCompletion(outcome);
    return outcome;
  }

  function attemptAiRecording(operation, deadline) {
    if (operation.settled) return Promise.resolve(operation.settled);
    const transport = Promise.resolve()
      .then(() => invokeBridge(operation.recordingInput))
      .then(
        (payload) => settleAiRecording(operation, payload),
        () => ({ kind: "failed" }),
      );
    return Promise.race([transport, operation.completion, deadline]);
  }

  async function recordHostNotification(record, response, recoveryBody = null) {
    if (typeof notifyHost !== "function") {
      record.hostNotificationStatus = "unavailable";
      return { kind: "unavailable" };
    }
    if (record.notificationInFlight) {
      return { kind: "in-flight" };
    }
    record.notificationInFlight = true;
    let timeout;
    const deadline = new Promise((resolve) => {
      timeout = setTimeout(() => resolve({ kind: "timeout" }), notificationTimeoutMs);
    });
    if (record.notificationRecording && !record.notificationRecording.settled) {
      try {
        const outcome = await attemptHostRecording(record.notificationRecording, deadline);
        if (outcome.kind !== "sent") record.hostNotificationStatus = "failed";
        return outcome;
      } finally {
        clearTimeout(timeout);
        record.notificationInFlight = false;
      }
    }
    const startingRevision = scopedRevision;
    const generation = ++record.notificationGeneration;
    let stage = "notify";
    let cancelNotification;
    const cancelled = new Promise((resolve) => {
      cancelNotification = () => resolve({ kind: "cancelled" });
    });
    const handleClosedResponse = () => {
      if (
        stage !== "notify"
        || response.writableEnded
        || generation !== record.notificationGeneration
      ) return;
      record.notificationGeneration += 1;
      record.hostNotificationStatus = "failed";
      cancelNotification();
    };
    response?.once("close", handleClosedResponse);
    try {
      const outcome = await Promise.race([
        Promise.resolve().then(() => notifyHost({
          projectRoot,
          reviewType,
          reviewSessionId,
          sourceVersion,
          bridgeSessionId,
          snapshotRevision: startingRevision,
          savedArtifactRef: record.savedArtifactRef,
          savedResult: record.savedResult,
        })).then(
          (receipt) => ({ kind: "receipt", receipt }),
          () => ({ kind: "failed" }),
        ),
        deadline,
        cancelled,
      ]);
      if (
        generation !== record.notificationGeneration
        || outcome.kind !== "receipt"
      ) {
        if (generation === record.notificationGeneration) {
          record.hostNotificationStatus = "failed";
        }
        return { kind: outcome.kind };
      }
      const receipt = outcome.receipt;
      const receiptRef = exactArtifactReference(
        receipt?.receiptRef,
        "review-host-notification-receipt",
      );
      if (!receipt?.sent || !receiptRef) {
        record.hostNotificationStatus = "failed";
        return { kind: "failed" };
      }
      if (
        scopedRevision !== startingRevision
        || currentVisualArtifacts.get(record.savedArtifactRef) !== record
      ) {
        record.hostNotificationStatus = "failed";
        return { kind: "stale" };
      }
      stage = "record";
      response?.removeListener("close", handleClosedResponse);
      const operation = createHostRecording(
        record,
        generation,
        startingRevision,
        {
          operation: "record-review-host-notification",
          project_root: projectRoot,
          expected_revision: startingRevision,
          review_type: reviewType,
          review_session_id: reviewSessionId,
          source_version: sourceVersion,
          saved_artifact_ref: record.savedArtifactRef,
          receipt_ref: receiptRef,
        },
        recoveryBody,
      );
      record.notificationRecording = operation;
      const recording = await attemptHostRecording(operation, deadline);
      if (recording.kind !== "sent") record.hostNotificationStatus = "failed";
      return recording;
    } catch {
      if (generation === record.notificationGeneration) {
        record.hostNotificationStatus = "failed";
      }
      return { kind: "failed" };
    } finally {
      clearTimeout(timeout);
      response?.removeListener("close", handleClosedResponse);
      record.notificationInFlight = false;
    }
  }

  async function notificationFacts(_savedResult, record, response) {
    await recordHostNotification(record, response);
  }

  function isExpired() {
    return now() > expiresAt;
  }

  function hasBearer(request) {
    return request.headers.authorization === `Bearer ${token}`;
  }

  function hasValidHost(request) {
    return request.headers.host === `${LOOPBACK_HOST}:${port}`;
  }

  function originIsSame(request, { required = false } = {}) {
    const supplied = request.headers.origin;
    if (!supplied) return !required;
    return supplied === origin;
  }

  function renewLease() {
    leaseUntil = Math.min(expiresAt, now() + leaseMs);
  }

  function authorize(request, response, { write = false } = {}) {
    if (stopped || isExpired()) {
      jsonResponse(response, 410, {
        ok: false,
        error: { code: "REVIEW_SESSION_EXPIRED", message: "Review session expired." },
      });
      return false;
    }
    if (!hasValidHost(request)) {
      jsonResponse(response, 421, {
        ok: false,
        error: { code: "INVALID_HOST", message: "Review session Host mismatch." },
      });
      return false;
    }
    if (!originIsSame(request, { required: write })) {
      jsonResponse(response, 403, {
        ok: false,
        error: { code: "CROSS_ORIGIN_REJECTED", message: "Review session Origin mismatch." },
      });
      return false;
    }
    if (!hasBearer(request)) {
      jsonResponse(
        response,
        401,
        {
          ok: false,
          error: { code: "INVALID_REVIEW_TOKEN", message: "Review session token is invalid." },
        },
        { "WWW-Authenticate": "Bearer" },
      );
      return false;
    }
    renewLease();
    return true;
  }

  async function handle(request, response) {
    const url = new URL(request.url || "/", origin || "http://127.0.0.1");
    const method = request.method || "GET";
    if (url.pathname === "/" && method === "GET") {
      if (!hasValidHost(request) || !originIsSame(request)) {
        jsonResponse(response, !hasValidHost(request) ? 421 : 403, {
          ok: false,
          error: { code: "REVIEW_SHELL_REJECTED", message: "Review shell request rejected." },
        });
        return;
      }
      if (typeof readReviewHtml !== "function") {
        jsonResponse(response, 503, {
          ok: false,
          error: { code: "REVIEW_SHELL_UNAVAILABLE", message: "Review shell is unavailable." },
        });
        return;
      }
      const nonce = randomBytes(18).toString("base64url");
      const html = nonceReviewHtml(await readReviewHtml(), nonce);
      htmlResponse(response, html, nonce);
      return;
    }
    const allowedMethod = API_METHODS[url.pathname];
    if (allowedMethod !== method) {
      const knownPath = Boolean(allowedMethod);
      jsonResponse(response, knownPath ? 405 : 404, {
        ok: false,
        error: {
          code: knownPath ? "METHOD_NOT_ALLOWED" : "NOT_FOUND",
          message: knownPath ? "Method is not allowed." : "Resource was not found.",
        },
      });
      return;
    }
    const write = method !== "GET";
    if (!authorize(request, response, { write })) return;

    try {
      if (url.pathname === "/api/review") {
        const generation = ++projectionGeneration;
        projectionRead = false;
        allowedAssetRefs = new Set();
        let projectionTimeout;
        let closeProjection;
        const closed = new Promise((resolve) => {
          closeProjection = () => resolve({ kind: "closed" });
          response.once("close", closeProjection);
        });
        const deadline = new Promise((resolve) => {
          projectionTimeout = setTimeout(
            () => resolve({ kind: "timeout" }),
            projectionTimeoutMs,
          );
        });
        let outcome;
        try {
          outcome = await Promise.race([
            Promise.resolve().then(() => invokeBridge({
              operation: PROJECTION_OPERATIONS[reviewType],
              project_root: projectRoot,
              review_session_id: reviewSessionId,
            })).then(
              (payload) => ({ kind: "projection", payload }),
              (error) => ({ kind: "failed", error }),
            ),
            deadline,
            closed,
          ]);
        } finally {
          clearTimeout(projectionTimeout);
          response.removeListener("close", closeProjection);
        }
        if (outcome.kind === "closed") {
          if (generation === projectionGeneration) projectionGeneration += 1;
          return;
        }
        if (outcome.kind === "timeout") {
          if (generation === projectionGeneration) projectionGeneration += 1;
          jsonResponse(response, 504, {
            ok: false,
            error: {
              code: "REVIEW_PROJECTION_TIMEOUT",
              message: "Review projection did not complete before the connection deadline.",
            },
          });
          return;
        }
        if (outcome.kind === "failed") throw outcome.error;
        const payload = outcome.payload;
        if (generation !== projectionGeneration) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_PROJECTION_SUPERSEDED",
              message: "A newer review projection request superseded this response.",
            },
          });
          return;
        }
        if (
          payload?.selected_project_root !== projectRoot ||
          payload?.review?.review_type !== reviewType ||
          payload?.review?.review_session_id !== reviewSessionId
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_SCOPE_MISMATCH",
              message: "Review projection does not match this fixed session scope.",
            },
          });
          return;
        }
        if (
          payload?.review?.source_version !== sourceVersion ||
          payload?.snapshot_revision !== scopedRevision
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_SOURCE_STALE",
              message: "Review projection no longer matches this session.",
            },
          });
          return;
        }
        const scopedReview = reviewType === "visual-professional"
          ? {
              ...payload.review,
              host_submission_capability:
                typeof notifyHost === "function" ? "available" : "unavailable",
              ai_receipt_capability:
                typeof verifyAiReceipt === "function" ? "available" : "unavailable",
          }
          : payload.review;
        if (reviewType === "visual-professional") {
          installProjectedVisualArtifacts(scopedReview);
        }
        allowedAssetRefs = collectProjectionAssetRefs(scopedReview);
        projectionRead = true;
        jsonResponse(response, 200, {
          ok: true,
          projectRoot,
          reviewType,
          sourceVersion,
          expectedRevision: scopedRevision,
          bridgeSessionId,
          review: scopedReview,
        });
        return;
      }

      if (url.pathname === "/api/heartbeat") {
        jsonResponse(response, 200, {
          ok: true,
          leaseExpiresAt: leaseUntil,
          sessionExpiresAt: expiresAt,
        });
        return;
      }

      if (url.pathname === "/api/asset") {
        const assetRef = String(url.searchParams.get("assetRef") || "").trim();
        if (!projectionRead || !allowedAssetRefs.has(assetRef)) {
          jsonResponse(response, 404, {
            ok: false,
            error: { code: "ASSET_NOT_ALLOWLISTED", message: "Asset is unavailable." },
          });
          return;
        }
        if (typeof readProjectAsset !== "function") {
          jsonResponse(response, 503, {
            ok: false,
            error: { code: "ASSET_READER_UNAVAILABLE", message: "Asset reader is unavailable." },
          });
          return;
        }
        try {
          const asset = await readProjectAsset({ projectRoot, assetRef });
          if (
            asset?.assetRef !== assetRef ||
            !IMAGE_MIME_TYPES.has(asset?.mimeType) ||
            !Number.isInteger(asset?.bytes) ||
            asset.bytes < 0 ||
            asset.bytes > MAX_ASSET_BYTES ||
            typeof asset?.dataBase64 !== "string"
          ) {
            throw new TypeError("Asset result violates the scoped image contract");
          }
          jsonResponse(response, 200, { ok: true, asset });
        } catch {
          jsonResponse(response, 404, {
            ok: false,
            error: { code: "ASSET_UNAVAILABLE", message: "Asset is unavailable." },
          });
        }
        return;
      }

      if (url.pathname === "/api/switch") {
        const body = await readJsonBody(request);
        const targetReviewType = String(body.reviewType || "");
        const targetFormalType = SWITCH_REVIEW_TYPES[targetReviewType];
        if (
          !targetFormalType ||
          targetFormalType === reviewType
        ) {
          jsonResponse(response, 422, {
            ok: false,
            error: {
              code: "INVALID_REVIEW_SWITCH",
              message: "Review switch target is invalid.",
            },
          });
          return;
        }
        if (typeof createReviewSession !== "function") {
          jsonResponse(response, 503, {
            ok: false,
            error: {
              code: "REVIEW_SWITCH_UNAVAILABLE",
              message: "Review switch is unavailable.",
            },
          });
          return;
        }
        const target = await createReviewSession({
          projectRoot,
          reviewType: targetReviewType,
        });
        jsonResponse(response, 200, {
          ok: true,
          url: target.url,
          expiresAt: target.expiresAt,
          reviewType: target.reviewType,
          sourceVersion: target.sourceVersion,
          expectedRevision: target.expectedRevision,
        });
        return;
      }

      const body = await readJsonBody(request);

      if (
        url.pathname === "/api/host-notification"
        || url.pathname === "/api/ai-receipt"
      ) {
        const replay = replayedRecoveryWrite(url.pathname, body);
        if (replay) {
          jsonResponse(response, 200, replay);
          return;
        }
      }

      if (
        AUTHORITATIVE_WRITE_PATHS.has(url.pathname)
        && scopedRevision >= Number.MAX_SAFE_INTEGER
      ) {
        jsonResponse(response, 409, {
          ok: false,
          error: {
            code: "REVISION_SUCCESSOR_UNSAFE",
            message: "The current revision has no exactly representable successor.",
          },
        });
        return;
      }

      if (url.pathname === "/api/host-open") {
        if (
          !projectionRead ||
          !scopeMatches(body, { source: false, session: false }) ||
          body.bridgeSessionId !== bridgeSessionId
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_OPEN_SCOPE_MISMATCH",
              message: "Host-open receipt does not match a loaded review session.",
            },
          });
          return;
        }
        const payload = await invokeBridge({
          operation: "record-review-bridge-host-open",
          project_root: projectRoot,
          expected_revision: scopedRevision,
          review_type: reviewType,
          review_session_id: reviewSessionId,
          bridge_session_id: bridgeSessionId,
          recorded_at: new Date(now()).toISOString(),
        });
        jsonResponse(response, 200, {
          ok: true,
          hostOpenStatus: "opened",
          snapshotRevision: snapshotRevision(payload),
        });
        return;
      }

      if (url.pathname === "/api/host-notification") {
        const suppliedRef = exactArtifactReference(
          body.savedArtifactRef,
          "visual-anchor-feedback-batch",
        ) || exactArtifactReference(
          body.savedArtifactRef,
          "visual-contract-review-mark-set",
        );
        const record = suppliedRef ? currentVisualArtifacts.get(suppliedRef) : null;
        if (
          reviewType !== "visual-professional"
          || !scopeMatches(body)
          || !record
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_SCOPE_MISMATCH",
              message: "Host notification does not match the current saved visual artifact.",
            },
          });
          return;
        }
        if (typeof notifyHost !== "function") {
          jsonResponse(response, 503, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_UNAVAILABLE",
              message: "No authoritative host notification adapter is available.",
            },
            savedArtifactRef: suppliedRef,
            hostNotificationStatus: "unavailable",
            snapshotRevision: scopedRevision,
          });
          return;
        }
        if (record.hostNotificationStatus === "sent") {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_ALREADY_SENT",
              message: "Host notification is already recorded for this saved artifact.",
            },
          });
          return;
        }
        if (record.notificationInFlight) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_IN_FLIGHT",
              message: "Host notification is already in flight for this saved artifact.",
            },
          });
          return;
        }
        const outcome = await recordHostNotification(record, response, body);
        if (outcome.kind === "sent") {
          const payload = {
            ok: true,
            savedArtifactRef: suppliedRef,
            hostNotificationStatus: "sent",
            snapshotRevision: outcome.snapshotRevision,
          };
          rememberRecoveryWrite(url.pathname, body, payload);
          jsonResponse(response, 200, payload);
          return;
        }
        if (outcome.kind === "in-flight") {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_IN_FLIGHT",
              message: "Host notification is already in flight for this saved artifact.",
            },
          });
          return;
        }
        if (outcome.kind === "stale") {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_HOST_NOTIFICATION_STALE",
              message: "The saved artifact or authoritative revision changed before notification could be recorded.",
            },
          });
          return;
        }
        jsonResponse(response, 502, {
          ok: false,
          error: {
            code: "REVIEW_HOST_NOTIFICATION_FAILED",
            message: "Host notification was not authoritatively recorded.",
          },
          savedArtifactRef: suppliedRef,
          hostNotificationStatus: record.hostNotificationStatus,
          snapshotRevision: scopedRevision,
        });
        return;
      }

      if (url.pathname === "/api/ai-receipt") {
        const visualAiReceipt = reviewType === "visual-professional";
        const suppliedRef = visualAiReceipt
          ? exactArtifactReference(
              body.savedArtifactRef,
              "visual-anchor-feedback-batch",
            ) || exactArtifactReference(
              body.savedArtifactRef,
              "visual-contract-review-mark-set",
            )
          : "";
        const record = suppliedRef ? currentVisualArtifacts.get(suppliedRef) : null;
        if (
          !(visualAiReceipt ? scopeMatches(body) && record : scopeMatches(
            body,
            { source: false, session: false },
          ))
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: { code: "REVIEW_SCOPE_MISMATCH", message: "AI receipt is stale." },
          });
          return;
        }
        if (typeof verifyAiReceipt !== "function") {
          jsonResponse(response, 503, {
            ok: false,
            error: {
              code: "REVIEW_AI_RECEIPT_UNVERIFIED",
              message: "No authoritative AI receipt verifier is available.",
            },
          });
          return;
        }
        if (visualAiReceipt && record.aiReceiptStatus === "received") {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_AI_RECEIPT_ALREADY_RECORDED",
              message: "AI receipt is already recorded for this saved artifact.",
            },
          });
          return;
        }
        if (visualAiReceipt && record.aiReceiptInFlight) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_AI_RECEIPT_IN_FLIGHT",
              message: "AI receipt verification is already in flight for this saved artifact.",
            },
          });
          return;
        }
        const existingAiRecording = visualAiReceipt
          ? record.aiReceiptRecording
          : null;
        const startingRevision = existingAiRecording?.startingRevision ?? scopedRevision;
        const aiReceiptGeneration = visualAiReceipt
          ? existingAiRecording?.generation ?? ++record.aiReceiptGeneration
          : 0;
        if (visualAiReceipt) record.aiReceiptInFlight = true;
        let verificationTimeout;
        const verificationDeadline = visualAiReceipt
          ? new Promise((resolve) => {
              verificationTimeout = setTimeout(
                () => resolve({ kind: "timeout" }),
                notificationTimeoutMs,
              );
            })
          : null;
        try {
        if (visualAiReceipt && existingAiRecording && !existingAiRecording.settled) {
          const recording = await attemptAiRecording(
            existingAiRecording,
            verificationDeadline,
          );
          if (recording.kind !== "received") {
            jsonResponse(response, 502, {
              ok: false,
              error: {
                code: "REVIEW_AI_RECEIPT_UNVERIFIED",
                message: "AI receipt recording did not complete authoritatively.",
              },
              savedArtifactRef: suppliedRef,
              aiReceiptStatus: "unverified",
              snapshotRevision: scopedRevision,
            });
            return;
          }
          jsonResponse(response, 200, {
            ok: true,
            savedArtifactRef: suppliedRef,
            aiReceiptStatus: "received",
            snapshotRevision: recording.snapshotRevision,
          });
          return;
        }
        const receiptIdentity = String(body.receiptIdentity || "").trim();
        const verificationInput = {
          projectRoot,
          reviewType,
          reviewSessionId,
          sourceVersion,
          expectedRevision: scopedRevision,
          bridgeSessionId,
          receiptIdentity,
          ...(visualAiReceipt ? { savedArtifactRef: suppliedRef } : {}),
        };
        let verified;
        if (visualAiReceipt) {
          const verification = await Promise.race([
            Promise.resolve().then(
              () => receiptIdentity && verifyAiReceipt(verificationInput),
            ).then(
              (result) => ({ kind: "verified", result }),
              () => ({ kind: "failed" }),
            ),
            verificationDeadline,
          ]);
          if (verification.kind !== "verified") {
            if (aiReceiptGeneration === record.aiReceiptGeneration) {
              record.aiReceiptGeneration += 1;
            }
            jsonResponse(response, 502, {
              ok: false,
              error: {
                code: "REVIEW_AI_RECEIPT_UNVERIFIED",
                message: "AI receipt verification did not complete authoritatively.",
              },
              savedArtifactRef: suppliedRef,
              aiReceiptStatus: "unverified",
              snapshotRevision: scopedRevision,
            });
            return;
          }
          verified = verification.result;
        } else {
          verified = receiptIdentity && await verifyAiReceipt(verificationInput);
        }
        const receiptRef = exactArtifactReference(
          verified?.receiptRef,
          "review-ai-receipt",
        );
        if (!verified?.verified || !receiptRef) {
          jsonResponse(response, 422, {
            ok: false,
            error: {
              code: "REVIEW_AI_RECEIPT_UNVERIFIED",
              message: "AI receipt could not be verified.",
            },
          });
          return;
        }
        if (
          visualAiReceipt
          && (
            aiReceiptGeneration !== record.aiReceiptGeneration
            || scopedRevision !== startingRevision
            || currentVisualArtifacts.get(suppliedRef) !== record
          )
        ) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_AI_RECEIPT_STALE",
              message: "The saved artifact or authoritative revision changed before the AI receipt could be recorded.",
            },
          });
          return;
        }
        const recordingInput = {
          operation: "record-review-ai-receipt",
          project_root: projectRoot,
          expected_revision: startingRevision,
          review_type: reviewType,
          review_session_id: reviewSessionId,
          ...(visualAiReceipt
            ? {
                source_version: sourceVersion,
                saved_artifact_ref: suppliedRef,
              }
            : {}),
          receipt_ref: receiptRef,
        };
        let payload;
        let authoritativeRevision;
        if (visualAiReceipt) {
          const operation = createAiRecording(
            record,
            aiReceiptGeneration,
            startingRevision,
            recordingInput,
            body,
          );
          record.aiReceiptRecording = operation;
          const recording = await attemptAiRecording(operation, verificationDeadline);
          if (recording.kind !== "received") {
            jsonResponse(response, 502, {
              ok: false,
              error: {
                code: "REVIEW_AI_RECEIPT_UNVERIFIED",
                message: "AI receipt recording did not complete authoritatively.",
              },
              savedArtifactRef: suppliedRef,
              aiReceiptStatus: "unverified",
              snapshotRevision: scopedRevision,
            });
            return;
          }
          authoritativeRevision = recording.snapshotRevision;
        } else {
          payload = await invokeBridge(recordingInput);
          authoritativeRevision = snapshotRevision(payload);
        }
        const responsePayload = {
          ok: true,
          ...(visualAiReceipt ? { savedArtifactRef: suppliedRef } : {}),
          aiReceiptStatus: "received",
          snapshotRevision: authoritativeRevision,
        };
        if (visualAiReceipt) {
          rememberRecoveryWrite(url.pathname, body, responsePayload);
        }
        jsonResponse(response, 200, responsePayload);
        } finally {
          clearTimeout(verificationTimeout);
          if (visualAiReceipt) record.aiReceiptInFlight = false;
        }
        return;
      }

      const visualWritePath = url.pathname === "/api/visual/anchor-feedback"
        || url.pathname === "/api/visual/marks";
      if (visualWritePath) {
        const replay = replayedVisualWrite(url.pathname, body);
        if (replay) {
          visualWriteResponse(response, replay);
          return;
        }
      }

      if (!scopeMatches(body)) {
        jsonResponse(response, 409, {
          ok: false,
          error: {
            code: "REVIEW_SCOPE_MISMATCH",
            message: "Review save does not match this source and revision.",
          },
        });
        return;
      }

      if (url.pathname === "/api/content/decision") {
        if (reviewType !== "content-full-deck") {
          jsonResponse(response, 409, { ok: false, error: { code: "REVIEW_TYPE_MISMATCH", message: "This is not a content review session." } });
          return;
        }
        const payload = await invokeBridge({
          operation: "save-content-page-decision",
          project_root: projectRoot,
          expected_revision: scopedRevision,
          review_session_id: reviewSessionId,
          source_version: sourceVersion,
          slide_id: body.slideId,
          decision: body.decision,
          comment: body.comment,
        });
        const result = payload?.result || {};
        jsonResponse(response, 200, {
          ok: true,
          decisionRef: result.decision_ref,
          decision: result.decision,
          snapshotRevision: snapshotRevision(payload),
        });
        return;
      }

      if (url.pathname === "/api/content/batch") {
        if (reviewType !== "content-full-deck") {
          jsonResponse(response, 409, { ok: false, error: { code: "REVIEW_TYPE_MISMATCH", message: "This is not a content review session." } });
          return;
        }
        const payload = await invokeBridge({
          operation: "submit-content-review-batch",
          project_root: projectRoot,
          expected_revision: scopedRevision,
          review_session_id: reviewSessionId,
          source_version: sourceVersion,
        });
        const result = payload?.result || {};
        jsonResponse(response, 200, {
          ok: true,
          batchRef: result.batch_ref,
          batch: result.batch,
          snapshotRevision: snapshotRevision(payload),
        });
        return;
      }

      if (reviewType !== "visual-professional") {
        jsonResponse(response, 409, { ok: false, error: { code: "REVIEW_TYPE_MISMATCH", message: "This is not a visual review session." } });
        return;
      }
      const anchor = url.pathname === "/api/visual/anchor-feedback";
      const payload = await invokeBridge({
        operation: anchor
          ? "submit-visual-anchor-feedback-batch"
          : "save-visual-contract-review-marks",
        project_root: projectRoot,
        expected_revision: scopedRevision,
        review_session_id: reviewSessionId,
        source_version: sourceVersion,
        [anchor ? "feedback" : "marks"]: anchor ? body.feedback : body.marks,
      });
      const result = payload?.result || {};
      const persistenceRevision = snapshotRevision(payload);
      const record = rememberVisualWrite(
        url.pathname,
        body,
        result,
        persistenceRevision,
      );
      await notificationFacts(result, record, response);
      visualWriteResponse(response, record);
    } catch (error) {
      jsonResponse(response, error?.status || statusForBridgeError(error), {
        ok: false,
        error: {
          code: error?.code || "REVIEW_BRIDGE_FAILURE",
          message:
            error?.status === 400 || error?.status === 413
              ? error.message
              : "Review Bridge could not complete the scoped operation.",
        },
      });
    }
  }

  async function stop() {
    if (sweepTimer) {
      clearInterval(sweepTimer);
      sweepTimer = null;
    }
    if (stopped && !server) return;
    stopped = true;
    const current = server;
    server = null;
    if (!current) return;
    await new Promise((resolve) => current.close(() => resolve()));
  }

  function sweep() {
    if (stopped) return;
    if (isExpired() || now() > leaseUntil) {
      stopped = true;
      const current = server;
      server = null;
      if (current) current.close();
    }
  }

  return {
    async start() {
      if (server || stopped) throw new Error("Review Bridge cannot be restarted");
      server = http.createServer((request, response) => {
        void handle(request, response);
      });
      await new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(0, LOOPBACK_HOST, resolve);
      });
      const address = server.address();
      if (!address || typeof address === "string") {
        await stop();
        throw new Error("Review Bridge did not receive a loopback port");
      }
      port = address.port;
      origin = `http://${LOOPBACK_HOST}:${port}`;
      sweepTimer = setInterval(sweep, Math.min(leaseMs, 1_000));
      sweepTimer.unref();
      return {
        host: LOOPBACK_HOST,
        port,
        origin,
        token,
        url: `${origin}/#token=${encodeURIComponent(token)}`,
        expiresAt,
        projectRoot,
        reviewType,
        sourceVersion,
        expectedRevision: scopedRevision,
        reviewSessionId,
        bridgeSessionId,
      };
    },
    stop,
    sweep,
    isActive() {
      return !stopped && !isExpired() && now() <= leaseUntil;
    },
    isStopped() {
      return stopped;
    },
  };
}
