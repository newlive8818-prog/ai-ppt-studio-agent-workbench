# MCP Bundled Python Runtime Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI PPT Studio Node MCP reliably select the Python runtime bundled beside the active Codex Node runtime, while preserving explicit overrides, safe fallback behavior, existing Python business contracts, and zero-write read-only acceptance.

**Architecture:** Forward the two approved Python environment variables through the plugin STDIO manifest, then add one pure path resolver at the Node-to-Python bridge boundary. The default resolver derives a sibling Python only from the exact non-Windows `dependencies/node/bin` layout, places it before system candidates, and retries another default candidate only for `ENOENT`; Python business behavior, project state, Gate logic, and review surfaces remain unchanged.

**Tech Stack:** Node.js ES modules, `node:test`, Codex plugin `.mcp.json`, Python 3.12 bridge runtime, npm release tooling, Codex plugin marketplace/cache, Git linked worktrees.

---

## Execution identity, file map, and rollback boundary

**Approved design:** `产品代码/docs/superpowers/specs/2026-08-25-v22-controlled-recovery-worktree-and-mcp-runtime-design.md`

**Execution identity:**

- Authoritative repository: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
- Recovery integration branch: `codex/v22-recovery-integration-20260825`
- Recovery integration commit and rollback point: `94f0f609ee4288995cf60ef90fc218dfa48f0ee8`
- Feature branch: `codex/slice-mcp-runtime-20260825`
- Feature linked worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-mcp-runtime-20260825`
- Approved design commit: `05b45a3d7e8c065e0d314b15d90e9622b96bea08`
- Quarantine branch: `codex/quarantine-mixed-worktree-20260825`
- Quarantine checkout: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`

The implementation executor must start from the docs-only plan commit whose parent is the approved design commit. The recovery integration branch must still resolve to the recorded rollback point unless the user has explicitly advanced it. A branch, HEAD, target-blob, or worktree mismatch is a stop condition, not permission to repair history.

**Create in the planning phase only:**

- `产品代码/docs/superpowers/plans/2026-08-25-mcp-bundled-python-runtime-recovery.md` — this plan; it is committed separately before implementation starts.

**Modify during implementation:**

- `产品代码/.mcp.json` — forwards exactly `AI_PPT_PYTHON` and `AI_PPT_PYTHONPATH` into the plugin STDIO MCP.
- `产品代码/mcp/runtime-bridge/python-runtime.mjs` — derives and prioritizes the sibling bundled Python without changing bridge business semantics.
- `产品代码/tests/mcp-runtime-bridge.test.mjs` — covers discovery, rejection, priority, fallback, and retry/error boundaries.
- `产品代码/tests/plugin-shape.test.mjs` — covers exact manifest forwarding.

**Read-only implementation context:**

- `产品代码/package.json`
- `产品代码/package-lock.json`
- `产品代码/scripts/build-plugin-release.mjs`
- `产品代码/scripts/verify-plugin-release.mjs`
- `产品代码/scripts/install-plugin.mjs`
- `产品代码/src/ai_ppt_studio/workbench_bridge.py`

**Expected untouched target blobs before RED:**

```text
6002e4896f04452e5f1b3e2751e4856efd63fead  产品代码/.mcp.json
507f6fecf112548b7407b7359217a5fb4d97e738  产品代码/mcp/runtime-bridge/python-runtime.mjs
d91f2138aafeaa4c31e2bc30f6b1e2893d9b406c  产品代码/tests/mcp-runtime-bridge.test.mjs
aa68af8b70a04e730bc927d90683d94d5d98546c  产品代码/tests/plugin-shape.test.mjs
```

**Do not modify:**

- The quarantine checkout or its existing `.superpowers/`, `.workbuddy/`, and `分享材料/` state.
- `产品代码/scripts/probe-mcp.mjs`, typed tool catalog, MCP server registration, or Review Bridge.
- Python Runtime business services, domain contracts, revision handling, idempotency, artifacts, Gate state, or trusted confirmation.
- Widget, content review, visual review, prototypes, or the four authoritative product baselines.
- Recovery integration branch history.

