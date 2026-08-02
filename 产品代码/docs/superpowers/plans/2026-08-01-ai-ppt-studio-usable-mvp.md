# AI PPT Studio Usable MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the verified isolated runtime foundation into an installed Codex Skill that can create/resume a presentation project, persist content and visual decisions, generate offline review pages, route PPTX work through Codex Presentations, and complete a real editable-PPTX smoke project.

**Architecture:** Keep AI PPT Studio as the orchestration, state, review, and experience layer. GPT performs content and design reasoning, Image 2 supplies concept visuals without an additional product privacy gate, and Codex Presentations is the only PPTX read/create/edit/render/inspection execution layer. Runtime code remains dependency-free Python; review pages are self-contained HTML generated from versioned JSON artifacts.

**Tech Stack:** Python 3.11+ standard library, `unittest`, offline HTML/CSS/JavaScript, Codex Image 2, Codex Presentations with `@oai/artifact-tool`, official Skill validator.

## Global Constraints

- Never write outside the configured managed runtime root except the explicit Skill installation target.
- Never mutate user-provided source materials or the upstream Web product directory.
- AI does not search for customer-project sources; it only consumes materials the user provides.
- Do not build a second PPT editor or compiler. All PPTX work uses Codex Presentations.
- Do not use `python-pptx`.
- Do not use whole-slide bitmaps to claim editability.
- Visible facts, text, numbers, tables, charts, and key relationships remain native editable objects.
- Image 2 may use user-provided project materials without a separate AI PPT Studio privacy gate.
- Every new runtime behavior follows red-green-refactor TDD.
- Every local PPTX smoke deliverable is rendered slide-by-slide and checked for overflow.

---

### Task 1: Discover the Existing Managed Workspace Without Repeating Root Arguments

**Files:**
- Modify: `src/ai_ppt_studio/config.py`
- Modify: `src/ai_ppt_studio/cli.py`
- Modify: `skill/ai-ppt-studio/scripts/ai_ppt_runtime.py`
- Test: `tests/test_workspace_profile.py`

**Interfaces:**
- Produces: `RuntimeConfig.from_workspace_file(path: Path) -> RuntimeConfig` supporting the existing `workspace.json` keys `workspace_root`, `source_repository`, `future_install_root`, and `protected_roots`.
- Produces: CLI option `--workspace-config PATH`; when all four explicit roots are absent, default to environment variable `AI_PPT_WORKSPACE_CONFIG`, then `/Users/defei/Documents/AI-PPT-Workspace/workspace.json` when present.
- Preserves: explicit root arguments as the highest-priority override.

- [ ] **Step 1: Write the failing profile-discovery test**

```python
def test_cli_uses_workspace_profile_without_repeated_roots(self) -> None:
    profile = base / "workspace.json"
    profile.write_text(json.dumps({
        "schema_version": "1.0",
        "workspace_root": str(base / "runtime"),
        "source_repository": str(base / "repo"),
        "future_install_root": str(base / "install"),
        "protected_roots": [str(base / "web")],
    }), encoding="utf-8")
    result = self.run_cli("--workspace-config", str(profile), "init", "--name", "方案")
    self.assertEqual(result.returncode, 0, result.stderr)
```

- [ ] **Step 2: Run `python3 -m unittest tests/test_workspace_profile.py -v`**

Expected: FAIL because `--workspace-config` is unknown.

- [ ] **Step 3: Implement profile parsing and CLI precedence**

