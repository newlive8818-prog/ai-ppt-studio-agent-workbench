# v2.3 Two-Slide Runtime Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the approved v2.3 visual-semantic mechanism on source slides 5 and 8, create one native editable two-slide PPTX with Codex Presentations, and record V0–V3 evidence without advancing any v2.2 Runtime Gate or expanding to the full deck.

**Architecture:** Use a dedicated Git Worktree for experiment scripts and a separate managed Runtime project for sample artifacts and evidence. Validate the real source hash, build immutable experiment contracts with the R1 compiler, hand the exact plan to a JavaScript `@oai/artifact-tool` builder, then keep automation, human review, macOS PowerPoint inspection, and user judgment in separate evidence records. The experiment uses no standard G0/G3/G4 claim; fixture prerequisites are explicitly labeled and cannot be promoted into v2.2 acceptance.

**Tech Stack:** Python 3.11+ validators and artifact kernel, JavaScript ES modules, `@oai/artifact-tool`, Codex Presentations render/overflow helpers, optional Image 2 for a replaceable non-text illustration, Microsoft PowerPoint for macOS, JSON evidence ledgers, Git.

---

## Execution isolation

- Required integrated predecessor: R3 approved and fast-forwarded into `codex/v23-visual-quality-20260831`.
- Execution branch: `codex/v23-two-slide-experiment-20260901`.
- Execution Worktree: `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v23-two-slide-experiment-20260901`.
- Independent Runtime project: `/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901`.
- Create both only after the user selects R4 and the integration Worktree is clean.
- Never write to the source PPTX, quarantine Worktree, v2.2 Runtime project, v2.2 integration branch, freeze tag, or public plugin location.
- R4 completion does not authorize R5 or a 27-page rewrite.

## Authoritative source identity

```text
source: /Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx
expected SHA-256: da54a46ea9dd91aa7643f502f09970c1bdf72c59a7a08e59928db647ce134cd1
source slide 5: AI 改变的不是按钮，而是产品的执行主体
source slide 8: 把 AI 的设计知识固化进工程
```

The source deck supplies content and comparison evidence, not a layout template. R4 uses the approved custom visual direction, not template following or Codex Grid. It does not modify, duplicate, or claim ownership of the source deck's master/theme.

## File map

- Create `scripts/experiments/v23-two-slide/prepare_experiment.py`: verify source identity; initialize the isolated mechanism project; validate and persist the two-page source, three visual contracts, and deterministic compilation plan under experiment-only heads.
- Create `scripts/experiments/v23-two-slide/build_two_slide.mjs`: consume only the emitted plan/contract JSON; create the two-slide native PPTX with `@oai/artifact-tool`.
- Create `scripts/experiments/v23-two-slide/verify_experiment.py`: verify hashes, native/bitmap routing ledger, required files, evidence-state separation, and no v2.2 Gate claims.
- Create `tests/test_v23_two_slide_experiment.py`: script payload, source/hash guard, contract closure, deterministic plan, and evidence-ledger tests using a temporary directory.
- Create nothing under the source `分享材料/` directory.
- Runtime-only, not Git: project manifest, source manifest/render copy, contract JSON, compilation-plan JSON, optional image asset, output PPTX, page renders, montage, automated ledger, human-review ledger, PowerPoint ledger, user-judgment ledger, revision history, and bounded experience candidate.

## Runtime project layout

```text
v23-visual-quality-two-slide-experiment-20260901/
├── project.json
├── source/
│   ├── source-manifest.json
│   ├── source-slide-5.png
│   └── source-slide-8.png
├── contracts/
│   ├── visual-brief.json
│   ├── deck-design-system.json
│   ├── slide-visual-contract-set.json
│   └── visual-compilation-plan.json
├── assets/
│   ├── asset-manifest.json
│   └── slide-5-structure-illustration.png   # only when Image 2 is actually used
├── output/
│   ├── v23-two-slide-experiment.pptx
│   ├── v23-two-slide-experiment/
│   │   ├── slide-1.png
│   │   └── slide-2.png
│   └── montage.png
├── evidence/
│   ├── automated-validation.json
│   ├── human-visual-review.json
│   ├── macos-powerpoint-check.json
│   ├── user-visual-judgment.json
│   └── experience-candidate.json
└── revisions/
    └── <revision-id>/...
```

