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
WORKING_SCOPE = 'CHG-IL-C2-three-page-working-candidate'
WORKING_ORIGIN = 'delegated-ai-working-selection'
WORKING_PAGES = [('C2-S04', 1), ('C2-S05', 2), ('C2-S06', 3)]


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
        if payload['project_id'] != self.kernel.project_id or not isinstance(payload['candidates'], list) or len(payload['candidates']) != 3:
            fail('SELECTION', 'C2 selection needs exactly three current candidate pages')
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
