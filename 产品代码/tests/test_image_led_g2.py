"""Real production entries with synthetic decisions and actual generated PPTX bytes."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.image_led_results import ImageLedResultService, DIMENSIONS
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image_led_results import render_runtime_fixture
from tests.test_image_led_runtime import formal_review
from tests.test_image2_input_boundary import tree_snapshot
from tests import test_image_led_runtime as runtime_fixtures


BASE_INVENTORY_FOR = runtime_fixtures.inventory_for


def heterogeneous_three_page_inventory(selection, selection_ref):
    """Keep the normal production fixture, varying only valid native objects."""
    inventory = BASE_INVENTORY_FOR(selection, selection_ref)
    colors = ("#E8F1F5", "#F3EBDD")
    for slide_index, slide in enumerate(inventory["slides"]):
        extra_count = slide_index
        for extra_index in range(extra_count):
            slide["regions"].append(
                {
                    "region_id": f"native-shape-{slide_index + 1}-{extra_index + 1}",
                    "kind": "shape",
                    "bbox": [900 + extra_index * 120, 64, 96, 72],
                    "z_order": len(slide["regions"]),
                    "content": {"items": []},
                    "material_binding": None,
                    "appearance": {
                        "geometry": "rect",
                        "corner_radius": 0,
                        "fill": {
                            "type": "solid",
                            "color": colors[extra_index % len(colors)],
                        },
                        "line": None,
                        "shadow": None,
                    },
                }
            )
    return inventory


def reviewed_result_fixture(root):
    kernel, producer, handoff, output = render_runtime_fixture(root)
    commands = ProjectCommandService(kernel)
    result_ref, _ = commands.commit_noncontent_agent_result(command_id='build-result', expected_revision=kernel.load().revision,
        task_id=producer['task_id'], request_kind='visual-contract', raw_request_payload={
            'artifact_type': 'image-led-build-result', 'project_id': kernel.project_id, 'output': output})
    _, task, _ = commands.request_agent_action('four-dimensions', kernel.load().revision,
        action_type='review-visual-engineering', target_refs=[result_ref], instructions='Synthetic judgments only')
    review_ref, _ = commands.commit_noncontent_agent_result(command_id='four-dimensions-result',
        expected_revision=kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract', raw_request_payload={
            'artifact_type': 'image-led-result-review', 'project_id': kernel.project_id, 'target_ref': result_ref,
            'reviewer_kind': 'engineering', 'reviewer_role': 'visual-engineering-reviewer', 'checks': [
                {'criterion': key, 'result': 'passed', 'detail': 'Synthetic result; not real visual acceptance'}
                for key in sorted(DIMENSIONS)]})
    return kernel, output, result_ref, review_ref


def promote(kernel, result_ref, review_ref):
    commands = ProjectCommandService(kernel)
    plan_ref = kernel.load().artifact_heads['visual/compilation-plan']
    _, task, _ = commands.request_agent_action(
        'promote-anchor-task', kernel.load().revision,
        action_type='build-native-first', target_refs=[plan_ref],
        instructions='Synthetic anchor promotion through the formal action/result entry')
    payload = {
        'artifact_type': 'image-led-anchor-set',
        'build_result_ref': result_ref,
        'four_dimension_review_ref': review_ref,
    }
    before = tree_snapshot(kernel.project_root)
    with unittest.TestCase().assertRaises(ContractValidationError):
        commands.commit_noncontent_agent_result(
            command_id='reject-stale-anchor-promotion',
            expected_revision=kernel.load().revision,
            task_id=task['task_id'],
            request_kind='native-anchor-set',
            raw_request_payload={
                **payload,
                'build_result_ref': 'artifact://image-led-build-result/' + '0' * 64,
            },
        )
    assert tree_snapshot(kernel.project_root) == before
    anchor_ref, _ = commands.commit_noncontent_agent_result(
        command_id='promote',
        expected_revision=kernel.load().revision,
        task_id=task['task_id'],
        request_kind='native-anchor-set',
        raw_request_payload=payload,
    )
    return anchor_ref


class ImageLedG2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='c2-g2-integration-')
        cls.root = Path(cls.folder.name).resolve()
        cls.kernel, cls.output, cls.result_ref, cls.review_ref = reviewed_result_fixture(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_actual_output_promotes_to_current_anchors_and_existing_g2_review_without_signing_g3(self):
        kernel = self.kernel; visual = VisualService(kernel)
        try:
            anchor_ref = promote(kernel, self.result_ref, self.review_ref)
        except ContractValidationError as error:
            self.fail('Actual checked output must become current anchors through the production service: ' + str(error))
        from ai_ppt_studio.kernel.references import ArtifactReference
        anchor = kernel.artifacts.resolve(ArtifactReference.parse(anchor_ref))['payload']
        self.assertEqual(anchor['pptx_sha256'], self.output['pptx_sha256'])
        self.assertEqual(anchor['slide_ids'], [row['slide_id'] for row in self.output['renders']])
        from tests.v16_visual_fixtures import rich_target_payload, passing_visual_review
        refs = {'anchors': anchor_ref, 'pptx': anchor['native_first_pptx_ref'],
                'pptx_sha256': anchor['pptx_sha256'], 'slide_ids': anchor['slide_ids']}
        target = rich_target_payload(visual, 'macos-powerpoint', refs)
        commands = ProjectCommandService(kernel)
        _, reviewer, _ = commands.request_agent_action('pre-write-byte-review', kernel.load().revision,
            action_type='review-visual-aesthetic', target_refs=[anchor_ref], instructions='Synthetic byte-race check')
        review = passing_visual_review(anchor_ref, stage='G2', reviewer_kind='aesthetic', reviewer_role='visual-aesthetic-reviewer')
        review['artifact_type'] = 'visual-review-record'
        path = Path(self.output['pptx_path']); original = path.read_bytes()
        try:
            path.write_bytes(original + b'mutated-before-evidence')
            attempts = {
                'review': lambda: commands.commit_noncontent_agent_result(command_id='reject-stale-g2-review',
                    expected_revision=kernel.load().revision, task_id=reviewer['task_id'],
                    request_kind='visual-contract', raw_request_payload=review),
                'target': lambda: visual.register_target_render_evidence('reject-stale-target', kernel.load().revision, target),
            }
            for name, operation in attempts.items():
                with self.subTest(prewrite_entry=name):
                    before = tree_snapshot(self.root)
                    with self.assertRaises(ContractValidationError):
                        operation()
                    self.assertEqual(tree_snapshot(self.root), before)
        finally:
            path.write_bytes(original)


        formal_review(kernel, anchor_ref, stage='G2', kind='aesthetic')
        formal_review(kernel, anchor_ref, stage='G2', kind='engineering')
        before = tree_snapshot(self.root)
        with self.assertRaises(GateBlockedError):
            visual.record_g2('no-desktop-proof', kernel.load().revision)
        self.assertEqual(tree_snapshot(self.root), before)
        # Test-only target evidence exercises the existing application validators.
        # It is synthetic and must never be claimed as an actual desktop result.
        visual.register_target_render_evidence('synthetic-target', kernel.load().revision, target)
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService
        with patch.object(
            ImageLedNativeService,
            'current_anchors',
            side_effect=TimeoutError('provider text must not control the diagnostic'),
        ):
            with self.assertRaises(GateBlockedError) as blocked:
                GateEvaluator(kernel).validate_current_g2_evidence()
        self.assertIn(
            'anchor-slide-set-invalid',
            blocked.exception.missing_evidence,
        )
        self.assertEqual(
            blocked.exception.diagnostics,
            (
                {
                        'stage': 'canonicalize',
                        'slot': 'visual/anchors',
                        'cause_class': 'TimeoutError',
                    'cause_code': 'deadline-exceeded',
                },
            ),
        )
        with patch.object(
            ImageLedNativeService,
            'current_anchors',
            side_effect=ContractValidationError('canonical anchor derivation failed'),
        ), patch(
            'ai_ppt_studio.application.gate_evaluator.validate_anchor_render_assets',
            side_effect=ContractValidationError('render assets also failed'),
        ):
            with self.assertRaises(GateBlockedError) as fallback_blocked:
                GateEvaluator(kernel).validate_current_g2_evidence()
            self.assertEqual(
                fallback_blocked.exception.diagnostics[-1],
                {
                    'stage': 'legacy-render-assets-fallback',
                    'slot': 'visual/anchors',
                    'cause_class': 'ContractValidationError',
                    'cause_code': 'legacy-render-assets-fallback-failed',
                },
            )
            self.assertEqual(
                fallback_blocked.exception.diagnostics[-2],
                {
                    'stage': 'canonicalize',
                    'slot': 'visual/anchors',
                    'cause_class': 'ContractValidationError',
                    'cause_code': 'canonical-anchor-derivation-failed',
                },
            )
        self.assertIn(
            'anchor-render-assets-invalid',
            fallback_blocked.exception.missing_evidence,
        )
        visual.record_g2('g2', kernel.load().revision)
        self.assertEqual(kernel.load().gate_status['G2'], 'passed')
        self.assertEqual(ImageLedResultService(kernel).current_result()['output'], self.output)
        visual.publish_visual_review('publish-review', kernel.load().revision)
        self.assertEqual(kernel.load().gate_status['G3'], 'user-reviewable')
        from ai_ppt_studio.application.review_session_service import ReviewSessionService
        from ai_ppt_studio.application.visual_review_service import VisualReviewService
        contract = kernel.load().artifact_heads['visual/contract']
        payload = kernel.artifacts.resolve(ArtifactReference.parse(contract))['payload']
        _, session, _ = ReviewSessionService(kernel).open_or_resume(command_id='open-existing-review',
            expected_revision=kernel.load().revision, review_type='visual-professional',
            target_artifact_ref=contract, source_version=payload['source_version'],
            source_revision=kernel.load().revision, open_policy='foreground-if-waiting')
        view = VisualReviewService(kernel).project(session['review_session_id'])
        self.assertTrue(view)
        self.assertEqual(
            view['projection_contract'],
            'image-led-formal-visual-review/v1',
        )
        self.assertNotEqual(kernel.load().gate_status['G3'], 'passed')
        path = Path(self.output['pptx_path']); original = path.read_bytes()
        try:
            path.write_bytes(original + b'mutated')
            before = tree_snapshot(self.root)
            with self.assertRaises(GateBlockedError):
                GateEvaluator(kernel).validate_current_g2_evidence()
            self.assertEqual(tree_snapshot(self.root), before)
        finally:
            path.write_bytes(original)

class ImageLedFormalThreePageChainTests(unittest.TestCase):
    def test_heterogeneous_three_page_chain_uses_formal_action_result_entries(self):
        with tempfile.TemporaryDirectory(prefix='c2-formal-three-page-chain-') as folder:
            root = Path(folder).resolve()
            with patch.object(
                runtime_fixtures,
                'inventory_for',
                heterogeneous_three_page_inventory,
            ):
                kernel, producer, handoff, output = render_runtime_fixture(root)

            self.assertEqual(producer['action_type'], 'build-native-first')
            self.assertEqual(len(handoff['slides']), 3)
            self.assertEqual(
                [len(slide['regions']) for slide in handoff['slides']],
                [2, 3, 4],
            )
            self.assertEqual(
                len({
                    slide['target_binding']['slide_id']
                    for slide in handoff['slides']
                }),
                3,
            )

            commands = ProjectCommandService(kernel)
            result_ref, _ = commands.commit_noncontent_agent_result(
                command_id='formal-three-page-build-result',
                expected_revision=kernel.load().revision,
                task_id=producer['task_id'],
                request_kind='visual-contract',
                raw_request_payload={
                    'artifact_type': 'image-led-build-result',
                    'project_id': kernel.project_id,
                    'output': output,
                },
            )
            self.assertEqual(
                ImageLedResultService(kernel).current_result(
                    result_ref, require_review=False
                )['output'],
                output,
            )

            _, reviewer, _ = commands.request_agent_action(
                'formal-three-page-four-dimension-review',
                kernel.load().revision,
                action_type='review-visual-engineering',
                target_refs=[result_ref],
                instructions='Synthetic four-dimension engineering review only',
            )
            review_ref, _ = commands.commit_noncontent_agent_result(
                command_id='formal-three-page-four-dimension-result',
                expected_revision=kernel.load().revision,
                task_id=reviewer['task_id'],
                request_kind='visual-contract',
                raw_request_payload={
                    'artifact_type': 'image-led-result-review',
                    'project_id': kernel.project_id,
                    'target_ref': result_ref,
                    'reviewer_kind': 'engineering',
                    'reviewer_role': 'visual-engineering-reviewer',
                    'checks': [
                        {
                            'criterion': criterion,
                            'result': 'passed',
                            'detail': 'Synthetic engineering evidence only',
                        }
                        for criterion in sorted(DIMENSIONS)
                    ],
                },
            )
            self.assertEqual(
                ImageLedResultService(kernel).current_result(
                    result_ref, review_ref=review_ref
                )['output'],
                output,
            )

            plan_ref = kernel.load().artifact_heads['visual/compilation-plan']
            _, promoter, _ = commands.request_agent_action(
                'formal-three-page-anchor-promotion',
                kernel.load().revision,
                action_type='build-native-first',
                target_refs=[plan_ref],
                instructions='Promote the already reviewed native result only',
            )
            anchor_ref, _ = commands.commit_noncontent_agent_result(
                command_id='formal-three-page-anchor-result',
                expected_revision=kernel.load().revision,
                task_id=promoter['task_id'],
                request_kind='native-anchor-set',
                raw_request_payload={
                    'artifact_type': 'image-led-anchor-set',
                    'build_result_ref': result_ref,
                    'four_dimension_review_ref': review_ref,
                },
            )
            anchors = kernel.artifacts.resolve(
                ArtifactReference.parse(anchor_ref)
            )['payload']
            self.assertEqual(
                anchors['slide_ids'],
                [row['slide_id'] for row in output['renders']],
            )
            self.assertEqual(
                anchors['image_led']['four_dimension_review_ref'],
                review_ref,
            )
            self.assertEqual(
                kernel.load().artifact_heads['visual/anchors'], anchor_ref
            )
            for task in (producer, reviewer, promoter):
                task_ref = kernel.load().artifact_heads[f"agent/task/{task['task_id']}"]
                stored = kernel.artifacts.resolve(
                    ArtifactReference.parse(task_ref)
                )['payload']
                self.assertEqual(stored['status'], 'completed')


class ImageLedAnchorPromotionLineageTests(unittest.TestCase):
    def test_old_build_result_cannot_be_promoted_after_current_result_head_changes(self):
        with tempfile.TemporaryDirectory(prefix='c2-anchor-lineage-') as folder:
            root = Path(folder).resolve()
            kernel, output, result_ref, review_ref = reviewed_result_fixture(root)

            forged_current_result = {
                'artifact_type': 'image-led-build-result',
                'project_id': kernel.project_id,
                'output': deepcopy(output),
                'producer_task_id': 'forged-current-producer',
                'producer_role': 'native-first-engineer',
                'context_pack_ref': 'artifact://context-pack/' + '0' * 64,
            }
            kernel.commit(
                command_id='forge-current-build-result-head-for-test',
                expected_revision=kernel.load().revision,
                event_type='test.current-build-result-head-replaced',
                artifact_updates={
                    'visual/image-led/build-result': (
                        'image-led-build-result',
                        forged_current_result,
                    )
                },
            )

            commands = ProjectCommandService(kernel)
            plan_ref = kernel.load().artifact_heads['visual/compilation-plan']
            _, promoter, _ = commands.request_agent_action(
                'old-build-result-promotion-task',
                kernel.load().revision,
                action_type='build-native-first',
                target_refs=[plan_ref],
                instructions='Synthetic stale-lineage rejection test',
            )
            before = tree_snapshot(root)
            with self.assertRaises(ContractValidationError):
                commands.commit_noncontent_agent_result(
                    command_id='reject-old-build-result-promotion',
                    expected_revision=kernel.load().revision,
                    task_id=promoter['task_id'],
                    request_kind='native-anchor-set',
                    raw_request_payload={
                        'artifact_type': 'image-led-anchor-set',
                        'build_result_ref': result_ref,
                        'four_dimension_review_ref': review_ref,
                    },
                )
            self.assertEqual(tree_snapshot(root), before)
