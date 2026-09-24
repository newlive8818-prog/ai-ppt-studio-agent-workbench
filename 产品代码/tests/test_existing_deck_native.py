"""A selected design has to map both ways before any native output directory exists."""
from copy import deepcopy
from unittest.mock import patch
import tempfile
from pathlib import Path
import unittest

from ai_ppt_studio.application.image_led_native import ExistingDeckNativeService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_existing_deck_selection import ExistingDeckSelectionTests
from tests.test_image_led_runtime import inventory_for
from tests.test_image_led_contracts import objects_for


class NativeTests(ExistingDeckSelectionTests):
    def test_complete_selection_and_two_way_region_mapping_precedes_build(self):
        selection_ref = self.complete_selection()
        selection = self.service.current_selection(selection_ref)
        inventory = inventory_for(selection, selection_ref)
        for item in inventory['slides']:
            item['source_image_size'] = {'width': 2048, 'height': 1152}
        objects = [objects_for(page['regions']) for page in inventory['slides']]
        native = ExistingDeckNativeService(self.kernel)
        before = self.kernel.load()
        bad = deepcopy(objects); bad[0].pop()
        with self.assertRaises(ContractValidationError):
            native.register_plan('missing-object', before.revision, inventory=inventory, objects=bad)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)
        bad = deepcopy(objects); bad[0].append({**bad[0][0], 'object_id': 'unbound-object'})
        with self.assertRaises(ContractValidationError):
            native.register_plan('extra-object', before.revision, inventory=inventory, objects=bad)
        self.assertEqual(self.kernel.load().artifact_heads, before.artifact_heads)
        plan_ref = native.register_plan('plan', before.revision, inventory=inventory, objects=objects)
        plan = native.current_plan(plan_ref)
        self.assertEqual(plan['selection_ref'], selection_ref)
        self.assertEqual(len(plan['slides']), 2)
        handoff = ContextCompiler(self.kernel).compile_existing_deck_handoff(
            task_id='a' * 64, plan_ref=plan_ref)
        self.assertEqual(len(handoff['slides']), 2)
        self.assertNotIn('source_slide_proto', handoff)
        self.assertEqual(handoff['slides'][0]['target_binding']['target_image_sha256'],
                         selection['slides'][0]['target_binding']['target_image_sha256'])
        self.assertFalse(Path(handoff['output_paths']['directory']).exists())

    def test_mutated_source_or_selected_image_blocks_handoff_before_file_write(self):
        selection_ref = self.complete_selection()
        selection = self.service.current_selection(selection_ref)
        inventory = inventory_for(selection, selection_ref)
        for item in inventory['slides']:
            item['source_image_size'] = {'width': 2048, 'height': 1152}
        plan_ref = ExistingDeckNativeService(self.kernel).register_plan('plan', self.kernel.load().revision,
            inventory=inventory, objects=[objects_for(page['regions']) for page in inventory['slides']])
        source = self.kernel.artifacts.resolve(ArtifactReference.parse(
            self.kernel.load().artifact_heads['optimization/source']))['payload']
        (self.kernel.project_root / source['source_pptx_ref'][len('project://'):]).write_bytes(b'mutated')
        with self.assertRaises(ContractValidationError):
            ContextCompiler(self.kernel).compile_existing_deck_handoff(task_id='a'*64, plan_ref=plan_ref)


if __name__ == '__main__':
    unittest.main()


