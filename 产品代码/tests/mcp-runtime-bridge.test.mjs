import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { invokePythonBridge } from "../mcp/runtime-bridge/python-runtime.mjs";

test("Python bridge returns a structured snapshot", async () => {
  const result = await invokePythonBridge({ operation: "list-projects" });
  assert.equal(result.ok, true);
  assert.equal(Array.isArray(result.projects), true);
});

test("Python bridge surfaces stable revision conflicts", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-bridge-"));
  const script = path.join(temporary, "bridge.py");
  await writeFile(
    script,
    [
      "import json, sys",
      "json.load(sys.stdin)",
      "print(json.dumps({'ok': False, 'error': {'code': 'REVISION_CONFLICT', 'message': 'stale', 'details': {'actual_revision': 2}}}))",
      "raise SystemExit(2)",
    ].join("\n"),
    "utf8",
  );
  await assert.rejects(
    invokePythonBridge(
      { operation: "submit-human-decision" },
      { pythonExecutable: "python3", bridgeArgs: [script] },
    ),
    (error) => error.code === "REVISION_CONFLICT" && error.details.actual_revision === 2,
  );
});
