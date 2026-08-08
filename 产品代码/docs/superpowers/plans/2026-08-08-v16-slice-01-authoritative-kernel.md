# v1.6 Slice 01 Authoritative Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the schema 3.0 authoritative local kernel, acceptance ledger, content-addressed artifact references, revision-safe logical transactions, and four-target evidence contract that every later v1.6 vertical slice will use.

**Architecture:** New code lives under focused `ai_ppt_studio.kernel`, `ai_ppt_studio.acceptance`, and `ai_ppt_studio.domains.presentation` packages. Immutable objects and revision events are written before one atomic state replacement, so the state file is the visibility boundary; orphaned pre-commit objects are ignored. Existing v1.x runtime modules remain temporarily unreferenced by this slice and are removed as later vertical slices switch to the new kernel.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON, SHA-256, existing crash-safe JSON helpers.

---

## File map

- `requirements/v1.6-acceptance-ledger.json`: generated inventory of formal numbered acceptance requirements and required evidence kinds.
- `scripts/build_acceptance_ledger.py`: deterministic generator for the checked-in ledger.
- `src/ai_ppt_studio/acceptance/ledger.py`: extraction, stable IDs, validation, and JSON serialization.
- `src/ai_ppt_studio/kernel/references.py`: strict `artifact://<kind>/<sha256>` identity.
- `src/ai_ppt_studio/kernel/artifacts.py`: immutable content-addressed object repository.
- `src/ai_ppt_studio/kernel/state.py`: schema 3.0 state model and initialization.
- `src/ai_ppt_studio/kernel/transactions.py`: revision guard, idempotency, event-before-state logical commit.
- `src/ai_ppt_studio/domains/presentation/targets.py`: four mandatory desktop target profiles and evidence aggregation.
- `src/ai_ppt_studio/adapters/legacy/importer.py`: one-way legacy import without fabricated pass states.
- `tests/test_acceptance_ledger.py`: ledger extraction and coverage tests.
- `tests/test_kernel_references.py`: formal reference parser tests.
- `tests/test_kernel_artifacts.py`: immutable repository and tamper detection tests.
- `tests/test_kernel_transactions.py`: revision, idempotency, and failure visibility tests.
- `tests/test_target_evidence_matrix.py`: four-target same-hash hard-gate tests.
- `tests/test_legacy_importer.py`: conservative schema 1/2 import tests.

### Task 1: Formal acceptance ledger

**Files:**
- Create: `产品代码/src/ai_ppt_studio/acceptance/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/acceptance/ledger.py`
- Create: `产品代码/scripts/build_acceptance_ledger.py`
- Create: `产品代码/requirements/v1.6-acceptance-ledger.json`
- Test: `产品代码/tests/test_acceptance_ledger.py`

- [ ] **Step 1: Write the failing ledger tests**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    extract_numbered_requirements,
)


