# Review Bridge Adapter Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the v2.2 `open_or_resume_review_session` MCP tool to the existing source-bound Review Bridge so a fresh Codex host receives a scoped Browser URL without requiring an impossible cross-process JavaScript adapter injection.

**Architecture:** Keep Python Runtime as the only business writer. After the Runtime returns the authoritative current ReviewSession and snapshot revision, the Node MCP server creates one short-lived loopback Review Bridge bound to the Runtime-selected project, review type, session, source version, and revision. The tool returns `review-session-ready` plus the scoped URL for the Agent's Codex In-app Browser; an explicitly injected compatibility adapter may open the URL, but adapter failure falls back to the same Agent handoff and never records a host-open receipt.

**Tech Stack:** Node.js ESM, `@modelcontextprotocol/sdk`, existing `mcp/review-bridge.mjs`, Node test runner, existing v2.2 typed MCP catalog.

---

### Task 1: Add the failing MCP handoff tests

**Files:**
- Modify: `产品代码/tests/mcp-server.test.mjs` near the existing ReviewSession tool mapping tests.
- Read-only reference: `产品代码/mcp/review-bridge.mjs` for the `start()` session shape.

- [ ] **Step 1: Write the failing test for a Runtime-bound Agent Browser handoff**

Add a test that injects an `invokeBridge` returning a Runtime result whose `selected_project_root`, `result.session.review_type`, `result.session.review_session_id`, `result.session.source_version`, and `result.snapshot.revision` are deliberately different from the caller's duplicate values. Inject a `reviewBridgeFactory` that records its scope and returns `start()` data containing a scoped fragment URL, `expiresAt`, and `bridgeSessionId`. Call `open_or_resume_review_session` and assert:

```js
assert.equal(result.isError, undefined);
assert.equal(result.structuredContent.status, "review-session-ready");
assert.equal(result.structuredContent.opened, false);
assert.equal(result.structuredContent.openMode, "agent-browser");
assert.equal(result.structuredContent.browserAction, "open-scoped-url");
assert.match(result.structuredContent.url, /^http:\/\/127\.0\.0\.1:\d+\/#token=/);
assert.deepEqual(factoryScope, {
  projectRoot: "/runtime/project",
  reviewType: "visual-professional",
  reviewSessionId: "runtime-session",
  sourceVersion: "runtime-source",
  expectedRevision: 9,
});
```

- [ ] **Step 2: Write the failing compatibility-adapter tests**

Add two tests using the same fake bridge: one with `{ canOpen: true, openUrl: async () => ({ opened: true }) }` that expects `status: "opened"`, `opened: true`, and `openMode: "host-adapter"`; one with `{ canOpen: true, openUrl: async () => ({ opened: false }) }` that expects the untouched Agent handoff (`review-session-ready`, `opened: false`) and verifies the bridge `stop()` was not called. This proves a failed optional adapter does not destroy the session or fabricate a Browser-unavailable error.

- [ ] **Step 3: Write the failing source/error tests**

Add a test where `reviewBridgeFactory` throws an error with code `REVIEW_BRIDGE_UNAVAILABLE` and assert the MCP result is an error with that exact code. Add a test where the Runtime result has a stale/missing session source and assert the handler returns an error without invoking `reviewBridgeFactory`; no URL or host-open receipt may be emitted.

- [ ] **Step 4: Run only the new tests and verify RED**

Run:

```bash
node --test tests/mcp-server.test.mjs --test-name-pattern="Review Bridge|review-session-ready|Browser handoff"
```

Expected: the new tests fail because `openOrResumeReviewSession` is still the generic Runtime handler and `reviewBridgeFactory` is not wired. Existing unrelated tests may pass.

### Task 2: Implement the minimal Review Bridge adapter wiring

**Files:**
- Modify: `产品代码/mcp/server.mjs` imports, constants, `createAiPptMcpServer` options, scoped bridge helpers, and the `openOrResumeReviewSession` handler entry.

- [ ] **Step 1: Import the existing bridge and define the built Browser shell path**

Add `createReviewBridge` from `./review-bridge.mjs` and define `BROWSER_REVIEW_HTML` below `ROOT` as `path.join(ROOT, "widget", "dist", "index.html")`. Keep the shell read deferred through `readFileSync` inside `readReviewHtml` so a missing build fails as a Review shell error when navigated, not during MCP startup.

- [ ] **Step 2: Add scoped bridge creation helpers inside `createAiPptMcpServer`**

Resolve `reviewBridgeFactory = options.reviewBridgeFactory || createReviewBridge` and `browserSurfaceAdapter = options.browserSurfaceAdapter || null`. Add a helper that receives only Runtime-derived scope values and constructs the existing bridge with:

