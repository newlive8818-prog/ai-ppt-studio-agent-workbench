import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    encoding: "utf8",
    ...options,
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim();
}

test("creates an isolated content full-deck preview from the current formal fixture", async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-content-preview-test-"));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));

  const seed = JSON.parse(run("python3", ["scripts/seed-v16-ui-project.py", temporaryRoot]));
  const outputDirectory = path.join(temporaryRoot, "preview");
  const outputPath = run(
    process.execPath,
    ["scripts/create-widget-preview.mjs", seed.project_root, seed.workspace_config],
    { env: { ...process.env, AI_PPT_PREVIEW_OUTPUT_DIR: outputDirectory } },
  );

  assert.equal((await stat(outputPath)).isFile(), true);
  const html = await readFile(outputPath, "utf8");
  assert.match(html, /"surface":"content-full-deck"/);
  assert.match(html, /__AI_PPT_CONTENT_REVIEW_PROJECT_ROOT__/);
  assert.match(html, /content-review-real-case/);
  assert.match(html, /"asset_ref":"review-assets\/content-evidence-page\.jpg"/);
  assert.match(html, /__AI_PPT_PREVIEW_ASSETS__=\{"review-assets\/content-evidence-page\.jpg":/);
});

test("creates long-deck and error-state preview scenarios from the current formal fixture", async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-content-preview-scenarios-"));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));

  const seed = JSON.parse(run("python3", ["scripts/seed-v16-ui-project.py", temporaryRoot]));
  const outputDirectory = path.join(temporaryRoot, "preview");
  run(
    process.execPath,
    ["scripts/create-widget-preview.mjs", seed.project_root, seed.workspace_config],
    {
      env: {
        ...process.env,
        AI_PPT_CONTENT_REVIEW_PREVIEWS: "1",
        AI_PPT_PREVIEW_OUTPUT_DIR: outputDirectory,
      },
    },
  );

  for (const name of [
    "content-review-long-60.html",
    "content-review-save-failure.html",
    "content-review-source-conflict.html",
  ]) {
    assert.equal((await stat(path.join(outputDirectory, name))).isFile(), true, name);
  }
  const longDeck = await readFile(path.join(outputDirectory, "content-review-long-60.html"), "utf8");
  assert.match(longDeck, /S60/);
  assert.match(longDeck, /visible_copy_blocks/);
});
