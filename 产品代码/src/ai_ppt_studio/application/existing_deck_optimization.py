"""Fail-closed admission of an existing PPTX as a source, never as a design."""
from __future__ import annotations

import hashlib
import re
import base64
from copy import deepcopy
from io import BytesIO

from PIL import Image

from ai_ppt_studio.application.artifact_guards import require_revision, resolve_kind
from ai_ppt_studio.application.image_led_ooxml import A, P, R, NS, Package, object_text, unsupported
from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
from ai_ppt_studio.errors import ContractValidationError

SOURCE_SLOT = 'optimization/source'
ROUTE_SLOT = 'project/optimization-workflow'
ROUTE_ID = 'existing-deck-optimization/v1'
EXTERNAL_SCOPE_SLOT = 'optimization/external-use-scope'

# An observed PPTX-internal 1x1 fully transparent PNG is a non-visible
# placeholder. Preserve it in source identity but never send it as customer
# media or make it a required editable visual. Do not generalize by size alone.
TRANSPARENT_PLACEHOLDER_BYTES = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c6360000000020001e221bea70000000049454e44ae426082')
TRANSPARENT_PLACEHOLDER_SHA256 = hashlib.sha256(TRANSPARENT_PLACEHOLDER_BYTES).hexdigest()


def source_real_media_refs(page: dict) -> list[dict]:
    return [row for row in page['media_refs']
            if row['sha256'] != TRANSPARENT_PLACEHOLDER_SHA256]



def _source_inventory(raw: bytes) -> list[dict]:
    """Derive page order, native copy and embedded-media identity from bytes."""
    package = Package(raw)
    try:
        main = [target for kind, target in package.rels.get('', {}).values()
                if kind == R + '/officeDocument']
        if len(main) != 1:
            unsupported('source PPTX has no unique presentation part')
        presentation = package.read_xml(main[0])
        lists = presentation.findall('p:sldIdLst', NS)
        if presentation.tag != f'{{{P}}}presentation' or len(lists) != 1 or not list(lists[0]):
            unsupported('source PPTX needs an explicit nonempty slide sequence')
        slides = []
        for order in range(1, len(lists[0]) + 1):
            part, tree = package.slide(order)
            text_items, media_items, object_ids = [], [], set()
            for item in tree.iter():
                kind = item.tag.rsplit('}', 1)[-1]
                if item.tag not in {f'{{{P}}}{name}' for name in ('sp', 'graphicFrame', 'cxnSp', 'pic')}:
                    continue
                holder = {'sp': 'nvSpPr', 'graphicFrame': 'nvGraphicFramePr',
                          'cxnSp': 'nvCxnSpPr', 'pic': 'nvPicPr'}[kind]
                identity = item.find(f'p:{holder}/p:cNvPr', NS)
                object_id = identity.get('id') if identity is not None else None
                if not object_id or object_id in object_ids:
                    unsupported('source PPTX has missing or duplicated object identities')
                object_ids.add(object_id)
                if kind == 'pic':
                    blips = item.findall('p:blipFill/a:blip', NS)
                    if (len(blips) != 1 or blips[0].get(f'{{{R}}}link')
                            or not blips[0].get(f'{{{R}}}embed')):
                        unsupported('linked or ambiguous source picture')
                    target = package.target(part, blips[0].get(f'{{{R}}}embed'), 'image')
                    media_items.append({'object_id': object_id,
                        'sha256': hashlib.sha256(package.file.read(target)).hexdigest()})
                elif kind == 'graphicFrame' or item.find('p:txBody', NS) is not None:
                    value = object_text(item)
                    if value:
                        text_items.append({'item_id': 'source-object-' + object_id, 'text': value})
            slides.append({'slide_id': f'S{order:04d}', 'page_order': order,
                           'visible_copy': text_items, 'media_refs': media_items})
        return slides
    finally:
        package.file.close()


