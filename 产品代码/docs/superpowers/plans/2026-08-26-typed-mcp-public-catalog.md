# Typed MCP Public Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing 43-tool MCP public catalog structurally fail-closed and prove its exact descriptor, registration, Python-operation, and server-list contract without changing the public surface.

**Architecture:** Keep `mcp/tool-catalog.mjs` as the sole production descriptor list and keep schemas/handlers in the five domain registration files and server. Add frozen group metadata and module-load catalog validation, then bind the accepted catalog through independent tests, a fixed canonical hash, domain registration probes, Python parity, and real in-memory MCP listing.

**Tech Stack:** Node.js ESM, Node test runner, MCP SDK 1.29, Zod 4, Python 3 `unittest`, React/Vitest regression suite.

---

## File map

- Modify `tests/tool-catalog-consistency.test.mjs`: own the exact catalog fixture, structural negative tests, registration behavior tests, and existing Python parity proof.
- Modify `tests/mcp-server.test.mjs`: strengthen the existing live `listTools()` assertion across all 43 registered schemas without adding a second server tool list.
- Modify `mcp/tool-catalog.mjs`: own fixed group cardinality, construction validation, canonical hashing, and exact group registration checks.
- No domain tool, server handler, Python, Widget, Review Bridge, UI, or CSS file is expected to change.

### Task 1: Add failing fixed-catalog and registration tests

**Files:**
- Modify: `tests/tool-catalog-consistency.test.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Test: `tests/tool-catalog-consistency.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Extend the catalog imports and add the accepted fixture**

Import the not-yet-implemented group metadata, validator, hash, and registration function:

```js
import {
  PUBLIC_TOOL_CATALOG,
  PUBLIC_TOOL_CATALOG_SHA256,
  PUBLIC_TOOL_GROUP_COUNTS,
  assertPublicToolCatalog,
  registerCatalogGroup,
} from "../mcp/tool-catalog.mjs";
```

Add the fixed names and hash above the tests:

```js
const EXPECTED_TOOL_NAMES = [
  "create_ai_ppt_project",
  "get_ai_ppt_project_snapshot",
  "get_ai_ppt_project_status",
  "add_ai_ppt_material",
  "save_ai_ppt_mission_draft",
  "confirm_ai_ppt_mission",
  "request_ai_ppt_agent_action",
  "submit_ai_ppt_human_decision",
  "commit_ai_ppt_artifact",
  "confirm_ai_ppt_gate",
  "close_ai_ppt_project",
  "abort_ai_ppt_project",
  "reopen_ai_ppt_scope",
  "set_ai_ppt_release_target_policy",
  "read_ai_ppt_project_asset",
  "build_presales_evidence_book",
  "build_customer_decision_context",
  "build_problem_solution_fit",
  "build_reading_deck_blueprint",
  "run_content_evidence_gate",
  "run_content_presales_reading_gate",
  "repair_reading_deck_blueprint",
  "get_content_review_projection",
  "save_content_page_decision",
  "submit_content_review_batch",
  "withdraw_content_review_batch",
  "save_content_batch_revision_plan",
  "confirm_content_batch_revision_plan",
  "create_content_batch_change_set",
  "open_g0_review",
  "open_or_resume_review_session",
  "record_review_host_open_receipt",
  "record_review_host_notification_receipt",
  "record_review_ai_receipt",
  "get_visual_review_projection",
  "submit_visual_anchor_feedback_batch",
  "save_visual_contract_review_marks",
  "record_internal_gate",
  "get_delivery_status_projection",
  "record_chat_delivery",
  "recommend_experience",
  "record_experience_application",
  "summarize_project_experience",
];

const EXPECTED_CATALOG_SHA256 =
  "fc5fd70727aa8a793d9a4a63fe1007bbf3d4c5f0dacd3082e9153ce4303a7d88";

function frozenCatalog(mutator = () => {}) {
  const rows = PUBLIC_TOOL_CATALOG.map((tool) => ({ ...tool }));
  mutator(rows);
  return Object.freeze(rows.map((tool) => Object.freeze(tool)));
}
```

- [ ] **Step 2: Add the exact public-contract test**

