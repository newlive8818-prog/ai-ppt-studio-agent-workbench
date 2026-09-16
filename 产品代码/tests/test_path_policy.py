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
