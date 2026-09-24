"""Image-led candidate, independent source review and trusted selection lifecycle."""
from __future__ import annotations
import base64
from copy import deepcopy
import hashlib
from uuid import UUID
from io import BytesIO
from ai_ppt_studio.application.artifact_guards import require_revision, resolve_kind
from ai_ppt_studio.application.image_led_service import ImageLedService, PREFIX
from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, text
from ai_ppt_studio.domains.visual.image_led import validate_selected_copy, selected_copy_sha256, validate_target_binding
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.domains.visual.image_output import output_fitness

SOURCE_CHECKS = {'visible-copy-transcription', 'no-unsupported-facts', 'material-roles', 'excluded-content'}
COMPOSED_SOURCE_CHECKS = SOURCE_CHECKS | {'composed-image-content', 'source-media-placement'}
PATCHED_SOURCE_CHECKS = COMPOSED_SOURCE_CHECKS | {'source-media-disposition'}
REMOTE_SOURCE_CHECKS = SOURCE_CHECKS | {'source-media-fidelity', 'source-media-role-placement'}
WORKING_SCOPE = 'CHG-IL-C2-three-page-working-candidate'
WORKING_ORIGIN = 'delegated-ai-working-selection'
WORKING_PAGES = [('C2-S04', 1), ('C2-S05', 2), ('C2-S06', 3)]


def client_logo_gallery_instruction(category_count: int, source_media_count: int) -> str:
    """Describe empty logo positions; actual customer marks stay on this machine."""
    if category_count != 4 or source_media_count < 20:
        fail('SOURCE', 'client logo gallery requires four source categories and at least 20 source images')
    return ('原稿本页有4组客户分类，按原文保留四个分类标题；每组5个，共20个空白客户标识版位。'
            '版位内无照片、无图标、无字、无伪造标识；只设计周围的层级、背景和间距。'
            '原稿客户标识在本地逐项核对并嵌回，不能凭图片总数推定哪些图片是客户标识。')