```js
test("catalog freezes one exact 43-tool public contract", () => {
  assert.deepEqual(
    PUBLIC_TOOL_GROUP_COUNTS,
    { project: 15, content: 15, review: 4, visual: 3, "delivery-experience": 6 },
  );
  assert.deepEqual(PUBLIC_TOOL_CATALOG.map((tool) => tool.name), EXPECTED_TOOL_NAMES);
  assert.equal(PUBLIC_TOOL_CATALOG.length, 43);
  assert.equal(PUBLIC_TOOL_CATALOG_SHA256, EXPECTED_CATALOG_SHA256);
  assert.equal(Object.isFrozen(PUBLIC_TOOL_GROUP_COUNTS), true);
  assert.equal(Object.isFrozen(PUBLIC_TOOL_CATALOG), true);
  assert.equal(PUBLIC_TOOL_CATALOG.every(Object.isFrozen), true);
  assert.ok(PUBLIC_TOOL_CATALOG.every((tool) => tool.schema === tool.name));
  assert.deepEqual(
    PUBLIC_TOOL_CATALOG.map((tool) => Object.keys(tool)),
    Array.from({ length: 43 }, () => ["name", "group", "handler", "operation", "schema"]),
  );
  assertPublicToolCatalog(PUBLIC_TOOL_CATALOG);
});
```

The fixed hash binds every group, handler, operation, schema identity, row order, and field order, while the readable assertions expose names, groups, counts, shape, and schema identity directly.

- [ ] **Step 3: Add negative invariant tests**

Add table-driven cases that independently prove mutability, descriptor shape, identity, uniqueness, group completeness, operation rules, and the local-asset exception:

```js
test("catalog validation rejects structural drift", () => {
  assert.throws(() => assertPublicToolCatalog([...PUBLIC_TOOL_CATALOG]), /must be frozen/);

  const cases = [
    ["descriptor fields", (rows) => { rows[0].extra = true; }, /descriptor fields/],
    ["tool name", (rows) => { rows[0].name = " "; }, /tool name/],
    ["duplicate tool", (rows) => { rows[1].name = rows[0].name; }, /duplicate tool name/],
    ["schema identity", (rows) => { rows[0].schema = "wrong"; }, /schema identity/],
    ["handler identity", (rows) => { rows[0].handler = " "; }, /handler identity/],
    ["duplicate handler", (rows) => { rows[1].handler = rows[0].handler; }, /duplicate handler/],
    ["operation identity", (rows) => { rows[0].operation = " "; }, /operation identity/],
    ["duplicate operation", (rows) => { rows[1].operation = rows[0].operation; }, /duplicate operation/],
    ["local asset", (rows) => { rows[0].operation = null; }, /local-asset operation/],
    ["group count", (rows) => { rows[34].group = "review"; }, /group count/],
    ["unsupported group", (rows) => { rows[0].group = "legacy"; }, /unsupported group/],
  ];
  for (const [label, mutate, pattern] of cases) {
    assert.throws(() => assertPublicToolCatalog(frozenCatalog(mutate)), pattern, label);
  }
});
```

- [ ] **Step 4: Add exact group-registration tests**

Build a fake project-group schema map, a shared handler map, and a capturing server. Assert all 15 project tools register in catalog order, each receives the exact schema object, and invoking the wrapper forwards the exact input, operation, and MCP `extra` object to the named handler. Add rejection cases for unknown groups, a missing schema, an extra schema, and a missing/non-function handler.

```js
test("catalog group registration binds exact schemas, handlers, operations, and extra", async () => {
  const tools = PUBLIC_TOOL_CATALOG.filter((tool) => tool.group === "project");
  const schemas = Object.fromEntries(tools.map((tool) => [tool.schema, { id: tool.schema }]));
  const received = [];
  const handlers = Object.fromEntries(tools.map((tool) => [
    tool.handler,
    async (...args) => { received.push([tool.handler, ...args]); return tool.name; },
  ]));
  handlers.unrelatedHandler = () => {};
  const registrations = [];
  const server = {
    registerTool(name, schema, callback) { registrations.push({ name, schema, callback }); },
  };

  registerCatalogGroup(server, "project", schemas, handlers);
  assert.deepEqual(registrations.map(({ name }) => name), tools.map(({ name }) => name));
  assert.ok(registrations.every(({ name, schema }) => schema === schemas[name]));

  const input = { projectRoot: "/tmp/project" };
  const extra = { requestId: "request-1" };
  await registrations[0].callback(input, extra);
  assert.deepEqual(received, [[tools[0].handler, input, tools[0].operation, extra]]);
});

test("catalog group registration rejects incomplete or foreign wiring", () => {
  const tools = PUBLIC_TOOL_CATALOG.filter((tool) => tool.group === "visual");
  const schemas = Object.fromEntries(tools.map((tool) => [tool.schema, {}]));
  const handlers = Object.fromEntries(tools.map((tool) => [tool.handler, () => {}]));
  const server = { registerTool() {} };

  assert.throws(() => registerCatalogGroup(server, "legacy", {}, handlers), /Unknown public tool group/);
  assert.throws(
    () => registerCatalogGroup(server, "visual", { ...schemas, extra_schema: {} }, handlers),
    /Schema contract mismatch/,
  );
  const missingSchemas = { ...schemas };
  delete missingSchemas[tools[0].schema];
  assert.throws(
    () => registerCatalogGroup(server, "visual", missingSchemas, handlers),
    /Schema contract mismatch/,
  );
  assert.throws(
    () => registerCatalogGroup(server, "visual", schemas, { ...handlers, [tools[0].handler]: null }),
    new RegExp(`Incomplete public tool contract: ${tools[0].name}`),
  );
});
```

