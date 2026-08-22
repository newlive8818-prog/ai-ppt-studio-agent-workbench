# Codex Host Form Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Codex Desktop confirmations through its negotiated `openai/form` extension so a real `_meta:null` acceptance reaches AI PPT Studio, while preserving standard MCP elicitation for other hosts and every existing Gate safety check.

**Architecture:** Add one narrow host-form transport selector and one request helper in the Node MCP boundary. The helper prefers `capabilities.extensions["openai/form"]`, falls back to SDK `elicitInput()` only when the extension is absent and standard elicitation is present, and never retries a second channel after a response error. Mission, Gate, and revision-plan callers keep their explicit `accept && confirmed === true` checks and existing version-bound assertion path; Python Runtime remains the final verifier and writer.

**Tech Stack:** Node.js ESM, `@modelcontextprotocol/sdk` 1.30.0, Zod 4, Node test runner, Python Runtime regression suite.

---

## File map

- Modify `mcp/server.mjs`: define the `openai/form` result Schema, select the negotiated transport, send one form request, and route the three existing confirmation functions through it.
- Modify `tests/mcp-server.test.mjs`: define a custom `openai/form` request Schema and add extension success, priority, standard failure evidence, no-write, and no-auto-retry regressions.
- No Runtime, UI, project-state, package-lock, dependency, Codex application, or installed-plugin source edits.

## Current CRS acceptance topology

Implementation and release acceptance must preserve the user's current environment:

```text
config model_provider=crs, wire_api=responses
-> /Applications/ChatGPT.app
-> /Applications/ChatGPT.app/Contents/Resources/codex
-> local MCP stdio
-> AI PPT Studio
```

The CRS provider is the model API upstream; current process and desktop-log evidence show that ChatGPT/Codex App Server remains the MCP client and form host. No production test should send project material, confirmation content, assertions, or secrets directly to CRS. Automated protocol tests remain local and in-memory. The final real G0 test must run with the current CRS configuration unchanged.

### Task 1: Establish the protocol fixtures and RED evidence

**Files:**
- Modify: `tests/mcp-server.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Import Zod and define the custom Codex request Schema**

Add:

```js
import { z } from "zod";

