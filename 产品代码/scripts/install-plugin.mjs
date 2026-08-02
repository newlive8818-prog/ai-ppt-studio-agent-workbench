import { spawn } from "node:child_process";
import { cp, mkdir, rename, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const installParent = path.join(os.homedir(), "plugins");
const targetRoot = path.join(installParent, "ai-ppt-studio");
const stagingRoot = path.join(installParent, `.ai-ppt-studio-install-${process.pid}`);
const backupRoot = path.join(installParent, `.ai-ppt-studio-backup-${Date.now()}`);
const validator = path.join(
  os.homedir(),
  ".codex",
  "skills",
  ".system",
  "plugin-creator",
  "scripts",
  "validate_plugin.py",
);

if (
  path.dirname(targetRoot) !== installParent ||
  path.basename(targetRoot) !== "ai-ppt-studio"
) {
  throw new Error(`Refusing unexpected plugin target: ${targetRoot}`);
}

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, stdio: "inherit" });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} exited with ${code}`));
    });
  });
}

const entries = [
  ".codex-plugin",
  ".mcp.json",
  "assets",
  "skills",
  "mcp",
  "src",
  "package.json",
  "package-lock.json",
];

await run("npm", ["run", "build"], sourceRoot);
await mkdir(installParent, { recursive: true });
await rm(stagingRoot, { recursive: true, force: true });
await mkdir(stagingRoot, { recursive: true });

for (const entry of entries) {
  await cp(path.join(sourceRoot, entry), path.join(stagingRoot, entry), {
    recursive: true,
  });
}
await mkdir(path.join(stagingRoot, "scripts"), { recursive: true });
for (const script of ["start-mcp.mjs", "probe-mcp.mjs"]) {
  await cp(
    path.join(sourceRoot, "scripts", script),
    path.join(stagingRoot, "scripts", script),
  );
}
await mkdir(path.join(stagingRoot, "widget", "dist"), { recursive: true });
await cp(
  path.join(sourceRoot, "widget", "dist", "index.html"),
  path.join(stagingRoot, "widget", "dist", "index.html"),
);

await run("npm", ["ci", "--omit=dev", "--ignore-scripts"], stagingRoot);
await run("python3", [validator, stagingRoot], sourceRoot);

let hadPreviousInstall = false;
try {
  await rename(targetRoot, backupRoot);
  hadPreviousInstall = true;
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}

try {
  await rename(stagingRoot, targetRoot);
} catch (error) {
  if (hadPreviousInstall) await rename(backupRoot, targetRoot);
  throw error;
}

if (hadPreviousInstall) {
  await rm(backupRoot, { recursive: true, force: true });
}

process.stdout.write(`${JSON.stringify({ ok: true, installRoot: targetRoot })}\n`);
