from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import MaterialImportError
from ai_ppt_studio.materials import ImportMode, MaterialIntake
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_and_policy(base: Path, protected: tuple[Path, ...] = ()) -> tuple[PathPolicy, Path]:
    runtime = base / "runtime"
    config = RuntimeConfig.create(
        runtime,
        base / "repo",
        base / "install",
        base / "web",
        protected,
    )
    policy = PathPolicy(config)
    project = ProjectStore(config, policy).create("测试项目")
    return policy, Path(project.project_root)


class MaterialIntakeTests(unittest.TestCase):
    def test_copy_preserves_original_and_verifies_managed_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source_dir = base / "originals"
            source_dir.mkdir()
            source = source_dir / "需求说明.txt"
            source.write_text("建设智慧园区运营平台", encoding="utf-8")
            before = digest(source)
            policy, project = project_and_policy(base, (source_dir,))
            records = MaterialIntake(policy).add_local(
                project, source, ImportMode.COPY
            )
            self.assertEqual(digest(source), before)
            self.assertEqual(len(records), 1)
            managed = Path(records[0].managed_ref or "")
            self.assertTrue(managed.is_file())
            self.assertEqual(digest(managed), before)

    def test_reference_records_metadata_without_copying_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "brief.txt"
            source.write_text("只读材料", encoding="utf-8")
            policy, project = project_and_policy(base)
            record = MaterialIntake(policy).add_local(
                project, source, ImportMode.REFERENCE
            )[0]
            self.assertIsNone(record.managed_ref)
            self.assertEqual(record.original_ref, str(source.resolve()))
            self.assertEqual(len(list((project / "sources").glob("*.json"))), 1)

    def test_directory_recursion_is_sorted_and_rejects_descendant_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source_dir = base / "materials"
            (source_dir / "b").mkdir(parents=True)
            (source_dir / "z.txt").write_text("z", encoding="utf-8")
            (source_dir / "b" / "a.txt").write_text("a", encoding="utf-8")
            policy, project = project_and_policy(base)
            records = MaterialIntake(policy).add_local(
                project, source_dir, ImportMode.REFERENCE
            )
            self.assertEqual(
                [
                    Path(record.original_ref)
                    .relative_to(source_dir.resolve())
                    .as_posix()
                    for record in records
                ],
                ["b/a.txt", "z.txt"],
            )
            (source_dir / "linked.txt").symlink_to(source_dir / "z.txt")
            with self.assertRaises(MaterialImportError):
                MaterialIntake(policy).add_local(
                    project, source_dir, ImportMode.REFERENCE
                )

    def test_url_registration_never_opens_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            policy, project = project_and_policy(base)
            with patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
                record = MaterialIntake(policy).add_url(
                    project, "https://example.com/meeting-notes"
                )
            self.assertEqual(record.original_ref, "https://example.com/meeting-notes")
            self.assertIsNone(record.managed_ref)

    def test_text_is_written_only_to_managed_text_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            policy, project = project_and_policy(base)
            record = MaterialIntake(policy).add_text(
                project, "客户希望九月完成上线", "会议纪要"
            )
            managed = Path(record.managed_ref or "")
            self.assertEqual(managed.parent, project / "managed-assets" / "text")
            self.assertEqual(managed.read_text(encoding="utf-8"), "客户希望九月完成上线\n")

    def test_rejects_symlink_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source.txt"
            source.write_text("source", encoding="utf-8")
            link = base / "link.txt"
            link.symlink_to(source)
            policy, project = project_and_policy(base)
            with self.assertRaises(MaterialImportError):
                MaterialIntake(policy).add_local(
                    project, link, ImportMode.REFERENCE
                )


if __name__ == "__main__":
    unittest.main()
