# Codex Host Elicitation Null Meta Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow AI PPT Studio to consume a real Codex Desktop form-elicitation acceptance when the host returns `_meta: null`, without weakening Gate confirmation or Runtime verification.

**Architecture:** Add one narrow response schema and one shared host-form request helper at the Node MCP boundary. The helper continues to use the MCP SDK Server's public `request()` method and the standard `elicitation/create` method, while accepting only the host's nullable metadata variation; Mission, Gate, and revision-plan flows retain their existing explicit `accept` and `confirmed === true` checks and their existing signed assertion path.

**Tech Stack:** Node.js ESM, `@modelcontextprotocol/sdk` 1.30.0, Zod, Node test runner, Python Runtime regression suite.

---

## File map

- Modify `mcp/server.mjs`: define the compatible elicitation-result schema and shared request helper; route the three existing host-confirmation functions through it.
- Modify `tests/mcp-server.test.mjs`: reproduce Codex Desktop's `_meta: null` response and prove the Gate write remains version-bound; prove non-confirmations make no write.
- No Runtime, UI, project-state, package-lock, or third-party dependency file changes.

### Task 1: Reproduce the Codex Desktop response at the MCP boundary

**Files:**
- Modify: `tests/mcp-server.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Change the host-native Gate test to return the real desktop response**

In `host-native Gate confirmation signs a host action for the current revision`, change the elicitation handler to:

```js
client.setRequestHandler(ElicitRequestSchema, async (request) => {
  elicitations.push(request.params);
  return {
    action: "accept",
    content: { confirmed: true },
    _meta: null,
  };
});
```

Keep all existing assertions that require one `confirm-gate` call, a signed host assertion, the exact source version, revision, evidence refs, and challenge.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
node --test --test-name-pattern='host-native Gate confirmation' tests/mcp-server.test.mjs
```

Expected: FAIL because the current SDK `ElicitResultSchema` rejects `_meta: null`; the tool returns `HOST_CONFIRMATION_UNAVAILABLE` instead of calling `confirm-gate`.

- [ ] **Step 3: Record the RED evidence before production changes**

Confirm the failure is a result-schema failure, not a test setup or assertion typo. Do not modify `mcp/server.mjs` until this failure is observed.

### Task 2: Add the narrow compatible host-form request boundary

**Files:**
- Modify: `mcp/server.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Import Zod and define the compatible result schema**

Add the import:

```js
import { z } from "zod";
```

After the plugin manifest initialization, add:

```js
const HostElicitResultSchema = z.looseObject({
  _meta: z.record(z.string(), z.unknown()).nullish(),
  action: z.enum(["accept", "decline", "cancel"]),
  content: z
    .record(
      z.string(),
      z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]),
    )
    .nullish(),
});

