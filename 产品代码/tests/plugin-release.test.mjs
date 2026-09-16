import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdtemp, mkdir, readdir, readFile, realpath, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { buildPluginRelease, refreshPluginReleaseManifest } from "../scripts/build-plugin-release.mjs";
import { installPluginRelease } from "../scripts/install-plugin.mjs";
import { verifyPluginRelease } from "../scripts/verify-plugin-release.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NATIVE_SCRIPT = "scripts/image-led-native.mjs";
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");

// Run only shipped code and a separately copied synthetic data fixture. The
// empty working directory and closed environment prevent source-tree fallback.
const PACKAGED_NATIVE_RUNNER = `
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [plugin, fixture, base, modules, python] = process.argv.slice(2);
const { preflight, render, verifyOutputSnapshots } = await import(pathToFileURL(path.join(plugin, 'scripts/image-led-native.mjs')).href);
const { syntheticHandoff, digest } = await import(pathToFileURL(fixture).href);
assert.equal(process.env.PYTHONPATH, undefined);
assert.equal(process.env.PYTHONHOME, undefined);
assert.deepEqual(await fs.readdir(process.cwd()), []);
const root = await fs.realpath(await fs.mkdir(path.join(base, 'native-project'), { recursive: true }).then(() => path.join(base, 'native-project')));
const options = { projectRoot: root, nodeModulesRoot: modules, pythonExecutable: python };
const valid = syntheticHandoff(root);
const checked = await preflight(valid, options);
assert.equal(checked.handoff.slides.length, 3);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
const negatives = [
  ['finalized text mutation', h => { h.slides[0].objects[0].content.items[0].text = 'unauthorized mutation'; }],
  ['selected copy hash', h => { h.slides[0].target_binding.selected_copy_sha256 = 'f'.repeat(64); }],
  ['target image hash', h => { h.slides[0].target_binding.target_image_sha256 = 'f'.repeat(64); }],
  ['page identity', h => { h.slides[1].target_binding.page_order = 1; }],
  ['missing region mapping', h => { h.slides[0].objects.pop(); }],
  ['output escapes project', h => { h.output_paths.directory = path.join(base, h.task_id); h.output_paths.pptx = path.join(h.output_paths.directory, 'native-anchors.pptx'); }],
];
for (const [label, mutate] of negatives) {
  const invalid = structuredClone(valid); mutate(invalid); let loads = 0;
  await assert.rejects(render(invalid, { ...options, loadSdk: async () => { loads++; throw new Error('unexpected authoring SDK load'); } }), /IMAGE_LED_/, label);
  assert.equal(loads, 0, label);
  await assert.rejects(fs.stat(invalid.output_paths.directory), { code: 'ENOENT' }, label);
  await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' }, label);
}
// A sacrificial complete package cannot recover its removed domain module from
// the source repo, the parent test's PYTHONPATH, or the working directory.
const missingDomain = path.join(base, 'missing-domain-plugin');
await fs.cp(plugin, missingDomain, { recursive: true });
await fs.rm(path.join(missingDomain, 'src/ai_ppt_studio/domains/visual/image_led.py'));
const broken = await import(pathToFileURL(path.join(missingDomain, 'scripts/image-led-native.mjs')).href);
let domainLoads = 0;
await assert.rejects(broken.render(valid, { ...options, loadSdk: async () => { domainLoads++; throw new Error('unexpected authoring SDK load'); } }), /Domain preflight rejected:[\\s\\S]*ModuleNotFoundError[\\s\\S]*ai_ppt_studio\\.domains\\.visual\\.image_led/);
assert.equal(domainLoads, 0);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
// Keep the real image dependency available while removing only the external
// authoring SDK from an isolated resolution root. Never stub SDK behavior.
const missingSdk = path.join(base, 'missing-sdk', 'node_modules');
await fs.mkdir(missingSdk, { recursive: true });
await fs.symlink(await fs.realpath(path.join(modules, 'sharp')), path.join(missingSdk, 'sharp'), 'dir');
let sdkLoads = 0;
await assert.rejects(render(valid, { ...options, nodeModulesRoot: missingSdk, loadSdk: async () => { sdkLoads++; throw new Error('unexpected authoring SDK load'); } }), error => error.code === 'MODULE_NOT_FOUND' && /@oai\\/artifact-tool/.test(error.message));
assert.equal(sdkLoads, 0);
await assert.rejects(fs.stat(valid.output_paths.directory), { code: 'ENOENT' });
// Existing outputs are byte-preserved, including nested and binary content.
await fs.mkdir(path.join(valid.output_paths.directory, 'nested'), { recursive: true });
const preserved = Buffer.from([0, 255, 13, 10, 42]);
const preservedPath = path.join(valid.output_paths.directory, 'nested', 'accepted.bin');
await fs.writeFile(preservedPath, preserved);
let existingLoads = 0;
await assert.rejects(render(valid, { ...options, loadSdk: async () => { existingLoads++; throw new Error('unexpected authoring SDK load'); } }), /Output directory already exists/);
assert.equal(existingLoads, 0);
assert.deepEqual(await fs.readdir(valid.output_paths.directory), ['nested']);
assert.deepEqual(await fs.readdir(path.dirname(preservedPath)), ['accepted.bin']);
assert.deepEqual(await fs.readFile(preservedPath), preserved);
// Render into a different fresh synthetic project; do not remove the preserved output.
const renderRoot = path.join(base, 'render-project'); await fs.mkdir(renderRoot);
const handoff = syntheticHandoff(renderRoot);
const result = await render(handoff, { ...options, projectRoot: renderRoot });
assert.equal(result.status, 'engineering-output-unassessed');
for (const key of ['visual_fidelity', 'user_acceptance', 'target_powerpoint']) assert.equal(result[key], 'not-established');
assert.equal(result.renders.length, 3); assert.equal(result.comparisons.length, 3);
assert.equal(digest(await fs.readFile(result.pptx_path)), result.pptx_sha256);
for (const row of [...result.renders, ...result.comparisons.flatMap(c => [c.side_by_side, c.overlay, c.region_differences])]) {
  assert.equal(digest(await fs.readFile(row.path)), row.sha256);
}
const encode = async p => (await fs.readFile(p)).toString('base64');
const snapshots = { pptx_base64: await encode(result.pptx_path), handoff,
  renders: await Promise.all(result.renders.map(r => encode(r.path))),
  comparisons: await Promise.all(result.comparisons.map(async c => ({ side_by_side: await encode(c.side_by_side.path), overlay: await encode(c.overlay.path), region_differences: JSON.parse(await fs.readFile(c.region_differences.path, 'utf8')) }))) };
const verified = await verifyOutputSnapshots(snapshots, { nodeModulesRoot: modules });
assert.equal(verified.pptx_sha256, result.pptx_sha256); assert.equal(verified.verified_pages, 3);
assert.deepEqual(await fs.readFile(preservedPath), preserved);
await fs.writeFile(path.join(base, 'packaged-native-result.json'), JSON.stringify({ packaged_native: 'PASS', preflight: 'read-only', counterexamples: [...negatives.map(([label]) => label), 'missing package domain', 'missing external SDK', 'existing output bytes preserved'], ...verified, user_acceptance: result.user_acceptance, target_powerpoint: result.target_powerpoint }), { flag: 'wx' });
`;

