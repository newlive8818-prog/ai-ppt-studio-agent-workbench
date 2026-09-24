"""Production Runtime integration; all inputs/decisions are synthetic test evidence."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from tests.test_image_led_selection import selection_fixture
from tests.test_image_led_contracts import text_style
from tests.test_image2_input_boundary import tree_snapshot
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference

REGION_CHECKS = {'visible-copy-transcription', 'complete-region-coverage', 'material-roles', 'faithful-geometry-appearance'}


def inventory_for(selection, selection_ref):
    return {'artifact_type': 'image-led-region-inventory', 'project_id': selection['project_id'],
        'selection_ref': selection_ref, 'slides': [{
            'target_binding': deepcopy(s['target_binding']),
            'canvas': {'width': 1280, 'height': 720, 'dpi': 96},
            'source_image_size': {'width': 1280, 'height': 720},
            'regions': [{'region_id': item['item_id'], 'kind': 'text',
                'bbox': [24, 24 + i * 100, 1200, 80], 'z_order': i,
                'content': {'items': [deepcopy(item)]}, 'material_binding': None,
                'appearance': text_style(item['text'])}
                for i, item in enumerate(s['selected_copy']['items'])]}
            for s in selection['slides']]}


def register_regions(kernel, payload, command='regions'):
    return VisualService(kernel).commit_public_artifact(command, kernel.load().revision,
        kind='visual-contract', payload=payload)


def region_review(kernel, inventory_ref, suffix='one'):
    command = ProjectCommandService(kernel)
    _, task, _ = command.request_agent_action('regions-review-' + suffix, kernel.load().revision,
        action_type='review-visual-engineering', target_refs=[inventory_ref], instructions='Synthetic region audit')
    payload = {'artifact_type': 'image-led-region-review', 'project_id': kernel.project_id,
        'target_ref': inventory_ref, 'reviewer_kind': 'engineering',
        'reviewer_role': 'visual-engineering-reviewer', 'checks': [
            {'criterion': criterion, 'result': 'passed', 'detail': 'Synthetic only'} for criterion in sorted(REGION_CHECKS)]}
    return command.commit_noncontent_agent_result(command_id='regions-reviewed-' + suffix,
        expected_revision=kernel.load().revision, task_id=task['task_id'],
        request_kind='visual-contract', raw_request_payload=payload)[0]


def regions_fixture(root, slide_count=3):
    svc, selection_ref = (selection_fixture(root) if slide_count == 3
                          else selection_fixture(root, slide_count=slide_count))
    selection = svc.current_selection(selection_ref)
    inventory = inventory_for(selection, selection_ref)
    ref = register_regions(svc.kernel, inventory)
    review = region_review(svc.kernel, ref)
    return svc.kernel, selection, inventory, ref, review


def contract_fixture(root, slide_count=3):
    from tests.test_image_led_compilation import fixture_for
    kernel, selection, inventory, inventory_ref, _ = regions_fixture(root, slide_count=slide_count)
    heads = kernel.load().artifact_heads
    blueprint_ref = heads['content/reading-blueprint']
    blueprint = kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))['payload']
    policy = kernel.artifacts.resolve(ArtifactReference.parse(heads['visual/image-led/input-policy']))['payload']
    _, brief, design, contract = fixture_for(selection, inventory, reading_blueprint=blueprint,
        blueprint_ref=blueprint_ref, selection_ref=inventory['selection_ref'], region_inventory_ref=inventory_ref)
    brief['image_led'] = {'selection_ref': inventory['selection_ref']}
    visual = VisualService(kernel)
    brief_ref = visual.register_visual_brief('brief', kernel.load().revision, brief)
    design['visual_brief_ref'] = brief_ref
    design['image_led'] = {'selection_ref': inventory['selection_ref']}
    for field, value in policy['common_rules'].items():
        design[field] = deepcopy(value)
    design_ref = visual.register_design_system('design', kernel.load().revision, design)
    contract['deck_design_system_ref'] = design_ref
    contract['source_version'] = blueprint['source_version']
    contract_ref = visual.register_visual_contract_set('contracts', kernel.load().revision, contract)
    return kernel, contract_ref


def formal_review(kernel, target_ref, *, stage='G1', kind='aesthetic'):
    from tests.v16_visual_fixtures import passing_visual_review
    command = ProjectCommandService(kernel)
    _, task, _ = command.request_agent_action('review-' + stage + kind, kernel.load().revision,
        action_type='review-visual-' + kind, target_refs=[target_ref], instructions='Synthetic formal review')
    payload = passing_visual_review(target_ref, stage=stage, reviewer_kind=kind,
        reviewer_role='visual-' + kind + '-reviewer')
    payload['artifact_type'] = 'visual-review-record'
    return command.commit_noncontent_agent_result(command_id='review-result-' + stage + kind,
        expected_revision=kernel.load().revision, task_id=task['task_id'],
        request_kind='visual-contract', raw_request_payload=payload)[0]


def g1_fixture(root, slide_count=3):
    kernel, contract_ref = contract_fixture(root, slide_count=slide_count)
    visual = VisualService(kernel)
    visual.register_convergence('converged', kernel.load().revision, {
        'production_route': 'strict-B', 'visual_contract_set_ref': contract_ref,
        'producer_role': 'slide-visual-designer', 'decision_summary': 'Synthetic finalized design transcription',
        'convergence_status': 'passed'})
    formal_review(kernel, contract_ref)
    visual.record_g1('g1', kernel.load().revision)
    return kernel, contract_ref


class ImageLedRuntimeTests(unittest.TestCase):
    def test_public_region_registration_accepts_current_selection_and_preserves_exact_content(self):
        with tempfile.TemporaryDirectory() as folder:
            svc, ref = selection_fixture(Path(folder))
            selection = svc.current_selection(ref)
            payload = inventory_for(selection, ref)
            self.assertEqual(validate_region_inventory(payload, selection, selection_ref=ref), payload)
            try:
                inventory_ref = register_regions(svc.kernel, payload)
            except ContractValidationError as error:
                self.fail('Current selection and valid regions must register through the public Runtime: ' + str(error))
            saved = svc.kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']
            self.assertEqual(saved, payload)
            self.assertEqual(svc.kernel.load().artifact_heads['visual/image-led/selection'], ref)

    def test_region_review_requires_real_agent_result_and_replacement_invalidates_it(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                kernel, _, payload, ref, review = regions_fixture(Path(folder))
            except ContractValidationError as error:
                self.fail('Region audit must have a governed producer/result path: ' + str(error))
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            service = ImageLedNativeService(kernel)
            self.assertEqual(service.current_regions(), payload)
            before = tree_snapshot(Path(folder))
            forged = kernel.artifacts.resolve(ArtifactReference.parse(review))['payload']
            with self.assertRaises(ContractValidationError):
                VisualService(kernel).commit_public_artifact('forged-review', kernel.load().revision,
                    kind='visual-contract', payload=forged)
            self.assertEqual(tree_snapshot(Path(folder)), before)
            changed = deepcopy(payload)
            changed['slides'][0]['regions'][0]['bbox'][0] += 1
            changed_ref = register_regions(kernel, changed, 'regions-revised')
            self.assertNotEqual(ref, changed_ref)
            with self.assertRaises(ContractValidationError):
                service.current_regions()
            self.assertNotIn(review, kernel.load().artifact_heads.values())

    def test_bad_regions_are_rejected_without_business_write(self):
        with tempfile.TemporaryDirectory() as folder:
            svc, ref = selection_fixture(Path(folder))
            good = inventory_for(svc.current_selection(ref), ref)
            for modify in (lambda p: p['slides'][0]['regions'].pop(),
                           lambda p: p['slides'][0]['target_binding'].update(page_order=2),
                           lambda p: p['slides'][0]['source_image_size'].update(width=640)):
                changed = deepcopy(good); modify(changed)
                before = tree_snapshot(Path(folder))
                with self.assertRaises(ContractValidationError):
                    register_regions(svc.kernel, changed, 'bad-' + str(modify))
                self.assertEqual(tree_snapshot(Path(folder)), before)


class ImageLedFormalChainTests(unittest.TestCase):
    def test_current_regions_publish_complete_contract_and_plan_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                kernel, contract_ref = contract_fixture(Path(folder))
            except ContractValidationError as error:
                self.fail('Complete formal Image-led contract must publish via production Runtime: ' + str(error))
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            from ai_ppt_studio.application.gate_evaluator import GateEvaluator
            contracts, plan = ImageLedNativeService(kernel).current_contract_plan()
            self.assertEqual(plan['compiler_version'], 'image-led-faithful-compiler/v1')
            self.assertEqual(plan['visual_contract_set_ref'], contract_ref)
            self.assertTrue(GateEvaluator(kernel)._visual_plan_publication_is_atomic(
                source_revision=plan['source_revision'], contract_ref=contract_ref,
                plan_ref=kernel.load().artifact_heads['visual/compilation-plan']))
            before = tree_snapshot(Path(folder))
            bad = deepcopy(contracts)
            bad['slide_contracts'][0]['regions'][0]['bbox'][0] += 10
            with self.assertRaises(ContractValidationError):
                VisualService(kernel).register_visual_contract_set('redesign', kernel.load().revision, bad)
            self.assertEqual(tree_snapshot(Path(folder)), before)


class ImageLedG1ChainTests(unittest.TestCase):
    def test_formal_image_led_g1_uses_current_plan_and_independent_review(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                kernel, contract_ref = g1_fixture(Path(folder))
            except ContractValidationError as error:
                self.fail('Current Image-led contract must reach formal G1 through reviewed production entries: ' + str(error))
            self.assertEqual(kernel.load().gate_status['G1'], 'passed')
            self.assertEqual(kernel.load().gate_status['G2'], 'open')
            self.assertEqual(kernel.load().gate_status['G3'], 'locked')
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(kernel).request_agent_action('old-image-assets', kernel.load().revision,
                    action_type='generate-image-assets', target_refs=[contract_ref], instructions='')
            self.assertEqual(tree_snapshot(Path(folder)), before)

class ImageLedInvalidationTests(unittest.TestCase):
    def test_region_change_reopens_g1_and_removes_contract_plan_and_old_review(self):
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            old = dict(kernel.load().artifact_heads)
            inventory = ImageLedNativeService(kernel).current_regions()
            inventory['slides'][0]['regions'][0]['bbox'][0] += 1
            register_regions(kernel, inventory, 'revised-after-g1')
            self.assertEqual(kernel.load().gate_status['G1'], 'open')
            self.assertEqual(kernel.load().gate_status['G2'], 'locked')
            for slot in ['visual/contracts', 'visual/compilation-plan', 'visual/review/G1/aesthetic']:
                self.assertNotIn(slot, kernel.load().artifact_heads)
            self.assertEqual(kernel.load().artifact_heads['visual/image-led/selection'], old['visual/image-led/selection'])


class ImageLedReviewInvalidationTests(unittest.TestCase):
    def test_revoking_current_material_scope_removes_usable_design_heads(self):
        from tests.test_image2_input_boundary import confirm_scope
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            confirm_scope(kernel, kernel.load().artifact_heads['visual/image-led/scope'], 'revoked', 'revoke-current-scope')
            self.assertEqual(kernel.load().gate_status['G1'], 'open')
            self.assertEqual(kernel.load().gate_status['G2'], 'locked')
            for slot in ('visual/image-led/selection', 'visual/contracts', 'visual/compilation-plan'):
                self.assertNotIn(slot, kernel.load().artifact_heads)

    def test_replacing_release_policy_invalidates_image_led_g1_and_contracts(self):
        from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            service = ReleaseTargetPolicyService(kernel)
            policy = service.current()[1].as_payload()
            policy['policy_version'] = '1.1'
            service.bind_policy('replace-release', kernel.load().revision, policy)
            self.assertEqual(kernel.load().gate_status['G1'], 'open')
            self.assertEqual(kernel.load().gate_status['G2'], 'locked')
            self.assertNotIn('visual/contracts', kernel.load().artifact_heads)

    def test_replacing_selected_candidate_source_review_invalidates_selection_and_g1(self):
        from tests.test_image_led_selection import review_candidate
        from ai_ppt_studio.application.image_led_service import ImageLedService
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = g1_fixture(Path(folder))
            heads = kernel.load().artifact_heads
            candidate_ref = next(value for slot, value in heads.items() if slot.startswith('visual/image-led/candidate/'))
            review_candidate(ImageLedService(kernel), candidate_ref, 'replace-selected-source')
            self.assertEqual(kernel.load().gate_status['G1'], 'open')
            self.assertEqual(kernel.load().gate_status['G2'], 'locked')
            for slot in ('visual/image-led/selection', 'visual/contracts', 'visual/compilation-plan'):
                self.assertNotIn(slot, kernel.load().artifact_heads)

    def test_replacing_convergence_reopens_g1_before_new_build(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, contract_ref = g1_fixture(Path(folder))
            visual = VisualService(kernel)
            visual.register_convergence('replace-convergence', kernel.load().revision, {
                'production_route': 'strict-B', 'visual_contract_set_ref': contract_ref,
                'producer_role': 'slide-visual-designer', 'decision_summary': 'Changed synthetic assessment',
                'convergence_status': 'passed'})
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(kernel).request_agent_action('build-with-stale-g1', kernel.load().revision,
                    action_type='build-native-first', target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], instructions='')
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_replacing_g1_with_failed_independent_review_prevents_native_build(self):
        from tests.v16_visual_fixtures import passing_visual_review
        with tempfile.TemporaryDirectory() as folder:
            kernel, contract_ref = g1_fixture(Path(folder))
            commands = ProjectCommandService(kernel)
            _, task, _ = commands.request_agent_action('replace-g1-review', kernel.load().revision,
                action_type='review-visual-aesthetic', target_refs=[contract_ref], instructions='Synthetic failed review')
            payload = passing_visual_review(contract_ref, reviewer_role='visual-aesthetic-reviewer')
            payload['artifact_type'] = 'visual-review-record'
            payload['checks'][0].update(result='failed', failure_reason='Synthetic wrong geometry')
            payload['overall_result'] = 'failed'
            commands.commit_noncontent_agent_result(command_id='failed-g1-result', expected_revision=kernel.load().revision,
                task_id=task['task_id'], request_kind='visual-contract', raw_request_payload=payload)
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                commands.request_agent_action('bad-build-after-review', kernel.load().revision,
                    action_type='build-native-first', target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], instructions='')
            self.assertEqual(tree_snapshot(Path(folder)), before)


class ImageLedProjectionTests(unittest.TestCase):
    def test_review_uses_exact_selected_copy_even_when_legacy_fields_are_present(self):
        from ai_ppt_studio.application.visual_review_service import VisualReviewService
        with tempfile.TemporaryDirectory() as folder:
            kernel, ref = contract_fixture(Path(folder))
            slide = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']['slide_contracts'][0]
            selected = slide['image_led']['selected_copy']
            selected['items'][0]['text'] = '  定版标题\n'
            selected['items'][1]['text'] = '  定版正文\n保留换行  '
            slide.update(visible_copy=['旧 G0 正文'], frozen_copy=['其他旧正文'], anchor_title='旧标题')
            view = VisualReviewService._project_slide_contract(slide)
            self.assertEqual(view['neutral_title'], selected['items'][0]['text'])
            self.assertEqual(view['anchor_title'], selected['items'][0]['text'])
            self.assertEqual(view['visible_copy'], [item['text'] for item in selected['items'][1:]])
            self.assertNotIn('image_led', view)
