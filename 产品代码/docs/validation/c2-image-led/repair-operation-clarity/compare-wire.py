"""Byte-for-byte ordinary wire and repair-only projection comparison, offline."""
from pathlib import Path
import hashlib
import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_image2_crs_provider import request, material, v2_request, PNG
from tests.test_image2_repair_transport import envelope, decoded_body

OUT = Path('/private/tmp/c2-repair-operation-clarity')
BASE = Path('/private/tmp/c2-native-exact-candidate-04319fcc-20260911/plugin-release/ai-ppt-studio')
CURRENT = Path.cwd()


def load(root, name):
    spec = importlib.util.spec_from_file_location(name, root / 'src/ai_ppt_studio/adapters/image2_crs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load(BASE, 'sealed_wrapper')
new = load(CURRENT, 'new_wrapper')
ordinary, repairs = [], []
with patch.object(new.uuid, 'uuid4', return_value=SimpleNamespace(hex='offline-comparison')), \
        patch.object(new.subprocess, 'run', side_effect=AssertionError('no helper')), \
        patch.object(new.urllib.request, 'build_opener', side_effect=AssertionError('no HTTP')):
    for model in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
        for protocol in (1, 2):
            for count in (0, 1, 2):
                value = v2_request(model, count) if protocol == 2 else request()
                if protocol == 1:
                    value['payload']['model'] = model
                    value['payload']['materials'] = [material(PNG + bytes([i])) for i in range(count)]
                a = old.compile_body(value, model=model)
                b = new.compile_body(value, model=model)
                assert a == b, (model, protocol, count)
                ordinary.append({'model': model, 'protocol': protocol, 'image_count': count,
                                 'wire_equal': True, 'body_sha256': hashlib.sha256(a[2]).hexdigest()})
    for count in (0, 1, 2):
        value = envelope(count)
        a = old.compile_body(value)
        b = new.compile_body(value)
        af, ai = decoded_body(a[1], a[2])
        bf, bi = decoded_body(b[1], b[2])
        ap, bp = json.loads(af.pop('prompt')), json.loads(bf.pop('prompt'))
        ar, br = ap.pop('repair_context'), bp.pop('repair_context')
        assert a[:2] == b[:2] and af == bf and ap == bp
        assert [p.as_bytes() for p in ai] == [p.as_bytes() for p in bi]
        assert [{k: v for k, v in i.items() if k != 'instruction'} for i in br['issues']] == ar['issues']
        assert ar['edit_target'] == br['edit_target']
        repairs.append({'original_material_image_count': count, 'unchanged_base_prompt': True,
                        'unchanged_fields_images_operations': True})
report = {'status': 'passed', 'base_plugin': str(BASE), 'ordinary_cases': ordinary,
          'repair_cases': repairs, 'http_or_helper': False}
(OUT / 'wire-equivalence.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'ordinary_wire_equal': len(ordinary), 'repair_only_changes': len(repairs)}))
