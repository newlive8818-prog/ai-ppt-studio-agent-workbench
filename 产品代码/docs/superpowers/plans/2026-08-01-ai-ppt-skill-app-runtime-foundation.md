# AI PPT Skill App Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the installable, standard-library-only runtime foundation that creates isolated AI PPT projects, protects upstream and source directories, ingests user-provided materials without modifying originals, persists G0–G4 state, and can be packaged as a valid Codex Skill.

**Architecture:** Keep the Codex-facing Skill thin and package a focused Python runtime beside it. All writes pass through one `PathPolicy`, all project state lives under a configurable managed runtime root, and all project changes are represented by atomic JSON snapshots plus an append-only JSONL event log. This plan deliberately stops before content generation, Image 2, Slide Scene Graph, PPT compilation, and experience promotion; those capabilities consume the stable interfaces produced here in later plans.

**Tech Stack:** Python 3.11+ standard library, `unittest`, JSON/JSONL, Codex Skill folder metadata, macOS filesystem semantics.

## Global Constraints

- Source repository: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码`.
- Upstream Web product protected root: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT  web app `.
- Default future install root: `/Users/defei/.codex/skills/ai-ppt-studio`.
- Default managed runtime root: `/Users/defei/Documents/AI-PPT-Workspace`.
- Runtime support floor: Python 3.11; do not depend on third-party runtime packages.
- Never write project state, caches, generated HTML, PPTX, logs, or hidden files into the current working directory unless it is already the configured managed project directory.
- Never write into the upstream Web product root, source repository, installed Skill root, or a user-declared original-material root.
- Resolve and validate absolute real paths before every write; reject unresolved, overly broad, protected, or symlink-traversing targets.
- Original materials are read-only. Copy only into the managed project when transformation is required, then verify source and copy hashes.
- User-provided URLs are recorded in this foundation plan but are not fetched from the network.
- Store timestamps as timezone-aware UTC ISO 8601 strings ending in `Z`.
- Write JSON as UTF-8 with `ensure_ascii=False`, stable indentation, and a trailing newline.
- Use atomic replace for JSON state; use append-only writes for event JSONL.
- Do not include real customer names, materials, paths, or screenshots in repository fixtures.
- Do not implement content blueprints, Image 2 calls, visual-concept generation, Slide Scene Graph, PowerPoint generation, or experience promotion in this plan.
- Every task uses red-green TDD and ends in a focused commit.

---

## Plan Boundary and Follow-on Plans

This specification contains four dependent subsystems. Implement them as separate plans so each produces independently testable software:

1. **This plan — Runtime Foundation:** Skill shape, path isolation, managed projects, material intake, state, CLI, and portable bundle.
2. **Follow-on Plan 2 — Content and Visual Conception:** project mission, material interpretation, content blueprint, `VisualBrief`, concept territories, Image 2 concept samples, and G0/G1 review pages.
3. **Follow-on Plan 3 — Editable Realization:** minimal `SlideSceneGraph`, object routing, two engineering samples, PPTX compilation, real rendering, repair, and G2–G4.
4. **Follow-on Plan 4 — Evaluation and Evolution:** `FeedbackEvent`, `CandidateExperience`, personal memory, replay evaluation, promotion, rollback, and privacy-safe release candidates.

Do not begin Plan 2 until the isolation acceptance test and portable-install smoke test at the end of this plan pass.

## Target File Map

```text
ai-ppt-skill-app-mvp/
├── pyproject.toml
├── src/
│   └── ai_ppt_studio/
│       ├── __init__.py              # package version
│       ├── __main__.py              # python -m entry
│       ├── cli.py                   # JSON CLI commands
│       ├── config.py                # RuntimeConfig creation/load/save
│       ├── errors.py                # typed domain errors
│       ├── paths.py                 # absolute path and protection policy
│       ├── models.py                # manifests and enums
│       ├── json_io.py               # atomic JSON and JSONL writes
│       ├── project_store.py         # managed project creation/load
│       ├── materials.py             # read-only reference/copy intake
│       ├── event_store.py           # append-only project events
│       └── state_store.py           # G0–G4 transition and reopen rules
├── skill/
│   └── ai-ppt-studio/
│       ├── SKILL.md                 # thin Codex router and hard safety rules
│       ├── agents/openai.yaml       # Skill UI metadata
│       ├── references/
│       │   ├── isolation-policy.md
│       │   └── runtime-workflow.md
│       ├── scripts/
│       │   └── ai_ppt_runtime.py    # installed bundle wrapper
│       └── assets/
│           └── project-schema.json  # human-readable initial schema marker
├── scripts/
│   └── build_skill_bundle.py        # assemble portable Skill directory
└── tests/
    ├── test_package_shape.py
    ├── test_path_policy.py
    ├── test_project_store.py
    ├── test_materials.py
    ├── test_state_store.py
    ├── test_cli.py
    ├── test_isolation_acceptance.py
    └── test_skill_bundle.py
```

