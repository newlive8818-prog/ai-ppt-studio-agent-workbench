# Codex Presentations handoff

Codex Presentations is mandatory for all PPTX reads, creates, edits, renders, and inspections. Do not create another compiler and never use `python-pptx`.

## Authorized handoff

The task must include current content blueprint, Deck Design System, full slide contract set, real local assets, output PPTX/render paths inside the managed project, source-note policy, exact change scope, expected revision, and authorizing Gate. Before G1, no anchor PPTX is authorized; before G3, no full-deck build is authorized.

## Native semantic editability

Keep titles, body, labels, facts, numbers, tables, charts, simple diagrams, connectors, business relationships, logos, and page markers native. Photos, screenshots, complex illustration, texture, and atmospheric background may be separate replaceable image layers. Prohibit whole-slide bitmap delivery, baked factual text, untraceable data, and decorative layers that prevent normal editing.

Add `[Sources]` blocks to speaker notes for non-trivial claims and external assets.

## Anchor build and G2

Build difficult and content-complex native anchors from the full accepted contract. Render and inspect every anchor, fix overlap, clipping, wrapping, crop, font, connector, source-note, object, and editability defects. Then resolve the current `ReleaseTargetPolicy` through `four-target-acceptance.md` and validate the identical anchor PPTX in every required desktop target; G2 remains blocked until every required row passes on the same PPTX SHA-256. Deferred profiles are not Gate rows.

## Full deck and G4

After G3, build the complete deck, render every page, inspect each page at full size, use a montage only for rhythm, run overflow/structure/source/editability checks, and repair all failures. Resolve the current policy again and validate the identical final PPTX in every required target. G4 requires a new final-PPTX macOS PowerPoint record, not the G2 anchor record. Register the policy-bound delivery package and send that exact file through Codex chat before G4 confirmation.
