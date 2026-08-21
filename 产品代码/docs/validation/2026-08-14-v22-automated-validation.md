# AI PPT Studio v2.2 automated validation

Updated: 2026-08-15 (Asia/Shanghai)

## Evidence boundary

This record covers development-only automation in the isolated `codex/v22-unified-runtime` worktree and temporary Runtime. It is not formal customer, host, Browser, Codex Presentations, Microsoft PowerPoint, G0, G3, or G4 acceptance.

- Source worktree: `/private/tmp/ai-ppt-v22-TmBomR`
- Source base: `3998a9694cd9c86cc3bf97b45de294c85a57109e`
- Fresh managed test workspace: `/private/tmp/ai-ppt-v22-managed-probe.ieFRJG`
- Fresh three-mode E2E report: `/private/tmp/ai-ppt-v22-managed-probe.ieFRJG/projects/e2e-report.json`
- Local UI report: `output/playwright/v22-ui/v22-ui-acceptance.json`
- No commit, merge, stash mutation, cherry-pick, push, release installation, formal plugin update, or real-project write was performed.

All automated fixture results below keep `proofEligible: false` for real host, Browser, Presentations, PowerPoint, and customer evidence. Fixture Gate statuses prove the mechanism chain only; they are not real user Gate confirmations.

## Fresh automated evidence

| Area | Command or evidence | Fresh result | Proof scope |
|---|---|---:|---|
| Diff hygiene | `git diff --check` | passed | Working-tree whitespace/conflict markers only |
| Type safety | `npm run typecheck` | passed | Static TypeScript only |
| Python syntax | AST parse of `src/**/*.py` | 88 files parsed | Static Python syntax only |
| Node syntax | `node --check` for `mcp`, `scripts`, and `tests` | 26 MJS files passed | Static JavaScript syntax only |
| Python full regression | `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests` | 337 passed | Python unit/integration fixtures only |
| Node full regression | `npm run test:node` | 41 passed | MCP, catalog, release and loopback Review Bridge fixtures |
| Widget full regression | `npm run test:widget` | 18 passed in 6 files | React/Vitest fixtures only |
| Production bundle | `npm run build` | passed | Local self-contained HTML bundle only |
| v2.2 local UI | `npm run accept:v22-ui` | passed | Local Playwright preview only |
| Public MCP probe | temporary `AI_PPT_WORKSPACE_CONFIG` and `AI_PPT_PROBE_PROJECT` | 44 unique tools | Isolated stdio MCP capability only |
| Three material modes | isolated Runtime E2E | 3 modes passed | Deterministic mechanism chain only |
| Baseline links | four Markdown baselines | 17 relative links, 0 missing | Repository link integrity only |
| Prototype reference | `prototypes/07-visual-anchor-chat-collaboration-prototype.html` | exists | Repository artifact presence only |

## UI regression and long-text correction

The local UI report covers:

- content full-deck review at 760, 1000, and 1440 px;
- visual professional review at 760, 1000, and 1440 px;
- read-only evidence opening and return inside the parent content review;
- 60-page content and 120-page visual long-document completeness;
- body and document widths equal to the checked viewport widths;
- zero captured console errors in all six screenshot states;
- the anchor-results to complete-visual-contract tab interaction.

Final visual QA found a real defect that the earlier page-width assertion missed: at 760 px, `.visual-professional-page { overflow-x: clip; }` hid long `artifact://...` values instead of wrapping them. A new regression assertion now scrolls each lazy visual contract into view and checks relevant `code`, `p`, `li`, and `dd` nodes for `scrollWidth > clientWidth + 1`.

The new assertion was verified RED before the production fix. It reported 11 clipped nodes, including editability evidence, native PPTX, preflight render, visual-contract-set, and material-finding references. The production correction is one inherited rule on `.visual-contract-document`: `overflow-wrap: anywhere`. The same UI acceptance then passed GREEN at 760, 1000, and 1440 px. `content-visibility: auto` and its intrinsic-size placeholder remain intact for long-document performance.

The UI report explicitly records:

```json
{
  "proofEligible": false,
  "realHostEvidence": false
}
```

Its deterministic seed contains no reusable customer facts. Repository Playwright was used after the built-in Codex Browser refused the local `file://` preview under its URL-safety policy; this fallback is not recorded as real Browser evidence.

## Three-mode Runtime E2E

The fresh managed workspace contains one independent schema 3 fixture project for each approved material mode:

| Material mode | Final revision | Fixture Gate mechanism | Feedback persistence | AI receipt |
|---|---:|---|---|---|
| `material-backed` | 56 | G0–G4 fixture chain passed | saved | pending |
| `mixed-evidence` | 56 | G0–G4 fixture chain passed | saved | pending |
| `proposal-led` | 55 | G0–G4 fixture chain passed | saved | pending |

Each mode exercises Mission and material identity, the four authoritative content objects, both non-compensable content gates, content ReviewSession, per-page decisions, Batch, revision plan, new blueprint and G0 mechanism, visual contracts and anchors, both feedback types, G3 mechanism, delivery package, chat-delivery fixture, G4 mechanism, and `ProjectExperienceRetrospective`.

The report fixes all of the following to `false`: `proofEligible`, `realHostEvidence`, `realPresentationsEvidence`, and `realPowerPointEvidence`. Both anchor feedback and visual-contract marks remain `ai_receipt_status: pending`; the fixture does not infer that AI received or executed feedback.

## MCP capability probe

The fresh probe used only `/private/tmp/ai-ppt-v22-managed-probe.ieFRJG`:

