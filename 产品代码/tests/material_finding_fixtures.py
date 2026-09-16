"""Synthetic local snapshots registered through the fixed production finding service."""
from copy import deepcopy
from hashlib import sha256
from ai_ppt_studio.application.material_finding_service import MaterialFindingService
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v22_content_contracts import REF

EXCLUDED_REF = 'artifact://material-finding/' + 'b' * 64
RAW = '客户材料记录了现有流程断点。原文字节保留。'.encode('utf-8')


def source_inventory(kernel):
    path = kernel.project_root / 'fixture-source.txt'
    path.write_bytes(RAW)
    return {'sources': [{'source_id': 'source-1', 'origin': 'user-provided', 'kind': 'file',
        'locator': 'project://fixture-source.txt', 'sha256': sha256(RAW).hexdigest()}]}


def finding_refs(kernel):
    inventory_ref = kernel.load().artifact_heads['materials']
    inventory = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']
    source = inventory['sources'][0]
    service = MaterialFindingService(kernel)
    refs=[]
    for selector in ({'kind': 'whole-source'}, {'kind': 'text-range', 'start': 0, 'end': 1}):
        payload={'material_inventory_ref': inventory_ref, 'source_id': source['source_id'],
            'source_sha256': source['sha256'], 'source_location': selector, 'content_kind': 'text', 'exclusion_mode': 'scope'}
        refs.append(service.register(f'fixture-finding:{inventory_ref}:{selector}',kernel.load().revision,payload))
    return refs


def replace_refs(value, declared, excluded):
    if isinstance(value, dict):
        return {key: replace_refs(item,declared,excluded) for key,item in value.items()}
    if isinstance(value, list):
        return [replace_refs(item,declared,excluded) for item in value]
    if value == REF: return declared
    if value == EXCLUDED_REF: return excluded
    return deepcopy(value)


def bind_findings(kernel, value):
    if not kernel.load().artifact_heads.get('materials'):
        return deepcopy(value)
    return replace_refs(value, *finding_refs(kernel))
