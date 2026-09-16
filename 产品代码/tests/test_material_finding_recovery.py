"""Formal finding registration through the existing bridge; only synthetic sources."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.domains.materials.image_input_contracts import overlaps
from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import evidence_book


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class FindingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.kernel = ProjectKernel.initialize(self.root, project_id='finding-test')
        self.raw = '  原文\n保持字节🙂  '.encode()
        self.path = self.root / 'source.txt'
        self.path.write_bytes(self.raw)
        self.inventory = MissionMaterialService(self.kernel).register_materials('inventory', 0, {'sources': [{
            'source_id': 'source-one', 'origin': 'user-provided', 'kind': 'file',
            'locator': 'project://source.txt', 'sha256': digest(self.raw)}]})
        self.request = {'operation': 'add-material', 'project_root': str(self.root),
            'expected_revision': self.kernel.load().revision, 'material_type': 'finding',
            'material_inventory_ref': self.inventory, 'source_id': 'source-one',
            'source_sha256': digest(self.raw), 'source_location': {'kind': 'whole-source'},
            'content_kind': 'text', 'exclusion_mode': 'scope'}

    def register(self, **updates):
        return dispatch_v16({**self.request, **updates})['result']['artifact_ref']

    def rejected(self, request, errors=(ContractValidationError, RevisionConflictError)):
        before = snapshot(self.root)
        with self.assertRaises(errors):
            dispatch_v16(request)
        self.assertEqual(before, snapshot(self.root))

    def test_formal_finding_is_detached_exact_and_replays_original_request(self):
        before = self.kernel.load()
        try:
            ref = self.register()
        except ContractValidationError as error:
            self.fail(f'Existing add-material route must register finding: {error}')
        payload = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual(payload, {'schema_version': 1, 'artifact_type': 'material-finding',
            'project_id': self.kernel.project_id, 'material_inventory_ref': self.inventory,
            'source_id': 'source-one', 'source_sha256': digest(self.raw),
            'source_location': {'kind': 'whole-source'}, 'content_kind': 'text',
            'exclusion_mode': 'scope', 'content_sha256': digest(self.raw)})
        after = self.kernel.load()
        self.assertEqual(before.artifact_heads, after.artifact_heads)
        self.assertEqual(before.gate_status, after.gate_status)
        self.assertEqual(after.revision, before.revision + 1)
        stable = snapshot(self.root)
        self.assertEqual(ref, self.register())
        self.assertEqual(stable, snapshot(self.root))
        self.rejected({**self.request, 'source_location': {'kind': 'text-range', 'start': 0, 'end': 2}})

    def test_direct_bridge_rejects_import_fields_on_finding_and_finding_fields_on_import(self):
        for field, value in {'value': '', 'data_base64': '', 'label': '', 'filename': '', 'mime_type': '',
                'payload': {}, 'kind': 'material-finding', 'content_sha256': digest(self.raw), 'unexpected': True}.items():
            with self.subTest(field=field):
                self.rejected({**self.request, field: value})
        for field in ('source_id', 'material_inventory_ref', 'content_kind', 'source_location', 'exclusion_mode', 'source_sha256'):
            with self.subTest(import_field=field):
                request = {'operation': 'add-material', 'project_root': str(self.root),
                    'expected_revision': self.kernel.load().revision, 'material_type': 'text', 'value': 'new',
                    field: self.request[field]}
                self.rejected(request)

    def test_production_evidence_rejects_symbolic_finding_without_writes(self):
        state = self.kernel.commit(command_id='mission', expected_revision=self.kernel.load().revision,
            event_type='test.mission', artifact_updates={'mission/confirmation': ('mission-confirmation', {'material_mode': 'material-backed'})})
        value = evidence_book()
        value['mission_confirmation_ref'] = state.artifact_heads['mission/confirmation']
        value['material_inventory_ref'] = self.inventory
        before = snapshot(self.root)
        with self.assertRaises(Exception):
            PresalesContentService(self.kernel).build_evidence_book('evidence', state.revision, value)
        self.assertEqual(before, snapshot(self.root))

    def test_registration_negative_inputs_and_direct_service_are_zero_write(self):
        from ai_ppt_studio.application.project_service import ProjectCommandService
        from ai_ppt_studio.application.material_finding_service import MaterialFindingService
        bad_values = [
            {"source_id": "absent"}, {"source_sha256": "a" * 64},
            {"material_inventory_ref": "artifact://material-inventory/" + "c" * 64},
            {"source_location": {"kind": "object", "page": 1, "object_id": "missing"}},
            {"source_location": {"kind": "text-range", "start": 0, "end": 999}},
            {"source_location": {"kind": "whole-source", "extra": True}},
            {"content_kind": "image"}, {"exclusion_mode": "image-content"},
            {"content_kind": []}, {"exclusion_mode": []}, {"expected_revision": True},
        ]
        for update in bad_values:
            with self.subTest(update=update): self.rejected({**self.request, **update})
        fields = {key:value for key,value in self.request.items() if key not in {"operation","project_root","material_type","expected_revision"}}
        for update in ({"payload": {}}, {"kind": "material-finding"}, {"content_sha256": digest(self.raw)}, {"label": ""}):
            before=snapshot(self.root)
            with self.subTest(direct=update), self.assertRaises(ContractValidationError):
                ProjectCommandService(self.kernel).add_material("direct", self.kernel.load().revision,
                    material_type="finding", **fields, **update)
            self.assertEqual(before,snapshot(self.root))
        service=MaterialFindingService(self.kernel)
        ref=service.register("fixed-id",self.kernel.load().revision,fields)
        before=snapshot(self.root)
        self.assertEqual(ref,service.register("fixed-id",0,fields))
        with self.assertRaisesRegex(ContractValidationError,"different semantics"):
            service.register("fixed-id",self.kernel.load().revision,{**fields,"source_location":{"kind":"text-range","start":0,"end":2}})
        self.assertEqual(before,snapshot(self.root))

    def test_source_mutation_and_cas_during_extraction_leave_no_finding(self):
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        from unittest.mock import patch
        self.path.write_bytes(b"source changed before finding")
        self.rejected(self.request)
        self.path.write_bytes(self.raw)
        original=MaterialSourceReader.extract
        after_concurrent={}
        def concurrent(reader,*args,**kwargs):
            value=original(reader,*args,**kwargs)
            self.kernel.commit(command_id="concurrent",expected_revision=self.kernel.load().revision,
                event_type="test.concurrent",artifact_updates={})
            after_concurrent.update(snapshot(self.root))
            return value
        with patch.object(MaterialSourceReader,"extract",concurrent),self.assertRaises(RevisionConflictError):
            self.register()
        self.assertEqual(after_concurrent,snapshot(self.root))

    def test_legacy_foreign_stale_and_false_content_findings_never_become_new_evidence(self):
        from tests.material_finding_fixtures import replace_refs
        from ai_ppt_studio.errors import ArtifactReferenceError
        ref=self.register()
        valid=self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        state=self.kernel.commit(command_id='mission',expected_revision=self.kernel.load().revision,
            event_type='test.mission',artifact_updates={'mission/confirmation':('mission-confirmation',{'material_mode':'materials-provided'})})
        for kind,payload in [
            ('material-finding',{'source_id':'source-one','source_sha256':digest(self.raw)}),
            ('source-material',valid),
            ('material-finding',{**valid,'project_id':'different-project'}),
            ('material-finding',{**valid,'material_inventory_ref':'artifact://material-inventory/'+'c'*64}),
            ('material-finding',{**valid,'content_sha256':'a'*64}),
        ]:
            with self.subTest(kind=kind,payload=payload):
                bad_ref=str(self.kernel.artifacts.reference_for(kind,payload))
                self.kernel.commit(command_id=f'corrupt-{self.kernel.load().revision}',expected_revision=self.kernel.load().revision,
                    event_type='test.explicit-forged-finding',artifact_updates={},detached_artifacts=((kind,payload),))
                value=replace_refs(evidence_book(),bad_ref,'unused')
                value['mission_confirmation_ref']=state.artifact_heads['mission/confirmation']
                value['material_inventory_ref']=self.inventory
                before=snapshot(self.root)
                with self.assertRaises((ContractValidationError,ArtifactReferenceError)):
                    PresalesContentService(self.kernel).build_evidence_book('reject-forged',self.kernel.load().revision,value)
                self.assertEqual(before,snapshot(self.root))

    def test_existing_import_variants_keep_their_source_behavior(self):
        import base64
        from ai_ppt_studio.application.project_service import ProjectCommandService
        for material_type, fields, kind in [
            (' text ', {'value':'  exact existing trim behavior  '}, 'text'),
            ('url', {'value':'https://example.invalid/source'}, 'url'),
            ('bytes', {'data_base64':base64.b64encode(b'byte snapshot').decode(),'filename':'source.dat'}, 'file'),
        ]:
            with self.subTest(material_type=material_type):
                ref,_=ProjectCommandService(self.kernel).add_material('import-'+kind,self.kernel.load().revision,
                    material_type=material_type,**fields)
                payload=self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
                self.assertEqual(payload['sources'][-1]['kind'],kind)

    def test_object_and_table_overlap_requires_same_object_and_is_symmetric(self):
        objects = [{'kind': 'object', 'page': 1, 'object_id': str(n)} for n in (33, 36, 39)]
        tables = [{'kind': 'table-range', 'page': 1, 'object_id': str(n), 'row_start': 0,
                   'row_end': 2, 'col_start': 0, 'col_end': 2} for n in (33, 36, 39)]
        for values in (objects, tables):
            for a in values:
                for b in values:
                    self.assertEqual(overlaps(a, b), a['object_id'] == b['object_id'])
                    self.assertEqual(overlaps(a, b), overlaps(b, a))


class ImageContentExclusionTests(unittest.TestCase):
    def setUp(self):
        from tests.test_image_led_ooxml import package_parts, archive, slide, shape, relationships, image_bytes
        from tests.test_image_led_materials import png
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.kernel = ProjectKernel.initialize(self.root, project_id='image-content-test')
        self.banned = image_bytes()
        self.good = png(Image.new('RGB', (3, 2), 'blue'))
        parts = package_parts()
        picture = lambda n, rel: f'<p:pic><p:nvPicPr><p:cNvPr id="{n}" name="pic-{n}"/></p:nvPicPr><p:blipFill><a:blip r:embed="{rel}"/></p:blipFill></p:pic>'
        parts['ppt/slides/slide9.xml'] = slide(shape('2',' exact page text ') + ''.join(picture(n, 'bad' if n in (39, 40) else 'good') for n in (33,36,39,40)))
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([('bad','image','../media/banned.png',''),('good','image','../media/good.png','')])
        parts['ppt/media/banned.png'] = self.banned; parts['ppt/media/good.png'] = self.good
        other = copy.deepcopy(parts); other['ppt/slides/slide1.xml'] = slide(shape('2','different PPTX source'))
        self.raw_sources = {'deck':archive(parts), 'other-deck':archive(other), 'separate-image':self.banned}
        self.sources=[]
        for name, raw in self.raw_sources.items():
            (self.root / name).write_bytes(raw)
            self.sources.append({'source_id':name,'origin':'user-provided','kind':'file','locator':'project://'+name,'sha256':digest(raw)})
        self.inventory=MissionMaterialService(self.kernel).register_materials('inventory',0,{'sources':self.sources})
        self.refs={}
        for key, source_id, selector, content_kind, mode in [
            *[(str(n),'deck',{'kind':'object','page':1,'object_id':str(n)},'image','image-content' if n==39 else 'scope') for n in (33,36,39,40)],
            ('other','other-deck',{'kind':'object','page':1,'object_id':'33'},'image','scope'),
            ('other-alias','other-deck',{'kind':'object','page':1,'object_id':'40'},'image','scope'),
            ('separate','separate-image',{'kind':'whole-source'},'image','scope'),
            ('page','deck',{'kind':'page','page':1},'text','scope')]:
            req={'operation':'add-material','project_root':str(self.root),'expected_revision':self.kernel.load().revision,
                'material_type':'finding','material_inventory_ref':self.inventory,'source_id':source_id,
                'source_sha256':digest(self.raw_sources[source_id]),'source_location':selector,'content_kind':content_kind,'exclusion_mode':mode}
            ref=dispatch_v16(req)['result']['artifact_ref']
            self.refs[key]=(ref,req)

    def publish(self, key, excluded=True):
        from tests.test_v22_content_contracts import blueprint
        ref, req=self.refs[key]
        evidence=evidence_book(); evidence['material_inventory_ref']=self.inventory; evidence['source_refs']=[ref]
        evidence['excluded_material_refs']=[self.refs['39'][0]] if excluded else []
        for bucket in ('facts','user_confirmed_facts','inferences','conflicts','unknowns','evidence_gaps','forbidden_extrapolations'):
            for row in evidence[bucket]: row['source_refs']=[ref]
        evidence_ref=str(self.kernel.artifacts.reference_for('presales-evidence-book',evidence))
        deck=blueprint(); deck['project_id']=self.kernel.project_id; deck['evidence_book_ref']=evidence_ref
        page=deck['slides'][0]; page['evidence_bindings'][0]['source_refs']=[ref]; page['material_views']=[]
        page['customer_decision_item']['evidence_refs']=[ref]
        self.kernel.commit(command_id=f'publish-{self.kernel.load().revision}',expected_revision=self.kernel.load().revision,
            event_type='test.evidence',artifact_updates={'content/evidence-book':('presales-evidence-book',evidence),'content/reading-blueprint':('reading-deck-blueprint',deck)})
        payload=self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        atom={'atom_id':'renamed-atom','origin_kind':'evidence','origin_id':'fact-1','source_ref':ref,
            'source_id':req['source_id'],'source_sha256':req['source_sha256'],'source_location':req['source_location'],
            'atom_type':req['content_kind'],'use':'style-reference','content_sha256':payload['content_sha256']}
        return atom,evidence_ref,page

    def resolve(self, key, excluded=True):
        from ai_ppt_studio.application.image_led_materials import ImageLedMaterialResolver
        atom,evidence_ref,page=self.publish(key,excluded)
        before=snapshot(self.root)
        try:
            return ImageLedMaterialResolver(self.kernel).resolve_atom(atom,inventory_ref=self.inventory,evidence_ref=evidence_ref,slide=page)
        finally:
            self.assertEqual(snapshot(self.root),before)

    def test_excluded_image_bytes_cannot_reenter_as_object_pptx_or_file_alias(self):
        for key in ('40','other-alias','separate'):
            with self.subTest(key=key),self.assertRaisesRegex(ContractValidationError,'EXCLUDED'):
                self.resolve(key)
        for key in ('33','36','other'):
            self.assertEqual(self.resolve(key)['content_sha256'],digest(self.good))
        self.assertEqual(self.resolve('separate',excluded=False)['content_sha256'],digest(self.banned))

    def test_local_exclusion_allows_page_declaration_but_rejects_page_atom(self):
        from ai_ppt_studio.application.material_finding_service import MaterialFindingService
        atom,evidence_ref,page=self.publish('page')
        payload=self.kernel.artifacts.resolve(ArtifactReference.parse(evidence_ref))['payload']
        self.assertTrue(MaterialFindingService(self.kernel).validate_evidence(payload))
        with self.assertRaisesRegex(ContractValidationError,'EXCLUDED'):
            self.resolve('page')

    def test_scope_only_does_not_upgrade_same_bytes_to_content_exclusion(self):
        reference,request=self.refs['39']
        request={**request,'exclusion_mode':'scope','expected_revision':self.kernel.load().revision}
        reference=dispatch_v16(request)['result']['artifact_ref']
        self.refs['39']=(reference,request)
        for key in ('40','other-alias','separate'):
            self.assertEqual(self.resolve(key)['content_sha256'],digest(self.banned))
        with self.assertRaisesRegex(ContractValidationError,'EXCLUDED'):
            self.resolve('39')

    def test_caller_hash_does_not_bypass_actual_image_content_exclusion(self):
        from ai_ppt_studio.application.image_led_materials import ImageLedMaterialResolver
        atom,evidence_ref,page=self.publish('separate')
        atom['content_sha256']=digest(self.good)
        before=snapshot(self.root)
        with self.assertRaisesRegex(ContractValidationError,'EXCLUDED'):
            ImageLedMaterialResolver(self.kernel).resolve_atom(atom,inventory_ref=self.inventory,evidence_ref=evidence_ref,slide=page)
        self.assertEqual(before,snapshot(self.root))

    def test_evidence_validation_reads_one_snapshot_per_source_and_rechecks_next_call(self):
        from ai_ppt_studio.application.material_finding_service import MaterialFindingService
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        from unittest.mock import patch
        _,evidence_ref,_=self.publish('33')
        evidence=self.kernel.artifacts.resolve(ArtifactReference.parse(evidence_ref))['payload']
        evidence['source_refs']=[ref for key,(ref,_) in self.refs.items() if key!='39']
        service=MaterialFindingService(self.kernel)
        original=MaterialSourceReader._read
        with patch.object(MaterialSourceReader,'_read',side_effect=original) as read:
            verified=service.validate_evidence(evidence)
            self.assertEqual(read.call_count,3)
            self.assertEqual(len({id(value['source_bytes']) for value in verified.values()}),3)
            (self.root/'deck').write_bytes(b'changed between calls')
            with self.assertRaisesRegex(ContractValidationError,'SOURCE_HASH'):
                service.validate_evidence(evidence)
            self.assertGreater(read.call_count,3)

    def test_p1_image_aliases_fail_compile_register_and_generation_before_writes_or_adapter(self):
        """Formal synthetic G0; only generation's legacy/corrupt pack is injected.

        Production registration rejects the prohibited pack, so reaching the
        generation recheck requires an explicit old/corrupt current-pack fixture.
        It does not claim that this fixture passed production pack registration.
        All sources, finding registrations, exclusion hashes and resolution are real.
        """
        from unittest.mock import patch
        from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
        from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
        from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
        from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
        from ai_ppt_studio.application.image_led_service import ImageLedService
        from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
        from ai_ppt_studio.application.review_session_service import ReviewSessionService
        from tests.host_confirmation_fixtures import gate_confirmation_kwargs
        from tests.material_finding_fixtures import replace_refs
        from tests.test_image2_input_boundary import scope_payload, confirm_scope
        from tests.test_v22_content_contracts import blueprint, decision_context, fit_map
        from tests.v22_hard_gate_fixtures import semantic_checks

        kernel = self.kernel
        mission = MissionMaterialService(kernel)
        draft = mission.save_mission_draft('p1-mission', kernel.load().revision, {
            'topic': '合成图片排除验证', 'primary_audience': '测试客户',
            'desired_judgment_or_action': '核验合成材料范围'})
        confirmation = mission.confirm_mission('p1-confirm-mission', kernel.load().revision,
            mission_draft_ref=draft, material_mode='materials-provided',
            material_inventory_ref=self.inventory,
            user_action_ref='test-user-action://p1-alias-mission', user_message_ref='')
        ReleaseTargetPolicyService(kernel).bind_current_policy('p1-release-policy', kernel.load().revision)
        content = PresalesContentService(kernel)
        declared = [ref for key, (ref, _) in self.refs.items() if key != '39']
        evidence = replace_refs(evidence_book(), self.refs['33'][0], 'unused')
        evidence.update(material_inventory_ref=self.inventory, mission_confirmation_ref=confirmation,
            source_refs=declared, excluded_material_refs=[self.refs['39'][0]])
        evidence['facts'][0]['source_refs'] = declared
        evidence_ref = content.build_evidence_book('p1-evidence', kernel.load().revision, evidence)
        context = decision_context()
        context['evidence_book_ref'] = evidence_ref
        context_ref = content.build_decision_context('p1-context', kernel.load().revision, context)
        fit = replace_refs(fit_map(), self.refs['33'][0], 'unused')
        fit.update(evidence_book_ref=evidence_ref, decision_context_ref=context_ref)
        fit_ref = content.build_problem_solution_fit('p1-fit', kernel.load().revision, fit)
        deck = replace_refs(blueprint(), self.refs['33'][0], 'unused')
        deck.update(project_id=kernel.project_id, evidence_book_ref=evidence_ref,
            decision_context_ref=context_ref, problem_solution_fit_ref=fit_ref)
        page = deck['slides'][0]
        page['evidence_bindings'][0]['source_refs'] = declared
        page['customer_decision_item']['evidence_refs'] = declared
        page['material_views'] = []
        deck_ref = content.build_reading_deck_blueprint('p1-blueprint', kernel.load().revision, deck)
        deck_revision = kernel.load().revision
        gates = ContentHardGateService(kernel)
        for gate_type, runner in [('evidence', gates.run_evidence_gate), ('presales-reading', gates.run_presales_reading_gate)]:
            runner(command_id='p1-gate-' + gate_type, expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(gate_type, deck_ref), reviewer_mode='isolated-review-task')
        _, session, _ = ReviewSessionService(kernel).open_or_resume(command_id='p1-open-review',
            expected_revision=kernel.load().revision, review_type='content-full-deck', target_artifact_ref=deck_ref,
            source_version=deck['source_version'], source_revision=deck_revision, open_policy='foreground-if-waiting')
        ContentDecisionService(kernel).save(command_id='p1-approve-page', expected_revision=kernel.load().revision,
            review_session_id=session['review_session_id'], source_version=deck['source_version'],
            slide_id=page['slide_id'], decision='approved', comment='')
        ContentReviewBatchService(kernel).submit(command_id='p1-review-batch', expected_revision=kernel.load().revision,
            review_session_id=session['review_session_id'], source_version=deck['source_version'])
        content.open_g0_review(command_id='p1-open-g0', expected_revision=kernel.load().revision)
        content.confirm_g0(command_id='p1-synthetic-trusted-g0', expected_revision=kernel.load().revision,
            **gate_confirmation_kwargs(content.gate_confirmation_context()))
        self.assertEqual(kernel.load().gate_status['G0'], 'passed')

        service = ImageLedService(kernel)
        strings = {page['neutral_title'], page['page_task'], *[row['text'] for row in page['visible_copy_blocks']]}
        allowed = [{'source_sha256': digest(value.encode()), 'source_location': {'kind': 'whole-source'},
                    'uses': ['content-source'], 'send_form': 'verbatim'} for value in sorted(strings)]
        allowed.extend({'source_sha256': source['sha256'], 'source_location': {'kind': 'whole-source'},
                        'uses': ['content-source', 'real-material', 'style-reference'], 'send_form': 'verbatim'}
                       for source in self.sources)
        scope = scope_payload(kernel, allowed)
        self.assertEqual(scope['excluded'], [])  # Refusal must come from EvidenceBook's P1 content exclusion.
        scope_ref = service.commit_artifact('p1-scope', kernel.load().revision, scope)
        grant = confirm_scope(kernel, scope_ref, identity='p1-synthetic-material-grant')
        heads = kernel.load().artifact_heads
        policy = {'artifact_type': 'image-led-input-policy', 'project_id': kernel.project_id,
            'reading_blueprint_ref': deck_ref, 'source_version': deck['source_version'],
            'material_inventory_ref': self.inventory, 'evidence_book_ref': evidence_ref,
            'g0_ref': heads['gate/G0/confirmation'], 'release_target_policy_ref': heads['release/target-policy'],
            'authorization_scope_ref': scope_ref, 'authorization_ref': grant,
            'receiver': scope['receiver'], 'model': scope['model'],
            'common_rules': {'typography_tokens': {'title': 'Arial', 'body': 'Arial'},
                'color_tokens': {'ink': '#123456'}, 'fallback_fonts': {'macOS': 'Arial'},
                'title_bar': '统一标题栏', 'background': '统一浅色背景'}}
        policy_ref = service.commit_artifact('p1-policy', kernel.load().revision, policy)

        def pack_for(key):
            reference, _ = self.refs[key]
            finding = kernel.artifacts.resolve(ArtifactReference.parse(reference))['payload']
            atom = {'atom_id': 'renamed-' + key, 'origin_kind': 'evidence', 'origin_id': 'fact-1',
                'source_ref': reference, 'source_id': finding['source_id'], 'source_sha256': finding['source_sha256'],
                'source_location': finding['source_location'], 'atom_type': 'image', 'use': 'style-reference',
                'content_sha256': finding['content_sha256']}
            return {'artifact_type': 'image-led-input-pack', 'project_id': kernel.project_id,
                'input_policy_ref': policy_ref, 'slide_id': page['slide_id'], 'page_order': page['order'],
                'confirmed_visible_copy': {'title': page['neutral_title'], 'blocks': page['visible_copy_blocks']},
                'page_goal': page['page_task'], 'atoms': [atom]}

        # Real, permitted image packets establish that the G0/policy/authorization
        # path is operational; the three failures below are specifically P1.
        for key in ('33', '36'):
            good_ref = service.register_pack('p1-good-' + key, kernel.load().revision, pack_for(key))
            self.assertEqual(service.compile_request(good_ref)['materials'][0]['content_sha256'], digest(self.good))
        with patch.object(Image2CommandAdapter, 'from_environment',
                          side_effect=AssertionError('Prohibited image must not load any adapter')) as adapter:
            for key in ('40', 'other-alias', 'separate'):
                prohibited = pack_for(key)
                for boundary in ('compile_request_payload', 'register_pack'):
                    with self.subTest(alias=key, boundary=boundary):
                        before = snapshot(self.root)
                        with self.assertRaisesRegex(ContractValidationError, 'IMAGE_LED_EXCLUDED'):
                            if boundary == 'compile_request_payload':
                                service.compile_request_payload(prohibited)
                            else:
                                service.register_pack('p1-rejected-' + key, kernel.load().revision, prohibited)
                        self.assertEqual(snapshot(self.root), before)
                        self.assertEqual(adapter.call_count, 0)
                # Deliberately forged old/corrupt current pack, only to make the
                # independent generation-consumer revalidation path reachable.
                state = kernel.commit(command_id='p1-corrupt-old-pack-' + key,
                    expected_revision=kernel.load().revision, event_type='test.explicit-corrupt-old-image-pack',
                    artifact_updates={'visual/image-led/pack/' + page['slide_id']: ('image-led-input-pack', prohibited)})
                bad_ref = state.artifact_heads['visual/image-led/pack/' + page['slide_id']]
                with self.subTest(alias=key, boundary='generate-slide-images'):
                    before = snapshot(self.root)
                    with self.assertRaisesRegex(ContractValidationError, 'IMAGE_LED_EXCLUDED'):
                        dispatch_v16({'operation': 'request-agent-action', 'project_root': str(self.root),
                            'expected_revision': state.revision, 'action_type': 'generate-slide-images',
                            'target_refs': [bad_ref], 'instructions': 'Synthetic prohibited-image recheck only'})
                    self.assertEqual(snapshot(self.root), before)
                    self.assertEqual(adapter.call_count, 0)
                    self.assertEqual(kernel.load().gate_status['G0'], 'passed')

    def test_changed_exclusion_source_fails_closed_even_for_different_source_candidate(self):
        atom,evidence_ref,page=self.publish('other')
        (self.root/'deck').write_bytes(b'tampered exclusion source')
        from ai_ppt_studio.application.image_led_materials import ImageLedMaterialResolver
        before=snapshot(self.root)
        with self.assertRaisesRegex(ContractValidationError,'SOURCE_HASH'):
            ImageLedMaterialResolver(self.kernel).resolve_atom(atom,inventory_ref=self.inventory,evidence_ref=evidence_ref,slide=page)
        self.assertEqual(before,snapshot(self.root))

class FindingProductionBoundaryTests(unittest.TestCase):
    def test_every_new_content_entry_revalidates_actual_source_bytes(self):
        from tests.test_v22_content_domain_service import ContentChainFixture
        from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
        from tests.v22_hard_gate_fixtures import semantic_checks
        for entry in ('evidence','context','fit','blueprint','evidence-gate','reading-gate'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as folder:
                fixture=ContentChainFixture(folder)
                fit,fit_ref=fixture.build_fit()
                deck=fixture.valid_blueprint(fit_ref)
                deck_ref=fixture.service.build_reading_deck_blueprint('deck',fixture.kernel.load().revision,deck)
                gates=ContentHardGateService(fixture.kernel)
                if entry=='reading-gate':
                    gates.run_evidence_gate(command_id='first-gate',expected_revision=fixture.kernel.load().revision,
                        semantic_check_results=semantic_checks('evidence',deck_ref),reviewer_mode='isolated-review-task')
                (Path(folder)/'fixture-source.txt').write_bytes(b'changed source after content chain')
                before=snapshot(Path(folder))
                revision=fixture.kernel.load().revision
                with self.assertRaisesRegex(ContractValidationError,'SOURCE_HASH'):
                    if entry=='evidence': fixture.service.build_evidence_book('changed',revision,fixture.evidence_payload)
                    elif entry=='context': fixture.service.build_decision_context('changed',revision,fixture.context_payload)
                    elif entry=='fit': fixture.service.build_problem_solution_fit('changed',revision,fit)
                    elif entry=='blueprint': fixture.service.build_reading_deck_blueprint('changed',revision,deck)
                    else:
                        gate_type='evidence' if entry=='evidence-gate' else 'presales-reading'
                        runner=gates.run_evidence_gate if entry=='evidence-gate' else gates.run_presales_reading_gate
                        runner(command_id='changed',expected_revision=revision,
                            semantic_check_results=semantic_checks(gate_type,deck_ref),reviewer_mode='isolated-review-task')
                self.assertEqual(before,snapshot(Path(folder)))

    def test_g0_pack_with_no_atoms_revalidates_material_evidence_before_write_and_adapter(self):
        from tests.test_image_led_requests import input_fixture
        from ai_ppt_studio.application.image_led_service import ImageLedService
        from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service,policy,packs=input_fixture(root,slide_count=1)
            payload=service.kernel.artifacts.resolve(ArtifactReference.parse(packs[0]))['payload']
            (root/'fixture-source.txt').write_bytes(b'changed after G0')
            before=snapshot(root)
            with patch.object(Image2CommandAdapter,'from_environment') as adapter:
                for action in ('compile','pack','generate'):
                    with self.subTest(action=action),self.assertRaisesRegex(ContractValidationError,'SOURCE_HASH'):
                        if action=='compile':service.compile_request(packs[0])
                        elif action=='pack':service.commit_artifact('new-pack',service.kernel.load().revision,payload)
                        else: dispatch_v16({'operation':'request-agent-action','project_root':str(root),
                            'expected_revision':service.kernel.load().revision,'action_type':'generate-slide-images','target_refs':[packs[0]],'instructions':'do not send'})
                self.assertEqual(adapter.call_count,0)
            self.assertEqual(before,snapshot(root))

    def test_material_atom_batch_shares_verified_snapshots_without_cross_call_cache(self):
        from tests.test_image_led_requests import input_fixture
        from tests.test_image2_input_boundary import confirm_scope
        from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            service,policy,packs=input_fixture(Path(folder),slide_count=1)
            kernel=service.kernel
            evidence=kernel.artifacts.resolve(ArtifactReference.parse(policy['evidence_book_ref']))['payload']
            finding_ref=evidence['source_refs'][0]
            finding=kernel.artifacts.resolve(ArtifactReference.parse(finding_ref))['payload']
            scope=kernel.artifacts.resolve(ArtifactReference.parse(policy['authorization_scope_ref']))['payload']
            scope['allowed'].append({'source_sha256':finding['source_sha256'],'source_location':finding['source_location'],
                'uses':['content-source'],'send_form':'verbatim'})
            scope_ref=service.commit_artifact('scope-with-material',kernel.load().revision,scope)
            grant=confirm_scope(kernel,scope_ref,identity='material-batch')
            policy.update(authorization_scope_ref=scope_ref,authorization_ref=grant)
            policy_ref=service.commit_artifact('policy-with-material',kernel.load().revision,policy)
            pack=kernel.artifacts.resolve(ArtifactReference.parse(packs[0]))['payload']
            pack['input_policy_ref']=policy_ref
            pack['atoms']=[{'atom_id':f'atom-{n}','origin_kind':'evidence','origin_id':'fact-1','source_ref':finding_ref,
                'source_id':finding['source_id'],'source_sha256':finding['source_sha256'],'source_location':finding['source_location'],
                'atom_type':'text','use':'content-source','content_sha256':finding['content_sha256']} for n in range(20)]
            pack_ref=service.commit_artifact('material-batch',kernel.load().revision,pack)
            original=MaterialSourceReader._read
            with patch.object(MaterialSourceReader,'_read',side_effect=original) as read:
                self.assertEqual(len(service.compile_request(pack_ref)['materials']),20)
                self.assertLessEqual(read.call_count,2)
                (Path(folder)/'fixture-source.txt').write_bytes(b'changed between calls')
                with self.assertRaisesRegex(ContractValidationError,'SOURCE_HASH'):
                    service.compile_request(pack_ref)


if __name__ == '__main__':
    unittest.main()