---

### Task 1: Create the Thin Skill and Python Package Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai_ppt_studio/__init__.py`
- Create: `src/ai_ppt_studio/errors.py`
- Create: `skill/ai-ppt-studio/SKILL.md`
- Create: `skill/ai-ppt-studio/agents/openai.yaml`
- Create: `skill/ai-ppt-studio/references/isolation-policy.md`
- Create: `skill/ai-ppt-studio/references/runtime-workflow.md`
- Create: `skill/ai-ppt-studio/assets/project-schema.json`
- Test: `tests/test_package_shape.py`

**Interfaces:**
- Produces: `ai_ppt_studio.__version__: str` with initial value `0.1.0`.
- Produces: `AiPptError`, `ConfigurationError`, `ProtectedPathError`, `ProjectNotFoundError`, `InvalidTransitionError`, and `MaterialImportError`.
- Produces: a valid `skill/ai-ppt-studio` source tree that later tasks package.

- [ ] **Step 1: Write the failing package-shape test**

```python
# tests/test_package_shape.py
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class PackageShapeTests(unittest.TestCase):
    def test_python_package_and_skill_metadata_exist(self) -> None:
        from ai_ppt_studio import __version__

        self.assertEqual(__version__, "0.1.0")
        skill = ROOT / "skill" / "ai-ppt-studio"
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertTrue((skill / "agents" / "openai.yaml").is_file())
        self.assertTrue((skill / "references" / "isolation-policy.md").is_file())
        self.assertTrue((skill / "references" / "runtime-workflow.md").is_file())
        self.assertTrue((skill / "assets" / "project-schema.json").is_file())

    def test_skill_is_thin_and_contains_hard_safety_language(self) -> None:
        body = (ROOT / "skill" / "ai-ppt-studio" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(body.splitlines()), 180)
        self.assertIn("Never write into the current working directory", body)
        self.assertIn("managed runtime root", body)
        self.assertIn("Read isolation-policy.md before any file write", body)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails because the package does not exist**

Run: `python3 -m unittest tests/test_package_shape.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_ppt_studio'`.

- [ ] **Step 3: Initialize the Skill source tree with official Skill tooling**

Run:

```bash
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  ai-ppt-studio \
  --path skill \
  --resources scripts,references,assets \
  --interface display_name="AI PPT Studio" \
  --interface short_description="Create high-design editable sales-solution PowerPoint projects in Codex" \
  --interface default_prompt="Use AI PPT Studio to create or resume an isolated editable PowerPoint project."
```

Expected: `skill/ai-ppt-studio` is created with `SKILL.md` and `agents/openai.yaml`.

- [ ] **Step 4: Replace generated placeholders and create the minimal Python package**

Use `apply_patch` to create `pyproject.toml`:

```toml
[project]
name = "ai-ppt-studio-runtime"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.unittest]
start-directory = "tests"
```

Create `src/ai_ppt_studio/__init__.py`:

```python
"""AI PPT Studio isolated runtime."""

__version__ = "0.1.0"
```

Create `src/ai_ppt_studio/errors.py`:

```python
class AiPptError(Exception):
    """Base error for user-recoverable AI PPT runtime failures."""


class ConfigurationError(AiPptError):
    pass


class ProtectedPathError(AiPptError):
    pass


class ProjectNotFoundError(AiPptError):
    pass


class InvalidTransitionError(AiPptError):
    pass


class MaterialImportError(AiPptError):
    pass
```

Replace `skill/ai-ppt-studio/SKILL.md` with a concise router containing this exact safety core:

```markdown
---
name: ai-ppt-studio
description: Create, resume, review, and validate isolated AI PowerPoint projects in Codex for sales-solution presentations. Use when a user asks to make, redesign, continue, inspect, render, or deliver an editable PPT/PPTX through the AI PPT Studio workflow.
---

# AI PPT Studio

Operate through the managed AI PPT workspace. Never write into the current working directory unless it is already the configured managed project directory.

## Required startup

1. Read `references/isolation-policy.md` before any file write.
2. Read `references/runtime-workflow.md` before creating or resuming a project.
3. Run the runtime preflight before initialization, material import, state changes, rendering, or delivery.
4. Treat user-provided source materials as read-only.
5. Stop when a write target is protected, unresolved, overly broad, or outside the managed runtime root.

## Current capability boundary

The runtime foundation can initialize isolated projects, register or copy user-provided materials, report G0–G4 state, and resume work. Do not claim that visual conception, Image 2 generation, Slide Scene Graph, PPT compilation, or experience promotion exists until the corresponding runtime modules and acceptance tests are present.
```

