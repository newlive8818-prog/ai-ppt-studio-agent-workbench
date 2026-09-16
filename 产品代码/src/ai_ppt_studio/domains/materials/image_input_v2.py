"""Closed v2 input projections. No IO, authorization grants, or layout inference."""
from copy import deepcopy
from hashlib import sha256
from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, text
from ai_ppt_studio.domains.content.contracts import FORMAL_CONTENT_IDENTITIES, EVIDENCE_BUCKET_IDENTITIES

PACK_VERSION = 'image-led-input-pack/v2'
COPY_VERSION = 'image-led-selected-copy/v2'
PAYLOAD_VERSION = 'image-led-image2-input/v2'
TRANSPORT_VERSION = 'image-led-image2-transport/v2'
PREFLIGHT_VERSION = 'image-led-image2-preflight/v2'
RULES = ['preserve-source-memberships-and-stated-flow',
         'do-not-invent-unstated-interfaces-or-endpoints',
         'do-not-infer-implemented-results', 'do-not-treat-source-layout-as-template']

def validate_pack_v2(payload, project_id):
    from ai_ppt_studio.domains.materials.image_input_contracts import validate_pack
    exact(payload, {'artifact_type','pack_version','project_id','input_policy_ref','slide_id',
        'page_order','confirmed_visible_copy','page_goal','atoms','required_atom_ids'}, 'v2 input pack')
    if payload['pack_version'] != PACK_VERSION:
        fail('VERSION', 'unsupported input pack version')
    copy = exact(payload['confirmed_visible_copy'], {'title','title_target','blocks'}, 'v2 confirmed copy')
    legacy = deepcopy(payload)
    legacy.pop('pack_version'); legacy.pop('required_atom_ids')
    legacy['confirmed_visible_copy'].pop('title_target')
    validate_pack(legacy, project_id)
    if payload['required_atom_ids'] != []:
        fail('MATERIAL_REQUIREMENT_NOT_ESTABLISHED', 'no current resolvable required-material decision contract')
    target = copy['title_target']
    if not isinstance(target, dict):
        fail('TITLE', 'one explicit title target is required')
    if target.get('kind') == 'block':
        exact(target, {'kind','block_id'}, 'title block target')
        matches = [b for b in copy['blocks'] if b['block_id'] == target['block_id']]
        if len(matches) != 1 or matches[0]['text'] != copy['title']:
            fail('TITLE', 'title target must resolve to one exact current visible block')
    elif target.get('kind') == 'standalone':
        exact(target, {'kind','item_id'}, 'standalone title target')
        if target['item_id'] != 'title' or any(b['block_id'] == 'title' for b in copy['blocks']):
            fail('TITLE', 'standalone title identity conflicts with a visible block')
    else:
        fail('TITLE', 'unsupported title target kind')
    return deepcopy(payload)

def visible_copy(pack):
    source = pack['confirmed_visible_copy']
    is_v2 = pack.get('pack_version') == PACK_VERSION
    target = source['title_target'] if is_v2 else {'kind':'standalone','item_id':'title'}
    title_id = target.get('block_id') if target['kind'] == 'block' else target['item_id']
    items = [] if target['kind'] == 'block' else [
        {'item_id':title_id,'kind':'text','role':'title','text':source['title']}]
    items += [{'item_id':b['block_id'],'kind':'text',
               'role':'title' if is_v2 and b['block_id'] == title_id else 'body','text':b['text']}
              for b in source['blocks']]
    return ({'copy_version':COPY_VERSION,'title_item_id':title_id,'items':items}
            if is_v2 else {'items':items})

def validate_used_materials(pack, roles):
    available = [{k:a[k] for k in ('atom_id','source_ref','content_sha256','use')} for a in pack['atoms']]
    if pack.get('pack_version') != PACK_VERSION:
        if roles != available:
            fail('MATERIAL', 'candidate material roles differ from the exact requested atoms')
        return
    if pack['required_atom_ids'] != []:
        fail('MATERIAL_REQUIREMENT_NOT_ESTABLISHED', 'required-material evidence is unavailable')
    if not isinstance(roles, list) or any(not isinstance(r,dict) for r in roles):
        fail('MATERIAL', 'actual material roles must be an ordered subset')
    ids = [r.get('atom_id') for r in roles]
    if any(not isinstance(i,str) for i in ids) or len(ids) != len(set(ids)):
        fail('MATERIAL', 'actual material identities must be unique')
    if roles != [r for r in available if r['atom_id'] in ids] or len(roles) != len(ids):
        fail('MATERIAL', 'actual material roles differ from the requested pool')

def aliases(copy, materials):
    return ({item['item_id']:f'text-{i:04d}' for i,item in enumerate(copy['items'],1)},
            {item['atom_id']:f'material-{i:04d}' for i,item in enumerate(materials,1)})

