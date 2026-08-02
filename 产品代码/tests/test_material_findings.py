from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.artifact_store import ArtifactStore
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ArtifactValidationError, MaterialImportError
from ai_ppt_studio.materials import MAX_UPLOAD_BYTES, MaterialIntake
from ai_ppt_studio.models import ArtifactKind, SourceKind
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


def make_project(base: Path) -> tuple[PathPolicy, Path]:
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    policy = PathPolicy(config)
    project = ProjectStore(config, policy).create("材料证据测试")
    return policy, Path(project.project_root)


class MaterialFindingsTests(unittest.TestCase):
    def test_material_findings_require_traceable_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            policy, project = make_project(Path(temp))
            store = ArtifactStore(project, policy)
            with self.assertRaises(ArtifactValidationError):
                store.save(
                    ArtifactKind.MATERIAL_FINDINGS,
                    {
                        "summary": "发现一个事实",
                        "findings": [
                            {
                                "finding_id": "F01",
                                "finding_type": "fact",
                                "content": "客户有五个分散系统",
                            }
                        ],
                        "source_assignments": [],
                        "conflicts": [],
                        "gaps": [],
                    },
                )

            artifact = store.save(
                ArtifactKind.MATERIAL_FINDINGS,
                {
                    "summary": "识别出客户现状和建设依据",
                    "findings": [
                        {
                            "finding_id": "F01",
                            "finding_type": "fact",
                            "content": "客户有五个分散系统",
                            "source_ref": "sources/source-1.json",
                            "locator": "第 3 页",
                            "fact_status": "source-fact",
                            "purposes": ["customer-needs"],
                        }
                    ],
                    "source_assignments": [
                        {
                            "source_id": "source-1",
                            "purposes": ["customer-needs"],
                            "summary": "客户现状材料",
                            "status": "usable",
                        }
                    ],
                    "conflicts": [],
                    "gaps": [],
                },
            )
            self.assertEqual(artifact.kind, "material-findings")
            self.assertIn("cognition/material-findings", artifact.path)

    def test_engineering_samples_require_editable_native_render_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            policy, project = make_project(Path(temp))
            store = ArtifactStore(project, policy)
            with self.assertRaises(ArtifactValidationError):
                store.save(
                    ArtifactKind.ENGINEERING_SAMPLES,
                    {
                        "summary": "只有概念图",
                        "samples": [{"sample_id": "E01"}],
                        "native_coverage": {"whole_slide_bitmap": True},
                        "qa_status": "passed",
                    },
                )

            render = project / "renders" / "engineering-sample.png"
            render.write_bytes(b"render")
            artifact = store.save(
                ArtifactKind.ENGINEERING_SAMPLES,
                {
                    "summary": "关键页已还原为可编辑工程样张",
                    "samples": [
                        {
                            "sample_id": "E01",
                            "slide_refs": ["S03"],
                            "render_ref": "renders/engineering-sample.png",
                            "native_element_ratio": 0.94,
                            "editable": True,
                            "notes": "文字、形状和图片裁切均原生可编辑",
                        }
                    ],
                    "native_coverage": {
                        "text": True,
                        "shape": True,
                        "chart": True,
                        "image_crop": True,
                        "whole_slide_bitmap": False,
                    },
                    "qa_status": "passed",
                },
            )
            self.assertEqual(artifact.kind, "engineering-samples")

    def test_uploaded_bytes_are_bounded_hashed_and_use_a_safe_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            policy, project = make_project(Path(temp))
            body = b"customer requirement"
            record = MaterialIntake(policy).add_bytes(
                project,
                "../客户/需求<>说明.pdf",
                body,
                "application/pdf",
            )
            managed = Path(record.managed_ref or "")
            self.assertEqual(record.kind, SourceKind.FILE)
            self.assertEqual(record.sha256, hashlib.sha256(body).hexdigest())
            self.assertEqual(record.size_bytes, len(body))
            self.assertTrue(managed.is_relative_to(project / "managed-assets" / "uploads"))
            self.assertNotIn("..", managed.name)
            self.assertNotIn("/", managed.name)
            self.assertEqual(managed.read_bytes(), body)

            with self.assertRaises(MaterialImportError):
                MaterialIntake(policy).add_bytes(
                    project,
                    "too-large.bin",
                    b"x" * (MAX_UPLOAD_BYTES + 1),
                    "application/octet-stream",
                )


if __name__ == "__main__":
    unittest.main()
