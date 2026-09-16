"""Private synthetic Runtime transaction coverage; never customer/G0 host proof."""
from copy import deepcopy
from contextlib import ExitStack
from io import BytesIO, StringIO
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ppt_studio.adapters import image2_command, image2_crs
from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.application.image_led_selection import ImageLedSelectionService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.domains.materials.image_input_v2 import visible_copy, customer_strings, validate_used_materials
from ai_ppt_studio.domains.visual.image_led import handoff_selected_copy
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_image_led_requests import input_fixture
from tests.test_image2_input_boundary import scope_payload, confirm_scope, tree_snapshot
from tests.test_image_led_selection import SyntheticTransport, review_candidate
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_image_led_handoff import context
from tests import test_image_led_runtime as runtime_fixtures

def v2_input_fixture(root, *, model='gpt-image-2', include_material=False):
    service,policy,_=input_fixture(root)
    kernel=service.kernel
    def resolve(ref):return kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
    evidence=resolve(policy['evidence_book_ref']);blueprint=resolve(policy['reading_blueprint_ref'])
    # Fixture setup: align the synthetic formal evidence item identity with its
    # exact source-bound b1 block. This is not a product migration or G0 receipt.
    evidence['facts'][0]['item_id']='b1'
    evidence_ref=str(kernel.artifacts.reference_for('presales-evidence-book',evidence))
    blueprint['evidence_book_ref']=evidence_ref
    blueprint_ref=str(kernel.artifacts.reference_for('reading-deck-blueprint',blueprint))
    g0=resolve(policy['g0_ref']);g0['reading_blueprint_ref']=blueprint_ref
    state=kernel.commit(command_id='synthetic-v2-source-setup',expected_revision=kernel.load().revision,
        event_type='synthetic.v2-source-setup',artifact_updates={
            'content/evidence-book':('presales-evidence-book',evidence),
            'content/reading-blueprint':('reading-deck-blueprint',blueprint),
            'gate/G0/confirmation':('g0-confirmation',g0)})
    words=set()
    for slide in blueprint['slides']:
        words.update([slide['neutral_title'],slide['page_task']]);words.update(b['text'] for b in slide['visible_copy_blocks'])
    for row in evidence['facts']:words.update(row.get('limitations',[]))
    for row in evidence['forbidden_extrapolations']:words.add(row['statement'])
    from ai_ppt_studio.domains.materials.image_input_v2 import common_rule_strings
    words.update(common_rule_strings(policy['common_rules']))
    atoms=[]
    if include_material:
        # Reuse the fixture's registered local source and real finding resolver;
        # this optional text material has the same source-bound evidence identity.
        source_ref=evidence['facts'][0]['source_refs'][0]
        finding=resolve(source_ref)
        atoms=[{'atom_id':'synthetic-source-atom','origin_kind':'evidence','origin_id':'b1',
            'source_ref':source_ref,'source_id':finding['source_id'],
            'source_sha256':finding['source_sha256'],'source_location':finding['source_location'],
            'atom_type':'text','use':'content-source','content_sha256':finding['content_sha256']}]
    scope=scope_payload(kernel,[{'source_sha256':hashlib.sha256(t.encode()).hexdigest(),
        'source_location':{'kind':'whole-source'},'uses':['content-source'],'send_form':'verbatim'} for t in sorted(words)])
    scope.update(receiver='CRS',model=model)
    scope['allowed'] += [{'source_sha256':a['source_sha256'],'source_location':a['source_location'],
                         'uses':[a['use']],'send_form':'verbatim'} for a in atoms]
    scope_ref=service.commit_artifact('v2-scope',kernel.load().revision,scope)
    grant=confirm_scope(kernel,scope_ref,identity='v2-synthetic-material-scope')
    policy.update(reading_blueprint_ref=blueprint_ref,evidence_book_ref=evidence_ref,
        g0_ref=state.artifact_heads['gate/G0/confirmation'],authorization_scope_ref=scope_ref,authorization_ref=grant,
        receiver='CRS',model=model)
    policy_ref=service.commit_artifact('v2-policy',kernel.load().revision,policy)
    packs=[]
    for slide in blueprint['slides']:
        pack={'artifact_type':'image-led-input-pack','pack_version':'image-led-input-pack/v2',
            'project_id':kernel.project_id,'input_policy_ref':policy_ref,'slide_id':slide['slide_id'],'page_order':slide['order'],
            'confirmed_visible_copy':{'title':slide['neutral_title'],'title_target':{'kind':'standalone','item_id':'title'},
                                      'blocks':deepcopy(slide['visible_copy_blocks'])},
            'page_goal':slide['page_task'],'atoms':deepcopy(atoms),'required_atom_ids':[]}
        packs.append(service.commit_artifact('v2-pack-'+slide['slide_id'],kernel.load().revision,pack))
    return service,policy,packs

