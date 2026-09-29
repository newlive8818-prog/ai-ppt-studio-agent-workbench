# Image-led design and faithful native conversion

## Freeze the input

Start only after G0. Bind the current `ReadingDeckBlueprint`, audience, decision objective, brand, evidence, reading mode, environment, and editability boundary. Internal exploration may compare mechanisms, but the user does not choose an implementation technology or an internal G1/G2 direction.

Image 2 candidates remain editable design work until finalization. Once the user finalizes an exact image, its design is binding. Before that decision, reconcile visible copy, numbers, relations, and material roles against confirmed source content; freeze the reconciled copy with the exact image and accepted deviations. Image transcription is not factual evidence. After finalization, never silently replace that copy with an older blueprint or remove/add content. A page image alone is not an editable delivery.

## Semantic compilation and handoff order

The visual production order is fixed and one-way:

```text
Confirmed content and materials
-> Lightweight Visual Brief and common deck rules
-> Image 2 autonomous page design
-> Content reconciliation and exact user design finalization
-> Bound final image, visible copy, materials, and accepted deviations
-> Complete region/object mapping and faithful visual contracts
-> Deterministic VisualCompilationPlan and closed handoff
-> Codex Presentations faithful native conversion
-> Bound copy / visual fidelity / editability / cross-page / target checks
-> User judgment on the actual result
```

`VisualCompilationPlan` is the only current visual implementation plan. Old briefs,
design systems, contract sets, plans, anchors, and reviews remain readable as
immutable history but are classified `legacy / unassessed-by-v23`; they must not be
silently rebound to a new task. C2 retains `build-native-first` as the formal action name but dispatches Image-led projects through explicit compiler/handoff versions: historical v1 remains `image-led-faithful-compiler/v1` / `codex-presentations-image-led/v1`; a v2 input selection with versionless regions uses `image-led-faithful-compiler/v2` / `codex-presentations-image-led/v2`; an explicit v3 region inventory derives compiler/handoff v3 while retaining selected-copy/v2. Never strip version fields or downgrade a current v2 plan. The current plan alone is insufficient: Runtime revalidates selection, region review, source/material policy, result, and anchor identity. The action name grants no second design pass.

## C2 production entries

Use the existing public action/artifact/decision tools; Python remains the only business writer. Keep revisions current and use a prepared Agent task for each governed result.

1. After real G0, register the allowed material scope, obtain or reuse its valid host-confirmed authorization, and register the current input policy and each input pack. Reuse inventory/evidence/views; send exact copy, page goal, permitted materials and common rules. Never supply page geometry at this stage. The host command adapter must match the authorized receiver/model; missing capability blocks before queue creation.
For new v2 packs, preserve every current block ID, exact text and source order. Set `confirmed_visible_copy.title_target` to the exact title block, which need not be first; use standalone only for a genuinely independent title. Do not add metadata title to the visible items again, deduplicate equal strings, or supply an old page graph/body layout. The shared compiler derives full `selected_copy` with `title_item_id`, source identities, limitations and material uses. All customer semantic strings must be covered by the exact authorization scope.

`atoms` is the authorized available pool; `material_roles` records actual image use after transcription and independent source review. Current `required_atom_ids` must be empty because no resolvable required-material decision contract is implemented; synthetic subset checks do not establish that capability. Optional unused assets are omitted from the finalized binding, but every actually selected real material still needs full region/native coverage.

Reuse an existing valid scope/grant without another confirmation. For a newly registered scope, consume the actual receipt's `authorization_continuation.call`, which fixes `confirmationMode=verified-message-only`; add only a real applicable verified `userMessageRef`. Do not reconstruct a default allow-native call, invent a message or silently open a form. Missing verifier/reference is a capability gap, not revoked user consent. If continuation identity is unavailable, retain the successful registration and refresh the exact context before proceeding. This guidance does not install a host verifier or establish a grant.

