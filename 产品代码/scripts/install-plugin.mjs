import { randomUUID } from "node:crypto";
import { cp, mkdir, rename, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { verifyPluginRelease } from "./verify-plugin-release.mjs";

function assertTarget(targetRoot) {
  const target = path.resolve(targetRoot);
  if (path.basename(target) !== "ai-ppt-studio")
    throw new Error(`Plugin target must end in ai-ppt-studio: ${target}`);
  if (target === path.parse(target).root || target === os.homedir())
    throw new Error(`Plugin target is too broad: ${target}`);
  return target;
}

export async function installPluginRelease({ releaseRoot, targetRoot }) {
  if (!releaseRoot || !targetRoot) throw new Error("releaseRoot and targetRoot are required");
  const source = path.resolve(releaseRoot);
  const target = assertTarget(targetRoot);
  await verifyPluginRelease(source, { probe: false });
  const parent = path.dirname(target);
  const token = randomUUID();
  const staging = path.join(parent, `.ai-ppt-studio-stage-${token}`);
  const backup = path.join(parent, `.ai-ppt-studio-backup-${token}`);
  await mkdir(parent, { recursive: true });
  let backedUp = false;
  try {
    await cp(source, staging, { recursive: true, errorOnExist: true, force: false });
    await verifyPluginRelease(staging, { probe: false });
    try {
      await rename(target, backup);
      backedUp = true;
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
    await rename(staging, target);
    if (backedUp) await rm(backup, { recursive: true, force: true });
    return { ok: true, installRoot: target };
  } catch (error) {
    if (backedUp) {
      try {
        await stat(target);
      } catch {
        await rename(backup, target);
      }
    }
    throw error;
  } finally {
    await rm(staging, { recursive: true, force: true });
    if (backedUp) await rm(backup, { recursive: true, force: true });
  }
}

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const releaseRoot = argument("--release");
  const targetRoot = argument("--target") || path.join(os.homedir(), "plugins", "ai-ppt-studio");
  const result = await installPluginRelease({ releaseRoot, targetRoot });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}