def derive_semantics(pack, slide, evidence, *, blueprint_ref, evidence_ref, slide_index):
    """Only exact current fields enter semantics; bindings never enter provider JSON."""
    semantics = {'context_version':'image-led-semantic-context/v1',
        'purpose':'constraints-only-not-visible-copy', 'relationship_summary':slide['page_task'],
        'rules':deepcopy(RULES), 'copy_facts':[], 'limitations':[], 'material_use':[]}
    provenance = []
    def record(value, reference, path):
        text(value, 'semantic customer text')
        provenance.append({'source_ref':reference,'field_path':path,
                           'text_sha256':sha256(value.encode('utf-8')).hexdigest()})
        return value
    if type(slide_index) is not int or slide_index < 0:
        fail('SEMANTIC', 'actual source array index is required')
    record(slide['page_task'], blueprint_ref, f"slides/{slide_index}/page_task")
    limits = {}
    def limitation(value, reference, path):
        record(value,reference,path)
        if value not in limits:
            limit_id = f'limit-{len(limits)+1:04d}'
            limits[value]=limit_id
            semantics['limitations'].append({'limit_id':limit_id,'text':value})
        return limits[value]
    bindings = slide.get('evidence_bindings',[])
    page_refs = {r for b in bindings for r in b.get('source_refs',[])}
    page_refs.update(slide.get('customer_decision_item',{}).get('evidence_refs',[]))
    page_refs.update(v.get('source_ref') for v in slide.get('material_views',[]))
    for n,block in enumerate(slide['visible_copy_blocks']):
        matches=[(bucket,i,row) for bucket in EVIDENCE_BUCKET_IDENTITIES if bucket != 'forbidden_extrapolations'
                 for i,row in enumerate(evidence.get(bucket,[])) if row.get('item_id') == block['block_id']]
        if len(matches)!=1:
            fail('SEMANTIC', 'missing or ambiguous current evidence item identity')
        bound=[b for b in bindings if b.get('content_ref')==block['block_id']]
        limit_ids=[]
        bucket,i,row=matches[0]
        if len(bound)!=1 or set(row.get('source_refs',[])) != set(bound[0].get('source_refs',[])):
            fail('SEMANTIC', 'evidence is not bound to this exact current content item')
        if row.get('identity') != block['identity'] or row['identity'] not in EVIDENCE_BUCKET_IDENTITIES[bucket]:
            fail('SEMANTIC', 'evidence identity differs from current content identity or supported category')
        for j,value in enumerate(row.get('limitations',[])):
            limit_ids.append(limitation(value,evidence_ref,f'{bucket}/{i}/limitations/{j}'))
        identity=record(block['identity'],blueprint_ref,f"slides/{slide_index}/visible_copy_blocks/{n}/identity")
        semantics['copy_facts'].append({'item_id':block['block_id'],'identity':identity,'limit_ids':limit_ids})
    for i,row in enumerate(evidence.get('forbidden_extrapolations',[])):
        refs=set(row.get('source_refs',[]))
        if refs and refs.issubset(page_refs):
            limitation(row['statement'],evidence_ref,f'forbidden_extrapolations/{i}/statement')
    image_number=0
    buckets=('facts','user_confirmed_facts','inferences','conflicts','unknowns','evidence_gaps')
    for atom in pack['atoms']:
        if atom['atom_type']=='image': image_number+=1
        row={'material_id':atom['atom_id'],'image_number':image_number if atom['atom_type']=='image' else None,
             'use':atom['use'],'presence':'optional','purpose':'','identity':'','limitations':[]}
        if atom['origin_kind']=='material-view':
            matches=[(i,v) for i,v in enumerate(slide.get('material_views',[])) if v.get('material_view_id')==atom['origin_id'] and v.get('source_ref')==atom['source_ref']]
            if len(matches)!=1: fail('SEMANTIC', 'material view semantic origin is not unique')
            i,view=matches[0]
            prefix=f"slides/{slide_index}/material_views/{i}/"
            row['purpose']=record(view['purpose'],blueprint_ref,prefix+'purpose')
            row['identity']=record(view['evidence_identity'],blueprint_ref,prefix+'evidence_identity')
            row['limitations']=[record(view['treatment'],blueprint_ref,prefix+'treatment')]
        else:
            matches=[(bucket,i,v) for bucket in buckets for i,v in enumerate(evidence.get(bucket,[])) if v.get('item_id')==atom['origin_id'] and atom['source_ref'] in v.get('source_refs',[])]
            if len(matches)!=1: fail('SEMANTIC', 'material evidence semantic origin is not unique')
            bucket,i,source=matches[0]
            row['identity']=record(source['identity'],evidence_ref,f'{bucket}/{i}/identity')
            row['limitations']=[record(v,evidence_ref,f'{bucket}/{i}/limitations/{j}') for j,v in enumerate(source.get('limitations',[]))]
            # No purpose is fabricated when no current material view provides it.
        semantics['material_use'].append(row)
    return semantics, provenance

