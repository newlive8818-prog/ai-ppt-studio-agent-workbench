# Codex Presentations handoff

Use Codex Presentations as the sole PPTX authoring and rendering engine; never use `python-pptx` or a second writer. Runtime may inspect OOXML read-only to verify the exported file. The Image-led plan compiler derives data, not another PPTX.

## Authorized handoff

The target Image-led route is:

```text
exact finalized design and reconciled visible copy
-> complete region mapping and validated VisualCompilationPlan
-> one faithful-conversion task
-> closed ContextPack visual_handoff
-> Codex Presentations
-> governed build result and independent four-dimension review
-> Runtime-derived same-plan AnchorSlideSet
```

The finalized image hash, bound visible copy, material roles, accepted deviations, and region-to-object mapping follow the same identity through the task, plan, ContextPack, and result. C2's `build-native-first` action dispatches explicit Image-led projects through the current reviewed plan and finalized dependencies. Legacy projects retain their separate behavior; prompts cannot switch the route.

The task and governance wrapper bind refs for the exact current `ReadingDeckBlueprint` as source provenance, `Visual Brief`,
`DeckDesignSystem`, full contract set, current plan, source revision, and
`ReleaseTargetPolicy`. Runtime resolves and revalidates these dependencies and the authorizing Gate. The renderer receives only its closed nested input, verified asset snapshots and managed task output paths; do not append raw blueprints, source-note policy, or extra instructions to its schema. The task target must be exactly
`[current visual/compilation-plan]`; an empty list, a contract ref, multiple refs, an
old plan, or a plan from another project is rejected before task creation.

The closed `layers.visual_handoff` is the governance wrapper containing current refs, revisions and policy. Its `renderer_handoff` is the actual data-only renderer input; never pass the wrapper itself or manually reconstruct a substitute. The nested input contains the bound slides, exact regions/objects, verified assets and task output paths, with explicit matching versions: historical v1 uses `compiler_version=image-led-faithful-compiler/v1` and `handoff_version=codex-presentations-image-led/v1`; v2 copy with versionless regions uses `compiler_version=image-led-faithful-compiler/v2` and `handoff_version=codex-presentations-image-led/v2`. Explicit v3 regions derive matching compiler/handoff v3 as described below. A v2 slide includes complete `selected_copy` with `copy_version`, `title_item_id` and ordered items; preserve its exact full-object hash and compare regions against it. Never reconstruct a versionless `{items}` object or infer the title from the first item. The binding contains actual used material roles, and every selected real material still requires complete region and native coverage. These are read-only projections of current artifacts, not independently editable facts. Visible copy comes only from the finalized selection. Output paths remain under the actual managed project root and include the immutable task id; existing directories, other projects, and another task's directory are rejected before any output write. Synthetic test project roots under temporary storage are engineering evidence only.

Before G1, no anchor PPTX is authorized; before G3, no full-deck build is authorized.

### Explicit native v3 regions

Use `region_version: image-led-region-inventory/v3` on the inventory root when transcribing source-image-derived relationships, finite polygon contours or natural wrapping. The original `image-led-selected-copy/v2` and its full-object hash remain unchanged. The compiler derives matching `image-led-faithful-compiler/v3` / `codex-presentations-image-led/v3` and includes `region_version` on every handoff slide. Versionless regions retain their historical v1/v2 behavior; do not add v3 fields or strip versions to bypass a check.

Each ordinary v3 text appearance and table cell style requires `wrap: none | square`. Preserve exact Unicode runs, their order, font values and explicit text; the renderer retains `noAutofit`. Natural wrapping is a display behavior, not permission to insert newline characters. One selected item still maps to one complete text region; only the explicit source-mapped fragment form below can expand it into independently positioned native text objects.

For text whose original parts occupy separate positions in the selected image, v3 text region appearance may instead contain only `fragments: [{span: [start,end], bbox, appearance}]`. Spans are Unicode codepoint intervals `[start,end)`, not UTF-16 offsets; they must cover the original full item once, in contiguous source order, without gaps or overlap. Every fragment appearance uses the ordinary nonfragment v3 text style, and its runs must concatenate exactly to that original span, including symbols and spaces. Fragment bbox uses absolute 96DPI canvas coordinates inside its owning region. Do not add line breaks, invent geometry, omit a separator or hide text to fit the image. The logical region still owns the full item once. The same renderer expands child object names as `<original-object-id>::fragment:<start>:<end>` and records span on their mapping rows; result inspection verifies each native child and reconstructs the complete original item. Source-image relation paths continue to reference the whole region; any legacy physical connector pointing to a region containing fragments is a pre-write CapabilityGap, without choosing a child or an implicit parent frame. Actual font ink and visual fidelity still need independent inspection.

When a selected image shows an authorized real material in its finalized presentation, v3 `kind: image` may retain the original four-field `material_binding` and add `render_source: selected-image-crop` to its usual `appearance: {asset_ref, asset_sha256, crop}`. That asset ref/hash must equal this page's exact TargetBinding image ref/hash, with the complete selected image bytes and normalized source crop; arbitrary cropped assets or other-page images are rejected. Original material provenance/use and selected real-material coverage remain required; the marker is not allowed for unbound images, non-real-material roles or decorations. Without the marker, the original material-byte identity rule remains. Explicit partial crops, including ordinary decoration crops, must preserve the supplied frame and source crop through the SDK's public aspect-lock control after the existing crop/bbox ratio check. Never silently restore the original JPEG or bake principal text into decoration to bypass these checks.

