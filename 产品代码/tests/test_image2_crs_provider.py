"""Offline CRS transport tests: all authentication and HTTP are synthetic."""
from __future__ import annotations

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'src/ai_ppt_studio/adapters/image2_crs.py'
PROTOCOL = 'image-led-image2-transport/v1'
PROBE = 'image-led-image2-preflight/v1'
PNG = b'\x89PNG\r\n\x1a\nsynthetic-image-bytes'
REAL_RUN = subprocess.run
SECRET = 'synthetic-credential-never-publish'
CUSTOMER = ' 合成客户专用文案\n保留  20% 原空格 '


def request():
    return {'protocol': PROTOCOL, 'request_id': 'design-A', 'payload': {
        'receiver': 'CRS', 'model': 'gpt-image-2',
        'confirmed_visible_copy': {'title': CUSTOMER, 'blocks': [
            {'block_id': 'internal-block', 'text': ' 第一段\n逐字  不变 ', 'identity': 'fact'}]},
        'page_goal': ' 让客户理解关系\n ',
        'common_rules': {'typography_tokens': {'title': 'Arial'}, 'color_tokens': {'primary': '#102030'},
                         'fallback_fonts': {'body': 'sans-serif'}, 'title_bar': ' 共同标题栏 ', 'background': ' 白色 '},
        'materials': []}}


def material(raw=PNG, mime='image/png', use='real-material'):
    return {'atom_id': 'internal-atom-'+hashlib.sha256(raw).hexdigest()[:8], 'type': 'image', 'use': use,
            'content_sha256': hashlib.sha256(raw).hexdigest(), 'data_base64': base64.b64encode(raw).decode(),
            'mime_type': mime, 'width': 32, 'height': 18}


def v2_request(model, count=0):
    """Pure synthetic transport input; no Runtime/grant acceptance is implied."""
    from ai_ppt_studio.domains.materials.image_input_v2 import RULES
    value = request()
    value['protocol'] = 'image-led-image2-transport/v2'
    payload = value['payload']
    payload.update(model=model, payload_version='image-led-image2-input/v2', required_atom_ids=[])
    payload['confirmed_visible_copy'] = {
        'copy_version': 'image-led-selected-copy/v2', 'title_item_id': 'heading', 'items': [
            {'item_id': 'heading', 'kind': 'text', 'role': 'title', 'text': CUSTOMER},
            {'item_id': 'body', 'kind': 'text', 'role': 'body', 'text': ' 第一段\n逐字  不变 '}]}
    payload['materials'] = [material(PNG + bytes([i])) for i in range(count)]
    payload['non_visible_semantics'] = {
        'context_version': 'image-led-semantic-context/v1', 'purpose': 'constraints-only-not-visible-copy',
        'relationship_summary': payload['page_goal'], 'rules': deepcopy(RULES),
        'copy_facts': [{'item_id': 'body', 'identity': '来源事实', 'limit_ids': ['limit']}],
        'limitations': [{'limit_id': 'limit', 'text': '不得推断已部署'}],
        'material_use': [{'material_id': item['atom_id'], 'image_number': i, 'use': item['use'],
            'presence': 'optional', 'purpose': '几何标记', 'identity': '来源事实',
            'limitations': ['不作为布局模板']} for i, item in enumerate(payload['materials'], 1)]}
    return value


