from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE=Path('/private/tmp/c2-image2-compat-20260911/runtime-verification')
ROOT=Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码')
BUNDLE=Path('/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies')
PYTHON=BUNDLE/'python/bin/python3'
NODE=BUNDLE/'node/bin/node'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(name,value):(BASE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def snapshot(name):
    files={}
    for relative in ('src','tests','scripts','mcp','skills'):
        for p in sorted((ROOT/relative).rglob('*')):
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                files[str(p.relative_to(ROOT))]=digest(p)
    record={'observed_at_utc':now(),'source_root':str(ROOT),'files':files,
        'production_python_count':sum(p.startswith('src/') and p.endswith('.py') for p in files),
        'test_python_count':sum(p.startswith('tests/') and p.endswith('.py') for p in files)}
    write(name,record)
    return record

environment={'PATH':os.pathsep.join([str(NODE.parent),str(PYTHON.parent),'/opt/homebrew/bin','/usr/bin','/bin']),
    'LANG':'en_US.UTF-8','PYTHONPATH':'src:/private/tmp/c2-python-deps',
    'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':'/private/tmp',
    'C2_RUNTIME_NODE':str(NODE),'C2_RUNTIME_PYTHON':str(PYTHON),
    'C2_RUNTIME_NODE_MODULES':str(BUNDLE/'node/node_modules'),
    'npm_config_offline':'true','npm_config_audit':'false','npm_config_fund':'false',
    'npm_config_cache':'/private/tmp/c2-candidate-edb12848-20260910/npm-cache'}
before=snapshot('python-start-manifest.json')
command=[str(PYTHON),'-m','unittest','discover','-s','tests']
execution={'status':'running','command':command,'cwd':str(ROOT),'environment':environment,
    'started_at_utc':now(),'start_manifest_sha256':digest(BASE/'python-start-manifest.json'),
    'script_sha256':digest(Path(__file__))}
write('python-execution.json',execution)
started=time.monotonic()
with (BASE/'python-full.log').open('wb') as log:
    result=subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
after=snapshot('python-end-manifest.json')
changed={p:{'before':before['files'].get(p),'after':after['files'].get(p)}
    for p in sorted(before['files'].keys()|after['files'].keys()) if before['files'].get(p)!=after['files'].get(p)}
execution.update(status='complete',exit_code=result.returncode,finished_at_utc=now(),
    elapsed_s=round(time.monotonic()-started,3),log=str(BASE/'python-full.log'),log_sha256=digest(BASE/'python-full.log'),
    end_manifest_sha256=digest(BASE/'python-end-manifest.json'),changed_during_run=changed)
write('python-execution.json',execution)
print(json.dumps({k:v for k,v in execution.items() if k not in ('environment','changed_during_run')},ensure_ascii=False))
print(json.dumps({'changed_during_run':changed},ensure_ascii=False))
raise SystemExit(result.returncode)
