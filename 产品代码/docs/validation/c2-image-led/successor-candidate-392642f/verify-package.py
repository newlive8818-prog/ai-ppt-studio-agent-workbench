from pathlib import Path
import hashlib,json,subprocess,time,os

B=Path('/private/tmp/c2-candidate-392642f-20260911')
S=B/'source/产品代码'; P=B/'plugin-release/ai-ppt-studio'; E=B/'empty-cwd'; E.mkdir(exist_ok=True)
Y='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
N='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
VERSION='0.4.0+codex.c2.392642f.20260911'; COMMIT='392642f2a34afd856b07228d97ce2b3180fdc961'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
env={'PATH':str(Path(N).parent)+':'+str(Path(Y).parent)+':/usr/bin:/bin','TMPDIR':'/private/tmp','PYTHONDONTWRITEBYTECODE':'1','AI_PPT_PYTHON':Y,'AI_PPT_PLUGIN_VALIDATOR':'/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/plugin-creator/scripts/validate_plugin.py'}
checks=[]
def run(label,args,extra=None):
 start=time.time(); log=B/(label+'.log')
 with log.open('x') as out: result=subprocess.run(args,cwd=E,env={**env,**(extra or {})},stdout=out,stderr=subprocess.STDOUT,timeout=240)
 entry={'label':label,'argv':args,'cwd':str(E),'exit_code':result.returncode,'elapsed_s':round(time.time()-start,3),'log':str(log),'sha256':sha(log)}
 checks.append(entry); write(B/'package-execution.json',checks); print(json.dumps(entry),flush=True)
 assert result.returncode==0,log.read_text()[-5000:]
 return log
def tree(root):
 out={}
 for p in sorted(root.rglob('*')):
  assert not p.is_symlink(),str(p)
  if p.is_file(): out[str(p.relative_to(root))]=sha(p)
 return out
manifest=read(P/'release-manifest.json'); before=tree(P); manifest_hash=sha(P/'release-manifest.json')
assert before=={**manifest['files'],'release-manifest.json':manifest_hash}
assert manifest['plugin_version']==VERSION
mapping={}; dependencies={}
for name,digest in manifest['files'].items():
 if name.startswith('node_modules/'):
  dependencies[name]=digest; continue
 if name=='widget/dist/index.html': continue
 source=S/name
 assert source.is_file(),name
 if name=='.codex-plugin/plugin.json':
  a,b=read(source),read(P/name); assert b['version']==VERSION
  b['version']=a['version']; assert a==b
 else: assert sha(source)==digest,name
 mapping[name]={'source_sha256':sha(source),'package_sha256':digest,'allowed_difference':'version only' if name=='.codex-plugin/plugin.json' else None}
assert sha(S/'widget/dist/index.html')==sha(P/'widget/dist/index.html')
reviewed_path=Path('/private/tmp/c2-image25-adaptation-20260911/user-agent-fix/reviewed-production-python-manifest.json')
reviewed=read(reviewed_path)
for name,digest in reviewed['files'].items(): assert sha(P/'src'/name)==digest,name
assert len(reviewed['files'])==104
assert sha(P/'src/ai_ppt_studio/adapters/image2_crs.py')=='b97a56cebff7d07c648e54aaa868f3c8f4eda8b613bef21f87493d8e8509d48f'
assert sha(P/'src/ai_ppt_studio/adapters/image2_command.py')=='67596266dca62af52c5a4730e3cbba0132d1bbbd12fdd8fe2a6b1380cc2a1a5b'
old=Path('/private/tmp/c2-candidate-edb12848-20260910/plugin-release/ai-ppt-studio')
old_manifest=read(old/'release-manifest.json')['files']
assert dependencies=={k:v for k,v in old_manifest.items() if k.startswith('node_modules/')}
write(B/'source-package-mapping.json',{'source_commit':COMMIT,'files':mapping,'source_file_count':len(mapping),'reviewed_production_python':{'manifest_sha256':sha(reviewed_path),'all_package_files_match':True,'count':104},'widget':{'path':'widget/dist/index.html','sha256':sha(P/'widget/dist/index.html'),'equals_fresh_build':True,'full_source_suites_this_task':'NotRun'},'production_dependencies':{'file_count':len(dependencies),'all_hashes_equal_prior_reviewed_candidate':True,'lockfile_sha256':sha(P/'package-lock.json'),'built_with_offline_npm_ci':True}})
write(B/'complete-file-manifest.json',{'source_commit':COMMIT,'version':VERSION,'files':before,'total_files':len(before),'dependency_files':len(dependencies)})
write(B/'prior-candidate-diff.json',{'added':sorted(manifest['files'].keys()-old_manifest.keys()),'removed':sorted(old_manifest.keys()-manifest['files'].keys()),'changed':[{'path':name,'old_sha256':old_manifest[name],'new_sha256':digest} for name,digest in manifest['files'].items() if name in old_manifest and old_manifest[name]!=digest]})
run('package-negative-probes',[N,str(B/'required-file-negatives.mjs'),str(S),str(P),str(B)])
formal=run('verify-final',[N,str(S/'scripts/verify-plugin-release.mjs'),'--release',str(P)],{'PYTHONPATH':'/private/tmp/c2-python-deps'})
archive=B/f'ai-ppt-studio-{VERSION}.tar.gz'
archive_log=run('archive',[Y,str(B/'archive-guard.py'),'build',str(P),str(archive)])
negative=run('archive-negative-probes',[Y,str(B/'archive-negative-probes.py'),str(B/'archive-guard.py'),str(P),str(archive),str(B)])
assert tree(P)==before
write(B/'package-integrity-result.json',{'status':'PASS','scope':'candidate static packaging and isolated stdio verification','source_commit':COMMIT,'version':VERSION,'plugin_root':str(P),'manifest_sha256':manifest_hash,'file_count':len(manifest['files']),'file_count_including_manifest':len(before),'complete_file_manifest_sha256':sha(B/'complete-file-manifest.json'),'source_mapping_sha256':sha(B/'source-package-mapping.json'),'source_files':len(mapping),'dependencies':len(dependencies),'wrapper_sha256':sha(P/'src/ai_ppt_studio/adapters/image2_crs.py'),'archive_path':str(archive),'archive':read(archive_log),'archive_negative_probes':read(negative),'package_negative_probes':read(B/'required-file-negative-result.json'),'formal_verifier_result':read(formal),'all_package_bytes_unchanged':True,'installation':'NotRun','restart':'NotRun','provider_calls_in_this_task':0,'real_host':'NotEstablished','source_full_suites_this_task':'NotRun'})
print(json.dumps(read(B/'package-integrity-result.json'),ensure_ascii=False,indent=2))