Every evidence file must exist. Before its stage runs, it contains `{"status":"not-run"}` rather than a false success.

### Task 1: Establish the isolated experiment project and V0 contracts

**Files:**
- Create: `scripts/experiments/v23-two-slide/prepare_experiment.py`
- Create: `tests/test_v23_two_slide_experiment.py`
- Runtime output: `project.json`, source manifest/renders, and `contracts/*.json`

- [ ] **Step 1: Add RED source-identity and isolation tests**

In a temporary directory, call `prepare_experiment.prepare()` with a copied file whose bytes do not match the expected SHA-256 and require:

```text
SOURCE_IDENTITY_MISMATCH
```

Assert no project directory is created. With the correct fixture bytes, assert all emitted paths stay below the explicit experiment root and none point to the source directory, repository, quarantine, or another Runtime project.

- [ ] **Step 2: Add RED contract-content tests**

Assert the script defines this project identity:

```python
{
    "project_id": "v23-visual-quality-two-slide-experiment-20260901",
    "project_type": "v23-visual-mechanism-experiment",
    "product_version": "v2.3",
    "source_identity": "sharing-deck-mechanism-sample",
    "gate_claims": {
        "G0": "not-applicable-mechanism-sample",
        "G1": "not-claimed-by-experiment",
        "G2": "not-claimed-by-experiment",
        "G3": "not-claimed-by-experiment",
        "G4": "not-claimed-by-experiment",
    },
}
```

The script must never write `gate/G0/confirmation`, `gate/G3/confirmation`, or `gate/G4/confirmation` heads.

- [ ] **Step 3: Define the exact two-slide frozen source payload**

Use two slides only, with stable IDs `S05` and `S08`. Preserve the source titles and visible text extracted during read-only inspection. The script must fail if the extracted source title does not match the expected title above; it must not invent customer facts, numbers, cases, or claims.

The experiment ReadingDeckBlueprint is an immutable fixture input under `experiment/content/reading-blueprint`, not a claimed user-approved G0 artifact.

- [ ] **Step 4: Define the Visual Brief**

Embed these exact strategic values and complete the existing required v2.2 fields:

```python
{
    "decision_task": "让读者先理解 AI 执行主体变化，再理解设计知识如何进入受治理工程",
    "design_stance": "编辑化、技术可信、克制，不使用组件库式科技模板",
    "emotional_boundary": "理性、清晰、具有张力；不使用炫技、未来主义发光或夸张情绪",
    "brand_boundary": "无客户品牌推断；以中性墨色、暖白和单一冷色强调建立一致性",
    "density_strategy": "S05 低密度图像主导；S08 中密度结构主导；两页轮廓明显不同",
    "forbidden_patterns": [
        "平均三卡片",
        "无意义图标",
        "泛蓝紫发光科技感",
        "无语义连线",
        "整页位图",
        "只靠标题表达主张",
    ],
}
```

The five-second contract records first noticed object, perceived message, perceived relationship, next reading step, and misdirection. `design_philosophy_refs` records reading order, structural chapter focus, observer viewpoint, evidence-to-judgment logic, and goal-layout-composition as non-gating references.

- [ ] **Step 5: Define the Deck Design System**

Use:

```text
theme: editorial engineering, warm-white canvas, near-black ink, one restrained blue accent
typography: Chinese sans-serif with macOS/Windows fallback; titles >= 35 pt; body >= 16 pt
composition: flat canvas, asymmetric focal composition, no card wall or UI chrome
density rhythm: low-density visual relationship -> medium-density governed sequence
emphasis budget: one primary focal point, at most two accent roles, at most two consecutive high-density pages
image language: one narrative image only when it carries structure/explanation; no decorative background
diagram language: native shapes/connectors, directional meaning, unequal stage weight, connectors behind nodes
```

