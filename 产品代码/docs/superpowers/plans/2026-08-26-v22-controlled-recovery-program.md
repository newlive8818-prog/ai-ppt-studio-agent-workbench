# AI PPT Studio v2.2 Controlled Recovery Program

> **Execution rule:** This is the program-level recovery plan. Every implementation slice requires its own `codex/` feature branch and linked worktree, its own design and implementation plan, TDD evidence, exact-file staging, verification, review, rollback point, and completion report. The recovery integration branch is not a development workspace.

**Program goal:** Recover the complete AI PPT Studio v2.2 product chain from the clean recovery baseline without merging the quarantine snapshot, while keeping every core capability independently testable, reviewable, and reversible.

**Authoritative baseline:** `codex/v22-recovery-integration-20260825` at `b7759b326b1ab22957616f66c7a179014a71e9db` when this program was written.

**Product chain:** Mission and materials -> presales evidence and decision context -> problem/solution fit -> reading deck blueprint -> two content hard gates -> chief repair -> full-deck content review -> G0 -> visual production -> visual professional review -> G3 -> native editable PPTX and target evidence -> delivery -> G4 -> experience retrospective.

---

## 1. Non-negotiable repository boundaries

1. The quarantine checkout and branch remain read-only. No complete merge or cherry-pick of the quarantine snapshot is allowed.
2. The recovery integration worktree receives only separately reviewed and explicitly authorized integrations. Business development does not happen there.
3. One core recovery unit maps to one feature branch and one linked worktree.
4. A downstream worktree is created only after its direct upstream slice reaches its engineering exit gate. Dependent worktrees are not pre-created in bulk.
5. Each feature branch records its exact parent commit as its rollback point. The slice delta is always the commits after that point.
6. Do not use `git add .`. Stage only the files listed by the slice plan.
7. Do not amend, merge, push, release, install, or delete preservation branches unless separately authorized.
8. Content review, visual review, MCP, delivery, and experience files must not be mixed merely because one test exposes an adjacent issue.
9. `implemented`, `committed`, `verified`, `reviewed`, `integrated`, `released`, and `user-accepted` remain separate facts.
10. Automated engineering acceptance may advance implementation slices under the user's 2026-08-26 authorization, but G0, G3, G4, external actions, release, and facts that explicitly require a real user or host action cannot be synthesized.

## 2. Current verified recovery state

### 2.1 Completed recovery foundations

| Unit | Current evidence | Status boundary |
|---|---|---|
| Quarantine and recovery baseline | `94f0f60` and recovery document | Recovery source established; quarantine is not an integration source |
| Bundled MCP Python Runtime | `6c458f7` | Implemented, committed, verified, present on recovery line |
| ReviewSession authority service | `a91bed3` through `b7759b3` | Python/Node authority and truthful status service recovered |
| Content review frontend and narrow projection | existing recovery commits including `78866ec` lineage | Local engineering implementation exists; real customer host chain and G0 are not proven |
| Optional content material visuals | existing recovery commits | Zero-image local behavior implemented; real mixed-material chain remains unproven |
| Visual review frontend and narrow projection | `33ef088` lineage and `9bc90f9` | Current UI was viewed and accepted by the user on 2026-08-26; runtime closure and G3 are not proven |

### 2.2 Newly discovered integration defect

The current ReviewSession projection can produce:

```text
host_notification_status = pending
```

The current Widget review-surface validator still accepts only the older subset:

```text
not-requested | sent | failed
```

As a result, an authoritative current visual preview is rejected before the accepted visual page renders. A temporary UI-only preview was used for visual acceptance by changing only the temporary preview value to `not-requested`; this is not runtime evidence. This defect must be closed before typed catalog or downstream real-review claims.

## 3. Worktree topology and dependency policy

### 3.1 Permanent roles

| Worktree role | Branch | Allowed activity |
|---|---|---|
| Quarantine preservation | `codex/quarantine-mixed-worktree-20260825` | Read-only evidence |
| Recovery integration | `codex/v22-recovery-integration-20260825` | Read-only development base and future authorized integration |
| Program governance | `codex/v22-recovery-program-plan-20260826` | Program plan and recovery status only |

### 3.2 Feature worktree lifecycle

For every feature slice:

