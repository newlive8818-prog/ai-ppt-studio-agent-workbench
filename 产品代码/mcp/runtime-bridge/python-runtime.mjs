import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

export class PythonBridgeError extends Error {
  constructor(payload, exitCode) {
    super(payload?.error?.message || `AI PPT Python bridge failed with exit ${exitCode}`);
    this.name = "PythonBridgeError";
    this.code = payload?.error?.code || "INTERNAL_ERROR";
    this.details = payload?.error?.details || {};
    this.exitCode = exitCode;
  }
}

function pythonModuleRoot(env = process.env) {
  const sourceRoot = path.join(PLUGIN_ROOT, "src");
  const installedRuntime = path.join(PLUGIN_ROOT, "runtime");
  return env.AI_PPT_PYTHONPATH || (existsSync(sourceRoot) ? sourceRoot : installedRuntime);
}

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
  const workspaceBundledPython = path.join(
    env.HOME || os.homedir(),
    ".cache",
    "codex-runtimes",
    "codex-primary-runtime",
    "dependencies",
    "python",
    "bin",
    "python3",
  );
  return [
    resolveBundledPythonExecutable(nodeExecutable, platform),
    workspaceBundledPython,
    "/usr/local/bin/python3",
    "/opt/homebrew/bin/python3",
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
    "/usr/bin/python3",
  ].filter(Boolean);
}

export function resolvePythonExecutable(options = {}) {
  return resolvePythonExecutables(options)[0];
}

function resolvePythonExecutables(options = {}) {
  if (options.pythonExecutable) return [options.pythonExecutable];
  const env = options.env || process.env;
  if (env.AI_PPT_PYTHON) return [env.AI_PPT_PYTHON];
  const candidates = options.pythonCandidates || defaultPythonCandidates(
    env,
    options.platform,
    options.nodeExecutable || process.execPath,
  );
  const resolved = [...new Set(candidates)].filter(
    (candidate) => path.isAbsolute(candidate) && existsSync(candidate),
  );
  return resolved.length > 0
    ? resolved
    : [options.platform === "win32" || process.platform === "win32" ? "py" : "python3"];
}

function invokeWithPython(pythonExecutable, request, options, hostEnv) {
  const bridgeArgs = options.bridgeArgs || ["-m", "ai_ppt_studio.workbench_bridge"];
  const moduleRoot = options.pythonPath || pythonModuleRoot(hostEnv);
  const existingPythonPath = hostEnv.PYTHONPATH || "";
  const pythonPath = [moduleRoot, existingPythonPath].filter(Boolean).join(path.delimiter);
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable, bridgeArgs, {
      cwd: PLUGIN_ROOT,
      env: {
        ...hostEnv,
        PYTHONPATH: pythonPath,
        PYTHONDONTWRITEBYTECODE: "1",
      },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (exitCode) => {
      let payload;
      try {
        payload = JSON.parse(stdout);
      } catch (_error) {
        reject(new PythonBridgeError({ error: { code: "INTERNAL_ERROR", message: stderr || "Bridge returned invalid JSON", details: {} } }, exitCode));
        return;
      }
      if (exitCode !== 0 || payload.ok === false) {
        reject(new PythonBridgeError(payload, exitCode));
        return;
      }
      resolve(payload);
    });
    child.stdin.end(JSON.stringify(request));
  });
}

export async function invokePythonBridge(request, options = {}) {
  const hostEnv = options.env || process.env;
  const pythonExecutables = resolvePythonExecutables({ ...options, env: hostEnv });
  for (let index = 0; index < pythonExecutables.length; index += 1) {
    try {
      return await invokeWithPython(pythonExecutables[index], request, options, hostEnv);
    } catch (error) {
      const canRetry = error?.code === "ENOENT" && index < pythonExecutables.length - 1;
      if (!canRetry) throw error;
    }
  }
  throw new Error("No Python interpreter candidate could be started");
}
