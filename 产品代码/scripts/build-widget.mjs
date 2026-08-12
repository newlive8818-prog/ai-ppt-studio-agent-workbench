import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WIDGET_ROOT = path.join(ROOT, "widget");
const DIST_DIR = path.join(WIDGET_ROOT, "dist");

function escapeInlineScript(source) {
  return source.replaceAll("</script", "<\\/script").replaceAll("</SCRIPT", "<\\/SCRIPT");
}

const rawDir = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-widget-build-"));
const finalHtml = path.join(DIST_DIR, "index.html");
const stagedHtml = path.join(DIST_DIR, `.index.html.stage-${process.pid}`);
try {
  await build({
    configFile: path.join(WIDGET_ROOT, "vite.config.ts"),
    logLevel: "warn",
    build: { outDir: rawDir, emptyOutDir: true },
  });

  let html = await readFile(path.join(rawDir, "index.html"), "utf8");
  const scriptMatch = html.match(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*><\/script>/i);
  const styleMatch = html.match(/<link\b[^>]*\brel=["']stylesheet["'][^>]*\bhref=["']([^"']+)["'][^>]*>/i)
    || html.match(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*\brel=["']stylesheet["'][^>]*>/i);

  if (!scriptMatch) throw new Error("Vite output did not contain a surface entry script.");
  const scriptPath = path.join(rawDir, scriptMatch[1].replace(/^\//, ""));
  const js = escapeInlineScript(await readFile(scriptPath, "utf8"));
  html = html.replace(scriptMatch[0], "");

  if (styleMatch) {
    const stylePath = path.join(rawDir, styleMatch[1].replace(/^\//, ""));
    const css = await readFile(stylePath, "utf8");
    html = html.replace(styleMatch[0], () => `<style>${css}</style>`);
  }

  html = html.replace(/<\/body>/i, () => `<script>${js}</script></body>`);
  await mkdir(DIST_DIR, { recursive: true });
  await writeFile(stagedHtml, html, "utf8");
  await rename(stagedHtml, finalHtml);
} finally {
  await rm(rawDir, { recursive: true, force: true });
  await rm(stagedHtml, { force: true });
}

process.stdout.write(`${finalHtml}\n`);
