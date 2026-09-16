"""Byte-backed renderer intake. No self-attested status promotes an anchor.

Preflight performs no business/file writes. It validates actual PPTX structure,
ordered objects, verbatim text and material bytes as well as all file digests.
Visual fidelity remains a separate, task-bound independent review dimension.
"""
from __future__ import annotations
from copy import deepcopy
import base64
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import stat
import subprocess
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from PIL import Image

from ai_ppt_studio.application.artifact_guards import require_exact_ref, require_revision, resolve_kind
from ai_ppt_studio.application.image_led_ooxml import A, P, R, NS, Package, paragraphs
from ai_ppt_studio.application.image_led_service import ImageLedService, PREFIX
from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, sha, text
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, validate_faithful_objects, REGION_VERSION_V3
from ai_ppt_studio.kernel.references import ArtifactReference

RESULT_SLOT = PREFIX + 'build-result'
DIMENSIONS = frozenset({'content', 'visual', 'editability', 'common-rules'})
OUTPUT_FIELDS = frozenset({'status', 'project_id', 'selection_ref', 'region_inventory_ref', 'plan_ref',
    'task_id', 'handoff_sha256', 'pptx_path', 'pptx_sha256', 'renders', 'mapping', 'files',
    'comparisons', 'visual_fidelity', 'user_acceptance', 'target_powerpoint'})
OUTPUT_DEPENDENCIES = ('visual/anchors', 'visual/target', 'visual/review/G2/', 'visual/quality',
    PREFIX + 'native-pptx', PREFIX + 'editability', PREFIX + 'preflight',
    'visual/contract-review', 'visual/contract-marks', 'visual/feedback', 'visual/marks')


def _check(condition, message):
    if not condition:
        fail('RESULT', message)


def _json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            _check(key not in value, 'duplicate JSON property in output evidence')
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda x: fail('RESULT', 'non-finite JSON evidence'))
    except (ValueError, UnicodeError) as error:
        fail('RESULT', 'unreadable JSON evidence: ' + type(error).__name__)


