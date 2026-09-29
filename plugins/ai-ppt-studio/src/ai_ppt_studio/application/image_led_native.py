"""Runtime-owned registration and resolution of finalized design dependencies."""
from __future__ import annotations
from copy import deepcopy
import base64
import hashlib
from io import BytesIO

from ai_ppt_studio.application.artifact_guards import require_revision, resolve_kind
from ai_ppt_studio.application.image_led_service import PREFIX, is_image_led
from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, text
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, REGION_VERSION_V3
from ai_ppt_studio.kernel.references import ArtifactReference

REGION_CHECKS = {'visible-copy-transcription', 'complete-region-coverage', 'material-roles', 'faithful-geometry-appearance'}


def upstream_keep(heads):
    """Only generation and trusted selection dependencies survive downstream changes."""
    return {slot for slot in heads if slot.startswith(PREFIX) and not any(
        slot.startswith(PREFIX + suffix) for suffix in (
            'regions', 'region-review/', 'build-result', 'result-review/',
            'native-pptx', 'editability', 'preflight'))}


class ImageLedNativeService(ImageLedSelectionService):
    def _upstream_changed(self):
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator
        return GateEvaluator(self.kernel).image_led_upstream_replaced()

    def _selection(self):
        if not is_image_led(self.kernel):
            fail('ROUTE', 'finalized design registration requires Image-led workflow')
        ref = self.kernel.load().artifact_heads.get(PREFIX + 'selection', '')
        return ref, self.current_selection(ref)

    def _validate_regions(self, payload):
        selection_ref, selection = self._selection()
        value = validate_region_inventory(payload, selection, selection_ref=selection_ref)
        from PIL import Image
        for slide in value['slides']:
            target = slide['target_binding']
            image = resolve_kind(self.kernel, target['target_image_ref'], 'image-led-image')['payload']
            raw = base64.b64decode(image['data_base64'], validate=True)
            if hashlib.sha256(raw).hexdigest() != target['target_image_sha256']:
                fail('HASH', 'regions target image bytes changed')
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                size = {'width': decoded.width, 'height': decoded.height}
            if size != slide['source_image_size']:
                fail('IMAGE', 'regions must use the actual selected image dimensions')
        return value

    def register_regions(self, command_id, revision, payload):
        require_revision(self.kernel, revision)
        self.require_g0()
        value = self._validate_regions(payload)
        state = self.kernel.load()
        keep = upstream_keep(state.artifact_heads) | {PREFIX + 'regions'}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.regions-registered', artifact_updates={
                PREFIX + 'regions': ('image-led-region-inventory', value)},
            gate_mutation=self._upstream_changed(),
            artifact_removals=visual_downstream_slots(state.artifact_heads, keep=keep))
        return committed.artifact_heads[PREFIX + 'regions']

    @staticmethod
    def _review_checks(payload, *, region_version=None):
        criteria = REGION_CHECKS | ({'source-image-derived-relations'} if region_version == REGION_VERSION_V3 else set())
        checks = payload.get('checks')
        if not isinstance(checks, list) or len(checks) != len(criteria):
            fail('REVIEW', 'region review requires all independent criteria')
        seen = set()
        for row in checks:
            exact(row, {'criterion', 'result', 'detail'}, 'region review criterion')
            if row['criterion'] not in criteria or row['criterion'] in seen:
                fail('REVIEW', 'unknown or duplicate region criterion')
            seen.add(row['criterion'])
            if row['result'] not in {'passed', 'failed', 'not-established'}:
                fail('REVIEW', 'unknown region result')
            text(row['detail'], 'detail')

    def register_region_review(self, command_id, revision, payload):
        require_revision(self.kernel, revision)
        self.require_g0()
        exact(payload, {'artifact_type', 'project_id', 'target_ref', 'reviewer_kind', 'reviewer_role', 'checks'}, 'region review')
        if payload['project_id'] != self.kernel.project_id:
            fail('PROJECT', 'region review belongs to another project')
        inventory = self.current_regions(require_review=False)
        ref = self.kernel.load().artifact_heads[PREFIX + 'regions']
        if payload['target_ref'] != ref:
            fail('STALE', 'region review must target current inventory')
        task = self._agent(action='review-visual-engineering', target_refs=[ref])
        if (task['role_id'] != 'visual-engineering-reviewer' or payload['reviewer_role'] != task['role_id']
                or payload['reviewer_kind'] != 'engineering'):
            fail('REVIEW', 'region reviewer role differs from the independent task')
        selected = self.current_selection(inventory['selection_ref'])
        for slide in selected['slides']:
            candidate = self.current_candidate(slide['target_binding']['candidate_ref'])
            if task['task_id'] == candidate['producer_task_id'] or task['role_id'] == candidate['producer_role']:
                fail('REVIEW', 'image producer cannot review its own regions')
        self._review_checks(payload, region_version=inventory.get('region_version'))
        value = {**deepcopy(payload), 'selection_ref': inventory['selection_ref'],
            'reviewer_task_id': task['task_id'], 'context_pack_ref': task['context_pack_ref']}
        slot = PREFIX + 'region-review/' + ArtifactReference.parse(ref).sha256
        # A changed assessment invalidates every artifact that depended on the old one.
        keep = upstream_keep(self.kernel.load().artifact_heads) | {PREFIX + 'regions', slot}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.regions-reviewed', artifact_updates={slot: ('image-led-region-review', value)},
            gate_mutation=self._upstream_changed(),
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep))
        return state.artifact_heads[slot]

    def current_region_review(self, ref):
        slot = PREFIX + 'region-review/' + ArtifactReference.parse(ref).sha256
        review_ref = self.kernel.load().artifact_heads.get(slot, '')
        if not review_ref:
            fail('REVIEW', 'current region inventory has no independent assessment')
        value = self._current(review_ref, slot, 'image-led-region-review')
        inventory = self._current(ref, PREFIX + 'regions', 'image-led-region-inventory')
        self._review_checks(value, region_version=inventory.get('region_version'))
        if (value['target_ref'] != ref or value['selection_ref'] != self.kernel.load().artifact_heads.get(PREFIX + 'selection')
                or any(row['result'] != 'passed' for row in value['checks'])):
            fail('REVIEW', 'region coverage review is not passed for current selection')
        task_id = value['reviewer_task_id']
        task = self._current(self.kernel.load().artifact_heads.get('agent/task/' + task_id, ''),
            'agent/task/' + task_id, 'agent-task')
        if (task['status'] != 'completed' or task['result_refs'] != [review_ref]
                or task['target_refs'] != [ref] or task['action_type'] != 'review-visual-engineering'
                or task['role_id'] != 'visual-engineering-reviewer' or task['context_pack_ref'] != value['context_pack_ref']):
            fail('REVIEW', 'region review lacks completed independent task lineage')
        return value

    def diagnostic_review(self):
        """Return the current region review when structural criteria passed.

        Appearance may remain not-established for the pre-G1 diagnostic route;
        every other admission rule remains identical to formal review lineage.
        """
        ref = self.kernel.load().artifact_heads.get(PREFIX + 'regions', '')
        if not ref:
            fail('REVIEW', 'diagnostic requires a current region inventory')
        slot = PREFIX + 'region-review/' + ArtifactReference.parse(ref).sha256
        review_ref = self.kernel.load().artifact_heads.get(slot, '')
        if not review_ref:
            fail('REVIEW', 'diagnostic requires an independent region review')
        value = self._current(review_ref, slot, 'image-led-region-review')
        inventory = self._current(ref, PREFIX + 'regions', 'image-led-region-inventory')
        self._review_checks(value, region_version=inventory.get('region_version'))
        structural = {'visible-copy-transcription', 'complete-region-coverage',
                      'material-roles', 'source-image-derived-relations'}
        checks = {row['criterion']: row['result'] for row in value['checks']}
        if value['target_ref'] != ref or value['selection_ref'] != self.kernel.load().artifact_heads.get(PREFIX + 'selection'):
            fail('REVIEW', 'diagnostic review is stale for current selection or regions')
        if any(checks.get(name) != 'passed' for name in structural) or checks.get('faithful-geometry-appearance') == 'failed':
            fail('REVIEW', 'diagnostic admission requires structural passes and appearance passed or not-established')
        task_id = value['reviewer_task_id']
        task = self._current(self.kernel.load().artifact_heads.get('agent/task/' + task_id, ''),
            'agent/task/' + task_id, 'agent-task')
        if (task['status'] != 'completed' or task['result_refs'] != [review_ref]
                or task['target_refs'] != [ref] or task['action_type'] != 'review-visual-engineering'
                or task['role_id'] != 'visual-engineering-reviewer' or task['context_pack_ref'] != value['context_pack_ref']):
            fail('REVIEW', 'diagnostic review lacks completed independent task lineage')
        return value

    def current_regions(self, *, require_review=True):
        ref = self.kernel.load().artifact_heads.get(PREFIX + 'regions', '')
        payload = self._current(ref, PREFIX + 'regions', 'image-led-region-inventory')
        value = self._validate_regions(payload)
        if require_review:
            self.current_region_review(ref)
        return value

    def _setup_identity(self, payload):
        self.require_g0()
        exact(payload.get('image_led'), {'selection_ref'}, 'finalized visual setup identity')
        ref, selection = self._selection()
        if payload['image_led']['selection_ref'] != ref:
            fail('SELECTION', 'visual setup is not bound to current finalized selection')
        self.current_regions()
        return selection

    def _register_setup(self, command_id, revision, payload, *, design=False):
        from ai_ppt_studio.domains.visual.contracts import validate_visual_brief, validate_deck_design_system
        from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
        require_revision(self.kernel, revision)
        selection = self._setup_identity(payload)
        state = self.kernel.load()
        self._current(payload.get('reading_blueprint_ref'), 'content/reading-blueprint', 'reading-deck-blueprint')
        if design:
            self._current(payload.get('visual_brief_ref'), 'visual/brief', 'visual-brief')
            value = validate_deck_design_system(payload)
            policy = self._current(selection['slides'][0]['target_binding']['common_rules_ref'],
                PREFIX + 'input-policy', 'image-led-input-policy')
            if any(value.get(key) != expected for key, expected in policy['common_rules'].items()):
                fail('COMMON_RULES', 'design system must preserve the selected shared rules without layout changes')
            slot, kind = 'visual/design-system', 'deck-design-system'
        else:
            _, policy = ReleaseTargetPolicyService(self.kernel).current()
            value = validate_visual_brief(payload, policy.required_target_ids)
            slot, kind = 'visual/brief', 'visual-brief'
        keep = upstream_keep(state.artifact_heads) | {PREFIX + 'regions', slot}
        keep.update(s for s in state.artifact_heads if s.startswith(PREFIX + 'region-review/'))
        if design:
            keep.add('visual/brief')
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.visual-setup-registered', artifact_updates={slot: (kind, value)},
            gate_mutation=self._upstream_changed(),
            artifact_removals=visual_downstream_slots(state.artifact_heads, keep=keep))
        return committed.artifact_heads[slot]

    def register_brief(self, command_id, revision, payload):
        return self._register_setup(command_id, revision, payload)

    def register_design(self, command_id, revision, payload):
        return self._register_setup(command_id, revision, payload, design=True)

    def _contract_inputs(self, payload):
        from ai_ppt_studio.domains.visual.contracts import validate_image_led_contract_set
        from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
        selection_ref, selection = self._selection()
        inventory = self.current_regions()
        state = self.kernel.load()
        region_ref = state.artifact_heads[PREFIX + 'regions']
        brief_ref = state.artifact_heads.get('visual/brief', '')
        brief = self._current(brief_ref, 'visual/brief', 'visual-brief')
        design_ref = state.artifact_heads.get('visual/design-system', '')
        design = self._current(design_ref, 'visual/design-system', 'deck-design-system')
        if (brief.get('image_led') != {'selection_ref': selection_ref}
                or design.get('image_led') != {'selection_ref': selection_ref}
                or design.get('visual_brief_ref') != brief_ref):
            fail('STALE', 'formal setup does not bind the current selection')
        blueprint_ref = state.artifact_heads.get('content/reading-blueprint', '')
        blueprint = self._current(payload.get('reading_blueprint_ref'), 'content/reading-blueprint', 'reading-deck-blueprint')
        if (payload.get('deck_design_system_ref') != design_ref
                or brief['reading_blueprint_ref'] != blueprint_ref or design['reading_blueprint_ref'] != blueprint_ref):
            fail('STALE', 'formal contract references a stale visual design or blueprint')
        normalized = validate_image_led_contract_set(payload, blueprint, selection=selection,
            region_inventory=inventory, selection_ref=selection_ref, region_inventory_ref=region_ref)
        policy_ref, _ = ReleaseTargetPolicyService(self.kernel).current()
        version = blueprint['source_version']
        if normalized.get('source_version', version) != version:
            fail('STALE', 'formal contract source_version differs from current blueprint')
        return normalized, dict(reading_blueprint_ref=blueprint_ref, visual_brief_ref=brief_ref,
            deck_design_system_ref=design_ref, release_target_policy_ref=policy_ref,
            source_version=version, visual_brief=brief, design_system=design,
            selection=selection, region_inventory=inventory, selection_ref=selection_ref, region_inventory_ref=region_ref)

    def register_contracts(self, command_id, revision, payload):
        from ai_ppt_studio.domains.visual.compilation import compile_image_led_plan
        from ai_ppt_studio.application.review_commands import fingerprint, replay_ref
        self.require_g0()
        normalized, inputs = self._contract_inputs(payload)
        semantic = fingerprint('register-image-led-contracts', normalized)
        replay = replay_ref(self.kernel, command_id, semantic, 'visual/contracts')
        if replay:
            self.current_contract_plan()
            return replay[0]
        require_revision(self.kernel, revision)
        contract_ref = str(self.kernel.artifacts.reference_for('visual-contract-set', normalized))
        plan = compile_image_led_plan(**inputs, visual_contract_set_ref=contract_ref,
            source_revision=revision + 1, contract_set=normalized)
        keep = upstream_keep(self.kernel.load().artifact_heads) | {
            PREFIX + 'regions', 'visual/brief', 'visual/design-system', 'visual/contracts', 'visual/compilation-plan'}
        keep.update(s for s in self.kernel.load().artifact_heads if s.startswith(PREFIX + 'region-review/'))
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='visual.contract-set-registered', artifact_updates={
                'visual/contracts': ('visual-contract-set', normalized),
                'visual/compilation-plan': ('visual-compilation-plan', plan)},
            gate_mutation=self._upstream_changed(),
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep),
            command_fingerprint=semantic)
        return state.artifact_heads['visual/contracts']

    def current_contract_plan(self):
        from ai_ppt_studio.domains.visual.compilation import compile_image_led_plan, validate_image_led_compilation_plan
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator
        state = self.kernel.load()
        contract_ref = state.artifact_heads.get('visual/contracts', '')
        plan_ref = state.artifact_heads.get('visual/compilation-plan', '')
        contract = self._current(contract_ref, 'visual/contracts', 'visual-contract-set')
        contract, inputs = self._contract_inputs(contract)
        plan = self._current(plan_ref, 'visual/compilation-plan', 'visual-compilation-plan')
        normalized = validate_image_led_compilation_plan(plan, contract_set=contract,
            selection=inputs['selection'], region_inventory=inputs['region_inventory'],
            selection_ref=inputs['selection_ref'], region_inventory_ref=inputs['region_inventory_ref'])
        expected = compile_image_led_plan(**inputs, visual_contract_set_ref=contract_ref,
            source_revision=normalized['source_revision'], contract_set=contract)
        if normalized != expected or not GateEvaluator(self.kernel)._visual_plan_publication_is_atomic(
                source_revision=normalized['source_revision'], contract_ref=contract_ref, plan_ref=plan_ref):
            fail('PLAN', 'current compilation differs from its exact atomic finalized publication')
        return contract, normalized

    def validate_formal_review(self, review_ref):
        value = resolve_kind(self.kernel, review_ref, 'visual-review-record')['payload']
        lineage = value.get('image_led_review')
        exact(lineage, {'reviewer_task_id', 'context_pack_ref', 'selection_ref', 'plan_ref'}, 'formal review lineage')
        state = self.kernel.load()
        if (lineage['selection_ref'] != state.artifact_heads.get(PREFIX + 'selection')
                or lineage['plan_ref'] != state.artifact_heads.get('visual/compilation-plan')):
            fail('REVIEW', 'formal review binds an old finalized design')
        task_id = lineage['reviewer_task_id']
        task = self._current(state.artifact_heads.get('agent/task/' + task_id, ''), 'agent/task/' + task_id, 'agent-task')
        if (task['status'] != 'completed' or task['result_refs'] != [review_ref]
                or task['target_refs'] != [value['target_ref']] or task['context_pack_ref'] != lineage['context_pack_ref']
                or task['role_id'] != 'visual-' + value['reviewer_kind'] + '-reviewer'
                or task['action_type'] != 'review-visual-' + value['reviewer_kind']):
            fail('REVIEW', 'formal visual review has no completed independent task provenance')
        return value

    def _anchor_projection(self, result_ref, review_ref, *, anchor_slide_ids=None):
        from pathlib import Path
        from ai_ppt_studio.application.image_led_results import ImageLedResultService
        from ai_ppt_studio.domains.visual.contracts import validate_anchor_slide_set
        contracts, plan = self.current_contract_plan()
        value = ImageLedResultService(self.kernel).current_result(result_ref, review_ref=review_ref)
        output = value['output']
        rendered = output['renders']
        all_slide_ids = [row['slide_id'] for row in rendered]
        if anchor_slide_ids is None:
            if len(rendered) != 3:
                fail('ANCHORS', 'a build with more than three pages requires three explicit anchor slide IDs')
            anchor_slide_ids = all_slide_ids
        if (not isinstance(anchor_slide_ids, list) or len(anchor_slide_ids) != 3
                or any(not isinstance(slide_id, str) for slide_id in anchor_slide_ids)
                or len(set(anchor_slide_ids)) != 3
                or [slide_id for slide_id in all_slide_ids if slide_id in anchor_slide_ids] != anchor_slide_ids):
            fail('ANCHORS', 'three anchor slide IDs must occur once in the reviewed build order')
        anchor_renders = [row for row in rendered if row['slide_id'] in anchor_slide_ids]
        identity = {'build_result_ref': result_ref, 'four_dimension_review_ref': review_ref,
            'selection_ref': output['selection_ref'], 'region_inventory_ref': output['region_inventory_ref'],
            'plan_ref': output['plan_ref'], 'pptx_sha256': output['pptx_sha256']}
        native = {**identity, 'production_route': 'strict-B', 'path': output['pptx_path']}
        editability = {**identity, 'semantic_objects_editable': True,
            'object_file_sha256': output['files']['mapping.json']['sha256'],
            'verification': 'actual-ooxml-and-independent-four-dimension-review'}
        preflight = {**identity, 'identity': 'preflight-only', 'renders': deepcopy(output['renders'])}
        records = {'visual/image-led/native-pptx': ('native-pptx', native),
            'visual/image-led/editability': ('editability-evidence', editability),
            'visual/image-led/preflight': ('preflight-render', preflight)}
        refs = {slot: str(self.kernel.artifacts.reference_for(kind, payload))
            for slot, (kind, payload) in records.items()}
        anchors = {'visual_contract_set_ref': self.kernel.load().artifact_heads['visual/contracts'],
            'visual_compilation_plan_ref': output['plan_ref'],
            'native_first_pptx_ref': refs['visual/image-led/native-pptx'],
            'pptx_sha256': output['pptx_sha256'], 'native_first_frozen': True,
            'slide_ids': anchor_slide_ids,
            'selection_reason': ('当前三页定版设计的忠实原生转换' if len(rendered) == 3 else
                                 '从当前完整构建中选取三页代表性定版成果'),
            'source_version': plan['source_version'],
            'editability_evidence_refs': [refs['visual/image-led/editability']],
            'preflight_render_refs': [refs['visual/image-led/preflight']],
            'render_assets': [{'slide_id': row['slide_id'],
                'current_asset_ref': Path(row['path']).relative_to(self.kernel.project_root).as_posix(),
                'previous_asset_ref': ''} for row in anchor_renders],
            'image_led': identity}
        return validate_anchor_slide_set(anchors, contracts), records

    def register_anchors(self, command_id, revision, payload):
        from ai_ppt_studio.errors import GateBlockedError
        require_revision(self.kernel, revision)
        self.require_g0()
        if self.kernel.load().gate_status.get('G1') != 'passed':
            raise GateBlockedError('image-led-anchors', ('G1-not-passed',))
        fields = {'artifact_type', 'build_result_ref', 'four_dimension_review_ref'}
        if isinstance(payload, dict) and 'slide_ids' in payload:
            fields.add('slide_ids')
        exact(payload, fields, 'Image-led anchor promotion')
        if payload['artifact_type'] != 'image-led-anchor-set':
            fail('RESULT', 'anchors require governed Image-led promotion')
        normalized, records = self._anchor_projection(payload['build_result_ref'], payload['four_dimension_review_ref'],
                                                      anchor_slide_ids=payload.get('slide_ids'))
        keep = {slot for slot in self.kernel.load().artifact_heads if slot.startswith('visual/')
            and not slot.startswith(('visual/anchors', 'visual/target-evidence/', 'visual/review/G2/', 'visual/contract/'))
            and slot != 'visual/contract'} | set(records) | {'visual/anchors'}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.anchors-promoted', artifact_updates={**records, 'visual/anchors': ('anchor-slide-set', normalized)},
            artifact_removals=visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep))
        return state.artifact_heads['visual/anchors']

    def current_anchors(self):
        ref = self.kernel.load().artifact_heads.get('visual/anchors', '')
        value = self._current(ref, 'visual/anchors', 'anchor-slide-set')
        binding = value.get('image_led') or {}
        expected, records = self._anchor_projection(binding.get('build_result_ref'), binding.get('four_dimension_review_ref'),
                                                    anchor_slide_ids=value.get('slide_ids'))
        if value != expected:
            fail('RESULT', 'anchor set differs from the actual current reviewed build result')
        for slot, (kind, payload) in records.items():
            wanted = str(self.kernel.artifacts.reference_for(kind, payload))
            if self._current(wanted, slot, kind) != payload:
                fail('RESULT', 'native support evidence differs from the checked result')
        return value


