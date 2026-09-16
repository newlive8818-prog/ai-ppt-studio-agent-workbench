# Content Hard Gates and Repair Loop Design

## Decision and scope

C2 turns the existing hard-gate skeleton into the authoritative boundary between
the current `ReadingDeckBlueprint` and C3 full-deck review. It owns two isolated,
non-compensatory reviewers:

- `content-evidence-gate-reviewer` for fact, evidence, identity, lineage, and
  unsupported-claim risk;
- `content-presales-reading-gate-reviewer` for customer position, problem
  completeness, mapping, neutral titles, independent reading, coherence,
  boundary, risk, validation, and next action.

The reviewers only write immutable `content-hard-gate-record` artifacts. They
never edit content, create a repair Blueprint, pass G0, open C3 ReviewSession,
or write UI, visual, PPTX, delivery, release, installation, or user-acceptance
facts. `PresalesChiefOrchestrator` remains the only repair owner.

The active Runtime has no independently attested reviewer-agent adapter or
closed `agent-output` receipt contract. C2 therefore executes formal reviews as
`isolated-review-task`. It rejects runtime claims of `independent-agent` instead
of accepting an instance id and output ref supplied by the caller. The domain
record retains `independent-agent` as a valid archival contract for a future
adapter, but C2 does not claim that capability exists.

## Closed C2 projection

`ContentHardGateService.inspect()` derives state from the current C0 chain and
current gate records. It does not persist another workflow ledger. It returns
exactly:

```text
project_id, revision, state, source_version, blueprint_ref
evidence_gate_ref, presales_reading_gate_ref, acceptance_ref
next_operation, failure_refs, repair_requirements
stop: code, message, resumable
```

States are:

```text
content-not-ready
-> evidence-gate-review
-> failed -> chief-repair
-> presales-reading-gate-review
-> failed -> chief-repair
-> content-user-reviewable
```

An invalid current ref, wrong kind, stale source/hash, malformed gate, or
acceptance mismatch produces `governed-stop` with a stable code. A failed gate
exposes repair requirements but C2 has no repair writer. After C1 commits a new
Blueprint, C0 atomically removes current gate/acceptance heads and the state
returns to `evidence-gate-review`.

## Closed hard-gate record

The record root has the approved SDD fields plus the existing `output_ref` and
no unknown fields. Check rows are closed:

```text
check_id, applicability, result, hard, evidence_refs, failure_reason
```

Rules:

- `hard` is always true; scoring, weighting, averaging, and voting are absent;
- check ids are unique across deterministic and semantic results;
- applicable checks cite the exact current Blueprint ref;
- not-applicable checks cite no evidence and use result `not-applicable`;
- passed checks have no failure reason; failed checks have one;
- `overall_result` is derived: any applicable failed item means `failed`;
- `repair_requirements` is a closed unique array of
  `{check_id, instruction}` and exactly covers failed check ids;
- passed records have no repair requirements;
- hashes are lowercase SHA-256 identities and timestamps are valid ISO-8601;
- `isolated-review-task` has empty independent instance/output identities;
- an `independent-agent` record requires all approved evidence fields, but the
  current service rejects attempts to create one until a real adapter exists.

## Deterministic and semantic coverage

C2 revalidates the complete current C0 chain before every new gate command.
Deterministic evidence checks cover current lineage, source/exclusion identity,
formal content identities/material mode, and problem-requirement-solution
mapping. Deterministic reading checks cover neutral-title contract,
independent-reading flags, page/section ordering, and mapping references.

The caller supplies the isolated review output as a closed set of gate-specific
semantic checks. Passing requires the complete exact set; an empty array cannot
silently mean that semantic review happened.

Evidence semantic checks:

```text
selective-evidence-risk
unsupported-causality
unsupported-capability-result-commitment
```

Presales-reading semantic checks:

```text
customer-decision-position
problem-completeness
whole-deck-coherence-and-repetition
boundary-risk-validation-next-step
```

Each result is binary or explicitly not applicable. Missing, duplicate, foreign,
soft, or wrong-target checks fail before any artifact/event write.

## Context, source identity, and replay

For each new review command, C2 compiles the approved reviewer Context Pack from
the exact current EvidenceBook, DecisionContext, FitMap, and Blueprint refs.
Producer self-evaluation and sibling reviewer opinions remain excluded. The
context is committed as a detached immutable artifact with the gate record.

Every new record binds:

- current Blueprint ref and SHA-256;
- current `source_version`;
- exact gate type and reviewer role;
- exact context pack ref/hash;
- exact semantic results and reviewer mode.

Command fingerprints bind the gate operation and normalized request. Exact
replay returns the original record/ref even after revision advances; changed
semantics or cross-gate command reuse fails zero-write. A new stale revision or
stale same-version Blueprint also fails zero-write.

The reading gate requires a current passed evidence record whose input hash and
source version match the current Blueprint. It never accepts a historical gate
merely because the source-version string was reused.

## Acceptance and repair loop

An evidence failure blocks the reading gate. A reading failure preserves the
current passed evidence record only until the chief repairs. C1 repair writes a
new immutable Blueprint with one canonical history entry bound to the current
failure; C0 then removes both gate heads and any acceptance, forcing the affected
review sequence to rerun.

Only a current passed evidence record and a current passed reading record, both
bound to the exact current Blueprint hash/source, create `content/acceptance`.
That acceptance means `content-user-reviewable`: it permits C3 to open full-deck
review. It is not a completed review batch, G0, host notification, AI receipt,
visual authorization, release, or user acceptance.

## Failure and exit proof

Tests snapshot revision, heads, event filenames, and artifact objects for every
rejection. Required proof includes closed contracts, exact check coverage,
reviewer non-edit authority, truthful reviewer mode, semantic command replay,
same-version stale hash rejection, evidence-before-reading order, failed-gate
repair requirements, C1 repair and mandatory rerun, exact dual-current acceptance,
and legacy-acceptance/G0 bypass rejection.

C2 exits only when a complete current Blueprint deterministically reaches either
one exact failed repair boundary or `content-user-reviewable` after both gates.
It does not implement C3 or synthesize G0.