class AcceptanceLedgerTests(unittest.TestCase):
    def test_extracts_stable_ids_and_proof_kinds(self) -> None:
        markdown = """# PRD\n## 17. 研发验收标准\n### 17.1 产品闭环\n1. 恢复项目。\n2. 状态一致。\n### 17.3 视觉与 PPTX\n1. 四目标实机通过。\n## 18. 其他\n1. 不应收录。\n"""
        entries = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )
        self.assertEqual(
            [entry.requirement_id for entry in entries],
            ["PRD-17.1-01", "PRD-17.1-02", "PRD-17.3-01"],
        )
        self.assertEqual(
            entries[-1].required_evidence,
            ("automated-test", "runtime-evidence", "target-evidence", "real-project"),
        )

    def test_rejects_duplicate_ids_and_missing_proof(self) -> None:
        markdown = "## 17. 标准\n### 17.1 闭环\n1. 恢复项目。\n"
        entry = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )[0]
        with self.assertRaises(ValueError):
            AcceptanceLedger(version="1.6", requirements=(entry, entry))

    def test_checked_in_ledger_matches_authoritative_sources(self) -> None:
        payload = json.loads(
            (ROOT / "requirements" / "v1.6-acceptance-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        ledger = AcceptanceLedger.from_dict(payload)
        self.assertGreaterEqual(len(ledger.requirements), 60)
        self.assertEqual(len(ledger.requirements), len(set(ledger.ids)))
        self.assertTrue(all(item.status == "unproven" for item in ledger.requirements))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the ledger tests and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_acceptance_ledger -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_ppt_studio.acceptance'`.

- [ ] **Step 3: Implement the ledger extractor and validator**

```python
# src/ai_ppt_studio/acceptance/__init__.py
"""Acceptance requirement inventory and proof tracking."""

from .ledger import AcceptanceLedger, Requirement, extract_numbered_requirements

__all__ = ["AcceptanceLedger", "Requirement", "extract_numbered_requirements"]
```

```python
# src/ai_ppt_studio/acceptance/ledger.py
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

MAJOR_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
HEADING = re.compile(r"^###\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$")
ITEM = re.compile(r"^(\d+)\.\s+(.+?)\s*$")


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    source_section: str
    text: str
    required_evidence: tuple[str, ...]
    status: str = "unproven"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = list(self.required_evidence)
        return payload


def _proof_kinds(source_prefix: str, section: str) -> tuple[str, ...]:
    proofs = ["automated-test", "runtime-evidence"]
    if source_prefix == "PRD" and section == "17.3":
        proofs.extend(["target-evidence", "real-project"])
    elif source_prefix == "SDD" and section == "21.3":
        proofs.append("real-project")
    elif source_prefix == "UI" and section.startswith("23"):
        proofs.append("viewport-evidence")
    return tuple(proofs)


def extract_numbered_requirements(
    markdown: str, *, source_prefix: str, section_prefix: str
) -> tuple[Requirement, ...]:
    current_section = ""
    entries: list[Requirement] = []
    for line in markdown.splitlines():
        major = MAJOR_HEADING.match(line)
        if major:
            current_section = major.group(1)
            continue
        heading = HEADING.match(line)
        if heading:
            current_section = heading.group(1)
            continue
        if not current_section.startswith(f"{section_prefix}."):
            continue
        item = ITEM.match(line)
        if not item:
            continue
        number, text = item.groups()
        entries.append(
            Requirement(
                requirement_id=f"{source_prefix}-{current_section}-{int(number):02d}",
                source_section=current_section,
                text=text,
                required_evidence=_proof_kinds(source_prefix, current_section),
            )
        )
    return tuple(entries)


@dataclass(frozen=True)
class AcceptanceLedger:
    version: str
    requirements: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        ids = self.ids
        if len(ids) != len(set(ids)):
            raise ValueError("Acceptance requirement IDs must be unique")
        if any(not item.required_evidence for item in self.requirements):
            raise ValueError("Every requirement needs an evidence contract")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.requirement_id for item in self.requirements)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "requirements": [item.as_dict() for item in self.requirements],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcceptanceLedger":
        return cls(
            version=str(payload["version"]),
            requirements=tuple(
                Requirement(
                    requirement_id=str(item["requirement_id"]),
                    source_section=str(item["source_section"]),
                    text=str(item["text"]),
                    required_evidence=tuple(item["required_evidence"]),
                    status=str(item.get("status", "unproven")),
                )
                for item in payload["requirements"]
            ),
        )
```

```python
# scripts/build_acceptance_ledger.py
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import AcceptanceLedger, extract_numbered_requirements

SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "17"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "21"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "23"),
)

requirements = []
for path, prefix, section in SOURCES:
    requirements.extend(
        extract_numbered_requirements(
            path.read_text(encoding="utf-8"),
            source_prefix=prefix,
            section_prefix=section,
        )
    )

ledger = AcceptanceLedger(version="1.6", requirements=tuple(requirements))
target = ROOT / "requirements" / "v1.6-acceptance-ledger.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(ledger.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"wrote {len(ledger.requirements)} requirements to {target}")
```

- [ ] **Step 4: Generate the ledger and verify GREEN**

Run: `cd 产品代码 && python3 scripts/build_acceptance_ledger.py && python3 -m unittest tests.test_acceptance_ledger -v`

Expected: the generator reports at least 60 requirements and all three tests PASS.

- [ ] **Step 5: Commit the ledger slice**

```bash
git add 产品代码/requirements 产品代码/scripts/build_acceptance_ledger.py 产品代码/src/ai_ppt_studio/acceptance 产品代码/tests/test_acceptance_ledger.py
git commit -m "feat: establish v1.6 acceptance ledger"
```

### Task 2: Strict artifact references

**Files:**
- Create: `产品代码/src/ai_ppt_studio/kernel/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/kernel/references.py`
- Test: `产品代码/tests/test_kernel_references.py`

- [ ] **Step 1: Write failing parser tests**

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.kernel.references import ArtifactReference


class ArtifactReferenceTests(unittest.TestCase):
    def test_round_trips_formal_reference(self) -> None:
        value = f"artifact://content-acceptance/{'a' * 64}"
        parsed = ArtifactReference.parse(value)
        self.assertEqual(parsed.kind, "content-acceptance")
        self.assertEqual(parsed.sha256, "a" * 64)
        self.assertEqual(str(parsed), value)

    def test_rejects_role_names_paths_versions_and_uppercase_hashes(self) -> None:
        invalid = (
            "content-review-agent",
            "artifacts/content.json",
            f"artifact://content-acceptance/v0001#{'a' * 64}",
            f"artifact://content-acceptance/{'A' * 64}",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ArtifactReferenceError):
                ArtifactReference.parse(value)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_references -v`

Expected: FAIL because `ai_ppt_studio.kernel` does not exist.

- [ ] **Step 3: Implement the strict reference value object**

```python
# src/ai_ppt_studio/kernel/__init__.py
"""Schema 3.0 authoritative project kernel."""
```

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from ai_ppt_studio.errors import ArtifactReferenceError

REFERENCE = re.compile(r"^artifact://([a-z][a-z0-9-]*)/([0-9a-f]{64})$")


@dataclass(frozen=True, order=True)
class ArtifactReference:
    kind: str
    sha256: str

    def __post_init__(self) -> None:
        if not REFERENCE.fullmatch(str(self)):
            raise ArtifactReferenceError(f"Invalid artifact reference: {self}")

    def __str__(self) -> str:
        return f"artifact://{self.kind}/{self.sha256}"

    @classmethod
    def parse(cls, value: str) -> "ArtifactReference":
        match = REFERENCE.fullmatch(value)
        if not match:
            raise ArtifactReferenceError(f"Invalid artifact reference: {value}")
        return cls(kind=match.group(1), sha256=match.group(2))
```

- [ ] **Step 4: Run and verify GREEN**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_references -v`

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add 产品代码/src/ai_ppt_studio/kernel 产品代码/tests/test_kernel_references.py
git commit -m "feat: add strict artifact identities"
```

### Task 3: Immutable content-addressed artifact repository

**Files:**
- Create: `产品代码/src/ai_ppt_studio/kernel/artifacts.py`
- Test: `产品代码/tests/test_kernel_artifacts.py`

- [ ] **Step 1: Write failing repository tests**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.kernel.artifacts import ArtifactRepository


class ArtifactRepositoryTests(unittest.TestCase):
    def test_put_is_immutable_deduplicated_and_project_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = ArtifactRepository(root, project_id="project-1")
            first = repo.put("mission-brief", {"goal": "通过方案"})
            second = repo.put("mission-brief", {"goal": "通过方案"})
            self.assertEqual(first, second)
            self.assertEqual(repo.resolve(first)["payload"]["goal"], "通过方案")
            with self.assertRaises(ArtifactReferenceError):
                ArtifactRepository(root, project_id="project-2").resolve(first)

    def test_resolve_rejects_tampered_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = ArtifactRepository(root, project_id="project-1")
            ref = repo.put("mission-brief", {"goal": "通过方案"})
            path = repo.path_for(ref)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["payload"]["goal"] = "已篡改"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ArtifactReferenceError):
                repo.resolve(ref)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_artifacts -v`

Expected: FAIL because `ArtifactRepository` does not exist.

- [ ] **Step 3: Implement immutable object storage**

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.references import ArtifactReference


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class ArtifactRepository:
    def __init__(self, project_root: Path, *, project_id: str) -> None:
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.objects_root = self.project_root / "artifacts" / "objects"

    def put(self, kind: str, payload: dict[str, Any]) -> ArtifactReference:
        envelope = {"project_id": self.project_id, "kind": kind, "payload": payload}
        sha256 = hashlib.sha256(canonical_json(envelope)).hexdigest()
        reference = ArtifactReference(kind=kind, sha256=sha256)
        path = self.path_for(reference)
        if not path.exists():
            atomic_write_json(path, envelope)
        return reference

    def path_for(self, reference: ArtifactReference) -> Path:
        return self.objects_root / reference.sha256[:2] / f"{reference.sha256}.json"

    def resolve(self, reference: ArtifactReference) -> dict[str, Any]:
        path = self.path_for(reference)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactReferenceError(f"Artifact does not resolve: {reference}") from exc
        actual = hashlib.sha256(canonical_json(envelope)).hexdigest()
        if actual != reference.sha256:
            raise ArtifactReferenceError(f"Artifact hash mismatch: {reference}")
        if envelope.get("project_id") != self.project_id:
            raise ArtifactReferenceError(f"Artifact belongs to another project: {reference}")
        if envelope.get("kind") != reference.kind:
            raise ArtifactReferenceError(f"Artifact kind mismatch: {reference}")
        return envelope
```

- [ ] **Step 4: Run and verify GREEN**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_artifacts -v`

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add 产品代码/src/ai_ppt_studio/kernel/artifacts.py 产品代码/tests/test_kernel_artifacts.py
git commit -m "feat: store immutable content-addressed artifacts"
```

### Task 4: Schema 3.0 state and logical transactions

**Files:**
- Create: `产品代码/src/ai_ppt_studio/kernel/state.py`
- Create: `产品代码/src/ai_ppt_studio/kernel/transactions.py`
- Test: `产品代码/tests/test_kernel_transactions.py`

- [ ] **Step 1: Write failing transaction tests**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import RevisionConflictError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ProjectKernelTests(unittest.TestCase):
    def test_commit_advances_revision_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            first = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={"mission": ("mission-brief", {"goal": "通过方案"})},
            )
            repeated = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={"mission": ("mission-brief", {"goal": "通过方案"})},
            )
            self.assertEqual(first.revision, 1)
            self.assertEqual(repeated.revision, 1)
            self.assertEqual(first.artifact_heads, repeated.artifact_heads)
            with self.assertRaises(RevisionConflictError):
                kernel.commit(
                    command_id="cmd-2",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={},
                )

    def test_state_is_visibility_boundary_when_state_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = ProjectKernel.initialize(root, project_id="p1")
            real_write = __import__(
                "ai_ppt_studio.kernel.transactions", fromlist=["atomic_write_json"]
            ).atomic_write_json

            def fail_state(path: Path, payload: dict[str, object]) -> None:
                if path.name == "state.json":
                    raise OSError("simulated state failure")
                real_write(path, payload)

            with patch(
                "ai_ppt_studio.kernel.transactions.atomic_write_json",
                side_effect=fail_state,
            ), self.assertRaises(OSError):
                kernel.commit(
                    command_id="cmd-1",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={"mission": ("mission-brief", {"goal": "通过方案"})},
                )
            self.assertEqual(kernel.load().revision, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_transactions -v`

Expected: FAIL because `ProjectKernel` does not exist.

- [ ] **Step 3: Implement schema 3.0 state**

```python
# src/ai_ppt_studio/kernel/state.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class KernelState:
    schema_version: str
    project_id: str
    revision: int
    artifact_heads: dict[str, str] = field(default_factory=dict)
    gate_status: dict[str, str] = field(default_factory=lambda: {
        "G0": "open", "G1": "locked", "G2": "locked", "G3": "locked", "G4": "locked"
    })
    processed_commands: dict[str, int] = field(default_factory=dict)
    last_transaction_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def initial(cls, project_id: str) -> "KernelState":
        return cls(schema_version="3.0", project_id=project_id, revision=0)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KernelState":
        return cls(
            schema_version=str(payload["schema_version"]),
            project_id=str(payload["project_id"]),
            revision=int(payload["revision"]),
            artifact_heads=dict(payload.get("artifact_heads", {})),
            gate_status=dict(payload.get("gate_status", {})),
            processed_commands={str(k): int(v) for k, v in payload.get("processed_commands", {}).items()},
            last_transaction_id=str(payload.get("last_transaction_id", "")),
        )
```

- [ ] **Step 4: Implement event-before-state logical commits**

```python
# src/ai_ppt_studio/kernel/transactions.py
from __future__ import annotations

import json
import fcntl
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from ai_ppt_studio.errors import RevisionConflictError
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.artifacts import ArtifactRepository
from ai_ppt_studio.kernel.state import KernelState


class ProjectKernel:
    def __init__(self, project_root: Path, *, project_id: str) -> None:
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.state_path = self.project_root / "kernel" / "state.json"
        self.events_root = self.project_root / "kernel" / "events"
        self.lock_path = self.project_root / "kernel" / "write.lock"
        self.artifacts = ArtifactRepository(self.project_root, project_id=project_id)

    @classmethod
    def initialize(cls, project_root: Path, *, project_id: str) -> "ProjectKernel":
        kernel = cls(project_root, project_id=project_id)
        if not kernel.state_path.exists():
            atomic_write_json(kernel.state_path, KernelState.initial(project_id).as_dict())
        return kernel

    def load(self) -> KernelState:
        return KernelState.from_dict(
            json.loads(self.state_path.read_text(encoding="utf-8"))
        )

    @contextmanager
    def _locked(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def commit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
    ) -> KernelState:
        with self._locked():
            state = self.load()
            if command_id in state.processed_commands:
                return state
            if state.revision != expected_revision:
                raise RevisionConflictError(expected_revision, state.revision)
            transaction_id = str(uuid.uuid4())
            heads = dict(state.artifact_heads)
            for slot, (kind, payload) in artifact_updates.items():
                heads[slot] = str(self.artifacts.put(kind, payload))
            next_revision = state.revision + 1
            event = {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "event_type": event_type,
                "revision": next_revision,
                "artifact_heads": heads,
            }
            atomic_write_json(self.events_root / f"r{next_revision:08d}.json", event)
            commands = dict(state.processed_commands)
            commands[command_id] = next_revision
            committed = replace(
                state,
                revision=next_revision,
                artifact_heads=heads,
                processed_commands=commands,
                last_transaction_id=transaction_id,
            )
            atomic_write_json(self.state_path, committed.as_dict())
            return committed
```

- [ ] **Step 5: Run and verify GREEN**

Run: `cd 产品代码 && python3 -m unittest tests.test_kernel_transactions -v`

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add 产品代码/src/ai_ppt_studio/kernel/state.py 产品代码/src/ai_ppt_studio/kernel/transactions.py 产品代码/tests/test_kernel_transactions.py
git commit -m "feat: add revision-safe schema 3 kernel"
```

### Task 5: Four-target same-hash evidence contract

**Files:**
- Create: `产品代码/src/ai_ppt_studio/domains/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/domains/presentation/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/domains/presentation/targets.py`
- Test: `产品代码/tests/test_target_evidence_matrix.py`

- [ ] **Step 1: Write failing four-target tests**

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.domains.presentation.targets import (
    REQUIRED_TARGET_IDS,
    TargetRenderEvidence,
    validate_required_targets,
)


def evidence(target: str, sha: str = "a" * 64, result: str = "passed") -> TargetRenderEvidence:
    return TargetRenderEvidence(
        target_id=target,
        operating_system="macOS" if target.startswith("macos") else "Windows 11",
        application="WPS Office" if target.endswith("wps") else "Microsoft PowerPoint",
        application_version="test-version",
        pptx_sha256=sha,
        overall_result=result,
        evidence_ref=f"artifact://target-render-evidence/{target[0] * 64}",
    )


class TargetEvidenceMatrixTests(unittest.TestCase):
    def test_accepts_all_four_targets_for_same_hash(self) -> None:
        result = validate_required_targets([evidence(target) for target in REQUIRED_TARGET_IDS])
        self.assertEqual(result.pptx_sha256, "a" * 64)
        self.assertEqual(result.target_ids, REQUIRED_TARGET_IDS)

    def test_rejects_missing_failed_duplicate_or_mismatched_hash(self) -> None:
        cases = (
            [evidence(target) for target in REQUIRED_TARGET_IDS[:-1]],
            [evidence(target, result="failed" if target == "macos-wps" else "passed") for target in REQUIRED_TARGET_IDS],
            [evidence(target, sha="b" * 64 if target == "windows-wps" else "a" * 64) for target in REQUIRED_TARGET_IDS],
            [evidence(target) for target in REQUIRED_TARGET_IDS] + [evidence("macos-wps")],
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(GateBlockedError):
                validate_required_targets(values)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_target_evidence_matrix -v`

Expected: FAIL because `ai_ppt_studio.domains.presentation.targets` does not exist.

- [ ] **Step 3: Implement the four-target contract**

```python
# src/ai_ppt_studio/domains/__init__.py
"""Versioned business domains for the v1.6 runtime."""
```

```python
# src/ai_ppt_studio/domains/presentation/__init__.py
"""Native presentation build and target-render contracts."""
```

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference

REQUIRED_TARGET_IDS = (
    "macos-powerpoint",
    "macos-wps",
    "windows-powerpoint",
    "windows-wps",
)


@dataclass(frozen=True)
class TargetRenderEvidence:
    target_id: str
    operating_system: str
    application: str
    application_version: str
    pptx_sha256: str
    overall_result: str
    evidence_ref: str

    def __post_init__(self) -> None:
        ArtifactReference.parse(self.evidence_ref)
        if self.target_id not in REQUIRED_TARGET_IDS:
            raise ValueError(f"Unknown target profile: {self.target_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", self.pptx_sha256):
            raise ValueError("PPTX SHA-256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class TargetEvidenceMatrix:
    pptx_sha256: str
    target_ids: tuple[str, ...]


def validate_required_targets(
    evidence: list[TargetRenderEvidence],
) -> TargetEvidenceMatrix:
    counts = {target: 0 for target in REQUIRED_TARGET_IDS}
    missing: list[str] = []
    for item in evidence:
        if item.target_id in counts:
            counts[item.target_id] += 1
    missing.extend(target for target, count in counts.items() if count != 1)
    if any(item.overall_result != "passed" for item in evidence):
        missing.append("failed-target")
    hashes = {item.pptx_sha256 for item in evidence}
    if len(hashes) != 1:
        missing.append("pptx-hash-mismatch")
    if missing:
        raise GateBlockedError("target-render-matrix", tuple(sorted(set(missing))))
    return TargetEvidenceMatrix(
        pptx_sha256=next(iter(hashes)), target_ids=REQUIRED_TARGET_IDS
    )
```

- [ ] **Step 4: Run and verify GREEN**

Run: `cd 产品代码 && python3 -m unittest tests.test_target_evidence_matrix -v`

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add 产品代码/src/ai_ppt_studio/domains 产品代码/tests/test_target_evidence_matrix.py
git commit -m "feat: require four target render profiles"
```

### Task 6: Conservative legacy importer

**Files:**
- Create: `产品代码/src/ai_ppt_studio/adapters/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/adapters/legacy/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/adapters/legacy/importer.py`
- Test: `产品代码/tests/test_legacy_importer.py`

- [ ] **Step 1: Write the failing importer test**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.adapters.legacy.importer import LegacyProjectImporter
from ai_ppt_studio.kernel.transactions import ProjectKernel


class LegacyImporterTests(unittest.TestCase):
    def test_imports_verifiable_payloads_without_copying_pass_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            legacy = base / "legacy"
            legacy.mkdir()
            (legacy / "project.json").write_text(
                json.dumps({"project_id": "legacy-1", "name": "旧项目", "schema_version": "2.0"}),
                encoding="utf-8",
            )
            (legacy / "state.json").write_text(
                json.dumps({"gates": {"G0": "passed", "G1": "passed"}}),
                encoding="utf-8",
            )
            (legacy / "mission.json").write_text(
                json.dumps({"goal": "确认一期方案", "audience": "客户决策者"}),
                encoding="utf-8",
            )
            destination = base / "new"
            report = LegacyProjectImporter().import_project(legacy, destination)
            state = ProjectKernel(destination, project_id="legacy-1").load()
            self.assertEqual(state.schema_version, "3.0")
            self.assertEqual(state.gate_status["G0"], "open")
            self.assertIn("mission", state.artifact_heads)
            self.assertIn("legacy pass states were not imported", report.warnings)
            self.assertEqual(json.loads((legacy / "state.json").read_text())["gates"]["G0"], "passed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `cd 产品代码 && python3 -m unittest tests.test_legacy_importer -v`

Expected: FAIL because the legacy importer does not exist.

- [ ] **Step 3: Implement read-only one-way import**

```python
# src/ai_ppt_studio/adapters/__init__.py
"""External storage and platform adapters."""
```

```python
# src/ai_ppt_studio/adapters/legacy/__init__.py
"""Conservative one-way import of legacy local projects."""
```

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_ppt_studio.kernel.transactions import ProjectKernel


@dataclass(frozen=True)
class LegacyImportReport:
    project_id: str
    imported_slots: tuple[str, ...]
    warnings: tuple[str, ...]


class LegacyProjectImporter:
    def import_project(self, source: Path, destination: Path) -> LegacyImportReport:
        source = source.resolve(strict=True)
        manifest = json.loads((source / "project.json").read_text(encoding="utf-8"))
        project_id = str(manifest["project_id"])
        kernel = ProjectKernel.initialize(destination, project_id=project_id)
        updates: dict[str, tuple[str, dict[str, object]]] = {}
        mission_path = source / "mission.json"
        if mission_path.is_file():
            updates["mission"] = (
                "mission-brief",
                json.loads(mission_path.read_text(encoding="utf-8")),
            )
        if updates:
            kernel.commit(
                command_id="legacy-import",
                expected_revision=0,
                event_type="legacy.imported",
                artifact_updates=updates,
            )
        return LegacyImportReport(
            project_id=project_id,
            imported_slots=tuple(sorted(updates)),
            warnings=("legacy pass states were not imported",),
        )
```

- [ ] **Step 4: Run and verify GREEN**

Run: `cd 产品代码 && python3 -m unittest tests.test_legacy_importer -v`

Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add 产品代码/src/ai_ppt_studio/adapters 产品代码/tests/test_legacy_importer.py
git commit -m "feat: import legacy projects without false evidence"
```

### Task 7: Slice verification and handoff

**Files:**
- Modify: `产品代码/docs/superpowers/plans/2026-08-08-v16-slice-01-authoritative-kernel.md`

- [ ] **Step 1: Run the focused schema 3.0 suite**

Run:

```bash
cd 产品代码 && python3 -m unittest \
  tests.test_acceptance_ledger \
  tests.test_kernel_references \
  tests.test_kernel_artifacts \
  tests.test_kernel_transactions \
  tests.test_target_evidence_matrix \
  tests.test_legacy_importer -v
```

Expected: 12 tests PASS with zero failures and zero errors.

- [ ] **Step 2: Run the complete Python regression suite**

Run: `cd 产品代码 && python3 -m unittest discover -s tests`

Expected: zero failures. Any legacy test that asserts a superseded v1.4/v1.5 behavior must be removed or rewritten only after a new v1.6 failing test demonstrates the replacement contract.

- [ ] **Step 3: Verify repository hygiene**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intentional remaining v1.6 work is dirty.

- [ ] **Step 4: Mark completed plan checkboxes and commit**

```bash
git add 产品代码/docs/superpowers/plans/2026-08-08-v16-slice-01-authoritative-kernel.md
git commit -m "docs: complete v1.6 authoritative kernel slice"
```
