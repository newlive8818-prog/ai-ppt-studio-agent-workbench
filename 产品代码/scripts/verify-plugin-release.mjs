import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdtemp,
  mkdir,
  readdir,
  readFile,
  stat,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

function run(command, args, cwd, env = process.env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${command} ${args.join(" ")} failed (${code}): ${stderr || stdout}`));
    });
  });
}

async function releaseFiles(root) {
  const result = [];
  async function visit(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const absolute = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Release contains a symlink: ${absolute}`);
      if (entry.isDirectory()) await visit(absolute);
      else if (entry.isFile()) result.push(absolute);
    }
  }
  await visit(root);
  return result;
}

export function pluginValidatorCandidates() {
  const configured = process.env.AI_PPT_PLUGIN_VALIDATOR;
  const codexHome = process.env.CODEX_HOME;
  return [
    configured,
    codexHome && path.join(codexHome, "skills", ".system", "plugin-creator", "scripts", "validate_plugin.py"),
    path.join(os.homedir(), "Library", "Application Support", "Codex API Client", "codex-home", "skills", ".system", "plugin-creator", "scripts", "validate_plugin.py"),
    path.join(os.homedir(), ".codex", "skills", ".system", "plugin-creator", "scripts", "validate_plugin.py"),
  ].filter(Boolean);
}

async function findValidator() {
  for (const candidate of pluginValidatorCandidates()) {
    try {
      if ((await stat(candidate)).isFile()) return candidate;
    } catch {}
  }
  throw new Error("Official plugin validator was not found; set AI_PPT_PLUGIN_VALIDATOR");
}

async function probeRelease(root) {
  const base = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-release-probe-"));
  const runtime = path.join(base, "runtime");
  const source = path.join(base, "source");
  const install = path.join(base, "install");
  const upstream = path.join(base, "web");
  await Promise.all([runtime, source, install, upstream].map((item) => mkdir(item, { recursive: true })));
  const cli = await run(
    "python3",
    [
      "-m", "ai_ppt_studio",
      "--runtime-root", runtime,
      "--source-repo-root", source,
      "--install-root", install,
      "--upstream-root", upstream,
      "init", "--name", "Release probe", "--project-id", "release-probe",
    ],
    upstream,
    {
      ...process.env,
      PYTHONPATH: path.join(root, "src"),
      PYTHONDONTWRITEBYTECODE: "1",
    },
  );
  const created = JSON.parse(cli.stdout);
  const profile = path.join(runtime, "workspace.json");
  await writeFile(
    profile,
    `${JSON.stringify({
      schema_version: "1.0",
      runtime_root: runtime,
      source_repo_root: source,
      install_root: install,
      upstream_root: upstream,
      protected_roots: [source, install, upstream],
    }, null, 2)}\n`,
    "utf8",
  );
  const result = await run(
    "node",
    ["scripts/probe-mcp.mjs"],
    root,
    {
      ...process.env,
      PYTHONPATH: "",
      AI_PPT_WORKSPACE_CONFIG: profile,
      AI_PPT_PROBE_PROJECT: created.project.project_root,
    },
  );
  return JSON.parse(result.stdout);
}

export async function verifyPluginRelease(pluginRoot, options = {}) {
  const root = path.resolve(pluginRoot);
  const manifestPath = path.join(root, "release-manifest.json");
  const release = JSON.parse(await readFile(manifestPath, "utf8"));
  const actual = {};
  for (const absolute of await releaseFiles(root)) {
    if (absolute === manifestPath) continue;
    const relative = path.relative(root, absolute).split(path.sep).join("/");
    actual[relative] = createHash("sha256").update(await readFile(absolute)).digest("hex");
  }
  if (JSON.stringify(actual) !== JSON.stringify(release.files))
    throw new Error("Release manifest does not exactly match shipped files");
  for (const required of [
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "skills/ai-ppt-studio/SKILL.md",
    "mcp/server.mjs",
    "scripts/image-led-native.mjs",
    "scripts/image-led-fonts.mjs",
    "src/ai_ppt_studio/workbench_bridge.py",
    "widget/dist/index.html",
  ]) {
    if (!actual[required]) throw new Error(`Release is missing required file: ${required}`);
  }
  for (const forbidden of ["tests/", "mcp/test/", "docs/", "widget/src/", "requirements/", ".git/"])
    if (Object.keys(actual).some((item) => item.startsWith(forbidden)))
      throw new Error(`Release contains forbidden source content: ${forbidden}`);
  if (options.validator !== false) {
    const validator = await findValidator();
    await run("python3", [validator, root], root);
  }
  const plugin = JSON.parse(await readFile(path.join(root, ".codex-plugin", "plugin.json"), "utf8"));
  const probe = options.probe === false ? null : await probeRelease(root);
  return {
    ok: true,
    pluginRoot: root,
    name: plugin.name,
    version: plugin.version,
    fileCount: Object.keys(actual).length,
    releaseManifestSha256: createHash("sha256").update(await readFile(manifestPath)).digest("hex"),
    probe,
  };
}

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const release = argument("--release");
  if (!release) throw new Error("--release is required");
  const result = await verifyPluginRelease(release);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}
