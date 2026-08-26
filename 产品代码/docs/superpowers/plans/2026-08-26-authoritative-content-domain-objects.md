# Authoritative Content Domain Objects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing four v2.2 content objects closed, identity-safe, source-bound, replay-safe, immutable, and readable through `PresalesContentService` without legacy authorization.

**Architecture:** Harden the existing JSON-compatible validators instead of introducing a second model representation. Keep cross-object/current-head checks, semantic command replay, and read projection in `PresalesContentService`; keep persistence in the content-addressed kernel; do not enter chief orchestration, hard gates, review, MCP, or UI.

**Tech Stack:** Python 3.12+, `unittest`, content-addressed JSON artifacts, revision-safe `ProjectKernel`, Node/Vitest/TypeScript regression suites.

---

## File map

- Modify `src/ai_ppt_studio/domains/content/contracts.py`: closed schemas, identity roles, local ID/reference integrity.
- Modify `src/ai_ppt_studio/application/presales_content_service.py`: current-chain source binding, semantic replay, immutable original-result replay, internal read projection.
- Modify `tests/test_v22_content_contracts.py`: contract RED/GREEN coverage and mode-aware fixtures.
- Create `tests/test_v22_content_domain_service.py`: service chain, cross-object binding, replay, zero-write, and immutable-history proof.
- Modify `tests/test_v22_presales_chief.py` only to consume the corrected mode-aware fit-map fixture; do not add chief behavior.
- Verify existing `tests/test_v16_content_chain.py` unchanged to prove legacy authorization remains absent.

### Task 1: Close the four domain contracts and identity roles

**Files:**
- Modify: `tests/test_v22_content_contracts.py`
- Modify: `src/ai_ppt_studio/domains/content/contracts.py`

- [ ] **Step 1: Add failing closed-schema tests**

Add one table-driven test that inserts an `unexpected` field into each root and each C0-owned nested record: evidence row, fit node, mapping, content block, customer decision item, evidence binding, material view, reading quality, and slide. Assert `ContractValidationError` and a `fields are not closed` message.

Use deep copies of `evidence_book()`, `decision_context()`, `fit_map()`, and `blueprint()` so each subtest changes exactly one record.

- [ ] **Step 2: Add failing identity-bucket tests**

For each evidence-book bucket, replace its first row with the identity shown below and require rejection:

```python
wrong_identities = {
    "facts": "方案建议",
    "user_confirmed_facts": "来源事实",
    "inferences": "来源事实",
    "conflicts": "方案建议",
    "unknowns": "材料推断",
    "evidence_gaps": "来源事实",
    "forbidden_extrapolations": "待联合验证",
}
```

Populate empty buckets from `evidence_item()` before changing the identity. Add explicit tests that `AI 分析` is accepted for `derived_requirements` and `analysis_or_proposal_blocks`, but rejected for facts, visible copy, slide identity labels, material views, and customer decision items.

- [ ] **Step 3: Add failing local-integrity tests**

Cover:

- duplicate node IDs within one fit-map bucket;
- duplicate mapping IDs;
- `problem_ref` pointing to a requirement;
- `requirement_ref` pointing to a solution component;
- `solution_component_ref` pointing to a symptom;
- duplicate content block IDs;
- evidence binding to an unknown block;
- duplicate evidence-binding `content_ref`;
- duplicate slide identity labels;
- duplicate solution mapping refs;
- duplicate section-flow entries.

- [ ] **Step 4: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_contracts -v
```

Expected: new cases fail because the first three roots/nested rows are open, bucket identities are not role-bound, duplicate IDs within one bucket pass, and blueprint local references are not closed.

- [ ] **Step 5: Implement exact keys and identity sets**

In `contracts.py` split identities into:

```python
FORMAL_CONTENT_IDENTITIES = frozenset({
    "来源事实", "材料推断", "用户已确认", "诊断假设",
    "方案建议", "待联合验证", "证据缺口", "禁止使用",
})
INTERNAL_ANALYSIS_IDENTITY = "AI 分析"
CONTENT_IDENTITIES = FORMAL_CONTENT_IDENTITIES | {INTERNAL_ANALYSIS_IDENTITY}
```

Call `_require_exact_keys()` for all four roots and every C0-owned nested record. Make `_evidence_row()` accept the bucket's allowed identities. Make `_fit_node()` and `_content_block()` accept an `allow_internal_analysis` flag; use it only for `derived_requirements` and `analysis_or_proposal_blocks`.

- [ ] **Step 6: Implement local ID and reference integrity**

Accumulate IDs row-by-row so duplicates within the same list fail. Keep separate problem, requirement, and solution ID sets for mapping category validation. Require unique mapping IDs.

Within each blueprint slide, build the combined set of visible and internal content-block IDs, require uniqueness, and validate each evidence binding before constructing the normalized slide. Require unique binding refs, identity labels, solution mapping refs, and section-flow entries.

- [ ] **Step 7: Run GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_contracts -v
```