**Git rules:**

- Never use `git add .`; stage explicit paths only.
- Do not amend, merge, cherry-pick, push, reset, clean, or delete a worktree in this plan.
- The quarantine implementation commits are read-only historical evidence, never a source for cherry-pick.
- The implementation rollback unit is the commit created in Task 6 with subject `fix: bind MCP to bundled Python runtime`.
- Rollback, if later authorized, is `git revert <implementation-commit>` from the appropriate integration context; the design and plan commits remain audit evidence.

## Global stop conditions

Stop immediately, leave the current feature worktree recoverable, and report evidence if any of the following occurs:

1. The current directory, Git root, git-dir/common-dir, branch, HEAD ancestry, or target blobs do not match this plan.
2. The feature worktree contains an unrelated tracked or untracked change before execution.
3. `npm ci` changes a tracked file or cannot establish the locked dependency tree.
4. A fresh pre-change engineering test exposes a genuine code baseline failure. Do not fix it here; return to the approved engineering-gate exception and establish a separate repair unit before resuming this plan.
5. A failure is only a dependency, network, sandbox, loopback, permission, or host capability boundary. Record it as such; do not convert it into a source-code fix without evidence.
6. RED requires a production file change, or GREEN requires a fifth implementation file.
7. Focused tests do not fail for the expected missing resolver/manifest reasons, or an existing behavior regresses.
8. Full engineering verification, release validation, installed-copy validation, or fresh MCP acceptance fails.
9. The release/install step would overwrite a different plugin root or marketplace than the exact paths recorded here.
10. The read-only acceptance project changes concurrently between the before snapshot and MCP call.

### Task 1: Re-establish the feature and recovery boundaries

**Files:**

- Verify: Git metadata for the feature linked worktree
- Verify: the four implementation targets
- Read: `产品代码/docs/superpowers/specs/2026-08-25-v22-controlled-recovery-worktree-and-mcp-runtime-design.md`

- [ ] **Step 1: Verify the linked worktree identity**

