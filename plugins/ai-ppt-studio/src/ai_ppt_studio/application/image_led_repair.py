"""Governed pre-selection repair of an exact completed Image 2 output."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
from io import BytesIO

from ai_ppt_studio.application.artifact_guards import require_revision, resolve_kind
from ai_ppt_studio.application.image_led_service import ImageLedService, PREFIX
from ai_ppt_studio.domains.materials.image_input_contracts import digest, exact, fail
from ai_ppt_studio.domains.visual.image_repair import (
    build_repair_payload, validate_diagnostic, validate_issues, validate_repair_payload)
from ai_ppt_studio.kernel.references import ArtifactReference

SERVER_FIELDS = {'reviewer_task_id', 'context_pack_ref', 'producer_task_id',
                 'source_payload_sha256', 'authorization_binding'}
REPAIR_VERSION = 'image-led-image2-repair-input/v1'


class ImageLedRepairService(ImageLedService):
    def _task_context(self, task, *, action, role, targets):
        context = self._current(task['context_pack_ref'],
            'agent/context/' + task['task_id'], 'context-pack')
        layers = context.get('layers', {})
        if (task.get('action_type') != action or task.get('role_id') != role
                or task.get('target_refs') != targets
                or context.get('project_id') != self.kernel.project_id
                or context.get('project_revision') != task.get('input_revision')
                or context.get('artifact_version_refs') != targets
                or layers.get('role_contract') != {'role_id': role}
                or layers.get('task_contract') != {'task_type': action, 'target_refs': targets}):
            fail('REPAIR_LINEAGE', 'task and immutable context identities disagree')
        return layers

    @staticmethod
    def _image(response):
        from PIL import Image
        try:
            raw = base64.b64decode(response['image_base64'], validate=True)
            with Image.open(BytesIO(raw)) as image:
                image.load()
                if (image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1
                        or response.get('image_mime_type') != 'image/png'
                        or response.get('image_size') != [image.width, image.height]
                        or hashlib.sha256(raw).hexdigest() != response.get('image_sha256')):
                    fail('REPAIR_IMAGE', 'source image bytes, dimensions, format or hash disagree')
        except (KeyError, TypeError, ValueError, OSError):
            fail('REPAIR_IMAGE', 'source must be a complete exact single-frame PNG')

    def _stored_diagnostic(self, ref, *, current=False):
        value = resolve_kind(self.kernel, ref, 'image-led-content-diagnostic')['payload']
        public = {k: v for k, v in value.items() if k not in SERVER_FIELDS}
        validate_diagnostic(public, self.kernel.project_id)
        exact(value, set(public) | SERVER_FIELDS, 'stored repair diagnosis')
        if current:
            self._current(ref, PREFIX + 'content-diagnostic/' +
                ArtifactReference.parse(value['generation_response_ref']).sha256, 'image-led-content-diagnostic')
        from ai_ppt_studio.application.project_service import ProjectCommandService
        task = ProjectCommandService(self.kernel).resolve_agent_task(value['reviewer_task_id'])
        if (task.get('status') != 'completed' or task.get('result_refs') != [ref]
                or task.get('context_pack_ref') != value['context_pack_ref']
                or task['task_id'] == value['producer_task_id']):
            fail('REPAIR_REVIEW', 'diagnosis lacks its completed independent result transaction')
        layers = self._task_context(task, action='review-visual-engineering',
            role='visual-engineering-reviewer', targets=[value['generation_response_ref']])
        return value, layers

    @staticmethod
    def _authorization(pack, base, policy):
        return {'derivation': 'same-project-page-image2-repair/v1',
            'input_policy_ref': pack['input_policy_ref'],
            'authorization_scope_ref': policy['authorization_scope_ref'],
            'authorization_ref': policy['authorization_ref'],
            'receiver': base['receiver'], 'model': base['model'],
            'base_payload_sha256': digest(base)}

    def source_info(self, response_ref):
        """Validate historical tasks, including completed tasks and repair ancestors.

        Only the next requested diagnosis must be current. Ancestor diagnoses
        remain immutable evidence after replacement; current inputs and grants
        are nevertheless revalidated for every link before a new send.
        """
        self.require_g0()
        from ai_ppt_studio.application.project_service import ProjectCommandService
        commands = ProjectCommandService(self.kernel)
        seen, first, child = set(), None, None
        while True:
            if response_ref in seen:
                fail('REPAIR_LINEAGE', 'repair lineage contains a cycle')
            seen.add(response_ref)
            response = resolve_kind(self.kernel, response_ref, 'image-led-generation-response')['payload']
            if (response.get('project_id') != self.kernel.project_id or response.get('status') != 'completed'):
                fail('REPAIR_SOURCE', 'repair needs this project exact completed response')
            task = commands.resolve_agent_task(response.get('request_id', ''))
            self._current(response_ref, 'project/image-led/request/' + task['task_id'], 'image-led-generation-response')
            if task.get('status') not in {'queued', 'completed'}:
                fail('REPAIR_LINEAGE', 'source task is not a valid generation task')
            layers = self._task_context(task, action='generate-slide-images', role='image-asset-producer',
                targets=task['target_refs'])
            request = layers.get('image_led_request', {})
            payload = request.get('payload', {})
            is_repair = payload.get('payload_version') == REPAIR_VERSION
            target = request.get('repair_diagnostic_ref') if is_repair else request.get('pack_ref')
            if (task['target_refs'] != [target] or request.get('request_id') != task['task_id']
                    or request.get('pack_ref') != response.get('pack_ref')
                    or request.get('payload_sha256') != digest(payload)
                    or response.get('payload_sha256') != digest(payload)):
                fail('REPAIR_LINEAGE', 'source response differs from its original generation request')
            base, binding = self.compile_request(request['pack_ref'], with_binding=True)
            if base.get('payload_version') != 'image-led-image2-input/v2' or (
                    base.get('receiver'), base.get('model')) != ('CRS', 'gpt-image-2'):
                fail('REPAIR_VERSION', 'repair currently requires the authorized CRS Image 2 v2 input')
            if request.get('semantic_binding') != binding:
                fail('REPAIR_STALE', 'source semantics differ from current original inputs')
            if is_repair:
                validate_repair_payload(payload)
                source_base = payload['base_payload']
            else:
                if any(k in request or k in response for k in ('repair_diagnostic_ref', 'source_generation_response_ref')):
                    fail('REPAIR_LINEAGE', 'normal generation cannot carry repair identity')
                source_base = payload
            if source_base != base:
                fail('REPAIR_STALE', 'source request original input is no longer current')
            self._image(response)
            pack = resolve_kind(self.kernel, request['pack_ref'], 'image-led-input-pack')['payload']
            policy = resolve_kind(self.kernel, pack['input_policy_ref'], 'image-led-input-policy')['payload']
            info = {'response_ref': response_ref, 'response': response, 'task': task,
                'pack': pack, 'base': base, 'binding': binding,
                'authorization': self._authorization(pack, base, policy)}
            if first is None:
                first = info
            if child is not None:
                diagnostic, diagnostic_layers, child_payload = child
                self._verify_diagnostic(diagnostic, info)
                if diagnostic_layers.get('image_led_diagnostic') != self._review_input(info):
                    fail('REPAIR_REVIEW', 'ancestor diagnosis context differs from its exact source')
                if diagnostic['excluded_content_check']['result'] != 'passed':
                    fail('REPAIR_EXCLUDED', 'ancestor source exclusion was not independently passed')
                if build_repair_payload(base, response, diagnostic['issues']) != child_payload:
                    fail('REPAIR_LINEAGE', 'repair payload differs from its bound source diagnosis')
            if not is_repair:
                return first
            diagnostic, diagnostic_layers = self._stored_diagnostic(request.get('repair_diagnostic_ref', ''))
            source_ref = diagnostic['generation_response_ref']
            if (request.get('source_generation_response_ref') != source_ref
                    or response.get('source_generation_response_ref') != source_ref
                    or response.get('repair_diagnostic_ref') != request['repair_diagnostic_ref']
                    or diagnostic['pack_ref'] != request['pack_ref']):
                fail('REPAIR_LINEAGE', 'repair task and response source identities disagree')
            child = diagnostic, diagnostic_layers, payload
            response_ref = source_ref

    def _review_input(self, info):
        source, pack = info['response'], info['pack']
        return {'generation_response_ref': info['response_ref'], 'pack_ref': source['pack_ref'],
            'slide_id': pack['slide_id'], 'page_order': pack['page_order'],
            'image_sha256': source['image_sha256'], 'image_size': source['image_size'],
            'image_base64': source['image_base64'], 'image_mime_type': source['image_mime_type'],
            'base_payload': info['base'], 'producer_task_id': info['task']['task_id'],
            'source_payload_sha256': source['payload_sha256'], 'authorization_binding': info['authorization']}

    def review_input(self, response_ref):
        return deepcopy(self._review_input(self.source_info(response_ref)))

    def _verify_diagnostic(self, value, info):
        expected = self._review_input(info)
        keys = {'generation_response_ref', 'pack_ref', 'slide_id', 'page_order', 'image_sha256', 'image_size'}
        if SERVER_FIELDS <= value.keys():
            keys |= SERVER_FIELDS - {'reviewer_task_id', 'context_pack_ref'}
        if any(value.get(k) != expected[k] for k in keys):
            fail('REPAIR_DIAGNOSTIC', 'diagnosis does not bind the exact source, page and authorization')
        validate_issues(value['issues'], info['base']['confirmed_visible_copy'], info['response']['image_size'])

    def register_diagnostic(self, command_id, revision, payload):
        require_revision(self.kernel, revision)
        value = validate_diagnostic(payload, self.kernel.project_id)
        task = getattr(self.kernel, 'prepared_agent_task', None)
        if not isinstance(task, dict) or task.get('status') != 'queued':
            fail('AGENT_RESULT', 'diagnosis requires the governed independent Agent result transaction')
        layers = self._task_context(task, action='review-visual-engineering',
            role='visual-engineering-reviewer', targets=[value['generation_response_ref']])
        info = self.source_info(value['generation_response_ref'])
        if task['task_id'] == info['task']['task_id'] or task['role_id'] == info['task']['role_id']:
            fail('REPAIR_REVIEW', 'generation task cannot diagnose itself')
        self._verify_diagnostic(value, info)
        if layers.get('image_led_diagnostic') != self._review_input(info):
            fail('REPAIR_STALE', 'diagnosis source changed after the review task was queued')
        value.update(reviewer_task_id=task['task_id'], context_pack_ref=task['context_pack_ref'],
            producer_task_id=info['task']['task_id'], source_payload_sha256=info['response']['payload_sha256'],
            authorization_binding=info['authorization'])
        slot = PREFIX + 'content-diagnostic/' + ArtifactReference.parse(value['generation_response_ref']).sha256
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.content-diagnosed', artifact_updates={slot: ('image-led-content-diagnostic', value)})
        return state.artifact_heads[slot]

    def compile_repair(self, diagnostic_ref, *, with_binding=False):
        value, layers = self._stored_diagnostic(diagnostic_ref, current=True)
        info = self.source_info(value['generation_response_ref'])
        self._verify_diagnostic(value, info)
        if layers.get('image_led_diagnostic') != self._review_input(info):
            fail('REPAIR_REVIEW', 'diagnostic context does not bind the current exact source')
        if value['excluded_content_check']['result'] != 'passed':
            fail('REPAIR_EXCLUDED', 'source image must pass independent excluded-content review before repair')
        payload = build_repair_payload(info['base'], info['response'], value['issues'])
        return (payload, info['binding']) if with_binding else payload
