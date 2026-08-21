import { createHmac, randomBytes, randomUUID } from "node:crypto";

export const HOST_CONFIRMATION_SECRET_ENV = "AI_PPT_HOST_CONFIRMATION_SECRET";

function encodeBase64Url(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value, "utf8");
  return bytes.toString("base64url");
}

export function createHostConfirmationAuthority(options = {}) {
  const secret = options.secret || randomBytes(32).toString("base64url");
  const now = options.now || (() => Math.floor(Date.now() / 1000));
  const lifetimeSeconds = options.lifetimeSeconds || 120;

  return {
    secret,
    issue(context, { identityType, identityRef }) {
      if (!context?.project_id || !context?.project_root) {
        throw new Error("Gate confirmation context lacks canonical project identity");
      }
      if (!Array.isArray(context.evidence_refs)) {
        throw new Error("Gate confirmation context lacks evidence references");
      }
      if (!["host-action", "verified-message"].includes(identityType)) {
        throw new Error("Unsupported host confirmation identity type");
      }
      if (typeof identityRef !== "string" || !identityRef.trim()) {
        throw new Error("Host confirmation identity is required");
      }
      const issuedAt = now();
      const payload = {
        project_id: context.project_id,
        project_root: context.project_root,
        scope_kind: context.scope_kind,
        scope_id: context.scope_id,
        source_version: context.source_version,
        evidence_refs: context.evidence_refs,
        challenge_id: context.challenge_id,
        challenge_revision: context.challenge_revision,
        identity_type: identityType,
        identity_ref: identityRef.trim(),
        nonce: randomUUID(),
        issued_at: issuedAt,
        expires_at: issuedAt + lifetimeSeconds,
      };
      const payloadSegment = encodeBase64Url(
        JSON.stringify(payload),
      );
      const signature = createHmac("sha256", secret)
        .update(payloadSegment, "ascii")
        .digest();
      return `v1.${payloadSegment}.${encodeBase64Url(signature)}`;
    },
  };
}
