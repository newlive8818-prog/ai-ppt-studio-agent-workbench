"""Schema-3 bridge for exact existing-deck reconstruction.

The public MCP schema exposes this explicit route; a source checkout does not
prove that the currently loaded desktop host has installed it.
"""
from __future__ import annotations

from ai_ppt_studio.application.bridge import object_array, object_value, response, result, string_array
from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService
from ai_ppt_studio.application.image_led_native import ExistingDeckNativeService
from ai_ppt_studio.application.image_led_results import ExistingDeckResultService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


def begin(ctx, request):
    ref = ExistingDeckOptimizationService(ctx.kernel).begin(
        ctx.command_id, int(request['expected_revision']), source_id=str(request.get('source_id') or ''),
        source_pptx_sha256=str(request.get('source_pptx_sha256') or ''),
        user_message_ref=str(request.get('user_message_ref') or ''))
    return result(ctx, source_ref=ref)


def external_scope(ctx, request):
    ref = ExistingDeckOptimizationService(ctx.kernel).set_external_scope(
        ctx.command_id, int(request['expected_revision']),
        user_message_ref=str(request.get('user_message_ref') or ''),
        allowed_page_orders=request.get('allowed_page_orders'),
        excluded_image_sha256=string_array(request, 'excluded_image_sha256'),
        excluded_text_item_ids=string_array(request, 'excluded_text_item_ids'))
    return result(ctx, scope_ref=ref)


def register_request(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).register_request(
        ctx.command_id, int(request['expected_revision']),
        slide_id=str(request.get('slide_id') or ''), request_id=str(request.get('request_id') or ''),
        title_item_id=str(request.get('title_item_id') or ''), common_rules=object_value(request, 'common_rules'),
        layout_mode=str(request.get('layout_mode') or 'standard'),
        required_visible_item_ids=(string_array(request, 'required_visible_item_ids')
                                   if 'required_visible_item_ids' in request else []),
        relationship_constraints=(object_array(request, 'relationship_constraints')
                                  if 'relationship_constraints' in request else []),
        source_media_role_bindings=(object_array(request, 'source_media_role_bindings')
                                    if 'source_media_role_bindings' in request else []),
        main_source_picture_object_id=str(request.get('main_source_picture_object_id') or ''))
    return result(ctx, request_ref=ref)


def register_historical_design(ctx, request):
    refs = ExistingDeckSelectionService(ctx.kernel).register_historical_design(
        ctx.command_id, int(request['expected_revision']),
        slide_id=str(request.get('slide_id') or ''),
        request_id=str(request.get('request_id') or ''),
        title_item_id=str(request.get('title_item_id') or ''),
        common_rules=object_value(request, 'common_rules'),
        image_base64=str(request.get('image_base64') or ''),
        image_sha256=str(request.get('image_sha256') or ''),
        provenance=object_value(request, 'provenance'))
    return result(ctx, request_ref=refs[0], response_ref=refs[1], response_status='completed')


def execute_request(ctx, request):
    from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
    from ai_ppt_studio.application.artifact_guards import require_revision
    require_revision(ctx.kernel, int(request['expected_revision']))
    service = ExistingDeckSelectionService(ctx.kernel)
    request_id = str(request.get('request_id') or '')
    service._request(request_id)
    response_ref = service.execute_request(request_id, transport=Image2CommandAdapter.from_environment())
    stored = ctx.kernel.artifacts.resolve(ArtifactReference.parse(response_ref))['payload']
    return result(ctx, response_ref=response_ref, response_status=stored['status'],
                  request_id=request_id,
                  **({'image_sha256': stored['image_sha256']} if stored['status'] == 'completed' else {}))


def recover_request(ctx, request):
    service = ExistingDeckSelectionService(ctx.kernel)
    request_id = str(request.get('request_id') or '')
    response_ref, stored = service.recover_request(request_id)
    return result(ctx, response_ref=response_ref, response_status=stored['status'],
                  request_id=request_id,
                  **({'image_sha256': stored['image_sha256']}
                     if stored['status'] == 'completed' else {}))


def withdraw_unsent_request(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).withdraw_unsent_request(
        ctx.command_id, int(request['expected_revision']),
        request_id=str(request.get('request_id') or ''), reason=str(request.get('reason') or ''))
    return result(ctx, withdrawal_ref=ref)


def supersede_unselected_response(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).supersede_unselected_response(
        ctx.command_id, int(request['expected_revision']),
        request_id=str(request.get('request_id') or ''), reason=str(request.get('reason') or ''))
    return result(ctx, supersession_ref=ref)


def register_local_media_composition(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).register_local_media_composition(
        ctx.command_id, int(request['expected_revision']),
        request_id=str(request.get('request_id') or ''), placements=object_array(request, 'placements'))
    return result(ctx, composition_ref=ref)


def review_response(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).review_response(
        ctx.command_id, int(request['expected_revision']),
        request_id=str(request.get('request_id') or ''),
        reviewer_task_id=str(request.get('reviewer_task_id') or ''),
        producer_task_id=str(request.get('producer_task_id') or ''),
        checks=object_value(request, 'checks'))
    return result(ctx, review_ref=ref)


def select_internal(ctx, request):
    ref = ExistingDeckSelectionService(ctx.kernel).select_internal(
        ctx.command_id, int(request['expected_revision']),
        selections=object_array(request, 'selections'),
        reviewer_task_id=str(request.get('reviewer_task_id') or ''))
    return result(ctx, selection_ref=ref)


