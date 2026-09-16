"""Standalone, standard-library-only CRS Image 2 single-attempt transport.

The compiler owns source authorization and full input-image decoding. This
boundary validates the closed transport schema and image headers, sends one
request, and emits one safe receipt. The Runtime owns unknown recovery and final
Pillow decoding. A local-response-sha256 receipt is not remote idempotency proof.
"""
from __future__ import annotations

import sys

# In particular the stat-only branch must not create bytecode files.
sys.dont_write_bytecode = True

import base64
from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
import re
import signal
import ssl
import subprocess
import threading
import urllib.error
import urllib.request
import uuid

PROTOCOL = 'image-led-image2-transport/v1'
PREFLIGHT_PROTOCOL = 'image-led-image2-preflight/v1'
RECEIVER = 'CRS'
MODEL = 'gpt-image-2'
SUNBURST_MODEL = 'gpt-image-2.5-sunburst'
USER_AGENT = 'AI-PPT-Studio/0.4.0'
HELPER = '/Applications/Codex API Client.app/Contents/Resources/crs-auth-helper'
GENERATIONS_URL = 'https://sub.523869.xyz/v1/images/generations'
EDITS_URL = 'https://sub.523869.xyz/v1/images/edits'
PNG_HEADER = b'\x89PNG\r\n\x1a\n'
TRANSPORT_DEADLINE_SECONDS = 900
SSE_MAX_LINE_BYTES = 32 * 1024 * 1024
SSE_MAX_EVENT_BYTES = 32 * 1024 * 1024
SSE_MAX_TOTAL_BYTES = 96 * 1024 * 1024
SSE_MAX_EVENTS = 256


class InvalidTransport(ValueError):
    """Details deliberately never contain caller, helper or provider content."""


class ProviderDecodeFailure(InvalidTransport):
    def __init__(self, reason):
        self.reason = reason
        super().__init__()


class TransportDeadlineExceeded(TimeoutError):
    """Only our process deadline; distinct from provider/socket timeouts."""


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise InvalidTransport()
    return value


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise InvalidTransport()
    value.encode('utf-8')  # Reject lone surrogates before authentication/HTTP.
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InvalidTransport()
        value[key] = item
    return value


def load_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def image_bytes(encoded, mime):
    text(encoded)
    raw = base64.b64decode(encoded, validate=True)
    valid = {
        'image/png': raw.startswith(PNG_HEADER),
        'image/jpeg': raw.startswith(b'\xff\xd8\xff'),
        'image/webp': raw.startswith(b'RIFF') and raw[8:12] == b'WEBP',
    }
    if not isinstance(mime, str) or not valid.get(mime, False):
        raise InvalidTransport()
    return raw