```text
resolve approved parent HEAD
-> create feature branch and linked worktree
-> startup audit
-> feature design and self-review
-> implementation plan and self-review
-> RED tests
-> minimal implementation
-> local verification
-> full relevant regression
-> independent code review
-> exact-file commit(s)
-> completion and rollback report
-> wait at integration boundary when merge is not authorized
```

If an upstream slice is not integrated because merge remains unauthorized, dependent implementation does not silently start from the old recovery integration HEAD. It either waits or is explicitly created as a stacked branch from the verified upstream feature HEAD, with the parent identity recorded. A stacked branch must still keep only its own delta in its worktree and completion report.

## 4. Ordered recovery slices

### Phase R - Recovery contract closure

#### R0 - Current visual UI acceptance evidence

**Recommended branch/worktree:** `codex/slice-visual-ui-acceptance-evidence-20260826`

**Purpose:** Bind the user's 2026-08-26 acceptance to the current rendered frontend and current recovery HEAD without claiming runtime, host, AI, or G3 success.

**Allowed scope:** Product baseline status lines and a dedicated validation record. No React, Runtime, MCP, Review Bridge, or visual redesign.

**Exit gate:** The evidence names the accepted HEAD, displayed surfaces, local-preview limitation, temporary compatibility normalization, and explicit non-acceptance of Runtime/G3.

#### R1 - ReviewSession consumer compatibility

**Recommended branch/worktree:** `codex/slice-review-session-consumer-compat-20260826`

**Purpose:** Align Node/Widget/preview consumers with the completed ReviewSession authority contract.

**Allowed scope:** ReviewSession TypeScript types, review-surface validation, preview fixtures, Node/Widget consistency tests, and directly required documentation. Do not change Python ReviewSession business behavior or visual layout.

**Required proof:**

- a failing test reproduces authoritative `pending`, `unavailable`, `rejected`, and `unverified` consumer handling;
- current Python-produced content and visual projections pass the frontend validator without temporary normalization;
- invalid or unknown status values still fail closed;
- accepted content and visual DOM structure is unchanged;
- full Python, Node, Widget, typecheck, and build regressions pass.

**Exit gate:** The unmodified authoritative visual preview renders in Browser with no framework error and no relevant console error. This is engineering evidence, not G3.

#### R2 - Typed MCP public catalog

**Recommended branch/worktree:** `codex/slice-mcp-typed-catalog-20260826`

**Purpose:** Harden the existing public MCP surface without changing its size or business meaning.

**Fixed public surface:** 43 tools: project 15, content 15, review 4, visual 3, delivery-experience 6. `read_ai_ppt_project_asset` remains the only descriptor whose operation is `null`.

**Architecture:** `mcp/tool-catalog.mjs` is the only public descriptor source. Five domain tool files own their schema and handler maps. The server consumes the catalog and domain registrations; it does not maintain a second public list.

**Required proof:** exact names, groups, handlers, operations, schema identities, uniqueness, group completeness, frozen descriptors, stable canonical hash, local-asset exception, Python operation parity, and server `listTools()` parity.

**Forbidden scope:** No Python ReviewSession behavior, content or visual UI, Widget, Review Bridge HTTP, or new public tools.

### Phase C - Presales content production authority

#### C0 - Authoritative content domain objects

**Recommended branch/worktree:** `codex/slice-presales-content-domain-objects-20260826`