- [ ] **Step 5: Strengthen live server parity**

In the existing `MCP exposes data contracts without rendering a Widget in chat` test, assert all 43 listed tools have a closed object input schema and match the catalog order after sorting by name:

```js
const listedByName = [...tools.tools].sort((left, right) => left.name.localeCompare(right.name));
const catalogByName = [...PUBLIC_TOOL_CATALOG].sort((left, right) => left.name.localeCompare(right.name));
assert.equal(listedByName.length, 43);
assert.deepEqual(listedByName.map(({ name }) => name), catalogByName.map(({ name }) => name));
assert.ok(listedByName.every((tool) => tool.inputSchema?.type === "object"));
```

- [ ] **Step 6: Run the focused tests and observe RED**

Run:

```bash
node --test tests/tool-catalog-consistency.test.mjs tests/mcp-server.test.mjs
```

Expected: FAIL during module linking because `PUBLIC_TOOL_GROUP_COUNTS` and `assertPublicToolCatalog` are not exported. This is the required RED and proves the tests demand production behavior that does not exist yet.

### Task 2: Implement catalog invariants and exact group wiring

**Files:**
- Modify: `mcp/tool-catalog.mjs`
- Test: `tests/tool-catalog-consistency.test.mjs`
- Test: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Add frozen group metadata and invariant validation**

Keep the 43 existing `rows` unchanged. Above catalog construction add:

```js
export const PUBLIC_TOOL_GROUP_COUNTS = Object.freeze({
  project: 15,
  content: 15,
  review: 4,
  visual: 3,
  "delivery-experience": 6,
});

const DESCRIPTOR_FIELDS = Object.freeze(["name", "group", "handler", "operation", "schema"]);
const LOCAL_ASSET_TOOL = "read_ai_ppt_project_asset";
```

After constructing `PUBLIC_TOOL_CATALOG`, add `assertPublicToolCatalog(catalog)` with this validation order:

1. array and every descriptor are frozen;
2. total equals the sum of group counts;
3. descriptor keys exactly equal `DESCRIPTOR_FIELDS`;
4. name is non-empty and unique;
5. group is a key of `PUBLIC_TOOL_GROUP_COUNTS`;
6. schema equals name;
7. handler is non-empty and unique;
8. operation is either the sole permitted local-asset `null`, or a non-empty unique string;
9. observed group counts equal the frozen expected counts;
10. the null-operation descriptor list is exactly `[LOCAL_ASSET_TOOL]`.

Each failure throws `Error` with the stable phrases used by Task 1: `must be frozen`, `descriptor fields`, `tool name`, `duplicate tool name`, `unsupported group`, `schema identity`, `handler identity`, `duplicate handler`, `operation identity`, `duplicate operation`, `local-asset operation`, or `group count`.

Finish construction with:

```js
assertPublicToolCatalog(PUBLIC_TOOL_CATALOG);

export const PUBLIC_TOOL_CATALOG_SHA256 = createHash("sha256")
  .update(JSON.stringify(PUBLIC_TOOL_CATALOG))
  .digest("hex");
```

- [ ] **Step 2: Harden `registerCatalogGroup` without changing invocation semantics**

Before registration, verify the group exists and that sorted `Object.keys(schemas)` exactly equals the sorted catalog schema identities for that group. Preserve the wrapper call exactly:

```js
handler(input, tool.operation, extra)
```

Do not reject unrelated handlers because `createAiPptMcpServer()` intentionally supplies one shared handler map to all five domain registrars.

