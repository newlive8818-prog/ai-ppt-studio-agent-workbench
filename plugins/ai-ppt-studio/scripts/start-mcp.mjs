import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sdk = path.join(root, "node_modules", "@modelcontextprotocol", "sdk");
if (!existsSync(sdk)) {
  throw new Error("AI PPT Studio dependencies are not installed. Run npm install in the plugin directory.");
}
process.chdir(root);
const module = await import(pathToFileURL(path.join(root, "mcp", "server.mjs")).href);
await module.startServer();
