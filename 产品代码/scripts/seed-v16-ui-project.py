"""Create one deterministic schema 3 project for local three-surface UI checks."""

from __future__ import annotations

import json
import os
import stat
import struct
import sys
import tempfile
import zlib
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests.v16_visual_fixtures import (
    passing_visual_review,
    prepared_g1_anchor,
    rich_target_payload,
)
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.references import ArtifactReference


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _write_review_png(path: Path, *, accent: tuple[int, int, int], variant: int) -> None:
    """Write a deterministic 16:9 PNG without adding an image dependency."""

    width, height = 960, 540
    background = (244, 246, 249)
    ink = (31, 40, 55)
    rows = []
    for y in range(height):
        if y < 72:
            row = bytes(ink) * width
        elif 112 <= y < 430:
            split = 520 + (variant % 3) * 55
            row = bytes(background) * 56 + bytes(accent) * (split - 56) + bytes((226, 231, 238)) * (width - split)
        elif 462 <= y < 478:
            row = bytes(accent) * width
        else:
            row = bytes(background) * width
        rows.append(b"\x00" + row)
    payload = b"".join((
        b"\x89PNG\r\n\x1a\n",
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        _png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9)),
        _png_chunk(b"IEND", b""),
    ))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _prepare_g2_review(project_root: Path):
    visual, revision, refs = prepared_g1_anchor(project_root, slide_count=3)
    anchors = visual.kernel.artifacts.resolve(ArtifactReference.parse(refs["anchors"]))[
        "payload"
    ]
    review_anchors = deepcopy(anchors)
    for asset in review_anchors["render_assets"]:
        asset["previous_asset_ref"] = (
            f"review-assets/anchors/{asset['slide_id']}-previous.png"
        )
    anchor_ref = visual.register_anchor_set(
        "ui-seed-anchor-comparison-assets",
        revision,
        review_anchors,
    )
    refs = {**refs, "anchors": anchor_ref}
    revision += 1
    visual.register_visual_review(
        "ui-seed-g2-aesthetic-review",
        revision,
        passing_visual_review(anchor_ref, stage="G2", reviewer_kind="aesthetic"),
    )
    visual.register_visual_review(
        "ui-seed-g2-engineering-review",
        revision + 1,
        passing_visual_review(
            anchor_ref,
            stage="G2",
            reviewer_kind="engineering",
            reviewer_role="independent-ppt-engineering-reviewer",
        ),
    )
    revision += 2
    _policy_ref, policy = ReleaseTargetPolicyService(visual.kernel).current()
    for target_id in policy.required_target_ids:
        visual.register_target_render_evidence(
            f"ui-seed-g2-target-{target_id}",
            revision,
            rich_target_payload(visual, target_id, refs),
        )
        revision += 1
    state = visual.record_g2("ui-seed-g2-pass", revision)
    state = visual.publish_visual_review(
        "ui-seed-publish-visual-review",
        state.revision,
    )
    return visual, state, refs, state.revision


def _reopen_content_review_fixture(kernel, state):
    session_ref = state.artifact_heads["review/session/content-full-deck"]
    session = kernel.artifacts.resolve(ArtifactReference.parse(session_ref))["payload"]
    _withdrawn_ref, _withdrawn, state = ContentReviewBatchService(kernel).withdraw(
        command_id="ui-seed-withdraw-content-review",
        expected_revision=state.revision,
        review_session_id=session["review_session_id"],
        source_version=session["source_version"],
    )
    _decision_ref, _decision, state = ContentDecisionService(kernel).save(
        command_id="ui-seed-save-modify-page",
        expected_revision=state.revision,
        review_session_id=session["review_session_id"],
        source_version=session["source_version"],
        slide_id="S01",
        decision="modify",
        comment="收紧当前断点说明，并保留来源事实与方案建议的身份边界。",
    )
    state = kernel.commit(
        command_id="ui-seed-open-unsubmitted-review-fixture",
        expected_revision=state.revision,
        event_type="local-preview.content-review-fixture-opened",
        artifact_updates={},
        artifact_removals=(
            "content/review-batch",
            "content/review/decision/S02",
            "content/review/decision/S03",
        ),
    )
    return session, state


