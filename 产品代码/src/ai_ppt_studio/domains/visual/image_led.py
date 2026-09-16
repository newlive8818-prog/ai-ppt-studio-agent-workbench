"""Pure structure/identity validation; no IO, approval or visual-fidelity proof.

The service must resolve current artifacts, real bytes, trusted selection and
independent reviews. The renderer may only execute these exact region values.

Coordinates, font sizes, strokes and offsets use 96DPI CSS pixels. Insets are
top/right/bottom/left; lineSpacing is a multiplier. Table cells are transparent,
borderless text carriers with fixed row/column dimensions: visible backgrounds
or lines require their own finalized shape regions. Merged cells/custom paths
have no v1 representation. V3 explicitly adds filled polygon relation carriers
and natural wrapping while retaining v2 selected copy unchanged. A connector's
text is its semantic meaning; any visible label is a separate selected text
item and native text region.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import math
import re
from typing import Any
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.artifacts import canonical_json
from ai_ppt_studio.kernel.references import ArtifactReference

TARGET_BINDING_FIELDS = frozenset({'project_id','slide_id','page_order','candidate_ref','target_image_ref','target_image_sha256','selected_copy_sha256','material_roles','common_rules_ref','accepted_deviations','design_authority','conversion_mode'})
REGION_FIELDS = frozenset({'region_id','kind','bbox','z_order','content','material_binding','appearance'})
MATERIAL_ROLE_FIELDS = frozenset({'atom_id','source_ref','content_sha256','use'})
REGION_KINDS = frozenset({'text','shape','image','connector','table','decoration'})
REGION_VERSION_V3 = 'image-led-region-inventory/v3'
REGION_KINDS_V3 = REGION_KINDS | {'relation-path'}

__all__ = [
    'TARGET_BINDING_FIELDS', 'REGION_FIELDS', 'MATERIAL_ROLE_FIELDS', 'REGION_KINDS',
    'REGION_VERSION_V3', 'REGION_KINDS_V3',
    'selected_copy_sha256', 'validate_selected_copy', 'validate_target_binding',
    'validate_region_inventory', 'validate_faithful_objects',
]


def _fail(message):
    raise ContractValidationError('IMAGE_LED_CONTRACT: ' + message)


def _closed(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        _fail(name + ' schema is not closed')
    return value


def _region_v3(version):
    if version is not None and version != REGION_VERSION_V3:
        _fail('unsupported region inventory version')
    return version == REGION_VERSION_V3


def _text(value, name, identity=False):
    if not isinstance(value, str) or not value.strip() or (identity and value != value.strip()):
        _fail(name + ' must be a non-empty exact string')
    return value


def _number(value, name, positive=False, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(name + ' must be finite numeric data')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        _fail(name + ' must be finite numeric data')
    if value < minimum or (positive and value <= minimum):
        _fail(name + ' is outside the supported range')
    return value


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(name + ' must be an integer in range')
    return value


def _hash(value, name):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        _fail(name + ' must be lowercase SHA-256')
    return value


def _ref(value, name, kinds=None):
    if not isinstance(value, str):
        _fail(name + ' must be an artifact reference')
    try:
        parsed = ArtifactReference.parse(value)
    except ArtifactReferenceError:
        _fail(name + ' must be an artifact reference')
    if kinds is not None and parsed.kind not in kinds:
        _fail(name + ' artifact kind is invalid')
    return value


def _list(value, name, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        _fail(name + ' must be an array with required items')
    return value


def _material_role(value):
    _closed(value, MATERIAL_ROLE_FIELDS, 'material role')
    _text(value['atom_id'], 'atom_id', True)
    _ref(value['source_ref'], 'source_ref')
    _hash(value['content_sha256'], 'content_sha256')
    if value['use'] not in ('content-source','real-material','style-reference'):
        _fail('material use is unsupported')
    return value


def validate_selected_copy(payload: dict[str, Any]) -> dict[str, Any]:
    """Return validated ordered items, preserving text including whitespace."""
    version = payload.get('copy_version') if isinstance(payload, dict) else None
    v2 = version == 'image-led-selected-copy/v2'
    _closed(payload, {'items','copy_version','title_item_id'} if v2 else {'items'}, 'selected copy')
    items = _list(payload['items'], 'items', True)
    identities, cells, titles = set(), set(), 0
    for item in items:
        if not isinstance(item, dict):
            _fail('selected item must be an object')
        kind = item.get('kind')
        extras = {'text': {'role'}, 'table-cell': {'table_id','row','column'}, 'relation': {'from_item_id','to_item_id','direction'}}
        if not isinstance(kind, str) or kind not in extras:
            _fail('selected item kind is unsupported')
        _closed(item, {'item_id','kind','text'} | extras[kind], 'selected item')
        identity = _text(item['item_id'], 'item_id', True)
        if identity in identities:
            _fail('duplicate selected item')
        identities.add(identity)
        if kind == 'table-cell':
            if not isinstance(item['text'], str):
                _fail('selected table cell text must be a string, including empty cells')
        else:
            _text(item['text'], 'selected text')
        if kind == 'text':
            if item['role'] not in ('title','body','label'):
                _fail('unsupported text role')
            titles += item['role'] == 'title'
        elif kind == 'table-cell':
            cell = (_text(item['table_id'], 'table_id', True), _integer(item['row'], 'row'), _integer(item['column'], 'column'))
            if cell in cells:
                _fail('duplicate selected table cell')
            cells.add(cell)
        else:
            _text(item['from_item_id'], 'from_item_id', True)
            _text(item['to_item_id'], 'to_item_id', True)
            if item['direction'] not in ('forward','backward','both','none'):
                _fail('unsupported relation direction')
    if v2:
        title_id = _text(payload['title_item_id'], 'title_item_id', True)
        if titles != 1 or not any(i['item_id'] == title_id and i.get('role') == 'title' for i in items):
            _fail('selected copy requires one exact title item identity')
    elif titles != 1 or items[0].get('role') != 'title':
        _fail('selected copy requires one explicit first title item')
    non_relations = {i['item_id'] for i in items if i['kind'] != 'relation'}
    for item in items:
        if item['kind'] == 'relation' and (item['from_item_id'] not in non_relations or item['to_item_id'] not in non_relations):
            _fail('relation endpoints do not resolve to selected content')
    return deepcopy(payload)


def selected_copy_sha256(payload: dict[str, Any]) -> str:
    """Hash validated copy payload; this is not an artifact envelope hash."""
    return sha256(canonical_json(validate_selected_copy(payload))).hexdigest()


def handoff_selected_copy(slide, handoff_version):
    """Read bound v2 copy; v1 retains its historical items-only representation."""
    if handoff_version in ('codex-presentations-image-led/v2', 'codex-presentations-image-led/v3'):
        value = validate_selected_copy(slide.get('selected_copy'))
        if value.get('copy_version') != 'image-led-selected-copy/v2':
            _fail('v2 handoff requires original v2 selected copy')
    elif handoff_version == 'codex-presentations-image-led/v1':
        if 'selected_copy' in slide:
            _fail('v1 handoff cannot contain v2 selected copy')
        value = validate_selected_copy({'items':[i for r in slide['regions'] for i in r['content']['items']]})
    else:
        _fail('unsupported handoff version')
    validate_target_binding(slide['target_binding'], selected_copy=value)
    return value


def _style_delta(value: str, name: str) -> None:
    """Require a closed, machine-checkable style delta instead of free prose."""
    _text(value, name)
    pairs = [part.strip() for part in value.split(';') if part.strip()]
    if not pairs:
        _fail(name + ' must contain explicit style key/value pairs')
    allowed = {
        'fontFamily', 'fontSize', 'color', 'bold', 'italic', 'alignment',
        'verticalAlignment', 'lineSpacing', 'fill', 'line', 'shadow',
        'cornerRadius', 'opacity', 'bbox', 'crop',
    }
    seen = set()
    for pair in pairs:
        if pair.count('=') != 1:
            _fail(name + ' must use key=value pairs')
        key, item = (part.strip() for part in pair.split('=', 1))
        if key not in allowed or key in seen or not item:
            _fail(name + ' contains an unsupported or duplicate style key')
        seen.add(key)


def validate_target_binding(payload: dict[str, Any], *, expected_project_id: str | None = None, expected_slide_id: str | None = None, expected_page_order: int | None = None, selected_copy: dict[str, Any] | None = None, allow_proposed_deviations: bool = False) -> dict[str, Any]:
    _closed(payload, TARGET_BINDING_FIELDS, 'TargetBinding')
    for key in ('project_id','slide_id'):
        _text(payload[key], key, True)
    _integer(payload['page_order'], 'page_order', 1)
    for key, expected in (('project_id',expected_project_id),('slide_id',expected_slide_id),('page_order',expected_page_order)):
        if expected is not None and payload[key] != expected:
            _fail(key + ' differs from the current selected target')
    for key, kind in (('candidate_ref','image-led-candidate'),('target_image_ref','image-led-image'),('common_rules_ref','image-led-input-policy')):
        _ref(payload[key], key, {kind})
    for key in ('target_image_sha256','selected_copy_sha256'):
        _hash(payload[key], key)
    if payload['design_authority'] != 'finalized-image' or payload['conversion_mode'] != 'faithful-native':
        _fail('target is not finalized-image faithful-native')
    role_ids = set()
    for role in _list(payload['material_roles'], 'material roles'):
        _material_role(role)
        if role['atom_id'] in role_ids:
            _fail('duplicate material role')
        role_ids.add(role['atom_id'])
    items = None
    if selected_copy is not None:
        selected_copy = validate_selected_copy(selected_copy)
        if sha256(canonical_json(selected_copy)).hexdigest() != payload['selected_copy_sha256']:
            _fail('selected visible copy hash mismatch')
        items = {i['item_id']: i for i in selected_copy['items']}
    deviations = set()
    if payload['accepted_deviations'] and selected_copy is None:
        _fail('selected copy is required to validate accepted deviations')
    material_roles = {role['atom_id'] for role in payload['material_roles']}
    for d in _list(payload['accepted_deviations'], 'accepted deviations'):
        _closed(d, {'candidate_ref','image_sha256','item_id','difference_kind','before','after','decision_ref'}, 'accepted deviation')
        if d['candidate_ref'] != payload['candidate_ref'] or d['image_sha256'] != payload['target_image_sha256']:
            _fail('deviation belongs to another candidate image')
        _text(d['item_id'], 'deviation item_id', True)
        if d['difference_kind'] not in ('text','number','material','style'):
            _fail('unsupported accepted deviation kind')
        _text(d['before'], 'before'); _text(d['after'], 'after')
        if d['before'] == d['after']:
            _fail('accepted deviation must describe an actual change')
        if allow_proposed_deviations:
            if d['decision_ref'] != '':
                _fail('proposed deviation cannot claim a user decision')
        else:
            _ref(d['decision_ref'], 'decision_ref')
        key = (d['item_id'],d['difference_kind'])
        if key in deviations:
            _fail('duplicate accepted deviation')
        deviations.add(key)
        if items is not None:
            if d['item_id'] not in items:
                _fail('deviation item is absent from selected copy')
            if d['difference_kind'] in ('text','number'):
                if d['after'] != items[d['item_id']]['text']:
                    _fail('deviation does not describe selected text')
            elif d['difference_kind'] == 'style':
                _style_delta(d['before'], 'style before')
                _style_delta(d['after'], 'style after')
        if d['difference_kind'] == 'material':
            if d['item_id'] not in material_roles:
                _fail('material deviation must bind a declared material role')
            _ref(d['before'], 'material before')
            _ref(d['after'], 'material after')
        elif d['difference_kind'] == 'style' and items is None:
            _style_delta(d['before'], 'style before')
            _style_delta(d['after'], 'style after')
    return deepcopy(payload)


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        _fail('color must be explicit six-digit hex')


def _text_appearance(value, text, *, region_version=None):
    v3 = _region_v3(region_version)
    _closed(value, {'runs','alignment','verticalAlignment','insets','lineSpacing'} | ({'wrap'} if v3 else set()), 'text appearance')
    if v3 and value['wrap'] not in ('none', 'square'):
        _fail('unsupported natural text wrapping')
    runs = _list(value['runs'], 'font runs', True)
    for run in runs:
        explicit_fill = v3 and isinstance(run, dict) and 'fill' in run
        explicit_spacing = v3 and isinstance(run, dict) and 'characterSpacing' in run
        explicit_outline = v3 and isinstance(run, dict) and 'outline' in run
        _closed(run, {'text','fontFamily','fontSize','bold','italic'} |
                ({'fill'} if explicit_fill else {'color'}) |
                ({'characterSpacing'} if explicit_spacing else set()) |
                ({'outline'} if explicit_outline else set()), 'font run')
        if explicit_spacing and (type(run['characterSpacing']) is not int or
                                 not -400000 <= run['characterSpacing'] <= 400000):
            _fail('characterSpacing requires an integer in native 1/100pt units within [-400000,400000]')
        if explicit_outline:
            outline = run['outline']
            _closed(outline, {'color', 'width'}, 'font outline')
            _color(outline['color'])
            width = outline['width']
            try:
                finite_width = math.isfinite(width)
            except (TypeError, OverflowError):
                finite_width = False
            if isinstance(width, bool) or not isinstance(width, (int, float)) or not finite_width:
                _fail('outline width must be finite numeric data')
            try:
                native_width = width * 9525
                exact_width = native_width == int(native_width)
                finite_native_width = math.isfinite(native_width)
            except (OverflowError, ValueError):
                exact_width = finite_native_width = False
                native_width = 0
            if width <= 0 or not finite_native_width or not exact_width or native_width > 20116800:
                _fail('outline width must map to an exact positive OOXML width within range')
        if not isinstance(run['text'], str) or (not run['text'] and text != ''):
            _fail('font run text cannot be empty')
        _text(run['fontFamily'], 'fontFamily', True); _number(run['fontSize'], 'fontSize', True)
        if explicit_fill:
            if run['fill'] is None:
                _fail('text run requires an explicit visible fill')
            _fill(run['fill'])
            if run['fill']['type'] == 'linear-gradient' and any(
                    stop['offset'] * 100000 != int(stop['offset'] * 100000)
                    for stop in run['fill']['stops']):
                _fail('CapabilityGap: text gradient stops require exact SDK 1/100000 units')
        else:
            _color(run['color'])
        if type(run['bold']) is not bool or type(run['italic']) is not bool:
            _fail('font bold and italic must be boolean')
    if ''.join(run['text'] for run in runs) != text:
        _fail('font runs changed selected visible text')
    if value['alignment'] not in ('left','center','right','justify') or value['verticalAlignment'] not in ('top','middle','bottom'):
        _fail('unsupported text alignment')
    if len(_list(value['insets'], 'insets')) != 4:
        _fail('insets need top/right/bottom/left')
    for inset in value['insets']:
        _number(inset, 'inset')
    _number(value['lineSpacing'], 'lineSpacing', True)


def _bbox(value, canvas=None):
    if not isinstance(value, list) or len(value) != 4:
        _fail('bbox requires x/y/width/height in 96DPI CSS pixels')
    for i, coordinate in enumerate(value):
        _number(coordinate, 'bbox coordinate', i >= 2)
    if canvas and (value[0]+value[2] > canvas['width'] or value[1]+value[3] > canvas['height']):
        _fail('region bbox is outside canvas')


def _line(value):
    _closed(value, {'color','width','dash'}, 'line')
    _color(value['color'])
    _number(value['width'], 'line width', True)
    if value['dash'] not in ('solid','dash','dot'):
        _fail('CapabilityGap: unsupported line dash')


def _fill(value):
    if value is None:
        return
    if not isinstance(value, dict):
        _fail('fill must be null or an explicit fill object')
    if value.get('type') == 'solid':
        _closed(value, {'type','color'}, 'solid fill')
        _color(value['color'])
    elif value.get('type') == 'linear-gradient':
        _closed(value, {'type','angle','stops'}, 'linear gradient')
        if _number(value['angle'], 'gradient angle') >= 360:
            _fail('gradient angle must be in [0,360)')
        stops = _list(value['stops'], 'gradient stops', True)
        offsets = []
        for stop in stops:
            _closed(stop, {'offset','color'}, 'gradient stop')
            offset = _number(stop['offset'], 'gradient offset')
            if offset > 1:
                _fail('gradient offset must be in [0,1]')
            offsets.append(offset)
            _color(stop['color'])
        if len(offsets) < 2 or offsets[0] != 0 or offsets[-1] != 1 or any(a >= b for a, b in zip(offsets, offsets[1:])):
            _fail('gradient stops must cover 0..1 in strict order')
    else:
        _fail('CapabilityGap: unsupported fill kind')


def _image_appearance(value):
    selected_crop = isinstance(value, dict) and 'render_source' in value
    _closed(value, {'asset_ref','asset_sha256','crop'} | ({'render_source'} if selected_crop else set()), 'image appearance')
    if selected_crop and value['render_source'] != 'selected-image-crop':
        _fail('unsupported image render source')
    _ref(value['asset_ref'], 'image asset_ref', {'image-led-image','image-led-crop','image-asset','material-image'})
    _hash(value['asset_sha256'], 'image asset_sha256')
    crop = value['crop']
    _bbox(crop)
    if crop[0]+crop[2] > 1 or crop[1]+crop[3] > 1:
        _fail('image crop must be a normalized source rectangle')


def _shape_appearance(value, bbox, *, region_version=None):
    polygon = _region_v3(region_version) and isinstance(value, dict) and value.get('geometry') == 'polygon'
    _closed(value, {'geometry','corner_radius','fill','line','shadow'} | ({'paths'} if polygon else set()), 'shape appearance')
    if polygon:
        _polygon_paths(value['paths'], bbox)
    elif value['geometry'] not in ('rect','round-rect','ellipse'):
        _fail('CapabilityGap: unsupported shape geometry or path')
    radius = _number(value['corner_radius'], 'corner radius')
    if radius > min(bbox[2:])/2 or (value['geometry'] != 'round-rect' and radius != 0):
        _fail('corner radius does not match shape geometry')
    _fill(value['fill'])
    if value['line'] is not None:
        _line(value['line'])
    if value['shadow'] is not None:
        shadow = _closed(value['shadow'], {'color','opacity','blur','offset_x','offset_y'}, 'shadow')
        _color(shadow['color'])
        if _number(shadow['opacity'], 'shadow opacity') > 1:
            _fail('shadow opacity must be in [0,1]')
        _number(shadow['blur'], 'shadow blur')
        _number(shadow['offset_x'], 'shadow x', minimum=-math.inf)
        _number(shadow['offset_y'], 'shadow y', minimum=-math.inf)


def _table_appearance(value, items, bbox, *, region_version=None):
    _closed(value, {'row_heights','column_widths','cells'}, 'table appearance')
    heights = _list(value['row_heights'], 'table row heights', True)
    widths = _list(value['column_widths'], 'table column widths', True)
    for dimension in heights + widths:
        _number(dimension, 'table dimension', True)
    if not math.isclose(sum(widths), bbox[2], rel_tol=1e-12) or not math.isclose(sum(heights), bbox[3], rel_tol=1e-12):
        _fail('table dimensions differ from finalized region bbox')
    if len(items) != len(heights)*len(widths) or any(not isinstance(i, dict) or i.get('kind') != 'table-cell' for i in items):
        _fail('table needs every selected cell as native content')
    by_position = {}
    tables = set()
    for item in items:
        position = (_integer(item.get('row'), 'cell row'), _integer(item.get('column'), 'cell column'))
        if position in by_position or position[0] >= len(heights) or position[1] >= len(widths):
            _fail('table cell is duplicated or outside grid')
        by_position[position] = item
        tables.add(_text(item.get('table_id'), 'table_id', True))
    if len(tables) != 1:
        _fail('one region cannot combine different selected tables')
    cells = _list(value['cells'], 'table cells', True)
    if len(cells) != len(items):
        _fail('table appearance must cover every selected cell')
    seen = set()
    for cell in cells:
        _closed(cell, {'row','column','item_id','style'}, 'table cell')
        position = (_integer(cell['row'], 'cell row'), _integer(cell['column'], 'cell column'))
        if position in seen or position not in by_position or cell['item_id'] != by_position[position]['item_id']:
            _fail('table appearance has wrong or repeated selected cell')
        seen.add(position)
        _text_appearance(cell['style'], by_position[position]['text'], region_version=region_version)


def _connector_appearance(value, items, bbox):
    _closed(value, {'from_region_id','to_region_id','start','end','line','arrow','meaning'}, 'connector appearance')
    if len(items) != 1 or not isinstance(items[0], dict) or items[0].get('kind') != 'relation':
        _fail('connector requires one selected relation')
    for key in ('from_region_id','to_region_id'):
        _text(value[key], key, True)
    for key in ('start','end'):
        point = _list(value[key], key)
        if len(point) != 2:
            _fail('connector endpoint needs x/y coordinates')
        x, y = (_number(point[0], 'endpoint x'), _number(point[1], 'endpoint y'))
        if not (bbox[0] <= x <= bbox[0]+bbox[2] and bbox[1] <= y <= bbox[1]+bbox[3]):
            _fail('connector endpoint is outside its finalized region')
    _line(value['line'])
    if value['arrow'] != items[0].get('direction') or value['meaning'] != items[0].get('text'):
        _fail('connector changed selected relation direction or meaning')


def _polygon_paths(paths, bbox):
    """Finite data-only contours; preserve command order and winding exactly."""
    _list(paths, 'polygon paths', True)
    if len(paths) > 16:
        _fail('polygon path count exceeds supported bounds')
    command_count = 0
    for path in paths:
        _closed(path, {'width','height','commands'}, 'polygon path')
        width = _number(path['width'], 'path width', True)
        height = _number(path['height'], 'path height', True)
        if [width, height] != bbox[2:]:
            _fail('polygon viewport must equal finalized region dimensions')
        commands = _list(path['commands'], 'polygon commands', True)
        command_count += len(commands)
        if command_count > 4096:
            _fail('polygon command count exceeds supported bounds')
        points = None
        contours = 0
        for command in commands:
            if not isinstance(command, dict) or len(command) != 1:
                _fail('polygon command must contain exactly one operation')
            operation = next(iter(command))
            if operation not in ('moveTo', 'lineTo', 'close'):
                _fail('unsupported polygon command')
            if operation == 'close':
                _closed(command['close'], set(), 'polygon close')
                if points is None or len(set(points)) < 3:
                    _fail('polygon contour needs at least three distinct vertices')
                # Normalize only for the degeneracy check, never the stored path.
                # Finite viewport coordinates can still overflow when multiplied.
                area = math.fsum((x1/width)*(y2/height)-(x2/width)*(y1/height)
                    for (x1,y1),(x2,y2) in zip(points, points[1:]+points[:1]))
                if not math.isfinite(area) or area == 0:
                    _fail('polygon contour must have finite nonzero area')
                contours += 1
                points = None
                continue
            point = _closed(command[operation], {'x','y'}, 'polygon point')
            x = _number(point['x'], 'polygon x')
            y = _number(point['y'], 'polygon y')
            if x > width or y > height:
                _fail('polygon vertex is outside its viewport')
            if operation == 'moveTo':
                if points is not None:
                    _fail('polygon contour must close before the next move')
                points = [(x, y)]
            elif points is None:
                _fail('polygon contour must start with moveTo')
            else:
                points.append((x, y))
        if points is not None or not contours:
            _fail('every polygon contour must close explicitly')


def _relation_path_appearance(value, bbox):
    _closed(value, {'paths','fill','line','relation_binding'}, 'relation path appearance')
    _polygon_paths(value['paths'], bbox)
    if value['fill'] is None:
        _fail('relation path requires an explicit surface fill')
    _fill(value['fill'])
    if value['line'] is not None:
        _line(value['line'])
    binding = value['relation_binding']
    if not isinstance(binding, dict):
        _fail('relation path requires source-image-derived binding')
    base = {'origin','target_image_sha256','kind'}
    if binding.get('kind') == 'directed-edge':
        region_endpoints = 'from_region_id' in binding or 'to_region_id' in binding
        endpoints = ('from_region_id','to_region_id') if region_endpoints else ('from_item_id','to_item_id')
        _closed(binding, base | set(endpoints) | {'direction'}, 'directed relation binding')
        for key in endpoints:
            _text(binding[key], key, True)
        if binding[endpoints[0]] == binding[endpoints[1]]:
            _fail('directed relation needs two distinct source endpoints')
        if binding['direction'] not in ('forward','backward','both'):
            _fail('unsupported directed relation direction')
    elif binding.get('kind') == 'feedback-symbol':
        _closed(binding, base | {'anchor_item_id'}, 'feedback relation binding')
        _text(binding['anchor_item_id'], 'anchor_item_id', True)
    else:
        _fail('unsupported source-image-derived relation kind')
    if binding['origin'] != 'source-image-derived':
        _fail('relation path must derive from the selected source image')
    _hash(binding['target_image_sha256'], 'relation target image hash')


def _source_image_relationships(regions, *, target=None):
    """Resolve same-slide source carriers without inferring members or geometry."""
    owners = {item['item_id']: region['region_id'] for region in regions
              for item in region['content']['items'] if item['kind'] in ('text','table-cell')}
    by_id = {region['region_id']: region for region in regions}
    for region in regions:
        if region['kind'] != 'relation-path':
            continue
        binding = region['appearance']['relation_binding']
        if target is not None and binding['target_image_sha256'] != target['target_image_sha256']:
            _fail('derived relation differs from its selected image identity')
        if binding['kind'] == 'directed-edge' and 'from_region_id' in binding:
            for key in ('from_region_id','to_region_id'):
                endpoint = by_id.get(binding[key])
                if endpoint is None or endpoint['kind'] not in ('text','table','shape','image'):
                    _fail('derived relation endpoint must resolve to a same-slide source region')
                if endpoint['kind'] == 'shape' and endpoint['appearance']['fill'] is None and endpoint['appearance']['line'] is None:
                    _fail('derived relation cannot use an invisible synthetic container')
            continue
        keys = ('from_item_id','to_item_id') if binding['kind'] == 'directed-edge' else ('anchor_item_id',)
        if any(binding[key] not in owners for key in keys):
            _fail('derived relation endpoint does not resolve to original selected content')


def _relationships(regions):
    owners = {item['item_id']: region['region_id'] for region in regions for item in region['content']['items']}
    fragmented = {r['region_id'] for r in regions if r['kind'] == 'text' and 'fragments' in r['appearance']}
    for region in regions:
        if region['kind'] != 'connector':
            continue
        item = region['content']['items'][0]
        appearance = region['appearance']
        if appearance['from_region_id'] != owners.get(item.get('from_item_id')) or appearance['to_region_id'] != owners.get(item.get('to_item_id')):
            _fail('connector endpoint region differs from selected relation')
        if any(appearance[key] in fragmented for key in ('from_region_id','to_region_id')):
            _fail('CapabilityGap: native connector cannot choose a text fragment endpoint')


def _text_region_appearance(value, text, bbox, *, region_version=None):
    if not (_region_v3(region_version) and isinstance(value, dict) and 'fragments' in value):
        return _text_appearance(value, text, region_version=region_version)
    _closed(value, {'fragments'}, 'fragmented text appearance')
    cursor = 0
    for fragment in _list(value['fragments'], 'text fragments', True):
        _closed(fragment, {'span','bbox','appearance'}, 'text fragment')
        span = fragment['span']
        if not isinstance(span, list) or len(span) != 2:
            _fail('fragment span requires [start,end) Unicode codepoints')
        start = _integer(span[0], 'fragment start'); end = _integer(span[1], 'fragment end')
        if start != cursor or end <= start or end > len(text):
            _fail('fragment spans must cover original text once in contiguous order')
        _bbox(fragment['bbox'])
        x, y, w, h = fragment['bbox']; rx, ry, rw, rh = bbox
        if x < rx or y < ry or x+w > rx+rw or y+h > ry+rh:
            _fail('fragment bbox must remain inside its source region')
        _text_appearance(fragment['appearance'], text[start:end], region_version=region_version)
        cursor = end
    if cursor != len(text):
        _fail('fragment spans do not cover the complete original text')


def native_object_projections(objects):
    """Expand validated logical text objects without changing their source item."""
    expanded = []
    for obj in objects:
        if obj['kind'] == 'text' and 'fragments' in obj['appearance']:
            for fragment in obj['appearance']['fragments']:
                start, end = fragment['span']
                expanded.append({**deepcopy(obj), 'object_id':obj['object_id']+f'::fragment:{start}:{end}',
                    'span':deepcopy(fragment['span']), 'bbox':deepcopy(fragment['bbox']),
                    'appearance':deepcopy(fragment['appearance'])})
        else:
            expanded.append(deepcopy(obj))
    return expanded


def _region(value, canvas=None, *, region_version=None):
    v3 = _region_v3(region_version)
    _closed(value, REGION_FIELDS, 'region')
    _text(value['region_id'], 'region_id', True); _bbox(value['bbox'], canvas); _integer(value['z_order'], 'z_order')
    _closed(value['content'], {'items'}, 'region content')
    items = _list(value['content']['items'], 'region content items')
    for item in items:
        if not isinstance(item, dict):
            _fail('region content item must be an object')
        kind = item.get('kind')
        extras = {'text': {'role'}, 'table-cell': {'table_id','row','column'}, 'relation': {'from_item_id','to_item_id','direction'}}
        if not isinstance(kind, str) or kind not in extras:
            _fail('unsupported region content item kind')
        _closed(item, {'item_id','kind','text'} | extras[kind], 'region content item')
        _text(item['item_id'], 'region content item_id', True)
        if kind == 'table-cell':
            if not isinstance(item['text'], str):
                _fail('table cell text must be a string')
        else:
            _text(item['text'], 'region content text')
        if kind == 'text' and item['role'] not in ('title','body','label'):
            _fail('region text role is unsupported')
        if kind == 'relation':
            _text(item['from_item_id'], 'from_item_id', True)
            _text(item['to_item_id'], 'to_item_id', True)
            if item['direction'] not in ('forward','backward','both','none'):
                _fail('region relation direction is unsupported')
    if value['material_binding'] is not None:
        _material_role(value['material_binding'])
        if value['kind'] in ('shape','table','connector','relation-path'):
            _fail('CapabilityGap: material binding has no exact extraction hash rule for this carrier')
    if value['kind'] == 'text':
        if len(items) != 1 or not isinstance(items[0], dict) or items[0].get('kind') != 'text':
            _fail('text region requires one selected text item')
        _text_region_appearance(value['appearance'], items[0].get('text'), value['bbox'], region_version=region_version)
        if value['material_binding'] is not None:
            actual = sha256(items[0]['text'].encode('utf-8')).hexdigest()
            if actual != value['material_binding']['content_sha256']:
                _fail('text bytes identity differs from selected material')
    elif value['kind'] == 'table':
        _table_appearance(value['appearance'], items, value['bbox'], region_version=region_version)
    elif value['kind'] == 'connector':
        _connector_appearance(value['appearance'], items, value['bbox'])
    elif value['kind'] == 'relation-path' and v3:
        if items:
            _fail('source-image-derived relation cannot add selected visible copy')
        _relation_path_appearance(value['appearance'], value['bbox'])
    elif value['kind'] in ('image','decoration','shape'):
        if items:
            _fail('image/decoration/shape cannot conceal semantic text/table/relations')
        if value['kind'] == 'shape':
            _shape_appearance(value['appearance'], value['bbox'], region_version=region_version)
        else:
            _image_appearance(value['appearance'])
            selected_crop = 'render_source' in value['appearance']
            if selected_crop and (not v3 or value['kind'] != 'image' or value['material_binding'] is None or value['material_binding']['use'] != 'real-material'):
                _fail('selected-image-crop requires a v3 image bound to original real material')
            if not selected_crop and value['material_binding'] is not None and value['appearance']['asset_sha256'] != value['material_binding']['content_sha256']:
                _fail('image bytes identity differs from selected real material')
    else:
        _fail('CapabilityGap: no executable schema for region kind')


def validate_region_inventory(payload: dict[str, Any], selection_payload: dict[str, Any], *, selection_ref: str | None = None) -> dict[str, Any]:
    """Resolve selection in the service first; confirmation fields stay there."""
    region_version = payload.get('region_version') if isinstance(payload, dict) else None
    v3 = _region_v3(region_version)
    _closed(payload, {'artifact_type','selection_ref','project_id','slides'} | ({'region_version'} if v3 else set()), 'RegionInventory')
    if payload['artifact_type'] != 'image-led-region-inventory':
        _fail('invalid RegionInventory artifact type')
    _ref(payload['selection_ref'], 'selection_ref', {'image-led-selection'})
    if selection_ref is not None and payload['selection_ref'] != selection_ref:
        _fail('stale RegionInventory selection ref')
    if not isinstance(selection_payload, dict) or payload['project_id'] != selection_payload.get('project_id'):
        _fail('RegionInventory project differs from selection')
    slides = _list(payload['slides'], 'inventory slides', True)
    selected_slides = _list(selection_payload.get('slides'), 'selected slides', True)
    if len(slides) != len(selected_slides):
        _fail('RegionInventory must cover every selected slide')
    slide_ids = set()
    for order, (slide, selected) in enumerate(zip(slides, selected_slides), 1):
        _closed(slide, {'target_binding','canvas','source_image_size','regions'}, 'inventory slide')
        if not isinstance(selected, dict):
            _fail('selected slide must be an object')
        copy = validate_selected_copy(selected.get('selected_copy'))
        if v3 and copy.get('copy_version') != 'image-led-selected-copy/v2':
            _fail('v3 regions require the original v2 selected visible copy')
        target = validate_target_binding(selected.get('target_binding'), expected_project_id=payload['project_id'], expected_page_order=order, selected_copy=copy)
        validate_target_binding(slide['target_binding'], selected_copy=copy)
        if slide['target_binding'] != target or target['slide_id'] in slide_ids:
            _fail('inventory target differs or is duplicated')
        slide_ids.add(target['slide_id'])
        canvas = _closed(slide['canvas'], {'width','height','dpi'}, 'canvas')
        source = _closed(slide['source_image_size'], {'width','height'}, 'source image size')
        for key in ('width','height'):
            _number(canvas[key], 'canvas '+key, True); _integer(source[key], 'source '+key, 1)
        if type(canvas['dpi']) is not int or canvas['dpi'] != 96:
            _fail('canvas dpi must be 96')
        if not math.isclose(canvas['width']/canvas['height'], source['width']/source['height'], rel_tol=1e-12):
            _fail('canvas must preserve source image aspect ratio')
        covered, ids, z_orders, material_ids = [], set(), set(), set()
        for region in _list(slide['regions'], 'regions', True):
            _region(region, canvas, region_version=region_version)
            if region['kind'] == 'image' and region['appearance'].get('render_source') == 'selected-image-crop':
                appearance = region['appearance']
                if appearance['asset_ref'] != target['target_image_ref'] or appearance['asset_sha256'] != target['target_image_sha256']:
                    _fail('selected-image-crop must use this slide exact selected image identity')
            if region['region_id'] in ids or region['z_order'] in z_orders:
                _fail('region IDs and z_order must be unique')
            ids.add(region['region_id']); z_orders.add(region['z_order'])
            covered.extend(region['content']['items'])
            if region['material_binding'] is not None and region['material_binding'] not in target['material_roles']:
                _fail('region material is absent from selected material roles')
            if region['material_binding'] is not None:
                material_ids.add(region['material_binding']['atom_id'])
        required_material_ids = {role['atom_id'] for role in target['material_roles']
                                 if role['use'] == 'real-material'}
        if not required_material_ids.issubset(material_ids):
            _fail('selected real material must be carried by at least one verified region')
        if covered != copy['items']:
            _fail('region content must cover selected items exactly once in order')
        _relationships(slide['regions'])
        if v3:
            _source_image_relationships(slide['regions'], target=target)
    return deepcopy(payload)


def validate_faithful_objects(regions: list[dict[str, Any]], objects: list[dict[str, Any]], *, region_version=None) -> list[dict[str, Any]]:
    """Check exact carriers; validate_region_inventory must establish coverage first."""
    v3 = _region_v3(region_version)
    _list(regions, 'regions', True); _list(objects, 'objects', True)
    by_id = {}
    for region in regions:
        _region(region, region_version=region_version)
        if region['region_id'] in by_id:
            _fail('duplicate region ID')
        by_id[region['region_id']] = region
    if len(objects) != len(regions):
        _fail('every region needs exactly one faithful object')
    _relationships(regions)
    if v3:
        _source_image_relationships(regions)
    ids, mapped = set(), set()
    for obj in objects:
        _closed(obj, REGION_FIELDS | {'object_id','render_mode'}, 'native object')
        identity = _text(obj['object_id'], 'object_id', True)
        region_id = obj['region_id']
        if identity in ids or not isinstance(region_id, str) or region_id in mapped or region_id not in by_id:
            _fail('object and region mappings must be unique and complete')
        ids.add(identity); mapped.add(region_id)
        projection = {key: obj[key] for key in REGION_FIELDS}
        _region(projection, region_version=region_version)
        if projection != by_id[region_id]:
            _fail('native object changed finalized region content or design')
        mode = 'bitmap' if obj['kind'] in ('image','decoration') else 'native'
        if obj['render_mode'] != mode:
            _fail('semantic text/table/relationships must remain native')
    expanded_ids = [obj['object_id'] for obj in native_object_projections(objects)]
    if len(expanded_ids) != len(set(expanded_ids)):
        _fail('expanded native object identities collide')
    return deepcopy(objects)
