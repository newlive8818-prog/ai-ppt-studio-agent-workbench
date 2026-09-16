import assert from "node:assert/strict";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ElicitRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { createAiPptMcpServer } from "../mcp/server.mjs";

const targetRef = "artifact://image-led-authorization-scope/" + "a".repeat(64);
const input = { projectRoot: "/managed/project", expectedRevision: 3, targetRef, choice: "approved" };
const context = (overrides = {}) => ({
  project_id: "p1", project_root: "/managed/project", scope_kind: "image-led-authorization",
  scope_id: targetRef, source_version: targetRef, evidence_refs: [targetRef],
  challenge_id: "b".repeat(64), challenge_revision: 3,
  target_ref: targetRef, choice: "approved", review_summary: "已登记材料范围；test-provider / gpt-image-2。",
  ...overrides,
});

async function setup({ rawContext = context(), imageLed = true, verifier, native, commitReceipt } = {}) {
  const calls = [];
  const verified = [];
  const forms = [];
  const server = createAiPptMcpServer({
    invokeBridge: async (request) => {
      calls.push(request);
      if (request.operation === "get-image-led-confirmation-context") {
        return { ok: true, image_led: imageLed, confirmation_context: rawContext };
      }
      if (request.operation === "commit-artifact" && commitReceipt) return commitReceipt;
      return { ok: true, result: { decision_ref: "synthetic-decision", follow_up_message: "继续处理" } };
    },
    ...(verifier ? { confirmationVerifier: { verify: async (request) => {
      verified.push(request);
      return verifier(request);
    } } } : {}),
  });
  const client = new Client({ name: "image-led-confirmation-synthetic", version: "0.1.0" }, {
    capabilities: native ? { elicitation: { form: {} } } : {},
  });
  if (native) client.setRequestHandler(ElicitRequestSchema, async (request) => {
    forms.push(request);
    return native(request);
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([client.connect(clientTransport), server.connect(serverTransport)]);
  return { client, calls, verified, forms, invoke: (args = input) => client.callTool({
    name: "submit_ai_ppt_human_decision", arguments: args,
  }) };
}

test("Image-led missing trusted host capability never reaches generic decision write", async () => {
  const fixture = await setup();
  try {
    const result = await fixture.invoke({ ...input, userMessageRef: "chat://unverified", hostConfirmationAssertion: "forged" });
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent.error.code, "CAPABILITY_GAP");
    assert.deepEqual(fixture.calls.map((r) => r.operation), ["get-image-led-confirmation-context"]);
  } finally { await fixture.client.close(); }
});

test("Image-led verified message signs only resolved current target context", async () => {
  const fixture = await setup({ verifier: () => true });
  try {
    const result = await fixture.invoke({ ...input, userMessageRef: "chat://verified", hostConfirmationAssertion: "forged" });
    assert.equal(result.isError, undefined);
    assert.equal(fixture.verified.length, 1);
    assert.equal(fixture.verified[0].scopeKind, "image-led-authorization");
    assert.equal(fixture.verified[0].choice, "approved");
    assert.equal(fixture.verified[0].projectRoot, "/managed/project");
    assert.deepEqual(fixture.calls.map((r) => r.operation), ["get-image-led-confirmation-context", "submit-human-decision"]);
    const request = fixture.calls[1];
    assert.equal(request.user_message_ref, undefined);
    assert.match(request.host_confirmation_assertion, /^v1\./);
    assert.notEqual(request.host_confirmation_assertion, "forged");
    const assertion = JSON.parse(Buffer.from(request.host_confirmation_assertion.split(".")[1], "base64url"));
    assert.equal(assertion.scope_kind, "image-led-authorization");
    assert.equal(assertion.scope_id, targetRef);
    assert.equal(assertion.identity_type, "verified-message");
    assert.equal(assertion.identity_ref, "chat://verified");
    assert.deepEqual(assertion.evidence_refs, [targetRef]);
  } finally { await fixture.client.close(); }
});

test("Image-led rejected verifier or stale/mismatched context never writes", async () => {
  for (const options of [
    { verifier: () => false },
    { verifier: () => ({ approved: true }) },
    { verifier: () => { throw new Error("unavailable"); } },
    { verifier: () => true, rawContext: context({ challenge_revision: 4 }) },
    { verifier: () => true, rawContext: context({ scope_id: "wrong-target" }) },
    { verifier: () => true, rawContext: context({ scope_kind: "gate" }) },
    { verifier: () => true, rawContext: context({ choice: "revoked" }) },
  ]) {
    const fixture = await setup(options);
    try {
      const result = await fixture.invoke({ ...input, userMessageRef: "chat://verified" });
      assert.equal(result.isError, true);
      assert.deepEqual(fixture.calls.map((r) => r.operation), ["get-image-led-confirmation-context"]);
    } finally { await fixture.client.close(); }
  }
});

test("Image-led native accept signs scoped revocation and decline stays read-only", async () => {
  for (const confirmed of [true, false]) {
    const fixture = await setup({
      rawContext: context({ scope_kind: "image-led-revocation", choice: "revoked" }),
      native: () => ({ action: "accept", content: { confirmed } }),
    });
    try {
      const result = await fixture.invoke({ ...input, choice: "revoked" });
      assert.equal(fixture.forms.length, 1);
      assert.match(fixture.forms[0].params.message, /撤销/);
      assert.equal(fixture.calls.length, confirmed ? 2 : 1);
      if (confirmed) {
        const assertion = JSON.parse(Buffer.from(fixture.calls[1].host_confirmation_assertion.split(".")[1], "base64url"));
        assert.equal(assertion.scope_kind, "image-led-revocation");
        assert.equal(assertion.identity_type, "host-action");
      } else assert.equal(result.isError, true);
    } finally { await fixture.client.close(); }
  }
});

test("non Image-led decision keeps existing generic write and needs no confirmation", async () => {
  const fixture = await setup({ imageLed: false, rawContext: null });
  try {
    const result = await fixture.invoke({ ...input, targetRef: "artifact://decision/" + "c".repeat(64), choice: "继续" });
    assert.equal(result.isError, undefined);
    assert.equal(fixture.verified.length, 0);
    assert.equal(fixture.calls[1].choice, "继续");
    assert.equal(fixture.calls[1].host_confirmation_assertion, undefined);
  } finally { await fixture.client.close(); }
});


const reuseInput = { ...input, confirmationMode: "verified-message-only" };
const commitInput = { projectRoot: input.projectRoot, expectedRevision: 2, kind: "visual-contract",
  payload: { artifact_type: "image-led-authorization-scope", project_id: "p1" } };
const scopeReceipt = () => ({ ok: true, selected_project_root: "/managed/project",
  result: { artifact_ref: targetRef, snapshot: { revision: 3, artifacts: { "visual/image-led/scope": targetRef },
    project: { project_id: "p1", project_root: "/managed/project" } } } });

for (const [label, options, args, reason] of [
  ["missing verifier", {}, { ...reuseInput, userMessageRef: "chat://existing" }, "verified-message-adapter-unavailable"],
  ["missing message", { verifier: () => true }, reuseInput, "verified-message-reference-unavailable"],
  ["both missing", {}, reuseInput, "verified-message-adapter-unavailable"],
]) test(`reuse-only ${label} never falls back to a native form`, async () => {
  const fixture = await setup({ ...options, native: () => ({ action: "cancel" }) });
  try {
    const result = await fixture.invoke(args);
    assert.equal(fixture.forms.length, 0);
    assert.equal(fixture.verified.length, 0);
    assert.equal(result.structuredContent.error.code, "CAPABILITY_GAP");
    assert.equal(result.structuredContent.error.details.reason, reason);
    assert.deepEqual(fixture.calls.map((r) => r.operation), ["get-image-led-confirmation-context"]);
  } finally { await fixture.client.close(); }
});

test("reuse-only failed, throwing or non-boolean verifier never falls back or signs", async () => {
  for (const verifier of [() => false, () => ({ approved: true }), () => { throw new Error("private-customer-content"); }]) {
    const fixture = await setup({ verifier, native: () => ({ action: "accept", content: { confirmed: true } }) });
    try {
      const result = await fixture.invoke({ ...reuseInput, userMessageRef: "chat://existing" });
      assert.equal(result.isError, true);
      assert.equal(fixture.forms.length, 0);
      assert.equal(fixture.verified.length, 1);
      assert.equal(fixture.calls.length, 1);
      assert.ok(!JSON.stringify(result).includes("private-customer-content"));
    } finally { await fixture.client.close(); }
  }
});

test("reuse-only strict true keeps exact scoped assertion and stale context cannot write", async () => {
  for (const stale of [false, true]) {
    const fixture = await setup({ verifier: () => true,
      rawContext: context(stale ? { challenge_revision: 4 } : {}),
      native: () => ({ action: "cancel" }) });
    try {
      const result = await fixture.invoke({ ...reuseInput, userMessageRef: "chat://existing" });
      assert.equal(fixture.forms.length, 0);
      assert.equal(fixture.verified.length, stale ? 0 : 1);
      assert.equal(fixture.calls.length, stale ? 1 : 2);
      if (stale) assert.equal(result.structuredContent.error.code, "REVISION_CONFLICT");
      else {
        const statement = JSON.parse(Buffer.from(fixture.calls[1].host_confirmation_assertion.split(".")[1], "base64url"));
        assert.equal(statement.identity_type, "verified-message");
        assert.equal(statement.identity_ref, "chat://existing");
        assert.equal(statement.scope_id, targetRef);
        assert.equal(statement.challenge_revision, 3);
      }
    } finally { await fixture.client.close(); }
  }
});

test("explicit allow-native keeps accept and cancellation behavior", async () => {
  for (const action of ["accept", "cancel"]) {
    const fixture = await setup({ native: () => ({ action, ...(action === "accept" ? { content: { confirmed: true } } : {}) }) });
    try {
      const result = await fixture.invoke({ ...input, confirmationMode: "allow-native" });
      assert.equal(fixture.forms.length, 1);
      assert.equal(fixture.calls.length, action === "accept" ? 2 : 1);
      if (action === "cancel") assert.equal(result.structuredContent.error.code, "HOST_CONFIRMATION_DECLINED");
    } finally { await fixture.client.close(); }
  }
});

test("scope commit supplies an explicit reuse-only call that the real handler consumes", async () => {
  const fixture = await setup({ commitReceipt: scopeReceipt(), native: () => ({ action: "cancel" }) });
  try {
    const receipt = await fixture.client.callTool({ name: "commit_ai_ppt_artifact", arguments: commitInput });
    const handoff = receipt.structuredContent.authorization_continuation;
    assert.equal(handoff.status, "requires-verified-message");
    assert.deepEqual(handoff.call, { name: "submit_ai_ppt_human_decision", arguments: reuseInput });
    assert.equal(fixture.forms.length, 0);
    assert.equal(fixture.calls.length, 1);
    const result = await fixture.client.callTool(handoff.call);
    assert.equal(result.structuredContent.error.code, "CAPABILITY_GAP");
    assert.equal(result.structuredContent.error.details.reason, "verified-message-adapter-unavailable");
    assert.equal(fixture.forms.length, 0);
    assert.deepEqual(fixture.calls.map((r) => r.operation), ["commit-artifact", "get-image-led-confirmation-context"]);
  } finally { await fixture.client.close(); }
});

test("scope continuation uses returned identity and fails closed on incomplete or inconsistent receipts", async () => {
  for (const mutate of [
    (r) => { delete r.result.snapshot; },
    (r) => { r.result.artifact_ref = "artifact://image-led-selection/" + "c".repeat(64); },
    (r) => { r.result.snapshot.revision = 1.5; },
    (r) => { r.result.snapshot.project.project_id = "p2"; },
    (r) => { r.result.snapshot.project.project_root = "/other/project"; },
    (r) => { delete r.selected_project_root; },
    (r) => { r.result.snapshot.revision = 1; },
    (r) => { delete r.result.snapshot.artifacts; },
    (r) => { r.result.snapshot.artifacts["visual/image-led/scope"] = "artifact://image-led-authorization-scope/" + "f".repeat(64); },
  ]) {
    const raw = scopeReceipt(); mutate(raw);
    const fixture = await setup({ commitReceipt: raw });
    try {
      const result = await fixture.client.callTool({ name: "commit_ai_ppt_artifact", arguments: commitInput });
      assert.equal(result.isError, undefined); // The preceding commit receipt must remain successful.
      assert.equal(result.structuredContent.authorization_continuation.status, "capability-gap");
      assert.equal(result.structuredContent.authorization_continuation.call, undefined);
      assert.equal(fixture.calls.length, 1);
    } finally { await fixture.client.close(); }
  }
});

test("other artifacts and generic decisions do not acquire authorization flow", async () => {
  const fixture = await setup({ commitReceipt: scopeReceipt(), imageLed: false });
  try {
    const receipt = await fixture.client.callTool({ name: "commit_ai_ppt_artifact", arguments: {
      ...commitInput, payload: { artifact_type: "visual-brief" } } });
    assert.equal(receipt.structuredContent.authorization_continuation, undefined);
    const result = await fixture.invoke({ ...reuseInput, targetRef: "artifact://decision/" + "c".repeat(64) });
    assert.equal(result.isError, undefined);
    assert.equal(fixture.forms.length, 0);
    assert.equal(fixture.calls.at(-1).operation, "submit-human-decision");
  } finally { await fixture.client.close(); }
});


test("cancellation while reuse verifier is pending prevents late signed write", async () => {
  let release;
  let started;
  const pending = new Promise((resolve) => { release = resolve; });
  const entered = new Promise((resolve) => { started = resolve; });
  const fixture = await setup({ verifier: async () => { started(); return pending; },
    native: () => ({ action: "accept", content: { confirmed: true } }) });
  try {
    const controller = new AbortController();
    const call = fixture.client.callTool({ name: "submit_ai_ppt_human_decision",
      arguments: { ...reuseInput, userMessageRef: "chat://existing" } }, undefined,
      { signal: controller.signal }).catch((error) => error);
    await entered;
    controller.abort();
    await call;
    await new Promise((resolve) => setImmediate(resolve));
    release(true);
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(fixture.forms.length, 0);
    assert.deepEqual(fixture.calls.map((r) => r.operation), ["get-image-led-confirmation-context"]);
  } finally { release(true); await fixture.client.close(); }
});

test("scope continuation retains the actual replay revision without guessing an increment", async () => {
  const raw = scopeReceipt(); raw.result.snapshot.revision = 11;
  const fixture = await setup({ commitReceipt: raw });
  try {
    const result = await fixture.client.callTool({ name: "commit_ai_ppt_artifact", arguments: commitInput });
    assert.equal(result.structuredContent.authorization_continuation.call.arguments.expectedRevision, 11);
    assert.equal(fixture.calls.length, 1);
  } finally { await fixture.client.close(); }
});
