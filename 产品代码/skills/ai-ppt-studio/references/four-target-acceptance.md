# Four-target desktop acceptance

G2 and G4 require these exact independent target IDs:

1. `macos-powerpoint` — Microsoft PowerPoint desktop on macOS.
2. `macos-wps` — WPS Office Presentation desktop on macOS.
3. `windows-powerpoint` — Microsoft PowerPoint desktop on Windows 11.
4. `windows-wps` — WPS Office Presentation desktop on Windows 11.

All four rows at one Gate must reference the same PPTX SHA-256. A browser render, developer render, deterministic fixture, historic PPTX, PDF alone, or one operating system cannot substitute for a current desktop row.

## Required evidence fields

Each immutable record contains target ID, Gate stage, OS name/version/build, application name/version, font inventory, missing fonts, substitutions and wrapping risk, exact PPTX SHA-256, export paths/hashes, per-page checks, executor, execution time, tool versions, and immutable evidence refs.

Each page and the whole target record must pass four binary doors:

- semantic: frozen facts, claims, relationships, real evidence, and notes remain correct;
- aesthetic: composition, hierarchy, rhythm, typography, color, and image intent remain complete;
- engineering: native editability, object presence, geometry, overflow, crop, layering, connectors, and sources remain valid;
- target-render: the named desktop application exported and displayed without silent degradation.

One failed/not-applicable-without-reason/missing/stale row blocks the Gate. A PPTX hash change invalidates all four rows. If the hash is unchanged but one application/OS/font environment changes, only that target requires a new evidence version.

G4 additionally requires the current delivery package, the exact PPTX sent through Codex chat, a successful host-verified delivery reference, and explicit final user confirmation. Do not assume a fixed host message URI format or fabricate the reference.

Four-target evidence is independent of UI evidence. Local previews, chat UI display modes, browser-only renders, and developer screenshots cannot prove the real Codex sidebar or Codex built-in Browser experience. Missing `HOST_SIDEBAR_UNAVAILABLE`, `BROWSER_REVIEW_UNAVAILABLE`, or `BROWSER_REVIEW_SAVE_UNAVAILABLE` capability gaps remain open acceptance blockers and must not be hidden by chat UI fallback.
