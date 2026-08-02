"""Generate disposable offline review pages from authoritative project artifacts."""

from __future__ import annotations

import html
import json
from enum import Enum
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .errors import ProjectNotFoundError
from .models import ArtifactKind, ArtifactVersion, ProjectManifest
from .paths import PathPolicy
from .state_store import StateStore


class ReviewKind(str, Enum):
    CONTENT = "content"
    CONCEPT = "concept"
    ENGINEERING = "engineering"
    DELIVERY = "delivery"


REVIEW_TITLES = {
    ReviewKind.CONTENT: ("内容蓝图集中审阅", "先确认讲什么、为什么这样讲，以及每页引用哪些真实材料。"),
    ReviewKind.CONCEPT: ("视觉方向与概念样张比较", "比较真正不同的设计命题，选择主方向或提出定向修改。"),
    ReviewKind.ENGINEERING: ("概念、场景图与工程样张对照", "检查视觉构想在真实可编辑 PPT 中是否发生设计掉级。"),
    ReviewKind.DELIVERY: ("整套渲染与交付验收", "集中检查事实、视觉、字体、素材、来源和编辑性。"),
}


class ReviewHtml:
    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.artifacts = ArtifactStore(self.project_root, policy)

    def generate(self, kind: ReviewKind) -> Path:
        manifest = self._manifest()
        state = StateStore(self.project_root, self.policy).load()
        title, description = REVIEW_TITLES[kind]
        content, count = self._render_content(kind)
        template = self._load_template()
        summary = self._summary(manifest, state.current_gate, state.revision, count)
        replacements = {
            "@@PAGE_TITLE@@": html.escape(title),
            "@@PAGE_DESCRIPTION@@": html.escape(description),
            "@@REVIEW_KIND@@": html.escape(kind.value),
            "@@PROJECT_ID@@": html.escape(manifest.project_id),
            "@@HEADER_META@@": html.escape(
                f"{manifest.name} · {state.current_gate} · revision {state.revision}"
            ),
            "@@SUMMARY@@": summary,
            "@@CONTENT@@": content,
        }
        for marker, value in replacements.items():
            template = template.replace(marker, value)
        destination = self.policy.assert_write_allowed(
            self.project_root / "reviews" / f"{kind.value}-review.html"
        )
        destination.write_text(template, encoding="utf-8")
        return destination

    def _manifest(self) -> ProjectManifest:
        path = self.project_root / "project.json"
        try:
            return ProjectManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProjectNotFoundError(f"Invalid project manifest: {path}") from exc

    def _render_content(self, kind: ReviewKind) -> tuple[str, int]:
        if kind is ReviewKind.CONTENT:
            artifact = self.artifacts.latest(ArtifactKind.CONTENT_BLUEPRINT)
            slides = artifact.payload.get("slides", [])
            cards = "".join(self._content_card(slide) for slide in slides)
            return self._section("逐页内容与依据", cards, artifact), len(slides)
        if kind is ReviewKind.CONCEPT:
            brief = self.artifacts.latest(ArtifactKind.VISUAL_BRIEF)
            concepts = self.artifacts.latest(ArtifactKind.CONCEPT_SET)
            directions = concepts.payload.get("directions", [])
            brief_card = self._generic_card("视觉任务", brief.payload, "visual-brief")
            cards = brief_card + "".join(
                self._direction_card(direction, index)
                for index, direction in enumerate(directions, start=1)
            )
            return self._section("设计命题与候选方向", cards, concepts), len(directions)
        if kind is ReviewKind.ENGINEERING:
            concepts = self.artifacts.latest(ArtifactKind.CONCEPT_SET)
            graph = self.artifacts.latest(ArtifactKind.SLIDE_SCENE_GRAPH)
            directions = concepts.payload.get("directions", [])
            graphs = graph.payload.get("slides", [graph.payload])
            cards = "".join(
                self._direction_card(direction, index)
                for index, direction in enumerate(directions, start=1)
            )
            cards += "".join(
                self._generic_card(
                    f"场景图 {item.get('slide_id', index)}", item, f"scene-{index}"
                )
                for index, item in enumerate(graphs, start=1)
            )
            cards += self._render_image_cards()
            return self._section("意图—结构—渲染对照", cards, graph), len(graphs)
        delivery = self.artifacts.latest(ArtifactKind.DELIVERY)
        payload = delivery.payload
        cards = self._generic_card("交付结果", payload, "delivery")
        renders = payload.get("renders", [])
        cards += "".join(
            self._image_card(str(item), f"render-{index}")
            for index, item in enumerate(renders, start=1)
        )
        return self._section("全页交付检查", cards, delivery), len(renders)

    def _content_card(self, slide: Any) -> str:
        if not isinstance(slide, dict):
            return ""
        slide_id = html.escape(str(slide.get("slide_id", "slide")))
        title = html.escape(str(slide.get("title", "未命名页面")))
        visible = self._value(slide.get("visible_content", []))
        sources = self._value(slide.get("source_refs", []))
        materials = self._value(slide.get("material_refs", []))
        return (
            f'<article class="card"><div class="kicker">{slide_id} · '
            f'{html.escape(str(slide.get("purpose", "")))}</div><h3>{title}</h3>'
            f'<div class="claim">{html.escape(str(slide.get("claim", "")))}</div>'
            f'<div class="label">页面可见内容</div><div class="value">{visible}</div>'
            f'<div class="label">讲解稿</div><div class="value">{html.escape(str(slide.get("speaker_notes", "")))}</div>'
            f'<div class="label">材料与来源</div><div class="value">{materials}{sources}</div>'
            f'{self._decision_buttons(slide_id)}</article>'
        )

    def _direction_card(self, direction: Any, index: int) -> str:
        if not isinstance(direction, dict):
            return ""
        key = html.escape(str(direction.get("id", f"direction-{index}")))
        title = html.escape(str(direction.get("name", f"方向 {index}")))
        thesis = html.escape(str(direction.get("thesis", direction.get("design_thesis", ""))))
        image = direction.get("sample_image")
        image_html = self._image(str(image)) if image else ""
        rest = {k: v for k, v in direction.items() if k not in {"id", "name", "thesis", "design_thesis", "sample_image"}}
        return (
            f'<article class="card direction"><div class="kicker">方向 {index}</div><h3>{title}</h3>'
            f'<div class="claim">{thesis}</div>{image_html}<div class="value">{self._value(rest)}</div>'
            f'{self._decision_buttons(key)}</article>'
        )

    def _generic_card(self, title: str, payload: Any, key: str) -> str:
        return (
            f'<article class="card"><h3>{html.escape(title)}</h3>'
            f'<div class="value">{self._value(payload)}</div>{self._decision_buttons(key)}</article>'
        )

    def _render_image_cards(self) -> str:
        renders = sorted((self.project_root / "renders").glob("*.png"))
        return "".join(
            self._image_card(str(path), f"render-{index}")
            for index, path in enumerate(renders, start=1)
        )

    def _image_card(self, reference: str, key: str) -> str:
        return (
            f'<article class="card"><h3>{html.escape(Path(reference).name)}</h3>'
            f'{self._image(reference)}{self._decision_buttons(key)}</article>'
        )

    def _image(self, reference: str) -> str:
        if reference.startswith(("http://", "https://")):
            return f'<div class="value">外部图片引用：{html.escape(reference)}</div>'
        candidate = Path(reference)
        if candidate.is_absolute():
            try:
                reference = candidate.relative_to(self.project_root).as_posix()
            except ValueError:
                return f'<div class="value">项目外图片引用：{html.escape(str(candidate))}</div>'
        src = "../" + reference.lstrip("./")
        return f'<img class="asset" src="{html.escape(src, quote=True)}" alt="本地项目视觉资产">'

    @staticmethod
    def _decision_buttons(key: str) -> str:
        safe = html.escape(key, quote=True)
        return (
            '<div class="decision">'
            f'<button data-review-key="{safe}" data-review-action="accept">采纳</button>'
            f'<button data-review-key="{safe}" data-review-action="revise">修改</button>'
            f'<button data-review-key="{safe}" data-review-action="reject">否决</button>'
            "</div>"
        )

    def _value(self, value: Any) -> str:
        if isinstance(value, dict):
            return "".join(
                f'<div><span class="label">{html.escape(str(key))}</span> '
                f'{self._value(item)}</div>'
                for key, item in value.items()
            )
        if isinstance(value, list):
            return '<div class="tags">' + "".join(
                f'<span class="tag">{html.escape(str(item))}</span>' for item in value
            ) + "</div>"
        return html.escape(str(value))

    @staticmethod
    def _section(title: str, cards: str, artifact: ArtifactVersion) -> str:
        return (
            f'<div class="section-title"><h2>{html.escape(title)}</h2>'
            f'<span>{html.escape(artifact.kind)} · v{artifact.version:04d}</span></div>'
            f'<section class="grid">{cards}</section>'
        )

    @staticmethod
    def _summary(
        manifest: ProjectManifest, current_gate: str, revision: int, count: int
    ) -> str:
        items = (
            ("项目", manifest.name),
            ("当前状态门", current_gate),
            ("项目修订", str(revision)),
            ("本页对象", str(count)),
        )
        return '<section class="summary">' + "".join(
            f'<div class="metric"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></div>'
            for label, value in items
        ) + "</section>"

    @staticmethod
    def _load_template() -> str:
        here = Path(__file__).resolve()
        candidates = (
            here.parents[2] / "assets" / "review-template.html",
            here.parents[2]
            / "skills"
            / "ai-ppt-studio"
            / "assets"
            / "review-template.html",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        raise ProjectNotFoundError("Review HTML template is missing from the Skill")