def source_page_media(raw: bytes, page: dict) -> list[dict]:
    """Replay embedded picture bytes for the source page in exact object order."""
    package = Package(raw)
    try:
        part, tree = package.slide(page['page_order'])
        result, observed = [], []
        for item in tree.iter(f'{{{P}}}pic'):
            identity = item.find('p:nvPicPr/p:cNvPr', NS)
            blips = item.findall('p:blipFill/a:blip', NS)
            if identity is None or len(blips) != 1 or blips[0].get(f'{{{R}}}link'):
                unsupported('source picture cannot be replayed')
            target = package.target(part, blips[0].get(f'{{{R}}}embed'), 'image')
            image_bytes = package.file.read(target)
            digest = hashlib.sha256(image_bytes).hexdigest()
            object_id = identity.get('id')
            observed.append({'object_id': object_id, 'sha256': digest})
            if image_bytes == TRANSPARENT_PLACEHOLDER_BYTES:
                continue
            with Image.open(BytesIO(image_bytes)) as decoded:
                decoded.load()
                if decoded.format not in {'PNG', 'JPEG'} or getattr(decoded, 'n_frames', 1) != 1:
                    unsupported('source media needs independently usable PNG/JPEG bytes')
                mime = 'image/png' if decoded.format == 'PNG' else 'image/jpeg'
                dimensions = (decoded.width, decoded.height)
            result.append({'atom_id': object_id, 'type': 'image', 'use': 'real-material',
                'content_sha256': digest, 'data_base64': base64.b64encode(image_bytes).decode('ascii'),
                'mime_type': mime, 'width': dimensions[0], 'height': dimensions[1]})
        if observed != page['media_refs']:
            unsupported('source media and current page inventory differ')
        return result
    finally:
        package.file.close()


def source_page_media_guidance(raw: bytes, page: dict) -> list[dict]:
    """Bind each replayable source image to its exact source-page geometry."""
    package = Package(raw)
    try:
        main = [target for kind, target in package.rels.get('', {}).values()
                if kind == R + '/officeDocument']
        if len(main) != 1:
            unsupported('source PPTX has no unique presentation part')
        presentation = package.read_xml(main[0])
        sizes = presentation.findall('p:sldSz', NS)
        if len(sizes) != 1:
            unsupported('source-media guidance needs one explicit slide size')
        try:
            slide_width = int(sizes[0].get('cx', ''))
            slide_height = int(sizes[0].get('cy', ''))
        except ValueError:
            unsupported('source-media guidance has an invalid slide size')
        if slide_width < 1 or slide_height < 1:
            unsupported('source-media guidance needs a positive slide size')
        part, tree = package.slide(page['page_order'])
        result, observed = [], []
        for item in tree.iter(f'{{{P}}}pic'):
            identity = item.find('p:nvPicPr/p:cNvPr', NS)
            blips = item.findall('p:blipFill/a:blip', NS)
            if identity is None or len(blips) != 1 or blips[0].get(f'{{{R}}}link'):
                unsupported('source picture cannot be guided')
            target = package.target(part, blips[0].get(f'{{{R}}}embed'), 'image')
            image_bytes = package.file.read(target)
            digest = hashlib.sha256(image_bytes).hexdigest()
            object_id = identity.get('id')
            observed.append({'object_id': object_id, 'sha256': digest})
            if image_bytes == TRANSPARENT_PLACEHOLDER_BYTES:
                continue
            transforms = item.findall('p:spPr/a:xfrm', NS)
            if len(transforms) != 1:
                unsupported('source-media guidance needs one picture transform')
            offsets = transforms[0].findall('a:off', NS)
            extents = transforms[0].findall('a:ext', NS)
            if len(offsets) != 1 or len(extents) != 1:
                unsupported('source-media guidance needs explicit picture position and size')
            try:
                x, y = int(offsets[0].get('x', '')), int(offsets[0].get('y', ''))
                width, height = int(extents[0].get('cx', '')), int(extents[0].get('cy', ''))
            except ValueError:
                unsupported('source-media guidance has invalid picture geometry')
            if width < 1 or height < 1:
                unsupported('source-media guidance needs positive picture dimensions')
            bbox = [round(10000 * value / bound) for value, bound in (
                (x, slide_width), (y, slide_height),
                (width, slide_width), (height, slide_height))]
            full_bleed = (abs(bbox[0]) <= 10 and abs(bbox[1]) <= 10
                          and bbox[2] >= 9900 and bbox[3] >= 9900)
            result.append({'image_number': len(result) + 1, 'object_id': object_id,
                'content_sha256': digest, 'source_bbox': bbox,
                'source_role': 'full-bleed-background' if full_bleed else 'positioned-source-media'})
        if observed != page['media_refs']:
            unsupported('source media guidance and current page inventory differ')
        return result
    finally:
        package.file.close()