2. Request `generate-slide-images` for one current pack. The production bridge first validates the pack version and matching transport capability; v2 needs preflight/v2 proving `image-led-image2-transport/v2` before queuing. It then executes the adapter and returns the exact image. Keep the returned `request_id`: on uncertain outcome use the same public action with `generationIntent="recover"`, `generationRequestId=request_id`, and `targetRefs=[]`. Recovery is read-only and does not resend, even after revision, scope, source or active-task changes or without adapter configuration. Omitted intent fields identify one stable default request for that exact pack and instructions; refreshing revision/command identity does not create another design. For an explicit user request to design another version, use `generationIntent="new"` with a fresh durable ID; retries reuse that ID. Valid existing scope remains sufficient, with no per-call approval or image-count limit. A returned image is preserved under its original request/claim; `generation_usability` describes current eligibility separately. A stale image may be inspected but cannot be promoted. Transcribe actual returned copy and materials into `image-led-candidate` through the same current task's Agent result; generation does not select it, and candidate intake rechecks eligibility.

For the existing-deck fast path, choose one declared media route before registration. `source-media-guided` sends exact authorized source-page images with replayed geometry and binds the independent engineering review to `[request_ref, response_ref]` plus `source-media-fidelity` and `source-media-role-placement`. `blank-media-slots` and `client-logo-gallery-20` send no source bytes; they require the exact local composition artifact and composed image in review and selection. A historical import remains immutable, but an otherwise sound historical composition may receive one bounded, reproducible `historical-design-source-replacement/v1` target before review: replace generated stand-ins with exact source media, explicitly classify unused source decoration, and limit masks/page-marker fixes to small named regions. Review the historical request, response, composition, and target image together and require `source-media-disposition`; bind only actually inserted media into TargetBinding. A completed Sunburst response cannot switch routes. Reject invented photos, redrawn logos, dropped materials, or role inversion and create a fresh Sunburst request ID only after superseding the unselected completed result.

After a host restart or interrupted call, inspect an existing-deck request through `recover_existing_deck_image_request` using the same request ID. This is a read-only persisted-status lookup with no adapter, network call, resend, revision increment, artifact-head change, or automatic candidate/selection. Preserve `started` and `unknown` as unresolved; accept `completed` only when the stored exact response is returned. If no persisted response exists, stop with the missing-record error rather than issuing another request.
For an actual pre-selection discrepancy, queue `review-visual-engineering` with the exact completed `generation_response_ref` as its only target. Its narrow context binds the original PNG, original v2 pack, complete copy/materials/common rules and current authorization. Submit `image-led-content-diagnostic/v1` as `kind="visual-contract"` through that reviewer task, without first claiming a correct candidate. The closed result contains `artifact_type="image-led-content-diagnostic"`, `diagnostic_version`, `project_id`, `pack_ref`, `generation_response_ref`, `slide_id`, `page_order`, exact `image_sha256` and `image_size`, `reviewer_kind="engineering"`, `reviewer_role="visual-engineering-reviewer"`, `excluded_content_check={result,detail}`, and `issues`. Only an actual independent `excluded_content_check.result="passed"` permits returning this exact generated image to Image 2. Failed or unestablished exclusion may be recorded but blocks repair before queuing, including when the requested correction would remove excluded content.

Issue forms are closed: `missing-item` names an existing `item_id`; `replace-item` names an existing item and original-pixel `bbox`; `remove-extra-text` has original-pixel `bbox` and local-only `observed_text`; `common-rule` has `bbox` and one original key (`typography_tokens`, `color_tokens`, `fallback_fonts`, `title_bar`, `background`). Bboxes are `[x,y,width,height]` in the actual original image, never guessed or copied from synthetic examples. They locate differences and do not dictate the new composition. No replacement prose, new style string or free task instructions are sent. Original common rules are not an exclusive color palette unless they explicitly say so.

