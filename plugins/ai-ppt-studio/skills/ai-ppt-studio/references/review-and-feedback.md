# Professional review and feedback

## Source-bound review

Content and visual review share infrastructure but keep separate ReviewSessions, source versions, revisions, drafts, writes, and receipts.

- `ReadingDeckBlueprint` remains the complete internal governance authority. Content React projects only the accepted `ContentReviewPageViewModel`: page goal, desired customer judgment, actual page text, optional real material/page visuals, and one current `PageDecision`. It must not project speaker notes, evidence identity/source-entry UI, analysis/proposal catalogs, mappings, cross-page relations, reading-quality fields, or every backend contract field.
- Zero-image pages omit the image region, image title, and empty-state filler and expand “页面实际文字” to the full row. They are valid in every material mode and do not automatically mean insufficient evidence.
- Visual review has two views. Anchor results accept multiple rectangle-region comments in one immutable `AnchorFeedbackBatch`; the complete contract accepts field or selected-text marks in one `VisualContractReviewMarkSet`.

React must project only fields required by the accepted frontend ViewModel, never invent a passed status, and never store business state locally. A write reports persistence only. Host open, host notification, and AI receipt require their own trusted receipts. None confirms G0 or G3.

`save_content_page_decision` is a silent page save: it changes no content, triggers no concentrated Agent work, and confirms no Gate. Require a comment for `modify | evidence | merge-or-delete`. Only a complete immutable `ContentReviewBatch` triggers concentrated processing. The chief then saves one whole-deck revision plan, the user confirms it before change, and every new source version starts full review with no inherited approvals.

Visual text marks preserve `field_anchor`, exact selected text, prefix, suffix, comment, and source version. A stale anchor must conflict rather than float to similar text.

## Change scope and recovery

Classify feedback as whole deck, chapter/page family, page, or element. Preserve raw wording separately from diagnosis and recommended action. Bind target refs, preserve refs, previous/current versions, source version, scope, evidence, decision, and result.

- Mission, audience, material, fact, narrative, or content-identity change reopens G0.
- Full visual-contract change reopens G1.
- Native/editability/required-target defect reopens G2.
- User visual judgment change reopens G3.
- Full-deck or delivery defect reopens G4 unless its root cause belongs earlier.

Reopen only the earliest affected Gate, lock its downstream chain, preserve unrelated accepted work, and retain immutable history. Revision or source conflicts preserve drafts; a network or save failure cannot display a saved state.

## Learning boundary

Govern feedback before creating a change set or reusable experience. One project reaction is not universal, but one clear valid reaction may immediately create or update a bounded `same-type` mechanism and influence the current remaining work. Reuse only sanitized, scoped `same-type` or `global` mechanisms with evidence, counterexamples, evaluation, and rollback.

After every G4, formal close, or abort, automatically create `ProjectExperienceRetrospective`. Sanitize customer facts and assets before reusable persistence. Retrospective failure writes a pending/retry record; counterexamples may narrow, split, demote, disable, or roll back a newer immutable experience version.
