"""Independent offline counterexamples. All helper and HTTP calls are mocked."""
from pathlib import Path
from copy import deepcopy
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
import base64, hashlib, importlib.util, json, unittest, urllib.error

from tests.test_image2_crs_provider import v2_request
from ai_ppt_studio.adapters import image2_diagnostics as d

ROOT = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
OUT = Path('/private/tmp/c2-decode-diagnostics-independent')
WRAPPER = ROOT / '产品代码/src/ai_ppt_studio/adapters/image2_crs.py'
PNG = b'\x89PNG\r\n\x1a\nheader-only-independent-counterexample'
SECRET = 'independent-synthetic-secret-never-emit'

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def event(kind='image_generation.completed', **extra):
    value = {'type': kind, **extra}
    if kind.endswith('.completed'):
        value.setdefault('b64_json', base64.b64encode(PNG).decode())
    return b'data: ' + json.dumps(value).encode() + b'\n\n'

class Response(BytesIO):
    status = 200
    def __init__(self, raw, mime='text/event-stream', after=None):
        super().__init__(raw)
        self.headers = {'Content-Type': mime}
        self.after = after
        self.lines = 0
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def readline(self, size=-1):
        self.lines += 1
        raw = super().readline(size)
        if not raw and self.after is not None:
            raise self.after
        return raw

