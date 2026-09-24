"""Closed decode evidence from synthetic wire bytes; no provider calls."""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch

from tests import test_image2_crs_provider as provider
from tests import test_image2_sse as stream_fixtures
from tests.test_image2_sse import event
from tests import test_image2_failure_diagnostics as diagnostic_fixtures
from tests.test_image2_failure_diagnostics import safe_diagnostic


class DecodeReasonTests(unittest.TestCase):
    setUp = provider.Image2CrsProviderTests.setUp
    invoke = provider.Image2CrsProviderTests.invoke
    stream = stream_fixtures.Image2StreamTests.stream

    def failure(self, reason, response_format):
        code, out, err = self.invoke()
        self.assertEqual(code, 1)
        value = json.loads(out)['failure_diagnostic']
        self.assertEqual(value['reason'], reason)
        self.assertEqual(value['version'], 'image-led-failure-diagnostic/v2')
        self.assertEqual(value['http_status'], 200)
        self.assertEqual(value['transport_state'], 'response-received')
        self.assertEqual(value['decode_context']['response_format'], response_format)
        self.assertLessEqual(len(out.encode()), 2048)
        for forbidden in (provider.SECRET, provider.CUSTOMER.strip(), 'Traceback', 'b64_json'):
            self.assertNotIn(forbidden, out + err)
        self.opener.open.assert_called_once()
        return value

    def test_sse_rejections_identify_the_failed_condition_without_relaxing_acceptance(self):
        cases = [
            (b'', 'sse-final-missing'),
            (b'data: [DONE]\n\n', 'sse-final-missing'),
            (event()[:-1], 'sse-incomplete-event'),
            (b'data: {}', 'sse-line-ending-invalid'),
            (b'data: \xff\n', 'sse-utf8-invalid'),
            (b'id: a\x00b\n', 'sse-control-character'),
            (b'event: ping\ndata: [DONE]\n\n', 'sse-done-with-event'),
            (b'data: not-json\n\n', 'sse-json-invalid'),
            (b'data: {"type":"ping","type":"ping"}\n\n', 'sse-json-invalid'),
            (b'data: []\n\n', 'sse-event-shape-invalid'),
            (event('error', error=provider.SECRET), 'sse-provider-error'),
            (event(image={'secret': provider.SECRET}), 'sse-event-envelope-unsupported'),
            (b'event: image_edit.completed\n' + event(), 'sse-event-name-mismatch'),
            (event('provider.' + provider.SECRET), 'sse-event-type-unsupported'),
            (event() + event(), 'sse-duplicate-final'),
            (event() + event('image_generation.partial_image'), 'sse-partial-after-final'),
            (event('heartbeat', b64_json=provider.SECRET), 'sse-heartbeat-image'),
            (event('keepalive', b64_json=provider.SECRET), 'sse-heartbeat-image'),
            (b'event: image_generation.completed\n\n', 'sse-empty-event-invalid'),
            (b'unknown: private\n', 'sse-field-invalid'),
            (b'retry: -1\n', 'sse-retry-invalid'),
            (b'event: ping\nevent: ping\n', 'sse-event-name-invalid'),
            (event(model=provider.SECRET), 'sse-model-invalid'),
            (event(quality={'private': provider.SECRET}), 'sse-metadata-invalid'),
            (event(b64_json='@@' + provider.SECRET), 'sse-base64-invalid'),
            (event(b64_json=base64.b64encode(b'not-png').decode()), 'sse-png-header-invalid'),
        ]
        for raw, reason in cases:
            with self.subTest(reason=reason):
                self.opener.open.reset_mock()
                self.stream(raw)
                value = self.failure(reason, 'sse')
                self.assertLessEqual(value['decode_context']['response_bytes_observed'], len(raw))

    def test_final_seen_and_block_counts_distinguish_error_after_final(self):
        for prefix, blocks, final in ((b'', 1, False), (event(), 2, True)):
            self.opener.open.reset_mock()
            raw = prefix + event('error', error={'message': provider.SECRET})
            self.stream(raw)
            value = self.failure('sse-provider-error', 'sse')
            self.assertEqual(value['decode_context'], {'response_format': 'sse',
                'response_bytes_observed': len(raw), 'sse_blocks_seen': blocks, 'sse_final_seen': final})

    def test_stream_bounds_have_distinct_diagnostics(self):
        cases = [('SSE_MAX_LINE_BYTES', 4, b':12345\n', 'sse-line-limit'),
                 ('SSE_MAX_EVENT_BYTES', 4, b':12345\n', 'sse-event-limit'),
                 ('SSE_MAX_TOTAL_BYTES', 4, b':12345\n', 'sse-total-limit'),
                 ('SSE_MAX_EVENTS', 1, b':a\n\n:b\n\n', 'sse-block-limit')]
        for name, limit, raw, reason in cases:
            with self.subTest(reason=reason), patch.object(self.wrapper, name, limit):
                self.opener.open.reset_mock(); self.stream(raw)
                self.failure(reason, 'sse')
        self.opener.open.reset_mock(); self.stream(b'')
        self.response.readline.side_effect = lambda _: 'not-bytes'
        self.failure('sse-read-type-invalid', 'sse')

    def test_json_fallback_distinguishes_parse_shape_model_and_image_failures(self):
        png = base64.b64encode(provider.PNG).decode()
        cases = [(b'{bad', 'json-parse-invalid'), (b'[]', 'json-response-shape-invalid'),
                 (b'{"data":[1]}', 'json-image-shape-invalid'),
                 (json.dumps({'data':[{'b64_json':png}], 'model':provider.SECRET}).encode(), 'json-model-invalid'),
                 (json.dumps({'data':[{'b64_json':png}], 'quality':False}).encode(), 'json-metadata-invalid'),
                 (b'{"data":[{"b64_json":"@@"}]}', 'json-base64-invalid'),
                 (b'{"data":[{"b64_json":"eA=="}]}', 'json-png-header-invalid')]
        for raw, reason in cases:
            with self.subTest(reason=reason):
                self.opener.open.reset_mock(); self.response.headers = {}
                self.response.read.side_effect = None; self.response.read.return_value = raw
                value = self.failure(reason, 'json-fallback')
                self.assertEqual(value['decode_context'], {'response_format':'json-fallback',
                    'response_bytes_observed':len(raw),'sse_blocks_seen':None,'sse_final_seen':None})

    def test_deadline_during_decode_is_not_reported_as_malformed_provider_data(self):
        self.stream(event())
        original = self.wrapper.load_json
        def slow_decode(raw):
            if isinstance(raw, str):
                time.sleep(0.2)
            return original(raw)
        with patch.object(self.wrapper, 'load_json', side_effect=slow_decode), \
                patch.object(self.wrapper, 'TRANSPORT_DEADLINE_SECONDS', 0.02):
            value = self.failure('deadline-exceeded', 'sse')
        self.assertEqual(value['stage'], 'provider-decode')
        self.assertFalse(value['decode_context']['sse_final_seen'])

    def test_deadline_wrapped_by_urlopen_is_still_our_deadline(self):
        self.opener.open.side_effect = urllib.error.URLError(self.wrapper.TransportDeadlineExceeded())
        code, out, err = self.invoke()
        self.assertEqual(code, 1)
        value = json.loads(out)['failure_diagnostic']
        self.assertEqual(value['reason'], 'deadline-exceeded')
        self.assertEqual(value['stage'], 'http-open')
        self.assertEqual(value['transport_state'], 'send-attempted')
        self.assertNotIn('decode_context', value)
        self.assertIsNone(value['http_status'])

    def test_socket_timeout_keeps_response_context_without_claiming_final(self):
        self.stream(b'')
        self.response.readline.side_effect = TimeoutError(provider.SECRET)
        value = self.failure('timeout', 'sse')
        self.assertEqual(value['stage'], 'response-read')
        self.assertEqual(value['decode_context']['response_bytes_observed'], 0)
        self.assertFalse(value['decode_context']['sse_final_seen'])