- [ ] **Step 3: Run focused tests and observe GREEN**

Run:

```bash
node --test tests/tool-catalog-consistency.test.mjs tests/mcp-server.test.mjs
```

Expected: all focused catalog and MCP server tests pass; total will be greater than the 29-test baseline because Task 1 added contract cases.

- [ ] **Step 4: Confirm the public surface did not change**

Run:

```bash
node --input-type=module -e 'import {PUBLIC_TOOL_CATALOG,PUBLIC_TOOL_CATALOG_SHA256,PUBLIC_TOOL_GROUP_COUNTS} from "./mcp/tool-catalog.mjs"; process.stdout.write(JSON.stringify({count:PUBLIC_TOOL_CATALOG.length,groups:PUBLIC_TOOL_GROUP_COUNTS,hash:PUBLIC_TOOL_CATALOG_SHA256}))'
```

Expected exact payload values: count `43`; groups `15/15/4/3/6`; hash `fc5fd70727aa8a793d9a4a63fe1007bbf3d4c5f0dacd3082e9153ce4303a7d88`.

### Task 3: Run full engineering verification

**Files:**
- Verify only; no new production scope.

- [ ] **Step 1: Run static and build checks**

```bash
npm run typecheck
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 2: Run full Node, Widget, and Python suites**

```bash
npm run test:node
npm run test:widget
npm run test:python
```

Expected: every suite exits 0; no baseline test is removed or skipped.

- [ ] **Step 3: Seed a temporary governed project and run the real stdio MCP probe**

Run:

```bash
r2_probe_seed=$(PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 scripts/seed-v16-ui-project.py)
r2_workspace_config=$(node -e 'const value=JSON.parse(process.argv[1]); process.stdout.write(value.workspace_config)' "$r2_probe_seed")
r2_project_root=$(node -e 'const value=JSON.parse(process.argv[1]); process.stdout.write(value.project_root)' "$r2_probe_seed")
AI_PPT_WORKSPACE_CONFIG="$r2_workspace_config" AI_PPT_PROBE_PROJECT="$r2_project_root" npm run probe:mcp
```

Expected JSON: `ok=true`, `tool_count=43`, `tool_catalog_sha256=fc5fd70727aa8a793d9a4a63fe1007bbf3d4c5f0dacd3082e9153ce4303a7d88`, no duplicate/drift error, and truthful non-proof host/receipt fields. Do not reinterpret the probe as real-host, AI-receipt, Gate, release, or user-acceptance evidence.

- [ ] **Step 4: Audit formatting and exact scope**

```bash
git diff --check
git status --short
git diff --stat 37e7cef35704bdad826af56564f2f9e03c722fc6...HEAD
git diff --stat
```

Expected: no whitespace error; only the R2 design/plan, `mcp/tool-catalog.mjs`, and the two named test files differ from the R1 parent. No Python, Widget, UI, Review Bridge, content-review, or visual-review file appears.

### Task 4: Create the atomic R2 implementation commit and reverify

**Files:**
- Stage exactly: `mcp/tool-catalog.mjs`
- Stage exactly: `tests/tool-catalog-consistency.test.mjs`
- Stage exactly: `tests/mcp-server.test.mjs`

- [ ] **Step 1: Inspect and stage exact implementation files**

```bash
git diff -- mcp/tool-catalog.mjs tests/tool-catalog-consistency.test.mjs tests/mcp-server.test.mjs
git add mcp/tool-catalog.mjs tests/tool-catalog-consistency.test.mjs tests/mcp-server.test.mjs
git diff --cached --check
git diff --cached --stat
```

Expected: exactly three implementation/test files staged. Do not use `git add .`.

- [ ] **Step 2: Commit the implementation**

```bash
git commit -m "fix: harden typed MCP public catalog"
```

- [ ] **Step 3: Perform fresh post-commit verification**

```bash
node --test tests/tool-catalog-consistency.test.mjs tests/mcp-server.test.mjs
npm run typecheck
npm run build
npm run test:node
npm run test:widget
npm run test:python
git diff --check
git status --short --branch
```

Expected: every command exits 0 and the worktree is clean. Preserve the branch and linked worktree; do not merge, amend, push, install, release, or delete it.

- [ ] **Step 4: Record the next recovery boundary**

Report R2 as implemented, committed, and locally verified only. Record its exact HEAD as the parent for a new C0 branch/worktree. Creating that C0 worktree is a separate reversible action; no C0 source edit may occur inside the R2 worktree.
