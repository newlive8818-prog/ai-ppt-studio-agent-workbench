"""Synthetic host fixture for the public MCP finding-to-content-to-input chain."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_image2_input_boundary import scope_payload, confirm_scope
from tests.test_v22_content_contracts import evidence_book, decision_context, fit_map, blueprint


def bootstrap(root):
    from ai_ppt_studio.config import RuntimeConfig
    roots=[root/name for name in ('runtime','source','install','upstream')]
    for path in roots: path.mkdir()
    profile=roots[0]/'workspace.json'
    RuntimeConfig.create(*roots).save(profile)
    root=roots[0]/'projects'/'public-finding-e2e'
    kernel=ProjectKernel.initialize(root,project_id='public-finding-e2e')
    ReleaseTargetPolicyService(kernel).bind_current_policy('release-policy',kernel.load().revision)
    raw='  客户合成原文\n未改写的字节🙂  '.encode()
    (root/'synthetic-source.txt').write_bytes(raw)
    mission=MissionMaterialService(kernel)
    draft=mission.save_mission_draft('mission',kernel.load().revision,{
        'topic':'合成售前流程','primary_audience':'测试客户','desired_judgment_or_action':'合成确认'})
    inventory=mission.register_materials('materials',kernel.load().revision,{'sources':[{
        'source_id':'source-public','origin':'user-provided','kind':'file','locator':'project://synthetic-source.txt','sha256':hashlib.sha256(raw).hexdigest()}]})
    confirmation=mission.confirm_mission('mission-confirmed',kernel.load().revision,
        mission_draft_ref=draft,material_mode='materials-provided',material_inventory_ref=inventory,
        user_action_ref='test-user-action://synthetic-finding-e2e',user_message_ref='')
    return {'projectRoot':str(root),'config':str(profile),'revision':kernel.load().revision,'inventory':inventory,'confirmation':confirmation,
        'sourceSha256':hashlib.sha256(raw).hexdigest(),'sourceId':'source-public',
        'evidence':evidence_book(),'context':decision_context(),'fit':fit_map(),'blueprint':blueprint()}


def finish(root, finding_ref):
    kernel=ProjectKernel(root,project_id='public-finding-e2e')
    content=PresalesContentService(kernel);state=kernel.load()
    blueprint_ref=state.artifact_heads['content/reading-blueprint']
    deck=kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))['payload']
    # Real production ReviewSession/PageDecision/batch and test-only trusted host assertion.
    _,session,state=ReviewSessionService(kernel).open_or_resume(command_id='open-review',expected_revision=state.revision,
        review_type='content-full-deck',target_artifact_ref=blueprint_ref,source_version=deck['source_version'],
        source_revision=state.revision-2,open_policy='foreground-if-waiting')
    ContentDecisionService(kernel).save(command_id='approve-page',expected_revision=state.revision,
        review_session_id=session['review_session_id'],source_version=deck['source_version'],slide_id='S01',decision='approved',comment='')
    ContentReviewBatchService(kernel).submit(command_id='review-batch',expected_revision=kernel.load().revision,
        review_session_id=session['review_session_id'],source_version=deck['source_version'])
    content.open_g0_review(command_id='open-g0',expected_revision=kernel.load().revision)
    content.confirm_g0(command_id='synthetic-host-g0',expected_revision=kernel.load().revision,
        **gate_confirmation_kwargs(content.gate_confirmation_context()))
    service=ImageLedService(kernel)
    finding=kernel.artifacts.resolve(ArtifactReference.parse(finding_ref))['payload']
    page=deck['slides'][0]
    strings={page['neutral_title'],page['page_task'],*[row['text'] for row in page['visible_copy_blocks']]}
    allowed=[{'source_sha256':hashlib.sha256(value.encode()).hexdigest(),'source_location':{'kind':'whole-source'},
        'uses':['content-source'],'send_form':'verbatim'} for value in sorted(strings)]
    allowed.append({'source_sha256':finding['source_sha256'],'source_location':finding['source_location'],
        'uses':['content-source'],'send_form':'verbatim'})
    scope=scope_payload(kernel,allowed)
    scope_ref=service.commit_artifact('scope',kernel.load().revision,scope)
    grant=confirm_scope(kernel,scope_ref)
    heads=kernel.load().artifact_heads
    policy={'artifact_type':'image-led-input-policy','project_id':kernel.project_id,'reading_blueprint_ref':blueprint_ref,
        'source_version':deck['source_version'],'material_inventory_ref':heads['materials'],'evidence_book_ref':heads['content/evidence-book'],
        'g0_ref':heads['gate/G0/confirmation'],'release_target_policy_ref':heads['release/target-policy'],
        'authorization_scope_ref':scope_ref,'authorization_ref':grant,'receiver':scope['receiver'],'model':scope['model'],
        'common_rules':{'typography_tokens':{'title':'Arial','body':'Arial'},'color_tokens':{'ink':'#123456'},
            'fallback_fonts':{'macOS':'Arial'},'title_bar':'统一标题栏','background':'统一浅色背景'}}
    policy_ref=service.commit_artifact('policy',kernel.load().revision,policy)
    atom={'atom_id':'public-material-atom','origin_kind':'evidence','origin_id':'fact-1','source_ref':finding_ref,
        'source_id':finding['source_id'],'source_sha256':finding['source_sha256'],'source_location':finding['source_location'],
        'atom_type':'text','use':'content-source','content_sha256':finding['content_sha256']}
    pack={'artifact_type':'image-led-input-pack','project_id':kernel.project_id,'input_policy_ref':policy_ref,
        'slide_id':'S01','page_order':1,'confirmed_visible_copy':{'title':page['neutral_title'],'blocks':page['visible_copy_blocks']},
        'page_goal':page['page_task'],'atoms':[atom]}
    pack_ref=service.commit_artifact('pack',kernel.load().revision,pack)
    compiled=service.compile_request(pack_ref)
    assert compiled['materials'][0]['text'].encode()==(root/'synthetic-source.txt').read_bytes()
    receipts=[json.loads(path.read_text()) for path in kernel.events_root.glob('*.json')]
    finding_receipts=[event for event in receipts if finding_ref in event.get('detached_artifact_refs',[])]
    assert len(finding_receipts)==1
    assert finding_receipts[0]['command_id'].startswith('bridge:add-material:')
    assert finding_receipts[0]['event_type']=='materials.finding-registered'
    return {'finding_ref':finding_ref,'pack_ref':pack_ref,'exact_source_bytes':True,'G0':kernel.load().gate_status['G0'],
        'finding_public_ingress':True,'synthetic_host_only':True}

if __name__=='__main__':
    root=Path(sys.argv[2]).resolve()
    if sys.argv[1]=='bootstrap':
        result=bootstrap(root)
    else:
        from unittest.mock import patch
        from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
        with patch.object(Image2CommandAdapter,'from_environment',side_effect=AssertionError('No adapter is allowed in this test')) as adapter:
            result=finish(root,sys.argv[3])
            result['adapter_calls']=adapter.call_count
    print(json.dumps(result,ensure_ascii=False))
