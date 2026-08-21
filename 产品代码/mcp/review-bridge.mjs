import { randomBytes } from "node:crypto";
import http from "node:http";

const LOOPBACK_HOST = "127.0.0.1";
const MAX_BODY_BYTES = 2 * 1024 * 1024;
const SECURITY_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
});

function apiCsp() {
  return "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; connect-src 'self'";
}

function jsonResponse(response, status, payload, extraHeaders = {}) {
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
  let result = "";
  let cursor = 0;
  let rawTextTag = "";
  const lower = html.toLowerCase();
  while (cursor < html.length) {
    if (rawTextTag) {
      const closeAt = lower.indexOf(`</${rawTextTag}`, cursor);
      if (closeAt < 0) return result + html.slice(cursor);
      result += html.slice(cursor, closeAt);
      cursor = closeAt;
      rawTextTag = "";
      continue;
    }
    const tagAt = html.indexOf("<", cursor);
    if (tagAt < 0) return result + html.slice(cursor);
    result += html.slice(cursor, tagAt);
    const tagEnd = html.indexOf(">", tagAt + 1);
    if (tagEnd < 0) return result + html.slice(tagAt);
    let tag = html.slice(tagAt, tagEnd + 1);
    const opening = tag.match(/^<\s*(script|style)\b/i);
    if (opening) {
      if (!/\bnonce\s*=/i.test(tag)) {
        const nameEnd = opening[0].length;
        tag = `${tag.slice(0, nameEnd)} nonce="${nonce}"${tag.slice(nameEnd)}`;
      }
      if (!/\/\s*>$/.test(tag)) rawTextTag = opening[1].toLowerCase();
    }
    result += tag;
    cursor = tagEnd + 1;
  }
  return result;
}

function statusForBridgeError(error) {
  if (error?.code === "REVISION_CONFLICT" || error?.code === "REVIEW_SOURCE_STALE") {
    return 409;
  }
  if (error?.code === "VALIDATION_ERROR") return 422;
  return 502;
}

function normalizedEvidenceScope(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const scope = {
    slideId: String(value.slideId || "").trim(),
    evidenceId: String(value.evidenceId || "").trim(),
    materialRef: String(value.materialRef || "").trim(),
    assetRef: String(value.assetRef || "").trim(),
  };
  return Object.values(scope).every(Boolean) ? scope : null;
}

function adjacentSlideSummary(slide) {
  if (!slide) return null;
  return {
    slide_id: String(slide.slide_id || ""),
    order: Number(slide.order || 0),
    neutral_title: String(slide.neutral_title || ""),
    page_task: String(slide.page_task || ""),
  };
}

