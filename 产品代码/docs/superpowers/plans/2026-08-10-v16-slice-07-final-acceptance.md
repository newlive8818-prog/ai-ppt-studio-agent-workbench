# v1.6 Slice 07 Packaging, Real-Project, and Four-Target Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user explicitly authorized inline execution without subagents, worktrees, intermediate approvals, backups, or intermediate commits; make one unified commit only after final acceptance.

**Goal:** Ship one schema 3-only AI PPT Studio plugin, prove install/reinstall/recovery and the real Codex UI, execute one real reading-first presales project, and close G2/G4 plus the 104-requirement ledger with one identical PPTX across macOS PowerPoint, macOS WPS, Windows 11 PowerPoint, and Windows 11 WPS.

**Architecture:** Replace the remaining dual-runtime entry with a schema 3 workspace/project application service and a thin MCP adapter. Build the Widget through an automatically cleaned temporary directory, stage one deterministic plugin release, and keep all customer/project/render evidence under `/Users/defei/Documents/AI-PPT-Workspace`. Acceptance evidence is immutable and content-addressed; a ledger requirement passes only when all evidence kinds declared by its authoritative baseline entry resolve to fresh records.

**Tech Stack:** Python 3.11+ schema 3 kernel/application services and unittest; Node.js ESM, MCP Apps, Zod, and node:test; React 19/Vite/Vitest; Codex plugin CLI and MCP stdio; Codex Presentations for PPTX; macOS PowerPoint/WPS desktop apps; Windows 11 PowerPoint/WPS desktop apps; SHA-256 evidence manifests.

**Requirement coverage:** All 104 entries in `requirements/v1.6-acceptance-ledger.json`, with special focus on plugin portability, runtime isolation, schema 3-only routing, Codex Widget/review resources, real-project delivery, chat receipts, and the four-target same-hash G2/G4 contract.

---

## File responsibility map

- `scripts/build-widget.mjs`: atomic self-contained Widget build; always deletes its temporary raw output.
- `scripts/build-plugin-release.mjs`: deterministic release staging, allowlist copying, production dependency install, manifest generation, and validation.
- `src/ai_ppt_studio/application/project_service.py`: schema 3 workspace/project discovery, creation, material intake, and compact project operations.
- `src/ai_ppt_studio/workbench_bridge.py`: schema 3-only JSON process boundary and stable error mapping.
- `src/ai_ppt_studio/application/v16_bridge.py`: one public operation registry over formal services.
- `mcp/server.mjs`: thin public MCP/Widget tools; no legacy artifact names or Gate inference.
- `skills/ai-ppt-studio/`: current v1.6 workflow, content-addressed references, strict route B, UI boundaries, and four-target evidence policy.
- `scripts/acceptance/prepare_real_project.py`: create the fixed real acceptance project and register user-provided mission/material identities.
- `scripts/acceptance/verify_target_evidence.py`: validate one desktop evidence directory and emit a formal `TargetRenderEvidence` payload.
- `scripts/acceptance/verify_release.py`: check the staged/installed plugin, real project, same-hash evidence, chat receipt, Gate state, and ledger closure.
- `requirements/v1.6-evidence.json`: repository-safe evidence index containing hashes and references only, never customer files or rendered slides.

### Task 1: Atomic Widget build and build-residue elimination

**Files:**
- Modify: `scripts/build-widget.mjs`
- Modify: `widget/vite.config.ts`
- Modify: `tests/widget-bundle.test.mjs`
- Modify: `../.gitignore`

- [x] **Step 1: Write the failing build-cleanliness test**

Extend `tests/widget-bundle.test.mjs` to run the build twice and assert that the only build directory below `widget/` is `dist/`:

```js
const residue = (await readdir(path.join(root, "widget"), { withFileTypes: true }))
  .filter((entry) => entry.isDirectory() && (entry.name === "dist-raw" || entry.name.startsWith(".dist-raw-")))
  .map((entry) => entry.name);
assert.deepEqual(residue, []);
```

- [x] **Step 2: Verify RED**