Parse the existing workspace file without rewriting it. Use the first protected root that is not the source repository or install root as `upstream_root`; preserve all remaining roots in `extra_protected_roots`. Raise `ConfigurationError` when required keys are missing.

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_workspace_profile.py -v
python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_ppt_studio/config.py src/ai_ppt_studio/cli.py skill/ai-ppt-studio/scripts/ai_ppt_runtime.py tests/test_workspace_profile.py
git commit -m "feat: discover managed AI PPT workspace"
```

---

### Task 2: Persist Versioned Content, Visual, Scene-Graph, Feedback, and Delivery Artifacts

**Files:**
- Modify: `src/ai_ppt_studio/models.py`
- Create: `src/ai_ppt_studio/artifact_store.py`
- Create: `skill/ai-ppt-studio/assets/content-blueprint-schema.json`
- Create: `skill/ai-ppt-studio/assets/visual-contract-schema.json`
- Create: `skill/ai-ppt-studio/assets/slide-scene-graph-schema.json`
- Modify: `src/ai_ppt_studio/cli.py`
- Test: `tests/test_artifact_store.py`

**Interfaces:**
- Produces: `ArtifactKind` enum values `mission`, `content-blueprint`, `visual-brief`, `concept-set`, `visual-contract`, `slide-scene-graph`, `feedback`, `presentation-handoff`, and `delivery`.
- Produces: `ArtifactStore(project_root: Path, policy: PathPolicy).save(kind: ArtifactKind, payload: dict[str, object]) -> ArtifactVersion`.
- Produces: `ArtifactStore.latest(kind: ArtifactKind) -> ArtifactVersion`.
- Produces CLI commands `save-artifact`, `show-artifact`, and `list-artifacts`.

- [ ] **Step 1: Write the failing versioning test**

```python
def test_save_creates_immutable_versions_and_latest_pointer(self) -> None:
    first = store.save(ArtifactKind.CONTENT_BLUEPRINT, {"title": "V1", "slides": []})
    second = store.save(ArtifactKind.CONTENT_BLUEPRINT, {"title": "V2", "slides": []})
    self.assertEqual(first.version, 1)
    self.assertEqual(second.version, 2)
    self.assertEqual(store.latest(ArtifactKind.CONTENT_BLUEPRINT).payload["title"], "V2")
    self.assertTrue(Path(first.path).is_file())
```

- [ ] **Step 2: Run `python3 -m unittest tests/test_artifact_store.py -v`**

Expected: FAIL because `artifact_store` does not exist.

- [ ] **Step 3: Implement immutable version files**

Map kinds to existing project directories. Write `v0001.json`, `v0002.json`, and an atomic `latest.json` pointer containing kind, version, path, hash, and timestamp. Never overwrite a version file. Append `project.artifact.saved` to the project event log.

- [ ] **Step 4: Add minimum semantic validation**

Require:

- content blueprint: non-empty `title`, `audience`, `goal`, and a non-empty `slides` list;
- each slide: `slide_id`, `title`, `purpose`, `claim`, `visible_content`, `speaker_notes`, `source_refs`, and `material_refs`;
- visual contract: `design_thesis`, `palette`, `typography`, `layout_rules`, `image_language`, `editability_rules`;
- scene graph: `slide_id`, `width`, `height`, and `elements`;
- presentation handoff: content, visual, scene-graph, output PPTX, render directory, and source-note references.

Invalid payloads raise `ArtifactValidationError`, a new `AiPptError` subtype.

- [ ] **Step 5: Add CLI tests and run the full suite**

Run:

```bash
python3 -m unittest tests/test_artifact_store.py -v
python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_ppt_studio/models.py src/ai_ppt_studio/artifact_store.py src/ai_ppt_studio/cli.py src/ai_ppt_studio/errors.py skill/ai-ppt-studio/assets tests/test_artifact_store.py
git commit -m "feat: version AI PPT project artifacts"
```

---

### Task 3: Generate Rebuildable Offline Review Pages

**Files:**
- Create: `src/ai_ppt_studio/review_html.py`
- Create: `skill/ai-ppt-studio/assets/review-template.html`
- Modify: `src/ai_ppt_studio/cli.py`
- Test: `tests/test_review_html.py`

**Interfaces:**
- Produces: `ReviewKind` enum values `content`, `concept`, `engineering`, and `delivery`.
- Produces: `ReviewHtml(project_root: Path, policy: PathPolicy).generate(kind: ReviewKind) -> Path`.
- Produces CLI command `review --project PATH --kind KIND`.

- [ ] **Step 1: Write the failing content-review test**

```python
def test_content_review_is_offline_and_contains_slide_decisions(self) -> None:
    path = ReviewHtml(project, policy).generate(ReviewKind.CONTENT)
    body = path.read_text(encoding="utf-8")
    self.assertIn("内容蓝图集中审阅", body)
    self.assertIn("客户为什么现在需要建设", body)
    self.assertNotIn("https://", body)
    self.assertNotIn("http://", body)
    self.assertIn("data-review-action", body)
