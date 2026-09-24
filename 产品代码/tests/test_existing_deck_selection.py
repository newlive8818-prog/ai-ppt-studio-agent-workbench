"""The optimized deck must choose exact produced images, not promote files or old pages."""
from copy import deepcopy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ai_ppt_studio.application.existing_deck_optimization import ExistingDeckOptimizationService
from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.application.project_service import ProjectCommandService
from tests.test_existing_deck_optimization import fixture

RULES = {'typography_tokens': {'title': 'Inter 32'}, 'color_tokens': {'accent': '#245AFF'},
         'fallback_fonts': {'zh': 'PingFang SC'}, 'title_bar': 'consistent title bar',
         'background': 'neutral light'}


def image(color):
    b = io.BytesIO()
    Image.new('RGB', (2048, 1152), color).save(b, 'PNG')
    return b.getvalue()


class FakeTransport:
    def __init__(self, raw):
        self.raw, self.calls = raw, []

    def generate(self, *, request_id, payload):
        self.calls.append((request_id, payload))
        return {'response_id': 'provider-response', 'image_bytes': self.raw}


class ExistingDeckSelectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.kernel, raw, source = fixture(Path(self.folder.name))
        self.source_ref = ExistingDeckOptimizationService(self.kernel).begin(
            'begin', self.kernel.load().revision, source_id=source['source_id'],
            source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
            user_message_ref='chat://message/optimize-this-file')
        ExistingDeckOptimizationService(self.kernel).set_external_scope(
            'external-use', self.kernel.load().revision,
            user_message_ref='chat://message/source-material-may-be-external',
            allowed_page_orders=[1, 2], excluded_image_sha256=[],
            excluded_text_item_ids=[])
        self.service = ExistingDeckSelectionService(self.kernel)


    def historical_provenance(self, *, page_order=1, model='gpt-image-2'):
        return {
            'source_pptx_sha256': self._source()['source_pptx_sha256'],
            'page_order': page_order,
            'historical_request_id': f'historical-source-p{page_order:02d}',
            'historical_request_sha256': hashlib.sha256(
                f'request-{page_order}'.encode()).hexdigest(),
            'historical_response_sha256': hashlib.sha256(
                f'response-{page_order}'.encode()).hexdigest(),
            'historical_receiver': 'CRS',
            'historical_model': model,
            'historical_quality': 'medium',
        }

    def import_historical(self, *, slide_id='S0001', request_id='historical-import-1',
                          color='purple', page_order=1, provenance=None):
        import base64
        raw = image(color)
        page = self.service.source_page(slide_id)
        return self.service.register_historical_design(
            'import-' + request_id, self.kernel.load().revision,
            slide_id=slide_id, request_id=request_id, common_rules=RULES,
            title_item_id=page['visible_copy'][0]['item_id'],
            image_base64=base64.b64encode(raw).decode('ascii'),
            image_sha256=hashlib.sha256(raw).hexdigest(),
            provenance=provenance or self.historical_provenance(page_order=page_order))

    def test_exact_historical_design_registers_completed_candidate_without_transport(self):
        request_ref, response_ref = self.import_historical()
        request = self.kernel.artifacts.resolve(ArtifactReference.parse(request_ref))['payload']
        response = self.kernel.artifacts.resolve(ArtifactReference.parse(response_ref))['payload']
        self.assertEqual(request['request_origin'], 'historical-design-import/v1')
        self.assertEqual(request['provenance']['historical_model'], 'gpt-image-2')
        self.assertEqual(request['provenance']['source_pptx_sha256'],
                         self._source()['source_pptx_sha256'])
        self.assertEqual(response['status'], 'completed')
        self.assertEqual(response['request_origin'], 'historical-design-import/v1')
        self.assertEqual(response['image_sha256'], hashlib.sha256(image('purple')).hexdigest())
        self.assertEqual(self.service._response('historical-import-1')[3], response)
        with self.assertRaises(ContractValidationError):
            self.service.execute_request('historical-import-1',
                                         transport=FakeTransport(image('black')))

    def _source(self):
        return ExistingDeckOptimizationService(self.kernel).current_source()

    def test_historical_import_fails_closed_on_identity_hash_or_model_mismatch(self):
        import base64
        raw = image('purple')
        valid = self.historical_provenance()
        cases = {
            'source': {**valid, 'source_pptx_sha256': '0' * 64},
            'page': {**valid, 'page_order': 2},
            'request-hash': {**valid, 'historical_request_sha256': 'bad'},
            'response-hash': {**valid, 'historical_response_sha256': 'bad'},
            'receiver': {**valid, 'historical_receiver': 'other'},
            'model': {**valid, 'historical_model': 'latest'},
        }
        for label, provenance in cases.items():
            with self.subTest(label=label):
                before = self.kernel.load()
                with self.assertRaises(ContractValidationError):
                    self.service.register_historical_design(
                        'invalid-' + label, before.revision, slide_id='S0001',
                        request_id='invalid-' + label, common_rules=RULES,
                        title_item_id=self.service.source_page('S0001')['visible_copy'][0]['item_id'],
                        image_base64=base64.b64encode(raw).decode('ascii'),
                        image_sha256=(hashlib.sha256(raw).hexdigest()
                                      if label != 'image-hash' else '0' * 64),
                        provenance=provenance)
                after = self.kernel.load()
                self.assertEqual(after.revision, before.revision)
                self.assertEqual(after.artifact_heads, before.artifact_heads)
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.register_historical_design(
                'invalid-image-hash', before.revision, slide_id='S0001',
                request_id='invalid-image-hash', common_rules=RULES,
                title_item_id=self.service.source_page('S0001')['visible_copy'][0]['item_id'],
                image_base64=base64.b64encode(raw).decode('ascii'), image_sha256='0' * 64,
                provenance=valid)
        self.assertEqual(self.kernel.load().revision, before.revision)

    def test_historical_import_can_coexist_with_same_page_unknown_generation(self):
        active_ref = self.request(request_id='same-page-unknown')
        claim = {'project_id': self.kernel.project_id, 'request_id': 'same-page-unknown',
                 'request_ref': active_ref, 'status': 'unknown'}
        self.kernel.commit(command_id='preserve-unknown', expected_revision=self.kernel.load().revision,
            event_type='optimization.image-response-preserved',
            artifact_updates={self.service.RESPONSE + 'same-page-unknown':
                ('optimization-image-response', claim)})
        imported = self.import_historical(request_id='historical-alternative')
        state = self.kernel.load()
        self.assertEqual(state.artifact_heads[self.service.REQUEST + 'same-page-unknown'], active_ref)
        self.assertEqual(self.kernel.artifacts.resolve(ArtifactReference.parse(
            state.artifact_heads[self.service.RESPONSE + 'same-page-unknown']))['payload']['status'],
            'unknown')
        self.assertEqual(state.artifact_heads[self.service.REQUEST + 'historical-alternative'],
                         imported[0])
        self.assertEqual(state.artifact_heads[self.service.RESPONSE + 'historical-alternative'],
                         imported[1])

    def test_historical_design_can_be_reviewed_and_selected(self):
        choices = []
        source_ref = self.kernel.load().artifact_heads['optimization/source']
        for n, color in ((1, 'purple'), (2, 'orange')):
            slide_id = f'S{n:04d}'
            request_id = f'historical-{n}'
            request_ref, response_ref = self.import_historical(
                slide_id=slide_id, request_id=request_id, color=color, page_order=n)
            _, task, _ = ProjectCommandService(self.kernel).request_agent_action(
                'review-' + request_id, self.kernel.load().revision,
                action_type='review-visual-engineering', target_refs=[response_ref],
                instructions='Review exact historical design bytes and source copy')
            review_ref = self.service.review_response(
                'record-' + request_id, self.kernel.load().revision, request_id=request_id,
                reviewer_task_id=task['task_id'], producer_task_id=request_id,
                checks={key: 'passed' for key in (
                    'visible-copy-transcription', 'no-unsupported-facts',
                    'material-roles', 'excluded-content')})
            choices.append({'slide_id': slide_id, 'request_id': request_id,
                            'review_ref': review_ref})
        _, selector, _ = ProjectCommandService(self.kernel).request_agent_action(
            'select-historical', self.kernel.load().revision,
            action_type='review-visual-aesthetic', target_refs=[source_ref],
            instructions='Choose reviewed historical designs')
        selection_ref = self.service.select_internal(
            'record-historical-selection', self.kernel.load().revision, selections=choices,
            reviewer_task_id=selector['task_id'])
        ProjectCommandService(self.kernel).complete_agent_task(
            'complete-selector', self.kernel.load().revision,
            task_id=selector['task_id'], result_ref=selection_ref)
        selected = self.service.current_selection(selection_ref)
        self.assertEqual([row['target_binding']['target_image_sha256'] for row in selected['slides']],
                         [hashlib.sha256(image('purple')).hexdigest(),
                          hashlib.sha256(image('orange')).hexdigest()])

    def request(self, slide_id='S0001', request_id='generation-1'):
        return self.service.register_request('request-'+request_id, self.kernel.load().revision,
            slide_id=slide_id, request_id=request_id, common_rules=RULES,
            title_item_id=self.service.source_page(slide_id)['visible_copy'][0]['item_id'] if slide_id in ('S0001','S0002') else 'source-object-2')

    def produce(self, slide_id='S0001', request_id='generation-1', color='red'):
        request_ref = self.request(slide_id, request_id)
        transport = FakeTransport(image(color))
        response_ref = self.service.execute_request(request_id, transport=transport)
        return request_ref, response_ref, transport

    def test_request_is_bound_to_exact_source_page_and_provider_response(self):
        request_ref, response_ref, transport = self.produce()
        request = self.kernel.artifacts.resolve(ArtifactReference.parse(request_ref))['payload']
        response = self.kernel.artifacts.resolve(ArtifactReference.parse(response_ref))['payload']
        self.assertEqual(request['source_ref'], self.source_ref)
        self.assertEqual(request['visible_copy'], self.service.source_page('S0001')['visible_copy'])
        self.assertEqual(response['request_ref'], request_ref)
        self.assertEqual(response['image_sha256'], hashlib.sha256(image('red')).hexdigest())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(self.service.execute_request('generation-1', transport=transport), response_ref)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(self.kernel.load().gate_status['G0'], 'open')

    def test_recover_started_request_is_read_only_and_never_needs_a_transport(self):
        request_ref = self.request(request_id='started-recovery')
        claim = {'project_id': self.kernel.project_id, 'request_id': 'started-recovery',
                 'request_ref': request_ref, 'status': 'started'}
        self.kernel.commit(command_id='started-claim', expected_revision=self.kernel.load().revision,
            event_type='optimization.image-request-started',
            artifact_updates={self.service.RESPONSE + 'started-recovery':
                ('optimization-image-response', claim)})
        before = self.kernel.load()
        response_ref, response = self.service.recover_request('started-recovery')
        self.assertEqual(response_ref, before.artifact_heads[self.service.RESPONSE + 'started-recovery'])
        self.assertEqual(response, claim)
        after = self.kernel.load()
        self.assertEqual(after.revision, before.revision)
        self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_recover_unknown_or_completed_request_returns_exact_persisted_record_read_only(self):
        request_ref = self.request(request_id='unknown-recovery')
        unknown = {'project_id': self.kernel.project_id, 'request_id': 'unknown-recovery',
                   'request_ref': request_ref, 'status': 'unknown',
                   'failure_reason': 'provider-or-image-validation-failed'}
        self.kernel.commit(command_id='unknown-claim', expected_revision=self.kernel.load().revision,
            event_type='optimization.image-response-preserved',
            artifact_updates={self.service.RESPONSE + 'unknown-recovery':
                ('optimization-image-response', unknown)})
        before_unknown = self.kernel.load()
        _, recovered_unknown = self.service.recover_request('unknown-recovery')
        self.assertEqual(recovered_unknown, unknown)
        self.assertEqual(self.kernel.load().revision, before_unknown.revision)

        _, completed_ref, _ = self.produce('S0002', 'completed-recovery', 'blue')
        before_completed = self.kernel.load()
        recovered_ref, completed = self.service.recover_request('completed-recovery')
        self.assertEqual(recovered_ref, completed_ref)
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['image_sha256'], hashlib.sha256(image('blue')).hexdigest())
        self.assertEqual(self.kernel.load().revision, before_completed.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before_completed.artifact_heads)

    def test_recover_request_without_persisted_response_fails_without_write(self):
        self.request(request_id='never-sent-recovery')
        before = self.kernel.load()
        with self.assertRaisesRegex(ContractValidationError, 'persisted response'):
            self.service.recover_request('never-sent-recovery')
        self.assertEqual(self.kernel.load().revision, before.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_new_request_uses_exact_sunburst_model_from_current_scope(self):
        request_ref = self.request(request_id='sunburst-only')
        request = self.kernel.artifacts.resolve(ArtifactReference.parse(request_ref))['payload']
        self.assertEqual((request['payload']['receiver'], request['payload']['model']),
            ('CRS', 'gpt-image-2.5-sunburst'))

    def test_revision_request_binds_source_items_as_mandatory_independent_structures(self):
        page = self.service.source_page('S0001')
        title_id = page['visible_copy'][0]['item_id']
        body_id = page['visible_copy'][1]['item_id']
        request_ref = self.service.register_request(
            'required-visible-items', self.kernel.load().revision,
            slide_id='S0001', request_id='required-visible-items', common_rules=RULES,
            title_item_id=title_id, required_visible_item_ids=[body_id])
        request = self.kernel.artifacts.resolve(
            ArtifactReference.parse(request_ref))['payload']
        self.assertEqual(request['required_visible_item_ids'], [body_id])
        self.assertIn('another object', request['payload']['page_goal'])
        self.assertIn('独立可见结构', request['payload']['page_goal'])
        self.assertIn('不得仅隐含', request['payload']['page_goal'])

    def test_revision_required_items_fail_closed_for_invalid_source_identities(self):
        page = self.service.source_page('S0001')
        title_id = page['visible_copy'][0]['item_id']
        body_id = page['visible_copy'][1]['item_id']
        for suffix, identities in (
                ('title', [title_id]),
                ('unknown', ['source-object-999999']),
                ('duplicate', [body_id, body_id])):
            with self.subTest(suffix=suffix):
                before = self.kernel.load()
                with self.assertRaises(ContractValidationError):
                    self.service.register_request(
                        'invalid-required-' + suffix, before.revision,
                        slide_id='S0001', request_id='invalid-required-' + suffix,
                        common_rules=RULES, title_item_id=title_id,
                        required_visible_item_ids=identities)
                after = self.kernel.load()
                self.assertEqual(after.revision, before.revision)
                self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_relation_constraints_bind_current_source_items_without_exposing_internal_ids(self):
        page = self.service.source_page('S0001')
        title_id = page['visible_copy'][0]['item_id']
        first = page['visible_copy'][1]['item_id']
        request_ref = self.service.register_request(
            'source-relations', self.kernel.load().revision,
            slide_id='S0001', request_id='source-relations', common_rules=RULES,
            title_item_id=title_id, relationship_constraints=[{
                'kind': 'belongs-to',
                'source_item_ids': [first],
                'target_item_ids': [title_id],
            }])
        request = self.kernel.artifacts.resolve(
            ArtifactReference.parse(request_ref))['payload']
        self.assertEqual(request['relationship_constraints'], [{
            'kind': 'belongs-to',
            'source_item_ids': [first],
            'target_item_ids': [title_id],
        }])
        self.assertIn(page['visible_copy'][1]['text'], request['payload']['page_goal'])
        self.assertIn(page['visible_copy'][0]['text'], request['payload']['page_goal'])
        self.assertIn('明确归属于', request['payload']['page_goal'])
        self.assertIn('不得跨列或悬空', request['payload']['page_goal'])
        self.assertNotIn(first, request['payload']['page_goal'])
        self.assertNotIn(title_id, request['payload']['page_goal'])

    def test_dual_direction_instruction_requires_a_distinct_bidirectional_structure(self):
        page = {'visible_copy': [
            {'item_id': 'title', 'text': '页面标题'},
            {'item_id': 'internal', 'text': '对内支持业务转型发展'},
            {'item_id': 'external', 'text': '助力社会治理对外'},
        ]}
        _, instruction = self.service._relationship_constraints(
            page, 'title', [{
                'kind': 'dual-direction',
                'source_item_ids': ['internal', 'external'],
                'target_item_ids': [],
            }])
        self.assertIn('独立双向结构', instruction)
        self.assertIn('不得与其他业务项合并为同一排普通卡片', instruction)

    def test_source_media_role_bindings_compile_exact_source_text_without_exposing_ids(self):
        self.assertTrue(hasattr(self.service, '_source_media_role_bindings'))
        page = {'visible_copy': [
            {'item_id': 'title', 'text': '页面标题'},
            {'item_id': 'business', 'text': '业务中台'},
            {'item_id': 'data', 'text': '数据中台'},
        ]}
        guidance = [
            {'image_number': 1, 'object_id': '9'},
            {'image_number': 2, 'object_id': '20'},
        ]
        normalized, instruction = self.service._source_media_role_bindings(
            page, 'title', guidance, [
                {'picture_object_id': '20', 'text_item_ids': ['data']},
                {'picture_object_id': '9', 'text_item_ids': ['business']},
            ])
        self.assertEqual(normalized, [
            {'picture_object_id': '9', 'text_item_ids': ['business']},
            {'picture_object_id': '20', 'text_item_ids': ['data']},
        ])
        self.assertIn('素材图片1', instruction)
        self.assertIn('业务中台', instruction)
        self.assertIn('素材图片2', instruction)
        self.assertIn('数据中台', instruction)
        self.assertIn('不得改配、复制到其他文字结构', instruction)
        self.assertNotIn('picture_object_id', instruction)
        self.assertNotIn('text_item_ids', instruction)
        self.assertNotIn('business', instruction)

    def test_relation_constraints_fail_closed_for_unknown_title_or_invalid_ownership(self):
        page = self.service.source_page('S0001')
        title_id = page['visible_copy'][0]['item_id']
        body_id = page['visible_copy'][1]['item_id']
        cases = {
            'unknown': {'kind': 'belongs-to',
                        'source_item_ids': ['source-object-999999'],
                        'target_item_ids': [title_id]},
            'title': {'kind': 'dual-direction',
                      'source_item_ids': [title_id, body_id],
                      'target_item_ids': []},
            'missing-owner': {'kind': 'belongs-to',
                              'source_item_ids': [body_id],
                              'target_item_ids': []},
        }
        for suffix, constraint in cases.items():
            with self.subTest(suffix=suffix):
                before = self.kernel.load()
                with self.assertRaises(ContractValidationError):
                    self.service.register_request(
                        'invalid-relation-' + suffix, before.revision,
                        slide_id='S0001', request_id='invalid-relation-' + suffix,
                        common_rules=RULES, title_item_id=title_id,
                        relationship_constraints=[constraint])
                after = self.kernel.load()
                self.assertEqual(after.revision, before.revision)
                self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_historical_unsent_image2_request_is_blocked_before_started_write(self):
        request_ref = self.request(request_id='current-request')
        request = deepcopy(self.kernel.artifacts.resolve(
            ArtifactReference.parse(request_ref))['payload'])
        request['request_id'] = 'legacy-unsent'
        request['payload']['model'] = 'gpt-image-2'
        request['payload_sha256'] = hashlib.sha256(
            self.service._canonical(request['payload'])).hexdigest()
        self.kernel.commit(command_id='historical-unsent-request',
            expected_revision=self.kernel.load().revision,
            event_type='test.historical-unsent-request',
            artifact_updates={self.service.REQUEST + 'legacy-unsent':
                ('optimization-image-request', request)})
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.execute_request('legacy-unsent', transport=FakeTransport(image('red')))
        after = self.kernel.load()
        self.assertEqual(after.revision, before.revision)
        self.assertNotIn(self.service.RESPONSE + 'legacy-unsent', after.artifact_heads)

    def test_design_input_explicitly_preserves_every_embedded_source_image(self):
        """Customer logos and screenshots cannot silently become generic artwork."""
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        picture = '<p:pic><p:nvPicPr><p:cNvPr id="9" name="customer-logo"/></p:nvPicPr><p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>'
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'customer page') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([('rPicture', 'image', '../media/image1.png', '')])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='source-media-page')
            inventory_ref, _ = ProjectCommandService(kernel).add_material('import', kernel.load().revision,
                material_type='bytes', data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=source['sha256'],
                user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope('scope', kernel.load().revision,
                user_message_ref='chat://message/authorized-source', allowed_page_orders=[1],
                excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            title_id = service.source_page('S0001')['visible_copy'][0]['item_id']
            ref = service.register_request('request', kernel.load().revision,
                slide_id='S0001', request_id='media-layout-1', common_rules=RULES, title_item_id=title_id,
                layout_mode='blank-media-slots')
            payload = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']['payload']
            self.assertEqual(payload['materials'], [])
            self.assertIn('1张', payload['page_goal'])
            self.assertIn('不得用通用图标', payload['page_goal'])
            self.assertIn('逐一预留', payload['page_goal'])
            self.assertIn('空白', payload['page_goal'])
            self.assertIn('无照片', payload['page_goal'])
            self.assertNotIn(base64.b64encode(image_bytes()).decode(), str(payload))

    def test_single_main_screenshot_focus_reserves_one_slot_and_composes_only_bound_media(self):
        import base64
        from ai_ppt_studio.application.local_media_composition import compositor_version
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import (
            archive, package_parts, slide, shape, relationships, image_bytes)

        parts = package_parts()
        parts['ppt/presentation.xml'] = parts['ppt/presentation.xml'].replace(
            '</p:presentation>', '<p:sldSz cx="1200" cy="675"/></p:presentation>')
        pictures = ''.join((
            '<p:pic><p:nvPicPr><p:cNvPr id="9" name="main-screen"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rMain"/></p:blipFill><p:spPr><a:xfrm>'
            '<a:off x="100" y="100"/><a:ext cx="800" cy="450"/></a:xfrm></p:spPr></p:pic>',
            '<p:pic><p:nvPicPr><p:cNvPr id="10" name="decoration"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rDecoration"/></p:blipFill><p:spPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="1200" cy="675"/></a:xfrm></p:spPr></p:pic>',
        ))
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'customer page') + pictures)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rMain', 'image', '../media/image1.png', ''),
            ('rDecoration', 'image', '../media/image2.png', ''),
        ])
        main_screen = io.BytesIO()
        Image.new('RGB', (1280, 720), (31, 62, 93)).save(main_screen, 'PNG')
        parts['ppt/media/image1.png'] = main_screen.getvalue()
        parts['ppt/media/image2.png'] = image('gray')
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='single-main-screen')
            inventory_ref, _ = ProjectCommandService(kernel).add_material(
                'import', kernel.load().revision, material_type='bytes',
                data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(
                ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ExistingDeckOptimizationService(kernel).begin(
                'begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=source['sha256'], user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope(
                'scope', kernel.load().revision, user_message_ref='chat://message/authorized',
                allowed_page_orders=[1], excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            request_ref = service.register_request(
                'request', kernel.load().revision, slide_id='S0001', request_id='main-screen',
                common_rules=RULES, title_item_id='source-object-2',
                layout_mode='single-main-screenshot-focus',
                main_source_picture_object_id='9')
            request = kernel.artifacts.resolve(ArtifactReference.parse(request_ref))['payload']
            self.assertEqual(request['main_source_picture_object_id'], '9')
            self.assertEqual(request['payload']['materials'], [])
            self.assertIn('一个大尺寸空白主截图版位', request['payload']['page_goal'])
            self.assertIn('其他源媒体不预留图片框', request['payload']['page_goal'])
            self.assertIn('16:9', request['payload']['page_goal'])
            self.assertIn('空白版位自身宽度至少达到整页画布的50%',
                          request['payload']['page_goal'])
            self.assertIn('空白版位自身高度至少达到整页画布的50%',
                          request['payload']['page_goal'])
            self.assertIn('实际显示宽度至少达到整页画布的45%', request['payload']['page_goal'])
            self.assertIn('实际显示高度至少达到整页画布的35%', request['payload']['page_goal'])
            self.assertIn('全页主要视觉焦点', request['payload']['page_goal'])
            service.execute_request('main-screen', transport=FakeTransport(image('white')))
            before = kernel.load()
            with self.assertRaisesRegex(ContractValidationError, 'meeting-readable'):
                service.register_local_media_composition(
                    'reject-wide-shallow-slot', before.revision,
                    request_id='main-screen', placements=[{
                        'operation': 'place-main-source-screenshot',
                        'source_picture_object_ids': ['9'],
                        'bbox': [244, 510, 1560, 267],
                        'fit': 'contain', 'fill_rgb': [255, 255, 255],
                    }, {
                        'operation': 'exclude-source-media',
                        'source_picture_object_ids': ['10'],
                        'reason': 'decorative-background',
                    }])
            self.assertEqual(kernel.load().revision, before.revision)
            composition_ref = service.register_local_media_composition(
                'compose', kernel.load().revision, request_id='main-screen', placements=[{
                    'operation': 'place-main-source-screenshot',
                    'source_picture_object_ids': ['9'], 'bbox': [300, 170, 1100, 619],
                    'fit': 'contain', 'fill_rgb': [255, 255, 255],
                }, {
                    'operation': 'exclude-source-media',
                    'source_picture_object_ids': ['10'], 'reason': 'decorative-background',
                }])
            composition = kernel.artifacts.resolve(
                ArtifactReference.parse(composition_ref))['payload']
            self.assertEqual(composition['compositor_version'],
                             compositor_version('single-main-screenshot-focus'))
            self.assertEqual(composition['selected_source_picture_object_ids'], ['9'])
            self.assertEqual(composition['excluded_source_picture_object_ids'], ['10'])

    def test_source_media_guided_request_sends_exact_media_with_source_geometry(self):
        """Dropping source media or its original placement would recreate invented visuals."""
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        parts['ppt/presentation.xml'] = parts['ppt/presentation.xml'].replace(
            '</p:presentation>', '<p:sldSz cx="1200" cy="675"/></p:presentation>')
        picture = ('<p:pic><p:nvPicPr><p:cNvPr id="9" name="brand-background"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rPicture"/></p:blipFill><p:spPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="1200" cy="675"/></a:xfrm></p:spPr></p:pic>')
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'customer page') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rPicture', 'image', '../media/image1.png', '')])
        media = image_bytes()
        parts['ppt/media/image1.png'] = media
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='guided-source-media')
            inventory_ref, _ = ProjectCommandService(kernel).add_material(
                'import', kernel.load().revision, material_type='bytes',
                data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ExistingDeckOptimizationService(kernel).begin(
                'begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=source['sha256'], user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope(
                'scope', kernel.load().revision,
                user_message_ref='chat://message/source-page-and-media-authorized',
                allowed_page_orders=[1], excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            request_ref = service.register_request(
                'guided-request', kernel.load().revision, slide_id='S0001',
                request_id='guided-request', common_rules=RULES,
                title_item_id='source-object-2', layout_mode='source-media-guided')
            request = kernel.artifacts.resolve(ArtifactReference.parse(request_ref))['payload']
            self.assertEqual(len(request['payload']['materials']), 1)
            self.assertEqual(base64.b64decode(
                request['payload']['materials'][0]['data_base64'], validate=True), media)
            self.assertEqual(request['payload']['materials'][0]['use'], 'real-material')
            self.assertEqual(request['source_media_guidance'], [{
                'image_number': 1, 'object_id': '9',
                'content_sha256': hashlib.sha256(media).hexdigest(),
                'source_bbox': [0, 0, 10000, 10000],
                'source_role': 'full-bleed-background',
            }])
            self.assertIn('素材图片1', request['payload']['page_goal'])
            self.assertIn('全幅背景', request['payload']['page_goal'])
            self.assertIn('不得新增素材池之外的照片', request['payload']['page_goal'])
            transport = FakeTransport(image('white'))
            service.execute_request('guided-request', transport=transport)
            self.assertEqual(transport.calls[0][1]['materials'], request['payload']['materials'])

    def test_guided_role_correction_compositor_restores_every_exact_source_image(self):
        import base64
        from ai_ppt_studio.application.existing_deck_optimization import _source_inventory
        from ai_ppt_studio.application.local_media_composition import (
            compose_original_media, compositor_version)
        from tests.test_image_led_ooxml import (
            archive, package_parts, slide, shape, relationships, image_bytes)

        parts = package_parts()
        parts['ppt/presentation.xml'] = parts['ppt/presentation.xml'].replace(
            '</p:presentation>', '<p:sldSz cx="1200" cy="675"/></p:presentation>')
        picture = ('<p:pic><p:nvPicPr><p:cNvPr id="9" name="source-icon"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rPicture"/></p:blipFill><p:spPr><a:xfrm>'
            '<a:off x="100" y="100"/><a:ext cx="300" cy="200"/></a:xfrm></p:spPr></p:pic>')
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'page one') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rPicture', 'image', '../media/image1.png', '')])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        page = _source_inventory(raw)[0]
        try:
            version = compositor_version('source-media-guided')
        except ContractValidationError:
            self.fail('guided source-media role correction compositor is not supported')
        self.assertEqual(version, 'guided-source-media-role-correction/v1')
        corrected = compose_original_media(
            response_bytes=image('white'), source_pptx_bytes=raw, page=page,
            layout_mode='source-media-guided', placements=[{
                'operation': 'replace-source-region',
                'source_picture_object_ids': ['9'],
                'bbox': [100, 100, 160, 160],
                'fit': 'contain', 'fill_rgb': [35, 104, 235],
                'background_shape': 'circle',
            }, {
                'operation': 'mask-region', 'bbox': [500, 100, 80, 60],
                'fill_rgb': [255, 255, 255],
            }])
        with Image.open(io.BytesIO(corrected)) as rendered:
            self.assertEqual(rendered.mode, 'RGB')
            self.assertNotEqual(rendered.getpixel((180, 180)), (255, 255, 255))
            self.assertEqual(rendered.getpixel((101, 101)), (255, 255, 255))

    def test_guided_media_response_is_reviewed_and_selected_without_local_composition(self):
        """A remote source-media design must stay bound to request bytes and review evidence."""
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        parts['ppt/presentation.xml'] = parts['ppt/presentation.xml'].replace(
            '</p:presentation>', '<p:sldSz cx="1200" cy="675"/></p:presentation>')
        picture = ('<p:pic><p:nvPicPr><p:cNvPr id="9" name="brand-background"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rPicture"/></p:blipFill><p:spPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="1200" cy="675"/></a:xfrm></p:spPr></p:pic>')
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'page one') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rPicture', 'image', '../media/image1.png', '')])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='guided-selection')
            inventory_ref, _ = ProjectCommandService(kernel).add_material(
                'import', kernel.load().revision, material_type='bytes',
                data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            source_ref = ExistingDeckOptimizationService(kernel).begin(
                'begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=source['sha256'], user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope(
                'scope', kernel.load().revision, user_message_ref='chat://message/authorized',
                allowed_page_orders=[1, 2], excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            choices = []
            for slide_id, request_id, title_id, layout_mode in (
                    ('S0001', 'guided-one', 'source-object-2', 'source-media-guided'),
                    ('S0002', 'plain-two', 'source-object-2', 'standard')):
                request_ref = service.register_request(
                    'register-' + request_id, kernel.load().revision, slide_id=slide_id,
                    request_id=request_id, common_rules=RULES,
                    title_item_id=title_id, layout_mode=layout_mode)
                response_ref = service.execute_request(request_id, transport=FakeTransport(image('white')))
                targets = ([request_ref, response_ref]
                    if layout_mode == 'source-media-guided' else [response_ref])
                checks = {key: 'passed' for key in (
                    ('visible-copy-transcription', 'no-unsupported-facts', 'material-roles',
                     'excluded-content', 'source-media-fidelity', 'source-media-role-placement')
                    if layout_mode == 'source-media-guided' else
                    ('visible-copy-transcription', 'no-unsupported-facts', 'material-roles',
                     'excluded-content'))}
                _, task, _ = ProjectCommandService(kernel).request_agent_action(
                    'review-' + request_id, kernel.load().revision,
                    action_type='review-visual-engineering', target_refs=targets,
                    instructions='Review the exact request media and provider result')
                review_ref = service.review_response(
                    'record-' + request_id, kernel.load().revision, request_id=request_id,
                    reviewer_task_id=task['task_id'], producer_task_id=request_id, checks=checks)
                reviewer = ProjectCommandService(kernel).resolve_agent_task(task['task_id'])
                self.assertEqual(reviewer['status'], 'completed')
                self.assertEqual(reviewer['result_refs'], [review_ref])
                choices.append({'slide_id': slide_id, 'request_id': request_id,
                                'review_ref': review_ref})
            _, selector, _ = ProjectCommandService(kernel).request_agent_action(
                'selector', kernel.load().revision, action_type='review-visual-aesthetic',
                target_refs=[source_ref], instructions='Choose exact guided and plain designs')
            selection_ref = service.select_internal(
                'select', kernel.load().revision, selections=choices,
                reviewer_task_id=selector['task_id'])
            ProjectCommandService(kernel).complete_agent_task(
                'complete-selector', kernel.load().revision,
                task_id=selector['task_id'], result_ref=selection_ref)
            selected = service.current_selection(selection_ref)['slides'][0]['target_binding']
            guided_response = kernel.artifacts.resolve(ArtifactReference.parse(
                kernel.load().artifact_heads['optimization/response/guided-one']))['payload']
            self.assertEqual(selected['target_image_sha256'], guided_response['image_sha256'])
            self.assertEqual(selected['material_roles'][0]['atom_id'], '9')

    def test_source_media_guided_request_rejects_missing_geometry_without_write(self):
        """A page without replayable media placement cannot claim guided fidelity."""
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        picture = ('<p:pic><p:nvPicPr><p:cNvPr id="9" name="unplaced"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>')
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'customer page') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rPicture', 'image', '../media/image1.png', '')])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='missing-guidance')
            inventory_ref, _ = ProjectCommandService(kernel).add_material(
                'import', kernel.load().revision, material_type='bytes',
                data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ExistingDeckOptimizationService(kernel).begin(
                'begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=source['sha256'], user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope(
                'scope', kernel.load().revision, user_message_ref='chat://message/authorized',
                allowed_page_orders=[1], excluded_image_sha256=[], excluded_text_item_ids=[])
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ExistingDeckSelectionService(kernel).register_request(
                    'guided-request', before.revision, slide_id='S0001',
                    request_id='guided-request', common_rules=RULES,
                    title_item_id='source-object-2', layout_mode='source-media-guided')
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)

    def test_unsent_media_request_can_be_withdrawn_without_reusing_identity(self):
        request_ref = self.request(request_id='unsent-media-request')
        before = self.kernel.load()
        withdrawal_ref = self.service.withdraw_unsent_request('withdraw', before.revision,
            request_id='unsent-media-request', reason='outbound source media not authorized')
        state = self.kernel.load()
        self.assertNotIn('optimization/request/unsent-media-request', state.artifact_heads)
        self.assertEqual(self.kernel.artifacts.resolve(ArtifactReference.parse(withdrawal_ref))['payload']['request_ref'], request_ref)
        with self.assertRaises(ContractValidationError):
            self.service.register_request('replay-id', state.revision, slide_id='S0001',
                request_id='unsent-media-request', common_rules=RULES,
                title_item_id=self.service.source_page('S0001')['visible_copy'][0]['item_id'])
        safe_ref = self.request(request_id='new-text-only-request')
        self.assertNotEqual(safe_ref, request_ref)

    def test_client_logo_gallery_mode_requires_four_source_categories_and_media(self):
        from ai_ppt_studio.application.image_led_selection import client_logo_gallery_instruction
        instruction = client_logo_gallery_instruction(4, 22)
        self.assertIn('4组', instruction)
        self.assertIn('每组5个', instruction)
        self.assertIn('20个', instruction)
        self.assertIn('无照片', instruction)
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.register_request('invalid-gallery', before.revision,
                slide_id='S0001', request_id='invalid-gallery', common_rules=RULES,
                title_item_id=self.service.source_page('S0001')['visible_copy'][0]['item_id'],
                layout_mode='client-logo-gallery-20')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_client_logo_gallery_is_text_only_even_with_twenty_embedded_images(self):
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        pictures = ''.join(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{index+10}" name="logo-{index}"/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="rLogo{index}"/></p:blipFill></p:pic>'
            for index in range(20))
        parts['ppt/slides/slide9.xml'] = slide(
            shape('2', '客户') + ''.join(shape(str(index + 3), name)
                for index, name in enumerate(('制造', '建筑', '交通', '政府'))) + pictures)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            (f'rLogo{index}', 'image', '../media/image1.png', '') for index in range(20)])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='gallery-source')
            inventory_ref, _ = ProjectCommandService(kernel).add_material('import', kernel.load().revision,
                material_type='bytes', data_base64=base64.b64encode(raw).decode(), filename='gallery.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=source['sha256'],
                user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope('scope', kernel.load().revision,
                user_message_ref='chat://message/text-only', allowed_page_orders=[1],
                excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            ref = service.register_request('request', kernel.load().revision,
                slide_id='S0001', request_id='gallery-text-only', common_rules=RULES,
                title_item_id='source-object-2', layout_mode='client-logo-gallery-20')
            payload = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']['payload']
            self.assertEqual(payload['materials'], [])
            self.assertIn('4组', payload['page_goal'])
            self.assertIn('20个空白客户标识版位', payload['page_goal'])
            self.assertNotIn(base64.b64encode(image_bytes()).decode(), str(payload))

    def test_local_original_media_becomes_exact_target_before_internal_selection(self):
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        picture = '<p:pic><p:nvPicPr><p:cNvPr id="9" name="source-logo"/></p:nvPicPr>' \
                  '<p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>'
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'customer page') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rPicture', 'image', '../media/image1.png', '')])
        parts['ppt/media/image1.png'] = image_bytes()
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='local-composite-test')
            inventory_ref, _ = ProjectCommandService(kernel).add_material('import', kernel.load().revision,
                material_type='bytes', data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            source_ref = ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=source['sha256'],
                user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope('scope', kernel.load().revision,
                user_message_ref='chat://message/text-only', allowed_page_orders=[1,2],
                excluded_image_sha256=[], excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            ref = service.register_request('design-first', kernel.load().revision,
                slide_id='S0001', request_id='design-first', common_rules=RULES,
                title_item_id='source-object-2', layout_mode='blank-media-slots')
            payload = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']['payload']
            self.assertEqual(payload['materials'], [])
            response_ref = service.execute_request('design-first', transport=FakeTransport(image('white')))
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                service.register_local_media_composition('wrong-source', before.revision,
                    request_id='design-first', placements=[
                        {'source_picture_object_ids':['other-picture'], 'bbox':[250,250,300,180]}])
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
            composition_ref = service.register_local_media_composition('local-source', kernel.load().revision,
                request_id='design-first', placements=[
                    {'source_picture_object_ids':['9'], 'bbox':[250,250,300,180]}])
            composition = kernel.artifacts.resolve(ArtifactReference.parse(composition_ref))['payload']
            actual = kernel.artifacts.resolve(ArtifactReference.parse(composition['target_image_ref']))['payload']
            self.assertNotEqual(actual['sha256'], kernel.artifacts.resolve(
                ArtifactReference.parse(response_ref))['payload']['image_sha256'])
            with Image.open(io.BytesIO(base64.b64decode(actual['data_base64']))) as rendered:
                self.assertEqual(rendered.getpixel((20,20)), (255,255,255))
                self.assertNotEqual(rendered.getpixel((400,340)), (255,255,255))
            choices = []
            for slide_id, request_id, result_ref in (
                    ('S0001','design-first',response_ref), ('S0002','design-second',None)):
                if result_ref is None:
                    service.register_request('design-second', kernel.load().revision,
                        slide_id=slide_id, request_id=request_id, common_rules=RULES,
                        title_item_id='source-object-2')
                    result_ref = service.execute_request(request_id, transport=FakeTransport(image('white')))
                if request_id == 'design-first':
                    _, wrong_task, _ = ProjectCommandService(kernel).request_agent_action(
                        'review-response-only', kernel.load().revision,
                        action_type='review-visual-engineering', target_refs=[result_ref],
                        instructions='Only the raw provider image')
                    before = kernel.load()
                    with self.assertRaises(ContractValidationError):
                        service.review_response('response-only', before.revision,
                            request_id=request_id, reviewer_task_id=wrong_task['task_id'],
                            producer_task_id=request_id,
                            checks={key:'passed' for key in (
                                'visible-copy-transcription','no-unsupported-facts',
                                'material-roles','excluded-content')})
                    self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
                targets = ([result_ref, composition_ref, composition['target_image_ref']]
                    if request_id == 'design-first' else [result_ref])
                checks = {key:'passed' for key in (
                    'visible-copy-transcription','no-unsupported-facts',
                    'material-roles','excluded-content')}
                if request_id == 'design-first':
                    checks.update({'composed-image-content':'passed', 'source-media-placement':'passed'})
                _, task, _ = ProjectCommandService(kernel).request_agent_action(
                    'review-'+request_id, kernel.load().revision,
                    action_type='review-visual-engineering', target_refs=targets,
                    instructions='Check source, response, and exact composite visual target')
                review_ref = service.review_response('pass-'+request_id, kernel.load().revision,
                    request_id=request_id, reviewer_task_id=task['task_id'],producer_task_id=request_id,
                    checks=checks)
                ProjectCommandService(kernel).complete_agent_task('complete-'+request_id,
                    kernel.load().revision,task_id=task['task_id'],result_ref=review_ref)
                choices.append({'slide_id':slide_id,'request_id':request_id,'review_ref':review_ref})
            _, task, _ = ProjectCommandService(kernel).request_agent_action('choose', kernel.load().revision,
                action_type='review-visual-aesthetic',target_refs=[source_ref],instructions='Choose exact images')
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                service.select_internal('uncomposed',before.revision,
                    selections=choices,reviewer_task_id=task['task_id'])
            self.assertEqual(kernel.load().artifact_heads,before.artifact_heads)
            choices[0]['composition_ref'] = composition_ref
            selection_ref = service.select_internal('composed',kernel.load().revision,
                selections=choices,reviewer_task_id=task['task_id'])
            ProjectCommandService(kernel).complete_agent_task('complete-choice',kernel.load().revision,
                task_id=task['task_id'],result_ref=selection_ref)
            selected = service.current_selection(selection_ref)['slides'][0]['target_binding']
            self.assertEqual(selected['target_image_sha256'], actual['sha256'])
            self.assertEqual(selected['material_roles'][0]['atom_id'],'9')

    def test_historical_design_supports_bounded_source_region_replacement_and_exact_selection(self):
        import base64
        from ai_ppt_studio.kernel.transactions import ProjectKernel
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        pictures = ''.join((
            '<p:pic><p:nvPicPr><p:cNvPr id="9" name="evidence"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rEvidence"/></p:blipFill>'
            '<p:spPr><a:xfrm><a:off x="100" y="100"/><a:ext cx="400" cy="240"/></a:xfrm></p:spPr></p:pic>',
            '<p:pic><p:nvPicPr><p:cNvPr id="10" name="decoration"/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="rDecoration"/></p:blipFill>'
            '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="50"/></a:xfrm></p:spPr></p:pic>',
        ))
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'historical page') + pictures)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rEvidence', 'image', '../media/image1.png', ''),
            ('rDecoration', 'image', '../media/image2.png', ''),
        ])
        parts['ppt/media/image1.png'] = image_bytes()
        parts['ppt/media/image2.png'] = image('gray')
        raw = archive(parts)
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id='historical-replace-test')
            inventory_ref, _ = ProjectCommandService(kernel).add_material(
                'import', kernel.load().revision, material_type='bytes',
                data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(
                ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            source_ref = ExistingDeckOptimizationService(kernel).begin(
                'begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=source['sha256'],
                user_message_ref='chat://message/optimize')
            ExistingDeckOptimizationService(kernel).set_external_scope(
                'scope', kernel.load().revision,
                user_message_ref='chat://message/current-scope',
                allowed_page_orders=[1, 2], excluded_image_sha256=[],
                excluded_text_item_ids=[])
            service = ExistingDeckSelectionService(kernel)
            historical = image((30, 80, 160))
            provenance = {
                'source_pptx_sha256': source['sha256'], 'page_order': 1,
                'historical_request_id': 'old-request',
                'historical_request_sha256': hashlib.sha256(b'old-request').hexdigest(),
                'historical_response_sha256': hashlib.sha256(b'old-response').hexdigest(),
                'historical_receiver': 'CRS', 'historical_model': 'gpt-image-2',
                'historical_quality': 'medium',
            }
            request_ref, response_ref = service.register_historical_design(
                'import-historical', kernel.load().revision, slide_id='S0001',
                request_id='historical-replace', common_rules=RULES,
                title_item_id='source-object-2',
                image_base64=base64.b64encode(historical).decode(),
                image_sha256=hashlib.sha256(historical).hexdigest(),
                provenance=provenance)
            placements = [
                {'operation': 'replace-source-region',
                 'source_picture_object_ids': ['9'], 'bbox': [180, 180, 520, 300],
                 'fit': 'cover', 'fill_rgb': [255, 255, 255]},
                {'operation': 'exclude-source-media',
                 'source_picture_object_ids': ['10'], 'reason': 'decorative-background'},
                {'operation': 'mask-region', 'bbox': [740, 180, 260, 70],
                 'fill_rgb': [247, 249, 255]},
                {'operation': 'page-marker', 'bbox': [1900, 1080, 96, 42],
                 'fill_rgb': [247, 249, 255], 'text_rgb': [65, 82, 112],
                 'text': 'S01', 'font_size': 18, 'align': 'center'},
            ]
            composition_ref = service.register_local_media_composition(
                'replace-source', kernel.load().revision,
                request_id='historical-replace', placements=placements)
            composition = kernel.artifacts.resolve(
                ArtifactReference.parse(composition_ref))['payload']
            self.assertEqual(composition['compositor_version'],
                             'historical-design-source-replacement/v1')
            self.assertEqual(composition['selected_source_picture_object_ids'], ['9'])
            self.assertEqual(composition['excluded_source_picture_object_ids'], ['10'])
            target = kernel.artifacts.resolve(
                ArtifactReference.parse(composition['target_image_ref']))['payload']
            self.assertNotEqual(target['sha256'], hashlib.sha256(historical).hexdigest())
            with Image.open(io.BytesIO(base64.b64decode(target['data_base64']))) as rendered:
                self.assertNotEqual(rendered.getpixel((440, 330)), (30, 80, 160))
                self.assertEqual(rendered.getpixel((760, 200)), (247, 249, 255))

            review_targets = [request_ref, response_ref, composition_ref,
                              composition['target_image_ref']]
            _, reviewer, _ = ProjectCommandService(kernel).request_agent_action(
                'review-replaced-historical', kernel.load().revision,
                action_type='review-visual-engineering', target_refs=review_targets,
                instructions='Check the exact historical base and local source replacements')
            checks = {key: 'passed' for key in (
                'visible-copy-transcription', 'no-unsupported-facts', 'material-roles',
                'excluded-content', 'composed-image-content', 'source-media-placement',
                'source-media-disposition')}
            review_ref = service.review_response(
                'review-historical-replacement', kernel.load().revision,
                request_id='historical-replace', reviewer_task_id=reviewer['task_id'],
                producer_task_id='historical-replace', checks=checks)
            second_request_ref = service.register_request(
                'request-second-page', kernel.load().revision, slide_id='S0002',
                request_id='second-page', common_rules=RULES,
                title_item_id='source-object-2')
            second_response_ref = service.execute_request(
                'second-page', transport=FakeTransport(image('white')))
            _, second_reviewer, _ = ProjectCommandService(kernel).request_agent_action(
                'review-second-page', kernel.load().revision,
                action_type='review-visual-engineering', target_refs=[second_response_ref],
                instructions='Check the second page')
            second_review_ref = service.review_response(
                'record-second-page-review', kernel.load().revision,
                request_id='second-page', reviewer_task_id=second_reviewer['task_id'],
                producer_task_id='second-page', checks={key: 'passed' for key in (
                    'visible-copy-transcription', 'no-unsupported-facts',
                    'material-roles', 'excluded-content')})
            _, selector, _ = ProjectCommandService(kernel).request_agent_action(
                'select-replaced-historical', kernel.load().revision,
                action_type='review-visual-aesthetic', target_refs=[source_ref],
                instructions='Select the exact locally corrected historical target')
            selection_ref = service.select_internal(
                'select-historical-replacement', kernel.load().revision,
                reviewer_task_id=selector['task_id'], selections=[{
                    'slide_id': 'S0001', 'request_id': 'historical-replace',
                    'review_ref': review_ref, 'composition_ref': composition_ref,
                }, {
                    'slide_id': 'S0002', 'request_id': 'second-page',
                    'review_ref': second_review_ref,
                }])
            ProjectCommandService(kernel).complete_agent_task(
                'complete-historical-selection', kernel.load().revision,
                task_id=selector['task_id'], result_ref=selection_ref)
            binding = service.current_selection(selection_ref)['slides'][0]['target_binding']
            self.assertEqual(binding['target_image_sha256'], target['sha256'])
            self.assertEqual([row['atom_id'] for row in binding['material_roles']], ['9'])

    def test_historical_region_replacement_rejects_whole_slide_touch(self):
        from ai_ppt_studio.application.existing_deck_optimization import _source_inventory
        from ai_ppt_studio.application.local_media_composition import compose_original_media
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes

        parts = package_parts()
        picture = ('<p:pic><p:nvPicPr><p:cNvPr id="9" name="evidence"/></p:nvPicPr>'
                   '<p:blipFill><a:blip r:embed="rEvidence"/></p:blipFill>'
                   '<p:spPr><a:xfrm><a:off x="100" y="100"/>'
                   '<a:ext cx="400" cy="240"/></a:xfrm></p:spPr></p:pic>')
        parts['ppt/slides/slide9.xml'] = slide(shape('2', 'historical page') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
            ('rEvidence', 'image', '../media/image1.png', ''),
        ])
        parts['ppt/media/image1.png'] = image_bytes()
        raw_source = archive(parts)
        page = _source_inventory(raw_source)[0]
        with self.assertRaisesRegex(ContractValidationError, 'whole-slide'):
            compose_original_media(
                response_bytes=image('white'), source_pptx_bytes=raw_source,
                page=page, layout_mode='historical-design-import', placements=[
                    {'operation': 'replace-source-region',
                     'source_picture_object_ids': ['9'], 'bbox': [0, 0, 2048, 1152],
                     'fit': 'cover', 'fill_rgb': [255, 255, 255]},
                ])

    def test_started_request_is_never_withdrawn_as_unsent(self):
        self.produce(request_id='sent-request')
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.withdraw_unsent_request('withdraw-sent', before.revision,
                request_id='sent-request', reason='must retain provider result')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_completed_unselected_design_can_be_superseded_for_explicit_revision(self):
        old_request, old_response, _ = self.produce(request_id='first-design')
        before = self.kernel.load()
        ref = self.service.supersede_unselected_response('revise-design', before.revision,
            request_id='first-design', reason='Source logo slots replaced by invented photos')
        after = self.kernel.load()
        record = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual((record['request_ref'], record['response_ref']), (old_request, old_response))
        self.assertNotIn('optimization/request/first-design', after.artifact_heads)
        self.assertNotIn('optimization/response/first-design', after.artifact_heads)
        with self.assertRaises(ContractValidationError):
            self.request(request_id='first-design')
        self.request(request_id='revised-design')

    def test_completed_stale_design_can_be_superseded_without_revalidating_old_contract(self):
        old_request, old_response, _ = self.produce(request_id='stale-completed-design')
        source = ExistingDeckOptimizationService(self.kernel).current_source()
        source_path = self.kernel.project_root / source['source_pptx_ref'][len('project://'):]
        source_path.write_bytes(b'changed after the completed design was persisted')
        with self.assertRaisesRegex(ContractValidationError, 'source'):
            self.service._request('stale-completed-design')
        ref = self.service.supersede_unselected_response(
            'retire-stale-completed', self.kernel.load().revision,
            request_id='stale-completed-design',
            reason='A stricter current contract requires a new explicit design request')
        record = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual((record['request_ref'], record['response_ref']),
                         (old_request, old_response))
        self.assertNotIn('optimization/request/stale-completed-design',
                         self.kernel.load().artifact_heads)
        self.assertNotIn('optimization/response/stale-completed-design',
                         self.kernel.load().artifact_heads)

    def test_independently_rejected_reviewed_design_can_be_superseded_without_erasing_history(self):
        old_request, old_response, _ = self.produce(request_id='reviewed-design')
        _, reviewer, _ = ProjectCommandService(self.kernel).request_agent_action(
            'review-old-design', self.kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[old_response],
            instructions='Review the exact current design before selection')
        old_review = self.service.review_response(
            'record-old-review', self.kernel.load().revision,
            request_id='reviewed-design', reviewer_task_id=reviewer['task_id'],
            producer_task_id='reviewed-design', checks={key: 'passed' for key in (
                'visible-copy-transcription', 'no-unsupported-facts',
                'material-roles', 'excluded-content')})

        ref = self.service.supersede_unselected_response(
            'supersede-reviewed-design', self.kernel.load().revision,
            request_id='reviewed-design',
            reason='Later independent visible review found an unsupported source-scene remnant')

        after = self.kernel.load()
        record = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual(record['request_ref'], old_request)
        self.assertEqual(record['response_ref'], old_response)
        self.assertEqual(record['review_ref'], old_review)
        self.assertNotIn('optimization/request/reviewed-design', after.artifact_heads)
        self.assertNotIn('optimization/response/reviewed-design', after.artifact_heads)
        self.assertNotIn('optimization/source-review/reviewed-design', after.artifact_heads)
        self.assertEqual(
            self.kernel.artifacts.resolve(ArtifactReference.parse(old_review))['payload']['request_id'],
            'reviewed-design')
        with self.assertRaises(ContractValidationError):
            self.request(request_id='reviewed-design')

    def test_unknown_result_is_preserved_and_not_superseded(self):
        request_ref = self.request(request_id='possibly-sent')
        from ai_ppt_studio.application.image_led_selection import ExistingDeckSelectionService as S
        claim = {'project_id':self.kernel.project_id, 'request_id':'possibly-sent',
                 'request_ref':request_ref, 'status':'unknown'}
        self.kernel.commit(command_id='unknown-claim',expected_revision=self.kernel.load().revision,
            event_type='optimization.image-response-preserved',
            artifact_updates={S.RESPONSE+'possibly-sent':('optimization-image-response',claim)})
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.supersede_unselected_response('unsafe-new-id', before.revision,
                request_id='possibly-sent', reason='unknown is not a revision')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_title_identity_is_explicit_not_first_text_object_by_guess(self):
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.register_request('ambiguous-title', before.revision,
                slide_id='S0001', request_id='title-ambiguous', common_rules=RULES)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)
        page = self.service.source_page('S0001')
        title_id = page['visible_copy'][1]['item_id']
        ref = self.service.register_request('specified-title', before.revision,
            slide_id='S0001', request_id='title-specific', common_rules=RULES,
            title_item_id=title_id)
        request = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual(request['title_item_id'], title_id)
        self.assertEqual(request['payload']['confirmed_visible_copy']['title'], page['visible_copy'][1]['text'])
        self.assertEqual(request['payload']['confirmed_visible_copy']['blocks'][0]['text'], page['visible_copy'][0]['text'])

    def test_missing_page_or_mutated_source_fails_before_request_write(self):
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.request('S0003')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)
        source = ExistingDeckOptimizationService(self.kernel).current_source()
        (self.kernel.project_root / source['source_pptx_ref'][len('project://'):]).write_bytes(b'mutated')
        with self.assertRaises(ContractValidationError):
            self.request()
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_external_source_scope_must_be_explicit_before_crs_request(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/optimize')
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ExistingDeckSelectionService(kernel).register_request('request', before.revision,
                    slide_id='S0001', request_id='generation-scope', common_rules=RULES)
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)

    def test_external_scope_denies_disallowed_page_before_request_write(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            scope = ExistingDeckOptimizationService(kernel)
            scope.begin('begin', kernel.load().revision, source_id=source['source_id'],
                source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/optimize')
            scope.set_external_scope('use-only-first', kernel.load().revision,
                user_message_ref='chat://message/external-use', allowed_page_orders=[1],
                excluded_image_sha256=[], excluded_text_item_ids=[])
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ExistingDeckSelectionService(kernel).register_request('denied', before.revision,
                    slide_id='S0002', request_id='generation-denied', common_rules=RULES)
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)

    def test_partial_or_unreviewed_design_never_becomes_selection(self):
        self.produce()
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.select_internal('choose', before.revision, selections=[
                {'slide_id': 'S0001', 'request_id': 'generation-1', 'review_ref': ''}],
                reviewer_task_id='internal-check-1')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)
        self.request('S0002', 'generation-2')
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.select_internal('choose', before.revision, selections=[],
                reviewer_task_id='internal-check-1')
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def complete_selection(self):
        choices = []
        for n in (1, 2):
            slide_id, req = f'S{n:04d}', f'generation-{n}'
            self.produce(slide_id, req, 'red' if n == 1 else 'blue')
            _, task, _ = ProjectCommandService(self.kernel).request_agent_action(
                'review-source-'+str(n), self.kernel.load().revision,
                action_type='review-visual-engineering',
                target_refs=[self.kernel.load().artifact_heads['optimization/response/'+req]],
                instructions='Check exact source and response')
            review_ref = self.service.review_response('review-'+str(n), self.kernel.load().revision,
                request_id=req, reviewer_task_id=task['task_id'],
                producer_task_id=req, checks={
                    'visible-copy-transcription': 'passed', 'no-unsupported-facts': 'passed',
                    'material-roles': 'passed', 'excluded-content': 'passed'})
            ProjectCommandService(self.kernel).complete_agent_task('finish-review-'+str(n),
                self.kernel.load().revision, task_id=task['task_id'], result_ref=review_ref)
            choices.append({'slide_id': slide_id, 'request_id': req, 'review_ref': review_ref})
        _, selector, _ = ProjectCommandService(self.kernel).request_agent_action(
            'select-deck', self.kernel.load().revision, action_type='review-visual-aesthetic',
            target_refs=[self.source_ref], instructions='Choose exact current reviewed images for all pages')
        ref = self.service.select_internal('select', self.kernel.load().revision,
            selections=choices, reviewer_task_id=selector['task_id'])
        ProjectCommandService(self.kernel).complete_agent_task('finish-selection',
            self.kernel.load().revision, task_id=selector['task_id'], result_ref=ref)
        selection = self.service.current_selection(ref)
        self.assertEqual(selection['selection_origin'], 'internally-selected')
        self.assertEqual(selection['source_ref'], self.source_ref)
        self.assertEqual([x['target_binding']['page_order'] for x in selection['slides']], [1, 2])
        self.assertNotIn('visual/image-led/selection-confirmation', self.kernel.load().artifact_heads)
        self.assertEqual(self.kernel.load().gate_status['G0'], 'open')
        return ref

    def test_complete_reviewed_selection_is_internal_and_exact(self):
        self.complete_selection()

    def test_page_swaps_and_replaced_response_bytes_are_rejected(self):
        self.produce('S0001', 'generation-1')
        self.produce('S0002', 'generation-2', 'blue')
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.review_response('wrong', before.revision, request_id='generation-1',
                reviewer_task_id='producer-1', producer_task_id='producer-1',
                checks={key: 'passed' for key in ('visible-copy-transcription','no-unsupported-facts',
                                                  'material-roles','excluded-content')})
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_review_cannot_invent_a_second_producer_task_identity(self):
        self.produce()
        _, task, _ = ProjectCommandService(self.kernel).request_agent_action(
            'check-source', self.kernel.load().revision,
            action_type='review-visual-engineering',
            target_refs=[self.kernel.load().artifact_heads['optimization/response/generation-1']],
            instructions='Check exact response')
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.review_response('bad-producer', before.revision,
                request_id='generation-1', reviewer_task_id=task['task_id'],
                producer_task_id='invented-agent-task',
                checks={key:'passed' for key in ('visible-copy-transcription',
                    'no-unsupported-facts','material-roles','excluded-content')})
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_fabricated_review_task_does_not_select_a_provider_image(self):
        self.produce()
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.review_response('forged-review', before.revision, request_id='generation-1',
                reviewer_task_id='unregistered-task', producer_task_id='generation-1',
                checks={key: 'passed' for key in ('visible-copy-transcription',
                    'no-unsupported-facts', 'material-roles', 'excluded-content')})
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_source_review_rejects_a_precompleted_task_without_write(self):
        _, response_ref, _ = self.produce()
        _, task, _ = ProjectCommandService(self.kernel).request_agent_action(
            'check-source-once', self.kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[response_ref],
            instructions='Check the exact provider response once')
        ProjectCommandService(self.kernel).complete_agent_task(
            'complete-review-before-result', self.kernel.load().revision,
            task_id=task['task_id'], result_ref=response_ref)
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.review_response('reuse-completed-reviewer', before.revision,
                request_id='generation-1', reviewer_task_id=task['task_id'],
                producer_task_id='generation-1', checks={key: 'passed' for key in (
                    'visible-copy-transcription', 'no-unsupported-facts',
                    'material-roles', 'excluded-content')})
        self.assertEqual(self.kernel.load().revision, before.revision)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)

    def test_replaced_source_review_invalidates_existing_selection(self):
        selection_ref = self.complete_selection()
        self.kernel.commit(command_id='replace-review-for-test',
            expected_revision=self.kernel.load().revision, event_type='test.review-replaced',
            artifact_updates={'optimization/source-review/generation-1':
                ('optimization-source-review', {'test_identity': 'replacement'})})
        with self.assertRaises(ContractValidationError):
            self.service.current_selection(selection_ref)

    def test_invalid_provider_observation_stays_unknown_and_cannot_be_selected(self):
        self.request()
        class InvalidObservation(FakeTransport):
            def generate(self, *, request_id, payload):
                result = super().generate(request_id=request_id, payload=payload)
                result['provider_observation'] = {'model_match': 'exact'}
                return result
        ref = self.service.execute_request('generation-1', transport=InvalidObservation(image('red')))
        response = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
        self.assertEqual(response['status'], 'unknown')
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.review_response('review', before.revision, request_id='generation-1',
                reviewer_task_id='fake', producer_task_id='generation-1',
                checks={key: 'passed' for key in ('visible-copy-transcription',
                    'no-unsupported-facts', 'material-roles', 'excluded-content')})
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)


if __name__ == '__main__':
    unittest.main()