class IndependentDecodeReview(unittest.TestCase):
    def setUp(self):
        self.w = load(WRAPPER, 'independent_decode_wrapper')

    def invoke(self, response, *, wrapper=None, model='gpt-image-2', count=0, protocol=2):
        w = wrapper or self.w
        value = v2_request(model, count)
        if protocol == 1:
            from tests.test_image2_crs_provider import request
            materials = value['payload']['materials']
            value = request()
            value['payload'].update(model=model, materials=materials)
        request_bytes = json.dumps(value, ensure_ascii=False).encode()
        out, err = StringIO(), StringIO()
        opener = Mock()
        if isinstance(response, BaseException): opener.open.side_effect = response
        else: opener.open.return_value = response
        with patch.object(w.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=SECRET.encode())) as helper, \
             patch.object(w.urllib.request, 'build_opener', return_value=opener), \
             patch.object(w.sys, 'stdin', StringIO(request_bytes.decode())), \
             patch.object(w.sys, 'stdout', out), patch.object(w.sys, 'stderr', err):
            rc = w.main([] if model == 'gpt-image-2' else ['--model', model])
        self.assertEqual(helper.call_count, 1)
        self.assertEqual(opener.open.call_count, 1)
        output = out.getvalue()
        self.assertNotIn(SECRET, output + err.getvalue())
        if rc:
            self.assertLessEqual(len(output.encode()), 2048)
            self.assertNotIn(base64.b64encode(PNG).decode(), output)
            envelope = json.loads(output)
            self.assertEqual(envelope['request_sha256'], hashlib.sha256(request_bytes).hexdigest())
            self.assertEqual(envelope['protocol'], d.PROTOCOL)
            parsed = d.parse_failure(output.encode(), request_bytes, rc)
            self.assertEqual(parsed['subprocess_exit_code'], rc)
        return rc, json.loads(output), err.getvalue()

    def diagnostic(self, response, **kwargs):
        rc, reply, _ = self.invoke(response, **kwargs)
        self.assertEqual(rc, 1)
        return reply['failure_diagnostic']

    def test_utf8_failure_counts_only_returned_bytes(self):
        first = b'data: \xff\xfe\n'
        response = Response(first + event())
        diag = self.diagnostic(response)
        self.assertEqual(diag['reason'], 'sse-utf8-invalid')
        self.assertEqual(diag['decode_context'], {'response_format': 'sse',
            'response_bytes_observed': len(first), 'sse_blocks_seen': 0, 'sse_final_seen': False})
        self.assertEqual(response.tell(), len(first))

    def test_header_only_final_then_timeout_is_failure_with_final_observed(self):
        raw = event()
        response = Response(raw, after=TimeoutError(SECRET))
        diag = self.diagnostic(response)
        self.assertEqual((diag['stage'], diag['reason']), ('response-read', 'timeout'))
        self.assertEqual(diag['decode_context'], {'response_format': 'sse',
            'response_bytes_observed': len(raw), 'sse_blocks_seen': 1, 'sse_final_seen': True})

    def test_257th_empty_block_stops_without_reading_tail(self):
        response = Response(b'\n' * 257 + event())
        diag = self.diagnostic(response)
        self.assertEqual(diag['reason'], 'sse-block-limit')
        self.assertEqual(diag['decode_context'], {'response_format': 'sse',
            'response_bytes_observed': 257, 'sse_blocks_seen': 257, 'sse_final_seen': False})
        self.assertEqual((response.tell(), response.lines), (257, 257))

    def test_fallback_label_is_branch_selection_not_claim_of_json_format(self):
        raw = b'<html>synthetic-error</html>'
        diag = self.diagnostic(Response(raw, 'text/html'))
        self.assertEqual(diag['reason'], 'json-parse-invalid')
        self.assertEqual(diag['decode_context'], {'response_format': 'json-fallback',
            'response_bytes_observed': len(raw), 'sse_blocks_seen': None, 'sse_final_seen': None})
        diag = self.diagnostic(Response(event(), 'text/event-stream'), model='gpt-image-2.5-sunburst')
        self.assertEqual(diag['reason'], 'json-parse-invalid')
        self.assertEqual(diag['decode_context']['response_format'], 'json-fallback')

    def test_internal_deadline_identity_is_exact_and_urllib_wrapping_preserves_it(self):
        class ChildDeadline(self.w.TransportDeadlineExceeded): pass
        Spoof = type('TransportDeadlineExceeded', (TimeoutError,), {})
        for error, reason in [
            (self.w.TransportDeadlineExceeded(), 'deadline-exceeded'),
            (urllib.error.URLError(self.w.TransportDeadlineExceeded()), 'deadline-exceeded'),
            (TimeoutError(SECRET), 'timeout'),
            (urllib.error.URLError(TimeoutError(SECRET)), 'timeout'),
            (ChildDeadline(), 'timeout'),
            (urllib.error.URLError(ChildDeadline()), 'timeout'),
            (Spoof(SECRET), 'timeout'),
            (urllib.error.URLError(Spoof(SECRET)), 'timeout')]:
            with self.subTest(error=type(error).__name__, expected=reason):
                diag = self.diagnostic(error)
                self.assertEqual((diag['stage'], diag['reason']), ('http-open', reason))
                self.assertNotIn('decode_context', diag)
                self.assertIsNone(diag['http_status'])

    def test_internal_deadline_at_each_decode_point_is_not_malformed_input(self):
        raw_json = json.dumps({'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode()
        for format_ in ('sse', 'json-fallback'):
            for point in ('json', 'metadata', 'base64'):
                with self.subTest(format=format_, point=point):
                    raw = event() if format_ == 'sse' else raw_json
                    response = Response(raw, 'text/event-stream' if format_ == 'sse' else 'application/json')
                    expired = self.w.TransportDeadlineExceeded()
                    if point == 'json':
                        original = self.w.load_json
                        def decode(value):
                            if (format_ == 'sse' and isinstance(value, str) and value.startswith('{"type":')) or (format_ != 'sse' and isinstance(value, bytes)):
                                raise expired
                            return original(value)
                        replacement = patch.object(self.w, 'load_json', side_effect=decode)
                    elif point == 'metadata':
                        replacement = patch.object(self.w, 'provider_observation', side_effect=expired)
                    else:
                        replacement = patch.object(self.w.base64, 'b64decode', side_effect=expired)
                    with replacement:
                        diag = self.diagnostic(response)
                    self.assertEqual((diag['stage'], diag['reason']), ('provider-decode', 'deadline-exceeded'))
                    self.assertEqual(diag['decode_context']['response_bytes_observed'], len(raw))
                    self.assertEqual(diag['decode_context']['sse_final_seen'], False if format_ == 'sse' else None)

    def value(self):
        return d.diagnostic('provider-decode', 'sse-final-missing', status=200,
            decode_context={'response_format': 'sse', 'response_bytes_observed': 14,
                'sse_blocks_seen': 1, 'sse_final_seen': False})

    def test_closed_v2_rejects_untrusted_types_limits_status_and_format_mismatch(self):
        mutations = [
            lambda v: v.update(http_status=201), lambda v: v.update(http_status=None),
            lambda v: v.update(http_status=True), lambda v: v.update(http_attempted=1),
            lambda v: v.update(transport_state='before-send'), lambda v: v.update(stage='http-open'),
            lambda v: v.update(reason='json-parse-invalid'), lambda v: v.update(version=d.VERSION),
            lambda v: v.update(extra=SECRET), lambda v: v.pop('decode_context'),
            lambda v: v['decode_context'].update(extra=SECRET),
            lambda v: v['decode_context'].update(response_format='json-fallback'),
            lambda v: v['decode_context'].update(sse_blocks_seen=0, sse_final_seen=True)]
        for field, bad_values in {
            'response_bytes_observed': [True, False, -1, 2**53, 1.0, '1', None],
            'sse_blocks_seen': [True, -1, 258, 1.0, '1', None],
            'sse_final_seen': [0, 1, None, 'false']}.items():
            for bad in bad_values:
                mutations.append(lambda v, field=field, bad=bad: v['decode_context'].update({field: bad}))
        for index, mutate in enumerate(mutations):
            value = self.value(); mutate(value)
            with self.subTest(mutation=index), self.assertRaises(ValueError): d.validate_diagnostic(value)
        for count, blocks, final in [(0, 0, False), (2**53 - 1, 257, True)]:
            value = self.value(); value['decode_context'].update(response_bytes_observed=count,
                sse_blocks_seen=blocks, sse_final_seen=final)
            self.assertEqual(d.validate_diagnostic(value), value)
        value = d.diagnostic('provider-decode', 'json-parse-invalid', status=200,
            decode_context={'response_format': 'json-fallback', 'response_bytes_observed': 0,
                'sse_blocks_seen': None, 'sse_final_seen': None})
        for field in ('sse_blocks_seen', 'sse_final_seen'):
            bad = deepcopy(value); bad['decode_context'][field] = 0
            with self.assertRaises(ValueError): d.validate_diagnostic(bad)

    def test_outer_binding_exit_duplicate_keys_and_size_cannot_be_forged(self):
        request = b'{"independent":"request"}'
        raw = d.encode_failure(request, self.value())
        good = json.loads(raw)
        bad_hash = deepcopy(good); bad_hash['request_sha256'] = '0' * 64
        extra = deepcopy(good); extra['extra'] = SECRET
        exit_claim = deepcopy(good); exit_claim['failure_diagnostic']['subprocess_exit_code'] = 1
        duplicates = raw.replace(b'"http_status":200', b'"http_status":200,"http_status":200')
        for output, request_bytes, code in [
            (raw, request + b' ', 1), (raw, request, 0), (raw, request, True),
            (raw, request, 256), (raw, request, -256), (raw + b' ' * 2048, request, 1),
            (duplicates, request, 1),
            *[(json.dumps(v).encode(), request, 1) for v in (bad_hash, extra, exit_claim)]]:
            with self.subTest(code=code, size=len(output)), self.assertRaises(ValueError):
                d.parse_failure(output, request_bytes, code)
        for code in (-255, -9, 1, 255):
            self.assertEqual(d.parse_failure(raw, request, code), {**self.value(), 'subprocess_exit_code': code})
        legacy = d.diagnostic('provider-decode', 'provider-decode-failed', status=200)
        self.assertEqual(d.parse_failure(d.encode_failure(request, legacy), request, 1),
            {**legacy, 'subprocess_exit_code': 1})
        self.assertEqual(len(legacy), 7)

    def test_generate_clears_context_before_a_new_compile_failure(self):
        progress = {'stage': 'provider-decode', 'status': 200, 'decode_context': self.value()['decode_context']}
        with self.assertRaises(Exception): self.w.generate({}, _progress=progress)
        self.assertEqual(progress, {'stage': 'compile', 'status': None})

    def test_success_and_rejection_are_unchanged_from_prior_head(self):
        old = load(OUT / 'before-wrapper.py', 'prior_head_decode_wrapper')
        valid_json = json.dumps({'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode()
        sse_cases = [event(), b':hb\n\n' + event() + b'data: [DONE]\n\n',
            event() + b'data: [DONE]\n\n' + event('error', error='unread'),
            event('heartbeat') + event(), b'id: x\nretry: 100\n' + event(),
            b'', b'\n' * 257, b'data: [DONE]\n\n', event() + event(),
            event('error', error=SECRET), b'data: \xff\n\n', event()[:-1],
            b'data: {"type":"ping","type":"heartbeat"}\n\n',
            event(model='other'), event(quality=False), event(b64_json='@@'),
            event(b64_json=base64.b64encode(b'not-png').decode()),
            event() + event('image_generation.partial_image'), event('heartbeat', b64_json='x')]
        cases = [(raw, 'text/event-stream', 'gpt-image-2', 0) for raw in sse_cases]
        cases += [(raw, mime, model, 0) for model in ('gpt-image-2', 'gpt-image-2.5-sunburst')
            for mime in ('application/json', 'text/html') for raw in (valid_json, b'{bad', b'[]')]
        cases += [(event('image_edit.completed'), 'text/event-stream', 'gpt-image-2', 2),
            (event(), 'text/event-stream', 'gpt-image-2', 2),
            (valid_json, 'text/event-stream', 'gpt-image-2.5-sunburst', 0)]
        for protocol in (1, 2):
            for index, (raw, mime, model, count) in enumerate(cases):
                with self.subTest(protocol=protocol, case=index):
                    new_rc, new_value, _ = self.invoke(Response(raw, mime), model=model, count=count, protocol=protocol)
                    old_rc, old_value, _ = self.invoke(Response(raw, mime), wrapper=old, model=model, count=count, protocol=protocol)
                    self.assertEqual(new_rc, old_rc)
                    if not new_rc:
                        for value in (new_value, old_value): value['provider_observation'].pop('observed_at_utc')
                        self.assertEqual(new_value, old_value)

    def test_reviewed_source_hashes_stay_frozen(self):
        for relative, expected in json.loads((OUT / 'frozen-files.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
