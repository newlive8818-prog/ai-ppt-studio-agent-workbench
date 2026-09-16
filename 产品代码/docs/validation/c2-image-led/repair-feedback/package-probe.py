"""Independent package integrity audit and offline package-only repair probe."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path('/private/tmp/c2-repair-candidate-c5dad25b-20260911')
PACKAGE = ROOT / 'plugin-release/ai-ppt-studio'
BASE_ROOT = Path('/private/tmp/c2-decode-candidate-62813b48-20260911')
BASE = BASE_ROOT / 'plugin-release/ai-ppt-studio'
EVIDENCE = Path('/private/tmp/c2-repair-feedback')
WORKSPACE = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码')
PYTHON = '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
VERSION = '0.4.0+codex.c2.repairc5dad25b.20260911'
NATIVE = ['src/ai_ppt_studio/application/image_led_native.py',
          'src/ai_ppt_studio/application/image_led_results.py',
          'src/ai_ppt_studio/context_compiler.py',
          'src/ai_ppt_studio/domains/visual/compilation.py',
          'src/ai_ppt_studio/domains/visual/image_led.py', 'scripts/image-led-native.mjs',
          'skills/ai-ppt-studio/references/presentations-handoff.md',
          'skills/ai-ppt-studio/references/visual-workflow.md']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def snapshot(root):
    result = {}
    for item in root.rglob('*'):
        assert not item.is_symlink(), 'unexpected package symlink'
        if item.is_file():
            result[item.relative_to(root).as_posix()] = sha(item.read_bytes())
    return result


def check(condition, description):
    if not condition:
        raise AssertionError(description)


def main():
    record = {'scope': 'packaging-integrity-only', 'source_review_owner': '/root/feedback_path_audit',
        'source_audit_performed_here': False, 'package_root': str(PACKAGE), 'version': VERSION,
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'http_or_helper': False,
        'customer_runtime_access': False, 'installed': False, 'full_suite_repeated': False}
    source_path = EVIDENCE / 'source-manifest.json'
    source_hash = sha(source_path.read_bytes())
    check(source_hash == '7dd2e700730465d0af0344228d159fa6c305cb84f1615624c79495cfc4bb3af3', 'frozen source manifest hash')
    source = json.loads(source_path.read_text())
    summary = json.loads((ROOT / 'candidate-summary.json').read_text())
    summary_hash_before = sha((ROOT / 'candidate-summary.json').read_bytes())
    before = snapshot(PACKAGE)
    base_directory_before = snapshot(BASE)
    base_before = json.loads((BASE_ROOT / 'complete-file-manifest.json').read_text())
    check(before == json.loads((ROOT / 'complete-file-manifest.json').read_text()), 'complete manifest differs from actual package')
    check(all(base_directory_before.get(p) == h for p, h in base_before.items()), 'sealed base manifested bytes differ')
    base_extra = {p: h for p, h in base_directory_before.items() if p not in base_before}
    check(all('/__pycache__/' in p and p.endswith('.pyc') for p in base_extra), 'unexplained extra files in sealed base directory')
    release = json.loads((PACKAGE / 'release-manifest.json').read_text())
    base_release = json.loads((BASE / 'release-manifest.json').read_text())
    check(base_before['release-manifest.json'] == 'd374e43b1897dd339e9e12977c38de8d0fd1c62d7f28d9ec3bffb185b923193b', 'sealed base release manifest hash')
    check(release['files'] == {p: h for p, h in before.items() if p != 'release-manifest.json'}, 'release manifest incomplete')
    check(base_release['files'] == {p: h for p, h in base_before.items() if p != 'release-manifest.json'}, 'base release manifest incomplete')
    plugin = json.loads((PACKAGE / '.codex-plugin/plugin.json').read_text())
    base_plugin = json.loads((BASE / '.codex-plugin/plugin.json').read_text())
    check(plugin['version'] == release['plugin_version'] == summary['version'] == VERSION, 'version identity')
    check({k: v for k, v in plugin.items() if k != 'version'} ==
          {k: v for k, v in base_plugin.items() if k != 'version'}, 'plugin metadata changed beyond version')
    overlay = source['production'] + source['references']
    check(len(source['production']) == 9 and len(source['references']) == 2, 'frozen overlay counts')
    check(all(before.get(p) == source['files'][p] for p in overlay), 'frozen source overlay mismatch')
    changed = sorted(p for p in set(before) | set(base_before) if before.get(p) != base_before.get(p))
    expected_changes = sorted(overlay + ['.codex-plugin/plugin.json', 'release-manifest.json'])
    check(changed == expected_changes, 'unexpected package changes outside frozen overlay/version metadata')
    added = sorted(set(before) - set(base_before))
    check(added == ['src/ai_ppt_studio/application/image_led_repair.py', 'src/ai_ppt_studio/domains/visual/image_repair.py'], 'unexpected added files')
    check(not set(base_before) - set(before), 'package file deletion')
    python_files = {p: h for p, h in before.items() if p.startswith('src/') and p.endswith('.py')}
    python_record = json.loads((ROOT / 'production-python-manifest.json').read_text())
    check(python_record == {'count': 108, 'files': python_files}, 'production Python manifest mismatch')
    unchanged_python = {p: h for p, h in python_files.items() if p not in source['production']}
    check(len(unchanged_python) == 99 and all(base_before.get(p) == h for p, h in unchanged_python.items()), 'non-overlay Python differs')
    groups = {}
    for label, prefixes in {'dependencies': ('node_modules/',), 'widget': ('widget/',),
                            'package_metadata': ('package.json', 'package-lock.json')}.items():
        current = {p: h for p, h in before.items() if p.startswith(prefixes)}
        prior = {p: h for p, h in base_before.items() if p.startswith(prefixes)}
        check(current == prior, label + ' changed')
        groups[label] = {'files': len(current), 'unchanged': True}
    native = []
    for name in NATIVE:
        unchanged = before[name] == base_before[name]
        check(unchanged or name in overlay and before[name] == source['files'][name], 'unapproved Native byte change')
        native.append({'path': name, 'base_sha256': base_before[name], 'candidate_sha256': before[name],
                       'status': 'unchanged' if unchanged else 'authorized-frozen-repair-overlay'})
    protected = ['src/ai_ppt_studio/domains/visual/image_led.py',
                 'src/ai_ppt_studio/application/image_led_results.py', 'scripts/image-led-native.mjs']
    parallel = []
    for name in protected:
        check(before[name] == base_before[name], 'parallel Native code entered candidate')
        current_sha = sha((WORKSPACE / name).read_bytes())
        parallel.append({'path': name, 'candidate_sha256': before[name], 'parallel_workspace_sha256': current_sha,
                         'candidate_matches_sealed_base': True, 'parallel_bytes_included': current_sha == before[name]})
    archive = Path(summary['archive'])
    archive_hash = sha(archive.read_bytes())
    check(archive_hash == summary['archive_sha256'] == 'dcdac2905d2dddb28ede9ebfce21caedebdd3942391f60256881a0143962c4ed', 'archive hash')
    tar_manifest, seen = {}, set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            check(not path.is_absolute() and '..' not in path.parts and path.parts[0] == 'ai-ppt-studio', 'unsafe archive path')
            check(member.name not in seen, 'duplicate archive member')
            seen.add(member.name)
            check(member.isfile() or member.isdir(), 'archive special member or link')
            if member.isfile():
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                tar_manifest[relative] = sha(tar.extractfile(member).read())
                check(stat.S_IMODE((PACKAGE / relative).stat().st_mode) == member.mode, 'archive file permissions differ')
    check(tar_manifest == before and len(tar_manifest) == 3769, 'archive file manifest differs from package')
    official = json.loads((ROOT / 'official-plugin-verification.json').read_text())
    check(official['ok'] is True and official['version'] == VERSION
          and official['releaseManifestSha256'] == before['release-manifest.json']
          and official['probe']['ok'] is True and official['probe']['tool_count'] == 43
          and len(set(official['probe']['tools'])) == 43, 'official verification receipt is not bound to candidate')

    child_script = r'''
import base64,hashlib,json,struct,sys,zlib
from email.parser import BytesParser
from email.policy import default
def no_external(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.getaddrinfo'):
        raise AssertionError('external operation forbidden in compile probe')
sys.addaudithook(no_external)
from ai_ppt_studio.adapters import image2_crs,image2_command
from ai_ppt_studio.domains.materials.image_input_v2 import RULES
from ai_ppt_studio.domains.visual.image_repair import build_repair_payload
from ai_ppt_studio.domains.visual.image_output import output_fitness
def png(w,h,rgb):
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+bytes(rgb)*w)*h))+chunk(b'IEND',b'')
raw_target=png(160,90,(21,52,84)); materials=[]
for i,color in enumerate(((60,80,100),(120,130,140))):
    raw=png(32,18,color)
    materials.append({'atom_id':'private-atom-'+str(i),'type':'image','use':'real-material' if i==0 else 'style-reference',
        'content_sha256':hashlib.sha256(raw).hexdigest(),'data_base64':base64.b64encode(raw).decode(),
        'mime_type':'image/png','width':32,'height':18})
base={'payload_version':'image-led-image2-input/v2','receiver':'CRS','model':'gpt-image-2',
    'confirmed_visible_copy':{'copy_version':'image-led-selected-copy/v2','title_item_id':'private-heading',
        'items':[{'item_id':'private-heading','kind':'text','role':'title','text':'Synthetic package title'},
                 {'item_id':'private-body','kind':'text','role':'body','text':'Synthetic package body'}]},
    'page_goal':'Synthetic package probe','common_rules':{'typography_tokens':{'title':'Arial'},
        'color_tokens':{'primary':'#123456'},'fallback_fonts':{'body':'Arial'},'title_bar':'Top title','background':'White'},
    'materials':materials,'required_atom_ids':[],
    'non_visible_semantics':{'context_version':'image-led-semantic-context/v1','purpose':'constraints-only-not-visible-copy',
        'relationship_summary':'Synthetic package probe','rules':RULES,
        'copy_facts':[{'item_id':'private-body','identity':'来源事实','limit_ids':[]}], 'limitations':[],
        'material_use':[{'material_id':m['atom_id'],'image_number':i+1,'use':m['use'],'presence':'optional',
            'purpose':'Synthetic geometric marker','identity':'来源事实','limitations':[]} for i,m in enumerate(materials)]}}
source={'status':'completed','image_base64':base64.b64encode(raw_target).decode(),
    'image_sha256':hashlib.sha256(raw_target).hexdigest(),'image_size':[160,90],'image_mime_type':'image/png'}
local=[{'kind':'missing-item','item_id':'private-heading'},
       {'kind':'replace-item','item_id':'private-body','bbox':[2,20,60,20]},
       {'kind':'remove-extra-text','bbox':[90,50,20,10],'observed_text':'LOCAL_ONLY_SENTINEL'},
       {'kind':'common-rule','rule_key':'color_tokens','bbox':[0,0,160,90]}]
payload=build_repair_payload(base,source,local)
protocol=image2_command.generation_protocol(payload)
url,mime,body=image2_crs.compile_body({'protocol':protocol,'request_id':'package-only-probe','payload':payload})
parts=list(BytesParser(policy=default).parsebytes(('Content-Type: '+mime+'\r\n\r\n').encode()+body).iter_parts())
files=[p.get_payload(decode=True) for p in parts if p.get_filename()]
fields={p.get_param('name',header='content-disposition'):p.get_payload(decode=True).decode() for p in parts if not p.get_filename()}
prompt=json.loads(fields['prompt'])
assert files==[raw_target]+[base64.b64decode(m['data_base64']) for m in materials]
assert [m['image_number'] for m in prompt['materials']]==[2,3]
assert [m['image_number'] for m in prompt['non_visible_semantics']['material_use']]==[2,3]
assert prompt['repair_context']['issues'][0]['item_id']=='text-0001'
assert prompt['repair_context']['issues'][1]['item_id']=='text-0002'
assert 'LOCAL_ONLY_SENTINEL' not in fields['prompt'] and 'private-' not in fields['prompt']
assert output_fitness(payload,[1672,941])['status']=='eligible'
assert output_fitness(payload,[160,90])['status']=='needs-revision'
assert protocol=='image-led-image2-repair-transport/v1' and url==image2_crs.EDITS_URL
assert 'PIL' not in sys.modules
print(json.dumps({'repair_protocol':protocol,'edit_image_count':len(files),'target_first':True,
    'material_numbers':[2,3],'aliases_verified':True,'local_notes_omitted':True,'fitness_unwrap':True,
    'stdlib_only':True,'module_path':image2_crs.__file__}))
'''
    child = subprocess.run([PYTHON, '-S', '-B', '-c', child_script],
        env={'PYTHONPATH': str(PACKAGE / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, timeout=15, check=False, cwd=EVIDENCE)
    check(child.returncode == 0, 'package-only compilation probe: ' + child.stderr.decode('utf-8', errors='replace')[:1000])
    compile_probe = json.loads(child.stdout)
    check(compile_probe['module_path'] == str(PACKAGE / 'src/ai_ppt_studio/adapters/image2_crs.py'), 'probe imported outside candidate package')
    protocol = 'image-led-image2-repair-transport/v1'
    preflight_request = {'protocol': 'image-led-image2-preflight/v2',
        'generation_protocol': protocol, 'request_id': 'package-preflight-only'}
    wrapper = PACKAGE / 'src/ai_ppt_studio/adapters/image2_crs.py'
    preflight = subprocess.run([PYTHON, str(wrapper), '--preflight'],
        input=json.dumps(preflight_request).encode(), capture_output=True, timeout=15, check=False,
        env={'PYTHONDONTWRITEBYTECODE': '1'}, cwd=EVIDENCE)
    check(preflight.returncode == 0 and not preflight.stderr, 'package stat-only preflight failed')
    probe = json.loads(preflight.stdout)
    check(probe['protocol'] == preflight_request['protocol'] and probe['request_id'] == preflight_request['request_id']
          and probe['generation_protocol'] == protocol and probe['receiver'] == 'CRS'
          and probe['model'] == 'gpt-image-2' and probe['external_connection'] == 'not-tested'
          and type(probe['helper_executable']) is bool, 'preflight protocol identity mismatch')
    after, base_after = snapshot(PACKAGE), snapshot(BASE)
    check(after == before and base_after == base_directory_before, 'package/base modified during audit')
    check(sha((ROOT / 'candidate-summary.json').read_bytes()) == summary_hash_before, 'candidate summary modified during audit')
    record.update(status='PASS', source_manifest_sha256=source_hash,
        release_manifest_sha256=before['release-manifest.json'],
        base_release_manifest_sha256=base_before['release-manifest.json'],
        package_file_count=len(before), release_manifest_entries=len(release['files']),
        archive_file_count=len(tar_manifest), archive_sha256=archive_hash, archive_exact=True,
        frozen_overlay={p: before[p] for p in overlay}, changed_files=changed, added_files=added,
        production_python_count=len(python_files), unchanged_python_count=len(unchanged_python),
        unchanged_groups=groups, native_eight=native,
        native_unchanged_count=sum(r['status']=='unchanged' for r in native),
        native_authorized_repair_overlay_count=sum(r['status']!='unchanged' for r in native),
        protected_parallel_native=parallel, official_43_tool_receipt_bound=True,
        compilation_probe=compile_probe, stat_only_preflight=probe,
        package_and_base_unchanged_after_probes=True, candidate_summary_unchanged=True,
        sealed_base_manifested_file_count=len(base_before), sealed_base_actual_file_count=len(base_directory_before),
        sealed_base_extra_cache_files=base_extra,
        clarification='Native baseline set has 6 byte-identical files and 2 explicitly frozen repair overlays: context_compiler.py and visual-workflow.md; do not claim all 8 are byte-identical.')
    (EVIDENCE / 'package-review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    native_rows = '\n'.join('| ' + row['path'] + ' | ' + row['status'] + ' | ' + row['candidate_sha256'] + ' |' for row in native)
    report = f'''# C2 repair candidate packaging integrity review

Result: **PASS for packaging integrity**. Source correctness is reviewed separately by `/root/feedback_path_audit`; this review does not re-review the implementation or establish real-host/customer execution.

Candidate: `{PACKAGE}`
Version: `{VERSION}`
Frozen source manifest SHA256: `{source_hash}`
Release manifest SHA256: `{before['release-manifest.json']}`
Sealed decode base release manifest SHA256: `{base_before['release-manifest.json']}`
Archive SHA256: `{archive_hash}`

All 9 Python overlays and 2 reference documents match the exact frozen source hashes. The remaining 99 Python files match the sealed decode base; production Python count is 108. Only the 11 approved overlays and 2 version/release metadata files differ. The only added files are application/image_led_repair.py and domains/visual/image_repair.py; no base file was removed.

All 3769 actual package files match the complete file manifest. The release manifest covers exactly the other 3768 files. The tar contains exactly the same 3769 file paths/bytes and matching file permissions, with no duplicate entries, unsafe paths, symlinks, hard links or special members. Dependencies, Widget and package metadata are unchanged. The existing official verification receipt is bound to this exact version and release manifest and reports 43 unique tools; the official verifier was not rerun here.

The sealed base directory now has {len(base_directory_before)} actual files: all {len(base_before)} manifested files retain their frozen bytes, plus {len(base_extra)} unmanifested `__pycache__/*.pyc` files. The byte comparison uses exactly the sealed manifest's {len(base_before)} files; these existing cache files are explicitly recorded in package-review.json, were not changed or removed, and are absent from the candidate package. This review does not claim the entire base directory still exactly matches its historical complete manifest.

## Native precision

The historical Native set contains **6 byte-identical files and 2 authorized repair overlays**. `context_compiler.py` and `visual-workflow.md` are explicitly included in the frozen repair source manifest, so saying all 8 files are unchanged would be inaccurate. All other Native set bytes match the sealed base. In particular image_led.py, image_led_results.py and image-led-native.mjs match the sealed base and do not include the current parallel Native edits.

| Native file | Result | Candidate SHA256 |
| --- | --- | --- |
{native_rows}

## Package-only probes

A real independent Python interpreter with `-S -B`, candidate-only PYTHONPATH and an audit hook blocking process/network operations successfully compiled a synthetic repair payload. It loaded the candidate wrapper, validated exact first-image placement, original material bytes/order and both shifted image_number mappings, item aliases, removal of local observation text, and base-unwrapped output fitness. No PIL/site-packages were loaded.

A separate real standalone candidate-wrapper invocation with `--preflight` returned preflight/v2 and the exact repair-transport/v1 protocol, CRS/gpt-image-2 identity and external_connection=not-tested. This was stat-only; no credential helper or HTTP was executed. No customer Runtime was accessed, no installation occurred and the 117-test suite was not repeated.

The complete candidate and sealed base file snapshots, plus candidate-summary.json hash, were unchanged after both probes. Machine-readable details are in package-review.json; this audit is reproducible with package-probe.py.
'''
    (EVIDENCE / 'package-review.md').write_text(report)
    print(json.dumps({'status': record['status'], 'files': len(before), 'python': len(python_files),
        'unchanged_python': len(unchanged_python), 'native_unchanged': record['native_unchanged_count'],
        'native_authorized_repair_overlays': record['native_authorized_repair_overlay_count'],
        'archive_exact': True, 'package_only_probes': 'PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
