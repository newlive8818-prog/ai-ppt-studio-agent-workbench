"""Deterministic local composition of exact source media into page designs.

Provider responses remain immutable. Blank-slot designs accept only empty regions.
Historical designs may use a bounded, explicit region-replacement contract so real
photos, logos, and screenshots can replace generated stand-ins without becoming a
second free-form image editor.
"""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from ai_ppt_studio.application.existing_deck_optimization import source_page_media
from ai_ppt_studio.application.image_led_ooxml import NS, P, Package
from ai_ppt_studio.domains.materials.image_input_contracts import fail

BLANK_SLOT_COMPOSITOR_VERSION = 'source-media-blank-slot-compositor/v1'
HISTORICAL_REPLACEMENT_COMPOSITOR_VERSION = 'historical-design-source-replacement/v1'
GUIDED_ROLE_CORRECTION_COMPOSITOR_VERSION = 'guided-source-media-role-correction/v1'
SINGLE_MAIN_SCREENSHOT_COMPOSITOR_VERSION = 'single-main-screenshot-focus-compositor/v1'
# Compatibility for callers and artifacts created before the historical route.
COMPOSITOR_VERSION = BLANK_SLOT_COMPOSITOR_VERSION

_HISTORICAL_EXCLUSION_REASONS = {
    'decorative-background', 'production-strip', 'generic-icon',
}


def compositor_version(layout_mode: str) -> str:
    if layout_mode in {'blank-media-slots', 'client-logo-gallery-20'}:
        return BLANK_SLOT_COMPOSITOR_VERSION
    if layout_mode == 'historical-design-import':
        return HISTORICAL_REPLACEMENT_COMPOSITOR_VERSION
    if layout_mode == 'source-media-guided':
        return GUIDED_ROLE_CORRECTION_COMPOSITOR_VERSION
    if layout_mode == 'single-main-screenshot-focus':
        return SINGLE_MAIN_SCREENSHOT_COMPOSITOR_VERSION
    fail('COMPOSITION', 'source media composition is not available for this design route')


def composition_disposition(placements: list[dict], layout_mode: str) -> dict[str, list[str]]:
    selected, excluded = [], []
    if layout_mode in {'historical-design-import', 'source-media-guided',
                       'single-main-screenshot-focus'}:
        for item in placements:
            operation = item.get('operation') if isinstance(item, dict) else None
            ids = item.get('source_picture_object_ids', []) if isinstance(item, dict) else []
            if operation in {'replace-source-region', 'place-main-source-screenshot'}:
                selected.extend(ids)
            elif operation == 'exclude-source-media' and layout_mode in {
                    'historical-design-import', 'single-main-screenshot-focus'}:
                excluded.extend(ids)
    else:
        for item in placements:
            if isinstance(item, dict):
                selected.extend(item.get('source_picture_object_ids', []))
    return {'selected_source_picture_object_ids': selected,
            'excluded_source_picture_object_ids': excluded}


