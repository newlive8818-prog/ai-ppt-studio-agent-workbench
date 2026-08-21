import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

import { PUBLIC_TOOL_CATALOG } from "../mcp/tool-catalog.mjs";

const OUTER_BRIDGE_OPERATIONS = new Set(["create-project"]);
const PRIVATE_PYTHON_OPERATIONS = new Set([
  "get-content-revision-plan-confirmation-context",
  "get-gate-confirmation-context",
  "record-review-bridge-host-open",
]);

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
