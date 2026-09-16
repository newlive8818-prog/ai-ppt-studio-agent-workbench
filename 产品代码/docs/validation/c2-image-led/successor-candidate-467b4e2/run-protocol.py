from pathlib import Path
import os,subprocess,json,hashlib,time,sys,uuid
B=Path('/private/tmp/c2-candidate-467b4e2-20260911'); P=B/'plugin-release/ai-ppt-studio'; E=B/'empty-cwd'; E.mkdir(exist_ok=True); R=B/'stdio-runtime'; R.mkdir(exist_ok=True)
N='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'; Y='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
WRAPPER=P/'src/ai_ppt_studio/adapters/image2_crs.py'
env={'PATH':str(Path(N).parent)+':'+str(Path(Y).parent)+':/usr/bin:/bin','TMPDIR':'/private/tmp','PYTHONDONTWRITEBYTECODE':'1'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def tree(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
package_before=tree(P);checks=[];results=[]
def run(label,args,extra=None,stdin=None,expected=0):
 start=time.time();r=subprocess.run(args,cwd=E,env={**env,**(extra or {})},input=stdin,text=True,capture_output=True,timeout=60)
 log=B/(label+'.log');log.write_text(r.stdout+r.stderr)
 entry={'label':label,'argv':args,'cwd':str(E),'exit_code':r.returncode,'elapsed_s':round(time.time()-start,3),'log':str(log),'sha256':sha(log)};checks.append(entry);write(B/'protocol-execution.json',checks);print(json.dumps(entry),flush=True)
 assert r.returncode==expected,r.stdout+r.stderr
 return r
setup='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ai_ppt_studio.kernel.transactions import ProjectKernel
r=Path(sys.argv[2]);ProjectKernel.initialize(r/'projects/package-probe',project_id='package-probe')
(r/'workspace.json').write_text(json.dumps({'schema_version':'1.0','runtime_root':str(r),'source_repo_root':str(r.parent/'protected-source'),'install_root':str(r.parent/'protected-install'),'upstream_root':str(r.parent/'protected-web'),'protected_roots':[str(r.parent/x) for x in ['protected-source','protected-install','protected-web']]}))
'''
run('stdio-fixture-init',[Y,'-c',setup,str(P/'src'),str(R)])
runtime_before=tree(R)
for label,model,selector in [('image2','gpt-image-2',[]),('sunburst','gpt-image-2.5-sunburst',['--model','gpt-image-2.5-sunburst'])]:
 argv=[Y,str(WRAPPER),*selector]
 configured={'AI_PPT_PYTHON':Y,'AI_PPT_PYTHONPATH':str(P/'src'),'AI_PPT_WORKSPACE_CONFIG':str(R/'workspace.json'),'AI_PPT_IMAGE2_ADAPTER_COMMAND':json.dumps(argv),'AI_PPT_IMAGE2_RECEIVER':'CRS','AI_PPT_IMAGE2_MODEL':model,'AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST':'[]'}
 stdio=B/(label+'-stdio-result.json')
 run(label+'-actual-stdio',[N,str(B/'stdio-probe.mjs'),str(P),str(R/'projects/package-probe'),str(stdio)],configured)
 entry={'model':model,'configured_argv':argv,'stdio_result_sha256':sha(stdio),'versions':[]}
 for version in ['v1','v2']:
  generation=None if version=='v1' else 'image-led-image2-transport/v2'
  probe="import sys,json;sys.path.insert(0,sys.argv[1]);from ai_ppt_studio.adapters.image2_command import image2_preflight;r=image2_preflight(generation_protocol=json.loads(sys.argv[2]));assert r['known_wrapper'] and r['protocol_probe']=='passed' and r['external_connection']=='not-tested';print(json.dumps(r))"
  adapter=run(label+'-'+version+'-adapter',[Y,'-c',probe,str(P/'src'),json.dumps(generation)],configured)
  nonce='467b4e2-'+label+'-'+version+'-'+uuid.uuid4().hex
  request={'protocol':'image-led-image2-preflight/'+version,'request_id':nonce}
  if generation:request['generation_protocol']=generation
  direct=run(label+'-'+version+'-wrapper',[*argv,'--preflight'],stdin=json.dumps(request)); d=json.loads(direct.stdout)
  assert d['protocol']==request['protocol'] and d['request_id']==nonce and d['model']==model and d['receiver']=='CRS' and d['external_connection']=='not-tested'
  if generation:assert d['generation_protocol']==generation
  entry['versions'].append({'version':version,'adapter':json.loads(adapter.stdout),'wrapper':d})
 results.append(entry)
assert tree(R)==runtime_before
assert tree(P)==package_before
write(B/'both-model-protocol-result.json',{'status':'PASS','source_commit':'467b4e2bafde0ca44b301ddb6f3fe934c79bc920','models':results,'wrapper_sha256':sha(WRAPPER),'synthetic_runtime_files':len(runtime_before),'synthetic_runtime_unchanged':True,'all_package_bytes_unchanged':True,'helper_execution':0,'http_calls':0,'no_external_calls_evidence':'Only reviewed stat-only --preflight branches, minimal environment; no generation entry invoked. Not a syscall trace.','installation':'NotRun','real_host':'NotEstablished','provider_authentication':'not-tested','production_model_match_rule':'request model remains exact; CRS Image2 permits observed Image2Codex; Sunburst remains exact; no engine proof','checks_count':len(checks)})
