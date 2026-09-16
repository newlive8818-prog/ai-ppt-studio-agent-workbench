"""Exercise evidence archive verification; all mutations use new temp archives."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tarfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    guard_path, plugin, archive_path, output = sys.argv[1:]
    spec = importlib.util.spec_from_file_location('archive_guard', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    root = Path(plugin)
    target = Path(archive_path)
    original_hash = digest(target)
    cases = []
    definitions = [
        ('extra-member', 'ARCHIVE_MEMBER_SET_MISMATCH'),
        ('duplicate-member', 'ARCHIVE_DUPLICATE_MEMBER'),
        ('changed-member-bytes', 'ARCHIVE_MEMBER_HASH_MISMATCH'),
    ]
    for name, rejection in definitions:
        altered = Path(output) / ('archive-negative-' + name + '.tar.gz')
        assert not altered.exists()
        changed = False
        with tarfile.open(target) as source, tarfile.open(altered, 'x:gz') as out:
            for member in source.getmembers():
                info = copy.copy(member)
                data = source.extractfile(member).read() if member.isfile() else None
                if name == 'changed-member-bytes' and member.isfile() and not changed:
                    data = b'synthetic changed archive bytes\n'
                    info.size = len(data)
                    changed = True
                out.addfile(info, io.BytesIO(data) if data is not None else None)
            if name in ('extra-member', 'duplicate-member'):
                relative = root.name + ('/unexpected-extra.txt' if name == 'extra-member' else '/release-manifest.json')
                data = b'synthetic extra member\n'
                info = tarfile.TarInfo(relative)
                info.size = len(data)
                out.addfile(info, io.BytesIO(data))
        if name == 'changed-member-bytes':
            assert changed
        try:
            guard.verify_archive(root, altered)
        except ValueError as error:
            assert str(error) == rejection, (name, str(error))
        else:
            raise AssertionError('Expected archive refusal: ' + name)
        cases.append({'case': name, 'rejection': rejection, 'result': 'PASS', 'archive': str(altered), 'sha256': digest(altered)})
    assert digest(target) == original_hash
    assert guard.verify_archive(root, target)['status'] == 'PASS'
    print(json.dumps({'cases': cases, 'current_candidate_archive_sha256': original_hash, 'candidate_preserved': True}, sort_keys=True))


if __name__ == '__main__':
    main()
