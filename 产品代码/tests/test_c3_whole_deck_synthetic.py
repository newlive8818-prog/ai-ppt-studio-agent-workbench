"""C3 synthetic whole-deck regression (12 pages).

Synthetic data only. This module proves deck-level coverage, ordering,
per-page target binding and batch status aggregation at whole-deck scale. It is
never a real presales acceptance, never substitutes for C2's accepted three
pages, and never closes G3, G4, delivery or a user visual acceptance.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
from ai_ppt_studio.domains.visual.image_led import validate_target_binding
from ai_ppt_studio.errors import ArtifactReferenceError, ContentWorkflowError, ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_image_led_contracts import binding as binding_fixture
from tests.test_v16_content_page_decisions import accepted_v22_review, approve_v22
from tests.test_v22_content_contracts import blueprint as single_page_blueprint


PAGES = 12
PAGE_TASKS = ("背景与现状", "问题诊断", "方案建议", "价值与收益", "交付路径")


def synthetic_whole_deck(pages: int = PAGES) -> dict:
    """Build a synthetic whole-deck blueprint that covers four or more page tasks."""
    deck = single_page_blueprint()
    template = deck["slides"][0]
    slides = []
    for order in range(1, pages + 1):
        slide = deepcopy(template)
        task_index = (order - 1) % len(PAGE_TASKS)
        slide["slide_id"] = f"S{order:02d}"
        slide["order"] = order
        slide["section_id"] = f"section-{task_index + 1}"
        slide["page_task"] = PAGE_TASKS[task_index]
        slide["neutral_title"] = f"第{order:02d}页 当前已知与待验证事项"
        slide["reading_question"] = f"第{order:02d}页 现在能确认什么，仍需验证什么"
        slides.append(slide)
    deck["slides"] = slides
    deck["section_flow"] = [f"section-{index + 1}" for index in range(len(PAGE_TASKS))]
    return deck


class SyntheticWholeDeckStructureTests(unittest.TestCase):
    def test_twelve_page_deck_covers_every_page_once_and_in_order(self) -> None:
        validated = validate_reading_deck_blueprint(synthetic_whole_deck())
        slides = validated["slides"]
        self.assertEqual(len(slides), PAGES)
        self.assertEqual([slide["order"] for slide in slides], list(range(1, PAGES + 1)))
        self.assertEqual(len({slide["slide_id"] for slide in slides}), PAGES)
        self.assertGreaterEqual(len({slide["page_task"] for slide in slides}), 4)

    def test_missing_page_is_rejected(self) -> None:
        deck = synthetic_whole_deck()
        deck["slides"] = [slide for slide in deck["slides"] if slide["order"] != 7]
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(deck)

    def test_duplicate_order_is_rejected(self) -> None:
        deck = synthetic_whole_deck()
        deck["slides"][PAGES - 1]["order"] = PAGES - 1
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(deck)

    def test_duplicate_slide_id_is_rejected(self) -> None:
        deck = synthetic_whole_deck()
        deck["slides"][4]["slide_id"] = deck["slides"][3]["slide_id"]
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(deck)


class SyntheticWholeDeckBindingTests(unittest.TestCase):
    def test_each_page_binding_matches_only_its_own_page(self) -> None:
        for order in range(1, PAGES + 1):
            slide_id = f"S{order:02d}"
            target = binding_fixture(slide_id=slide_id, order=order)
            self.assertEqual(
                validate_target_binding(
                    target,
                    expected_project_id="project-a",
                    expected_slide_id=slide_id,
                    expected_page_order=order,
                ),
                target,
            )
            with self.subTest(order=order, neighbour="slide-id"), self.assertRaises(
                ContractValidationError
            ):
                validate_target_binding(
                    target,
                    expected_project_id="project-a",
                    expected_slide_id=f"S{(order % PAGES) + 1:02d}",
                    expected_page_order=order,
                )
            with self.subTest(order=order, neighbour="page-order"), self.assertRaises(
                ContractValidationError
            ):
                validate_target_binding(
                    target,
                    expected_project_id="project-a",
                    expected_slide_id=slide_id,
                    expected_page_order=(order % PAGES) + 1,
                )


class SyntheticWholeDeckBatchStatusTests(unittest.TestCase):
    def test_batch_status_covers_every_page_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="c3-synthetic")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(
                kernel, slide_count=PAGES
            )
            for order in range(1, PAGES):
                approve_v22(kernel, session, f"S{order:02d}")

            batches = ContentReviewBatchService(kernel)
            with self.assertRaises(GateBlockedError):
                batches.submit(
                    command_id="c3-submit-with-eleven-pages",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version=session["source_version"],
                )

            approve_v22(kernel, session, f"S{PAGES:02d}")
            submit_revision = kernel.load().revision
            reference, batch, _state = batches.submit(
                command_id="c3-submit-complete-deck",
                expected_revision=submit_revision,
                review_session_id=session["review_session_id"],
                source_version=session["source_version"],
            )
            # Model a lost acknowledgement: retry the same command and old revision.
            from tests.test_image2_input_boundary import tree_snapshot
            before = tree_snapshot(Path(folder))
            replay_ref, replay_batch, _ = batches.submit(
                command_id="c3-submit-complete-deck",
                expected_revision=submit_revision,
                review_session_id=session["review_session_id"],
                source_version=session["source_version"],
            )
            self.assertEqual((replay_ref, replay_batch), (reference, batch))
            self.assertEqual(tree_snapshot(Path(folder)), before)
            with self.assertRaises(ContentWorkflowError):
                batches.submit(command_id="c3-duplicate-review-submit",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version=session["source_version"])
            self.assertEqual(tree_snapshot(Path(folder)), before)
            self.assertEqual(batch["status"], "submitted")
            self.assertEqual(len(batch["slide_ids"]), PAGES)
            self.assertEqual(len(set(batch["slide_ids"])), PAGES)
            self.assertEqual(batch["slide_ids"], [f"S{order:02d}" for order in range(1, PAGES + 1)])
            self.assertEqual(len(batch["decision_refs"]), PAGES)
            self.assertEqual(sum(batch["counts"].values()), PAGES)
            self.assertEqual(batch["counts"]["approved"], PAGES)

class SyntheticWholeDeckFinalizationTests(unittest.TestCase):
    def test_six_page_selection_covers_current_blueprint_and_trusted_decision(self) -> None:
        from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
        from tests.host_confirmation_fixtures import gate_confirmation_kwargs
        from tests.test_image_led_requests import input_fixture
        from tests.test_image_led_selection import make_candidate, review_candidate
        from tests.test_image2_input_boundary import tree_snapshot

        with tempfile.TemporaryDirectory() as folder:
            service, _policy, packs = input_fixture(Path(folder), slide_count=6)
            rows = []
            for order, pack_ref in enumerate(packs, 1):
                candidate_ref, _ = make_candidate(service, pack_ref, f"c3-{order}")
                review_ref = review_candidate(service, candidate_ref, f"c3-{order}")
                rows.append({"candidate_ref": candidate_ref, "source_review_ref": review_ref,
                             "accepted_deviations": []})

            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.commit_artifact("incomplete-six-page-choice", service.kernel.load().revision,
                    {"artifact_type": "image-led-selection-proposal", "project_id": service.kernel.project_id,
                     "candidates": rows[:-1]})
            self.assertEqual(tree_snapshot(Path(folder)), before)

            proposal_ref = service.commit_artifact("complete-six-page-choice", service.kernel.load().revision,
                {"artifact_type": "image-led-selection-proposal", "project_id": service.kernel.project_id,
                 "candidates": rows})
            context = service.confirmation_context(proposal_ref)
            selection_ref = service.confirm("confirm-six-page-choice", service.kernel.load().revision,
                target_ref=proposal_ref, choice="approved", **gate_confirmation_kwargs(context,
                    identity_ref="test-host-confirmation://c3-six-page-selection"))
            selection = ImageLedSelectionService(service.kernel).current_selection(selection_ref)
            self.assertEqual([s["target_binding"]["page_order"] for s in selection["slides"]],
                             list(range(1, 7)))
            self.assertEqual([s["target_binding"]["slide_id"] for s in selection["slides"]],
                             [f"S{n:02d}" for n in range(1, 7)])
            self.assertEqual(service.kernel.confirmation_artifact_binding(
                "test-host-confirmation://c3-six-page-selection"), selection["confirmation_ref"])
            self.assertEqual(service.kernel.load().gate_status["G3"], "locked")


    def test_single_page_redesign_keeps_other_five_reviewed_candidates(self) -> None:
        from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
        from tests.host_confirmation_fixtures import gate_confirmation_kwargs
        from tests.test_image_led_requests import input_fixture
        from tests.test_image_led_selection import make_candidate, review_candidate
        from tests.test_image2_input_boundary import tree_snapshot

        with tempfile.TemporaryDirectory(prefix="c3-six-page-redesign-") as folder:
            root = Path(folder)
            service, _policy, packs = input_fixture(root, slide_count=6)
            rows = []
            for order, pack_ref in enumerate(packs, 1):
                candidate_ref, _ = make_candidate(service, pack_ref, f"initial-{order}")
                review_ref = review_candidate(service, candidate_ref, f"initial-{order}")
                rows.append({"candidate_ref": candidate_ref, "source_review_ref": review_ref,
                             "accepted_deviations": []})
            proposal = service.commit_artifact("initial-six-page-proposal", service.kernel.load().revision,
                {"artifact_type": "image-led-selection-proposal", "project_id": service.kernel.project_id,
                 "candidates": rows})
            context = service.confirmation_context(proposal)
            selection_ref = service.confirm("initial-six-page-decision", service.kernel.load().revision,
                target_ref=proposal, choice="approved", **gate_confirmation_kwargs(context,
                    identity_ref="test-host-confirmation://c3-initial-design"))
            old = ImageLedSelectionService(service.kernel).current_selection(selection_ref)

            changed_candidate, _ = make_candidate(service, packs[2], "revised-3")
            self.assertNotEqual(changed_candidate, rows[2]["candidate_ref"])
            heads = service.kernel.load().artifact_heads
            self.assertNotIn("visual/image-led/selection", heads)
            self.assertNotIn("visual/image-led/selection-proposal", heads)
            for order, row in enumerate(rows):
                if order == 2:
                    continue
                self.assertEqual(heads[f"visual/image-led/candidate/S{order + 1:02d}"],
                                 row["candidate_ref"])
                self.assertIn(row["source_review_ref"], heads.values())
            with self.assertRaises(ArtifactReferenceError):
                ImageLedSelectionService(service.kernel).current_selection(selection_ref)

            revised_review = review_candidate(service, changed_candidate, "revised-3")
            revised_rows = deepcopy(rows)
            revised_rows[2] = {"candidate_ref": changed_candidate,
                               "source_review_ref": revised_review, "accepted_deviations": []}
            before = tree_snapshot(root)
            with self.assertRaises(ArtifactReferenceError):
                service.commit_artifact("stale-six-page-proposal", service.kernel.load().revision,
                    {"artifact_type": "image-led-selection-proposal", "project_id": service.kernel.project_id,
                     "candidates": rows})
            self.assertEqual(tree_snapshot(root), before)

            proposal = service.commit_artifact("revised-six-page-proposal", service.kernel.load().revision,
                {"artifact_type": "image-led-selection-proposal", "project_id": service.kernel.project_id,
                 "candidates": revised_rows})
            context = service.confirmation_context(proposal)
            selection_ref = service.confirm("revised-six-page-decision", service.kernel.load().revision,
                target_ref=proposal, choice="approved", **gate_confirmation_kwargs(context,
                    identity_ref="test-host-confirmation://c3-revised-design"))
            current = ImageLedSelectionService(service.kernel).current_selection(selection_ref)
            self.assertEqual(len(current["slides"]), 6)
            for index in (0, 1, 3, 4, 5):
                self.assertEqual(current["slides"][index]["target_binding"],
                                 old["slides"][index]["target_binding"])
            self.assertNotEqual(current["slides"][2]["target_binding"]["candidate_ref"],
                                old["slides"][2]["target_binding"]["candidate_ref"])
            self.assertEqual(service.kernel.load().gate_status["G3"], "locked")


    def test_six_page_content_edit_reopens_g0_and_rejects_old_visual_selection(self) -> None:
        from unittest.mock import patch
        from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
        from ai_ppt_studio.application.presales_content_service import PresalesContentService
        from tests.test_image_led_selection import selection_fixture
        from tests.test_v22_content_repair_loop import build_content
        from tests.test_image2_input_boundary import tree_snapshot
        from ai_ppt_studio.kernel.references import ArtifactReference

        with tempfile.TemporaryDirectory(prefix="c3-six-page-content-change-") as folder:
            root = Path(folder)
            visual, old_selection_ref = selection_fixture(root, slide_count=6)
            kernel = visual.kernel
            old_selection = visual.current_selection(old_selection_ref)
            old_blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            old_pack = old_selection["slides"][2]["target_binding"]["candidate_ref"]
            original = PresalesContentService.build_reading_deck_blueprint

            def build_changed_page(content_service, command_id, revision, payload):
                revised = deepcopy(payload)
                revised["slides"][2]["visible_copy_blocks"][0]["text"] = (
                    "第 3 页经重新核对的项目事实，需重新审核")
                return original(content_service, command_id, revision, revised)

            with patch.object(PresalesContentService, "build_reading_deck_blueprint",
                              new=build_changed_page):
                new_blueprint_ref = build_content(kernel, source_version="c3-content-revised",
                                                  slide_count=6)
            self.assertNotEqual(new_blueprint_ref, old_blueprint_ref)
            new_blueprint = kernel.artifacts.resolve(ArtifactReference.parse(new_blueprint_ref))["payload"]
            self.assertEqual(new_blueprint["slides"][2]["visible_copy_blocks"][0]["text"],
                             "第 3 页经重新核对的项目事实，需重新审核")
            state = kernel.load()
            self.assertEqual(state.gate_status["G0"], "open")
            self.assertEqual([state.gate_status[g] for g in ("G1", "G2", "G3", "G4")],
                             ["locked"] * 4)
            for slot in ("gate/G0/confirmation", "visual/image-led/selection",
                         "visual/image-led/input-policy", "visual/contracts", "visual/compilation-plan"):
                self.assertNotIn(slot, state.artifact_heads)
            self.assertEqual(len(new_blueprint["slides"]), 6)
            # Old immutable history remains readable, but can no longer authorize an output.
            self.assertEqual(kernel.artifacts.resolve(ArtifactReference.parse(old_selection_ref))
                             ["payload"], old_selection)
            before = tree_snapshot(root)
            with self.assertRaises(ArtifactReferenceError):
                ImageLedSelectionService(kernel).current_selection(old_selection_ref)
            with self.assertRaises(ArtifactReferenceError):
                visual.current_candidate(old_pack)
            self.assertEqual(tree_snapshot(root), before)


    def test_six_page_common_style_change_invalidates_all_old_designs(self) -> None:
        from ai_ppt_studio.application.image_led_service import ImageLedService
        from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
        from ai_ppt_studio.kernel.references import ArtifactReference
        from tests.test_image_led_runtime import g1_fixture
        from tests.test_image2_input_boundary import tree_snapshot

        with tempfile.TemporaryDirectory(prefix="c3-six-page-style-change-") as folder:
            root = Path(folder)
            kernel, old_contract_ref = g1_fixture(root, slide_count=6)
            original_heads = dict(kernel.load().artifact_heads)
            policy_ref = original_heads["visual/image-led/input-policy"]
            policy = deepcopy(kernel.artifacts.resolve(ArtifactReference.parse(policy_ref))["payload"])
            old_packs = {slot: ref for slot, ref in original_heads.items()
                         if slot.startswith("visual/image-led/pack/")}
            self.assertEqual(len(old_packs), 6)
            old_selection_ref = original_heads["visual/image-led/selection"]
            grant_ref = original_heads["visual/image-led/authorization"]
            consumption_ref = original_heads["kernel/confirmation-consumptions"]

            policy["common_rules"]["typography_tokens"]["title"] = "PingFang SC"
            service = ImageLedService(kernel)
            new_policy_ref = service.commit_artifact("c3-change-common-style",
                                                     kernel.load().revision, policy)
            self.assertNotEqual(new_policy_ref, policy_ref)
            heads = kernel.load().artifact_heads
            self.assertEqual(kernel.load().gate_status["G0"], "passed")
            self.assertEqual(kernel.load().gate_status["G1"], "open")
            self.assertEqual(kernel.load().gate_status["G2"], "locked")
            self.assertEqual(heads["visual/image-led/authorization"], grant_ref)
            self.assertEqual(heads["kernel/confirmation-consumptions"], consumption_ref)
            for slot in (*old_packs, "visual/image-led/selection",
                         "visual/contracts", "visual/compilation-plan"):
                self.assertNotIn(slot, heads)
            self.assertEqual(kernel.artifacts.resolve(ArtifactReference.parse(old_contract_ref))["kind"],
                             "visual-contract-set")
            before = tree_snapshot(root)
            with self.assertRaises(ArtifactReferenceError):
                service.compile_request(next(iter(old_packs.values())))
            with self.assertRaises(ArtifactReferenceError):
                ImageLedSelectionService(kernel).current_selection(old_selection_ref)
            self.assertEqual(tree_snapshot(root), before)


    def test_six_page_generation_unknown_preserves_completed_pages_without_resend(self) -> None:
        from ai_ppt_studio.application.project_service import ProjectCommandService
        from tests.test_image_led_requests import input_fixture
        from tests.test_image_led_selection import make_candidate, review_candidate
        from tests.test_image2_input_boundary import tree_snapshot
        from ai_ppt_studio.kernel.references import ArtifactReference

        class UnknownTransport:
            def __init__(self):
                self.calls = 0
            def generate(self, *, request_id, payload):
                self.calls += 1
                raise TimeoutError("synthetic upstream result unknown")

        with tempfile.TemporaryDirectory(prefix="c3-six-page-unknown-") as folder:
            root = Path(folder)
            service, _policy, packs = input_fixture(root, slide_count=6)
            completed = []
            for order in (1, 2):
                candidate_ref, _ = make_candidate(service, packs[order - 1],
                                                  f"before-unknown-{order}")
                review_ref = review_candidate(service, candidate_ref,
                                              f"before-unknown-{order}")
                completed.append((candidate_ref, review_ref))
            commands = ProjectCommandService(service.kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "c3-unknown-third-page", service.kernel.load().revision,
                action_type="generate-slide-images", target_refs=[packs[2]], instructions="")
            transport = UnknownTransport()
            response_ref = service.execute_generation(task["task_id"], transport=transport)
            response = service.kernel.artifacts.resolve(ArtifactReference.parse(response_ref))["payload"]
            self.assertEqual(response["status"], "unknown")
            self.assertEqual(response["pack_ref"], packs[2])
            self.assertEqual(transport.calls, 1)
            receipt_ref, historical, usability = service.generation_receipt(task)
            self.assertEqual(receipt_ref, response_ref)
            self.assertEqual(historical, response)
            self.assertFalse(usability["candidate_eligible"])
            heads = service.kernel.load().artifact_heads
            self.assertEqual(heads["project/image-led/request/" + task["task_id"]],
                             response_ref)
            for order, (candidate_ref, review_ref) in enumerate(completed, 1):
                self.assertEqual(heads[f"visual/image-led/candidate/S{order:02d}"],
                                 candidate_ref)
                self.assertIn(review_ref, heads.values())
            before = tree_snapshot(root)
            with self.assertRaises(ContractValidationError):
                service.execute_generation(task["task_id"], transport=transport)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(tree_snapshot(root), before)
            # A later page can proceed without rewriting the uncertain page.
            fourth, _ = make_candidate(service, packs[3], "after-unknown-fourth")
            self.assertIn(fourth, service.kernel.load().artifact_heads.values())
            self.assertEqual(service.kernel.load().artifact_heads[
                "project/image-led/request/" + task["task_id"]], response_ref)
            self.assertEqual(transport.calls, 1)
            self.assertNotIn("visual/image-led/selection",
                             service.kernel.load().artifact_heads)


class SyntheticSixPageAnchorTests(unittest.TestCase):
    def test_six_page_export_failure_keeps_previous_valid_pptx(self) -> None:
        from tests.test_image_led_results import (
            CODE_ROOT, MODULES, NODE, PYTHON, render_runtime_fixture,
        )
        from tests.test_image2_input_boundary import tree_snapshot

        if not NODE.exists() or not (MODULES / "@oai/artifact-tool").exists():
            self.skipTest("bundled renderer runtime unavailable")
        with tempfile.TemporaryDirectory(prefix="c3-six-page-export-failure-") as folder:
            root = Path(folder).resolve()
            kernel, _task, handoff, output = render_runtime_fixture(root, slide_count=6)
            good_dir = Path(output["pptx_path"]).parent
            prior_files = tree_snapshot(good_dir)
            prior_revision = kernel.load().revision
            self.assertEqual(len(output["renders"]), 6)
            self.assertIn(Path(output["pptx_path"]).name, prior_files)
            self.assertIn("result.json", prior_files)

            # Use a distinct attempt under the same project and exact task identity.
            # The exporter fails after the handoff/mapping are written to that attempt.
            attempt_parent = root / "failed-attempt"
            attempt_parent.mkdir()
            failed_dir = attempt_parent / handoff["task_id"]
            failed_handoff = deepcopy(handoff)
            failed_handoff["output_paths"] = {
                "directory": str(failed_dir),
                "pptx": str(failed_dir / Path(output["pptx_path"]).name),
            }
            runner = """
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {render} from './scripts/image-led-native.mjs';
const h=JSON.parse(fs.readFileSync(0,'utf8'));
const requireRuntime=createRequire(path.join(process.argv[2],'__image_led_runtime__.cjs'));
const sdk=await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
try {
  await render(h,{projectRoot:process.argv[1],nodeModulesRoot:process.argv[2],
    pythonExecutable:process.argv[3],loadSdk:async()=>({
      Presentation:sdk.Presentation,FileBlob:sdk.FileBlob,
      PresentationFile:{exportPptx(){throw Error('C3_INJECTED_EXPORT_STOP');}}
    })});
  console.log(JSON.stringify({unexpectedSuccess:true}));
} catch(error) {
  console.log(JSON.stringify({message:error.message}));
}
"""
            completed = subprocess.run(
                [str(NODE), "--input-type=module", "-e", runner,
                 str(root), str(MODULES), str(PYTHON)],
                input=json.dumps(failed_handoff), text=True, capture_output=True,
                cwd=CODE_ROOT, timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["message"],
                             "C3_INJECTED_EXPORT_STOP")
            self.assertTrue((failed_dir / "handoff.json").is_file())
            self.assertTrue((failed_dir / "mapping.json").is_file())
            self.assertEqual(json.loads((failed_dir / "failure.json").read_text())["status"],
                             "failed-unpublishable")
            self.assertFalse((failed_dir / "result.json").exists())
            self.assertFalse(Path(failed_handoff["output_paths"]["pptx"]).exists())
            self.assertEqual(tree_snapshot(good_dir), prior_files)
            self.assertEqual(kernel.load().revision, prior_revision)

            # Retrying at the previous output path must reject before any write.
            replay = subprocess.run(
                [str(NODE), "--input-type=module", "-e", runner,
                 str(root), str(MODULES), str(PYTHON)],
                input=json.dumps(handoff), text=True, capture_output=True,
                cwd=CODE_ROOT, timeout=90,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("Output directory already exists",
                          json.loads(replay.stdout)["message"])
            self.assertEqual(tree_snapshot(good_dir), prior_files)
            self.assertEqual(kernel.load().revision, prior_revision)

    def test_six_page_result_review_interruption_preserves_unpromoted_build(self) -> None:
        from ai_ppt_studio.application.image_led_results import ImageLedResultService, DIMENSIONS
        from ai_ppt_studio.application.project_service import ProjectCommandService
        from tests.test_image_led_results import MODULES, NODE, render_runtime_fixture
        from tests.test_image2_input_boundary import tree_snapshot

        if not NODE.exists() or not (MODULES / "@oai/artifact-tool").exists():
            self.skipTest("bundled renderer runtime unavailable")
        with tempfile.TemporaryDirectory(prefix="c3-six-page-review-recovery-") as folder:
            root = Path(folder).resolve()
            kernel, producer, _handoff, output = render_runtime_fixture(root, slide_count=6)
            commands = ProjectCommandService(kernel)
            result_ref, _ = commands.commit_noncontent_agent_result(
                command_id="c3-six-page-build-result", expected_revision=kernel.load().revision,
                task_id=producer["task_id"], request_kind="visual-contract",
                raw_request_payload={"artifact_type": "image-led-build-result",
                                     "project_id": kernel.project_id, "output": output})
            results = ImageLedResultService(kernel)
            self.assertEqual(results.current_result(result_ref, require_review=False)["output"], output)
            _, reviewer, _ = commands.request_agent_action(
                "c3-six-page-result-review", kernel.load().revision,
                action_type="review-visual-engineering", target_refs=[result_ref],
                instructions="Synthetic six-page review recovery only")
            review = {"artifact_type": "image-led-result-review",
                      "project_id": kernel.project_id, "target_ref": result_ref,
                      "reviewer_kind": "engineering", "reviewer_role": "visual-engineering-reviewer",
                      "checks": [{"criterion": kind, "result": "passed",
                                  "detail": "Synthetic review, no real visual approval"}
                                 for kind in sorted(DIMENSIONS)]}
            interrupted = deepcopy(review)
            interrupted["checks"].pop()
            before = tree_snapshot(root)
            with self.assertRaises(ContractValidationError):
                commands.commit_noncontent_agent_result(
                    command_id="c3-six-page-review-interrupted",
                    expected_revision=kernel.load().revision,
                    task_id=reviewer["task_id"], request_kind="visual-contract",
                    raw_request_payload=interrupted)
            self.assertEqual(tree_snapshot(root), before)
            self.assertNotIn("visual/anchors", kernel.load().artifact_heads)
            self.assertNotEqual(kernel.load().gate_status["G2"], "passed")
            with self.assertRaises(ArtifactReferenceError):
                results.current_result(result_ref)
            self.assertEqual(tree_snapshot(root), before)

            review_ref, _ = commands.commit_noncontent_agent_result(
                command_id="c3-six-page-review-recovered",
                expected_revision=kernel.load().revision,
                task_id=reviewer["task_id"], request_kind="visual-contract",
                raw_request_payload=review)
            self.assertEqual(results.current_result(result_ref, review_ref=review_ref)["output"], output)
            self.assertNotIn("visual/anchors", kernel.load().artifact_heads)
            self.assertNotEqual(kernel.load().gate_status["G2"], "passed")
            self.assertEqual(Path(output["pptx_path"]).read_bytes(),
                             before[str(Path(output["pptx_path"]).relative_to(root))])

    def test_six_page_native_result_promotes_three_explicit_review_anchors(self) -> None:
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService
        from ai_ppt_studio.application.project_service import ProjectCommandService
        from ai_ppt_studio.kernel.references import ArtifactReference
        from tests.test_image_led_g2 import reviewed_result_fixture
        from tests.test_image2_input_boundary import tree_snapshot

        with tempfile.TemporaryDirectory(prefix="c3-six-page-anchors-") as folder:
            root = Path(folder).resolve()
            kernel, output, result_ref, review_ref = reviewed_result_fixture(root, slide_count=6)
            self.assertEqual([row["slide_id"] for row in output["renders"]],
                             [f"S{n:02d}" for n in range(1, 7)])
            commands = ProjectCommandService(kernel)
            plan_ref = kernel.load().artifact_heads["visual/compilation-plan"]
            _, task, _ = commands.request_agent_action("c3-anchor-promotion-task", kernel.load().revision,
                action_type="build-native-first", target_refs=[plan_ref],
                instructions="Synthetic three-of-six representative anchor promotion")
            payload = {"artifact_type": "image-led-anchor-set", "build_result_ref": result_ref,
                       "four_dimension_review_ref": review_ref}
            before = tree_snapshot(root)
            with self.assertRaises(ContractValidationError):
                commands.commit_noncontent_agent_result(command_id="c3-reject-implicit-six-page-anchors",
                    expected_revision=kernel.load().revision, task_id=task["task_id"],
                    request_kind="native-anchor-set", raw_request_payload=payload)
            self.assertEqual(tree_snapshot(root), before)
            with self.assertRaises(ContractValidationError):
                ImageLedNativeService(kernel).register_anchors(
                    "c3-reject-non-object-anchor-input", kernel.load().revision, None)
            self.assertEqual(tree_snapshot(root), before)
            native = ImageLedNativeService(kernel)
            for invalid_ids in (["S01", "S01", "S06"], ["S01", "S07", "S06"],
                                ["S06", "S03", "S01"], ["S01", "S03"],
                                ["S01", "S03", "S06", "S02"]):
                with self.subTest(anchor_ids=invalid_ids), self.assertRaises(ContractValidationError):
                    native._anchor_projection(result_ref, review_ref, anchor_slide_ids=invalid_ids)
                self.assertEqual(tree_snapshot(root), before)

            anchor_ref, _ = commands.commit_noncontent_agent_result(
                command_id="c3-promote-explicit-three-of-six", expected_revision=kernel.load().revision,
                task_id=task["task_id"], request_kind="native-anchor-set",
                raw_request_payload={**payload, "slide_ids": ["S01", "S03", "S06"]})
            anchors = kernel.artifacts.resolve(ArtifactReference.parse(anchor_ref))["payload"]
            self.assertEqual(anchors["slide_ids"], ["S01", "S03", "S06"])
            self.assertEqual([row["slide_id"] for row in anchors["render_assets"]],
                             ["S01", "S03", "S06"])
            self.assertEqual(anchors["pptx_sha256"], output["pptx_sha256"])
            self.assertEqual(ImageLedNativeService(kernel).current_anchors(), anchors)
            self.assertEqual(kernel.load().gate_status["G2"], "open")

            from ai_ppt_studio.application.visual_service import VisualService
            from tests.test_image_led_runtime import formal_review
            from tests.v16_visual_fixtures import rich_target_payload
            visual = VisualService(kernel)
            formal_review(kernel, anchor_ref, stage="G2", kind="aesthetic")
            formal_review(kernel, anchor_ref, stage="G2", kind="engineering")
            target = rich_target_payload(visual, "macos-powerpoint", {
                "anchors": anchor_ref, "pptx": anchors["native_first_pptx_ref"],
                "pptx_sha256": anchors["pptx_sha256"], "slide_ids": anchors["slide_ids"]})
            visual.register_target_render_evidence("c3-synthetic-target", kernel.load().revision, target)
            visual.record_g2("c3-synthetic-g2", kernel.load().revision)
            self.assertEqual(kernel.load().gate_status["G2"], "passed")


if __name__ == "__main__":
    unittest.main()