Run from the feature worktree root:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git rev-parse HEAD
git status --short --branch
```

Expected:

- `pwd` and Git root are `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-mcp-runtime-20260825`.
- git-dir is the main repository's `.git/worktrees/slice-mcp-runtime-20260825` entry.
- git-common-dir is `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/.git`.
- Branch is `codex/slice-mcp-runtime-20260825`.
- Status is clean.

- [ ] **Step 2: Verify the recovery ancestry and design commit**

Run:

```bash
git rev-parse codex/v22-recovery-integration-20260825
git merge-base --is-ancestor 94f0f609ee4288995cf60ef90fc218dfa48f0ee8 HEAD
git show -s --format='%H %P %s' 05b45a3d7e8c065e0d314b15d90e9622b96bea08
git log --oneline --decorate -3
```

Expected:

- Recovery integration still resolves to `94f0f609ee4288995cf60ef90fc218dfa48f0ee8` unless the user has explicitly advanced it.
- The ancestry command exits `0`.
- `05b45a3...` has parent `94f0f609...` and subject `docs: design controlled recovery worktree boundaries`.
- HEAD is the separate docs-only plan commit after `05b45a3...`.

- [ ] **Step 3: Verify the exact target blobs**

Run:

```bash
git ls-tree HEAD -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/tests/mcp-runtime-bridge.test.mjs 产品代码/tests/plugin-shape.test.mjs
```

Expected: the four blob IDs exactly match the list in this plan. Any mismatch stops execution for a new audit.

- [ ] **Step 4: Record the quarantine state read-only**

Run:

```bash
git -C '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app' branch --show-current
git -C '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app' rev-parse HEAD
git -C '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app' status --short --branch
```

Expected: branch remains `codex/quarantine-mixed-worktree-20260825`; this command is observation only. Do not stage, clean, restore, switch, or edit there.

### Task 2: Establish a fresh pre-change engineering baseline

**Files:**

- Read: `产品代码/package.json`
- Read: `产品代码/package-lock.json`
- Verify: the complete tracked worktree

- [ ] **Step 1: Install the exact locked dependencies**

Run:

```bash
cd 产品代码
npm ci
```

Expected: exit `0`. A registry/network/sandbox failure is an environment boundary until proven otherwise. Do not edit `package.json` or `package-lock.json` to bypass it.

- [ ] **Step 2: Prove dependency installation changed no tracked file**

Run from the feature worktree root:

```bash
git status --short --branch
git diff --exit-code
git diff --cached --exit-code
```

Expected: clean status and both diff commands exit `0`.

- [ ] **Step 3: Run every engineering baseline command separately**

Run from `产品代码`:

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

Expected: every command exits `0`. Record each current test count and exit code; historical counts are not pass criteria.

- [ ] **Step 4: Reconfirm a zero-diff baseline**

Run from the feature worktree root:

```bash
git status --short --branch
git diff --exit-code
git diff --cached --exit-code
```

Expected: no tracked or staged change. If a fresh command exposes a real code failure, stop the MCP unit and report the failing command, assertion/error, environment, and proposed engineering-gate repair worktree. Do not edit business or test code here.

### Task 3: Add RED tests for discovery, priority, fallback, and manifest forwarding

**Files:**

- Modify: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Modify: `产品代码/tests/plugin-shape.test.mjs`
- Test: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Test: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Extend the bridge test imports without importing a missing named export**

Replace the current import block at the top of `tests/mcp-runtime-bridge.test.mjs` with:

```js
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
```

The namespace import allows the RED suite to load before `resolveBundledPythonExecutable` exists, so the test can report the missing contract rather than aborting module initialization.

- [ ] **Step 2: Add the bundled-runtime discovery and layout-safety tests**

Insert immediately after `Python bridge returns a structured snapshot`:

```js
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
```

This also proves `AI_PPT_PYTHONPATH` remains a module-root variable and is not used as the executable.

- [ ] **Step 3: Add explicit priority and missing-bundled fallback tests**

Insert immediately after the layout-safety test:

```js
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
```

- [ ] **Step 4: Prove both explicit executable choices fail deterministically**

Insert immediately after the missing-bundled fallback test:

```js
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
```

The injected fallback is intentionally available; either test resolves instead of rejecting if an explicit choice is silently replaced.

- [ ] **Step 5: Prove default candidates retry only on `ENOENT`**

Keep the existing `Python bridge falls back when an existing interpreter cannot be spawned` test unchanged; it already proves an `ENOENT` default candidate may move to the next candidate.

Insert immediately after that existing test:

```js
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
    const workingPython = resolvePythonExecutable({
      env: { ...process.env, PATH: "" },
      nodeExecutable: "/not-a-bundled-node/bin/node",
    });

    await assert.rejects(
      invokePythonBridge(
        { operation: "list-projects" },
        {
          pythonCandidates: [nonExecutablePython, workingPython],
          bridgeArgs: [bridge],
        },
      ),
      (error) => error?.code === "EACCES",
    );
  },
);
```

- [ ] **Step 6: Prove a Python business error never switches interpreter**

Insert immediately before `Python bridge surfaces stable revision conflicts`:

```js
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
```

If the bridge retries after the valid Python business error, the second candidate changes the observed error to `ENOENT` and this assertion fails.

- [ ] **Step 7: Extend the exact MCP manifest assertion**

In `MCP config starts the local stdio server from the plugin root` in `tests/plugin-shape.test.mjs`, add:

```js
  assert.deepEqual(server.env_vars, [
    "AI_PPT_PYTHON",
    "AI_PPT_PYTHONPATH",
  ]);