class ExistingDeckNativeService:
    """Preflight a complete source-sized, exact-image region/object plan."""

    PLAN_SLOT = 'optimization/native-plan'
    REGIONS_SLOT = 'optimization/regions'

    def __init__(self, kernel):
        self.kernel = kernel

    def _validate(self, inventory, objects, *, selection_ref=None):
        from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService
        from ai_ppt_studio.domains.visual.image_led import validate_faithful_objects
        service = ExistingDeckSelectionService(self.kernel)
        selection_ref = selection_ref or self.kernel.load().artifact_heads.get(service.SELECTION, '')
        selection = service.current_selection(selection_ref)
        region_inventory = validate_region_inventory(inventory, selection, selection_ref=selection_ref)
        if (not isinstance(objects, list) or len(objects) != len(region_inventory['slides'])
                or region_inventory.get('region_version') is not None):
            fail('REGIONS', 'existing-deck v1 plan needs every page with supported native regions')
        from PIL import Image
        for index, (page, mapped) in enumerate(zip(region_inventory['slides'], objects)):
            target = page['target_binding']
            image = resolve_kind(self.kernel, target['target_image_ref'], 'image-led-image')['payload']
            raw = base64.b64decode(image['data_base64'], validate=True)
            if (hashlib.sha256(raw).hexdigest() != target['target_image_sha256']
                    or image.get('sha256') != target['target_image_sha256']):
                fail('HASH', 'native plan target differs from actual selected image bytes')
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                actual = {'width': decoded.width, 'height': decoded.height}
            if actual != page['source_image_size']:
                fail('REGIONS', 'page canvas differs from selected image dimensions')
            validate_faithful_objects(page['regions'], mapped)
            # Every source page must have native semantic text carriers. A source
            # slide proto, whole-slide bitmap or missing page never fills a gap.
            if (target['page_order'] != index + 1 or
                    not any(obj['kind'] == 'text' and obj['render_mode'] == 'native' for obj in mapped)):
                fail('NATIVE', 'source page lacks exact native text carriers')
        return region_inventory

    def register_plan(self, command_id, revision, *, inventory, objects):
        require_revision(self.kernel, revision)
        if self.PLAN_SLOT in self.kernel.load().artifact_heads:
            fail('PLAN', 'a current native plan cannot be replaced without explicit revision')
        checked = self._validate(inventory, objects)
        selection_ref = checked['selection_ref']
        region_ref = str(self.kernel.artifacts.reference_for('image-led-region-inventory', checked))
        slides = []
        for page, mapped, selected in zip(checked['slides'], objects,
                resolve_kind(self.kernel, selection_ref, 'image-led-selection')['payload']['slides']):
            slides.append({**deepcopy(page), 'selected_copy': deepcopy(selected['selected_copy']),
                'objects': deepcopy(mapped)})
        from ai_ppt_studio.application.existing_deck_optimization import SOURCE_SLOT
        from ai_ppt_studio.domains.visual.compilation import image_led_versions
        version, handoff = image_led_versions({'slides': resolve_kind(self.kernel, selection_ref,
            'image-led-selection')['payload']['slides']}, checked)
        plan = {'project_id': self.kernel.project_id, 'source_ref': self.kernel.load().artifact_heads[SOURCE_SLOT],
            'selection_ref': selection_ref, 'region_inventory_ref': region_ref,
            'compiler_version': version, 'handoff_version': handoff, 'slides': slides}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='optimization.native-plan-registered', artifact_updates={
                self.REGIONS_SLOT: ('image-led-region-inventory', checked),
                self.PLAN_SLOT: ('visual-compilation-plan', plan)})
        return committed.artifact_heads[self.PLAN_SLOT]

    def current_plan(self, ref=None):
        from ai_ppt_studio.application.artifact_guards import require_exact_ref
        from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService
        state = self.kernel.load()
        ref = ref or state.artifact_heads.get(self.PLAN_SLOT, '')
        plan = require_exact_ref(self.kernel, ref, self.PLAN_SLOT, 'visual-compilation-plan')['payload']
        if (plan.get('project_id') != self.kernel.project_id
                or plan.get('source_ref') != state.artifact_heads.get('optimization/source')
                or plan.get('selection_ref') != state.artifact_heads.get(ExistingDeckSelectionService.SELECTION)
                or plan.get('region_inventory_ref') != state.artifact_heads.get(self.REGIONS_SLOT)):
            fail('PLAN', 'native plan refers to an outdated source, image, or region inventory')
        selected = ExistingDeckSelectionService(self.kernel).current_selection(plan['selection_ref'])
        regions = require_exact_ref(self.kernel, plan['region_inventory_ref'], self.REGIONS_SLOT,
            'image-led-region-inventory')['payload']
        self._validate(regions, [page['objects'] for page in plan['slides']], selection_ref=plan['selection_ref'])
        if (len(plan['slides']) != len(selected['slides'])
                or any({key: page[key] for key in ('target_binding', 'canvas', 'source_image_size', 'regions')}
                    != region or page['selected_copy'] != chosen['selected_copy']
                    for page, region, chosen in zip(plan['slides'], regions['slides'], selected['slides']))):
            fail('PLAN', 'stored native plan differs from current reviewed region/object mapping')
        return plan