Run: `npm run build && node --test tests/widget-bundle.test.mjs`

Expected: FAIL because `.dist-raw-*` directories remain after every current build.

- [x] **Step 3: Implement automatic temporary-output cleanup**

Use `mkdtemp(path.join(os.tmpdir(), "ai-ppt-widget-build-"))`, pass the absolute directory as Vite `build.outDir`, inline JS/CSS into one HTML file, write `widget/dist/index.html` through a temporary file plus `rename`, and remove the build temp in `finally`:

```js
const rawDir = await mkdtemp(path.join(os.tmpdir(), "ai-ppt-widget-build-"));
try {
  await build({ configFile, build: { outDir: rawDir, emptyOutDir: true } });
  await writeFile(stagedHtml, html, "utf8");
  await rename(stagedHtml, finalHtml);
} finally {
  await rm(rawDir, { recursive: true, force: true });
}
```

Remove the fixed `outDir` from `widget/vite.config.ts` and ignore `产品代码/widget/dist/` plus any future `.dist-raw-*` residue at the repository boundary.

- [x] **Step 4: Remove confirmed generated residue and verify GREEN**

Delete only the currently enumerated `widget/.dist-raw-*` build directories after confirming they contain Vite output, then run:

`npm run build && npm run build && node --test tests/widget-bundle.test.mjs && find widget -maxdepth 1 -type d -name '.dist-raw-*' -print`

Expected: tests PASS and `find` prints nothing.

### Task 2: Schema 3 workspace/project lifecycle and complete public bridge

**Files:**
- Create: `src/ai_ppt_studio/application/project_service.py`
- Create: `tests/test_v16_project_service.py`
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `src/ai_ppt_studio/workbench_bridge.py`
- Modify: `tests/test_v16_bridge.py`
- Modify: `tests/mcp-runtime-bridge.test.mjs`

- [x] **Step 1: Write failing schema 3 default-route tests**

Cover these exact cases:

```python
created = ProjectService(workspace).create_project("经营一体化验收", project_id="real-presales-v16")
self.assertEqual(created.load().schema_version, "3.0")
self.assertEqual(ProjectService(workspace).latest_project(), created.root)
self.assertEqual(dispatch({"operation": "get-project-snapshot", "workspace_config": str(profile)})["snapshot"]["schema_version"], "3.0")
```

Also assert `create-project`, `list-projects`, `register-mission`, `add-material`, `request-agent-action`, `submit-human-decision`, content/visual/experience/delivery artifact commits, reviews, internal Gates, chat receipts, and reopen operations all reach formal schema 3 services. An old schema 1/2 project may be listed for one-way import but must never be opened through the normal public route.

- [x] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_v16_project_service tests.test_v16_bridge -v && npm run test:node`

Expected: FAIL because omitted `projectRoot` currently falls through to `WorkbenchStore`, and several Node-exposed operations are missing from `dispatch_v16`.

- [x] **Step 3: Implement `ProjectService`**

The service accepts a validated workspace profile, creates only under `<runtime_root>/projects`, rejects symlinks/protected roots, initializes `ProjectKernel`, and registers a `project-manifest` artifact containing `project_id`, `name`, `created_at`, and `scenario_pack: reading-first-presales`.

Material intake must copy byte inputs before transformation and store this normalized inventory entry:

```python
{
    "source_id": source_id,
    "origin": "user-provided",
    "kind": material_type,
    "locator": locator,
    "sha256": sha256,
    "project_copy": relative_copy,
}
```

No method may write outside the configured runtime root or infer a passed Gate.

- [x] **Step 4: Make the JSON bridge schema 3-only**

Resolve the project through `ProjectService` before dispatch. Route all public operations through formal application services, map each public artifact kind to one exact validator/service method, and retain the existing stable error payloads. Remove the normal `WorkbenchStore` and `ReviewSurfaceProjector` branch; legacy import remains an explicit `import-legacy-project` operation only.

- [x] **Step 5: Verify GREEN**

Run: `python3 -m unittest tests.test_v16_project_service tests.test_v16_bridge tests.test_v16_content_chain tests.test_v16_visual_bridge tests.test_v16_delivery_bridge tests.test_v16_experience_bridge -v`

Run: `npm run test:node && npm run probe:mcp`

Expected: every public tool reads or writes schema 3, omitted project selection resolves the latest schema 3 project, and no dual runtime remains.

### Task 3: MCP, Skill, and formal contract alignment

**Files:**
- Modify: `mcp/server.mjs`
- Modify: `scripts/probe-mcp.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `skills/ai-ppt-studio/references/visual-workflow.md`
- Modify: `skills/ai-ppt-studio/references/presentations-handoff.md`
- Modify: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `skills/ai-ppt-studio/references/review-and-feedback.md`
- Create: `skills/ai-ppt-studio/references/four-target-acceptance.md`
- Modify: `tests/test_skill_workflow.py`

