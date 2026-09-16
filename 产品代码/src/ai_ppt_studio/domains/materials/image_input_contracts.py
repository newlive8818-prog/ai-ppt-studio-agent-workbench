"""Closed Image-led input contracts. No filesystem access or content rewriting."""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any

from ai_ppt_studio.domains.visual.contracts import _visual_text_map
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.artifacts import canonical_json

USES = frozenset({'content-source', 'real-material', 'style-reference'})


def fail(code: str, detail: str) -> None:
    raise ContractValidationError(f'IMAGE_LED_{code}: {detail}')


def exact(value: Any, fields: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        fail('SCHEMA', f'{name} requires exactly {sorted(fields)}')
    return value


def text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail('SCHEMA', f'{name} must contain text')
    return value  # Validation never changes confirmed copy.


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        fail('HASH', 'expected a lowercase SHA256')
    return value


def location(value: Any) -> dict:
    if not isinstance(value, dict):
        fail('LOCATION', 'source selector must be an object')
    kind = value.get('kind')
    fields = {
        'whole-source': {'kind'},
        'text-range': {'kind', 'start', 'end'},
        'image-region': {'kind', 'x', 'y', 'width', 'height'},
        'page': {'kind', 'page'},
        'object': {'kind', 'page', 'object_id'},
        'table-range': {'kind', 'page', 'object_id', 'row_start', 'row_end', 'col_start', 'col_end'},
    }
    if kind not in fields:
        fail('LOCATION', 'unsupported selector kind')
    exact(value, fields[kind], 'source_location')
    for key, item in value.items():
        if key in {'kind', 'object_id'}:
            text(item, key)
        elif type(item) is not int or item < (1 if key in {'page', 'width', 'height'} else 0):
            fail('LOCATION', f'{key} must be an integer in the source coordinate system')
    for start, end in (('start', 'end'), ('row_start', 'row_end'), ('col_start', 'col_end')):
        if start in value and value[start] >= value[end]:
            fail('LOCATION', 'empty or inverted source range')
    return deepcopy(value)


def contains(outer: dict, inner: dict) -> bool:
    """Unknown cross-coordinate comparisons fail closed at the caller."""
    if outer['kind'] == 'whole-source':
        return True
    if outer == inner:
        return True
    if outer['kind'] == 'page' and inner['kind'] in {'object', 'table-range'}:
        return outer['page'] == inner['page']
    if outer['kind'] == 'object' and inner['kind'] == 'table-range':
        return outer['page'] == inner['page'] and outer['object_id'] == inner['object_id']
    if outer['kind'] != inner['kind']:
        return False
    if outer['kind'] == 'text-range':
        return outer['start'] <= inner['start'] and inner['end'] <= outer['end']
    if outer['kind'] == 'image-region':
        return all((outer['x'] <= inner['x'], outer['y'] <= inner['y'],
            inner['x'] + inner['width'] <= outer['x'] + outer['width'],
            inner['y'] + inner['height'] <= outer['y'] + outer['height']))
    if outer['kind'] == 'table-range':
        return (outer['page'] == inner['page'] and outer['object_id'] == inner['object_id']
                and outer['row_start'] <= inner['row_start'] and inner['row_end'] <= outer['row_end']
                and outer['col_start'] <= inner['col_start'] and inner['col_end'] <= outer['col_end'])
    return False


def overlaps(a: dict, b: dict) -> bool:
    if 'whole-source' in {a['kind'], b['kind']}:
        return True
    if 'page' in a and 'page' in b and a['page'] != b['page']:
        return False
    if a['kind'] == 'page' and b['kind'] in {'object', 'table-range'}:
        return a['page'] == b['page']
    if b['kind'] == 'page' and a['kind'] in {'object', 'table-range'}:
        return a['page'] == b['page']
    if a['kind'] == 'object' and b['kind'] == 'table-range':
        return a['page'] == b['page'] and a['object_id'] == b['object_id']
    if b['kind'] == 'object' and a['kind'] == 'table-range':
        return a['page'] == b['page'] and a['object_id'] == b['object_id']
    if a['kind'] != b['kind']:
        return True  # Unresolved coordinate relationships cannot bypass exclusion.
    if a['kind'] == 'object':
        return a['page'] == b['page'] and a['object_id'] == b['object_id']
    if a['kind'] == 'table-range':
        return (a['page'] == b['page'] and a['object_id'] == b['object_id']
                and a['row_start'] < b['row_end'] and b['row_start'] < a['row_end']
                and a['col_start'] < b['col_end'] and b['col_start'] < a['col_end'])
    if a['kind'] == 'text-range':
        return a['start'] < b['end'] and b['start'] < a['end']
    if a['kind'] == 'image-region':
        return (a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width']
                and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height'])
    return True


def validate_scope(payload: dict, project_id: str) -> dict:
    exact(payload, {'artifact_type', 'project_id', 'receiver', 'model', 'allowed', 'excluded'}, 'authorization scope')
    if payload['artifact_type'] != 'image-led-authorization-scope':
        fail('SCHEMA', 'wrong scope artifact type')
    if payload['project_id'] != project_id:
        fail('PROJECT', 'scope belongs to another project')
    for field in ('receiver', 'model'):
        text(payload[field], field)
    for key in ('allowed', 'excluded'):
        if not isinstance(payload[key], list):
            fail('SCHEMA', f'{key} must be a list')
        for item in payload[key]:
            fields = {'source_sha256', 'source_location'}
            if key == 'allowed':
                fields |= {'uses', 'send_form'}
            exact(item, fields, key)
            sha(item['source_sha256'])
            location(item['source_location'])
            if key == 'allowed':
                if (not isinstance(item['uses'], list) or not item['uses']
                        or any(use not in USES for use in item['uses'])
                        or len(set(item['uses'])) != len(item['uses'])):
                    fail('USE', 'allowed uses must be explicit and unique')
                if item['send_form'] != 'verbatim':
                    fail('CAPABILITY_GAP', 'redaction needs replayable transformation evidence')
    return deepcopy(payload)


def validate_common_rules(value: dict) -> dict:
    exact(value, {'typography_tokens', 'color_tokens', 'fallback_fonts', 'title_bar', 'background'}, 'common rules')
    for key in ('typography_tokens', 'color_tokens', 'fallback_fonts'):
        _visual_text_map(value[key], key)
    text(value['title_bar'], 'title_bar')
    text(value['background'], 'background')
    return deepcopy(value)


def authorize_atom(scope: dict, atom: dict) -> None:
    source_hash = sha(atom['source_sha256'])
    selector = location(atom['source_location'])
    if atom['use'] not in USES:
        fail('USE', 'unsupported material use')
    if any(item['source_sha256'] == source_hash and overlaps(item['source_location'], selector)
           for item in scope['excluded']):
        fail('EXCLUDED', 'source content or intersecting region is excluded')
    if not any(item['source_sha256'] == source_hash and atom['use'] in item['uses']
               and contains(item['source_location'], selector) for item in scope['allowed']):
        fail('UNAUTHORIZED', 'source region or use is outside the persistent authorization')


def validate_policy(payload: dict, project_id: str) -> dict:
    exact(payload, {'artifact_type', 'project_id', 'reading_blueprint_ref', 'source_version',
        'material_inventory_ref', 'evidence_book_ref', 'g0_ref', 'release_target_policy_ref',
        'authorization_scope_ref', 'authorization_ref', 'receiver', 'model', 'common_rules'}, 'input policy')
    if payload['artifact_type'] != 'image-led-input-policy' or payload['project_id'] != project_id:
        fail('PROJECT', 'input policy has the wrong project or type')
    for key in set(payload) - {'common_rules', 'material_inventory_ref'}:
        text(payload[key], key)
    validate_common_rules(payload['common_rules'])
    if not isinstance(payload['material_inventory_ref'], str):
        fail('SCHEMA', 'material_inventory_ref must be a string or empty')
    return deepcopy(payload)


def validate_pack(payload: dict, project_id: str) -> dict:
    if isinstance(payload, dict) and 'pack_version' in payload:
        from ai_ppt_studio.domains.materials.image_input_v2 import validate_pack_v2
        return validate_pack_v2(payload, project_id)
    exact(payload, {'artifact_type', 'project_id', 'input_policy_ref', 'slide_id', 'page_order',
        'confirmed_visible_copy', 'page_goal', 'atoms'}, 'visual input pack')
    if payload['artifact_type'] != 'image-led-input-pack' or payload['project_id'] != project_id:
        fail('PROJECT', 'input pack has the wrong project or type')
    text(payload['input_policy_ref'], 'input_policy_ref')
    if not isinstance(payload['slide_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', payload['slide_id']):
        fail('PAGE', 'slide_id must be an explicit safe page identifier')
    if type(payload['page_order']) is not int or payload['page_order'] < 1:
        fail('PAGE', 'page_order must be positive')
    text(payload['page_goal'], 'page_goal')
    copy = exact(payload['confirmed_visible_copy'], {'title', 'blocks'}, 'confirmed copy')
    text(copy['title'], 'title')
    if not isinstance(copy['blocks'], list):
        fail('SCHEMA', 'copy blocks must be a list')
    seen = set()
    for block in copy['blocks']:
        exact(block, {'block_id', 'text', 'identity'}, 'copy block')
        for key in block:
            text(block[key], key)
        if block['block_id'] in seen:
            fail('COPY', 'duplicate content block')
        seen.add(block['block_id'])
    if not isinstance(payload['atoms'], list):
        fail('SCHEMA', 'atoms must be a list')
    seen = set()
    for atom in payload['atoms']:
        exact(atom, {'atom_id', 'origin_kind', 'origin_id', 'source_ref', 'source_id',
            'source_sha256', 'source_location', 'atom_type', 'use', 'content_sha256'}, 'material atom')
        for key in ('atom_id', 'origin_id', 'source_ref', 'source_id'):
            text(atom[key], key)
        if atom['atom_id'] in seen or atom['origin_kind'] not in {'evidence', 'material-view'}:
            fail('SOURCE', 'atom identity or origin is invalid')
        seen.add(atom['atom_id'])
        if atom['atom_type'] not in {'text', 'image'} or atom['use'] not in USES:
            fail('USE', 'atom type or use is unsupported')
        sha(atom['source_sha256']); sha(atom['content_sha256']); location(atom['source_location'])
    return deepcopy(payload)
