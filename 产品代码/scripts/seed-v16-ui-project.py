"""Create one deterministic schema 3 project for local three-surface UI checks."""

from __future__ import annotations

import base64
import json
import re
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
    (project_root / "project.json").write_text(
        json.dumps(
            {
                "project_id": "schema3-ui-project",
                "project_root": str(project_root),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_assets = project_root / "review-assets"
    review_assets.mkdir(parents=True, exist_ok=True)
    accepted_prototype = (
        ROOT / "prototypes" / "08-content-full-deck-review-v7-inline-feedback.html"
    ).read_text(encoding="utf-8")
    embedded_slide = re.search(
        r"image:'data:image/jpeg;base64,([^']+)'",
        accepted_prototype,
    )
    if embedded_slide is None:
        raise RuntimeError("accepted content-review prototype has no embedded slide image")
    (review_assets / "content-evidence-page.jpg").write_bytes(
        base64.b64decode(embedded_slide.group(1))
    )
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