def semantic_strings(semantics):
    yield semantics['relationship_summary']
    for row in semantics['limitations']: yield row['text']
    for row in semantics['material_use']:
        if row['purpose']: yield row['purpose']
        yield from row['limitations']

def customer_strings(payload):
    """All non-atom customer strings; atom bytes retain their typed source scope."""
    yield from (i['text'] for i in payload['confirmed_visible_copy']['items'])
    yield payload['page_goal']
    yield from semantic_strings(payload['non_visible_semantics'])
    yield from common_rule_strings(payload['common_rules'])

def common_rule_strings(rules):
    """Free design-rule text has no implicit exemption from the scoped sender."""
    yield rules['title_bar']
    yield rules['background']
    for field in ('typography_tokens','color_tokens','fallback_fonts'):
        for key,value in rules[field].items():
            yield key
            yield value

def validate_semantics(value, copy, materials, *, expected_fact_item_ids=None):
    exact(value,{'context_version','purpose','relationship_summary','rules','copy_facts','limitations','material_use'},'semantic context')
    if (value['context_version']!='image-led-semantic-context/v1' or value['purpose']!='constraints-only-not-visible-copy' or value['rules']!=RULES):
        fail('SEMANTIC','unsupported semantic context or rules')
    for key in ('copy_facts','limitations','material_use'):
        if not isinstance(value[key],list):fail('SEMANTIC','semantic entries must be arrays')
    limits=[]
    for row in value['limitations']:
        exact(row,{'limit_id','text'},'limitation');text(row['limit_id'],'limit_id');text(row['text'],'limitation')
        limits.append(row['limit_id'])
    if len(set(limits))!=len(limits):fail('SEMANTIC','duplicate limitation identity')
    items={i['item_id'] for i in copy['items']}; seen=set()
    for row in value['copy_facts']:
        exact(row,{'item_id','identity','limit_ids'},'copy fact')
        if (not isinstance(row['item_id'],str) or row['item_id'] not in items or row['item_id'] in seen
                or not isinstance(row['limit_ids'],list) or any(i not in limits for i in row['limit_ids'])):
            fail('SEMANTIC','fact identity or limitation is unbound')
        seen.add(row['item_id'])
        if not isinstance(row['identity'],str) or row['identity'] not in FORMAL_CONTENT_IDENTITIES:
            fail('SEMANTIC','unsupported content identity')
    if expected_fact_item_ids is not None:
        if [r['item_id'] for r in value['copy_facts']] != expected_fact_item_ids:
            fail('SEMANTIC','semantic facts must cover current blocks exactly in order')
    else:
        # The wrapper lacks pack title-origin context. Production compilation
        # proves every source block; the wrapper can prove body coverage only.
        expected = [i['item_id'] for i in copy['items'] if i['item_id'] in seen]
        required = {i['item_id'] for i in copy['items'] if i.get('role') != 'title'}
        if not required.issubset(seen) or [r['item_id'] for r in value['copy_facts']] != expected:
            fail('SEMANTIC','body semantics must preserve complete item coverage and order')
    if len(value['material_use'])!=len(materials):fail('SEMANTIC','material semantics must cover the pool')
    image_number=0
    for row,material in zip(value['material_use'],materials):
        exact(row,{'material_id','image_number','use','presence','purpose','identity','limitations'},'material semantics')
        if material['type']=='image':image_number+=1
        if (row['material_id']!=material['atom_id'] or row['use']!=material['use'] or row['presence']!='optional'
                or row['image_number']!=(image_number if material['type']=='image' else None)):
            fail('SEMANTIC','material semantics differ from exact pool identity')
        if not isinstance(row['purpose'],str) or not isinstance(row['limitations'],list):fail('SEMANTIC','invalid material purpose/limitations')
        if (not isinstance(row['identity'],str) or row['identity'] not in FORMAL_CONTENT_IDENTITIES
                or row['identity']=='禁止使用'):
            fail('SEMANTIC','unsupported usable material identity')
    for word in semantic_strings(value):text(word,'semantic text')
    return deepcopy(value)

def public_projection(copy, materials, semantics):
    """One mapping for visible items and all semantic references; no source IDs."""
    texts,atoms=aliases(copy,materials)
    public_copy=deepcopy(copy)
    public_copy['title_item_id']=texts[copy['title_item_id']]
    for item in public_copy['items']:
        item['item_id']=texts[item['item_id']]
        for key in ('from_item_id','to_item_id'):
            if key in item:item[key]=texts[item[key]]
    public_semantics=deepcopy(semantics)
    for row in public_semantics['copy_facts']:row['item_id']=texts[row['item_id']]
    for row in public_semantics['material_use']:row['material_id']=atoms[row['material_id']]
    return public_copy,public_semantics,atoms