Include binary rule definitions for frozen content, one focal point, semantic connectors, native text/relationships, separate replaceable images, no whole-slide bitmap, no overflow, and evidence-state separation.

- [ ] **Step 6: Define S05 and S08 contracts**

S05:

```text
reader_judgment: 主要执行责任从人转向 AI，软件承担治理与事实边界
primary_relationship: system-boundary
secondary_relationship: network
visual_mechanism: 一张结构／解释型主图形成主体转移，原生边界与责任标注建立治理关系
focal_point: AI 成为主要执行者的转移节点
asset role: structure or explanation; independent replaceable layer; contains no factual text
reading path: title -> human/AI responsibility shift -> software governance boundary -> conclusion
forbidden: three equal cards, floating labels, particles, decorative lines, equal-weight actors
```

S08:

```text
reader_judgment: 设计知识必须经过视觉合同、编译、原生实现和 Gate 才能进入交付
primary_relationship: sequence
secondary_relationship: evidence-to-judgment
visual_mechanism: 不等权的原生路径与门；放大合同到原生交付的关键转化段
focal_point: Visual Contract -> Compilation Plan -> Native PPTX
asset roles: []
reading path: design knowledge -> contracts -> compilation -> native build -> evidence gates
forbidden: equal-spaced node list, directionless line, color-only stages, English-term inventory
```

For both pages, `powerpoint_implementation_requirements` and `acceptance_evidence_plan` must use the exact R1 closed structures. All visible semantic text and relations remain native.

- [ ] **Step 7: Add deterministic plan and evidence-state tests**

Call the integrated R1 validators and compiler. Assert two runs produce byte-identical canonical JSON and the same `artifact://visual-compilation-plan/<sha256>` ref. Initialize all five evidence ledgers as:

```json
{"status":"not-run","evidence_refs":[],"result":null}
```

Require `verify_experiment.py` to reject any ledger that sets `result: "passed"` while `status` is `not-run` or lacks evidence refs.

- [ ] **Step 8: Run RED**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_two_slide_experiment
```

Expected: missing script/import failures.

- [ ] **Step 9: Implement `prepare_experiment.py` with atomic temp-to-final creation**

Build into a sibling temporary directory created by `tempfile.mkdtemp()`. Verify source hash before creating it. Write UTF-8 canonical JSON with sorted keys and a trailing newline. Render source pages read-only into the temp project, then rename the complete directory to the final explicit Runtime path only when every contract validates. If the final path already exists, stop and require a new revision directory; never overwrite or delete it.

- [ ] **Step 10: Run GREEN and create V0 evidence**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_two_slide_experiment
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 scripts/experiments/v23-two-slide/prepare_experiment.py \
  --source '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx' \
  --project-root '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901'
```

Expected: tests pass; source hash matches; exactly two source renders and four contract JSON files exist; V0 can be marked `passed` only with contract refs and compiler ref. This is E3 input preparation, not a product Gate.

### Task 2: Create the native two-slide PPTX with Codex Presentations

**Files:**
- Create: `scripts/experiments/v23-two-slide/build_two_slide.mjs`
- Temporary build input: `$TMP_DIR/source-notes.txt`
- Runtime output: optional image asset, PPTX, renders, montage, and evidence bindings to the source-notes hash

- [ ] **Step 1: Load the presentation runtime and read required local documentation**

Invoke `load_workspace_dependencies` and capture the returned absolute Node executable, Node packages, and override binary directory as command-scoped `RUNTIME_NODE`, `RUNTIME_NODE_MODULES`, and `RUNTIME_BIN_DIR`. Read completely:

```text
<Presentations skill>/artifact_tool_docs/API_QUICK_START.md
<Presentations skill>/artifact_tool_docs/api/API_DOCS.md
```

Expected: all three runtime paths exist. If any is missing, stop as a capability blocker; do not install or search for alternate runtimes.

- [ ] **Step 2: Inspect source pages and contract inputs read-only**