async function packagedNativeRegression(plugin, base) {
  const modules = process.env.C2_RUNTIME_NODE_MODULES;
  const python = process.env.C2_RUNTIME_PYTHON;
  assert.ok(modules && path.isAbsolute(modules), "C2_RUNTIME_NODE_MODULES is required; packaged native regression cannot be skipped");
  assert.ok(python && path.isAbsolute(python), "C2_RUNTIME_PYTHON is required; packaged native regression cannot be skipped");
  const emptyCwd = path.join(base, "empty-cwd");
  const harness = path.join(base, "harness");
  await mkdir(emptyCwd); await mkdir(harness);
  const fixture = path.join(harness, "image-led-synthetic.mjs");
  await cp(path.join(ROOT, "tests/fixtures/image-led-synthetic.mjs"), fixture);
  assert.equal(digest(await readFile(fixture)), digest(await readFile(path.join(ROOT, "tests/fixtures/image-led-synthetic.mjs"))));
  const runner = path.join(harness, "packaged-native.mjs");
  await writeFile(runner, PACKAGED_NATIVE_RUNNER);
  const env = {
    PATH: [path.dirname(process.execPath), path.dirname(python), "/usr/bin", "/bin"].join(path.delimiter),
    PYTHONDONTWRITEBYTECODE: "1",
    ...(process.env.TMPDIR ? { TMPDIR: process.env.TMPDIR } : {}),
  };
  const origin = spawnSync(python, ["-c", "import pathlib,sys; sys.path.insert(0,sys.argv[1]); import ai_ppt_studio.application.image_led_results as m; p=pathlib.Path(m.__file__).resolve(); root=pathlib.Path(sys.argv[1]).resolve().parent; assert p.is_relative_to(root/'src'); script=p.parents[3]/'scripts/image-led-native.mjs'; assert script==root/'scripts/image-led-native.mjs' and script.is_file(); print('PACKAGED_PYTHON_ORIGIN_PASS')", path.join(plugin, "src")], { cwd: emptyCwd, env, encoding: "utf8", timeout: 30000 });
  assert.equal(origin.status, 0, origin.stderr || origin.error?.message);
  assert.equal(origin.stdout.trim(), "PACKAGED_PYTHON_ORIGIN_PASS");
  const run = spawnSync(process.execPath, [runner, plugin, fixture, base, modules, python], {
    cwd: emptyCwd, env, encoding: "utf8", timeout: 180000, maxBuffer: 8 * 1024 * 1024,
  });
  await writeFile(path.join(base, "packaged-native.stdout.log"), run.stdout ?? "");
  await writeFile(path.join(base, "packaged-native.stderr.log"), run.stderr ?? "");
  assert.equal(run.error, undefined, run.error?.message);
  assert.equal(run.status, 0, run.stderr || run.stdout);
  return { ...JSON.parse(await readFile(path.join(base, "packaged-native-result.json"), "utf8")), evidence_root: base };
}

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

