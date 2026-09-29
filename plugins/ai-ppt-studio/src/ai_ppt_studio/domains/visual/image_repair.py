"""Closed pre-selection repair projections; stdlib only, no IO or authority writes.

Runtime owns source/task/grant/exclusion evidence and full single-frame decoding.
These validators cannot prove that a local observation is visible in the pixels.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import math
import re
import struct
import zlib

from ai_ppt_studio.domains.materials.image_input_contracts import (
    exact, fail, sha, text, validate_common_rules)
from ai_ppt_studio.domains.materials.image_input_v2 import (
    COPY_VERSION, PAYLOAD_VERSION as BASE_VERSION, validate_semantics)
from ai_ppt_studio.domains.visual.image_led import validate_selected_copy

DIAGNOSTIC_VERSION = 'image-led-content-diagnostic/v1'
PAYLOAD_VERSION = 'image-led-image2-repair-input/v1'
TRANSPORT_VERSION = 'image-led-image2-repair-transport/v1'
RULE_KEYS = frozenset({'typography_tokens', 'color_tokens', 'fallback_fonts', 'title_bar', 'background'})
PNG_HEADER = b'\x89PNG\r\n\x1a\n'


def _local_text(value):
    text(value, 'local diagnostic text')
    if len(value) > 2000:
        fail('REPAIR_DIAGNOSTIC', 'local diagnostic text exceeds its bound')
    try:
        value.encode('utf-8')
    except UnicodeError:
        fail('REPAIR_DIAGNOSTIC', 'local diagnostic text is not valid UTF-8')


def _image_size(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(n) is not int or n <= 0 for n in value)):
        fail('REPAIR_IMAGE', 'image_size requires positive original pixel dimensions')
    return value


def _bbox(value, image_size):
    if not isinstance(value, list) or len(value) != 4:
        fail('REPAIR_REGION', 'bbox requires four original pixel coordinates')
    for n in value:
        if type(n) not in (int, float):
            fail('REPAIR_REGION', 'bbox requires finite non-boolean numbers')
        try:
            finite = math.isfinite(n)
        except OverflowError:
            finite = False
        if not finite:
            fail('REPAIR_REGION', 'bbox requires finite numbers')
    x, y, width, height = value
    if (x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > image_size[0] or y + height > image_size[1]):
        fail('REPAIR_REGION', 'bbox is outside the original image')


def _issues(issues, image_size, *, item_ids=None, external=False):
    _image_size(image_size)
    if not isinstance(issues, list) or not 1 <= len(issues) <= 128:
        fail('REPAIR_ISSUES', 'issues must contain 1 through 128 operations')
    seen_items, seen_regions = set(), set()
    for issue in issues:
        if not isinstance(issue, dict):
            fail('REPAIR_ISSUES', 'each issue must be a closed operation')
        kind = issue.get('kind')
        if kind == 'missing-item':
            fields = {'kind', 'item_id'}
        elif kind == 'replace-item':
            fields = {'kind', 'item_id', 'bbox'}
        elif kind == 'remove-extra-text':
            fields = {'kind', 'bbox'} | (set() if external else {'observed_text'})
        elif kind == 'common-rule':
            fields = {'kind', 'rule_key', 'bbox'}
        else:
            fail('REPAIR_ISSUES', 'unsupported repair operation')
        exact(issue, fields, 'repair issue')
        if 'item_id' in issue:
            identity = text(issue['item_id'], 'item_id')
            if identity in seen_items or item_ids is not None and identity not in item_ids:
                fail('REPAIR_ITEM', 'repair item is absent, repeated, or conflicting')
            seen_items.add(identity)
        if kind == 'common-rule':
            if not isinstance(issue['rule_key'], str) or issue['rule_key'] not in RULE_KEYS:
                fail('REPAIR_RULE', 'repair may only reference an existing common rule field')
        if 'bbox' in issue:
            _bbox(issue['bbox'], image_size)
            key = (kind, tuple(issue['bbox']), issue.get('rule_key'))
            if key in seen_regions:
                fail('REPAIR_ISSUES', 'duplicate repair region operation')
            seen_regions.add(key)
        if 'observed_text' in issue:
            _local_text(issue['observed_text'])
    return deepcopy(issues)


def validate_issues(issues, confirmed_visible_copy, image_size, *, external=False):
    copy = validate_selected_copy(confirmed_visible_copy)
    if copy.get('copy_version') != COPY_VERSION:
        fail('REPAIR_VERSION', 'repair requires the complete v2 visible copy')
    return _issues(issues, image_size, item_ids={i['item_id'] for i in copy['items']}, external=external)


def validate_diagnostic(payload, project_id):
    exact(payload, {'artifact_type', 'diagnostic_version', 'project_id', 'pack_ref',
        'generation_response_ref', 'slide_id', 'page_order', 'image_sha256', 'image_size',
        'reviewer_kind', 'reviewer_role', 'excluded_content_check', 'issues'}, 'content diagnostic')
    if (payload['artifact_type'] != 'image-led-content-diagnostic'
            or payload['diagnostic_version'] != DIAGNOSTIC_VERSION
            or payload['project_id'] != project_id):
        fail('REPAIR_DIAGNOSTIC', 'diagnostic project, type or version does not match')
    text(payload['project_id'], 'project_id')
    for field, kind in (('pack_ref', 'image-led-input-pack'),
                        ('generation_response_ref', 'image-led-generation-response')):
        value = payload[field]
        if not isinstance(value, str) or not re.fullmatch(r'artifact://' + kind + r'/[0-9a-f]{64}', value):
            fail('REPAIR_SOURCE', 'diagnostic must bind an exact typed artifact reference')
    if not isinstance(payload['slide_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', payload['slide_id']):
        fail('REPAIR_PAGE', 'diagnostic must identify an exact page')
    if type(payload['page_order']) is not int or payload['page_order'] <= 0:
        fail('REPAIR_PAGE', 'diagnostic page order must be positive')
    sha(payload['image_sha256']); _image_size(payload['image_size'])
    if payload['reviewer_kind'] != 'engineering' or payload['reviewer_role'] != 'visual-engineering-reviewer':
        fail('REPAIR_REVIEW', 'diagnostic requires its independent engineering role')
    excluded = exact(payload['excluded_content_check'], {'result', 'detail'}, 'source exclusion check')
    if excluded['result'] not in ('passed', 'failed', 'not-established'):
        fail('REPAIR_EXCLUDED', 'unsupported source exclusion check result')
    _local_text(excluded['detail'])
    # No source pack is available to this pure shape validator. Runtime calls
    # validate_issues again with the exact resolved copy before recording/sending.
    _issues(payload['issues'], payload['image_size'])
    return deepcopy(payload)


def _raw_image(encoded, mime):
    text(encoded, 'encoded image')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        fail('REPAIR_IMAGE', 'invalid image encoding')
    valid = ((mime == 'image/png' and raw.startswith(PNG_HEADER))
        or (mime == 'image/jpeg' and raw.startswith(b'\xff\xd8\xff'))
        or (mime == 'image/webp' and raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'))
    if not valid:
        fail('REPAIR_IMAGE', 'image bytes do not match a supported header')
    return raw


def _base_payload(payload):
    exact(payload, {'payload_version', 'receiver', 'model', 'confirmed_visible_copy',
        'page_goal', 'common_rules', 'materials', 'required_atom_ids', 'non_visible_semantics'}, 'repair base payload')
    if (payload['payload_version'] != BASE_VERSION or payload['receiver'] != 'CRS'
            or payload['model'] != 'gpt-image-2' or payload['required_atom_ids'] != []):
        fail('REPAIR_VERSION', 'repair base must be the original supported v2 Image 2 input')
    copy = validate_selected_copy(payload['confirmed_visible_copy'])
    if copy.get('copy_version') != COPY_VERSION:
        fail('REPAIR_VERSION', 'repair base requires complete v2 visible copy')
    text(payload['page_goal'], 'page_goal')
    validate_common_rules(payload['common_rules'])
    if any(not payload['common_rules'][key] for key in ('typography_tokens', 'color_tokens', 'fallback_fonts')):
        fail('REPAIR_RULE', 'repair base requires its original nonempty rule maps')
    if not isinstance(payload['materials'], list):
        fail('REPAIR_MATERIAL', 'repair base materials must be an ordered array')
    seen = set()
    for material in payload['materials']:
        if not isinstance(material, dict) or material.get('type') not in ('text', 'image'):
            fail('REPAIR_MATERIAL', 'unsupported repair base material type')
        fields = {'atom_id', 'type', 'use', 'content_sha256'} | ({'text'} if material['type'] == 'text'
            else {'data_base64', 'mime_type', 'width', 'height'})
        exact(material, fields, 'repair base material')
        identity = text(material['atom_id'], 'atom_id')
        if identity in seen or material['use'] not in ('content-source', 'real-material', 'style-reference'):
            fail('REPAIR_MATERIAL', 'repair base material identity or role is invalid')
        seen.add(identity); sha(material['content_sha256'])
        if material['type'] == 'text':
            try:
                raw = text(material['text'], 'material text').encode('utf-8')
            except UnicodeError:
                fail('REPAIR_MATERIAL', 'material text is not valid UTF-8')
        else:
            _image_size([material['width'], material['height']])
            raw = _raw_image(material['data_base64'], material['mime_type'])
        if hashlib.sha256(raw).hexdigest() != material['content_sha256']:
            fail('REPAIR_MATERIAL', 'repair base material bytes differ from their exact hash')
    validate_semantics(payload['non_visible_semantics'], copy, payload['materials'])
    if payload['non_visible_semantics']['relationship_summary'] != payload['page_goal']:
        fail('REPAIR_SEMANTIC', 'repair base semantics do not match its page goal')


def validate_repair_payload(payload):
    exact(payload, {'payload_version', 'receiver', 'model', 'base_payload', 'edit_target', 'issues'}, 'repair payload')
    if (payload['payload_version'] != PAYLOAD_VERSION or payload['receiver'] != 'CRS'
            or payload['model'] != 'gpt-image-2'):
        fail('REPAIR_VERSION', 'unsupported repair payload route or version')
    _base_payload(payload['base_payload'])
    target = exact(payload['edit_target'], {'role', 'image_sha256', 'data_base64', 'mime_type', 'width', 'height'}, 'edit target')
    if target['role'] != 'edit-target' or target['mime_type'] != 'image/png':
        fail('REPAIR_IMAGE', 'repair target must be the original PNG edit target')
    size = _image_size([target['width'], target['height']])
    raw = _raw_image(target['data_base64'], target['mime_type'])
    if hashlib.sha256(raw).hexdigest() != sha(target['image_sha256']):
        fail('REPAIR_IMAGE', 'repair target bytes differ from the exact image hash')
    # Validate the PNG's actual header dimensions, not caller display geometry.
    # Runtime additionally loads all pixels and proves single-frame PNG content.
    if (len(raw) < 33 or raw[8:16] != b'\x00\x00\x00\rIHDR'
            or list(struct.unpack('>II', raw[16:24])) != size
            or zlib.crc32(raw[12:29]) != struct.unpack('>I', raw[29:33])[0]):
        fail('REPAIR_IMAGE', 'repair target PNG header or dimensions do not match')
    validate_issues(payload['issues'], payload['base_payload']['confirmed_visible_copy'], size, external=True)
    return deepcopy(payload)


def build_repair_payload(base_payload, source_response, issues):
    if not isinstance(source_response, dict) or source_response.get('status') != 'completed':
        fail('REPAIR_SOURCE', 'repair requires an exact completed source response')
    if any(key not in source_response for key in ('image_base64', 'image_sha256', 'image_size', 'image_mime_type')):
        fail('REPAIR_SOURCE', 'completed source response is missing its original image fields')
    size = _image_size(source_response['image_size'])
    _base_payload(base_payload)
    checked = validate_issues(issues, base_payload['confirmed_visible_copy'], size)
    projected = [{key: value for key, value in issue.items() if key != 'observed_text'} for issue in checked]
    payload = {'payload_version': PAYLOAD_VERSION, 'receiver': base_payload['receiver'],
        'model': base_payload['model'], 'base_payload': deepcopy(base_payload),
        'edit_target': {'role': 'edit-target', 'image_sha256': source_response['image_sha256'],
            'data_base64': source_response['image_base64'], 'mime_type': source_response['image_mime_type'],
            'width': size[0], 'height': size[1]}, 'issues': projected}
    return validate_repair_payload(payload)
