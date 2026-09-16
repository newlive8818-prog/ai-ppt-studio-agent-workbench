# v2.3 Baseline Contract Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the approved v2.3 visual-semantic design into the four authoritative baselines and establish an independently generated v2.3 acceptance ledger without rewriting or inheriting any frozen v2.2 acceptance fact.

**Architecture:** Treat the four Markdown baselines as one cross-linked current contract set and acceptance ledgers as versioned evidence inventories. Current v2.9 baselines may generate only the v2.3 ledger; the checked-in v2.2 ledger/evidence remain frozen catalogs protected by exact identity checks. Release verification selects authoritative requirements from the ledger version, so v2.2 never consumes current v2.3 baselines and v2.3 never inherits v2.2 proof.

**Tech Stack:** Markdown, Python 3.11+, stdlib `unittest`, JSON acceptance ledgers, Git, `rg`, shell link/path checks, `git diff --check`.

---

## Execution isolation

- Integration source: current clean HEAD of `codex/v23-visual-quality-20260831` in `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/6fe4/PPT-codex-app`.
- Execution branch: `codex/v23-baseline-contract-20260901`.
- Execution Worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-baseline-contract-20260901`.
- Create the Worktree only after the user selects R0 and `superpowers:using-git-worktrees` confirms the integration Worktree is clean.
- Planning approval does not authorize baseline writes. Task 1 must be reported and separately approved before Task 2.
- The user approved the exact four-baseline difference package and then, on 2026-09-02, explicitly expanded R0 to establish an independent v2.3 acceptance ledger.
- The only product-code exception in expanded R0 is the minimum ledger generation/release-verification infrastructure and its tests listed below. No visual-domain implementation, Skill, MCP, Widget, Runtime data, PPTX, plugin install, or plugin release may change.

## File map

- Modify `00-唯一研发基线索引-v1.0.md`: register v2.3 as an approved design and planned R&D program while preserving the v2.2 engineering-freeze identity.
- Modify `01-产品需求基线-v1.0.md`: add the visual-semantic product objects, sample evidence model, five evidence levels, and product acceptance boundaries.
- Modify `02-系统详细设计-v1.0.md`: add exact fields, `visual-compilation-plan`, `visual/compilation-plan`, deterministic derivation, invalidation, lineage, legacy handling, and handoff contracts.
- Modify `03-UI设计与交互规范-v1.0.md`: add only user-reviewable Visual Brief, design-system, and slide-contract semantics; preserve the accepted visual-review structure.
- Modify `产品代码/src/ai_ppt_studio/acceptance/ledger.py`: make v2.3 visual requirement IDs retain the existing visual evidence obligations without changing v2.2 records.
- Modify `产品代码/scripts/build_acceptance_ledger.py`: generate only the current v2.3 ledger/evidence from current baselines; never rebuild or overwrite v2.2.
- Modify `产品代码/scripts/acceptance/verify_release.py`: select the authoritative requirement catalog by ledger version and verify frozen catalog identity.
- Modify `产品代码/tests/test_acceptance_ledger.py`: protect the frozen v2.2 identity and prove the independent v2.3 generator and checked-in ledger.
- Modify `产品代码/tests/test_v16_final_acceptance_verifier.py`: prove release verification does not compare v2.2 ledgers with current v2.3 baselines and supports current v2.3 authority.
- Create `产品代码/requirements/v2.3-acceptance-ledger.json`: 157 current requirements, all initially `unproven`, with no proof refs.
- Create `产品代码/requirements/v2.3-evidence.json`: empty v2.3 evidence index; no inherited v2.2 proof.
- Preserve byte-for-byte `产品代码/requirements/v2.2-acceptance-ledger.json` and `产品代码/requirements/v2.2-evidence.json`.
- Read only `产品代码/docs/superpowers/specs/2026-09-01-v23-visual-quality-semantic-compilation-design.md`: authoritative design source.
- Read only `产品代码/docs/superpowers/roadmaps/2026-09-01-v23-visual-quality-product-map.md`: product decomposition.
- Read only `产品代码/docs/superpowers/roadmaps/2026-09-01-v23-visual-quality-rnd-map.md`: R0–R5 boundaries.

### Task 1: Verify isolation and produce the exact baseline change ledger

**Files:**
- Read: `00-唯一研发基线索引-v1.0.md`
- Read: `01-产品需求基线-v1.0.md`
- Read: `02-系统详细设计-v1.0.md`
- Read: `03-UI设计与交互规范-v1.0.md`
- Read: `产品代码/docs/superpowers/specs/2026-09-01-v23-visual-quality-semantic-compilation-design.md`

- [ ] **Step 1: Verify branch, HEAD, freeze ancestry, Worktree identity, and clean state**

Run from the R0 Worktree:

```bash
git status --porcelain=v1 --branch
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor b874d6581c14c8fb26bf498848f37c9456a42482 HEAD
git rev-parse 'ai-ppt-studio-v2.2-engineering-freeze-20260831^{}'
git rev-parse --git-dir
git rev-parse --git-common-dir
```

Expected: branch is `codex/v23-baseline-contract-20260901`; status has no file entries; freeze ancestry exits 0; tag resolves to `b874d6581c14c8fb26bf498848f37c9456a42482`; Git dir differs from common dir, proving a linked Worktree.

- [ ] **Step 2: Record proposed document identities without editing**

Prepare a user-facing ledger with these exact proposals:

```text
product program identity: AI PPT Studio v2.3 视觉质量与设计感攻关
baseline document revision: v2.8 -> v2.9
v2.2 engineering freeze: remains frozen and unchanged
v2.3 design status: approved
v2.3 implementation status: not implemented
v2.3 sample status: not run
v2.3 PowerPoint status: not checked
v2.3 user visual status: not accepted
```

The version proposal must remain a proposal until the user approves it. If the user rejects `v2.9`, update this plan through a new planning commit before editing any baseline.

- [ ] **Step 3: Produce a section-level change ledger**

Report these planned changes and no others:

```text
00: add v2.3 authority entry, design/roadmap/plan links, state boundary, and R0-R5 index
01: add visual semantic compilation product mechanism, five-second judgment, anti-patterns,
    VisualCompilationPlan, sample evidence package, five evidence levels, V0-V4 exits
