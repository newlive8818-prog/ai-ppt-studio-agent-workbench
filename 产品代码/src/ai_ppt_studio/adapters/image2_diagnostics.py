"""Closed, content-free failure evidence. No network, environment, or file I/O."""
from copy import deepcopy
import hashlib
import json

from ai_ppt_studio.errors import ContractValidationError

VERSION = 'image-led-failure-diagnostic/v1'
DECODE_VERSION = 'image-led-failure-diagnostic/v2'
PROTOCOL = 'image-led-command-failure/v1'
MAX_BYTES = 2048
REASONS = {
    'input': {'invalid-input'},
    'compile': {'compile-failed'},
    'credential-helper': {'helper-failed', 'helper-timeout', 'deadline-exceeded'},
    'http-open': {'http-error', 'tls-error', 'connection-error', 'timeout', 'unknown-failure', 'deadline-exceeded'},
    'response-read': {'response-read-failed', 'timeout', 'deadline-exceeded'},
    'provider-decode': {'provider-decode-failed', 'deadline-exceeded',
        'sse-read-type-invalid', 'sse-line-limit', 'sse-total-limit', 'sse-event-limit',
        'sse-incomplete-event', 'sse-line-ending-invalid', 'sse-utf8-invalid',
        'sse-control-character', 'sse-block-limit', 'sse-done-with-event',
        'sse-json-invalid', 'sse-event-shape-invalid', 'sse-provider-error',
        'sse-event-envelope-unsupported', 'sse-event-name-mismatch', 'sse-event-type-unsupported',
        'sse-model-invalid', 'sse-metadata-invalid', 'sse-duplicate-final',
        'sse-base64-invalid', 'sse-png-header-invalid', 'sse-partial-after-final',
        'sse-heartbeat-image', 'sse-empty-event-invalid', 'sse-field-invalid',
        'sse-retry-invalid', 'sse-event-name-invalid', 'sse-final-missing',
        'json-parse-invalid', 'json-response-shape-invalid', 'json-image-shape-invalid',
        'json-model-invalid', 'json-metadata-invalid', 'json-base64-invalid', 'json-png-header-invalid'},
    'wrapper-receipt': {'wrapper-receipt-failed'},
    'adapter-receipt': {'adapter-receipt-invalid'},
    'image-decode': {'image-decode-failed'},
    'subprocess': {'subprocess-failed'},
}
LOCAL_STAGES = {'adapter-receipt', 'image-decode', 'subprocess'}


def validate_diagnostic(value):
    keys = {'version', 'stage', 'transport_state', 'http_attempted', 'reason',
            'http_status', 'subprocess_exit_code'}
    if type(value) is not dict:
        raise ValueError('invalid safe diagnostic')
    v2 = value.get('version') == DECODE_VERSION
    if set(value) != keys | ({'decode_context'} if v2 else set()) or value['version'] not in (VERSION, DECODE_VERSION):
        raise ValueError('invalid safe diagnostic')
    stage, reason = value['stage'], value['reason']
    if type(stage) is not str or stage not in REASONS or type(reason) is not str or reason not in REASONS[stage]:
        raise ValueError('invalid safe diagnostic')
    if stage in {'input', 'compile', 'credential-helper'}:
        state, attempted = 'before-send', False
    elif stage in LOCAL_STAGES:
        state, attempted = 'not-established', None
    elif stage == 'http-open' and reason != 'http-error':
        state, attempted = 'send-attempted', True
    else:
        state, attempted = 'response-received', True
    if value['transport_state'] != state or value['http_attempted'] is not attempted:
        raise ValueError('invalid safe diagnostic')
    status, code = value['http_status'], value['subprocess_exit_code']
    if status is not None and (type(status) is not int or not 100 <= status <= 599 or state != 'response-received'):
        raise ValueError('invalid safe diagnostic')
    if reason == 'http-error' and status is None:
        raise ValueError('invalid safe diagnostic')
    if code is not None and (type(code) is not int or not -255 <= code <= 255):
        raise ValueError('invalid safe diagnostic')
    if v2:
        context = value['decode_context']
        if (stage not in {'response-read', 'provider-decode'} or status != 200
                or type(context) is not dict or set(context) != {'response_format',
                    'response_bytes_observed', 'sse_blocks_seen', 'sse_final_seen'}):
            raise ValueError('invalid decode context')
        format_ = context['response_format']
        if type(format_) is not str or format_ not in {'sse', 'json-fallback'}:
            raise ValueError('invalid decode context')
        count = context['response_bytes_observed']
        if type(count) is not int or not 0 <= count <= 2**53 - 1:
            raise ValueError('invalid decode context')
        blocks, final = context['sse_blocks_seen'], context['sse_final_seen']
        if format_ == 'sse':
            if type(blocks) is not int or not 0 <= blocks <= 257 or type(final) is not bool:
                raise ValueError('invalid decode context')
            if final and blocks == 0:
                raise ValueError('invalid decode context')
        elif blocks is not None or final is not None:
            raise ValueError('invalid decode context')
        if reason.startswith('sse-') and format_ != 'sse' or reason.startswith('json-') and format_ != 'json-fallback':
            raise ValueError('invalid decode context')
    return deepcopy(value)