def compile_body(envelope, *, model=MODEL):
    """Validate all local input before helper/HTTP; serialize only approved text."""
    if model not in (MODEL, SUNBURST_MODEL):
        raise InvalidTransport()
    exact(envelope, {'protocol', 'request_id', 'payload'})
    repair = envelope['protocol'] == 'image-led-image2-repair-transport/v1'
    repair_payload = None
    if repair:
        if not __package__:
            from pathlib import Path
            source_root = str(Path(__file__).resolve().parents[2])
            if source_root not in sys.path:
                sys.path.insert(0, source_root)
        from ai_ppt_studio.domains.visual.image_repair import validate_repair_payload
        repair_payload = validate_repair_payload(envelope['payload'])
        envelope = {**envelope, 'payload': repair_payload['base_payload']}
    v2 = repair or envelope['protocol'] == 'image-led-image2-transport/v2'
    if not v2 and envelope['protocol'] != PROTOCOL:
        raise InvalidTransport()
    text(envelope['request_id'])
    fields = {'receiver', 'model', 'confirmed_visible_copy', 'page_goal', 'common_rules', 'materials'}
    payload = exact(envelope['payload'], fields | ({'payload_version','required_atom_ids','non_visible_semantics'} if v2 else set()))
    if payload['receiver'] != RECEIVER or payload['model'] != model:
        raise InvalidTransport()
    if v2:
        copy, semantics, material_aliases = _v2_projection(payload)
    else:
        copy = exact(payload['confirmed_visible_copy'], {'title', 'blocks'})
        text(copy['title'])
        if not isinstance(copy['blocks'], list):
            raise InvalidTransport()
        blocks, seen = [], set()
        for block in copy['blocks']:
            exact(block, {'block_id', 'text', 'identity'})
            for key in block:
                text(block[key])
            if block['block_id'] in seen:
                raise InvalidTransport()
            seen.add(block['block_id'])
            blocks.append(block['text'])
    text(payload['page_goal'])
    rules = exact(payload['common_rules'], {'typography_tokens', 'color_tokens',
                                          'fallback_fonts', 'title_bar', 'background'})
    for key in ('typography_tokens', 'color_tokens', 'fallback_fonts'):
        if not isinstance(rules[key], dict) or not rules[key]:
            raise InvalidTransport()
        for token, value in rules[key].items():
            text(token)
            text(value)
    text(rules['title_bar'])
    text(rules['background'])
    if not isinstance(payload['materials'], list):
        raise InvalidTransport()
    materials, images, seen = [], [], set()
    if repair_payload is not None:
        target = repair_payload['edit_target']
        images.append((image_bytes(target['data_base64'], target['mime_type']), target['mime_type']))
        for material in semantics['material_use']:
            if material['image_number'] is not None:
                material['image_number'] += 1
    for item in payload['materials']:
        if not isinstance(item, dict) or item.get('type') not in ('text', 'image'):
            raise InvalidTransport()
        fields = {'atom_id', 'type', 'use', 'content_sha256'}
        fields |= {'text'} if item['type'] == 'text' else {'data_base64', 'mime_type', 'width', 'height'}
        exact(item, fields)
        text(item['atom_id'])
        if item['atom_id'] in seen or item['use'] not in ('content-source', 'real-material', 'style-reference'):
            raise InvalidTransport()
        seen.add(item['atom_id'])
        if not isinstance(item['content_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['content_sha256']):
            raise InvalidTransport()
        public = {'type': item['type'], 'use': item['use']}
        if v2:
            public['material_id'] = material_aliases[item['atom_id']]
        if item['type'] == 'text':
            public['text'] = text(item['text'])
        else:
            for dimension in ('width', 'height'):
                if type(item[dimension]) is not int or item[dimension] < 1:
                    raise InvalidTransport()
            raw = image_bytes(item['data_base64'], item['mime_type'])
            images.append((raw, item['mime_type']))
            public['image_number'] = len(images)
        materials.append(public)
    # JSON preserves exact string values and sequence. There is deliberately no
    # C1 prompt, layout template, content rewriting or internal source identity.
    public_payload = {'confirmed_visible_copy': copy if v2 else {'title': copy['title'], 'blocks': blocks},
                      'page_goal': payload['page_goal'], 'common_rules': rules, 'materials': materials}
    # Fixed product instructions, outside the authorized customer input. These
    # govern content fidelity and shared chrome, never the page's body layout.
    # Free-form task instructions are deliberately not an external input channel.
    public_payload['system_output_requirements'] = {
        'version': 'image-led-system-output/v2', 'canvas': {'aspect_ratio': '16:9'},
        'visible_copy': (
            'confirmed_visible_copy 是本页可见文案的唯一指定清单。逐项完整呈现每个条目的原文，'
            '每个条目仅呈现一次；不同 item_id 即使文字相同也各自保留，严格遵循清单的显式重复次数。'
            '不得遗漏、概括、改写、翻译或截断；保留原始 Unicode 字符、标点、引号、圈号、分隔符、'
            '数字、单位和字符顺序，不做字符正规化或把文字符号替换成另一种编号。'
            '不得新增清单之外的可见文字，包括标语、数字、页码、图表文字或装饰内标签；'
            '不得从已有句子摘取词语再额外显示为标签。旧格式的 title 和每个 blocks 条目分别保留。'),
        'title_bar': (
            '新格式 confirmed_visible_copy.title_item_id 引用的 role=title 条目才是本页标题，'
            '该引用不是额外的一份可见文案，不得重复渲染。旧格式使用 confirmed_visible_copy.title。'
            '按 common_rules.title_bar 把这个确切标题置于共同标题栏内，遵循同一标题字体、层级和配色；'
            '章节标签不能替代标题，也不能把真正标题移到栏外后用章节标签冒充共同标题。'),
        'non_visible_context': (
            'page_goal、non_visible_semantics、材料文字和用途说明、共同规范及本系统要求用于理解、'
            '约束与设计，不得作为新增可见文案。不得把字段名、item_id、material_id 或内部说明上版。'
            + ('素材池为可选，由你按用途决定是否采用。' if v2 else
               '旧格式的全部材料均须按各自用途使用；风格参考只承担风格用途，不要求原图上版。') +
            '采用真实素材时保留其原始内容与用途；真实素材内原有文字按授权角色保留，不属于新增文案。'
            '不从素材或风格参考提炼新的文字，'
            '不把风格参考中的口号、标签或布局当作本页要求。'),
        'design_freedom': (
            '由你承担整页视觉设计责任。将 common_rules 的字体、备用字体、配色、标题栏和背景'
            '共同规范落实到本页，保持整套一致。正文构图、布局、图形、比例、层次和装饰由你自主设计，'
            '本要求不指定正文列数、模板或坐标。可以自然折行和进行字体渲染，但不改变底层文字字符；'
            '可用无字图形表达关系，不新增有字标签或虚构数据。'),
        'self_check': (
            '输出前逐项核对指定文案是否存在遗漏、改写、新增、额外重复、标点或符号替换；'
            '核对标题身份与共同标题栏位置，并检查字体、配色和背景一致性。'
            '先在本次设计内纠正这些差异，再输出完整页面；这些自检要求不代替后续独立内容与设计审核。'),
    }
    if v2:
        public_payload.update(non_visible_semantics=semantics, required_material_ids=[])
    if repair_payload is not None:
        from ai_ppt_studio.domains.materials.image_input_v2 import aliases
        text_aliases, _ = aliases(payload['confirmed_visible_copy'], payload['materials'])
        issues = []
        for issue in repair_payload['issues']:
            public_issue = dict(issue)
            if 'item_id' in public_issue:
                public_issue['item_id'] = text_aliases[public_issue['item_id']]
            # Derive actions only from the validated closed operation. Local
            # observations and caller instructions never enter this channel.
            if 'bbox' in public_issue:
                x, y, width, height = public_issue['bbox']
                location = (f'第1张源图中左上角(x={x}, y={y})，'
                            f'宽{width}像素、高{height}像素的矩形区域')
            kind = public_issue['kind']
            if kind == 'missing-item':
                instruction = (f'补回 confirmed_visible_copy 中 item_id={public_issue["item_id"]} '
                               '对应的完整原条目；使用其完整原文，不改写或概括。')
            elif kind == 'replace-item':
                instruction = (f'将{location}中有误的文字替换为 confirmed_visible_copy 中 '
                               f'item_id={public_issue["item_id"]} 对应的完整原条目；保留其他原条目。')
            elif kind == 'remove-extra-text':
                instruction = (f'删除{location}内多余的这一次文字呈现。'
                               '该额外文字在修订后整页不再额外出现，不得挪到别处、换成其他标签或仅改色隐藏。'
                               '即使同词出现在 confirmed_visible_copy 中，也只删除此处的额外副本；'
                               '原图其他位置对应的完整原条目及清单中合法的同文不同项仍须保留，不作整词禁用。')
            else:  # The closed validator permits only common-rule here.
                instruction = (f'在{location}定位并纠正 common_rules.{public_issue["rule_key"]} '
                               '对应的共同规范差异；沿用该字段原值，不追加新规则。')
            public_issue['instruction'] = instruction
            issues.append(public_issue)
        repair_context = {
            'version': 'image-led-image2-repair-context/v1',
            'edit_target': {'role': 'edit-target', 'image_number': 1,
                            'width': target['width'], 'height': target['height']},
            'requirements': {
                'task': (f'本次是修订任务：第1张图片是确切源图，原始尺寸为{target["width"]}×{target["height"]}像素。'
                         '先读取并逐项落实 issues 中的修订指令，结合后附完整 confirmed_visible_copy 和 common_rules '
                         '核对后输出完整修订页面。后续图片仍按各自材料用途使用。'),
                'visible_copy': '所有指定文案仍只来自 confirmed_visible_copy。missing-item 补回原条目，replace-item 使用对应原条目完整原文；remove-extra-text 删除所定位额外文字。原图的额外标签不是新的指定文案或事实。',
                'issue_coordinates': ('bbox 的数组顺序为 [x, y, width, height]，单位是第1张源图的原始像素。'
                                      '原点(0,0)在左上角，x 向右、y 向下；后两项是宽度和高度，不是右下角坐标。'
                                      '坐标不按请求的输出 size 换算，也不是百分比，仅用于定位源图差异，不规定新图的布局或输出坐标。'
                                      '字段名、坐标数值、instruction 与本说明都不是可见文字。'),
                'common_rules': 'common-rule 只引用原 common_rules 的对应字段，不添加新字体、颜色、模板或布局要求。原规则未限定排他色板时，不把辅助色自动判为违规。',
                'design_freedom': '由 Image 2 负责整页设计，可按修正需要自主构图，沿用原共同规范；完整保留全部原文及材料用途，不要求可选材料全部上版。',
            },
            'issues': issues,
        }
        public_payload = {'repair_context': repair_context, **public_payload}
    prompt = json.dumps(public_payload, ensure_ascii=False)
    fields = {'model': model, 'n': 1, 'size': '2048x1152', 'quality': 'high',
              'output_format': 'png', 'prompt': prompt}
    if model == MODEL:
        fields.update(stream=True, partial_images=1)
    if not images:
        return GENERATIONS_URL, 'application/json', json.dumps(fields, ensure_ascii=False).encode('utf-8')
    boundary = 'image2-' + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        if type(value) is bool:
            value = 'true' if value else 'false'
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                       f'{value}\r\n').encode('utf-8'))
    field = 'image' if len(images) == 1 else 'image[]'
    extensions = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
    for number, (raw, mime) in enumerate(images, 1):
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                       f'filename="image-{number}.{extensions[mime]}"\r\nContent-Type: {mime}\r\n\r\n').encode('ascii'))
        chunks.extend((raw, b'\r\n'))
    chunks.append(f'--{boundary}--\r\n'.encode('ascii'))
    return EDITS_URL, 'multipart/form-data; boundary=' + boundary, b''.join(chunks)


