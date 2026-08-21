# Codex Presentations handoff

Codex Presentations is mandatory for all PPTX reads, creates, edits, renders, and inspections. Do not create another compiler and never use `python-pptx`.

## Authorized handoff

The task must include the current `ReadingDeckBlueprint`, `DeckDesignSystem`, every `SlideVisualContract`, real local assets, output PPTX/render paths inside the managed project, source-note policy, exact change scope, expected revision, current `ReleaseTargetPolicy`, and authorizing Gate. Before G1, no anchor PPTX is authorized; before G3, no full-deck build is authorized.

## Native semantic editability

Keep titles, body, labels, facts, numbers, tables, charts, simple diagrams, connectors, business relationships, logos, and page markers native. Photos, screenshots, complex illustration, texture, and atmospheric background may be separate replaceable image layers. Prohibit whole-slide bitmap delivery, baked factual text, untraceable data, and decorative layers that prevent normal editing.

Add `[Sources]` blocks to speaker notes for non-trivial claims and external assets.

## Anchor build and G2

Build difficult and content-complex native anchors from the full accepted contract. Render and inspect every anchor; fix overlap, clipping, wrapping, crop, font, connector, source-note, object, and editability defects. Validate the identical anchor PPTX in every `ReleaseTargetPolicy.required_target_ids` target defined in `release-target-policy.md`. G2 remains blocked until every current required row passes on the same PPTX SHA-256.

Deferred profiles are not Gate rows and do not imply pass, failure, lack of support, or compatibility.

## Full deck and G4

After G3, build the complete deck, render every page, inspect each page at full size, use a montage only for rhythm, run overflow/structure/source/editability checks, and repair all failures. Re-resolve the current policy, validate the identical final PPTX against every current required target, and create new final-PPTX evidence; never reuse a G2 anchor record. Bind the exact current policy ref into the delivery package and send that exact file through Codex chat before G4 confirmation.
