import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { readProjectAsset } from "../mcp/project-asset.mjs";
import * as reviewBridgeModule from "../mcp/review-bridge.mjs";

const { createReviewBridge } = reviewBridgeModule;

const review = {
  review_type: "content-full-deck",
  review_session_id: "content-session-1",
  project_id: "p1",
  project_name: "测试项目",
  source_version:
    "artifact://content-blueprint/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  revision: 7,
  slides: [{
    slide_id: "S01",
    order: 1,
    section_id: "problem",
    page_task: "确认现状边界",
    reading_question: "现有材料能否支持当前判断？",
    neutral_title: "当前流程断点与证据边界",
    customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
    visible_copy_blocks: [{ block_id: "copy-1", text: "当前流程存在待核实断点。" }],
    material_views: [{ material_view_id: "S01-M01", asset_ref: "review-assets/content/S01-M01.png" }],
  }],
  sections: [],
  outline: [],
  mark_set: { marks: [] },
};

const visualReview = {
  review_type: "visual-professional",
  review_session_id: "visual-session-1",
  project_id: "p1",
  source_version: "visual-v1",
  revision: 7,
  anchors: [],
  slide_visual_contracts: [],
};

const ANCHOR_BATCH_REF = "artifact://visual-anchor-feedback-batch/" + "a".repeat(64);
const CONTRACT_MARK_SET_REF = "artifact://visual-contract-review-mark-set/" + "b".repeat(64);

function visualReviewWithSavedArtifacts() {
  return {
    ...visualReview,
    anchor_feedback_batch_ref: ANCHOR_BATCH_REF,
    anchor_feedback_batch: {
      batch_id: "saved-anchor-batch",
      items: [],
      persistence_status: "saved",
      host_notification_status: "unavailable",
      ai_receipt_status: "unverified",
    },
    contract_review_marks_ref: CONTRACT_MARK_SET_REF,
    contract_review_marks: {
      mark_set_id: "saved-contract-marks",
      marks: [],
      persistence_status: "saved",
      host_notification_status: "unavailable",
      ai_receipt_status: "unverified",
    },
  };
}
async function startedBridge(options = {}) {
  const {
    review: suppliedReview = review,
    invokeBridge: suppliedInvokeBridge,
    ...bridgeOptions
  } = options;
  const calls = [];
  let authoritativeRevision = 7;
  const invokeBridge = suppliedInvokeBridge || (async (request) => {
    calls.push(request);
    if (["get-content-review-projection", "get-visual-review-projection"].includes(request.operation)) {
      return {
        ok: true,
        selected_project_root: bridgeOptions.projectRoot || "/managed/project",
        review: suppliedReview,
        snapshot_revision: authoritativeRevision,
      };
    }
    authoritativeRevision += 1;
    const snapshot = { revision: authoritativeRevision };
    if (request.operation === "save-content-page-decision") {
      return { ok: true, result: { decision_ref: "content-page-decision:v1", decision: { slide_id: request.slide_id, decision: request.decision, comment: request.comment, status: "completed" }, snapshot } };
    }
    if (request.operation === "submit-content-review-batch") {
      return { ok: true, result: { batch_ref: "content-review-batch:v1", batch: { status: "submitted", immutable_after_submit: true }, snapshot } };
    }
    if (request.operation === "submit-visual-anchor-feedback-batch") {
      return { ok: true, result: { batch_ref: ANCHOR_BATCH_REF, batch: { items: request.feedback, persistence_status: "saved", host_notification_status: "not-requested", ai_receipt_status: "pending" }, snapshot } };
    }
    if (request.operation === "save-visual-contract-review-marks") {
      return { ok: true, result: { mark_set_ref: CONTRACT_MARK_SET_REF, mark_set: { marks: request.marks, persistence_status: "saved", host_notification_status: "not-requested", ai_receipt_status: "pending" }, snapshot } };
    }
    return { ok: true, result: { session_ref: "review-session:v1", session: {}, snapshot } };
  });
  const bridge = createReviewBridge({
    projectRoot: "/managed/project",
    reviewType: suppliedReview.review_type,
    reviewSessionId: suppliedReview.review_session_id,
    sourceVersion: suppliedReview.source_version,
    expectedRevision: 7,
    ttlMs: 10_000,
    leaseMs: 500,
    readReviewHtml: async () =>
      "<!doctype html><html><head><style>body{margin:0}</style></head><body><div id=\"root\"></div><script>window.__reviewBrowserShell=true;</script></body></html>",
    invokeBridge,
    ...bridgeOptions,
  });
  const session = await bridge.start();
  return { bridge, session, calls };
}

function bearer(session) {
  return { Authorization: `Bearer ${session.token}` };
}

