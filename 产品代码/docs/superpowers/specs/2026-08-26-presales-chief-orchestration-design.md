# Presales Chief Orchestration Design

## Decision and scope

C1 adds one internal `PresalesChiefOrchestrator` that makes
`presales-solution-chief` the only owner of v2.2 content production and repair.
Python governs order, authority, material mode, replay, repair budget, and
truthful stops; it does not generate semantic customer content. The AI chief
supplies complete payloads and the Runtime commits them through the C0
`PresalesContentService`.

C1 ends with a consistent four-object chain in
`ready-for-independent-gates`, or one exact governed stop. It does not create
or pass C2 hard gates, open C3 review, confirm G0, add MCP/UI, or enter visual,
PPTX, delivery, release, installation, or user acceptance.

Rejected alternatives are Python template generation, a second persisted
workflow ledger, and restoration of the fixed five-role content pipeline. The
first displaces AI as producer, the second creates duplicate truth, and the
third contradicts the approved v2.2 role contract.

## Components and closed projection

The new service composes `MissionReadinessPolicy` and
`PresalesContentService`. It derives state from current Mission identity, the
four C0 heads, and current failed hard-gate refs; it never persists a second
workflow state.

```python
class PresalesChiefOrchestrator:
    def inspect(self) -> dict[str, Any]: ...
    def advance(self, *, command_id: str, expected_revision: int,
                payload: dict[str, Any]) -> dict[str, Any]: ...
    def repair_blueprint(self, *, command_id: str, expected_revision: int,
                         payload: dict[str, Any]) -> dict[str, Any]: ...
    def consultant_capability(self, *, risk_area: str, question: str,
                              target_refs: list[str]) -> dict[str, Any]: ...
```

`inspect()` returns exactly:

```text
project_id, revision, state, material_mode
current_refs: mission_confirmation, material_inventory, evidence_book,
              decision_context, problem_solution_fit, reading_blueprint
next_operation, target_refs
repair: applicable, attempts_used, attempts_remaining, failure_refs
stop: code, message, resumable
```

It never returns hidden reasoning, prompts, UI state, Gate pass claims, host
receipts, AI receipts, or delivery claims.

## Derived state machine

```text
mission-not-ready
-> reconstructing-evidence
-> building-decision-context
-> diagnosing-problem-solution-fit
-> drafting-reading-deck
-> ready-for-independent-gates
```

| Condition | State | Next operation |
|---|---|---|
| Mission not current/confirmed | `mission-not-ready` | empty |
| EvidenceBook missing | `reconstructing-evidence` | `build-presales-evidence-book` |
| DecisionContext missing | `building-decision-context` | `build-customer-decision-context` |
| FitMap missing | `diagnosing-problem-solution-fit` | `build-problem-solution-fit` |
| Blueprint missing | `drafting-reading-deck` | `build-reading-deck-blueprint` |
| Complete chain, no failed gate | `ready-for-independent-gates` | empty |
| Failed current gate, budget remains | `chief-repair` | `repair-reading-deck-blueprint` |
| Failed gate, budget exhausted | `governed-stop` | empty |

Mission failure is a truthful resumable stop, never a generated confirmation.
Inconsistent C0 lineage fails closed as `CONTENT_CHAIN_INCONSISTENT`.

## One-step advance and authority

`advance()` computes the projection from the current revision, requires the
caller's revision to match, and dispatches only the derived next operation. The
caller cannot name an operation, so it cannot skip a stage or select a legacy
route.

The evidence step derives mode from trusted Mission plus actual evidence gaps:

- no-material confirmation -> `proposal-led`;
- current materials without gaps -> `material-backed`;
- current materials with gaps -> `mixed-evidence`.

The remaining steps delegate reference and lineage checks to C0. Exact replay,
changed-semantics rejection, stale revision, immutable history, and dependent
head invalidation remain C0 behavior.

Only `presales-solution-chief` owns the four build operations and Blueprint
repair. The chief cannot write hard-gate passed, trusted confirmation, submitted
review batches, pre-G0 visual artifacts, or fake external receipts. No old
`framework-confirmed` or `awaiting-full-deck-authorization` state participates.

## Repair budget

C1 may recognize current failed content hard-gate records created elsewhere;
it never creates or passes them. The automatic repair budget is three.
`attempts_used` is derived from current Blueprint `repair_history`, avoiding a
second counter. Each new entry must bind a current failed-gate ref and have a
new attempt identity. At three attempts the projection stops with
`REPAIR_ATTEMPTS_EXHAUSTED` and no write. C2 remains responsible for reviewer
execution and reruns.

## On-demand consultant boundary

Risk specialists never appear in the fixed state sequence.
`consultant_capability()` accepts a bounded risk question and unique current
target refs. No real risk-specialist adapter exists in C1, so it truthfully
returns, without writing:

```text
status = unavailable
code = CONSULTANT_RUNTIME_UNAVAILABLE
requested_role = presales-risk-specialist/<normalized-risk-area>
write_authority = none
```

It must not create an AgentTask or claim that a consultant ran.

## Failure, testing, and exit proof

Mission absence, stale revision, wrong material mode, skipped/completed steps,
mixed lineage, repair without a failed gate, invalid/repeated repair history,
exhausted budget, and invalid consultant refs fail before a commit. Tests
snapshot revision, heads, events, and artifact objects and require zero writes.

C1 passes only when tests prove all three material modes, deterministic ordered
transitions, single chief authority, absence of legacy authorization, C0 replay
and lineage preservation, bounded repair without reviewer self-approval, and a
truthful zero-write consultant capability gap. A complete chain proves only
`ready-for-independent-gates`; it does not prove C2/C3/G0, host notification,
AI receipt, visual work, PPTX, release, installation, or user acceptance.
