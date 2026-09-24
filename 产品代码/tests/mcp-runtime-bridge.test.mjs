import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import * as pythonRuntime from "../mcp/runtime-bridge/python-runtime.mjs";
import { createHostConfirmationAuthority } from "../mcp/host-confirmation-assertion.mjs";

const {
  invokePythonBridge,
  resolvePythonExecutable,
} = pythonRuntime;

test("host confirmation assertion is signed, version-bound, and carries one identity", () => {
  const authority = createHostConfirmationAuthority({
    secret: "node-test-host-confirmation-secret-32-bytes-minimum",
    now: () => 1_800_000_000,
  });
  const context = {
    project_id: "p1",
    project_root: "/managed/project",
    scope_kind: "gate",
    scope_id: "G3",
    source_version: `artifact://visual-contract/${"a".repeat(64)}`,
    evidence_refs: [`artifact://deck-design-system/${"b".repeat(64)}`],
    challenge_id: "challenge-g3-current",
    challenge_revision: 42,
  };
  const assertion = authority.issue(context, {
    identityType: "verified-message",
    identityRef: "chat://message/explicit-g3-acceptance",
  });

  const [version, payloadSegment, signatureSegment] = assertion.split(".");
  const payload = JSON.parse(Buffer.from(payloadSegment, "base64url").toString("utf8"));
  assert.equal(version, "v1");
  assert.ok(signatureSegment.length > 32);
  assert.equal(payload.project_id, context.project_id);
  assert.equal(payload.project_root, context.project_root);
  assert.equal(payload.scope_kind, context.scope_kind);
  assert.equal(payload.scope_id, context.scope_id);
  assert.equal(payload.source_version, context.source_version);
  assert.deepEqual(payload.evidence_refs, context.evidence_refs);
  assert.equal(payload.challenge_id, context.challenge_id);
  assert.equal(payload.challenge_revision, context.challenge_revision);
  assert.equal(payload.identity_type, "verified-message");
  assert.equal(payload.identity_ref, "chat://message/explicit-g3-acceptance");
  assert.equal(payload.expires_at - payload.issued_at, 120);
  assert.ok(payload.nonce);
});

test("Python bridge returns a structured snapshot", async () => {
  const result = await invokePythonBridge({ operation: "list-projects" });
  assert.equal(result.ok, true);
  assert.equal(Array.isArray(result.projects), true);
});

test("Python bridge prefers the Python bundled beside the active Codex Node runtime", async () => {
  const runtime = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-codex-runtime-"));
  const nodeExecutable = path.join(runtime, "dependencies", "node", "bin", "node");
  const pythonExecutable = path.join(runtime, "dependencies", "python", "bin", "python3");
  await mkdir(path.dirname(nodeExecutable), { recursive: true });
  await mkdir(path.dirname(pythonExecutable), { recursive: true });
  await writeFile(nodeExecutable, "", "utf8");
  await writeFile(pythonExecutable, "", "utf8");

  const hostEnv = {
    ...process.env,
    PATH: "",
    AI_PPT_PYTHONPATH: "/module-root-only",
  };
  delete hostEnv.AI_PPT_PYTHON;
  assert.equal(
    resolvePythonExecutable({ env: hostEnv, nodeExecutable }),
    pythonExecutable,
  );
});

test("bundled Python discovery rejects unrelated and Windows Node layouts", () => {
  assert.equal(typeof pythonRuntime.resolveBundledPythonExecutable, "function");
  assert.equal(
    pythonRuntime.resolveBundledPythonExecutable("/opt/homebrew/bin/node", "darwin"),
    undefined,
  );
  assert.equal(
    pythonRuntime.resolveBundledPythonExecutable(
      "/runtime/dependencies/not-node/bin/node",
      "darwin",
    ),
    undefined,
  );
  assert.equal(
    pythonRuntime.resolveBundledPythonExecutable(
      "C:\\runtime\\dependencies\\node\\bin\\node.exe",
      "win32",
    ),
    undefined,
  );
});

test("AI_PPT_PYTHON overrides bundled and system Python candidates", () => {
  const configured = "/managed/runtime/python";
  assert.equal(
    resolvePythonExecutable({
      env: { ...process.env, AI_PPT_PYTHON: configured },
      nodeExecutable: "/runtime/dependencies/node/bin/node",
    }),
    configured,
  );
});

test("pythonExecutable option overrides every discovered candidate", () => {
  const configured = "/request-scoped/runtime/python";
  assert.equal(
    resolvePythonExecutable({
      pythonExecutable: configured,
      env: { ...process.env, AI_PPT_PYTHON: "/managed/runtime/python" },
      nodeExecutable: "/runtime/dependencies/node/bin/node",
    }),
    configured,
  );
});