class Image2CrsProviderTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WRAPPER.is_file(), 'The approved standalone CRS wrapper has not been implemented')
        spec = importlib.util.spec_from_file_location('synthetic_crs_wrapper', WRAPPER)
        self.wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.wrapper)
        self.raw_reply = json.dumps({'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode()
        self.response = Mock()
        self.response.__enter__ = Mock(return_value=self.response)
        self.response.__exit__ = Mock(return_value=False)
        self.response.read.return_value = self.raw_reply
        self.response.status = 200
        self.response.headers = {}
        self.opener = Mock()
        self.opener.open.return_value = self.response
        self.auth = self.enterContext(patch.object(self.wrapper.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=(SECRET+'\n').encode())))
        self.build = self.enterContext(patch.object(self.wrapper.urllib.request, 'build_opener', return_value=self.opener))

    def invoke(self, payload=None, argv=None, raw=None):
        out, err = StringIO(), StringIO()
        with patch.object(self.wrapper.sys, 'stdin', StringIO(raw if raw is not None else json.dumps(payload or request(), ensure_ascii=False))), patch.object(self.wrapper.sys, 'stdout', out), patch.object(self.wrapper.sys, 'stderr', err):
            code = self.wrapper.main([] if argv is None else argv)
        return code, out.getvalue(), err.getvalue()

    def assert_safe_failure(self, result):
        code, out, err = result
        self.assertNotEqual(code, 0)
        if out:
            from ai_ppt_studio.adapters.image2_diagnostics import validate_diagnostic
            safe = json.loads(out)
            self.assertEqual(set(safe), {'protocol', 'request_sha256', 'failure_diagnostic'})
            self.assertEqual(safe['protocol'], 'image-led-command-failure/v1')
            self.assertRegex(safe['request_sha256'], r'^[0-9a-f]{64}$')
            validate_diagnostic(safe['failure_diagnostic'])
            self.assertLessEqual(len(out.encode()), 2048)
        self.assertNotIn(SECRET, out + err)
        self.assertNotIn(CUSTOMER.strip(), out + err)
        self.assertNotIn('Authorization', out + err)
        self.assertNotIn('Traceback', out + err)
        self.assertLess(len(err), 120)

    def test_json_generation_preserves_copy_and_omits_internal_metadata(self):
        original = request()
        code, out, err = self.invoke(original)
        self.assertEqual((code, err), (0, ''))
        reply = json.loads(out)
        self.assertEqual(set(reply), {'protocol','request_id','receiver','model','response_id','image_base64','provider_observation'})
        self.assertEqual(reply['request_id'], original['request_id'])
        self.assertEqual(reply['receiver'], 'CRS')
        self.assertEqual(reply['model'], 'gpt-image-2')
        self.assertEqual(reply['protocol'], PROTOCOL)
        self.assertEqual(base64.b64decode(reply['image_base64']), PNG)
        self.assertEqual(reply['response_id'], 'local-response-sha256:' + hashlib.sha256(self.raw_reply).hexdigest())
        self.auth.assert_called_once()
        args, kwargs = self.auth.call_args
        self.assertEqual(args[0], ['/Applications/Codex API Client.app/Contents/Resources/crs-auth-helper'])
        self.assertEqual(kwargs['timeout'], 30)
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
        self.opener.open.assert_called_once()
        req = self.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, 'https://sub.523869.xyz/v1/images/generations')
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.get_header('Authorization'), 'Bearer '+SECRET)
        self.assertEqual(self.opener.open.call_args.kwargs['timeout'], 300)
        body = json.loads(req.data)
        self.assertEqual({k:v for k,v in body.items() if k != 'prompt'}, {'model':'gpt-image-2','n':1,'size':'2048x1152','quality':'high','output_format':'png','stream':True,'partial_images':1})
        prompt = json.loads(body['prompt'])
        self.assertEqual(prompt['confirmed_visible_copy'], {'title': CUSTOMER, 'blocks': [' 第一段\n逐字  不变 ']})
        self.assertEqual(prompt['page_goal'], original['payload']['page_goal'])
        self.assertEqual(prompt['common_rules'], original['payload']['common_rules'])
        for excluded in ('internal-block', 'identity', 'block_id', 'atom_id', 'content_sha256'):
            self.assertNotIn(excluded, body['prompt'])
        self.assertEqual(original, request(), 'serialization must not rewrite the compiler payload')

    def test_actual_json_and_multipart_requests_use_fixed_product_user_agent(self):
        for model in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
            for protocol in (PROTOCOL, 'image-led-image2-transport/v2'):
                for count in (0, 1, 2):
                    with self.subTest(model=model, protocol=protocol, images=count):
                        self.auth.reset_mock(); self.opener.open.reset_mock()
                        value = v2_request(model, count)
                        if protocol == PROTOCOL:
                            materials = value['payload']['materials']
                            value = request()
                            value['payload'].update(model=model, materials=materials)
                        argv = [] if model == 'gpt-image-2' else ['--model', model]
                        code, out, err = self.invoke(value, argv)
                        self.assertEqual((code, err), (0, ''))
                        self.auth.assert_called_once(); self.opener.open.assert_called_once()
                        sent = self.opener.open.call_args.args[0]
                        self.assertEqual(sent.get_header('User-agent'), 'AI-PPT-Studio/0.4.0')
                        self.assertEqual(sent.get_header('Authorization'), 'Bearer ' + SECRET)
                        self.assertEqual({key.lower() for key, _ in sent.header_items()},
                                         {'content-type', 'authorization', 'user-agent'}
                                         | ({'accept'} if model == 'gpt-image-2' else set()))
                        self.assertEqual(sent.full_url, self.wrapper.EDITS_URL if count else self.wrapper.GENERATIONS_URL)
                        self.assertEqual(sent.get_method(), 'POST')
                        self.assertEqual(json.loads(out)['model'], model)

    def test_product_header_cannot_be_overridden_by_payload_or_environment(self):
        with patch.dict(os.environ, {'AI_PPT_IMAGE2_USER_AGENT': 'arbitrary-agent',
                                    'AI_PPT_IMAGE2_HEADERS': '{"User-Agent":"arbitrary-agent"}'}):
            self.assertEqual(self.invoke()[0], 0)
        self.assertEqual(self.opener.open.call_args.args[0].get_header('User-agent'), 'AI-PPT-Studio/0.4.0')
        self.auth.reset_mock(); self.opener.open.reset_mock()
        for key, content in (('headers', {'User-Agent': 'arbitrary-agent'}), ('user_agent', 'arbitrary-agent')):
            for v2 in (False, True):
                value = v2_request('gpt-image-2') if v2 else request()
                value['payload'][key] = content
                self.assert_safe_failure(self.invoke(value))
        self.auth.assert_not_called(); self.opener.open.assert_not_called()

    def test_one_and_multiple_images_keep_order_use_and_original_bytes(self):
        text_material = {'atom_id':'text-internal','type':'text','use':'content-source',
                         'content_sha256':'b'*64,'text':' 材料\n第二行  '}
        images = [material(), material(b'\xff\xd8\xffjpeg-original','image/jpeg','style-reference'),
                  material(b'RIFF\x12\x00\x00\x00WEBPwebp-original','image/webp')]
        for count in (1, 3):
            with self.subTest(count=count):
                self.auth.reset_mock(); self.opener.open.reset_mock()
                value = request(); value['payload']['materials'] = [images[0], text_material, *images[1:count]]
                self.assertEqual(self.invoke(value)[0], 0)
                req = self.opener.open.call_args.args[0]
                self.assertEqual(req.full_url, 'https://sub.523869.xyz/v1/images/edits')
                msg = BytesParser(policy=default).parsebytes(('Content-Type: '+req.get_header('Content-type')+'\r\n\r\n').encode()+req.data)
                parts = list(msg.iter_parts())
                files = [p for p in parts if p.get_filename()]
                self.assertEqual(len(files), count)
                self.assertEqual([p.get_param('name', header='content-disposition') for p in files], ['image' if count==1 else 'image[]']*count)
                self.assertEqual([p.get_payload(decode=True) for p in files], [base64.b64decode(i['data_base64']) for i in images[:count]])
                self.assertEqual([p.get_content_type() for p in files], [i['mime_type'] for i in images[:count]])
                fields = {p.get_param('name',header='content-disposition'):p.get_payload(decode=True).decode() for p in parts if not p.get_filename()}
                prompt = json.loads(fields.pop('prompt'))
                self.assertEqual(fields, {'model':'gpt-image-2','n':'1','size':'2048x1152','quality':'high','output_format':'png','stream':'true','partial_images':'1'})
                self.assertEqual(prompt['materials'][1], {'type':'text','use':'content-source','text':text_material['text']})
                self.assertEqual(prompt['materials'][0], {'type':'image','use':'real-material','image_number':1})
                if count>1:
                    self.assertEqual(prompt['materials'][2], {'type':'image','use':'style-reference','image_number':2})
                self.auth.assert_called_once(); self.opener.open.assert_called_once()

    def test_closed_schema_invalid_types_destinations_and_images_fail_before_auth(self):
        cases = []
        for field, bad in [('receiver','https://evil.invalid'),('model','other'),('endpoint','https://evil.invalid'),
                           ('page_goal',False),('common_rules',[]),('materials',{}),('confirmed_visible_copy',[] )]:
            value=request(); value['payload'][field]=bad; cases.append(value)
        for field,bad in [('protocol','other'),('request_id',False),('argv',['evil']),('payload',None)]:
            value=request(); value[field]=bad; cases.append(value)
        for field,bad in [('data_base64','@@'),('data_base64',''),('data_base64',True),('mime_type','image/gif'),
                           ('mime_type','image/jpeg'),('path','/tmp/customer.png'),('width',True),('height',0),
                           ('use','external-url'),('atom_id',1),('content_sha256','invalid')]:
            value=request(); item=material(); item[field]=bad; value['payload']['materials']=[item]; cases.append(value)
        value=request(); value['payload']['confirmed_visible_copy']['blocks'][0]['path']='/tmp/private'; cases.append(value)
        value=request(); value['payload']['common_rules']['background']=False; cases.append(value)
        value=request(); value['payload']['common_rules']['typography_tokens']={'body':2}; cases.append(value)
        value=request(); value['payload']['materials']=[{'type':'text','use':'content-source','atom_id':'a','content_sha256':'a'*64,'text':True}]; cases.append(value)
        for value in cases:
            with self.subTest(index=cases.index(value)):
                self.assert_safe_failure(self.invoke(value))
        for raw in ('not JSON '+CUSTOMER, '{"protocol":"a","protocol":"b"}', '[]'):
            self.assert_safe_failure(self.invoke(raw=raw))
        self.auth.assert_not_called(); self.build.assert_not_called(); self.opener.open.assert_not_called()

    def test_helper_errors_and_timeouts_have_no_http_or_leaked_diagnostics(self):
        for error in (OSError(SECRET+CUSTOMER), subprocess.TimeoutExpired('helper',30, output=SECRET.encode()),
                      None):
            self.auth.reset_mock()
            self.auth.side_effect=error
            self.auth.return_value=SimpleNamespace(returncode=7, stdout=(SECRET+CUSTOMER).encode())
            self.assert_safe_failure(self.invoke())
            self.auth.assert_called_once()
            self.opener.open.assert_not_called()
        self.auth.side_effect=None
        self.auth.return_value=SimpleNamespace(returncode=0,stdout=b' \n')
        self.assert_safe_failure(self.invoke())
        self.opener.open.assert_not_called()

    def test_http_error_redirect_timeout_and_malformed_response_never_retry(self):
        for failure in (urllib.error.HTTPError('https://unused.invalid',500,SECRET,{},None),
                        urllib.error.HTTPError('https://unused.invalid',302,SECRET,{'Location':'https://evil.invalid'},None),
                        TimeoutError(SECRET+CUSTOMER), OSError(SECRET+CUSTOMER)):
            self.auth.reset_mock(); self.opener.open.reset_mock(); self.opener.open.side_effect=failure
            self.assert_safe_failure(self.invoke())
            self.auth.assert_called_once(); self.opener.open.assert_called_once()
        self.opener.open.side_effect=None
        cases=[b'not JSON '+SECRET.encode(), b'{}', b'{"data":[]}', b'{"data":[{},{}]}', b'{"data":[{}]}',
               b'{"data":[{"url":"https://evil.invalid/image"}]}', b'{"data":[{"b64_json":""}]}',
               b'{"data":[{"b64_json":"@@"}]}', b'{"data":[{"b64_json":true}]}',
               json.dumps({'data':[{'b64_json':base64.b64encode(b'not-png').decode()}]}).encode()]
        for raw in cases:
            self.auth.reset_mock(); self.opener.open.reset_mock(); self.response.read.return_value=raw
            self.assert_safe_failure(self.invoke())
            self.auth.assert_called_once(); self.opener.open.assert_called_once()
        self.response.read.return_value=self.raw_reply
        self.response.status=302
        self.assert_safe_failure(self.invoke())

    def test_provider_request_id_is_only_taken_from_received_header(self):
        self.response.headers={'x-request-id':'remote-request-123'}
        self.assertEqual(json.loads(self.invoke()[1])['response_id'],'remote-request-123')
        self.response.headers={'x-request-id':'unsafe\n'+SECRET}
        self.assertEqual(json.loads(self.invoke()[1])['response_id'],'local-response-sha256:'+hashlib.sha256(self.raw_reply).hexdigest())
        self.assertEqual(self.opener.open.call_count,2)

    def test_opener_disables_proxies_and_redirect_handler_refuses_every_redirect(self):
        self.invoke()
        handlers=self.build.call_args.args
        self.assertTrue(any(isinstance(h,self.wrapper.urllib.request.ProxyHandler) and h.proxies=={} for h in handlers))
        redirect=next(h for h in handlers if isinstance(h,self.wrapper.urllib.request.HTTPRedirectHandler))
        for status in (301,302,303,307,308):
            self.assertIsNone(redirect.redirect_request(None,None,status,'redirect',{},'https://evil.invalid'))

    def test_preflight_stat_only_and_strict_protocol_never_authenticates_or_requests(self):
        value={'protocol':PROBE,'request_id':'nonce-abc'}
        with patch.object(self.wrapper.os.path,'isfile',return_value=True), patch.object(self.wrapper.os,'access',return_value=False):
            code,out,err=self.invoke(value,['--preflight'])
        self.assertEqual((code,err),(0,''))
        self.assertEqual(json.loads(out), {'protocol':PROBE,'request_id':'nonce-abc','receiver':'CRS','model':'gpt-image-2','helper_executable':False,'external_connection':'not-tested'})
        for bad in ({**value,'extra':True},{**value,'protocol':PROTOCOL},{**value,'request_id':True}):
            self.assert_safe_failure(self.invoke(bad,['--preflight']))
        self.assert_safe_failure(self.invoke(value,['--other']))
        self.assert_safe_failure(self.invoke(value,['--preflight','extra']))
        self.auth.assert_not_called(); self.build.assert_not_called(); self.opener.open.assert_not_called()

    def test_wrapper_runs_standalone_from_unrelated_cwd_without_pythonpath(self):
        # This subprocess only takes the stat-only preflight branch.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            completed=REAL_RUN([sys.executable,str(WRAPPER),'--preflight'],
                input=json.dumps({'protocol':PROBE,'request_id':'standalone'}),text=True,capture_output=True,
                cwd=folder,env={'PYTHONDONTWRITEBYTECODE':'1'},timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['request_id'],'standalone')
        self.assertEqual(completed.stderr,'')

    def test_sunburst_exact_argv_sets_real_json_body_and_receipt_model(self):
        value = request()
        value['payload']['model'] = 'gpt-image-2.5-sunburst'
        code, out, err = self.invoke(value, ['--model', 'gpt-image-2.5-sunburst'])
        self.assertEqual((code, err), (0, ''))
        sent = self.opener.open.call_args.args[0]
        self.assertEqual(sent.full_url, self.wrapper.GENERATIONS_URL)
        body = json.loads(sent.data)
        self.assertEqual({k: v for k, v in body.items() if k != 'prompt'}, {
            'model': 'gpt-image-2.5-sunburst', 'n': 1, 'size': '2048x1152',
            'quality': 'high', 'output_format': 'png'})
        self.assertEqual(json.loads(body['prompt'])['confirmed_visible_copy']['title'], CUSTOMER)
        self.assertEqual(json.loads(out)['model'], body['model'])
        self.assertEqual(self.opener.open.call_count, 1)

    def test_sunburst_exact_argv_sets_real_two_image_multipart_model(self):
        value = request()
        value['payload']['model'] = 'gpt-image-2.5-sunburst'
        images = [material(PNG), material(PNG + b'-second')]
        value['payload']['materials'] = images
        code, out, err = self.invoke(value, ['--model', 'gpt-image-2.5-sunburst'])
        self.assertEqual((code, err), (0, ''))
        sent = self.opener.open.call_args.args[0]
        self.assertEqual(sent.full_url, self.wrapper.EDITS_URL)
        parsed = BytesParser(policy=default).parsebytes(
            ('Content-Type: ' + sent.headers['Content-type'] + '\r\n\r\n').encode() + sent.data)
        fields, actual_images = {}, []
        for part in parsed.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if name == 'image[]':
                actual_images.append(part.get_payload(decode=True))
            else:
                fields[name] = part.get_payload(decode=True).decode()
        self.assertEqual(fields['model'], 'gpt-image-2.5-sunburst')
        self.assertEqual(fields['size'], '2048x1152')
        self.assertEqual(fields['quality'], 'high')
        self.assertEqual(actual_images, [PNG, PNG + b'-second'])
        self.assertEqual(json.loads(out)['model'], fields['model'])
        self.assertEqual(self.opener.open.call_count, 1)

    def test_sunburst_standalone_preflight_preserves_closed_v1_and_v2(self):
        from tempfile import TemporaryDirectory
        for protocol in (PROBE, 'image-led-image2-preflight/v2'):
            value = {'protocol': protocol, 'request_id': 'sunburst-stat-only'}
            if protocol.endswith('/v2'):
                value['generation_protocol'] = 'image-led-image2-transport/v2'
            with self.subTest(protocol=protocol), TemporaryDirectory() as folder:
                completed = REAL_RUN([sys.executable, str(WRAPPER), '--model',
                    'gpt-image-2.5-sunburst', '--preflight'], input=json.dumps(value),
                    text=True, capture_output=True, cwd=folder,
                    env={'PYTHONDONTWRITEBYTECODE': '1'}, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                reply = json.loads(completed.stdout)
                self.assertEqual(reply['model'], 'gpt-image-2.5-sunburst')
                self.assertEqual(reply['protocol'], protocol)
                self.assertEqual(reply['request_id'], value['request_id'])
                self.assertEqual(reply['external_connection'], 'not-tested')
                self.assertEqual(set(reply), set(value) | {
                    'receiver', 'model', 'helper_executable', 'external_connection'})
        self.auth.assert_not_called()
        self.opener.open.assert_not_called()

    def test_both_models_v2_zero_one_two_image_actual_body_and_semantic_identity(self):
        for model in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
            for count in (0, 1, 2):
                with self.subTest(model=model, count=count):
                    self.auth.reset_mock(); self.opener.open.reset_mock()
                    value = v2_request(model, count); original = deepcopy(value)
                    code, out, err = self.invoke(value, [] if model == 'gpt-image-2' else ['--model', model])
                    self.assertEqual((code, err), (0, ''))
                    sent = self.opener.open.call_args.args[0]
                    actual_images = []
                    if count:
                        self.assertEqual(sent.full_url, self.wrapper.EDITS_URL)
                        parsed = BytesParser(policy=default).parsebytes(
                            ('Content-Type: ' + sent.headers['Content-type'] + '\r\n\r\n').encode() + sent.data)
                        fields = {}
                        for part in parsed.iter_parts():
                            name = part.get_param('name', header='content-disposition')
                            raw = part.get_payload(decode=True)
                            if part.get_filename():
                                self.assertEqual(name, 'image' if count == 1 else 'image[]')
                                self.assertEqual(part.get_content_type(), 'image/png')
                                actual_images.append(raw)
                            else:
                                fields[name] = raw.decode()
                        self.assertEqual(fields['n'], '1')
                    else:
                        self.assertEqual(sent.full_url, self.wrapper.GENERATIONS_URL)
                        fields = json.loads(sent.data)
                        self.assertEqual(fields['n'], 1)
                    self.assertEqual(actual_images, [PNG + bytes([i]) for i in range(count)])
                    self.assertEqual({k: fields[k] for k in ('model', 'size', 'quality', 'output_format')},
                        {'model': model, 'size': '2048x1152', 'quality': 'high', 'output_format': 'png'})
                    prompt = json.loads(fields['prompt'])
                    copy = prompt['confirmed_visible_copy']
                    self.assertEqual([i['text'] for i in copy['items']],
                        [i['text'] for i in original['payload']['confirmed_visible_copy']['items']])
                    self.assertEqual(copy['title_item_id'], copy['items'][0]['item_id'])
                    self.assertEqual(prompt['non_visible_semantics']['copy_facts'][0]['item_id'], copy['items'][1]['item_id'])
                    self.assertEqual([r['material_id'] for r in prompt['non_visible_semantics']['material_use']],
                        [r['material_id'] for r in prompt['materials']])
                    self.assertEqual(prompt['common_rules'], original['payload']['common_rules'])
                    self.assertEqual(value, original)
                    self.assertEqual(json.loads(out)['model'], model)
                    self.auth.assert_called_once(); self.opener.open.assert_called_once()

    def test_invalid_model_argv_and_payload_are_rejected_before_helper_and_http(self):
        sun = 'gpt-image-2.5-sunburst'
        invalid_argv = [['--model'], ['--model', 'gpt-image-2'], ['--model', 'gpt-image-2.5-flare'],
            ['--model', 'gpt-image-2.5'], ['--model', 'unknown'], ['--model', sun, 'extra'],
            ['--preflight', '--model', sun], ['--model', sun, '--model', sun],
            ['--model=' + sun], ['--model', sun, '--preflight', 'extra']]
        for argv in invalid_argv:
            with self.subTest(argv=argv):
                self.assert_safe_failure(self.invoke(v2_request(sun), argv))
        for argv, model in (([], sun), (['--model', sun], 'gpt-image-2'),
                            (['--model', sun], 'gpt-image-2.5-flare'), ([], 'unknown')):
            self.assert_safe_failure(self.invoke(v2_request(model), argv))
        self.auth.assert_not_called(); self.opener.open.assert_not_called()

    def test_sunburst_rejects_broken_v2_identity_and_probe_schema_without_auth(self):
        sun = 'gpt-image-2.5-sunburst'
        for mutate in (lambda p: p.pop('payload_version'), lambda p: p.update(payload_version='image-led-image2-input/v3'),
                       lambda p: p['non_visible_semantics'].update(copy_facts=[]),
                       lambda p: p['non_visible_semantics']['material_use'][0].update(material_id='other'),
                       lambda p: p['confirmed_visible_copy'].update(title_item_id='unknown')):
            value = v2_request(sun, 1); mutate(value['payload'])
            self.assert_safe_failure(self.invoke(value, ['--model', sun]))
        for value in ({'protocol': PROBE, 'request_id': 'nonce', 'model': sun},
                      {'protocol': 'image-led-image2-preflight/v2', 'request_id': 'nonce'},
                      {'protocol': 'image-led-image2-preflight/v2', 'request_id': 'nonce', 'generation_protocol': PROTOCOL},
                      {'protocol': 'image-led-image2-preflight/v3', 'request_id': 'nonce'}):
            self.assert_safe_failure(self.invoke(value, ['--model', sun, '--preflight']))
        self.auth.assert_not_called(); self.opener.open.assert_not_called()

    def test_explicit_upstream_model_mismatch_rejects_after_one_http_send(self):
        for model in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
            for location in ('top', 'item'):
                for reported in (model, 'gpt-image-2.5-flare', None):
                    with self.subTest(model=model, location=location, reported=reported):
                        self.auth.reset_mock(); self.opener.open.reset_mock()
                        response = json.loads(self.raw_reply)
                        (response if location == 'top' else response['data'][0])['model'] = reported
                        self.response.read.return_value = json.dumps(response).encode()
                        result = self.invoke(v2_request(model), [] if model == 'gpt-image-2' else ['--model', model])
                        if reported == model:
                            self.assertEqual(result[0], 0)
                        else:
                            self.assert_safe_failure(result)
                        self.auth.assert_called_once(); self.opener.open.assert_called_once()

    def test_invalid_unicode_request_identity_fails_before_authentication(self):
        value = request()
        value['request_id'] = chr(0xD800)
        self.assert_safe_failure(self.invoke(value))
        self.auth.assert_not_called()
        self.opener.open.assert_not_called()

    def test_local_receipt_hashes_exact_http_bytes_and_never_response_body_id(self):
        self.response.read.return_value = b'  ' + self.raw_reply[:-1] + b', "id":"caller-looking-id"}\n'
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['response_id'], 'local-response-sha256:' +
                         hashlib.sha256(self.response.read.return_value).hexdigest())

    def test_synthetic_helper_timeout_terminates_and_reaps_the_direct_child(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            pid_path = Path(folder).resolve() / 'helper.pid'
            synthetic = ('import os,time\n' +
                         'open(' + repr(str(pid_path)) + ', "w").write(str(os.getpid()))\n' +
                         'print(' + repr(SECRET) + ', flush=True)\ntime.sleep(60)\n')
            # Replace only the executable at the fake-helper boundary; the real
            # helper is never run. Keep the production timeout argument check,
            # then shorten this synthetic child's kill-and-reap exercise.
            def short_timeout(command, **kwargs):
                self.assertEqual(command, [self.wrapper.HELPER])
                self.assertEqual(kwargs['timeout'], 30)
                return REAL_RUN([sys.executable, '-c', synthetic], **{**kwargs, 'timeout': 2})
            self.auth.side_effect = short_timeout
            self.assert_safe_failure(self.invoke())
            self.auth.assert_called_once()
            self.build.assert_not_called()
            self.opener.open.assert_not_called()
            pid = int(pid_path.read_text())
            with self.assertRaises(ChildProcessError):
                os.waitpid(pid, os.WNOHANG)