Each v3 text run may use exactly one of legacy `color` or explicit `fill`; all original text/font/bold/italic fields stay required and unchanged. Explicit fill uses the existing non-null `solid` or finite `linear-gradient` object. Linear stop offsets must multiply by 100000 to an exact integer accepted by the current SDK; unrepresentable new text stops fail before registration as a CapabilityGap, without rounding or converting text to an image. The renderer passes the original fill to native `textStyle.fill`; results verify editable OOXML text and exact encoded gradient stops/colors/angle, including SDK angle truncation to integer 1/60000-degree units. A successful synthetic export/reimport establishes this finite carrier capability, not customer fidelity or PowerPoint acceptance.

V3 ordinary text runs, fragment runs and table-cell runs may explicitly carry `characterSpacing`, a strict integer in `[-400000,400000]` measured in 1/100 pt (75 units = one 96DPI CSS px). Omit it to retain the old contract; do not synthesize a default or infer a value merely to fit a box. The same renderer passes the exact value to the SDK's public `textStyle.characterSpacing` while retaining original Unicode, typeface, font size and `noAutofit`. Actual PPTX inspection requires the corresponding exact integer `a:rPr@spc`; missing or changed spacing fails. A run that did not select this field still rejects any added `spc`, including zero. This controls inter-character spacing, not single-glyph width: it cannot solve nonuniform `▎` or `｜` shapes, and similar total line width is not visual-fidelity proof. Never shrink font size, replace a character, hand-edit XML or hide text to claim a match.

Those same v3 runs may explicitly carry `outline: {color, width}`: an opaque six-digit color and positive finite 96DPI CSS-pixel width whose product with 9525 is an exact integer EMU no greater than 20116800. The renderer uses only the public SDK solid text outline. Actual PPTX checks require the exact integer width/color and the supported solid `a:ln` structure; missing/changed outline, alpha, extra line effects or an added outline on an unselected run all reject. Original visible text fill, Unicode, font values and `noAutofit` remain mandatory. The field is not permission to hide characters or synthesize fitting values. A smaller font plus outline may reproduce a source ink shape only after independent measurement; it is not a nonuniform transform that retains the previous font size. Background-color outlines require actual visible-center, halo and source-background inspection and do not automatically establish faithful rendering.

For a relationship visible in the exact selected image, use `kind: relation-path`, `content: {items: []}`, `material_binding: null`, and appearance containing exactly `paths`, `fill`, `line`, `relation_binding`. A directed binding has `{origin: source-image-derived, target_image_sha256, kind: directed-edge, from_item_id, to_item_id, direction: forward | backward | both}`; its two distinct endpoints reference original selected text/table-cell IDs on this page. A feedback binding has `{origin: source-image-derived, target_image_sha256, kind: feedback-symbol, anchor_item_id}`; it references one original item, without inventing a physical return edge. Region identity, binding and path travel together through the reviewed inventory and exact object mapping. This carrier is an editable freeform shape with semantic binding in the governed handoff, without dynamic connector snapping. Do not add relation items or visible meaning labels to selected copy, and do not hide business arrows as ordinary decoration.

When the visible source endpoint is a shared container, the directed binding may replace the complete item pair with `from_region_id` and `to_region_id`. The two forms are mutually exclusive; region endpoints must be distinct existing text/table/shape/image regions on this exact page and image hash. A shape with no visible fill or line, relation path, connector or decoration cannot serve as a container endpoint. Original item content stays in its own mapped regions; the container does not assign those words to one inferred business endpoint. Transcribe and independently review the actual source relationship, preserving the original paths and geometry. This adds no container-membership inference, new labels, automatic routing or endpoint snapping.

`paths` contains 1–16 `{width, height, commands}` records. Width/height equal the region bbox dimensions; points are finite numeric coordinates local to its top-left corner and inside this viewport. Across one region at most 4096 commands are allowed, only `{"moveTo":{"x":0,"y":0}}`, `{"lineTo":{"x":100,"y":0}}`, and `{"close":{}}`; each contour needs at least three distinct vertices and nonzero area and must close before the next move. Preserve all coordinates, ordering and winding. A hole uses opposite winding inside the same path; multiple paths do not subtract each other. No SVG/XML, formulas, curves, arbitrary commands or external path data are accepted. Use existing `fill` objects (`type: solid`, or `type: linear-gradient` with angle and ordered stops covering 0..1); relation paths require a non-null fill, and line may be null. A plain nonsemantic polygon uses `kind: shape`, `geometry: polygon`, `corner_radius: 0` and `paths` alongside the existing `fill/line/shadow` fields. Non-null shadows remain an explicit capability gap.

