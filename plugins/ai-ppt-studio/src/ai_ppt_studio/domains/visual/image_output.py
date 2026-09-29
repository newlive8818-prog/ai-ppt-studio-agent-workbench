"""Closed provider observations and original-image eligibility, using stdlib only.

Reported metadata is not execution-engine proof. Fitness concerns raster geometry
only; it neither changes image bytes nor establishes visible-copy/design quality.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import re

OBSERVATION_VERSION = 'image-led-provider-observation/v1'
IMAGE2 = 'gpt-image-2'
IMAGE2_CODEX = 'gpt-image-2-codex'
SUNBURST = 'gpt-image-2.5-sunburst'
REPORTED_FIELDS = {'model', 'quality', 'size', 'output_format'}


def model_match(reported, *, receiver, model):
    if receiver != 'CRS' or model not in (IMAGE2, SUNBURST):
        raise ValueError('unsupported observation route')
    allowed = {model, IMAGE2_CODEX} if model == IMAGE2 else {model}
    models = []
    for origin in ('response', 'image'):
        row = reported[origin]
        if 'model' in row:
            if row['model'] not in allowed:
                raise ValueError('explicit provider model is outside the requested route')
            models.append(row['model'])
    if IMAGE2_CODEX in models:
        return 'compatible-image2-codex'
    return 'exact' if models else 'not-reported'


def validate_provider_observation(value, *, receiver, model):
    keys = {'version', 'reported', 'model_match', 'independent_engine_proof',
            'response_sha256', 'observed_at_utc'}
    if not isinstance(value, dict) or set(value) != keys or value['version'] != OBSERVATION_VERSION:
        raise ValueError('invalid provider observation schema')
    reported = value['reported']
    if not isinstance(reported, dict) or set(reported) != {'response', 'image'}:
        raise ValueError('invalid provider observation origins')
    for row in reported.values():
        if not isinstance(row, dict) or not set(row) <= REPORTED_FIELDS:
            raise ValueError('invalid provider observation fields')
        for item in row.values():
            # Preserve bounded raw labels, never arbitrary provider text or objects.
            if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,63}', item):
                raise ValueError('invalid provider observation value')
    if (value['independent_engine_proof'] is not False
            or value['model_match'] != model_match(reported, receiver=receiver, model=model)):
        raise ValueError('invalid provider model evidence claim')
    if not isinstance(value['response_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', value['response_sha256']):
        raise ValueError('invalid response digest')
    stamp = value['observed_at_utc']
    if not isinstance(stamp, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\+00:00', stamp):
        raise ValueError('invalid local observation time')
    if datetime.fromisoformat(stamp).utcoffset() != timedelta(0):
        raise ValueError('observation time must be UTC')
    return deepcopy(value)


def output_fitness(payload, dimensions):
    """Scope the current widescreen rule to the two implemented CRS v2 routes.

    Nearest integer height has <= 0.5 px error: |16*h - 9*w| <= 8.
    The 1280x720 floor is a minimum viewing raster, not a readability verdict.
    Legacy input and other injected routes retain their existing contracts.
    """
    if payload.get('payload_version') == 'image-led-image2-repair-input/v1':
        from ai_ppt_studio.domains.visual.image_repair import validate_repair_payload
        payload = validate_repair_payload(payload)['base_payload']
    if (payload.get('payload_version') != 'image-led-image2-input/v2'
            or payload.get('receiver') != 'CRS' or payload.get('model') not in (IMAGE2, SUNBURST)):
        return None
    if (not isinstance(dimensions, (list, tuple)) or len(dimensions) != 2
            or any(type(n) is not int or n < 1 for n in dimensions)):
        raise ValueError('invalid decoded dimensions')
    width, height = dimensions
    reasons = []
    if abs(16 * height - 9 * width) > 8:
        reasons.append('aspect-ratio')
    if width < 1280 or height < 720:
        reasons.append('minimum-resolution')
    return {'version': 'image-led-output-fitness/v1',
            'status': 'needs-revision' if reasons else 'eligible', 'reasons': reasons,
            'target_aspect_ratio': '16:9', 'max_height_rounding_error_px': 0.5,
            'minimum_size': [1280, 720]}