def v2_candidate(service,pack_ref,suffix):
    kernel=service.kernel;commands=ProjectCommandService(kernel)
    _,task,_=commands.request_agent_action('v2-generate-'+suffix,kernel.load().revision,
        action_type='generate-slide-images',target_refs=[pack_ref],instructions='')
    response_ref=service.execute_generation(task['task_id'],transport=SyntheticTransport())
    pack=kernel.artifacts.resolve(ArtifactReference.parse(pack_ref))['payload']
    payload={'artifact_type':'image-led-candidate','project_id':kernel.project_id,'request_id':task['task_id'],
        'generation_response_ref':response_ref,'pack_ref':pack_ref,'slide_id':pack['slide_id'],
        'page_order':pack['page_order'],'selected_copy':visible_copy(pack),'material_roles':[]}
    ref,_=commands.commit_noncontent_agent_result(command_id='v2-candidate-'+suffix,
        expected_revision=kernel.load().revision,task_id=task['task_id'],request_kind='visual-contract',raw_request_payload=payload)
    return ref,payload

def v2_selection_fixture(root):
    service,_,packs=v2_input_fixture(root);rows=[]
    for i,pack in enumerate(packs):
        candidate,_=v2_candidate(service,pack,str(i))
        review=review_candidate(service,candidate,'v2-'+str(i))
        rows.append({'candidate_ref':candidate,'source_review_ref':review,'accepted_deviations':[]})
    proposal=service.commit_artifact('v2-proposal',service.kernel.load().revision,
        {'artifact_type':'image-led-selection-proposal','project_id':service.kernel.project_id,'candidates':rows})
    context=service.confirmation_context(proposal)
    selected=service.confirm('v2-select',service.kernel.load().revision,target_ref=proposal,choice='approved',
        **gate_confirmation_kwargs(context,identity_ref='test-host-confirmation://v2-only'))
    return ImageLedSelectionService(service.kernel),selected


def exact_crs_environment(model):
    wrapper=str(Path(image2_command.__file__).resolve().with_name('image2_crs.py'))
    command=[sys.executable,wrapper]
    if model == image2_crs.SUNBURST_MODEL:
        command += ['--model',model]
    return {'AI_PPT_IMAGE2_ADAPTER_COMMAND':json.dumps(command),
            'AI_PPT_IMAGE2_RECEIVER':'CRS','AI_PPT_IMAGE2_MODEL':model,
            'AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST':'[]'}