test("release is deterministic, production-only, installable, and runtime-safe", async (t) => {
  const base = await realpath(await mkdtemp(path.join(os.tmpdir(), "ai-ppt-plugin-release-test-")));
  const output = path.join(base, "release");
  const sourceMcpTests = await tree(path.join(ROOT, "mcp/test"));
  assert.ok(sourceMcpTests.length > 0, "repository MCP tests remain available as packaging inputs");
  const plugin = await buildPluginRelease({ outputRoot: output });
  const firstManifest = await readFile(path.join(plugin, "release-manifest.json"), "utf8");
  assert.deepEqual(await tree(path.join(ROOT, "mcp/test")), sourceMcpTests, "packaging must preserve repository MCP tests");
  assert.equal(Object.keys(JSON.parse(firstManifest).files).some(name => name.startsWith("mcp/test/")), false,
    "Actual builder must exclude first-party mcp/test/ content");
  await assert.rejects(stat(path.join(plugin, "mcp/test")), { code: "ENOENT" });
  assert.ok(Object.hasOwn(JSON.parse(firstManifest).files, NATIVE_SCRIPT), "Actual builder must ship scripts/image-led-native.mjs");
  assert.ok(Object.hasOwn(JSON.parse(firstManifest).files, "scripts/image-led-fonts.mjs"), "Actual builder must ship the native renderer font dependency");
  const firstVerification = await verifyPluginRelease(plugin, { probe: false });

  assert.equal(firstVerification.ok, true);
  assert.equal(firstVerification.version, "0.4.0");
  for (const required of [
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "skills/ai-ppt-studio/SKILL.md",
    "mcp/server.mjs",
    NATIVE_SCRIPT,
    "src/ai_ppt_studio/workbench_bridge.py",
    "widget/dist/index.html",
    "node_modules/@modelcontextprotocol/sdk/package.json",
    "node_modules/call-bound/test/index.js",
  ]) {
    assert.equal((await stat(path.join(plugin, required))).isFile(), true, required);
  }
  const nativeHash = digest(await readFile(path.join(ROOT, NATIVE_SCRIPT)));
  assert.equal(digest(await readFile(path.join(plugin, NATIVE_SCRIPT))), nativeHash);
  assert.equal(JSON.parse(firstManifest).files[NATIVE_SCRIPT], nativeHash);
  assert.deepEqual(await readFile(path.join(plugin, "package-lock.json")), await readFile(path.join(ROOT, "package-lock.json")));
  for (const forbidden of ["tests", "docs", "widget/src", "requirements", ".git"])
    await assert.rejects(stat(path.join(plugin, forbidden)));
  assert.equal((await tree(plugin)).some(([, kind]) => kind === "symlink"), false);

  const rebuilt = await buildPluginRelease({ outputRoot: output });
  assert.equal(
    await readFile(path.join(rebuilt, "release-manifest.json"), "utf8"),
    firstManifest,
  );
  assert.deepEqual(await tree(path.join(ROOT, "mcp/test")), sourceMcpTests, "rebuilding must preserve repository MCP tests");
  await verifyPluginRelease(rebuilt);
  assert.equal(
    await readFile(path.join(rebuilt, "release-manifest.json"), "utf8"),
    firstManifest,
  );
  await verifyPluginRelease(rebuilt, { probe: false });

  const tampered = path.join(base, "tampered-plugin");
  await cp(rebuilt, tampered, { recursive: true });
  await writeFile(path.join(tampered, NATIVE_SCRIPT), "\n// unauthorized package edit\n", { flag: "a" });
  await assert.rejects(verifyPluginRelease(tampered), /Release manifest does not exactly match shipped files/);
  t.diagnostic(JSON.stringify(await packagedNativeRegression(rebuilt, base)));
  assert.equal(await readFile(path.join(rebuilt, "release-manifest.json"), "utf8"), firstManifest);
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

test("release verifier requires the native script even after a missing-file manifest is refreshed", async () => {
  const base = await realpath(await mkdtemp(path.join(os.tmpdir(), "ai-ppt-native-required-file-")));
  const plugin = await buildPluginRelease({ outputRoot: path.join(base, "release") });
  const incomplete = path.join(base, "incomplete-plugin");
  await cp(plugin, incomplete, { recursive: true });
  await rm(path.join(incomplete, NATIVE_SCRIPT), { force: true });
  await refreshPluginReleaseManifest(incomplete);
  // Only isolate the required-file check; normal package verification above
  // still exercises the official validator and the actual synthetic MCP probe.
  await assert.rejects(verifyPluginRelease(incomplete, { validator: false, probe: false }), /Release is missing required file: scripts\/image-led-native\.mjs/);
});

for (const injectedRelative of ["mcp/test/injected-packaging-regression.test.mjs", "mcp/test/nested/another-regression.test.mjs"]) {
  test(`release verifier rejects refreshed manifest containing ${injectedRelative}`, async () => {
    const base = await realpath(await mkdtemp(path.join(os.tmpdir(), "ai-ppt-forbidden-mcp-test-")));
    const plugin = await buildPluginRelease({ outputRoot: path.join(base, "release") });
    const tainted = path.join(base, "tainted-plugin");
    await cp(plugin, tainted, { recursive: true });
    // Remove any inherited test subtree so each injection independently proves
    // prefix rejection, including with the unfixed builder during RED.
    await rm(path.join(tainted, "mcp/test"), { recursive: true, force: true });
    const injected = path.join(tainted, injectedRelative);
    const bytes = "// Synthetic package-only rejection fixture. Never executed.\n";
    await mkdir(path.dirname(injected), { recursive: true });
    await writeFile(injected, bytes);
    await refreshPluginReleaseManifest(tainted);
    const manifest = JSON.parse(await readFile(path.join(tainted, "release-manifest.json"), "utf8"));
    assert.equal(manifest.files[injectedRelative], digest(bytes));
    await assert.rejects(verifyPluginRelease(tainted, { validator: false, probe: false }),
      /Release contains forbidden source content: mcp\/test\//);
  });
}
