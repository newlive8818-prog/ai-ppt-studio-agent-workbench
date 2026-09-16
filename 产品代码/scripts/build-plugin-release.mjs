import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  cp,
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SOURCE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PLUGIN_NAME = "ai-ppt-studio";
const ALLOWLIST = [
  [".codex-plugin", ".codex-plugin"],
  [".mcp.json", ".mcp.json"],
  ["assets", "assets"],
  ["skills", "skills"],
  ["mcp", "mcp"],
  ["src/ai_ppt_studio", "src/ai_ppt_studio"],
  ["package.json", "package.json"],
  ["package-lock.json", "package-lock.json"],
  ["scripts/start-mcp.mjs", "scripts/start-mcp.mjs"],
  ["scripts/probe-mcp.mjs", "scripts/probe-mcp.mjs"],
  ["scripts/image-led-native.mjs", "scripts/image-led-native.mjs"],
  ["scripts/image-led-fonts.mjs", "scripts/image-led-fonts.mjs"],
  ["widget/dist/index.html", "widget/dist/index.html"],
];

function within(child, parent) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function assertSafeOutput(outputRoot, runtimeRoot) {
  const output = path.resolve(outputRoot);
  const source = path.resolve(SOURCE_ROOT);
  const runtime = path.resolve(runtimeRoot || path.join(os.homedir(), "Documents", "AI-PPT-Workspace"));
  if (output === path.parse(output).root || output === os.homedir())
    throw new Error(`Release output is too broad: ${output}`);
  for (const protectedRoot of [source, runtime]) {
    if (within(output, protectedRoot) || within(protectedRoot, output))
      throw new Error(`Release output intersects a protected root: ${protectedRoot}`);
  }
  return output;
}

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

async function copyAllowlist(staging) {
  for (const [sourceRelative, targetRelative] of ALLOWLIST) {
    const source = path.join(SOURCE_ROOT, sourceRelative);
    const target = path.join(staging, targetRelative);
    await mkdir(path.dirname(target), { recursive: true });
    await cp(source, target, {
      recursive: true,
      filter: (candidate) => {
        const relative = path.relative(SOURCE_ROOT, candidate).split(path.sep).join("/");
        if (relative === "mcp/test" || relative.startsWith("mcp/test/")) return false;
        const name = path.basename(candidate);
        return name !== "__pycache__" && !name.endsWith(".pyc") && name !== ".DS_Store";
      },
    });
  }
}

async function files(root) {
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

async function writeManifest(staging) {
  const manifestPath = path.join(staging, "release-manifest.json");
  const hashes = {};
  for (const absolute of await files(staging)) {
    if (absolute === manifestPath) continue;
    const relative = path.relative(staging, absolute).split(path.sep).join("/");
    hashes[relative] = createHash("sha256").update(await readFile(absolute)).digest("hex");
  }
  const plugin = JSON.parse(await readFile(path.join(staging, ".codex-plugin", "plugin.json"), "utf8"));
  const payload = {
    schema_version: "1.0",
    plugin_name: plugin.name,
    plugin_version: plugin.version,
    hash_algorithm: "sha256",
    files: hashes,
  };
  await writeFile(manifestPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

export async function refreshPluginReleaseManifest(pluginRoot) {
  const root = path.resolve(pluginRoot);
  await rm(path.join(root, "release-manifest.json"), { force: true });
  await writeManifest(root);
  return path.join(root, "release-manifest.json");
}

export async function buildPluginRelease({ outputRoot, runtimeRoot } = {}) {
  if (!outputRoot) throw new Error("outputRoot is required");
  const output = assertSafeOutput(outputRoot, runtimeRoot);
  const target = path.join(output, PLUGIN_NAME);
  const token = randomUUID();
  const staging = path.join(output, `.${PLUGIN_NAME}-stage-${token}`);
  const backup = path.join(output, `.${PLUGIN_NAME}-backup-${token}`);
  await mkdir(output, { recursive: true });
  await run("npm", ["run", "build", "--silent"], SOURCE_ROOT);
  let backedUp = false;
  try {
    await mkdir(staging, { recursive: true });
    await copyAllowlist(staging);
    await run("npm", ["ci", "--omit=dev", "--ignore-scripts"], staging);
    await rm(path.join(staging, "node_modules", ".bin"), {
      recursive: true,
      force: true,
    });
    await writeManifest(staging);
    try {
      await rename(target, backup);
      backedUp = true;
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
    await rename(staging, target);
    if (backedUp) await rm(backup, { recursive: true, force: true });
    return target;
  } catch (error) {
    if (backedUp) {
      try {
        await stat(target);
      } catch {
        await rename(backup, target);
      }
    }
    throw error;
  } finally {
    await rm(staging, { recursive: true, force: true });
    if (backedUp) await rm(backup, { recursive: true, force: true });
  }
}

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const refresh = argument("--refresh-release");
  if (refresh) {
    const manifestPath = await refreshPluginReleaseManifest(refresh);
    process.stdout.write(`${JSON.stringify({ ok: true, manifestPath })}\n`);
  } else {
    const plugin = await buildPluginRelease({
      outputRoot: argument("--output"),
      runtimeRoot: argument("--runtime-root"),
    });
    process.stdout.write(`${JSON.stringify({ ok: true, pluginRoot: plugin })}\n`);
  }
}