**Purpose:** Implement validated, immutable versions of `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and the new `ReadingDeckBlueprint`.

**Required proof:** schema validation, content-identity enforcement, source and evidence binding, material mode behavior, revision/idempotency, immutable artifact history, and no invented facts.

**Exit gate:** All four objects can be created and read through internal application services without old framework or expansion authorization.

#### C1 - Presales chief and production state machine

**Recommended branch/worktree:** `codex/slice-presales-chief-orchestration-20260826`

**Purpose:** Make the presales chief the single content production and repair owner.

**Required proof:** three material modes, deterministic transitions, on-demand consultant boundaries, removal of fixed five-role production dependencies, no old dual-authorization precondition, bounded repair attempts, and truthful capability gaps.

**Exit gate:** Mission confirmation can drive the four-object chain to a reviewable blueprint or a specific governed stop reason.

#### C2 - Two content hard gates and repair loop

**Recommended branch/worktree:** `codex/slice-content-hard-gates-and-repair-20260826`

**Purpose:** Implement the fact/evidence gate and the presales-reading/customer-position gate as isolated reviewers; only the chief can repair.

**Required proof:** pass/fail-only gate records, exact evidence and repair requirements, neutral-title deterministic checks, reviewer non-edit authority, failed-gate repair and re-run, stale-source rejection, and independent-agent evidence where actually used.

**Exit gate:** No blueprint reaches content review until both current-source gates pass.

#### C3 - Full-deck review backend and G0 closure

**Recommended branch/worktree:** `codex/slice-content-review-runtime-g0-20260826`

**Purpose:** Connect the already accepted content review frontend to the new content objects, immutable batch, whole-deck revision plan, new version, complete re-review, and truthful G0 context.

**Required proof:** current ReviewSession, page decisions, immutable completed batch, withdrawal/freeze rules, chief revision proposal, trusted plan confirmation, new blueprint version, full re-review, current-source G0, downstream invalidation, mixed/no-image/material ordering, host/AI receipt separation, and long-document recovery.

**Exit gate:** An isolated real-like project reaches `G0=user-reviewable`; G0 itself remains a real trusted-user action and is not self-synthesized.

### Phase V - Visual production, professional review, and PPTX

#### V0 - Visual production authority and G1/G2 recovery

**Recommended branch/worktree:** `codex/slice-visual-production-g1-g2-20260826`

**Purpose:** Bind visual production to the current G0 content source, Deck Design System, three real native-first anchors, complete Slide Visual Contracts, and internal quality gates.

**Required proof:** exact source lineage, three non-placeholder anchor images, native-first PPTX identity, Image 2 limited to replaceable imagery, current G1/G2 evidence, stale cleanup, and no visual production before G0.

**Exit gate:** A current visual contract and exact three-anchor set are ready for professional review; no G3 claim.

#### V1 - Visual review Runtime/Bridge closure and G3 readiness

**Recommended branch/worktree:** `codex/slice-visual-review-runtime-g3-20260826`

**Purpose:** Connect the accepted visual UI to real ReviewSession, Browser/Review Bridge, Python writes, host notification, and AI receipts.

**Required proof:** rectangle selection, multiple feedback items, immutable `AnchorFeedbackBatch`, contract-field and selected-text `VisualContractReviewMarkSet`, revision conflict, stale zero-write, draft recovery, notification retry, AI receipt truthfulness, 21+ page contract stability, and accepted UI preservation.

**Exit gate:** The current visual source can reach `G3=user-reviewable`; G3 itself requires a real trusted-user action and is not self-synthesized.

#### V2 - Native editable PPTX and target quality evidence

**Recommended branch/worktree:** `codex/slice-pptx-production-and-target-evidence-20260826`

**Purpose:** Produce, render, inspect, and repair the exact current native editable PPTX using Codex Presentations and the active `ReleaseTargetPolicy`.

**Required proof:** same PPTX hash across build and evidence, slide-level semantic/visual/engineering checks, full-deck rhythm checks, editability, target-render identity, stale evidence invalidation, and repair loop.

**Exit gate:** The exact current build is delivery-ready for all currently required targets. Build success alone is not delivery or user acceptance.

#### V3 - Delivery receipt and G4 readiness

**Recommended branch/worktree:** `codex/slice-delivery-receipt-g4-20260826`

**Purpose:** Build the delivery package, record actual chat delivery, expose truthful delivery status, and preserve retry identity.

**Required proof:** package/build/hash binding, `ChatDeliveryReceipt`, sent/failed separation, retry without rebuilding a passing PPTX, current policy evidence, and no simulated send success.

**Exit gate:** A genuinely sent current package reaches `G4=user-reviewable`; G4 itself remains a real user acceptance action.

### Phase X - Experience, single-entry product surface, and closure

#### X0 - Same-type/global experience model

**Recommended branch/worktree:** `codex/slice-experience-two-level-model-20260826`

**Purpose:** Replace candidate/personal mixed paths with same-type/global content and visual experience governance.

**Required proof:** de-identification, matching, exact version application, evaluation, two-type-signature promotion, counterexample degradation, rollback by new version, and prohibition on changing policy/facts/permissions.

#### X1 - Project retrospective

**Recommended branch/worktree:** `codex/slice-project-experience-retrospective-20260826`

**Purpose:** Trigger project-level retrospective only after G4, close, or abort; support retry and index update without blocking G4.

**Required proof:** completion/close/abort triggers, pending and retry semantics, no premature retrospective, de-identification, and immutable provenance.

#### X2 - Conversation-only entry and legacy surface retirement

**Recommended branch/worktree:** `codex/slice-conversation-entry-legacy-retirement-20260826`

**Purpose:** Make the Codex conversation the only main entry, keep only on-demand content/visual review pages, and retire five-space navigation, project dashboard, persistent product sidebar, and old delivery pages.

**Required proof:** four truthful conversation states, material access, review handoff, production/delivery projection, no hidden second source of truth, historical read-only compatibility, Skill alignment, and no accepted review UI regression.

#### X3 - End-to-end recovery acceptance

**Recommended branch/worktree:** `codex/slice-v22-end-to-end-acceptance-20260826`

**Purpose:** Exercise the complete current product chain using real-like material-backed, mixed-evidence, and proposal-led projects, then perform release preflight.

**Required proof:** full automated regression, Browser handoffs, long content/visual documents, conflict and recovery cases, Presentations/PPTX evidence, delivery receipts, experience triggers, package verification, installation verification if authorized, and a fresh-task capability probe.

**Exit gate:** Produce an acceptance report that explicitly separates implemented, committed, verified, integrated, installed, released, and user-accepted facts. It may list `CapabilityGap`, `NotRun`, or `awaiting-real-user-action`; it must not convert them to pass.

## 5. Dependency graph

```text
R0 acceptance evidence