class OfflineKnownCrsBoundary:
    """Run the real fixed wrapper main in-process at its subprocess boundary.

    Only helper output and HTTP responses are synthetic. The shim records and
    checks exact argv, then executes main/preflight/generate/compile_body. It is
    not child-process, current-account, remote-model, or real-host evidence.
    """
    def __init__(self, *, model=image2_crs.SUNBURST_MODEL, probe_change=None,
                 upstream_model=None, transport_model=None):
        self.model=model
        self.command=json.loads(exact_crs_environment(model)['AI_PPT_IMAGE2_ADAPTER_COMMAND'])
        self.probe_change=probe_change
        self.upstream_model=upstream_model or model
        self.transport_model=transport_model
        self.probes=[];self.generations=[];self.helper_calls=[];self.http_calls=[];self.receipts=[]
        stream=BytesIO()
        Image.new('RGB',(2048,1152),'#203040').save(stream,format='PNG')
        self.image=stream.getvalue()

    def __enter__(self):
        self.stack=ExitStack()
        self.stack.enter_context(patch.object(image2_command.subprocess,'run',side_effect=self.run))
        opener=self.stack.enter_context(patch.object(image2_crs.urllib.request,'build_opener'))
        opener.return_value.open.side_effect=self.open
        return self

    def __exit__(self,*args):
        return self.stack.__exit__(*args)

    def run(self, command, **options):
        argv=list(command)
        if argv == [image2_crs.HELPER]:
            self.helper_calls.append(argv)
            return subprocess.CompletedProcess(argv,0,stdout=b'synthetic-offline-key')
        probe=argv == self.command+['--preflight']
        if not probe and argv != self.command:
            raise AssertionError('Runtime attempted an unrecognized wrapper argv')
        request=json.loads(options['input'])
        (self.probes if probe else self.generations).append(deepcopy(request))
        self.options=options
        stdout=StringIO();stderr=StringIO()
        with patch.object(sys,'stdin',StringIO(options['input'].decode('utf-8'))), patch.object(sys,'stdout',stdout), patch.object(sys,'stderr',stderr):
            code=image2_crs.main(argv[2:])
        raw=stdout.getvalue()
        if code == 0:
            value=json.loads(raw)
            if probe and self.probe_change:
                value.update(self.probe_change)
            elif not probe:
                if self.transport_model is not None:
                    value['model']=self.transport_model
                self.receipts.append(deepcopy(value))
            raw=json.dumps(value)
        return subprocess.CompletedProcess(argv,code,stdout=raw.encode())

    def open(self, request, **options):
        self.http_calls.append((request,options))
        result={'model':self.upstream_model,
                'data':[{'b64_json':base64.b64encode(self.image).decode()}]}
        class Response:
            status=200
            headers={'x-request-id':'synthetic-offline-response'}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return json.dumps(result).encode()
        return Response()

