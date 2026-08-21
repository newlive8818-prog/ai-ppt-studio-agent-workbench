"""Create one deterministic schema 3 project for local three-surface UI checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests.v16_delivery_fixtures import prepared_delivery_ready
from ai_ppt_studio.config import RuntimeConfig


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: seed-v16-ui-project.py <isolated-base-directory>")
    base = Path(sys.argv[1]).expanduser().resolve(strict=False)
    config = RuntimeConfig.create(
        runtime_root=base,
        source_repo_root=ROOT,
        install_root=ROOT / ".ui-acceptance-install-root",
        upstream_root=ROOT.parent,
    )
    workspace_config = base / "workspace.json"
    config.save(workspace_config)
    project_root = base / "projects" / "schema3-ui-project"
    delivery, revision, refs = prepared_delivery_ready(project_root, slide_count=2)
    state = delivery.kernel.load()
    print(
        json.dumps(
            {
                "schema_version": state.schema_version,
                "project_root": str(project_root),
                "workspace_config": str(workspace_config),
                "revision": revision,
                "pptx_sha256": refs["pptx_sha256"],
                "evidence_identity": "deterministic-contract-fixture-not-real-project-proof",
                "content_review_scenarios": [
                    "content-producing",
                    "content-hard-gate-review",
                    "content-hard-gate-failed",
                    "content-hard-gate-repaired",
                    "ready-10",
                    "mixed-decisions-24",
                    "long-review-60",
                    "save-failure",
                    "source-conflict",
                    "submitted-frozen",
                    "plan-proposed",
                    "new-version-zero-decisions",
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
