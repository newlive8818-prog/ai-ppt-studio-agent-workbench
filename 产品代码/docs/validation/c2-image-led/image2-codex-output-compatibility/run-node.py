from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

BASE=Path('/private/tmp/c2-image2-compat-20260911/runtime-verification')
WORKTREE=Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app')
SOURCE=BASE/'private-source'
ROOT=SOURCE/'产品代码'
DEPS=Path('/private/tmp/c2-image25-adaptation-20260911/user-agent-fix/repo/产品代码/node_modules')
BUNDLE=Path('/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies')
NODE=BUNDLE/'node/bin/node'
PYTHON=BUNDLE/'python/bin/python3'
NPM=Path('/opt/homebrew/bin/npm')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(name,value):(BASE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

if SOURCE.exists():raise RuntimeError('Do not overwrite a previous verification source')
paths=set(subprocess.check_output(['/usr/bin/git','ls-files','-z'],cwd=WORKTREE).decode().split('\0'))-{''}
paths.update(['产品代码/src/ai_ppt_studio/domains/visual/image_output.py',
              '产品代码/tests/test_image2_output_compatibility.py',
              '产品代码/docs/superpowers/plans/2026-09-11-c2-image2-codex-output-compatibility.md'])
files={}
for relative in sorted(paths):
    source=WORKTREE/relative
    if source.is_symlink() or not source.is_file():raise RuntimeError('Nonregular source '+relative)
    target=SOURCE/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    value=digest(target)
    if value!=digest(source):raise RuntimeError('Snapshot drift '+relative)
    files[relative]=value
write('node-source-manifest.json',{'observed_at_utc':now(),'kind':'working-tree-input-snapshot-not-a-reviewed-commit',
    'source':str(WORKTREE),'snapshot':str(SOURCE),'file_count':len(files),'files':files})
if DEPS.is_symlink():raise RuntimeError('Source dependency root is shared symlink')
links={};count=0
for directory,names,filenames in os.walk(DEPS,followlinks=False):
    for name in names+filenames:
        item=Path(directory)/name
        if item.is_symlink():
            actual=item.resolve(strict=True)
            if not actual.is_relative_to(DEPS.resolve()):raise RuntimeError('Dependency link escapes private root')
            links[str(item.relative_to(DEPS))]=str(actual.relative_to(DEPS.resolve()))
        elif item.is_file():count+=1
destination=ROOT/'node_modules'
shutil.copytree(DEPS,destination,symlinks=True)
for relative,target_relative in links.items():
    item=destination/relative;item.unlink()
    item.symlink_to(os.path.relpath(destination/target_relative,item.parent))
    assert item.resolve(strict=True).is_relative_to(destination.resolve())
write('node-dependency-copy.json',{'source':str(DEPS),'destination':str(destination),
    'regular_file_count':count,'internal_link_count':len(links),'links':links})
(BASE/'empty-user.npmrc').write_text('');(BASE/'empty-global.npmrc').write_text('')
environment={'PATH':os.pathsep.join([str(NODE.parent),str(PYTHON.parent),'/opt/homebrew/bin','/usr/bin','/bin']),
    'LANG':'en_US.UTF-8','PYTHONPATH':'src:/private/tmp/c2-python-deps',
    'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':'/private/tmp',
    'C2_RUNTIME_NODE':str(NODE),'C2_RUNTIME_PYTHON':str(PYTHON),
    'C2_RUNTIME_NODE_MODULES':str(BUNDLE/'node/node_modules'),
    'npm_config_offline':'true','npm_config_audit':'false','npm_config_fund':'false',
    'npm_config_cache':'/private/tmp/c2-candidate-edb12848-20260910/npm-cache',
    'npm_config_userconfig':str(BASE/'empty-user.npmrc'),'npm_config_globalconfig':str(BASE/'empty-global.npmrc')}
records=[]
for label,script in [('typecheck','typecheck'),('build','build'),('node-full','test:node')]:
    command=[str(NPM),'run',script]
    record={'label':label,'command':command,'cwd':str(ROOT),'environment':environment,
        'started_at_utc':now(),'source_manifest_sha256':digest(BASE/'node-source-manifest.json'),
        'script_sha256':digest(Path(__file__))}
    started=time.monotonic();log=BASE/(label+'.log')
    with log.open('wb') as stream:
        result=subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,
            stdout=stream,stderr=subprocess.STDOUT,check=False)
    record.update(finished_at_utc=now(),elapsed_s=round(time.monotonic()-started,3),
        exit_code=result.returncode,log=str(log),log_sha256=digest(log))
    records.append(record);write('node-execution.json',records)
    print(json.dumps({k:v for k,v in record.items() if k!='environment'},ensure_ascii=False),flush=True)
    if result.returncode!=0:raise SystemExit(result.returncode)
changed={p:{'before':sha,'after':digest(SOURCE/p)} for p,sha in files.items() if digest(SOURCE/p)!=sha}
write('node-source-postrun.json',{'observed_at_utc':now(),'changed_tracked_and_explicit_inputs':changed})
