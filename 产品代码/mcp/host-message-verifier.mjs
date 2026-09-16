import { createReadStream } from "node:fs";
import { lstat, readdir, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";

const UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const REF = new RegExp("^chat://message/(" + UUID + ")/(msg_" + UUID + ")$");
const ACCEPTANCE = /^(?:接受(?:达到要求)?|达到要求|确认(?:当前)?视觉(?:合同|方案)(?:和G3)?|确认(?:当前)?G3|认可当前视觉合同|通过视觉验收)[。.!！]?$/iu;
const WITHDRAWAL = /^(?:不接受|撤回|取消|拒绝).{0,20}(?:视觉|G3|验收|确认)|^不接受[。.!！]?$/u;
const snapshotTool = (p) => p.name === "mcp__ai_ppt_studio__get_ai_ppt_project_snapshot"
  || p.name === "mcp__ai_ppt_studio.get_ai_ppt_project_snapshot"
  || (p.name === "get_ai_ppt_project_snapshot" && p.namespace === "mcp__ai_ppt_studio");

function defaultSessionsRoot() {
  return path.join(process.env.CODEX_HOME || path.join(os.homedir(),
    "Library", "Application Support", "Codex API Client", "codex-home"), "sessions");
}

function textOf(message) {
  const expected = message.role === "user" ? "input_text" : "output_text";
  if (!Array.isArray(message.content) || message.content.some(x => x.type !== expected || typeof x.text !== "string")) return "";
  return message.content.map(x => x.text).join("\n");
}

// Decode only known MCP result envelopes, never arbitrary text containing JSON.
function snapshotOf(output) {
  if (typeof output === "string") {
    const prefix = output.match(/^(?:Wall time: [^\n]+\n)?Output:\n/);
    return snapshotOf(JSON.parse(prefix ? output.slice(prefix[0].length) : output));
  }
  return output?.structuredContent?.snapshot || output?.snapshot || null;
}

async function findTranscript(root, threadId) {
  const matches = [];
  async function visit(dir, depth) {
    if (depth > 4) return;
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) continue;
      const filename = path.join(dir, entry.name);
      if (entry.isDirectory()) await visit(filename, depth + 1);
      else if (entry.isFile() && entry.name.startsWith("rollout-") && entry.name.endsWith("-" + threadId + ".jsonl")) matches.push(filename);
    }
  }
  if ((await lstat(root)).isSymbolicLink()) return null;
  await visit(await realpath(root), 0);
  if (matches.length !== 1) return null;
  const filename = matches[0];
  if (await realpath(filename) !== filename) return null;
  return filename;
}

function scopeMatches(snapshot, request) {
  return snapshot?.project?.project_id === request.projectId
    && snapshot.project.project_root === request.projectRoot
    && snapshot.revision === request.challengeRevision
    && snapshot.gate_state?.gates?.G2 === "passed"
    && snapshot.gate_state?.gates?.G3 === "user-reviewable"
    && snapshot.artifacts?.["visual/contract"] === request.sourceVersion
    && request.evidenceRefs.every(ref => Object.values(snapshot.artifacts).includes(ref));
}

function promptMatches(message, request) {
  const text = textOf(message).replaceAll("`", "").replaceAll("**", "");
  const revisions = [...text.matchAll(/(?:权威\s+)?revision\s*[:：=]\s*(\d+)/giu)];
  return ["final", "final_answer"].includes(message.phase)
    && text.includes(request.sourceVersion)
    && /确认(?:当前)?视觉合同.{0,8}G3|确认(?:当前)?G3/u.test(text)
    && revisions.some(m => Number(m[1]) === request.challengeRevision);
}

async function inspectTranscript(filename, threadId, messageId, request) {
  const input = createReadStream(filename, { encoding: "utf8" });
  const lines = readline.createInterface({ input, crlfDelay: Infinity });
  let meta, snapshot, snapshotAt, prompt, found, matchingMessages = 0, withdrawn = false;
  const calls = new Set();
  try {
    for await (const line of lines) {
      const record = JSON.parse(line);
      const p = record.payload || {};
      if (record.type === "session_meta") {
        if (meta) return null;
        meta = p;
      }
      if (record.type !== "response_item") continue;
      if (p.type === "function_call" && snapshotTool(p)) {
        const args = JSON.parse(p.arguments);
        if (args.projectRoot === request.projectRoot) calls.add(p.call_id);
      }
      if (p.type === "function_call_output" && calls.has(p.call_id)) {
        calls.delete(p.call_id);
        snapshot = snapshotOf(p.output);
        snapshotAt = Date.parse(record.timestamp);
        prompt = null;
      }
      if (p.type !== "message") continue;
      if (p.id === messageId) {
        matchingMessages++;
        const acceptedAt = Date.parse(record.timestamp);
        const text = textOf(p);
        if (p.role === "user" && ACCEPTANCE.test(text.replace(/\s/g, ""))
            && prompt && scopeMatches(snapshot, request)
            && promptMatches(prompt.payload, request)
            && Number.isFinite(snapshotAt) && Number.isFinite(acceptedAt)
            && acceptedAt >= Date.parse(prompt.timestamp) && Date.parse(prompt.timestamp) >= snapshotAt) {
          found = { threadId, messageId, promptId: prompt.payload.id,
            acceptedAt: record.timestamp, reviewedRevision: snapshot.revision,
            sourceVersion: request.sourceVersion,
            messageSha256: createHash("sha256").update(text).digest("hex"),
            evidenceRefs: [...request.evidenceRefs] };
        }
      } else if (found && p.role === "user" && WITHDRAWAL.test(textOf(p).trim())) {
        withdrawn = true;
      }
      if (p.role === "user") prompt = null;
      if (p.role === "assistant") prompt = record;
    }
  } finally {
    lines.close();
    input.destroy();
  }
  if (meta?.id !== threadId || meta.originator !== "Codex Desktop" || meta.thread_source !== "user"
      || meta.forked_from_id || meta.parent_thread_id || matchingMessages !== 1 || withdrawn) return null;
  return found || null;
}

export function createHostMessageVerifier(options = {}) {
  const sessionsRoot = path.resolve(options.sessionsRoot || defaultSessionsRoot());
  return {
    async inspect(request = {}) {
      const ref = REF.exec(request.userMessageRef || "");
      if (!ref || request.gate !== "G3" || !request.projectId || !path.isAbsolute(request.projectRoot || "")
          || !/^artifact:\/\/visual-contract\/[0-9a-f]{64}$/.test(request.sourceVersion || "")
          || !Number.isSafeInteger(request.challengeRevision) || request.challengeRevision < 0
          || !Array.isArray(request.evidenceRefs) || request.evidenceRefs.length === 0
          || !request.evidenceRefs.includes(request.sourceVersion)
          || !/^[0-9a-f]{64}$/.test(request.challengeId || "")
          || (options.threadId && options.threadId !== ref[1])) return null;
      try {
        const filename = await findTranscript(sessionsRoot, ref[1]);
        return filename ? await inspectTranscript(filename, ref[1], ref[2], request) : null;
      } catch {
        return null;
      }
    },
    async verify(request) {
      return Boolean(await this.inspect(request));
    },
  };
}