- [x] **Step 1: Write failing public-contract tests**

Assert the MCP publishes `create_ai_ppt_project`, all schema 3 artifact kinds, review tools, G0/G3/G4 user checkpoints, G1/G2 internal-only checkpoints, and the four exact target IDs. Assert its instructions and Skill contain:

```text
artifact://<kind>/<sha256>
macos-powerpoint
macos-wps
windows-powerpoint
windows-wps
same PPTX SHA-256
```

Reject the old versioned URI example, user-selected G1/G2, engineering-sample-as-G2, Image 2 before native-first, and any claim that one platform can satisfy final G2/G4.

- [x] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_skill_workflow -v && node --test tests/mcp-server.test.mjs`

Expected: FAIL on stale v0.3 workflow language and the missing project creation/public schema 3 operations.

- [x] **Step 3: Align MCP and Skill**

Make Node validate and forward only formal fields; keep application logic in Python. Rewrite the Skill and directly linked references around the approved v1.6 order: content chain → G0 → full visual contract → G1 → native anchors → four-target G2 → G3 → full deck → four-target G4 → chat receipt. Describe Widget 360–480px and the shared review resource at 760/1000/1440px; saving marks never confirms a Gate.

- [x] **Step 4: Verify GREEN and static package shape**

Run: `python3 -m unittest tests.test_skill_workflow tests.test_package_shape -v && npm run test:node && npm run probe:mcp`

Expected: Skill, MCP descriptions, Zod schemas, runtime operations, and four-target IDs agree exactly.

### Task 4: Remove legacy runtime, tests, fixtures, and false evidence

**Files:**
- Delete after dependency proof: `src/ai_ppt_studio/workbench_store.py`, `src/ai_ppt_studio/workbench_models.py`, `src/ai_ppt_studio/space_projection.py`, `src/ai_ppt_studio/review_surface.py`, `src/ai_ppt_studio/state_store.py`, `src/ai_ppt_studio/project_store.py`, `src/ai_ppt_studio/models.py`, `src/ai_ppt_studio/artifact_store.py`, `src/ai_ppt_studio/content_governance.py`, `src/ai_ppt_studio/visual_governance.py`, and obsolete v1.x-only support files identified by the import audit
- Delete: `scripts/seed-v15-smoke-project.py`
- Delete: `scripts/run-v15-playwright-acceptance.mjs`
- Delete: `tests/test_v15_gate_and_chat_delivery.py`
- Delete or migrate every test that imports a deleted module
- Delete: `tests/SIMULATION_REPORT.md`
- Modify: `tests/test_package_shape.py`

- [x] **Step 1: Create and run a legacy-import denylist test**

Scan production JS/Python/Skill files and fail if they contain `WorkbenchStore`, `space_projections`, `ReviewSurfaceProjector`, `schema_version": "2.0"`, `seed-v15`, or false phrases that call deterministic fixtures real project/desktop proof.

- [x] **Step 2: Verify RED and inventory dependencies**

Run: `python3 -m unittest tests.test_package_shape -v`

Run: `rg -n 'WorkbenchStore|space_projections|ReviewSurfaceProjector|seed-v15|schema_version.*2\.0' src mcp scripts skills tests widget/src`

