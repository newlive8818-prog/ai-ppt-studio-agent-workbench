# Release-target desktop acceptance

This filename is retained as a compatibility entry point. The old fixed-four-target Gate contract is superseded. Active acceptance is driven only by the immutable project-bound `ReleaseTargetPolicy`.

## Resolve policy before evidence

Before G2 or G4, resolve the current `release/target-policy` artifact and bind its exact ref into the Gate lineage or delivery package. The public Agent cannot supply arbitrary target arrays or shrink the policy. If the policy is missing, invalid, or stale, stop; never infer a default from available evidence.

The current v1.6 policy is:

- required: `macos-powerpoint` — Microsoft PowerPoint desktop on macOS;
- deferred: `macos-wps`, `windows-powerpoint`, `windows-wps`.

`deferred` means not required in the current release. It is not passed, failed, unsupported, or proof of compatibility. Enforce this literal rule: `do not claim WPS or Windows compatibility`. A future policy may promote a supported profile without deleting historical evidence.

All required rows at one Gate must reference the same PPTX SHA-256. A browser render, developer render, deterministic fixture, historic PPTX, PDF alone, or preflight-only output cannot replace desktop evidence.

## Required evidence fields

Each immutable required record contains target ID, Gate stage, OS name/version/build, application name/version, font inventory, missing fonts, substitutions and wrapping risk, exact PPTX SHA-256, export paths/hashes, per-page checks, executor, execution time, tool versions, reviewer attestation, and immutable evidence refs.

Each page and the whole required record must pass four binary doors:

- semantic: frozen facts, claims, relationships, real evidence, and notes remain correct;
- aesthetic: composition, hierarchy, rhythm, typography, color, and image intent remain complete;
- engineering: native editability, object presence, geometry, overflow, crop, layering, connectors, and sources remain valid;
- target-render: the named desktop application exported and displayed without silent degradation.

One failed, missing, stale, not-applicable-without-reason, or different-hash required row blocks the Gate. A PPTX hash change invalidates every current required row. An unchanged hash plus one application/OS/font environment change invalidates only that target row.

G2 validates the native anchor PPTX. G4 requires a new final-PPTX macOS PowerPoint record and never reuses G2 anchor evidence. G4 also requires the current policy-bound delivery package, the exact PPTX sent through Codex chat, a successful host-verified delivery reference, and explicit final user confirmation. Do not assume a fixed host message URI format or fabricate the reference.

Release-target evidence is independent of UI evidence. Local previews, chat UI display modes, browser-only renders, and developer screenshots cannot prove the real Codex sidebar or Codex built-in Browser experience. A `review-session-ready` MCP result proves only the scoped Review Bridge handoff; it becomes real Browser evidence only after the Agent opens it in the Codex built-in Browser and verifies read/save behavior. Actual `HOST_SIDEBAR_UNAVAILABLE`, `BROWSER_REVIEW_UNAVAILABLE`, or `BROWSER_REVIEW_SAVE_UNAVAILABLE` gaps remain open acceptance blockers.
