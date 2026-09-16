#!/usr/bin/env python3
"""Local, read-only audit of the nine explicitly scoped C2 source files.

Prints a deterministic structural inventory to stdout. With --inspect, writes
full XML text observations to a new private inspection file (never to sources).
It does not render slides, OCR images, resolve external links or write Runtime.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import posixpath
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image

BASE = Path('/Users/defei/Documents/项目资料/低代码项目/机电集团/00_一客一档')
NAMES = [
    '重庆机电合作.pptx',
    '重庆机电智能制造有限公司合作意向与能力展示.pptx',
    '重庆机电智能制造全域数字化解决方案_v13(1).pptx',
    '重庆机电智能制造公司介绍（05.19新）.pptx',
    '集成应用.jpg', '集团门户.jpg', '采购系统.jpg',
    '重庆机电智能制造有限公司业务背景文件(1).md',
    '全域数字化解决方案_文字审阅稿_v3.md',
]
NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_sha(value):
    return sha(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def relationships(z, part):
    relpart = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    if relpart not in z.namelist():
        return {}
    result = {}
    for r in ET.fromstring(z.read(relpart)):
        external = r.get('TargetMode') == 'External'
        target = r.get('Target', '')
        result[r.get('Id')] = {
            'kind': r.get('Type', '').rsplit('/', 1)[-1],
            'external': external,
            'target': target if external else posixpath.normpath(
                target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(part), target)),
        }
    return result


def paragraphs(root):
    # Source XML paragraphs, not proof of rendered visibility or reading order.
    result = []
    for p in root.findall('.//a:p', NS):
        value = ''.join('\n' if n.tag == '{' + NS['a'] + '}br' else (n.text or '')
                        for n in p.iter() if n.tag in ('{' + NS['a'] + '}t', '{' + NS['a'] + '}br'))
        if value.strip():
            result.append(value)
    return result


def image_info(data):
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return {'decode': 'readable', 'format': im.format, 'width': im.width, 'height': im.height}
    except Exception as exc:
        return {'decode': 'not_decoded_by_pillow', 'error_type': type(exc).__name__}


def pptx_info(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        bad = z.testzip()
        if bad:
            raise ValueError('ZIP CRC failure: ' + bad)
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate ZIP member')
        ppart = 'ppt/presentation.xml'
        p = ET.fromstring(z.read(ppart))
        rels = relationships(z, ppart)
        ordered, inspected = [], []
        assets = []
        for name in sorted(n for n in z.namelist() if n.startswith('ppt/media/') and not n.endswith('/')):
            b = z.read(name)
            assets.append({'part': name, 'sha256': sha(b), 'bytes': len(b), **image_info(b)})
        asset_by_part = {a['part']: a for a in assets}
        for order, sid in enumerate(p.findall('./p:sldIdLst/p:sldId', NS), 1):
            rel = rels[sid.get('{' + NS['r'] + '}id')]
            if rel['external'] or rel['kind'] != 'slide':
                raise ValueError('invalid ordered slide relationship')
            part = rel['target']
            raw = z.read(part)
            root = ET.fromstring(raw)
            sr = relationships(z, part)
            objects, hidden_objects = [], []
            for shape in root.iter():
                if shape.tag not in ['{' + NS['p'] + '}' + n for n in ('sp', 'pic', 'graphicFrame')]:
                    continue
                cnv = shape.find('.//p:cNvPr', NS)
                if cnv is None:
                    continue
                obj = {'shape_id': cnv.get('id'), 'xml_paragraphs': paragraphs(shape)}
                pictures = []
                for blip in shape.findall('.//a:blip', NS):
                    rid = blip.get('{' + NS['r'] + '}embed') or blip.get('{' + NS['r'] + '}link')
                    ar = sr.get(rid)
                    if ar and not ar['external']:
                        pictures.append({'relationship_id': rid, 'part': ar['target'],
                                         'sha256': sha(z.read(ar['target']))})
                obj['images'] = pictures
                (hidden_objects if cnv.get('hidden') in ('1', 'true') else objects).append(obj)
            texts = [t for o in objects for t in o['xml_paragraphs']]
            notes = []
            for nr in sr.values():
                if nr['kind'] == 'notesSlide' and not nr['external']:
                    nb = z.read(nr['target'])
                    notes.append({'part': nr['target'], 'sha256': sha(nb),
                                  'paragraph_count': len(paragraphs(ET.fromstring(nb)))})
            refs = []
            for rid, ar in sr.items():
                if not ar['external'] and ar['kind'] == 'image':
                    asset = asset_by_part.get(ar['target'])
                    refs.append({'relationship_id': rid, 'part': ar['target'],
                                 'sha256': asset['sha256'] if asset else sha(z.read(ar['target']))})
            ordered.append({
                'page_order': order, 'presentation_slide_id': sid.get('id'), 'part': part,
                'slide_xml_sha256': sha(raw), 'slide_hidden': root.get('show') in ('0', 'false'),
                'xml_text_sha256': json_sha(texts), 'xml_paragraph_count': len(texts),
                'xml_character_count': sum(map(len, texts)),
                'visibility': 'source_xml_only_not_rendered',
                'hidden_shape_count': len(hidden_objects), 'notes': notes,
                'slide_image_relationships': refs,
                'external_relationship_count': sum(r['external'] for r in sr.values()),
            })
            inspected.append({'page_order': order, 'part': part, 'objects': objects,
                              'hidden_objects': hidden_objects})
        size = p.find('p:sldSz', NS)
        return {'parse_status': 'readable_nonempty' if ordered else 'empty_presentation',
                'zip_crc': 'pass', 'presentation_xml_sha256': sha(z.read(ppart)),
                'slide_size_emu': dict(size.attrib) if size is not None else None,
                'ordered_page_count': len(ordered), 'pages': ordered,
                'media_part_count': len(assets), 'media': assets}, inspected


def audit():
    sources, inspection = [], {}
    for number, name in enumerate(NAMES, 1):
        path = BASE / name
        if path.is_symlink() or path.resolve().parent != BASE.resolve():
            raise ValueError('unexpected source path')
        b = path.read_bytes()
        row = {'source_id': f'M{number:02}', 'path': str(path), 'bytes': len(b), 'sha256': sha(b)}
        try:
            if path.suffix == '.pptx':
                details, inspection[row['source_id']] = pptx_info(b)
                row.update(details)
            elif path.suffix == '.jpg':
                row.update(image_info(b))
                row['parse_status'] = row.pop('decode')
            else:
                text = b.decode('utf-8')
                row.update(parse_status='readable_nonempty' if text.strip() else 'empty_text',
                           line_count=len(text.splitlines()))
        except (zipfile.BadZipFile, KeyError, ValueError, ET.ParseError, UnicodeError) as exc:
            row.update(parse_status='parse_failure', error_type=type(exc).__name__, error=str(exc))
        sources.append(row)
    return {'schema': 'c2-local-source-audit-v1', 'scope': 'nine_named_files_only',
            'status': 'local_audit_not_runtime_registration_or_g0',
            'text_hash_encoding': 'UTF-8 JSON array ensure_ascii=False separators=(comma,colon)',
            'visibility_limit': 'XML records are not rendered visibility; inherited master/layout text, chart data, SmartArt and raster text require separate review. Media includes unused assets; media membership is not approval.',
            'sources': sources}, inspection


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', type=Path, help='New file under /private/tmp for local-only raw text inspection')
    args = parser.parse_args()
    if args.inspect and Path('/private/tmp') not in args.inspect.resolve().parents:
        parser.error('--inspect must be under /private/tmp')
    inventory, inspection = audit()
    if args.inspect:
        with args.inspect.open('x', encoding='utf-8') as f:
            json.dump(inspection, f, ensure_ascii=False, indent=2)
    print(json.dumps(inventory, ensure_ascii=False, indent=2))