```

- [ ] **Step 8: Run the focused suite and verify RED**

Run from `产品代码`:

```bash
node --test tests/mcp-runtime-bridge.test.mjs tests/plugin-shape.test.mjs
```

Expected: non-zero exit. At minimum, bundled discovery/layout tests fail because `resolveBundledPythonExecutable` is absent or the sibling is not selected, and the plugin-shape test fails because `server.env_vars` is absent. Priority and retry regression tests that describe existing behavior may already pass.

- [ ] **Step 9: Prove RED changed no production file**

Run from the feature worktree root:

```bash
git status --short
git diff --exit-code -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs
git diff --check
```

Expected: only the two test files are modified; the production-file diff command exits `0`; whitespace check prints nothing. If RED requires production edits to become observable, stop and revise the plan before implementation.

### Task 4: Implement the minimal bundled-runtime binding

**Files:**

- Modify: `产品代码/.mcp.json`
- Modify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Test: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Test: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Forward exactly the approved MCP environment variables**

Replace `产品代码/.mcp.json` with:

```json
{
  "mcpServers": {
    "ai_ppt_studio": {
      "title": "AI PPT Studio Native Workbench",
      "description": "Read and update governed AI PPT projects and render the native Codex workbench.",
      "command": "node",
      "args": [
        "./scripts/start-mcp.mjs"
      ],
      "cwd": ".",
      "env_vars": [
        "AI_PPT_PYTHON",
        "AI_PPT_PYTHONPATH"
      ]
    }
  }
}
```

Do not embed a local executable path, Python module path, credential, or default value.

- [ ] **Step 2: Add the pure bundled-path resolver**

Insert immediately before `defaultPythonCandidates` in `产品代码/mcp/runtime-bridge/python-runtime.mjs`:

```js
export function resolveBundledPythonExecutable(
  nodeExecutable = process.execPath,
  platform = process.platform,
) {
  if (platform === "win32" || !nodeExecutable || !path.isAbsolute(nodeExecutable))
    return undefined;
  const nodeBin = path.dirname(nodeExecutable);
  const nodeRoot = path.dirname(nodeBin);
  const dependenciesRoot = path.dirname(nodeRoot);
  if (
    path.basename(nodeBin) !== "bin"
    || path.basename(nodeRoot) !== "node"
    || path.basename(dependenciesRoot) !== "dependencies"
  ) return undefined;
  return path.join(dependenciesRoot, "python", "bin", "python3");
}
```

The function derives one candidate only. It does not call `existsSync`, scan parents, infer Windows support, or inspect `AI_PPT_PYTHONPATH`.

- [ ] **Step 3: Insert the bundled candidate before system candidates**

Replace `defaultPythonCandidates` with:

```js
function defaultPythonCandidates(
  env = process.env,
  platform = process.platform,
  nodeExecutable = process.execPath,
) {
  if (platform === "win32") {
    return [
      env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, "Programs", "Python", "Python314", "python.exe"),
      env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, "Programs", "Python", "Python313", "python.exe"),
      env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, "Programs", "Python", "Python312", "python.exe"),
      env.ProgramFiles && path.join(env.ProgramFiles, "Python314", "python.exe"),
      env.ProgramFiles && path.join(env.ProgramFiles, "Python313", "python.exe"),
      env.ProgramFiles && path.join(env.ProgramFiles, "Python312", "python.exe"),
    ].filter(Boolean);
  }
  return [
    resolveBundledPythonExecutable(nodeExecutable, platform),
    "/usr/local/bin/python3",
    "/opt/homebrew/bin/python3",
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
    "/usr/bin/python3",
  ].filter(Boolean);
}
```

Windows behavior remains the existing behavior; this plan makes no Windows bundled-runtime compatibility claim.

- [ ] **Step 4: Inject the active Node executable and deduplicate candidates**

Inside `resolvePythonExecutables`, keep the two explicit early returns unchanged and replace the default candidate block with:

```js
  const candidates = options.pythonCandidates || defaultPythonCandidates(
    env,
    options.platform,
    options.nodeExecutable || process.execPath,
  );
  const resolved = [...new Set(candidates)].filter(
    (candidate) => path.isAbsolute(candidate) && existsSync(candidate),
  );
```

The full priority remains:

```text
options.pythonExecutable
-> AI_PPT_PYTHON
-> bundled Python beside active Codex Node
-> existing platform system candidates
-> python3/py command fallback
```

Do not modify `invokeWithPython`, bridge arguments, `PLUGIN_ROOT`, `pythonModuleRoot`, `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, JSON parsing, `PythonBridgeError`, or the `ENOENT`-only retry predicate.

