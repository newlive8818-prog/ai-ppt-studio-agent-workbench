# MCP Bundled Python Runtime Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI PPT Studio Node MCP reliably start the Codex bundled Python runtime without depending on `/usr/bin/python3`, while preserving explicit overrides and existing fallback behavior.

**Architecture:** Forward optional Python override variables through the plugin STDIO manifest. In the Node bridge, resolve a bundled Python candidate from the active Node executable only when it matches the Codex `dependencies/node/bin` layout, then place that candidate after explicit overrides and before system Python candidates. Keep bridge JSON, Runtime business rules, Gate logic, and project state unchanged.

**Tech Stack:** Node.js ES modules, `node:test`, Codex plugin `.mcp.json`, AI PPT Studio Python bridge, release manifest tooling, Git.

---

## File map and rollback boundary

**Create:**

- `产品代码/docs/superpowers/plans/2026-08-23-mcp-bundled-python-runtime-binding.md` — this execution plan.

**Modify:**

- `产品代码/.mcp.json` — forwards `AI_PPT_PYTHON` and `AI_PPT_PYTHONPATH` into the plugin STDIO MCP.
- `产品代码/mcp/runtime-bridge/python-runtime.mjs` — discovers the Codex bundled Python from the active Node executable and preserves override/fallback order.
- `产品代码/tests/mcp-runtime-bridge.test.mjs` — proves bundled discovery, malformed-layout rejection, explicit override priority, and existing retry behavior.
- `产品代码/tests/plugin-shape.test.mjs` — proves the MCP manifest forwards exactly the two approved variables.

**Do not modify:**

- `产品代码/scripts/probe-mcp.mjs` — its stale `18`-tool assertion is a separate rollback unit.
- Python Runtime business services, Gate rules, project state, acceptance ledger, visual reviewer fixtures, Widget, or review UI.
- `.superpowers/`, `.workbuddy/`, or `分享材料/`.

**Rollback:** revert the implementation commit created in Task 4. Do not amend `2d832fb` or design commit `12b9454`; do not reset or clean the worktree.

### Task 1: Add RED tests for bundled Python discovery and manifest forwarding

**Files:**

- Modify: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Modify: `产品代码/tests/plugin-shape.test.mjs`
- Test: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Test: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Extend the bridge test imports**

Change the filesystem import and bridge import to:

```js
import { chmod, mkdir, mkdtemp, writeFile } from "node:fs/promises";

import {
  invokePythonBridge,
  resolveBundledPythonExecutable,
  resolvePythonExecutable,
} from "../mcp/runtime-bridge/python-runtime.mjs";
```

- [ ] **Step 2: Add a failing bundled-runtime discovery test**

Add after `Python bridge returns a structured snapshot`:

```js
test("Python bridge prefers the Python bundled beside the active Codex Node runtime", async () => {
  const runtime = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-codex-runtime-"));
  const nodeExecutable = path.join(runtime, "dependencies", "node", "bin", "node");
  const pythonExecutable = path.join(runtime, "dependencies", "python", "bin", "python3");
  await mkdir(path.dirname(nodeExecutable), { recursive: true });
  await mkdir(path.dirname(pythonExecutable), { recursive: true });
  await writeFile(nodeExecutable, "", "utf8");
  await writeFile(pythonExecutable, "", "utf8");

  const hostEnv = { ...process.env, PATH: "" };
  delete hostEnv.AI_PPT_PYTHON;
  assert.equal(
    resolvePythonExecutable({ env: hostEnv, nodeExecutable }),
    pythonExecutable,
  );
});
```

- [ ] **Step 3: Add a failing layout-safety test**

Add immediately after the bundled discovery test:

```js
test("bundled Python discovery rejects an unrelated Node directory layout", () => {
  assert.equal(
    resolveBundledPythonExecutable("/opt/homebrew/bin/node", "darwin"),
    undefined,
  );
  assert.equal(
    resolveBundledPythonExecutable("C:\\Program Files\\nodejs\\node.exe", "win32"),
    undefined,
  );
});
```

