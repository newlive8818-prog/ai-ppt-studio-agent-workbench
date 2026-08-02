import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { readProjectAsset } from "../mcp/project-asset.mjs";


function makeProject() {
  const root = mkdtempSync(path.join(tmpdir(), "ai-ppt-asset-"));
  writeFileSync(
    path.join(root, "project.json"),
    JSON.stringify({ project_root: root, project_id: "p1", name: "asset test" }),
  );
  mkdirSync(path.join(root, "renders"));
  writeFileSync(path.join(root, "renders", "slide-1.png"), Buffer.from("png-data"));
  writeFileSync(path.join(root, "renders", "notes.txt"), "safe text");
  return root;
}

test("project asset reader returns bounded base64 and MIME only inside project", () => {
  const projectRoot = makeProject();
  const asset = readProjectAsset({
    projectRoot,
    assetRef: "renders/slide-1.png",
  });
  assert.equal(asset.mimeType, "image/png");
  assert.equal(Buffer.from(asset.dataBase64, "base64").toString(), "png-data");
  assert.equal(asset.assetRef, "renders/slide-1.png");

  assert.throws(
    () => readProjectAsset({ projectRoot, assetRef: "../project.json" }),
    /inside the selected project/,
  );
  assert.throws(
    () => readProjectAsset({ projectRoot, assetRef: "project.json" }),
    /unsupported/i,
  );
});