def _v2_projection(payload):
    # The standalone bundled wrapper imports only this package's exact source.
    if not __package__:
        from pathlib import Path
        source_root = str(Path(__file__).resolve().parents[2])
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
    from ai_ppt_studio.domains.materials.image_input_v2 import (
        PAYLOAD_VERSION, COPY_VERSION, validate_semantics, public_projection)
    from ai_ppt_studio.domains.visual.image_led import validate_selected_copy
    try:
        if payload['payload_version'] != PAYLOAD_VERSION or payload['required_atom_ids'] != []:
            raise InvalidTransport()
        copy = validate_selected_copy(payload['confirmed_visible_copy'])
        if copy.get('copy_version') != COPY_VERSION:
            raise InvalidTransport()
        semantics = validate_semantics(payload['non_visible_semantics'], copy, payload['materials'])
        if semantics['relationship_summary'] != payload['page_goal']:
            raise InvalidTransport()
        return public_projection(copy, payload['materials'], semantics)
    except Exception:
        raise InvalidTransport() from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider_observation(value, item, raw_response, *, model, response_sha256=None):
    # The fixed standalone command uses only its own bundled stdlib contract.
    if not __package__:
        from pathlib import Path
        source_root = str(Path(__file__).resolve().parents[2])
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
    from datetime import datetime, timezone
    from ai_ppt_studio.domains.visual.image_output import (
        OBSERVATION_VERSION, REPORTED_FIELDS, model_match, validate_provider_observation)
    reported = {origin: {key: source[key] for key in REPORTED_FIELDS if key in source}
                for origin, source in (('response', value), ('image', item))}
    observation = {'version': OBSERVATION_VERSION, 'reported': reported,
        'model_match': model_match(reported, receiver=RECEIVER, model=model),
        'independent_engine_proof': False,
        'response_sha256': response_sha256 or hashlib.sha256(raw_response).hexdigest(),
        'observed_at_utc': datetime.now(timezone.utc).isoformat()}
    return validate_provider_observation(observation, receiver=RECEIVER, model=model)


