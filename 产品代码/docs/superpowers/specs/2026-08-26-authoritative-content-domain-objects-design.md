# Authoritative Content Domain Objects Design

## 1. Context and objective

C0 is the first content-authority recovery unit after the MCP foundation. The current recovery line already contains recognizable validators and writers for `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and `ReadingDeckBlueprint`, and its focused baseline passes. The remaining work is not to introduce a fifth content model or revive the retired framework flow. It is to make the existing four-object chain closed, source-bound, replay-safe, immutable, and readable through one internal application service.

C0 stops at domain contracts and the ordered internal writer/reader. It does not implement the presales chief state machine, independent hard-gate reviewers, repair attempts, content-review batches, G0 confirmation, or UI projection.

## 2. Authority and recovery source

The approved v2.2 baselines and the current recovery lineage through R2 HEAD `8fdbc1870bbc235195e53f88be29e8f41b35ee63` are authoritative.

The quarantine checkout is evidence only. Its content diff contains old v1.6 stage objects, fixed reviewer-role dependencies, different content slots, legacy opinion-first fields, and incompatible service signatures. None of it is a selectable implementation source, and no quarantine commit or file is merged or cherry-picked.

The current four artifact kinds and slots remain:

| Object | Slot | Artifact kind |
|---|---|---|
| `PresalesEvidenceBook` | `content/evidence-book` | `presales-evidence-book` |
| `CustomerDecisionContext` | `content/decision-context` | `customer-decision-context` |
| `ProblemSolutionFitMap` | `content/problem-solution-fit` | `problem-solution-fit-map` |
| `ReadingDeckBlueprint` | `content/reading-blueprint` | `reading-deck-blueprint` |

## 3. Considered approaches

### 3.1 Recover the quarantine content chain

This appears to contain more code, but it restores retired objects, slots, producer assumptions, and opinion-first fields. It would combine several future recovery units and regress approved v2.2 behavior. This approach is rejected.

### 3.2 Replace dictionaries with a new class hierarchy

Frozen dataclasses or a new schema library could make types more visible. That would require broad adapters across hard gates, review projection, visual production, bridge handlers, and fixtures. The migration would be larger than C0 and would obscure whether failures came from recovery or representation changes. This approach is deferred.

### 3.3 Harden the current contracts and service

Keep JSON-compatible dictionaries as the persisted contract, make every C0-owned object and nested row closed, add role-specific identity and reference validation, and bind write commands to semantic fingerprints and original-result replay. Use the content-addressed repository as the immutable history authority and expose a read-only current-chain projection from `PresalesContentService`. This is the selected approach.

## 4. Closed domain contracts

The four root objects reject missing and unknown keys. C0-owned nested records also reject missing and unknown keys:

- evidence rows;
- fit nodes;
- problem-requirement-solution mappings;
- content blocks;
- customer decision items;
- evidence bindings;
- material views;
- reading-quality records;
- blueprint slides.

Existing normalized return shapes remain JSON-compatible and deterministic. Validators never silently drop unknown fields and never coerce booleans, numbers, arrays, or objects into another type.

`repair_history` remains an opaque object array in C0 because its exact repair-record contract belongs to C2. `hard_gate_refs` remain an array that may be empty before C2. C0 does not invent their future fields.

## 5. Content identity semantics

The eight approved formal identities are:

```text
来源事实 | 材料推断 | 用户已确认 | 诊断假设 |
方案建议 | 待联合验证 | 证据缺口 | 禁止使用
```

The baselines also mention `AI 分析` when describing internal analysis. C0 resolves that wording conservatively without changing product baselines:

- `AI 分析` is an internal analysis identity only;
- it may appear in `derived_requirements` and `analysis_or_proposal_blocks`;
- it may not appear in evidence-book fact buckets, visible copy, slide identity labels, material evidence identity, or `customer_decision_item`;
- it never upgrades analysis into a source fact, user-confirmed fact, capability proof, result, guarantee, or commitment.

Evidence-book buckets enforce their role:

| Bucket | Permitted identity |
|---|---|
| `facts` | `来源事实` |
| `user_confirmed_facts` | `用户已确认` |
| `inferences` | `材料推断` |
| `conflicts` | `材料推断` or `证据缺口` |
| `unknowns` | `证据缺口` |
| `evidence_gaps` | `证据缺口` |
| `forbidden_extrapolations` | `禁止使用` |

Factual rows require source references. Proposal-led objects cannot claim project sources or customer facts. Structural validation cannot prove that prose is true; it guarantees that every fact claim is explicitly typed and bound to declared evidence so C2 can review it semantically.

## 6. Source and reference binding

### 6.1 Evidence book

- `source_refs` and `excluded_material_refs` are unique and disjoint.
- Every row source reference must be declared in top-level `source_refs`.
- No row may cite an excluded material reference.
- `proposal-led` keeps the existing zero-material rule.
- `material-backed` and `mixed-evidence` keep the existing current material-inventory requirement.
- `mixed-evidence` requires at least one explicit evidence gap.

### 6.2 Fit map

- Node IDs are unique across the entire map, including duplicates within one bucket.
- Mapping IDs are unique.
- `problem_ref` points only to a problem-side node (`situations`, `symptoms`, `causes_or_hypotheses`, `impacts`, `constraints`, or `unknowns`).
- `requirement_ref` points only to `derived_requirements`.
- `solution_component_ref` points only to `solution_components`.
- A factual node requires evidence; internal analysis or proposal nodes do not become facts merely because they carry evidence references.
- Every fit-node and mapping evidence reference is declared by the current evidence book and is not excluded.
- In `proposal-led` mode, fit nodes and mappings carry no project evidence and cannot use factual identities; in the two material modes, each mapping keeps at least one declared evidence reference.

### 6.3 Blueprint and upstream chain

The service resolves the exact current evidence book, decision context, and fit map before creating a blueprint. In addition to reference kind/current-head checks:

- blueprint `source_version` equals the current evidence book `source_version`;
- blueprint `material_mode` equals the current evidence book mode;
- every evidence binding points to a current slide content block;
- every evidence-binding source reference is declared by the current evidence book and is not excluded;
- every material-view `source_ref` is declared and not excluded;
- every `solution_mapping_ref` identifies a current fit-map mapping;
- content block IDs are unique within a slide;
- evidence-binding `content_ref` values are unique;
- slide identity labels are unique;
- section-flow entries are unique, while the existing distinction between flow labels and slide `section_id` remains unchanged.

## 7. Revision, replay, and immutable history

Each four-object write computes a semantic command fingerprint from its operation and normalized payload, then checks for an earlier command result before checking current upstream heads.

Exact replay semantics are:

1. the same `command_id`, operation, and normalized payload returns the artifact reference created by the original command;
2. this remains true after later commands advance the project or replace the current head;
3. replay creates no event, artifact object, or revision;
4. reusing a command ID with a different operation or payload fails with `Processed command has different semantics` and performs zero writes;
5. a new command with a stale `expected_revision` fails with the existing revision conflict and performs zero writes.

New versions replace only the current head. The content-addressed artifact repository retains every prior envelope, validates its SHA-256 identity on read, and never overwrites an existing object. Tests resolve old and new references after replacement and verify that the original bytes and payload remain unchanged.

## 8. Internal application-service read surface

`PresalesContentService.get_current_content_chain()` returns a closed read-only projection:

```text
project_id
revision
objects:
  evidence_book: { ref, payload } | null
  decision_context: { ref, payload } | null
  problem_solution_fit: { ref, payload } | null
  reading_blueprint: { ref, payload } | null