R1 ReviewSession consumer compatibility
  -> R2 typed MCP catalog
      -> C0 content domain objects
          -> C1 presales chief
              -> C2 hard gates
                  -> C3 content review backend / G0 readiness
                      -> V0 visual production / G1-G2
                          -> V1 visual review closure / G3 readiness
                              -> V2 PPTX and target evidence
                                  -> V3 delivery / G4 readiness

C1/C2/C3 and V1/V3 outcomes
  -> X0 two-level experience
      -> X1 retrospective

C3 + V1 + V3 + X0/X1
  -> X2 conversation-only entry and legacy retirement
      -> X3 end-to-end recovery acceptance
```

R0 is documentation-only and can be completed independently. All other arrows are hard creation gates for downstream implementation worktrees unless an explicit stacked-branch exception records the verified upstream HEAD.

## 6. Standard engineering acceptance for every code slice

Each slice plan selects the applicable subset, but cannot omit a relevant layer:

1. RED: focused failing tests prove the missing behavior or reproduced defect.
2. GREEN: focused tests pass with the minimum implementation.
3. Python: complete current Python suite when Python/runtime contracts are touched.
4. Node: complete Node suite when MCP, Review Bridge, packaging, or server contracts are touched.
5. Widget: complete Widget suite when types, projections, Router, review pages, or UI behavior are touched.
6. TypeScript: `npm run typecheck` for TypeScript contract changes.
7. Build: `npm run build` for MCP package or Widget changes.
8. Browser: required for rendered review pages, handoff, long documents, console health, and interaction evidence.
9. Package verification: required for release-manifest, plugin, Runtime bundling, or Skill changes.
10. Git: `git diff --check`, exact staged diff review, clean post-commit status, and recorded rollback commit.
11. Independent review: verify requirements, scope isolation, error semantics, tests, and no unrelated edits.

## 7. Program stop conditions

Autonomous execution pauses only when one of these conditions occurs:

- a real G0, G3, or G4 user action is required;
- an external send, install, release, OAuth/permission, merge, push, or other separately prohibited action is required;
- authoritative baselines conflict in a way that changes product scope;
- the same blocking condition prevents progress after safe alternatives are exhausted;
- verification exposes an architectural decision not covered by the current slice design;
- completing the next step would require changing another slice's accepted surface or files.

Routine design decisions, test fixes inside the current slice, local builds, temporary previews, and engineering acceptance do not require intermediate user confirmation under the user's 2026-08-26 authorization.

## 8. Immediate next action after this program plan

1. Complete and commit this program plan in the program-governance worktree.
2. Create R0 as a documentation-only acceptance-evidence worktree from the recorded recovery HEAD.
3. Create R1 from the correct verified parent and close the ReviewSession consumer incompatibility found in the live visual preview.
4. Only after R1 exits cleanly, recreate or rebase the currently empty R2 worktree from the verified parent; do not implement typed catalog on the stale pre-R1 base.
5. Continue through the dependency graph, creating one worktree at a time and preserving the no-merge/no-push boundary.
