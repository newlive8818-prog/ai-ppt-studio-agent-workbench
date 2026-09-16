"""Authorized local-only candidate packaging; does not validate or install it."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

BASE = Path('/private/tmp/c2-candidate-392642f-20260911')
WORKTREE = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
HEAD = '392642f2a34afd856b07228d97ce2b3180fdc961'
SOURCE = BASE / 'source'
CODE = SOURCE / '产品代码'
PYTHON = Path('/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
NODE = Path('/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
NPM = Path('/opt/homebrew/bin/npm')
CACHE = Path('/private/tmp/c2-candidate-edb12848-20260910/npm-cache')
DEPENDENCIES = Path('/private/tmp/c2-image25-adaptation-20260911/user-agent-fix/repo/产品代码/node_modules')
REVIEWED = Path('/private/tmp/c2-image25-adaptation-20260911/user-agent-fix/reviewed-production-python-manifest.json')
PLUGIN = BASE / 'plugin-release' / 'ai-ppt-studio'
VERSION = '0.4.0+codex.c2.392642f.20260911'


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(relative, value):
    destination = BASE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(['/usr/bin/git', *args], cwd=WORKTREE)


def snapshot():
    if SOURCE.exists() or PLUGIN.exists():
        raise RuntimeError('Refuse to overwrite an existing snapshot or package')
    if git('rev-parse', 'HEAD').decode().strip() != HEAD:
        raise RuntimeError('HEAD is not the authorized commit')
    subprocess.run(['/usr/bin/git', 'diff', '--cached', '--quiet', HEAD, '--'], cwd=WORKTREE, check=True)
    index = git('ls-files', '--stage', '-z')
    (BASE / 'git-ls-files-stage.z').write_bytes(index)
    SOURCE.mkdir(mode=0o700)
    files = {}
    for entry in index.split(b'\0'):
        if not entry:
            continue
        metadata, raw_name = entry.split(b'\t', 1)
        mode, expected, stage = metadata.decode().split()
        relative = raw_name.decode('utf-8')
        if stage != '0' or mode not in {'100644', '100755'}:
            raise RuntimeError('Unexpected staged or non-regular tracked path')
        src = WORKTREE / relative
        if not stat.S_ISREG(src.lstat().st_mode):
            raise RuntimeError('Tracked source is not a regular file: ' + relative)
        raw = src.read_bytes()
        observed = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if observed != expected:
            raise RuntimeError('Current file differs from index blob: ' + relative)
        target = SOURCE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if mode == '100755' else 0o644)
        copied = target.read_bytes()
        if copied != raw:
            raise RuntimeError('Copied source differs: ' + relative)
        files[relative] = {'git_mode': mode, 'index_blob_sha1': expected,
            'observed_blob_sha1': observed, 'sha256': sha256(raw), 'bytes': len(raw),
            'source_path': str(src), 'snapshot_path': str(target)}
    if git('rev-parse', 'HEAD').decode().strip() != HEAD or git('ls-files', '--stage', '-z') != index:
        raise RuntimeError('Source HEAD or index changed during snapshot')
    reviewed = json.loads(REVIEWED.read_text())
    python_root = CODE / 'src'
    actual_python = {str(path.relative_to(python_root)): sha256(path.read_bytes())
        for path in sorted(python_root.rglob('*.py'))}
    if actual_python != reviewed['files'] or len(actual_python) != 104:
        raise RuntimeError('Production Python does not equal the fixed reviewed manifest')
    payload = {'status': 'exact-tracked-source-snapshot', 'source_commit': HEAD,
        'source_worktree': str(WORKTREE), 'snapshot_root': str(SOURCE),
        'tracked_file_count': len(files), 'method': 'current tracked regular bytes checked against index blob SHA1; no git archive or historic-tree extraction',
        'index_sha256': sha256(index), 'reviewed_production_python': {
            'manifest_path': str(REVIEWED), 'manifest_sha256': sha256(REVIEWED.read_bytes()),
            'file_count': len(actual_python), 'exact_match': True, 'files': actual_python},
        'files': files}
    write_json('identity/source-snapshot-manifest.json', payload)
    print(json.dumps({'snapshot': 'ready', 'tracked_files': len(files), 'reviewed_python': len(actual_python)}), flush=True)
    return files


def copy_private_dependencies():
    if DEPENDENCIES.is_symlink() or not DEPENDENCIES.is_dir():
        raise RuntimeError('Expected a private dependency directory, not a shared symlink')
    canonical = DEPENDENCIES.resolve()
    link_map = {}
    file_count = 0
    for directory, names, filenames in os.walk(DEPENDENCIES, followlinks=False):
        for name in names + filenames:
            item = Path(directory) / name
            if item.is_symlink():
                resolved = item.resolve(strict=True)
                if not resolved.is_relative_to(canonical):
                    raise RuntimeError('Dependency symlink escapes the private tree: ' + str(item))
                link_map[str(item.relative_to(DEPENDENCIES))] = str(resolved.relative_to(canonical))
            elif item.is_file():
                file_count += 1
    destination = CODE / 'node_modules'
    shutil.copytree(DEPENDENCIES, destination, symlinks=True)
    # Rebind every audited link to its counterpart in this private copy.
    for relative, target_relative in link_map.items():
        item = destination / relative
        item.unlink()
        item.symlink_to(os.path.relpath(destination / target_relative, item.parent))
        if not item.resolve(strict=True).is_relative_to(destination.resolve()):
            raise RuntimeError('Copied dependency link does not stay private')
    write_json('identity/dependency-copy.json', {'status': 'private-copy',
        'source': str(DEPENDENCIES), 'destination': str(destination),
        'regular_file_count': file_count, 'symlink_count': len(link_map),
        'all_links_rebound_within_private_copy': True, 'link_mapping': link_map})
    print(json.dumps({'private_dependencies': 'ready', 'regular_files': file_count, 'internal_links': len(link_map)}), flush=True)


def main():
    files = snapshot()
    copy_private_dependencies()
    (BASE / 'tmp').mkdir()
    (BASE / 'empty-user.npmrc').write_text('')
    (BASE / 'empty-global.npmrc').write_text('')
    environment = {'PATH': os.pathsep.join([str(NODE.parent), str(PYTHON.parent), '/opt/homebrew/bin', '/usr/bin', '/bin']),
        'LANG': 'en_US.UTF-8', 'TMPDIR': str(BASE / 'tmp'), 'PYTHONDONTWRITEBYTECODE': '1',
        'npm_config_offline': 'true', 'npm_config_audit': 'false', 'npm_config_fund': 'false',
        'npm_config_cache': str(CACHE), 'npm_config_userconfig': str(BASE / 'empty-user.npmrc'),
        'npm_config_globalconfig': str(BASE / 'empty-global.npmrc')}
    execution = []
    def run(label, arguments):
        command = [str(NODE), 'scripts/build-plugin-release.mjs', *arguments]
        log = BASE / (label + '.log')
        start = time.monotonic()
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=CODE, env=environment, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, check=False)
        execution.append({'label': label, 'command': command, 'cwd': str(CODE),
            'environment': environment, 'npm_resolved': str(NPM), 'exit_code': result.returncode,
            'elapsed_s': round(time.monotonic() - start, 3), 'log': str(log), 'sha256': sha256(log.read_bytes())})
        write_json('build-execution.json', execution)
        if result.returncode != 0:
            raise RuntimeError('Build step failed: ' + label)
        print(json.dumps({'step': label, 'exit_code': 0}), flush=True)
    run('build', ['--output', str(BASE / 'plugin-release'), '--runtime-root', str(BASE / 'synthetic-runtime')])
    plugin_file = PLUGIN / '.codex-plugin/plugin.json'
    original = plugin_file.read_bytes()
    plugin = json.loads(original)
    plugin['version'] = VERSION
    plugin_file.write_text(json.dumps(plugin, ensure_ascii=False, indent=2) + '\n')
    write_json('identity/package-version-mutation.json', {'path': str(plugin_file),
        'field': 'version', 'from': json.loads(original)['version'], 'to': VERSION,
        'before_sha256': sha256(original), 'after_sha256': sha256(plugin_file.read_bytes()),
        'source_mutated': False})
    run('refresh-manifest', ['--refresh-release', str(PLUGIN)])
    # This is source-copy integrity, not formal package validation.
    for relative, item in files.items():
        if sha256((SOURCE / relative).read_bytes()) != item['sha256']:
            raise RuntimeError('Build changed a tracked snapshot input: ' + relative)
    manifest_path = PLUGIN / 'release-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    identity = {'status': 'candidate-built-awaiting-controller-static-validation',
        'source_commit': HEAD, 'plugin_version': VERSION, 'plugin_root': str(PLUGIN),
        'source_snapshot_manifest': str(BASE / 'identity/source-snapshot-manifest.json'),
        'source_snapshot_manifest_sha256': sha256((BASE / 'identity/source-snapshot-manifest.json').read_bytes()),
        'release_manifest': str(manifest_path), 'release_manifest_sha256': sha256(manifest_path.read_bytes()),
        'release_manifest_file_count': len(manifest['files']),
        'plugin_descriptor_sha256': sha256(plugin_file.read_bytes()),
        'production_python_count': 104, 'tracked_snapshot_inputs_unchanged_after_build': True,
        'builder_sha256': sha256((CODE / 'scripts/build-plugin-release.mjs').read_bytes()),
        'orchestration_script_sha256': sha256(Path(__file__).read_bytes()),
        'adapter_sha256': {name: sha256((PLUGIN / 'src/ai_ppt_studio/adapters' / name).read_bytes())
            for name in ('image2_crs.py', 'image2_command.py')},
        'formal_package_validation': 'NotRun', 'actual_host_or_installation': 'NotRun',
        'external_http': 'NotRun', 'customer_runtime': 'NotTouched',
        'upstream_note': 'Controller reported HTTP 200 with explicit response model mismatch rejected; this package does not establish external capability.'}
    write_json('identity/candidate-build.json', identity)
    print(json.dumps(identity, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