def register_plan(ctx, request):
    ref = ExistingDeckNativeService(ctx.kernel).register_plan(
        ctx.command_id, int(request['expected_revision']),
        inventory=object_value(request, 'inventory'), objects=object_array(request, 'objects'))
    return result(ctx, plan_ref=ref)


def compile_handoff(ctx, request):
    from ai_ppt_studio.application.artifact_guards import require_revision
    require_revision(ctx.kernel, int(request['expected_revision']))
    handoff = ContextCompiler(ctx.kernel).compile_existing_deck_handoff(
        task_id=str(request.get('task_id') or ''), plan_ref=str(request.get('plan_ref') or ''))
    return response(ctx, handoff=handoff)


def register_result(ctx, request):
    ref = ExistingDeckResultService(ctx.kernel).register_result(
        ctx.command_id, int(request['expected_revision']),
        task_id=str(request.get('task_id') or ''), plan_ref=str(request.get('plan_ref') or ''),
        output=object_value(request, 'output'))
    return result(ctx, result_ref=ref)


def register_target(ctx, request):
    ref = ExistingDeckResultService(ctx.kernel).register_target_evidence(
        ctx.command_id, int(request['expected_revision']),
        result_ref=str(request.get('result_ref') or ''), payload=object_value(request, 'payload'))
    return result(ctx, target_evidence_ref=ref)


def register_qa(ctx, request):
    ref = ExistingDeckResultService(ctx.kernel).register_qa(
        ctx.command_id, int(request['expected_revision']),
        result_ref=str(request.get('result_ref') or ''),
        reviewer_task_id=str(request.get('reviewer_task_id') or ''),
        pages=object_array(request, 'pages'), target_environment=object_value(request, 'target_environment'))
    return result(ctx, qa_ref=ref)


def status(ctx, _request):
    heads = ctx.kernel.load().artifact_heads
    if 'project/optimization-workflow' not in heads:
        raise ContractValidationError('Existing-deck route is not bound to this project')
    source = ExistingDeckOptimizationService(ctx.kernel).current_source()
    requests = []
    for key, ref in sorted(heads.items()):
        if not key.startswith(ExistingDeckSelectionService.REQUEST):
            continue
        entry = ctx.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        response_ref = heads.get(ExistingDeckSelectionService.RESPONSE + entry['request_id'])
        current = ctx.kernel.artifacts.resolve(ArtifactReference.parse(response_ref))['payload']['status'] if response_ref else 'not-sent'
        requests.append({'slide_id': entry['slide_id'], 'request_id': entry['request_id'],
                         'request_ref': ref, 'response_ref': response_ref, 'status': current})
    candidate = 'not-established'
    if ExistingDeckResultService.QA_SLOT in heads:
        ExistingDeckResultService(ctx.kernel).delivery_candidate()
        candidate = 'delivery-candidate'
    return response(ctx, optimization={'source': {'source_ref': heads['optimization/source'],
        'source_pptx_sha256': source['source_pptx_sha256'], 'page_count': len(source['slides'])},
        'scope_ref': heads.get('optimization/external-use-scope'), 'requests': requests,
        'selection_ref': heads.get('optimization/selection'),
        'plan_ref': heads.get('optimization/native-plan'),
        'result_ref': heads.get('optimization/native-result'),
        'qa_ref': heads.get('optimization/full-deck-qa'),
        'delivery_status': candidate})


def preview_image(ctx, request):
    """Read the exact current design; composed media is the target when present."""
    import base64
    import hashlib
    from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
    service = ExistingDeckSelectionService(ctx.kernel)
    request_id = str(request.get('request_id') or '')
    request_ref, design_request, response_ref, design = service._response(request_id)
    page = service.source_page(design_request['slide_id'])
    if source_real_media_refs(page) and ctx.kernel.load().artifact_heads.get(
            'optimization/composition/' + request_id):
        composition_ref, _, image_ref, image = service._current_composition(
            request_id, request_ref=request_ref, response_ref=response_ref, page=page)
        preview_role = 'composed-target'
        image_base64, image_sha256 = image['data_base64'], image['sha256']
        mime_type = image['mime_type']
    else:
        preview_role = 'uncomposed-design-base' if source_real_media_refs(page) else 'provider-design'
        image_base64, image_sha256 = design['image_base64'], design['image_sha256']
        mime_type = design['image_mime_type']
    if hashlib.sha256(base64.b64decode(image_base64, validate=True)).hexdigest() != image_sha256:
        raise ContractValidationError('Preview image bytes differ from the current design identity')
    return response(ctx, image={'slide_id': page['slide_id'], 'page_order': page['page_order'],
        'request_id': request_id, 'response_ref': response_ref,
        'image_sha256': image_sha256, 'image_mime_type': mime_type,
        'preview_role': preview_role, 'image_base64': image_base64})


INTERNAL_HANDLERS = {
    'optimization-begin': begin,
    'optimization-external-scope': external_scope,
    'optimization-register-request': register_request,
    'optimization-register-historical-design': register_historical_design,
    'optimization-execute-request': execute_request,
    'optimization-recover-request': recover_request,
    'optimization-withdraw-unsent-request': withdraw_unsent_request,
    'optimization-supersede-unselected-response': supersede_unselected_response,
    'optimization-register-local-media-composition': register_local_media_composition,
    'optimization-review-response': review_response,
    'optimization-select-internal': select_internal,
    'optimization-register-plan': register_plan,
    'optimization-compile-handoff': compile_handoff,
    'optimization-register-result': register_result,
    'optimization-register-target-evidence': register_target,
    'optimization-register-qa': register_qa,
    'optimization-status': status,
    'optimization-preview-image': preview_image,
}
