import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WIDGET_ROOT = path.join(ROOT, "widget");
const RAW_DIR = path.join(WIDGET_ROOT, "dist-raw");
const DIST_DIR = path.join(WIDGET_ROOT, "dist");

function escapeInlineScript(source) {
  return source.replaceAll("</script", "<\\/script").replaceAll("</SCRIPT", "<\\/SCRIPT");
}

await build({
  configFile: path.join(WIDGET_ROOT, "vite.config.ts"),
  logLevel: "warn",
});

let html = await readFile(path.join(RAW_DIR, "index.html"), "utf8");
const scriptMatch = html.match(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*><\/script>/i);
const styleMatch = html.match(/<link\b[^>]*\brel=["']stylesheet["'][^>]*\bhref=["']([^"']+)["'][^>]*>/i)
  || html.match(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*\brel=["']stylesheet["'][^>]*>/i);

if (!scriptMatch) throw new Error("Vite output did not contain a Widget entry script.");
const scriptPath = path.join(RAW_DIR, scriptMatch[1].replace(/^\//, ""));
const js = escapeInlineScript(await readFile(scriptPath, "utf8"));
html = html.replace(scriptMatch[0], "");

if (styleMatch) {
  const stylePath = path.join(RAW_DIR, styleMatch[1].replace(/^\//, ""));
  const css = await readFile(stylePath, "utf8");
  html = html.replace(styleMatch[0], () => `<style>${css}</style>`);
}

html = html.replace(/<\/body>/i, () => `<script>${js}</script></body>`);

await rm(DIST_DIR, { recursive: true, force: true });
await mkdir(DIST_DIR, { recursive: true });
await writeFile(path.join(DIST_DIR, "index.html"), html, "utf8");
await rm(RAW_DIR, { recursive: true, force: true });

process.stdout.write(`${path.join(DIST_DIR, "index.html")}\n`);