class ExistingDeckOptimizationService:
    def __init__(self, kernel):
        self.kernel = kernel

    def begin(self, command_id: str, expected_revision: int, *, source_id: str,
              source_pptx_sha256: str, user_message_ref: str) -> str:
        state = require_revision(self.kernel, expected_revision)
        if (not isinstance(user_message_ref, str) or not (
                user_message_ref.startswith('chat://message/') and user_message_ref != 'chat://message/'
                or re.fullmatch(r'agent-recorded://thread/[0-9a-f-]{36}/turn/[0-9a-f-]{36}', user_message_ref))):
            raise ContractValidationError('Existing-deck route needs a traceable user instruction identity')
        if not isinstance(source_pptx_sha256, str) or not re.fullmatch('[0-9a-f]{64}', source_pptx_sha256):
            raise ContractValidationError('Existing-deck source needs an actual SHA-256')
        if (state.gate_status.get('G0') != 'open'
                or any(slot in state.artifact_heads for slot in (
                    ROUTE_SLOT, 'project/visual-workflow', 'mission/confirmation',
                    'content/reading-blueprint', 'gate/G0/confirmation'))):
            raise ContractValidationError('Existing-deck route needs a fresh source-only project')
        inventory_ref = state.artifact_heads.get('materials', '')
        if not inventory_ref:
            raise ContractValidationError('Existing-deck route needs a registered source PPTX')
        inventory = resolve_kind(self.kernel, inventory_ref, 'material-inventory')['payload']
        matches = [item for item in inventory['sources'] if item['source_id'] == source_id]
        if len(matches) != 1:
            raise ContractValidationError('Existing-deck source ID is not unique in current materials')
        source = matches[0]
        if (source.get('kind') != 'file' or source.get('origin') != 'user-provided'
                or not source.get('locator', '').startswith('project://')
                or source.get('project_copy') != source['locator'][len('project://'):]
                or source['sha256'] != source_pptx_sha256):
            raise ContractValidationError('Existing-deck source must be the exact managed PPTX snapshot')
        reader = MaterialSourceReader(self.kernel)
        path = reader._path(source['locator'], source_kind=source['kind'])
        raw = reader._read(path)
        if hashlib.sha256(raw).hexdigest() != source_pptx_sha256:
            raise ContractValidationError('Existing-deck source bytes changed since registration')
        slides = _source_inventory(raw)
        snapshot = {'artifact_type': 'source-deck-snapshot', 'project_id': self.kernel.project_id,
                    'material_inventory_ref': inventory_ref, 'source_id': source_id,
                    'source_pptx_sha256': source_pptx_sha256,
                    'source_pptx_ref': 'project://' + source['project_copy'], 'slides': slides}
        state = self.kernel.commit(command_id=command_id, expected_revision=expected_revision,
            event_type='optimization.source-bound', artifact_updates={
                ROUTE_SLOT: ('optimization-workflow', {'project_id': self.kernel.project_id,
                    'workflow': ROUTE_ID, 'user_message_ref': user_message_ref,
                    'authorization_identity': 'agent-recorded' if user_message_ref.startswith('agent-recorded://') else 'chat-reference-unverified'}),
                SOURCE_SLOT: ('source-deck-snapshot', deepcopy(snapshot))})
        return state.artifact_heads[SOURCE_SLOT]

    def current_source(self):
        state = self.kernel.load()
        workflow = resolve_kind(self.kernel, state.artifact_heads.get(ROUTE_SLOT, ''),
                                'optimization-workflow')['payload']
        if workflow.get('project_id') != self.kernel.project_id or workflow.get('workflow') != ROUTE_ID:
            raise ContractValidationError('Existing-deck route is not current')
        ref = state.artifact_heads.get(SOURCE_SLOT, '')
        source = resolve_kind(self.kernel, ref, 'source-deck-snapshot')['payload']
        if source['material_inventory_ref'] != state.artifact_heads.get('materials'):
            raise ContractValidationError('Existing-deck source is stale after materials changed')
        inventory = resolve_kind(self.kernel, source['material_inventory_ref'], 'material-inventory')['payload']
        matches = [item for item in inventory['sources'] if item['source_id'] == source['source_id']]
        if len(matches) != 1 or matches[0]['sha256'] != source['source_pptx_sha256']:
            raise ContractValidationError('Existing-deck source inventory changed')
        reader = MaterialSourceReader(self.kernel)
        raw = reader._read(reader._path(matches[0]['locator'], source_kind=matches[0]['kind']))
        if hashlib.sha256(raw).hexdigest() != source['source_pptx_sha256'] or _source_inventory(raw) != source['slides']:
            raise ContractValidationError('Existing-deck source bytes or page inventory changed')
        return source

    def set_external_scope(self, command_id: str, expected_revision: int, *,
                           user_message_ref: str, allowed_page_orders: list[int],
                           excluded_image_sha256: list[str], excluded_text_item_ids: list[str]) -> str:
        """Record explicit source use boundaries; no default permission to send a deck."""
        state = require_revision(self.kernel, expected_revision)
        source = self.current_source()
        if (not isinstance(user_message_ref, str) or not (
                user_message_ref.startswith('chat://message/') and user_message_ref != 'chat://message/'
                or re.fullmatch(r'agent-recorded://thread/[0-9a-f-]{36}/turn/[0-9a-f-]{36}', user_message_ref))):
            raise ContractValidationError('External source use requires a traceable instruction identity')
        all_pages = {item['page_order'] for item in source['slides']}
        if (not isinstance(allowed_page_orders, list) or not allowed_page_orders
                or any(type(item) is not int or item not in all_pages for item in allowed_page_orders)
                or len(set(allowed_page_orders)) != len(allowed_page_orders)):
            raise ContractValidationError('External scope must list exact authorized source pages')
        actual_images = {image['sha256'] for page in source['slides'] for image in page['media_refs']}
        actual_text = {item['item_id'] for page in source['slides'] for item in page['visible_copy']}
        if (not isinstance(excluded_image_sha256, list) or len(set(excluded_image_sha256)) != len(excluded_image_sha256)
                or any(not isinstance(value, str) or value not in actual_images for value in excluded_image_sha256)
                or not isinstance(excluded_text_item_ids, list)
                or len(set(excluded_text_item_ids)) != len(excluded_text_item_ids)
                or any(not isinstance(value, str) or value not in actual_text for value in excluded_text_item_ids)):
            raise ContractValidationError('External exclusions must bind actual source item or media identities')
        from ai_ppt_studio.adapters.image2_crs import MODEL, SUNBURST_MODEL
        scope = {'project_id': self.kernel.project_id, 'source_ref': state.artifact_heads[SOURCE_SLOT],
            'source_pptx_sha256': source['source_pptx_sha256'],
            'receiver': 'CRS', 'model': SUNBURST_MODEL, 'user_message_ref': user_message_ref,
            'authority': 'agent-recorded-user-scope', 'allowed_page_orders': sorted(allowed_page_orders),
            'excluded_image_sha256': sorted(excluded_image_sha256),
            'excluded_text_item_ids': sorted(excluded_text_item_ids)}
        existing_ref = state.artifact_heads.get(EXTERNAL_SCOPE_SLOT, '')
        event_type = 'optimization.source-external-use-bound'
        if existing_ref:
            existing = resolve_kind(self.kernel, existing_ref,
                                    'optimization-external-use-scope')['payload']
            unchanged = {key: existing.get(key) for key in (
                'project_id', 'source_ref', 'source_pptx_sha256', 'receiver',
                'authority', 'allowed_page_orders', 'excluded_image_sha256',
                'excluded_text_item_ids')}
            expected = {key: scope[key] for key in unchanged}
            if existing.get('model') != MODEL or unchanged != expected:
                raise ContractValidationError(
                    'Existing-deck external use scope cannot be silently replaced')
            scope['supersedes_scope_ref'] = existing_ref
            event_type = 'optimization.source-external-use-upgraded'
        committed = self.kernel.commit(command_id=command_id, expected_revision=expected_revision,
            event_type=event_type,
            artifact_updates={EXTERNAL_SCOPE_SLOT: ('optimization-external-use-scope', scope)})
        return committed.artifact_heads[EXTERNAL_SCOPE_SLOT]

    def current_external_scope(self, page: dict) -> dict:
        state = self.kernel.load()
        ref = state.artifact_heads.get(EXTERNAL_SCOPE_SLOT, '')
        if not ref:
            raise ContractValidationError('Existing-deck source has no explicit external-use scope')
        scope = resolve_kind(self.kernel, ref, 'optimization-external-use-scope')['payload']
        source = self.current_source()
        if (scope.get('project_id') != self.kernel.project_id
                or scope.get('source_ref') != state.artifact_heads.get(SOURCE_SLOT)
                or scope.get('source_pptx_sha256') != source['source_pptx_sha256']
                or (scope.get('receiver'), scope.get('model')) != (
                    'CRS', 'gpt-image-2.5-sunburst')
                or scope.get('authority') != 'agent-recorded-user-scope'
                or page.get('page_order') not in scope.get('allowed_page_orders', [])
                or any(item['sha256'] in scope.get('excluded_image_sha256', []) for item in page['media_refs'])
                or any(item['item_id'] in scope.get('excluded_text_item_ids', []) for item in page['visible_copy'])):
            raise ContractValidationError('Existing-deck page or material is outside its external-use scope')
        return scope