- [ ] **Step 4: Add an explicit override priority test**

Add immediately after the layout-safety test:

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
```

- [ ] **Step 5: Prove the direct call option has the highest priority**

Add immediately after the environment override test:

```js
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
```

- [ ] **Step 6: Prove a missing bundled Python falls back to a system candidate**

Add immediately after the direct-option test:

```js
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

- [ ] **Step 7: Prove a Python business error does not switch interpreters**

Add immediately before `Python bridge surfaces stable revision conflicts`:

```js
test("Python bridge does not retry another interpreter after a business error", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-python-no-business-retry-"));
  const bridge = path.join(temporary, "bridge.py");
  const missingFallback = path.join(temporary, "must-not-run-python");
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
        pythonCandidates: [workingPython, missingFallback],
        bridgeArgs: [bridge],
      },
    ),
    (error) => error.code === "REVISION_CONFLICT" && error.details.actual_revision === 2,
  );
});
```

If the bridge incorrectly retries after `REVISION_CONFLICT`, the missing second executable changes the observed error to `ENOENT`, so this assertion fails.

- [ ] **Step 8: Extend the plugin-shape assertion**

In `MCP config starts the local stdio server from the plugin root`, add:

```js
  assert.deepEqual(server.env_vars, [
    "AI_PPT_PYTHON",
    "AI_PPT_PYTHONPATH",
  ]);
```

- [ ] **Step 9: Run the focused tests and verify RED**

Run:

```bash
cd 产品代码
node --test tests/mcp-runtime-bridge.test.mjs tests/plugin-shape.test.mjs
```

Expected: FAIL before production changes. The bridge suite must report that `resolveBundledPythonExecutable` is not exported or the bundled candidate is not selected; the plugin-shape suite must report `server.env_vars` is missing. Existing bridge tests may continue passing.

- [ ] **Step 10: Confirm RED changed no production files**

Run:

```bash
git status --short
git diff -- 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/.mcp.json
```

Expected: only the two test files and this plan differ; production-file diff is empty.

### Task 2: Implement the minimal bundled-runtime binding

**Files:**

- Modify: `产品代码/.mcp.json`
- Modify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Test: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Test: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Forward the approved MCP environment variables**

Change the `ai_ppt_studio` server entry in `.mcp.json` to:

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

- [ ] **Step 2: Add the pure bundled-path resolver**

Insert before `defaultPythonCandidates` in `python-runtime.mjs`:

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

- [ ] **Step 3: Put the bundled candidate before system candidates**

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

- [ ] **Step 4: Pass the injectable Node executable and deduplicate candidates**

Replace the candidate-resolution block inside `resolvePythonExecutables` with:

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

