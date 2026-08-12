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
