#!/usr/bin/env python3
import hashlib,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
errors=[]
market=json.loads((root/'.agents/plugins/marketplace.json').read_text())
plugin=json.loads((root/'plugins/ai-ppt-studio/.codex-plugin/plugin.json').read_text())
release=json.loads((root/'plugins/ai-ppt-studio/release-manifest.json').read_text())
if market.get('name')!='newlive8818-ai-ppt-studio': errors.append('marketplace name mismatch')
entries=market.get('plugins',[])
if len(entries)!=1: errors.append('marketplace must contain exactly one plugin')
else:
    e=entries[0]
    expected={'name':'ai-ppt-studio','source':{'source':'local','path':'./plugins/ai-ppt-studio'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}
    if e!=expected: errors.append('marketplace plugin entry mismatch')
if plugin.get('name')!='ai-ppt-studio': errors.append('plugin name mismatch')
if plugin.get('version')!='0.4.0+codex.c3.release-20260928': errors.append('plugin version mismatch')
if plugin.get('mcpServers')!='./.mcp.json': errors.append('stdio MCP manifest path mismatch')
if release.get('plugin_name')!=plugin.get('name') or release.get('plugin_version')!=plugin.get('version'): errors.append('release identity mismatch')
files={}
plugin_root=root/'plugins/ai-ppt-studio'
for p in sorted(plugin_root.rglob('*')):
    if p.is_file() and p.name!='release-manifest.json':
        files[p.relative_to(plugin_root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
if files!=release.get('files'): errors.append('release manifest does not exactly match shipped files')
readme=(root/'README.md').read_text()
required=[
'codex plugin marketplace add newlive8818-prog/ai-ppt-studio-agent-workbench --ref codex/plugin-marketplace-0.4.0',
'codex plugin marketplace list',
'codex plugin add ai-ppt-studio@newlive8818-ai-ppt-studio',
]
for cmd in required:
    if cmd not in readme: errors.append('README missing command: '+cmd)
out={'schema_version':'c3-marketplace-validation/v1','marketplace_name':market.get('name'),'plugin_name':plugin.get('name'),'plugin_version':plugin.get('version'),'release_file_count':len(files),'release_manifest_sha256':hashlib.sha256((plugin_root/'release-manifest.json').read_bytes()).hexdigest(),'checks':{'marketplace_catalog':'passed' if not any('marketplace' in e for e in errors) else 'failed','plugin_identity':'passed' if not any('plugin ' in e or 'stdio' in e for e in errors) else 'failed','release_manifest':'passed' if not any('release' in e for e in errors) else 'failed','install_commands':'passed' if not any('README' in e for e in errors) else 'failed'},'errors':errors,'status':'passed' if not errors else 'failed'}
path=root/'validation/marketplace/static-validation.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if not errors else 1)