function requestWithHost(session, host) {
  return new Promise((resolve, reject) => {
    const request = http.request(
      {
        hostname: session.host,
        port: session.port,
        path: "/api/review",
        method: "GET",
        headers: {
          ...bearer(session),
          Host: host,
        },
      },
      (response) => {
        response.resume();
        response.once("end", () => resolve(response.statusCode));
      },
    );
    request.once("error", reject);
    request.end();
  });
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function visualProjection(assetRef, options = {}) {
  return {
    ok: true,
    selected_project_root: options.selectedProjectRoot ?? "/managed/project",
    review: {
      ...visualReview,
      anchors: assetRef ? [{ slide_id: "S01", asset_ref: assetRef }] : [],
      ...(options.reviewOverrides || {}),
    },
    snapshot_revision: options.snapshotRevision ?? 7,
  };
}

test("collectProjectionAssetRefs trims, deduplicates, and only reads closed projection fields", () => {
  assert.equal(typeof reviewBridgeModule.collectProjectionAssetRefs, "function");

  const refs = reviewBridgeModule.collectProjectionAssetRefs({
    slides: [{
      slide_id: "S01",
      asset_ref: "ignored-slide.png",
      material_views: [
        { asset_ref: " review-assets/content/S01-M01.png " },
        { asset_ref: "review-assets/content/S01-M01.png" },
        { asset_ref: "   " },
        { asset_ref: null },
      ],
    }, {
      slide_id: "S02",
      material_views: [],
    }],
    anchors: [{
      slide_id: "S01",
      asset_ref: " legacy.png ",
      current_asset_ref: " current.png ",
      previous_asset_ref: " previous.png ",
      preview_url: "ignored-preview.png",
      nested: { asset_ref: "ignored-nested.png" },
    }, {
      slide_id: "S02",
      asset_ref: "legacy.png",
      current_asset_ref: "",
      previous_asset_ref: undefined,
    }],
    unrelated: {
      asset_ref: "ignored-unrelated.png",
      nested: { private_asset_ref: "private-material.png" },
    },
  });

  assert.ok(refs instanceof Set);
  assert.deepEqual([...refs], [
    "review-assets/content/S01-M01.png",
    "legacy.png",
    "current.png",
    "previous.png",
  ]);
  assert.equal(refs.has("private-material.png"), false);
});

test("Review Bridge binds only loopback and keeps the token in the URL fragment", async () => {
  const { bridge, session } = await startedBridge();
  try {
    assert.equal(session.host, "127.0.0.1");
    assert.ok(session.port > 0);
    assert.match(session.url, /^http:\/\/127\.0\.0\.1:\d+\/#token=/);
    assert.equal(new URL(session.url).search, "");
    assert.equal(new URL(session.url).hash.includes(session.token), true);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge reads the fixed projection with Bearer and security headers", async () => {
  const { bridge, session, calls } = await startedBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/api/review`, {
      headers: bearer(session),
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    assert.match(response.headers.get("content-security-policy"), /default-src 'none'/);
    const payload = await response.json();
    assert.equal(payload.review.source_version, review.source_version);
    assert.equal(
      payload.review.slides[0].customerJudgment,
      "客户确认现状边界后，再判断是否进入联合方案验证。",
    );
    assert.deepEqual(Object.keys(payload.review.slides[0]), [
      "slide_id",
      "order",
      "section_id",
      "page_task",
      "reading_question",
      "neutral_title",
      "customerJudgment",
      "visible_copy_blocks",
      "material_views",
    ]);
    assert.deepEqual(
      Object.keys(payload.review.slides[0].visible_copy_blocks[0]),
      ["block_id", "text"],
    );
    assert.deepEqual(
      Object.keys(payload.review.slides[0].material_views[0]),
      ["material_view_id", "asset_ref"],
    );
    assert.equal(calls.at(-1).operation, "get-content-review-projection");
    assert.equal(calls.at(-1).review_session_id, "content-session-1");
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge reads all declared visual anchor asset fields and no other projection asset", async () => {
  const assetRefs = [
    "renders/anchors/S01-legacy.png",
    "renders/anchors/S01-current.png",
    "renders/anchors/S01-previous.png",
  ];
  const reads = [];
  const { bridge, session } = await startedBridge({
    review: {
      ...visualReview,
      anchors: [{
        slide_id: "S01",
        asset_ref: ` ${assetRefs[0]} `,
        current_asset_ref: ` ${assetRefs[1]} `,
        previous_asset_ref: assetRefs[2],
      }],
    },
    readProjectAsset: ({ projectRoot, assetRef: requested }) => {
      reads.push({ projectRoot, assetRef: requested });
      return {
        assetRef: requested,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    await fetch(`${origin}/api/review`, { headers: bearer(session) });
    for (const assetRef of assetRefs) {
      const response = await fetch(
        `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
        { headers: bearer(session) },
      );
      assert.equal(response.status, 200, assetRef);
      assert.equal((await response.json()).asset.assetRef, assetRef);
    }
    assert.deepEqual(reads, assetRefs.map((assetRef) => ({
      projectRoot: "/managed/project",
      assetRef,
    })));

    const rejected = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent("review-assets/content/S01-M01.png")}`,
      { headers: bearer(session) },
    );
    assert.equal(rejected.status, 404);
    assert.equal(reads.length, 3);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge allows content material assets only after the fixed projection is read", async () => {
  const assetRef = "review-assets/content/S01-M01.png";
  const reads = [];
  const { bridge, session } = await startedBridge({
    review: {
      ...review,
      slides: [{
        slide_id: "S01",
        material_views: [{ asset_ref: ` ${assetRef} ` }, { asset_ref: "" }],
      }],
    },
    readProjectAsset: ({ projectRoot, assetRef: requested }) => {
      reads.push({ projectRoot, assetRef: requested });
      return {
        assetRef: requested,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const beforeProjection = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    );
    assert.equal(beforeProjection.status, 404);
    assert.equal(reads.length, 0);

    const projection = await fetch(`${origin}/api/review`, { headers: bearer(session) });
    assert.equal(projection.status, 200);
    const allowed = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    );
    assert.equal(allowed.status, 200);
    assert.deepEqual(reads, [{ projectRoot: "/managed/project", assetRef }]);

    const fromAnotherProjection = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent("renders/anchors/S01-current.png")}`,
      { headers: bearer(session) },
    );
    assert.equal(fromAnotherProjection.status, 404);
    assert.equal(reads.length, 1);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge keeps zero-image content pages out of the asset allowlist", async () => {
  const allowedRef = "review-assets/content/S01-M01.png";
  const absentRef = "review-assets/content/S02-M01.png";
  const reads = [];
  const { bridge, session } = await startedBridge({
    review: {
      ...review,
      slides: [{
        ...review.slides[0],
        material_views: [{ material_view_id: "S01-M01", asset_ref: allowedRef }],
      }, {
        ...review.slides[0],
        slide_id: "S02",
        order: 2,
        material_views: [],
      }],
    },
    readProjectAsset: ({ projectRoot, assetRef }) => {
      reads.push({ projectRoot, assetRef });
      return {
        assetRef,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });

    const allowed = await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(allowedRef)}`,
      { headers: bearer(session) },
    );
    const absent = await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(absentRef)}`,
      { headers: bearer(session) },
    );

    assert.equal(allowed.status, 200);
    assert.equal(absent.status, 404);
    assert.deepEqual(reads, [{
      projectRoot: "/managed/project",
      assetRef: allowedRef,
    }]);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge revokes the previous asset allowlist when projection refresh is stale", async () => {
  const assetRef = "old.png";
  const reads = [];
  let projectionReads = 0;
  const { bridge, session } = await startedBridge({
    review: {
      ...visualReview,
      anchors: [{ slide_id: "S01", asset_ref: assetRef }],
    },
    invokeBridge: async (request) => {
      assert.equal(request.operation, "get-visual-review-projection");
      projectionReads += 1;
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: projectionReads === 1
          ? { ...visualReview, anchors: [{ slide_id: "S01", asset_ref: assetRef }] }
          : { ...visualReview, source_version: "visual-stale", anchors: [] },
        snapshot_revision: 7,
      };
    },
    readProjectAsset: ({ projectRoot, assetRef: requested }) => {
      reads.push({ projectRoot, assetRef: requested });
      return {
        assetRef: requested,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    assert.equal((await fetch(`${origin}/api/review`, { headers: bearer(session) })).status, 200);
    assert.equal((await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    )).status, 200);
    assert.equal(reads.length, 1);

    const stale = await fetch(`${origin}/api/review`, { headers: bearer(session) });
    assert.equal(stale.status, 409);
    assert.equal((await stale.json()).error.code, "REVIEW_SOURCE_STALE");
    const revoked = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    );
    assert.equal(revoked.status, 404);
    assert.equal((await revoked.json()).error.code, "ASSET_NOT_ALLOWLISTED");
    assert.equal(reads.length, 1);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge revokes the previous asset allowlist when projection refresh fails", async () => {
  const assetRef = "old.png";
  const reads = [];
  let projectionReads = 0;
  const { bridge, session } = await startedBridge({
    review: {
      ...visualReview,
      anchors: [{ slide_id: "S01", asset_ref: assetRef }],
    },
    invokeBridge: async (request) => {
      assert.equal(request.operation, "get-visual-review-projection");
      projectionReads += 1;
      if (projectionReads === 2) throw new Error("Runtime projection read failed");
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: { ...visualReview, anchors: [{ slide_id: "S01", asset_ref: assetRef }] },
        snapshot_revision: 7,
      };
    },
    readProjectAsset: ({ projectRoot, assetRef: requested }) => {
      reads.push({ projectRoot, assetRef: requested });
      return {
        assetRef: requested,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    assert.equal((await fetch(`${origin}/api/review`, { headers: bearer(session) })).status, 200);
    assert.equal((await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    )).status, 200);
    assert.equal(reads.length, 1);

    assert.equal((await fetch(`${origin}/api/review`, { headers: bearer(session) })).status, 502);
    const revoked = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
      { headers: bearer(session) },
    );
    assert.equal(revoked.status, 404);
    assert.equal((await revoked.json()).error.code, "ASSET_NOT_ALLOWLISTED");
    assert.equal(reads.length, 1);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge does not publish an older success when a newer projection request later fails", async () => {
  const oldProjection = deferred();
  const newProjection = deferred();
  const invoked = [deferred(), deferred()];
  const reads = [];
  let invocation = 0;
  const { bridge, session } = await startedBridge({
    review: { ...visualReview, anchors: [] },
    invokeBridge: (request) => {
      assert.equal(request.operation, "get-visual-review-projection");
      const index = invocation;
      invocation += 1;
      invoked[index].resolve();
      return [oldProjection.promise, newProjection.promise][index];
    },
    readProjectAsset: ({ assetRef }) => {
      reads.push(assetRef);
      return { assetRef, mimeType: "image/png", bytes: 3, dataBase64: "YWJj" };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const oldResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[0].promise;
    const newResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[1].promise;

    oldProjection.resolve(visualProjection("A-old.png"));
    const oldResponse = await oldResponsePromise;
    newProjection.reject(new Error("newer projection failed"));
    const newResponse = await newResponsePromise;

    assert.equal(oldResponse.status, 409);
    assert.equal((await oldResponse.json()).error.code, "REVIEW_PROJECTION_SUPERSEDED");
    assert.equal(newResponse.status, 502);
    for (const assetRef of ["A-old.png", "B-new.png"]) {
      const asset = await fetch(
        `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
        { headers: bearer(session) },
      );
      assert.equal(asset.status, 404, assetRef);
      assert.equal((await asset.json()).error.code, "ASSET_NOT_ALLOWLISTED");
    }
    assert.deepEqual(reads, []);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge keeps only a newer successful projection when an older success resolves late", async () => {
  const oldProjection = deferred();
  const newProjection = deferred();
  const invoked = [deferred(), deferred()];
  const reads = [];
  let invocation = 0;
  const { bridge, session } = await startedBridge({
    review: { ...visualReview, anchors: [] },
    invokeBridge: (request) => {
      assert.equal(request.operation, "get-visual-review-projection");
      const index = invocation;
      invocation += 1;
      invoked[index].resolve();
      return [oldProjection.promise, newProjection.promise][index];
    },
    readProjectAsset: ({ assetRef }) => {
      reads.push(assetRef);
      return { assetRef, mimeType: "image/png", bytes: 3, dataBase64: "YWJj" };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const oldResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[0].promise;
    const newResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[1].promise;

    newProjection.resolve(visualProjection("B-new.png"));
    const newResponse = await newResponsePromise;
    oldProjection.resolve(visualProjection("A-old.png"));
    const oldResponse = await oldResponsePromise;

    assert.equal(newResponse.status, 200);
    assert.equal(oldResponse.status, 409);
    assert.equal((await oldResponse.json()).error.code, "REVIEW_PROJECTION_SUPERSEDED");
    const current = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent("B-new.png")}`,
      { headers: bearer(session) },
    );
    assert.equal(current.status, 200);
    const superseded = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent("A-old.png")}`,
      { headers: bearer(session) },
    );
    assert.equal(superseded.status, 404);
    assert.equal((await superseded.json()).error.code, "ASSET_NOT_ALLOWLISTED");
    assert.deepEqual(reads, ["B-new.png"]);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge bounds a never-settling projection and prevents its late result from publishing", async () => {
  const lateProjection = deferred();
  let projectionReads = 0;
  const oldAsset = "review-assets/old-timeout.png";
  const currentAsset = "review-assets/current-after-timeout.png";
  const invokeBridge = (request) => {
    if (request.operation !== "get-visual-review-projection") {
      throw new Error(`unexpected operation ${request.operation}`);
    }
    projectionReads += 1;
    if (projectionReads === 1) return lateProjection.promise;
    return Promise.resolve(visualProjection(currentAsset));
  };
  const { bridge, session } = await startedBridge({
    review: visualReview,
    invokeBridge,
    projectionTimeoutMs: 20,
    readProjectAsset: async ({ assetRef }) => ({
      assetRef,
      mimeType: "image/png",
      bytes: 3,
      dataBase64: "YWJj",
    }),
  });
  const controller = new AbortController();
  try {
    const bounded = await Promise.race([
      fetch(`${session.origin}/api/review`, {
        headers: bearer(session),
        signal: controller.signal,
      }),
      new Promise((resolve) => setTimeout(() => resolve("still-loading"), 100)),
    ]);
    assert.notEqual(bounded, "still-loading");
    assert.equal(bounded.status, 504);
    assert.equal((await bounded.json()).error.code, "REVIEW_PROJECTION_TIMEOUT");

    lateProjection.resolve(visualProjection(oldAsset));
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    assert.equal((await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(oldAsset)}`,
      { headers: bearer(session) },
    )).status, 404);
    assert.equal((await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(currentAsset)}`,
      { headers: bearer(session) },
    )).status, 200);
  } finally {
    controller.abort();
    lateProjection.resolve(visualProjection(oldAsset));
    await bridge.stop();
  }
});

test("Review Bridge abandons a client-aborted projection without publishing its late allowlist", async () => {
  const lateProjection = deferred();
  const firstStarted = deferred();
  let projectionReads = 0;
  const oldAsset = "review-assets/old-aborted.png";
  const currentAsset = "review-assets/current-after-abort.png";
  const invokeBridge = (request) => {
    if (request.operation !== "get-visual-review-projection") {
      throw new Error(`unexpected operation ${request.operation}`);
    }
    projectionReads += 1;
    if (projectionReads === 1) {
      firstStarted.resolve();
      return lateProjection.promise;
    }
    return Promise.resolve(visualProjection(currentAsset));
  };
  const { bridge, session } = await startedBridge({
    review: visualReview,
    invokeBridge,
    projectionTimeoutMs: 1_000,
    readProjectAsset: async ({ assetRef }) => ({
      assetRef,
      mimeType: "image/png",
      bytes: 3,
      dataBase64: "YWJj",
    }),
  });
  try {
    const aborted = new Promise((resolve) => {
      const request = http.request({
        hostname: session.host,
        port: session.port,
        path: "/api/review",
        method: "GET",
        headers: bearer(session),
      });
      request.once("error", resolve);
      request.once("close", resolve);
      request.end();
      void firstStarted.promise.then(() => request.destroy());
    });
    await aborted;

    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    lateProjection.resolve(visualProjection(oldAsset));
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal((await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(oldAsset)}`,
      { headers: bearer(session) },
    )).status, 404);
    assert.equal((await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(currentAsset)}`,
      { headers: bearer(session) },
    )).status, 200);
  } finally {
    lateProjection.resolve(visualProjection(oldAsset));
    await bridge.stop();
  }
});

test("Review Bridge does not let an older success publish after a newer stale projection", async () => {
  const oldProjection = deferred();
  const newProjection = deferred();
  const invoked = [deferred(), deferred()];
  const reads = [];
  let invocation = 0;
  const { bridge, session } = await startedBridge({
    review: { ...visualReview, anchors: [] },
    invokeBridge: (request) => {
      assert.equal(request.operation, "get-visual-review-projection");
      const index = invocation;
      invocation += 1;
      invoked[index].resolve();
      return [oldProjection.promise, newProjection.promise][index];
    },
    readProjectAsset: ({ assetRef }) => {
      reads.push(assetRef);
      return { assetRef, mimeType: "image/png", bytes: 3, dataBase64: "YWJj" };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const oldResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[0].promise;
    const newResponsePromise = fetch(`${origin}/api/review`, { headers: bearer(session) });
    await invoked[1].promise;

    newProjection.resolve(visualProjection("B-stale.png", {
      reviewOverrides: { source_version: "visual-stale" },
    }));
    const newResponse = await newResponsePromise;
    oldProjection.resolve(visualProjection("A-old.png"));
    const oldResponse = await oldResponsePromise;

    assert.equal(newResponse.status, 409);
    assert.equal((await newResponse.json()).error.code, "REVIEW_SOURCE_STALE");
    assert.equal(oldResponse.status, 409);
    assert.equal((await oldResponse.json()).error.code, "REVIEW_PROJECTION_SUPERSEDED");
    const asset = await fetch(
      `${origin}/api/asset?assetRef=${encodeURIComponent("A-old.png")}`,
      { headers: bearer(session) },
    );
    assert.equal(asset.status, 404);
    assert.equal((await asset.json()).error.code, "ASSET_NOT_ALLOWLISTED");
    assert.deepEqual(reads, []);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge rejects projections that mismatch the fixed project, review type, or session", async () => {
  const cases = [{
    name: "project root",
    payload: visualProjection("malicious.png", { selectedProjectRoot: "/another/project" }),
  }, {
    name: "review type",
    payload: visualProjection("malicious.png", {
      reviewOverrides: { review_type: "content-full-deck" },
    }),
  }, {
    name: "review session",
    payload: visualProjection("malicious.png", {
      reviewOverrides: { review_session_id: "another-session" },
    }),
  }];

  for (const scenario of cases) {
    const reads = [];
    const { bridge, session } = await startedBridge({
      review: { ...visualReview, anchors: [] },
      invokeBridge: async () => scenario.payload,
      readProjectAsset: ({ assetRef }) => {
        reads.push(assetRef);
        return { assetRef, mimeType: "image/png", bytes: 3, dataBase64: "YWJj" };
      },
    });
    try {
      const origin = `http://${session.host}:${session.port}`;
      const projection = await fetch(`${origin}/api/review`, { headers: bearer(session) });
      assert.equal(projection.status, 409, scenario.name);
      assert.equal((await projection.json()).error.code, "REVIEW_SCOPE_MISMATCH", scenario.name);
      const asset = await fetch(
        `${origin}/api/asset?assetRef=${encodeURIComponent("malicious.png")}`,
        { headers: bearer(session) },
      );
      assert.equal(asset.status, 404, scenario.name);
      assert.equal((await asset.json()).error.code, "ASSET_NOT_ALLOWLISTED", scenario.name);
      assert.deepEqual(reads, [], scenario.name);
    } finally {
      await bridge.stop();
    }
  }
});