Expected: all contract tests pass.

### Task 2: Bind evidence sources and the current four-object chain

**Files:**
- Modify: `tests/test_v22_content_contracts.py`
- Create: `tests/test_v22_content_domain_service.py`
- Modify: `tests/test_v22_presales_chief.py`
- Modify: `src/ai_ppt_studio/domains/content/contracts.py`
- Modify: `src/ai_ppt_studio/application/presales_content_service.py`

- [ ] **Step 1: Make fixtures mode-aware**

Change `fit_map()` to `fit_map(mode="material-backed")`. For `proposal-led`, give problem-side nodes `诊断假设`, requirements `AI 分析`, solution/boundary/alternative nodes `方案建议`, validation items `待联合验证`, and set every node/mapping `evidence_refs` to `[]`. For material modes, preserve the current factual nodes and `REF` evidence.

Update only the three-mode call in `tests/test_v22_presales_chief.py` to `fit_map(mode)`. Other callers retain the default material-backed fixture.

- [ ] **Step 2: Add failing evidence-book source tests**

Require rejection when:

- top-level `source_refs` contains duplicates;
- `excluded_material_refs` contains duplicates;
- a ref appears in both lists;
- a row cites a ref not declared at the top level;
- a row cites an excluded ref.

- [ ] **Step 3: Add the C0 service fixture and failing cross-object tests**

Create a helper that initializes a temporary `ProjectKernel`, seeds current `mission/confirmation` and optional `materials`, then writes the current evidence book, decision context, and fit map through `PresalesContentService`.

Add tests that reject with zero writes when:

- fit-map node/mapping evidence is undeclared or excluded;
- proposal-led fit content carries project evidence or factual identity;
- a material-mode mapping has no evidence;
- blueprint source version differs from the evidence book;
- a blueprint binding cites undeclared or excluded evidence;
- a material view cites undeclared or excluded evidence;
- a solution mapping ref does not exist in the current fit map.

Capture revision, heads, event filenames, and artifact-object filenames before each rejection and assert exact equality afterward.

- [ ] **Step 4: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_contracts tests.test_v22_content_domain_service tests.test_v22_presales_chief -v
```

Expected: new source and cross-object cases fail against current validators/service.

- [ ] **Step 5: Implement evidence-book declared-source validation**

After normalizing the evidence book, require unique/disjoint top-level source/excluded lists. For every bucket row, require each `source_ref` to occur in declared sources and not in excluded sources. Preserve the existing proposal-led and mixed-evidence mode rules.

- [ ] **Step 6: Implement service cross-object binding**

Resolve the current evidence payload before committing fit/blueprint objects. Add private helpers that:

```python
def _declared_evidence(self, evidence: dict[str, Any]) -> tuple[set[str], set[str]]: ...
def _require_declared_refs(self, refs: list[str], *, declared: set[str], excluded: set[str], field: str) -> None: ...
```

For a fit map, walk every node bucket and mapping. Enforce proposal-led zero-evidence/non-factual behavior; otherwise require declared evidence and non-empty mapping evidence.

For a blueprint, compare source version and mode, validate each evidence binding and material view against the evidence book, and validate every solution mapping ref against the current fit payload.

- [ ] **Step 7: Run GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_contracts tests.test_v22_content_domain_service tests.test_v22_presales_chief -v
```

Expected: all focused contract/service/mode tests pass.

### Task 3: Add semantic replay, immutable original results, and internal reads

**Files:**
- Modify: `tests/test_v22_content_domain_service.py`
- Modify: `src/ai_ppt_studio/application/presales_content_service.py`

- [ ] **Step 1: Add failing replay tests**

For each of the four build operations, prove:

1. immediate exact replay returns the original ref with no new revision/event/object;
2. reuse of the same command ID with one changed normalized field raises `Processed command has different semantics` with zero writes;
3. after a later command replaces the current head, exact replay of the earlier command still returns its original ref, not the current head.

