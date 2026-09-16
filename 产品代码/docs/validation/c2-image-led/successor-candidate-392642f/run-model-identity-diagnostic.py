"""Read-only traced integration of an unchanged reviewed wrapper; no Runtime writes."""
from pathlib import Path
import argparse, base64, contextlib, datetime, email.parser, email.policy
import hashlib, io, json, os, re, runpy, sys

ROOT = Path('/private/tmp/c2-image25-adaptation-20260911/synthetic-provider-tests/model-identity-diagnostic-v3')
MODEL = 'gpt-image-2.5-sunburst'
FIXTURES = {
    'generation': ('152f9731e34d7d742ac9e656fa4855108fc81329deeecd5c92fae005eb621529', 0),
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def main():
    if sys.flags.optimize != 0:
        raise RuntimeError('OPTIMIZED_PYTHON_NOT_ALLOWED')
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=FIXTURES, required=True)
    parser.add_argument('--wrapper', required=True)
    parser.add_argument('--wrapper-sha256', required=True)
    parser.add_argument('--source-manifest', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    sys.dont_write_bytecode = True
    wrapper = Path(args.wrapper).resolve(strict=True)
    assert wrapper.name == 'image2_crs.py'
    assert sha(wrapper.read_bytes()) == args.wrapper_sha256
    source_manifest = Path(args.source_manifest).resolve(strict=True)
    manifest = json.loads(source_manifest.read_bytes())
    source_root = Path(manifest['source_root']).resolve(strict=True)
    assert wrapper.is_relative_to(source_root)
    assert manifest['status'] == 'reviewed-fixed-source'
    def verify_source():
        for rel, digest in manifest['files'].items():
            file = (source_root / rel).resolve(strict=True)
            assert file.is_relative_to(source_root)
            assert sha(file.read_bytes()) == digest
        actual = {str(p.relative_to(source_root)) for p in source_root.rglob('*.py')}
        assert actual == set(manifest['files'])
    verify_source()
    raw_fixture = (ROOT / (args.case + '-request.json')).read_bytes()
    expected_hash, image_count = FIXTURES[args.case]
    assert sha(raw_fixture) == expected_hash
    envelope = json.loads(raw_fixture)
    assert envelope['payload']['model'] == MODEL
    expected_images = [m for m in envelope['payload']['materials'] if m['type'] == 'image']
    assert len(expected_images) == image_count
    record = {
        'started_at': now(), 'case': args.case, 'status': 'prepared',
        'scope': 'noncustomer-wrapper-component-integration',
        'formal_runtime_or_current_host_proof': False, 'customer_data_sent': False,
        'wrapper': str(wrapper), 'wrapper_sha256': args.wrapper_sha256,
        'source_manifest_sha256': sha(source_manifest.read_bytes()),
        'request_fixture_sha256': expected_hash, 'request_id': envelope['request_id'],
        'model': MODEL, 'entry': 'unmodified wrapper via runpy with read-only sys.settrace',
        'python': sys.executable, 'wrapper_sys_argv': [str(wrapper), '--model', MODEL],
        'tls_verification': True, 'automatic_retry': False,
    }
    if not args.execute:
        print(json.dumps(record, ensure_ascii=False))
        return 0
    result_dir = ROOT / (args.case + '-live-v1')
    result_dir.mkdir(exist_ok=False)
    record_path = result_dir / 'receipt.json'
    def save():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    record['status'] = 'started-result-unknown'
    save()
    request_seen, response_seen = False, False
    def trace(frame, event, arg):
        nonlocal request_seen, response_seen
        if frame.f_code.co_filename != str(wrapper) or frame.f_code.co_name != 'generate':
            return None
        local = frame.f_locals
        if event == 'exception':
            exception_type, exception_value, _ = arg
            safe_exception = {'type': exception_type.__name__}
            if exception_type.__name__ == 'HTTPError' and type(getattr(exception_value, 'code', None)) is int:
                safe_exception['http_status'] = exception_value.code
            if exception_type.__name__ == 'URLError':
                safe_exception['reason_type'] = type(getattr(exception_value, 'reason', None)).__name__
            record['wrapper_exception'] = safe_exception
            save()
        if not request_seen and 'req' in local:
            req = local['req']
            assert req.get_header('User-agent') == 'AI-PPT-Studio/0.4.0'
            body = req.data
            content_type = req.get_header('Content-type')
            fields, images = {}, []
            if content_type == 'application/json':
                fields = json.loads(body)
            else:
                message = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                    ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
                assert message.is_multipart()
                for part in message.iter_parts():
                    name = part.get_param('name', header='content-disposition')
                    raw = part.get_payload(decode=True)
                    if name in ('image', 'image[]'):
                        images.append({'field': name, 'sha256': sha(raw), 'bytes': len(raw),
                                       'mime_type': part.get_content_type()})
                    else:
                        assert name not in fields
                        fields[name] = raw.decode('utf8')
            assert fields['model'] == MODEL and fields['size'] == '2048x1152'
            assert fields['quality'] == 'high' and fields['output_format'] == 'png'
            assert str(fields['n']) == '1'
            assert len(images) == image_count
            for observed, expected in zip(images, expected_images):
                assert observed['field'] == 'image[]'
                assert observed['sha256'] == sha(base64.b64decode(expected['data_base64'], validate=True))
                assert observed['mime_type'] == expected['mime_type']
            expected_url = 'https://sub.523869.xyz/v1/images/' + ('edits' if images else 'generations')
            assert req.full_url == expected_url and req.get_method() == 'POST'
            record['request_observed_before_open'] = {
                'at': now(), 'url': req.full_url, 'method': req.get_method(),
                'user_agent': req.get_header('User-agent'),
                'body_sha256': sha(body), 'body_bytes': len(body),
                'model': fields['model'], 'size': fields['size'], 'quality': fields['quality'],
                'output_format': fields['output_format'], 'n': int(fields['n']),
                'prompt_sha256': sha(fields['prompt'].encode()), 'images': images,
            }
            request_seen = True
            save()
        if not response_seen and 'raw_response' in local:
            raw = local['raw_response']
            remote = json.loads(raw)
            items = remote.get('data')
            explicit = []
            if 'model' in remote:
                explicit.append(remote['model'])
            if isinstance(items, list):
                explicit.extend(x['model'] for x in items if isinstance(x, dict) and 'model' in x)
            record['response_observed'] = {
                'at': now(), 'http_status': local['response'].status,
                'response_sha256': sha(raw), 'response_bytes': len(raw),
                'explicit_model_present': bool(explicit),
                'all_explicit_models_match': all(v == MODEL for v in explicit) if explicit else None,
                'independent_provider_execution_model_proof': False,
            }
            safe_models = []
            for reported in explicit:
                if reported is None or reported == '':
                    safe_models.append({'value': reported, 'type': type(reported).__name__})
                elif isinstance(reported, str) and re.fullmatch(r'(?:gpt-|dall-e-|imagen-|gemini-|flux-)[A-Za-z0-9._:-]{1,90}', reported):
                    safe_models.append({'value': reported, 'type': 'str'})
                else:
                    safe_models.append({'type': type(reported).__name__, 'value_recorded': False})
            record['response_observed']['explicit_model_metadata'] = safe_models
            record['response_observed']['observation_is_not_model_acceptance'] = True
            # Retain a fully decoded noncustomer image only as rejected diagnostic evidence.
            try:
                from PIL import Image
                diagnostic_raw = base64.b64decode(items[0]['b64_json'], validate=True)
                with Image.open(io.BytesIO(diagnostic_raw)) as im:
                    if im.format != 'PNG':
                        raise ValueError('DIAGNOSTIC_FORMAT')
                    im.verify()
                with Image.open(io.BytesIO(diagnostic_raw)) as im:
                    im.load(); dimensions = list(im.size)
                rejected_path = result_dir / 'unaccepted-diagnostic-image.png'
                rejected_path.write_bytes(diagnostic_raw)
                record['unaccepted_diagnostic_image'] = {'path':str(rejected_path),
                    'sha256':sha(diagnostic_raw),'dimensions':dimensions,'accepted':False}
            except Exception as diagnostic_error:
                record['diagnostic_decode_failure_type'] = type(diagnostic_error).__name__
            response_seen = True
            save()
        return trace
    previous_argv, previous_stdin = sys.argv, sys.stdin
    output, errors = io.StringIO(), io.StringIO()
    exit_code = 0
    try:
        sys.argv = [str(wrapper), '--model', MODEL]
        sys.stdin = io.StringIO(raw_fixture.decode('utf8'))
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            sys.settrace(trace)
            try:
                runpy.run_path(str(wrapper), run_name='__main__')
            except SystemExit as ex:
                exit_code = ex.code
            finally:
                sys.settrace(None)
        record['wrapper_exit_code'] = exit_code
        record['safe_failure_marker'] = errors.getvalue() == 'IMAGE2_CRS_SAFE_FAILURE\n'
        assert exit_code == 0 and request_seen and response_seen
        result = json.loads(output.getvalue())
        assert result['model'] == MODEL and result['receiver'] == 'CRS'
        assert result['protocol'] == envelope['protocol'] and result['request_id'] == envelope['request_id']
        raw_image = base64.b64decode(result['image_base64'], validate=True)
        from PIL import Image
        with Image.open(io.BytesIO(raw_image)) as check:
            assert check.format == 'PNG'
            check.verify()
        with Image.open(io.BytesIO(raw_image)) as decoded:
            decoded.load()
            dimensions = list(decoded.size)
        (result_dir / 'result.png').write_bytes(raw_image)
        record['result'] = {'image_sha256': sha(raw_image), 'image_bytes': len(raw_image),
                            'dimensions': dimensions, 'path': str(result_dir / 'result.png'),
                            'response_id': result['response_id'], 'model': result['model']}
        assert dimensions == [2048, 1152]
        record['status'] = 'execution-passed-source-after-check-pending'
    except BaseException as ex:
        # Never emit raw exceptions, provider text, helper data, or frame locals.
        record['failure_type'] = type(ex).__name__
        record['status'] = 'failed-no-retry-result-may-be-unknown'
        exit_code = 1
    finally:
        sys.settrace(None)
        sys.argv, sys.stdin = previous_argv, previous_stdin
        try:
            verify_source()
            record['source_after_check'] = 'passed'
        except BaseException as source_error:
            record['source_after_check'] = 'failed'
            record['source_after_failure_type'] = type(source_error).__name__
            exit_code = 1
        if record['status'] == 'execution-passed-source-after-check-pending':
            record['status'] = ('passed' if record['source_after_check'] == 'passed'
                                else 'failed-source-after-check')
        record['finished_at'] = now()
        save()
    print(json.dumps(record, ensure_ascii=False))
    return exit_code

if __name__ == '__main__':
    raise SystemExit(main())
