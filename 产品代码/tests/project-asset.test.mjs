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

function makeSchema3Project() {
  const workspaceRoot = mkdtempSync(path.join(tmpdir(), "ai-ppt-schema3-workspace-"));
  const projectsRoot = path.join(workspaceRoot, "projects");
  const projectRoot = path.join(projectsRoot, "p-schema3");
  mkdirSync(path.join(projectRoot, "kernel"), { recursive: true });
  mkdirSync(path.join(projectRoot, "materials", "files"), { recursive: true });
  writeFileSync(
    path.join(workspaceRoot, "workspace.json"),
    JSON.stringify({
      schema_version: "1.0",
      workspace_type: "ai-ppt-studio-managed-runtime",
      workspace_root: workspaceRoot,
      zones: { projects: projectsRoot },
    }),
  );
  writeFileSync(
    path.join(projectRoot, "kernel", "state.json"),
    JSON.stringify({ schema_version: "3.0", project_id: "p-schema3", revision: 1 }),
  );
  const png = Buffer.from("89504e470d0a1a0a0000000d49484452", "hex");
  writeFileSync(path.join(projectRoot, "materials", "files", "abcdef-png"), png);
  return { projectRoot, png };
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

test("project asset reader accepts a managed schema 3 project and sniffs an extensionless PNG", () => {
  const { projectRoot, png } = makeSchema3Project();

  const asset = readProjectAsset({
    projectRoot,
    assetRef: "materials/files/abcdef-png",
  });

  assert.equal(asset.assetRef, "materials/files/abcdef-png");
  assert.equal(asset.mimeType, "image/png");
  assert.deepEqual(Buffer.from(asset.dataBase64, "base64"), png);
});

test("project asset reader rejects a schema 3-shaped directory outside a managed Runtime workspace", () => {
  const projectRoot = mkdtempSync(path.join(tmpdir(), "ai-ppt-unmanaged-schema3-"));
  mkdirSync(path.join(projectRoot, "kernel"));
  writeFileSync(
    path.join(projectRoot, "kernel", "state.json"),
    JSON.stringify({
      schema_version: "3.0",
      project_id: path.basename(projectRoot),
      revision: 1,
    }),
  );
  writeFileSync(path.join(projectRoot, "asset.png"), Buffer.from("png-data"));

  assert.throws(
    () => readProjectAsset({ projectRoot, assetRef: "asset.png" }),
    /managed Runtime workspace/i,
  );
});
