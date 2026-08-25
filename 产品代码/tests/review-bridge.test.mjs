import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";

import { createReviewBridge } from "../mcp/review-bridge.mjs";

const review = {
  review_type: "content",
  project_id: "p1",
  project_name: "测试项目",
  source_version:
    "artifact://content-blueprint/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  revision: 7,
  sections: [],
  outline: [],
  mark_set: { marks: [] },
};

const contentSidebarReview = {
  display_policy: "content-sidebar-full-deck",
  phase: "full-deck-review-ready",
  project_id: "p1",
  project_name: "测试项目",
  source_version: review.source_version,
  revision: 7,
  slides: [
    {
      slide_id: "S01",
      order: 1,
      neutral_title: "业务范围与系统现状",
      page_task: "说明业务范围",
      reading_question: "当前范围是什么？",
      visible_copy: [{ copy_id: "copy-1", role: "body", text: "当前页完整文字" }],
      previous_relation: "",
      next_relation: "进入问题页",
      evidence_items: [
        {
          evidence_id: "EV-S01-01",
          material_ref: "artifact://material/m1",
          asset_ref: "project-asset://renders/page-03.png",
          source_file: "客户材料.pptx",
          source_page_or_region: "P03 · 业务范围图",
          used_region: "页面中部业务环节",
          supports_claim: "支持范围说明",
          treatment: "裁切页脚",
          evidence_gap: "跨系统频次待核验",
        },
      ],
    },
    {
      slide_id: "S02",
      order: 2,
      neutral_title: "跨系统协同事项",
      page_task: "说明协同问题",
      reading_question: "哪些事项需要联动？",
      visible_copy: [{ copy_id: "copy-2", role: "body", text: "下一页完整文字" }],
      previous_relation: "承接范围",
      next_relation: "进入方案",
      evidence_items: [],
    },
  ],
};

const formalContentReview = {
  surface: "content-full-deck",
  project_id: "p1",
  source_version: review.source_version,
  revision: 7,
  gate_status: "content-review-ready",
  review_session: {
    review_session_id: "review-session-current-v22",
    review_type: "content-full-deck",
  },
  slides: [
    {
      slide_id: "S01",
      order: 1,
      neutral_title: "业务范围与系统现状",
      page_task: "说明业务范围",
      reading_question: "当前范围是什么？",
      visible_copy_blocks: [{ block_id: "copy-1", role: "body", text: "当前页完整文字" }],
      previous_relation: "当前为第一页",
      next_relation: "进入问题页",
      evidence_bindings: [{
        binding_id: "EV-S01-01",
        identity: "来源事实",
        source_refs: ["artifact://source/s1#page=3"],
        supports_block_refs: ["copy-1"],
        material_ref: "artifact://material/m1",
      }],
    },
    {
      slide_id: "S02",
      order: 2,
      neutral_title: "跨系统协同事项",
      page_task: "说明协同问题",
      reading_question: "哪些事项需要联动？",
      visible_copy_blocks: [{ block_id: "copy-2", role: "body", text: "下一页完整文字" }],
      previous_relation: "承接范围",
      next_relation: "进入方案",
      evidence_bindings: [],
    },
  ],
};

async function startedBridge(options = {}) {
  const calls = [];
  const bridge = createReviewBridge({
    projectRoot: "/managed/project",
    reviewType: "content",
    sourceVersion: review.source_version,
    expectedRevision: 7,
    ttlMs: 10_000,
    leaseMs: 500,
    readReviewHtml: async () =>
      "<!doctype html><html><head><style>body{margin:0}</style></head><body><div id=\"root\"></div><script>window.__reviewBrowserShell=true;</script></body></html>",
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-review-projection") {
        return {
          ok: true,
          selected_project_root: "/managed/project",
          review,
          snapshot_revision: 7,
        };
      }
      return {
        ok: true,
        result: { snapshot: { revision: 8 } },
      };
    },
    ...options,
  });
  const session = await bridge.start();
  return { bridge, session, calls };
}

async function startedEvidenceBridge(options = {}) {
  const calls = [];
  const bridge = createReviewBridge({
    projectRoot: "/managed/project",
    reviewType: "content-evidence",
    sourceVersion: review.source_version,
    expectedRevision: 7,
    evidenceScope: {
      slideId: "S01",
      evidenceId: "EV-S01-01",
      materialRef: "artifact://material/m1",
      assetRef: "project-asset://renders/page-03.png",
    },
    evidenceAsset: {
      assetRef: "renders/page-03.png",
      mimeType: "image/png",
      bytes: 3,
      dataBase64: "YWJj",
    },
    ttlMs: 10_000,
    leaseMs: 500,
    readReviewHtml: async () => "<!doctype html><html><body><div id=\"root\"></div></body></html>",
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-content-sidebar-review-projection") {
        return {
          ok: true,
          selected_project_root: "/managed/project",
          review: contentSidebarReview,
          snapshot_revision: 7,
        };
      }
      throw new Error(`unexpected evidence operation ${request.operation}`);
    },
    ...options,
  });
  const session = await bridge.start();
  return { bridge, session, calls };
}