def _write_project_review_assets(project_root: Path, content, anchors) -> None:
    content_palette = ((35, 94, 196), (37, 129, 91), (184, 96, 32))
    for index, slide in enumerate(content["slides"]):
        for material in slide["material_views"]:
            path = project_root / material["asset_ref"]
            if not path.exists():
                _write_review_png(
                    path,
                    accent=content_palette[index % len(content_palette)],
                    variant=index,
                )
    anchor_palette = ((24, 89, 214), (196, 59, 50), (19, 114, 82))
    for index, anchor in enumerate(anchors):
        _write_review_png(
            project_root / anchor["current_asset_ref"],
            accent=anchor_palette[index],
            variant=index + 3,
        )
        _write_review_png(
            project_root / anchor["previous_asset_ref"],
            accent=tuple(max(0, channel - 38) for channel in anchor_palette[index]),
            variant=index,
        )


def _create_private_acceptance_root() -> Path:
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    created = Path(
        tempfile.mkdtemp(prefix="ai-ppt-v22-ui.", dir=temp_root)
    )
    created.chmod(0o700)
    created_stat = created.lstat()
    resolved = created.resolve(strict=True)
    owner_is_current = not hasattr(os, "getuid") or created_stat.st_uid == os.getuid()
    if (
        stat.S_ISLNK(created_stat.st_mode)
        or not stat.S_ISDIR(created_stat.st_mode)
        or resolved != created
        or resolved.parent != temp_root
        or not resolved.name.startswith("ai-ppt-v22-ui.")
        or not owner_is_current
        or stat.S_IMODE(created_stat.st_mode) & 0o077
    ):
        raise SystemExit("UI acceptance private temporary directory verification failed")
    return resolved


def main() -> int:
    if len(sys.argv) != 1:
        raise SystemExit("Usage: seed-v16-ui-project.py")
    base = _create_private_acceptance_root()
    config = RuntimeConfig.create(
        runtime_root=base,
        source_repo_root=ROOT,
        install_root=ROOT / ".ui-acceptance-install-root",
        upstream_root=ROOT.parent,
    )
    workspace_config = base / "workspace.json"
    config.save(workspace_config)
    project_root = base / "projects" / "schema3-ui-project"
    visual, state, refs, visual_publication_revision = _prepare_g2_review(project_root)
    atomic_write_json(
        project_root / "project.json",
        {
            "project_id": state.project_id,
            "project_root": str(project_root),
            "identity": "local-development-preview-asset-manifest",
        },
    )
    content_session, state = _reopen_content_review_fixture(visual.kernel, state)
    contract_ref = state.artifact_heads["visual/contract"]
    contract = visual.kernel.artifacts.resolve(
        ArtifactReference.parse(contract_ref)
    )["payload"]
    _visual_session_ref, visual_session, state = ReviewSessionService(
        visual.kernel
    ).open_or_resume(
        command_id="ui-seed-open-visual-review",
        expected_revision=state.revision,
        review_type="visual-professional",
        target_artifact_ref=contract_ref,
        source_version=str(contract.get("source_version") or contract_ref),
        source_revision=visual_publication_revision,
        open_policy="notify-only",
    )
    content_projection = visual.kernel.artifacts.resolve(
        ArtifactReference.parse(state.artifact_heads["content/reading-blueprint"])
    )["payload"]
    anchors = visual.kernel.artifacts.resolve(
        ArtifactReference.parse(state.artifact_heads["visual/anchors"])
    )["payload"]["render_assets"]
    _write_project_review_assets(project_root, content_projection, anchors)
    print(
        json.dumps(
            {
                "schema_version": state.schema_version,
                "acceptance_root": str(base),
                "project_root": str(project_root),
                "workspace_config": str(workspace_config),
                "revision": state.revision,
                "content_review_session_id": content_session["review_session_id"],
                "visual_review_session_id": visual_session["review_session_id"],
                "pptx_sha256": refs["pptx_sha256"],
                "content_review_draft": {
                    "slide_id": "S01",
                    "decision": "modify",
                    "comment": "把断点描述压缩为一屏可读，并保留材料来源与待验证边界。",
                },
                "evidence_identity": "local-development-preview-not-host-ai-presentations-powerpoint-or-user-proof",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
