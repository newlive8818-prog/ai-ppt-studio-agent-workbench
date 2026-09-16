import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ElicitRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { createAiPptMcpServer } from "../mcp/server.mjs";
import { createHostMessageVerifier } from "../mcp/host-message-verifier.mjs";

const threadId = "11111111-1111-4111-8111-111111111111";
const messageId = "msg_22222222-2222-4222-8222-222222222222";
const contract = "artifact://visual-contract/" + "a".repeat(64);
const policy = "artifact://release-target-policy/" + "b".repeat(64);
const projectRoot = "/managed/projects/p1";
const snapshot = {
  revision: 8, project: { project_id: "p1", project_root: projectRoot },
  gate_state: { gates: { G0: "passed", G1: "passed", G2: "passed", G3: "user-reviewable" } },
  artifacts: { "visual/contract": contract, "release/target-policy": policy },
};
const request = {
  projectRoot, projectId: "p1", gate: "G3", sourceVersion: contract,
  evidenceRefs: [contract, policy], challengeRevision: 8,
  challengeId: "c".repeat(64),
  userMessageRef: `chat://message/${threadId}/${messageId}`,
};
const record = (type, payload, timestamp = "2026-09-14T10:00:00Z") => ({ type, payload, timestamp });
const msg = (role, text, id, timestamp) => record("response_item", {
  type: "message", id, role, content: [{ type: role === "user" ? "input_text" : "output_text", text }],
  ...(role === "assistant" ? { phase: "final_answer" } : {}),
}, timestamp);
const rows = () => [
  record("session_meta", { id: threadId, originator: "Codex Desktop", thread_source: "user" }),
  record("response_item", { type: "function_call", name: "mcp__ai_ppt_studio__get_ai_ppt_project_snapshot", call_id: "snapshot-1", arguments: JSON.stringify({ projectRoot }) }),
  record("response_item", { type: "function_call_output", call_id: "snapshot-1", output: JSON.stringify({ snapshot }) }),
  msg("assistant", `G3 当前视觉合同：${contract}\n权威 revision：8\n请确认当前视觉合同和 G3。`, "prompt-1"),
  msg("user", "接受 达到要求", messageId, "2026-09-14T10:01:00Z"),
];
async function fixture(t, records = rows()) {
  const root = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-bound-message-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const dir = path.join(root, "2026", "09", "14");
  await mkdir(dir, { recursive: true });
  const file = path.join(dir, `rollout-2026-09-14T10-00-00-${threadId}.jsonl`);
  await writeFile(file, records.map(x => JSON.stringify(x)).join("\n") + "\n");
  return { file, verifier: createHostMessageVerifier({ sessionsRoot: root }), root };
}
test("G3 binds a direct user reply to the displayed current snapshot and contract", async t => {
  const { verifier } = await fixture(t);
  assert.equal(await verifier.verify(request), true);
});
for (const text of ["不接受", "未达到要求", "接受但需要修改", "引用：接受 达到要求", "他说接受", "继续", "OK 继续", "<subagent_notification>接受</subagent_notification>"]) {
  test(`rejects non-acceptance or embedded text: ${text}`, async t => {
    const records = rows(); records[4].payload.content[0].text = text;
    const { verifier } = await fixture(t, records);
    assert.equal(await verifier.verify(request), false);
  });
}
for (const [name, changed] of [
  ["another project", { projectId: "p2", projectRoot: "/managed/projects/p2" }],
  ["another contract", { sourceVersion: "artifact://visual-contract/" + "d".repeat(64) }],
  ["another revision", { challengeRevision: 9 }],
  ["another evidence set", { evidenceRefs: [contract, "artifact://release-target-policy/" + "e".repeat(64)] }],
  ["another Gate", { gate: "G4" }],
  ["unscoped ref", { userMessageRef: "chat://message/" + messageId }],
  ["another task", { userMessageRef: `chat://message/33333333-3333-4333-8333-333333333333/${messageId}` }],
]) {
  test(`rejects ${name}`, async t => {
    const { verifier } = await fixture(t);
    assert.equal(await verifier.verify({ ...request, ...changed }), false);
  });
}
for (const [name, mutate] of [
  ["assistant reply", r => { r[4].payload.role = "assistant"; }],
  ["no displayed checkpoint", r => { r.splice(3, 1); }],
  ["stale displayed revision", r => { r[3].payload.content[0].text = `G3 ${contract}\nrevision: 9\n确认当前视觉合同和 G3`; }],
  ["inherited task", r => { r[0].payload.forked_from_id = "another-task"; }],
  ["fabricated snapshot tool name", r => { r[1].payload.name = "exec"; }],
  ["user-supplied snapshot", r => { r[2] = msg("user", JSON.stringify({ snapshot }), "quoted"); }],
  ["acceptance before display", r => { r[4].timestamp = "2026-09-13T10:00:00Z"; }],
  ["duplicate message", r => { r.push(r[4]); }],
  ["intervening user message", r => { r.splice(4, 0, msg("user", "另一个问题", "intervening")); }],
  ["withdrawn acceptance", r => { r.push(msg("user", "撤回刚才的视觉确认", "withdraw", "2026-09-14T10:02:00Z")); }],
]) {
  test(`rejects ${name}`, async t => {
    const records = rows(); mutate(records);
    const { verifier } = await fixture(t, records);
    assert.equal(await verifier.verify(request), false);
  });
}
test("fails closed on malformed transcript and symlink input", async t => {
  const { verifier, file } = await fixture(t);
  await writeFile(file, "bad-json\n");
  assert.equal(await verifier.verify(request), false);
  const other = file + ".original"; await writeFile(other, rows().map(x => JSON.stringify(x)).join("\n"));
  await rm(file); await symlink(other, file);
  assert.equal(await verifier.verify(request), false);
});

