"""Offline independent reviewer probe; all data synthetic, no customer/host proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.image_led_service import PREFIX
from ai_ppt_studio.application.image_led_results import preflight_output
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError, WorkbenchValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests import test_image_led_runtime as runtime_fixtures
from tests.test_image_led_v2_runtime import v2_input_fixture, v2_candidate
from tests.test_image_led_selection import review_candidate
from tests.test_image_led_results import render_runtime_fixture
from tests.test_image2_input_boundary import tree_snapshot

seen = []
def check(condition, label):
    assert condition, label
    seen.append(label)

def working_v2(root):
    original = PresalesContentService.build_reading_deck_blueprint
    def rename(service, command_id, revision, payload):
        payload = deepcopy(payload)
        for slide in payload['slides']:
            slide['slide_id'] = 'C2-S' + str(slide['order'] + 3).zfill(2)
        return original(service, command_id, revision, payload)
    with patch.object(PresalesContentService, 'build_reading_deck_blueprint', rename):
        service, _, packs = v2_input_fixture(root)
    rows = []
    for i, pack in enumerate(packs):
        ref, _ = v2_candidate(service, pack, str(i))
        review = review_candidate(service, ref, str(i))
        rows.append({'candidate_ref': ref, 'source_review_ref': review, 'accepted_deviations': []})
    proposal = service.commit_artifact('proposal-reviewer', service.kernel.load().revision,
        {'artifact_type': 'image-led-selection-proposal', 'project_id': service.kernel.project_id, 'candidates': rows})
    payload = {'artifact_type': 'image-led-working-selection', 'project_id': service.kernel.project_id,
        'proposal_ref': proposal, 'delegation': {'source_type': 'agent-recorded-user-instruction',
            'verification': 'agent-context-only', 'source_thread_id': '11111111-2222-3333-4444-555555555555',
            'instruction': 'Synthetic independent reviewer: prepare three editable candidates; no user approval.'}}
    selected = VisualService(service.kernel).commit_public_artifact('working-reviewer', service.kernel.load().revision,
        kind='visual-contract', payload=payload)
    return ImageLedSelectionService(service.kernel), selected

with tempfile.TemporaryDirectory(prefix='c2-working-review-v2-', dir='/private/tmp') as directory:
    root = Path(directory).resolve()
    with patch.object(runtime_fixtures, 'selection_fixture', working_v2):
        kernel, task, handoff, output = render_runtime_fixture(root)
    service = ImageLedSelectionService(kernel)
    selection_ref = kernel.load().artifact_heads[PREFIX + 'selection']
    selection = service.current_selection(selection_ref)
    check(handoff['handoff_version'] == 'codex-presentations-image-led/v2', 'default v2 handoff and real offline renderer')
    check(all(s['selected_copy']['copy_version'] == 'image-led-selected-copy/v2' for s in handoff['slides']), 'v2 selected copy preserved')
    check([(s['target_binding']['slide_id'], s['target_binding']['page_order']) for s in handoff['slides']] == [('C2-S04',1), ('C2-S05',2), ('C2-S06',3)], 'three exact page identities and order')
    check(all(s['target_binding']['accepted_deviations'] == [] for s in handoff['slides']), 'no accepted deviations')
    check(preflight_output(output, handoff, root) == output, 'real bytes pass native preflight')
    check(output['status'] == 'engineering-output-unassessed', 'native output remains unassessed')
    stored_context = kernel.artifacts.resolve(ArtifactReference.parse(task['context_pack_ref']))['payload']
    wrapper = stored_context['layers']['visual_handoff']
    before = tree_snapshot(root)
    variants = []
    altered = deepcopy(wrapper); altered.pop('selection_provenance'); variants.append(('removed provenance', altered))
    altered = deepcopy(wrapper); altered['selection_provenance']['human_image_approval'] = 'passed'; variants.append(('forged approval', altered))
    altered = deepcopy(wrapper); altered['selection_provenance']['delegation']['verification'] = 'verified-message'; variants.append(('forged verifier', altered))
    altered = deepcopy(wrapper); altered['renderer_handoff']['slides'][0]['selected_copy']['items'][0]['text'] += ' altered'; variants.append(('changed native copy', altered))
    for label, altered in variants:
        try:
            ContextCompiler(kernel).validate_visual_handoff_for_result(altered,
                project_revision=task['input_revision'], expected_revision=wrapper['result_expected_revision'],
                target_refs=task['target_refs'], task_id=task['task_id'])
        except (ContractValidationError, WorkbenchValidationError):
            check(tree_snapshot(root) == before, label + ' rejected with zero writes')
        else:
            raise AssertionError(label + ' accepted')
    result_ref, _ = ProjectCommandService(kernel).commit_noncontent_agent_result(
        command_id='working-native-reviewer', expected_revision=kernel.load().revision,
        task_id=task['task_id'], request_kind='visual-contract', raw_request_payload={
            'artifact_type':'image-led-build-result', 'project_id':kernel.project_id, 'output':output})
    check(result_ref.startswith('artifact://image-led-build-result/'), 'formal Runtime native result transaction')
    check(kernel.load().gate_status['G3'] == 'locked' and kernel.load().gate_status['G4'] == 'locked', 'G3 and G4 remain locked after native result')
    check(PREFIX + 'selection-confirmation' not in kernel.load().artifact_heads, 'no user selection confirmation generated')
    check(service.current_selection(selection_ref)['human_image_approval'] == 'NotEstablished', 'human approval remains unestablished')
    # Publish a fresh proposal over the same reviewed images. Old working choice,
    # native dependencies, and replayed selection must no longer be current.
    proposal = kernel.artifacts.resolve(ArtifactReference.parse(selection['proposal_ref']))['payload']
    service.register_proposal('replacement-proposal-reviewer', kernel.load().revision, proposal)
    check(PREFIX + 'selection' not in kernel.load().artifact_heads, 'proposal replacement invalidates working selection')
    check('visual/compilation-plan' not in kernel.load().artifact_heads and PREFIX + 'build-result' not in kernel.load().artifact_heads, 'replacement invalidates native plan and result')
    before = tree_snapshot(root)
    try:
        service.current_selection(selection_ref)
    except (ArtifactReferenceError, ContractValidationError):
        check(tree_snapshot(root) == before, 'stale selection rejected read only')
    else:
        raise AssertionError('stale selection accepted')
print(json.dumps({'passed': len(seen), 'checks': seen, 'proof_scope':'synthetic private Runtime, real offline renderer bytes; no customer, HTTP, helper, installed-host, PowerPoint or user acceptance proof'}, indent=2))