async function startedFormalEvidenceBridge(options = {}) {
  const calls = [];
  const bridge = createReviewBridge({
    projectRoot: "/managed/project",
    reviewType: "content-evidence",
    sourceVersion: review.source_version,
    expectedRevision: 7,
    evidenceScope: {
      parentReviewSessionId: "review-session-current-v22",
      slideId: "S01",
      evidenceId: "EV-S01-01",
      materialRef: "artifact://material/m1",
    },
    ttlMs: 10_000,
    leaseMs: 500,
    readReviewHtml: async () => "<!doctype html><html><body><div id=\"root\"></div></body></html>",
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-content-full-deck-review-projection") {
        return {
          ok: true,
          selected_project_root: "/managed/project",
          review: formalContentReview,
          snapshot_revision: 7,
        };
      }
      throw new Error(`unexpected formal evidence operation ${request.operation}`);
    },
    ...options,
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
    assert.equal(calls.at(-1).operation, "get-review-projection");
    assert.equal(calls.at(-1).review_type, "content");
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
      '<!doctype html><html><body><script>const example = "<script data-example>"; window.example = example;</script></body></html>',
  });
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/`);
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /<script nonce="[^"]+">const example/);
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

    const wrongOrigin = await fetch(`${origin}/api/marks`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: "http://evil.invalid",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        sourceVersion: review.source_version,
        marks: [],
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

test("Review Bridge saves only the scoped source/revision through Python", async () => {
  const { bridge, session, calls } = await startedBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/api/marks`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        sourceVersion: review.source_version,
        marks: [
          {
            mark_id: "m1",
            field_anchor: "content-overview",
            exact_text: "",
            prefix: "",
            suffix: "",
            comment: "补充身份说明",
          },
        ],
      }),
    });
    assert.equal(response.status, 200);
    assert.equal(calls.at(-1).operation, "save-review-marks");
    assert.equal(calls.at(-1).expected_revision, 7);
    assert.equal(calls.at(-1).source_version, review.source_version);

    const stale = await fetch(`${origin}/api/marks`, {
      method: "POST",
      headers: {
        ...bearer(session),
        Origin: origin,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 8,
        sourceVersion: review.source_version,
        marks: [],
      }),
    });
    assert.equal(stale.status, 409);
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

test("content evidence session exposes only one exact slide/material and adjacent comparison", async () => {
  const { bridge, session, calls } = await startedEvidenceBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/api/review`, { headers: bearer(session) });
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.review.review_type, "content-evidence");
    assert.equal(payload.review.display_policy, "content-evidence-read-only");
    assert.equal(payload.review.evidence_view.slide.slide_id, "S01");
    assert.equal(payload.review.evidence_view.evidence.evidence_id, "EV-S01-01");
    assert.equal(payload.review.evidence_view.evidence.material_ref, "artifact://material/m1");
    assert.equal(payload.review.evidence_view.adjacent.next.slide_id, "S02");
    assert.equal(payload.review.evidence_view.asset.dataBase64, "YWJj");
    assert.deepEqual(payload.review.outline, []);
    assert.deepEqual(payload.review.sections, []);
    assert.deepEqual(payload.review.capabilities, {
      canSavePageDecision: false,
      canSaveReviewMarks: false,
      canCompareSourceAndSlide: true,
      canCompareAdjacentSlides: true,
    });
    assert.equal(calls.at(-1).operation, "get-content-sidebar-review-projection");
  } finally {
    await bridge.stop();
  }
});

test("v2.2 evidence session binds the parent ReviewSession and typed material without requiring an image", async () => {
  const { bridge, session, calls } = await startedFormalEvidenceBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    const response = await fetch(`${origin}/api/review`, { headers: bearer(session) });
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.review.review_type, "content-evidence");
    assert.equal(payload.review.evidence_view.slide.slide_id, "S01");
    assert.equal(payload.review.evidence_view.evidence.evidence_id, "EV-S01-01");
    assert.equal(payload.review.evidence_view.evidence.material_ref, "artifact://material/m1");
    assert.deepEqual(payload.review.source_refs, ["artifact://source/s1#page=3"]);
    assert.deepEqual(payload.review.gate_status, {});
    assert.equal(payload.review.evidence_view.asset, null);
    assert.equal(payload.review.capabilities.canSavePageDecision, false);
    assert.equal(payload.review.capabilities.canSaveReviewMarks, false);
    assert.equal(calls.at(-1).operation, "get-content-full-deck-review-projection");
    assert.equal(calls.at(-1).review_session_id, "review-session-current-v22");
  } finally {
    await bridge.stop();
  }
});

test("content evidence session rejects marks, switches, and scope drift without writes", async () => {
  const { bridge, session, calls } = await startedEvidenceBridge();
  try {
    const origin = `http://${session.host}:${session.port}`;
    for (const path of ["/api/marks", "/api/switch"]) {
      const response = await fetch(`${origin}${path}`, {
        method: "POST",
        headers: { ...bearer(session), Origin: origin, "Content-Type": "application/json" },
        body: JSON.stringify({ marks: [], reviewType: "visual" }),
      });
      assert.equal(response.status, 405);
    }
    assert.equal(calls.some((call) => call.operation === "save-review-marks"), false);
  } finally {
    await bridge.stop();
  }

  const drifted = structuredClone(contentSidebarReview);
  drifted.slides[0].evidence_items[0].material_ref = "artifact://material/changed";
  const stale = await startedEvidenceBridge({
    invokeBridge: async () => ({ ok: true, review: drifted, snapshot_revision: 7 }),
  });
  try {
    const origin = `http://${stale.session.host}:${stale.session.port}`;
    const response = await fetch(`${origin}/api/review`, { headers: bearer(stale.session) });
    assert.equal(response.status, 409);
    assert.equal((await response.json()).error.code, "REVIEW_SOURCE_STALE");
  } finally {
    await stale.bridge.stop();
  }
});
