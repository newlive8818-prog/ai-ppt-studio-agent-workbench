#!/usr/bin/env python3
"""Verify local audit against actual read-only source bytes; print receipt JSON."""
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image
import audit_sources as audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COUNTS = {}
ERRORS = []


def check(condition, name):
    COUNTS[name] = COUNTS.get(name, 0) + 1
    if not condition:
        ERRORS.append(name + ':' + str(COUNTS[name]))


def load(name):
    return json.loads((HERE / name).read_bytes())


def verify():
    inventory = load('source-inventory.json')
    fresh, inspected = audit.audit()
    check(inventory == fresh, 'deterministic_source_inventory')
    check(len(fresh['sources']) == 9, 'nine_sources')
    check(all(s['parse_status'] in ('readable', 'readable_nonempty') for s in fresh['sources']), 'all_sources_readable')
    sources = {s['source_id']: s for s in inventory['sources']}
    sel = load('material-selections.json')
    for group in sel['pptx_text_candidates']:
        source = sources[group['source_id']]
        check(source['sha256'] == group['source_sha256'], 'pptx_source_hash')
        page = next(p for p in source['pages'] if p['page_order'] == group['page_order'])
        check(page['part'] == group['slide_part'] and page['slide_xml_sha256'] == group['slide_xml_sha256'], 'pptx_page_identity')
        observed = next(p for p in inspected[group['source_id']] if p['page_order'] == group['page_order'])
        for e in group['excerpts']:
            objects = [o for o in observed['objects'] if o['shape_id'] == e['shape_id']]
            check(len(objects) == 1 and objects[0]['xml_paragraphs'] == e['exact_xml_paragraphs'], 'exact_pptx_shape_text')
    for group in sel['markdown_text_candidates']:
        s = sources[group['source_id']]
        raw = Path(s['path']).read_bytes()
        exact = ''.join(raw.decode('utf-8').splitlines(keepends=True)[group['line_start']-1:group['line_end']])
        check(audit.sha(raw) == group['source_sha256'], 'md_source_hash')
        check(exact == group['exact_text'] and audit.sha(exact.encode()) == group['text_sha256'], 'md_exact_lines_and_raw_newlines')
    for c in sel['jpeg_crop_candidates']:
        source = sources[c['source_id']]
        check(source['sha256'] == c['source_sha256'], 'crop_source_hash')
        cropfile = Path(c['inspection_file'])
        with Image.open(source['path']) as im:
            left, top, right, bottom = c['bbox_xyxy']
            check(0 <= left < right <= im.width and 0 <= top < bottom <= im.height, 'crop_bounds')
            expected = im.crop(c['bbox_xyxy'])
            encoded = io.BytesIO()
            expected.save(encoded, format='PNG')
            check(audit.sha(encoded.getvalue()) == c['sha256'], 'crop_exact_png_derivation')
            if cropfile.exists():
                check(audit.sha(cropfile.read_bytes()) == c['sha256'], 'crop_file_hash')
                with Image.open(cropfile) as crop:
                    check(expected.size == crop.size and expected.convert('RGB').tobytes() == crop.convert('RGB').tobytes(), 'crop_exact_source_pixels')
        check(not c['image2_input_selected'] and not c['external_send_authorized'], 'crop_not_external_request')
    for c in sel['embedded_photo_candidates']:
        s = sources[c['source_id']]
        with zipfile.ZipFile(s['path']) as z:
            check(audit.sha(z.read(c['media']['part'])) == c['media']['sha256'], 'photo_exact_asset')
        check(s['sha256'] == c['source_sha256'], 'photo_source_hash')
    history = load('historical-copy.json')
    for f in history['source_files']:
        check(audit.sha(Path(f['path']).read_bytes()) == f['actual_sha256'], 'historical_source_hash')
    check(audit.sha((Path(history['handoff_root']) / 'manifest.json').read_bytes()) == history['manifest_expected_sha256'], 'pinned_historical_manifest')
    transcribed = json.loads((Path(history['handoff_root']) / 'accepted/transcribed-visible-text.json').read_bytes())
    # The handoff transcription is a plain array, verified separately from new input.
    for page in history['pages']:
        exact = [transcribed[i]['text'] for i in page['source_array_indices']]
        check(exact == page['exact_text_array'], 'historical_exact_copy')
        check(audit.json_sha(exact) == page['audit_derived_text_array_sha256'], 'historical_audit_copy_hash')
        check(audit.sha(Path(page['image']['verified_snapshot_path']).read_bytes()) == page['image']['expected_sha256'], 'historical_image_hash')
    check(sum(p['segment_count'] for p in history['pages']) == len(transcribed) == 94, 'historical_94_segments')
    pack = load('three-page-input-audit.json')
    check(not pack['ready_for_external_request'] and not pack['native_conversion_target_created'], 'non_executable_input_audit')
    check(pack['common_rules']['body_layout_instructions'] == [], 'no_body_layout_instructions')
    complexity = load('complexity-selection.json')
    check([p['page_id'] for p in pack['pages']] == ['C2-S04', 'C2-S05', 'C2-S06'], 'new_complex_pages_replace_old_set')
    for index, p in enumerate(pack['pages']):
        current = complexity['pages'][index]
        check(p['page_id'] == current['page_id'] and p['title'] == current['title'] and p['page_order'] == index + 1, 'page_order_title_binding')
        check(p['current_confirmed_copy'] is None and p['current_selected_image_sha256'] is None and p['historical_target_image_sha256'] is None, 'current_gate_not_fabricated')
        source = sources[current['source_id']]
        page = next(p for p in source['pages'] if p['page_order'] == current['source_page_order'])
        check(source['sha256'] == current['source_sha256'] and page['part'] == current['slide_part'] and page['slide_xml_sha256'] == current['slide_xml_sha256'], 'complex_source_page_hash')
        observed = next(x for x in inspected[current['source_id']] if x['page_order'] == current['source_page_order'])
        expected = [{'shape_id':o['shape_id'], 'exact_xml_paragraphs':o['xml_paragraphs']} for o in observed['objects'] if o['xml_paragraphs']]
        check(expected == current['source_copy_excerpts'], 'complex_exact_source_copy')
        strings = [t for x in expected for t in x['exact_xml_paragraphs']]
        check(audit.json_sha(strings) == current['source_copy_array_sha256'] == p['candidate_copy']['source_copy_array_sha256'], 'complex_source_copy_hash')
        check(all(p['source_binding'][k] == current[k] for k in p['source_binding']), 'complex_input_source_binding')
        for m in current['media_candidates']:
            matches = [a for a in source['media'] if a['part'] == m['part'] and a['sha256'] == m['sha256']]
            check(len(matches) == 1, 'complex_media_hash')
        check(p['required_body_layout'] is None, 'complex_no_layout_commands')
    last = pack['pages'][2]
    check(last['excluded_media_sha256'] == ['0c19e88a931133dec1b3210f462eb2eccfa5cd762ad2cd5253b000e66bf41f2b'] and len(last['optional_real_material_sha256']) == 2, 'mislabelled_warehouse_photo_excluded')
    for record in load('source-render-evidence.json')['pages']:
        current = next(p for p in complexity['pages'] if p['page_id'] == record['page_id'])
        check(record['source_sha256'] == current['source_sha256'] and record['slide_xml_sha256'] == current['slide_xml_sha256'] and record['source_page_order'] == current['source_page_order'], 'render_source_identity')
        for kind in ('pdf', 'png'):
            check(audit.sha(Path(record[kind + '_path']).read_bytes()) == record[kind + '_sha256'], 'render_artifact_hash')
    baselines = [ROOT / n for n in ('00-唯一研发基线索引-v1.0.md', '01-产品需求基线-v1.0.md', '02-系统详细设计-v1.0.md', '03-UI设计与交互规范-v1.0.md')]
    for path in baselines + [HERE / 'README.md', HERE / 'complexity-selection.md']:
        text = path.read_text()
        for dest in re.findall(r'\]\(([^)]+)\)', text):
            dest = dest.strip('<>').split('#', 1)[0]
            if not dest or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', dest):
                continue
            resolved = path.parent / unquote(dest)
            check(resolved.exists(), 'markdown_file_links')
            if '产品代码/prototypes/' in dest:
                check(resolved.is_file(), 'baseline_prototype_files')
    artifacts = {p.name: audit.sha(p.read_bytes()) for p in HERE.iterdir()
                 if p.is_file() and p.name != 'verification.json'}
    return {'schema': 'c2-local-audit-verification-v1', 'status': 'PASS' if not ERRORS else 'FAIL',
            'checks': COUNTS, 'errors': ERRORS, 'artifact_sha256': artifacts,
            'source_files': 9, 'ordered_pptx_pages': 177, 'media_parts': 493,
            'proof_boundary': 'Source/copy/crop identity and document consistency only; no new Runtime, user acceptance, external generation, PowerPoint, G0 or G3 proof.'}


if __name__ == '__main__':
    receipt = verify()
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    raise SystemExit(bool(ERRORS))
