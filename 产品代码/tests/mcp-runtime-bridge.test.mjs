import assert from "node:assert/strict";
import { chmod, mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  invokePythonBridge,
  resolvePythonExecutable,
} from "../mcp/runtime-bridge/python-runtime.mjs";

test("Python bridge returns a structured snapshot", async () => {
  const result = await invokePythonBridge({ operation: "list-projects" });
  assert.equal(result.ok, true);
  assert.equal(Array.isArray(result.projects), true);
});

test("Python bridge resolves an absolute interpreter when the Codex host PATH is empty", async () => {
  const hostEnv = { ...process.env, PATH: "" };
  delete hostEnv.AI_PPT_PYTHON;
  const executable = resolvePythonExecutable({ env: hostEnv });
  assert.equal(path.isAbsolute(executable), true);
  const result = await invokePythonBridge(
    { operation: "list-projects" },
    { env: hostEnv },
  );
  assert.equal(result.ok, true);
  assert.equal(Array.isArray(result.projects), true);
});

test("Python bridge falls back when an existing interpreter cannot be spawned", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-fallback-"));
  const unavailableInterpreter = path.join(temporary, "unavailable-python");
  const bridge = path.join(temporary, "bridge.py");
  await writeFile(
    unavailableInterpreter,
    "#!/definitely/missing/python\n",
    "utf8",
  );
  await chmod(unavailableInterpreter, 0o755);
  await writeFile(
    bridge,
    [
      "import json, sys",
      "request = json.load(sys.stdin)",
      "print(json.dumps({'ok': True, 'operation': request['operation']}))",
    ].join("\n"),
    "utf8",
  );

  const result = await invokePythonBridge(
    { operation: "list-projects" },
    {
      env: { ...process.env, PATH: "" },
      pythonCandidates: [unavailableInterpreter, "/usr/bin/python3"],
      bridgeArgs: [bridge],
    },
  );

  assert.deepEqual(result, { ok: true, operation: "list-projects" });
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
