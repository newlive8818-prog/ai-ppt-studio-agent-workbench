import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parse } from "@babel/parser";

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

test("server delegates registration to the five bounded tool groups", () => {
  const serverSource = readFileSync(new URL("../mcp/server.mjs", import.meta.url), "utf8");
  const groups = [
    ["project", "registerProjectTools"],
    ["content", "registerContentTools"],
    ["review", "registerReviewTools"],
    ["visual", "registerVisualTools"],
    ["delivery-experience", "registerDeliveryExperienceTools"],
  ];
  for (const [file, register] of groups) {
    const moduleSource = readFileSync(
      new URL(`../mcp/tools/${file}-tools.mjs`, import.meta.url),
      "utf8",
    );
    assert.match(moduleSource, new RegExp(`export function ${register}\\(`));
    assert.match(serverSource, new RegExp(`${register}\\(toolContext\\)`));
  }
  assert.doesNotMatch(serverSource, /server\.registerTool\s*\(/);
});

test("tool results use the single two-argument textResult contract", () => {
  const files = [
    "project", "content", "review", "visual", "delivery-experience",
  ].map((group) => new URL(`../mcp/tools/${group}-tools.mjs`, import.meta.url));
  const violations = [];
  function visit(node, file) {
    if (!node || typeof node !== "object") return;
    if (
      node.type === "CallExpression" &&
      node.callee?.type === "Identifier" &&
      node.callee.name === "textResult" &&
      node.arguments.length !== 2
    ) {
      violations.push(`${file}:${node.loc.start.line}:${node.arguments.length}`);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach((item) => visit(item, file));
      else visit(value, file);
    }
  }
  for (const file of files) {
    const source = readFileSync(file, "utf8");
    visit(parse(source, { sourceType: "module" }), file.pathname.split("/").at(-1));
  }
  assert.deepEqual(violations, []);
});
