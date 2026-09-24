"""Existing-deck source admission must bind actual PPTX bytes before design."""
from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from ai_ppt_studio.application.existing_deck_optimization import (
    EXTERNAL_SCOPE_SLOT,
    SOURCE_SLOT,
    ExistingDeckOptimizationService,
    _source_inventory,
    source_page_media,
)
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_image_led_ooxml import archive, package_parts, slide, shape, relationships, image_bytes


def fixture(root: Path):
    raw = archive(package_parts())
    kernel = ProjectKernel.initialize(root, project_id='existing-deck-test')
    inventory_ref, _ = ProjectCommandService(kernel).add_material('source-import', kernel.load().revision,
        material_type='bytes', data_base64=base64.b64encode(raw).decode(), filename='source.pptx',
        label='用户指定的现有 PPT', mime_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
    return kernel, raw, source


class ExistingDeckSourceTests(unittest.TestCase):
    def test_new_external_scope_uses_the_only_current_sunburst_route(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            service = ExistingDeckOptimizationService(kernel)
            service.begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/existing-deck-task')
            ref = service.set_external_scope('scope', kernel.load().revision,
                user_message_ref='chat://message/current-sunburst-authorization',
                allowed_page_orders=[1, 2], excluded_image_sha256=[],
                excluded_text_item_ids=[])
            scope = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
            self.assertEqual((scope['receiver'], scope['model']),
                ('CRS', 'gpt-image-2.5-sunburst'))

    def test_explicit_scope_refresh_upgrades_legacy_image2_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            service = ExistingDeckOptimizationService(kernel)
            service.begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/existing-deck-task')
            source_ref = kernel.load().artifact_heads[SOURCE_SLOT]
            legacy = {
                'project_id': kernel.project_id,
                'source_ref': source_ref,
                'source_pptx_sha256': hashlib.sha256(raw).hexdigest(),
                'receiver': 'CRS',
                'model': 'gpt-image-2',
                'user_message_ref': 'chat://message/historical-image2-authorization',
                'authority': 'agent-recorded-user-scope',
                'allowed_page_orders': [1, 2],
                'excluded_image_sha256': [],
                'excluded_text_item_ids': [],
            }
            state = kernel.commit(command_id='legacy-scope',
                expected_revision=kernel.load().revision,
                event_type='test.legacy-external-scope',
                artifact_updates={EXTERNAL_SCOPE_SLOT:
                    ('optimization-external-use-scope', legacy)})
            legacy_ref = state.artifact_heads[EXTERNAL_SCOPE_SLOT]
            refreshed_ref = service.set_external_scope('upgrade-scope', state.revision,
                user_message_ref='chat://message/current-sunburst-authorization',
                allowed_page_orders=[1, 2], excluded_image_sha256=[],
                excluded_text_item_ids=[])
            self.assertNotEqual(refreshed_ref, legacy_ref)
            self.assertEqual(kernel.artifacts.resolve(
                ArtifactReference.parse(legacy_ref))['payload']['model'], 'gpt-image-2')
            refreshed = kernel.artifacts.resolve(
                ArtifactReference.parse(refreshed_ref))['payload']
            self.assertEqual(refreshed['model'], 'gpt-image-2.5-sunburst')
            self.assertEqual(refreshed['supersedes_scope_ref'], legacy_ref)

    def test_registers_exact_source_order_text_and_bytes_in_optimization_route(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            result = ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/existing-deck-task')
            record = kernel.artifacts.resolve(ArtifactReference.parse(result))['payload']
            self.assertEqual(record['source_pptx_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual([page['slide_id'] for page in record['slides']], ['S0001', 'S0002'])
            self.assertEqual([page['page_order'] for page in record['slides']], [1, 2])
            self.assertEqual([row['text'] for row in record['slides'][0]['visible_copy']],
                [' first visible page \n', 'another object'])
            self.assertEqual([row['text'] for row in record['slides'][1]['visible_copy']],
                ['second visible page'])
            self.assertEqual(kernel.load().artifact_heads['optimization/source'], result)
            self.assertNotIn('gate/G0/confirmation', kernel.load().artifact_heads)
            self.assertEqual(kernel.load().gate_status['G0'], 'open')

    def test_project_command_exposes_explicit_route_without_user_gate_forgery(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, raw, source = fixture(Path(folder))
            commands = ProjectCommandService(kernel)
            ref = commands.begin_existing_deck_optimization('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=hashlib.sha256(raw).hexdigest(),
                user_message_ref='chat://message/existing-deck-task')
            self.assertEqual(kernel.load().artifact_heads['optimization/source'], ref)
            self.assertNotIn('gate/G0/confirmation', kernel.load().artifact_heads)

    def test_wrong_source_hash_is_rejected_without_runtime_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _, source = fixture(Path(folder))
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ExistingDeckOptimizationService(kernel).begin('wrong-source', before.revision,
                    source_id=source['source_id'], source_pptx_sha256='0' * 64,
                    user_message_ref='chat://message/existing-deck-task')
            self.assertEqual(kernel.load().revision, before.revision)
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)

    def test_missing_or_mutated_project_snapshot_is_rejected_without_runtime_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _, source = fixture(Path(folder))
            path = kernel.project_root / source['project_copy']
            path.write_bytes(b'mutated source')
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ExistingDeckOptimizationService(kernel).begin('mutated-source', before.revision,
                    source_id=source['source_id'], source_pptx_sha256=source['sha256'],
                    user_message_ref='chat://message/existing-deck-task')
            self.assertEqual(kernel.load().revision, before.revision)
            self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)

    def test_invisible_exact_placeholder_is_tracked_but_not_sent_as_real_material(self):
        from ai_ppt_studio.application.existing_deck_optimization import TRANSPARENT_PLACEHOLDER_BYTES
        parts = package_parts()
        picture = '<p:pic><p:nvPicPr><p:cNvPr id="9" name="pixel"/></p:nvPicPr><p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>'
        parts['ppt/slides/slide9.xml'] = slide(shape('2', ' visible ') + picture)
        parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([('rPicture','image','../media/image1.png','')])
        parts['ppt/media/image1.png'] = TRANSPARENT_PLACEHOLDER_BYTES
        raw = archive(parts)
        page = _source_inventory(raw)[0]
        self.assertEqual(page['media_refs'][0]['sha256'], hashlib.sha256(TRANSPARENT_PLACEHOLDER_BYTES).hexdigest())
        self.assertEqual(source_page_media(raw, page), [])

    def test_embedded_image_identity_is_taken_from_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = package_parts()
            picture = '<p:pic><p:nvPicPr><p:cNvPr id="9" name="image"/></p:nvPicPr><p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>'
            parts['ppt/slides/slide9.xml'] = slide(shape('2', ' exact original ') + picture)
            parts['ppt/slides/_rels/slide9.xml.rels'] = relationships([
                ('rPicture', 'image', '../media/image1.png', '')])
            media = image_bytes()
            parts['ppt/media/image1.png'] = media
            raw = archive(parts)
            kernel = ProjectKernel.initialize(Path(folder), project_id='existing-deck-test')
            inventory_ref, _ = ProjectCommandService(kernel).add_material('import', kernel.load().revision,
                material_type='bytes', data_base64=base64.b64encode(raw).decode(), filename='source.pptx')
            source = kernel.artifacts.resolve(ArtifactReference.parse(inventory_ref))['payload']['sources'][0]
            ref = ExistingDeckOptimizationService(kernel).begin('begin', kernel.load().revision,
                source_id=source['source_id'], source_pptx_sha256=source['sha256'],
                user_message_ref='chat://message/existing-deck-task')
            record = kernel.artifacts.resolve(ArtifactReference.parse(ref))['payload']
            self.assertEqual(record['slides'][0]['media_refs'], [
                {'object_id': '9', 'sha256': hashlib.sha256(media).hexdigest()}])


if __name__ == '__main__':
    unittest.main()
