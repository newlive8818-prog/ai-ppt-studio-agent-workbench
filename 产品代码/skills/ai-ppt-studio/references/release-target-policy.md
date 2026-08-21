# Release target policy

Treat `ReleaseTargetPolicy` as the immutable current authority for G2 and G4 target scope. Never hard-code a target matrix in prompts, UI, fixtures, or Skill logic.

Resolve the current project-bound policy before G2 and re-resolve it before G4. Missing, invalid, or stale policy fails closed. The public Agent cannot supply arbitrary targets, remove required rows, or shrink, expand, or replace the policy ad hoc.

## Current required target

The current product policy requires:

- `macos-powerpoint`: Microsoft PowerPoint desktop on macOS.

The current deferred target IDs are `macos-wps`, `windows-powerpoint`, and `windows-wps`. Deferred targets do not block a Gate until a new immutable policy places them in `required_target_ids`. A policy identity change reopens G2 and locks G3/G4.

`deferred` means neither passed, failed, unsupported, nor compatible; it is not a Gate row. Do not claim WPS or Windows compatibility without current policy-required evidence.

## Evidence contract

Each required target record must bind the exact policy reference, Gate stage, target ID, OS name/version/build, application name/version, font inventory, missing fonts, substitutions and wrapping risk, PPTX SHA-256, exports and hashes, per-page checks, executor, execution time, tool versions, reviewer attestation, and immutable evidence refs.

Every applicable target must pass:

- semantic fidelity: frozen facts, claims, relationships, evidence, and notes remain correct;
- aesthetics: composition, hierarchy, rhythm, typography, color, and image intent remain complete;
- engineering: native editability, geometry, overflow, crop, layering, connectors, and sources remain valid;
- target rendering: the named desktop application displayed and exported without silent degradation.

One missing, failed, stale, `not-applicable` without a recorded reason, or different-hash required row blocks the Gate. A PPTX hash change invalidates every required row. With an unchanged hash, an application, OS, or font-environment change invalidates only the affected target.

Local rendering, PDF export, Browser preview, fixtures, screenshots, historic files, or another desktop application cannot substitute for the required current target. G2 evidence belongs to the native anchor PPTX. G4 requires new evidence for the final PPTX and never reuses the G2 anchor record; it also requires a delivery package bound to the re-resolved current policy, the exact sent PPTX, a verified delivery receipt, and explicit final user confirmation.

Release-target evidence is independent from content/visual review UI and Browser evidence. A `review-session-ready` result proves only that a scoped Review Bridge handoff is ready; it becomes real Browser evidence only after the Agent opens the scoped resource in the Codex built-in Browser and verifies the required read/save behavior.
