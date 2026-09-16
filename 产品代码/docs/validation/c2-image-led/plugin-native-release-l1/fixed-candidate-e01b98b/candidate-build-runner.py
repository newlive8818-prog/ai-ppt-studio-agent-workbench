from pathlib import Path
import os,json,hashlib,shutil,subprocess,sys,time,tarfile,importlib.util,datetime
W=Path.cwd();sp=importlib.util.spec_from_file_location('l1env','/private/tmp/c2-l1-env.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
commit=sys.argv[1];assert commit==subprocess.check_output(['git','rev-parse','HEAD']).decode().strip();assert len(commit)==40
base=m.BASE/('candidate-'+commit[:7]+'-r2');base.mkdir();src=base/'source';src.mkdir();archive=base/'source.tar'
with archive.open('wb') as out:subprocess.run(['git','archive','--format=tar',commit],stdout=out,check=True,timeout=60)
with tarfile.open(archive) as t:t.extractall(src,filter='data')
source=src/'产品代码';shutil.copytree(m.SRC/'node_modules',source/'node_modules',symlinks=True)
def sha(b):return hashlib.sha256(b).hexdigest()
freeze=json.loads((W/'产品代码/docs/validation/c2-image-led/plugin-native-release-l1/code-freeze.json').read_text())
for f in freeze['files']:assert sha((src/f['path']).read_bytes())==f['sha256']
env=m.env()
for key in ('PYTHONPATH','PYTHONHOME','AI_PPT_WORKSPACE_CONFIG'):env.pop(key,None)
assert not any(k.startswith('AI_PPT_IMAGE2_') for k in env)
validator_env={**env,'PYTHONPATH':'/private/tmp/c2-python-deps'}
checks=[]
def run(label,args,cwd=source,command_env=None):
 log=base/(label+'.log');start=time.time()
 with log.open('wb') as out:r=subprocess.run(args,cwd=cwd,env=env if command_env is None else command_env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
 rec={'label':label,'command':args,'cwd':str(cwd),'exit_code':r.returncode,'elapsed_seconds':round(time.time()-start,3),'log':str(log),'log_sha256':sha(log.read_bytes())};checks.append(rec);(base/'execution.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rec,ensure_ascii=False),flush=True)
 if r.returncode:print(log.read_text(errors='replace')[-9000:],flush=True);raise SystemExit(r.returncode)
 return log
run('build',[m.NODE,'scripts/build-plugin-release.mjs','--output',str(base/'plugin-release'),'--runtime-root',str(base/'synthetic-runtime')])
plugin=base/'plugin-release/ai-ppt-studio';meta=plugin/'.codex-plugin/plugin.json';old=json.loads(meta.read_text());before=sha(meta.read_bytes());date=subprocess.check_output(['git','show','-s','--format=%cd','--date=format:%Y%m%d',commit]).decode().strip();version='0.4.0+codex.c2.'+commit[:7]+'.'+date;new={**old,'version':version};meta.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n');assert {k:v for k,v in old.items() if k!='version'}=={k:v for k,v in new.items() if k!='version'}
run('refresh-manifest',[m.NODE,'scripts/build-plugin-release.mjs','--refresh-release',str(plugin)])
verify=run('verify-before',[m.NODE,'scripts/verify-plugin-release.mjs','--release',str(plugin)],source,validator_env)
manifest_before=(plugin/'release-manifest.json').read_bytes();verification=json.loads(verify.read_text());assert verification['ok'] and verification['version']==version
# Replay the reviewed standalone test harness from its pinned successful run.
impl=json.loads((W/'产品代码/docs/validation/c2-image-led/plugin-native-release-l1/implementation-report.json').read_text());art=impl['packaged_native_evidence'][0]['artifacts'];harness=base/'harness';harness.mkdir();empty=base/'empty-cwd';empty.mkdir();native=base/'native-check';native.mkdir()
for key,name in [('harness/packaged-native.mjs','packaged-native.mjs'),('harness/image-led-synthetic.mjs','image-led-synthetic.mjs')]:
 origin=Path(art[key]['path']);assert sha(origin.read_bytes())==art[key]['sha256'];shutil.copyfile(origin,harness/name)
assert sha((harness/'image-led-synthetic.mjs').read_bytes())==sha((source/'tests/fixtures/image-led-synthetic.mjs').read_bytes())
native_env={'PATH':str(Path(m.NODE).parent)+':'+str(Path(m.PYTHON).parent)+':/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':'/private/tmp'}
origin_code="import pathlib,sys; sys.path.insert(0,sys.argv[1]); import ai_ppt_studio.application.image_led_results as m; p=pathlib.Path(m.__file__).resolve(); root=pathlib.Path(sys.argv[1]).resolve().parent; assert p.is_relative_to(root/'src'); script=p.parents[3]/'scripts/image-led-native.mjs'; assert script==root/'scripts/image-led-native.mjs' and script.is_file(); print('PACKAGED_PYTHON_ORIGIN_PASS')"
origin_log=run('packaged-python-origin',[m.PYTHON,'-c',origin_code,str(plugin/'src')],empty,native_env)
assert origin_log.read_text().strip()=='PACKAGED_PYTHON_ORIGIN_PASS'
run('native-positive-and-negatives',[m.NODE,str(harness/'packaged-native.mjs'),str(plugin),str(harness/'image-led-synthetic.mjs'),str(native),env['C2_RUNTIME_NODE_MODULES'],m.PYTHON],empty,native_env)
result=json.loads((native/'packaged-native-result.json').read_text());assert result['packaged_native']=='PASS' and result['verified_pages']==3 and len(result['counterexamples'])==9
negative=base/'required-file-negatives.mjs';negative.write_text("""import assert from 'node:assert/strict';
import fs from 'node:fs/promises';import path from 'node:path';import {pathToFileURL} from 'node:url';
const [source,plugin,base]=process.argv.slice(2);
const {refreshPluginReleaseManifest}=await import(pathToFileURL(path.join(source,'scripts/build-plugin-release.mjs')).href);
const {verifyPluginRelease}=await import(pathToFileURL(path.join(source,'scripts/verify-plugin-release.mjs')).href);
const missing=path.join(base,'required-file-negative');await fs.cp(plugin,missing,{recursive:true});await fs.rm(path.join(missing,'scripts/image-led-native.mjs'));await refreshPluginReleaseManifest(missing);
await assert.rejects(verifyPluginRelease(missing,{validator:false,probe:false}),/Release is missing required file: scripts\\/image-led-native\\.mjs/);
const altered=path.join(base,'tampered-negative');await fs.cp(plugin,altered,{recursive:true});await fs.appendFile(path.join(altered,'scripts/image-led-native.mjs'),'\\n// test mutation\\n');
await assert.rejects(verifyPluginRelease(altered,{validator:false,probe:false}),/Release manifest does not exactly match shipped files/);
await fs.writeFile(path.join(base,'required-file-negative-result.json'),JSON.stringify({missing_native_with_fresh_manifest:'PASS',tampered_native:'PASS'}),{flag:'wx'});
""")
run('required-file-negatives',[m.NODE,str(negative),str(source),str(plugin),str(base)],empty)
run('verify-final',[m.NODE,'scripts/verify-plugin-release.mjs','--release',str(plugin)],source,validator_env)
assert (plugin/'release-manifest.json').read_bytes()==manifest_before
manifest=json.loads(manifest_before);mapping=[]
for relative,h in manifest['files'].items():
 p=plugin/relative;assert sha(p.read_bytes())==h
 original=source/relative
 if relative.startswith('node_modules/') or relative=='widget/dist/index.html':continue
 if original.is_file():
  source_hash=sha(original.read_bytes());allowed=relative=='.codex-plugin/plugin.json';assert source_hash==h or allowed,relative;mapping.append({'path':relative,'source_sha256':source_hash,'package_sha256':h,'exact':source_hash==h,'allowed_metadata_difference':'version only' if allowed else None})
assert not any(p.is_symlink() for p in plugin.rglob('*'))
archive=base/('ai-ppt-studio-'+version+'.tar.gz');run('archive',['tar','-czf',str(archive),'-C',str(plugin.parent),'ai-ppt-studio'],empty)
report={'schema':'c2-l1-fixed-plugin-candidate/v1','source_commit':commit,'version':version,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plugin_root':str(plugin),'archive':{'path':str(archive),'sha256':sha(archive.read_bytes())},'manifest':{'path':str(plugin/'release-manifest.json'),'sha256':sha(manifest_before),'file_count':len(manifest['files'])},'metadata_derivation':{'path':'.codex-plugin/plugin.json','source_sha256':before,'package_sha256':sha(meta.read_bytes()),'field':'version','source_version':old['version'],'package_version':version,'all_other_fields_equal':True},'source_file_mapping':mapping,'wrapper_sha256':manifest['files']['src/ai_ppt_studio/adapters/image2_crs.py'],'native_sha256':manifest['files']['scripts/image-led-native.mjs'],'harness_sha256':sha((harness/'packaged-native.mjs').read_bytes()),'fixture_sha256':sha((harness/'image-led-synthetic.mjs').read_bytes()),'packaged_python_origin':'PASS','native_probe_env_keys':sorted(native_env),'native_result':result,'native_result_path':str(native/'packaged-native-result.json'),'native_result_sha256':sha((native/'packaged-native-result.json').read_bytes()),'required_file_negative_result':json.loads((base/'required-file-negative-result.json').read_text()),'package_manifest_unchanged_after_probes':True,'execution':checks,'host_installation_configuration_helper_HTTP_customer_runtime':0,'independent_final_package_review':'pending','real_host_PowerPoint_customer_acceptance':'NotEstablished'}
(base/'candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(m.BASE/'candidate-location.json').write_text(json.dumps({'root':str(base),'report':str(base/'candidate.json'),'report_sha256':sha((base/'candidate.json').read_bytes())},indent=2)+'\n');print(json.dumps({'report':str(base/'candidate.json'),'report_sha256':sha((base/'candidate.json').read_bytes()),'version':version,'file_count':len(manifest['files']),'source_files_mapped':len(mapping),'archive_sha256':report['archive']['sha256']},ensure_ascii=False),flush=True)