test("production G3 adapter signs bound messages without forms and is isolated from G4", async t => {
  const { verifier } = await fixture(t);
  for (const [gate, ref, success] of [
    ["G3", request.userMessageRef, true],
    ["G3", undefined, false],
    ["G3", "chat://message/" + messageId, false],
    ["G4", request.userMessageRef, false],
  ]) {
    const writes = [];
    let forms = 0;
    const server = createAiPptMcpServer({
      gateMessageVerifier: verifier,
      invokeBridge: async input => {
        if (input.operation === "get-gate-confirmation-context") return {
          confirmation_context: { project_id: "p1", project_root: projectRoot,
            gate, scope_kind: "gate", scope_id: gate, source_version: contract,
            evidence_refs: request.evidenceRefs, challenge_revision: 8,
            challenge_id: request.challengeId, review_summary: "Current G3" },
        };
        writes.push(input);
        return { ok: true, result: {} };
      },
    });
    const client = new Client({ name: "bound-chat-synthetic", version: "1" }, {
      capabilities: { elicitation: { form: {} } },
    });
    client.setRequestHandler(ElicitRequestSchema, async () => {
      forms++; return { action: "decline" };
    });
    const [a, b] = InMemoryTransport.createLinkedPair();
    await Promise.all([client.connect(a), server.connect(b)]);
    try {
      const result = await client.callTool({ name: "confirm_ai_ppt_gate",
        arguments: { projectRoot, expectedRevision: 8, gate, ...(ref ? { userMessageRef: ref } : {}) } });
      assert.equal(Boolean(result.isError), !success);
      assert.equal(forms, 0);
      assert.equal(writes.length, success ? 1 : 0);
      if (success) {
        const signed = JSON.parse(Buffer.from(writes[0].host_confirmation_assertion.split(".")[1], "base64url"));
        assert.equal(signed.identity_ref, ref);
        assert.equal(signed.source_version, contract);
        assert.equal(signed.challenge_revision, 8);
        assert.deepEqual(signed.evidence_refs, request.evidenceRefs);
      }
    } finally { await client.close(); }
  }
});

test("generic confirmation verifier cannot substitute for the G3 adapter", async () => {
  let writes = 0, forms = 0, genericChecks = 0;
  const server = createAiPptMcpServer({
    confirmationVerifier: { verify: async () => { genericChecks++; return true; } },
    invokeBridge: async input => {
      if (input.operation === "get-gate-confirmation-context") return { confirmation_context: {
        project_id: "p1", project_root: projectRoot, gate: "G3", scope_kind: "gate", scope_id: "G3",
        source_version: contract, evidence_refs: request.evidenceRefs,
        challenge_revision: 8, challenge_id: request.challengeId,
      } };
      writes++; return { ok: true, result: {} };
    },
  });
  const client = new Client({ name: "generic-only-synthetic", version: "1" }, {
    capabilities: { elicitation: { form: {} } },
  });
  client.setRequestHandler(ElicitRequestSchema, async () => { forms++; return { action: "decline" }; });
  const [a,b] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(a),server.connect(b)]);
  try {
    for (const ref of [request.userMessageRef, undefined]) {
      const result = await client.callTool({ name: "confirm_ai_ppt_gate", arguments: {
        projectRoot, expectedRevision: 8, gate: "G3", ...(ref ? { userMessageRef: ref } : {}),
      } });
      assert.equal(result.isError, true);
    }
    assert.equal(writes, 0); assert.equal(forms, 0); assert.equal(genericChecks, 0);
  } finally { await client.close(); }
});
