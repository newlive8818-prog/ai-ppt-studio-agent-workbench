import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
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

function pythonModuleRoot() {
  const sourceRoot = path.join(PLUGIN_ROOT, "src");
  const installedRuntime = path.join(PLUGIN_ROOT, "runtime");
  return process.env.AI_PPT_PYTHONPATH || (existsSync(sourceRoot) ? sourceRoot : installedRuntime);
}

export function invokePythonBridge(request, options = {}) {
  const pythonExecutable = options.pythonExecutable || process.env.AI_PPT_PYTHON || "python3";
  const bridgeArgs = options.bridgeArgs || ["-m", "ai_ppt_studio.workbench_bridge"];
  const moduleRoot = options.pythonPath || pythonModuleRoot();
  const existingPythonPath = process.env.PYTHONPATH || "";
  const pythonPath = [moduleRoot, existingPythonPath].filter(Boolean).join(path.delimiter);
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable, bridgeArgs, {
      cwd: PLUGIN_ROOT,
      env: { ...process.env, PYTHONPATH: pythonPath },
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
