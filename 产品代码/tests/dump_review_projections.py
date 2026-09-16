"""Generate schema 3 ReviewService fixtures for the React integration tests.

The generated target evidence is deterministic contract data. It proves the
runtime/UI boundary only and must never be described as desktop PowerPoint/WPS
evidence.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.review_service import ReviewService
from tests.v16_visual_fixtures import prepared_g2


def projections() -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory(prefix="ai-ppt-v16-review-fixture-") as temp:
        visual, revision, _refs = prepared_g2(Path(temp), slide_count=3)
        visual.publish_visual_review("publish-review-fixture", revision)
        reviewer = ReviewService(visual.kernel)
        return reviewer.content_projection(), reviewer.visual_projection()


def main() -> None:
    content, visual = projections()
    out = ROOT / "widget" / "src" / "__fixtures__"
    out.mkdir(parents=True, exist_ok=True)
    for review_type, projection in (("content", content), ("visual", visual)):
        path = out / f"review-projection.{review_type}.json"
        path.write_text(
            json.dumps(projection, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