Inspect the complete source slides 5 and 8, including title, visible copy, imagery, notes, and object relationships. Compare them with the source renders and contract JSON. Keep the required provenance record at `$TMP_DIR/source-notes.txt`, bind its hash in the automated evidence ledger, and embed `[Sources]` blocks in the output slide notes. Do not edit the source PPTX.

- [ ] **Step 3: Resolve the S05 image layer only if it serves the contract**

First determine whether the source deck already contains a lawful, extractable, sufficiently sharp structure/explanation asset with known provenance. If it does, copy that asset into the experiment project and record its source slide/object identity.

If it does not, use the `imagegen` skill for one non-sensitive, text-free, landscape structure/explanation illustration. The prompt must reserve clear negative space for native labels and express a human-to-AI responsibility shift inside a governed software boundary. The generated image cannot contain words, numbers, logos, UI, icons, or claims. Record provider, prompt, output hash, role, replaceability, and crop. If neither source nor generated asset meets the contract, stop V1; do not substitute a decorative technology background.

- [ ] **Step 4: Add RED builder-source tests**

In `tests/test_v23_two_slide_experiment.py`, read `build_two_slide.mjs` and require:

```text
bare @oai/artifact-tool import includes Presentation and PresentationFile
python-pptx absent
PptxGenJS absent
exact plan path required
exact output path required
two slides only
connectors are created before nodes on S08
[Sources] speaker-note blocks present
PPTX export uses PresentationFile.exportPptx
```

Require the builder to exit non-zero when the plan hash, source hash, or slide IDs are not exact.

- [ ] **Step 5: Run the authoring-operation marker exactly once**

Immediately before the first create command, from the Presentations skill directory run as one standalone command:

```bash
node container_tools/mark_artifact_operation_started.mjs \
  --operation-kind create \
  --expected-output-count 1 \
  --output-format pptx
```

Expected: exit 0. Do not run it during read-only inspection and do not run it a second time for the same build.

- [ ] **Step 6: Implement S05 as an image-led asymmetric composition**

The builder must:

- use a 16:9 slide and equal outer margins;
- keep the source title native at 35 pt or larger on one line;
- place the narrative image as a separate replaceable layer, not a full-slide bitmap;
- keep `人 / AI / 软件治理边界` labels and responsibility statements native;
- use scale, position, foreground/background, and direction to make the responsibility shift the single focal point;
- use no equal cards, pills, badges, UI chrome, decorative particles, or meaningless arrows;
- add `[Sources]` notes for the source slide and image asset.

- [ ] **Step 7: Implement S08 as a native unequal sequence**

The builder must:

- keep the source title native at 35 pt or larger on one line;
- create directional connectors before entity nodes so edges stay behind nodes;
- render `设计知识 → Visual Brief / Deck Design System / Slide Visual Contract → VisualCompilationPlan → 原生 PPTX → 证据层` as a governed path, with the contract-to-native transformation visually larger than the input/output stages;
- use native shapes, text, connectors, and page marker; no diagram screenshot or baked text;
- distinguish inputs, transformation, and evidence gates through position/scale before color;
- keep body text at 16 pt or larger;
- add `[Sources]` notes for the source slide and contract/plan refs.

- [ ] **Step 8: Export with the bundled runtime**

Create a `node_modules` symlink in a temporary build directory pointing to the returned `RUNTIME_NODE_MODULES`, then execute `build_two_slide.mjs` with the returned `RUNTIME_NODE`. The builder writes only:

```text
/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901/output/v23-two-slide-experiment.pptx
```

If the file exists, write into a new `revisions/<revision-id>/output/` directory; never overwrite the prior result.

- [ ] **Step 9: Render and inspect every slide**

Use the bundled Presentations helpers:

```bash
python3 '<Presentations skill>/container_tools/render_slides.py' \
  '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901/output/v23-two-slide-experiment.pptx'
python3 '<Presentations skill>/container_tools/slides_test.py' \
  '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901/output/v23-two-slide-experiment.pptx'
python3 '<Presentations skill>/container_tools/create_montage.py' \
  --input_dir '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901/output/v23-two-slide-experiment' \
  --output_file '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901/output/montage.png'
```

