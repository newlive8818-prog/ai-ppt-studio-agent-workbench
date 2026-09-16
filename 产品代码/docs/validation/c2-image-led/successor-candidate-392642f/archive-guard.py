"""L1 evidence-only portable archive builder and exact manifest verifier."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_archive(plugin_root, archive_path):
    root = Path(plugin_root)
    with tarfile.open(archive_path, 'x:gz') as archive:
        for entry in [root, *sorted(root.rglob('*'))]:
            if entry.is_symlink():
                raise ValueError('ARCHIVE_SYMLINK_SOURCE')
            archive.add(entry, arcname=str(entry.relative_to(root.parent)), recursive=False)


def verify_archive(plugin_root, archive_path):
    root = Path(plugin_root)
    prefix = root.name
    manifest_bytes = (root / 'release-manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if 'release-manifest.json' in manifest['files']:
        raise ValueError('ARCHIVE_MANIFEST_SELF_REFERENCE')
    expected = {prefix + '/' + name: checksum for name, checksum in manifest['files'].items()}
    expected[prefix + '/release-manifest.json'] = digest(manifest_bytes)
    allowed_dirs = {prefix}
    for name in expected:
        allowed_dirs.update(str(parent) for parent in PurePosixPath(name).parents if str(parent) != '.')
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names):
            raise ValueError('ARCHIVE_DUPLICATE_MEMBER')
        files = {}
        for member in members:
            if member.isdir():
                if member.name not in allowed_dirs:
                    raise ValueError('ARCHIVE_UNEXPECTED_DIRECTORY')
            elif member.isfile():
                files[member.name] = member
            else:
                raise ValueError('ARCHIVE_UNSUPPORTED_MEMBER')
        if set(files) != set(expected):
            raise ValueError('ARCHIVE_MEMBER_SET_MISMATCH')
        for name, member in files.items():
            if digest(archive.extractfile(member).read()) != expected[name]:
                raise ValueError('ARCHIVE_MEMBER_HASH_MISMATCH')
    return {
        'status': 'PASS',
        'archive_sha256': digest(Path(archive_path).read_bytes()),
        'manifest_sha256': digest(manifest_bytes),
        'verified_file_count': len(expected),
        'member_count': len(members),
        'extra_files': 0,
        'duplicate_members': 0,
        'unsupported_members': 0,
    }


if __name__ == '__main__':
    action, plugin, archive = sys.argv[1:]
    if action == 'build':
        write_archive(plugin, archive)
    elif action != 'verify':
        raise ValueError('ARCHIVE_UNKNOWN_ACTION')
    print(json.dumps(verify_archive(plugin, archive), sort_keys=True))