```

The method resolves every present reference through `ArtifactRepository`; it does not return mutable kernel state objects and does not write. Missing downstream objects are represented as `null`, allowing C1 to inspect a partially built chain without inventing completion.

This is an internal Python service API only. C0 does not add an MCP tool or a user-facing page.

## 9. Data flow

```text
current MissionConfirmation + MaterialInventory
-> validated PresalesEvidenceBook
-> validated CustomerDecisionContext bound to current EvidenceBook
-> validated ProblemSolutionFitMap bound to current EvidenceBook + DecisionContext
-> validated ReadingDeckBlueprint bound to all three current upstream objects
-> immutable content-addressed artifacts + current heads
-> get_current_content_chain() for internal consumers
```

No old framework confirmation or full-deck expansion authorization participates in this flow.

## 10. Failure and zero-write behavior

Contract, identity, source, mapping, lineage, project, material-mode, command-semantic, and revision failures occur before commit. Tests record the revision, event files, artifact object files, and artifact heads before each rejected operation and require exact equality afterward.

Replacing an upstream content object does not silently make old downstream objects current. Existing downstream invalidation remains in force; C0 tests only the four-object chain and immutable history. Hard-gate, ReviewSession, visual, delivery, and Gate invalidation semantics remain owned by later slices and existing regression suites.

## 11. Testing and acceptance

TDD must first reproduce these current defects:

1. unknown root/nested fields are silently dropped from the first three objects;
2. an evidence row can appear in the wrong identity bucket;
3. undeclared or excluded source references are accepted;
4. duplicate fit-node IDs within one bucket are accepted;
5. mappings can point to the wrong node category;
6. blueprint bindings can point to unknown block, evidence, material, or mapping references;
7. same command ID with changed content can replay without semantic rejection;
8. replay after a later head replacement can return the newer head instead of the original command result.

Engineering exit requires:

- focused contract and service tests;
- all four objects created and read through `PresalesContentService` without legacy authorization;
- all three material modes covered;
- exact replay, changed replay, stale revision, zero-write failure, and immutable-history evidence;
- complete Python suite;
- full Node and Widget regressions, TypeScript typecheck, and Widget build because later consumers share the repository;
- `git diff --check` and an exact scope audit;
- independent code review with no unresolved Critical or Important issue.

These are local engineering facts only. C0 does not prove C1 chief orchestration, C2 hard-gate passage, C3 content-review readiness, G0, host notification, AI receipt, visual production, PowerPoint, release, installation, or user acceptance.

## 12. Allowed and forbidden scope

Allowed production files:

- `src/ai_ppt_studio/domains/content/contracts.py`;
- `src/ai_ppt_studio/application/presales_content_service.py`;
- C0-focused Python tests;
- this design and its implementation plan.

Forbidden scope:

- presales chief orchestration, role dispatch, consultant spawning, or repair-attempt policy;
- content hard-gate reviewer behavior or acceptance records;
- content review batch, revision-plan, ReviewSession, G0, or Browser behavior;
- MCP public tools or Node handler behavior;
- Widget, content-review UI, visual-review UI, CSS, or ViewModels;
- visual production, PPTX, delivery, experience, retrospective, release, installation, merge, or push.
