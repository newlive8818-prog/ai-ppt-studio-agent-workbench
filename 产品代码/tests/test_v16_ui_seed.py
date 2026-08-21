from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.workbench_bridge import dispatch


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise AssertionError(f"Not a real PNG fixture: {path}")
    return struct.unpack(">II", data[16:24])


class V16UiSeedTests(unittest.TestCase):
    def run_seed(
        self,
        *,
        check: bool = True,
        env: dict[str, str] | None = None,
        arguments: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "seed-v16-ui-project.py"),
                *(arguments or []),
            ],
            cwd=ROOT,
            check=check,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )

    def test_seed_atomically_creates_private_distinct_children_and_rejects_arguments_before_creation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="seed-policy-root.") as controlled:
            parent = Path(controlled).resolve()
            child_env = {"TMPDIR": str(parent)}
            roots: list[Path] = []
            for _ in range(2):
                seeded = json.loads(self.run_seed(env=child_env).stdout)
                private_root = Path(seeded["acceptance_root"])
                roots.append(private_root)
                self.assertEqual(private_root.resolve().parent, parent)
                self.assertTrue(private_root.name.startswith("ai-ppt-v22-ui."))
                self.assertFalse(private_root.is_symlink())
                private_stat = private_root.lstat()
                if hasattr(os, "getuid"):
                    self.assertEqual(private_stat.st_uid, os.getuid())
                self.assertEqual(private_stat.st_mode & 0o077, 0)
                self.assertTrue(Path(seeded["workspace_config"]).is_file())
                self.assertTrue(Path(seeded["project_root"]).is_dir())
            self.assertEqual(len(set(roots)), 2)

            user_directory = parent / "existing-user-directory"
            user_directory.mkdir()
            sentinel = user_directory / "keep.txt"
            sentinel.write_text("user-owned", encoding="utf-8")
            before = {path.name for path in parent.iterdir()}
            rejected = self.run_seed(
                check=False,
                env=child_env,
                arguments=[str(user_directory)],
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Usage", rejected.stderr)
            self.assertEqual({path.name for path in parent.iterdir()}, before)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user-owned")

    def test_seed_creates_real_review_assets_and_an_unsubmitted_content_draft(self) -> None:
        with tempfile.TemporaryDirectory(prefix="seed-policy-root.") as temp:
            result = self.run_seed(env={"TMPDIR": temp})
            seeded = json.loads(result.stdout)
            acceptance_root = Path(seeded["acceptance_root"])
            self.assertEqual(
                acceptance_root,
                Path(seeded["project_root"]).parents[1],
            )
            project_root = Path(seeded["project_root"])
            self.assertIn("workspace_config", seeded)
            workspace_config = Path(seeded["workspace_config"])
            self.assertTrue(
                project_root.is_relative_to(acceptance_root / "projects")
            )
            self.assertEqual(acceptance_root.resolve().parent, Path(temp).resolve())
            self.assertTrue(workspace_config.is_file())

            snapshot = dispatch(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project_root),
                    "workspace_config": str(workspace_config),
                }
            )["snapshot"]
            self.assertEqual(snapshot["schema_version"], "3.0")
            self.assertNotIn("workspace", snapshot)
            self.assertIn("release/target-policy", snapshot["artifacts"])
            self.assertIn(
                snapshot["status"]["status"],
                {"AI 正在处理", "成果已可查看", "需要你处理", "任务受阻"},
            )
            self.assertNotIn("active_space", snapshot["status"])

            content = dispatch(
                {
                    "operation": "get-content-review-projection",
                    "project_root": str(project_root),
                    "review_session_id": seeded["content_review_session_id"],
                    "workspace_config": str(workspace_config),
                }
            )["review"]
            visual = dispatch(
                {
                    "operation": "get-visual-review-projection",
                    "project_root": str(project_root),
                    "review_session_id": seeded["visual_review_session_id"],
                    "workspace_config": str(workspace_config),
                }
            )["review"]
            self.assertEqual(content["review_type"], "content-full-deck")
            self.assertEqual(len(content["slides"]), 3)
            self.assertGreaterEqual(content["progress"]["remaining"], 1)
            self.assertIsNone(content["batch"])
            self.assertEqual(content["review_session"]["status"], "ready")
            self.assertEqual(len(content["decisions"]), 1)
            self.assertEqual(content["decisions"][0]["decision"], "modify")
            draft = seeded["content_review_draft"]
            self.assertEqual(draft["decision"], "modify")
            self.assertTrue(draft["comment"].strip())
            self.assertIn(draft["slide_id"], {slide["slide_id"] for slide in content["slides"]})
            self.assertEqual(draft["slide_id"], content["decisions"][0]["slide_id"])

            material_ids: list[str] = []
            material_refs: list[str] = []
            material_hashes: list[str] = []
            for slide in content["slides"]:
                self.assertTrue(slide["material_views"], slide["slide_id"])
                for material in slide["material_views"]:
                    self.assertEqual(
                        set(material), {"material_view_id", "asset_ref"}
                    )
                    self.assertTrue(
                        material["material_view_id"].startswith(f"{slide['slide_id']}-"),
                        material,
                    )
                    self.assertTrue(
                        Path(material["asset_ref"]).stem.startswith(f"{slide['slide_id']}-"),
                        material,
                    )
                    asset_path = project_root / material["asset_ref"]
                    width, height = png_dimensions(asset_path)
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)
                    material_ids.append(material["material_view_id"])
                    material_refs.append(material["asset_ref"])
                    material_hashes.append(hashlib.sha256(asset_path.read_bytes()).hexdigest())
            self.assertEqual(len(set(material_ids)), len(material_ids))
            self.assertEqual(len(set(material_refs)), len(material_refs))
            self.assertGreaterEqual(len(set(material_hashes)), len(content["slides"]))

            self.assertEqual(visual["review_type"], "visual-professional")
            self.assertEqual(len(visual["anchors"]), 3)
            self.assertEqual(len(visual["slide_visual_contracts"]), 3)
            current_asset_refs = [anchor["current_asset_ref"] for anchor in visual["anchors"]]
            self.assertEqual(len(set(current_asset_refs)), 3)
            previous_asset_refs = [
                anchor["previous_asset_ref"]
                for anchor in visual["anchors"]
                if anchor["previous_asset_ref"]
            ]
            self.assertGreaterEqual(len(previous_asset_refs), 1)
            for asset_ref in [*current_asset_refs, *previous_asset_refs]:
                width, height = png_dimensions(project_root / asset_ref)
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
            self.assertEqual(visual["host_submission_capability"], "unknown")
            self.assertEqual(visual["ai_receipt_capability"], "unknown")
            self.assertEqual(
                seeded["evidence_identity"],
                "local-development-preview-not-host-ai-presentations-powerpoint-or-user-proof",
            )


if __name__ == "__main__":
    unittest.main()
