"""Synthetic generation and trustworthy selection integration, never real G0/G3."""
from __future__ import annotations
import base64
import tempfile
import unittest
from pathlib import Path
from tests.test_image_led_requests import input_fixture
from tests.test_image2_input_boundary import tree_snapshot
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService, SOURCE_CHECKS
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


class SyntheticTransport:
    def generate(self, *, request_id, payload):
        from PIL import Image
        from io import BytesIO
        buf = BytesIO()
        Image.new('RGB', (1280, 720), '#ffffff').save(buf, format='PNG')
        return {'response_id': 'synthetic-' + request_id, 'image_bytes': buf.getvalue()}


def make_candidate(service, pack_ref, suffix):
    kernel = service.kernel
    commands = ProjectCommandService(kernel)
    _, task, _ = commands.request_agent_action('generate-' + suffix, kernel.load().revision,
        action_type='generate-slide-images', target_refs=[pack_ref], instructions='')
    response_ref = service.execute_generation(task['task_id'], transport=SyntheticTransport())
    pack = kernel.artifacts.resolve(ArtifactReference.parse(pack_ref))['payload']
    copy = pack['confirmed_visible_copy']
    payload = {'artifact_type': 'image-led-candidate', 'project_id': kernel.project_id,
        'request_id': task['task_id'], 'generation_response_ref': response_ref,
        'pack_ref': pack_ref, 'slide_id': pack['slide_id'], 'page_order': pack['page_order'],
        'selected_copy': {'items': [{'item_id': 'title', 'kind': 'text', 'role': 'title', 'text': copy['title']}]
            + [{'item_id': b['block_id'], 'kind': 'text', 'role': 'body', 'text': b['text']} for b in copy['blocks']]},
        'material_roles': []}
    ref, _ = commands.commit_noncontent_agent_result(command_id='candidate-' + suffix,
        expected_revision=kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract',
        raw_request_payload=payload)
    return ref, payload


def review_candidate(service, candidate_ref, suffix):
    kernel = service.kernel
    commands = ProjectCommandService(kernel)
    _, task, _ = commands.request_agent_action('review-' + suffix, kernel.load().revision,
        action_type='review-visual-engineering', target_refs=[candidate_ref], instructions='Synthetic source review')
    payload = {'artifact_type': 'image-led-review', 'project_id': kernel.project_id,
        'target_ref': candidate_ref, 'review_kind': 'candidate-source',
        'reviewer_kind': 'engineering', 'reviewer_role': 'visual-engineering-reviewer',
        'checks': [{'criterion': k, 'result': 'passed', 'detail': 'Synthetic fixture only; not a real visual judgement'}
                   for k in sorted(SOURCE_CHECKS)]}
    ref, _ = commands.commit_noncontent_agent_result(command_id='source-result-' + suffix,
        expected_revision=kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract',
        raw_request_payload=payload)
    return ref


def selection_fixture(root):
    service, policy, packs = input_fixture(root)
    rows = []
    for i, ref in enumerate(packs):
        candidate, _ = make_candidate(service, ref, str(i))
        review = review_candidate(service, candidate, str(i))
        rows.append({'candidate_ref': candidate, 'source_review_ref': review, 'accepted_deviations': []})
    proposal = service.commit_artifact('proposal', service.kernel.load().revision,
        {'artifact_type': 'image-led-selection-proposal', 'project_id': service.kernel.project_id, 'candidates': rows})
    context = service.confirmation_context(proposal)
    selection_ref = service.confirm('select', service.kernel.load().revision,
        target_ref=proposal, choice='approved', **gate_confirmation_kwargs(context,
            identity_ref='test-host-confirmation://image-led-selection'))
    return ImageLedSelectionService(service.kernel), selection_ref


class ImageLedSelectionTests(unittest.TestCase):
    def test_three_candidate_selection_is_bound_to_one_trusted_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                service, selection_ref = selection_fixture(Path(folder))
            except ContractValidationError as error:
                self.fail(f'An exact reviewed three-page proposal must support trusted selection: {error}')
            before = tree_snapshot(Path(folder))
            selection = service.current_selection(selection_ref)
            self.assertEqual(len(selection['slides']), 3)
            for slide in selection['slides']:
                self.assertEqual(slide['target_binding']['design_authority'], 'finalized-image')
                self.assertEqual(slide['target_binding']['conversion_mode'], 'faithful-native')
            identity = 'test-host-confirmation://image-led-selection'
            self.assertEqual(service.kernel.confirmation_artifact_binding(identity), selection['confirmation_ref'])
            self.assertEqual(service.kernel.load().gate_status['G3'], 'locked')
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_selection_forgery_and_missing_source_review_never_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = input_fixture(Path(folder))
            candidate, _ = make_candidate(service, packs[0], 'unreviewed')
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.commit_artifact('forged-selection', service.kernel.load().revision,
                    {'artifact_type': 'image-led-selection', 'project_id': service.kernel.project_id, 'approved': True})
            self.assertEqual(tree_snapshot(Path(folder)), before)
            with self.assertRaises(ContractValidationError):
                service.commit_artifact('short-proposal', service.kernel.load().revision,
                    {'artifact_type': 'image-led-selection-proposal', 'project_id': service.kernel.project_id,
                     'candidates': [{'candidate_ref': candidate, 'source_review_ref': candidate, 'accepted_deviations': []}]})
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_generated_candidate_uses_exact_response_image_and_cannot_be_forged_directly(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = input_fixture(Path(folder))
            try:
                ref, payload = make_candidate(service, packs[0], 'one')
            except ContractValidationError as error:
                self.fail(f'Checked generation result should become a candidate in its task transaction: {error}')
            kernel = service.kernel
            candidate = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
            response = kernel.artifacts.resolve(ArtifactReference.parse(candidate['generation_response_ref']))['payload']
            self.assertEqual(candidate['image_sha256'], response['image_sha256'])
            image = kernel.artifacts.resolve(ArtifactReference.parse(candidate['image_ref']))['payload']
            self.assertEqual(image['data_base64'], response['image_base64'])
            self.assertEqual(kernel.load().gate_status['G3'], 'locked')
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.commit_artifact('direct-forgery', kernel.load().revision, payload)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_candidate_cannot_change_g0_visible_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = input_fixture(Path(folder))
            kernel = service.kernel
            original = make_candidate(service, packs[0], 'copy-original')[1]
            changed = dict(original)
            changed['selected_copy'] = {'items': [dict(item) for item in original['selected_copy']['items']]}
            changed['selected_copy']['items'][0]['text'] = '改写后的标题'
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                # Direct public registration cannot bypass the queued Agent result contract.
                service.commit_artifact('copy-forgery', kernel.load().revision, changed)
            self.assertEqual(tree_snapshot(Path(folder)), before)


if __name__ == '__main__':
    unittest.main()