02: add exact field contracts, artifact/head, atomic deterministic derivation,
    invalidation, G1/G2/G3 lineage, legacy/unassessed status, ContextPack and handoff
03: add only reviewable Visual Brief/design-system/slide fields; preserve one top bar,
    two views, inline anchor batch, left/right overlay drawers, and contextual marking
```

Explicitly list preserved facts: v2.2 freeze; current required target `macos-powerpoint`; deferred target boundaries; Codex Presentations-only rule; no G3/G4 advancement; no public plugin release; accepted content/visual review UI scope.

- [ ] **Step 4: Stop for separate baseline authorization**

Do not edit any file. Ask the user to approve or revise the exact ledger. R0 remains blocked by product authority, not by engineering difficulty. Proceed only after a clear user approval that specifically authorizes changing the four baselines.

### Task 2: Update the authority index and product requirements

**Files:**
- Modify: `00-唯一研发基线索引-v1.0.md`
- Modify: `01-产品需求基线-v1.0.md`

- [ ] **Step 1: Add failing document-contract assertions**

Before editing, run:

```bash
rg -n 'VisualCompilationPlan|visual-compilation-plan|五秒读者判断|E1 机制实现|R0：权威基线' \
  00-唯一研发基线索引-v1.0.md \
  01-产品需求基线-v1.0.md
