"""Synthetic Agent work records: never user confirmation or final acceptance."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.image_led_service import PREFIX
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.errors import WorkbenchValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image_led_requests import input_fixture
from tests.test_image_led_selection import make_candidate, review_candidate, selection_fixture
from tests.test_image2_input_boundary import tree_snapshot


def proposal_fixture(root, *, c2_pages=True, v2=False):
    from ai_ppt_studio.application.presales_content_service import PresalesContentService
    original = PresalesContentService.build_reading_deck_blueprint
    def c2_blueprint(service, command_id, revision, payload):
        payload = deepcopy(payload)
        if c2_pages:
            for slide in payload['slides']:
                slide['slide_id'] = 'C2-S' + str(slide['order'] + 3).zfill(2)
        return original(service, command_id, revision, payload)
    with patch.object(PresalesContentService, 'build_reading_deck_blueprint', c2_blueprint):
        if v2:
            from tests.test_image_led_v2_runtime import v2_input_fixture, v2_candidate
            service, _, packs = v2_input_fixture(root)
        else:
            service, _, packs = input_fixture(root)
    rows = []
    for i, pack in enumerate(packs):
        candidate, _ = (v2_candidate if v2 else make_candidate)(service, pack, str(i))
        review = review_candidate(service, candidate, str(i))
        rows.append({'candidate_ref': candidate, 'source_review_ref': review, 'accepted_deviations': []})
    ref = service.commit_artifact('proposal', service.kernel.load().revision,
        {'artifact_type': 'image-led-selection-proposal', 'project_id': service.kernel.project_id, 'candidates': rows})
    return ImageLedSelectionService(service.kernel), ref


def working_payload(service, ref):
    return {'artifact_type': 'image-led-working-selection', 'project_id': service.kernel.project_id,
        'proposal_ref': ref, 'delegation': {'source_type': 'agent-recorded-user-instruction',
            'verification': 'agent-context-only', 'source_thread_id': '11111111-2222-3333-4444-555555555555',
            'instruction': 'Synthetic fixture: prepare three editable candidate slides; acceptance remains pending.'}}


def working_fixture(root):
    service, ref = proposal_fixture(root)
    selected = VisualService(service.kernel).commit_public_artifact('working', service.kernel.load().revision,
        kind='visual-contract', payload=working_payload(service, ref))
    return service, selected


class WorkingSelectionTests(unittest.TestCase):
    def test_delegated_selection_binds_exact_three_pages_without_human_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = working_fixture(Path(folder))
            before = tree_snapshot(Path(folder))
            selected = service.current_selection(ref)
            self.assertEqual(selected['selection_origin'], 'delegated-ai-working-selection')
            self.assertEqual(selected['human_image_approval'], 'NotEstablished')
            self.assertEqual(selected['final_human_acceptance'], 'NotEstablished')
            self.assertEqual(selected['scope'], 'CHG-IL-C2-three-page-working-candidate')
            self.assertEqual(len(selected['slides']), 3)
            self.assertNotIn('confirmation_ref', selected)
            self.assertNotIn(PREFIX + 'selection-confirmation', service.kernel.load().artifact_heads)
            delegation = service.kernel.artifacts.resolve(ArtifactReference.parse(selected['delegation_ref']))['payload']
            self.assertEqual(delegation['delegation']['verification'], 'agent-context-only')
            self.assertEqual(delegation['proposal_ref'], selected['proposal_ref'])
            self.assertEqual(service.kernel.load().gate_status['G3'], 'locked')
            self.assertEqual(service.kernel.load().gate_status['G4'], 'locked')
            for row in selected['slides']:
                candidate = service.current_candidate(row['target_binding']['candidate_ref'])
                self.assertEqual(row['selected_copy'], candidate['selected_copy'])
                self.assertEqual(row['target_binding']['target_image_sha256'], candidate['image_sha256'])
                self.assertEqual(row['target_binding']['accepted_deviations'], [])
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_agent_record_cannot_claim_verified_or_human_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = proposal_fixture(Path(folder))
            for key, value in [('verification', 'verified-message'), ('source_type', 'host-action'),
                               ('user_approved', True), ('source_thread_id', 'not-a-thread'), ('instruction', '')]:
                payload = working_payload(service, ref)
                payload['delegation'][key] = value
                before = tree_snapshot(Path(folder))
                with self.assertRaises(ContractValidationError):
                    VisualService(service.kernel).commit_public_artifact('bad', service.kernel.load().revision,
                        kind='visual-contract', payload=payload)
                self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_working_selection_rejects_deviations_and_preserves_user_path(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = proposal_fixture(Path(folder))
            proposal = deepcopy(service.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload'])
            proposal['candidates'][0]['accepted_deviations'] = [{'item_id': 'title', 'difference_kind': 'text', 'before': 'a', 'after': 'b'}]
            with self.assertRaises(ContractValidationError):
                service._working_slides(proposal)
        with tempfile.TemporaryDirectory() as folder:
            service, ref = selection_fixture(Path(folder))
            selected = service.current_selection(ref)
            self.assertIn('confirmation_ref', selected)
            self.assertNotIn('selection_origin', selected)

    def test_working_selection_can_enter_unchanged_region_registration(self):
        from tests.test_image_led_runtime import inventory_for, register_regions
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService
        with tempfile.TemporaryDirectory() as folder:
            service, ref = working_fixture(Path(folder))
            selected = service.current_selection(ref)
            inventory = inventory_for(selected, ref)
            register_regions(service.kernel, inventory)
            self.assertEqual(ImageLedNativeService(service.kernel).current_regions(require_review=False), inventory)

    def test_handoff_carries_unverified_work_provenance_and_rechecks_it(self):
        from unittest.mock import patch
        from tests import test_image_led_runtime as fixtures
        from tests.test_image_led_handoff import context, TASK_ID
        from ai_ppt_studio.context_compiler import ContextCompiler
        with tempfile.TemporaryDirectory() as folder, patch.object(fixtures, 'selection_fixture', working_fixture):
            kernel, _ = fixtures.g1_fixture(Path(folder))
            wrapper = context(kernel)['layers']['visual_handoff']
            provenance = wrapper['selection_provenance']
            self.assertEqual(provenance['selection_origin'], 'delegated-ai-working-selection')
            self.assertEqual(provenance['human_image_approval'], 'NotEstablished')
            self.assertEqual(provenance['final_human_acceptance'], 'NotEstablished')
            self.assertEqual(provenance['delegation']['verification'], 'agent-context-only')
            self.assertNotIn('selection_provenance', wrapper['renderer_handoff'])
            altered = deepcopy(wrapper)
            altered['selection_provenance']['human_image_approval'] = 'passed'
            with self.assertRaises(WorkbenchValidationError):
                ContextCompiler(kernel).validate_visual_handoff_for_result(altered,
                    project_revision=kernel.load().revision, expected_revision=kernel.load().revision + 1,
                    target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], task_id=TASK_ID)

    def test_working_command_is_idempotent_and_rejects_other_project_or_extra_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = proposal_fixture(Path(folder))
            payload = working_payload(service, ref)
            visual = VisualService(service.kernel)
            revision = service.kernel.load().revision
            selected = visual.commit_public_artifact('working', revision, kind='visual-contract', payload=payload)
            before = tree_snapshot(Path(folder))
            self.assertEqual(visual.commit_public_artifact('working', revision,
                kind='visual-contract', payload=payload), selected)
            self.assertEqual(tree_snapshot(Path(folder)), before)
            for change in ({'project_id': 'another-project'}, {'human_image_approval': 'passed'},
                           {'artifact_type': 'image-led-selection'}):
                with self.assertRaises(ContractValidationError):
                    visual.commit_public_artifact('invalid', service.kernel.load().revision,
                        kind='visual-contract', payload={**payload, **change})
                self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_other_three_page_decks_cannot_use_the_c2_working_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = proposal_fixture(Path(folder), c2_pages=False)
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                VisualService(service.kernel).commit_public_artifact('other-three', service.kernel.load().revision,
                    kind='visual-contract', payload=working_payload(service, ref))
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_v2_public_bridge_keeps_copy_version_title_identity_and_ledger_untouched(self):
        from ai_ppt_studio.application.v16_bridge import dispatch_v16
        with tempfile.TemporaryDirectory() as folder:
            service, ref = proposal_fixture(Path(folder), v2=True)
            kernel = service.kernel
            ledger = kernel.load().artifact_heads.get('kernel/confirmation-consumptions')
            result = dispatch_v16({'operation': 'commit-artifact', 'project_root': str(kernel.project_root),
                'command_id': 'working-public', 'expected_revision': kernel.load().revision,
                'kind': 'visual-contract', 'payload': working_payload(service, ref)})
            selected = service.current_selection(result['result']['artifact_ref'])
            self.assertEqual(kernel.load().artifact_heads.get('kernel/confirmation-consumptions'), ledger)
            for row in selected['slides']:
                self.assertEqual(row['selected_copy']['copy_version'], 'image-led-selected-copy/v2')
                self.assertEqual(row['selected_copy']['title_item_id'], 'title')

    def test_source_review_replacement_invalidates_working_selection(self):
        from ai_ppt_studio.errors import ArtifactReferenceError
        with tempfile.TemporaryDirectory() as folder:
            service, ref = working_fixture(Path(folder))
            candidate = service.current_selection(ref)['slides'][0]['target_binding']['candidate_ref']
            review_candidate(service, candidate, 'replacement')
            self.assertNotIn(PREFIX + 'selection', service.kernel.load().artifact_heads)
            before = tree_snapshot(Path(folder))
            with self.assertRaises((ContractValidationError, ArtifactReferenceError)):
                service.current_selection(ref)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_forged_working_acceptance_or_copy_cannot_pass_current_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            service, ref = working_fixture(Path(folder))
            original = service.current_selection(ref)
            for name in ('acceptance', 'copy'):
                value = deepcopy(original)
                if name == 'acceptance':
                    value['human_image_approval'] = 'passed'
                else:
                    value['slides'][0]['selected_copy']['items'][0]['text'] = 'forged content'
                # Synthetic corrupted-store fixture only; production public paths reject these fields.
                state = service.kernel.commit(command_id='synthetic-corruption-' + name,
                    expected_revision=service.kernel.load().revision, event_type='synthetic.corruption',
                    artifact_updates={PREFIX + 'selection': ('image-led-selection', value)})
                before = tree_snapshot(Path(folder))
                with self.assertRaises(ContractValidationError):
                    service.current_selection(state.artifact_heads[PREFIX + 'selection'])
                self.assertEqual(tree_snapshot(Path(folder)), before)