class DecodeEnvelopeTests(unittest.TestCase):
    setUp = diagnostic_fixtures.AdapterFailureDiagnosticsTests.setUp
    envelope = diagnostic_fixtures.AdapterFailureDiagnosticsTests.envelope
    failure = diagnostic_fixtures.AdapterFailureDiagnosticsTests.failure

    def value(self):
        return {**safe_diagnostic('provider-decode', 'sse-final-missing', 'response-received', 200),
                'version':'image-led-failure-diagnostic/v2',
                'decode_context':{'response_format':'sse','response_bytes_observed':14,
                                  'sse_blocks_seen':1,'sse_final_seen':False}}

    def test_parent_accepts_bound_v2_and_preserves_v1(self):
        value = self.value()
        self.assertEqual(self.failure(json.dumps(self.envelope(value)).encode()),
                         {**value,'subprocess_exit_code':1})
        legacy = safe_diagnostic('provider-decode','provider-decode-failed','response-received',200)
        self.assertEqual(self.failure(json.dumps(self.envelope(legacy)).encode()),
                         {**legacy,'subprocess_exit_code':1})

    def test_bad_decode_context_is_not_promoted_as_trusted_http_evidence(self):
        mutations = [lambda d:d.update(version='image-led-failure-diagnostic/v1'),
            lambda d:d.update(stage='input'), lambda d:d.update(reason=provider.SECRET),
            lambda d:d['decode_context'].update(raw=provider.SECRET),
            lambda d:d['decode_context'].update(response_format=provider.SECRET),
            lambda d:d['decode_context'].update(response_bytes_observed=True),
            lambda d:d['decode_context'].update(response_bytes_observed=-1),
            lambda d:d['decode_context'].update(sse_blocks_seen=True),
            lambda d:d['decode_context'].update(sse_blocks_seen=-1),
            lambda d:d['decode_context'].update(sse_final_seen=0),
            lambda d:d['decode_context'].update(response_format='json-fallback'),
            lambda d:d.pop('decode_context')]
        for change in mutations:
            value=self.value(); change(value)
            with self.subTest(change=mutations.index(change)):
                self.assertEqual(self.failure(json.dumps(self.envelope(value)).encode()),
                    safe_diagnostic('subprocess','subprocess-failed','not-established',exit_code=1))