Create the two references with the exact rules from the confirmed specification, and create `assets/project-schema.json` as:

```json
{
  "schema_version": "1.0",
  "project_manifest": "project.json",
  "event_log": "events/events.jsonl",
  "state_file": "state/state.json"
}
```

- [ ] **Step 5: Run the package-shape test and Skill validator**

Run:

```bash
python3 -m unittest tests/test_package_shape.py -v
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/ai-ppt-studio
```

Expected: two package-shape tests PASS and validator prints `Skill is valid!`.

- [ ] **Step 6: Commit the package skeleton**

```bash
git add pyproject.toml src/ai_ppt_studio skill/ai-ppt-studio tests/test_package_shape.py
git commit -m "feat: scaffold isolated AI PPT Skill runtime"
```

---

### Task 2: Implement Runtime Configuration and Protected Path Policy

**Files:**
- Modify: `src/ai_ppt_studio/errors.py`
- Create: `src/ai_ppt_studio/config.py`
- Create: `src/ai_ppt_studio/paths.py`
- Test: `tests/test_path_policy.py`

**Interfaces:**
- Produces: `RuntimeConfig.create(runtime_root: Path, source_repo_root: Path, install_root: Path, upstream_root: Path, extra_protected_roots: tuple[Path, ...] = ()) -> RuntimeConfig`.
- Produces: `RuntimeConfig.save(path: Path) -> None` and `RuntimeConfig.load(path: Path) -> RuntimeConfig`.
- Produces: `PathPolicy(config: RuntimeConfig)`.
- Produces: `PathPolicy.assert_write_allowed(target: Path) -> Path` returning an absolute resolved path or raising `ProtectedPathError`.
- Produces: `PathPolicy.assert_source_readable(source: Path) -> Path` returning a resolved regular file or directory without granting write permission.

- [ ] **Step 1: Write path-policy tests for allowed, protected, broad, and symlink targets**

```python
# tests/test_path_policy.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ProtectedPathError
from ai_ppt_studio.paths import PathPolicy


class PathPolicyTests(unittest.TestCase):
    def test_allows_only_targets_under_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            runtime.mkdir()
            config = RuntimeConfig.create(
                runtime_root=runtime,
                source_repo_root=base / "source-repo",
                install_root=base / "installed-skill",
                upstream_root=base / "web-product",
            )
            target = runtime / "projects" / "demo"
            self.assertEqual(PathPolicy(config).assert_write_allowed(target), target.resolve())

    def test_rejects_protected_and_outside_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            runtime.mkdir()
            upstream = base / "web-product"
            upstream.mkdir()
            config = RuntimeConfig.create(
                runtime_root=runtime,
                source_repo_root=base / "source-repo",
                install_root=base / "installed-skill",
                upstream_root=upstream,
            )
            policy = PathPolicy(config)
            with self.assertRaises(ProtectedPathError):
                policy.assert_write_allowed(upstream / "new-file.json")
            with self.assertRaises(ProtectedPathError):
                policy.assert_write_allowed(base / "unmanaged" / "new-file.json")

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            outside = base / "outside"
            runtime.mkdir()
            outside.mkdir()
            (runtime / "escape").symlink_to(outside, target_is_directory=True)
            config = RuntimeConfig.create(
                runtime_root=runtime,
                source_repo_root=base / "source-repo",
                install_root=base / "installed-skill",
                upstream_root=base / "web-product",
            )
            with self.assertRaises(ProtectedPathError):
                PathPolicy(config).assert_write_allowed(runtime / "escape" / "file.json")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the path-policy tests and verify imports fail**

Run: `python3 -m unittest tests/test_path_policy.py -v`

Expected: FAIL because `ai_ppt_studio.config` and `ai_ppt_studio.paths` do not exist.

- [ ] **Step 3: Implement immutable runtime configuration**

Implement `RuntimeConfig` as a frozen dataclass with canonical absolute paths and these serialized keys:

```python
@dataclass(frozen=True)
class RuntimeConfig:
    schema_version: str
    runtime_root: Path
    source_repo_root: Path
    install_root: Path
    upstream_root: Path
    protected_roots: tuple[Path, ...]

    @classmethod
    def create(
        cls,
        runtime_root: Path,
        source_repo_root: Path,
        install_root: Path,
        upstream_root: Path,
        extra_protected_roots: tuple[Path, ...] = (),
    ) -> "RuntimeConfig":
        roots = (source_repo_root, install_root, upstream_root, *extra_protected_roots)
        return cls(
            schema_version="1.0",
            runtime_root=runtime_root.expanduser().resolve(strict=False),
            source_repo_root=source_repo_root.expanduser().resolve(strict=False),
            install_root=install_root.expanduser().resolve(strict=False),
            upstream_root=upstream_root.expanduser().resolve(strict=False),
            protected_roots=tuple(p.expanduser().resolve(strict=False) for p in roots),
        )