def _picture_geometry(raw: bytes, page_order: int) -> dict[str, tuple[int, int, int, int]]:
    package = Package(raw)
    try:
        _, tree = package.slide(page_order)
        geometry = {}
        for picture in tree.iter(f'{{{P}}}pic'):
            identity = picture.find('p:nvPicPr/p:cNvPr', NS)
            off = picture.find('p:spPr/a:xfrm/a:off', NS)
            ext = picture.find('p:spPr/a:xfrm/a:ext', NS)
            if identity is None or off is None or ext is None:
                continue
            geometry[identity.get('id')] = (
                int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy')))
        return geometry
    finally:
        package.file.close()


def _original_mark(ids: list[str], media: dict, geometry: dict) -> Image.Image:
    if len(ids) == 1:
        return Image.open(BytesIO(base64.b64decode(media[ids[0]]['data_base64']))).convert('RGBA')
    boxes = [geometry.get(identity) for identity in ids]
    if any(box is None or box[2] <= 0 or box[3] <= 0 for box in boxes):
        fail('MEDIA', 'a grouped customer mark lacks original picture geometry')
    x0, y0 = min(box[0] for box in boxes), min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    factor = min(1000 / (x1 - x0), 250 / (y1 - y0))
    result = Image.new('RGBA', (max(1, round((x1 - x0) * factor)),
                                max(1, round((y1 - y0) * factor))), (255, 255, 255, 0))
    for identity, box in zip(ids, boxes):
        source = Image.open(BytesIO(base64.b64decode(media[identity]['data_base64']))).convert('RGBA')
        scaled = source.resize((max(1, round(box[2] * factor)),
                                max(1, round(box[3] * factor))), Image.Resampling.LANCZOS)
        result.alpha_composite(scaled, (round((box[0] - x0) * factor),
                                        round((box[1] - y0) * factor)))
    return result


def _rgb(value, field: str) -> tuple[int, int, int]:
    if (not isinstance(value, list) or len(value) != 3
            or any(type(channel) is not int or channel < 0 or channel > 255 for channel in value)):
        fail('COMPOSITION', f'{field} needs three integer RGB channels')
    return tuple(value)


def _bbox(value, *, width: int, height: int, minimum=(16, 12)) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
        fail('COMPOSITION', 'placement bbox needs four integer pixel coordinates')
    x, y, w, h = value
    if x < 0 or y < 0 or w < minimum[0] or h < minimum[1] or x + w > width or y + h > height:
        fail('COMPOSITION', 'placement bbox must fit the exact design image')
    return x, y, w, h


def _check_overlap(box, rectangles):
    x, y, w, h = box
    if any(x < ox + ow and ox < x + w and y < oy + oh and oy < y + h
           for ox, oy, ow, oh in rectangles):
        fail('COMPOSITION', 'two local correction regions overlap on the design')
    rectangles.append(box)


def _place_mark(design: Image.Image, mark: Image.Image, box, *, fit: str, fill,
                background_shape: str = 'rectangle'):
    x, y, w, h = box
    if background_shape not in {'rectangle', 'circle'}:
        fail('COMPOSITION', 'source region background shape must be rectangle or circle')
    if background_shape == 'circle' and fit != 'contain':
        fail('COMPOSITION', 'circle source regions support contain fit only')
    surface = design if background_shape == 'rectangle' else Image.new(
        'RGBA', (w, h), (255, 255, 255, 0))
    offset_x, offset_y = (x, y) if background_shape == 'rectangle' else (0, 0)
    draw = ImageDraw.Draw(surface)
    if background_shape == 'rectangle':
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=fill + (255,))
    else:
        draw.ellipse((0, 0, w - 1, h - 1), fill=fill + (255,))
    if fit == 'cover':
        placed = ImageOps.fit(mark, (w, h), method=Image.Resampling.LANCZOS,
                              centering=(0.5, 0.5))
        surface.alpha_composite(placed, (offset_x, offset_y))
        return
    if fit != 'contain':
        fail('COMPOSITION', 'source region fit must be contain or cover')
    padding = max(6, round(min(w, h) * .04))
    placed = ImageOps.contain(mark, (max(1, w - 2 * padding), max(1, h - 2 * padding)),
                              method=Image.Resampling.LANCZOS)
    surface.alpha_composite(placed, (offset_x + round((w - placed.width) / 2),
                                     offset_y + round((h - placed.height) / 2)))
    if background_shape == 'circle':
        circle = Image.new('L', (w, h), 0)
        ImageDraw.Draw(circle).ellipse((0, 0, w - 1, h - 1), fill=255)
        surface.putalpha(ImageChops.multiply(surface.getchannel('A'), circle))
        design.alpha_composite(surface, (x, y))


