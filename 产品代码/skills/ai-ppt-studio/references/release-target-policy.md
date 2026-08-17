# Release target policy

Treat `ReleaseTargetPolicy` as the immutable current authority for G2 and G4 target scope. Never hard-code a target matrix in prompts, UI, fixtures, or Skill logic.

## Current required target

The current product policy requires:

- `macos-powerpoint`: Microsoft PowerPoint desktop on macOS.

Additional targets may be listed as deferred, but they do not block a Gate until a new immutable policy places them in `required_target_ids`. A policy identity change reopens G2 and locks G3/G4.

## Evidence contract

Each required target record must bind the exact policy reference, Gate stage, target ID, OS and application versions, font inventory and substitutions, PPTX SHA-256, exports and hashes, per-page checks, executor, execution time, tool versions, and immutable evidence refs.

Every applicable target must pass:

- semantic fidelity: frozen facts, claims, relationships, evidence, and notes remain correct;
- aesthetics: composition, hierarchy, rhythm, typography, color, and image intent remain complete;
- engineering: native editability, geometry, overflow, crop, layering, connectors, and sources remain valid;
- target rendering: the named desktop application displayed and exported without silent degradation.

One missing, failed, stale, or different-hash required row blocks the Gate. A PPTX hash change invalidates every required row. With an unchanged hash, an application, OS, or font-environment change invalidates only the affected target.

Local rendering, PDF export, Browser preview, fixtures, screenshots, historic files, or another desktop application cannot substitute for the required current target. G4 also requires the current delivery package, the exact sent PPTX, a verified delivery receipt, and explicit final user confirmation.