Expected: RED with an exact list of production and test dependencies to migrate.

- [x] **Step 3: Migrate reusable safety capabilities and delete the old path**

Keep only behavior still required by v1.6—workspace config, protected path policy, bounded asset reads, and explicit legacy import—under schema 3 adapters. Delete obsolete dual state, projection, Gate, review HTML, test fixture, and smoke acceptance implementations once no production import reaches them.

- [x] **Step 4: Verify GREEN**

Run: `python3 -m unittest discover -s tests && npm run test:node && npm run test:widget -- --reporter=dot && rg -n 'WorkbenchStore|space_projections|ReviewSurfaceProjector|seed-v15|schema_version.*2\.0' src mcp scripts skills tests widget/src`

Expected: all tests PASS; `rg` has no production hits and only explicit legacy-import documentation/test fixtures where semantically required.

### Task 5: Deterministic plugin release, install, reinstall, and recovery

**Files:**
- Create: `scripts/build-plugin-release.mjs`
- Create: `scripts/verify-plugin-release.mjs`
- Modify: `scripts/install-plugin.mjs`
- Modify: `package.json`
- Modify: `.codex-plugin/plugin.json`
- Create: `tests/plugin-release.test.mjs`
- Modify: `tests/plugin-shape.test.mjs`
- Modify: `tests/test_skill_bundle.py`
- Modify: `tests/test_install_skill.py`

- [x] **Step 1: Write failing release and recovery tests**

Build to a temporary release root and assert it contains one manifest/Skill/MCP/runtime/Widget, production dependencies, no source tests, no customer/runtime data, no build residue, no symlinks, and a manifest of every shipped file SHA-256. Install twice to a temporary target and assert a schema 3 project created before reinstall remains byte-identical and reopens at the same revision afterward.

- [x] **Step 2: Verify RED**

Run: `node --test tests/plugin-release.test.mjs && python3 -m unittest tests.test_skill_bundle tests.test_install_skill -v`

Expected: FAIL because the current installer builds directly from the dirty source tree, has a hard-coded validator location, and has no release manifest/recovery probe.

- [x] **Step 3: Implement one release staging pipeline**

`build-plugin-release.mjs` must accept `--output`, copy an explicit allowlist, bundle `src/ai_ppt_studio` as installed runtime, install production Node dependencies with the lockfile, validate the plugin, write `release-manifest.json`, and refuse an output intersecting the repo/runtime root. `install-plugin.mjs` must install only a validated staged release through an atomic exact-target swap and never touch `/Users/defei/Documents/AI-PPT-Workspace`.

- [x] **Step 4: Verify temporary install/reinstall/recovery**

Run: `npm run release -- --output /private/tmp/ai-ppt-studio-v16-release`

Run: `npm run verify:release -- --release /private/tmp/ai-ppt-studio-v16-release/ai-ppt-studio`

Expected: release manifest hashes match, MCP probe passes from the release without the source repo on `PYTHONPATH`, and the preserved schema 3 project digest/revision is unchanged after reinstall.

- [x] **Step 5: Install the approved local release into Codex**

Use the plugin creator's cachebuster/reinstall workflow against the validated release, then run its MCP probe. Record installed plugin identity, version, release-manifest SHA-256, install time, and probe output in `output/acceptance/v1.6/plugin-install/`.

### Task 6: Real-project and target-evidence acceptance harness

**Files:**
- Create: `scripts/acceptance/prepare_real_project.py`
- Create: `scripts/acceptance/verify_target_evidence.py`
- Create: `scripts/acceptance/verify_release.py`
- Create: `tests/test_v16_real_project_acceptance.py`
- Create: `tests/test_v16_target_evidence_import.py`
- Create: `tests/test_v16_final_acceptance_verifier.py`
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Modify: `src/ai_ppt_studio/domains/presentation/targets.py`
- Modify: `src/ai_ppt_studio/acceptance/ledger.py`
- Modify: `scripts/build_acceptance_ledger.py`
- Create: `requirements/v1.6-evidence.json`

