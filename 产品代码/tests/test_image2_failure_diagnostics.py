"""Offline failure visibility: synthetic credentials/responses only, no retries."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from ai_ppt_studio.adapters import image2_command
from tests import test_image2_crs_provider as provider
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from tests.test_image_led_v2_runtime import exact_crs_environment, v2_input_fixture, OfflineKnownCrsBoundary
from tests.test_image2_input_boundary import tree_snapshot
from tests.test_image2_output_compatibility import action, resolve


def safe_diagnostic(stage='credential-helper', reason='helper-failed', state='before-send', status=None, exit_code=None):
    return {'version': 'image-led-failure-diagnostic/v1', 'stage': stage,
        'transport_state': state, 'http_attempted': {'before-send': False,
            'send-attempted': True, 'response-received': True, 'not-established': None}[state],
        'reason': reason, 'http_status': status, 'subprocess_exit_code': exit_code}


class AdapterFailureDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        command = json.loads(exact_crs_environment('gpt-image-2')['AI_PPT_IMAGE2_ADAPTER_COMMAND'])
        self.adapter = image2_command.Image2CommandAdapter(command, 'CRS', 'gpt-image-2', {})
        self.enterContext(patch.object(self.adapter, 'preflight'))
        self.request = provider.request()
        self.request_bytes = json.dumps(self.request, ensure_ascii=False).encode()

    def envelope(self, diagnostic=None):
        return {'protocol': 'image-led-command-failure/v1',
            'request_sha256': hashlib.sha256(self.request_bytes).hexdigest(),
            'failure_diagnostic': diagnostic or safe_diagnostic()}

    def failure(self, raw, code=1):
        with patch.object(image2_command.subprocess, 'run', return_value=subprocess.CompletedProcess(
                self.adapter.command, code, stdout=raw)) as runner:
            with self.assertRaises(RuntimeError) as caught:
                self.adapter.generate(request_id=self.request['request_id'], payload=self.request['payload'])
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(runner.call_args.kwargs['input'], self.request_bytes)
        diagnostic = getattr(caught.exception, 'failure_diagnostic', None)
        self.assertIsInstance(diagnostic, dict, 'Parent discarded the bounded safe diagnostic')
        self.assertNotIn(provider.SECRET, str(caught.exception) + json.dumps(diagnostic))
        return diagnostic

    def test_bound_known_wrapper_failure_uses_actual_parent_exit(self):
        self.assertEqual(self.failure(json.dumps(self.envelope()).encode(), 7),
                         safe_diagnostic(exit_code=7))

    def test_signal_without_receipt_does_not_claim_before_send(self):
        self.assertEqual(self.failure(b'', -9), safe_diagnostic('subprocess', 'subprocess-failed',
                         'not-established', exit_code=-9))

    def test_invalid_success_stdout_is_local_receipt_not_http_proof(self):
        self.assertEqual(self.failure(provider.SECRET.encode(), 0), safe_diagnostic(
            'adapter-receipt', 'adapter-receipt-invalid', 'not-established', exit_code=0))

    def test_untrusted_diagnostic_fields_cannot_be_promoted(self):
        mutations = [
            lambda e: e.update(request_sha256='0'*64),
            lambda e: e.update(secret=provider.SECRET),
            lambda e: e['failure_diagnostic'].update(reason=provider.SECRET),
            lambda e: e['failure_diagnostic'].update(stage=provider.SECRET),
            lambda e: e['failure_diagnostic'].update(http_attempted=0),
            lambda e: e['failure_diagnostic'].update(http_attempted=True),
            lambda e: e['failure_diagnostic'].update(http_status=True),
            lambda e: e['failure_diagnostic'].update(http_status=200),
            lambda e: e['failure_diagnostic'].update(subprocess_exit_code=0),
            lambda e: e['failure_diagnostic'].update(subprocess_exit_code=True),
            lambda e: e['failure_diagnostic'].update(reason='tls-error'),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                envelope = self.envelope(); mutate(envelope)
                self.assertEqual(self.failure(json.dumps(envelope).encode()),
                    safe_diagnostic('subprocess', 'subprocess-failed', 'not-established', exit_code=1))

    def test_duplicate_keys_and_byte_limit_reject_entire_envelope(self):
        original = json.dumps(self.envelope()).encode()
        duplicate = original.replace(b'"protocol":', b'"protocol":"wrong","protocol":', 1)
        for raw in (duplicate, original + b' ' * 2048, b'\xff', b'[]', b'null'):
            with self.subTest(length=len(raw)):
                self.assertEqual(self.failure(raw), safe_diagnostic('subprocess', 'subprocess-failed',
                    'not-established', exit_code=1))

    def test_byte_limit_includes_multibyte_padding_and_nested_duplicate_keys(self):
        original = json.dumps(self.envelope()).encode()
        nested = original.replace(b'"http_status":', b'"http_status":200,"http_status":', 1)
        deep = b'[' * 1020 + b'0' + b']' * 1020
        for raw in (nested, deep, original + '中'.encode() * 700):
            self.assertEqual(self.failure(raw), safe_diagnostic('subprocess', 'subprocess-failed',
                'not-established', exit_code=1))
        exact = original + b' ' * (2048 - len(original))
        self.assertEqual(self.failure(exact), safe_diagnostic(exit_code=1))
        self.assertEqual(self.failure(exact + b' '), safe_diagnostic('subprocess',
            'subprocess-failed', 'not-established', exit_code=1))

    def test_contract_validation_error_keeps_existing_exception_and_category(self):
        from ai_ppt_studio.adapters.image2_diagnostics import command_failure, error_category
        with patch.object(image2_command.subprocess, 'run', return_value=subprocess.CompletedProcess(
                self.adapter.command, 0, stdout=b'{}')):
            with self.assertRaises(ContractValidationError) as caught:
                self.adapter.generate(request_id=self.request['request_id'], payload=self.request['payload'])
        self.assertEqual(error_category(caught.exception), 'ContractValidationError')
        self.assertEqual(command_failure(caught.exception), safe_diagnostic('adapter-receipt',
            'adapter-receipt-invalid', 'not-established', exit_code=0))

    def test_other_adapter_cannot_self_report_known_wrapper_diagnostic(self):
        self.adapter.command = ['/synthetic/other-adapter']
        self.assertEqual(self.failure(json.dumps(self.envelope()).encode()),
            safe_diagnostic('subprocess', 'subprocess-failed', 'not-established', exit_code=1))


class WrapperFailureDiagnosticsTests(unittest.TestCase):
    setUp = provider.Image2CrsProviderTests.setUp
    invoke = provider.Image2CrsProviderTests.invoke

    def diagnostic(self, result, *, stage, state, reason, status=None, value=None, context=None):
        code, out, err = result
        self.assertEqual(code, 1)
        self.assertTrue(out.strip(), 'Wrapper discards the safe failure stage')
        receipt = json.loads(out)
        self.assertEqual(set(receipt), {'protocol', 'request_sha256', 'failure_diagnostic'})
        self.assertEqual(receipt['protocol'], 'image-led-command-failure/v1')
        raw = json.dumps(value or provider.request(), ensure_ascii=False).encode('utf-8')
        self.assertEqual(receipt['request_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['failure_diagnostic'], {
            'version': 'image-led-failure-diagnostic/v2' if context is not None else 'image-led-failure-diagnostic/v1', 'stage': stage,
            'transport_state': state, 'http_attempted': state != 'before-send',
            'reason': reason, 'http_status': status, 'subprocess_exit_code': None,
            **({'decode_context': context} if context is not None else {})})
        for forbidden in (provider.SECRET, provider.CUSTOMER.strip(), 'Traceback', 'Authorization'):
            self.assertNotIn(forbidden, out + err)
        self.assertLessEqual(len(out.encode()), 2048)
        return receipt

    def test_helper_failure_is_before_send_and_does_not_call_http(self):
        self.auth.return_value.returncode = 7
        self.diagnostic(self.invoke(), stage='credential-helper', state='before-send', reason='helper-failed')
        self.opener.open.assert_not_called()

    def test_compile_failure_is_before_helper_and_http(self):
        value = provider.request()
        value['payload']['unsafe'] = provider.SECRET
        self.diagnostic(self.invoke(value), stage='compile', state='before-send', reason='compile-failed', value=value)
        self.auth.assert_not_called()
        self.opener.open.assert_not_called()

    def test_helper_timeout_is_before_send(self):
        self.auth.side_effect = subprocess.TimeoutExpired(provider.SECRET, 30, output=provider.SECRET.encode())
        self.diagnostic(self.invoke(), stage='credential-helper', state='before-send', reason='helper-timeout')
        self.opener.open.assert_not_called()

    def test_tls_failure_means_attempted_not_received(self):
        self.opener.open.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError(1, provider.SECRET))
        self.diagnostic(self.invoke(), stage='http-open', state='send-attempted', reason='tls-error')
        self.opener.open.assert_called_once()

    def test_all_http_open_failure_reasons_are_fixed(self):
        for error, reason in ((TimeoutError(provider.SECRET), 'timeout'),
            (urllib.error.URLError(TimeoutError(provider.SECRET)), 'timeout'),
            (ConnectionError(provider.SECRET), 'connection-error'),
            (urllib.error.URLError(provider.SECRET), 'connection-error'),
            (RuntimeError(provider.SECRET), 'unknown-failure')):
            self.opener.open.side_effect = error
            self.diagnostic(self.invoke(), stage='http-open', state='send-attempted', reason=reason)

    def test_http_error_has_response_observation_without_body(self):
        self.opener.open.side_effect = urllib.error.HTTPError('https://example.invalid', 403, provider.SECRET, {}, None)
        self.diagnostic(self.invoke(), stage='http-open', state='response-received', reason='http-error', status=403)
        self.opener.open.assert_called_once()

    def test_read_timeout_retains_received_status(self):
        self.response.read.side_effect = TimeoutError(provider.SECRET)
        self.diagnostic(self.invoke(), stage='response-read', state='response-received', reason='timeout', status=200, context={
            'response_format':'json-fallback','response_bytes_observed':0,'sse_blocks_seen':None,'sse_final_seen':None})

    def test_read_error_is_distinct_from_provider_decode(self):
        self.response.read.side_effect = OSError(provider.SECRET)
        self.diagnostic(self.invoke(), stage='response-read', state='response-received', reason='response-read-failed', status=200, context={
            'response_format':'json-fallback','response_bytes_observed':0,'sse_blocks_seen':None,'sse_final_seen':None})

    def test_invalid_input_envelope_hashes_exact_raw_bytes(self):
        raw = '{"duplicate":1,"duplicate":2}'
        code, out, err = self.invoke(raw=raw)
        self.assertEqual(code, 1)
        receipt = json.loads(out)
        self.assertEqual(receipt['request_sha256'], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(receipt['failure_diagnostic'], safe_diagnostic('input', 'invalid-input'))
        self.auth.assert_not_called()
        self.opener.open.assert_not_called()


    def test_provider_decode_failure_retains_received_status(self):
        self.response.read.return_value = (provider.SECRET + provider.CUSTOMER).encode()
        self.diagnostic(self.invoke(), stage='provider-decode', state='response-received', reason='json-parse-invalid', status=200, context={
            'response_format':'json-fallback', 'response_bytes_observed':len((provider.SECRET + provider.CUSTOMER).encode()),
            'sse_blocks_seen':None,'sse_final_seen':None})

    def test_wrapper_receipt_serialization_failure_has_own_stage(self):
        original = self.wrapper.generate
        def corrupt(*args, **kwargs):
            result = original(*args, **kwargs)
            result['response_id'] = object()
            return result
        with patch.object(self.wrapper, 'generate', side_effect=corrupt):
            self.diagnostic(self.invoke(), stage='wrapper-receipt', state='response-received', reason='wrapper-receipt-failed', status=200)


class RuntimeFailureDiagnosticsTests(unittest.TestCase):
    def test_exact_failure_survives_runtime_recover_without_resend(self):
        class FailingBoundary(OfflineKnownCrsBoundary):
            def open(self, request, **options):
                self.http_calls.append((request, options))
                raise urllib.error.HTTPError('https://example.invalid', 504, provider.SECRET, {}, None)
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            with patch.dict(os.environ, exact_crs_environment('gpt-image-2')), FailingBoundary(model='gpt-image-2') as boundary:
                result = dispatch_v16(action(service, packs[0]))['result']
                response = result['generation_response']
                self.assertEqual(response['status'], 'unknown')
                self.assertEqual(response['error_category'], 'RuntimeError')
                self.assertEqual(response['failure_diagnostic'], safe_diagnostic('http-open', 'http-error',
                    'response-received', status=504, exit_code=1))
                self.assertNotIn(provider.SECRET, json.dumps(response))
                before = tree_snapshot(Path(folder))
                recovered = dispatch_v16(action(service, packs[0], command_id='diagnostic-recover', generation_intent='recover'))['result']
                self.assertEqual(recovered['generation_response'], response)
                self.assertEqual(tree_snapshot(Path(folder)), before)
                self.assertEqual(len(boundary.http_calls), 1)
                self.assertEqual(len(boundary.helper_calls), 1)
                self.assertFalse(recovered['generation_usability']['candidate_eligible'])

    def test_injected_bad_image_is_local_decode_not_http_proof(self):
        class Transport:
            def generate(self, **kwargs):
                return {'response_id': 'synthetic', 'image_bytes': b'bad-image'}
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            _, task, _ = ProjectCommandService(service.kernel).request_agent_action('diag-decode',
                service.kernel.load().revision, action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            response = resolve(service, service.execute_generation(task['task_id'], transport=Transport()))
            self.assertEqual(response['status'], 'unknown')
            self.assertEqual(response['failure_diagnostic'], safe_diagnostic('image-decode',
                'image-decode-failed', 'not-established'))

    def test_arbitrary_exception_diagnostic_and_name_never_leak(self):
        SecretError = type(provider.SECRET, (RuntimeError,), {})
        class Transport:
            def generate(self, **kwargs):
                error = SecretError(provider.SECRET)
                error.failure_diagnostic = {**safe_diagnostic(), 'secret': provider.SECRET}
                raise error
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            _, task, _ = ProjectCommandService(service.kernel).request_agent_action('diag-untrusted',
                service.kernel.load().revision, action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            response = resolve(service, service.execute_generation(task['task_id'], transport=Transport()))
            self.assertEqual(response['error_category'], 'Exception')
            self.assertEqual(response['failure_diagnostic'], safe_diagnostic('subprocess',
                'subprocess-failed', 'not-established'))
            self.assertNotIn(provider.SECRET, json.dumps(response))

    def test_historical_unknown_recover_does_not_backfill_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = v2_input_fixture(Path(folder))
            _, task, _ = ProjectCommandService(service.kernel).request_agent_action('diag-history',
                service.kernel.load().revision, action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            # Synthetic historical receipt setup, never customer history mutation.
            _, _, payload = service.generation_context(task['task_id'])
            from ai_ppt_studio.domains.materials.image_input_contracts import digest
            value = {'project_id': service.kernel.project_id, 'request_id': task['task_id'],
                'pack_ref': packs[0], 'payload_sha256': digest(payload), 'status': 'unknown',
                'claim_id': 'synthetic-old-claim', 'error_category': 'RuntimeError'}
            service.kernel.commit(command_id='synthetic-diag-history', expected_revision=service.kernel.load().revision,
                event_type='synthetic.old-unknown', artifact_updates={
                    'project/image-led/request/' + task['task_id']: ('image-led-generation-response', value)})
            before = tree_snapshot(Path(folder))
            self.assertEqual(service.generation_receipt(task)[1], value)
            self.assertEqual(tree_snapshot(Path(folder)), before)


class FreshProcessDiagnosticsTests(unittest.TestCase):
    def test_fresh_python_minimal_environment_and_os_pipe_reject_before_helper(self):
        raw = json.dumps({'合成输入': '纯离线错误合同'}, ensure_ascii=False).encode('utf-8')
        env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, str(provider.WRAPPER)], input=raw,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=folder, timeout=10)
        self.assertEqual(result.returncode, 1)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['request_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['failure_diagnostic'], safe_diagnostic('compile', 'compile-failed'))
        self.assertEqual(result.stderr, b'IMAGE2_CRS_SAFE_FAILURE\n')

if __name__ == '__main__':
    unittest.main()