def _compose_blank_slots(*, design: Image.Image, media: dict, geometry: dict,
                         page: dict, placements: list[dict], layout_mode: str) -> None:
    width, height = design.size
    allowed_categories = [item['text'] for item in page['visible_copy'][1:]]
    if layout_mode == 'client-logo-gallery-20':
        if len(allowed_categories) != 4 or len(placements) != 20:
            fail('COMPOSITION', 'client gallery needs 20 slots under four source categories')
        if [item.get('category') for item in placements] != [cat for cat in allowed_categories for _ in range(5)]:
            fail('COMPOSITION', 'logo groups must match four original categories in source order')
    seen, rectangles = set(), []
    for item in placements:
        if not isinstance(item, dict) or set(item) != {'source_picture_object_ids', 'bbox'} | (
                {'category'} if layout_mode == 'client-logo-gallery-20' else set()):
            fail('COMPOSITION', 'local media placement has unexpected or missing fields')
        ids, box = item['source_picture_object_ids'], item['bbox']
        if (not isinstance(ids, list) or not ids
                or any(not isinstance(value, str) or value not in media for value in ids)
                or len(set(ids)) != len(ids) or any(value in seen for value in ids)):
            fail('COMPOSITION', 'placement needs each original picture object exactly once')
        seen.update(ids)
        box = _bbox(box, width=width, height=height, minimum=(32, 24))
        x, y, w, h = box
        if w * h > width * height / 5:
            fail('COMPOSITION', 'placement must fit a local blank slot without replacing the page')
        _check_overlap(box, rectangles)
        sample = design.crop((x + 4, y + 4, x + w - 4, y + h - 4)).convert('RGB')
        pixels = list(sample.get_flattened_data())
        if sum(min(rgb) >= 215 for rgb in pixels) / len(pixels) < .90:
            fail('COMPOSITION', 'source material may replace only a mostly blank design slot')
        mark = _original_mark(ids, media, geometry)
        max_w, max_h = w - 15, h - 25
        scale = min(max_w / mark.width, max_h / mark.height)
        mark = mark.resize((max(1, round(mark.width * scale)),
                            max(1, round(mark.height * scale))), Image.Resampling.LANCZOS)
        design.alpha_composite(mark, (x + round((w - mark.width) / 2),
                                      y + round((h - mark.height) / 2)))
    if seen != set(media):
        fail('COMPOSITION', 'some original source pictures have no exact target slot')


def _compose_historical_replacements(*, design: Image.Image, media: dict, geometry: dict,
                                     page: dict, placements: list[dict]) -> None:
    width, height = design.size
    if not isinstance(placements, list) or not placements:
        fail('COMPOSITION', 'historical design correction needs explicit bounded operations')
    used, excluded, rectangles = set(), set(), []
    replacement_area = correction_area = 0
    for item in placements:
        if not isinstance(item, dict) or not isinstance(item.get('operation'), str):
            fail('COMPOSITION', 'historical design correction needs an explicit operation')
        operation = item['operation']
        if operation in {'replace-source-region', 'exclude-source-media'}:
            ids = item.get('source_picture_object_ids')
            if (not isinstance(ids, list) or not ids
                    or any(not isinstance(value, str) or value not in media for value in ids)
                    or len(set(ids)) != len(ids)
                    or any(value in used or value in excluded for value in ids)):
                fail('COMPOSITION', 'each source picture needs one exact use or exclusion disposition')
            if operation == 'exclude-source-media':
                if set(item) != {'operation', 'source_picture_object_ids', 'reason'} \
                        or item['reason'] not in _HISTORICAL_EXCLUSION_REASONS:
                    fail('COMPOSITION', 'source-media exclusion needs one governed decorative reason')
                excluded.update(ids)
                continue
            if set(item) != {'operation', 'source_picture_object_ids', 'bbox', 'fit', 'fill_rgb'}:
                fail('COMPOSITION', 'source region replacement has unexpected or missing fields')
            box = _bbox(item['bbox'], width=width, height=height, minimum=(32, 24))
            if box[2] * box[3] > width * height * .45:
                fail('COMPOSITION', 'historical correction cannot become a whole-slide replacement')
            _check_overlap(box, rectangles)
            replacement_area += box[2] * box[3]
            mark = _original_mark(ids, media, geometry)
            _place_mark(design, mark, box, fit=item['fit'], fill=_rgb(item['fill_rgb'], 'fill_rgb'))
            used.update(ids)
            continue
        if operation == 'mask-region':
            if set(item) != {'operation', 'bbox', 'fill_rgb'}:
                fail('COMPOSITION', 'mask region has unexpected or missing fields')
            box = _bbox(item['bbox'], width=width, height=height)
            if box[2] * box[3] > width * height * .08:
                fail('COMPOSITION', 'historical mask must remain a small local correction')
            _check_overlap(box, rectangles)
            correction_area += box[2] * box[3]
            x, y, w, h = box
            ImageDraw.Draw(design).rectangle((x, y, x + w - 1, y + h - 1),
                                             fill=_rgb(item['fill_rgb'], 'fill_rgb') + (255,))
            continue
        if operation == 'page-marker':
            required = {'operation', 'bbox', 'fill_rgb', 'text_rgb', 'text', 'font_size', 'align'}
            if set(item) != required or item['text'] != f'S{page["page_order"]:02d}' \
                    or type(item['font_size']) is not int or not 10 <= item['font_size'] <= 48 \
                    or item['align'] not in {'left', 'center', 'right'}:
                fail('COMPOSITION', 'page marker must use the exact source page order and closed styling')
            box = _bbox(item['bbox'], width=width, height=height, minimum=(24, 14))
            if box[2] * box[3] > width * height * .02:
                fail('COMPOSITION', 'page marker correction must remain local')
            _check_overlap(box, rectangles)
            correction_area += box[2] * box[3]
            x, y, w, h = box
            fill = _rgb(item['fill_rgb'], 'fill_rgb')
            color = _rgb(item['text_rgb'], 'text_rgb')
            draw = ImageDraw.Draw(design)
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=fill + (255,))
            font = ImageFont.load_default(size=item['font_size'])
            text_box = draw.textbbox((0, 0), item['text'], font=font)
            text_w, text_h = text_box[2] - text_box[0], text_box[3] - text_box[1]
            tx = {'left': x + 4, 'center': x + (w - text_w) / 2,
                  'right': x + w - text_w - 4}[item['align']]
            ty = y + (h - text_h) / 2 - text_box[1]
            draw.text((tx, ty), item['text'], font=font, fill=color + (255,))
            continue
        fail('COMPOSITION', 'unsupported historical design correction operation')
    all_media = set(media)
    if used & excluded or used | excluded != all_media:
        fail('COMPOSITION', 'every source picture needs one exact use or exclusion disposition')
    if not used:
        fail('COMPOSITION', 'historical correction must restore at least one exact source picture')
    if replacement_area > width * height * .65 or correction_area > width * height * .12 \
            or replacement_area + correction_area > width * height * .70:
        fail('COMPOSITION', 'historical correction cannot become a whole-slide replacement')


