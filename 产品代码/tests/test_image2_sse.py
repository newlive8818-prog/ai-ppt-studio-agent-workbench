"""Offline stream contract tests; never run the credential helper or HTTP."""
from __future__ import annotations

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
from io import BytesIO
import json
import os
import sys
import textwrap
import unittest
from unittest.mock import patch

from tests import test_image2_crs_provider as provider_fixture
from tests.test_image2_crs_provider import PNG, ROOT, SECRET, CUSTOMER, request, v2_request


def event(kind='image_generation.completed', **metadata):
    value = {'type': kind, **metadata}
    if kind.endswith(('.completed', '.partial_image')):
        value.setdefault('b64_json', base64.b64encode(PNG).decode())
    return b'data: ' + json.dumps(value, ensure_ascii=False).encode() + b'\n\n'


class Image2StreamTests(unittest.TestCase):
    setUp = provider_fixture.Image2CrsProviderTests.setUp
    invoke = provider_fixture.Image2CrsProviderTests.invoke
    assert_safe_failure = provider_fixture.Image2CrsProviderTests.assert_safe_failure

    def stream(self, raw):
        reader = BytesIO(raw)
        self.response.headers = {'Content-Type': 'text/event-stream; charset=utf-8'}
        self.response.readline.side_effect = reader.readline
        self.response.read.side_effect = AssertionError('SSE must use bounded reads')
        return reader

    def test_both_protocols_and_endpoints_add_only_stream_transport_fields(self):
        for protocol in (1, 2):
            for count in (0, 1, 2):
                for model in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
                    with self.subTest(protocol=protocol, count=count, model=model):
                        value = v2_request(model, count)
                        if protocol == 1:
                            materials = value['payload']['materials']
                            value = request()
                            value['payload'].update(model=model, materials=materials)
                        original = deepcopy(value)
                        url, mime, body = self.wrapper.compile_body(value, model=model)
                        if count:
                            parts = list(BytesParser(policy=default).parsebytes(
                                ('Content-Type: ' + mime + '\r\n\r\n').encode() + body).iter_parts())
                            fields = {p.get_param('name', header='content-disposition'):
                                p.get_payload(decode=True).decode() for p in parts if not p.get_filename()}
                            self.assertEqual([p.get_payload(decode=True) for p in parts if p.get_filename()],
                                [base64.b64decode(m['data_base64']) for m in original['payload']['materials']])
                            expected = {'stream': 'true', 'partial_images': '1'}
                        else:
                            fields = json.loads(body)
                            expected = {'stream': True, 'partial_images': 1}
                        self.assertEqual({k: fields[k] for k in ('stream', 'partial_images') if k in fields},
                                         expected if model == 'gpt-image-2' else {})
                        self.assertEqual(value, original)
                        prompt = json.loads(fields['prompt'])
                        self.assertEqual(prompt['common_rules'], original['payload']['common_rules'])
                        self.assertEqual(prompt['page_goal'], original['payload']['page_goal'])
                        self.assertIn(CUSTOMER, fields['prompt'].replace('\\n', '\n'))

    def test_comments_crlf_multiline_event_and_done_preserve_final_bytes_and_digest(self):
        raw = (b': heartbeat\r\n\r\n' + b'event: image_generation.completed\r\n'
               + b'data: {"type":"image_generation.completed",\r\n'
               + b'data: "b64_json":"' + base64.b64encode(PNG) + b'"}\r\n\r\n'
               + b'data: [DONE]\r\n\r\n')
        reader = self.stream(raw + event('error', error=SECRET))
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ''))
        reply = json.loads(out)
        self.assertEqual(base64.b64decode(reply['image_base64']), PNG)
        observation = reply['provider_observation']
        self.assertEqual(observation['response_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(reply['response_id'], 'local-response-sha256:' + hashlib.sha256(raw).hexdigest())
        self.assertEqual(observation['reported'], {'response': {}, 'image': {}})
        self.assertEqual(observation['model_match'], 'not-reported')
        self.assertFalse(observation['independent_engine_proof'])
        self.assertEqual(reader.tell(), len(raw), 'DONE ends reading before trailing data')
        self.assertTrue(all(c.args == (self.wrapper.SSE_MAX_LINE_BYTES + 1,)
                            for c in self.response.readline.call_args_list))
        self.opener.open.assert_called_once()
        self.assertEqual(self.opener.open.call_args.kwargs['timeout'], 300)
        self.assertEqual(self.opener.open.call_args.args[0].get_header('Accept'), 'text/event-stream')

    def test_crs_keepalive_before_completed_image_preserves_final_and_stream_digest(self):
        raw = event('keepalive') + event('image_generation.completed')
        self.stream(raw)
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ''))
        reply = json.loads(out)
        self.assertEqual(base64.b64decode(reply['image_base64']), PNG)
        self.assertEqual(reply['provider_observation']['response_sha256'], hashlib.sha256(raw).hexdigest())
        self.opener.open.assert_called_once()

    def test_observed_endpoint_event_families_are_bound_to_the_requested_endpoint(self):
        for count, family in ((0, 'image_generation'), (2, 'image_edit')):
            with self.subTest(count=count):
                self.opener.open.reset_mock()
                self.stream(event(family + '.partial_image', b64_json='not-a-final-image')
                            + event(family + '.completed'))
                self.assertEqual(self.invoke(v2_request('gpt-image-2', count))[0], 0)
                self.opener.open.assert_called_once()
                other = 'image_edit' if count == 0 else 'image_generation'
                self.stream(event(other + '.completed'))
                self.assert_safe_failure(self.invoke(v2_request('gpt-image-2', count)))

    def test_explicit_matching_metadata_is_preserved_without_engine_proof(self):
        for model in ('gpt-image-2', 'gpt-image-2-codex'):
            self.stream(event(model=model, quality='high', size='1672x941', output_format='png'))
            code, out, err = self.invoke()
            self.assertEqual((code, err), (0, ''))
            observation = json.loads(out)['provider_observation']
            self.assertEqual(observation['reported']['response'],
                {'model': model, 'quality': 'high', 'size': '1672x941', 'output_format': 'png'})
            self.assertEqual(observation['reported']['image'], {})
            self.assertEqual(observation['model_match'],
                             'exact' if model == 'gpt-image-2' else 'compatible-image2-codex')
            self.assertFalse(observation['independent_engine_proof'])

    def test_invalid_or_incomplete_streams_fail_safely_with_one_attempt(self):
        cases = [b'', b'data: [DONE]\n\n', event('image_generation.partial_image'),
                 event() + event(), event() + event('error', error=SECRET),
                 event() + event('image_generation.partial_image'),
                 event('unknown'), b'data: not-json\n\n', b'data: []\n\n',
                 b'data: {"type":"ping","type":"heartbeat"}\n\n',
                 b'data: \xff\n\n', b'data: {}\n\n', b'data: [DONE]',
                 event()[:-1], b'event: image_edit.completed\n' + event(),
                 b'event: image_generation.completed\n\n',
                 b'field: arbitrary\n\n', event(b64_json='@@'),
                 event(b64_json=base64.b64encode(b'not-png').decode()),
                 event(error={'message': SECRET + CUSTOMER}),
                 event(model='gpt-image-2', image={'model': 'other'}),
                 event(model='gpt-image-2', response={'model': 'other'})]
        for raw in cases:
            with self.subTest(raw_sha256=hashlib.sha256(raw).hexdigest()):
                self.opener.open.reset_mock(); self.auth.reset_mock()
                self.stream(raw)
                self.assert_safe_failure(self.invoke())
                self.opener.open.assert_called_once(); self.auth.assert_called_once()

    def test_each_event_rejects_wrong_or_malformed_explicit_model(self):
        for bad in ('other', 'gpt-image-2.5-sunburst', None, 3, {'model': SECRET}):
            for kind in ('image_generation.completed', 'image_generation.partial_image', 'ping'):
                with self.subTest(kind=kind, bad_type=type(bad).__name__):
                    self.stream(event(kind, model=bad) + (event() if not kind.endswith('.completed') else b''))
                    self.assert_safe_failure(self.invoke())

    def test_heartbeat_events_do_not_supply_or_forge_an_image(self):
        self.stream(b'event: ping\n\n' + event('heartbeat') + event())
        self.assertEqual(self.invoke()[0], 0)
        for raw in (event('ping'), event('ping', b64_json=base64.b64encode(PNG).decode()) + event()):
            self.stream(raw)
            self.assert_safe_failure(self.invoke())

    def test_sse_id_and_retry_are_ignored_without_retry_or_remote_identity(self):
        raw = b'id: provider-event-only\nretry: 1000\n' + event() + b'data: [DONE]\n\n'
        self.stream(raw)
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['response_id'],
                         'local-response-sha256:' + hashlib.sha256(raw).hexdigest())
        self.assertNotIn('provider-event-only', out)
        self.opener.open.assert_called_once()
        for invalid in (b'retry: -1\n', b'retry: 1.5\n', 'retry: １２\n'.encode(), b'id: a\x00b\n'):
            self.stream(invalid + event())
            self.assert_safe_failure(self.invoke())

    def test_line_event_total_and_event_count_are_bounded(self):
        cases = [('SSE_MAX_LINE_BYTES', 12, b':' + b'x' * 20 + b'\n\n' + event()),
                 ('SSE_MAX_EVENT_BYTES', 20, b'data: {"type":"ping",\ndata: "x":"value"}\n\n' + event()),
                 ('SSE_MAX_TOTAL_BYTES', 20, b':abc\n\n' * 8 + event()),
                 ('SSE_MAX_EVENTS', 2, event('ping') * 3 + event())]
        for name, limit, raw in cases:
            with self.subTest(bound=name), patch.object(self.wrapper, name, limit):
                self.stream(raw)
                self.assert_safe_failure(self.invoke())

    def test_socket_failure_does_not_retry_or_leak_and_restores_alarm(self):
        import signal
        handler = signal.getsignal(signal.SIGALRM)
        self.stream(event())
        self.response.readline.side_effect = TimeoutError(SECRET + CUSTOMER)
        result = self.invoke()
        self.assert_safe_failure(result)
        self.assertEqual(json.loads(result[1])['failure_diagnostic']['reason'], 'timeout')
        self.opener.open.assert_called_once()
        self.assertEqual(signal.getsignal(signal.SIGALRM), handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_active_alarm_is_not_overwritten_and_fails_before_auth(self):
        with patch.object(self.wrapper.signal, 'getitimer', return_value=(7.0, 0.0)), \
                patch.object(self.wrapper.signal, 'setitimer') as timer:
            self.assert_safe_failure(self.invoke())
        self.auth.assert_not_called(); self.opener.open.assert_not_called(); timer.assert_not_called()

    def test_success_restores_previous_signal_and_non_main_thread_fails_before_auth(self):
        import signal
        previous = signal.getsignal(signal.SIGALRM)
        self.stream(event())
        self.assertEqual(self.invoke()[0], 0)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.auth.reset_mock(); self.opener.open.reset_mock()
        with patch.object(self.wrapper.threading, 'current_thread', return_value=object()):
            self.assert_safe_failure(self.invoke())
        self.auth.assert_not_called(); self.opener.open.assert_not_called()

    def test_real_short_deadline_interrupts_blocked_read_and_restores_signal_in_subprocess(self):
        script = textwrap.dedent('''
            import base64, contextlib, importlib.util, io, json, signal, time
            from types import SimpleNamespace
            from tests.test_image2_crs_provider import WRAPPER, request
            spec = importlib.util.spec_from_file_location('offline_deadline_wrapper', WRAPPER)
            wrapper = importlib.util.module_from_spec(spec); spec.loader.exec_module(wrapper)
            wrapper.TRANSPORT_DEADLINE_SECONDS = 0.05
            opens = []
            class Response:
                status = 200
                headers = {'Content-Type': 'text/event-stream'}
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def readline(self, limit): time.sleep(5); return b''
            def open_once(*args, **kwargs): opens.append(1); return Response()
            wrapper.subprocess.run = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b'offline-key')
            wrapper.urllib.request.build_opener = lambda *args: SimpleNamespace(open=open_once)
            def original_handler(signum, frame): raise AssertionError('original handler must not fire')
            signal.signal(signal.SIGALRM, original_handler)
            wrapper.sys.stdin = io.StringIO(json.dumps(request()))
            out, err = io.StringIO(), io.StringIO()
            started = time.monotonic()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): code = wrapper.main([])
            assert code == 1 and len(opens) == 1
            assert time.monotonic() - started < 1.5
            assert json.loads(out.getvalue())['failure_diagnostic']['reason'] == 'deadline-exceeded'
            assert signal.getsignal(signal.SIGALRM) is original_handler
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
            assert 'offline-key' not in out.getvalue() + err.getvalue()
            print('deadline-interrupted-and-restored')
        ''')
        # The parent fixture patches subprocess.run for the helper; use the saved real runner.
        from tests.test_image2_crs_provider import REAL_RUN
        result = REAL_RUN([sys.executable, '-c', script], cwd=ROOT,
                          env={**os.environ, 'PYTHONPATH': 'src:.'}, capture_output=True,
                          text=True, timeout=8, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'deadline-interrupted-and-restored')


if __name__ == '__main__':
    unittest.main()