class ImageLedSelectionService(ImageLedService):
    def _upstream_mutation(self):
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator
        return GateEvaluator(self.kernel).image_led_upstream_replaced()

    def _agent(self, *, action, target_refs):
        task = getattr(self.kernel, 'prepared_agent_task', None)
        if (not isinstance(task, dict) or task.get('action_type') != action
                or task.get('target_refs') != target_refs or task.get('status') != 'queued'):
            fail('AGENT_RESULT', 'this artifact requires the governed Agent result transaction')
        return task

    def register_candidate(self, command_id, revision, payload):
        exact(payload, {'artifact_type', 'project_id', 'request_id', 'generation_response_ref',
            'pack_ref', 'slide_id', 'page_order', 'selected_copy', 'material_roles'}, 'candidate result')
        if payload['project_id'] != self.kernel.project_id:
            fail('PROJECT', 'candidate belongs to another project')
        generation_task, request, request_payload = self.generation_context(payload['request_id'])
        task = self._agent(action='generate-slide-images', target_refs=generation_task['target_refs'])
        if task['task_id'] != payload['request_id']:
            fail('REQUEST', 'candidate belongs to another generation request')
        if request['pack_ref'] != payload['pack_ref']:
            fail('REQUEST', 'candidate original pack differs from its generation context')
        pack = resolve_kind(self.kernel, payload['pack_ref'], 'image-led-input-pack')['payload']
        if (pack['slide_id'] != payload['slide_id'] or pack['page_order'] != payload['page_order']):
            fail('PAGE', 'candidate does not bind the requested page')
        response = self._current(payload['generation_response_ref'],
            'project/image-led/request/' + task['task_id'], 'image-led-generation-response')
        if (response.get('status') != 'completed' or response.get('pack_ref') != payload['pack_ref']
                or response.get('request_id') != task['task_id']
                or response.get('payload_sha256') != request['payload_sha256']
                or any(response.get(k) != request.get(k) for k in ('repair_diagnostic_ref', 'source_generation_response_ref'))):
            fail('RESPONSE', 'candidate needs a completed response for its exact input pack')
        raw = base64.b64decode(response['image_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != response['image_sha256']:
            fail('HASH', 'generation image bytes changed')
        from PIL import Image
        with Image.open(BytesIO(raw)) as im:
            im.load()
            if [im.width, im.height] != response['image_size']:
                fail('IMAGE', 'generation image dimensions changed')
            mime = Image.MIME.get(im.format)
            fitness = output_fitness(request_payload, [im.width, im.height])
            if fitness and fitness['status'] != 'eligible':
                fail('OUTPUT_FITNESS', 'original image dimensions or aspect ratio need revision before candidate selection')
        if mime not in {'image/png', 'image/jpeg', 'image/webp'}:
            fail('CAPABILITY_GAP', 'candidate image format is unsupported')
        copy = validate_selected_copy(payload['selected_copy'])
        from ai_ppt_studio.domains.materials.image_input_v2 import visible_copy, validate_used_materials
        if copy != visible_copy(pack):
            fail('COPY', 'candidate visible copy must equal the exact G0 input text, including whitespace')
        validate_used_materials(pack, payload['material_roles'])
        image = {'sha256': response['image_sha256'], 'data_base64': response['image_base64'],
            'mime_type': mime, 'width': response['image_size'][0], 'height': response['image_size'][1]}
        image_ref = str(self.kernel.artifacts.reference_for('image-led-image', image))
        candidate = {**deepcopy(payload), 'selected_copy': copy, 'image_ref': image_ref,
            'image_sha256': image['sha256'], 'common_rules_ref': pack['input_policy_ref'],
            'producer_task_id': task['task_id'], 'producer_role': task['role_id']}
        slot = PREFIX + 'candidate/' + pack['slide_id']
        image_slot = PREFIX + 'image/' + task['task_id']
        from ai_ppt_studio.application.image_led_native import upstream_keep
        keep = upstream_keep(self.kernel.load().artifact_heads)
        keep -= {PREFIX + 'selection', PREFIX + 'selection-proposal', PREFIX + 'selection-confirmation', PREFIX + 'regions'}
        require_revision(self.kernel, revision)
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.candidate-registered',
            gate_mutation=self._upstream_mutation(), artifact_updates={
                slot: ('image-led-candidate', candidate), image_slot: ('image-led-image', image)},
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep | {slot, image_slot}))
        return state.artifact_heads[slot]

    def current_candidate(self, ref):
        candidate = resolve_kind(self.kernel, ref, 'image-led-candidate')['payload']
        self._current(ref, PREFIX + 'candidate/' + candidate['slide_id'], 'image-led-candidate')
        pack = resolve_kind(self.kernel, candidate['pack_ref'], 'image-led-input-pack')['payload']
        request_payload = self.compile_request(candidate['pack_ref'])
        if (candidate['page_order'] != pack['page_order'] or candidate['slide_id'] != pack['slide_id']
                or candidate['common_rules_ref'] != pack['input_policy_ref']):
            fail('STALE', 'candidate identity is not the current input page')
        image = resolve_kind(self.kernel, candidate['image_ref'], 'image-led-image')['payload']
        if image['sha256'] != candidate['image_sha256'] or hashlib.sha256(
                base64.b64decode(image['data_base64'], validate=True)).hexdigest() != image['sha256']:
            fail('HASH', 'candidate image is no longer exact')
        from PIL import Image
        with Image.open(BytesIO(base64.b64decode(image['data_base64'], validate=True))) as decoded:
            decoded.load()
            fitness = output_fitness(request_payload, [decoded.width, decoded.height])
        if fitness and fitness['status'] != 'eligible':
            fail('OUTPUT_FITNESS', 'original image dimensions or aspect ratio need revision before selection')
        from ai_ppt_studio.domains.materials.image_input_v2 import visible_copy, validate_used_materials
        if validate_selected_copy(candidate['selected_copy']) != visible_copy(pack):
            fail('COPY', 'current candidate does not equal its exact requested visible identities')
        validate_used_materials(pack, candidate['material_roles'])
        return candidate

    def register_review(self, command_id, revision, payload):
        require_revision(self.kernel, revision)
        self.require_g0()
        exact(payload, {'artifact_type', 'project_id', 'target_ref', 'review_kind',
            'reviewer_kind', 'reviewer_role', 'checks'}, 'Image-led independent review')
        task = self._agent(action='review-visual-engineering', target_refs=[payload['target_ref']])
        if payload['project_id'] != self.kernel.project_id or payload['review_kind'] != 'candidate-source':
            fail('REVIEW', 'review project or stage is not supported')
        candidate = self.current_candidate(payload['target_ref'])
        if task['task_id'] == candidate['producer_task_id'] or task['role_id'] == candidate['producer_role']:
            fail('REVIEW', 'candidate cannot review itself')
        if payload['reviewer_role'] != task['role_id'] or payload['reviewer_kind'] != 'engineering':
            fail('REVIEW', 'review identity differs from its task')
        self._check_source_review(payload)
        value = {**deepcopy(payload), 'reviewer_task_id': task['task_id'], 'context_pack_ref': task['context_pack_ref'],
            'producer_task_id': candidate['producer_task_id']}
        slot = PREFIX + 'source-review/' + ArtifactReference.parse(payload['target_ref']).sha256
        from ai_ppt_studio.application.image_led_native import upstream_keep
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator
        keep = upstream_keep(self.kernel.load().artifact_heads) - {
            PREFIX + 'selection', PREFIX + 'selection-proposal', PREFIX + 'selection-confirmation'}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.source-reviewed', artifact_updates={slot: ('image-led-review', value)},
            gate_mutation=GateEvaluator(self.kernel).image_led_upstream_replaced(),
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep | {slot}))
        return state.artifact_heads[slot]

    @staticmethod
    def _check_source_review(value):
        checks = value.get('checks')
        if not isinstance(checks, list) or len(checks) != len(SOURCE_CHECKS):
            fail('REVIEW', 'source review needs each independent criterion')
        seen = set()
        for check in checks:
            exact(check, {'criterion', 'result', 'detail'}, 'source check')
            if check['criterion'] not in SOURCE_CHECKS or check['criterion'] in seen:
                fail('REVIEW', 'source review criterion is unknown or duplicated')
            seen.add(check['criterion'])
            if check['result'] not in {'passed', 'failed', 'not-established'}:
                fail('REVIEW', 'invalid source review result')
            text(check['detail'], 'detail')

    def current_source_review(self, candidate_ref, review_ref):
        value = self._current(review_ref, PREFIX + 'source-review/' + ArtifactReference.parse(candidate_ref).sha256, 'image-led-review')
        self._check_source_review(value)
        if value['target_ref'] != candidate_ref or any(c['result'] != 'passed' for c in value['checks']):
            fail('REVIEW', 'candidate source review is not passed for this exact image')
        task = self._current(self.kernel.load().artifact_heads.get('agent/task/' + value['reviewer_task_id'], ''),
            'agent/task/' + value['reviewer_task_id'], 'agent-task')
        if (task['status'] != 'completed' or task['result_refs'] != [review_ref]
                or task['target_refs'] != [candidate_ref] or task['role_id'] != 'visual-engineering-reviewer'
                or task['context_pack_ref'] != value['context_pack_ref']):
            fail('REVIEW', 'source review lacks its completed independent task lineage')
        return value

    def register_proposal(self, command_id, revision, payload):
        exact(payload, {'artifact_type', 'project_id', 'candidates'}, 'selection proposal')
        if (payload['project_id'] != self.kernel.project_id
                or not isinstance(payload['candidates'], list) or not payload['candidates']):
            fail('SELECTION', 'selection needs current reviewed candidate pages')
        blueprint_ref = self.kernel.load().artifact_heads.get('content/reading-blueprint', '')
        blueprint = self._current(blueprint_ref, 'content/reading-blueprint', 'reading-deck-blueprint')
        if len(payload['candidates']) != len(blueprint['slides']):
            fail('SELECTION', 'selection must cover every current blueprint page')
        self.proposal_slides(payload, confirmation_ref=None)
        from ai_ppt_studio.application.image_led_native import upstream_keep
        return self._register_input(command_id, revision, PREFIX + 'selection-proposal', deepcopy(payload),
            keep={s for s in upstream_keep(self.kernel.load().artifact_heads)
                if s not in {PREFIX + 'selection', PREFIX + 'selection-confirmation', PREFIX + 'regions'}})

    def proposal_slides(self, proposal, confirmation_ref):
        slides, seen, policies = [], set(), set()
        for row in proposal['candidates']:
            exact(row, {'candidate_ref', 'source_review_ref', 'accepted_deviations'}, 'selected candidate')
            candidate = self.current_candidate(row['candidate_ref'])
            self.current_source_review(row['candidate_ref'], row['source_review_ref'])
            if candidate['slide_id'] in seen:
                fail('SELECTION', 'selection contains the same page twice')
            seen.add(candidate['slide_id']); policies.add(candidate['common_rules_ref'])
            if not isinstance(row['accepted_deviations'], list):
                fail('SELECTION', 'accepted deviations must be explicit')
            differences = []
            for deviation in row['accepted_deviations']:
                exact(deviation, {'item_id', 'difference_kind', 'before', 'after'}, 'proposed deviation')
                differences.append({**deviation, 'candidate_ref': row['candidate_ref'],
                    'image_sha256': candidate['image_sha256'],
                    # A source review proves provenance only.  Until the user
                    # confirms the proposal there is no decision reference.
                    'decision_ref': confirmation_ref or ''})
            target = {'project_id': self.kernel.project_id, 'slide_id': candidate['slide_id'],
                'page_order': candidate['page_order'], 'candidate_ref': row['candidate_ref'],
                'target_image_ref': candidate['image_ref'], 'target_image_sha256': candidate['image_sha256'],
                'selected_copy_sha256': selected_copy_sha256(candidate['selected_copy']),
                'material_roles': candidate['material_roles'], 'common_rules_ref': candidate['common_rules_ref'],
                'accepted_deviations': differences, 'design_authority': 'finalized-image', 'conversion_mode': 'faithful-native'}
            validate_target_binding(target, expected_project_id=self.kernel.project_id,
                selected_copy=candidate['selected_copy'],
                allow_proposed_deviations=confirmation_ref is None)
            slides.append({'target_binding': target, 'selected_copy': deepcopy(candidate['selected_copy'])})
        orders = [s['target_binding']['page_order'] for s in slides]
        if len({s['selected_copy'].get('copy_version','v1') for s in slides}) != 1:
            fail('VERSION', 'one selection cannot mix visible-copy versions')
        if len(policies) != 1 or len(set(orders)) != len(orders) or orders != sorted(orders):
            fail('SELECTION', 'selected pages must share current common rules and explicit unique page order')
        policy = self._current(next(iter(policies)), PREFIX + 'input-policy', 'image-led-input-policy')
        blueprint = self._current(policy['reading_blueprint_ref'], 'content/reading-blueprint', 'reading-deck-blueprint')
        selected_pages = [(slide['target_binding']['slide_id'], slide['target_binding']['page_order'])
                          for slide in slides]
        current_pages = [(slide['slide_id'], slide['order']) for slide in blueprint['slides']]
        if selected_pages != current_pages:
            fail('SELECTION', 'selection must cover every current blueprint page in its exact order')
        return slides

    def selection_context(self, target_ref):
        from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
        proposal = self._current(target_ref, PREFIX + 'selection-proposal', 'image-led-selection-proposal')
        self.proposal_slides(proposal, confirmation_ref=None)
        return ScopedConfirmationPolicy(self.kernel).context(scope_kind='image-led-selection',
            scope_id=target_ref, source_version=target_ref, evidence_refs=[target_ref])

    def finalize(self, command_id, revision, proposal_ref, confirmed, consumptions):
        proposal = self._current(proposal_ref, PREFIX + 'selection-proposal', 'image-led-selection-proposal')
        confirmation_ref = str(self.kernel.artifacts.reference_for('image-led-selection-confirmation', confirmed))
        selection = {'project_id': self.kernel.project_id, 'proposal_ref': proposal_ref, 'confirmation_ref': confirmation_ref,
            'slides': self.proposal_slides(proposal, confirmation_ref)}
        from ai_ppt_studio.application.image_led_native import upstream_keep
        keep = upstream_keep(self.kernel.load().artifact_heads) - {PREFIX + 'regions'}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision, event_type='image-led.selection-confirmed',
            gate_mutation=self._upstream_mutation(),
            artifact_updates={PREFIX + 'selection-confirmation': ('image-led-selection-confirmation', confirmed),
                PREFIX + 'selection': ('image-led-selection', selection)},
            confirmation_consumptions=consumptions,
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep))
        return state.artifact_heads[PREFIX + 'selection']

    def current_selection(self, ref):
        selection = self._current(ref, PREFIX + 'selection', 'image-led-selection')
        if selection.get('selection_origin') == WORKING_ORIGIN:
            return self.current_working_selection(ref)
        proposal = self._current(selection['proposal_ref'], PREFIX + 'selection-proposal', 'image-led-selection-proposal')
        self.trusted_confirmation(selection['confirmation_ref'], kind='image-led-selection',
            artifact_kind='image-led-selection-confirmation', target_ref=selection['proposal_ref'])
        expected = {'project_id': self.kernel.project_id, 'proposal_ref': selection['proposal_ref'],
            'confirmation_ref': selection['confirmation_ref'],
            'slides': self.proposal_slides(proposal, selection['confirmation_ref'])}
        if selection != expected:
            fail('SELECTION', 'selection does not equal the trusted proposal and exact candidate images')
        return selection

    @staticmethod
    def _working_delegation(value):
        """An Agent work record, explicitly never a trusted user confirmation."""
        exact(value, {'source_type', 'verification', 'source_thread_id', 'instruction'}, 'working delegation')
        if (value['source_type'] != 'agent-recorded-user-instruction'
                or value['verification'] != 'agent-context-only'):
            fail('SELECTION', 'working delegation cannot claim verified user authority')
        thread_id = text(value['source_thread_id'], 'source_thread_id')
        try:
            if str(UUID(thread_id)) != thread_id:
                raise ValueError
        except ValueError:
            fail('SELECTION', 'working delegation requires its exact source thread identifier')
        if len(text(value['instruction'], 'instruction')) > 4096:
            fail('SELECTION', 'working instruction exceeds its bounded context record')
        return deepcopy(value)

    def _working_slides(self, proposal):
        exact(proposal, {'artifact_type', 'project_id', 'candidates'}, 'working selection proposal')
        if (proposal['artifact_type'] != 'image-led-selection-proposal'
                or proposal['project_id'] != self.kernel.project_id
                or not isinstance(proposal['candidates'], list) or len(proposal['candidates']) != 3):
            fail('SELECTION', 'working selection is limited to the exact C2 three-page proposal')
        for row in proposal['candidates']:
            exact(row, {'candidate_ref', 'source_review_ref', 'accepted_deviations'}, 'working candidate')
            if row['accepted_deviations'] != []:
                fail('SELECTION', 'working selection cannot accept deviations for the user')
        slides = self.proposal_slides(proposal, confirmation_ref=None)
        if [(slide['target_binding']['slide_id'], slide['target_binding']['page_order'])
                for slide in slides] != WORKING_PAGES:
            fail('SELECTION', 'working selection is limited to C2-S04/1, C2-S05/2, C2-S06/3')
        return slides

    def _working_value(self, proposal_ref, delegation_ref, proposal):
        return {'project_id': self.kernel.project_id, 'proposal_ref': proposal_ref,
            'delegation_ref': delegation_ref, 'scope': WORKING_SCOPE,
            'selection_origin': WORKING_ORIGIN, 'human_image_approval': 'NotEstablished',
            'final_human_acceptance': 'NotEstablished', 'slides': self._working_slides(proposal)}

    def register_working_selection(self, command_id, revision, payload):
        """Publish a bounded internal candidate choice without consuming user authority."""
        from ai_ppt_studio.application.review_commands import fingerprint, replay_ref
        from ai_ppt_studio.application.image_led_native import upstream_keep
        exact(payload, {'artifact_type', 'project_id', 'proposal_ref', 'delegation'}, 'working selection request')
        if payload['artifact_type'] != 'image-led-working-selection' or payload['project_id'] != self.kernel.project_id:
            fail('SELECTION', 'working selection requires its exact current project')
        self.require_g0()
        delegation = self._working_delegation(payload['delegation'])
        proposal = self._current(payload['proposal_ref'], PREFIX + 'selection-proposal', 'image-led-selection-proposal')
        # Validate everything, including the independently reviewed images and copy,
        # before the kernel creates any durable artifact.
        self._working_slides(proposal)
        semantic = fingerprint('image-led-working-selection', payload)
        replay = replay_ref(self.kernel, command_id, semantic, PREFIX + 'selection')
        if replay:
            self.current_working_selection(replay[0])
            return replay[0]
        require_revision(self.kernel, revision)
        record = {'project_id': self.kernel.project_id, 'proposal_ref': payload['proposal_ref'],
            'scope': WORKING_SCOPE, 'delegation': delegation}
        delegation_ref = str(self.kernel.artifacts.reference_for('image-led-working-delegation', record))
        selection = self._working_value(payload['proposal_ref'], delegation_ref, proposal)
        keep = upstream_keep(self.kernel.load().artifact_heads) - {PREFIX + 'regions', PREFIX + 'selection-confirmation'}
        keep |= {PREFIX + 'selection', PREFIX + 'working-delegation'}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.working-selection-recorded', gate_mutation=self._upstream_mutation(),
            artifact_updates={PREFIX + 'selection': ('image-led-selection', selection),
                PREFIX + 'working-delegation': ('image-led-working-delegation', record)},
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep),
            command_fingerprint=semantic)
        return state.artifact_heads[PREFIX + 'selection']

    def current_working_selection(self, ref):
        selection = self._current(ref, PREFIX + 'selection', 'image-led-selection')
        exact(selection, {'project_id', 'proposal_ref', 'delegation_ref', 'scope', 'selection_origin',
            'human_image_approval', 'final_human_acceptance', 'slides'}, 'working selection')
        record = self._current(selection['delegation_ref'], PREFIX + 'working-delegation', 'image-led-working-delegation')
        exact(record, {'project_id', 'proposal_ref', 'scope', 'delegation'}, 'working delegation record')
        self._working_delegation(record['delegation'])
        if (record['project_id'] != self.kernel.project_id or record['proposal_ref'] != selection['proposal_ref']
                or record['scope'] != WORKING_SCOPE):
            fail('SELECTION', 'working delegation does not bind this exact project and proposal')
        proposal = self._current(selection['proposal_ref'], PREFIX + 'selection-proposal', 'image-led-selection-proposal')
        if selection != self._working_value(selection['proposal_ref'], selection['delegation_ref'], proposal):
            fail('SELECTION', 'working selection differs from its exact reviewed candidates')
        return selection