def _compose_guided_role_corrections(*, design: Image.Image, media: dict, geometry: dict,
                                     placements: list[dict]) -> None:
    width, height = design.size
    if not isinstance(placements, list) or not placements:
        fail('COMPOSITION', 'guided source-media correction needs explicit bounded operations')
    used, rectangles = set(), []
    replacement_area = correction_area = 0
    for item in placements:
        if not isinstance(item, dict) or not isinstance(item.get('operation'), str):
            fail('COMPOSITION', 'guided source-media correction needs an explicit operation')
        operation = item['operation']
        if operation == 'replace-source-region':
            if set(item) != {
                    'operation', 'source_picture_object_ids', 'bbox', 'fit', 'fill_rgb',
                    'background_shape'}:
                fail('COMPOSITION', 'guided source replacement has unexpected or missing fields')
            ids = item['source_picture_object_ids']
            if (not isinstance(ids, list) or not ids
                    or any(not isinstance(value, str) or value not in media for value in ids)
                    or len(set(ids)) != len(ids) or any(value in used for value in ids)):
                fail('COMPOSITION', 'each guided source picture needs one exact replacement region')
            box = _bbox(item['bbox'], width=width, height=height, minimum=(24, 20))
            if box[2] * box[3] > width * height * .12:
                fail('COMPOSITION', 'guided source replacement must remain a local role correction')
            _check_overlap(box, rectangles)
            replacement_area += box[2] * box[3]
            mark = _original_mark(ids, media, geometry)
            _place_mark(design, mark, box, fit=item['fit'], fill=_rgb(item['fill_rgb'], 'fill_rgb'),
                        background_shape=item['background_shape'])
            used.update(ids)
            continue
        if operation == 'mask-region':
            if set(item) != {'operation', 'bbox', 'fill_rgb'}:
                fail('COMPOSITION', 'guided mask region has unexpected or missing fields')
            box = _bbox(item['bbox'], width=width, height=height)
            if box[2] * box[3] > width * height * .025:
                fail('COMPOSITION', 'guided mask must remain a small local correction')
            _check_overlap(box, rectangles)
            correction_area += box[2] * box[3]
            x, y, w, h = box
            ImageDraw.Draw(design).rectangle((x, y, x + w - 1, y + h - 1),
                                             fill=_rgb(item['fill_rgb'], 'fill_rgb') + (255,))
            continue
        fail('COMPOSITION', 'guided source-media correction supports only exact replacement or mask')
    if used != set(media):
        fail('COMPOSITION', 'guided source-media correction must restore every source picture exactly once')
    if replacement_area > width * height * .40 or correction_area > width * height * .05 \
            or replacement_area + correction_area > width * height * .42:
        fail('COMPOSITION', 'guided source-media correction cannot become a page redesign')