Keep the explicit `options.pythonExecutable` and `env.AI_PPT_PYTHON` early returns unchanged.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
cd 产品代码
node --test tests/mcp-runtime-bridge.test.mjs tests/plugin-shape.test.mjs
```

Expected: all focused tests pass, including the existing ENOENT retry and revision-conflict tests.

- [ ] **Step 6: Run static and whitespace checks**

Run:

```bash
node --check mcp/runtime-bridge/python-runtime.mjs
node -e 'JSON.parse(require("node:fs").readFileSync(".mcp.json", "utf8")); process.stdout.write("valid\n")'
git diff --check
```

Expected: Node syntax check exits `0`, JSON prints `valid`, and `git diff --check` prints nothing.

### Task 3: Prove the bridge works with an empty ordinary PATH

**Files:**

- Verify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Verify: `产品代码/src/ai_ppt_studio/workbench_bridge.py`
- Verify: `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`
- Verify: `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`

- [ ] **Step 1: Run the bridge with bundled Node and empty PATH**

Run from `产品代码`:

```bash
PATH='' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --input-type=module -e '
import { invokePythonBridge, resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
const env = { ...process.env, PATH: "" };
delete env.AI_PPT_PYTHON;
const executable = resolvePythonExecutable({ env });
const result = await invokePythonBridge({ operation: "list-projects" }, { env });
process.stdout.write(JSON.stringify({ executable, ok: result.ok, projectCount: result.projects.length }));
'
```

Expected JSON:

```json
{
  "executable": "/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
  "ok": true,
  "projectCount": 14
}
```

The `projectCount` may increase if another managed project exists; `executable` and `ok` are the pass conditions.

- [ ] **Step 2: Prove an explicit override still wins**

Run:

```bash
AI_PPT_PYTHON='/usr/bin/python3' PATH='' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --input-type=module -e '
import { resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
process.stdout.write(resolvePythonExecutable({ env: process.env }));
'
```

Expected exact output: `/usr/bin/python3`. This proves the new fallback does not override an explicit administrator choice.

- [ ] **Step 3: Run the full Node suite and classify unrelated failures**

Run:

```bash
cd 产品代码
npm run test:node
```

Expected: all Node tests affected by this change pass. If an existing test fails only because `scripts/probe-mcp.mjs` expects 18 rather than 26 tools, record it as the already-known separate release-probe defect and do not change that script in this task.

### Task 4: Review and commit the implementation rollback unit

**Files:**

- Modify: `产品代码/.mcp.json`
- Modify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Modify: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Modify: `产品代码/tests/plugin-shape.test.mjs`

- [ ] **Step 1: Inspect the exact implementation diff**

Run:

```bash
git diff -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/tests/mcp-runtime-bridge.test.mjs 产品代码/tests/plugin-shape.test.mjs
git diff --check
git status --short --branch
```

Expected: only the four implementation files and this plan are new/modified; unrelated untracked directories remain untouched.

- [ ] **Step 2: Stage only the four implementation files**

Run:

```bash
git add -- 产品代码/.mcp.json 产品代码/mcp/runtime-bridge/python-runtime.mjs 产品代码/tests/mcp-runtime-bridge.test.mjs 产品代码/tests/plugin-shape.test.mjs
git diff --cached --check
git diff --cached --stat
```

Expected: four files staged, no whitespace error.

- [ ] **Step 3: Commit the implementation**

Run:

```bash
git commit -m "fix: bind MCP to bundled Python runtime"
```

Expected: one new commit after `12b9454`; do not amend prior history.

### Task 5: Build, verify, and install a new plugin release

**Files:**

- Read: `产品代码/scripts/build-plugin-release.mjs`
- Read: `产品代码/scripts/verify-plugin-release.mjs`
- Read: `产品代码/scripts/install-plugin.mjs`
- Output: `/private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio`
- Install: `/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio`

- [ ] **Step 1: Build a clean release**

Run from `产品代码`:

```bash
node scripts/build-plugin-release.mjs --output /private/tmp/ai-ppt-studio-mcp-python-release
```

Expected: JSON with `ok: true` and plugin root `/private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio`.

- [ ] **Step 2: Verify the manifest without the unrelated stale tool-count probe**

Run:

```bash
node --input-type=module -e '
import { verifyPluginRelease } from "./scripts/verify-plugin-release.mjs";
const result = await verifyPluginRelease("/private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio", { probe: false });
process.stdout.write(JSON.stringify(result));
'
```

Expected: `ok: true`, `version: "0.4.0"`, and a manifest SHA-256. This step must also pass the official plugin validator.

- [ ] **Step 3: Confirm the release contains the binding**

Run:

```bash
rg -n 'AI_PPT_PYTHON|resolveBundledPythonExecutable' /private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio/.mcp.json /private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio/mcp/runtime-bridge/python-runtime.mjs
```

Expected: both environment-variable entries and the bundled resolver are present.

- [ ] **Step 4: Run the installed-release bridge under empty PATH before installation**

Run:

```bash
cd /private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio
PATH='' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --input-type=module -e '
import { invokePythonBridge, resolvePythonExecutable } from "./mcp/runtime-bridge/python-runtime.mjs";
const env = { ...process.env, PATH: "" };
const executable = resolvePythonExecutable({ env });
const result = await invokePythonBridge({ operation: "list-projects" }, { env });
process.stdout.write(JSON.stringify({ executable, ok: result.ok }));
'
```

Expected: bundled Python path and `ok: true`.

- [ ] **Step 5: Install the verified release**

Run from `产品代码`:

```bash
node scripts/install-plugin.mjs --release /private/tmp/ai-ppt-studio-mcp-python-release/ai-ppt-studio --target /Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio
```

Expected: JSON with `ok: true` and the exact install root. The installer must replace only the plugin directory and preserve managed project data.

- [ ] **Step 6: Generate a new installed-plugin cachebuster**

Run:

```bash
python3 "/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py" "/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio"
```

Expected: `.codex-plugin/plugin.json` receives a new `0.4.0+codex.<timestamp>` version; source repository version remains `0.4.0`.

- [ ] **Step 7: Re-register the plugin**

Run:

```bash
codex plugin add "/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio"
```

Expected: plugin registration succeeds and a new cache directory contains the new cachebuster version.

- [ ] **Step 8: Inspect installed and cached copies**

Run:

```bash
rg -n 'AI_PPT_PYTHON|resolveBundledPythonExecutable' "/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/.mcp.json" "/Users/defei/plugins/AI-PPT-Studio-Codex-Plugin-0.4.0/plugins/ai-ppt-studio/mcp/runtime-bridge/python-runtime.mjs"
```

Then locate the new cache with `rg --files` under:

```text
/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040
```

and run the same `rg` check against that exact cache directory.

Expected: source release, installed plugin, and new cache all contain the same binding logic.

### Task 6: Fresh-process Codex MCP acceptance

**Files and state:**

- Read-only target project: `/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7`
- Expected pre-confirmation state: revision `95`, G4 `delivery-ready`

- [ ] **Step 1: Restart the Codex task MCP after installation**

Use the ChatGPT desktop app/Codex MCP server control to restart the AI PPT Studio server, or reopen the task so it creates a fresh plugin STDIO process. Do not infer a restart from disk installation or cache presence.

Expected: the active tool process is created from the new cachebuster version.

- [ ] **Step 2: Call the real MCP snapshot tool**

Call:

```text
get_ai_ppt_project_snapshot(
  projectRoot="/Users/defei/Documents/AI-PPT-Workspace/projects/project-b0974a94f2a7"
)
```

Expected:

- the tool returns a structured schema 3 snapshot;
- revision remains `95`;
- G4 remains `delivery-ready` until the separate G4 closeout task;
- no `spawn /usr/bin/python3 ENOENT` appears.

- [ ] **Step 3: Check zero-write behavior**

Run a direct read of `kernel/state.json` and compare revision and `last_transaction_id` with the pre-restart values.

Expected: snapshot verification is read-only and does not create a transaction.

- [ ] **Step 4: Mark this repair complete without crossing into G4**

Report separately:

- source fix committed;
- release built and installed;
- fresh MCP snapshot passed;
- project business state unchanged;
- G4 confirmation, project closure, retrospective, acceptance-ledger migration, visual fixture repair, and 18/26 probe repair remain separate tasks.

Do not call `record_chat_delivery`, `confirm_ai_ppt_gate`, `close_ai_ppt_project`, or `summarize_project_experience` in this implementation plan.

## Plan self-review result

- **Spec coverage:** explicit env forwarding, bundled discovery, safe layout matching, override priority, fallback/retry behavior, release propagation, installation, fresh-process proof, rollback, and no business-state mutation are covered.
- **Scope:** one integration defect and one implementation commit; no acceptance-ledger, visual, UI, Gate, or tool-count changes.
- **Type consistency:** the plan uses one exported resolver name, `resolveBundledPythonExecutable`, and one injectable option, `nodeExecutable`, throughout.
- **No placeholders:** every code change, command, expected outcome, and stop condition is explicit.