- Public tools: 44; all names unique and exactly equal to `PUBLIC_TOOL_CATALOG`.
- Catalog SHA-256: `2244025bdda5c10faecb81b1208711af89bc499b64dbe1b08fc5864a2e1ae90b`.
- Chat UI templates: 0; ordinary public tools remain data-only.
- Mission confirmation exposes the complete host-native confirmation summary.
- ReviewSession plus content and visual review projections: available.
- Real host open: unavailable with `BROWSER_REVIEW_UNAVAILABLE`, `proofEligible: false`.
- Host notification: unverified.
- AI receipt: unverified.

## Code reduction and final source review

The scope `src`, `mcp`, and `widget/src` was compared to the base revision using physical lines in Python, MJS/JS, TS/TSX, and CSS files:

| Measure | Base | Current | Change |
|---|---:|---:|---:|
| Runtime files | 89 | 124 | +35 responsibility-focused files |
| Runtime lines | 24,589 | 21,612 | -2,977 (-12.1%) |
| Deleted obsolete runtime files | — | 28 | old surfaces and write paths removed |
| Public MCP tools | multiple hard-coded consumers | 44 | one catalog, 44 unique names |

The added files split explicit business responsibilities: ReviewSession, content review decision/batch/planning/projection, visual review, release policy, retrospective, exact bridge groups, legacy read-only adapters, and the two professional review pages. The reduction is therefore not a mechanical minification result.

Confirmed removals and corrections include:

- removed five-space UI, persistent sidebar, old navigation preview, old content writers, obsolete framework/expansion path, and old candidate/personal/stable experience writers;
- removed 28 obsolete runtime files, including `CompactWorkspace`, `StableNavigation`, `ProfessionalReviewApp`, old content services and old workspace projection;
- replaced repeated MCP arrays with one catalog used by registration, probe, release verification, and consistency tests;
- separated content and visual professional review surfaces from the read-only evidence auxiliary layer;
- separated feedback persistence, host-open receipt, host-notification receipt, and verified AI receipt instead of inferring one from another;
- removed three confirmed dead imports from `scenario_packs.py`, `content_review/decision_service.py`, and `content_review/projection_service.py`;
- fixed stale content-source invalidation, unreachable current-reference validation, false anchor-image loading, and visual save/notification/AI-receipt boundaries;
- added the long-text clipping regression and the one-rule inherited CSS correction described above.

Production-path searches have zero matches for `CompactWorkspace`, `StableNavigation`, `get_ai_ppt_sidebar_projection`, `content-sidebar`, `proposal-only`, and `awaiting-full-deck-authorization`. Deprecated five-space/sidebar/framework/full-deck-authorization language is absent from current production paths; the remaining “candidate” identifiers are ordinary local candidate-value variables, not an experience level or writer.

Two intentionally large boundaries were retained after source review:

- `ProjectKernel.commit` is 311 lines because it is one atomic lock/revision/replay/confirmation/artifact/event/state/rollback transaction. Splitting its transaction ordering across collaborators would increase correctness risk without removing a product concept.
- `createReviewBridge` is 571 lines and contains a 350-line request handler because the short-lived loopback session shares one token, Origin policy, revision, lease, receipt state, and server lifecycle. The bridge remains transport-only and is covered by the full Node security/lifecycle suite; no state-free duplicate extraction was identified.

## Zero-impact verification

Read-only identity checks after all automation show:

- main worktree: `codex/content-blueprint-sidebar-review` at `3998a9694cd9c86cc3bf97b45de294c85a57109e`;
- old Task 2 worktree: `2813aaf864434e6353fcc2b306ea43a4faf301b5`;
- old Task 3 worktree: `b5879c0d1f9ca52fe94f559257ad0da7bfd0826d`;
- old Task 4 worktree: `a7f76a65c2833ef123851ae7b5ef1ca565bfe6f4`;
- old Task 5 worktree: `d7ff354b1f64035cd924567d8ead28200c02cb61`;
- `stash@{0}`: `e67fa96e377f28bed1c4f7dbbed81ceb8ded0034`;
- `stash@{1}`: `f3bf56ae62c1e789a32d7f1cc240a16a1362a2ed`.

The main worktree was already modified by user/parallel work and is not claimed clean. All writes performed by this development run targeted the isolated worktree or explicit `/private/tmp/ai-ppt-v22-*` paths. No command targeted `/Users/defei/Documents/AI-PPT-Workspace`, the formal installed plugin/cache, the old worktrees, the two stashes, or the parallel `../PPT  web app ` product line.

## Automated conclusion

Task 17 development automation is complete for the isolated v2.2 source: syntax, type checking, 396 automated tests (337 Python + 41 Node + 18 Widget), production build, multi-viewport/long-document UI acceptance, three material-mode E2E, MCP probe, code-reduction audit, dead-path search, baseline-link check, and zero-impact identity check all have fresh passing evidence.

This conclusion does not authorize commit, merge, plugin installation, real-project migration, or release. It also does not convert fixture G0–G4 results into real user acceptance.

## Evidence that automation cannot supply

The following remain `待真实证据`:

- real Codex Browser opening the content and visual review pages;
- real Browser opening source evidence and restoring the parent review state;
- real Browser write-back to a real project;
- real host injection of `readProjectAsset` and real anchor-image reads;
- real host-open and host-notification receipts;
- verified AI receipt and execution of submitted feedback;
- user confirmation of a real project's G0, G3, and G4;
- real Codex Presentations PPTX creation, editing, rendering, and inspection;
- Microsoft PowerPoint loading, editing, rendering, and validating the current PPTX;
- real customer-project acceptance.

Fixtures, loopback servers, generated URLs, local renders, screenshots, builds, and automated tests must not be substituted for those facts.
