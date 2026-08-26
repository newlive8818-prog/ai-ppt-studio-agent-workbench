import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  PUBLIC_TOOL_CATALOG,
  PUBLIC_TOOL_CATALOG_SHA256,
  PUBLIC_TOOL_GROUP_COUNTS,
  assertPublicToolCatalog,
  registerCatalogGroup,
} from "../mcp/tool-catalog.mjs";

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

const OUTER_BRIDGE_OPERATIONS = new Set(["create-project"]);
const PRIVATE_PYTHON_OPERATIONS = new Set([
  "get-content-revision-plan-confirmation-context",
  "get-gate-confirmation-context",
  "record-review-bridge-host-open",
]);

function frozenCatalog(mutator = () => {}) {
  const rows = PUBLIC_TOOL_CATALOG.map((tool) => ({ ...tool }));
  mutator(rows);
  return Object.freeze(rows.map((tool) => Object.freeze(tool)));
}

function pythonOperations() {
  const code = [
    "import json,sys",
    'sys.path.insert(0, "src")',
    "from ai_ppt_studio.application.v16_bridge import HANDLERS",
    "print(json.dumps(sorted(HANDLERS)))",
  ].join(";");
  const result = spawnSync("python3", ["-c", code], {
    cwd: new URL("..", import.meta.url),
    encoding: "utf8",
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(result.status, 0, result.stderr);
  return new Set(JSON.parse(result.stdout));
}

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
    Array.from(
      { length: 43 },
      () => ["name", "group", "handler", "operation", "schema"],
    ),
  );
  assertPublicToolCatalog(PUBLIC_TOOL_CATALOG);
});

test("catalog validation rejects structural drift", () => {
  assert.throws(
    () => assertPublicToolCatalog([...PUBLIC_TOOL_CATALOG]),
    /must be frozen/,
  );

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
    assert.throws(
      () => assertPublicToolCatalog(frozenCatalog(mutate)),
      pattern,
      label,
    );
  }
});

test("catalog group registration binds exact schemas, handlers, operations, and extra", async () => {
  const tools = PUBLIC_TOOL_CATALOG.filter((tool) => tool.group === "project");
  const schemas = Object.fromEntries(
    tools.map((tool) => [tool.schema, { id: tool.schema }]),
  );
  const received = [];
  const handlers = Object.fromEntries(tools.map((tool) => [
    tool.handler,
    async (...args) => {
      received.push([tool.handler, ...args]);
      return tool.name;
    },
  ]));
  handlers.unrelatedHandler = () => {};
  const registrations = [];
  const server = {
    registerTool(name, schema, callback) {
      registrations.push({ name, schema, callback });
    },
  };

  registerCatalogGroup(server, "project", schemas, handlers);
  assert.deepEqual(
    registrations.map(({ name }) => name),
    tools.map(({ name }) => name),
  );
  assert.ok(
    registrations.every(({ name, schema }) => schema === schemas[name]),
  );

  const input = { projectRoot: "/tmp/project" };
  const extra = { requestId: "request-1" };
  await registrations[0].callback(input, extra);
  assert.deepEqual(
    received,
    [[tools[0].handler, input, tools[0].operation, extra]],
  );
});

test("catalog group registration rejects incomplete or foreign wiring", () => {
  const tools = PUBLIC_TOOL_CATALOG.filter((tool) => tool.group === "visual");
  const schemas = Object.fromEntries(tools.map((tool) => [tool.schema, {}]));
  const handlers = Object.fromEntries(
    tools.map((tool) => [tool.handler, () => {}]),
  );
  const registrations = [];
  const server = {
    registerTool(name) {
      registrations.push(name);
    },
  };

  assert.throws(
    () => registerCatalogGroup(server, "legacy", {}, handlers),
    /Unknown public tool group/,
  );
  assert.throws(
    () => registerCatalogGroup(
      server,
      "visual",
      { ...schemas, extra_schema: {} },
      handlers,
    ),
    /Schema contract mismatch/,
  );
  const missingSchemas = { ...schemas };
  delete missingSchemas[tools[0].schema];
  assert.throws(
    () => registerCatalogGroup(server, "visual", missingSchemas, handlers),
    /Schema contract mismatch/,
  );
  assert.throws(
    () => registerCatalogGroup(
      server,
      "visual",
      schemas,
      { ...handlers, [tools.at(-1).handler]: null },
    ),
    new RegExp(`Incomplete public tool contract: ${tools.at(-1).name}`),
  );
  assert.deepEqual(registrations, []);

  assert.throws(
    () => registerCatalogGroup(
      server,
      "visual",
      { ...schemas, [tools.at(-1).schema]: null },
      handlers,
    ),
    new RegExp(`Incomplete public tool contract: ${tools.at(-1).name}`),
  );
  assert.deepEqual(registrations, []);
});

test("catalog, Node handlers, and Python operations have one exact public surface", () => {
  assert.ok(
    PUBLIC_TOOL_CATALOG.every(
      (tool) => typeof tool.operation === "string" || tool.operation === null,
    ),
  );
  assert.deepEqual(
    PUBLIC_TOOL_CATALOG.filter((tool) => tool.operation === null).map(
      (tool) => tool.name,
    ),
    ["read_ai_ppt_project_asset"],
  );
  assert.equal(
    new Set(PUBLIC_TOOL_CATALOG.map((tool) => tool.handler)).size,
    PUBLIC_TOOL_CATALOG.length,
  );

  const publicPythonOperations = new Set(
    PUBLIC_TOOL_CATALOG.map((tool) => tool.operation).filter(
      (operation) => operation && !OUTER_BRIDGE_OPERATIONS.has(operation),
    ),
  );
  const runtimeOperations = pythonOperations();
  assert.deepEqual(
    [...runtimeOperations].filter(
      (operation) => !publicPythonOperations.has(operation),
    ),
    [...PRIVATE_PYTHON_OPERATIONS],
  );
  assert.deepEqual(
    [...publicPythonOperations].filter(
      (operation) => !runtimeOperations.has(operation),
    ),
    [],
  );
});
