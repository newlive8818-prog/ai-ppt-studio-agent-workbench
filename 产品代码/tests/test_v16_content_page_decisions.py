from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review_service import ContentReviewService
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.domains.content.contracts import REQUIRED_CONTENT_REVIEW_ROLES
from ai_ppt_studio.domains.content.review_contracts import (
    validate_page_decision,
    validate_page_decision_set,
)
from ai_ppt_studio.errors import (
    ContractValidationError,
    ContentWorkflowError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_content_acceptance import review_payload
from tests.test_v16_content_chain import build_ready_draft
from tests.v16_content_fixtures import (
    complete_slide_draft_payload,
    publish_content_review,
    publish_content_stage,
)


def artifact_ref(kind: str, marker: str = "a") -> str:
    return f"artifact://{kind}/{marker * 64}"


def valid_decision(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "page_decision_id": "page-decision-1",
        "review_batch_id": "review-batch-1",
        "project_id": "project-1",
        "review_type": "content",
        "source_version": artifact_ref("content-blueprint"),
        "slide_id": "s1",
        "slide_order": 1,
        "slide_title_snapshot": "为什么现在必须改变",
        "visible_copy_snapshot_ref": artifact_ref(
            "content-visible-copy-snapshot", "b"
        ),
        "decision": "approved",
        "comment": "",
        "saved_at": "2026-08-14T09:30:00+00:00",
        "supersedes_decision_ref": "",
    }
    payload.update(updates)
    return payload


def object_files(service: ContentService) -> tuple[str, ...]:
    root = service.kernel.artifacts.objects_root
    return tuple(
        sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
        )
    )


def event_files(service: ContentService) -> tuple[str, ...]:
    root = service.kernel.events_root
    if not root.exists():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_file()))


def resolve_payload(service: ContentService, reference: str) -> dict:
    return service.kernel.artifacts.resolve(
        ArtifactReference.parse(reference)
    )["payload"]


def register_reviews(
    service: ContentService,
    draft_ref: str,
    *,
    prefix: str,
) -> None:
    for index, role in enumerate(REQUIRED_CONTENT_REVIEW_ROLES):
        publish_content_review(
            service,
            f"{prefix}-{index}",
            review_payload(draft_ref, role),
        )


def accept_blueprint(
    service: ContentService,
    *,
    slide_count: int = 3,
) -> tuple[str, dict]:
    _revision, draft_ref, _refs = build_ready_draft(service, slide_count)
    register_reviews(service, draft_ref, prefix="initial-review")
    accepted = service.accept_content(
        "initial-accept", service.kernel.load().revision
    )
    return accepted.blueprint_ref, resolve_payload(service, accepted.blueprint_ref)


def publish_revised_blueprint(
    service: ContentService,
    *,
    slide_count: int = 2,
) -> tuple[str, dict]:
    state = service.kernel.load()
    payload = complete_slide_draft_payload(
        argument_map_ref=state.artifact_heads["content/argument-map"],
        material_ref=state.artifact_heads["materials"],
        slide_count=slide_count,
        slide_id_prefix="s",
    )
    payload["slides"][0]["title"] = "新版经营判断"
    payload["slides"][0]["visible_copy"] = [
        {
            "copy_id": "COPY-NEW-01",
            "role": "headline",
            "text": "新版全量可见文字",
        },
        {
            "copy_id": "COPY-NEW-02",
            "role": "body",
            "text": "新版证据边界与客户判断",
        },
    ]
    draft_ref = publish_content_stage(
        service,
        "revised-draft",
        "slide-draft-set",
        payload,
    )
    register_reviews(service, draft_ref, prefix="revised-review")
    accepted = service.accept_content(
        "revised-accept", service.kernel.load().revision
    )
    return accepted.blueprint_ref, resolve_payload(service, accepted.blueprint_ref)