class ExistingDeckSelectionService:
    """Source-bound Image 2 generation and AI selection, independent of G0/G3."""

    REQUEST = 'optimization/request/'
    RESPONSE = 'optimization/response/'
    REVIEW = 'optimization/source-review/'
    SELECTION = 'optimization/selection'
    RULES = 'optimization/common-rules'
    WITHDRAWN = 'optimization/withdrawn-request/'
    SUPERSEDED = 'optimization/superseded-request/'

    def __init__(self, kernel):
        self.kernel = kernel

    def _source(self):
        from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
        return ExistingDeckOptimizationService(self.kernel).current_source()

    def source_page(self, slide_id):
        pages = [row for row in self._source()['slides'] if row['slide_id'] == slide_id]
        if len(pages) != 1:
            fail('SOURCE', 'source page identity is missing or ambiguous')
        return pages[0]

    def _current(self, slot, kind):
        from ai_ppt_studio.application.artifact_guards import require_exact_ref
        ref = self.kernel.load().artifact_heads.get(slot, '')
        return ref, require_exact_ref(self.kernel, ref, slot, kind)['payload']

    def _request(self, request_id):
        ref, request = self._current(self.REQUEST + request_id, 'optimization-image-request')
        source = self._source()
        page = self.source_page(request['slide_id'])
        rules_ref, rules = self._current(self.RULES, 'image-led-input-policy')
        if request.get('request_origin') == 'historical-design-import/v1':
            provenance = request.get('provenance')
            if (request.get('source_ref') != self.kernel.load().artifact_heads.get('optimization/source')
                    or request.get('project_id') != self.kernel.project_id
                    or request.get('page_order') != page['page_order']
                    or request.get('visible_copy') != page['visible_copy']
                    or request.get('selected_copy') != self._copy(page, request.get('title_item_id'))
                    or request.get('media_refs') != page['media_refs']
                    or request.get('rules_ref') != rules_ref
                    or request.get('common_rules') != rules['common_rules']
                    or not self._valid_historical_provenance(provenance, source=source, page=page)):
                fail('STALE', 'historical design import differs from current exact source page, provenance, or common rules')
            return ref, request
        from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
        ExistingDeckOptimizationService(self.kernel).current_external_scope(page)
        relationship_constraints, relationship_instruction = self._relationship_constraints(
            page, request.get('title_item_id'), request.get('relationship_constraints', []))
        main_source_picture_object_id = self._main_screenshot_identity(
            page, request.get('layout_mode'), request.get('main_source_picture_object_id', ''))
        main_screenshot_spec = self._main_screenshot_spec(
            source, page, request.get('layout_mode'), main_source_picture_object_id)
        main_screenshot_instruction = self._main_screenshot_instruction(main_screenshot_spec)
        if (request['source_ref'] != self.kernel.load().artifact_heads.get('optimization/source')
                or request['project_id'] != self.kernel.project_id
                or request['page_order'] != page['page_order']
                or request['visible_copy'] != page['visible_copy']
                or request['payload']['confirmed_visible_copy'] != self._copy(page, request.get('title_item_id'))
                or request.get('required_visible_item_ids', []) != self._required_visible_items(
                    page, request.get('title_item_id'), request.get('required_visible_item_ids', []))[0]
                or self._required_visible_instruction(self._required_visible_items(
                    page, request.get('title_item_id'), request.get('required_visible_item_ids', []))[1])
                    not in request['payload']['page_goal']
                or request.get('relationship_constraints', []) != relationship_constraints
                or relationship_instruction not in request['payload']['page_goal']
                or request.get('main_source_picture_object_id', '') != main_source_picture_object_id
                or request.get('main_screenshot_spec', {}) != main_screenshot_spec
                or main_screenshot_instruction not in request['payload']['page_goal']
                or request['media_refs'] != page['media_refs']
                or request['rules_ref'] != rules_ref
                or request['payload']['common_rules'] != rules['common_rules']
                or hashlib.sha256(self._canonical(request['payload'])).hexdigest() != request['payload_sha256']):
            fail('STALE', 'generation request differs from current exact source page or common rules')
        if request['source_ref'] != self.kernel.load().artifact_heads['optimization/source']:
            fail('STALE', 'source deck changed')
        if request.get('layout_mode') == 'source-media-guided':
            materials, guidance = self._guided_source_media(self._source(), page)
            role_bindings, role_instruction = self._source_media_role_bindings(
                page, request.get('title_item_id'), guidance,
                request.get('source_media_role_bindings', []))
            if (request['payload']['materials'] != materials
                    or request.get('source_media_guidance') != guidance
                    or request.get('source_media_role_bindings', []) != role_bindings
                    or role_instruction not in request['payload']['page_goal']):
                fail('STALE', 'guided source media differs from current source bytes, geometry, or roles')
        elif (request.get('source_media_guidance') not in (None, [])
                or request.get('source_media_role_bindings') not in (None, [])
                or request['payload']['materials']):
            fail('STALE', 'non-guided request contains externally sent source media')
        return ref, request

    @staticmethod
    def _valid_historical_provenance(provenance, *, source, page):
        if not isinstance(provenance, dict) or set(provenance) != {
                'source_pptx_sha256', 'page_order', 'historical_request_id',
                'historical_request_sha256', 'historical_response_sha256',
                'historical_receiver', 'historical_model', 'historical_quality'}:
            return False
        import re
        digest = re.compile(r'^[0-9a-f]{64}$')
        return (provenance['source_pptx_sha256'] == source['source_pptx_sha256']
                and provenance['page_order'] == page['page_order']
                and isinstance(provenance['historical_request_id'], str)
                and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', provenance['historical_request_id']) is not None
                and isinstance(provenance['historical_request_sha256'], str)
                and digest.fullmatch(provenance['historical_request_sha256']) is not None
                and isinstance(provenance['historical_response_sha256'], str)
                and digest.fullmatch(provenance['historical_response_sha256']) is not None
                and provenance['historical_receiver'] == 'CRS'
                and provenance['historical_model'] == 'gpt-image-2'
                and provenance['historical_quality'] in {'low', 'medium', 'high'})

    @staticmethod
    def _canonical(value):
        from ai_ppt_studio.kernel.artifacts import canonical_json
        return canonical_json(value)

    @staticmethod
    def _copy(page, title_item_id):
        rows = page['visible_copy']
        titles = [row for row in rows if row['item_id'] == title_item_id]
        if len(titles) != 1 or not title_item_id:
            fail('COPY', 'Image 2 needs an explicitly bound source title item')
        if any(not item['text'].strip() for item in rows):
            fail('COPY', 'source page contains an unsupported empty visible text item')
        return {'title': titles[0]['text'], 'blocks': [
            {'block_id': row['item_id'], 'text': row['text'], 'identity': 'source-claim'}
            for row in rows if row['item_id'] != title_item_id]}

    def _materials(self, source, page):
        """Include actual embedded media bytes, never a path/declared digest."""
        from ai_ppt_studio.application.existing_deck_optimization import source_page_media
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        reader = MaterialSourceReader(self.kernel)
        raw = reader._read(reader._path(source['source_pptx_ref'], source_kind='file'))
        return source_page_media(raw, page)

    def _guided_source_media(self, source, page):
        """Replay exact media plus source geometry for a governed remote design input."""
        from ai_ppt_studio.application.existing_deck_optimization import (
            source_page_media, source_page_media_guidance)
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        reader = MaterialSourceReader(self.kernel)
        raw = reader._read(reader._path(source['source_pptx_ref'], source_kind='file'))
        materials = source_page_media(raw, page)
        guidance = source_page_media_guidance(raw, page)
        if ([item['atom_id'] for item in materials]
                != [item['object_id'] for item in guidance]
                or [item['content_sha256'] for item in materials]
                != [item['content_sha256'] for item in guidance]):
            fail('SOURCE', 'source media bytes and placement guidance disagree')
        return materials, guidance

    @staticmethod
    def _source_media_role_bindings(page, title_item_id, guidance, bindings):
        if bindings is None:
            bindings = []
        if not isinstance(bindings, list) or len(bindings) > 64:
            fail('MEDIA', 'source media role bindings need a bounded current-source list')
        if not bindings:
            return [], ''
        rows = {row['item_id']: row['text'] for row in page['visible_copy']}
        image_numbers = {row['object_id']: row['image_number'] for row in guidance}
        supplied = {}
        for binding in bindings:
            if (not isinstance(binding, dict)
                    or set(binding) != {'picture_object_id', 'text_item_ids'}):
                fail('MEDIA', 'source media role bindings need exact picture/text fields')
            picture_id = binding['picture_object_id']
            text_ids = binding['text_item_ids']
            if (not isinstance(picture_id, str) or picture_id not in image_numbers
                    or picture_id in supplied
                    or not isinstance(text_ids, list) or not 1 <= len(text_ids) <= 4
                    or any(not isinstance(value, str) or not value.strip() for value in text_ids)
                    or len(text_ids) != len(set(text_ids))
                    or title_item_id in text_ids or not set(text_ids).issubset(rows)):
                fail('MEDIA', 'each source image needs one exact current-page text role')
            supplied[picture_id] = list(text_ids)
        if set(supplied) != set(image_numbers):
            fail('MEDIA', 'source media role bindings must cover every guided source image exactly once')
        normalized, instructions = [], []
        for row in guidance:
            picture_id = row['object_id']
            text_ids = supplied[picture_id]
            normalized.append({'picture_object_id': picture_id, 'text_item_ids': text_ids})
            role = ' / '.join(rows[value].replace('\n', ' ') for value in text_ids)
            instructions.append(f'素材图片{row["image_number"]}的原稿角色只对应“{role}”；'
                                '必须放在该文字结构或这些文字之间的关系位置，'
                                '不得改配、复制到其他文字结构或作为通用图标。')
        instructions.append('没有绑定素材图片的文字结构不得新增、复制或挪用上述素材图片。')
        return normalized, ''.join(instructions)

    @staticmethod
    def _required_visible_items(page, title_item_id, item_ids):
        if item_ids is None:
            item_ids = []
        if (not isinstance(item_ids, list) or len(item_ids) > 32
                or any(not isinstance(value, str) or not value.strip() for value in item_ids)
                or len(set(item_ids)) != len(item_ids)):
            fail('COPY', 'required visible items need unique current source identities')
        if title_item_id in item_ids:
            fail('COPY', 'the source title cannot be repeated as a required body structure')
        requested = set(item_ids)
        current = {row['item_id'] for row in page['visible_copy']}
        if not requested.issubset(current):
            fail('COPY', 'required visible items must belong to the current source page')
        rows = [row for row in page['visible_copy'] if row['item_id'] in requested]
        return [row['item_id'] for row in rows], [row['text'] for row in rows]

    @staticmethod
    def _required_visible_instruction(texts):
        if not texts:
            return ''
        return ('本次修订中，以下原稿项目必须在画面主体中分别设置独立可见结构，'
                '必须逐项显示完整原文，不得仅隐含在说明段、合并省略或删除：'
                + '；'.join(texts) + '。')

    @staticmethod
    def _relationship_constraints(page, title_item_id, constraints):
        if constraints is None:
            constraints = []
        if not isinstance(constraints, list) or len(constraints) > 16:
            fail('COPY', 'relationship constraints need a bounded current-source list')
        rows = {row['item_id']: row['text'] for row in page['visible_copy']}
        normalized, instructions = [], []
        for constraint in constraints:
            if (not isinstance(constraint, dict)
                    or set(constraint) != {'kind', 'source_item_ids', 'target_item_ids'}):
                fail('COPY', 'relationship constraints need exact kind/source/target fields')
            kind = constraint['kind']
            source_ids = constraint['source_item_ids']
            target_ids = constraint['target_item_ids']
            for values in (source_ids, target_ids):
                if (not isinstance(values, list) or len(values) > 16
                        or any(not isinstance(value, str) or not value.strip() for value in values)
                        or len(values) != len(set(values))):
                    fail('COPY', 'relationship item identities must be unique bounded lists')
            if (not source_ids or set(source_ids) & set(target_ids)
                    or not set(source_ids + target_ids).issubset(rows)):
                fail('COPY', 'relationship items must belong to one current source page')
            if kind == 'overlapping-peers':
                if len(source_ids) < 2 or target_ids or title_item_id in source_ids:
                    fail('COPY', 'overlapping peers need at least two current body items')
                instructions.append('原稿关系约束：' + '、'.join(rows[value] for value in source_ids)
                    + '是并列叠加关系，必须用重叠或交叠构图表达，不得改成先后流程。')
            elif kind == 'dual-direction':
                if len(source_ids) != 2 or target_ids or title_item_id in source_ids:
                    fail('COPY', 'dual direction needs exactly two current body items')
                instructions.append('原稿关系约束：' + '、'.join(rows[value] for value in source_ids)
                    + '是对内/对外双向并列分支，必须使用独立双向结构同时从中央主体向两侧展开，'
                      '不得与其他业务项合并为同一排普通卡片，也不得改成单向流程或上下级关系。')
            elif kind == 'belongs-to':
                if len(target_ids) != 1 or title_item_id in source_ids:
                    fail('COPY', 'ownership needs body items and one current owner item')
                instructions.append('原稿关系约束：' + '、'.join(rows[value] for value in source_ids)
                    + '必须明确归属于“' + rows[target_ids[0]] + '”分区，不得跨列或悬空。')
            else:
                fail('COPY', 'unsupported source relationship kind')
            normalized.append({'kind': kind, 'source_item_ids': list(source_ids),
                               'target_item_ids': list(target_ids)})
        return normalized, ''.join(instructions)

    @staticmethod
    def _guided_media_instruction(guidance):
        rows = []
        for item in guidance:
            x, y, width, height = item['source_bbox']
            if item['source_role'] == 'full-bleed-background':
                role = ('是源页全幅背景；沿用其真实蓝紫品牌画面作为背景设计依据，'
                        '不得替换成城市、建筑、人物或其他示意照片')
            else:
                role = ('是源页定位素材；保持原图完整内容与长宽关系，不重绘其中的品牌文字或标识')
            rows.append(f'素材图片{item["image_number"]}{role}；其源页位置为'
                        f'x={x/100:.2f}%、y={y/100:.2f}%、宽={width/100:.2f}%、高={height/100:.2f}%。')
        return (''.join(rows) + '这些坐标只说明源页素材角色与层级，正文构图仍由你优化；'
                '不得新增素材池之外的照片、客户标识、建筑画面或概念插画。')

    @staticmethod
    def _main_screenshot_identity(page, layout_mode, value):
        if layout_mode != 'single-main-screenshot-focus':
            if value not in (None, ''):
                fail('MEDIA', 'main source screenshot identity requires the single-main layout mode')
            return ''
        current = {item['object_id'] for item in page['media_refs']}
        if not isinstance(value, str) or value not in current:
            fail('MEDIA', 'single-main layout needs one exact current-page source picture identity')
        return value

    def _main_screenshot_spec(self, source, page, layout_mode, object_id):
        if layout_mode != 'single-main-screenshot-focus':
            return {}
        matches = [item for item in self._materials(source, page)
                   if item['atom_id'] == object_id]
        if len(matches) != 1:
            fail('MEDIA', 'single-main screenshot dimensions must come from one exact source image')
        from math import gcd
        width, height = matches[0]['width'], matches[0]['height']
        divisor = gcd(width, height)
        return {'object_id': object_id, 'pixel_width': width, 'pixel_height': height,
                'aspect_ratio': f'{width // divisor}:{height // divisor}',
                'minimum_slot_width_percent': 50,
                'minimum_slot_height_percent': 50,
                'minimum_canvas_width_percent': 45,
                'minimum_canvas_height_percent': 35}

    @staticmethod
    def _main_screenshot_instruction(spec):
        if not spec:
            return ''
        return ('本页只设计一个大尺寸空白主截图版位，版位内无字、无照片、无图标；'
                '原稿确切业务主截图将在本地精确插入。其他源媒体不预留图片框；'
                f'源主截图长宽比为{spec["aspect_ratio"]}，空白版位须接近此比例；'
                f'空白版位自身宽度至少达到整页画布的{spec["minimum_slot_width_percent"]}%，'
                f'空白版位自身高度至少达到整页画布的{spec["minimum_slot_height_percent"]}%；'
                '优先采用左侧或中部主截图、右侧与底部承载能力关系和路径的构图，'
                '不得把主截图位压成横向浅条；'
                f'截图按contain完整插入后，实际显示宽度至少达到整页画布的'
                f'{spec["minimum_canvas_width_percent"]}%，实际显示高度至少达到整页画布的'
                f'{spec["minimum_canvas_height_percent"]}%，并成为全页主要视觉焦点；'
                '正文能力、层级关系和底部路径必须使用文字、连接器和结构完整呈现，'
                '不得改成图片槽，也不得因预留主截图位而省略。')

    @staticmethod
    def _disposition_review_required(request):
        return (request.get('request_origin') == 'historical-design-import/v1'
                or request.get('layout_mode') == 'single-main-screenshot-focus')

    @staticmethod
    def _validate_main_screenshot_disposition(request, page, disposition):
        if request.get('layout_mode') != 'single-main-screenshot-focus':
            return
        main = request.get('main_source_picture_object_id')
        all_media = {item['object_id'] for item in page['media_refs']}
        if (disposition.get('selected_source_picture_object_ids') != [main]
                or set(disposition.get('excluded_source_picture_object_ids', [])) != all_media - {main}):
            fail('COMPOSITION', 'single-main target must place only the bound screenshot and exclude other source media')

    def register_request(self, command_id, revision, *, slide_id, request_id, common_rules,
                         title_item_id=None, layout_mode='standard', required_visible_item_ids=None,
                         relationship_constraints=None, source_media_role_bindings=None,
                         main_source_picture_object_id=None):
        import re
        from ai_ppt_studio.application.existing_deck_optimization import SOURCE_SLOT
        require_revision(self.kernel, revision)
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', request_id):
            fail('REQUEST', 'generation request needs a stable, unique identifier')
        state = self.kernel.load()
        if (self.REQUEST + request_id in state.artifact_heads
                or self.WITHDRAWN + request_id in state.artifact_heads
                or self.SUPERSEDED + request_id in state.artifact_heads
                or self.SELECTION in state.artifact_heads):
            fail('REQUEST', 'request identity cannot be reused or modify a selected design')
        source = self._source()
        page = self.source_page(slide_id)
        from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
        scope = ExistingDeckOptimizationService(self.kernel).current_external_scope(page)
        from ai_ppt_studio.adapters.image2_crs import compile_body
        from ai_ppt_studio.adapters.image2_command import PROTOCOL
        rules = deepcopy(common_rules)
        rules_ref = state.artifact_heads.get(self.RULES, '')
        if rules_ref:
            _, existing = self._current(self.RULES, 'image-led-input-policy')
            if existing != {'project_id': self.kernel.project_id, 'common_rules': rules}:
                fail('RULES', 'one existing deck needs one immutable common design rule set')
        else:
            rules_ref = str(self.kernel.artifacts.reference_for('image-led-input-policy',
                {'project_id': self.kernel.project_id, 'common_rules': rules}))
        if any(slot.startswith(self.REQUEST) and resolve_kind(self.kernel, ref, 'optimization-image-request')['payload']['slide_id'] == slide_id
               for slot, ref in state.artifact_heads.items() if slot.startswith(self.REQUEST)):
            fail('REQUEST', 'a page already has an active request; use explicit revision/recovery')
        copy = self._copy(page, title_item_id)
        required_visible_item_ids, required_visible_texts = self._required_visible_items(
            page, title_item_id, required_visible_item_ids)
        relationship_constraints, relationship_instruction = self._relationship_constraints(
            page, title_item_id, relationship_constraints)
        from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
        media_count = len(source_real_media_refs(page))
        if layout_mode not in {'standard', 'blank-media-slots', 'client-logo-gallery-20',
                               'source-media-guided', 'single-main-screenshot-focus'} or (
                layout_mode in {'blank-media-slots', 'source-media-guided',
                                'single-main-screenshot-focus'} and not media_count):
            fail('REQUEST', 'unsupported source-media layout mode')
        main_source_picture_object_id = self._main_screenshot_identity(
            page, layout_mode, main_source_picture_object_id)
        main_screenshot_spec = self._main_screenshot_spec(
            source, page, layout_mode, main_source_picture_object_id)
        gallery_instruction = ''
        if layout_mode == 'client-logo-gallery-20':
            gallery_instruction = client_logo_gallery_instruction(len(copy['blocks']), media_count)
        media_instruction = (f'本页有{media_count}张真实原稿图片；只为它们逐一预留合适位置，'
            '不得用通用图标、模型绘制的品牌标识或概念插画替代需要保真的原图；'
            '图片字节只留在本地原生还原阶段，不发送给生图服务。') if media_count else ''
        if layout_mode == 'blank-media-slots':
            media_instruction += (f'本次只绘制{media_count}个空白、无字、无照片、无图标的可替换图片版位，'
                '按原页已有的分类排布，不产生示意照片、客户标识或新名称；之后在本地将原稿图片分别放入这些版位。')
        if layout_mode == 'single-main-screenshot-focus':
            media_instruction = self._main_screenshot_instruction(main_screenshot_spec)
        if gallery_instruction:
            media_instruction += gallery_instruction
        materials, guidance = [], []
        source_media_role_instruction = ''
        if layout_mode == 'source-media-guided':
            materials, guidance = self._guided_source_media(source, page)
            media_instruction = self._guided_media_instruction(guidance)
            source_media_role_bindings, source_media_role_instruction = self._source_media_role_bindings(
                page, title_item_id, guidance, source_media_role_bindings)
        elif source_media_role_bindings not in (None, []):
            fail('MEDIA', 'source media role bindings require the guided source-media route')
        else:
            source_media_role_bindings = []
        payload = {'receiver': scope['receiver'], 'model': scope['model'],
            'confirmed_visible_copy': copy,
            'page_goal': (f'为现有原稿第{page["page_order"]}页设计完整画面，保留原文和真实素材身份，不新增客户事实。'
                + media_instruction + source_media_role_instruction
                + self._required_visible_instruction(required_visible_texts)
                + relationship_instruction),
            'common_rules': rules, 'materials': materials}
        # Serializer checks the exact production protocol before any Runtime write.
        try:
            compile_body({'protocol': PROTOCOL, 'request_id': request_id, 'payload': payload},
                         model=scope['model'])
        except (ValueError, TypeError, KeyError) as error:
            fail('CAPABILITY_GAP', 'current source page cannot be safely compiled for CRS: ' + type(error).__name__)
        request = {'project_id': self.kernel.project_id, 'source_ref': state.artifact_heads[SOURCE_SLOT],
            'slide_id': slide_id, 'page_order': page['page_order'], 'title_item_id': title_item_id,
            'layout_mode': layout_mode, 'required_visible_item_ids': required_visible_item_ids,
            'relationship_constraints': relationship_constraints,
            'source_media_guidance': deepcopy(guidance),
            'source_media_role_bindings': deepcopy(source_media_role_bindings),
            'main_source_picture_object_id': main_source_picture_object_id,
            'main_screenshot_spec': deepcopy(main_screenshot_spec),
            'visible_copy': deepcopy(page['visible_copy']),
            'media_refs': deepcopy(page['media_refs']), 'rules_ref': rules_ref, 'request_id': request_id,
            'payload': payload, 'payload_sha256': hashlib.sha256(self._canonical(payload)).hexdigest()}
        updates = {self.REQUEST + request_id: ('optimization-image-request', request)}
        if not state.artifact_heads.get(self.RULES):
            updates[self.RULES] = ('image-led-input-policy', {'project_id': self.kernel.project_id, 'common_rules': rules})
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.image-request-registered', artifact_updates=updates)
        return committed.artifact_heads[self.REQUEST + request_id]

    def register_historical_design(self, command_id, revision, *, slide_id, request_id,
                                   common_rules, title_item_id, image_base64,
                                   image_sha256, provenance):
        """Register exact prior design bytes without sending a provider request."""
        import re
        from io import BytesIO
        from PIL import Image
        from ai_ppt_studio.application.existing_deck_optimization import SOURCE_SLOT
        require_revision(self.kernel, revision)
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', request_id):
            fail('REQUEST', 'historical import needs a stable, unique identifier')
        state = self.kernel.load()
        if (self.REQUEST + request_id in state.artifact_heads
                or self.RESPONSE + request_id in state.artifact_heads
                or self.WITHDRAWN + request_id in state.artifact_heads
                or self.SUPERSEDED + request_id in state.artifact_heads
                or self.SELECTION in state.artifact_heads):
            fail('REQUEST', 'historical request identity cannot be reused or modify a selected design')
        source = self._source()
        page = self.source_page(slide_id)
        if not self._valid_historical_provenance(provenance, source=source, page=page):
            fail('PROVENANCE', 'historical design provenance must bind the exact source, page, request, response, and model identity')
        rules = deepcopy(common_rules)
        rules_ref = state.artifact_heads.get(self.RULES, '')
        if rules_ref:
            _, existing = self._current(self.RULES, 'image-led-input-policy')
            if existing != {'project_id': self.kernel.project_id, 'common_rules': rules}:
                fail('RULES', 'one existing deck needs one immutable common design rule set')
        else:
            rules_ref = str(self.kernel.artifacts.reference_for('image-led-input-policy',
                {'project_id': self.kernel.project_id, 'common_rules': rules}))
        selected_copy = self._copy(page, title_item_id)
        if not isinstance(image_base64, str) or not image_base64:
            fail('IMAGE', 'historical design requires exact base64 image bytes')
        try:
            raw = base64.b64decode(image_base64, validate=True)
        except Exception:
            fail('IMAGE', 'historical design image base64 is invalid')
        if (not isinstance(image_sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', image_sha256)
                or hashlib.sha256(raw).hexdigest() != image_sha256):
            fail('HASH', 'historical design bytes differ from the declared image hash')
        try:
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                if decoded.format not in {'PNG', 'JPEG'} or getattr(decoded, 'n_frames', 1) != 1:
                    fail('IMAGE', 'historical design must be one PNG or JPEG frame')
                size = [decoded.width, decoded.height]
                mime = 'image/png' if decoded.format == 'PNG' else 'image/jpeg'
        except ContractValidationError:
            raise
        except Exception:
            fail('IMAGE', 'historical design bytes cannot be decoded')
        request = {'project_id': self.kernel.project_id, 'source_ref': state.artifact_heads[SOURCE_SLOT],
            'slide_id': slide_id, 'page_order': page['page_order'], 'title_item_id': title_item_id,
            'layout_mode': 'historical-design-import',
            'request_origin': 'historical-design-import/v1',
            'visible_copy': deepcopy(page['visible_copy']), 'selected_copy': selected_copy,
            'media_refs': deepcopy(page['media_refs']), 'rules_ref': rules_ref,
            'common_rules': rules, 'request_id': request_id, 'provenance': deepcopy(provenance)}
        request_ref = str(self.kernel.artifacts.reference_for('optimization-image-request', request))
        response = {'project_id': self.kernel.project_id, 'request_id': request_id,
            'request_ref': request_ref, 'request_origin': 'historical-design-import/v1',
            'status': 'completed',
            'response_id': 'historical-response-sha256:' + provenance['historical_response_sha256'],
            'image_base64': image_base64, 'image_sha256': image_sha256,
            'image_size': size, 'image_mime_type': mime,
            'provenance': deepcopy(provenance)}
        updates = {self.REQUEST + request_id: ('optimization-image-request', request),
            self.RESPONSE + request_id: ('optimization-image-response', response)}
        if not state.artifact_heads.get(self.RULES):
            updates[self.RULES] = ('image-led-input-policy',
                {'project_id': self.kernel.project_id, 'common_rules': rules})
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.historical-design-imported', artifact_updates=updates)
        return (committed.artifact_heads[self.REQUEST + request_id],
                committed.artifact_heads[self.RESPONSE + request_id])

    def withdraw_unsent_request(self, command_id, revision, *, request_id, reason):
        """Retire one never-sent request; keep its bytes in immutable history."""
        require_revision(self.kernel, revision)
        if not isinstance(reason, str) or not reason.strip():
            fail('REQUEST', 'withdrawing an unsent request needs a reason')
        state = self.kernel.load()
        slot = self.REQUEST + request_id
        if (not state.artifact_heads.get(slot) or state.artifact_heads.get(self.RESPONSE + request_id)
                or state.artifact_heads.get(self.WITHDRAWN + request_id)
                or self.SELECTION in state.artifact_heads):
            fail('REQUEST', 'only a current never-sent unselected request can be withdrawn')
        ref, request = self._request(request_id)
        record = {'project_id': self.kernel.project_id, 'request_id': request_id,
            'request_ref': ref, 'slide_id': request['slide_id'], 'reason': reason.strip(),
            'status': 'withdrawn-without-external-send'}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.unsent-image-request-withdrawn',
            artifact_updates={self.WITHDRAWN + request_id: ('optimization-request-withdrawal', record)},
            artifact_removals=(slot,))
        return committed.artifact_heads[self.WITHDRAWN + request_id]

    def supersede_unselected_response(self, command_id, revision, *, request_id, reason):
        """Keep a completed rejected design, allowing a new explicit design intent."""
        require_revision(self.kernel, revision)
        if not isinstance(reason, str) or not reason.strip():
            fail('REQUEST', 'design revision needs a concrete reason')
        state = self.kernel.load()
        request_slot, response_slot = self.REQUEST + request_id, self.RESPONSE + request_id
        if (not state.artifact_heads.get(request_slot) or not state.artifact_heads.get(response_slot)
                or state.artifact_heads.get(self.SUPERSEDED + request_id)
                or self.SELECTION in state.artifact_heads):
            fail('REQUEST', 'only a completed unselected design can be revised')
        request_ref = state.artifact_heads[request_slot]
        request = resolve_kind(
            self.kernel, request_ref, 'optimization-image-request')['payload']
        response_ref = state.artifact_heads[response_slot]
        response = resolve_kind(
            self.kernel, response_ref, 'optimization-image-response')['payload']
        if (request.get('project_id') != self.kernel.project_id
                or request.get('request_id') != request_id
                or not isinstance(request.get('slide_id'), str) or not request['slide_id']
                or response.get('status') != 'completed' or response.get('request_ref') != request_ref
                or response.get('request_id') != request_id):
            fail('REQUEST_UNKNOWN', 'started or unknown generation cannot be replaced with a new ID')
        review_slot = self.REVIEW + request_id
        review_ref = state.artifact_heads.get(review_slot)
        if review_ref:
            current_review_ref, review = self._current(
                review_slot, 'optimization-source-review')
            if (current_review_ref != review_ref
                    or review.get('project_id') != self.kernel.project_id
                    or review.get('request_id') != request_id
                    or review.get('response_ref') != response_ref):
                fail('REQUEST', 'current source review does not belong to this completed design')
        record = {'project_id': self.kernel.project_id, 'request_id': request_id,
            'request_ref': request_ref, 'response_ref': response_ref,
            'slide_id': request['slide_id'], 'reason': reason.strip(),
            'status': 'completed-design-revision-needed'}
        if review_ref:
            record['review_ref'] = review_ref
        removals = [request_slot, response_slot,
            'optimization/composition/' + request_id,
            'optimization/composed-image/' + request_id]
        if review_ref:
            removals.append(review_slot)
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.completed-design-superseded',
            artifact_updates={self.SUPERSEDED + request_id: ('optimization-design-supersession', record)},
            artifact_removals=tuple(removals))
        return committed.artifact_heads[self.SUPERSEDED + request_id]

    def recover_request(self, request_id):
        """Return the exact persisted request outcome without loading or calling a provider."""
        request_ref, _ = self._request(request_id)
        state = self.kernel.load()
        response_ref = state.artifact_heads.get(self.RESPONSE + request_id)
        if not response_ref:
            fail('REQUEST_UNKNOWN',
                 'recovery requires a persisted response for the original request identity')
        stored = resolve_kind(self.kernel, response_ref, 'optimization-image-response')['payload']
        if (stored.get('project_id') != self.kernel.project_id
                or stored.get('request_id') != request_id
                or stored.get('request_ref') != request_ref
                or stored.get('status') not in {'started', 'unknown', 'completed'}):
            fail('REQUEST_UNKNOWN', 'persisted response does not match the original request identity')
        if stored['status'] == 'completed':
            _, _, response_ref, stored = self._response(request_id)
        return response_ref, stored

    def execute_request(self, request_id, *, transport):
        from io import BytesIO
        from PIL import Image
        from ai_ppt_studio.domains.visual.image_output import output_fitness
        ref, request = self._request(request_id)
        if request.get('request_origin') == 'historical-design-import/v1':
            fail('REQUEST', 'historical design imports are completed local candidates and cannot execute a provider request')
        from ai_ppt_studio.adapters.image2_crs import SUNBURST_MODEL
        if (request['payload'].get('receiver'), request['payload'].get('model')) != (
                'CRS', SUNBURST_MODEL):
            fail('CAPABILITY_GAP',
                 'historical Image 2 request cannot be sent through the current Sunburst route')
        if request.get('layout_mode') == 'source-media-guided':
            expected_materials, expected_guidance = self._guided_source_media(
                self._source(), self.source_page(request['slide_id']))
            if (request['payload']['materials'] != expected_materials
                    or request.get('source_media_guidance') != expected_guidance):
                fail('STALE', 'guided source media differs from the exact current PPTX page')
        elif request['payload']['materials']:
            fail('UNAUTHORIZED', 'this existing-deck layout mode cannot send original source image bytes')
        slot = self.RESPONSE + request_id
        state = self.kernel.load()
        if state.artifact_heads.get(slot):
            old_ref, old = self._current(slot, 'optimization-image-response')
            if old.get('status') == 'completed':
                return old_ref
            fail('REQUEST_UNKNOWN', 'an unknown/started request must be recovered by its original identity')
        if not callable(getattr(transport, 'generate', None)):
            fail('CAPABILITY_GAP', 'a configured CRS Image 2 transport is required')
        if callable(getattr(transport, 'preflight', None)):
            transport.preflight(request['payload'])
        claim = {'project_id': self.kernel.project_id, 'request_id': request_id,
            'request_ref': ref, 'status': 'started'}
        self.kernel.commit(command_id='optimization-start-' + request_id,
            expected_revision=state.revision, event_type='optimization.image-request-started',
            artifact_updates={slot: ('optimization-image-response', claim)})
        try:
            received = transport.generate(request_id=request_id, payload=deepcopy(request['payload']))
            exact(received, {'response_id', 'image_bytes'} |
                  ({'provider_observation'} if 'provider_observation' in received else set()), 'CRS response')
            raw = received['image_bytes']
            if not isinstance(raw, bytes) or not raw:
                fail('RESPONSE', 'actual image bytes required')
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                if decoded.format not in {'PNG', 'JPEG'} or getattr(decoded, 'n_frames', 1) != 1:
                    fail('RESPONSE', 'unsupported or animated target image')
                size = [decoded.width, decoded.height]
                mime = 'image/png' if decoded.format == 'PNG' else 'image/jpeg'
            fitness = output_fitness(request['payload'], size)
            if fitness and fitness['status'] != 'eligible':
                fail('RESPONSE', 'generated original image is not fit for selection')
            text(received['response_id'], 'response_id')
            observation = {}
            if 'provider_observation' in received:
                from ai_ppt_studio.domains.visual.image_output import validate_provider_observation
                observation = {'provider_observation': validate_provider_observation(
                    received['provider_observation'], receiver='CRS', model=request['payload']['model'])}
            terminal = {**claim, 'status': 'completed', 'response_id': received['response_id'],
                'image_base64': base64.b64encode(raw).decode('ascii'),
                'image_sha256': hashlib.sha256(raw).hexdigest(), 'image_size': size,
                'image_mime_type': mime, **observation}
        except Exception:
            terminal = {**claim, 'status': 'unknown', 'failure_reason': 'provider-or-image-validation-failed'}
        current = self.kernel.load()
        if current.artifact_heads.get(slot) != str(self.kernel.artifacts.reference_for('optimization-image-response', claim)):
            fail('REQUEST_CONFLICT', 'generation claim changed before result was saved')
        committed = self.kernel.commit(command_id='optimization-finish-' + request_id,
            expected_revision=current.revision, event_type='optimization.image-response-preserved',
            artifact_updates={slot: ('optimization-image-response', terminal)})
        return committed.artifact_heads[slot]

    def _response(self, request_id):
        request_ref, request = self._request(request_id)
        response_ref, response = self._current(self.RESPONSE + request_id, 'optimization-image-response')
        if (response.get('status') != 'completed' or response.get('project_id') != self.kernel.project_id
                or response.get('request_ref') != request_ref or response.get('request_id') != request_id):
            fail('RESPONSE', 'source-bound generation is not complete')
        raw = base64.b64decode(response['image_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != response['image_sha256']:
            fail('HASH', 'actual provider image bytes differ from recorded hash')
        return request_ref, request, response_ref, response

    def register_local_media_composition(self, command_id, revision, *, request_id, placements):
        """Insert exact source media locally before a design can become a target."""
        from ai_ppt_studio.application.local_media_composition import (
            compose_original_media, composition_disposition, compositor_version)
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        require_revision(self.kernel, revision)
        state = self.kernel.load()
        slot = 'optimization/composition/' + request_id
        if slot in state.artifact_heads or self.SELECTION in state.artifact_heads:
            fail('COMPOSITION', 'a composed design cannot be replaced or alter selected output')
        request_ref, request, response_ref, response = self._response(request_id)
        source = self._source()
        page = self.source_page(request['slide_id'])
        reader = MaterialSourceReader(self.kernel)
        raw_source = reader._read(reader._path(source['source_pptx_ref'], source_kind='file'))
        base_image = base64.b64decode(response['image_base64'], validate=True)
        result = compose_original_media(response_bytes=base_image, source_pptx_bytes=raw_source,
            page=page, placements=placements, layout_mode=request['layout_mode'])
        disposition = composition_disposition(placements, request['layout_mode'])
        self._validate_main_screenshot_disposition(request, page, disposition)
        digest = hashlib.sha256(result).hexdigest()
        image = {'sha256': digest, 'data_base64': base64.b64encode(result).decode('ascii'),
            'mime_type': 'image/png', 'width': response['image_size'][0],
            'height': response['image_size'][1]}
        image_ref = str(self.kernel.artifacts.reference_for('image-led-image', image))
        composition = {'project_id': self.kernel.project_id,
            'source_ref': state.artifact_heads['optimization/source'],
            'request_ref': request_ref, 'response_ref': response_ref,
            'request_id': request_id, 'slide_id': page['slide_id'],
            'page_order': page['page_order'],
            'compositor_version': compositor_version(request['layout_mode']),
            'placements': deepcopy(placements), **deepcopy(disposition),
            'base_image_sha256': response['image_sha256'],
            'target_image_ref': image_ref, 'target_image_sha256': digest,
            'source_media_local_only': True}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.local-source-media-composed',
            artifact_updates={slot: ('optimization-local-composition', composition),
                'optimization/composed-image/' + request_id: ('image-led-image', image)})
        return committed.artifact_heads[slot]

    def _current_composition(self, request_id, *, request_ref, response_ref, page):
        from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
        from ai_ppt_studio.application.local_media_composition import (
            compose_original_media, composition_disposition, compositor_version)
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        slot = 'optimization/composition/' + request_id
        composition_ref, composition = self._current(slot, 'optimization-local-composition')
        response = self._current(self.RESPONSE + request_id, 'optimization-image-response')[1]
        image_ref, image = self._current('optimization/composed-image/' + request_id, 'image-led-image')
        if (not source_real_media_refs(page)
                or composition.get('source_ref') != self.kernel.load().artifact_heads['optimization/source']
                or composition.get('project_id') != self.kernel.project_id
                or composition.get('request_ref') != request_ref
                or composition.get('response_ref') != response_ref
                or composition.get('slide_id') != page['slide_id']
                or composition.get('page_order') != page['page_order']
                or composition.get('request_id') != request_id
                or composition.get('compositor_version') != compositor_version(
                    self._request(request_id)[1]['layout_mode'])
                or composition.get('base_image_sha256') != response['image_sha256']
                or composition.get('source_media_local_only') is not True
                or composition.get('target_image_ref') != image_ref
                or composition.get('target_image_sha256') != image['sha256']
                or {key: composition.get(key) for key in (
                    'selected_source_picture_object_ids',
                    'excluded_source_picture_object_ids')} != composition_disposition(
                        composition.get('placements'), self._request(request_id)[1]['layout_mode'])):
            fail('COMPOSITION', 'local material target differs from its source or provider design')
        self._validate_main_screenshot_disposition(
            self._request(request_id)[1], page,
            {key: composition.get(key) for key in (
                'selected_source_picture_object_ids', 'excluded_source_picture_object_ids')})
        source = self._source()
        reader = MaterialSourceReader(self.kernel)
        raw_source = reader._read(reader._path(source['source_pptx_ref'], source_kind='file'))
        expected = compose_original_media(response_bytes=base64.b64decode(response['image_base64'], validate=True),
            source_pptx_bytes=raw_source, page=page, placements=composition['placements'],
            layout_mode=self._request(request_id)[1]['layout_mode'])
        if (hashlib.sha256(expected).hexdigest() != image['sha256']
                or base64.b64decode(image['data_base64'], validate=True) != expected):
            fail('COMPOSITION', 'local media target is not the reproducible composed image')
        return composition_ref, composition, image_ref, image

    def review_response(self, command_id, revision, *, request_id, reviewer_task_id,
                        producer_task_id, checks):
        require_revision(self.kernel, revision)
        request_ref, request, response_ref, _ = self._response(request_id)
        from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
        page = self.source_page(request['slide_id'])
        has_original_media = bool(source_real_media_refs(page))
        historical = request.get('request_origin') == 'historical-design-import/v1'
        guided_candidate = request.get('layout_mode') == 'source-media-guided' or historical
        has_composition = bool(self.kernel.load().artifact_heads.get(
            'optimization/composition/' + request_id))
        uses_composition = has_original_media and (has_composition or not guided_candidate)
        guided_media = has_original_media and guided_candidate and not uses_composition
        review_targets = [request_ref, response_ref] if guided_media else [response_ref]
        composition_binding = {}
        if uses_composition:
            composition_ref, composition, image_ref, image = self._current_composition(
                request_id, request_ref=request_ref, response_ref=response_ref, page=page)
            review_targets = (([request_ref, response_ref] if historical else [response_ref])
                + [composition_ref, image_ref])
            composition_binding = {'composition_ref': composition_ref,
                'target_image_ref': image_ref, 'target_image_sha256': image['sha256'],
                'compositor_version': composition['compositor_version'],
                'selected_source_picture_object_ids':
                    composition['selected_source_picture_object_ids'],
                'excluded_source_picture_object_ids':
                    composition['excluded_source_picture_object_ids']}
        from ai_ppt_studio.application.project_service import ProjectCommandService
        try:
            task = ProjectCommandService(self.kernel).require_active_agent_task(reviewer_task_id)
        except Exception:
            fail('REVIEW', 'source check requires a current governed review task')
        if (task['action_type'] != 'review-visual-engineering'
                or task['role_id'] != 'visual-engineering-reviewer'
                or task['target_refs'] != review_targets
                or task.get('status') != 'queued'
                or task.get('result_refs') != []):
            fail('REVIEW', 'source check task must target the exact provider response and composed visual')
        expected_checks = (PATCHED_SOURCE_CHECKS if uses_composition and self._disposition_review_required(request) else
            COMPOSED_SOURCE_CHECKS if uses_composition else
            REMOTE_SOURCE_CHECKS if guided_media else SOURCE_CHECKS)
        if (not reviewer_task_id or producer_task_id != request_id
                or reviewer_task_id == request_id
                or set(checks) != expected_checks
                or any(value != 'passed' for value in checks.values())):
            fail('REVIEW', 'source checks require the exact generation request identity and a separate review task')
        slot = self.REVIEW + request_id
        if slot in self.kernel.load().artifact_heads:
            fail('REVIEW', 'current response review cannot be replaced without a new request')
        review = {'project_id': self.kernel.project_id, 'request_id': request_id,
            'response_ref': response_ref, 'reviewer_task_id': reviewer_task_id,
            'generation_request_id': request_id, 'checks': deepcopy(checks),
            'review_authority': 'agent-recorded-internal-check', **composition_binding}
        review_ref = str(self.kernel.artifacts.reference_for(
            'optimization-source-review', review))
        completed = {**task, 'status': 'completed',
            'progress': {'stage': 'completed', 'done': 1, 'total': 1},
            'result_refs': [review_ref], 'error': None}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.image-internal-review', artifact_updates={
                slot: ('optimization-source-review', review),
                'agent/task/active': ('agent-task', completed),
                'agent/task/' + reviewer_task_id: ('agent-task', completed)})
        return committed.artifact_heads[slot]

    def select_internal(self, command_id, revision, *, selections, reviewer_task_id):
        from ai_ppt_studio.domains.visual.image_led import validate_target_binding, selected_copy_sha256
        require_revision(self.kernel, revision)
        source = self._source()
        source_ref = self.kernel.load().artifact_heads['optimization/source']
        if (self.SELECTION in self.kernel.load().artifact_heads or not reviewer_task_id
                or not isinstance(selections, list) or len(selections) != len(source['slides'])):
            fail('SELECTION', 'internal selection must cover every source page exactly once')
        from ai_ppt_studio.application.project_service import ProjectCommandService
        try:
            task = ProjectCommandService(self.kernel).require_active_agent_task(reviewer_task_id)
        except Exception:
            fail('SELECTION', 'internal image choice requires a current governed selector task')
        if (task['action_type'] != 'review-visual-aesthetic'
                or task['role_id'] != 'visual-aesthetic-reviewer'
                or task['target_refs'] != [source_ref]):
            fail('SELECTION', 'selector must target this exact source deck')
        slides, updates, producers = [], {}, set()
        for page, row in zip(source['slides'], selections):
            from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
            has_original_media = bool(source_real_media_refs(page))
            request_preview = self._request(row.get('request_id', ''))[1] if isinstance(row, dict) else {}
            historical = request_preview.get('request_origin') == 'historical-design-import/v1'
            guided_candidate = request_preview.get('layout_mode') == 'source-media-guided' or historical
            has_composition = bool(self.kernel.load().artifact_heads.get(
                'optimization/composition/' + row.get('request_id', ''))) if isinstance(row, dict) else False
            needs_composition = has_original_media and (has_composition or not guided_candidate)
            guided_media = has_original_media and guided_candidate and not needs_composition
            exact(row, {'slide_id', 'request_id', 'review_ref'} |
                ({'composition_ref'} if needs_composition else set()), 'internal selection row')
            if row['slide_id'] != page['slide_id']:
                fail('SELECTION', 'selected image belongs to another source page or order')
            request_ref, request, response_ref, response = self._response(row['request_id'])
            if request['slide_id'] != page['slide_id'] or request['page_order'] != page['page_order']:
                fail('SELECTION', 'generation request is for a different source slide')
            review_ref, review = self._current(self.REVIEW + row['request_id'], 'optimization-source-review')
            if (row['review_ref'] != review_ref or review['response_ref'] != response_ref
                    or review['review_authority'] != 'agent-recorded-internal-check'
                    or set(review['checks']) != (PATCHED_SOURCE_CHECKS
                        if needs_composition and self._disposition_review_required(request_preview) else COMPOSED_SOURCE_CHECKS
                        if needs_composition else REMOTE_SOURCE_CHECKS
                        if guided_media else SOURCE_CHECKS)
                    or any(value != 'passed' for value in review['checks'].values())
                    or review['reviewer_task_id'] == reviewer_task_id):
                fail('SELECTION', 'candidate does not have a separate current source check')
            reviewer = self.kernel.load().artifact_heads.get('agent/task/' + review['reviewer_task_id'], '')
            if not reviewer:
                fail('REVIEW', 'source-check task is missing')
            review_task = resolve_kind(self.kernel, reviewer, 'agent-task')['payload']
            if (review_task['status'] != 'completed'
                    or review_task['action_type'] != 'review-visual-engineering'
                    or review_task['result_refs'] != [review_ref]
                    or review_task['target_refs'] != ([request_ref, response_ref] if guided_media else
                        ([request_ref, response_ref] if historical else [response_ref])
                        + [row['composition_ref'], review['target_image_ref']]
                        if needs_composition else [response_ref])):
                fail('REVIEW', 'source-check task has no completed review result')
            producers.add(row['request_id'])
            if needs_composition:
                composition_ref, composition, image_ref, image = self._current_composition(
                    row['request_id'], request_ref=request_ref, response_ref=response_ref, page=page)
                if (row['composition_ref'] != composition_ref
                        or review.get('composition_ref') != composition_ref
                        or review.get('target_image_ref') != image_ref
                        or review.get('target_image_sha256') != image['sha256']):
                    fail('COMPOSITION', 'internal choice must use the exact local-media target')
            else:
                image = {'sha256': response['image_sha256'], 'data_base64': response['image_base64'],
                    'mime_type': response['image_mime_type'], 'width': response['image_size'][0],
                    'height': response['image_size'][1]}
                image_ref = str(self.kernel.artifacts.reference_for('image-led-image', image))
            candidate = {'project_id': self.kernel.project_id, 'source_ref': source_ref,
                'request_ref': request_ref, 'response_ref': response_ref, 'review_ref': review_ref,
                'slide_id': page['slide_id'], 'page_order': page['page_order'],
                'image_ref': image_ref, 'image_sha256': image['sha256'],
                'selection_status': 'internally-selected'}
            if needs_composition:
                candidate['composition_ref'] = composition_ref
            candidate_ref = str(self.kernel.artifacts.reference_for('image-led-candidate', candidate))
            copy = {'items': [dict(item_id=row['item_id'], kind='text', text=row['text'],
                    role='title' if row['item_id'] == request['title_item_id'] else 'body')
                for row in page['visible_copy']]}
            selected_media_ids = (set(composition['selected_source_picture_object_ids'])
                if needs_composition else {item['object_id'] for item in source_real_media_refs(page)})
            roles = [{'atom_id': item['object_id'], 'source_ref': source_ref,
                'content_sha256': item['sha256'], 'use': 'real-material'}
                for item in source_real_media_refs(page) if item['object_id'] in selected_media_ids]
            target = {'project_id': self.kernel.project_id, 'slide_id': page['slide_id'],
                'page_order': page['page_order'], 'candidate_ref': candidate_ref,
                'target_image_ref': image_ref, 'target_image_sha256': image['sha256'],
                'selected_copy_sha256': selected_copy_sha256(copy), 'material_roles': roles,
                'common_rules_ref': request['rules_ref'], 'accepted_deviations': [],
                'design_authority': 'finalized-image', 'conversion_mode': 'faithful-native'}
            validate_target_binding(target, expected_project_id=self.kernel.project_id,
                expected_slide_id=page['slide_id'], expected_page_order=page['page_order'], selected_copy=copy)
            slides.append({'target_binding': target, 'selected_copy': copy})
            updates['optimization/candidate/' + page['slide_id']] = ('image-led-candidate', candidate)
            updates['optimization/image/' + page['slide_id']] = ('image-led-image', image)
        if len(producers) != len(selections):
            fail('SELECTION', 'the same generation response cannot be used for two pages')
        selection = {'project_id': self.kernel.project_id, 'source_ref': source_ref,
            'selection_origin': 'internally-selected', 'selector_task_id': reviewer_task_id,
            'human_image_approval': 'NotEstablished', 'slides': slides}
        updates[self.SELECTION] = ('image-led-selection', selection)
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.internal-selection-recorded', artifact_updates=updates)
        return committed.artifact_heads[self.SELECTION]

    def current_selection(self, ref=None):
        from ai_ppt_studio.domains.visual.image_led import validate_target_binding
        current_ref, selection = self._current(self.SELECTION, 'image-led-selection')
        if ref is not None and ref != current_ref:
            fail('STALE', 'internal selection is not current')
        source = self._source()
        if (selection.get('project_id') != self.kernel.project_id
                or selection.get('source_ref') != self.kernel.load().artifact_heads['optimization/source']
                or selection.get('selection_origin') != 'internally-selected'
                or selection.get('human_image_approval') != 'NotEstablished'
                or len(selection.get('slides', [])) != len(source['slides'])):
            fail('STALE', 'internal selection is not bound to current source deck')
        selection_task_ref = self.kernel.load().artifact_heads.get('agent/task/' + selection['selector_task_id'], '')
        if not selection_task_ref:
            fail('SELECTION', 'internal image choice has no governed task record')
        selection_task = resolve_kind(self.kernel, selection_task_ref, 'agent-task')['payload']
        if (selection_task['status'] != 'completed'
                or selection_task['action_type'] != 'review-visual-aesthetic'
                or selection_task['target_refs'] != [selection['source_ref']]
                or selection_task['result_refs'] != [current_ref]):
            fail('SELECTION', 'internal image choice has no completed task result')
        from ai_ppt_studio.application.existing_deck_optimization import source_real_media_refs
        for page, row in zip(source['slides'], selection['slides']):
            target, copy = row['target_binding'], row['selected_copy']
            validate_target_binding(target, expected_project_id=self.kernel.project_id,
                expected_slide_id=page['slide_id'], expected_page_order=page['page_order'], selected_copy=copy)
            candidate = resolve_kind(self.kernel, target['candidate_ref'], 'image-led-candidate')['payload']
            request_id = resolve_kind(self.kernel, candidate['request_ref'],
                'optimization-image-request')['payload']['request_id']
            current_request_ref, request, response_ref, response = self._response(request_id)
            expected = [dict(item_id=item['item_id'], kind='text', text=item['text'],
                role='title' if item['item_id'] == request['title_item_id'] else 'body') for item in page['visible_copy']]
            if copy['items'] != expected:
                fail('COPY', 'selected image copy differs from source deck')
            heads = self.kernel.load().artifact_heads
            if (heads.get(self.REVIEW + request_id) != candidate['review_ref']
                    or heads.get('optimization/candidate/' + page['slide_id']) != target['candidate_ref']
                    or heads.get('optimization/image/' + page['slide_id']) != target['target_image_ref']
                    or candidate['image_ref'] != target['target_image_ref']
                    or request['rules_ref'] != target['common_rules_ref']):
                fail('STALE', 'current source review, selected candidate, image, or rules changed')
            review = resolve_kind(self.kernel, candidate['review_ref'], 'optimization-source-review')['payload']
            task_ref = heads.get('agent/task/' + review['reviewer_task_id'], '')
            task = resolve_kind(self.kernel, task_ref, 'agent-task')['payload']
            media_is_present = bool(source_real_media_refs(page))
            historical = request.get('request_origin') == 'historical-design-import/v1'
            guided_candidate = request.get('layout_mode') == 'source-media-guided' or historical
            has_composition = bool(heads.get('optimization/composition/' + request_id))
            needs_composition = media_is_present and (has_composition or not guided_candidate)
            guided_media = media_is_present and guided_candidate and not needs_composition
            if (review['response_ref'] != response_ref
                    or task['status'] != 'completed' or task['result_refs'] != [candidate['review_ref']]
                    or task['target_refs'] != ([current_request_ref, response_ref] if guided_media else
                        ([current_request_ref, response_ref] if historical else [response_ref])
                        + [candidate.get('composition_ref'), target['target_image_ref']]
                        if needs_composition else [response_ref])
                    or set(review['checks']) != (PATCHED_SOURCE_CHECKS
                        if needs_composition and self._disposition_review_required(request) else COMPOSED_SOURCE_CHECKS
                        if needs_composition else REMOTE_SOURCE_CHECKS
                        if guided_media else SOURCE_CHECKS)
                    or any(value != 'passed' for value in review['checks'].values())):
                fail('REVIEW', 'source review no longer proves this exact selected image')
            expected_media_ids = {item['object_id'] for item in source_real_media_refs(page)}
            if needs_composition:
                composition_ref, composition, composed_ref, _ = self._current_composition(
                    request_id, request_ref=current_request_ref, response_ref=response_ref, page=page)
                expected_media_ids = set(composition['selected_source_picture_object_ids'])
            expected_roles = [{'atom_id': item['object_id'], 'source_ref': selection['source_ref'],
                'content_sha256': item['sha256'], 'use': 'real-material'}
                for item in source_real_media_refs(page) if item['object_id'] in expected_media_ids]
            if (candidate['source_ref'] != selection['source_ref']
                    or current_request_ref != candidate['request_ref']
                    or request['slide_id'] != page['slide_id']
                    or candidate['response_ref'] != response_ref
                    or candidate['image_sha256'] != target['target_image_sha256']
                    or candidate['slide_id'] != page['slide_id']
                    or target['material_roles'] != expected_roles):
                fail('SELECTION', 'target binding differs from reviewed source image or material roles')
            if needs_composition:
                if (candidate.get('composition_ref') != composition_ref
                        or target['target_image_ref'] != composed_ref
                        or review.get('composition_ref') != composition_ref
                        or review.get('target_image_ref') != composed_ref
                        or review.get('target_image_sha256') != target['target_image_sha256']):
                    fail('COMPOSITION', 'selected visual target lacks its source-media composition')
            elif (candidate.get('composition_ref') or review.get('composition_ref')
                    or response['image_sha256'] != target['target_image_sha256']):
                fail('COMPOSITION', 'a source-free or guided page must use its exact provider image')
            image = resolve_kind(self.kernel, target['target_image_ref'], 'image-led-image')['payload']
            if image['sha256'] != target['target_image_sha256'] or hashlib.sha256(
                    base64.b64decode(image['data_base64'], validate=True)).hexdigest() != image['sha256']:
                fail('HASH', 'selected image bytes changed')
        return selection
