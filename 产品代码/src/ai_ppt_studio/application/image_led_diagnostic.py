"""Pre-G1 Image-led native engineering diagnostic lifecycle."""
from __future__ import annotations
from copy import deepcopy
from ai_ppt_studio.application.image_led_native import ImageLedNativeService
from ai_ppt_studio.application.image_led_service import PREFIX, is_image_led
from ai_ppt_studio.application.artifact_guards import require_revision
from ai_ppt_studio.domains.materials.image_input_contracts import fail
from ai_ppt_studio.domains.visual.diagnostic import (
    DIAGNOSTIC_INPUT_KIND, DIAGNOSTIC_INPUT_VERSION, DIAGNOSTIC_HANDOFF_VERSION,
    DIAGNOSTIC_COMPILER_VERSION, DIAGNOSTIC_PURPOSE, diagnostic_projection,
)
from ai_ppt_studio.kernel.references import ArtifactReference

DIAGNOSTIC_INPUT_PREFIX = PREFIX + 'diagnostic/'

class ImageLedDiagnosticService(ImageLedNativeService):
    def _admission(self):
        if not is_image_led(self.kernel):
            fail('ROUTE', 'native diagnostic requires Image-led workflow')
        state = self.require_g0(mutable=False)
        if state.gate_status.get('G2') == 'passed':
            fail('GATE', 'native diagnostic cannot reopen frozen visual production')
        return self.diagnostic_review()

    def _refs(self):
        state = self.kernel.load()
        selection_ref = state.artifact_heads.get(PREFIX + 'selection', '')
        region_ref = state.artifact_heads.get(PREFIX + 'regions', '')
        if not selection_ref or not region_ref:
            fail('DIAGNOSTIC', 'current selection and region inventory are required')
        selection = self.current_selection(selection_ref)
        inventory = self._current(region_ref, PREFIX + 'regions', 'image-led-region-inventory')
        self._validate_regions(inventory)
        return selection_ref, region_ref, selection, inventory

    def compile_input(self, *, task_id: str, project_revision: int, target_refs: list[str]) -> dict:
        state = self.kernel.load()
        review = self._admission()
        selection_ref, region_ref, selection, inventory = self._refs()
        if target_refs != [selection_ref, region_ref]:
            fail('DIAGNOSTIC', 'diagnostic targets must be current selection and regions')
        if state.revision != project_revision:
            fail('REVISION', 'diagnostic input revision is stale')
        projection = diagnostic_projection(inventory, selection, task_id=task_id)
        return {
            'artifact_type': DIAGNOSTIC_INPUT_KIND,
            'diagnostic_version': DIAGNOSTIC_INPUT_VERSION,
            'handoff_version': DIAGNOSTIC_HANDOFF_VERSION,
            'compiler_version': DIAGNOSTIC_COMPILER_VERSION,
            'purpose': DIAGNOSTIC_PURPOSE,
            'project_id': self.kernel.project_id,
            'project_revision': project_revision,
            'task_id': task_id,
            'selection_ref': selection_ref,
            'region_inventory_ref': region_ref,
            'region_review_ref': self.kernel.load().artifact_heads[PREFIX + 'region-review/' + ArtifactReference.parse(region_ref).sha256],
            'selection': deepcopy(selection),
            'region_review': deepcopy(review),
            'slides': projection['slides'],
        }

    def compile_handoff(self, *, input_payload: dict, diagnostic_ref: str, project_revision: int) -> dict:
        """Build the closed diagnostic renderer handoff from the persisted input projection."""
        task_id = input_payload['task_id']
        output_root = self.kernel.project_root.resolve()
        directory = output_root / 'diagnostics' / task_id
        output_paths = {
            'directory': str(directory),
            'pptx': str(directory / 'native-diagnostic.pptx'),
        }
        for value in output_paths.values():
            path = __import__('pathlib').Path(value)
            if path.is_symlink() or path.resolve().parent != path.parent.resolve() and not path.resolve().is_relative_to(output_root):
                fail('DIAGNOSTIC_HANDOFF', 'diagnostic output path escaped project')
            if not path.resolve().is_relative_to(output_root) or task_id not in path.parts:
                fail('DIAGNOSTIC_HANDOFF', 'diagnostic output path is not task-scoped')
        assets = {}
        for slide in input_payload['slides']:
            for region in slide['regions']:
                appearance = region.get('appearance') or {}
                if region['kind'] not in {'image', 'decoration'}:
                    continue
                ref = appearance.get('asset_ref'); digest = appearance.get('asset_sha256')
                if not ref or not digest:
                    fail('DIAGNOSTIC_HANDOFF', 'diagnostic image region lacks exact asset identity')
                value = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
                if value.get('sha256') != digest:
                    fail('DIAGNOSTIC_HANDOFF', 'diagnostic asset hash changed')
                assets[ref] = {'sha256': digest, 'data_base64': value['data_base64'], 'mime_type': value['mime_type']}
        return {
            'handoff_version': DIAGNOSTIC_HANDOFF_VERSION,
            'compiler_version': DIAGNOSTIC_COMPILER_VERSION,
            'purpose': DIAGNOSTIC_PURPOSE,
            'diagnostic_ref': diagnostic_ref,
            'project_id': self.kernel.project_id,
            'selection_ref': input_payload['selection_ref'],
            'region_inventory_ref': input_payload['region_inventory_ref'],
            'task_id': task_id,
            'slides': deepcopy(input_payload['slides']),
            'assets': assets,
            'output_paths': output_paths,
        }

    @staticmethod
    def input_slot(task_id: str) -> str:
        if not task_id or '/' in task_id:
            fail('DIAGNOSTIC', 'invalid diagnostic task identity')
        return DIAGNOSTIC_INPUT_PREFIX + task_id + '/input'