### Task 5: Establish focused GREEN and real bundled-runtime proof

**Files:**

- Verify: the four implementation targets
- Verify: `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`
- Verify: `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`

- [ ] **Step 1: Run the focused tests and verify GREEN**

Run from `产品代码`:

```bash
node --test tests/mcp-runtime-bridge.test.mjs tests/plugin-shape.test.mjs
```

Expected: exit `0`; all new and existing tests in both files pass. Record the fresh pass count rather than copying a historical count.

- [ ] **Step 2: Run syntax, JSON, and whitespace checks**

Run:

```bash
node --check mcp/runtime-bridge/python-runtime.mjs
node -e 'JSON.parse(require("node:fs").readFileSync(".mcp.json", "utf8")); process.stdout.write("valid\n")'
git diff --check
```

Expected: syntax exits `0`, JSON prints `valid`, and the whitespace check prints nothing.

- [ ] **Step 3: Prove selection with the actual bundled Node and an empty ordinary PATH**

Run from `产品代码`:

```bash
PATH='' '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' --input-type=module -e '
import { invokePythonBridge, resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
const env = { ...process.env, PATH: "" };
delete env.AI_PPT_PYTHON;
const executable = resolvePythonExecutable({ env });
const result = await invokePythonBridge({ operation: "list-projects" }, { env });
process.stdout.write(`${JSON.stringify({
  executable,
  ok: result.ok,
  projectCount: result.projects.length,
})}\n`);
'
```

Expected: one-line JSON whose `executable` is exactly `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`, whose `ok` is `true`, and whose `projectCount` is the non-negative integer derived from the live projects array. No fixed project count is a pass criterion.

- [ ] **Step 4: Prove an explicit environment override still wins**

Run:

```bash
AI_PPT_PYTHON='/usr/bin/python3' PATH='' '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' --input-type=module -e '
import { resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
process.stdout.write(`${resolvePythonExecutable({ env: process.env })}\n`);
'
```

Expected exact output: `/usr/bin/python3`.

### Task 6: Run the full engineering gate and commit the four-file rollback unit

**Files:**

- Modify: `产品代码/.mcp.json`
- Modify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Modify: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Modify: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Run the full engineering gate from the changed tree**

Run from `产品代码`:

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

Expected: every command exits `0`. Record current pass/fail counts and classify any loopback/sandbox failure separately; do not weaken tests or modify unrelated files.

- [ ] **Step 2: Inspect the exact four-file diff**

Run from the feature worktree root:

```bash
git diff -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/tests/mcp-runtime-bridge.test.mjs 产品代码/tests/plugin-shape.test.mjs
git diff --name-only
git diff --check
git status --short --branch
```

Expected `git diff --name-only` contains exactly:

```text
产品代码/.mcp.json
产品代码/mcp/runtime-bridge/python-runtime.mjs
产品代码/tests/mcp-runtime-bridge.test.mjs
产品代码/tests/plugin-shape.test.mjs
```

No generated Widget output, dependency lock, Python cache, content-review file, visual-review file, or quarantine file may appear.

- [ ] **Step 3: Stage only the four approved files**

Run:

```bash
git add -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/tests/mcp-runtime-bridge.test.mjs 产品代码/tests/plugin-shape.test.mjs
git diff --cached --check
git diff --cached --name-only
git status --short --branch
```

Expected: exactly the four implementation files are staged and no unstaged change remains.

- [ ] **Step 4: Create the implementation commit without amending history**

Run:

```bash
git commit -m "fix: bind MCP to bundled Python runtime"
```

Expected: one new commit after the design and plan commits. Do not amend it, merge it, or push it.

- [ ] **Step 5: Verify the commit identity and clean worktree**

Run:

```bash
git show --stat --oneline --decorate HEAD
git show --format= --name-only HEAD
git status --short --branch
```