def _verify_render_snapshots(pptx, handoff, renders, comparisons):
    """Re-import this exact in-memory PPTX, never a second mutable path read."""
    bundle = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
    node = Path(os.environ.get('C2_RUNTIME_NODE', str(bundle / 'node/bin/node')))
    modules = Path(os.environ.get('C2_RUNTIME_NODE_MODULES', str(bundle / 'node/node_modules')))
    script = Path(__file__).resolve().parents[3] / 'scripts/image-led-native.mjs'
    _check(node.is_file() and (modules / '@oai/artifact-tool').is_dir() and script.is_file(),
           'CapabilityGap: bundled native render verification runtime unavailable')
    snapshots = {'pptx_base64': base64.b64encode(pptx).decode(), 'handoff': handoff,
                 'renders': renders, 'comparisons': comparisons}
    runner = """
import fs from 'node:fs';import {pathToFileURL} from 'node:url';
const {verifyOutputSnapshots}=await import(pathToFileURL(process.argv[1]).href);
const value=await verifyOutputSnapshots(JSON.parse(fs.readFileSync(0,'utf8')),{nodeModulesRoot:process.argv[2]});
console.log(JSON.stringify(value));
"""
    try:
        result = subprocess.run([str(node), '--input-type=module', '-e', runner, str(script), str(modules)],
            input=json.dumps(snapshots), text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail('RESULT', 'CapabilityGap: current-PPTX re-render verification unavailable: ' + type(error).__name__)
    _check(result.returncode == 0, 'current PPTX/render/comparison derivation failed: ' + result.stderr[-1200:])
    checked = _json(result.stdout)
    _check(checked == {'pptx_sha256': hashlib.sha256(pptx).hexdigest(), 'verified_pages': len(handoff['slides'])},
           'native render verification returned a different output identity')


def _file(root, path, expected_hash):
    sha(expected_hash)
    _check(isinstance(path, str), 'result file needs an exact absolute path')
    root, file = Path(root).absolute(), Path(path)
    _check(file.is_absolute() and str(file) == os.path.normpath(path), 'noncanonical result path')
    try:
        parts = file.relative_to(root).parts
    except ValueError:
        fail('RESULT', 'result file escaped project root')
    _check(bool(parts), 'result path cannot be project root')
    current = root
    try:
        for part in parts:
            current /= part
            _check(not current.is_symlink(), 'symlink result path is forbidden')
        _check(file.resolve().is_relative_to(root.resolve()), 'physical result path escaped project')
        with file.open('rb') as stream:
            metadata = os.fstat(stream.fileno())
            _check(stat.S_ISREG(metadata.st_mode) and metadata.st_size <= 512 * 1024 * 1024,
                   'unsupported result file')
            raw = stream.read()
    except OSError as error:
        fail('RESULT', 'result file unavailable: ' + type(error).__name__)
    _check(hashlib.sha256(raw).hexdigest() == expected_hash, 'actual output file hash mismatch')
    return raw


def _numbers(node, attributes, expected, scale=1):
    _check(node is not None, 'missing native geometry')
    try:
        actual = [float(node.get(k, 'nan')) / scale for k in attributes]
    except ValueError:
        fail('RESULT', 'invalid native geometry')
    _check(len(actual) == len(expected) and all(math.isfinite(x) and abs(x - y) <= 1 / 9525
        for x, y in zip(actual, expected)), 'native object geometry changed')


def _xml_fields(node, allowed, *, required=(), repeated=(), attrs=()):
    """A closed OOXML carrier: unknown visible properties are unsupported."""
    _check(node is not None, 'missing native XML carrier')
    def qname(key):
        prefix, name = key.split(':')
        return '{' + NS[prefix] + '}' + name
    names = [child.tag for child in node]
    _check(not set(names) - {qname(key) for key in allowed}, 'unsupported native visual XML property')
    _check(not set(node.attrib) - set(attrs), 'unsupported native visual XML attribute')
    for key in required:
        _check(qname(key) in names, 'native XML carrier property missing')
    for key in set(allowed) - set(repeated):
        _check(names.count(qname(key)) <= 1, 'ambiguous native visual XML property')


def _carrier_check(node, obj):
    kind = obj['kind']
    nv_tag = {'text': 'nvSpPr', 'shape': 'nvSpPr', 'relation-path': 'nvSpPr', 'image': 'nvPicPr', 'decoration': 'nvPicPr',
              'table': 'nvGraphicFramePr', 'connector': 'nvCxnSpPr'}[kind]
    if kind == 'table':
        _xml_fields(node, ['p:' + nv_tag, 'p:xfrm', 'a:graphic'], required=['p:' + nv_tag, 'p:xfrm', 'a:graphic'])
    else:
        extra = ['p:txBody'] if kind == 'text' else ['p:blipFill'] if kind in {'image', 'decoration'} else []
        _xml_fields(node, ['p:' + nv_tag, 'p:spPr', *extra], required=['p:' + nv_tag, 'p:spPr', *extra])
    nv = node.find('p:' + nv_tag, NS)
    nv_property = {'text': 'cNvSpPr', 'shape': 'cNvSpPr', 'relation-path': 'cNvSpPr', 'image': 'cNvPicPr', 'decoration': 'cNvPicPr',
                   'table': 'cNvGraphicFramePr', 'connector': 'cNvCxnSpPr'}[kind]
    _xml_fields(nv, ['p:cNvPr', 'p:' + nv_property, 'p:nvPr'], required=['p:cNvPr', 'p:' + nv_property, 'p:nvPr'])
    name = nv.find('p:cNvPr', NS)
    _xml_fields(name, ['a:extLst'], attrs=['id', 'name', 'descr', 'title'])
    extension_list = name.find('a:extLst', NS)
    if extension_list is not None:
        _xml_fields(extension_list, ['a:ext'], required=['a:ext'])
        extension = extension_list.find('a:ext', NS)
        _check(extension.attrib == {'uri': '{FF2B5EF4-FFF2-40B4-BE49-F238E27FC236}'} and len(extension) == 1
               and extension[0].tag == '{http://schemas.microsoft.com/office/drawing/2014/main}creationId'
               and set(extension[0].attrib) == {'id'} and len(extension[0]) == 0,
               'unsupported native visual extension')
    inner = nv.find('p:' + nv_property, NS)
    locks = 'picLocks' if kind in {'image', 'decoration'} else 'graphicFrameLocks' if kind == 'table' else 'cxnSpLocks' if kind == 'connector' else 'spLocks'
    _xml_fields(inner, ['a:' + locks, *(['a:stCxn', 'a:endCxn'] if kind == 'connector' else [])])
    lock = inner.find('a:' + locks, NS)
    if lock is not None:
        _xml_fields(lock, [], attrs=['noChangeAspect'] if kind in {'image', 'decoration'} else ['noGrp'])
        _check(all(v in {'1', 'true'} for v in lock.attrib.values()), 'native editability lock changed')
    _xml_fields(nv.find('p:nvPr', NS), [])  # no placeholder/media/hidden surface
    if kind == 'table':
        graphic = node.find('a:graphic', NS); _xml_fields(graphic, ['a:graphicData'], required=['a:graphicData'])
        data = graphic.find('a:graphicData', NS); _xml_fields(data, ['a:tbl'], required=['a:tbl'], attrs=['uri'])
        _check(data.get('uri') == 'http://schemas.openxmlformats.org/drawingml/2006/table', 'unsupported graphic carrier')
        table = data.find('a:tbl', NS)
        _xml_fields(table, ['a:tblPr', 'a:tblGrid', 'a:tr'], required=['a:tblPr', 'a:tblGrid', 'a:tr'], repeated=['a:tr'])
        properties = table.find('a:tblPr', NS)
        _xml_fields(properties, ['a:tableStyleId'], attrs=['firstRow', 'firstCol', 'lastRow', 'lastCol', 'bandRow', 'bandCol'])
        _check(all(v in {'0', 'false'} for v in properties.attrib.values()), 'implicit native table styling changed')
        _xml_fields(table.find('a:tblGrid', NS), ['a:gridCol'], required=['a:gridCol'], repeated=['a:gridCol'])
        for column in table.findall('a:tblGrid/a:gridCol', NS):
            _xml_fields(column, [], attrs=['w'])
        for row in table.findall('a:tr', NS):
            _xml_fields(row, ['a:tc'], required=['a:tc'], repeated=['a:tc'], attrs=['h'])
            for cell in row:
                _xml_fields(cell, ['a:txBody', 'a:tcPr'], required=['a:txBody', 'a:tcPr'])
                properties = cell.find('a:tcPr', NS)
                _xml_fields(properties, ['a:noFill', 'a:lnL', 'a:lnR', 'a:lnT', 'a:lnB'],
                            attrs=['marL', 'marR', 'marT', 'marB', 'anchor'])
                _check(properties.find('a:noFill', NS) is not None, 'native table cell acquired a fill')
                for line in list(properties):
                    if line.tag != '{' + A + '}noFill':
                        _line_check(line, None)
        return
    props = node.find('p:spPr', NS)
    custom = kind == 'relation-path' or (kind == 'shape' and obj['appearance']['geometry'] == 'polygon')
    geometry_tag = 'a:custGeom' if custom else 'a:prstGeom'
    visual = ['a:xfrm', geometry_tag]
    if kind in {'text', 'shape', 'connector', 'relation-path'}:
        visual += ['a:noFill', 'a:solidFill', 'a:gradFill', 'a:ln', 'a:effectLst']
    _xml_fields(props, visual, required=['a:xfrm', geometry_tag])
    xfrm = props.find('a:xfrm', NS)
    _xml_fields(xfrm, ['a:off', 'a:ext'], required=['a:off', 'a:ext'], attrs=['rot', 'flipH', 'flipV'])
    _xml_fields(xfrm.find('a:off', NS), [], attrs=['x', 'y'])
    _xml_fields(xfrm.find('a:ext', NS), [], attrs=['cx', 'cy'])
    geom = props.find(geometry_tag, NS)
    if custom:
        _path_check(geom, obj['appearance']['paths'])
        return
    _xml_fields(geom, ['a:avLst'], required=['a:avLst'], attrs=['prst'])
    adjustments = geom.find('a:avLst', NS)
    if kind == 'shape' and obj['appearance']['geometry'] == 'round-rect':
        _xml_fields(adjustments, ['a:gd'], required=['a:gd'])
    else:
        _xml_fields(adjustments, [])
    if kind == 'text':
        _check(geom.get('prst') == 'rect' and props.find('a:noFill', NS) is not None and
               props.find('a:solidFill', NS) is None and props.find('a:gradFill', NS) is None and
               props.find('a:effectLst', NS) is None, 'native textbox acquired unselected visual styling')
        _line_check(props.find('a:ln', NS), None)
    elif kind in {'image', 'decoration'}:
        _check(geom.get('prst') == 'rect', 'native image mask geometry changed')
        fill = node.find('p:blipFill', NS)
        _xml_fields(fill, ['a:blip', 'a:srcRect', 'a:stretch'], required=['a:blip', 'a:stretch'])
        _xml_fields(fill.find('a:blip', NS), [], attrs=['{' + R + '}embed'])
        if fill.find('a:srcRect', NS) is not None:
            _xml_fields(fill.find('a:srcRect', NS), [], attrs=['l', 't', 'r', 'b'])
        stretch = fill.find('a:stretch', NS)
        _xml_fields(stretch, ['a:fillRect'])
        if stretch.find('a:fillRect', NS) is not None:
            _xml_fields(stretch.find('a:fillRect', NS), [])


def _text_check(body, expected, *, table_cell=False):
    _xml_fields(body, ['a:bodyPr', 'a:lstStyle', 'a:p'], required=['a:bodyPr', 'a:lstStyle', 'a:p'], repeated=['a:p'])
    _xml_fields(body.find('a:lstStyle', NS), [])
    _check(body is not None and paragraphs(body) == ''.join(r['text'] for r in expected['runs']),
           'native visible text differs from selected text')
    native_runs = body.findall('a:p/a:r', NS)
    _check(len(native_runs) == len(expected['runs']), 'native font run coverage changed')
    for actual, run in zip(native_runs, expected['runs']):
        _xml_fields(actual, ['a:rPr', 'a:t'], required=['a:rPr', 'a:t'])
        props = actual.find('a:rPr', NS)
        _check(props is not None and actual.findtext('a:t', '', NS) == run['text'], 'native run text changed')
        _check(not set(props.attrib) - {'sz', 'b', 'i', 'lang', 'dirty'}, 'unsupported native font transformation')
        _xml_fields(props, ['a:solidFill', 'a:gradFill', 'a:latin', 'a:ea', 'a:cs'],
                    required=['a:latin', 'a:ea', 'a:cs'], attrs=['sz', 'b', 'i', 'lang', 'dirty'])
        _numbers(props, ['sz'], [run['fontSize']], 75)
        for family in ('latin', 'ea', 'cs'):
            value = props.find('a:' + family, NS)
            _check(value is not None and value.get('typeface') == run['fontFamily'], 'native font family changed')
        for key in ('bold', 'italic'):
            _check(props.get({'bold': 'b', 'italic': 'i'}[key], '0') in
                   ({'1', 'true'} if run[key] else {'0', 'false'}), 'native font style changed')
        _fill_check(props, run['fill'] if 'fill' in run else {'type':'solid','color':run['color']})
    body_props = body.find('a:bodyPr', NS)
    _xml_fields(body_props, ['a:noAutofit'], required=['a:noAutofit'], attrs=['wrap', 'tIns', 'rIns', 'bIns', 'lIns', 'anchor'])
    _check(body_props is not None and body_props.find('a:noAutofit', NS) is not None,
           'native text requires explicit noAutofit')
    _check(body_props.get('wrap') == expected.get('wrap', 'none'), 'native wrapping changed')
    _numbers(body_props, ['tIns', 'rIns', 'bIns', 'lIns'], expected['insets'], 9525)
    # Table anchor is expressed in tcPr; txBody must not add a second anchor.
    _check(body_props.get('anchor', 't') == ('t' if table_cell else
           {'top': 't', 'middle': 'ctr', 'bottom': 'b'}[expected['verticalAlignment']]),
           'native vertical alignment changed')
    for paragraph in body.findall('a:p', NS):
        _xml_fields(paragraph, ['a:pPr', 'a:r'], required=['a:pPr', 'a:r'], repeated=['a:r'])
        props = paragraph.find('a:pPr', NS)
        _xml_fields(props, ['a:lnSpc', 'a:buNone'], required=['a:lnSpc', 'a:buNone'], attrs=['algn'])
        _xml_fields(props.find('a:lnSpc', NS), ['a:spcPct'], required=['a:spcPct'])
        _check(props is not None and props.get('algn', 'l') ==
               {'left': 'l', 'center': 'ctr', 'right': 'r', 'justify': 'just'}[expected['alignment']],
               'native paragraph alignment changed')
        _check(props.find('a:buChar', NS) is None and props.find('a:buAutoNum', NS) is None,
               'native text acquired unselected bullets/numbering')
        spacing = props.find('a:lnSpc/a:spcPct', NS)
        _numbers(spacing, ['val'], [expected['lineSpacing']], 100000)


def _color(node, expected, *, allow_alpha=False):
    _check(node is not None and '#' + node.get('val', '').upper() == expected.upper(), 'native color changed')
    _check(all(child.tag == '{' + A + '}alpha' and allow_alpha for child in node), 'native color transformation changed')


def _line_check(node, expected, *, allow_arrows=False):
    if node is not None:
        _xml_fields(node, ['a:noFill', 'a:solidFill', 'a:prstDash', *(['a:headEnd', 'a:tailEnd'] if allow_arrows else [])], attrs=['w'])
        _check(sum(node.find(name, NS) is not None for name in ('a:noFill', 'a:solidFill')) == 1,
               'ambiguous native line fill')
    if expected is None:
        _check(node is None or (node.find('a:noFill', NS) is not None and float(node.get('w', 0)) == 0),
               'native object acquired an unselected line')
        return
    _numbers(node, ['w'], [expected['width']], 9525)
    _color(node.find('a:solidFill/a:srgbClr', NS), expected['color'])
    dash = node.find('a:prstDash', NS)
    _check(dash is not None and dash.get('val') == {'solid':'solid','dash':'dash','dot':'dot'}[expected['dash']],
           'native line dash changed')


def _path_check(geometry, paths):
    """Compare numeric M/L/Z, including every hole contour and its winding.

    These are editable freeform shapes, with semantic endpoints bound in the
    immutable handoff. They have no native connector/dynamic snap semantics.
    """
    _xml_fields(geometry, ['a:pathLst'], required=['a:pathLst'])
    path_list = geometry.find('a:pathLst', NS)
    _xml_fields(path_list, ['a:path'], required=['a:path'], repeated=['a:path'])
    _check(len(path_list) == len(paths), 'native path count changed')
    for actual, expected in zip(path_list, paths):
        _xml_fields(actual, ['a:moveTo', 'a:lnTo', 'a:close'],
                    repeated=['a:moveTo', 'a:lnTo', 'a:close'], attrs=['w', 'h'])
        _numbers(actual, ['w', 'h'], [expected['width'], expected['height']], 9525)
        _check(len(actual) == len(expected['commands']), 'native path command count changed')
        for node, command in zip(actual, expected['commands']):
            operation = next(iter(command))
            tag = {'moveTo': 'moveTo', 'lineTo': 'lnTo', 'close': 'close'}[operation]
            _check(node.tag == '{' + A + '}' + tag, 'native path command order changed')
            if operation == 'close':
                _xml_fields(node, [])
            else:
                _xml_fields(node, ['a:pt'], required=['a:pt'])
                point = node.find('a:pt', NS)
                _xml_fields(point, [], attrs=['x', 'y'])
                _numbers(point, ['x', 'y'], [command[operation]['x'], command[operation]['y']], 9525)


def _fill_integer(node, attribute, expected, scale):
    """Match the SDK's integer OOXML fill units, without CSS geometry tolerance."""
    _check(node is not None, 'missing native gradient value')
    try:
        actual = int(node.get(attribute, ''))
    except ValueError:
        fail('RESULT', 'invalid native gradient integer')
    # The bundled SDK truncates linear angles to 1/60000 degree; stop positions
    # are already integers in its public proto. No fill stop is rounded here.
    _check(actual == int(expected * scale), 'native gradient value changed')


def _fill_check(props, expected):
    _check(sum(props.find(name, NS) is not None for name in ('a:noFill', 'a:solidFill', 'a:gradFill')) == 1,
           'ambiguous native fill')
    if expected is None:
        _check(props.find('a:noFill', NS) is not None, 'native object acquired a fill')
    elif expected['type'] == 'solid':
        _color(props.find('a:solidFill/a:srgbClr', NS), expected['color'])
    else:
        gradient = props.find('a:gradFill', NS)
        _xml_fields(gradient, ['a:gsLst', 'a:lin'], required=['a:gsLst', 'a:lin'])
        _xml_fields(gradient.find('a:gsLst', NS), ['a:gs'], required=['a:gs'], repeated=['a:gs'])
        _check(gradient is not None, 'native gradient was simplified')
        stops = gradient.findall('a:gsLst/a:gs', NS)
        _check(len(stops) == len(expected['stops']), 'native gradient stop count changed')
        for actual, stop in zip(stops, expected['stops']):
            _xml_fields(actual, ['a:srgbClr'], required=['a:srgbClr'], attrs=['pos'])
            _fill_integer(actual, 'pos', stop['offset'], 100000)
            _color(actual.find('a:srgbClr', NS), stop['color'])
        linear = gradient.find('a:lin', NS)
        _xml_fields(linear, [], attrs=['ang'])
        _fill_integer(linear, 'ang', expected['angle'], 60000)


def _shape_check(props, appearance, bbox):
    _fill_check(props, appearance['fill'])
    _line_check(props.find('a:ln', NS), appearance['line'])
    shadow = props.find('a:effectLst/a:outerShdw', NS)
    if props.find('a:effectLst', NS) is not None:
        _xml_fields(props.find('a:effectLst', NS), ['a:outerShdw'], required=['a:outerShdw'])
    expected = appearance.get('shadow')
    if expected is None:
        _check(shadow is None, 'native shape acquired an unselected shadow')
    else:
        _numbers(shadow, ['blurRad'], [expected['blur']], 9525)
        distance = math.hypot(expected['offset_x'], expected['offset_y'])
        angle = math.degrees(math.atan2(expected['offset_y'], expected['offset_x'])) % 360
        _numbers(shadow, ['dist', 'dir'], [distance * 9525, angle * 60000])
        color = shadow.find('a:srgbClr', NS)
        _color(color, expected['color'], allow_alpha=True)
        _numbers(color.find('a:alpha', NS), ['val'], [expected['opacity']], 100000)
    if appearance.get('geometry') == 'round-rect':
        adjustments = props.findall('a:prstGeom/a:avLst/a:gd', NS)
        _check(len(adjustments) == 1 and adjustments[0].get('name') == 'adj', 'native corner radius is implicit')
        value = adjustments[0].get('fmla', '').split()
        _check(len(value) == 2 and value[0] == 'val' and
               abs(float(value[1]) / 100000 * min(bbox[2:]) - appearance['corner_radius']) < 0.001,
               'native corner radius changed')


def inspect_native_pptx(raw, handoff):
    """Re-read standard OOXML bytes. Names bind exact objects, never similarity."""
    try:
        package = Package(raw)
        inherited = {target for records in package.rels.values() for kind, target in records.values()
                     if kind in {R + '/slideLayout', R + '/slideMaster'}}
        for part in inherited:
            tree = package.read_xml(part).find('p:cSld/p:spTree', NS)
            _check(tree is not None and all(e.tag.rsplit('}', 1)[-1] in {'nvGrpSpPr', 'grpSpPr'} for e in tree),
                   'native slide inherited unselected visual objects')
        main = [target for kind, target in package.rels.get('', {}).values() if kind == R + '/officeDocument']
        _check(len(main) == 1, 'ambiguous presentation package')
        presentation = package.read_xml(main[0])
        _check(len(presentation.findall('p:sldIdLst/p:sldId', NS)) == len(handoff['slides']), 'native slide count changed')
        _numbers(presentation.find('p:sldSz', NS), ['cx', 'cy'],
                 [handoff['slides'][0]['canvas'][k] for k in ('width', 'height')], 9525)
        evidence = []
        for index, slide in enumerate(handoff['slides'], 1):
            part, tree = package.slide(index)
            root = package.read_xml(part)
            _check(root.find('p:timing', NS) is None and root.find('p:transition', NS) is None,
                   'native output contains unselected animation/transition')
            background = root.find('p:cSld/p:bg/p:bgPr', NS)
            _check(background is not None and len(background) == 1 and background.find('a:noFill', NS) is not None,
                   'native slide background was changed outside mapped objects')
            allowed = {'sp', 'pic', 'graphicFrame', 'cxnSp', 'nvGrpSpPr', 'grpSpPr'}
            _check(all(element.tag.rsplit('}', 1)[-1] in allowed for element in tree), 'unknown/grouped native object')
            actual = [e for e in tree if e.tag.rsplit('}', 1)[-1] not in {'nvGrpSpPr', 'grpSpPr'}]
            expected = sorted(slide['objects'], key=lambda o: o['z_order'])
            _check(len(actual) == len(expected), 'native object count changed')
            ids = {}
            for node, obj in zip(actual, expected):
                names = node.findall('.//p:cNvPr', NS)
                _check(len(names) == 1 and names[0].get('name') == obj['object_id'],
                       'native object identity or stacking order changed')
                identity = names[0].get('id')
                _check(identity and identity not in ids, 'native object ids are not unique')
                ids[identity] = obj['region_id']
            for node, obj in zip(actual, expected):
                tag, kind, a = node.tag.rsplit('}', 1)[-1], obj['kind'], obj['appearance']
                _carrier_check(node, obj)
                _check(tag == {'text': 'sp', 'shape': 'sp', 'relation-path': 'sp', 'image': 'pic', 'decoration': 'pic',
                               'table': 'graphicFrame', 'connector': 'cxnSp'}[kind], 'native object carrier changed')
                transform = node.find('p:xfrm', NS) if kind == 'table' else node.find('p:spPr/a:xfrm', NS)
                _check(transform is not None, 'missing native object transform')
                _numbers(transform.find('a:off', NS), ['x', 'y'], obj['bbox'][:2], 9525)
                _numbers(transform.find('a:ext', NS), ['cx', 'cy'], obj['bbox'][2:], 9525)
                _check(transform.get('rot', '0') == '0', 'unexpected native object rotation')
                if kind != 'connector':
                    _check(transform.get('flipH', '0') in {'0', 'false'} and transform.get('flipV', '0') in {'0', 'false'},
                           'unexpected native object reflection')
                if kind == 'text':
                    _text_check(node.find('p:txBody', NS), a)
                elif kind == 'table':
                    table = node.find('a:graphic/a:graphicData/a:tbl', NS)
                    _check(table is not None, 'table is not native')
                    rows = table.findall('a:tr', NS)
                    columns = table.findall('a:tblGrid/a:gridCol', NS)
                    _check(len(rows) == len(a['row_heights']) and len(columns) == len(a['column_widths']), 'native table size changed')
                    for row, height in zip(rows, a['row_heights']):
                        _numbers(row, ['h'], [height], 9525)
                        _check(len(row.findall('a:tc', NS)) == len(columns), 'native table cell coverage changed')
                    for column, width in zip(columns, a['column_widths']):
                        _numbers(column, ['w'], [width], 9525)
                    for cell in a['cells']:
                        node_cell = rows[cell['row']].findall('a:tc', NS)[cell['column']]
                        _check(not any(k in node_cell.attrib for k in ('gridSpan', 'rowSpan', 'hMerge', 'vMerge')), 'merged native cell unsupported')
                        _text_check(node_cell.find('a:txBody', NS), cell['style'], table_cell=True)
                        properties = node_cell.find('a:tcPr', NS)
                        _numbers(properties, ['marT', 'marR', 'marB', 'marL'], cell['style']['insets'], 9525)
                        _check(properties.get('anchor') == {'top':'t', 'middle':'ctr', 'bottom':'b'}[cell['style']['verticalAlignment']],
                               'native table cell alignment changed')
                elif kind in {'image', 'decoration'}:
                    blip = node.find('p:blipFill/a:blip', NS)
                    _check(blip is not None and len(node.findall('.//a:blip', NS)) == 1, 'image material is ambiguous')
                    image_path = package.target(part, blip.get('{' + R + '}embed'), 'image')
                    _check(hashlib.sha256(package.file.read(image_path)).hexdigest() == a['asset_sha256'], 'native material bytes changed')
                    crop = node.find('p:blipFill/a:srcRect', NS)
                    values = [float(crop.get(k, '0')) / 100000 if crop is not None else 0 for k in ('l', 't', 'r', 'b')]
                    x, y, w, h = a['crop']
                    _check(all(abs(v - e) <= 0.00001 for v, e in zip(values, [x, y, 1-x-w, 1-y-h])), 'native image crop changed')
                elif kind == 'connector':
                    shape_props = node.find('p:spPr', NS)
                    _xml_fields(shape_props, ['a:xfrm', 'a:prstGeom', 'a:ln'], required=['a:xfrm', 'a:prstGeom', 'a:ln'])
                    _check(shape_props.find('a:prstGeom', NS).get('prst') == 'straightConnector1', 'native relation geometry changed')
                    _check(all(transform.get(key, '0') in ({'1','true'} if active else {'0','false'})
                               for key, active in (('flipH', a['start'][0] > a['end'][0]), ('flipV', a['start'][1] > a['end'][1]))),
                           'native relation geometry changed')
                    props = node.find('p:nvCxnSpPr/p:cNvCxnSpPr', NS)
                    _check(props is not None, 'native connector identity missing')
                    for tag_name, key in (('stCxn', 'from_region_id'), ('endCxn', 'to_region_id')):
                        endpoint = props.find('a:' + tag_name, NS)
                        _xml_fields(endpoint, [], attrs=['id', 'idx'])
                        _check(endpoint is not None and ids.get(endpoint.get('id')) == a[key], 'native relation endpoints changed')
                        target = next(e for e in expected if e['region_id'] == a[key])
                        x, y, w, h = target['bbox']
                        point = a['start' if tag_name == 'stCxn' else 'end']
                        sites = ([x+w/2,y], [x,y+h/2], [x+w/2,y+h], [x+w,y+h/2])
                        _check(point in sites and endpoint.get('idx') == str(sites.index(point)),
                               'native relation connection site changed')
                    line = node.find('p:spPr/a:ln', NS)
                    _check(line is not None, 'native connector line missing')
                    _line_check(line, a['line'], allow_arrows=True)
                    for marker, active in (('headEnd', a['arrow'] in {'backward', 'both'}), ('tailEnd', a['arrow'] in {'forward', 'both'})):
                        arrow = line.find('a:' + marker, NS)
                        _xml_fields(arrow, [], attrs=['type', 'w', 'len'])
                        _check((arrow.get('type', 'none') if arrow is not None else 'none') == ('triangle' if active else 'none'), 'native relation arrow changed')
                        _check(arrow.get('w') == 'med' and arrow.get('len') == 'med', 'native relation arrow dimensions changed')
                else:
                    _check(node.find('p:txBody', NS) is None, 'shape gained unselected visible text')
                    if kind != 'relation-path' and a['geometry'] != 'polygon':
                        geom = node.find('p:spPr/a:prstGeom', NS)
                        _check(geom is not None and geom.get('prst') == {'rect':'rect','round-rect':'roundRect','ellipse':'ellipse'}[a['geometry']], 'native shape geometry changed')
                    _shape_check(node.find('p:spPr', NS), a, obj['bbox'])
                evidence.append({'slide_id': slide['target_binding']['slide_id'], 'region_id': obj['region_id'],
                                 'object_id': obj['object_id'], 'kind': kind})
        return evidence
    except (KeyError, ValueError, OSError, BadZipFile, ParseError) as error:
        fail('RESULT', 'unreadable native object evidence: ' + type(error).__name__)


def preflight_output(payload, handoff, project_root):
    """Closed unassessed output -> checked bytes/identity; does not publish."""
    exact(payload, OUTPUT_FIELDS, 'renderer output')
    _check(payload['status'] == 'engineering-output-unassessed', 'renderer status is not assessment evidence')
    for key in ('visual_fidelity', 'user_acceptance', 'target_powerpoint'):
        _check(payload[key] == 'not-established', 'renderer cannot self-approve ' + key)
    for key in ('project_id', 'selection_ref', 'region_inventory_ref', 'plan_ref', 'task_id'):
        _check(payload[key] == handoff.get(key), 'renderer output changed ' + key)
    selection = {'project_id': handoff['project_id'], 'slides': []}
    inventory = {'artifact_type': 'image-led-region-inventory', 'project_id': handoff['project_id'],
                 'selection_ref': handoff['selection_ref'], 'slides': []}
    v3 = handoff['handoff_version'] == 'codex-presentations-image-led/v3'
    from ai_ppt_studio.domains.visual.compilation import image_led_versions
    if v3:
        inventory['region_version'] = REGION_VERSION_V3
    for slide in handoff['slides']:
        _check((slide.get('region_version') == REGION_VERSION_V3) if v3 else 'region_version' not in slide,
               'native handoff region version changed')
        from ai_ppt_studio.domains.visual.image_led import handoff_selected_copy
        copy = handoff_selected_copy(slide, handoff['handoff_version'])
        selection['slides'].append({'target_binding': slide['target_binding'], 'selected_copy': copy})
        inventory['slides'].append({key: slide[key] for key in ('target_binding', 'canvas', 'source_image_size', 'regions')})
        validate_faithful_objects(slide['regions'], slide['objects'], region_version=slide.get('region_version'))
    validate_region_inventory(inventory, selection, selection_ref=handoff['selection_ref'])
    _check((handoff.get('compiler_version'), handoff['handoff_version']) == image_led_versions(selection, inventory),
           'native handoff compiler version changed')
    output_dir = Path(handoff['output_paths']['directory'])
    _check(payload['pptx_path'] == handoff['output_paths']['pptx'] and
           Path(payload['pptx_path']).parent == output_dir and handoff['task_id'] in output_dir.parts,
           'output path differs from exact build task')
    pptx = _file(project_root, payload['pptx_path'], payload['pptx_sha256'])
    required = {'handoff.json', 'mapping.json', 'inspect.ndjson', 'authoring.proto.json', 'reimport.proto.json'} | {
        'slide-' + str(i) + '.layout.json' for i in range(1, len(handoff['slides']) + 1)}
    exact(payload['files'], required, 'result files')
    files = {}
    for name, entry in payload['files'].items():
        exact(entry, {'path', 'sha256'}, 'result file entry')
        _check(entry['path'] == str(output_dir / name), 'object inspection file moved outside output')
        files[name] = _file(project_root, entry['path'], entry['sha256'])
    _check(payload['handoff_sha256'] == payload['files']['handoff.json']['sha256'] and
           _json(files['handoff.json']) == handoff, 'handoff bytes differ from governed input')
    _check(_json(files['mapping.json']) == payload['mapping'], 'mapping file differs from submitted mapping')
    _check(isinstance(payload['mapping'], list), 'mapping must be an array')
    mapped = []
    for row in payload['mapping']:
        exact(row, {'slide_id', 'region_id', 'object_id', 'sdk_id', 'kind'}, 'native mapping')
        text(str(row['sdk_id']), 'sdk_id')
        mapped.append({key: row[key] for key in ('slide_id', 'region_id', 'object_id', 'kind')})
    checked = inspect_native_pptx(pptx, handoff)
    sort_key = lambda row: (row['slide_id'], row['region_id'])
    _check(sorted(mapped, key=sort_key) == sorted(checked, key=sort_key), 'mapping does not cover actual native objects')
    # SDK inspection evidence is parsed and bound, never accepted as a substitute
    # for the independent native-package inspection above.
    for name in ('authoring.proto.json', 'reimport.proto.json'):
        proto = _json(files[name])
        _check(isinstance(proto, dict) and len(proto.get('slides', [])) == len(handoff['slides']), 'SDK inspection slide count changed')
    inspected = [_json(line) for line in files['inspect.ndjson'].splitlines() if line.strip()]
    _check(sum(row.get('kind') == 'slide' for row in inspected) == len(handoff['slides']), 'SDK inspection is incomplete')
    _check(isinstance(payload['renders'], list) and len(payload['renders']) == len(handoff['slides']), 'render page coverage changed')
    _check(isinstance(payload['comparisons'], list) and len(payload['comparisons']) == len(handoff['slides']), 'comparison page coverage changed')
    render_snapshots, comparison_snapshots = [], []
    for index, (render, slide) in enumerate(zip(payload['renders'], handoff['slides']), 1):
        exact(render, {'slide_id', 'path', 'sha256'}, 'rendered page')
        _check(render['slide_id'] == slide['target_binding']['slide_id'] and
               render['path'] == str(output_dir / f'slide-{index}.png'), 'render page identity changed')
        raw = _file(project_root, render['path'], render['sha256'])
        render_snapshots.append(base64.b64encode(raw).decode())
        try:
            with Image.open(BytesIO(raw)) as image:
                image.load()
                _check(image.format == 'PNG' and image.size == (slide['canvas']['width'], slide['canvas']['height']), 'render image format/dimensions changed')
        except (ValueError, OSError) as error:
            fail('RESULT', 'invalid render bytes: ' + type(error).__name__)
        layout = _json(files[f'slide-{index}.layout.json'])
        _check(isinstance(layout, dict) and layout.get('slide', {}).get('slide') == index,
               'layout inspection belongs to another page')
        comparison = payload['comparisons'][index - 1]
        exact(comparison, {'slide_id', 'side_by_side', 'overlay', 'region_differences'}, 'visual comparison')
        _check(comparison['slide_id'] == render['slide_id'], 'visual comparison page changed')
        compare_snapshot = {}
        for key, suffix in (('side_by_side', 'side-by-side.png'), ('overlay', 'overlay.png'), ('region_differences', 'regions.json')):
            entry = comparison[key]
            exact(entry, {'path', 'sha256'}, 'comparison file')
            _check(entry['path'] == str(output_dir / f'compare-{index}-{suffix}'), 'comparison file outside exact output')
            raw = _file(project_root, entry['path'], entry['sha256'])
            if key == 'region_differences':
                difference = _json(raw)
                exact(difference, {'status', 'target_image_sha256', 'render_sha256', 'regions'}, 'region differences')
                _check(difference['status'] == 'unassessed' and difference['render_sha256'] == render['sha256'] and
                       difference['target_image_sha256'] == slide['target_binding']['target_image_sha256'], 'region difference output identity changed')
                _check(isinstance(difference['regions'], list) and len(difference['regions']) == len(slide['regions']), 'region comparison coverage changed')
                for row, region in zip(difference['regions'], slide['regions']):
                    exact(row, {'region_id', 'bbox', 'mean_absolute_error'}, 'region difference')
                    score = row['mean_absolute_error']
                    _check(row['region_id'] == region['region_id'] and row['bbox'] == region['bbox'] and
                           type(score) in {int, float} and math.isfinite(score) and 0 <= score <= 255, 'region difference identity invalid')
                compare_snapshot[key] = difference
            else:
                try:
                    with Image.open(BytesIO(raw)) as image:
                        image.load()
                        expected = (slide['canvas']['width'] * (2 if key == 'side_by_side' else 1), slide['canvas']['height'])
                        _check(image.format == 'PNG' and image.size == expected, 'comparison canvas differs from selected design')
                except (ValueError, OSError) as error:
                    fail('RESULT', 'invalid comparison bytes: ' + type(error).__name__)
                compare_snapshot[key] = base64.b64encode(raw).decode()
        comparison_snapshots.append(compare_snapshot)
    _verify_render_snapshots(pptx, handoff, render_snapshots, comparison_snapshots)
    return deepcopy(payload)


class ImageLedResultService(ImageLedService):
    """Governed Agent transactions own producer/reviewer provenance."""
    def _prepared(self, action, target_refs):
        task = getattr(self.kernel, 'prepared_agent_task', None)
        _check(isinstance(task, dict) and task.get('action_type') == action and
               task.get('status') == 'queued' and task.get('target_refs') == target_refs,
               'result requires its exact governed Agent transaction')
        _check(task.get('role_id') == {'build-native-first': 'native-first-engineer',
            'review-visual-engineering': 'visual-engineering-reviewer'}[action], 'result task role mismatch')
        return task

    def _handoff(self, task, supplied=None):
        from ai_ppt_studio.context_compiler import ContextCompiler
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService
        context = require_exact_ref(self.kernel, task['context_pack_ref'],
            'agent/context/' + task['task_id'], 'context-pack')['payload']
        _check(context.get('project_id') == self.kernel.project_id and context.get('project_revision') == task['input_revision'],
               'producer context belongs to another project/revision')
        wrapper = context.get('layers', {}).get('visual_handoff')
        _check(isinstance(wrapper, dict), 'producer context lacks visual handoff')
        ContextCompiler(self.kernel).validate_visual_handoff_for_result(wrapper,
            project_revision=task['input_revision'], expected_revision=wrapper.get('result_expected_revision'),
            target_refs=task['target_refs'], task_id=task['task_id'])
        handoff = wrapper.get('renderer_handoff')
        _check(isinstance(handoff, dict), 'producer context lacks Image-led renderer handoff')
        _check(supplied is None or supplied == handoff, 'supplied handoff differs from governed context')
        service = ImageLedNativeService(self.kernel)
        _, plan = service.current_contract_plan()
        inventory = service.current_regions()
        selection = service.current_selection(handoff['selection_ref'])
        require_exact_ref(self.kernel, handoff['plan_ref'], 'visual/compilation-plan', 'visual-compilation-plan')
        require_exact_ref(self.kernel, handoff['region_inventory_ref'], PREFIX + 'regions', 'image-led-region-inventory')
        _check(plan['selection_ref'] == handoff['selection_ref'] and plan['region_inventory_ref'] == handoff['region_inventory_ref']
               and plan['slides'] == handoff['slides'], 'result plan dependencies changed')
        validate_region_inventory(inventory, selection, selection_ref=handoff['selection_ref'])
        return handoff

    def preflight_build_result(self, payload, *, handoff=None):
        exact(payload, {'artifact_type', 'project_id', 'output'}, 'Image-led build result')
        _check(payload['artifact_type'] == 'image-led-build-result' and payload['project_id'] == self.kernel.project_id,
               'build result project/type changed')
        plan_ref = self.kernel.load().artifact_heads.get('visual/compilation-plan', '')
        task = self._prepared('build-native-first', [plan_ref])
        checked_handoff = self._handoff(task, handoff)
        output = preflight_output(payload['output'], checked_handoff, self.kernel.project_root)
        return {**deepcopy(payload), 'output': output, 'producer_task_id': task['task_id'],
                'producer_role': task['role_id'], 'context_pack_ref': task['context_pack_ref']}

    def register_build_result(self, command_id, revision, payload, *, handoff=None):
        require_revision(self.kernel, revision)
        self.require_g0()
        value = self.preflight_build_result(payload, handoff=handoff)
        from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
        state = self.kernel.load()
        # Preserve reviewed contracts, invalidate prior outputs and all dependent reviews.
        keep = {s for s in state.artifact_heads if s.startswith('visual/') and s != 'visual/contract' and not any(
            s.startswith(p) for p in (*OUTPUT_DEPENDENCIES, PREFIX + 'result-review/', RESULT_SLOT))} | {RESULT_SLOT}
        committed = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.build-result-registered', artifact_updates={RESULT_SLOT: ('image-led-build-result', value)},
            artifact_removals=visual_downstream_slots(state.artifact_heads, keep=keep))
        return committed.artifact_heads[RESULT_SLOT]

    def _current_output(self, result_ref, handoff=None):
        value = require_exact_ref(self.kernel, result_ref, RESULT_SLOT, 'image-led-build-result')['payload']
        exact(value, {'artifact_type', 'project_id', 'output', 'producer_task_id', 'producer_role', 'context_pack_ref'}, 'stored build result')
        _check(value['artifact_type'] == 'image-led-build-result' and value['project_id'] == self.kernel.project_id,
               'stored result project/type mismatch')
        task_id = value['producer_task_id']
        task = require_exact_ref(self.kernel, self.kernel.load().artifact_heads.get('agent/task/' + task_id, ''),
                                 'agent/task/' + task_id, 'agent-task')['payload']
        _check(task['status'] == 'completed' and task['action_type'] == 'build-native-first' and task['result_refs'] == [result_ref]
               and task['role_id'] == value['producer_role'] == 'native-first-engineer' and task['context_pack_ref'] == value['context_pack_ref'],
               'build result lacks its completed producer task')
        checked_handoff = self._handoff(task, handoff)
        preflight_output(value['output'], checked_handoff, self.kernel.project_root)
        return value

    @staticmethod
    def _checks(payload):
        checks = payload.get('checks')
        _check(isinstance(checks, list) and len(checks) == len(DIMENSIONS), 'review requires all four dimensions')
        seen = set()
        for row in checks:
            exact(row, {'criterion', 'result', 'detail'}, 'result review criterion')
            _check(row['criterion'] in DIMENSIONS and row['criterion'] not in seen, 'unknown/duplicate review dimension')
            seen.add(row['criterion'])
            _check(row['result'] in {'passed', 'failed', 'not-established'}, 'unknown review status')
            text(row['detail'], 'review detail')

    def register_review(self, command_id, revision, payload):
        require_revision(self.kernel, revision)
        self.require_g0()
        exact(payload, {'artifact_type', 'project_id', 'target_ref', 'reviewer_kind', 'reviewer_role', 'checks'}, 'result review')
        _check(payload['artifact_type'] == 'image-led-result-review' and payload['project_id'] == self.kernel.project_id,
               'result review type/project mismatch')
        result = self._current_output(payload['target_ref'])
        task = self._prepared('review-visual-engineering', [payload['target_ref']])
        _check(task['role_id'] == 'visual-engineering-reviewer' and payload['reviewer_role'] == task['role_id']
               and payload['reviewer_kind'] == 'engineering' and task['task_id'] != result['producer_task_id']
               and task['role_id'] != result['producer_role'], 'producer cannot review its own native result')
        context = require_exact_ref(self.kernel, task['context_pack_ref'], 'agent/context/' + task['task_id'], 'context-pack')['payload']
        _check(context.get('project_id') == self.kernel.project_id and context.get('project_revision') == task['input_revision'],
               'review context identity changed')
        self._checks(payload)
        output = result['output']
        value = {**deepcopy(payload), 'reviewer_task_id': task['task_id'], 'context_pack_ref': task['context_pack_ref'],
            'producer_task_id': result['producer_task_id'], 'selection_ref': output['selection_ref'], 'plan_ref': output['plan_ref'],
            'region_inventory_ref': output['region_inventory_ref'], 'pptx_sha256': output['pptx_sha256'],
            'renders': deepcopy(output['renders']), 'comparisons': deepcopy(output['comparisons'])}
        slot = PREFIX + 'result-review/' + ArtifactReference.parse(payload['target_ref']).sha256
        from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
        heads = self.kernel.load().artifact_heads
        keep = {s for s in heads if s.startswith('visual/') and s != 'visual/contract' and not any(
            s.startswith(p) for p in OUTPUT_DEPENDENCIES)} | {slot}
        state = self.kernel.commit(command_id=command_id, expected_revision=revision,
            event_type='image-led.native-result-reviewed', artifact_updates={slot: ('image-led-result-review', value)},
            artifact_removals=visual_downstream_slots(heads, keep=keep))
        return state.artifact_heads[slot]

    def current_result(self, result_ref=None, *, handoff=None, review_ref=None, require_review=True):
        result_ref = result_ref or self.kernel.load().artifact_heads.get(RESULT_SLOT, '')
        result = self._current_output(result_ref, handoff)
        if not require_review:
            return result
        slot = PREFIX + 'result-review/' + ArtifactReference.parse(result_ref).sha256
        current_ref = self.kernel.load().artifact_heads.get(slot, '')
        _check(review_ref is None or review_ref == current_ref, 'review is not current for this native result')
        review = require_exact_ref(self.kernel, current_ref, slot, 'image-led-result-review')['payload']
        exact(review, {'artifact_type', 'project_id', 'target_ref', 'reviewer_kind', 'reviewer_role', 'checks',
            'reviewer_task_id', 'context_pack_ref', 'producer_task_id', 'selection_ref', 'plan_ref',
            'region_inventory_ref', 'pptx_sha256', 'renders', 'comparisons'}, 'stored result review')
        _check(review['artifact_type'] == 'image-led-result-review' and review['project_id'] == self.kernel.project_id
               and review['reviewer_kind'] == 'engineering' and review['reviewer_role'] == 'visual-engineering-reviewer'
               and review['producer_task_id'] == result['producer_task_id'], 'stored result review identity changed')
        self._checks(review)
        _check(review['target_ref'] == result_ref and all(row['result'] == 'passed' for row in review['checks']),
               'native result four-dimension review has not passed')
        for key in ('selection_ref', 'plan_ref', 'region_inventory_ref', 'pptx_sha256', 'renders', 'comparisons'):
            _check(review[key] == result['output'][key], 'review output identity changed')
        task_id = review['reviewer_task_id']
        task = require_exact_ref(self.kernel, self.kernel.load().artifact_heads.get('agent/task/' + task_id, ''),
                                 'agent/task/' + task_id, 'agent-task')['payload']
        _check(task['status'] == 'completed' and task['action_type'] == 'review-visual-engineering' and task['result_refs'] == [current_ref]
               and task['target_refs'] == [result_ref] and task['role_id'] == 'visual-engineering-reviewer'
               and task_id != result['producer_task_id'] and task['role_id'] != result['producer_role']
               and task['context_pack_ref'] == review['context_pack_ref'], 'result review lacks independent completed task lineage')
        require_exact_ref(self.kernel, task['context_pack_ref'], 'agent/context/' + task_id, 'context-pack')
        return result