This repair sequence is historical Image 2 behavior and is not available in the current Sunburst-only minimal loop. For current Sunburst, create a fresh explicit full-generation request with a fresh `generationRequestId` and the unchanged confirmed source inputs; do not attach the old repair diagnostic as a transport target or fall back to Image 2. For an explicitly resumed historical Image 2 repair only, queue `generate-slide-images` with this current diagnostic ref as its only target, `generationIntent="new"`, and a fresh explicit `generationRequestId`. Preflight must explicitly support `image-led-image2-repair-transport/v1`. The first image is the exact completed source; original input materials follow with unchanged bytes, order and roles. Optional assets still need not all appear in the output. The unchanged original v2 payload remains the copy/material authority; the diagnostic observation and edit target are not new facts or MaterialAtoms. A historical completed source may be selected explicitly even after a newer image exists. Every repair rechecks current inputs and grants; it never changes the old grant. Recover the same request ID read-only after unknown, without resending or claiming that the model received/executed the feedback. The returned image needs a fresh complete check, candidate, source review and selection; it inherits no old approval, regions or TargetBinding. A completed repair can be diagnosed again using its own exact output as the next target.

3. Obtain each independent `image-led-review` with `review_kind=candidate-source`. Submit exactly one reviewed candidate for every current blueprint page, in blueprint order, as `image-led-selection-proposal`; C2 projects still have three pages, while a C3 pilot may have six. Then obtain the real trusted selection decision through the existing human-decision tool. Do not submit a fabricated selection or reuse a test signer.
4. Transcribe the finalized images into `image-led-region-inventory`, then run an independent engineering task submitting `image-led-region-review`. Complete copy/material/region coverage and faithful geometry/appearance must pass before formal visual contracts. For finite polygons, source-image-derived relationship paths or natural wrapping, use the explicit native v3 contract in [presentations-handoff.md](presentations-handoff.md#explicit-native-v3-regions): keep selected-copy/v2 unchanged, require `source-image-derived-relations` as the fifth region review criterion, and retain v3 through compiler/handoff/result. A single-anchor feedback symbol is not an invented two-endpoint return edge. Native v3 does not change the Image 2 transport/input versions.
5. Register brief and design with current selection identity; register the full contract set with current selection/regions and exact selected copy. Runtime atomically derives the independent-version plan. Submit convergence and independent G1 aesthetic review, then pass G1 through the normal entry.
6. Request `build-native-first` for exactly the current plan. Follow `presentations-handoff.md`: pass only `layers.visual_handoff.renderer_handoff` to the data-only renderer. Keep its governance wrapper for Runtime verification.
7. Submit the actual `image-led-build-result` through that producer task. Obtain a separate `image-led-result-review` with all four dimensions; then submit minimal `image-led-anchor-set` promotion. If the current build has more than three pages, explicitly name exactly three distinct `slide_ids` in their build order for the professional-review anchors. The full reviewed PPTX, six-page renders, and PPTX hash remain the same result; missing, unknown, repeated, or reordered IDs block promotion. A three-page build keeps its original no-argument path. No caller-provided editability flag, hash, or self-review replaces this chain.
8. Run the existing G2 aesthetic/engineering reviews and real required target checks on the same PPTX. Only then publish the existing visual review. G3 remains a real user decision. C2 engineering automation does not authorize C3 or establish customer acceptance.

Changed selection, source/region review, contracts, convergence, results or current authorization invalidate their dependent evidence. Resolve current state again; never carry old passed Gates forward. Source implementation does not imply the installed plugin or real provider is configured.

The handoff is a read-only projection of registered finalized inputs. Every source region maps to native objects or a replaceable crop; every output object has a finalized origin or an accepted revision. Preserve positions, proportions, font hierarchy, gradients, spacing, decoration, material roles, and relations. Resolve visible copy from the reconciled finalized content artifact. Earlier source artifacts remain provenance, not a silent replacement for finalized wording. The handoff never becomes an independently editable second truth.

Before finalization, the design philosophy is deliberately non-forcing. A page may use cinematic or
photographer-like framing, preserve a prominent directory or chapter title, vary
reading rhythm, or choose a different composition when its page contract justifies
it. After finalization, these choices belong to the exact approved image and cannot be changed by extraction or native construction. These are design-stage review prompts and evidence questions, not a mandate to apply one
template. The contract must still explain the page goal, first visual focus, evidence
to-claim relationship, reading path, composition, density, and cross-page rhythm.

Treat the following as anti-pattern evidence, not as a checklist to satisfy by adding
decoration: equal-weight title/cards/icons on every page; average allocation with no
focal point; filler rules, gradients, glow, or meaningless icons; unrelated hero
images; too many similar cards; text merely placed inside shapes; one composition
repeated across the deck; hierarchy driven only by font size; accent-color sprawl;
charts without a viewpoint; tidy but tensionless pages; missing chapter rhythm; or a
technically clean render that reads poorly in a real meeting. Review these signals before design finalization. After finalization, a reconstruction agent must not invoke them to redesign an approved page; flag a concrete concern and preserve the approved version until an explicit revision decision.

## Complete contract before anchors

Create the full `DeckDesignSystem` and every `SlideVisualContract`. The Deck system defines theme proposition, composition grammar, grid, density rhythm, typography, color, imagery, recurring geometry, page families, native/bitmap routing, accessibility, fallback, and binary acceptance rules. Every slide contract describes the exact finalized image and binds its reconciled copy, source/material refs, actual geometry, hierarchy, reading order, complete regions, relationships, imagery, token application, editability, and accepted deviations. Contract extraction may not invent a new layout or reset copy to an older source. A technical limitation is reported with a concrete difference, not treated as permission for fallback.

G1 is internal and passes only when the current full contract resolves and every applicable check passes.

## Faithful native conversion and G2

Use Codex Presentations to convert the finalized difficult and content-complex pages into native editable objects. Keep complex text-free decoration as independently replaceable image layers. Do not rebuild the page as a convenient card template, flatten gradients, resize icons, change headers, remove relations, replace material, or rewrite text. If a technical fix would change the finalized appearance or content, report the exact difference and obtain the scoped revision decision instead of silently changing it.

Reject missing/stale/cross-page design bindings, incomplete region coverage, old-copy substitution, unauthorized geometry or asset changes, ungrounded output objects, whole-slide bitmap delivery, failed checks, and reuse of old-version evidence. Compare exact finalized copy, aligned side-by-side/overlay renders, and critical regions; a green old-text Counter or a global similarity score is insufficient. These checks must be implemented in C1 experiments and C2 production validators, not asserted from a prompt.

Resolve the immutable current `ReleaseTargetPolicy` and bind its exact artifact ref into visual lineage. Validate semantic fidelity, aesthetics, PowerPoint engineering, target rendering, fonts, and editability for each `required_target_ids` row. All current rows must bind the same anchor PPTX hash. One missing, failed, stale, or different-hash row blocks G2. Deferred targets are not Gate rows and never imply compatibility.

## Visual professional review and G3

After G2, open the current `visual-professional` ReviewSession in the Codex built-in Browser. Keep two top-level views:

1. Anchor results: show the real anchor images, accept drag-created rectangle regions, keep drafts across slides, and submit multiple comments as one immutable `AnchorFeedbackBatch`. A point-like click creates nothing.
2. Complete visual contract: render the Deck system, anchor identity, current required-target identities, and every slide contract in order. Save field marks and selected-text marks as one `VisualContractReviewMarkSet`.

Keep the two feedback types, their current slots, and their persistence actions separate. After either save, report persistence, host notification, and AI receipt independently. G3 requires an explicit user judgment bound to the current visual contract, source version, revision, and review Batch/mark identities; saved feedback alone never confirms it.

The accepted v2.8 production frontend is the binding user-surface contract:

- use one compact top bar, with no project badge and no persistent product navigation;
- keep the slide directory in a left overlay drawer and contract marks in a right overlay drawer so opening either does not alter document geometry or scroll position;
- do not show a persistent right-side feedback panel;
- show no feedback-batch panel in the empty state; after real feedback exists, place one compact batch below the canvas;
- reveal text-range marking only contextually after a real selection;
- keep the two top-level views separate and make the complete contract readable in source order;
- preserve visible contract semantics for `核心主张`, `页面可见文案`, `讲解备注`, and `来源引用`.

These frontend facts do not prove Runtime persistence, Review Bridge behavior, MCP wiring, host open/notification, AI receipt, or G3. Review marks and feedback batches never pass G3; explicit current user judgment is still required.
