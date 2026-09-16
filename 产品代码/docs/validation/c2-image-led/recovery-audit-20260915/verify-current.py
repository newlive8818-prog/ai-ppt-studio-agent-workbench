import hashlib
import json
import os
import pathlib
import platform
import sys
import time
import traceback

ROOT = pathlib.Path('/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909')
PACKAGE = pathlib.Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/0.4.0+codex.c2.chat-confirm.20260914')
OUT = pathlib.Path('/private/tmp/c2-recovery-audit-20260915')
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE / 'src'))
CASE = sys.argv[1] if len(sys.argv) > 1 else 'powerpoint-fonts'
FONTS = [pathlib.Path('/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts') / n for n in ['msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc']]
if CASE == 'user-fonts':
    FONTS = [pathlib.Path('/Users/defei/Library/Fonts') / n for n in ['AI-PPT-e4b3b9d05875-msyh.ttc', 'AI-PPT-06e1a30f687a-msyhbd.ttc', 'AI-PPT-2db3f3100589-msyhl.ttc']]
os.environ['C2_RUNTIME_FONT_FILES'] = json.dumps([str(p) for p in FONTS])
if CASE == 'native-host':
    os.environ.pop('C2_RUNTIME_FONT_FILES', None)

from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.application.image_led_native import ImageLedNativeService
from ai_ppt_studio.application.gate_evaluator import GateEvaluator

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def fingerprint():
    files = sorted(p for folder in ['kernel', 'artifacts'] for p in (ROOT / folder).rglob('*') if p.is_file())
    items = {str(p.relative_to(ROOT)): sha(p) for p in files}
    return {'file_count': len(items), 'sha256': hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(), 'state_sha256': sha(ROOT/'kernel/state.json')}

k = ProjectKernel(ROOT, project_id=ROOT.name)
s = k.load()
before = fingerprint()
report = {'scope': 'read-only current C2 evidence replay; no gate or business writes', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runtime_revision': s.revision, 'gate_status': s.gate_status, 'python': {'path': sys.executable, 'version': platform.python_version(), 'machine': platform.machine()}, 'package': str(PACKAGE), 'package_manifest_sha256': sha(PACKAGE/'release-manifest.json'), 'fonts': [{'path':str(p), 'sha256':sha(p)} for p in FONTS], 'before':before, 'checks': {}}
report['font_configuration'] = 'system host discovery; listed fonts are comparison metadata, not explicit registration' if CASE == 'native-host' else 'explicit C2_RUNTIME_FONT_FILES registration'

def resolve(ref):
    h=ref.rsplit('/',1)[1]
    p=ROOT/'artifacts/objects'/h[:2]/(h+'.json')
    v=json.loads(p.read_text())
    return v['payload']

for slot in ['gate/G3/confirmation', 'review/session/visual-professional', 'release/target-policy', 'visual/target-evidence/G2/macos-powerpoint']:
    report[slot] = {'ref':s.artifact_heads[slot], 'payload':resolve(s.artifact_heads[slot])}
report['g2_reviews']=[]
for slot in ['visual/review/G2/aesthetic', 'visual/review/G2/engineering']:
    v=resolve(s.artifact_heads[slot])
    report['g2_reviews'].append({'slot':slot,'ref':s.artifact_heads[slot], 'overall_result':v.get('overall_result'), 'reviewer_role':v.get('reviewer_role'), 'retained_failed_reference_checks':[c for c in v.get('checks',[]) if c.get('result')=='failed']})

build=resolve(s.artifact_heads['visual/image-led/build-result'])
files=[]
def scan(v):
    if isinstance(v,dict):
        if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
            p=pathlib.Path(v['path']);actual=sha(p) if p.is_file() else None
            files.append({'path':str(p),'expected_sha256':v['sha256'],'actual_sha256':actual,'matches':actual==v['sha256']})
        for x in v.values(): scan(x)
    elif isinstance(v,list):
        for x in v:scan(x)
scan(build['output'])
report['build_files']=files

def check(name,fn,summarize=lambda v:v):
    start=time.time()
    try:
        value=fn()
        result={'status':'passed','elapsed_seconds':round(time.time()-start,3),'result':summarize(value)}
    except Exception as e:
        result={'status':'failed','elapsed_seconds':round(time.time()-start,3),'error_type':type(e).__name__,'error':str(e),'traceback':traceback.format_exc()}
    report['checks'][name]=result
    print(name,json.dumps(result,ensure_ascii=False),flush=True)
    (OUT/('runtime-replay-'+CASE+'.partial.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))

check('current_authority', lambda:k._validate_current_authority(k.load()))
check('current_anchors', lambda:ImageLedNativeService(k).current_anchors(), lambda v:{'slide_ids':v['slide_ids'],'pptx_sha256':v['pptx_sha256'],'image_led':v['image_led']})
check('current_g2_evidence', lambda:GateEvaluator(k).validate_current_g2_evidence(), lambda v:{'validated':True,'keys':list(v),'evidence_refs':v.get('evidence_refs',[])})
def projection_summary(v):
    return {'review_session':v['review_session'],'revision':v['revision'],'authoritative_revision':v['authoritative_revision'],'anchor_count':len(v['anchors']),'contract_count':len(v.get('slide_visual_contracts',v.get('slides',[]))),'projection_keys':list(v)}
check('visual_review_projection', lambda:VisualReviewService(k).project('visual-professional-c24c85b250a883d18ae0'),projection_summary)
report['after']=fingerprint()
report['zero_authority_write']=report['before']==report['after']
report['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
(OUT/('runtime-replay-'+CASE+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('FINAL', json.dumps({'checks':{n:v['status'] for n,v in report['checks'].items()},'zero_authority_write':report['zero_authority_write'],'build_files':len(files),'all_build_hashes_match':all(x['matches'] for x in files),'report':str(OUT/('runtime-replay-'+CASE+'.json'))}),flush=True)