class ImageLedV2RuntimeTests(unittest.TestCase):
    def test_real_private_transactions_bind_v2_request_candidate_and_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            service,ref=v2_selection_fixture(Path(folder));selection=service.current_selection(ref)
            self.assertEqual(len(selection['slides']),3)
            self.assertTrue(all(s['selected_copy']['copy_version']=='image-led-selected-copy/v2' for s in selection['slides']))
            before=tree_snapshot(Path(folder));service.current_selection(ref)
            self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_full_native_context_and_result_domain_keep_v2_copy(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime_fixtures,'selection_fixture',v2_selection_fixture):
            kernel,_=runtime_fixtures.g1_fixture(Path(folder))
            before=tree_snapshot(Path(folder));handoff=context(kernel)['layers']['visual_handoff']['renderer_handoff']
            self.assertEqual(handoff['handoff_version'],'codex-presentations-image-led/v2')
            for slide in handoff['slides']:
                self.assertEqual(handoff_selected_copy(slide,handoff['handoff_version']),slide['selected_copy'])
                bad=deepcopy(slide);bad['selected_copy'].pop('copy_version')
                with self.assertRaises(ContractValidationError):handoff_selected_copy(bad,handoff['handoff_version'])
            self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_optional_pool_subset_and_legacy_all_pool_contract(self):
        fields=('atom_id','source_ref','content_sha256','use')
        atoms=[dict(zip(fields,[f'a{i}',f'artifact://material-finding/{str(i)*64}',str(i)*64,'real-material'])) for i in (1,2)]
        pack={'pack_version':'image-led-input-pack/v2','atoms':atoms,'required_atom_ids':[]}
        for roles in ([],[atoms[0]],[atoms[1]],atoms):validate_used_materials(pack,roles)
        for roles in ([atoms[0],atoms[0]],list(reversed(atoms)),[{**atoms[0],'use':'style-reference'}],
                      [{**atoms[0],'atom_id':'not-sent'}],[{**atoms[0],'content_sha256':'f'*64}]):
            with self.assertRaises(ContractValidationError):validate_used_materials(pack,roles)
        with self.assertRaises(ContractValidationError):validate_used_materials({'atoms':atoms},[atoms[0]])
        validate_used_materials({'atoms':atoms},atoms)

    def test_actual_known_wrapper_v2_probe_runs_without_auth_or_http(self):
        from ai_ppt_studio.adapters.image2_command import image2_preflight, Image2CommandAdapter
        for model in (image2_crs.MODEL,image2_crs.SUNBURST_MODEL):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as folder:
                service,_,packs=v2_input_fixture(Path(folder),model=model,include_material=True)
                payload=service.compile_request(packs[0]);before=tree_snapshot(Path(folder))
                with patch.dict(os.environ,exact_crs_environment(model),clear=True):
                    probe=image2_preflight(generation_protocol='image-led-image2-transport/v2')
                    self.assertEqual(probe['protocol_probe'],'passed')
                    self.assertEqual(probe['external_connection'],'not-tested')
                    Image2CommandAdapter.from_environment().preflight(payload)
                self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_actual_v2_renderer_bytes_pass_original_copy_result_validator(self):
        from tests.test_image_led_results import render_runtime_fixture
        from ai_ppt_studio.application.image_led_results import preflight_output
        with tempfile.TemporaryDirectory(prefix='image-led-v2-result-') as folder, patch.object(runtime_fixtures,'selection_fixture',v2_selection_fixture):
            root=Path(folder).resolve()
            kernel,task,handoff,output=render_runtime_fixture(root)
            self.assertEqual(handoff['handoff_version'],'codex-presentations-image-led/v2')
            self.assertEqual(preflight_output(output,handoff,root),output)
            commands=ProjectCommandService(kernel)
            result_ref,_=commands.commit_noncontent_agent_result(command_id='v2-native-result',
                expected_revision=kernel.load().revision,task_id=task['task_id'],request_kind='visual-contract',
                raw_request_payload={'artifact_type':'image-led-build-result','project_id':kernel.project_id,'output':output})
            self.assertTrue(result_ref.startswith('artifact://image-led-build-result/'))

    def test_protocol_capability_failure_blocks_bridge_before_queue_and_network(self):
        from ai_ppt_studio.application.v16_bridge import dispatch_v16
        from tests.test_image2_preflight import configured
        with tempfile.TemporaryDirectory() as folder:
            service,_,packs=v2_input_fixture(Path(folder));before=tree_snapshot(Path(folder))
            request={'operation':'request-agent-action','project_root':folder,'command_id':'blocked-v2',
                'expected_revision':service.kernel.load().revision,'action_type':'generate-slide-images',
                'target_refs':[packs[0]],'instructions':''}
            with patch.dict(os.environ,configured(),clear=True), patch(
                'ai_ppt_studio.adapters.image2_command.image2_preflight',return_value={'protocol_probe':'failed'}), patch(
                'ai_ppt_studio.adapters.image2_command.Image2CommandAdapter.generate') as generate:
                with self.assertRaisesRegex(ContractValidationError,'CAPABILITY_GAP'):
                    dispatch_v16(request)
                generate.assert_not_called()
            self.assertEqual(tree_snapshot(Path(folder)),before)