def _decode_observation(value, item, raw_response, *, model, format_, response_sha256=None):
    try:
        return provider_observation(value, item, raw_response, model=model, response_sha256=response_sha256)
    except (ValueError, TypeError):
        allowed = (model, 'gpt-image-2-codex') if model == MODEL else (model,)
        invalid_model = any('model' in row and (type(row['model']) is not str
                            or row['model'] not in allowed) for row in (value, item))
        raise ProviderDecodeFailure(format_ + ('-model-invalid' if invalid_model else '-metadata-invalid')) from None


def _decode_png(encoded, *, format_):
    try:
        text(encoded)
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ProviderDecodeFailure(format_ + '-base64-invalid') from None
    if not raw.startswith(PNG_HEADER):
        raise ProviderDecodeFailure(format_ + '-png-header-invalid')
    return raw


@contextmanager
def _transport_deadline():
    # This is a standalone process contract. Refuse before authentication rather
    # than stealing an embedding application's timer or silently losing a bound.
    if (threading.current_thread() is not threading.main_thread()
            or not all(hasattr(signal, name) for name in ('SIGALRM', 'ITIMER_REAL', 'getitimer', 'setitimer'))
            or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0)):
        raise InvalidTransport()
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise TransportDeadlineExceeded()

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, TRANSPORT_DEADLINE_SECONDS)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _read_sse(response, *, url, model, progress):
    # Only the two endpoint/event families established by isolated probes. The
    # final event is flat; nested JSON-response/image envelopes are ambiguous.
    family = 'image_generation' if url == GENERATIONS_URL else 'image_edit'
    complete, partial = family + '.completed', family + '.partial_image'
    digest = hashlib.sha256()
    total = event_bytes = events = 0
    data, event_name = [], None
    final = None
    context = progress['decode_context']
    while True:
        progress['stage'] = 'response-read'
        line = response.readline(SSE_MAX_LINE_BYTES + 1)
        progress['stage'] = 'provider-decode'
        if not isinstance(line, bytes):
            raise ProviderDecodeFailure('sse-read-type-invalid')
        context['response_bytes_observed'] += len(line)
        if len(line) > SSE_MAX_LINE_BYTES:
            raise ProviderDecodeFailure('sse-line-limit')
        if not line:
            if event_bytes or data or event_name is not None:
                raise ProviderDecodeFailure('sse-incomplete-event')
            break
        total += len(line)
        event_bytes += len(line)
        if total > SSE_MAX_TOTAL_BYTES:
            raise ProviderDecodeFailure('sse-total-limit')
        if event_bytes > SSE_MAX_EVENT_BYTES:
            raise ProviderDecodeFailure('sse-event-limit')
        digest.update(line)
        if not line.endswith(b'\n'):
            raise ProviderDecodeFailure('sse-line-ending-invalid')
        row = line[:-1]
        if row.endswith(b'\r'):
            row = row[:-1]
        try:
            decoded = row.decode('utf-8')
        except UnicodeError:
            raise ProviderDecodeFailure('sse-utf8-invalid') from None
        if '\r' in decoded or '\x00' in decoded:
            raise ProviderDecodeFailure('sse-control-character')
        if not decoded:
            events += 1
            context['sse_blocks_seen'] = events
            if events > SSE_MAX_EVENTS:
                raise ProviderDecodeFailure('sse-block-limit')
            payload = '\n'.join(data)
            if payload == '[DONE]':
                if event_name is not None:
                    raise ProviderDecodeFailure('sse-done-with-event')
                break
            if data:
                try:
                    value = load_json(payload)
                except (ValueError, TypeError, RecursionError):
                    raise ProviderDecodeFailure('sse-json-invalid') from None
                if not isinstance(value, dict):
                    raise ProviderDecodeFailure('sse-event-shape-invalid')
                if 'error' in value:
                    raise ProviderDecodeFailure('sse-provider-error')
                if any(key in value for key in ('response', 'image', 'data')):
                    raise ProviderDecodeFailure('sse-event-envelope-unsupported')
                kind = value.get('type', event_name)
                if event_name is not None and kind != event_name:
                    raise ProviderDecodeFailure('sse-event-name-mismatch')
                if kind not in (complete, partial, 'ping', 'heartbeat'):
                    raise ProviderDecodeFailure('sse-event-type-unsupported')
                # Validate each explicit provider label, including partials and
                # heartbeats. Only the final's actual labels enter the receipt.
                _decode_observation(value, {}, b'', model=model, format_='sse')
                if kind == complete:
                    if final is not None:
                        raise ProviderDecodeFailure('sse-duplicate-final')
                    _decode_png(value.get('b64_json'), format_='sse')
                    final = value
                    context['sse_final_seen'] = True
                elif kind == partial:
                    if final is not None:
                        raise ProviderDecodeFailure('sse-partial-after-final')
                elif 'b64_json' in value:
                    raise ProviderDecodeFailure('sse-heartbeat-image')
            elif event_name is not None and event_name not in ('ping', 'heartbeat'):
                raise ProviderDecodeFailure('sse-empty-event-invalid')
            data, event_name, event_bytes = [], None, 0
        elif decoded.startswith(':'):
            continue
        else:
            field, separator, value = decoded.partition(':')
            if not separator or field not in ('data', 'event', 'id', 'retry'):
                raise ProviderDecodeFailure('sse-field-invalid')
            if value.startswith(' '):
                value = value[1:]
            if field in ('id', 'retry'):
                if field == 'retry' and not re.fullmatch(r'[0-9]+', value):
                    raise ProviderDecodeFailure('sse-retry-invalid')
                # Transport-only hints never become receipt identity, a saved
                # provider field, or permission for another HTTP attempt.
                continue
            elif field == 'data':
                data.append(value)
            else:
                if event_name is not None or not value:
                    raise ProviderDecodeFailure('sse-event-name-invalid')
                event_name = value
    if final is None:
        raise ProviderDecodeFailure('sse-final-missing')
    return final, digest.hexdigest()


