from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE=Path('/private/tmp/c2-image2-compat-20260911/runtime-verification')
ROOT=BASE/'private-source/产品代码'
NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
environment=json.loads((BASE/'node-execution.json').read_text())[0]['environment']
profile=BASE/'loopback-only.sb'
command=['/usr/bin/sandbox-exec','-f',str(profile),NODE,'--test','tests/review-bridge.test.mjs']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
record={'command':command,'cwd':str(ROOT),'environment':environment,
    'started_at_utc':datetime.now(timezone.utc).isoformat(),
    'test_sha256':digest(ROOT/'tests/review-bridge.test.mjs'),'sandbox_profile_sha256':digest(profile),
    'boundary':'local loopback HTTP only; external outbound and real crs-auth-helper process execution denied'}
log=BASE/'review-bridge-loopback.log';started=time.monotonic()
with log.open('wb') as stream:
    result=subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,
        stdout=stream,stderr=subprocess.STDOUT,check=False)
record.update(exit_code=result.returncode,elapsed_s=round(time.monotonic()-started,3),
    finished_at_utc=datetime.now(timezone.utc).isoformat(),log=str(log),log_sha256=digest(log))
(BASE/'review-bridge-loopback-execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='environment'},ensure_ascii=False))
raise SystemExit(result.returncode)
