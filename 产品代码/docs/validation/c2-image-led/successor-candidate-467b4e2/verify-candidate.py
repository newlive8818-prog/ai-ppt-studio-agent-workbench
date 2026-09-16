from pathlib import Path
import hashlib,json,subprocess,time
B=Path('/private/tmp/c2-candidate-467b4e2-20260911'); S=B/'source/产品代码';P=B/'plugin-release/ai-ppt-studio'; E=B/'empty-cwd'
Y='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';N='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
VERSION='0.4.0+codex.c2.467b4e2.20260911';COMMIT='467b4e2bafde0ca44b301ddb6f3fe934c79bc920';REVIEWED=Path('/private/tmp/c2-image2-compat-20260911/reviewed-production-python-manifest.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def tree(root):
    files={}
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink(),str(p)
        if p.is_file(): files[str(p.relative_to(root))]=sha(p)
    return files
assert P.is_dir();E.mkdir(exist_ok=True)
manifest=read(P/'release-manifest.json');before=tree(P);mh=sha(P/'release-manifest.json');assert before=={**manifest['files'],'release-manifest.json':mh};assert manifest['plugin_version']==VERSION
mapping={};deps={}
for name,digest in manifest['files'].items():
    if name.startswith('node_modules/'):deps[name]=digest;continue
    if name=='widget/dist/index.html':continue
    source=S/name;assert source.is_file(),name
    if name=='.codex-plugin/plugin.json':
        original,current=read(source),read(P/name);assert current['version']==VERSION;current['version']=original['version'];assert current==original
    else:assert sha(source)==digest,name
    mapping[name]={'source_sha256':sha(source),'package_sha256':digest,'allowed_difference':'version only' if name=='.codex-plugin/plugin.json' else None}
assert sha(S/'widget/dist/index.html')==sha(P/'widget/dist/index.html')
reviewed=read(REVIEWED)['files']; actual={str(p.relative_to(P/'src')):sha(p) for p in sorted((P/'src').rglob('*.py'))};assert actual==reviewed;assert len(actual)==105
old=read(Path('/private/tmp/c2-candidate-392642f-20260911/plugin-release/ai-ppt-studio/release-manifest.json'))['files'];assert deps=={k:v for k,v in old.items() if k.startswith('node_modules/')}
write(B/'source-package-mapping.json',{'source_commit':COMMIT,'files':mapping,'source_file_count':len(mapping),'reviewed_production_python':{'manifest_sha256':sha(REVIEWED),'all_package_files_match':True,'count':105},'widget':{'path':'widget/dist/index.html','sha256':sha(P/'widget/dist/index.html'),'equals_fresh_build':True},'production_dependencies':{'file_count':len(deps),'all_hashes_equal_prior_reviewed_candidate':True,'lockfile_sha256':sha(P/'package-lock.json'),'built_with_offline_npm_ci':True}})
write(B/'complete-file-manifest.json',{'source_commit':COMMIT,'version':VERSION,'files':before,'total_files':len(before),'dependency_files':len(deps)})
checks=[];env={'PATH':str(Path(N).parent)+':'+str(Path(Y).parent)+':/usr/bin:/bin','TMPDIR':'/private/tmp','PYTHONDONTWRITEBYTECODE':'1','AI_PPT_PYTHON':Y,'AI_PPT_PLUGIN_VALIDATOR':'/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/plugin-creator/scripts/validate_plugin.py','PYTHONPATH':'/private/tmp/c2-python-deps'}
def run(label,args):
    start=time.monotonic();log=B/(label+'.log')
    with log.open('x') as stream: result=subprocess.run(args,cwd=E,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
    entry={'label':label,'argv':args,'cwd':str(E),'environment':env,'exit_code':result.returncode,'elapsed_s':round(time.monotonic()-start,3),'log':str(log),'sha256':sha(log)};checks.append(entry);write(B/'package-execution.json',checks);print(json.dumps(entry),flush=True)
    assert result.returncode==0,log.read_text()[-2000:]
    return log
formal=run('verify-final',[N,str(S/'scripts/verify-plugin-release.mjs'),'--release',str(P)])
archive=B/f'ai-ppt-studio-{VERSION}.tar.gz'
archive_log=run('archive',[Y,'/private/tmp/c2-candidate-392642f-20260911/archive-guard.py','build',str(P),str(archive)])
assert tree(P)==before
write(B/'package-integrity-result.json',{'status':'PASS','scope':'candidate static packaging and isolated stdio verification','source_commit':COMMIT,'version':VERSION,'plugin_root':str(P),'manifest_sha256':mh,'file_count':len(manifest['files']),'file_count_including_manifest':len(before),'complete_file_manifest_sha256':sha(B/'complete-file-manifest.json'),'source_mapping_sha256':sha(B/'source-package-mapping.json'),'source_files':len(mapping),'dependencies':len(deps),'wrapper_sha256':sha(P/'src/ai_ppt_studio/adapters/image2_crs.py'),'archive_path':str(archive),'archive':read(archive_log),'formal_verifier_result':read(formal),'all_package_bytes_unchanged':True,'package_negative_probes_this_candidate':'NotRun - unchanged guards covered in source full Node run','archive_negative_probes_this_candidate':'NotRun - unchanged archive guard previously tested','installation':'NotRun','restart':'NotRun','provider_calls_in_this_task':0,'real_host':'NotEstablished','source_full_suites_this_package_task':'NotRun - separately bound source verification'})
print(json.dumps({'status':'PASS','files':len(before),'source_files':len(mapping),'dependencies':len(deps),'manifest_sha256':mh,'archive_sha256':sha(archive)}))