def generate(envelope, *, model=MODEL, _progress=None):
    progress = {} if _progress is None else _progress
    progress.update(stage='compile', status=None)
    progress.pop('decode_context', None)
    url, content_type, body = compile_body(envelope, model=model)
    with _transport_deadline() if model == MODEL else nullcontext():
        return _generate(envelope, model=model, progress=progress,
                         url=url, content_type=content_type, body=body)


def _generate(envelope, *, model, progress, url, content_type, body):
    # subprocess.run kills and reaps its direct child on its existing 30s timeout.
    # Image 2 additionally has one 900s deadline spanning helper, HTTP and decode.
    progress['stage'] = 'credential-helper'
    helper = subprocess.run([HELPER], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=30, check=False)
    if helper.returncode != 0:
        raise InvalidTransport()
    key = helper.stdout.decode('utf-8').strip()
    if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise InvalidTransport()
    progress['stage'] = 'compile'
    req = urllib.request.Request(url, data=body, method='POST',
                                 headers={'Content-Type': content_type, 'Authorization': 'Bearer ' + key,
                                          'User-Agent': USER_AGENT,
                                          **({'Accept': 'text/event-stream'} if model == MODEL else {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    # Exactly one open; default TLS validation remains enabled. The timeout is
    # per blocking socket operation, not a 300-second total generation budget.
    progress['stage'] = 'http-open'
    try:
        response = opener.open(req, timeout=300)
    except urllib.error.HTTPError as error:
        # HTTPError owns a response body. Close it before the safe diagnostic
        # path so provider/error text cannot leak through ResourceWarning.
        error.close()
        raise
    progress.update(stage='response-read', status=response.status if type(response.status) is int and 100 <= response.status <= 599 else None)
    with response:
        if response.status != 200:
            raise InvalidTransport()
        remote_id = response.headers.get('x-request-id')
        response_type = response.headers.get('Content-Type', response.headers.get('content-type', ''))
        is_sse = isinstance(response_type, str) and response_type.split(';', 1)[0].strip().lower() == 'text/event-stream'
        use_sse = model == MODEL and is_sse
        format_ = 'sse' if use_sse else 'json'
        progress['decode_context'] = {'response_format': 'sse' if use_sse else 'json-fallback',
            'response_bytes_observed': 0, 'sse_blocks_seen': 0 if use_sse else None,
            'sse_final_seen': False if use_sse else None}
        if model == MODEL and is_sse:
            value, response_sha256 = _read_sse(response, url=url, model=model, progress=progress)
            item = value
            observation = _decode_observation(value, {}, b'', model=model, format_=format_, response_sha256=response_sha256)
        else:
            # Keep the existing JSON response contract, including model checks.
            raw_response = response.read()
            if isinstance(raw_response, bytes):
                progress['decode_context']['response_bytes_observed'] = len(raw_response)
            progress['stage'] = 'provider-decode'
            try:
                value = load_json(raw_response)
            except (ValueError, TypeError, RecursionError):
                raise ProviderDecodeFailure('json-parse-invalid') from None
            if not isinstance(value, dict) or not isinstance(value.get('data'), list) or len(value['data']) != 1:
                raise ProviderDecodeFailure('json-response-shape-invalid')
            item = value['data'][0]
            if not isinstance(item, dict):
                raise ProviderDecodeFailure('json-image-shape-invalid')
            observation = _decode_observation(value, item, raw_response, model=model, format_=format_)
            response_sha256 = observation['response_sha256']
    raw_image = _decode_png(item.get('b64_json'), format_=format_)
    # This checks only PNG header/base64; the Runtime still fully decodes it.
    if not isinstance(remote_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}', remote_id):
        remote_id = 'local-response-sha256:' + response_sha256
    return {'protocol': envelope['protocol'], 'receiver': RECEIVER, 'model': model,
            'request_id': envelope['request_id'], 'response_id': remote_id,
            'image_base64': base64.b64encode(raw_image).decode('ascii'),
            'provider_observation': observation}


def preflight(envelope, *, model=MODEL):
    if model not in (MODEL, SUNBURST_MODEL):
        raise InvalidTransport()
    v2 = envelope.get('protocol') == 'image-led-image2-preflight/v2'
    exact(envelope, {'protocol', 'request_id'} | ({'generation_protocol'} if v2 else set()))
    if v2 and envelope['generation_protocol'] not in ('image-led-image2-transport/v2', 'image-led-image2-repair-transport/v1'):
        raise InvalidTransport()
    if v2 and envelope['generation_protocol'] == 'image-led-image2-repair-transport/v1' and model != MODEL:
        raise InvalidTransport()
    if not v2 and envelope['protocol'] != PREFLIGHT_PROTOCOL:
        raise InvalidTransport()
    text(envelope['request_id'])
    return {'protocol': envelope['protocol'], 'request_id': envelope['request_id'],
            'receiver': RECEIVER, 'model': model,
            'helper_executable': os.path.isfile(HELPER) and os.access(HELPER, os.X_OK),
            'external_connection': 'not-tested',
            **({'generation_protocol': envelope['generation_protocol']} if v2 else {})}


def _failure_diagnostic(progress, error):
    # The same tiny package module is usable from a fresh standalone interpreter.
    if not __package__:
        from pathlib import Path
        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
    from ai_ppt_studio.adapters.image2_diagnostics import diagnostic
    stage, status = progress['stage'], progress.get('status')
    reasons = {'input': 'invalid-input', 'compile': 'compile-failed',
        'credential-helper': 'helper-failed', 'response-read': 'response-read-failed',
        'provider-decode': 'provider-decode-failed', 'wrapper-receipt': 'wrapper-receipt-failed'}
    reason = reasons.get(stage, 'unknown-failure')
    if (type(error) is TransportDeadlineExceeded or isinstance(error, urllib.error.URLError)
            and type(error.reason) is TransportDeadlineExceeded):
        reason = 'deadline-exceeded'
    elif stage == 'provider-decode' and type(error) is ProviderDecodeFailure:
        reason = error.reason
    elif stage == 'credential-helper' and isinstance(error, subprocess.TimeoutExpired):
        reason = 'helper-timeout'
    elif stage == 'http-open':
        if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
            reason, status = 'http-error', error.code
        else:
            underlying = error.reason if isinstance(error, urllib.error.URLError) else error
            if isinstance(underlying, ssl.SSLError):
                reason = 'tls-error'
            elif isinstance(underlying, TimeoutError):
                reason = 'timeout'
            elif isinstance(error, (urllib.error.URLError, OSError)):
                reason = 'connection-error'
    elif stage == 'response-read' and isinstance(error, TimeoutError):
        reason = 'timeout'
    return diagnostic(stage, reason, status=status,
        decode_context=progress.get('decode_context') if stage in {'response-read', 'provider-decode'} else None)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    progress = {'stage': 'input', 'status': None}
    request_bytes = None
    is_preflight = '--preflight' in argv
    try:
        if argv in ([], ['--preflight']):
            model = MODEL
        elif argv in (['--model', SUNBURST_MODEL], ['--model', SUNBURST_MODEL, '--preflight']):
            model = SUNBURST_MODEL
        else:
            raise InvalidTransport()
        # Binary pipes preserve the hash and avoid locale-dependent decoding.
        # StringIO remains supported for pure offline component tests.
        stream = getattr(sys.stdin, 'buffer', None)
        request_bytes = stream.read() if stream is not None else sys.stdin.read().encode('utf-8')
        envelope = load_json(request_bytes.decode('utf-8'))
        result = (preflight(envelope, model=model) if argv and argv[-1] == '--preflight'
                  else generate(envelope, model=model, _progress=progress))
        progress['stage'] = 'wrapper-receipt'
        encoded = json.dumps(result, ensure_ascii=False)
        sys.stdout.write(encoded + '\n')
    except Exception as error:
        if not is_preflight and request_bytes is not None:
            try:
                value = _failure_diagnostic(progress, error)
                from ai_ppt_studio.adapters.image2_diagnostics import encode_failure
                sys.stdout.write(encode_failure(request_bytes, value).decode('ascii'))
            except Exception:
                # No trustworthy envelope is still an unknown process outcome.
                pass
        # Never echo exception/response/header/helper output or customer content.
        sys.stderr.write('IMAGE2_CRS_SAFE_FAILURE\n')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