- [x] **Step 1: Write failing external-evidence tests**

Assert the real acceptance project lives below `/Users/defei/Documents/AI-PPT-Workspace/projects`, product files never contain its customer payloads, and each target evidence directory contains immutable source PPTX identity, exported PDF/images, environment/application/font manifests, per-slide four-door findings, evidence hashes, executor/tool/time, and a formal payload. Assert a hash mismatch rejects all four rows.

Extend the ledger model so an entry contains `proof_refs` and passes only when every `required_evidence` kind resolves:

```python
missing = set(requirement.required_evidence) - {
    proof.kind for proof in evidence.resolve(requirement.proof_refs)
}
status = "passed" if not missing else "unproven"
```

- [x] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_v16_real_project_acceptance tests.test_v16_target_evidence_import tests.test_acceptance_ledger -v`

Expected: FAIL because no external-evidence verifier or proof-aware ledger exists.

- [x] **Step 3: Implement evidence validation without desktop automation claims**

The verifier hashes the exact PPTX and every export, validates application/OS/font/per-slide/four-door fields, and emits one payload accepted by `TargetRenderEvidence.from_payload`. It does not mark the application check passed itself; it preserves the independent desktop reviewer result. G2/G4 evaluation remains exclusively in `GateEvaluator`.

- [x] **Step 4: Implement proof-aware ledger generation**

Keep 104 stable source-derived entries. Load `requirements/v1.6-evidence.json`, verify every proof reference/hash/path, attach only matching proof kinds, and leave real-host/real-project/target requirements `unproven` until the corresponding immutable records exist.

- [x] **Step 5: Verify GREEN with deterministic negative fixtures**

Run: `python3 -m unittest tests.test_v16_real_project_acceptance tests.test_v16_target_evidence_import tests.test_acceptance_ledger -v`

Expected: valid fixtures pass validation but do not masquerade as desktop evidence; altered PPTX/export/application identity fails.

### Task 7: Execute the real presales project and Codex/macOS acceptance

**Runtime output only:**
- Project: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案`
- Evidence: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/acceptance/g2/` and `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/acceptance/g4/`
- Delivery: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/delivery/经营一体化解决方案-v1.6.pptx`

- [x] **Step 1: Initialize/resume the fixed schema 3 project**

Run the installed runtime preflight, then `prepare_real_project.py` with the approved reading-first mission and user-provided source material already inside the managed workspace. Record source hashes; never copy customer content into this repository.

- [x] **Step 2: Execute content governance and G0**

Produce mission, material inventory, content strategy, evidence map, argument map, complete slide draft, five isolated reviews, repair/acceptance, and the professional content review. Record the user's already-authorized execution context as workflow authority, but do not fabricate a content-acceptance chat message; G0 requires a real Codex message identity.

- [ ] **Step 3: Execute strict route B and G1/G2**

Create the full Deck Design System and every slide visual contract before native anchors. Use Codex Presentations for the editable PPTX; Image 2 may add only post-native non-semantic layers. Render and inspect anchors, then export the identical anchor PPTX through macOS PowerPoint and macOS WPS desktop applications. Import two independent target evidence records and allow G2 only when all four target records—including the later Windows records—pass.

Current checkpoint: Visual Brief, Deck Design System, all 12 Slide Visual Contracts, visual convergence, independent aesthetic review, and G1 are complete at project revision 41. OpenAI Presentations `26.805.11740` is installed and enabled; the remaining work starts in a post-installation new Codex task with native S02/S05/S10 anchors and four-target same-hash G2 evidence.

- [ ] **Step 4: Validate the real Codex Widget and review resource**

Open the installed plugin in the actual Codex host, verify the 360–480px compact Widget and the same professional review resource in sidebar/fullscreen or independent form, save an exact-text mark, close/reopen, and confirm revision/source/draft recovery. Store screenshots and host/tool/plugin identities under the real project acceptance directory; add only their hashes/references to the repository evidence index.

- [ ] **Step 5: Complete the full editable deck and macOS G4 evidence**

