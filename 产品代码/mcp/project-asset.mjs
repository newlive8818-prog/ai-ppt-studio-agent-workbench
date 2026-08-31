import { lstatSync, readFileSync, realpathSync } from "node:fs";
import path from "node:path";


const MIME_TYPES = new Map([
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".gif", "image/gif"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".md", "text/markdown; charset=utf-8"],
]);

export const MAX_PROJECT_ASSET_BYTES = 12 * 1024 * 1024;

function isInside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function readRegularJson(filePath, label) {
  const stat = lstatSync(filePath);
  if (stat.isSymbolicLink() || !stat.isFile()) {
    throw new Error(`${label} must be a regular file.`);
  }
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function validateManagedProjectRoot(root) {
  const legacyManifestPath = path.join(root, "project.json");
  try {
    const manifest = readRegularJson(legacyManifestPath, "Managed project manifest");
    if (realpathSync(path.resolve(manifest.project_root)) !== root) {
      throw new Error("Managed project manifest root does not match the selected project.");
    }
    return;
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  const state = readRegularJson(
    path.join(root, "kernel", "state.json"),
    "Schema 3 project state",
  );
  const projectsRoot = realpathSync(path.dirname(root));
  const workspaceRoot = realpathSync(path.dirname(projectsRoot));
  let workspace;
  try {
    workspace = readRegularJson(
      path.join(workspaceRoot, "workspace.json"),
      "Managed Runtime workspace manifest",
    );
  } catch (error) {
    throw new Error("Schema 3 project must belong to a managed Runtime workspace.", {
      cause: error,
    });
  }
  const declaredWorkspaceRoot = String(workspace.workspace_root || "");
  const declaredProjectsRoot = String(workspace.zones?.projects || "");
  if (
    state.schema_version !== "3.0"
    || String(state.project_id || "") !== path.basename(root)
    || workspace.workspace_type !== "ai-ppt-studio-managed-runtime"
    || !path.isAbsolute(declaredWorkspaceRoot)
    || !path.isAbsolute(declaredProjectsRoot)
    || realpathSync(declaredWorkspaceRoot) !== workspaceRoot
    || realpathSync(declaredProjectsRoot) !== projectsRoot
  ) {
    throw new Error("Schema 3 project must belong to a managed Runtime workspace.");
  }
}

function sniffExtensionlessImage(data) {
  if (
    data.length >= 8
    && data.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))
  ) return "image/png";
  if (data.length >= 3 && data[0] === 0xff && data[1] === 0xd8 && data[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    data.length >= 6
    && (data.subarray(0, 6).toString("ascii") === "GIF87a"
      || data.subarray(0, 6).toString("ascii") === "GIF89a")
  ) return "image/gif";
  if (
    data.length >= 12
    && data.subarray(0, 4).toString("ascii") === "RIFF"
    && data.subarray(8, 12).toString("ascii") === "WEBP"
  ) return "image/webp";
  return "";
}

export function readProjectAsset({ projectRoot, assetRef, maxBytes = MAX_PROJECT_ASSET_BYTES }) {
  const root = realpathSync(path.resolve(projectRoot));
  validateManagedProjectRoot(root);
  const lexical = path.resolve(root, assetRef);
  if (!isInside(lexical, root)) {
    throw new Error("Project asset must stay inside the selected project.");
  }
  const stat = lstatSync(lexical);
  if (stat.isSymbolicLink() || !stat.isFile()) {
    throw new Error("Project asset must be a regular file.");
  }
  const resolved = realpathSync(lexical);
  if (!isInside(resolved, root)) {
    throw new Error("Project asset must stay inside the selected project.");
  }
  if (stat.size > maxBytes) {
    throw new Error(`Project asset exceeds ${maxBytes} bytes.`);
  }
  const data = readFileSync(resolved);
  const extension = path.extname(resolved).toLowerCase();
  const mimeType = MIME_TYPES.get(extension) || (!extension ? sniffExtensionlessImage(data) : "");
  if (!mimeType) {
    throw new Error(`Project asset type is unsupported: ${extension || "none"}`);
  }
  return {
    assetRef: path.relative(root, resolved).split(path.sep).join("/"),
    mimeType,
    bytes: data.byteLength,
    dataBase64: data.toString("base64"),
  };
}