```

Expected: no complete v2.3 contract appears in either file; exit status may be 1.

- [ ] **Step 2: Update document headers and authority index**

Change the `00` and `01` document revision headers from `v2.8` to the user-approved revision, update the date to `2026-09-01`, and add a concise v2.3 change source. In `00`, link exactly:

```markdown
- [v2.3 视觉质量与设计感攻关设计规格](./产品代码/docs/superpowers/specs/2026-09-01-v23-visual-quality-semantic-compilation-design.md)
- [v2.3 视觉质量攻关产品地图](./产品代码/docs/superpowers/roadmaps/2026-09-01-v23-visual-quality-product-map.md)
- [v2.3 视觉质量攻关研发地图](./产品代码/docs/superpowers/roadmaps/2026-09-01-v23-visual-quality-rnd-map.md)
```

Add a state table with five independent rows: `机制实现 / 自动化验证 / 真实 PPT 样本验证 / 目标 PowerPoint 检查 / 用户视觉认可`. Set every v2.3 row to `未完成` except design status `已批准`.

- [ ] **Step 3: Add the product object and capability contract to `01`**

Add `VisualCompilationPlan` to the core-object table with this identity:

```text
由当前 ReadingDeckBlueprint、Visual Brief、Deck Design System、
Slide Visual Contract、ReleaseTargetPolicy 和适用经验版本确定性派生；
不是第二套设计真相，不是用户表面，不得改写冻结内容。
```

Add P0 capability rows after `VIS-006`:

```text
VIS-007  Visual Brief v2.3 visual strategy
VIS-008  Deck Design System rhythm and emphasis contract
VIS-009  Slide five-second judgment and visual relationship contract
VIS-010  Deterministic VisualCompilationPlan
VIS-011  Anti-pattern and sample-evidence review
VIS-012  Target PowerPoint and user-result evidence separation
```

Use Chinese product labels in the file, keep IDs stable, and do not mark them implemented.

- [ ] **Step 4: Add product acceptance and non-goals**

Add acceptance IDs:

```text
PRD-ACC-V23-VISUAL-001  same normalized inputs/compiler version -> same plan ref
PRD-ACC-V23-VISUAL-002  every slide has one primary relationship and one visual mechanism
PRD-ACC-V23-VISUAL-003  compilation cannot change frozen content
PRD-ACC-V23-VISUAL-004  build-native-first consumes only the current plan
PRD-ACC-V23-VISUAL-005  anti-pattern failures identify page region and evidence
PRD-ACC-V23-VISUAL-006  E1-E5 are stored and reported separately
PRD-ACC-V23-VISUAL-007  two-page experiment cannot authorize full-deck or real-sample expansion
```

Add explicit non-goals: no template market, no second PPTX tool, no 27-page rewrite, no automatic aesthetic score, no v2.2 Runtime G3/G4 continuation, no plugin publication.

- [ ] **Step 5: Verify the product contract is present and not overclaimed**

```bash
rg -n 'VIS-00[7-9]|VIS-01[0-2]|PRD-ACC-V23-VISUAL|VisualCompilationPlan|未实现|未完成' \
  00-唯一研发基线索引-v1.0.md \
  01-产品需求基线-v1.0.md
```

Expected: every new ID occurs once; v2.3 implementation/sample/PowerPoint/user states remain negative or pending.

### Task 3: Update the system and UI contracts

**Files:**
- Modify: `02-系统详细设计-v1.0.md`
- Modify: `03-UI设计与交互规范-v1.0.md`

- [ ] **Step 1: Add failing system-contract searches**

```bash
rg -n 'visual/compilation-plan|visual-semantic-compiler/v1|legacy / unassessed-by-v23|reader_judgment' \
  02-系统详细设计-v1.0.md
