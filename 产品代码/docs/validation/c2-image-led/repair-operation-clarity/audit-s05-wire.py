"""Read exact immutable S05 artifacts and compile locally; never call a provider."""
from pathlib import Path
import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
import importlib.util
import json
import sys
from unittest.mock import patch

ROOT = Path('/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909')
OUT = Path('/private/tmp/c2-repair-operation-clarity')
CONTEXT = 'cb0c0f6e839c1aa087bc1c13cd5588f0bf484174b68eb91870849f7ecc69e980'
RESPONSE = '9632c094c0c6f36ac7a444234392f953b34ff0bca74a4f4c53029c7f6e8af132'
SOURCE = 'c1d97bf4aaa15e4b649dbc5f86f64f9febd9f1de826f6ae7417162c70c66a1ee'
DIAGNOSTIC = '095c39035719c3f7b9e683c73aecae9e0ba6859e3e69350b423da20ae0494ef7'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


identities = {}


def artifact(identity):
    p = ROOT / 'artifacts/objects' / identity[:2] / (identity + '.json')
    raw = p.read_bytes()
    value = json.loads(raw)
    assert sha(canonical(value)) == identity
    identities[identity] = sha(raw)
    return value['payload']


request = artifact(CONTEXT)['layers']['image_led_request']
response = artifact(RESPONSE)
source = artifact(SOURCE)
diagnostic = artifact(DIAGNOSTIC)
payload = request['payload']
assert request['request_id'] == response['request_id'] == 'c2-repair-C2-S05-20260911-v5'
assert sha(canonical(payload)) == request['payload_sha256'] == response['payload_sha256']
assert request['repair_diagnostic_ref'] == response['repair_diagnostic_ref'] == 'artifact://image-led-content-diagnostic/' + DIAGNOSTIC
assert request['source_generation_response_ref'] == response['source_generation_response_ref'] == 'artifact://image-led-generation-response/' + SOURCE
target = payload['edit_target']
source_raw = base64.b64decode(source['image_base64'], validate=True)
assert base64.b64decode(target['data_base64'], validate=True) == source_raw
assert sha(source_raw) == target['image_sha256'] == source['image_sha256'] == diagnostic['image_sha256']
assert [target['width'], target['height']] == source['image_size'] == diagnostic['image_size'] == [1672, 941]
assert payload['issues'] == [{k: v for k, v in i.items() if k != 'observed_text'} for i in diagnostic['issues']]
assert sha(canonical(payload['base_payload'])) == source['payload_sha256'] == diagnostic['source_payload_sha256']

wrapper_path = Path(sys.argv[1])
label = sys.argv[2]
spec = importlib.util.spec_from_file_location('s05_offline_wrapper', wrapper_path)
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
envelope = {'protocol': 'image-led-image2-repair-transport/v1', 'request_id': request['request_id'], 'payload': payload}
original = deepcopy(envelope)
with patch.object(wrapper.subprocess, 'run', side_effect=AssertionError('no helper')), patch.object(wrapper.urllib.request, 'build_opener', side_effect=AssertionError('no HTTP')):
    url, mime, body = wrapper.compile_body(envelope)
assert envelope == original
parts = list(BytesParser(policy=default).parsebytes(('Content-Type: ' + mime + '\r\n\r\n').encode() + body).iter_parts())
images = [p for p in parts if p.get_filename()]
fields = {p.get_param('name', header='content-disposition'): p.get_payload(decode=True).decode() for p in parts if not p.get_filename()}
assert len(images) == 1 and images[0].get_payload(decode=True) == source_raw
assert url == wrapper.EDITS_URL
public = json.loads(fields['prompt'])
assert len(public['confirmed_visible_copy']['items']) == 36
assert payload['base_payload']['materials'] == [] and public['materials'] == []
original_copy = payload['base_payload']['confirmed_visible_copy']['items']
assert [i['text'] for i in public['confirmed_visible_copy']['items']] == [i['text'] for i in original_copy]
assert 'observed_text' not in fields['prompt']
assert diagnostic['excluded_content_check']['detail'] not in fields['prompt']
for i in diagnostic['issues']:
    assert i['observed_text'] not in json.dumps(public['repair_context'], ensure_ascii=False)
review = OUT.parent / 'c2-repair-feedback/S05-v5-independent-source-review.md'
result = {
    'status': 'offline-exact-context-compilation-verified',
    'evidence_boundary': 'Recompiled from exact immutable context and fixed wrapper; not a captured original HTTP multipart body or proof of model instruction compliance.',
    'request_id': request['request_id'], 'artifact_envelope_sha256': identities,
    'wrapper_path': str(wrapper_path), 'wrapper_sha256': sha(wrapper_path.read_bytes()),
    'payload_sha256': request['payload_sha256'], 'base_payload_sha256': source['payload_sha256'],
    'source_image_sha256': sha(source_raw), 'source_image_size': source['image_size'],
    'output_image_sha256': response['image_sha256'], 'provider_reported': response['provider_observation']['reported'],
    'request_fields': {k: v for k, v in fields.items() if k != 'prompt'},
    'endpoint': url, 'image_count': len(images), 'image1_exact': True,
    'copy_items': 36, 'visible_copy_exact': True, 'material_count': 0,
    'repair_context_position': list(public).index('repair_context'),
    'prompt_sha256': sha(fields['prompt'].encode()),
    'repair_context': public['repair_context'],
    'review_sha256': sha(review.read_bytes()),
    'unchanged_original_payload': envelope == original, 'http_or_helper': False, 'customer_runtime_write': False,
}
(OUT / (label + '-wire-audit.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
