import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { PUBLIC_TOOL_CATALOG } from "../mcp/tool-catalog.mjs";

const implementedReviewSessionTools = [
  "get_ai_ppt_project_status",
  "open_or_resume_review_session",
  "record_review_host_open_receipt",
  "record_review_host_notification_receipt",
  "record_review_ai_receipt",
];

test("public MCP tool catalog is the single unique registration source", () => {
  const names = PUBLIC_TOOL_CATALOG.map((tool) => tool.name);
  assert.equal(new Set(names).size, names.length);
  assert.ok(names.length > 0);
  for (const tool of PUBLIC_TOOL_CATALOG) {
    assert.match(tool.name, /^[a-z][a-z0-9_]*$/);
    assert.match(tool.group, /^(project|content|review|visual|delivery-experience)$/);
    assert.match(tool.schema, /^[A-Za-z][A-Za-z0-9]*$/);
    assert.match(tool.handler, /^[A-Za-z][A-Za-z0-9]*$/);
  }
  for (const name of implementedReviewSessionTools) {
    assert.ok(names.includes(name), `${name} must be published from the catalog`);
  }
});

test("server and production probe import the public catalog", () => {
  const serverSource = readFileSync(new URL("../mcp/server.mjs", import.meta.url), "utf8");
  const probeSource = readFileSync(new URL("../scripts/probe-mcp.mjs", import.meta.url), "utf8");
  assert.match(serverSource, /import\s*\{\s*PUBLIC_TOOL_CATALOG\s*\}\s*from\s*"\.\/tool-catalog\.mjs"/);
  assert.match(probeSource, /import\s*\{\s*PUBLIC_TOOL_CATALOG\s*\}\s*from\s*"\.\.\/mcp\/tool-catalog\.mjs"/);
  assert.doesNotMatch(probeSource, /const\s+requiredTools\s*=/);
});
