from __future__ import annotations

import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.artifact_store import ArtifactStore
from ai_ppt_studio.cli import build_parser, dispatch
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.models import ArtifactKind
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.review_html import ReviewHtml, ReviewKind
from ai_ppt_studio.state_store import StateStore

from tests.test_artifact_store import content_blueprint


class TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external_resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        candidate = values.get("src") or values.get("href")
        if candidate and candidate.startswith(("http://", "https://")):
            self.external_resources.append(candidate)


class ReviewHtmlTests(unittest.TestCase):
    def make_project(self, base: Path) -> tuple[Path, PathPolicy, ArtifactStore]:
        config = RuntimeConfig.create(
            base / "runtime", base / "repo", base / "install", base / "web"
        )
        policy = PathPolicy(config)
        manifest = ProjectStore(config, policy).create("审阅页测试")
        project = Path(manifest.project_root)
        StateStore(project, policy).initialize()
        return project, policy, ArtifactStore(project, policy)

    def test_content_review_is_offline_and_contains_slide_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy, artifacts = self.make_project(Path(temp))
            artifacts.save(
                ArtifactKind.CONTENT_BLUEPRINT, content_blueprint("智慧园区内容蓝图")
            )
            path = ReviewHtml(project, policy).generate(ReviewKind.CONTENT)
            body = path.read_text(encoding="utf-8")
            self.assertIn("内容蓝图集中审阅", body)
            self.assertIn("客户为什么现在需要建设", body)
            self.assertIn("data-review-action", body)
            self.assertIn("自然语言修改意见", body)
            self.assertIn('rel="icon"', body)
            self.assertIn("data:image/svg+xml", body)
            parser = TagCollector()
            parser.feed(body)
            self.assertEqual(parser.external_resources, [])

    def test_all_four_review_modes_are_rebuildable_from_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy, artifacts = self.make_project(Path(temp))
            artifacts.save(
                ArtifactKind.CONTENT_BLUEPRINT, content_blueprint("完整项目")
            )
            artifacts.save(
                ArtifactKind.VISUAL_BRIEF,
                {
                    "design_challenge": "把复杂方案讲得可信且易读",
                    "audience": "园区管委会",
                    "desired_response": "相信路径可落地",
                    "constraints": ["阅读优先", "16:9"],
                },
            )
            artifacts.save(
                ArtifactKind.CONCEPT_SET,
                {
                    "directions": [
                        {"id": "A", "name": "秩序之城", "thesis": "结构化秩序"},
                        {"id": "B", "name": "生长网络", "thesis": "连接与演进"},
                    ]
                },
            )
            artifacts.save(
                ArtifactKind.SLIDE_SCENE_GRAPH,
                {
                    "slides": [
                        {
                            "slide_id": "S01",
                            "width": 13.333,
                            "height": 7.5,
                            "elements": [{"type": "text", "role": "title"}],
                        }
                    ]
                },
            )
            artifacts.save(
                ArtifactKind.DELIVERY,
                {
                    "pptx": "ppt/demo.pptx",
                    "renders": ["renders/slide-1.png"],
                    "qa_status": "passed",
                    "sources": ["sources/source-1.json"],
                },
            )
            generated = {
                kind: ReviewHtml(project, policy).generate(kind)
                for kind in ReviewKind
            }
            self.assertEqual(set(generated), set(ReviewKind))
            for path in generated.values():
                self.assertTrue(path.is_file())
                self.assertIn("AI PPT Studio", path.read_text(encoding="utf-8"))

    def test_cli_review_command_returns_generated_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config = RuntimeConfig.create(
                base / "runtime", base / "repo", base / "install", base / "web"
            )
            policy = PathPolicy(config)
            manifest = ProjectStore(config, policy).create("CLI 审阅")
            project = Path(manifest.project_root)
            StateStore(project, policy).initialize()
            ArtifactStore(project, policy).save(
                ArtifactKind.CONTENT_BLUEPRINT, content_blueprint("CLI 内容")
            )
            args = build_parser().parse_args(
                [
                    "--runtime-root",
                    str(config.runtime_root),
                    "--source-repo-root",
                    str(config.source_repo_root),
                    "--install-root",
                    str(config.install_root),
                    "--upstream-root",
                    str(config.upstream_root),
                    "review",
                    "--project",
                    str(project),
                    "--kind",
                    ReviewKind.CONTENT.value,
                ]
            )
            payload = dispatch(args)
            self.assertTrue(Path(str(payload["review_path"])).is_file())


if __name__ == "__main__":
    unittest.main()
