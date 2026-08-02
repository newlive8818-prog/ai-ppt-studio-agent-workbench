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

export function readProjectAsset({ projectRoot, assetRef, maxBytes = MAX_PROJECT_ASSET_BYTES }) {
  const root = realpathSync(path.resolve(projectRoot));
  const manifestPath = path.join(root, "project.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (realpathSync(path.resolve(manifest.project_root)) !== root) {
    throw new Error("Managed project manifest root does not match the selected project.");
  }
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
  const extension = path.extname(resolved).toLowerCase();
  const mimeType = MIME_TYPES.get(extension);
  if (!mimeType) {
    throw new Error(`Project asset type is unsupported: ${extension || "none"}`);
  }
  if (stat.size > maxBytes) {
    throw new Error(`Project asset exceeds ${maxBytes} bytes.`);
  }
  const data = readFileSync(resolved);
  return {
    assetRef: path.relative(root, resolved).split(path.sep).join("/"),
    mimeType,
    bytes: data.byteLength,
    dataBase64: data.toString("base64"),
  };
}