```js
{
  projectRoot,
  reviewType,
  reviewSessionId,
  sourceVersion,
  expectedRevision,
  invokeBridge,
  readReviewHtml: () => readFileSync(BROWSER_REVIEW_HTML, "utf8"),
  readProjectAsset: readProjectAssetFn,
  notifyHost: options.notifyHost,
  verifyAiReceipt: options.verifyAiReceipt,
}
```

Start the bridge and return its `{ bridge, session }`. Add a target-session callback for `/api/switch` that reads the Runtime projection for the requested target type, validates `review_session_id`, `source_version`, and `snapshot_revision`, then uses the same helper. Do not write Runtime state from the helper.

- [ ] **Step 3: Replace the generic open handler with the two-stage handoff**

The handler first calls the existing `genericRequest(operation, input)` and unwraps `outcome.payload.result`. It must reject an invalid Runtime result before creating a bridge. Use only `selected_project_root`, `session.review_type`, `session.review_session_id`, `session.source_version`, and `snapshot.revision` from that result for the Bridge scope. Return `REVIEW_BRIDGE_UNAVAILABLE` if bridge construction/start fails. On success, return the original Runtime result fields plus:

```js
{
  status: "review-session-ready" | "opened",
  opened: false | true,
  openMode: "agent-browser" | "host-adapter",
  browserAction: "open-scoped-url",
  url: session.url,
  expiresAt: session.expiresAt,
  bridgeSessionId: session.bridgeSessionId,
  projectRoot,
  reviewType,
  reviewSessionId,
  sourceVersion,
  revision: expectedRevision,
}
```

If `browserSurfaceAdapter.canOpen` is truthy and `openUrl(session.url)` resolves with `{ opened: true }`, mark the result `opened`/`host-adapter`; otherwise preserve the running bridge and return `review-session-ready`/`agent-browser`. Never call `record-review-bridge-host-open` from this handler; the Browser page records host-open only after its authenticated projection read.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
node --test tests/mcp-server.test.mjs --test-name-pattern="Review Bridge|review-session-ready|Browser handoff"
```

Expected: all new handoff, adapter fallback, and bridge-error tests pass with no Runtime write beyond the one requested `open-or-resume-review-session` call.

### Task 3: Refactor checks and full engineering verification

**Files:**
- Modify only the files listed above if a test-driven cleanup is required; otherwise no further source changes.

- [ ] **Step 1: Run syntax and diff checks**

```bash
node --check mcp/server.mjs
git diff --check
```

Expected: exit 0 and no whitespace errors.

- [ ] **Step 2: Run the complete Node, Python, Widget, typecheck, and build gates**

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

Expected: every command exits 0. Run loopback/Vite commands with the approved non-sandbox environment if the sandbox reproduces the known `listen EPERM` or `.vite-temp` restrictions; report those environment boundaries separately.

- [ ] **Step 3: Build and inspect the release candidate**

Run the existing release builder and verifier in a fresh `/private/tmp` directory, then inspect the manifest to confirm the modified `mcp/server.mjs`, `mcp/review-bridge.mjs`, and built Browser shell are present while tests, `.git`, and raw source-only artifacts are absent. Do not install or refresh the host cache until this candidate is independently verified.

- [ ] **Step 4: Commit the implementation atomically**

```bash
git add -- mcp/server.mjs tests/mcp-server.test.mjs docs/superpowers/plans/2026-08-27-review-bridge-adapter.md
git commit -m "fix: wire review bridge browser handoff"
```

Do not amend, merge, push, or modify the quarantine checkout. The commit proves implementation identity only; integration and fresh-host acceptance remain separate states.

### Task 4: Fresh-host Browser evidence after release propagation

**Files:**
- No source changes; use the installed release/cache and the managed technical acceptance fixture only.

- [ ] **Step 1: Install the verified candidate and refresh the Codex plugin cache**

Use the existing release/install/cache-refresh workflow and record candidate identity separately from installed/cache identity.

- [ ] **Step 2: Start a fresh MCP session and call `open_or_resume_review_session`**

Confirm the fresh tool result contains `review-session-ready`, a scoped fragment URL, Runtime-derived scope, and no Runtime state change before Browser navigation.

- [ ] **Step 3: Navigate the returned URL with the Codex In-app Browser**

Only after real Browser navigation succeeds, read the authenticated projection and verify that `/api/host-open` produces one Runtime host-open fact with the exact `bridgeSessionId`. Keep persistence, host notification, and AI receipt as independent evidence.

- [ ] **Step 4: Report boundaries**

Report implementation, commit, engineering verification, release verification, installation, cache refresh, fresh MCP, and real Browser evidence separately. Do not claim G0/G3/G4, public release, or user acceptance from this adapter unit alone.
