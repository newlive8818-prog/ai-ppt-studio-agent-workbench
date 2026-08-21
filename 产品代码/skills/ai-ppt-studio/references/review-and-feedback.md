# Professional review and feedback

## Source-bound review

Content and visual review share infrastructure but keep separate ReviewSessions, source versions, revisions, drafts, writes, and receipts.

- Content review shows the complete `ReadingDeckBlueprint`, every page's visible copy and notes, evidence bindings, identities, relations, and one current `PageDecision`.
- The content evidence layer opens source material read-only and writes no review decision.
- Visual review has two views. Anchor results accept multiple rectangle-region comments in one immutable `AnchorFeedbackBatch`; the complete contract accepts field or selected-text marks in one `VisualContractReviewMarkSet`.

React must project every current contract field, never invent a passed status, and never store business state locally. A write reports persistence only. Host open, host notification, and AI receipt require their own trusted receipts. None confirms G0 or G3.

## Change scope and recovery

Classify feedback as whole deck, chapter/page family, page, or element. Preserve raw wording separately from diagnosis and recommended action. Bind target refs, preserve refs, previous/current versions, source version, scope, evidence, decision, and result.

- Mission, audience, material, fact, narrative, or content-identity change reopens G0.
- Full visual-contract change reopens G1.
- Native/editability/required-target defect reopens G2.
- User visual judgment change reopens G3.
- Full-deck or delivery defect reopens G4 unless its root cause belongs earlier.

Reopen only the earliest affected Gate, lock its downstream chain, preserve unrelated accepted work, and retain immutable history. Revision or source conflicts preserve drafts; a network or save failure cannot display a saved state.

## Learning boundary

Govern feedback before creating a change set or reusable experience. One project reaction is not universal. Reuse only a sanitized, scoped `same-type` or `global` mechanism with evidence, counterexamples, evaluation, and rollback.