The independent v3 region review requires all five criteria: `visible-copy-transcription`, `complete-region-coverage`, `material-roles`, `faithful-geometry-appearance`, and `source-image-derived-relations`. The last checks that each relation is actually present in the bound image, with the correct endpoints or single-anchor meaning, and that no business relation is disguised as a nonsemantic shape. Hash and schema checks do not prove pixel semantics. Review changes invalidate downstream plans/results. Runtime reads actual OOXML path commands, fill, wrapping and copy, then reimports the exact PPTX to verify renders. Content, visual fidelity, editability, common rules, PowerPoint and human acceptance remain separate evidence.

## Native semantic editability

Keep titles, body, labels, facts, numbers, tables, charts, simple diagrams, connectors, business relationships, logos, and page markers native. Photos, screenshots, complex illustration, texture, and atmospheric background may be separate replaceable image layers. Prohibit whole-slide bitmap delivery, baked factual text, untraceable data, and decorative layers that prevent normal editing.

Source-note and other delivery requirements remain applicable where supported. If the data-only renderer cannot express a required chart, logo, source-note or other carrier, report the exact CapabilityGap and keep that delivery requirement unestablished. Current non-null shadows also fail before output because their SDK theme-effect representation is not yet faithfully verified. Never remove such effects, append unbound objects, or switch to another authoring script to satisfy a requirement.

The authoring tool and editability boundary remain fixed: use Codex Presentations
with `@oai/artifact-tool` as a JavaScript ES module; preserve the finalized `z_order` and object identities;
keep semantic objects native; keep image layers separate and replaceable; and target
`macos-powerpoint`. Image 2 owns page design before finalization. Once finalized, preserve its geometry, typography, gradients, decoration, material roles, and visible copy. Reconstruct core content natively and retain complex text-free decoration as separate replaceable images. Extraction and repair cannot redesign. There is no silent template fallback, content rewrite, or second PPTX compiler.
Every handoff must carry one `TargetBinding` with project/page/order, finalized-image SHA256, selected-visible-copy SHA256, material roles, accepted deviations, `design_authority=finalized-image`, and `conversion_mode=faithful-native`. File names, directory order, newest output, similarity, and prior frozen copy are never target identity. Missing or inconsistent binding, region mapping, dependency hash, or existing output is a pre-write rejection; deck-wide common rules may be checked but cannot rewrite a page-local finalized composition.

## Anchor build and G2

Run the exported `render()` from `scripts/image-led-native.mjs` with the exact `renderer_handoff` and trusted current project/runtime options. It preflights before SDK loading and output creation; a failure preserves its diagnostic output. Do not re-author pages in a separate script. The result remains `engineering-output-unassessed`.

Use the producer's normal Agent result channel with `{artifact_type: 'image-led-build-result', project_id, output: result}`. Runtime reads the producer ContextPack, actual PPTX and file hashes, native object identity/copy/appearance and current dependencies. `result.files` includes handoff, mapping, inspect, authoring/reimport proto and per-slide layout; `result.comparisons` includes aligned side-by-side, overlay and per-region differences. `handoff_sha256` is the actual handoff file hash.

Prepare a separate engineering reviewer task against the result ref. Its `image-led-result-review` contains `content`, `visual`, `editability`, `common-rules`, each with `passed/failed/not-established` and detail. Producer self-review, missing dimensions, stale result or unestablished dimensions cannot promote anchors. Submit only `{artifact_type: 'image-led-anchor-set', build_result_ref, four_dimension_review_ref}`; Runtime derives the native support evidence and current anchors. It never treats an automatic pixel score as visual approval.

Build difficult and content-complex native anchors from the full accepted contract and
the current handoff plan. The resulting `AnchorSlideSet` must declare and resolve the
same current `visual_compilation_plan_ref` as the task and ContextPack; `native_first_frozen`
alone is insufficient. Render and inspect every anchor; fix overlap, clipping,
wrapping, crop, font, connector, source-note, object, and editability defects while preserving the finalized design and copy. Reject incomplete source-region/output-object mappings, unauthorized changes, stale bindings, and failed fidelity checks before candidate publication. Compare each page against the exact finalized image using aligned overlays and critical-region crops, and compare all finalized visible copy. An old source-text check is not finalized-copy validation.
Validate the identical anchor PPTX in every `ReleaseTargetPolicy.required_target_ids`
target defined in `release-target-policy.md`. G2 remains blocked until every current
required row passes on the same PPTX SHA-256.

Deferred profiles are not Gate rows and do not imply pass, failure, lack of support, or compatibility.

## Full deck and G4

After G3, build the complete deck, render every page, inspect each page at full size, use a montage only for rhythm, run overflow/structure/source/editability checks, and repair all failures. Re-resolve the current policy, validate the identical final PPTX against every current required target, and create new final-PPTX evidence; never reuse a G2 anchor record. Bind the exact current policy ref into the delivery package and send that exact file through Codex chat before G4 confirmation.

Evidence levels stay separate throughout: mechanism implementation is not automated
verification; automated verification is not real-sample validation; real-sample
validation is not a target PowerPoint check; and a target check is not user visual
acceptance. A successful build, render, no-overflow result, or clean console never
closes the visual quality question by itself.