const OpenAIFormRequestSchema = z.object({
  method: z.literal("openai/form"),
  params: z.looseObject({
    message: z.string(),
    requestedSchema: z.record(z.string(), z.unknown()),
  }),
});
```

This Schema intentionally uses a non-standard method name, so SDK Client does not wrap its handler with the standard `ElicitResultSchema`.

- [ ] **Step 2: Add a reusable Gate context fixture**

Add beside the existing snapshot fixture:

```js
function gateConfirmationContext() {
  return {
    project_id: "p1",
    project_root: "/managed/project",
    gate: "G0",
    scope_kind: "gate",
    scope_id: "G0",
    source_version: "content-v1",
    evidence_refs: ["artifact://test-evidence/" + "b".repeat(64)],
    challenge_id: "a".repeat(64),
    challenge_revision: 3,
    review_summary: "G0 当前完整审阅源。",
  };
}
```

Use this fixture in newly added tests; do not mechanically rewrite unrelated existing tests.

- [ ] **Step 3: Add the desired Codex extension success test**

Add before the existing standard host-native Gate test:

```js
test("Codex openai/form Gate confirmation accepts nullable metadata once", async () => {
  const calls = [];
  const forms = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-gate-confirmation-context") {
        return { ok: true, confirmation_context: gateConfirmationContext() };
      }
      return { ok: true, result: { snapshot: { ...snapshot, revision: 4 } } };
    },
  });
  const client = new Client(
    { name: "gate-openai-form-test", version: "0.1.0" },
    { capabilities: { extensions: { "openai/form": {} } } },
  );
  client.setRequestHandler(OpenAIFormRequestSchema, async (request) => {
    forms.push(request.params);
    return {
      action: "accept",
      content: { confirmed: true },
      _meta: null,
    };
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G0",
      },
    });
    assert.equal(result.isError, undefined);
    assert.equal(forms.length, 1);
    assert.match(forms[0].message, /G0 当前完整审阅源/);
    assert.deepEqual(
      calls.map((call) => call.operation),
      ["get-gate-confirmation-context", "confirm-gate"],
    );
    const write = calls.at(-1);
    assert.equal(write.source_version, "content-v1");
    assert.equal(write.challenge_id, "a".repeat(64));
    assert.equal(write.challenge_revision, 3);
    const [, payloadSegment] = write.host_confirmation_assertion.split(".");
    const payload = JSON.parse(
      Buffer.from(payloadSegment, "base64url").toString("utf8"),
    );
    assert.equal(payload.identity_type, "host-action");
    assert.match(payload.identity_ref, /^host-elicitation:\/\//);
  } finally {
    await client.close();
  }
});
```

- [ ] **Step 4: Run the extension test and verify RED**

Run:

```bash
node --test --test-name-pattern='Codex openai/form Gate confirmation' tests/mcp-server.test.mjs
```

Expected: FAIL because current production code checks only `capabilities.elicitation` and returns `HOST_CONFIRMATION_UNAVAILABLE`; no `openai/form` request or `confirm-gate` write occurs.

- [ ] **Step 5: Lock in the first design's upstream failure**

Add:

```js
test("standard elicitation rejects nullable metadata before the plugin can consume it", async () => {
  const calls = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-gate-confirmation-context") {
        return { ok: true, confirmation_context: gateConfirmationContext() };
      }
      throw new Error("nullable standard response must not reach confirm-gate");
    },
  });
  const client = new Client(
    { name: "gate-standard-null-test", version: "0.1.0" },
    { capabilities: { elicitation: { form: {} } } },
  );
  client.setRequestHandler(ElicitRequestSchema, async () => ({
    action: "accept",
    content: { confirmed: true },
    _meta: null,
  }));
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  try {
    const result = await client.callTool({
      name: "confirm_ai_ppt_gate",
      arguments: {
        projectRoot: "/managed/project",
        expectedRevision: 3,
        gate: "G0",
      },
    });
    assert.equal(result.isError, true);
    assert.equal(
      result.structuredContent.error.code,
      "HOST_CONFIRMATION_UNAVAILABLE",
    );
    assert.deepEqual(
      calls.map((call) => call.operation),
      ["get-gate-confirmation-context"],
    );
  } finally {
    await client.close();
  }
});
```

Run:

```bash
node --test --test-name-pattern='standard elicitation rejects nullable metadata' tests/mcp-server.test.mjs
```

Expected: PASS as a documented negative capability test. It proves the standard channel cannot deliver this host variation and must not be interpreted as a confirmation.

- [ ] **Step 6: Commit the test-only RED checkpoint**

```bash
git add tests/mcp-server.test.mjs
git commit -m "test: reproduce Codex host form protocol boundary"
```

The desired extension test remains failing at this checkpoint; do not run the full suite or represent the branch as green.

### Task 2: Implement one-shot host-form transport selection

**Files:**
- Modify: `mcp/server.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Import Zod and define the extension result Schema**

Add:

```js
import { z } from "zod";

const OpenAIFormResultSchema = z.looseObject({
  _meta: z.record(z.string(), z.unknown()).nullable().optional(),
  action: z.enum(["accept", "decline", "cancel"]),
  content: z.record(z.string(), z.unknown()).nullable().optional(),
});
```

The Schema accepts only the host's nullable metadata variation. It does not manufacture an action, confirmation, identity, revision, challenge, or assertion.

- [ ] **Step 2: Add the transport selector**

Add after the manifest initialization:

```js
function hostFormTransport(server) {
  const capabilities = server.server.getClientCapabilities() || {};
  if (capabilities.extensions?.["openai/form"]) return "openai-form";
  if (capabilities.elicitation) return "standard-elicitation";
  return null;
}
```

Extension priority is deliberate. Do not use truthiness of a form result to select or switch channels.

- [ ] **Step 3: Add the one-shot request helper**

Add:

```js
async function requestHostForm(server, params, transport) {
  if (transport === "openai-form") {
    return server.server.request(
      { method: "openai/form", params },
      OpenAIFormResultSchema,
    );
  }
  if (transport === "standard-elicitation") {
    return server.server.elicitInput({ ...params, mode: "form" });
  }
  throw new Error("Host form transport is unavailable");
}
```

The helper sends exactly one request. It contains no catch-and-fallback path.

- [ ] **Step 4: Route Mission confirmation through the helper**

