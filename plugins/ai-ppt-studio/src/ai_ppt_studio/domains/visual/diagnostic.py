"""Closed contracts for pre-G1 Image-led native engineering diagnostics."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, text

DIAGNOSTIC_INPUT_KIND = 'image-led-native-diagnostic-input'
DIAGNOSTIC_RESULT_KIND = 'image-led-native-diagnostic-result'
DIAGNOSTIC_INPUT_VERSION = 'image-led-native-diagnostic-input/v1'
DIAGNOSTIC_HANDOFF_VERSION = 'codex-presentations-image-led-diagnostic/v1'
DIAGNOSTIC_COMPILER_VERSION = 'image-led-diagnostic-compiler/v1'
DIAGNOSTIC_PURPOSE = 'region-diagnostic'
_REQUIRED_REVIEW = frozenset({
    'visible-copy-transcription', 'complete-region-coverage',
    'material-roles', 'source-image-derived-relations',
})
_OPTIONAL_REVIEW = 'faithful-geometry-appearance'


def validate_diagnostic_review_admission(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept exactly four completed structural passes plus appearance pass/unknown."""
    if not isinstance(payload, dict) or set(payload) != {'checks'}:
        fail('DIAGNOSTIC_REVIEW', 'diagnostic admission review schema is not closed')
    checks = payload['checks']
    if not isinstance(checks, list) or len(checks) != 5:
        fail('DIAGNOSTIC_REVIEW', 'diagnostic admission requires five criteria')
    seen: set[str] = set()
    values: dict[str, str] = {}
    for row in checks:
        exact(row, {'criterion', 'result', 'detail'}, 'diagnostic review criterion')
        criterion = row['criterion']
        if criterion in seen or criterion not in _REQUIRED_REVIEW | {_OPTIONAL_REVIEW}:
            fail('DIAGNOSTIC_REVIEW', 'unknown or duplicate diagnostic criterion')
        seen.add(criterion)
        if row['result'] not in {'passed', 'failed', 'not-established'}:
            fail('DIAGNOSTIC_REVIEW', 'unknown diagnostic review result')
        text(row['detail'], 'detail')
        values[criterion] = row['result']
    if seen != _REQUIRED_REVIEW | {_OPTIONAL_REVIEW}:
        fail('DIAGNOSTIC_REVIEW', 'diagnostic admission review is incomplete')
    if any(values[name] != 'passed' for name in _REQUIRED_REVIEW):
        fail('DIAGNOSTIC_REVIEW', 'diagnostic admission requires all structural review criteria passed')
    if values[_OPTIONAL_REVIEW] == 'failed':
        fail('DIAGNOSTIC_REVIEW', 'appearance failed cannot enter diagnostic route')
    return {'checks': deepcopy(checks), 'appearance_result': values[_OPTIONAL_REVIEW]}


def diagnostic_projection(region_inventory: dict[str, Any], selection: dict[str, Any] | None = None, *, task_id: str = '') -> dict[str, Any]:
    """Project exact registered regions into the diagnostic renderer input."""
    if not isinstance(region_inventory, dict) or not isinstance(region_inventory.get('slides'), list):
        fail('DIAGNOSTIC_INPUT', 'region inventory slides are required')
    slides = []
    selected_by_slide = {
        slide.get('target_binding', {}).get('slide_id'): slide.get('selected_copy')
        for slide in (selection or {}).get('slides', [])
        if isinstance(slide, dict)
    }
    for slide in region_inventory['slides']:
        if not isinstance(slide, dict) or not isinstance(slide.get('regions'), list):
            fail('DIAGNOSTIC_INPUT', 'region inventory slide is invalid')
        projected = deepcopy(slide)
        projected['objects'] = [
            {**deepcopy(region), 'object_id': 'object-' + str(region['region_id']),
             'render_mode': 'bitmap' if region['kind'] in {'image', 'decoration'} else 'native'}
            for region in slide['regions']
        ]
        projected['selected_copy'] = deepcopy(selected_by_slide.get(
            slide.get('target_binding', {}).get('slide_id'), {'items': []}))
        if 'region_version' in region_inventory:
            projected['region_version'] = region_inventory['region_version']
        slides.append(projected)
    return {
        'artifact_type': DIAGNOSTIC_INPUT_KIND,
        'diagnostic_version': DIAGNOSTIC_INPUT_VERSION,
        'handoff_version': DIAGNOSTIC_HANDOFF_VERSION,
        'compiler_version': DIAGNOSTIC_COMPILER_VERSION,
        'purpose': DIAGNOSTIC_PURPOSE,
        'task_id': task_id,
        'slides': slides,
    }


def validate_diagnostic_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    fields = {'handoff_version', 'compiler_version', 'purpose', 'diagnostic_ref',
              'project_id', 'selection_ref', 'region_inventory_ref', 'task_id',
              'slides', 'assets', 'output_paths'}
    if not isinstance(payload, dict) or set(payload) != fields:
        fail('DIAGNOSTIC_HANDOFF', 'diagnostic handoff schema is not closed')
    if payload['handoff_version'] != DIAGNOSTIC_HANDOFF_VERSION or payload['compiler_version'] != DIAGNOSTIC_COMPILER_VERSION:
        fail('DIAGNOSTIC_HANDOFF', 'diagnostic compiler version is invalid')
    if payload['purpose'] != DIAGNOSTIC_PURPOSE:
        fail('DIAGNOSTIC_HANDOFF', 'diagnostic purpose is invalid')
    for key in ('diagnostic_ref', 'project_id', 'selection_ref', 'region_inventory_ref', 'task_id'):
        text(payload[key], key)
    if 'plan_ref' in payload:
        fail('DIAGNOSTIC_HANDOFF', 'diagnostic handoff cannot contain plan_ref')
    if not isinstance(payload['slides'], list) or not isinstance(payload['assets'], dict) or not isinstance(payload['output_paths'], dict):
        fail('DIAGNOSTIC_HANDOFF', 'diagnostic handoff collections are invalid')
    return deepcopy(payload)