Expected: subject is `fix: bind MCP to bundled Python runtime`, the commit contains exactly four files, and the feature worktree is clean.

### Task 7: Build and verify an isolated release candidate

**Files:**

- Read: `产品代码/scripts/build-plugin-release.mjs`
- Read: `产品代码/scripts/verify-plugin-release.mjs`
- Output: `/private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio`

- [ ] **Step 1: Require an unused isolated output root**

Run:

```bash
test ! -e /private/tmp/ai-ppt-studio-mcp-python-release-20260825
```

Expected: exit `0`. If the path already exists, stop and report it; do not recursively delete an unresolved target.

- [ ] **Step 2: Build the release from the committed feature tree**

Run from `产品代码`:

```bash
npm run release -- --output /private/tmp/ai-ppt-studio-mcp-python-release-20260825
```

Expected: JSON with `ok: true` and `pluginRoot` equal to `/private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio`.

- [ ] **Step 3: Verify manifest, required/forbidden shape, and official validator**

Run:

```bash
node --input-type=module -e '
import { verifyPluginRelease } from "./scripts/verify-plugin-release.mjs";
const result = await verifyPluginRelease(
  "/private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio",
  { probe: false },
);
process.stdout.write(`${JSON.stringify(result)}\n`);
'
```

Expected: `ok: true`, `version: "0.4.0"`, a positive file count, and a release-manifest SHA-256. `{ probe: false }` deliberately excludes `scripts/probe-mcp.mjs`, whose tool-catalog assertions are outside this recovery unit; the official validator and release allowlist/manifest checks still run.

- [ ] **Step 4: Prove the binding propagated and forbidden source did not**

Run:

```bash
rg -n 'AI_PPT_PYTHON|resolveBundledPythonExecutable' /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/.mcp.json /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/mcp/runtime-bridge/python-runtime.mjs
test ! -e /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/tests
test ! -e /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/docs
test ! -e /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/widget/src
test ! -e /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/.git
shasum -a 256 /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio/release-manifest.json
```

Expected: both environment-variable names and resolver are found; all absence checks exit `0`; record the manifest hash.

- [ ] **Step 5: Run the release bridge with bundled Node and empty PATH**

Run from the release plugin root:

```bash
cd /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio
PATH='' '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' --input-type=module -e '
import { invokePythonBridge, resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
const env = { ...process.env, PATH: "" };
delete env.AI_PPT_PYTHON;
const executable = resolvePythonExecutable({ env });
const result = await invokePythonBridge({ operation: "list-projects" }, { env });
process.stdout.write(`${JSON.stringify({ executable, ok: result.ok })}\n`);
'
```

Expected: the exact bundled Python path and `ok: true`.

### Task 8: Install the verified release and generate a fresh Codex cache

**Files and external state:**

- Read: `产品代码/scripts/install-plugin.mjs`
- Replace atomically after explicit authorization: `/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio`
- Update: installed `.codex-plugin/plugin.json` cachebuster and installed `release-manifest.json`
- Generate: a new cache below `/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/`

- [ ] **Step 1: Pause for the release-install checkpoint**

Report the feature commit, clean status, full engineering results, release root, release manifest SHA-256, validator result, and empty-PATH release-bridge result. Obtain explicit authorization before replacing the installed plugin or changing Codex cache state.

- [ ] **Step 2: Verify the marketplace still points to the approved root**

Run:

```bash
codex plugin marketplace list --json
codex plugin list --json
```

Expected: marketplace `defei-ai-ppt-studio-040` points to `/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0`, and `ai-ppt-studio@defei-ai-ppt-studio-040` is the enabled target. A different root stops installation.

- [ ] **Step 3: Atomically install the verified release**

Run from the feature worktree's `产品代码` directory:

```bash
node scripts/install-plugin.mjs --release /private/tmp/ai-ppt-studio-mcp-python-release-20260825/ai-ppt-studio --target /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
```

Expected: JSON with `ok: true` and the exact install root. The installer pre-verifies, stages, re-verifies, renames atomically, and limits replacement to this plugin directory; managed projects are outside the target.

