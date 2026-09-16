"""Versioned input identities through real production pure/service entrypoints."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.adapters import image2_crs
from ai_ppt_studio.domains.materials.image_input_contracts import validate_pack
from ai_ppt_studio.domains.visual.image_led import validate_selected_copy, selected_copy_sha256
from ai_ppt_studio.domains.visual.contracts import image_led_visible_fields
from ai_ppt_studio.errors import ContractValidationError
from tests.test_image_led_contracts import rich_fixture
from tests.test_image_led_compilation import fixture_for, compile_plan

PACK_VERSION='image-led-input-pack/v2'
COPY_VERSION='image-led-selected-copy/v2'
INPUT_VERSION='image-led-image2-input/v2'
TRANSPORT='image-led-image2-transport/v2'

def pack_fixture():
    blocks=[{'block_id':'before','text':' 前置项\n','identity':'来源事实'},
            {'block_id':'heading','text':'标题','identity':'来源事实'},
            {'block_id':'repeat','text':'标题','identity':'来源事实'}]
    return {'artifact_type':'image-led-input-pack','pack_version':PACK_VERSION,
        'project_id':'synthetic-v2','input_policy_ref':'artifact://image-led-input-policy/'+'a'*64,
        'slide_id':'S01','page_order':1,'confirmed_visible_copy':{'title':'标题',
            'title_target':{'kind':'block','block_id':'heading'},'blocks':blocks},
        'page_goal':'说明来源成员与关系','atoms':[],'required_atom_ids':[]}

def expected_copy(pack):
    value=pack['confirmed_visible_copy']; target=value['title_target']
    title_id=target.get('block_id',target.get('item_id'))
    items=[] if target['kind']=='block' else [{'item_id':'title','kind':'text','role':'title','text':value['title']}]
    items += [{'item_id':b['block_id'],'kind':'text','role':'title' if b['block_id']==title_id else 'body',
               'text':b['text']} for b in value['blocks']]
    return {'copy_version':COPY_VERSION,'title_item_id':title_id,'items':items}

def compiled_fixture(pack=None, *, allowed_extra=True):
    pack=deepcopy(pack or pack_fixture())
    slide={'slide_id':'S01','order':1,'neutral_title':pack['confirmed_visible_copy']['title'],
        'visible_copy_blocks':deepcopy(pack['confirmed_visible_copy']['blocks']), 'page_task':pack['page_goal'],
        'evidence_bindings':[{'content_ref':b['block_id'],'source_refs':['finding-local']} for b in pack['confirmed_visible_copy']['blocks']],
        'material_views':[], 'complex_relations':{'old':'MUST_NOT_LEAK_OLD_GRAPH'}}
    evidence={'facts':[{'item_id':b['block_id'],'identity':b['identity'],'source_refs':['finding-local'],
                       'limitations':[' 不证明已经部署\n']} for b in slide['visible_copy_blocks']],
        'forbidden_extrapolations':[{'item_id':'ban','statement':'不得推断接口已验证','source_refs':['finding-local']} ]}
    policy={'receiver':'CRS','model':'gpt-image-2','evidence_book_ref':'eb-current',
        'reading_blueprint_ref':'blueprint-current', 'common_rules':{
            'typography_tokens':{'body':'Arial'},'color_tokens':{'ink':'#10233F'},
            'fallback_fonts':{'macOS':'Arial'},'title_bar':'统一标题栏','background':'浅色背景'}}
    words=[pack['confirmed_visible_copy']['title'],pack['page_goal']]+[b['text'] for b in slide['visible_copy_blocks']]
    words += [policy['common_rules']['title_bar'],policy['common_rules']['background']]
    words += [x for field in ('typography_tokens','color_tokens','fallback_fonts') for pair in policy['common_rules'][field].items() for x in pair]
    if allowed_extra: words += [' 不证明已经部署\n','不得推断接口已验证']+[b['identity'] for b in slide['visible_copy_blocks']]
    scope={'allowed':[{'source_sha256':hashlib.sha256(t.encode()).hexdigest(),
        'source_location':{'kind':'whole-source'},'uses':['content-source'],'send_form':'verbatim'} for t in words], 'excluded':[]}
    kernel=SimpleNamespace(project_id='synthetic-v2')
    service=ImageLedService(kernel)
    service._current=lambda ref,slot,kind: deepcopy(evidence if kind=='presales-evidence-book' else policy)
    service.check_policy=lambda p:(deepcopy(policy),deepcopy(scope),{'slides':[deepcopy(slide)]})
    return service,pack

class ImageLedV2Tests(unittest.TestCase):
    def accepted(self, fn, *args, **kwargs):
        try:return fn(*args, **kwargs)
        except Exception as error:self.fail(f'approved v2 behavior rejected: {type(error).__name__}: {error}')

    def test_pack_embedded_title_preserves_nonfirst_and_same_text_identities(self):
        pack=pack_fixture()
        self.assertEqual(self.accepted(validate_pack,pack,'synthetic-v2'),pack)
        copy=expected_copy(pack)
        self.assertEqual(self.accepted(validate_selected_copy,copy),copy)
        self.assertEqual(image_led_visible_fields(copy)['neutral_title'],'标题')
        self.assertEqual([b['block_id'] for b in image_led_visible_fields(copy)['visible_copy_blocks']],['before','repeat'])

    def test_closed_missing_wrong_multiple_title_target_and_required_reject(self):
        for target in [None,{}, {'kind':'block','block_id':'missing'},
                       [{'kind':'block','block_id':'heading'}],
                       {'kind':'block','block_id':'heading','item_id':'title'}]:
            pack=pack_fixture();pack['confirmed_visible_copy']['title_target']=target
            with self.subTest(target=target),self.assertRaises(ContractValidationError):validate_pack(pack,'synthetic-v2')
        pack=pack_fixture();pack['required_atom_ids']=['invented']
        with self.assertRaises(ContractValidationError):validate_pack(pack,'synthetic-v2')

    def test_standalone_v2_and_legacy_do_not_deduplicate_equal_body_text(self):
        pack=pack_fixture();pack['confirmed_visible_copy']['title_target']={'kind':'standalone','item_id':'title'}
        self.accepted(validate_pack,pack,'synthetic-v2')
        copy=expected_copy(pack)
        self.assertEqual(len(self.accepted(validate_selected_copy,copy)['items']),4)
        legacy=deepcopy(pack);legacy.pop('pack_version');legacy.pop('required_atom_ids');legacy['confirmed_visible_copy'].pop('title_target')
        self.assertEqual(validate_pack(legacy,'synthetic-v2'),legacy)

    def test_copy_hash_binds_title_identity_and_role_without_reordering(self):
        copy=expected_copy(pack_fixture());self.accepted(validate_selected_copy,copy)
        changed=deepcopy(copy);changed['title_item_id']='repeat';changed['items'][1]['role']='body';changed['items'][2]['role']='title'
        self.assertNotEqual(selected_copy_sha256(copy),selected_copy_sha256(changed))
        bad=deepcopy(copy);bad['title_item_id']='before'
        with self.assertRaises(ContractValidationError):validate_selected_copy(bad)

    def test_service_compiles_authoritative_semantics_and_wrapper_shared_aliases(self):
        service,pack=compiled_fixture()
        value=self.accepted(service.compile_request_payload,pack)
        self.assertEqual(value['payload_version'],INPUT_VERSION)
        self.assertEqual(value['confirmed_visible_copy'],expected_copy(pack))
        self.assertIn(' 不证明已经部署\n',[row['text'] for row in value['non_visible_semantics']['limitations']])
        _,mime,body=self.accepted(image2_crs.compile_body,{'protocol':TRANSPORT,'request_id':'v2-test','payload':value})
        self.assertEqual(mime,'application/json')
        prompt=json.loads(json.loads(body)['prompt']);copy=prompt['confirmed_visible_copy']
        self.assertEqual(copy['title_item_id'],'text-0002')
        self.assertEqual([x['item_id'] for x in copy['items']],['text-0001','text-0002','text-0003'])
        self.assertEqual(len(copy['items']),3)
        self.assertEqual(prompt['non_visible_semantics']['copy_facts'][1]['item_id'],'text-0002')
        for forbidden in ['heading','finding-local','blueprint-current','MUST_NOT_LEAK_OLD_GRAPH','artifact://']:
            self.assertNotIn(forbidden,json.dumps(prompt))

    def test_new_semantic_customer_strings_need_scope_before_request(self):
        service,pack=compiled_fixture(allowed_extra=False)
        with self.assertRaises(ContractValidationError):service.compile_request_payload(pack)

    def test_missing_authoritative_fact_or_unknown_identity_rejected(self):
        service,pack=compiled_fixture()
        original=service._current
        def missing(ref,slot,kind):
            result=original(ref,slot,kind)
            if kind=='presales-evidence-book': result['facts'].pop()
            return result
        service._current=missing
        with self.assertRaises(ContractValidationError):service.compile_request_payload(pack)

    def test_semantic_binding_uses_actual_blueprint_array_index_not_page_order(self):
        service,pack=compiled_fixture();original=service.check_policy
        def unsorted(value):
            policy,scope,blueprint=original(value)
            other=deepcopy(blueprint['slides'][0]);other.update(slide_id='S02',order=2,page_task='other page')
            blueprint['slides'].insert(0,other)
            return policy,scope,blueprint
        service.check_policy=unsorted
        _,binding=service.compile_request_payload(pack,with_binding=True)
        paths=[e['field_path'] for e in binding['entries'] if e['source_ref']=='blueprint-current']
        self.assertTrue(paths)
        self.assertTrue(all(p.startswith('slides/1/') for p in paths),paths)
        pack=pack_fixture();pack['confirmed_visible_copy']['blocks'][0]['identity']='自由客户句子'
        service,pack=compiled_fixture(pack)
        with self.assertRaises(ContractValidationError):service.compile_request_payload(pack)

    def test_wrapper_rejects_missing_semantic_annotation(self):
        service,pack=compiled_fixture();payload=service.compile_request_payload(pack)
        payload['non_visible_semantics']['copy_facts'].pop()
        with self.assertRaises(image2_crs.InvalidTransport):
            image2_crs.compile_body({'protocol':TRANSPORT,'request_id':'test','payload':payload})

    def test_decision_only_evidence_keeps_all_current_page_forbidden_statements(self):
        from ai_ppt_studio.domains.materials.image_input_v2 import derive_semantics
        service,pack=compiled_fixture()
        _,_,blueprint=service.check_policy(None)
        slide=blueprint['slides'][0]
        slide['customer_decision_item']={'evidence_refs':['finding-decision-only']}
        evidence=service._current(None,None,'presales-evidence-book')
        evidence['forbidden_extrapolations'] += [
            {'item_id':'decision-ban-1','statement':'不得宣称客户已经采购',
             'source_refs':['finding-decision-only']},
            {'item_id':'decision-ban-2','statement':'不得宣称决策已经完成',
             'source_refs':['finding-decision-only']},
            {'item_id':'other-page-ban','statement':'其它页的限制不应混入',
             'source_refs':['finding-other-page']},
        ]
        semantics,provenance=derive_semantics(pack,slide,evidence,
            blueprint_ref='blueprint-current',evidence_ref='eb-current',slide_index=0)
        limits=[row['text'] for row in semantics['limitations']]
        self.assertIn('不得宣称客户已经采购',limits)
        self.assertIn('不得宣称决策已经完成',limits)
        self.assertNotIn('其它页的限制不应混入',limits)
        for index in (1,2):
            statement=evidence['forbidden_extrapolations'][index]['statement']
            self.assertIn({'source_ref':'eb-current',
                'field_path':f'forbidden_extrapolations/{index}/statement',
                'text_sha256':hashlib.sha256(statement.encode('utf-8')).hexdigest()},provenance)

    def test_v2_free_common_rule_fields_cannot_hide_unscoped_customer_text(self):
        cases=[('title_bar','value'),('background','value')]+[(f,m) for f in ('typography_tokens','color_tokens','fallback_fonts') for m in ('key','value')]
        for field,mode in cases:
            service,pack=compiled_fixture();original=service.check_policy
            def changed(value):
                policy,scope,blueprint=original(value)
                if field.endswith('_tokens') or field=='fallback_fonts':
                    old_key=next(iter(policy['common_rules'][field]))
                    if mode=='key':policy['common_rules'][field]['UNSCOPED_CUSTOMER_KEY']=policy['common_rules'][field][old_key]
                    else:policy['common_rules'][field][old_key]='UNSCOPED_CUSTOMER_SENTENCE'
                else:policy['common_rules'][field]='UNSCOPED_CUSTOMER_SENTENCE'
                return policy,scope,blueprint
            service.check_policy=changed
            with self.subTest(field=field,mode=mode),self.assertRaises(ContractValidationError):service.compile_request_payload(pack)

    def test_adapter_cannot_probe_one_wrapper_then_execute_another(self):
        from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
        service,pack=compiled_fixture();payload=service.compile_request_payload(pack)
        adapter=Image2CommandAdapter(('/untrusted/counterfeit',),'CRS','gpt-image-2',{})
        with patch('ai_ppt_studio.adapters.image2_command.image2_preflight',return_value={'protocol_probe':'passed'}):
            with self.assertRaises(ContractValidationError):adapter.preflight(payload)

    def test_wrapper_v2_probe_and_unknown_or_downgraded_payload_reject(self):
        probe={'protocol':'image-led-image2-preflight/v2','request_id':'nonce', 'generation_protocol':TRANSPORT}
        self.assertEqual(self.accepted(image2_crs.preflight,probe)['generation_protocol'],TRANSPORT)
        bad={**probe,'generation_protocol':'unknown'}
        with self.assertRaises(image2_crs.InvalidTransport):image2_crs.preflight(bad)
        service,pack=compiled_fixture();value=self.accepted(service.compile_request_payload,pack)
        with self.assertRaises(image2_crs.InvalidTransport):image2_crs.compile_body({'protocol':image2_crs.PROTOCOL,'request_id':'test','payload':value})

    def test_compiler_v2_carries_original_copy_for_native_hash_validation(self):
        selection,inventory=rich_fixture()
        copy=selection['slides'][0]['selected_copy']
        copy.update(copy_version=COPY_VERSION,title_item_id=copy['items'][0]['item_id'])
        self.accepted(validate_selected_copy,copy)
        selection['slides'][0]['target_binding']['selected_copy_sha256']=selected_copy_sha256(copy)
        inventory['slides'][0]['target_binding']=deepcopy(selection['slides'][0]['target_binding'])
        _,brief,design,contract=fixture_for(selection,inventory)
        plan=self.accepted(compile_plan,contract,selection,inventory,brief,design)
        self.assertEqual(plan['compiler_version'],'image-led-faithful-compiler/v2')
        self.assertEqual(plan['handoff_version'],'codex-presentations-image-led/v2')
        self.assertEqual(plan['slides'][0]['selected_copy'],copy)

if __name__=='__main__':unittest.main()
