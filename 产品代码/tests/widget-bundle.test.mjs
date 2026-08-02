import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("built Widget is one self-contained MCP App HTML resource", async () => {
  const html = await readFile(path.join(root, "widget", "dist", "index.html"), "utf8");
  const shell = html.replace(/(<script\b[^>]*>)[\s\S]*?<\/script>/gi, "$1</script>");
  assert.match(html, /<div id="root"><\/div>/);
  assert.match(html, /AI PPT Studio/);
  assert.doesNotMatch(shell, /<script\b[^>]+\bsrc=/i);
  assert.doesNotMatch(shell, /<link\b[^>]+\brel=["']stylesheet/i);
  assert.doesNotMatch(shell, /<script\b[^>]*\btype=["']module/i);
  assert.doesNotMatch(shell, /(?:src|href)=["']https?:\/\//i);
  assert.doesNotMatch(shell, /url\(["']?https?:\/\//i);
  assert.match(html, /<style>[\s\S]+<\/style>/);
  assert.match(html, /<script\b[^>]*>[\s\S]+<\/script>/);
  const inlineScript = html.match(/<script\b[^>]*>([\s\S]*?)<\/script>/i)?.[1];
  assert.ok(inlineScript, "Widget must contain one executable inline script.");
  assert.doesNotThrow(
    () => new Function(inlineScript),
    "Widget inline script must execute as a classic script without ESM syntax.",
  );
});
