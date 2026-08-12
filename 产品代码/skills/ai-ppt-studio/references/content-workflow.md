# Content-first presales workflow

## Mission, material identity, and sources

Finish what the presentation says before deciding how it looks. Follow this mandatory order:

1. Save `MissionDraft` with `save_ai_ppt_mission_draft`.
2. Show the audience, topic, desired judgment/action, current material inventory or explicit no-material choice, background, constraints, red lines, and unknowns. Complete required fields mean only `confirmable`.
3. After displaying the complete current card, recognize `OK / 确认 / 采纳 / 继续` only as confirmation intent when mission confirmation is the sole pending high-impact action. Ordinary conversation and unrelated adoption do not qualify.
4. Call `confirm_ai_ppt_mission` with the current card summary. A verified sidebar/message reference or accepted host-native confirmation creates `MissionConfirmation` bound to the current draft, revision, and material identity; intent text is never evidence.
5. Pass the Python content precondition gate before creating a formal content task or committing formal content.
6. Continue as `material-backed` from `materials-provided`, or as `proposal-only` from `no-materials-confirmed`.

In `material-backed`, preserve source fact, source-derived inference, AI-authored connective content, and unsupported gap. Critical unsupported facts cannot pass content acceptance or G0.

In `proposal-only`, preserve the user-facing identities 诊断假设 for customer situation and pain, 方案建议 for architecture/scope/path, and 待联合验证 for capabilities/results. Carry them through strategy, every claim, chapter task, slide title/copy, speaker notes, review, repair, acceptance, and Browser projection. Never invent customer facts, numbers, cases, product capabilities, results, or commitments.

## Formal production chain

Produce one role-bound artifact at a time:

1. `PresalesContentStrategy`: decision stage, core tension, persuasion proposition, boundaries, current mission confirmation/material identity refs, and content identity mode.
2. `ClaimEvidenceMap`: each claim classified and bound to resolvable evidence, or explicitly governed under one of the three `proposal-only` identities.
3. `DeckArgumentMap`: chapters, narrative tasks, transitions, evidence progression, and identity-visible chapter tasks.
4. `SlideDraftSet`: final page order; title, communication goal, one core claim, all visible copy, complete speaker notes, source/material refs, identity status, gaps, and media intent for every page.

References use `artifact://<kind>/<sha256>` and must point to current verified upstream heads.

## Isolated review and repair

Run exactly the required five independent roles—presales, decision-maker, evidence, narrative, and editorial review—against the same current draft. Applicable hard checks are binary. One missing, stale, duplicated, or failed role blocks acceptance; there is no score compensation. In `proposal-only`, each reviewer must reject any missing identity, false supported-fact status, material citation that does not exist, invented fact/number/case, or capability/result commitment.

When checks fail, create a repair plan and revise only the affected content. Re-run every invalidated reviewer. Only the aggregated passing acceptance record may publish the content blueprint to professional review.

## G0

The shared professional review document opens only in the Codex built-in Browser and continuously displays structure, every page's complete visible copy, speaker notes, source/material refs, fact or proposal identity, state, and mark targets. Saving marks does not pass G0. G0 requires the current internally accepted blueprint and explicit user confirmation with a real host-verified message reference. Visual discussion begins only after G0 passes.