- [ ] **Step 4: Add a new cachebuster to the installed plugin**

Run:

```bash
python3 '/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py' '/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio'
```

Expected: installed plugin version changes from `0.4.0` to one new `0.4.0+codex.<timestamp>` value. The source repository remains `0.4.0`.

- [ ] **Step 5: Refresh the installed manifest after the cachebuster mutation**

Run from the feature worktree's `产品代码` directory:

```bash
node scripts/build-plugin-release.mjs --refresh-release /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
node --input-type=module -e '
import { verifyPluginRelease } from "./scripts/verify-plugin-release.mjs";
const result = await verifyPluginRelease(
  "/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio",
  { probe: false },
);
process.stdout.write(`${JSON.stringify(result)}\n`);
'
```

Expected: manifest refresh reports `ok: true`, then installed-root verification passes with the new cachebuster version. Never retain the pre-cachebuster manifest because its hash for `plugin.json` is stale.

- [ ] **Step 6: Ask Codex to install the new marketplace version into cache**

Run:

```bash
codex plugin add ai-ppt-studio@defei-ai-ppt-studio-040 --json
codex plugin list --json | jq '.installed[] | select(.pluginId == "ai-ppt-studio@defei-ai-ppt-studio-040") | {pluginId, version, installed, enabled, source}'
```

Expected: add succeeds, and the listed version equals the new installed cachebuster with `installed: true` and `enabled: true`.

- [ ] **Step 7: Verify the exact installed and cached copies**

Run as one shell block:

```bash
AI_PPT_CACHE_VERSION="$(node -p 'JSON.parse(require("node:fs").readFileSync("/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/.codex-plugin/plugin.json", "utf8")).version')"
AI_PPT_CACHE_PLUGIN_ROOT="/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/${AI_PPT_CACHE_VERSION}"
test -d "$AI_PPT_CACHE_PLUGIN_ROOT"
rg -n 'AI_PPT_PYTHON|resolveBundledPythonExecutable' '/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/.mcp.json' '/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/mcp/runtime-bridge/python-runtime.mjs' "$AI_PPT_CACHE_PLUGIN_ROOT/.mcp.json" "$AI_PPT_CACHE_PLUGIN_ROOT/mcp/runtime-bridge/python-runtime.mjs"
node --input-type=module -e '
import { verifyPluginRelease } from "./scripts/verify-plugin-release.mjs";
const cacheRoot = process.argv[1];
const result = await verifyPluginRelease(cacheRoot, { probe: false });
process.stdout.write(`${JSON.stringify(result)}\n`);
' "$AI_PPT_CACHE_PLUGIN_ROOT"
```

Expected: the new exact cache directory exists; installed and cache copies contain the binding; cache manifest and official validator pass.

### Task 9: Perform fresh-process MCP acceptance with zero project writes

**Files and external state:**

- Read-only target: `/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7`
- Read: `kernel/state.json`
- Temporary evidence: `/private/tmp/ai-ppt-mcp-runtime-state-before.json`
- MCP operation: `get_ai_ppt_project_snapshot`

The target path is fixed, but its revision is not. Do not hardcode the previously observed revision `95` or any prior `last_transaction_id`; read current live state immediately before acceptance.

- [ ] **Step 1: Start a genuinely fresh plugin process**

Completely restart Codex or open a fresh Codex task after the new cache is installed. If the host cannot prove a fresh process, stop and ask the user to restart/reopen; disk installation, cache presence, or tool listing alone is insufficient.

- [ ] **Step 2: Capture the immediate pre-call project state**

Run:

```bash
cp '/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7/kernel/state.json' /private/tmp/ai-ppt-mcp-runtime-state-before.json
shasum -a 256 /private/tmp/ai-ppt-mcp-runtime-state-before.json
jq '{revision, last_transaction_id, gate_status, artifact_heads}' /private/tmp/ai-ppt-mcp-runtime-state-before.json
```

Expected: one current hash and structured values are captured immediately before the MCP call. Do not run a project mutation between this step and Step 3.

