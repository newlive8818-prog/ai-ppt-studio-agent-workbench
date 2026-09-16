from pathlib import Path
from hashlib import sha256
import gzip,json,os,shutil,subprocess,tarfile,time
repo=Path.cwd()/'产品代码'
base=Path('/private/tmp/c2-repair-candidate-c5dad25b-20260911/plugin-release/ai-ppt-studio')
root=Path('/private/tmp/c2-native-exact-candidate-04319fcc-20260911'); resume=False; root.mkdir(exist_ok=False)
bundle=root/'plugin-release/ai-ppt-studio'
def digest(p):return sha256(p.read_bytes()).hexdigest()
def files(p):
 out={}
 for f in sorted(p.rglob('*')):
  assert not f.is_symlink(),str(f)
  if f.is_file():out[str(f.relative_to(p))]=digest(f)
  else:assert f.is_dir(),str(f)
 return out
old=files(base); old_manifest=json.loads((base/'release-manifest.json').read_text())
assert digest(base/'release-manifest.json')=='5069897793f8eec016419d895a3316f2c09a684d2478609c7b35c6043f60985b'
assert {k:v for k,v in old.items() if k!='release-manifest.json'}==old_manifest['files']
review_manifest=json.loads(Path('/private/tmp/c2-region-endpoints/package-source-manifest.json').read_text())
reviewed=review_manifest['files']
frozen=Path('/private/tmp/c2-region-endpoints/frozen-source')
for rel,h in reviewed.items():assert digest(frozen/rel)==h,rel
if not resume: shutil.copytree(base,bundle)
changes=review_manifest['production']+review_manifest['references']
for rel in changes:
 (bundle/rel).parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(frozen/rel,bundle/rel)
version='0.4.0+codex.c2.nativeexact04319fcc.20260911'
config=bundle/'.codex-plugin/plugin.json';obj=json.loads(config.read_text());obj['version']=version
config.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
node='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
py='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin'
(root/'tmp').mkdir(exist_ok=True)
env={k:os.environ[k] for k in ['HOME','LANG','LC_ALL'] if k in os.environ}
env.update(PATH=str(Path(node).parent)+':'+py+':/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/private/tmp/c2-python-deps',TMPDIR=str(root/'tmp'))
tools=Path('/private/tmp/c2-candidate-ab13760f-20260911/build-source/scripts')
execution=[]
steps=[('verify','verify-plugin-release.mjs','--release')] if resume else [('refresh','build-plugin-release.mjs','--refresh-release'),('verify','verify-plugin-release.mjs','--release')]
for label,script,flag in steps:
 assert digest(tools/script)==digest(repo/'scripts'/script)
 args=[node,str(tools/script),flag,str(bundle)];start=time.monotonic()
 result=subprocess.run(args,cwd=repo,env=env,capture_output=True,timeout=50)
 (root/(label+'.stdout.log')).write_bytes(result.stdout);(root/(label+'.stderr.log')).write_bytes(result.stderr)
 execution.append({'label':label,'args':args,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3)})
 assert result.returncode==0,{'label':label,'exit':result.returncode,'log':str(root/(label+'.stderr.log'))}
(root/'build-execution.json').write_text(json.dumps(execution,indent=2)+'\n')
verify=json.loads((root/'verify.stdout.log').read_text())
(root/'official-plugin-verification.json').write_text(json.dumps(verify,ensure_ascii=False,indent=2)+'\n')
current=files(bundle);manifest=json.loads((bundle/'release-manifest.json').read_text())
added=sorted(set(current)-set(old)); assert added==sorted(k for k in changes if k not in old); assert not set(old)-set(current); assert len(current)==3769
assert {k:v for k,v in current.items() if k!='release-manifest.json'}==manifest['files']
changed=sorted(k for k in current if current[k]!=old.get(k));assert changed==sorted(changes+['.codex-plugin/plugin.json','release-manifest.json']),changed
assert files(base)==old
source={k:v for k,v in current.items() if k.startswith('src/') and k.endswith('.py')};assert len(source)==108
(root/'production-python-manifest.json').write_text(json.dumps({'count':len(source),'files':source},indent=2)+'\n')
(root/'complete-file-manifest.json').write_text(json.dumps(current,indent=2)+'\n')
archive=root/('ai-ppt-studio-'+version+'.tar.gz')
with archive.open('wb') as f,gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as tar:
 for path in [bundle]+sorted(bundle.rglob('*')):
  info=tar.gettarinfo(str(path),arcname='ai-ppt-studio'+('/'+str(path.relative_to(bundle)) if path!=bundle else ''))
  info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
  if path.is_file():
   with path.open('rb') as data:tar.addfile(info,data)
  else:tar.addfile(info)
seen=set(); archived={}
with tarfile.open(archive,'r:gz') as tar:
 for member in tar:
  assert member.name not in seen and '..' not in Path(member.name).parts and not member.name.startswith('/')
  seen.add(member.name);assert member.isfile() or member.isdir()
  if member.isfile():archived[str(Path(member.name).relative_to('ai-ppt-studio'))]=sha256(tar.extractfile(member).read()).hexdigest()
assert archived==current
summary={'status':'local-package-verified-awaiting-independent-review','plugin_root':str(bundle),'version':version,
 'source_status':'hash-pinned-overlay-pending-review','base_plugin_root':str(base),'base_manifest_sha256':old['release-manifest.json'],
 'native_v3_included':True,'wrapper_sha256':current['src/ai_ppt_studio/adapters/image2_crs.py'],'diagnostics_sha256':current['src/ai_ppt_studio/adapters/image2_diagnostics.py'],
 'release_manifest_sha256':current['release-manifest.json'],'source108_manifest_sha256':digest(root/'production-python-manifest.json'),
 'package_files':len(current),'manifest_entries':len(manifest['files']),'changed_from_repair_base':changed,
 'unchanged_python_files':106,'new_native_region_or_text_gradient_included':True,'repair_feedback_included':True,'unchanged_dependencies_and_widget':True,'official_verify':verify['ok'],
 'tool_count':len(verify['probe']['tools']),
 'archive':str(archive),'archive_sha256':digest(archive),'archive_exact':True,
 'customer_runtime_access':False,'http_or_helper':False,'installed':False}
(root/'candidate-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