Inspect slide 1 and slide 2 individually at full size. The montage is only for silhouette/rhythm comparison. Fix all unintended overlap, clipping, wrapping, crop, connector, font, source-note, object, and editability defects before V1 passes.

- [ ] **Step 10: Record V1 without overclaiming**

`automated-validation.json` may record `status: "passed"` only when it binds the exact PPTX SHA-256, two render hashes, compilation-plan ref, source hash, object/editability ledger, and zero unresolved overlap/overflow results. It must separately state:

```json
{
  "mechanism_implemented": true,
  "automated_validation": "passed",
  "real_sample_used": true,
  "target_powerpoint_checked": false,
  "user_visual_accepted": false
}
```

### Task 3: Run V2 human review and macOS PowerPoint inspection

**Files:**
- Create: `scripts/experiments/v23-two-slide/verify_experiment.py`
- Modify: `tests/test_v23_two_slide_experiment.py`
- Runtime output: `evidence/human-visual-review.json`, `evidence/macos-powerpoint-check.json`

- [ ] **Step 1: Implement evidence-ledger validation**

Require every passed result to bind:

```text
source PPTX hash
source page number
current output PPTX hash
render hash
contract ref
compilation-plan ref
reviewer identity
timestamp
specific observations or target-environment facts
```

Reject total-score-only review, missing page regions, unbound screenshots, or a user result copied into the PowerPoint ledger.

- [ ] **Step 2: Perform the human visual review**

For each page, record binary results and evidence for:

- five-second judgment matches `reader_judgment`;
- page body, not title alone, expresses the claim;
- exactly one primary focal point;
- primary relationship is readable;
- image/diagram has a non-decorative task;
- reading path is clear;
- text density and hierarchy support reading;
- named anti-patterns are absent or have an allowed exception;
- the page looks like a real presentation, not a UI component demo;
- the two pages have distinct but coherent silhouettes.

Any failure records `pattern_id`, page region, observation, evidence ref, and repair mechanism. Do not average it away with a score.

- [ ] **Step 3: Inspect the exact PPTX in Microsoft PowerPoint for macOS**

This stage genuinely requires the native PowerPoint UI. Use direct file inspection and PowerPoint-supported interfaces first; if no purpose-built control is available, announce the reason and use the `computer-use` skill narrowly for the target-app check.

Open the exact hashed PPTX and verify both slides at 100% and slideshow view. For each slide check:

```text
font names and substitutions
title remains one line
text wrapping and line breaks
image crop and sharpness
connector direction and z-order
shape alignment and grouping
native text/shape/connector editability
image remains an independent replaceable layer
save/reopen stability
```

Capture target application name/version, macOS version, exact PPTX hash, page screenshots, edit actions, observed substitutions, and result. If PowerPoint is unavailable, set `status: "blocked"`; do not substitute LibreOffice, WPS, preflight render, or automation.

- [ ] **Step 4: Repair and rerun V1/V2 when needed**

Preserve the failed PPTX/render/evidence under `revisions/<revision-id>/`. Make a narrow builder or asset change, create a new PPTX hash, rerun automated validation, full-size human review, and the target PowerPoint check. Never edit evidence to make an old hash appear current.

- [ ] **Step 5: Run the verifier**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 scripts/experiments/v23-two-slide/verify_experiment.py \
  --project-root '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901'