def diagnostic(stage, reason, *, status=None, exit_code=None, decode_context=None):
    if stage in {'input', 'compile', 'credential-helper'}:
        state, attempted = 'before-send', False
    elif stage in LOCAL_STAGES:
        state, attempted = 'not-established', None
    elif stage == 'http-open' and reason != 'http-error':
        state, attempted = 'send-attempted', True
    else:
        state, attempted = 'response-received', True
    return validate_diagnostic({'version': DECODE_VERSION if decode_context is not None else VERSION,
        'stage': stage, 'reason': reason,
        'transport_state': state, 'http_attempted': attempted, 'http_status': status,
        'subprocess_exit_code': exit_code,
        **({'decode_context': decode_context} if decode_context is not None else {})})


def encode_failure(request_bytes, value):
    checked = validate_diagnostic(value)
    if checked['subprocess_exit_code'] is not None or checked['stage'] in LOCAL_STAGES:
        raise ValueError('invalid wrapper diagnostic')
    raw = (json.dumps({'protocol': PROTOCOL, 'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
        'failure_diagnostic': checked}, ensure_ascii=True, separators=(',', ':')) + '\n').encode('ascii')
    if len(raw) > MAX_BYTES:
        raise ValueError('invalid wrapper diagnostic')
    return raw


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('invalid failure envelope')
        result[key] = value
    return result


def parse_failure(raw, request_bytes, returncode):
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES or type(returncode) is not int or returncode == 0:
        raise ValueError('invalid failure envelope')
    try:
        envelope = json.loads(raw, object_pairs_hook=unique_object)
        if (type(envelope) is not dict or set(envelope) != {'protocol', 'request_sha256', 'failure_diagnostic'}
                or envelope['protocol'] != PROTOCOL
                or envelope['request_sha256'] != hashlib.sha256(request_bytes).hexdigest()):
            raise ValueError('invalid failure envelope')
        value = validate_diagnostic(envelope['failure_diagnostic'])
        if value['subprocess_exit_code'] is not None or value['stage'] in LOCAL_STAGES:
            raise ValueError('invalid failure envelope')
        value['subprocess_exit_code'] = returncode
        return validate_diagnostic(value)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ValueError('invalid failure envelope') from None


class CommandFailure(RuntimeError):
    def __init__(self, value):
        self.failure_diagnostic = validate_diagnostic(value)
        super().__init__('Image 2 execution outcome is unknown')


class CommandContractFailure(ContractValidationError):
    def __init__(self, value):
        self.failure_diagnostic = validate_diagnostic(value)
        super().__init__('Image 2 adapter response contract is invalid')


def command_failure(error):
    """Only exact internal carriers; never trust arbitrary exception attributes."""
    if type(error) not in (CommandFailure, CommandContractFailure):
        return None
    try:
        return validate_diagnostic(error.failure_diagnostic)
    except (ValueError, TypeError, AttributeError):
        return None


def error_category(error):
    if type(error) is CommandFailure:
        return 'RuntimeError'
    if type(error) is CommandContractFailure:
        return 'ContractValidationError'
    name = type(error).__name__
    return name if name in {'RuntimeError', 'ContractValidationError', 'TimeoutError',
        'ValueError', 'TypeError', 'KeyError', 'OSError', 'FileNotFoundError', 'PermissionError',
        'ConnectionError', 'ModuleNotFoundError', 'ImportError', 'UnidentifiedImageError',
        'DecompressionBombError', 'MemoryError'} else 'Exception'
