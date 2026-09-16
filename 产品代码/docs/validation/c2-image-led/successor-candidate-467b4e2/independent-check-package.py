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

B = Path('/private/tmp/c2-candidate-467b4e2-20260911')
W = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
S = B / 'source'
C = S / '产品代码'
P = B / 'plugin-release/ai-ppt-studio'
Y = '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
COMMIT = '467b4e2bafde0ca44b301ddb6f3fe934c79bc920'
VERSION = '0.4.0+codex.c2.467b4e2.20260911'
ARCHIVE = B / ('ai-ppt-studio-' + VERSION + '.tar.gz')
OUT = B / 'independent-package-checks.json'
REVIEWED = Path('/private/tmp/c2-image2-compat-20260911/reviewed-production-python-manifest.json')
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
        P / 'release-manifest.json': '3e88d785551c28909e8a66c5de6af4099e7ec5f5ef22b36696b2891d61e33c32',
        ARCHIVE: 'd928bb7f13bab4dc7f94987d806d706d6ad019c1cb4571eec38b6544ae2c2398',
        B / 'identity/source-snapshot-manifest.json': 'e968851f085d4bea9baed1b7475f04d3cea367a8b3003a14516b7ad77d4586f8',
        B / 'complete-file-manifest.json': 'bcfeeff75c3cc2ee8bfc069e24e2abf5b09138c003043656d1fd5e578e1a1b52',
        B / 'source-package-mapping.json': 'e546535a21a4c9c98637c6301358ef5cecab431f8d681aaa803656a848b43242',
        REVIEWED: '0bd9348dbaafe60c4d0b64799a53895f3375f44f0db45fd381160d7cacf61c7f',
        C / 'scripts/build-plugin-release.mjs': '217ca2eef5ff9fffb3b68cd9f17621f6d71c0c22e8e43267134f78ba4020d1df',
        B / 'build-candidate.py': '59b7d5b1c2224e5e5849a0d93f2bc0a696c30fcc599f416b35c49e893e936f31',
    }
    for path, expected in expected_ids.items():
        check('frozen-identity:' + str(path), sha(path) == expected)
    check('source-identities', all(x['source_commit'] == COMMIT for x in [identity, snapshot, complete, mapping, integrity, protocols]))
    check('version-identities', release['plugin_version'] == identity['plugin_version'] == complete['version'] == integrity['version'] == VERSION)
    before_files, before_dirs, before_modes = tree(P)
    check('exact-release-file-map', before_files == {**release['files'], 'release-manifest.json': sha(P / 'release-manifest.json')})
    check('exact-complete-file-map', before_files == complete['files'])
    check('file-counts', len(before_files) == 3766 and len(release['files']) == 3765)
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
    check('snapshot-index-exact-set', set(snapshot['files']) == set(index_entries) and len(index_entries) == 1034)
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
        'historical_tree_note': 'Known dataless mmap limitation from earlier review; no historical tree or blob read attempted this review.',
        'complete_historical_tree_proof': False, 'git_database_mutation': False}

    dependencies = {k: v for k, v in release['files'].items() if k.startswith('node_modules/')}
    direct = {k: v for k, v in release['files'].items() if k not in dependencies and k != 'widget/dist/index.html'}
    check('first-party-map-exact-set', set(direct) == set(mapping['files']) and len(direct) == 142)
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
    a = (C / '.codex-plugin/plugin.json').read_text(); b = (P / '.codex-plugin/plugin.json').read_text()
    needle = '"version": ' + json.dumps(read(C / '.codex-plugin/plugin.json')['version'])
    check('descriptor-byte-version-replacement-only', a.count(needle) == 1 and a.replace(needle, '"version": ' + json.dumps(VERSION), 1) == b)
    widget = sha(P / 'widget/dist/index.html')
    check('widget-generated-output', widget == sha(C / 'widget/dist/index.html') == mapping['widget']['sha256'])
    for root in (P, C):
        py_files = {p.relative_to(root / 'src').as_posix(): sha(p) for p in (root / 'src').rglob('*.py')}
        check('production-python-complete-set:' + str(root), py_files == reviewed['files'] and len(py_files) == 105)
    old = Path('/private/tmp/c2-candidate-392642f-20260911/plugin-release/ai-ppt-studio')
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
    check('archive-counts', len(members) == 4361 and len(tar_files) == 3766)
    result['checks']['archive'] = {'status': 'PASS', 'sha256': sha(ARCHIVE), 'member_count': len(members),
        'regular_files': len(tar_files), 'directories': len(tar_dirs), 'unique_safe_members_only': True,
        'unsupported_members': 0, 'full_file_directory_mode_and_content_equality': True, 'extracted': False}

    wrapper = P / 'src/ai_ppt_studio/adapters/image2_crs.py'
    adapter = P / 'src/ai_ppt_studio/adapters/image2_command.py'
    check('reviewed-wrapper-hash', sha(wrapper) == '06a859241b1cc3e29697426dcb2a57cc3cf5cac630e1fb759d84b50e11bfaffb')
    check('reviewed-adapter-hash', sha(adapter) == '1530fc665a6a3544ae8b682be8ab3f139da89f61d6224a2e1717d0ac2160c974')
    parsed = ast.parse(wrapper.read_text())
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in parsed.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    check('fixed-user-agent', constants['USER_AGENT'] == 'AI-PPT-Studio/0.4.0')
    check('exact-model-constants', constants['MODEL'] == 'gpt-image-2' and constants['SUNBURST_MODEL'] == 'gpt-image-2.5-sunburst')
    functions = {n.name: n for n in parsed.body if isinstance(n, ast.FunctionDef)}
    preflight_calls = sorted({ast.unparse(n.func) for n in ast.walk(functions['preflight']) if isinstance(n, ast.Call)})
    check('stat-only-preflight-calls', set(preflight_calls) == {'InvalidTransport', 'envelope.get', 'exact', 'os.access', 'os.path.isfile', 'set', 'text'})
    observation_module = P / 'src/ai_ppt_studio/domains/visual/image_output.py'
    check('new-observation-module-hash', sha(observation_module) == '796fe8c2288a30c6eb4838829f9130bb1b27654c3ac90b758276c81a2ffb694c')
    old_python = {p.relative_to(old / 'src').as_posix(): sha(p) for p in (old / 'src').rglob('*.py')}
    new_python = {p.relative_to(P / 'src').as_posix(): sha(p) for p in (P / 'src').rglob('*.py')}
    changed_python = sorted(k for k in new_python.keys() & old_python.keys() if new_python[k] != old_python[k])
    added_python = sorted(new_python.keys() - old_python.keys())
    unchanged_python = sorted(k for k in new_python.keys() & old_python.keys() if new_python[k] == old_python[k])
    expected_changed = sorted(['ai_ppt_studio/adapters/image2_crs.py', 'ai_ppt_studio/adapters/image2_command.py',
        'ai_ppt_studio/application/image_led_service.py', 'ai_ppt_studio/application/image_led_selection.py',
        'ai_ppt_studio/application/bridge/project.py'])
    check('five-reviewed-python-changes-only', changed_python == expected_changed)
    check('observation-module-only-new-python', added_python == ['ai_ppt_studio/domains/visual/image_output.py'])
    check('other-99-python-unchanged-none-removed', len(unchanged_python) == 99 and not old_python.keys() - new_python.keys())
    check('reviewed-provider-observation-call', 'provider_observation' in functions
          and 'validate_provider_observation' in ast.unparse(functions['provider_observation']))
    adapter_text = ast.unparse(ast.parse(adapter.read_text()))
    check('adapter-receipt-request-model-exact-equality', "response['model'] != self.model" in adapter_text)
    result['checks']['reviewed_contract'] = {'status': 'PASS', 'wrapper_sha256': sha(wrapper), 'adapter_sha256': sha(adapter),
        'observation_module_sha256': sha(observation_module), 'user_agent': constants['USER_AGENT'],
        'reviewed_105_python_exactly_packaged': True, 'changed_python': changed_python, 'added_python': added_python,
        'unchanged_old_python_count': len(unchanged_python), 'strict_adapter_receipt_requested_model_equality': True,
        'allowed_reported_compatibility': 'CRS/gpt-image-2 accepts exact or gpt-image-2-codex; Sunburst exact; engine unproven',
        'preflight_calls': preflight_calls, 'independent_engine_proof': 'NotEstablished'}

    independent_cwd = Path(tempfile.mkdtemp(prefix='c2-independent-package-preflight-'))
    probes = []
    for label, model, selector in [('image2', 'gpt-image-2', []), ('sunburst', 'gpt-image-2.5-sunburst', ['--model', 'gpt-image-2.5-sunburst'])]:
        for version in ['v1', 'v2']:
            nonce = 'independent-467b4e2-' + label + '-' + version + '-' + uuid.uuid4().hex
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
          and integrity['source_full_suites_this_package_task'].startswith('NotRun'))
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
    check('exact-positive-protocol-check-count', protocols['checks_count'] == len(read(B / 'protocol-execution.json')) == 11)
    check('negative-probes-not-misreported', integrity['package_negative_probes_this_candidate'].startswith('NotRun')
          and integrity['archive_negative_probes_this_candidate'].startswith('NotRun'))
    check('formal-package-identity', formal['pluginRoot'] == str(P) and formal['version'] == VERSION
          and formal['releaseManifestSha256'] == sha(P / 'release-manifest.json'))
    check('reused-stdio-script-bytes', sha(B / 'stdio-probe.mjs') == sha(old.parent.parent / 'stdio-probe.mjs'))
    for label, entry in zip(['image2', 'sunburst'], protocols['models']):
        d = read(B / (label + '-stdio-result.json'))
        check('stdio-exact-current-package:' + label, d['plugin_root'] == str(P)
              and d['configured_argv'] == entry['configured_argv'] and d['configured_model'] == entry['model'])
        for v in entry['versions']:
            check('recorded-adapter-and-wrapper-log-contents:' + label + v['version'],
                  v['adapter'] == read(B / (label + '-' + v['version'] + '-adapter.log'))
                  and v['wrapper'] == read(B / (label + '-' + v['version'] + '-wrapper.log')))
    result['checks']['execution_and_evidence_boundary'] = {'status': 'PASS', 'existing_execution_logs_verified': execution_logs,
        'existing_formal_and_stdio_results_reviewed_not_rerun': stdio_results,
        'formal_verifier_bound_to_current_package_and_version': True, 'positive_protocol_checks': 11,
        'package_negative_probes_this_candidate': integrity['package_negative_probes_this_candidate'],
        'archive_negative_probes_this_candidate': integrity['archive_negative_probes_this_candidate'],
        'stdio_script_reused_bytes': True, 'stdio_client_label_is_not_source_identity': True,
        'full_source_or_ui_suites_in_this_review': 'NotRun', 'current_desktop_host': 'NotEstablished',
        'installation': 'NotRun', 'real_provider_http': 'NotRun', 'provider_authentication': 'not-tested',
        'independent_engine_proof': 'NotEstablished',
        'scope_note': 'Only this candidate static/offline records checked; separate controller provider work is not evaluated here.'}
    result['status'] = 'PASS'
    result['candidate_state'] = 'local-package-static-pass-external-proof-not-established'
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