- [ ] **Step 3: Call the real fresh MCP snapshot tool**

Call in the fresh task:

```text
get_ai_ppt_project_snapshot(
  projectRoot="/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7"
)
```

Expected:

- A structured schema 3 snapshot is returned.
- Snapshot revision equals the live pre-call revision read in Step 2.
- No `spawn /usr/bin/python3 ENOENT` or interpreter startup error occurs.
- The operation remains read-only; do not call any material, artifact, decision, Gate, delivery, closeout, or experience-writing tool.

- [ ] **Step 4: Prove the MCP call caused zero project-state change**

Run immediately after the MCP result:

```bash
cmp -s /private/tmp/ai-ppt-mcp-runtime-state-before.json '/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7/kernel/state.json'
shasum -a 256 '/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7/kernel/state.json'
jq '{revision, last_transaction_id, gate_status, artifact_heads}' '/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7/kernel/state.json'
```

Expected: `cmp` exits `0`; before/after SHA-256 values match; revision, `last_transaction_id`, complete Gate map, and artifact/project heads are unchanged. Any concurrent state change invalidates the acceptance evidence even if the MCP call returned successfully.

### Task 10: Close the feature unit without integration

**Files:**

- Verify: feature branch commit history and worktree status
- Verify read-only: recovery integration and quarantine refs

- [ ] **Step 1: Re-run source checks after external acceptance**

Run from the feature worktree root:

```bash
git status --short --branch
git log --oneline --decorate -4
git show --format= --name-only HEAD
git diff --check HEAD^ HEAD
git rev-parse codex/v22-recovery-integration-20260825
git -C '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app' status --short --branch
```

Expected:

- Feature worktree is clean.
- HEAD is the four-file implementation commit.
- Recovery integration remains unmodified unless the user separately authorized an integration action.
- Quarantine remains observation-only with no change attributable to this unit.

- [ ] **Step 2: Report every completion state separately**

Report:

```text
Design approved: yes
Plan committed: yes
Implemented: yes/no
Implementation committed: yes/no + commit
Focused verification: pass/fail + counts
Full engineering verification: pass/fail + counts
Release verified: yes/no + release manifest SHA-256
Installed: yes/no + cachebuster version
Fresh MCP verified: yes/no + snapshot revision read live
Zero write verified: yes/no + matching state SHA-256
Integrated: no unless separately authorized
Pushed: no unless separately authorized
Released: not implied by installation
User accepted: not implied by technical completion
```

List any CapabilityGap or NotRun item explicitly. Do not describe this unit as completing ReviewSession, typed catalog, content objects, hard gates, content review, visual review, G3/G4, complete v2.2 recovery, release, or user product acceptance.

## Plan self-review result

- **Spec coverage:** Task 1 freezes the exact worktree/source/blobs; Task 2 enforces the pre-change engineering gate; Tasks 3–4 cover all required resolver, priority, manifest, fallback, and error contracts; Tasks 5–6 cover focused and full engineering proof plus the atomic four-file commit; Tasks 7–9 cover release propagation, installed/cache validation, fresh MCP, and zero-write evidence; Task 10 preserves the integration/acceptance boundary.
- **Scope:** the plan creates one implementation rollback unit and never authorizes edits to a fifth production file, content review, visual review, Python business services, tool catalog, baseline documents, recovery integration, or quarantine.
- **Signature consistency:** the resolver is always `resolveBundledPythonExecutable(nodeExecutable = process.execPath, platform = process.platform)`, test injection is always `options.nodeExecutable`, and executable priority is consistent in tests and implementation.
- **Error consistency:** explicit options are deterministic; default candidates retry only on `ENOENT`; `EACCES`, valid Python business errors, and invalid bridge responses do not switch interpreters.
- **Placeholder scan:** every file edit contains complete code, every command has an expected result, the acceptance project is exact, and dynamic revision/cache values are read at runtime rather than guessed.
- **Status boundary:** implementation, commit, engineering verification, release verification, installation, fresh MCP verification, integration, release, and user acceptance remain distinct states.