Add a stale-revision test for a new command and require zero writes.

- [ ] **Step 2: Add failing immutable-history and read-surface tests**

Write version 1 and version 2 of each object chain. Save the v1 artifact bytes and payloads, then assert after replacement that:

- v1 refs still resolve;
- v1 bytes/payloads are unchanged;
- v2 refs are different where payloads differ;
- only v2 refs are current heads.

Call the not-yet-existing `get_current_content_chain()` after each construction step and assert the exact closed shape, current revision, current refs/payloads, and `None` for missing downstream objects. Mutating the returned payload must not mutate a later read.

- [ ] **Step 3: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_domain_service -v
```

Expected: changed command replay is accepted by the unfingerprinted writer, historical replay can return a newer head, and the read method is absent.

- [ ] **Step 4: Implement semantic fingerprints and original-result replay**

Import `replay_ref` beside the existing `fingerprint`. For each build method:

```python
normalized = validate_...(payload)
command_fingerprint = fingerprint("exact-operation-name", normalized)
replay = replay_ref(self.kernel, command_id, command_fingerprint, SLOT)
if replay is not None:
    return replay[0]
```

Perform this check before current-head preconditions. Pass `command_fingerprint` into every `kernel.commit()`. Extend `_commit()` to require and forward the fingerprint. Use operation names:

```text
build-presales-evidence-book
build-customer-decision-context
build-problem-solution-fit
build-reading-deck-blueprint
```

- [ ] **Step 5: Implement the internal read projection**

Add frozen class metadata mapping the four output keys to slot/kind pairs. `get_current_content_chain()` loads one state snapshot, resolves each present reference, verifies its kind, deep-copies payloads, and returns exactly:

```python
{
    "project_id": self.kernel.project_id,
    "revision": state.revision,
    "objects": {
        "evidence_book": value_or_none,
        "decision_context": value_or_none,
        "problem_solution_fit": value_or_none,
        "reading_blueprint": value_or_none,
    },
}
```

- [ ] **Step 6: Run GREEN and the unchanged migration guard**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_domain_service tests.test_v16_content_chain -v
```

Expected: all replay/read/history tests pass and the old framework/expansion authorization remains absent.

### Task 4: Full verification, atomic commit, and branch preservation

**Files:**
- Verify exact C0 scope only.

- [ ] **Step 1: Run all focused content-authority tests**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_content_contracts \
  tests.test_v22_content_domain_service \
  tests.test_v22_presales_chief \
  tests.test_v16_content_chain -v
```

Expected: all pass.

- [ ] **Step 2: Run full regressions**

```bash
npm run typecheck
npm run build
npm run test:node
npm run test:widget
npm run test:python
```

Expected: all commands exit 0 with no skipped baseline test.

- [ ] **Step 3: Audit exact scope**

```bash
git diff --check
git status --short
git diff --name-only 8fdbc1870bbc235195e53f88be29e8f41b35ee63...HEAD
git diff --name-only
```

Expected: committed docs plus the two allowed Python production files and named C0 tests only. No MCP, Node server, Widget, Review Bridge, hard-gate, content-review, visual, Gate, or delivery file.

- [ ] **Step 4: Stage exact implementation files and commit**

```bash
git add \
  产品代码/src/ai_ppt_studio/domains/content/contracts.py \
  产品代码/src/ai_ppt_studio/application/presales_content_service.py \
  产品代码/tests/test_v22_content_contracts.py \
  产品代码/tests/test_v22_content_domain_service.py \
  产品代码/tests/test_v22_presales_chief.py
git diff --cached --check
git diff --cached --stat
git commit -m "fix: harden authoritative content domain objects"
```

Do not use `git add .`.

- [ ] **Step 5: Perform fresh post-commit verification**

Repeat focused tests, typecheck, build, full Node/Widget/Python suites, `git diff --check`, and `git status --short --branch`. Expected: all pass and worktree clean.

- [ ] **Step 6: Request independent read-only code review**

Review the C0 base `8fdbc1870bbc235195e53f88be29e8f41b35ee63` through the final C0 HEAD against the design/spec. Resolve every Critical and Important issue with test-first follow-up commits; do not amend.

- [ ] **Step 7: Preserve C0 and establish the next boundary**

Keep the C0 branch/worktree as-is. Do not merge, push, install, release, or clean it up. Only after C0 is clean and reviewed may C1 be created as a new linked worktree from the verified C0 HEAD; no C1 code may be written in C0.
