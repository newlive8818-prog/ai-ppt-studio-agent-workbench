"""Image-led lifecycle; all writes remain revision-safe kernel transactions."""
from __future__ import annotations
import hashlib
from copy import deepcopy

from ai_ppt_studio.application.artifact_guards import require_revision, resolve_kind
from ai_ppt_studio.application.review_commands import fingerprint, replay_ref
from ai_ppt_studio.domains.materials.image_input_contracts import (
    validate_scope, validate_policy, validate_pack, authorize_atom, fail, digest)
from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.domains.visual.image_output import output_fitness, validate_provider_observation

PREFIX = 'visual/image-led/'
WORKFLOW_SLOT = 'project/visual-workflow'


def is_image_led(kernel):
    ref = kernel.load().artifact_heads.get(WORKFLOW_SLOT)
    if not ref:
        return False
    payload = resolve_kind(kernel, ref, 'visual-workflow')['payload']
    if payload != {'visual_workflow': 'image-led/v1', 'project_id': kernel.project_id}:
        fail('ROUTE', 'persistent visual workflow is invalid')
    return True


def reject_legacy_production(kernel):
    if is_image_led(kernel):
        fail('ROUTE', 'Image-led project requires the finalized-image production path')


class ImageLedService:
    def __init__(self, kernel):
        self.kernel = kernel

    def require_g0(self, *, mutable=True):
        state = self.kernel.load()
        if state.gate_status.get('G0') != 'passed':
            raise GateBlockedError('image-led', ('G0-not-passed',))
        if mutable and state.gate_status.get('G2') == 'passed':
            raise GateBlockedError('image-led', ('formal-visual-reopen-required',))
        return state

    def commit_artifact(self, command_id, expected_revision, payload):
        artifact_type = payload.get('artifact_type')
        if artifact_type == 'image-led-content-diagnostic':
            from ai_ppt_studio.application.image_led_repair import ImageLedRepairService
            return ImageLedRepairService(self.kernel).register_diagnostic(command_id, expected_revision, payload)
        if artifact_type == 'image-led-working-selection':
            from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
            return ImageLedSelectionService(self.kernel).register_working_selection(
                command_id, expected_revision, payload)
        if artifact_type in {'image-led-build-result', 'image-led-result-review', 'image-led-native-diagnostic-result'}:
            from ai_ppt_studio.application.image_led_results import ImageLedResultService
            method = {'image-led-build-result': 'register_build_result', 'image-led-result-review': 'register_review',
                      'image-led-native-diagnostic-result': 'register_diagnostic_result'}[artifact_type]
            return getattr(ImageLedResultService(self.kernel), method)(command_id, expected_revision, payload)
        if artifact_type in {'image-led-region-inventory', 'image-led-region-review'}:
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            method = 'register_regions' if artifact_type == 'image-led-region-inventory' else 'register_region_review'
            return getattr(ImageLedNativeService(self.kernel), method)(command_id, expected_revision, payload)
        if artifact_type == 'image-led-input-policy':
            return self.register_policy(command_id, expected_revision, payload)
        if artifact_type == 'image-led-input-pack':
            return self.register_pack(command_id, expected_revision, payload)
        if artifact_type in {'image-led-candidate', 'image-led-review', 'image-led-selection-proposal'}:
            from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
            methods = {'image-led-candidate': 'register_candidate', 'image-led-review': 'register_review',
                       'image-led-selection-proposal': 'register_proposal'}
            return getattr(ImageLedSelectionService(self.kernel), methods[artifact_type])(command_id, expected_revision, payload)
        if artifact_type != 'image-led-authorization-scope':
            fail('SCHEMA', 'unrecognized Image-led artifact type')
        normalized = validate_scope(payload, self.kernel.project_id)
        slot = PREFIX + 'scope'
        semantic = fingerprint('image-led-register-scope', normalized)
        replay = replay_ref(self.kernel, command_id, semantic, slot)
        if replay:
            return replay[0]
        require_revision(self.kernel, expected_revision)
        self.require_g0()
        state = self.kernel.commit(command_id=command_id, expected_revision=expected_revision,
            event_type='image-led.scope-registered', artifact_updates={
                slot: (artifact_type, normalized),
                WORKFLOW_SLOT: ('visual-workflow', {
                    'visual_workflow': 'image-led/v1', 'project_id': self.kernel.project_id})},
            command_fingerprint=semantic)
        return state.artifact_heads[slot]

    def trusted_confirmation(self, confirmation_ref, *, kind, target_ref, artifact_kind=None):
        """Recheck the immutable statement and its kernel-owned consumption binding."""
        from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
        from ai_ppt_studio.domains.materials.image_input_contracts import sha
        value = resolve_kind(self.kernel, confirmation_ref, artifact_kind or kind)['payload']
        expected = {'project_id': self.kernel.project_id, 'scope_kind': kind,
                    'scope_id': target_ref, 'source_version': target_ref,
                    'evidence_refs': [target_ref]}
        if any(value.get(k) != v for k, v in expected.items()):
            fail('CONFIRMATION', 'confirmation scope does not bind the exact target')
        revision = value.get('challenge_revision')
        if type(revision) is not int or not 0 <= revision < self.kernel.load().revision:
            fail('CONFIRMATION', 'invalid confirmation revision')
        body = {**expected, 'project_root': str(self.kernel.project_root),
                'challenge_revision': revision}
        if value.get('challenge_id') != ScopedConfirmationPolicy.challenge_id(body):
            fail('CONFIRMATION', 'confirmation challenge is not authentic to its scope')
        action, message = value.get('user_action_ref'), value.get('user_message_ref')
        identity_type = value.get('confirmation_identity_type')
        if not ((identity_type == 'host-action' and action and not message)
                or (identity_type == 'verified-message' and message and not action)):
            fail('CONFIRMATION', 'confirmation lacks one exclusive trusted identity')
        sha(value.get('host_assertion_sha256'))
        identity = action or message
        if (self.kernel.confirmation_owner(identity) != kind + ':' + target_ref
                or self.kernel.confirmation_artifact_binding(identity) != confirmation_ref):
            fail('CONFIRMATION', 'confirmation lacks atomic consumption binding')
        return value

    def authorized_scope(self, scope_ref, authorization_ref):
        """Reusing authorization never consumes another user identity or writes state."""
        scope = validate_scope(resolve_kind(self.kernel, scope_ref,
            'image-led-authorization-scope')['payload'], self.kernel.project_id)
        grant = self.trusted_confirmation(authorization_ref,
            kind='image-led-authorization', target_ref=scope_ref)
        ledger_ref = self.kernel.load().artifact_heads.get('kernel/confirmation-consumptions', '')
        ledger = resolve_kind(self.kernel, ledger_ref, 'confirmation-consumption-ledger')['payload']
        # Iterate the immutable ledger even when transient visual heads were cleared.
        from ai_ppt_studio.kernel.references import ArtifactReference
        for ref in set(ledger.get('artifact_bindings', {}).values()):
            if ArtifactReference.parse(ref).kind != 'image-led-revocation':
                continue
            revoked = resolve_kind(self.kernel, ref, 'image-led-revocation')['payload']
            if revoked.get('scope_id') != scope_ref:
                continue
            revoked = self.trusted_confirmation(ref, kind='image-led-revocation', target_ref=scope_ref)
            if revoked['challenge_revision'] > grant['challenge_revision']:
                fail('REVOKED', 'the material scope was revoked after this grant')
        return scope

    def _current(self, ref, slot, kind):
        from ai_ppt_studio.application.artifact_guards import require_exact_ref
        return require_exact_ref(self.kernel, ref, slot, kind)['payload']

    def check_policy(self, payload):
        self.require_g0(mutable=False)
        if not is_image_led(self.kernel):
            fail('ROUTE', 'register the Image-led scope before preparing input')
        policy = validate_policy(payload, self.kernel.project_id)
        blueprint = self._current(policy['reading_blueprint_ref'], 'content/reading-blueprint', 'reading-deck-blueprint')
        evidence = self._current(policy['evidence_book_ref'], 'content/evidence-book', 'presales-evidence-book')
        g0 = self._current(policy['g0_ref'], 'gate/G0/confirmation', 'g0-confirmation')
        self._current(policy['release_target_policy_ref'], 'release/target-policy', 'release-target-policy')
        material_ref = self.kernel.load().artifact_heads.get('materials', '')
        if material_ref != policy['material_inventory_ref']:
            fail('SOURCE', 'policy is not bound to current material inventory')
        if material_ref:
            resolve_kind(self.kernel, material_ref, 'material-inventory')
        if (blueprint.get('source_version') != policy['source_version']
                or blueprint.get('evidence_book_ref') != policy['evidence_book_ref']
                or evidence.get('material_inventory_ref') != material_ref
                or evidence.get('source_version') != policy['source_version']
                or g0.get('reading_blueprint_ref') != policy['reading_blueprint_ref']):
            fail('STALE', 'current content, evidence, G0 and input policy disagree')
        from ai_ppt_studio.application.material_finding_service import MaterialFindingService
        MaterialFindingService(self.kernel).validate_evidence(evidence)
        scope = self.authorized_scope(policy['authorization_scope_ref'], policy['authorization_ref'])
        if any(policy[k] != scope[k] for k in ('receiver', 'model')):
            fail('UNAUTHORIZED', 'input receiver or model is outside the material grant')
        return policy, scope, blueprint

    def _register_input(self, command_id, revision, slot, payload, *, keep):
        self.require_g0()
        from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator
        semantic = fingerprint('image-led-register-input', payload)
        replay = replay_ref(self.kernel, command_id, semantic, slot)
        if replay:
            return replay[0]
        require_revision(self.kernel, revision)
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.input-registered',
            gate_mutation=GateEvaluator(self.kernel).image_led_upstream_replaced(),
            artifact_updates={slot: (payload['artifact_type'], payload)},
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep | {slot}),
            command_fingerprint=semantic)
        return state.artifact_heads[slot]

    def register_policy(self, command_id, revision, payload):
        policy, _, _ = self.check_policy(payload)
        return self._register_input(command_id, revision, PREFIX + 'input-policy', policy,
            keep={PREFIX + key for key in ('scope', 'authorization', 'revocation')})

    def register_pack(self, command_id, revision, payload):
        pack = validate_pack(payload, self.kernel.project_id)
        self.compile_request_payload(pack)
        from ai_ppt_studio.application.image_led_native import upstream_keep
        keep = upstream_keep(self.kernel.load().artifact_heads)
        keep -= {PREFIX + 'selection', PREFIX + 'selection-proposal',
                 PREFIX + 'candidate/' + pack['slide_id'], PREFIX + 'regions'}
        return self._register_input(command_id, revision, PREFIX + 'pack/' + pack['slide_id'], pack, keep=keep)

    def compile_request_payload(self, payload, *, with_binding=False):
        """Resolve everything before returning the exact in-memory external payload."""
        pack = validate_pack(payload, self.kernel.project_id)
        policy = self._current(pack['input_policy_ref'], PREFIX + 'input-policy', 'image-led-input-policy')
        policy, scope, blueprint = self.check_policy(policy)
        slides = [(i,s) for i,s in enumerate(blueprint['slides']) if s['slide_id'] == pack['slide_id'] and s['order'] == pack['page_order']]
        if len(slides) != 1:
            fail('PAGE', 'pack is not the current requested slide')
        slide_index, slide = slides[0]
        expected_copy = {'title': slide['neutral_title'], 'blocks': slide['visible_copy_blocks']}
        from ai_ppt_studio.domains.materials.image_input_v2 import (
            PACK_VERSION, PAYLOAD_VERSION, visible_copy, derive_semantics, customer_strings, validate_semantics, aliases)
        v2 = pack.get('pack_version') == PACK_VERSION
        actual_copy = {k:pack['confirmed_visible_copy'][k] for k in ('title','blocks')} if v2 else pack['confirmed_visible_copy']
        if actual_copy != expected_copy or pack['page_goal'] != slide['page_task']:
            fail('COPY', 'input text is not the exact G0 visible copy and page goal')
        # G0 copy/goal remain blueprint-derived, not a second material inventory.
        # Hashing exact UTF-8 permits one scope for all pages and repeated calls.
        for value in ([] if v2 else [expected_copy['title'], pack['page_goal']] + [b['text'] for b in expected_copy['blocks']]):
            authorize_atom(scope, {'source_sha256': hashlib.sha256(value.encode('utf-8')).hexdigest(),
                'source_location': {'kind': 'whole-source'}, 'use': 'content-source'})
        materials = []
        if pack['atoms']:
            from ai_ppt_studio.application.image_led_materials import ImageLedMaterialResolver
            resolver = ImageLedMaterialResolver(self.kernel)
            for atom in pack['atoms']:
                authorize_atom(scope, atom)
            materials = resolver.resolve_atoms(pack['atoms'], inventory_ref=policy['material_inventory_ref'],
                evidence_ref=policy['evidence_book_ref'], slide=slide)
        result = {'receiver': policy['receiver'], 'model': policy['model'],
            'confirmed_visible_copy': deepcopy(expected_copy), 'page_goal': pack['page_goal'],
            'common_rules': deepcopy(policy['common_rules']), 'materials': materials}
        binding = None
        if v2:
            evidence = self._current(policy['evidence_book_ref'], 'content/evidence-book', 'presales-evidence-book')
            semantics, provenance = derive_semantics(pack, slide, evidence,
                blueprint_ref=policy['reading_blueprint_ref'], evidence_ref=policy['evidence_book_ref'], slide_index=slide_index)
            result.update(payload_version=PAYLOAD_VERSION, confirmed_visible_copy=visible_copy(pack),
                          required_atom_ids=[], non_visible_semantics=semantics)
            validate_semantics(semantics, result['confirmed_visible_copy'], materials,
                expected_fact_item_ids=[b['block_id'] for b in expected_copy['blocks']])
            for value in customer_strings(result):
                authorize_atom(scope, {'source_sha256': hashlib.sha256(value.encode('utf-8')).hexdigest(),
                    'source_location': {'kind':'whole-source'}, 'use':'content-source'})
            text_aliases, material_aliases = aliases(result['confirmed_visible_copy'], materials)
            binding = {'blueprint_ref':policy['reading_blueprint_ref'], 'evidence_book_ref':policy['evidence_book_ref'],
                'slide_id':pack['slide_id'], 'page_order':pack['page_order'], 'entries':provenance,
                'text_aliases':text_aliases, 'material_aliases':material_aliases, 'payload_sha256':digest(result)}
        return (result, binding) if with_binding else result

    def compile_request(self, pack_ref, *, with_binding=False):
        from ai_ppt_studio.kernel.references import ArtifactReference
        if ArtifactReference.parse(pack_ref).kind == 'image-led-content-diagnostic':
            from ai_ppt_studio.application.image_led_repair import ImageLedRepairService
            return ImageLedRepairService(self.kernel).compile_repair(pack_ref, with_binding=with_binding)
        pack = resolve_kind(self.kernel, pack_ref, 'image-led-input-pack')['payload']
        self._current(pack_ref, PREFIX + 'pack/' + pack['slide_id'], 'image-led-input-pack')
        return self.compile_request_payload(pack, with_binding=with_binding)

    def request_identity(self, target_ref):
        from ai_ppt_studio.kernel.references import ArtifactReference
        if ArtifactReference.parse(target_ref).kind == 'image-led-content-diagnostic':
            value = resolve_kind(self.kernel, target_ref, 'image-led-content-diagnostic')['payload']
            return {'pack_ref': value['pack_ref'], 'repair_diagnostic_ref': target_ref,
                    'source_generation_response_ref': value['generation_response_ref']}
        return {'pack_ref': target_ref}

    @staticmethod
    def request_target(request):
        """Historical identity needs no current grant or current diagnostic head."""
        from ai_ppt_studio.kernel.references import ArtifactReference
        repair = request.get('payload', {}).get('payload_version') == 'image-led-image2-repair-input/v1'
        if repair:
            for key, kind in (('repair_diagnostic_ref', 'image-led-content-diagnostic'),
                              ('source_generation_response_ref', 'image-led-generation-response')):
                if ArtifactReference.parse(request.get(key, '')).kind != kind:
                    fail('REQUEST', 'repair request lacks its exact source identity')
            return request['repair_diagnostic_ref']
        if any(k in request for k in ('repair_diagnostic_ref', 'source_generation_response_ref')):
            fail('REQUEST', 'normal request cannot carry repair identity')
        return request.get('pack_ref')

    def generation_context(self, task_id):
        self.require_g0()
        from ai_ppt_studio.application.project_service import ProjectCommandService
        task = ProjectCommandService(self.kernel).require_active_agent_task(task_id)
        if task.get('action_type') != 'generate-slide-images' or task.get('status') != 'queued':
            fail('REQUEST', 'generation needs the exact current queued Image 2 task')
        context = self._current(task['context_pack_ref'], 'agent/context/' + task_id, 'context-pack')
        request = context.get('layers', {}).get('image_led_request', {})
        target = self.request_target(request)
        if (request.get('request_id') != task_id or task['target_refs'] != [target]
                or context.get('project_id') != self.kernel.project_id
                or context.get('project_revision') != task['input_revision']):
            fail('REQUEST', 'generation task and input context disagree')
        payload, binding = self.compile_request(target, with_binding=True)
        if any(request.get(k) != v for k, v in self.request_identity(target).items()):
            fail('REQUEST', 'generation source and pack identities disagree')
        if binding is not None and request.get('semantic_binding') != binding:
            fail('STALE', 'generation semantic binding changed after queuing')
        if binding is None and 'semantic_binding' in request:
            fail('VERSION', 'legacy generation cannot carry a v2 semantic binding')
        if request.get('payload_sha256') != digest(payload) or request.get('payload') != payload:
            fail('STALE', 'generation input changed after queuing')
        return task, request, payload

    def generation_intent(self, *, target_refs, instructions, intent='', request_id=''):
        """Resolve public intent before any production preflight or new write."""
        import re
        from ai_ppt_studio.application.project_service import ProjectCommandService
        if intent not in {'', 'new', 'recover'}:
            fail('REQUEST_INTENT', 'generation intent must be new or recover')
        from ai_ppt_studio.kernel.references import ArtifactReference
        if (not intent and any(ArtifactReference.parse(ref).kind == 'image-led-content-diagnostic' for ref in target_refs)):
            fail('REQUEST_INTENT', 'repair requires an explicit new or recover request ID')
        if intent:
            if not isinstance(request_id, str) or not re.fullmatch(r'(?!active$)[A-Za-z0-9_-]{1,128}', request_id):
                fail('REQUEST_INTENT', 'new and recover require a durable generation request ID')
        elif request_id:
            fail('REQUEST_INTENT', 'a supplied request ID requires an explicit intent')
        else:
            request_id = digest({'operation': 'image-led-default-intent/v1',
                'project_id': self.kernel.project_id, 'target_refs': target_refs,
                'instructions': instructions.strip()})
        if intent != 'recover' and len(target_refs) != 1:
            fail('REQUEST', 'generation requires one exact input pack')
        state = self.kernel.load()
        ref = state.artifact_heads.get('agent/task/' + request_id)
        if not ref:
            if intent == 'recover':
                fail('REQUEST', 'the original generation request is unavailable')
            return request_id, None
        task = ProjectCommandService(self.kernel).resolve_agent_task(request_id)
        if task.get('action_type') != 'generate-slide-images':
            fail('REQUEST', 'the request ID belongs to another kind of task')
        if ((intent != 'recover' or target_refs) and task['target_refs'] != target_refs
                or (intent != 'recover' or instructions) and task['instructions'] != instructions.strip()):
            fail('REQUEST_INTENT', 'the original request ID cannot be rebound to different input')
        return request_id, task

    def generation_receipt(self, task):
        """Read historical output independently of current production eligibility."""
        task_id = task['task_id']
        context = resolve_kind(self.kernel, task['context_pack_ref'], 'context-pack')['payload']
        request = context.get('layers', {}).get('image_led_request', {})
        if (context.get('project_id') != self.kernel.project_id
                or request.get('request_id') != task_id
                or task['target_refs'] != [self.request_target(request)]
                or request.get('payload_sha256') != digest(request.get('payload'))):
            fail('REQUEST', 'generation history has inconsistent request identity')
        ref = self.kernel.load().artifact_heads.get('project/image-led/request/' + task_id)
        value = (resolve_kind(self.kernel, ref, 'image-led-generation-response')['payload'] if ref else
            {'project_id': self.kernel.project_id, 'request_id': task_id, 'status': 'pending',
             'pack_ref': request['pack_ref'], 'payload_sha256': request['payload_sha256'],
             **{k: request[k] for k in ('repair_diagnostic_ref', 'source_generation_response_ref') if k in request}})
        if (value.get('project_id') != self.kernel.project_id or value.get('request_id') != task_id
                or value.get('pack_ref') != request['pack_ref']
                or value.get('payload_sha256') != request['payload_sha256']):
            fail('REQUEST', 'generation response does not match its original input')
        if any(value.get(k) != request.get(k) for k in ('repair_diagnostic_ref', 'source_generation_response_ref')):
            fail('REQUEST', 'generation response does not match its original repair source')
        usability = {'status': 'unavailable', 'candidate_eligible': False,
                     'checked_revision': self.kernel.load().revision}
        if value.get('status') == 'completed':
            from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
            try:
                _, _, payload = self.generation_context(task_id)
                if self.kernel.load().revision == usability['checked_revision']:
                    fitness = output_fitness(payload, value['image_size'])
                    if fitness and fitness['status'] == 'needs-revision':
                        usability.update(status='needs-revision', output_fitness=fitness)
                    else:
                        usability.update(status='current', candidate_eligible=True)
            except (ArtifactReferenceError, ContractValidationError, GateBlockedError):
                usability['status'] = 'stale'
        return ref, value, usability

    def execute_generation(self, task_id, *, transport):
        """Send a checked snapshot once; uncertain outcomes retain query identity."""
        import base64
        import uuid
        from ai_ppt_studio.domains.materials.image_input_contracts import exact, text
        validated_revision = self.kernel.load().revision
        task, request, payload = self.generation_context(task_id)
        slot = 'project/image-led/request/' + task_id
        previous_ref = self.kernel.load().artifact_heads.get(slot)
        if previous_ref:
            previous = resolve_kind(self.kernel, previous_ref, 'image-led-generation-response')['payload']
            if previous.get('status') == 'completed':
                return previous_ref
            fail('REQUEST_UNKNOWN', 'query the existing request identity before any new generation')
        if not callable(getattr(transport, 'generate', None)):
            fail('CAPABILITY_GAP', 'an Image 2 transport is required')
        response = {'project_id': self.kernel.project_id, 'request_id': task_id,
            'pack_ref': request['pack_ref'], 'payload_sha256': digest(payload), 'status': 'started',
            'claim_id': uuid.uuid4().hex,
            **{k: request[k] for k in ('repair_diagnostic_ref', 'source_generation_response_ref') if k in request}}
        started = self.kernel.commit(command_id='image-led-start-' + task_id,
            expected_revision=validated_revision, event_type='image-led.request-started',
            artifact_updates={slot: ('image-led-generation-response', response)})
        claim = resolve_kind(self.kernel, started.artifact_heads[slot], 'image-led-generation-response')['payload']
        if claim.get('claim_id') != response['claim_id']:
            fail('REQUEST_DUPLICATE', 'the existing request claim belongs to another execution')
        failure_stage = 'subprocess'
        try:
            received = transport.generate(request_id=task_id, payload=deepcopy(payload))
            failure_stage = 'adapter-receipt'
            has_observation = isinstance(received, dict) and 'provider_observation' in received
            exact(received, {'response_id', 'image_bytes'} | ({'provider_observation'} if has_observation else set()),
                  'Image 2 transport response')
            text(received['response_id'], 'response_id')
            observed = ({'provider_observation': validate_provider_observation(received['provider_observation'],
                receiver=payload['receiver'], model=payload['model'])} if has_observation else {})
            raw = received['image_bytes']
            if not isinstance(raw, bytes) or not raw:
                fail('RESPONSE', 'Image 2 response must contain actual image bytes')
            # Actual image decoding is repeated when a candidate is registered.
            from io import BytesIO
            from PIL import Image
            failure_stage = 'image-decode'
            with Image.open(BytesIO(raw)) as decoded:
                mime = Image.MIME.get(decoded.format)
                if mime not in {'image/png', 'image/jpeg', 'image/webp'} or getattr(decoded, 'n_frames', 1) != 1:
                    fail('RESPONSE', 'Image 2 response must be a supported single-frame image')
                decoded.load()
                dimensions = [decoded.width, decoded.height]
            fitness = output_fitness(payload, dimensions)
            response = {**response, 'status': 'completed', 'response_id': received['response_id'],
                'image_sha256': hashlib.sha256(raw).hexdigest(),
                'image_base64': base64.b64encode(raw).decode('ascii'), 'image_size': dimensions,
                'image_mime_type': mime, **observed,
                **({'output_fitness': fitness} if fitness is not None else {})}
        except Exception as error:
            # No provider text/credentials are stored, and no candidate is promoted.
            from ai_ppt_studio.adapters.image2_diagnostics import command_failure, diagnostic, error_category
            safe = command_failure(error) or diagnostic(failure_stage, {
                'subprocess': 'subprocess-failed', 'adapter-receipt': 'adapter-receipt-invalid',
                'image-decode': 'image-decode-failed'}[failure_stage])
            response = {**response, 'status': 'unknown', 'error_category': error_category(error),
                'failure_diagnostic': safe}
        return self.preserve_generation_response(response)

    def preserve_generation_response(self, response):
        """CAS only the original claim's receipt; never replay the external call.

        Project revisions may advance while the provider is working. Each local
        retry validates the same request/claim and uses that read's revision,
        so unrelated writes survive and a competing receipt cannot be replaced.
        Current production eligibility is deliberately checked at candidate intake.
        """
        from ai_ppt_studio.errors import RevisionConflictError
        value = deepcopy(response)
        if value.get('status') not in {'completed', 'unknown'}:
            fail('RESPONSE', 'only a terminal response can be preserved')
        slot = 'project/image-led/request/' + value['request_id']
        identity = ('project_id', 'request_id', 'claim_id', 'pack_ref', 'payload_sha256')
        semantic = fingerprint('image-led-preserve-response', value)
        while True:
            state = self.kernel.load()
            reference = state.artifact_heads.get(slot)
            if not reference:
                fail('REQUEST', 'the original generation claim is unavailable')
            current = resolve_kind(self.kernel, reference, 'image-led-generation-response')['payload']
            if (value.get('project_id') != self.kernel.project_id
                    or any(not value.get(key) or value.get(key) != current.get(key) for key in identity)
                    or any(value.get(k) != current.get(k) for k in ('repair_diagnostic_ref', 'source_generation_response_ref'))):
                fail('REQUEST_CLAIM', 'returned response does not belong to the original claim')
            if current.get('status') != 'started':
                if current == value:
                    return reference
                fail('RESPONSE_CONFLICT', 'a different terminal response is already preserved')
            try:
                finished = self.kernel.commit(
                    command_id='image-led-response-' + value['request_id'],
                    expected_revision=state.revision, event_type='image-led.request-returned',
                    artifact_updates={slot: ('image-led-generation-response', value)},
                    command_fingerprint=semantic)
            except RevisionConflictError:
                continue
            exact_ref = str(self.kernel.artifacts.reference_for('image-led-generation-response', value))
            if finished.artifact_heads.get(slot) != exact_ref:
                fail('RESPONSE_CONFLICT', 'the committed response is not this exact return')
            return exact_ref

    def confirmation_context(self, target_ref, choice='approved'):
        from ai_ppt_studio.application.artifact_guards import require_exact_ref
        from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
        from ai_ppt_studio.kernel.references import ArtifactReference
        if ArtifactReference.parse(target_ref).kind == 'image-led-selection-proposal':
            if choice != 'approved':
                fail('CONFIRMATION', 'selection proposal requires explicit approval')
            from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
            return ImageLedSelectionService(self.kernel).selection_context(target_ref)
        if choice not in {'approved', 'revoked'}:
            fail('CONFIRMATION', 'scope choice must be approved or revoked')
        if choice == 'approved':
            self.require_g0()
            require_exact_ref(self.kernel, target_ref, PREFIX + 'scope', 'image-led-authorization-scope')
        else:
            # Stopping use of a historical grant is independent of production gates.
            validate_scope(resolve_kind(self.kernel, target_ref, 'image-led-authorization-scope')['payload'],
                self.kernel.project_id)
            from ai_ppt_studio.kernel.references import ArtifactReference
            ledger_ref = self.kernel.load().artifact_heads.get('kernel/confirmation-consumptions', '')
            ledger = resolve_kind(self.kernel, ledger_ref, 'confirmation-consumption-ledger')['payload']
            found = False
            for ref in set(ledger.get('artifact_bindings', {}).values()):
                if ArtifactReference.parse(ref).kind != 'image-led-authorization':
                    continue
                value = resolve_kind(self.kernel, ref, 'image-led-authorization')['payload']
                if value.get('scope_id') == target_ref:
                    self.trusted_confirmation(ref, kind='image-led-authorization', target_ref=target_ref)
                    found = True
            if not found:
                fail('CONFIRMATION', 'revocation requires a previously trusted material grant')
        kind = 'image-led-authorization' if choice == 'approved' else 'image-led-revocation'
        return ScopedConfirmationPolicy(self.kernel).context(
            scope_kind=kind, scope_id=target_ref, source_version=target_ref,
            evidence_refs=[target_ref])

    def confirm(self, command_id, expected_revision, *, target_ref, choice,
                source_version, challenge_id, challenge_revision, host_confirmation_assertion):
        from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
        require_revision(self.kernel, expected_revision)
        context = self.confirmation_context(target_ref, choice)
        confirmed, consumptions = ScopedConfirmationPolicy(self.kernel).confirmation_payload(
            current=context, source_version=source_version, challenge_id=challenge_id,
            challenge_revision=challenge_revision, host_confirmation_assertion=host_confirmation_assertion)
        if context['scope_kind'] == 'image-led-selection':
            from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
            return ImageLedSelectionService(self.kernel).finalize(command_id, expected_revision, target_ref, confirmed, consumptions)
        kind = context['scope_kind']
        slot = PREFIX + ('authorization' if choice == 'approved' else 'revocation')
        invalidation = {}
        heads = self.kernel.load().artifact_heads
        policy_ref = heads.get(PREFIX + 'input-policy')
        if choice == 'revoked' and policy_ref:
            policy = resolve_kind(self.kernel, policy_ref, 'image-led-input-policy')['payload']
            if policy['authorization_scope_ref'] == target_ref:
                from ai_ppt_studio.application.gate_evaluator import GateEvaluator
                from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
                # Preserve the exact inputs so queued executions report revocation;
                # selected designs and all usable engineering outputs are invalidated.
                keep = {PREFIX + name for name in ('scope', 'authorization', 'revocation', 'input-policy')}
                keep.update(key for key in heads if key.startswith(PREFIX + 'pack/'))
                invalidation = {'gate_mutation': GateEvaluator(self.kernel).image_led_upstream_replaced(),
                    'artifact_removals': visual_downstream_slots(heads, keep=keep)}
        # Persistent grant/revocation is outside G0's transient visual invalidation.
        state = self.kernel.commit(command_id=command_id, expected_revision=expected_revision,
            event_type=kind + '.confirmed', artifact_updates={
                slot: (kind, confirmed),
            }, confirmation_consumptions=consumptions, **invalidation)
        # The confirmation itself is already durable via the kernel ledger;
        # no second write is needed or allowed. Revocation lookup uses the ledger
        # and immutable event heads, not a transient visual head.
        return state.artifact_heads[slot]