```

Expected: the complete v2.3 system contract is absent before editing.

- [ ] **Step 2: Update the remaining document identities**

Change the `02` and `03` document revision headers from `v2.8` to the same user-approved revision used in `00` and `01`, update the date to `2026-09-01`, and add the same concise v2.3 change source. Do not change document status to implementation-complete, sample-validated, PowerPoint-checked, or user-visually-accepted.

- [ ] **Step 3: Add the exact system object and current head**

Add to the current-head table:

```text
visual/compilation-plan | visual-compilation-plan | 当前三层视觉合同的确定性原生实现计划
```

Document compiler identity `visual-semantic-compiler/v1`, handoff identity `codex-presentations-handoff/v23-v1`, atomic two-head write, exact input refs, `source_version`, policy ref, role runs, experience refs, per-slide fields, and canonical JSON determinism. Define `source_revision` as the atomic publication revision of `visual/contracts` and `visual/compilation-plan` (`expected_revision + 1`), not the later mutable project revision.

- [ ] **Step 4: Add validators, invalidation, lineage, and legacy behavior**

Document the exact new fields from the研发地图. Require:

```text
Visual Brief change -> design system/contracts/compilation/convergence/reviews/anchors/evidence stale
Design System change -> contracts/compilation/convergence/reviews/anchors/evidence stale
Contract Set change -> compilation/convergence/reviews/anchors/evidence stale; write new plan atomically
ReleaseTargetPolicy change -> current compilation plan invalid; G2/G3 locked by existing policy rules
G1/G2/final visual contract -> exact current compilation plan ref required
old visual artifact -> readable only as legacy / unassessed-by-v23
```

Do not state that migration or tests have already run.

- [ ] **Step 5: Add ContextPack and Presentations handoff constraints**

Specify that `build-native-first` accepts the current compilation plan as its only target ref; ContextPack resolves its bound current contract refs and carries object plan, connector semantics, asset plan, layout constraints, PowerPoint constraints, anti-pattern checks, evidence plan, output paths, expected revision, and authorization scope. Preserve the 43-tool public MCP catalog and the Python Runtime writer boundary.

- [ ] **Step 6: Add the minimal UI projection contract**

In `03`, add a v2.3 subsection that allows these visible additions only:

```text
Visual Brief: decision task, design stance, emotional/brand boundary, density strategy,
              forbidden patterns, five-second contract, optional philosophy references
Deck system: density/cross-slide rhythm, emphasis budget, image/diagram language,
             five-second rules
Slide contract: reader judgment, primary/secondary relationship, visual mechanism,
                focal point, asset roles, forbidden patterns, rhythm relations,
                text-density budget, PowerPoint requirements, evidence plan
```

State that `VisualCompilationPlan` is never a user-visible module. Preserve the accepted one-top-bar/two-view layout, anchor feedback behavior, overlay directions, contextual mark interaction, and absence of visible Gate/revision ledgers.

- [ ] **Step 7: Add UI acceptance IDs**

Add:

```text
UI-ACC-V23-VISUAL-001  new visual semantics render in source order inside the existing contract document
UI-ACC-V23-VISUAL-002  VisualCompilationPlan and technical lineage do not become visible modules
UI-ACC-V23-VISUAL-003  exact-field validation rejects undeclared backend fields
UI-ACC-V23-VISUAL-004  accepted top bar, views, drawers, anchor batch, and marking behavior are unchanged
UI-ACC-V23-VISUAL-005  new field display does not imply sample, PowerPoint, or user visual acceptance
```

### Task 4: Establish version-isolated v2.3 acceptance ledger and release verification

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/acceptance/ledger.py`
- Modify: `产品代码/scripts/build_acceptance_ledger.py`
- Modify: `产品代码/scripts/acceptance/verify_release.py`
- Modify: `产品代码/tests/test_acceptance_ledger.py`
- Modify: `产品代码/tests/test_v16_final_acceptance_verifier.py`
- Create: `产品代码/requirements/v2.3-acceptance-ledger.json`
- Create: `产品代码/requirements/v2.3-evidence.json`
- Verify unchanged: `产品代码/requirements/v2.2-acceptance-ledger.json`
- Verify unchanged: `产品代码/requirements/v2.2-evidence.json`

- [ ] **Step 1: Add RED tests for frozen v2.2 and independent v2.3 identities**

Add tests that require:

```text
v2.2 ledger version/count: 2.2 / 145
v2.2 ledger SHA-256: 3f328cd52877ce134ca11a8467c86868fec94bd5973d4d83ce44fbee8adcee8d
v2.2 evidence SHA-256: 3805ba2e5e09980ec8485b3fff84a40ddb484d6ec90fbccda37f1f3174ce4f14
v2.2 V23 requirement count: 0
v2.3 ledger version/count: 2.3 / 157
v2.3 V23 requirement count: 12
v2.3 evidence proofs: []
v2.3 requirement status: all unproven
v2.3 proof_refs: all empty
```

