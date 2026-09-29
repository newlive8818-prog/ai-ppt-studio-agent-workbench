#!/usr/bin/env python3
import argparse, hashlib, json, re
from pathlib import Path

TEXT_ROOTS = [Path('.agents/plugins/marketplace.json'), Path('plugins/ai-ppt-studio'), Path('README.md'), Path('docs')]
CUSTOMER_PATTERNS = {
    'customer_name_zh': re.compile('奥哲'),
    'customer_name_ascii': re.compile(r'aozhe', re.I),
    'local_macos_user_path': re.compile(r'/Users/[A-Za-z0-9._-]+/'),
    'local_windows_user_path': re.compile(r'(?i)[A-Z]:\\\\Users\\\\[^\\\\\s]+\\\\'),
}
SECRET_PATTERNS = {
    'github_token': re.compile(r'gh[opusr]_[A-Za-z0-9_]{20,}'),
    'openai_style_secret': re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
    'aws_access_key': re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    'jwt_bearer': re.compile(r'(?i)Bearer\s+eyJ[A-Za-z0-9._-]{20,}'),
    'private_key_block': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}
CUSTOMER_FILE_SUFFIXES={'.ppt','.pptx','.png','.jpg','.jpeg','.gif','.webp','.tif','.tiff'}

def iter_files(root: Path):
    for item in TEXT_ROOTS:
        p=root/item
        if p.is_file(): yield p
        elif p.is_dir():
            for child in sorted(p.rglob('*')):
                if child.is_file() and '.git' not in child.parts: yield child

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default='.')
    ap.add_argument('--output',default='validation/marketplace/privacy-scan.json')
    args=ap.parse_args(); root=Path(args.root).resolve(); output=(root/args.output).resolve()
    findings=[]; reviewed=[]; scanned=[]; runtime_mentions=[]; pptx_mentions=[]
    for path in iter_files(root):
        if path.resolve()==output: continue
        rel=path.relative_to(root).as_posix(); raw=path.read_bytes(); scanned.append(rel)
        if rel.startswith('plugins/ai-ppt-studio/') and path.suffix.lower() in CUSTOMER_FILE_SUFFIXES:
            if rel.startswith('plugins/ai-ppt-studio/node_modules/'):
                reviewed.append({
                    'path':rel,
                    'classification':'third-party package asset; not customer material',
                })
            else:
                findings.append({'kind':'shipped_customer_media_or_ppt','path':rel})
        if b'\x00' in raw[:8192]: continue
        try: text=raw.decode('utf-8')
        except UnicodeDecodeError: continue
        for kind,rx in CUSTOMER_PATTERNS.items():
            for m in rx.finditer(text):
                line=text.count('\n',0,m.start())+1
                findings.append({'kind':kind,'path':rel,'line':line})
        for kind,rx in SECRET_PATTERNS.items():
            for m in rx.finditer(text):
                line=text.count('\n',0,m.start())+1
                findings.append({'kind':kind,'path':rel,'line':line})
        for i,line in enumerate(text.splitlines(),1):
            if 'AI-PPT-Workspace' in line: runtime_mentions.append({'path':rel,'line':i,'classification':'generic-runtime-location-name; no runtime data'})
            if re.search(r'\.pptx?\b',line,re.I): pptx_mentions.append({'path':rel,'line':i,'classification':'capability or documentation reference; no shipped PPT/PPTX file'})
            if "Authorization: 'Bearer myToken'" in line:
                reviewed.append({'path':rel,'line':i,'classification':'third-party documentation placeholder; not a credential'})
            if '-----BEGIN PRIVATE KEY-----' in line and 'indexOf' in line:
                reviewed.append({'path':rel,'line':i,'classification':'third-party parser marker; no key material'})
    report={
      'schema_version':'c3-marketplace-privacy-scan/v1',
      'scan_scope':[str(p) for p in TEXT_ROOTS],
      'scanned_file_count':len(scanned),
      'scanned_path_list_sha256':hashlib.sha256(('\n'.join(sorted(scanned))+'\n').encode()).hexdigest(),
      'blocking_findings':findings,
      'reviewed_non_blocking_matches':reviewed,
      'generic_runtime_mentions':runtime_mentions,
      'pptx_text_mentions':pptx_mentions,
      'checks':{
        'customer_names':'passed' if not any(x['kind'].startswith('customer_') for x in findings) else 'failed',
        'local_absolute_user_paths':'passed' if not any('user_path' in x['kind'] for x in findings) else 'failed',
        'customer_ppt_or_images':'passed' if not any(x['kind']=='shipped_customer_media_or_ppt' for x in findings) else 'failed',
        'high_confidence_credentials':'passed' if not any(x['kind'] in SECRET_PATTERNS for x in findings) else 'failed',
      },
      'status':'passed' if not findings else 'failed',
    }
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'scanned_file_count':len(scanned),'blocking_findings':len(findings),'checks':report['checks']},ensure_ascii=False))
    raise SystemExit(0 if not findings else 1)
if __name__=='__main__': main()