class RenderedOutputTests(ExistingDeckSelectionTests):
    @unittest.skipUnless(__import__('tests.test_image_led_results', fromlist=['NODE']).NODE.exists() and
                         (__import__('tests.test_image_led_results', fromlist=['MODULES']).MODULES / '@oai/artifact-tool').exists(),
                         'bundled native renderer unavailable')
    def test_actual_two_page_editable_output_is_unassessed_until_qa(self):
        import json
        import subprocess
        from tests.test_image_led_results import NODE, MODULES, PYTHON, CODE_ROOT
        from ai_ppt_studio.application.image_led_results import ExistingDeckResultService
        selection_ref = self.complete_selection()
        inventory = inventory_for(self.service.current_selection(selection_ref), selection_ref)
        for item in inventory['slides']:
            item['source_image_size'] = {'width': 2048, 'height': 1152}
        plan_ref = ExistingDeckNativeService(self.kernel).register_plan('plan', self.kernel.load().revision,
            inventory=inventory, objects=[objects_for(page['regions']) for page in inventory['slides']])
        task_id = 'a'*64
        handoff = ContextCompiler(self.kernel).compile_existing_deck_handoff(task_id=task_id, plan_ref=plan_ref)
        runner = """
import fs from 'node:fs';import {render} from './scripts/image-led-native.mjs';
const h=JSON.parse(fs.readFileSync(0,'utf8'));
await render(h,{projectRoot:process.argv[1],nodeModulesRoot:process.argv[2],pythonExecutable:process.argv[3]});
"""
        completed = subprocess.run([str(NODE), '--input-type=module', '-e', runner,
            str(self.kernel.project_root), str(MODULES), str(PYTHON)], input=json.dumps(handoff),
            text=True, capture_output=True, cwd=CODE_ROOT, timeout=100)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads((Path(handoff['output_paths']['directory']) / 'result.json').read_text())
        results = ExistingDeckResultService(self.kernel)
        ref = results.register_result('native-result', self.kernel.load().revision,
            task_id=task_id, plan_ref=plan_ref, output=output)
        self.assertEqual(results.current_result(ref)['output']['pptx_sha256'], output['pptx_sha256'])
        self.assertEqual(len(output['renders']), 2)
        pages = []
        for slide, render, comparison in zip(handoff['slides'], output['renders'], output['comparisons']):
            pages.append({'slide_id': slide['target_binding']['slide_id'],
                'target_image_sha256': slide['target_binding']['target_image_sha256'],
                'render_sha256': render['sha256'],
                'comparison_sha256': comparison['region_differences']['sha256'],
                'checks': {key: 'passed' for key in results.REQUIRED},
                'region_checks': [{'region_id': row['region_id'], 'result': 'passed',
                    'detail': 'Synthetic test only'} for row in slide['regions']]})
        with self.assertRaisesRegex(ContractValidationError, 'governed'):
            results.register_qa('forged-qa', self.kernel.load().revision, result_ref=ref,
                reviewer_task_id='fabricated-reviewer', pages=pages,
                target_environment={'status': 'passed', 'target_id': 'macos-powerpoint',
                    'pptx_sha256': output['pptx_sha256'], 'evidence_ref': 'artifact://target-render-evidence/'+'c'*64})
        from ai_ppt_studio.application.project_service import ProjectCommandService
        _, reviewer, _ = ProjectCommandService(self.kernel).request_agent_action(
            'qa-review-task', self.kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[ref],
            instructions='Compare each region and all content dimensions against the selected image')
        for field in results.REQUIRED:
            changed = deepcopy(pages)
            changed[0]['checks'][field] = 'failed'
            with self.assertRaisesRegex(ContractValidationError, 'per page'):
                results.register_qa('failed-'+field, self.kernel.load().revision, result_ref=ref,
                    reviewer_task_id=reviewer['task_id'], pages=changed, target_environment={})
        # Isolate the target-evidence precondition in this synthetic fixture;
        # the real byte-backed mismatch is exercised below without a patch.
        with patch.object(ExistingDeckResultService, '_reject_obvious_visual_mismatch'):
            with self.assertRaisesRegex(ContractValidationError, 'PowerPoint'):
                results.register_qa('missing-target', self.kernel.load().revision, result_ref=ref,
                    reviewer_task_id=reviewer['task_id'], pages=pages, target_environment={})
        self.assertNotIn(results.QA_SLOT, self.kernel.load().artifact_heads)
        # Typed synthetic desktop receipts exercise identity routing only. They
        # are not a macOS PowerPoint run or user acceptance of this fixture.
        def synthetic(kind):
            return str(self.kernel.artifacts.put(kind, {'test_identity': 'synthetic-only'}))
        final_ref = self.kernel.load().artifact_heads[results.FINAL_SLOT]
        page_check_refs = [synthetic('slide-check') for _ in pages]
        target = {'target_id': 'macos-powerpoint', 'evidence_identity': 'formal-target-render',
            'operating_system': 'macOS', 'operating_system_version': 'synthetic-only',
            'application': 'Microsoft PowerPoint', 'application_version': 'synthetic-only',
            'application_check_result': 'passed', 'font_check_result': 'passed',
            'font_inventory_ref': synthetic('font-inventory'),
            'font_substitution_plan_ref': synthetic('font-plan'),
            'reviewer_attestation_ref': synthetic('desktop-review-attestation'),
            'source_pptx_ref': final_ref, 'pptx_sha256': output['pptx_sha256'],
            'sha256_before': output['pptx_sha256'], 'sha256_after': output['pptx_sha256'],
            'export_refs': [synthetic('target-export')],
            'page_image_refs': [synthetic('target-page-image') for _ in pages],
            'slide_checks': [{'slide_id': page['slide_id'], 'evidence_refs': [check_ref],
                'semantic_result': 'passed', 'aesthetic_result': 'passed',
                'engineering_result': 'passed', 'target_render_result': 'passed'}
                for page, check_ref in zip(pages, page_check_refs)],
            'executor': 'synthetic-only', 'exported_at': '2026-09-20T00:00:00+08:00',
            'tool_version': 'synthetic-only', 'overall_result': 'passed',
            'evidence_ref': synthetic('target-render-capture')}
        target_ref = results.register_target_evidence('target', self.kernel.load().revision,
            result_ref=ref, payload=target)
        # The actual renderer differs radically from the arbitrary red/blue
        # selected images. A complete, self-attested passed review cannot
        # overrule the byte-backed difference on either page.
        with self.assertRaisesRegex(ContractValidationError, 'obvious visual mismatch'):
            results.register_qa('gross-mismatch', self.kernel.load().revision, result_ref=ref,
                reviewer_task_id=reviewer['task_id'], pages=pages,
                target_environment={'status': 'passed', 'target_id': 'macos-powerpoint',
                    'pptx_sha256': output['pptx_sha256'], 'evidence_ref': target_ref})
        self.assertNotIn(results.QA_SLOT, self.kernel.load().artifact_heads)
        # Only the older synthetic identity-routing assertion below bypasses
        # this new gross-mismatch veto; no real project or positive visual
        # acceptance can use this test-only patch.
        with patch.object(ExistingDeckResultService, '_reject_obvious_visual_mismatch'):
            qa_ref = results.register_qa('qa', self.kernel.load().revision, result_ref=ref,
                reviewer_task_id=reviewer['task_id'], pages=pages,
                target_environment={'status': 'passed', 'target_id': 'macos-powerpoint',
                    'pptx_sha256': output['pptx_sha256'], 'evidence_ref': target_ref})
        with self.assertRaisesRegex(ContractValidationError, 'not completed'):
            results.delivery_candidate()
        ProjectCommandService(self.kernel).complete_agent_task('finish-qa', self.kernel.load().revision,
            task_id=reviewer['task_id'], result_ref=qa_ref)
        self.assertEqual(results.delivery_candidate()['result_ref'], ref)
        self.assertEqual(self.kernel.load().gate_status['G4'], 'locked')