function buildContentEvidenceProjection(review, scope, evidenceAsset) {
  const slides = Array.isArray(review?.slides) ? review.slides : [];
  const index = slides.findIndex((slide) => String(slide?.slide_id || "") === scope.slideId);
  const slide = index >= 0 ? slides[index] : null;
  const evidenceItems = Array.isArray(slide?.evidence_items) ? slide.evidence_items : [];
  const evidence = evidenceItems.find((item) =>
    String(item?.evidence_id || "") === scope.evidenceId
    && String(item?.material_ref || "") === scope.materialRef
    && String(item?.asset_ref || "") === scope.assetRef
  );
  if (!slide || !evidence) return null;
  return {
    review_type: "content-evidence",
    display_policy: "content-evidence-read-only",
    project_id: String(review.project_id || ""),
    project_name: String(review.project_name || review.project_id || "内容项目"),
    title: `${String(slide.neutral_title || slide.slide_id)} · 材料证据`,
    revision: Number(review.revision || 0),
    status: "read-only",
    gate_status: review.gate_status || {},
    source_version: String(review.source_version || ""),
    source_refs: [scope.materialRef, scope.assetRef],
    sections: [],
    outline: [],
    mark_set: { status: "read-only", marks: [] },
    capabilities: {
      canSavePageDecision: false,
      canSaveReviewMarks: false,
      canCompareSourceAndSlide: true,
      canCompareAdjacentSlides: true,
    },
    evidence_view: {
      slide,
      evidence,
      asset: evidenceAsset || null,
      adjacent: {
        previous: adjacentSlideSummary(slides[index - 1]),
        next: adjacentSlideSummary(slides[index + 1]),
      },
    },
  };
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
  const sourceVersion = String(options.sourceVersion || "").trim();
  const expectedRevision = Number(options.expectedRevision);
  const evidenceScope = normalizedEvidenceScope(options.evidenceScope);
  const evidenceAsset = options.evidenceAsset || null;
  if (
    !projectRoot ||
    !["content", "visual", "content-evidence"].includes(reviewType) ||
    !sourceVersion ||
    !Number.isInteger(expectedRevision) ||
    expectedRevision < 0 ||
    (reviewType === "content-evidence" && !evidenceScope)
  ) {
    throw new TypeError("Review Bridge scope is invalid");
  }
  const invokeBridge = options.invokeBridge;
  const readReviewHtml = options.readReviewHtml;
  const createReviewSession = options.createReviewSession;
  const now = options.now || Date.now;
  const ttlMs = Math.max(1, Number(options.ttlMs || 5 * 60_000));
  const leaseMs = Math.max(1, Number(options.leaseMs || 30_000));
  const token = randomBytes(32).toString("base64url");
  const createdAt = now();
  const expiresAt = createdAt + ttlMs;
  let leaseUntil = createdAt + leaseMs;
  let server = null;
  let port = 0;
  let origin = "";
  let stopped = false;
  let activated = false;
  let sweepTimer = null;

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
    activated = true;
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
    const evidenceReadOnly = reviewType === "content-evidence";
    const allowed =
      (url.pathname === "/api/review" && method === "GET") ||
      (!evidenceReadOnly && url.pathname === "/api/marks" && method === "POST") ||
      (!evidenceReadOnly && url.pathname === "/api/switch" && method === "POST") ||
      (url.pathname === "/api/heartbeat" && method === "POST");
    if (!allowed) {
      const knownPath = ["/api/review", "/api/marks", "/api/switch", "/api/heartbeat"].includes(
        url.pathname,
      );
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
        const payload = await invokeBridge({
          operation: evidenceReadOnly
            ? "get-content-sidebar-review-projection"
            : "get-review-projection",
          project_root: projectRoot,
          ...(evidenceReadOnly ? {} : { review_type: reviewType }),
        });
        if (
          payload?.review?.source_version !== sourceVersion ||
          payload?.snapshot_revision !== expectedRevision
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
        const projectedReview = evidenceReadOnly
          ? buildContentEvidenceProjection(payload.review, evidenceScope, evidenceAsset)
          : payload.review;
        if (!projectedReview) {
          jsonResponse(response, 409, {
            ok: false,
            error: {
              code: "REVIEW_SOURCE_STALE",
              message: "Scoped content evidence no longer matches this session.",
            },
          });
          return;
        }
        jsonResponse(response, 200, {
          ok: true,
          projectRoot,
          reviewType,
          sourceVersion,
          expectedRevision,
          review: projectedReview,
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

      if (url.pathname === "/api/switch") {
        const body = await readJsonBody(request);
        const targetReviewType = String(body.reviewType || "");
        if (
          !["content", "visual"].includes(targetReviewType) ||
          targetReviewType === reviewType
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
        body.expectedRevision !== expectedRevision ||
        body.sourceVersion !== sourceVersion ||
        !Array.isArray(body.marks)
      ) {
        jsonResponse(response, 409, {
          ok: false,
          error: {
            code: "REVIEW_SCOPE_MISMATCH",
            message: "Review save does not match this source and revision.",
          },
        });
        return;
      }
      const payload = await invokeBridge({
        operation: "save-review-marks",
        project_root: projectRoot,
        expected_revision: expectedRevision,
        review_type: reviewType,
        source_version: sourceVersion,
        marks: body.marks,
      });
      jsonResponse(response, 200, {
        ok: true,
        status: "saved",
        snapshotRevision: payload?.result?.snapshot?.revision,
      });
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
    if (isExpired() || (activated && now() > leaseUntil)) {
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
      server.unref();
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
        expectedRevision,
        evidenceScope,
      };
    },
    stop,
    sweep,
    isActive() {
      return !stopped && !isExpired() && (!activated || now() <= leaseUntil);
    },
    isStopped() {
      return stopped;
    },
  };
}
