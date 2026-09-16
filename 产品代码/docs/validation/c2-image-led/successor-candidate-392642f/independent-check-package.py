from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import os
import stat
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone

B = Path('/private/tmp/c2-candidate-392642f-20260911')
W = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
S = B / 'source'
C = S / '产品代码'
P = B / 'plugin-release/ai-ppt-studio'
Y = '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
COMMIT = '392642f2a34afd856b07228d97ce2b3180fdc961'
VERSION = '0.4.0+codex.c2.392642f.20260911'
ARCHIVE = B / ('ai-ppt-studio-' + VERSION + '.tar.gz')
OUT = B / 'independent-package-checks.json'
REVIEWED = Path('/private/tmp/c2-image25-adaptation-20260911/user-agent-fix/reviewed-production-python-manifest.json')
ENV = {'PATH': '/usr/bin:/bin', 'TMPDIR': '/private/tmp', 'PYTHONDONTWRITEBYTECODE': '1'}
result = {'status': 'IN_PROGRESS', 'source_commit': COMMIT, 'version': VERSION,
          'started_at': datetime.now(timezone.utc).isoformat(), 'checks': {}, 'findings': []}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def sha(path):
    return digest(path.read_bytes())

def read(path):
    return json.loads(path.read_text())

def save():
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

def check(label, condition, detail=None):
    if not condition:
        result['findings'].append({'check': label, 'detail': detail})
        raise AssertionError(label)

def tree(root):
    files, directories, modes = {}, {'.'}, {'.': stat.S_IMODE(root.lstat().st_mode)}
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        mode = p.lstat().st_mode
        check('ordinary-filesystem-entry:' + str(p), stat.S_ISREG(mode) or stat.S_ISDIR(mode))
        modes[name] = stat.S_IMODE(mode)
        if stat.S_ISDIR(mode):
            directories.add(name)
        else:
            files[name] = sha(p)
    return files, directories, modes