def _compose_single_main_screenshot(*, design: Image.Image, media: dict, geometry: dict,
                                    placements: list[dict]) -> None:
    width, height = design.size
    if not isinstance(placements, list) or not placements:
        fail('COMPOSITION', 'single main screenshot composition needs explicit operations')
    used, excluded, rectangles = set(), set(), []
    for item in placements:
        if not isinstance(item, dict) or not isinstance(item.get('operation'), str):
            fail('COMPOSITION', 'single main screenshot composition needs an explicit operation')
        operation = item['operation']
        ids = item.get('source_picture_object_ids')
        if (not isinstance(ids, list) or not ids
                or any(not isinstance(value, str) or value not in media for value in ids)
                or len(set(ids)) != len(ids) or any(value in used or value in excluded for value in ids)):
            fail('COMPOSITION', 'single main screenshot media needs one exact disposition')
        if operation == 'exclude-source-media':
            if (set(item) != {'operation', 'source_picture_object_ids', 'reason'}
                    or item['reason'] not in _HISTORICAL_EXCLUSION_REASONS):
                fail('COMPOSITION', 'single main screenshot exclusions need a governed decorative reason')
            excluded.update(ids)
            continue
        if operation != 'place-main-source-screenshot' or set(item) != {
                'operation', 'source_picture_object_ids', 'bbox', 'fit', 'fill_rgb'} or len(ids) != 1:
            fail('COMPOSITION', 'single main screenshot needs one exact source image and one blank slot')
        if used:
            fail('COMPOSITION', 'single main screenshot composition accepts only one placed source image')
        box = _bbox(item['bbox'], width=width, height=height, minimum=(160, 90))
        if box[2] * box[3] > width * height * .70:
            fail('COMPOSITION', 'single main screenshot cannot replace the whole page')
        _check_overlap(box, rectangles)
        x, y, w, h = box
        sample = design.crop((x + 4, y + 4, x + w - 4, y + h - 4)).convert('RGB')
        pixels = list(sample.get_flattened_data())
        if sum(min(rgb) >= 215 for rgb in pixels) / len(pixels) < .85:
            fail('COMPOSITION', 'main screenshot may replace only the reserved mostly blank slot')
        mark = _original_mark(ids, media, geometry)
        if item['fit'] != 'contain':
            fail('COMPOSITION', 'main screenshot must use contain fit')
        padding = max(6, round(min(w, h) * .04))
        scale = min((w - 2 * padding) / mark.width, (h - 2 * padding) / mark.height)
        displayed_width = max(1, round(mark.width * scale))
        displayed_height = max(1, round(mark.height * scale))
        if displayed_width < width * .45 or displayed_height < height * .35:
            fail('COMPOSITION',
                 'main screenshot slot is not meeting-readable after contain placement')
        _place_mark(design, mark, box, fit=item['fit'], fill=_rgb(item['fill_rgb'], 'fill_rgb'))
        used.update(ids)
    if len(used) != 1 or used & excluded or used | excluded != set(media):
        fail('COMPOSITION', 'one main screenshot must be placed and every other source image explicitly excluded')


def compose_original_media(*, response_bytes: bytes, source_pptx_bytes: bytes,
                           page: dict, placements: list[dict], layout_mode: str) -> bytes:
    """Return an exact composite PNG or fail before writing a Runtime artifact."""
    compositor_version(layout_mode)
    source = source_page_media(source_pptx_bytes, page)
    media = {item['atom_id']: item for item in source}
    if not media or not isinstance(placements, list) or not placements:
        fail('COMPOSITION', 'the current source page needs a complete local media placement map')
    with Image.open(BytesIO(response_bytes)) as decoded:
        decoded.load()
        design = decoded.convert('RGBA')
    geometry = _picture_geometry(source_pptx_bytes, page['page_order'])
    if layout_mode == 'historical-design-import':
        _compose_historical_replacements(design=design, media=media, geometry=geometry,
                                         page=page, placements=placements)
    elif layout_mode == 'source-media-guided':
        _compose_guided_role_corrections(design=design, media=media, geometry=geometry,
                                         placements=placements)
    elif layout_mode == 'single-main-screenshot-focus':
        _compose_single_main_screenshot(design=design, media=media, geometry=geometry,
                                        placements=placements)
    else:
        _compose_blank_slots(design=design, media=media, geometry=geometry,
                             page=page, placements=placements, layout_mode=layout_mode)
    result = BytesIO()
    design.convert('RGB').save(result, format='PNG')
    return result.getvalue()