test("Python resolution falls back when the sibling bundled Python is absent", async () => {
  const runtime = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-codex-runtime-missing-python-"));
  const nodeExecutable = path.join(runtime, "dependencies", "node", "bin", "node");
  const missingPython = path.join(runtime, "dependencies", "python", "bin", "python3");
  await mkdir(path.dirname(nodeExecutable), { recursive: true });
  await writeFile(nodeExecutable, "", "utf8");

  const hostEnv = { ...process.env, PATH: "" };
  delete hostEnv.AI_PPT_PYTHON;
  const executable = resolvePythonExecutable({ env: hostEnv, nodeExecutable });
  assert.notEqual(executable, missingPython);
  assert.equal(path.isAbsolute(executable), true);
});

test("Python bridge does not replace a missing AI_PPT_PYTHON override", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-env-override-"));
  const missingPython = path.join(temporary, "missing-configured-python");
  const hostEnv = { ...process.env, AI_PPT_PYTHON: missingPython };
  const fallbackPython = resolvePythonExecutable({
    env: { ...process.env, AI_PPT_PYTHON: "" },
    nodeExecutable: "/not-a-bundled-node/bin/node",
  });

  await assert.rejects(
    invokePythonBridge(
      { operation: "list-projects" },
      { env: hostEnv, pythonCandidates: [fallbackPython] },
    ),
    (error) => error?.code === "ENOENT",
  );
});

test("Python bridge does not replace a missing pythonExecutable option", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-option-override-"));
  const missingPython = path.join(temporary, "missing-request-python");
  const fallbackPython = resolvePythonExecutable({
    env: { ...process.env, AI_PPT_PYTHON: "" },
    nodeExecutable: "/not-a-bundled-node/bin/node",
  });

  await assert.rejects(
    invokePythonBridge(
      { operation: "list-projects" },
      {
        pythonExecutable: missingPython,
        pythonCandidates: [fallbackPython],
      },
    ),
    (error) => error?.code === "ENOENT",
  );
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
      pythonCandidates: [unavailableInterpreter, resolvePythonExecutable({
        env: { ...process.env, PATH: "" },
      })],
      bridgeArgs: [bridge],
    },
  );

  assert.deepEqual(result, { ok: true, operation: "list-projects" });
});

test(
  "Python bridge does not retry another interpreter after a non-ENOENT spawn error",
  { skip: process.platform === "win32" },
  async () => {
    const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-no-eacces-retry-"));
    const nonExecutablePython = path.join(temporary, "non-executable-python");
    const bridge = path.join(temporary, "bridge.py");
    await writeFile(nonExecutablePython, "", "utf8");
    await writeFile(
      bridge,
      [
        "import json, sys",
        "request = json.load(sys.stdin)",
        "print(json.dumps({'ok': True, 'operation': request['operation']}))",
      ].join("\n"),
      "utf8",
    );
    const hostEnv = { ...process.env, PATH: "" };
    delete hostEnv.AI_PPT_PYTHON;
    const workingPython = resolvePythonExecutable({
      env: hostEnv,
      nodeExecutable: "/not-a-bundled-node/bin/node",
    });

    await assert.rejects(
      invokePythonBridge(
        { operation: "list-projects" },
        {
          env: hostEnv,
          pythonCandidates: [nonExecutablePython, workingPython],
          bridgeArgs: [bridge],
        },
      ),
      (error) => error?.code === "EACCES",
    );
  },
);

test("Python bridge does not retry another interpreter after a business error", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-no-business-retry-"));
  const bridge = path.join(temporary, "bridge.py");
  const unavailableFallback = path.join(temporary, "must-not-run-python");
  await writeFile(
    unavailableFallback,
    "#!/definitely/missing/python\n",
    "utf8",
  );
  await chmod(unavailableFallback, 0o755);
  await writeFile(
    bridge,
    [
      "import json, sys",
      "json.load(sys.stdin)",
      "print(json.dumps({'ok': False, 'error': {'code': 'REVISION_CONFLICT', 'message': 'stale', 'details': {'actual_revision': 2}}}))",
      "raise SystemExit(2)",
    ].join("\n"),
    "utf8",
  );
  const workingPython = resolvePythonExecutable({
    env: { ...process.env, PATH: "" },
    nodeExecutable: "/not-a-bundled-node/bin/node",
  });

  await assert.rejects(
    invokePythonBridge(
      { operation: "submit-human-decision" },
      {
        pythonCandidates: [workingPython, unavailableFallback],
        bridgeArgs: [bridge],
      },
    ),
    (error) => error.code === "REVISION_CONFLICT" && error.details.actual_revision === 2,
  );
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
