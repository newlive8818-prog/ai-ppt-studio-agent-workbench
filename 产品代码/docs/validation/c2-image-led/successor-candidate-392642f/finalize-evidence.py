from pathlib import Path
import hashlib,json,shutil,re,subprocess
from urllib.parse import unquote
B=Path('/private/tmp/c2-candidate-392642f-20260911')
WORK=Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
OUT=WORK/'产品代码/docs/validation/c2-image-led/successor-candidate-392642f'
LEDGER=OUT.parent/'verification-report.md'
COMMIT='392642f2a34afd856b07228d97ce2b3180fdc961'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=WORK).decode().strip()==COMMIT
assert (B/'independent-package-review.md').is_file()
review=read(B/'independent-package-checks.json')
assert review['status']=='PASS' and not review['findings'] and review['source_commit']==COMMIT
for p in sorted(B.iterdir()):
 if p.is_file() and (p.name.startswith('independent-') or p.name=='doc-checks.json'):
  shutil.copyfile(p,OUT/p.name)
shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
integrity=read(B/'package-integrity-result.json');protocols=read(B/'both-model-protocol-result.json')
assert integrity['status']==protocols['status']=='PASS'
plugin=Path(integrity['plugin_root']); package_files={str(p.relative_to(plugin)):sha(p) for p in plugin.rglob('*') if p.is_file()}
assert package_files==read(B/'complete-file-manifest.json')['files']
assert sha(Path(integrity['archive_path']))==integrity['archive']['archive_sha256']
checks=[]
for p in [WORK/n for n in ['00-唯一研发基线索引-v1.0.md','01-产品需求基线-v1.0.md','02-系统详细设计-v1.0.md','03-UI设计与交互规范-v1.0.md']]+[LEDGER]:
 for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text()):
  target=match.group(1).split(' "')[0].strip('<>'); local=unquote(target.split('#')[0])
  if not local or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',local):continue
  destination=(p.parent/local).resolve()
  # validation.json is the last file created by this script.
  assert destination.exists() or destination==OUT/'validation.json',(str(p),target)
  checks.append({'source':str(p.relative_to(WORK)),'target':target,'exists':True})
subprocess.run(['git','diff','--check'],cwd=WORK,check=True)
receipts=[]
for name in ['ua-generation-receipt.json','ua-double-edit-receipt.json','model-diagnostic-receipt.json']:
 p=OUT/name; d=read(p); assert d['wrapper_sha256']==integrity['wrapper_sha256'];assert d['source_after_check']=='passed';assert d['wrapper_exit_code']==1;assert d['response_observed']['http_status']==200
 receipts.append({'file':name,'sha256':sha(p),'request_id':d['request_id'],'http_status':200,'wrapper_exit_code':1,'source_after_check':'passed'})
payload={'status':'local-package-ready-provider-blocked','source_commit':COMMIT,'evidence_commit':'this evidence-only commit; source and package remain pinned to source_commit','version':integrity['version'],'plugin_root':str(plugin),'archive_path':integrity['archive_path'],'archive_sha256':integrity['archive']['archive_sha256'],'release_manifest_sha256':integrity['manifest_sha256'],'packaged_wrapper_sha256':integrity['wrapper_sha256'],'tracked_source_snapshot_files':921,'reviewed_production_python_files':104,'package_files_including_manifest':len(package_files),'source_to_package_mapped_files':141,'fresh_widget_bundles':1,'production_dependency_files':3622,'local_package_checks':'PASS','model_preflight_checks':'PASS','process_checks':protocols['checks_count'],'provider_readonly_receipts':receipts,'provider_status':'not-passed; v3 explicit model gpt-image-2-codex and decoded dimensions 1536x1024 do not meet requested Sunburst / 2048x1152','provider_engine_independently_proven':False,'strict_model_and_dimensions_unchanged':True,'source_full_suites_this_task':'NotRun','installation':'NotRun','restart':'NotRun','release':'NotRun','customer_operations_performed':False,'current_host_acceptance':'NotEstablished','additional_http_calls_in_this_task':0,'relative_link_target_checks':len(checks),'evidence_files':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='validation.json'},'ledger_sha256':sha(LEDGER),'proof_limits':['Local candidate and isolated stdio/stat-only probes are separate from currently running desktop plugin.','Controller provider calls are noncustomer wrapper component checks, not formal customer Runtime or visual acceptance.','v3 upstream model metadata is a report, not independent evidence of its backend engine.','Build-stage NotRun records remain immutable; this validation and the unique ledger carry final local state.','Historical Git dataless object limitations were not repaired or represented as full history verification.']}
payload['independent_package_review']={'status':'PASS','report_sha256':sha(OUT/'independent-package-review.md'),'checks_sha256':sha(OUT/'independent-package-checks.json'),'independent_stat_only_cases':4,'findings':[]}
write(OUT/'validation.json',payload);write(B/'validation.json',payload)
write(B/'final-relative-links.json',checks)
print(json.dumps({'status':payload['status'],'evidence_files':len(payload['evidence_files']),'validation_sha256':sha(OUT/'validation.json'),'relative_links':len(checks),'archive_sha256':payload['archive_sha256']},ensure_ascii=False))