test("Review Bridge keeps declared traversal and URI-like assets behind readProjectAsset safety", async () => {
  const projectRoot = mkdtempSync(path.join(tmpdir(), "ai-ppt-review-asset-"));
  writeFileSync(
    path.join(projectRoot, "project.json"),
    JSON.stringify({ project_root: projectRoot, project_id: "p1", name: "review asset" }),
  );
  const unsafeRefs = [
    "../../outside.png",
    "file:///etc/passwd",
    "https://example.com/remote.png",
    "asset://anchor/S01",
  ];
  const { bridge, session } = await startedBridge({
    projectRoot,
    review: {
      ...visualReview,
      anchors: [{
        slide_id: "S01",
        asset_ref: unsafeRefs[0],
        current_asset_ref: unsafeRefs[1],
        previous_asset_ref: unsafeRefs[2],
      }, {
        slide_id: "S02",
        asset_ref: unsafeRefs[3],
      }],
    },
    readProjectAsset,
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    assert.equal((await fetch(`${origin}/api/review`, { headers: bearer(session) })).status, 200);
    for (const assetRef of unsafeRefs) {
      const response = await fetch(
        `${origin}/api/asset?assetRef=${encodeURIComponent(assetRef)}`,
        { headers: bearer(session) },
      );
      assert.equal(response.status, 404, assetRef);
      assert.equal((await response.json()).error.code, "ASSET_UNAVAILABLE");
    }
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge serves only the fixed Browser shell with nonce CSP", async () => {
  const { bridge, session } = await startedBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    const csp = response.headers.get("content-security-policy");
    assert.match(csp, /script-src 'nonce-[^']+'/);
    assert.match(csp, /style-src 'nonce-[^']+'/);
    assert.match(csp, /connect-src 'self'/);
    const html = await response.text();
    assert.match(html, /<script nonce="[^"]+">/);
    assert.match(html, /<style nonce="[^"]+">/);
    assert.doesNotMatch(html, /short-lived-token|Authorization/);

    const asset = await fetch(`${origin}/assets/anything.js`);
    assert.equal(asset.status, 404);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge adds nonces only to real HTML tags, not script string literals", async () => {
  const { bridge, session } = await startedBridge({
    readReviewHtml: async () =>
      '<!doctype html><html><body><script>const fakeClose = "</script-not-real>"; const example = "<script data-example>"; window.example = example;</script></body></html>',
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/`);
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /<script nonce="[^"]+">const fakeClose/);
    assert.match(html, /const fakeClose = "<\/script-not-real>"/);
    assert.match(html, /const example = "<script data-example>"/);
    assert.doesNotMatch(html, /const example = "<script nonce=/);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge rejects wrong bearer, Host, Origin, methods, and path traversal", async () => {
  const { bridge, session } = await startedBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const wrongBearer = await fetch(`${origin}/api/review`, {
      headers: { Authorization: "Bearer wrong" },
    });
    assert.equal(wrongBearer.status, 401);

    const wrongHostStatus = await requestWithHost(
      session,
      `localhost:${session.port}`,
    );
    assert.equal(wrongHostStatus, 421);

    const wrongOrigin = await fetch(`${origin}/api/content/decision`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: "http://evil.invalid",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        sourceVersion: review.source_version,
        reviewSessionId: "content-session-1",
        slideId: "S01",
        decision: "approved",
        comment: "",
      }),
    });
    assert.equal(wrongOrigin.status, 403);

    const method = await fetch(`${origin}/api/review`, {
      method: "PUT",
      headers: bearer(session),
    });
    assert.equal(method.status, 405);

    const traversal = await fetch(`${origin}/..%2F..%2Fsecret`, {
      headers: bearer(session),
    });
    assert.equal(traversal.status, 404);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge forwards content decisions and batches as exact sequential Python operations", async () => {
  const { bridge, session, calls } = await startedBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const decision = await fetch(`${origin}/api/content/decision`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        sourceVersion: review.source_version,
        reviewSessionId: "content-session-1",
        slideId: "S01",
        decision: "modify",
        comment: "补充身份说明",
      }),
    });
    assert.equal(decision.status, 200);
    assert.equal(calls.at(-1).operation, "save-content-page-decision");
    assert.equal(calls.at(-1).expected_revision, 7);
    assert.equal(calls.at(-1).source_version, review.source_version);
    assert.equal((await decision.json()).decisionRef, "content-page-decision:v1");

    const batch = await fetch(`${origin}/api/content/batch`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({
        expectedRevision: 8,
        sourceVersion: review.source_version,
        reviewSessionId: "content-session-1",
      }),
    });
    assert.equal(batch.status, 200);
    assert.equal(calls.at(-1).operation, "submit-content-review-batch");
    assert.equal(calls.at(-1).expected_revision, 8);
    assert.equal((await batch.json()).snapshotRevision, 9);

    const stale = await fetch(`${origin}/api/content/batch`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        sourceVersion: review.source_version,
        reviewSessionId: "content-session-1",
      }),
    });
    assert.equal(stale.status, 409);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge exposes a terminal safe revision for reads but rejects writes before Runtime", async () => {
  const terminalRevision = Number.MAX_SAFE_INTEGER;
  const runtimeCalls = [];
  const invokeBridge = async (request) => {
    runtimeCalls.push(request);
    if (request.operation === "get-content-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: { ...review, revision: terminalRevision },
        snapshot_revision: terminalRevision,
      };
    }
    throw new Error("terminal revision write reached Runtime");
  };
  const { bridge, session } = await startedBridge({
    invokeBridge,
    expectedRevision: terminalRevision,
  });
  try {
    const projection = await fetch(`${session.origin}/api/review`, {
      headers: bearer(session),
    });
    assert.equal(projection.status, 200);
    assert.equal((await projection.json()).expectedRevision, terminalRevision);

    const decision = await fetch(`${session.origin}/api/content/decision`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: session.origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: terminalRevision,
        sourceVersion: review.source_version,
        reviewSessionId: "content-session-1",
        slideId: "S01",
        decision: "approved",
        comment: "",
      }),
    });

    assert.equal(decision.status, 409);
    assert.deepEqual(runtimeCalls.map((call) => call.operation), [
      "get-content-review-projection",
    ]);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge keeps visual anchor batches and contract marks on separate exact routes", async () => {
  const { bridge, session, calls } = await startedBridge({ review: visualReview });
  try {
    const origin = session.origin;
    const feedback = [{
      feedback_id: "f1", anchor_slide_id: "S01", anchor_artifact_ref: "anchor-slide-set:v1",
      normalized_region: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 }, comment: "调整层级",
      order: 1, visual_source_version: "visual-v1", revision: 7,
      created_at: "2026-08-15T00:00:00Z", created_by: "user",
    }];
    const anchor = await fetch(`${origin}/api/visual/anchor-feedback`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: 7, sourceVersion: "visual-v1", reviewSessionId: "visual-session-1", feedback }),
    });
    assert.equal(anchor.status, 200);
    assert.equal(calls.at(-1).operation, "submit-visual-anchor-feedback-batch");
    assert.deepEqual(calls.at(-1).feedback, feedback);
    const anchorPayload = await anchor.json();
    assert.equal(anchorPayload.hostNotificationStatus, "unavailable");
    assert.equal(anchorPayload.aiReceiptStatus, "unverified");

    const marks = [{
      mark_id: "m1", target_type: "contract-field", slide_id: "S01", deck_section_id: "",
      target_key: "composition_intent", selected_text: "", context_before: "", context_after: "",
      comment: "调整构图", visual_contract_ref: "visual-contract:v1", source_version: "visual-v1",
      revision: 8, created_at: "2026-08-15T00:00:00Z", created_by: "user",
    }];
    const markResponse = await fetch(`${origin}/api/visual/marks`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: 8, sourceVersion: "visual-v1", reviewSessionId: "visual-session-1", marks }),
    });
    assert.equal(markResponse.status, 200);
    assert.equal(calls.at(-1).operation, "save-visual-contract-review-marks");
    assert.deepEqual(calls.at(-1).marks, marks);
    assert.equal((await markResponse.json()).snapshotRevision, 9);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge replays the exact persisted visual write after the first HTTP request is aborted during host notification", async () => {
  const notifyPending = deferred();
  const notifyStarted = deferred();
  const runtimeCalls = [];
  let authoritativeRevision = 7;
  let notifyCount = 0;
  const invokeBridge = async (request) => {
    runtimeCalls.push(request);
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: visualReview,
        snapshot_revision: authoritativeRevision,
      };
    }
    if (request.operation === "submit-visual-anchor-feedback-batch") {
      authoritativeRevision += 1;
      return {
        ok: true,
        result: {
          batch_ref: "artifact://visual-anchor-feedback-batch/" + "e".repeat(64),
          batch: {
            batch_id: "timeout-after-commit",
            items: request.feedback,
            persistence_status: "saved",
            host_notification_status: "not-requested",
            ai_receipt_status: "pending",
          },
          snapshot: { revision: authoritativeRevision },
        },
      };
    }
    if (request.operation === "record-review-host-notification") {
      authoritativeRevision += 1;
      return {
        ok: true,
        result: {
          session_ref: "artifact://review-session/" + "f".repeat(64),
          session: {},
          snapshot: { revision: authoritativeRevision },
        },
      };
    }
    throw new Error(`unexpected Runtime operation ${request.operation}`);
  };
  const { bridge, session } = await startedBridge({
    review: visualReview,
    invokeBridge,
    notifyHost: async () => {
      notifyCount += 1;
      if (notifyCount === 1) {
        notifyStarted.resolve();
        return notifyPending.promise;
      }
      return { sent: false };
    },
  });
  const feedback = [{
    feedback_id: "timeout-feedback",
    anchor_slide_id: "S01",
    anchor_artifact_ref: "artifact://anchor-slide-set/" + "a".repeat(64),
    normalized_region: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
    comment: "commit 后 HTTP 超时必须精确重放",
    order: 1,
    visual_source_version: "visual-v1",
    revision: 7,
    created_at: "2026-08-15T00:00:00Z",
    created_by: "user",
  }];
  const requestBody = {
    expectedRevision: 7,
    sourceVersion: "visual-v1",
    reviewSessionId: "visual-session-1",
    feedback,
  };
  const post = (body, signal) => fetch(`${session.origin}/api/visual/anchor-feedback`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });

  try {
    const controller = new AbortController();
    const first = post(requestBody, controller.signal);
    await notifyStarted.promise;
    assert.equal(authoritativeRevision, 8);
    controller.abort();
    await assert.rejects(first, (error) => error?.name === "AbortError");
    await new Promise((resolve) => setImmediate(resolve));

    const replay = await post(requestBody);
    assert.equal(replay.status, 200);
    const replayPayload = await replay.json();
    assert.equal(replayPayload.snapshotRevision, 8);
    assert.equal(replayPayload.batchRef, "artifact://visual-anchor-feedback-batch/" + "e".repeat(64));
    assert.deepEqual(replayPayload.batch.items, feedback);
    assert.equal(replayPayload.hostNotificationStatus, "failed");
    assert.equal(replayPayload.aiReceiptStatus, "unverified");
    assert.equal(runtimeCalls.filter((call) => call.operation === "submit-visual-anchor-feedback-batch").length, 1);
    assert.equal(notifyCount, 1);

    for (const rejectedBody of [
      { ...requestBody, feedback: [{ ...feedback[0], comment: "different body" }] },
      { ...requestBody, sourceVersion: "visual-v2" },
      { ...requestBody, reviewSessionId: "visual-session-2" },
      { ...requestBody, expectedRevision: 9 },
    ]) {
      const rejected = await post(rejectedBody);
      assert.equal(rejected.status, 409);
    }

    const nextFeedback = [{ ...feedback[0], feedback_id: "next-feedback", revision: 8 }];
    const next = await post({ ...requestBody, expectedRevision: 8, feedback: nextFeedback });
    assert.equal(next.status, 200);
    assert.equal((await next.json()).snapshotRevision, 9);
    assert.equal(runtimeCalls.filter((call) => call.operation === "submit-visual-anchor-feedback-batch").length, 2);
    assert.equal(notifyCount, 2);

    notifyPending.resolve({
      sent: true,
      receiptRef: "artifact://review-host-notification-receipt/" + "d".repeat(64),
    });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(authoritativeRevision, 9);
    assert.equal(runtimeCalls.some((call) => call.operation === "record-review-host-notification"), false);
  } finally {
    notifyPending.resolve({ sent: false });
    await bridge.stop();
  }
});

test("Review Bridge returns the authoritative revision after automatic host receipt recording and keeps the next write reachable", async () => {
  const { bridge, session, calls } = await startedBridge({
    review: visualReview,
    notifyHost: async () => ({
      sent: true,
      receiptRef: "artifact://review-host-notification-receipt/" + "c".repeat(64),
    }),
  });
  const feedback = [{
    feedback_id: "notified-feedback",
    anchor_slide_id: "S01",
    anchor_artifact_ref: "artifact://anchor-slide-set/" + "a".repeat(64),
    normalized_region: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
    comment: "自动通知不得制造隐藏 revision",
    order: 1,
    visual_source_version: "visual-v1",
    revision: 7,
    created_at: "2026-08-15T00:00:00Z",
    created_by: "user",
  }];
  const anchorBody = {
    expectedRevision: 7,
    sourceVersion: "visual-v1",
    reviewSessionId: "visual-session-1",
    feedback,
  };
  const post = (path, body) => fetch(`${session.origin}${path}`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    const first = await post("/api/visual/anchor-feedback", anchorBody);
    assert.equal(first.status, 200);
    assert.equal((await first.json()).snapshotRevision, 9);
    assert.deepEqual(calls.slice(-2).map((call) => call.operation), [
      "submit-visual-anchor-feedback-batch",
      "record-review-host-notification",
    ]);
    assert.equal(calls.at(-1).review_session_id, "visual-session-1");
    assert.equal(calls.at(-1).source_version, "visual-v1");
    assert.equal(calls.at(-1).saved_artifact_ref, ANCHOR_BATCH_REF);

    const exactReplay = await post("/api/visual/anchor-feedback", anchorBody);
    assert.equal(exactReplay.status, 200);
    assert.equal((await exactReplay.json()).snapshotRevision, 9);

    const marks = [{
      mark_id: "next-mark",
      target_type: "contract-field",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "composition_intent",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "下一次合法写入必须可达",
      visual_contract_ref: "artifact://visual-contract/" + "b".repeat(64),
      source_version: "visual-v1",
      revision: 9,
      created_at: "2026-08-15T00:00:00Z",
      created_by: "user",
    }];
    const next = await post("/api/visual/marks", {
      expectedRevision: 9,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks,
    });
    assert.equal(next.status, 200);
    assert.equal((await next.json()).snapshotRevision, 11);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge rejects wrong-kind or malformed visual save refs before notification", async () => {
  for (const invalidRef of [
    "artifact://visual-contract-review-mark-set/" + "1".repeat(64),
    "visual-anchor-feedback-batch:v1",
    "artifact://visual-anchor-feedback-batch/not-a-sha256",
  ]) {
    const calls = [];
    let authoritativeRevision = 7;
    let notifyCount = 0;
    const invokeBridge = async (request) => {
      calls.push(request);
      if (request.operation === "get-visual-review-projection") {
        return {
          ok: true,
          selected_project_root: "/managed/project",
          review: visualReview,
          snapshot_revision: authoritativeRevision,
        };
      }
      if (request.operation === "submit-visual-anchor-feedback-batch") {
        authoritativeRevision += 1;
        return {
          ok: true,
          result: {
            batch_ref: invalidRef,
            batch: { items: request.feedback, persistence_status: "saved" },
            snapshot: { revision: authoritativeRevision },
          },
        };
      }
      if (request.operation === "save-visual-contract-review-marks") {
        authoritativeRevision += 1;
        return {
          ok: true,
          result: {
            mark_set_ref: CONTRACT_MARK_SET_REF,
            mark_set: { marks: request.marks, persistence_status: "saved" },
            snapshot: { revision: authoritativeRevision },
          },
        };
      }
      throw new Error(`unexpected Runtime operation ${request.operation}`);
    };
    const { bridge, session } = await startedBridge({
      review: visualReview,
      invokeBridge,
      notifyHost: async () => {
        notifyCount += 1;
        return { sent: false };
      },
    });
    const post = (path, body) => fetch(`${session.origin}${path}`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: session.origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    try {
      const invalid = await post("/api/visual/anchor-feedback", {
        expectedRevision: 7,
        reviewSessionId: "visual-session-1",
        sourceVersion: "visual-v1",
        feedback: [],
      });
      assert.equal(invalid.status, 502);
      assert.equal(notifyCount, 0);
      assert.equal(calls.some((call) => call.operation === "record-review-host-notification"), false);

      const reachable = await post("/api/visual/marks", {
        expectedRevision: 8,
        reviewSessionId: "visual-session-1",
        sourceVersion: "visual-v1",
        marks: [],
      });
      assert.equal(reachable.status, 200);
      assert.equal((await reachable.json()).snapshotRevision, 9);
    } finally {
      await bridge.stop();
    }
  }
});

test("Review Bridge retries host notification independently for the exact current saved visual artifact", async () => {
  const notified = [];
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    notifyHost: async (input) => {
      notified.push(input);
      return {
        sent: true,
        receiptRef: "artifact://review-host-notification-receipt/" + "c".repeat(64),
      };
    },
  });
  const post = (body) => fetch(`${session.origin}/api/host-notification`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const exact = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: ANCHOR_BATCH_REF,
  };
  try {
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    for (const wrong of [
      { ...exact, expectedRevision: 8 },
      { ...exact, reviewSessionId: "visual-session-2" },
      { ...exact, sourceVersion: "visual-v2" },
      { ...exact, savedArtifactRef: "artifact://visual-anchor-feedback-batch/" + "d".repeat(64) },
    ]) {
      assert.equal((await post(wrong)).status, 409);
    }
    assert.equal(notified.length, 0);

    const anchor = await post(exact);
    assert.equal(anchor.status, 200);
    const anchorPayload = await anchor.json();
    assert.deepEqual(anchorPayload, {
      ok: true,
      savedArtifactRef: ANCHOR_BATCH_REF,
      hostNotificationStatus: "sent",
      snapshotRevision: 8,
    });
    assert.equal(notified.length, 1);
    assert.equal(notified[0].reviewSessionId, "visual-session-1");
    assert.equal(notified[0].sourceVersion, "visual-v1");
    assert.equal(notified[0].savedArtifactRef, ANCHOR_BATCH_REF);
    assert.equal(notified[0].snapshotRevision, 7);
    assert.equal(notified[0].savedResult.batch_ref, ANCHOR_BATCH_REF);
    assert.equal(calls.at(-1).operation, "record-review-host-notification");
    assert.equal(calls.at(-1).review_session_id, "visual-session-1");
    assert.equal(calls.at(-1).source_version, "visual-v1");
    assert.equal(calls.at(-1).saved_artifact_ref, ANCHOR_BATCH_REF);
    assert.equal("aiReceiptStatus" in anchorPayload, false);

    const exactReplay = await post(exact);
    assert.equal(exactReplay.status, 200);
    assert.deepEqual(await exactReplay.json(), anchorPayload);
    assert.equal(notified.length, 1);
    const marks = await post({
      ...exact,
      expectedRevision: 8,
      savedArtifactRef: CONTRACT_MARK_SET_REF,
    });
    assert.equal(marks.status, 200);
    assert.equal((await marks.json()).snapshotRevision, 9);
    assert.equal(notified.length, 2);
    assert.equal(calls.filter((call) => call.operation === "record-review-host-notification").length, 2);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge projection refresh preserves one Host notification owner for the same artifact", async () => {
  const firstReceipt = deferred();
  const firstStarted = deferred();
  let notifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    notifyHost: async () => {
      notifyCount += 1;
      if (notifyCount === 1) {
        firstStarted.resolve();
        return firstReceipt.promise;
      }
      return {
        sent: true,
        receiptRef: "artifact://review-host-notification-receipt/" + "d".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: ANCHOR_BATCH_REF,
  };
  const post = () => fetch(`${session.origin}/api/host-notification`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const first = post();
    await Promise.race([
      firstStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("Host notification did not start")),
        100,
      )),
    ]);
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const concurrent = await post();
    assert.equal(concurrent.status, 409);
    assert.equal((await concurrent.json()).error.code, "REVIEW_HOST_NOTIFICATION_IN_FLIGHT");
    assert.equal(notifyCount, 1);
    assert.equal(calls.some((call) => call.operation === "record-review-host-notification"), false);

    firstReceipt.resolve({
      sent: true,
      receiptRef: "artifact://review-host-notification-receipt/" + "c".repeat(64),
    });
    const completed = await first;
    assert.equal(completed.status, 200);
    assert.equal((await completed.json()).snapshotRevision, 8);
    const exactReplay = await post();
    assert.equal(exactReplay.status, 200);
    assert.equal((await exactReplay.json()).snapshotRevision, 8);
    assert.equal(notifyCount, 1);
    assert.equal(calls.filter((call) => call.operation === "record-review-host-notification").length, 1);
  } finally {
    firstReceipt.resolve({ sent: false });
    await bridge.stop();
  }
});

test("Review Bridge exposes unavailable host notification recovery without claiming a send", async () => {
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({ review: savedReview });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const response = await fetch(`${session.origin}/api/host-notification`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: session.origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        reviewSessionId: "visual-session-1",
        sourceVersion: "visual-v1",
        savedArtifactRef: ANCHOR_BATCH_REF,
      }),
    });
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), {
      ok: false,
      error: {
        code: "REVIEW_HOST_NOTIFICATION_UNAVAILABLE",
        message: "No authoritative host notification adapter is available.",
      },
      savedArtifactRef: ANCHOR_BATCH_REF,
      hostNotificationStatus: "unavailable",
      snapshotRevision: 7,
    });
    assert.equal(calls.some((call) => call.operation === "record-review-host-notification"), false);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge bounds one host notification attempt per saved artifact and ignores a timed-out late receipt", async () => {
  const firstReceipt = deferred();
  const firstStarted = deferred();
  let notifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    notificationTimeoutMs: 20,
    notifyHost: async () => {
      notifyCount += 1;
      if (notifyCount === 1) {
        firstStarted.resolve();
        return firstReceipt.promise;
      }
      return {
        sent: true,
        receiptRef: "artifact://review-host-notification-receipt/" + "e".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: ANCHOR_BATCH_REF,
  };
  const post = () => fetch(`${session.origin}/api/host-notification`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const first = post();
    await Promise.race([
      firstStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("host notification attempt did not start")),
        100,
      )),
    ]);
    const concurrent = await post();
    assert.equal(concurrent.status, 409);
    assert.equal((await concurrent.json()).error.code, "REVIEW_HOST_NOTIFICATION_IN_FLIGHT");

    const timedOut = await first;
    assert.equal(timedOut.status, 502);
    assert.equal((await timedOut.json()).error.code, "REVIEW_HOST_NOTIFICATION_FAILED");
    assert.equal(calls.some((call) => call.operation === "record-review-host-notification"), false);

    const retry = await post();
    assert.equal(retry.status, 200);
    assert.equal((await retry.json()).snapshotRevision, 8);
    assert.equal(notifyCount, 2);
    assert.equal(calls.filter((call) => call.operation === "record-review-host-notification").length, 1);

    firstReceipt.resolve({
      sent: true,
      receiptRef: "artifact://review-host-notification-receipt/" + "f".repeat(64),
    });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(calls.filter((call) => call.operation === "record-review-host-notification").length, 1);
  } finally {
    firstReceipt.resolve({ sent: false });
    await bridge.stop();
  }
});

test("Review Bridge recovers a committed Host receipt whose first Runtime transport misses the HTTP deadline", async () => {
  const firstRecording = deferred();
  const firstRecordingStarted = deferred();
  const calls = [];
  let authoritativeRevision = 7;
  let firstRecordingInput;
  let notifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: authoritativeRevision < 8
          ? savedReview
          : {
              ...savedReview,
              anchor_feedback_batch: {
                ...savedReview.anchor_feedback_batch,
                host_notification_status: "sent",
              },
              ...(authoritativeRevision < 9
                ? {}
                : {
                    contract_review_marks: {
                      ...savedReview.contract_review_marks,
                      host_notification_status: "sent",
                    },
                  }),
            },
        snapshot_revision: authoritativeRevision,
      };
    }
    if (request.operation === "record-review-host-notification") {
      if (request.saved_artifact_ref === ANCHOR_BATCH_REF && !firstRecordingInput) {
        firstRecordingInput = structuredClone(request);
        authoritativeRevision = 8;
        firstRecordingStarted.resolve();
        return firstRecording.promise;
      }
      if (request.saved_artifact_ref === ANCHOR_BATCH_REF) {
        assert.deepEqual(request, firstRecordingInput);
        assert.equal(authoritativeRevision, 8);
      } else {
        assert.equal(request.saved_artifact_ref, CONTRACT_MARK_SET_REF);
        assert.equal(request.expected_revision, 8);
        authoritativeRevision = 9;
      }
      return {
        ok: true,
        result: {
          session_ref: "artifact://review-session/" + "d".repeat(64),
          session: {},
          snapshot: { revision: authoritativeRevision },
        },
      };
    }
    throw new Error(`unexpected Runtime operation ${request.operation}`);
  };
  const { bridge, session } = await startedBridge({
    review: savedReview,
    invokeBridge,
    notificationTimeoutMs: 20,
    notifyHost: async () => {
      notifyCount += 1;
      return {
        sent: true,
        receiptRef: "artifact://review-host-notification-receipt/" + "e".repeat(64),
      };
    },
  });
  const anchorBody = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: ANCHOR_BATCH_REF,
  };
  const marksBody = {
    ...anchorBody,
    expectedRevision: 8,
    savedArtifactRef: CONTRACT_MARK_SET_REF,
  };
  const post = (body) => fetch(`${session.origin}/api/host-notification`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const first = post(anchorBody);
    await Promise.race([
      firstRecordingStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("Host Runtime recording did not start")),
        100,
      )),
    ]);
    const timedOut = await first;
    assert.equal(timedOut.status, 502);
    const timedOutPayload = await timedOut.json();
    assert.equal(timedOutPayload.error.code, "REVIEW_HOST_NOTIFICATION_FAILED");
    assert.equal(timedOutPayload.hostNotificationStatus, "failed");
    assert.equal(timedOutPayload.snapshotRevision, 7);

    assert.equal(authoritativeRevision, 8);
    const retry = await post(anchorBody);
    assert.equal(retry.status, 200);
    assert.equal((await retry.json()).snapshotRevision, 8);
    assert.equal(notifyCount, 1);

    const independent = await post(marksBody);
    assert.equal(independent.status, 200);
    assert.equal((await independent.json()).snapshotRevision, 9);
    assert.equal(authoritativeRevision, 9);
    assert.equal(notifyCount, 2);

    firstRecording.resolve({
      ok: true,
      result: {
        session_ref: "artifact://review-session/" + "f".repeat(64),
        session: {},
        snapshot: { revision: 8 },
      },
    });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const laterReplay = await post(marksBody);
    assert.equal(laterReplay.status, 200);
    assert.equal((await laterReplay.json()).snapshotRevision, 9);
    assert.equal(notifyCount, 2);
  } finally {
    firstRecording.resolve({ ok: false });
    await bridge.stop();
  }
});

test("Review Bridge exactly replays a committed host notification when the HTTP response is lost", async () => {
  const recordPending = deferred();
  const recordStarted = deferred();
  const calls = [];
  let notifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: savedReview,
        snapshot_revision: 7,
      };
    }
    if (request.operation === "record-review-host-notification") {
      recordStarted.resolve();
      return recordPending.promise;
    }
    throw new Error(`unexpected Runtime operation ${request.operation}`);
  };
  const { bridge, session } = await startedBridge({
    review: savedReview,
    invokeBridge,
    notifyHost: async () => {
      notifyCount += 1;
      return {
        sent: true,
        receiptRef: "artifact://review-host-notification-receipt/" + "7".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: ANCHOR_BATCH_REF,
  };
  const post = (requestBody, signal) => fetch(`${session.origin}/api/host-notification`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
    signal,
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const controller = new AbortController();
    const first = post(body, controller.signal);
    await Promise.race([
      recordStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("host notification receipt recording did not start")),
        100,
      )),
    ]);
    controller.abort();
    await assert.rejects(first, (error) => error?.name === "AbortError");
    recordPending.resolve({
      ok: true,
      result: {
        session_ref: "artifact://review-session/" + "8".repeat(64),
        session: {},
        snapshot: { revision: 8 },
      },
    });
    await new Promise((resolve) => setImmediate(resolve));

    const replay = await post(body);
    assert.equal(replay.status, 200);
    assert.deepEqual(await replay.json(), {
      ok: true,
      savedArtifactRef: ANCHOR_BATCH_REF,
      hostNotificationStatus: "sent",
      snapshotRevision: 8,
    });
    assert.equal(notifyCount, 1);
    assert.equal(calls.filter((call) => call.operation === "record-review-host-notification").length, 1);
    assert.equal((await post({ ...body, retryNonce: "different" })).status, 409);
  } finally {
    recordPending.resolve({ ok: false });
    await bridge.stop();
  }
});

test("Review Bridge binds verified AI receipt to the exact current saved visual artifact", async () => {
  const verified = [];
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    verifyAiReceipt: async (input) => {
      verified.push(input);
      return {
        verified: true,
        receiptRef: "artifact://review-ai-receipt/" + "9".repeat(64),
      };
    },
  });
  const post = (body) => fetch(`${session.origin}/api/ai-receipt`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const exact = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: CONTRACT_MARK_SET_REF,
    receiptIdentity: "host-ai-receipt-for-marks",
  };
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const wrong = await post({
      ...exact,
      savedArtifactRef: "artifact://visual-contract-review-mark-set/" + "8".repeat(64),
    });
    assert.equal(wrong.status, 409);
    assert.equal(verified.length, 0);

    const response = await post(exact);
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.deepEqual(payload, {
      ok: true,
      savedArtifactRef: CONTRACT_MARK_SET_REF,
      aiReceiptStatus: "received",
      snapshotRevision: 8,
    });
    assert.equal("hostNotificationStatus" in payload, false);
    assert.equal(verified[0].reviewSessionId, "visual-session-1");
    assert.equal(verified[0].sourceVersion, "visual-v1");
    assert.equal(verified[0].savedArtifactRef, CONTRACT_MARK_SET_REF);
    assert.equal(calls.at(-1).operation, "record-review-ai-receipt");
    assert.equal(calls.at(-1).review_session_id, "visual-session-1");
    assert.equal(calls.at(-1).source_version, "visual-v1");
    assert.equal(calls.at(-1).saved_artifact_ref, CONTRACT_MARK_SET_REF);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge projection refresh preserves one AI receipt owner for the same artifact", async () => {
  const firstReceipt = deferred();
  const firstStarted = deferred();
  let verifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    verifyAiReceipt: async () => {
      verifyCount += 1;
      if (verifyCount === 1) {
        firstStarted.resolve();
        return firstReceipt.promise;
      }
      return {
        verified: true,
        receiptRef: "artifact://review-ai-receipt/" + "d".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: CONTRACT_MARK_SET_REF,
    receiptIdentity: CONTRACT_MARK_SET_REF,
  };
  const post = () => fetch(`${session.origin}/api/ai-receipt`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const first = post();
    await Promise.race([
      firstStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("AI receipt verification did not start")),
        100,
      )),
    ]);
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const concurrent = await post();
    assert.equal(concurrent.status, 409);
    assert.equal((await concurrent.json()).error.code, "REVIEW_AI_RECEIPT_IN_FLIGHT");
    assert.equal(verifyCount, 1);
    assert.equal(calls.some((call) => call.operation === "record-review-ai-receipt"), false);

    firstReceipt.resolve({
      verified: true,
      receiptRef: "artifact://review-ai-receipt/" + "c".repeat(64),
    });
    const completed = await first;
    assert.equal(completed.status, 200);
    assert.equal((await completed.json()).snapshotRevision, 8);
    const exactReplay = await post();
    assert.equal(exactReplay.status, 200);
    assert.equal((await exactReplay.json()).snapshotRevision, 8);
    assert.equal(verifyCount, 1);
    assert.equal(calls.filter((call) => call.operation === "record-review-ai-receipt").length, 1);
  } finally {
    firstReceipt.resolve({ verified: false });
    await bridge.stop();
  }
});

test("Review Bridge bounds one visual AI verifier attempt and ignores its timed-out late receipt", async () => {
  const firstReceipt = deferred();
  const firstStarted = deferred();
  let verifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const { bridge, session, calls } = await startedBridge({
    review: savedReview,
    notificationTimeoutMs: 20,
    verifyAiReceipt: async () => {
      verifyCount += 1;
      if (verifyCount === 1) {
        firstStarted.resolve();
        return firstReceipt.promise;
      }
      return {
        verified: true,
        receiptRef: "artifact://review-ai-receipt/" + "e".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: CONTRACT_MARK_SET_REF,
    receiptIdentity: CONTRACT_MARK_SET_REF,
  };
  const post = () => fetch(`${session.origin}/api/ai-receipt`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  let lateTimer;
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const first = post();
    await Promise.race([
      firstStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("AI receipt verification did not start")),
        100,
      )),
    ]);
    const concurrent = await post();
    assert.equal(concurrent.status, 409);
    assert.equal((await concurrent.json()).error.code, "REVIEW_AI_RECEIPT_IN_FLIGHT");

    lateTimer = setTimeout(() => firstReceipt.resolve({
      verified: true,
      receiptRef: "artifact://review-ai-receipt/" + "f".repeat(64),
    }), 100);
    const timedOut = await first;
    assert.equal(timedOut.status, 502);
    const timedOutPayload = await timedOut.json();
    assert.equal(timedOutPayload.error.code, "REVIEW_AI_RECEIPT_UNVERIFIED");
    assert.equal(timedOutPayload.savedArtifactRef, CONTRACT_MARK_SET_REF);
    assert.equal(timedOutPayload.aiReceiptStatus, "unverified");
    assert.equal(timedOutPayload.snapshotRevision, 7);
    assert.equal(calls.some((call) => call.operation === "record-review-ai-receipt"), false);

    const retry = await post();
    assert.equal(retry.status, 200);
    assert.equal((await retry.json()).snapshotRevision, 8);
    assert.equal(verifyCount, 2);
    assert.equal(calls.filter((call) => call.operation === "record-review-ai-receipt").length, 1);

    await new Promise((resolve) => setTimeout(resolve, 110));
    assert.equal(calls.filter((call) => call.operation === "record-review-ai-receipt").length, 1);
  } finally {
    clearTimeout(lateTimer);
    firstReceipt.resolve({ verified: false });
    await bridge.stop();
  }
});

test("Review Bridge recovers a committed AI receipt whose first Runtime transport misses the HTTP deadline", async () => {
  const firstRecording = deferred();
  const firstRecordingStarted = deferred();
  const calls = [];
  let authoritativeRevision = 7;
  let firstRecordingInput;
  let verifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: authoritativeRevision < 8
          ? savedReview
          : {
              ...savedReview,
              contract_review_marks: {
                ...savedReview.contract_review_marks,
                ai_receipt_status: "received",
              },
              ...(authoritativeRevision < 9
                ? {}
                : {
                    anchor_feedback_batch: {
                      ...savedReview.anchor_feedback_batch,
                      ai_receipt_status: "received",
                    },
                  }),
            },
        snapshot_revision: authoritativeRevision,
      };
    }
    if (request.operation === "record-review-ai-receipt") {
      if (request.saved_artifact_ref === CONTRACT_MARK_SET_REF && !firstRecordingInput) {
        firstRecordingInput = structuredClone(request);
        authoritativeRevision = 8;
        firstRecordingStarted.resolve();
        return firstRecording.promise;
      }
      if (request.saved_artifact_ref === CONTRACT_MARK_SET_REF) {
        assert.deepEqual(request, firstRecordingInput);
        assert.equal(authoritativeRevision, 8);
      } else {
        assert.equal(request.saved_artifact_ref, ANCHOR_BATCH_REF);
        assert.equal(request.expected_revision, 8);
        authoritativeRevision = 9;
      }
      return {
        ok: true,
        result: {
          session_ref: "artifact://review-session/" + "d".repeat(64),
          session: {},
          snapshot: { revision: authoritativeRevision },
        },
      };
    }
    throw new Error(`unexpected Runtime operation ${request.operation}`);
  };
  const { bridge, session } = await startedBridge({
    review: savedReview,
    invokeBridge,
    notificationTimeoutMs: 20,
    verifyAiReceipt: async () => {
      verifyCount += 1;
      return {
        verified: true,
        receiptRef: "artifact://review-ai-receipt/" + "e".repeat(64),
      };
    },
  });
  const marksBody = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: CONTRACT_MARK_SET_REF,
    receiptIdentity: CONTRACT_MARK_SET_REF,
  };
  const anchorBody = {
    ...marksBody,
    expectedRevision: 8,
    savedArtifactRef: ANCHOR_BATCH_REF,
    receiptIdentity: ANCHOR_BATCH_REF,
  };
  const post = (body) => fetch(`${session.origin}/api/ai-receipt`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const first = post(marksBody);
    await Promise.race([
      firstRecordingStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("AI Runtime recording did not start")),
        100,
      )),
    ]);
    const timedOut = await first;
    assert.equal(timedOut.status, 502);
    const timedOutPayload = await timedOut.json();
    assert.equal(timedOutPayload.error.code, "REVIEW_AI_RECEIPT_UNVERIFIED");
    assert.equal(timedOutPayload.aiReceiptStatus, "unverified");
    assert.equal(timedOutPayload.snapshotRevision, 7);

    assert.equal(authoritativeRevision, 8);
    const retry = await post(marksBody);
    assert.equal(retry.status, 200);
    assert.equal((await retry.json()).snapshotRevision, 8);
    assert.equal(verifyCount, 1);

    const independent = await post(anchorBody);
    assert.equal(independent.status, 200);
    assert.equal((await independent.json()).snapshotRevision, 9);
    assert.equal(authoritativeRevision, 9);
    assert.equal(verifyCount, 2);

    firstRecording.resolve({
      ok: true,
      result: {
        session_ref: "artifact://review-session/" + "f".repeat(64),
        session: {},
        snapshot: { revision: 8 },
      },
    });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal((await fetch(`${session.origin}/api/review`, { headers: bearer(session) })).status, 200);
    const laterReplay = await post(anchorBody);
    assert.equal(laterReplay.status, 200);
    assert.equal((await laterReplay.json()).snapshotRevision, 9);
    assert.equal(verifyCount, 2);
  } finally {
    firstRecording.resolve({ ok: false });
    await bridge.stop();
  }
});

test("Review Bridge exactly replays a committed visual AI receipt when the HTTP response is lost", async () => {
  const recordPending = deferred();
  const recordStarted = deferred();
  const calls = [];
  let verifyCount = 0;
  const savedReview = visualReviewWithSavedArtifacts();
  const invokeBridge = async (request) => {
    calls.push(request);
    if (request.operation === "get-visual-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review: savedReview,
        snapshot_revision: 7,
      };
    }
    if (request.operation === "record-review-ai-receipt") {
      recordStarted.resolve();
      return recordPending.promise;
    }
    throw new Error(`unexpected Runtime operation ${request.operation}`);
  };
  const { bridge, session } = await startedBridge({
    review: savedReview,
    invokeBridge,
    verifyAiReceipt: async () => {
      verifyCount += 1;
      return {
        verified: true,
        receiptRef: "artifact://review-ai-receipt/" + "6".repeat(64),
      };
    },
  });
  const body = {
    expectedRevision: 7,
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    savedArtifactRef: CONTRACT_MARK_SET_REF,
    receiptIdentity: "ai-receipt-lost-response",
  };
  const post = (requestBody, signal) => fetch(`${session.origin}/api/ai-receipt`, {
    method: "POST",
    headers: {
      ...bearer(session),
      Origin: session.origin,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
    signal,
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });
    const controller = new AbortController();
    const first = post(body, controller.signal);
    await Promise.race([
      recordStarted.promise,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("AI receipt recording did not start")),
        100,
      )),
    ]);
    controller.abort();
    await assert.rejects(first, (error) => error?.name === "AbortError");
    recordPending.resolve({
      ok: true,
      result: {
        session_ref: "artifact://review-session/" + "5".repeat(64),
        session: {},
        snapshot: { revision: 8 },
      },
    });
    await new Promise((resolve) => setImmediate(resolve));

    const replay = await post(body);
    assert.equal(replay.status, 200);
    assert.deepEqual(await replay.json(), {
      ok: true,
      savedArtifactRef: CONTRACT_MARK_SET_REF,
      aiReceiptStatus: "received",
      snapshotRevision: 8,
    });
    assert.equal(verifyCount, 1);
    assert.equal(calls.filter((call) => call.operation === "record-review-ai-receipt").length, 1);
    assert.equal((await post({ ...body, receiptIdentity: "different" })).status, 409);
  } finally {
    recordPending.resolve({ ok: false });
    await bridge.stop();
  }
});

test("Review Bridge enriches visual capability from actual adapters without receipts", async () => {
  for (const withAdapters of [false, true]) {
    const persisted = {
      ...visualReview,
      host_submission_capability: "unknown",
      ai_receipt_capability: "unknown",
      review_session: {
        host_notification_status: "not-requested",
        ai_receipt_status: "pending",
      },
    };
    const adapterOptions = withAdapters
      ? {
          notifyHost: async () => ({ sent: false }),
          verifyAiReceipt: async () => ({ verified: false }),
        }
      : {};
    const { bridge, session } = await startedBridge({
      review: persisted,
      ...adapterOptions,
    });
    try {
      const response = await fetch(`${session.origin}/api/review`, {
        headers: bearer(session),
      });
      assert.equal(response.status, 200);
      const payload = await response.json();
      assert.equal(
        payload.review.host_submission_capability,
        withAdapters ? "available" : "unavailable",
      );
      assert.equal(
        payload.review.ai_receipt_capability,
        withAdapters ? "available" : "unavailable",
      );
      assert.deepEqual(payload.review.review_session, {
        host_notification_status: "not-requested",
        ai_receipt_status: "pending",
      });
      assert.equal(persisted.host_submission_capability, "unknown");
      assert.equal(persisted.ai_receipt_capability, "unknown");
    } finally {
      await bridge.stop();
    }
  }
});

test("Review Bridge records host-open only after projection read and requires verified AI receipts", async () => {
  const verified = [];
  const { bridge, session, calls } = await startedBridge({
    verifyAiReceipt: async (input) => {
      verified.push(input);
      return { verified: true, receiptRef: "artifact://review-ai-receipt/" + "d".repeat(64) };
    },
  });
  try {
    const origin = session.origin;
    assert.equal(calls.some((call) => call.operation === "record-review-bridge-host-open"), false);
    const projection = await fetch(`${origin}/api/review`, { headers: bearer(session) });
    const projectionPayload = await projection.json();
    assert.equal(calls.some((call) => call.operation === "record-review-bridge-host-open"), false);

    const opened = await fetch(`${origin}/api/host-open`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: 7, bridgeSessionId: projectionPayload.bridgeSessionId }),
    });
    assert.equal(opened.status, 200);
    assert.equal(calls.at(-1).operation, "record-review-bridge-host-open");
    assert.equal(calls.at(-1).bridge_session_id, projectionPayload.bridgeSessionId);

    const ai = await fetch(`${origin}/api/ai-receipt`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: 8, receiptIdentity: "host-ai-receipt-1" }),
    });
    assert.equal(ai.status, 200);
    assert.equal(verified.length, 1);
    assert.equal(calls.at(-1).operation, "record-review-ai-receipt");
    assert.equal(calls.at(-1).receipt_ref, "artifact://review-ai-receipt/" + "d".repeat(64));
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge rejects a skipped host-open successor without advancing scoped revision", async () => {
  const writes = [];
  let hostOpenAttempt = 0;
  const invokeBridge = async (request) => {
    if (request.operation === "get-content-review-projection") {
      return {
        ok: true,
        selected_project_root: "/managed/project",
        review,
        snapshot_revision: 7,
      };
    }
    writes.push(request);
    hostOpenAttempt += 1;
    return {
      ok: true,
      result: {
        session_ref: "review-session:v1",
        session: {},
        snapshot: { revision: hostOpenAttempt === 1 ? 9 : 8 },
      },
    };
  };
  const { bridge, session } = await startedBridge({ invokeBridge });
  try {
    const projection = await fetch(`${session.origin}/api/review`, {
      headers: bearer(session),
    });
    const projectionPayload = await projection.json();
    const request = () => fetch(`${session.origin}/api/host-open`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: session.origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        bridgeSessionId: projectionPayload.bridgeSessionId,
      }),
    });

    const skipped = await request();
    assert.equal(skipped.status, 502);
    const recovered = await request();
    assert.equal(recovered.status, 200);
    assert.equal((await recovered.json()).snapshotRevision, 8);
    assert.deepEqual(writes.map((call) => call.expected_revision), [7, 7]);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge never infers AI receipt and rejects oversized or unknown writes", async () => {
  const { bridge, session, calls } = await startedBridge();
  try {
    const origin = session.origin;
    const ai = await fetch(`${origin}/api/ai-receipt`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: 7, receiptIdentity: "unverified" }),
    });
    assert.equal(ai.status, 503);
    assert.equal(calls.some((call) => call.operation === "record-review-ai-receipt"), false);

    const unknown = await fetch(`${origin}/api/unknown`, {
      method: "POST", headers: { ...bearer(session), Origin: origin }, body: "{}",
    });
    assert.equal(unknown.status, 404);

    const oversized = await fetch(`${origin}/api/content/decision`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(2 * 1024 * 1024 + 1) }),
    });
    assert.equal(oversized.status, 413);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge switches only through an authenticated server-created target session", async () => {
  const requestedScopes = [];
  const { bridge, session } = await startedBridge({
    createReviewSession: async ({ projectRoot, reviewType }) => {
      requestedScopes.push({ projectRoot, reviewType });
      return {
        url: "http://127.0.0.1:43124/#token=independent-token",
        expiresAt: 123456,
        reviewType,
        sourceVersion: "visual-authoritative-v2",
        expectedRevision: 9,
      };
    },
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/api/switch`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        reviewType: "visual",
        sourceVersion: "client-must-not-control-this",
        projectRoot: "/another/project",
      }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(requestedScopes, [
      { projectRoot: "/managed/project", reviewType: "visual" },
    ]);
    const payload = await response.json();
    assert.equal(payload.sourceVersion, "visual-authoritative-v2");
    assert.match(payload.url, /^http:\/\/127\.0\.0\.1:\d+\/#token=/);

    const sameType = await fetch(`${origin}/api/switch`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reviewType: "content" }),
    });
    assert.equal(sameType.status, 422);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge lease heartbeat extends activity and expiry stops the server", async () => {
  let now = 1_000;
  const { bridge, session } = await startedBridge({
    now: () => now,
    ttlMs: 2_000,
    leaseMs: 100,
  });
  const origin = `http://${session.host}:${session.port}`;
  try {
    const heartbeat = await fetch(`${origin}/api/heartbeat`, {
      method: "POST",
      headers: { ...bearer(session), Origin: origin },
    });
    assert.equal(heartbeat.status, 200);
    now = 1_150;
    bridge.sweep();
    assert.equal(bridge.isActive(), false);
    assert.equal(bridge.isStopped(), true);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge keeps an unactivated Agent handoff alive until the hard TTL", async () => {
  let now = 1_000;
  const { bridge } = await startedBridge({
    now: () => now,
    ttlMs: 2_000,
    leaseMs: 100,
  });
  try {
    now = 1_150;
    bridge.sweep();
    assert.equal(bridge.isActive(), true);
    assert.equal(bridge.isStopped(), false);

    now = 3_001;
    bridge.sweep();
    assert.equal(bridge.isActive(), false);
    assert.equal(bridge.isStopped(), true);
  } finally {
    await bridge.stop();
  }
});

test("Review Bridge rejects the deprecated content evidence Browser scope", () => {
  assert.throws(
    () => createReviewBridge({
      projectRoot: "/managed/project",
      reviewType: "content-evidence",
      reviewSessionId: "content-evidence-session-1",
      sourceVersion: review.source_version,
      expectedRevision: 7,
      invokeBridge: async () => ({}),
    }),
    /Review Bridge scope is invalid/,
  );
});