Patch the generator `ROOT` to a temporary directory, place sentinel v2.2 files there, run `build()`, and require that the sentinel bytes remain unchanged while v2.3 files are created. Require every `PRD-ACC-V23-VISUAL-*` item to retain `target-evidence` and `real-project` in addition to automated/runtime evidence.

- [ ] **Step 2: Add RED release-verifier version-selection tests**

Build a closed v2.2 fixture from the frozen v2.2 catalog and a closed v2.3 fixture from current baselines. Require both to verify in fixture mode. Relabeling the v2.3 catalog as v2.2 must fail with requirement identity drift rather than being accepted against current baselines.

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_acceptance_ledger \
    tests.test_v16_final_acceptance_verifier
```

Expected RED: the current v2.2/current-baseline comparison fails; v2.3 files do not exist; the generator overwrites the temporary v2.2 sentinel; v2.3 visual IDs lack the existing target/real-project proof obligations.

- [ ] **Step 3: Implement the minimal version-isolated generator**

Keep `build()` as the existing public entry point but make its identity explicit:

```python
LEDGER_VERSION = "2.3"

def build() -> tuple[AcceptanceLedger, Path]:
    requirements = authoritative_requirements()
    evidence_path = ROOT / "requirements" / "v2.3-evidence.json"
    if not evidence_path.is_file():
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(
                {"schema_version": "1.0", "proofs": []},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    ledger = AcceptanceLedger(
        version=LEDGER_VERSION,
        requirements=requirements,
    ).with_evidence(EvidenceIndex.from_path(evidence_path))
    target = ROOT / "requirements" / "v2.3-acceptance-ledger.json"
    target.write_text(
        json.dumps(
            ledger.as_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )
    return ledger, target
```

Do not add a mode that regenerates v2.2 from current baselines. Extend `_proof_kinds()` only so `PRD-ACC-V23-VISUAL-*` follows the existing visual evidence branch; do not change any checked-in v2.2 payload.

- [ ] **Step 4: Implement version-aware release authority**

Use exact frozen catalog identities for prior versions and current Markdown for v2.3:

```python
FROZEN_LEDGER_SHA256 = {
    "2.2": "3f328cd52877ce134ca11a8467c86868fec94bd5973d4d83ce44fbee8adcee8d",
}

def _authoritative_ledger(version: str, index: EvidenceIndex) -> AcceptanceLedger:
    if version == "2.3":
        requirements = _current_authoritative_requirements()
    elif version in FROZEN_LEDGER_SHA256:
        requirements = _frozen_authoritative_requirements(version)
    else:
        raise ValueError(f"Unsupported acceptance ledger version: {version}")
    return AcceptanceLedger(version, requirements).with_evidence(index)
```

The frozen loader must verify the checked-in catalog SHA-256, verify its embedded version, then strip stored proof/status fields before applying the caller-supplied evidence index. `_verify_ledger()` must parse the candidate first and call `_authoritative_ledger(checked_in.version, index)`.

- [ ] **Step 5: Run GREEN and generate the checked-in v2.3 files**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_acceptance_ledger \
    tests.test_v16_final_acceptance_verifier
python3 scripts/build_acceptance_ledger.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_acceptance_ledger \
    tests.test_v16_final_acceptance_verifier
```

Expected: focused suites pass; generator reports 157 v2.3 requirements; no v2.2 file changes.

- [ ] **Step 6: Verify no proof inheritance or frozen-file drift**

```bash
cd 产品代码
python3 -c 'import json; from pathlib import Path; p=json.loads(Path("requirements/v2.3-acceptance-ledger.json").read_text()); assert p["version"]=="2.3" and len(p["requirements"])==157; assert all(x["status"]=="unproven" and not x["proof_refs"] for x in p["requirements"]); e=json.loads(Path("requirements/v2.3-evidence.json").read_text()); assert e=={"schema_version":"1.0","proofs":[]}'
git diff --exit-code c7861e033fa14bba085ffe08a32dff8ef26495c1 -- \
  requirements/v2.2-acceptance-ledger.json requirements/v2.2-evidence.json
```

Expected: assertions pass and the frozen-file diff exits 0.

### Task 5: Cross-baseline consistency, full verification, and commit

**Files:**
- Verify: all four baselines
- Verify: v2.3 design, product map, R&D map, and five plans

- [ ] **Step 1: Verify all relative targets exist**

Run this exact Python read-only check from the repository root:

```bash
python3 -c 'from pathlib import Path; import re; files=[Path(x) for x in ["00-唯一研发基线索引-v1.0.md","01-产品需求基线-v1.0.md","02-系统详细设计-v1.0.md","03-UI设计与交互规范-v1.0.md"]]; missing=[]; [(missing.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\[[^]]+\]\((?!https?://)([^)#]+)",f.read_text(encoding="utf-8"))]; print(missing); raise SystemExit(bool(missing))'
```

Expected: `[]` and exit 0.

- [ ] **Step 2: Scan state overclaims, conflicts, and placeholders**

```bash
rg -n '^(<<<<<<<|=======|>>>>>>>)|TODO|TBD|适当处理|后续补充' \
  00-唯一研发基线索引-v1.0.md \
  01-产品需求基线-v1.0.md \
  02-系统详细设计-v1.0.md \
  03-UI设计与交互规范-v1.0.md
rg -n 'v2\.3.*(已实现|已通过|已验收|可交付)' \
  00-唯一研发基线索引-v1.0.md \
  01-产品需求基线-v1.0.md \
  02-系统详细设计-v1.0.md \
  03-UI设计与交互规范-v1.0.md
git diff --check
```

Expected: no conflict/placeholder hits; any “已批准” hit is limited to design or baseline authority, not implementation/sample/PowerPoint/user visual status; `git diff --check` exits 0.

- [ ] **Step 3: Run focused and full product verification**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v \
    tests.test_acceptance_ledger \
    tests.test_v16_final_acceptance_verifier
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm test
```

Expected: zero Python, Node, Widget, type, or build failures. These results are E2 automation only and do not prove any v2.3 visual mechanism, PPT sample, target PowerPoint, or user acceptance.

- [ ] **Step 4: Verify scope**

```bash
git status --short
git diff --stat
git diff --name-only
```

Expected: changes are limited to the four baselines, this R0 plan, the approved ledger generator/verifier infrastructure and tests, and the two new v2.3 requirement files. No visual-domain implementation, Skill, MCP, Widget, sample, Runtime, plugin, or PPTX file is changed.

- [ ] **Step 5: Commit the R0 rollback unit**

```bash
git add \
  00-唯一研发基线索引-v1.0.md \
  01-产品需求基线-v1.0.md \
  02-系统详细设计-v1.0.md \
  03-UI设计与交互规范-v1.0.md \
  产品代码/docs/superpowers/plans/2026-09-01-v23-baseline-contract-migration.md \
  产品代码/src/ai_ppt_studio/acceptance/ledger.py \
  产品代码/scripts/build_acceptance_ledger.py \
  产品代码/scripts/acceptance/verify_release.py \
  产品代码/tests/test_acceptance_ledger.py \
  产品代码/tests/test_v16_final_acceptance_verifier.py \
  产品代码/requirements/v2.3-acceptance-ledger.json \
  产品代码/requirements/v2.3-evidence.json
git diff --cached --check
git commit -m "feat: establish v2.3 visual quality acceptance contracts"
```

Expected: one non-amended local commit on `codex/v23-baseline-contract-20260901`; no merge, push, Worktree deletion, plugin install, or publication.

## R0 exit report

Report separately:

```text
baseline contract migration: implemented and committed / not implemented
document checks: passed / failed
v2.3 ledger isolation: passed / failed
v2.2 ledger/evidence: unchanged / drifted
product visual mechanism: not implemented
real PPT sample: not run
target PowerPoint: not checked
user visual acceptance: not requested
integration into codex/v23-visual-quality-20260831: awaiting user decision
```