try:
    identity = read(B / 'identity/candidate-build.json')
    snapshot = read(B / 'identity/source-snapshot-manifest.json')
    release = read(P / 'release-manifest.json')
    complete = read(B / 'complete-file-manifest.json')
    mapping = read(B / 'source-package-mapping.json')
    reviewed = read(REVIEWED)
    integrity = read(B / 'package-integrity-result.json')
    protocols = read(B / 'both-model-protocol-result.json')
    expected_ids = {
        P / 'release-manifest.json': '3d35eeeeb3e1b9d89090fa67d5add9b9de0ad76facb66faf965500a724067caf',
        ARCHIVE: '575a768dbc8a43148b0cab069117aa8ca0b0417471b5c49169c390d117f7fdf4',
        B / 'identity/source-snapshot-manifest.json': '00d530d571b5b16a22377427671b8806e208dc4157db38999c945ed34c95059b',
        B / 'complete-file-manifest.json': '24da3c184a5bb0d774b9b01e0d5c1b5174afb48b7f8ee678aa42d90c26c32b0b',
        B / 'source-package-mapping.json': '8eacfd496a2a6d77ef4e2bd73276d47b45b57d7eecd37ac3bc12b8b1a878fdef',
        REVIEWED: '063029558be1d4e21ead8ec2408b0517053c4e74e938c51dc0169f1fe3caeab5',
        C / 'scripts/build-plugin-release.mjs': '217ca2eef5ff9fffb3b68cd9f17621f6d71c0c22e8e43267134f78ba4020d1df',
        B / 'build-candidate.py': '22ef91f06fb321da030d0450ef1e2c60240adc08c122a8d8dc2314a56c1f0713',
    }
    for path, expected in expected_ids.items():
        check('frozen-identity:' + str(path), sha(path) == expected)
    check('source-identities', all(x['source_commit'] == COMMIT for x in [identity, snapshot, complete, mapping, integrity, protocols]))
    check('version-identities', release['plugin_version'] == identity['plugin_version'] == complete['version'] == integrity['version'] == VERSION)
    before_files, before_dirs, before_modes = tree(P)
    check('exact-release-file-map', before_files == {**release['files'], 'release-manifest.json': sha(P / 'release-manifest.json')})
    check('exact-complete-file-map', before_files == complete['files'])
    check('file-counts', len(before_files) == 3765 and len(release['files']) == 3764)
    result['checks']['identities_and_package'] = {'status': 'PASS', 'files_including_manifest': len(before_files),
        'release_manifest_entries': len(release['files']), 'directories_including_root': len(before_dirs),
        'frozen_hashes': {str(k): v for k, v in expected_ids.items()}, 'files': before_files}

    # A prior attempt to recursively read the historical tree failed with the
    # repository's known dataless mmap limitation. Do not repeat or repair it.
    head = subprocess.run(['/usr/bin/git', 'rev-parse', 'HEAD'], cwd=W,
        env={**ENV, 'GIT_OPTIONAL_LOCKS': '0'}, capture_output=True, timeout=20, check=True)
    check('current-head-identity', head.stdout.decode().strip() == COMMIT)
    current_index = subprocess.run(['/usr/bin/git', 'ls-files', '--stage', '-z'], cwd=W,
        env={**ENV, 'GIT_OPTIONAL_LOCKS': '0'}, capture_output=True, timeout=20, check=True)
    raw_index = (B / 'git-ls-files-stage.z').read_bytes()
    check('captured-index-hash', digest(raw_index) == snapshot['index_sha256'])
    check('current-index-equals-captured-index', current_index.stdout == raw_index)
    index_entries = {}
    for row in raw_index.split(b'\0'):
        if not row:
            continue
        meta, name = row.split(b'\t', 1)
        mode, object_id, stage = meta.decode().split()
        check('index-stage-zero-regular-blob', stage == '0' and mode in ('100644', '100755'))
        index_entries[name.decode()] = {'mode': mode, 'blob': object_id}
    check('snapshot-index-exact-set', set(snapshot['files']) == set(index_entries) and len(index_entries) == 921)
    for name, expected in snapshot['files'].items():
        path = S / name
        check('snapshot-regular:' + name, stat.S_ISREG(path.lstat().st_mode))
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        check('snapshot-content:' + name, sha(path) == expected['sha256'] and len(data) == expected['bytes']
              and blob == expected['observed_blob_sha1'] == expected['index_blob_sha1'] == index_entries[name]['blob'])
        check('snapshot-mode:' + name, expected['git_mode'] == index_entries[name]['mode']
              and bool(path.stat().st_mode & 0o111) == (expected['git_mode'] == '100755'))
        check('snapshot-path-binding:' + name, expected['snapshot_path'] == str(path) and expected['source_path'] == str(W / name))
    result['checks']['source_snapshot'] = {'status': 'PASS_WITH_KNOWN_HISTORY_READ_LIMIT', 'tracked_files': len(index_entries),
        'current_head': head.stdout.decode().strip(), 'current_index_equals_captured_index': True,
        'all_sha256_sizes_blob_sha1_and_executable_bits_match': True, 'captured_index_sha256': digest(raw_index),
        'historical_recursive_tree_read': 'NotEstablished',
        'historical_tree_attempt': {'exit_code': 128, 'error': 'fatal: mmap failed: Resource deadlock avoided',
            'partial_root_entries_observed': 7, 'complete_tree_proof': False,
            'attempt_record': str(B / 'independent-package-attempt1-git-read-limit.json')},
        'historical_tree_retry_after_controller_instruction': False, 'git_database_mutation': False}

    dependencies = {k: v for k, v in release['files'].items() if k.startswith('node_modules/')}
    direct = {k: v for k, v in release['files'].items() if k not in dependencies and k != 'widget/dist/index.html'}
    check('first-party-map-exact-set', set(direct) == set(mapping['files']) and len(direct) == 141)
    differences = []
    for name, expected in direct.items():
        source_hash = sha(C / name)
        m = mapping['files'][name]
        check('source-package-mapping-hashes:' + name, m['source_sha256'] == source_hash and m['package_sha256'] == expected)
        if source_hash != expected:
            differences.append(name)
            check('only-descriptor-different', name == '.codex-plugin/plugin.json' and m['allowed_difference'] == 'version only')
            old_descriptor, new_descriptor = read(C / name), read(P / name)
            check('candidate-descriptor-version', new_descriptor['version'] == VERSION)
            new_descriptor['version'] = old_descriptor['version']
            check('descriptor-json-version-only', new_descriptor == old_descriptor)
        else:
            check('no-extra-allowed-difference:' + name, m['allowed_difference'] is None)
    check('exact-difference-set', differences == ['.codex-plugin/plugin.json'])
    widget = sha(P / 'widget/dist/index.html')
    check('widget-generated-output', widget == sha(C / 'widget/dist/index.html') == mapping['widget']['sha256'])
    for root in (P, C):
        py_files = {p.relative_to(root / 'src').as_posix(): sha(p) for p in (root / 'src').rglob('*.py')}
        check('production-python-complete-set:' + str(root), py_files == reviewed['files'] and len(py_files) == 104)
    old = Path('/private/tmp/c2-candidate-edb12848-20260910/plugin-release/ai-ppt-studio')
    old_manifest = read(old / 'release-manifest.json')['files']
    actual_old_dependencies = {'node_modules/' + k: v for k, v in tree(old / 'node_modules')[0].items()}
    check('dependencies-exact-prior-bytes', dependencies == actual_old_dependencies == {k:v for k,v in old_manifest.items() if k.startswith('node_modules/')} and len(dependencies) == 3622)
    check('lockfile-identity', sha(P / 'package-lock.json') == sha(C / 'package-lock.json') == sha(old / 'package-lock.json') == mapping['production_dependencies']['lockfile_sha256'])
    result['checks']['source_package_mapping'] = {'status': 'PASS', 'first_party_files': len(direct),
        'byte_differences': differences, 'descriptor_difference': 'JSON version only', 'widget_sha256': widget,
        'production_python_count': len(reviewed['files']), 'reviewed_production_python_manifest_sha256': sha(REVIEWED),
        'dependencies': len(dependencies), 'dependencies_equal_actual_previous_candidate_and_manifest': True,
        'lockfile_sha256': sha(P / 'package-lock.json')}

    tar_files, tar_dirs, tar_modes, seen = {}, set(), {}, set()
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            name = member.name
            path = PurePosixPath(name)
            check('safe-tar-member:' + name, not path.is_absolute() and '..' not in path.parts
                  and path.as_posix() == name and path.parts[0] == 'ai-ppt-studio')
            check('unique-tar-member:' + name, name not in seen)
            seen.add(name)
            check('ordinary-tar-member:' + name, member.isfile() or member.isdir())
            rel = path.relative_to('ai-ppt-studio').as_posix()
            tar_modes[rel] = member.mode
            if member.isdir():
                tar_dirs.add(rel)
            else:
                with archive.extractfile(member) as stream:
                    tar_files[rel] = digest(stream.read())
    check('archive-exact-files-and-bytes', tar_files == before_files)
    check('archive-exact-directories', tar_dirs == before_dirs)
    check('archive-exact-modes', tar_modes == before_modes)
    check('archive-counts', len(members) == 4360 and len(tar_files) == 3765)
    result['checks']['archive'] = {'status': 'PASS', 'sha256': sha(ARCHIVE), 'member_count': len(members),
        'regular_files': len(tar_files), 'directories': len(tar_dirs), 'unique_safe_members_only': True,
        'unsupported_members': 0, 'full_file_directory_mode_and_content_equality': True, 'extracted': False}

    wrapper = P / 'src/ai_ppt_studio/adapters/image2_crs.py'
    adapter = P / 'src/ai_ppt_studio/adapters/image2_command.py'
    check('reviewed-wrapper-hash', sha(wrapper) == 'b97a56cebff7d07c648e54aaa868f3c8f4eda8b613bef21f87493d8e8509d48f')
    check('reviewed-adapter-hash', sha(adapter) == '67596266dca62af52c5a4730e3cbba0132d1bbbd12fdd8fe2a6b1380cc2a1a5b')
    parsed = ast.parse(wrapper.read_text())
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in parsed.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    check('fixed-user-agent', constants['USER_AGENT'] == 'AI-PPT-Studio/0.4.0')
    check('exact-model-constants', constants['MODEL'] == 'gpt-image-2' and constants['SUNBURST_MODEL'] == 'gpt-image-2.5-sunburst')
    functions = {n.name: n for n in parsed.body if isinstance(n, ast.FunctionDef)}
    preflight_calls = sorted({ast.unparse(n.func) for n in ast.walk(functions['preflight']) if isinstance(n, ast.Call)})
    check('stat-only-preflight-calls', set(preflight_calls) == {'InvalidTransport', 'envelope.get', 'exact', 'os.access', 'os.path.isfile', 'set', 'text'})
    generate_text = ast.unparse(functions['generate'])
    check('root-response-model-exact-equality', "'model' in value and value['model'] != model" in generate_text)
    check('single-image-response-model-exact-equality', "'model' in item and item['model'] != model" in generate_text and "item = value['data'][0]" in generate_text)
    adapter_text = ast.unparse(ast.parse(adapter.read_text()))
    check('adapter-receipt-model-exact-equality', "response['model'] != self.model" in adapter_text)
    result['checks']['reviewed_contract'] = {'status': 'PASS', 'wrapper_sha256': sha(wrapper), 'adapter_sha256': sha(adapter),
        'user_agent': constants['USER_AGENT'], 'strict_response_model_locations': ['root.model', 'data[0].model'],
        'strict_adapter_receipt_model_equality': True, 'preflight_calls': preflight_calls,
        'model_alias_or_snapshot_normalization_added': False}

    independent_cwd = Path(tempfile.mkdtemp(prefix='c2-independent-package-preflight-'))
    probes = []
    for label, model, selector in [('image2', 'gpt-image-2', []), ('sunburst', 'gpt-image-2.5-sunburst', ['--model', 'gpt-image-2.5-sunburst'])]:
        for version in ['v1', 'v2']:
            nonce = 'independent-392642f-' + label + '-' + version + '-' + uuid.uuid4().hex
            request = {'protocol': 'image-led-image2-preflight/' + version, 'request_id': nonce}
            if version == 'v2':
                request['generation_protocol'] = 'image-led-image2-transport/v2'
            argv = [Y, str(wrapper), *selector, '--preflight']
            proc = subprocess.run(argv, input=json.dumps(request), cwd=independent_cwd, env=ENV,
                text=True, capture_output=True, timeout=20)
            check('independent-preflight-exit:' + label + version, proc.returncode == 0 and proc.stderr == '')
            response = json.loads(proc.stdout)
            expected = {**request, 'receiver': 'CRS', 'model': model, 'helper_executable': True, 'external_connection': 'not-tested'}
            check('independent-preflight-exact-response:' + label + version, response == expected and type(response['helper_executable']) is bool)
            probes.append({'label': label, 'version': version, 'argv': argv, 'request': request,
                'response': response, 'exit_code': proc.returncode, 'stdout_sha256': digest(proc.stdout.encode()), 'stderr_empty': True})
    check('independent-cwd-remains-empty', list(independent_cwd.iterdir()) == [])
    check('package-files-directories-modes-unchanged-after-probes', tree(P) == (before_files, before_dirs, before_modes))
    result['checks']['independent_preflights'] = {'status': 'PASS', 'count': len(probes), 'cwd': str(independent_cwd),
        'environment': ENV, 'probes': probes, 'package_and_empty_cwd_unchanged': True,
        'external_connection': 'not-tested', 'provider_authentication': 'not-tested',
        'helper_executable_observation_only': True, 'http_and_helper_execution_in_review': 'NotRun',
        'proof_boundary': 'Only reviewed stat-only wrapper branches invoked; no syscall tracing was performed.'}

    execution_logs = []
    for filename in ['build-execution.json', 'package-execution.json', 'protocol-execution.json']:
        for item in read(B / filename):
            check('execution-log-hash:' + item['label'], sha(Path(item['log'])) == item['sha256'])
            expected_exit = 1 if '-rejected-' in item['label'] else 0
            check('execution-log-exit:' + item['label'], item['exit_code'] == expected_exit)
            execution_logs.append({'execution_file': filename, 'label': item['label'], 'exit_code': item['exit_code'], 'log_sha256': item['sha256']})
    check('package-proof-boundaries', integrity['installation'] == integrity['restart'] == 'NotRun'
          and integrity['real_host'] == 'NotEstablished' and integrity['provider_calls_in_this_task'] == 0
          and integrity['source_full_suites_this_task'] == 'NotRun')
    formal = integrity['formal_verifier_result']
    check('formal-result-matches-log', formal == read(B / 'verify-final.log') and formal['ok'] is True and formal['probe']['tool_count'] == 43)
    professional = formal['probe']['professional_review']
    check('formal-host-proof-not-established', all(professional[k]['realHostEvidence'] is False for k in ['host_open', 'host_notification', 'ai_receipt']))
    check('protocol-proof-boundaries', protocols['installation'] == 'NotRun' and protocols['real_host'] == 'NotEstablished'
          and protocols['provider_authentication'] == 'not-tested' and protocols['helper_execution'] == protocols['http_calls'] == 0)
    stdio_results = []
    for label, entry in zip(['image2', 'sunburst'], protocols['models']):
        path = B / (label + '-stdio-result.json')
        d = read(path)
        check('stdio-result-hash:' + label, sha(path) == entry['stdio_result_sha256'])
        check('stdio-result-equals-log:' + label, d == read(B / (label + '-actual-stdio.log')))
        check('stdio-evidence-boundary:' + label, d['status'] == 'PASS' and d['tool_count'] == 43
              and d['transport'] == 'actual-stdio-child-process-of-isolated-probe' and d['customer_runtime_access'] is False
              and d['host_installation'] is False and d['real_host_loading'] is False and d['provider_authentication'] == 'not-tested')
        stdio_results.append({'path': str(path), 'sha256': sha(path), 'status': d['status'], 'tool_count': d['tool_count'], 'real_host_loading': False})
    evidence = W / '产品代码/docs/validation/c2-image-led/successor-candidate-392642f'
    provider_receipts = []
    for name in ['ua-generation-receipt.json', 'ua-double-edit-receipt.json', 'model-diagnostic-receipt.json']:
        d = read(evidence / name)
        check('provider-failure-boundary:' + name, d['status'] == 'failed-no-retry-result-may-be-unknown'
              and d['wrapper_exit_code'] == 1 and d['response_observed']['http_status'] == 200
              and d['response_observed']['all_explicit_models_match'] is False
              and d['formal_runtime_or_current_host_proof'] is False and d['customer_data_sent'] is False)
        provider_receipts.append({'path': str(evidence / name), 'sha256': sha(evidence / name),
            'status': d['status'], 'requested_model': d['model'], 'request_size': d['request_observed_before_open']['size'],
            'response_observed': d['response_observed'], 'unaccepted_diagnostic_image': d.get('unaccepted_diagnostic_image')})
    diagnostic = read(evidence / 'model-diagnostic-receipt.json')
    check('latest-diagnostic-preserves-rejection', diagnostic['response_observed']['explicit_model_metadata'] == [{'value': 'gpt-image-2-codex', 'type': 'str'}]
          and diagnostic['unaccepted_diagnostic_image']['accepted'] is False and diagnostic['unaccepted_diagnostic_image']['dimensions'] == [1536,1024])
    check('diagnostic-png-not-in-package', diagnostic['unaccepted_diagnostic_image']['sha256'] not in before_files.values())
    ledger = W / '产品代码/docs/validation/c2-image-led/verification-report.md'
    ledger_text = ledger.read_text()
    check('ledger-preserves-provider-block', 'local-package-ready-provider-blocked' in ledger_text and '禁止安装、重启、发布或客户写入' in ledger_text)
    result['checks']['execution_and_evidence_boundary'] = {'status': 'PASS', 'existing_execution_logs_verified': execution_logs,
        'existing_formal_and_stdio_results_reviewed_not_rerun': stdio_results,
        'existing_package_negatives': integrity['package_negative_probes'], 'existing_archive_negatives': integrity['archive_negative_probes'],
        'provider_receipts_reviewed_not_reexecuted': provider_receipts, 'diagnostic_png_not_in_package': True,
        'latest_ledger': str(ledger), 'latest_ledger_sha256_at_review': sha(ledger),
        'full_source_or_ui_suites_in_this_review': 'NotRun', 'current_desktop_host': 'NotEstablished',
        'installation': 'PROHIBITED', 'external_provider_capability': 'BLOCKED'}
    result['status'] = 'PASS'
    result['candidate_state'] = 'local-package-ready-provider-blocked'
except Exception as exc:
    result['status'] = 'FAIL'
    result['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
finally:
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['checker_sha256'] = sha(Path(__file__))
    save()
    print(json.dumps({'status': result['status'], 'output': str(OUT), 'output_sha256': sha(OUT),
        'checks': list(result['checks']), 'findings': result['findings'], 'exception': result.get('exception')}, ensure_ascii=False))
    if result['status'] != 'PASS':
        raise SystemExit(1)
