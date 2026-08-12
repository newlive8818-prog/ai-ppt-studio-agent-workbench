import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import { buildPluginRelease } from "../scripts/build-plugin-release.mjs";
import { installPluginRelease } from "../scripts/install-plugin.mjs";
import { verifyPluginRelease } from "../scripts/verify-plugin-release.mjs";

async function tree(root) {
  const rows = [];
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      const relative = path.relative(root, absolute).split(path.sep).join("/");
      if (entry.isSymbolicLink()) rows.push([relative, "symlink"]);
      else if (entry.isDirectory()) {
        rows.push([relative, "directory"]);
        await visit(absolute);
      } else {
        const digest = createHash("sha256").update(await readFile(absolute)).digest("hex");
        rows.push([relative, digest]);
      }
    }
  }
  await visit(root);
  return rows.sort((left, right) => left[0].localeCompare(right[0]));
}

function runCli(pluginRoot, roots, args) {
  const result = spawnSync(
    "python3",
    [
      "-m",
      "ai_ppt_studio",
      "--runtime-root",
      roots.runtime,
      "--source-repo-root",
      roots.repo,
      "--install-root",
      roots.install,
      "--upstream-root",
      roots.web,
      ...args,
    ],
    {
      cwd: roots.web,
      encoding: "utf8",
      env: { ...process.env, PYTHONPATH: path.join(pluginRoot, "src") },
    },
  );
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test("release is deterministic, production-only, installable, and runtime-safe", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-plugin-release-test-"));
  const output = path.join(base, "release");
  const plugin = await buildPluginRelease({ outputRoot: output });
  const firstManifest = await readFile(path.join(plugin, "release-manifest.json"), "utf8");
  const firstVerification = await verifyPluginRelease(plugin, { probe: false });

  assert.equal(firstVerification.ok, true);
  assert.equal(firstVerification.version, "0.4.0");
  for (const required of [
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "skills/ai-ppt-studio/SKILL.md",
    "mcp/server.mjs",
    "src/ai_ppt_studio/workbench_bridge.py",
    "widget/dist/index.html",
    "node_modules/@modelcontextprotocol/sdk/package.json",
  ]) {
    assert.equal((await stat(path.join(plugin, required))).isFile(), true, required);
  }
  for (const forbidden of ["tests", "docs", "widget/src", "requirements", ".git"])
    await assert.rejects(stat(path.join(plugin, forbidden)));
  assert.equal((await tree(plugin)).some(([, kind]) => kind === "symlink"), false);

  const rebuilt = await buildPluginRelease({ outputRoot: output });
  assert.equal(
    await readFile(path.join(rebuilt, "release-manifest.json"), "utf8"),
    firstManifest,
  );
  await verifyPluginRelease(rebuilt);
  assert.equal(
    await readFile(path.join(rebuilt, "release-manifest.json"), "utf8"),
    firstManifest,
  );
  await verifyPluginRelease(rebuilt, { probe: false });

  const installParent = path.join(base, "plugins");
  const target = path.join(installParent, "ai-ppt-studio");
  await installPluginRelease({ releaseRoot: rebuilt, targetRoot: target });
  const roots = {
    runtime: path.join(base, "runtime"),
    repo: path.join(base, "source-repo"),
    install: installParent,
    web: path.join(base, "web"),
  };
  await mkdir(roots.web, { recursive: true });
  const created = runCli(target, roots, ["init", "--name", "恢复验收项目", "--project-id", "recovery-project"]);
  assert.equal(created.project.schema_version, "3.0");
  const workspaceProfile = path.join(roots.runtime, "workspace.json");
  await writeFile(
    workspaceProfile,
    `${JSON.stringify({
      schema_version: "1.0",
      runtime_root: roots.runtime,
      source_repo_root: roots.repo,
      install_root: roots.install,
      upstream_root: roots.web,
      protected_roots: [roots.repo, roots.install, roots.web],
    }, null, 2)}\n`,
    "utf8",
  );
  const pathlessProbe = spawnSync(process.execPath, ["scripts/probe-mcp.mjs"], {
    cwd: target,
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: "",
      PYTHONPATH: "",
      AI_PPT_WORKSPACE_CONFIG: workspaceProfile,
      AI_PPT_PROBE_PROJECT: created.project.project_root,
    },
  });
  assert.equal(pathlessProbe.status, 0, pathlessProbe.stderr || pathlessProbe.stdout);
  const probe = JSON.parse(pathlessProbe.stdout);
  assert.equal(probe.ok, true);
  assert.equal(probe.mission_confirmation.host_native_fallback, true);
  assert.equal(probe.mission_confirmation.mission_summary_exposed, true);
  assert.equal(probe.mission_confirmation.chat_ui_template, false);
  const before = await tree(roots.runtime);

  await installPluginRelease({ releaseRoot: rebuilt, targetRoot: target });
  assert.deepEqual(await tree(roots.runtime), before);
  const status = runCli(target, roots, ["status", "--project", created.project.project_root]);
  assert.equal(status.snapshot.schema_version, "3.0");
  assert.equal(status.snapshot.revision, created.project.revision);
  assert.deepEqual(
    (await readdir(installParent)).filter((name) => name.startsWith(".ai-ppt-studio-")),
    [],
  );
});