At the start of `requestHostMissionConfirmation`:

```js
const transport = hostFormTransport(server);
if (!transport) {
  return {
    ok: false,
    error: {
      code: "HOST_CONFIRMATION_UNAVAILABLE",
      message: "当前宿主未提供原生确认能力；任务卡已保留，可在能力可用后重试。",
      details: {},
    },
  };
}
```

Replace `server.server.elicitInput({...})` with:

```js
requestHostForm(server, {
  message: prompt.message,
  requestedSchema: {
    type: "object",
    properties: {
      confirmed: {
        type: "boolean",
        title: "确认当前任务卡并继续",
        default: false,
      },
    },
    required: ["confirmed"],
  },
}, transport)
```

In the catch result, use:

```js
details: { phase: "host-form-response", transport },
```

- [ ] **Step 5: Route Gate and revision-plan confirmations identically**

For `requestHostGateConfirmation` and `requestHostRevisionPlanConfirmation`, replace the old capability check with `hostFormTransport(server)`, call `requestHostForm(server, params, transport)`, and add only non-sensitive diagnostics:

```js
details: {
  gate: context.gate,
  phase: "host-form-response",
  transport,
}
```

```js
details: {
  planRef: context.scope_id,
  phase: "host-form-response",
  transport,
}
```

Keep all existing decline/cancel handling, `confirmed === true` checks, identity generation, assertion signing, and Runtime request construction unchanged.

- [ ] **Step 6: Run the desired extension test and verify GREEN**

Run:

```bash
node --test --test-name-pattern='Codex openai/form Gate confirmation' tests/mcp-server.test.mjs
```

Expected: PASS; one `openai/form` request and one `confirm-gate` write occur.

- [ ] **Step 7: Run the standard nullable negative test**

Run:

```bash
node --test --test-name-pattern='standard elicitation rejects nullable metadata' tests/mcp-server.test.mjs
```

Expected: PASS; standard SDK validation still prevents the write, and production code does not infer acceptance from the error.

### Task 3: Verify extension priority, no-write outcomes, and no automatic retry

**Files:**
- Modify: `tests/mcp-server.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Add extension-priority coverage**

Add a test client with both capabilities:

```js
{
  capabilities: {
    extensions: { "openai/form": {} },
    elicitation: { form: {} },
  },
}
```

Register both request handlers. Return success from `openai/form`; increment a counter and throw from the standard handler. Assert:

```js
assert.equal(openAIFormCount, 1);
assert.equal(standardElicitationCount, 0);
assert.deepEqual(
  calls.map((call) => call.operation),
  ["get-gate-confirmation-context", "confirm-gate"],
);
```

- [ ] **Step 2: Add table-driven extension no-write coverage**

Use these responses:

```js
[
  { name: "decline", response: { action: "decline", content: null, _meta: null } },
  { name: "cancel", response: { action: "cancel", content: null, _meta: null } },
  {
    name: "confirmed false",
    response: { action: "accept", content: { confirmed: false }, _meta: null },
  },
  {
    name: "confirmed missing",
    response: { action: "accept", content: {}, _meta: null },
  },
]
```

For each response, call `confirm_ai_ppt_gate` and assert:

```js
assert.equal(result.isError, true, name);
assert.equal(
  result.structuredContent.error.code,
  "HOST_CONFIRMATION_DECLINED",
  name,
);
assert.deepEqual(
  calls.map((call) => call.operation),
  ["get-gate-confirmation-context"],
  name,
);
```

- [ ] **Step 3: Add protocol-error no-auto-retry coverage**

Create a client that declares both capabilities. Make `openai/form` throw `new Error("host form failed")`; register a standard handler that increments `standardElicitationCount`. Assert:

```js
assert.equal(result.isError, true);
assert.equal(
  result.structuredContent.error.code,
  "HOST_CONFIRMATION_UNAVAILABLE",
);
assert.equal(result.structuredContent.error.details.transport, "openai-form");
assert.equal(result.structuredContent.error.details.phase, "host-form-response");
assert.equal(standardElicitationCount, 0);
assert.deepEqual(
  calls.map((call) => call.operation),
  ["get-gate-confirmation-context"],
);
```

- [ ] **Step 4: Run all focused host-form tests**

Run:

```bash
node --test --test-name-pattern='openai/form|standard elicitation rejects nullable metadata|host form' tests/mcp-server.test.mjs
```

Expected: all matching tests PASS with no unhandled rejection.

- [ ] **Step 5: Run the complete MCP server test file**

Run:

```bash
node --test tests/mcp-server.test.mjs
```

Expected: all tests PASS. Existing standard host-native Mission, Gate, and revision-plan confirmation tests prove fallback compatibility.

- [ ] **Step 6: Commit the implementation**

```bash
git add mcp/server.mjs tests/mcp-server.test.mjs
git commit -m "fix: route Codex confirmations through openai form"
```

Do not amend the design or plan commits, and do not stage generated output or formal project data.

### Task 4: Complete engineering verification

**Files:**
- Verify only; no planned additional production files.

- [ ] **Step 1: Run the complete Node, MCP, Widget, typecheck, and build quality suite**

```bash
npm run quality
```

Expected: typecheck, production build, Node/MCP/Review Bridge tests, and Widget tests all PASS.

- [ ] **Step 2: Run the complete Python Runtime regression**

```bash
npm run test:python
```

Expected: all Python tests PASS.

- [ ] **Step 3: Verify repository hygiene**

```bash
git diff --check
git status --short
```

Expected: `git diff --check` emits no output and `git status --short` is empty after the implementation commit.

### Task 5: Build, verify, and install the release candidate

**Files:**
- Verify release and install scripts already present; do not edit formal project state.

- [ ] **Step 1: Build and verify the plugin release candidate**

```bash
npm run release -- --output /private/tmp/ai-ppt-studio-null-meta-release
npm run verify:release -- --release /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio
```

Expected: both commands exit zero; verification reports `ok: true`, plugin identity `ai-ppt-studio`, a release-manifest SHA-256, and a passing MCP probe.

- [ ] **Step 2: Install the verified release**

```bash
npm run install:plugin -- \
  --release /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio \
  --target /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