After G3, build the full deck with native editable semantic objects and `[Sources]` notes, render every page, repair all defects, run overflow/structure checks, and export the same final PPTX in macOS PowerPoint and macOS WPS. The final SHA-256 becomes the only allowed G4 hash.

### Task 8: Windows four-target closure, chat delivery, ledger, and unified commit

**Runtime output only:**
- Windows evidence package: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/acceptance/windows-transfer/`
- Final four-target record: `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/acceptance/g4/four-target-summary.json`

**Repository evidence only:**
- Modify: `requirements/v1.6-evidence.json`
- Create: `docs/validation/2026-08-10-v16-final-acceptance.md`
- Modify: all Slice 01–07 plan checkboxes after their evidence exists

- [ ] **Step 1: Validate the exact final PPTX on Windows 11 PowerPoint and WPS**

Transfer the PPTX without mutation, verify its SHA-256 equals the macOS final hash, export every slide from Windows 11 PowerPoint and Windows 11 WPS, inspect fonts, wrapping, overflow, clipping, object loss, alignment, semantic accuracy, visual completion, engineering integrity, and target rendering, then import both evidence directories through `verify_target_evidence.py`.

- [ ] **Step 2: Close G2/G4 from four same-hash records only**

Register exactly `macos-powerpoint`, `macos-wps`, `windows-powerpoint`, and `windows-wps`. Run `GateEvaluator`; any missing/failed row or differing PPTX SHA-256 keeps the Gate blocked. Rebuild/retest all four rows if the PPTX changes.

- [ ] **Step 3: Send the final PPTX through Codex chat and record G4**

Send `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案/delivery/经营一体化解决方案-v1.6.pptx` in the actual Codex chat, persist the returned `chat://message/...` receipt bound to the current delivery package and PPTX identity, then record explicit G4 acceptance against that sent version.

- [ ] **Step 4: Close the 104-requirement ledger and write final validation**

Run: `python3 scripts/build_acceptance_ledger.py`

Run: `python3 scripts/acceptance/verify_release.py --project /Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案 --ledger requirements/v1.6-acceptance-ledger.json`

Expected: exactly 104/104 requirements passed, all four G2/G4 rows use the same PPTX SHA-256, the chat receipt is sent/current, and the release/install/host/project evidence resolves.

- [ ] **Step 5: Run fresh final verification**

Run: `python3 -m unittest discover -s tests`

Run: `npm run test:node && npm run test:widget -- --reporter=dot && npm run build && npm run accept:v16-ui`

Run: `npm run release -- --output /private/tmp/ai-ppt-studio-v16-final && npm run verify:release -- --release /private/tmp/ai-ppt-studio-v16-final/ai-ppt-studio`

Run: `git diff --check && git status --short`

Expected: all commands exit 0, no `.dist-raw-*`, no legacy production path, no false evidence, no source/runtime boundary violation, and no unexplained untracked file included.

- [ ] **Step 6: Stage and create the one authorized unified commit**

Stage only reviewed product code, tests, plans, baselines, release metadata, and repository-safe evidence references. Exclude `.workbuddy/`, runtime/customer data, build output, temporary release folders, caches, and screenshots that belong to the external project. Commit once with:

```bash
git commit -m "feat: deliver AI PPT Studio v1.6 final acceptance"
```

---

## Self-review

- Spec coverage: packaging, schema 3-only runtime, MCP/Skill/UI alignment, legacy removal, install/reinstall/recovery, real project, real Codex host, four same-hash desktop targets, chat delivery, and all 104 ledger requirements each map to an executable task above.
- Placeholder scan: runtime paths, target IDs, project name, commands, output locations, evidence fields, and pass/fail rules are explicit; the angle-bracket notation that remains is only the normative artifact URI grammar.
- Type consistency: all target IDs match `TARGETS`; formal references use `artifact://<kind>/<sha256>`; `ReviewService`, `TargetRenderEvidence`, `GateEvaluator`, and `Requirement.required_evidence/proof_refs` names remain consistent across tasks.