```

- [ ] **Step 2: Run `python3 -m unittest tests/test_review_html.py -v`**

Expected: FAIL because `review_html` does not exist.

- [ ] **Step 3: Implement one self-contained renderer**

Embed CSS and JavaScript. Escape all project content. Use relative local image references only. Include project/version/gate/source information, selectable decision cards, reject buttons, a natural-language feedback textarea, and an “export decision JSON” browser action. Generated review pages are disposable and live under `reviews/<kind>-review.html`.

- [ ] **Step 4: Implement all four review modes**

- content: chapters, per-slide purpose/claim/content/notes/materials/sources;
- concept: visual brief and side-by-side concept directions;
- engineering: concept sample, scene preview, rendered PPT image, and editability notes;
- delivery: slide renders, issue status, source coverage, and final acceptance.

- [ ] **Step 5: Run HTML structural validation and all tests**

Use Python `html.parser.HTMLParser`, assert no external scripts/styles, then run the full test suite.

- [ ] **Step 6: Commit**

```bash
git add src/ai_ppt_studio/review_html.py src/ai_ppt_studio/cli.py skill/ai-ppt-studio/assets/review-template.html tests/test_review_html.py
git commit -m "feat: generate offline AI PPT review pages"
```

---

### Task 4: Turn the Thin Skill Into the Complete Codex Orchestrator

**Files:**
- Modify: `skill/ai-ppt-studio/SKILL.md`
- Create: `skill/ai-ppt-studio/references/content-workflow.md`
- Create: `skill/ai-ppt-studio/references/visual-workflow.md`
- Create: `skill/ai-ppt-studio/references/presentations-handoff.md`
- Create: `skill/ai-ppt-studio/references/review-and-feedback.md`
- Create: `skill/ai-ppt-studio/references/experience-evolution.md`
- Test: `tests/test_skill_workflow.py`

**Interfaces:**
- Consumes: installed runtime wrapper, Image 2, and Codex Presentations.
- Produces: a thin routing `SKILL.md` under 220 lines.
- Produces: explicit G0-G4 flow, automatic work between concentrated user decisions, and a Presentations handoff contract.

- [ ] **Step 1: Write the failing routing-contract test**

```python
def test_skill_routes_pptx_to_codex_presentations(self) -> None:
    body = SKILL.read_text(encoding="utf-8")
    self.assertIn("Codex Presentations", body)
    self.assertIn("Do not build or use a second PPTX editor", body)
    self.assertIn("Image 2", body)
    self.assertIn("G0", body)
    self.assertIn("G4", body)
```

- [ ] **Step 2: Run `python3 -m unittest tests/test_skill_workflow.py -v`**

Expected: FAIL because the routing contract is absent.

- [ ] **Step 3: Implement the thin router and focused references**

The router must:

1. load the isolation policy first;
2. use the managed workspace profile;
3. initialize or resume a project;
4. ingest only user-provided materials and let AI classify them;
5. finish content and pass G0 before visual discussion;
6. use Image 2 for concept collaboration when it improves the visual decision;
7. use Codex Presentations for every PPTX operation;
8. render and inspect every slide before G2/G4;
9. record feedback and candidate experience;
10. ask only high-impact product/content/visual questions, never implementation questions.

- [ ] **Step 4: Validate the Skill and run tests**

Run:

```bash
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/ai-ppt-studio
python3 -m unittest discover -s tests -v
```

Expected: official validation and all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/ai-ppt-studio tests/test_skill_workflow.py
git commit -m "feat: orchestrate complete AI PPT workflow"
```

---

### Task 5: Install the Portable Skill Safely

**Files:**
- Create: `scripts/install_skill.py`
- Modify: `scripts/build_skill_bundle.py`
- Test: `tests/test_install_skill.py`