```

Implement JSON save/load without third-party dependencies. Reject `/`, the user home directory, and any runtime root that is equal to or inside a protected root by raising `ConfigurationError`.

- [ ] **Step 4: Implement one path-policy gate for all writes**

Implement these helpers in `paths.py`:

```python
def is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class PathPolicy:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    def assert_write_allowed(self, target: Path) -> Path:
        candidate = target.expanduser().resolve(strict=False)
        if not is_within(candidate, self.config.runtime_root):
            raise ProtectedPathError(f"Write target is outside managed runtime root: {candidate}")
        for protected in self.config.protected_roots:
            if is_within(candidate, protected) or is_within(protected, candidate):
                raise ProtectedPathError(f"Write target intersects protected root: {protected}")
        current = candidate
        while current != self.config.runtime_root.parent:
            if current.exists() and current.is_symlink():
                raise ProtectedPathError(f"Write target traverses symlink: {current}")
            if current == self.config.runtime_root:
                break
            current = current.parent
        return candidate
```

Also implement `assert_source_readable` to accept only existing regular files or directories and never create or modify the source.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_path_policy.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit path isolation**

```bash
git add src/ai_ppt_studio/config.py src/ai_ppt_studio/paths.py src/ai_ppt_studio/errors.py tests/test_path_policy.py
git commit -m "feat: enforce managed runtime path isolation"
```

---

### Task 3: Create Managed Project Folders and Atomic Manifests

**Files:**
- Create: `src/ai_ppt_studio/json_io.py`
- Create: `src/ai_ppt_studio/models.py`
- Create: `src/ai_ppt_studio/project_store.py`
- Test: `tests/test_project_store.py`

**Interfaces:**
- Produces: `ProjectManifest(project_id: str, name: str, slug: str, schema_version: str, created_at: str, source_context: str | None, project_root: str)`.
- Produces: `ProjectStore(config: RuntimeConfig, policy: PathPolicy)`.
- Produces: `ProjectStore.create(name: str, source_context: Path | None = None) -> ProjectManifest`.
- Produces: `ProjectStore.load(project_root: Path) -> ProjectManifest`.
- Produces: `atomic_write_json(path: Path, payload: dict[str, object]) -> None`.

- [ ] **Step 1: Write the failing managed-project tests**

```python
# tests/test_project_store.py
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_create_project_writes_only_managed_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            protected = base / "web-product"
            protected.mkdir()
            config = RuntimeConfig.create(
                runtime_root=runtime,
                source_repo_root=base / "source-repo",
                install_root=base / "installed-skill",
                upstream_root=protected,
            )
            manifest = ProjectStore(config, PathPolicy(config)).create(
                "智慧园区解决方案",
                source_context=protected,
            )
            project = Path(manifest.project_root)
            self.assertTrue(project.is_dir())
            self.assertEqual(project.parent, (runtime / "projects").resolve())
            self.assertTrue((project / "project.json").is_file())
            self.assertEqual(json.loads((project / "project.json").read_text("utf-8"))["name"], "智慧园区解决方案")
            expected = {
                "sources", "managed-assets", "blueprint", "visual", "scene-graph",
                "ppt", "renders", "reviews", "state", "events", "logs"
            }
            self.assertEqual({p.name for p in project.iterdir() if p.is_dir()}, expected)
            self.assertEqual(list(protected.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails because `ProjectStore` is missing**

Run: `python3 -m unittest tests/test_project_store.py -v`

Expected: FAIL with import error for `ai_ppt_studio.project_store`.

- [ ] **Step 3: Implement atomic JSON output**

Implement `atomic_write_json` by creating a temporary file in the target directory, flushing and `os.fsync`-ing it, then calling `os.replace`. Always remove an uncommitted temporary file in `finally`.

```python
def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Implement manifest creation and deterministic project structure**

Use `uuid.uuid4()` for `project_id`, a Unicode-safe slug normalizer with fallback `project`, and UTC timestamps. The folder name must be `<slug>-<first-eight-project-id-chars>`.

Before every directory or file creation, pass the final target through `PathPolicy.assert_write_allowed`. `source_context` is metadata only and must never become the output root.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_project_store.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS; the protected source context remains empty.

- [ ] **Step 6: Commit managed project creation**

```bash
git add src/ai_ppt_studio/json_io.py src/ai_ppt_studio/models.py src/ai_ppt_studio/project_store.py tests/test_project_store.py
git commit -m "feat: create isolated managed PPT projects"
```

---

### Task 4: Register and Copy User-Provided Materials Without Mutation

**Files:**
- Modify: `src/ai_ppt_studio/models.py`
- Create: `src/ai_ppt_studio/materials.py`
- Test: `tests/test_materials.py`

**Interfaces:**
- Produces: `SourceKind` enum with `FILE`, `DIRECTORY`, `URL`, and `TEXT`.
- Produces: `ImportMode` enum with `REFERENCE` and `COPY`.
- Produces: `MaterialSource(source_id: str, kind: SourceKind, mode: ImportMode, original_ref: str, managed_ref: str | None, sha256: str | None, size_bytes: int | None, created_at: str)`.
- Produces: `MaterialIntake(policy: PathPolicy)`.
- Produces: `MaterialIntake.add_local(project_root: Path, source: Path, mode: ImportMode) -> tuple[MaterialSource, ...]`.
- Produces: `MaterialIntake.add_url(project_root: Path, url: str) -> MaterialSource` without network access.
- Produces: `MaterialIntake.add_text(project_root: Path, text: str, label: str) -> MaterialSource`.

- [ ] **Step 1: Write failing tests for reference, copy, directory, URL, text, and symlink rejection**

```python
# tests/test_materials.py
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import MaterialImportError
from ai_ppt_studio.materials import ImportMode, MaterialIntake
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MaterialIntakeTests(unittest.TestCase):
    def test_copy_preserves_original_and_verifies_managed_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source_dir = base / "originals"
            source_dir.mkdir()
            source = source_dir / "需求说明.txt"
            source.write_text("建设智慧园区运营平台", encoding="utf-8")
            before = digest(source)
            runtime = base / "runtime"
            config = RuntimeConfig.create(runtime, base / "repo", base / "install", base / "web", (source_dir,))
            policy = PathPolicy(config)
            project = ProjectStore(config, policy).create("测试项目")
            records = MaterialIntake(policy).add_local(Path(project.project_root), source, ImportMode.COPY)
            self.assertEqual(digest(source), before)
            self.assertEqual(len(records), 1)
            managed = Path(records[0].managed_ref or "")
            self.assertTrue(managed.is_file())
            self.assertEqual(digest(managed), before)

    def test_rejects_symlink_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source.txt"
            source.write_text("source", encoding="utf-8")
            link = base / "link.txt"
            link.symlink_to(source)
            runtime = base / "runtime"
            config = RuntimeConfig.create(runtime, base / "repo", base / "install", base / "web")
            policy = PathPolicy(config)
            project = ProjectStore(config, policy).create("测试项目")
            with self.assertRaises(MaterialImportError):
                MaterialIntake(policy).add_local(Path(project.project_root), link, ImportMode.REFERENCE)


if __name__ == "__main__":
    unittest.main()
```

Add separate test methods that assert directory recursion sorts paths, URL registration does not issue network requests, and text input is written only to `managed-assets/text/`.

- [ ] **Step 2: Run the tests and verify they fail because material types are missing**

Run: `python3 -m unittest tests/test_materials.py -v`

Expected: FAIL with import error for `ai_ppt_studio.materials`.

- [ ] **Step 3: Implement source hashing and read-only reference records**

Hash local files in 1 MiB chunks. For `REFERENCE`, write only a metadata record under `sources/<source-id>.json`; do not copy the file. Record directories as one `MaterialSource` per regular file, sorted by relative POSIX path.

- [ ] **Step 4: Implement verified managed copies**

For `COPY`, use `shutil.copy2` into `managed-assets/local/<source-id>/<original-name>`, compute both hashes, and raise `MaterialImportError` while deleting the invalid managed copy if hashes differ. Reject source symlinks and symlinked descendants before copying.

- [ ] **Step 5: Implement URL and text registration without network access**

For URLs, accept only `http` and `https`, store the exact user-provided URL and `managed_ref=None`, and never call a network library. For text, require a non-empty stripped value and store it as UTF-8 under `managed-assets/text/<source-id>-<safe-label>.txt`.

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_materials.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS; original hashes are unchanged.

- [ ] **Step 7: Commit safe material intake**

```bash
git add src/ai_ppt_studio/models.py src/ai_ppt_studio/materials.py tests/test_materials.py
git commit -m "feat: ingest materials without mutating sources"
```

---

### Task 5: Persist G0–G4 State and Append-Only Events

**Files:**
- Modify: `src/ai_ppt_studio/models.py`
- Modify: `src/ai_ppt_studio/json_io.py`
- Create: `src/ai_ppt_studio/event_store.py`
- Create: `src/ai_ppt_studio/state_store.py`
- Test: `tests/test_state_store.py`

**Interfaces:**
- Produces: `Gate` enum with `G0`, `G1`, `G2`, `G3`, and `G4`.
- Produces: `GateStatus` enum with `LOCKED`, `OPEN`, and `PASSED`.
- Produces: `ProjectState(schema_version: str, revision: int, gates: dict[str, str], current_gate: str, updated_at: str)`.
- Produces: `append_jsonl(path: Path, payload: dict[str, object]) -> None` using one UTF-8 line per event.
- Produces: `EventStore(project_root: Path, policy: PathPolicy).append(event_type: str, payload: dict[str, object]) -> str` returning `event_id`.
- Produces: `StateStore(project_root: Path, policy: PathPolicy).initialize() -> ProjectState`.
- Produces: `StateStore.pass_gate(gate: Gate, evidence_refs: tuple[str, ...]) -> ProjectState`.
- Produces: `StateStore.reopen_from(gate: Gate, reason: str) -> ProjectState`.

- [ ] **Step 1: Write failing sequential-transition and reopen tests**

```python
# tests/test_state_store.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import InvalidTransitionError
from ai_ppt_studio.models import Gate, GateStatus
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_gates_advance_sequentially_and_reopen_only_affected_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            config = RuntimeConfig.create(runtime, base / "repo", base / "install", base / "web")
            policy = PathPolicy(config)
            project = ProjectStore(config, policy).create("状态测试")
            store = StateStore(Path(project.project_root), policy)
            initial = store.initialize()
            self.assertEqual(initial.gates[Gate.G0.value], GateStatus.OPEN.value)
            self.assertEqual(initial.gates[Gate.G1.value], GateStatus.LOCKED.value)
            with self.assertRaises(InvalidTransitionError):
                store.pass_gate(Gate.G1, ("visual/brief.json",))
            after_g0 = store.pass_gate(Gate.G0, ("blueprint/content.json",))
            self.assertEqual(after_g0.gates[Gate.G0.value], GateStatus.PASSED.value)
            self.assertEqual(after_g0.gates[Gate.G1.value], GateStatus.OPEN.value)
            reopened = store.reopen_from(Gate.G0, "核心事实变化")
            self.assertEqual(reopened.gates[Gate.G0.value], GateStatus.OPEN.value)
            self.assertEqual(reopened.gates[Gate.G1.value], GateStatus.LOCKED.value)
            self.assertGreater(reopened.revision, after_g0.revision)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify missing state modules fail**

Run: `python3 -m unittest tests/test_state_store.py -v`

Expected: FAIL with import error for `state_store` or missing gate types.

- [ ] **Step 3: Implement append-only events and initial state**

Initialize exactly one `OPEN` gate (`G0`) and four `LOCKED` gates. Create `state/state.json` atomically and append a `project.state.initialized` event to `events/events.jsonl`.

Every event must contain:

```python
{
    "event_id": str(uuid.uuid4()),
    "event_type": event_type,
    "occurred_at": utc_now(),
    "payload": payload,
}
```

- [ ] **Step 4: Implement sequential pass and scoped reopen rules**

`pass_gate` must require the requested gate to be `OPEN`, require at least one evidence reference, mark the gate `PASSED`, open the next gate when present, increment revision, atomically save state, and append `project.gate.passed`.

`reopen_from` must require a non-empty reason, mark the selected gate `OPEN`, mark every later gate `LOCKED`, preserve earlier gates, increment revision, save, and append `project.gate.reopened`.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_state_store.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS and each state mutation has a corresponding JSONL event.

- [ ] **Step 6: Commit state and event persistence**

```bash
git add src/ai_ppt_studio/models.py src/ai_ppt_studio/json_io.py src/ai_ppt_studio/event_store.py src/ai_ppt_studio/state_store.py tests/test_state_store.py
git commit -m "feat: persist resumable G0 to G4 project state"
```

---

### Task 6: Add a Structured CLI and Installed-Skill Wrapper

**Files:**
- Create: `src/ai_ppt_studio/cli.py`
- Create: `src/ai_ppt_studio/__main__.py`
- Create: `skill/ai-ppt-studio/scripts/ai_ppt_runtime.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int`.
- Produces CLI commands: `preflight`, `init`, `import`, `status`, `pass-gate`, and `reopen-gate`.
- Produces one JSON object on stdout for success and one JSON object on stderr for domain errors.
- Produces exit codes: `0` success, `2` invalid arguments/configuration, `3` protected path, `4` missing project/material, `5` invalid gate transition, `10` unexpected internal error.

- [ ] **Step 1: Write failing subprocess CLI tests**

```python
# tests/test_cli.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ai_ppt_studio", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_init_and_status_emit_machine_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            protected = base / "web"
            protected.mkdir()
            runtime = base / "runtime"
            common = (
                "--runtime-root", str(runtime),
                "--source-repo-root", str(base / "repo"),
                "--install-root", str(base / "install"),
                "--upstream-root", str(protected),
            )
            created = self.run_cli(*common, "init", "--name", "测试方案", cwd=protected)
            self.assertEqual(created.returncode, 0, created.stderr)
            payload = json.loads(created.stdout)
            self.assertEqual(payload["ok"], True)
            project_root = payload["project"]["project_root"]
            status = self.run_cli(*common, "status", "--project", project_root, cwd=protected)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["state"]["current_gate"], "G0")
            self.assertEqual(list(protected.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the module entry point is missing**

Run: `python3 -m unittest tests/test_cli.py -v`

Expected: FAIL because `ai_ppt_studio.__main__` does not exist.

- [ ] **Step 3: Implement shared arguments and JSON responses**

Use `argparse`. All commands must receive explicit `--runtime-root`, `--source-repo-root`, `--install-root`, and `--upstream-root` in this foundation. Build `RuntimeConfig` once, then create `PathPolicy` and the required store.

Success output shape:

```json
{"ok": true, "command": "init", "project": {"project_id": "2b24c5ab-4b39-40a1-8d8c-f9f319387c8a", "project_root": "/Users/example/Documents/AI-PPT-Workspace/projects/demo-2b24c5ab"}}
```

Error output shape:

```json
{"ok": false, "error": {"type": "ProtectedPathError", "message": "Write target is outside managed runtime root: /Users/example/protected/output.json"}}
```

- [ ] **Step 4: Implement command dispatch and exit-code mapping**

Map domain errors by type and never print a Python traceback for expected user-recoverable failures. `preflight` must report resolved roots, Python version, write-policy result, and capability flags with all future capabilities set to `false`.

- [ ] **Step 5: Add the installed Skill wrapper**

`skill/ai-ppt-studio/scripts/ai_ppt_runtime.py` must locate `../runtime` relative to itself, prepend that directory to `sys.path`, import `ai_ppt_studio.cli.main`, and exit with its return code. It must not import from the source repository.

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
python3 -m unittest tests/test_cli.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS, and invoking `init` from a protected current directory writes only under the managed runtime root.

- [ ] **Step 7: Commit the CLI**

```bash
git add src/ai_ppt_studio/cli.py src/ai_ppt_studio/__main__.py skill/ai-ppt-studio/scripts/ai_ppt_runtime.py tests/test_cli.py
git commit -m "feat: expose isolated project runtime CLI"
```

---

### Task 7: Prove End-to-End Isolation

**Files:**
- Create: `tests/test_isolation_acceptance.py`
- Modify: `src/ai_ppt_studio/paths.py` only if the acceptance test exposes a real policy gap
- Modify: `src/ai_ppt_studio/materials.py` only if the acceptance test exposes a real intake gap

**Interfaces:**
- Consumes: CLI, `PathPolicy`, `ProjectStore`, `MaterialIntake`, and `StateStore` from Tasks 2–6.
- Produces: a regression test proving zero mutation of the protected upstream tree and original-material tree.

- [ ] **Step 1: Write an end-to-end acceptance test that snapshots protected trees**

```python
# tests/test_isolation_acceptance.py
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tree_digest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            result[relative] = "directory"
    return result


class IsolationAcceptanceTests(unittest.TestCase):
    def test_full_foundation_flow_never_mutates_protected_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            upstream = base / "web-product"
            originals = base / "original-materials"
            runtime = base / "managed-runtime"
            upstream.mkdir()
            originals.mkdir()
            (upstream / "baseline.md").write_text("权威 Web 产品基线", encoding="utf-8")
            source = originals / "需求.txt"
            source.write_text("建设统一运营平台", encoding="utf-8")
            upstream_before = tree_digest(upstream)
            originals_before = tree_digest(originals)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            common = [
                "--runtime-root", str(runtime),
                "--source-repo-root", str(base / "source-repo"),
                "--install-root", str(base / "install"),
                "--upstream-root", str(upstream),
                "--protect", str(originals),
            ]
            created = subprocess.run(
                [sys.executable, "-m", "ai_ppt_studio", *common, "init", "--name", "纵向切片"],
                cwd=upstream,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            project = json.loads(created.stdout)["project"]["project_root"]
            imported = subprocess.run(
                [sys.executable, "-m", "ai_ppt_studio", *common, "import", "--project", project, "--source", str(source), "--mode", "copy"],
                cwd=originals,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(tree_digest(upstream), upstream_before)
            self.assertEqual(tree_digest(originals), originals_before)
            self.assertTrue(Path(project).is_relative_to(runtime.resolve()))
            self.assertEqual([p for p in runtime.rglob("*") if p.is_symlink()], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the acceptance test before any fix**

Run: `python3 -m unittest tests/test_isolation_acceptance.py -v`

Expected: PASS if prior tasks meet the specification. If it fails, preserve the failing output and change only the policy or intake code responsible for the mutation or escape.

- [ ] **Step 3: Run all tests twice to catch state leakage**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -v
```

Expected: both runs PASS with identical test counts and no files created outside temporary directories.

- [ ] **Step 4: Commit the isolation acceptance gate**

```bash
git add tests/test_isolation_acceptance.py src/ai_ppt_studio/paths.py src/ai_ppt_studio/materials.py
git commit -m "test: prove zero mutation of protected inputs"
```

---

### Task 8: Build and Smoke-Test a Portable Skill Bundle

**Files:**
- Create: `scripts/build_skill_bundle.py`
- Test: `tests/test_skill_bundle.py`
- Modify: `skill/ai-ppt-studio/SKILL.md` only to reflect capabilities that actually passed Tasks 1–7

**Interfaces:**
- Produces: `build_bundle(source_root: Path, output_root: Path) -> Path`.
- Produces bundle layout `output_root/ai-ppt-studio/{SKILL.md,agents,references,scripts,assets,runtime}`.
- Produces a bundle that passes official Skill validation and runs without importing from the source repository.

- [ ] **Step 1: Write the failing portable-bundle test**

```python
# tests/test_skill_bundle.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_skill_bundle import build_bundle


class SkillBundleTests(unittest.TestCase):
    def test_bundle_runs_without_source_repository_on_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = build_bundle(ROOT, base / "bundle")
            runtime_root = base / "runtime"
            protected = base / "protected"
            protected.mkdir()
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "ai_ppt_runtime.py"),
                    "--runtime-root", str(runtime_root),
                    "--source-repo-root", str(base / "unavailable-source"),
                    "--install-root", str(bundle),
                    "--upstream-root", str(protected),
                    "preflight",
                ],
                cwd=protected,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["ok"], True)
            self.assertEqual(payload["capabilities"]["runtime_foundation"], True)
            self.assertEqual(payload["capabilities"]["ppt_compilation"], False)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify bundle builder is missing**

Run: `python3 -m unittest tests/test_skill_bundle.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_skill_bundle'`.

- [ ] **Step 3: Implement deterministic bundle assembly**

`build_bundle` must:

1. remove only the explicit output bundle directory when it already exists;
2. copy `skill/ai-ppt-studio` into the bundle;
3. copy `src/ai_ppt_studio` into `bundle/runtime/ai_ppt_studio`;
4. exclude `__pycache__`, `.pyc`, test fixtures, `.DS_Store`, customer data, source Git metadata, and repository docs;
5. reject any symlink encountered in source inputs;
6. write `bundle/runtime/VERSION` with `0.1.0\n`;
7. return the absolute bundle path.

Use explicit resolved paths and refuse an output root that is `/`, the user home directory, the source repository, or an ancestor of the source repository.

- [ ] **Step 4: Validate the assembled Skill and run the smoke test**

Run:

```bash
python3 -m unittest tests/test_skill_bundle.py -v
temp_bundle=$(mktemp -d)
python3 scripts/build_skill_bundle.py --output "$temp_bundle"
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$temp_bundle/ai-ppt-studio"
```

Expected: bundle test PASS and validator prints `Skill is valid!`.

- [ ] **Step 5: Run the complete foundation verification**

Run:

```bash
python3 -m unittest discover -s tests -v
git diff --check
git status --short
```

Expected: all tests PASS, `git diff --check` prints nothing, and status lists only the intended Task 8 changes before commit.

- [ ] **Step 6: Commit the portable bundle**

```bash
git add scripts/build_skill_bundle.py tests/test_skill_bundle.py skill/ai-ppt-studio/SKILL.md
git commit -m "feat: package portable AI PPT Skill runtime"
```

---

## Foundation Completion Gate

Before planning or implementing visual conception, verify all of the following in one fresh run:

```bash
python3 -m unittest discover -s tests -v
bundle_dir=$(mktemp -d)
python3 scripts/build_skill_bundle.py --output "$bundle_dir"
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$bundle_dir/ai-ppt-studio"
git diff --check
git status --short
```

The Runtime Foundation is complete only when:

1. all tests pass twice without state leakage;
2. the protected upstream and original-material tree digests remain unchanged;
3. no symlink exists in a managed project or bundle;
4. project creation from a protected working directory writes only under the managed runtime root;
5. the portable bundle runs with `PYTHONPATH` removed and without the source repository;
6. official Skill validation passes;
7. capability output truthfully reports later visual and PPT modules as unavailable;
8. the branch is clean after the final task commit.

After this gate passes, write Follow-on Plan 2 for Content and Visual Conception using the persisted `ProjectManifest`, `MaterialSource`, `ProjectState`, and event-log interfaces defined here.