class PageDecisionContractTests(unittest.TestCase):
    def test_four_decisions_are_exact_and_approved_discards_comment(self) -> None:
        expected = {"approved", "modify", "evidence", "merge-or-delete"}
        observed: set[str] = set()
        for decision in sorted(expected):
            with self.subTest(decision=decision):
                comment = "  保留完整意见  " if decision != "approved" else "应被丢弃"
                normalized = validate_page_decision(
                    valid_decision(decision=decision, comment=comment)
                )
                observed.add(normalized["decision"])
                self.assertEqual(
                    normalized["comment"],
                    "" if decision == "approved" else "保留完整意见",
                )
                self.assertTrue(normalized["completed"])
                self.assertEqual(
                    tuple(normalized),
                    (
                        "page_decision_id",
                        "review_batch_id",
                        "project_id",
                        "review_type",
                        "source_version",
                        "slide_id",
                        "slide_order",
                        "slide_title_snapshot",
                        "visible_copy_snapshot_ref",
                        "decision",
                        "comment",
                        "completed",
                        "saved_at",
                        "supersedes_decision_ref",
                    ),
                )
        self.assertEqual(observed, expected)
        self.assertEqual(
            validate_page_decision(
                valid_decision(decision="approved", comment=None)
            )["comment"],
            "",
        )

        for invalid in ("", "delete", "merge_or_delete", "approved|modify"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ContractValidationError):
                    validate_page_decision(valid_decision(decision=invalid))

    def test_required_comments_trim_whitespace_and_enforce_unicode_limit(self) -> None:
        for decision in ("modify", "evidence", "merge-or-delete"):
            with self.subTest(decision=decision):
                with self.assertRaises(ContentWorkflowError) as caught:
                    validate_page_decision(
                        valid_decision(decision=decision, comment=" \n\t ")
                    )
                self.assertEqual(
                    caught.exception.code, "CONTENT_PAGE_COMMENT_REQUIRED"
                )
                self.assertIn(
                    "CONTENT_PAGE_COMMENT_REQUIRED", str(caught.exception)
                )

        accepted = validate_page_decision(
            valid_decision(decision="modify", comment="修" * 1200)
        )
        self.assertEqual(len(accepted["comment"]), 1200)
        with self.assertRaisesRegex(ContractValidationError, "1200"):
            validate_page_decision(
                valid_decision(decision="modify", comment="🧩" * 1201)
            )

    def test_identity_reference_timestamp_and_unknown_fields_fail_closed(self) -> None:
        invalid_payloads = (
            valid_decision(project_id=""),
            valid_decision(slide_order=True),
            valid_decision(slide_order=0),
            valid_decision(source_version=artifact_ref("content-acceptance")),
            valid_decision(
                visible_copy_snapshot_ref=artifact_ref("content-blueprint")
            ),
            valid_decision(
                supersedes_decision_ref=artifact_ref(
                    "content-visible-copy-snapshot"
                )
            ),
            valid_decision(saved_at="2026-08-14T09:30:00"),
            {**valid_decision(), "ambiguous_extra": True},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ContractValidationError):
                    validate_page_decision(payload)

    def test_decision_set_accepts_draft_or_frozen_and_rejects_duplicates(self) -> None:
        decision_ref = artifact_ref("content-page-decision", "c")
        payload = {
            "decision_set_id": "decision-set-1",
            "review_batch_id": "review-batch-1",
            "project_id": "project-1",
            "review_type": "content",
            "source_version": artifact_ref("content-blueprint"),
            "expected_slide_count": 2,
            "status": "draft",
            "decision_refs": [
                {
                    "slide_id": "s1",
                    "slide_order": 1,
                    "decision_ref": decision_ref,
                }
            ],
            "updated_at": "2026-08-14T09:30:00+00:00",
        }
        self.assertEqual(validate_page_decision_set(payload)["status"], "draft")
        self.assertEqual(
            validate_page_decision_set({**payload, "status": "frozen"})["status"],
            "frozen",
        )
        duplicate = copy.deepcopy(payload)
        duplicate["decision_refs"].append(dict(duplicate["decision_refs"][0]))
        with self.assertRaises(ContractValidationError):
            validate_page_decision_set(duplicate)


class ContentReviewServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="decision-project"
        )
        self.source_version, self.blueprint = accept_blueprint(
            self.content, slide_count=3
        )
        self.review = ContentReviewService(self.content.kernel)
        self.batch_id = "review-batch-current"

    def save(
        self,
        *,
        command_id: str,
        slide_id: str,
        decision: str,
        comment: str = "",
        expected_revision: int | None = None,
        source_version: str | None = None,
        review_batch_id: str | None = None,
    ):
        return self.review.save_page_decision(
            command_id=command_id,
            expected_revision=(
                self.content.kernel.load().revision
                if expected_revision is None
                else expected_revision
            ),
            source_version=source_version or self.source_version,
            review_batch_id=review_batch_id or self.batch_id,
            slide_id=slide_id,
            decision=decision,
            comment=comment,
        )

    def current_set(self) -> tuple[str, dict]:
        reference = self.content.kernel.load().artifact_heads[
            "content/page-decisions"
        ]
        return reference, resolve_payload(self.content, reference)

    def decision_for(self, slide_id: str) -> tuple[str, dict]:
        _set_ref, decision_set = self.current_set()
        row = next(
            item
            for item in decision_set["decision_refs"]
            if item["slide_id"] == slide_id
        )
        return row["decision_ref"], resolve_payload(
            self.content, row["decision_ref"]
        )

    def test_atomic_save_snapshots_full_authoritative_slide_and_has_no_side_effects(self) -> None:
        before = self.content.kernel.load()
        before_heads = dict(before.artifact_heads)
        before_events = event_files(self.content)
        target = self.blueprint["slides"][0]

        page, progress, after = self.save(
            command_id="save-s1",
            slide_id=target["slide_id"],
            decision="modify",
            comment="  保留客户判断，补充证据边界。  ",
        )

        changed_heads = {
            key
            for key in set(before_heads) | set(after.artifact_heads)
            if before_heads.get(key) != after.artifact_heads.get(key)
        }
        self.assertEqual(changed_heads, {"content/page-decisions"})
        self.assertEqual(
            after.artifact_heads["content/blueprint"], self.source_version
        )
        for protected in (
            "content/acceptance",
            "feedback/governance",
            "content/change-set",
        ):
            self.assertEqual(
                after.artifact_heads.get(protected), before_heads.get(protected)
            )
        self.assertEqual(after.gate_status["G0"], "user-reviewable")
        self.assertNotIn("follow_up_message", page)
        self.assertNotIn("follow_up_message", progress)
        self.assertEqual(page["decision"], "modify")
        self.assertEqual(page["comment"], "保留客户判断，补充证据边界。")
        self.assertTrue(page["completed"])

        decision_ref, decision = self.decision_for(target["slide_id"])
        self.assertEqual(page["page_decision_ref"], decision_ref)
        self.assertEqual(decision["slide_order"], target["order"])
        self.assertEqual(decision["slide_title_snapshot"], target["title"])
        snapshot = resolve_payload(
            self.content, decision["visible_copy_snapshot_ref"]
        )
        self.assertEqual(snapshot["visible_copy"], target["visible_copy"])
        self.assertEqual(snapshot["slide_order"], target["order"])
        self.assertEqual(snapshot["slide_title_snapshot"], target["title"])
        self.assertEqual(event_files(self.content)[:-1], before_events)
        event = json.loads(
            (
                self.content.kernel.events_root
                / event_files(self.content)[-1]
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(event["event_type"], "content.page-decision-saved")
        self.assertEqual(event["artifact_heads"], after.artifact_heads)

    def test_replacement_supersedes_only_same_slide_and_preserves_history(self) -> None:
        first_page, _progress, _state = self.save(
            command_id="first-s1",
            slide_id="s1",
            decision="modify",
            comment="第一版意见",
        )
        second_page, _progress, _state = self.save(
            command_id="save-s2",
            slide_id="s2",
            decision="evidence",
            comment="需要补充来源证据",
        )
        first_ref = first_page["page_decision_ref"]
        second_ref = second_page["page_decision_ref"]

        replacement, progress, _state = self.save(
            command_id="replace-s1",
            slide_id="s1",
            decision="approved",
            comment="这段应被清空",
        )
        replacement_ref = replacement["page_decision_ref"]
        self.assertNotEqual(replacement_ref, first_ref)
        self.assertEqual(replacement["supersedes_decision_ref"], first_ref)
        self.assertEqual(replacement["comment"], "")
        _set_ref, decision_set = self.current_set()
        self.assertEqual(
            decision_set["decision_refs"],
            [
                {
                    "slide_id": "s1",
                    "slide_order": 1,
                    "decision_ref": replacement_ref,
                },
                {
                    "slide_id": "s2",
                    "slide_order": 2,
                    "decision_ref": second_ref,
                },
            ],
        )
        self.assertEqual(resolve_payload(self.content, first_ref)["comment"], "第一版意见")
        self.assertEqual(progress["completed"], 2)
        self.assertEqual(progress["remaining"], 1)
        self.assertEqual(progress["next_incomplete_slide_id"], "s3")
        self.assertEqual(
            progress["counts"],
            {
                "approved": 1,
                "modify": 0,
                "evidence": 1,
                "merge_or_delete": 0,
            },
        )

    def test_progress_uses_all_authoritative_slides_and_completes_in_order(self) -> None:
        page, progress, _state = self.save(
            command_id="progress-s2",
            slide_id="s2",
            decision="merge-or-delete",
            comment="合并到第三页，保留案例证据",
        )
        self.assertEqual(page["slide_id"], "s2")
        self.assertEqual(
            progress,
            {
                "total": 3,
                "completed": 1,
                "remaining": 2,
                "saved_comment_count": 1,
                "next_incomplete_slide_id": "s1",
                "counts": {
                    "approved": 0,
                    "modify": 0,
                    "evidence": 0,
                    "merge_or_delete": 1,
                },
            },
        )
        self.save(
            command_id="progress-s1",
            slide_id="s1",
            decision="approved",
        )
        _page, complete, _state = self.save(
            command_id="progress-s3",
            slide_id="s3",
            decision="modify",
            comment="收紧结论",
        )
        self.assertEqual(complete["completed"], 3)
        self.assertEqual(complete["remaining"], 0)
        self.assertEqual(complete["saved_comment_count"], 2)
        self.assertEqual(complete["next_incomplete_slide_id"], "")
        self.assertEqual(
            complete["counts"],
            {
                "approved": 1,
                "modify": 1,
                "evidence": 0,
                "merge_or_delete": 1,
            },
        )

    def test_stale_source_wrong_kind_unknown_slide_and_revision_conflict_are_zero_write(self) -> None:
        cases = (
            (
                "stale-source",
                lambda: self.save(
                    command_id="stale-source",
                    slide_id="s1",
                    decision="approved",
                    source_version=artifact_ref("content-blueprint", "f"),
                ),
                ContentWorkflowError,
            ),
            (
                "wrong-kind-source",
                lambda: self.save(
                    command_id="wrong-kind-source",
                    slide_id="s1",
                    decision="approved",
                    source_version=artifact_ref("content-acceptance", "e"),
                ),
                ContentWorkflowError,
            ),
            (
                "unknown-slide",
                lambda: self.save(
                    command_id="unknown-slide",
                    slide_id="missing",
                    decision="approved",
                ),
                ContentWorkflowError,
            ),
            (
                "revision-conflict",
                lambda: self.save(
                    command_id="revision-conflict",
                    slide_id="s1",
                    decision="approved",
                    expected_revision=self.content.kernel.load().revision - 1,
                ),
                RevisionConflictError,
            ),
        )
        for label, operation, exception_type in cases:
            with self.subTest(label=label):
                before = self.content.kernel.load()
                objects = object_files(self.content)
                events = event_files(self.content)
                with self.assertRaises(exception_type) as caught:
                    operation()
                if isinstance(caught.exception, ContentWorkflowError):
                    self.assertEqual(
                        caught.exception.code, "CONTENT_REVIEW_CONFLICT"
                    )
                self.assertEqual(self.content.kernel.load(), before)
                self.assertEqual(object_files(self.content), objects)
                self.assertEqual(event_files(self.content), events)

    def test_same_batch_is_required_until_source_changes(self) -> None:
        self.save(
            command_id="batch-a",
            slide_id="s1",
            decision="approved",
        )
        before = self.content.kernel.load()
        objects = object_files(self.content)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save(
                command_id="batch-b",
                slide_id="s2",
                decision="approved",
                review_batch_id="different-batch",
            )
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), objects)

    def test_frozen_decision_set_rejects_changes_without_writes(self) -> None:
        self.save(
            command_id="before-freeze",
            slide_id="s1",
            decision="approved",
        )
        _set_ref, decision_set = self.current_set()
        frozen = validate_page_decision_set({**decision_set, "status": "frozen"})
        state = self.content.kernel.commit(
            command_id="test-install-frozen-set",
            expected_revision=self.content.kernel.load().revision,
            event_type="test.content-page-decision-set-frozen",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    frozen,
                )
            },
        )
        objects = object_files(self.content)
        events = event_files(self.content)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save(
                command_id="reject-frozen",
                slide_id="s2",
                decision="approved",
                expected_revision=state.revision,
            )
        self.assertEqual(
            caught.exception.code, "CONTENT_PAGE_DECISION_FROZEN"
        )
        self.assertEqual(self.content.kernel.load(), state)
        self.assertEqual(object_files(self.content), objects)
        self.assertEqual(event_files(self.content), events)

    def test_forged_snapshot_that_differs_from_source_fails_closed(self) -> None:
        page, _progress, _state = self.save(
            command_id="authentic-snapshot",
            slide_id="s1",
            decision="approved",
        )
        authentic = resolve_payload(
            self.content, page["page_decision_ref"]
        )
        forged_snapshot = {
            **resolve_payload(
                self.content, authentic["visible_copy_snapshot_ref"]
            ),
            "visible_copy": [
                {
                    "copy_id": "FORGED",
                    "role": "headline",
                    "text": "不属于该蓝图的文字",
                }
            ],
        }
        forged_snapshot_ref = str(
            self.content.kernel.artifacts.put(
                "content-visible-copy-snapshot", forged_snapshot
            )
        )
        forged_decision = validate_page_decision(
            {
                **authentic,
                "page_decision_id": "forged-decision",
                "visible_copy_snapshot_ref": forged_snapshot_ref,
            }
        )
        forged_decision_ref = str(
            self.content.kernel.artifacts.put(
                "content-page-decision", forged_decision
            )
        )
        _set_ref, decision_set = self.current_set()
        forged_set = validate_page_decision_set(
            {
                **decision_set,
                "decision_refs": [
                    {
                        **decision_set["decision_refs"][0],
                        "decision_ref": forged_decision_ref,
                    }
                ],
            }
        )
        self.content.kernel.commit(
            command_id="test-install-forged-snapshot",
            expected_revision=self.content.kernel.load().revision,
            event_type="test.install-forged-page-snapshot",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    forged_set,
                )
            },
        )
        before = self.content.kernel.load()
        objects = object_files(self.content)
        events = event_files(self.content)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save(
                command_id="reject-forged-snapshot",
                slide_id="s2",
                decision="approved",
            )
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), objects)
        self.assertEqual(event_files(self.content), events)

    def test_command_replay_is_exact_and_semantic_collision_fails_closed(self) -> None:
        revision = self.content.kernel.load().revision
        first = self.save(
            command_id="idempotent-save",
            slide_id="s1",
            decision="modify",
            comment="保持结论，收紧证据",
            expected_revision=revision,
        )
        after_first = self.content.kernel.load()
        objects = object_files(self.content)
        events = event_files(self.content)
        replay = self.save(
            command_id="idempotent-save",
            slide_id="s1",
            decision="modify",
            comment="保持结论，收紧证据",
            expected_revision=revision,
        )
        self.assertEqual(replay[0], first[0])
        self.assertEqual(replay[1], first[1])
        self.assertEqual(replay[2], after_first)
        self.assertEqual(object_files(self.content), objects)
        self.assertEqual(event_files(self.content), events)

        with self.assertRaises(ContractValidationError):
            self.save(
                command_id="idempotent-save",
                slide_id="s1",
                decision="modify",
                comment="不同语义的意见",
                expected_revision=revision,
            )
        self.assertEqual(self.content.kernel.load(), after_first)
        self.assertEqual(object_files(self.content), objects)
        self.assertEqual(event_files(self.content), events)

    def test_new_blueprint_starts_a_new_source_bound_set_and_old_snapshot_is_immutable(self) -> None:
        old_page, _progress, _state = self.save(
            command_id="old-source-decision",
            slide_id="s1",
            decision="modify",
            comment="旧版意见",
        )
        old_ref = old_page["page_decision_ref"]
        old_decision = copy.deepcopy(resolve_payload(self.content, old_ref))
        old_snapshot = copy.deepcopy(
            resolve_payload(
                self.content, old_decision["visible_copy_snapshot_ref"]
            )
        )

        new_source, new_blueprint = publish_revised_blueprint(
            self.content, slide_count=2
        )
        self.assertNotEqual(new_source, self.source_version)
        page, progress, _state = self.save(
            command_id="new-source-decision",
            slide_id="s1",
            decision="approved",
            source_version=new_source,
            review_batch_id="review-batch-new-source",
        )
        _set_ref, decision_set = self.current_set()
        self.assertEqual(decision_set["source_version"], new_source)
        self.assertEqual(
            decision_set["review_batch_id"], "review-batch-new-source"
        )
        self.assertEqual(len(decision_set["decision_refs"]), 1)
        self.assertNotEqual(page["page_decision_ref"], old_ref)
        self.assertEqual(progress["total"], 2)
        self.assertEqual(progress["completed"], 1)
        self.assertEqual(progress["next_incomplete_slide_id"], "s2")
        new_decision = resolve_payload(
            self.content, page["page_decision_ref"]
        )
        new_snapshot = resolve_payload(
            self.content, new_decision["visible_copy_snapshot_ref"]
        )
        self.assertEqual(
            new_snapshot["visible_copy"],
            new_blueprint["slides"][0]["visible_copy"],
        )
        self.assertEqual(resolve_payload(self.content, old_ref), old_decision)
        self.assertEqual(
            resolve_payload(
                self.content, old_decision["visible_copy_snapshot_ref"]
            ),
            old_snapshot,
        )


if __name__ == "__main__":
    unittest.main()