**Interfaces:**
- Produces: `install_bundle(bundle: Path, target: Path) -> Path`.
- Produces: exact target `/Users/defei/.codex/skills/ai-ppt-studio` for this machine.

- [ ] **Step 1: Write the failing safe-install test**

```python
def test_install_replaces_only_exact_skill_and_preserves_runtime(self) -> None:
    installed = install_bundle(bundle, base / "skills" / "ai-ppt-studio")
    self.assertTrue((installed / "SKILL.md").is_file())
    self.assertTrue((installed / "runtime" / "VERSION").is_file())
    self.assertTrue((base / "runtime" / "keep.txt").is_file())
```

- [ ] **Step 2: Run `python3 -m unittest tests/test_install_skill.py -v`**

Expected: FAIL because the installer is missing.

- [ ] **Step 3: Implement exact-target staged installation**

Reject `/`, the home directory, `.codex/skills`, and symlinks. Copy to a sibling staging directory, run the official validator against staging, move an existing exact Skill target to a timestamped sibling backup, atomically rename staging to the target, then remove only the backup created by this successful invocation. Never touch `/Users/defei/Documents/AI-PPT-Workspace`.

- [ ] **Step 4: Test, build, validate, and install**

Run the full suite, build a fresh bundle, validate it, then install to the exact target. Run installed `preflight` with `PYTHONPATH` removed and the existing workspace profile.

- [ ] **Step 5: Commit**

```bash
git add scripts/install_skill.py scripts/build_skill_bundle.py tests/test_install_skill.py
git commit -m "feat: install AI PPT Studio safely"
```

---

### Task 6: Complete a Real Presentations Smoke Project

**Files:**
- Create only under: `/Users/defei/Documents/AI-PPT-Workspace/projects/`
- Do not create customer material or smoke output in the source repository.

**Interfaces:**
- Consumes: installed AI PPT Studio, Image 2, and Codex Presentations.
- Produces: one managed sample project with mission, materials, content blueprint, visual brief, visual contract, scene graph, four review pages, editable PPTX, slide renders, QA ledger, G0-G4 events, and one candidate experience.

- [ ] **Step 1: Create a synthetic, non-customer sales-solution project through the installed CLI**

Use the existing workspace profile and add synthetic text materials for a “智慧园区运营中台解决方案”.

- [ ] **Step 2: Save a six-slide content blueprint and generate its review HTML**

Slides: cover, current challenge, target operating model, solution architecture, scenario proof, and phased roadmap. Use speaker notes and source references on every slide.

- [ ] **Step 3: Generate one Image 2 concept visual and save the visual contract/scene graph**

The concept should provide atmosphere and composition inspiration, not final baked slide text.

- [ ] **Step 4: Use Codex Presentations to create the editable PPTX**

Read the Presentations style guidance and Artifact Tool docs. Create native editable text, shapes, relationships, and diagrams. Use generated visual assets only as separate replaceable image layers. Put `[Sources]` blocks in speaker notes.

- [ ] **Step 5: Render and inspect every slide**

Run `render_slides.py`, inspect all six full-size slides, build a montage for deck flow, run `slides_test.py`, fix every unintended overlap, clip, wrap, unresolved placeholder, and source-note defect.

- [ ] **Step 6: Pass G0-G4 and validate delivery**

Generate all review pages, save delivery metadata, record one feedback event and candidate experience, then run the installed runtime status command.

- [ ] **Step 7: Run complete verification twice and commit source changes only**

Run all tests twice, official Skill validation, installed preflight, `git diff --check`, and confirm the upstream Web product tree remains unchanged. Runtime smoke artifacts stay outside Git.

---

## Completion Gate

The MVP is usable only when:

1. the installed Skill passes official validation;
2. the installed wrapper runs with no source-repository `PYTHONPATH`;
3. a managed project can be created from a protected current directory;
4. content, visual, scene-graph, feedback, and delivery artifacts are versioned;
5. all four HTML review pages open offline;
6. the six-slide smoke PPTX is editable and was produced through Codex Presentations;
7. every slide was rendered and inspected;
8. overflow checks pass;
9. G0-G4 are traceable and sequential;
10. source materials and the upstream Web product remain unchanged.
