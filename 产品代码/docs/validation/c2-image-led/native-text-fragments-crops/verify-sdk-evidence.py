from pathlib import Path
from io import BytesIO
from copy import deepcopy
import json,hashlib,xml.etree.ElementTree as ET
from zipfile import ZipFile
from test_image_led_text_fragments_sdk import render_source_mapped_fixture
from ai_ppt_studio.application.image_led_results import preflight_output,inspect_native_pptx
from ai_ppt_studio.application.image_led_ooxml import NS
from ai_ppt_studio.errors import ContractValidationError

root=Path('/private/tmp/c2-text-fragments');project=root/'sdk-success';project.mkdir(exist_ok=True)
h,out=render_source_mapped_fixture(project)
assert preflight_output(out,h,project)==out
raw=Path(out['pptx_path']).read_bytes();evidence=inspect_native_pptx(raw,h);assert len(evidence)==14
folder=root/'sdk-mutants';folder.mkdir(exist_ok=True)
def shape(tree,name):
 return next(p for p in tree.findall('.//p:sp',NS) if p.find('p:nvSpPr/p:cNvPr',NS).get('name')==name)
def picture(tree,name):
 return next(p for p in tree.findall('.//p:pic',NS) if p.find('p:nvPicPr/p:cNvPr',NS).get('name')==name)
def separator(tree):return shape(tree,'o-body-0::fragment:11:12')
changes={
 'missing-separator':lambda t:t.find('p:cSld/p:spTree',NS).remove(separator(t)),
 'missing-original-double-space':lambda t:t.find('p:cSld/p:spTree',NS).remove(shape(t,'o-body-0::fragment:16:18')),
 'duplicate-separator':lambda t:t.find('p:cSld/p:spTree',NS).append(deepcopy(separator(t))),
 'hidden-separator':lambda t:separator(t).find('p:nvSpPr/p:cNvPr',NS).set('hidden','1'),
 'changed-separator-text':lambda t:setattr(separator(t).find('p:txBody/a:p/a:r/a:t',NS),'text','/'),
 'moved-separator':lambda t:separator(t).find('p:spPr/a:xfrm/a:off',NS).set('x','1'),
 'changed-selected-crop':lambda t:picture(t,'o-sample-image').find('p:blipFill/a:srcRect',NS).set('l','0'),
 'changed-legacy-decoration-crop':lambda t:picture(t,'o-legacy-decoration').find('p:blipFill/a:srcRect',NS).set('t','0'),
 'replaced-selected-image-bytes':None,
}
mutants=[]
for name,change in changes.items():
 buf=BytesIO()
 with ZipFile(BytesIO(raw)) as src,ZipFile(buf,'w') as dst:
  for entry in src.infolist():
   data=src.read(entry.filename)
   if entry.filename=='ppt/slides/slide1.xml' and change:
    tree=ET.fromstring(data);change(tree);data=ET.tostring(tree)
   if change is None and entry.filename.startswith('ppt/media/'):
    data=data[:-1]+bytes([data[-1]^1])
   dst.writestr(entry,data)
 data=buf.getvalue();path=folder/(name+'.pptx');path.write_bytes(data)
 try:inspect_native_pptx(data,h)
 except ContractValidationError as error:reason=str(error)
 else:raise AssertionError('Mutation was accepted: '+name)
 mutants.append({'name':name,'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'status':'REJECTED','reason':reason})
report={'status':'PASS','scope':'synthetic actual SDK create/export/reimport plus native byte gate','pptx':out['pptx_path'],'pptx_sha256':out['pptx_sha256'],
 'render':out['renders'][0]['path'],'logical_object_count':len(h['slides'][0]['objects']),'native_object_count':len(evidence),
 'fragments':[x for x in evidence if 'span'in x],'native_evidence':evidence,'mutations':mutants,
 'original_text':'Headline😀e\u0301|Body  text','unicode_codepoints':22,'pure_whitespace_span':[16,18],
 'powerpoint_host':'NotRun','customer_runtime_writes':'NotRun','customer_visual_fidelity':'NotEstablished','user_acceptance':'NotEstablished'}
(root/'sdk-evidence-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'status':'PASS','pptx':out['pptx_path'],'sha256':out['pptx_sha256'],'mutations_rejected':len(mutants)},ensure_ascii=False))