```

Expected: V0 and V1 pass; V2 passes only when human and macOS PowerPoint ledgers both bind the current PPTX hash. User judgment may remain `not-run` at this stage.

### Task 4: Obtain V3 user judgment and write bounded experience evidence

**Files:**
- Runtime output: `evidence/user-visual-judgment.json`
- Runtime output: `evidence/experience-candidate.json`

- [ ] **Step 1: Present the actual current pages to the user**

Show both full-size renders and provide the exact current PPTX. Ask the user to judge each page as `accepted | revise | rejected`, focusing on five-second judgment, visual focus, template feeling, reading path, relation between evidence and viewpoint, and real-use willingness.

Do not ask the user to approve code, tests, or a score. Do not infer acceptance from silence, download, PowerPoint opening, or a previous design-spec approval.

- [ ] **Step 2: Bind the explicit result**

Write `user-visual-judgment.json` only after the user replies. It must include the exact message ref or transcript excerpt, timestamp, PPTX hash, slide IDs/pages, result per page, requested changes, and overall permission:

```json
{
  "expand_to_formal_samples": false
}
```

This value remains false unless the user separately authorizes R5 after reviewing V0–V3.

- [ ] **Step 3: Write the experience candidate or no-entry reason**

If accepted, write a `same-type` visual candidate containing only the observed mechanism, anti-patterns avoided, applicability, counterexamples, failure boundaries, before/after refs, PowerPoint evidence refs, and user outcome ref. Do not include source deck content, full-page design, customer facts, images, logos, or source material.

If revised/rejected, write a failure anti-pattern candidate or `no-entry` record with the explicit reason. Never create `global` experience in R4 unless the user explicitly gives a global instruction; two sharing-sample pages do not satisfy cross-type proof.

- [ ] **Step 4: Run the final experiment verifier**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 scripts/experiments/v23-two-slide/verify_experiment.py \
  --project-root '/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901' \
  --require-v3
```

Expected: V0–V3 each bind the same current PPTX/contract lineage; the experience record is `same-type` or `no-entry`; `expand_to_formal_samples` remains false unless separately authorized.

### Task 5: Verify repository scope and commit experiment tooling

**Files:**
- Verify: experiment scripts and tests only

- [ ] **Step 1: Run repository tests for experiment tooling**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest -v tests.test_v23_two_slide_experiment
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm run test:node
npm run test:widget -- --configLoader runner
npm run build
```

Expected: all available suites pass. The actual visual outcome is still reported from V0–V3, not from these tests.

- [ ] **Step 2: Verify the source and forbidden paths remain unchanged**

```bash
shasum -a 256 \
  '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx'
git status --short
git diff --check
```

Expected: source hash remains `da54a46ea9dd91aa7643f502f09970c1bdf72c59a7a08e59928db647ce134cd1`; Git changes are limited to `scripts/experiments/v23-two-slide/` and `tests/test_v23_two_slide_experiment.py`; Runtime outputs remain outside Git.

- [ ] **Step 3: Scan prohibited implementations and placeholders**

```bash
cd 产品代码
rg -n 'TODO|TBD|适当处理|后续补充|NotImplemented|python-pptx|PptxGenJS' \
  scripts/experiments/v23-two-slide \
  tests/test_v23_two_slide_experiment.py
rg -n 'gate/G[034]/confirmation|public.*publish|plugin.*install' \
  scripts/experiments/v23-two-slide \
  tests/test_v23_two_slide_experiment.py
```

Expected: no placeholders, prohibited PPTX libraries, standard user-Gate writes, install, or publish actions.

- [ ] **Step 4: Commit tooling as separate rollback units**

```bash
git add \
  scripts/experiments/v23-two-slide/prepare_experiment.py \
  scripts/experiments/v23-two-slide/verify_experiment.py \
  tests/test_v23_two_slide_experiment.py
git commit -m "test: establish v2.3 two-slide experiment evidence"

git add scripts/experiments/v23-two-slide/build_two_slide.mjs
git commit -m "test: build v2.3 native visual experiment"
```

Expected: two non-amended local commits; no generated PPTX or Runtime evidence is committed; no merge, push, Worktree deletion, plugin install, or publication.

## R4 exit report

Report each level independently:

```text
E1 mechanism implementation: inherited from integrated R1-R3; exact commit refs
E2 automated verification: passed / failed / blocked, exact commands and hashes
E3 real PPT sample validation: passed / failed for S05 and S08, exact evidence refs
E4 macOS PowerPoint check: passed / failed / blocked, exact app/file evidence
E5 user visual judgment: accepted / revise / rejected / not-run, exact current hash
same-type experience: written / no-entry / pending user evidence
R5 expansion: not authorized unless the user separately says so
integration into codex/v23-visual-quality-20260831: awaiting user decision
```
