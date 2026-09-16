import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("plugin package declares one authoritative skill and an MCP server", () => {
  const manifestPath = path.join(root, ".codex-plugin", "plugin.json");
  const mcpPath = path.join(root, ".mcp.json");
  assert.equal(existsSync(manifestPath), true);
  assert.equal(existsSync(mcpPath), true);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.name, "ai-ppt-studio");
  assert.equal(manifest.version, "0.4.0");
  assert.match(manifest.version, /^\d+\.\d+\.\d+$/);
  assert.equal(manifest.skills, "./skills/");
  assert.equal(manifest.mcpServers, "./.mcp.json");
  assert.equal(manifest.keywords.includes("native-widget"), false);
  assert.deepEqual(manifest.interface.capabilities.slice(0, 2), [
    "Real Codex sidebar workbench",
    "Codex built-in Browser review",
  ]);
  assert.equal(
    JSON.stringify(manifest.interface).includes("原生工作台"),
    false,
  );
  assert.equal(existsSync(path.join(root, "skills", "ai-ppt-studio", "SKILL.md")), true);
  assert.equal(existsSync(path.join(root, "skill", "ai-ppt-studio")), false);
  assert.equal(existsSync(path.join(root, "scripts", "start-mcp.mjs")), true);
  assert.equal(existsSync(path.join(root, "assets", "app-icon.svg")), true);
});

test("MCP config starts the local stdio server from the plugin root", () => {
  const config = JSON.parse(readFileSync(path.join(root, ".mcp.json"), "utf8"));
  const server = config.mcpServers.ai_ppt_studio;
  assert.equal(server.command, "node");
  assert.deepEqual(server.args, ["./scripts/start-mcp.mjs"]);
  assert.equal(server.cwd, ".");
  assert.deepEqual(server.env_vars, [
    "AI_PPT_PYTHON",
    "AI_PPT_PYTHONPATH",
    "AI_PPT_IMAGE2_ADAPTER_COMMAND",
    "AI_PPT_IMAGE2_RECEIVER",
    "AI_PPT_IMAGE2_MODEL",
    "AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST",
  ]);
});