class DecodeRuntimeTests(unittest.TestCase):
    def test_actual_decode_diagnostic_survives_recover_without_replay_or_old_receipt_changes(self):
        from tests.test_image_led_v2_runtime import OfflineKnownCrsBoundary, exact_crs_environment, v2_input_fixture
        from tests.test_image2_output_compatibility import action
        from tests.test_image2_input_boundary import tree_snapshot
        from ai_ppt_studio.application.v16_bridge import dispatch_v16
        class Boundary(OfflineKnownCrsBoundary):
            def open(self, request, **options):
                response = super().open(request, **options)
                response.headers={'Content-Type':'text/event-stream'}
                response.readline=BytesIO(b'data: [DONE]\n\n').readline
                return response
        with tempfile.TemporaryDirectory() as folder:
            service,_,packs=v2_input_fixture(Path(folder))
            with patch.dict(os.environ,exact_crs_environment('gpt-image-2')), Boundary(model='gpt-image-2') as boundary:
                result=dispatch_v16(action(service,packs[0]))['result']; response=result['generation_response']
                self.assertEqual(response['status'],'unknown')
                self.assertEqual(response['failure_diagnostic']['reason'],'sse-final-missing')
                self.assertNotIn('image_base64',response)
                before=tree_snapshot(Path(folder))
                recovered=dispatch_v16(action(service,packs[0],command_id='decode-recover',generation_intent='recover'))['result']
                self.assertEqual(recovered['generation_response'],response)
                self.assertEqual(tree_snapshot(Path(folder)),before)
                self.assertEqual(len(boundary.http_calls),1)
                self.assertEqual(len(boundary.helper_calls),1)
                self.assertFalse(recovered['generation_usability']['candidate_eligible'])


if __name__ == '__main__':
    unittest.main()