```

Expected: command exits zero and returns `ok: true` with the exact target as `installRoot`. Do not manually patch installed source or dependencies.

- [ ] **Step 3: Compare release and installed source**

```bash
shasum -a 256 \
  /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio/mcp/server.mjs \
  /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/mcp/server.mjs
```

Expected: the two SHA-256 values are identical.

### Task 6: Perform the single real G0 host retry

**Files:**
- No source edits and no direct project-state edits.

- [ ] **Step 1: Completely restart Codex/MCP**

Before restart, read only these non-secret configuration keys and confirm they remain:

```text
model_provider = "crs"
wire_api = "responses"
```

Do not print or copy the CRS credential, token, authorization header, or full process environment.

Fully quit and reopen Codex so the stdio MCP process cannot retain the pre-install module. Resume this task and verify one AI PPT project tool is callable. Inspect the new desktop startup log under:

```text
/Users/defei/Library/Logs/com.openai.codex/2026/08/22/
```

Expected:

```text
running host = /Applications/ChatGPT.app
MCP/App Server = /Applications/ChatGPT.app/Contents/Resources/codex
model provider = crs
wire API = responses
loaded plugin = ai-ppt-studio@defei-ai-ppt-studio-040
```

The skipped duplicate `ai-ppt-studio@personal` warning remains a separate cleanup item.

- [ ] **Step 2: Refresh the formal project snapshot**

Read:

```text
/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7
```

Do not assume the historical `revision = 23` remains current. Resolve the current revision, Gate status, sourceVersion, evidence refs, and challenge immediately before the retry.

- [ ] **Step 3: Perform exactly one real host-native G0 confirmation**

With the CRS configuration still active, call `confirm_ai_ppt_gate` with the refreshed current revision and `gate = G0`. The user must take the real host form action. Do not provide a fabricated `userMessageRef`, receipt, or assertion.

- [ ] **Step 4: Refresh the authoritative snapshot and classify the result**

Success requires all of:

```text
the tool returns success
revision advances
G0 is confirmed/passed in the refreshed authoritative snapshot
Runtime history binds the confirmation to the current challenge
```

If any item is missing, report the exact failing boundary and do not enter visual production. If all items hold, classify real G0 host acceptance under the current CRS channel as complete and proceed to the already-approved visual-production sequence.