async function requestHostForm(server, params) {
  return server.server.request(
    {
      method: "elicitation/create",
      params: { ...params, mode: "form" },
    },
    HostElicitResultSchema,
  );
}
```

This accepts only the metadata difference. It does not manufacture an acceptance, identity reference, assertion, revision, or challenge.

- [ ] **Step 2: Route all three host confirmation forms through the helper**

In these functions:

```text
requestHostMissionConfirmation
requestHostGateConfirmation
requestHostRevisionPlanConfirmation
```

replace only:

```js
server.server.elicitInput({
```

with:

```js
requestHostForm(server, {
```

Keep each function's existing requested schema, message, capability check, decline/cancel handling, `confirmed === true` check, and identity/assertion logic unchanged.

- [ ] **Step 3: Make protocol-phase failures diagnosable without changing write behavior**

Change the three elicitation catch blocks so their details include the phase while preserving their current error codes and user messages. Gate example:

```js
details: { gate: context.gate, phase: "elicitation-response" },
```

Mission example:

```js
details: { phase: "elicitation-response" },
```

Revision-plan example:

```js
details: {
  planRef: context.scope_id,
  phase: "elicitation-response",
},
```

Do not include raw form content, signed assertions, secrets, or user data in error details.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
node --test --test-name-pattern='host-native Gate confirmation' tests/mcp-server.test.mjs
```

Expected: PASS. The handler receives one form request; the tool performs exactly one `confirm-gate` call; the assertion identity type remains `host-action`.

### Task 3: Lock down decline, cancel, false, and malformed confirmation behavior

**Files:**
- Modify: `tests/mcp-server.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Add a table-driven no-write regression**

Add a test beside the host-native Gate success test:

```js
test("host-native Gate confirmation rejects non-confirming form responses without a write", async () => {
  const responses = [
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
  ];

  for (const { name, response } of responses) {
    const calls = [];
    const server = createAiPptMcpServer({
      invokeBridge: async (request) => {
        calls.push(request);
        if (request.operation !== "get-gate-confirmation-context") {
          throw new Error(`${name} must not reach confirm-gate`);
        }
        return {
          ok: true,
          confirmation_context: {
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
          },
        };
      },
    });
    const client = new Client(
      { name: `gate-${name}-test`, version: "0.1.0" },
      { capabilities: { elicitation: { form: {} } } },
    );
    client.setRequestHandler(ElicitRequestSchema, async () => response);
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
      assert.equal(result.isError, true, name);
      assert.equal(result.structuredContent.error.code, "HOST_CONFIRMATION_DECLINED", name);
      assert.deepEqual(
        calls.map((call) => call.operation),
        ["get-gate-confirmation-context"],
        name,
      );
    } finally {
      await client.close();
    }
  }
});
```

- [ ] **Step 2: Run the two focused host-native tests**

Run:

```bash
node --test --test-name-pattern='host-native Gate confirmation' tests/mcp-server.test.mjs
```

Expected: both the successful nullable-metadata case and all four no-write cases PASS.

- [ ] **Step 3: Run the complete MCP server test file**

Run:

```bash
node --test tests/mcp-server.test.mjs
```

Expected: all tests in `tests/mcp-server.test.mjs` PASS with no unhandled rejection or warning.

### Task 4: Complete engineering verification

**Files:**
- Verify only; no planned additional production files.

- [ ] **Step 1: Run the complete Node, MCP, Widget, typecheck, and build quality suite**

Run:

```bash
npm run quality
```

Expected: typecheck, production build, Node/MCP/Review Bridge tests, and Widget tests all PASS.

- [ ] **Step 2: Run the complete Python Runtime regression**

Run:

```bash
npm run test:python
```

Expected: all Python tests PASS.

- [ ] **Step 3: Verify repository hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` emits no output; `git status --short` lists only the planned `mcp/server.mjs`, `tests/mcp-server.test.mjs`, and this implementation-plan commit if it has not yet been committed.

- [ ] **Step 4: Commit the implementation**

Stage exact files only:

```bash
git add mcp/server.mjs tests/mcp-server.test.mjs
git commit -m "fix: accept nullable host elicitation metadata"
```

Do not amend an unrelated commit and do not stage generated output or user project data.

### Task 5: Build, install, and perform the single real G0 retry

**Files:**
- Verify release/install scripts already present in the repository; do not edit formal project state directly.

- [ ] **Step 1: Build and verify the plugin release candidate**

Run:

```bash
npm run release -- --output /private/tmp/ai-ppt-studio-null-meta-release
npm run verify:release -- --release /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio
```

Expected: both commands exit zero; verification reports `ok: true`, the plugin identity `ai-ppt-studio`, a release-manifest SHA-256, and a passing MCP probe.

- [ ] **Step 2: Install the verified release candidate**

Run:

```bash
npm run install:plugin -- \
  --release /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio \
  --target /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
```

Expected: command exits zero and returns `ok: true` with the exact target as `installRoot`. Do not manually patch the installed `node_modules` or installed `mcp/server.mjs`.

Verify the installed source identity:

```bash
shasum -a 256 \
  /private/tmp/ai-ppt-studio-null-meta-release/ai-ppt-studio/mcp/server.mjs \
  /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/mcp/server.mjs
```

Expected: the two SHA-256 values are identical.

- [ ] **Step 3: Restart Codex/MCP and verify the loaded plugin identity**

After installation, fully quit and reopen Codex so the stdio MCP process cannot retain the pre-install module. Resume this task, call the AI PPT project snapshot tool once, and inspect the new desktop startup log under:

```text
/Users/defei/Library/Logs/com.openai.codex/2026/08/22/
```

Expected: the tool is callable and the loader selects `ai-ppt-studio@defei-ai-ppt-studio-040`. Treat the separate skipped duplicate `ai-ppt-studio@personal` warning as a later cleanup item.

- [ ] **Step 4: Refresh the formal project before confirmation**

Read the formal project snapshot at:

```text
/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7
```

Expected before the retry unless another authorized process changed it:

```text
revision = 23
G0 = user-reviewable
```

If revision or Gate differs, stop and re-resolve the current confirmation context; do not reuse revision 23 assumptions.

- [ ] **Step 5: Perform exactly one real host-native G0 confirmation**

Call `confirm_ai_ppt_gate` with the refreshed current revision and `gate = G0`. The user must take the real host form action. Do not provide a fabricated `userMessageRef`, receipt, or assertion.

- [ ] **Step 6: Refresh the snapshot and classify the result**

Success requires all of:

```text
the tool returns success
revision advances
G0 is confirmed in the refreshed authoritative snapshot
the Runtime history records the confirmation against the current challenge
```

If any item is missing, report the exact failing boundary and do not enter visual production. If all items hold, mark real G0 host acceptance complete and proceed to the already-approved visual-production sequence.