class ImageLedSunburstRuntimeTests(unittest.TestCase):
    def action(self,service,pack_ref,**changes):
        return {'operation':'request-agent-action','project_root':str(service.kernel.project_root),
            'command_id':'sunburst-runtime-action','expected_revision':service.kernel.load().revision,
            'action_type':'generate-slide-images','target_refs':[pack_ref],'instructions':'',
            'generation_intent':'new','generation_request_id':'synthetic-sunburst-request',**changes}

    def resolve(self,service,ref):
        return service.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']

    def assert_no_external_send(self,boundary):
        self.assertEqual(boundary.generations,[])
        self.assertEqual(boundary.helper_calls,[])
        self.assertEqual(boundary.http_calls,[])

    def assert_rejected_before_queue(self,service,request,environment,*,pattern='IMAGE_LED_',probe_change=None):
        root=service.kernel.project_root
        before=tree_snapshot(root)
        tasks={k:v for k,v in service.kernel.load().artifact_heads.items() if k.startswith('agent/task/')}
        with patch.dict(os.environ,environment,clear=True), OfflineKnownCrsBoundary(probe_change=probe_change) as boundary:
            with self.assertRaisesRegex((ContractValidationError,ArtifactReferenceError),pattern):
                dispatch_v16(request)
            self.assert_no_external_send(boundary)
        self.assertEqual(tree_snapshot(root),before)
        self.assertEqual({k:v for k,v in service.kernel.load().artifact_heads.items() if k.startswith('agent/task/')},tasks)
        return boundary

    def test_formal_bridge_exact_old_and_sunburst_bind_complete_v2_material_and_response(self):
        for model in (image2_crs.MODEL,image2_crs.SUNBURST_MODEL):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as folder:
                service,policy,packs=v2_input_fixture(Path(folder),model=model,include_material=True)
                kernel=service.kernel
                pack=self.resolve(service,packs[0]);payload,binding=service.compile_request(packs[0],with_binding=True)
                source=self.resolve(service,pack['atoms'][0]['source_ref'])
                scope=self.resolve(service,policy['authorization_scope_ref'])
                grant=self.resolve(service,policy['authorization_ref'])
                self.assertEqual(scope['model'],model)
                self.assertEqual(policy['model'],model)
                self.assertEqual(grant['scope_id'],policy['authorization_scope_ref'])
                self.assertEqual(payload['model'],model)
                self.assertEqual(payload['confirmed_visible_copy'],visible_copy(pack))
                self.assertEqual(payload['confirmed_visible_copy']['copy_version'],'image-led-selected-copy/v2')
                material=payload['materials'][0]
                self.assertEqual(material['atom_id'],pack['atoms'][0]['atom_id'])
                self.assertEqual(material['content_sha256'],source['content_sha256'])
                self.assertEqual(hashlib.sha256(material['text'].encode()).hexdigest(),source['content_sha256'])
                self.assertEqual(payload['non_visible_semantics']['material_use'][0],{
                    'material_id':material['atom_id'],'image_number':None,'use':'content-source',
                    'presence':'optional','purpose':'','identity':'来源事实','limitations':['未包含量化影响']})
                self.assertEqual(binding['material_aliases'],{material['atom_id']:'material-0001'})
                content_heads={k:v for k,v in kernel.load().artifact_heads.items() if k.startswith('content/') or k=='gate/G0/confirmation'}
                with patch.dict(os.environ,exact_crs_environment(model),clear=True),OfflineKnownCrsBoundary(model=model) as boundary:
                    reply=dispatch_v16(self.action(service,packs[0]))['result']
                self.assertEqual(len(boundary.generations),1)
                self.assertEqual(len(boundary.helper_calls),1)
                self.assertEqual(len(boundary.http_calls),1)
                self.assertEqual(len(boundary.probes),2)
                self.assertTrue(all(p['protocol']=='image-led-image2-preflight/v2' and
                    p['generation_protocol']=='image-led-image2-transport/v2' for p in boundary.probes))
                sent=boundary.generations[0]
                self.assertEqual(sent,{'protocol':'image-led-image2-transport/v2',
                    'request_id':reply['task']['task_id'],'payload':payload})
                queued=self.resolve(service,reply['task']['context_pack_ref'])['layers']['image_led_request']
                self.assertEqual(queued['semantic_binding'],binding)
                self.assertEqual(queued['payload'],payload)
                request,options=boundary.http_calls[0]
                self.assertEqual(request.full_url,image2_crs.GENERATIONS_URL)
                self.assertEqual(request.get_header('Content-type'),'application/json')
                body=json.loads(request.data)
                self.assertEqual({k:v for k,v in body.items() if k!='prompt'},
                    {'model':model,'n':1,'size':'2048x1152','quality':'high','output_format':'png',
                     **({'stream':True,'partial_images':1} if model == 'gpt-image-2' else {})})
                prompt=json.loads(body['prompt'])
                self.assertEqual([i['text'] for i in prompt['confirmed_visible_copy']['items']],
                    [i['text'] for i in payload['confirmed_visible_copy']['items']])
                self.assertEqual(prompt['non_visible_semantics']['material_use'][0]['material_id'],'material-0001')
                self.assertEqual(prompt['materials'],[{'type':'text','use':'content-source',
                    'material_id':'material-0001','text':material['text']}])
                self.assertEqual(prompt['non_visible_semantics']['limitations'],payload['non_visible_semantics']['limitations'])
                for internal in ('artifact://',str(kernel.project_root),material['atom_id'],source['source_id']):
                    self.assertNotIn(internal,body['prompt'])
                self.assertEqual(boundary.receipts[0]['model'],model)
                response=reply['generation_response']
                self.assertEqual(response['status'],'completed')
                self.assertEqual(response['pack_ref'],packs[0])
                self.assertEqual(response['request_id'],sent['request_id'])
                self.assertEqual(response['payload_sha256'],queued['payload_sha256'])
                self.assertEqual(response['image_sha256'],hashlib.sha256(boundary.image).hexdigest())
                self.assertEqual(response['image_size'],[2048,1152])
                self.assertTrue(reply['generation_usability']['candidate_eligible'])
                self.assertEqual({k:v for k,v in kernel.load().artifact_heads.items() if k in content_heads},content_heads)
                self.assertEqual(kernel.load().gate_status['G0'],'passed')
                self.assertEqual(kernel.load().gate_status['G3'],'locked')

    def test_scope_model_and_grant_scope_mismatch_fail_registration_and_formal_dispatch(self):
        for mismatch in ('old-scope-new-model','old-grant-new-scope'):
            with self.subTest(mismatch=mismatch),tempfile.TemporaryDirectory() as folder:
                service,policy,packs=v2_input_fixture(Path(folder),include_material=True)
                kernel=service.kernel
                bad=deepcopy(policy);bad['model']=image2_crs.SUNBURST_MODEL
                if mismatch=='old-grant-new-scope':
                    scope=self.resolve(service,policy['authorization_scope_ref'])
                    scope['model']=image2_crs.SUNBURST_MODEL
                    bad['authorization_scope_ref']=service.commit_artifact('new-model-scope',kernel.load().revision,scope)
                before=tree_snapshot(Path(folder))
                with OfflineKnownCrsBoundary() as boundary:
                    with self.assertRaisesRegex(ContractValidationError,'UNAUTHORIZED|CONFIRMATION'):
                        service.commit_artifact('invalid-model-policy',kernel.load().revision,bad)
                    self.assert_no_external_send(boundary)
                self.assertEqual(tree_snapshot(Path(folder)),before)
                # Deliberately corrupt fixture heads to test the consumer too.
                # No trusted grant is invented for the mismatched scope.
                bad_ref=str(kernel.artifacts.reference_for('image-led-input-policy',bad))
                pack=self.resolve(service,packs[0]);pack['input_policy_ref']=bad_ref
                state=kernel.commit(command_id='synthetic-corrupt-policy-heads',expected_revision=kernel.load().revision,
                    event_type='test.corrupt-policy-heads',artifact_updates={
                        'visual/image-led/input-policy':('image-led-input-policy',bad),
                        'visual/image-led/pack/'+pack['slide_id']:('image-led-input-pack',pack)})
                pack_ref=state.artifact_heads['visual/image-led/pack/'+pack['slide_id']]
                self.assert_rejected_before_queue(service,self.action(service,pack_ref),
                    exact_crs_environment(image2_crs.SUNBURST_MODEL),pattern='UNAUTHORIZED|CONFIRMATION')

    def test_configured_model_payload_and_exact_argv_mismatch_have_zero_queue_helper_http(self):
        old=image2_crs.MODEL;new=image2_crs.SUNBURST_MODEL
        for policy_model,configured_model,argv_model in ((old,new,new),(new,old,old),(new,new,old),(old,old,new)):
            with self.subTest(policy=policy_model,configured=configured_model,argv=argv_model),tempfile.TemporaryDirectory() as folder:
                service,_,packs=v2_input_fixture(Path(folder),model=policy_model)
                env=exact_crs_environment(argv_model);env['AI_PPT_IMAGE2_MODEL']=configured_model
                boundary=self.assert_rejected_before_queue(service,self.action(service,packs[0]),env,
                    pattern='UNAUTHORIZED|CAPABILITY_GAP')
                self.assertEqual(boundary.probes,[])

    def test_bad_probe_nonce_model_and_v2_downgrade_fail_before_queue_helper_http(self):
        for changes in ({'request_id':'wrong-nonce'},{'model':image2_crs.MODEL},
                        {'generation_protocol':'image-led-image2-transport/v1'}):
            with self.subTest(changes=changes),tempfile.TemporaryDirectory() as folder:
                service,_,packs=v2_input_fixture(Path(folder),model=image2_crs.SUNBURST_MODEL,include_material=True)
                boundary=self.assert_rejected_before_queue(service,self.action(service,packs[0]),
                    exact_crs_environment(image2_crs.SUNBURST_MODEL),pattern='CAPABILITY_GAP',probe_change=changes)
                self.assertEqual(len(boundary.probes),1)

    def test_previous_pack_cannot_follow_a_new_exact_model_policy_before_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            service,policy,packs=v2_input_fixture(Path(folder),include_material=True)
            kernel=service.kernel
            original_scope=self.resolve(service,policy['authorization_scope_ref'])
            scope=deepcopy(original_scope);scope['model']=image2_crs.SUNBURST_MODEL
            scope_ref=service.commit_artifact('new-model-scope',kernel.load().revision,scope)
            grant_ref=confirm_scope(kernel,scope_ref,identity='synthetic-new-exact-model')
            replacement={**policy,'model':image2_crs.SUNBURST_MODEL,
                'authorization_scope_ref':scope_ref,'authorization_ref':grant_ref}
            service.commit_artifact('new-model-policy',kernel.load().revision,replacement)
            boundary=self.assert_rejected_before_queue(service,self.action(service,packs[0]),
                exact_crs_environment(image2_crs.SUNBURST_MODEL),pattern='current|stale|exact')
            self.assertEqual(boundary.probes,[])
            self.assertEqual(self.resolve(service,policy['authorization_scope_ref']),original_scope)

    def test_queued_model_policy_revocation_and_source_drift_reject_before_claim_or_send(self):
        for drift in ('configured-model','policy-model','revoked-grant','source-bytes'):
            with self.subTest(drift=drift),tempfile.TemporaryDirectory() as folder:
                service,policy,packs=v2_input_fixture(Path(folder),model=image2_crs.SUNBURST_MODEL,include_material=True)
                kernel=service.kernel
                _,task,_=ProjectCommandService(kernel).request_agent_action('queue-drift',kernel.load().revision,
                    action_type='generate-slide-images',target_refs=[packs[0]],instructions='')
                env=exact_crs_environment(image2_crs.SUNBURST_MODEL)
                if drift=='configured-model':
                    env=exact_crs_environment(image2_crs.MODEL)
                elif drift=='policy-model':
                    scope=self.resolve(service,policy['authorization_scope_ref']);scope['model']=image2_crs.MODEL
                    scope_ref=service.commit_artifact('replace-model-scope',kernel.load().revision,scope)
                    grant_ref=confirm_scope(kernel,scope_ref,identity='synthetic-replacement-model')
                    policy.update(model=image2_crs.MODEL,authorization_scope_ref=scope_ref,authorization_ref=grant_ref)
                    service.commit_artifact('replace-model-policy',kernel.load().revision,policy)
                elif drift=='revoked-grant':
                    confirm_scope(kernel,policy['authorization_scope_ref'],'revoked','synthetic-after-queue')
                else:
                    (Path(folder)/'fixture-source.txt').write_text('synthetic source bytes drifted')
                before=tree_snapshot(Path(folder))
                with patch.dict(os.environ,env,clear=True),OfflineKnownCrsBoundary() as boundary:
                    with self.assertRaises((ContractValidationError,ArtifactReferenceError)):
                        dispatch_v16({'operation':'execute-image-led-generation','project_root':folder,
                            'task_id':task['task_id'],'expected_revision':kernel.load().revision})
                    self.assert_no_external_send(boundary)
                    self.assertEqual(boundary.probes,[])
                self.assertEqual(tree_snapshot(Path(folder)),before)
                self.assertNotIn('project/image-led/request/'+task['task_id'],kernel.load().artifact_heads)

    def test_wrong_upstream_or_transport_model_is_unknown_after_one_http_and_recovery_never_resends(self):
        for mismatch in ('upstream','transport'):
            with self.subTest(mismatch=mismatch),tempfile.TemporaryDirectory() as folder:
                service,_,packs=v2_input_fixture(Path(folder),model=image2_crs.SUNBURST_MODEL,include_material=True)
                env=exact_crs_environment(image2_crs.SUNBURST_MODEL)
                options={mismatch+'_model':image2_crs.MODEL}
                with patch.dict(os.environ,env,clear=True),OfflineKnownCrsBoundary(**options) as boundary:
                    reply=dispatch_v16(self.action(service,packs[0]))['result']
                    response=reply['generation_response']
                    self.assertEqual(response['status'],'unknown')
                    self.assertFalse(reply['generation_usability']['candidate_eligible'])
                    self.assertNotIn('image_base64',response)
                    self.assertNotIn('image_sha256',response)
                    self.assertEqual(len(boundary.generations),1)
                    self.assertEqual(len(boundary.helper_calls),1)
                    self.assertEqual(len(boundary.http_calls),1)
                    self.assertEqual(json.loads(boundary.http_calls[0][0].data)['model'],image2_crs.SUNBURST_MODEL)
                    before=tree_snapshot(Path(folder));probe_count=len(boundary.probes)
                    recovered=dispatch_v16(self.action(service,packs[0],generation_intent='recover'))['result']
                    self.assertEqual(recovered['generation_response'],response)
                    self.assertEqual(recovered['generation_response_ref'],reply['generation_response_ref'])
                    self.assertEqual(tree_snapshot(Path(folder)),before)
                    self.assertEqual(len(boundary.probes),probe_count)
                    with self.assertRaisesRegex(ContractValidationError,'REQUEST_UNKNOWN'):
                        dispatch_v16({'operation':'execute-image-led-generation','project_root':folder,
                            'task_id':reply['task']['task_id'],'expected_revision':service.kernel.load().revision})
                    self.assertEqual(tree_snapshot(Path(folder)),before)
                    self.assertEqual(len(boundary.generations),1)
                    self.assertEqual(len(boundary.helper_calls),1)
                    self.assertEqual(len(boundary.http_calls),1)
                self.assertFalse(any(k.startswith('visual/image-led/candidate/') for k in service.kernel.load().artifact_heads))

    def test_rejected_request_has_no_recoverable_queue_or_file_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            service,_,packs=v2_input_fixture(Path(folder),model=image2_crs.SUNBURST_MODEL)
            request=self.action(service,packs[0])
            self.assert_rejected_before_queue(service,request,exact_crs_environment(image2_crs.MODEL),pattern='UNAUTHORIZED')
            self.assert_rejected_before_queue(service,self.action(service,packs[0],generation_intent='recover'),
                exact_crs_environment(image2_crs.SUNBURST_MODEL),pattern='REQUEST')


if __name__=='__main__':unittest.main()
