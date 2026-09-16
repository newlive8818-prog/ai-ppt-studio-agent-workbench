"""Real ContextCompiler and Agent action handoff for the finalized native route."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import ContractValidationError, WorkbenchValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests import test_image_led_runtime as runtime_fixtures
from tests.test_image2_input_boundary import tree_snapshot

TASK_ID = 'a' * 64


def ready_fixture(root):
    return runtime_fixtures.g1_fixture(root)


def context(kernel, targets=None):
    return ContextCompiler(kernel).compile_role_task(
        role_id='native-first-engineer', task_type='build-native-first',
        project_revision=kernel.load().revision,
        target_refs=targets if targets is not None else [kernel.load().artifact_heads['visual/compilation-plan']],
        instructions='忠实转换定版图，不改字、不重排。', task_id=TASK_ID)


class ImageLedHandoffTests(unittest.TestCase):
    def test_context_compiler_produces_renderer_consumable_closed_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            before = tree_snapshot(Path(folder))
            try:
                compiled = context(kernel)
            except (ContractValidationError, WorkbenchValidationError, GateBlockedError) as exc:
                self.fail(f'Current finalized plan must compile through real ContextCompiler: {exc}')
            wrapper = compiled['layers']['visual_handoff']
            renderer = wrapper['renderer_handoff']
            self.assertEqual(set(renderer), {'handoff_version','compiler_version','project_id',
                'selection_ref','region_inventory_ref','plan_ref','task_id','slides','assets','output_paths'})
            self.assertEqual(renderer['compiler_version'], 'image-led-faithful-compiler/v1')
            self.assertEqual(renderer['handoff_version'], 'codex-presentations-image-led/v1')
            self.assertEqual(renderer['plan_ref'], kernel.load().artifact_heads['visual/compilation-plan'])
            plan = kernel.artifacts.resolve(ArtifactReference.parse(renderer['plan_ref']))['payload']
            self.assertEqual(renderer['slides'], plan['slides'])
            self.assertEqual(set(renderer['assets']), {s['target_binding']['target_image_ref'] for s in plan['slides']})
            self.assertEqual(wrapper['result_expected_revision'], kernel.load().revision + 1)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_stale_target_and_existing_output_fail_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            before = tree_snapshot(Path(folder))
            with self.assertRaises((ContractValidationError, WorkbenchValidationError)):
                context(kernel, [kernel.load().artifact_heads['visual/contracts']])
            self.assertEqual(tree_snapshot(Path(folder)), before)

            output = kernel.project_root / TASK_ID
            output.mkdir()
            before = tree_snapshot(Path(folder))
            with self.assertRaises((ContractValidationError, WorkbenchValidationError)):
                context(kernel)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_native_handoff_requires_the_formal_builder_role_and_g1(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = runtime_fixtures.contract_fixture(Path(folder))
            before = tree_snapshot(Path(folder))
            with self.assertRaises((ContractValidationError, WorkbenchValidationError, GateBlockedError)):
                context(kernel)
            self.assertEqual(tree_snapshot(Path(folder)), before)
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            before = tree_snapshot(Path(folder))
            with self.assertRaises((ContractValidationError, WorkbenchValidationError, GateBlockedError)):
                ContextCompiler(kernel).compile_role_task(role_id='image-asset-producer',
                    task_type='build-native-first', project_revision=kernel.load().revision,
                    target_refs=[kernel.load().artifact_heads['visual/compilation-plan']],
                    instructions='', task_id=TASK_ID)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_result_revalidation_requires_exact_wrapper_and_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            revision = kernel.load().revision
            wrapper = context(kernel)['layers']['visual_handoff']
            validator = ContextCompiler(kernel)
            kwargs = dict(project_revision=revision, expected_revision=revision + 1,
                target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], task_id=TASK_ID)
            validator.validate_visual_handoff_for_result(wrapper, **kwargs)
            changed = deepcopy(wrapper)
            changed['renderer_handoff']['slides'][0]['objects'][0]['bbox'][0] += 1
            with self.assertRaises((ContractValidationError, WorkbenchValidationError)):
                validator.validate_visual_handoff_for_result(changed, **kwargs)
            with self.assertRaises((ContractValidationError, WorkbenchValidationError)):
                validator.validate_visual_handoff_for_result(wrapper, **{**kwargs, 'expected_revision': revision + 2})

    def test_existing_result_revalidation_survives_later_revision_and_gate_closure(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            revision = kernel.load().revision
            wrapper = context(kernel)['layers']['visual_handoff']
            # A synthetic state-transition boundary test, never a real G2 proof.
            from ai_ppt_studio.kernel.gates import issue_gate_mutation
            kernel.commit(command_id='synthetic-g2-read-boundary', expected_revision=revision,
                event_type='test.synthetic-later-gate', artifact_updates={}, gate_mutation=issue_gate_mutation({'G2': 'passed'}, ()))
            before = tree_snapshot(Path(folder))
            try:
                ContextCompiler(kernel).validate_visual_handoff_for_result(wrapper,
                    project_revision=revision, expected_revision=revision + 1,
                    target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], task_id=TASK_ID)
            except (ContractValidationError, WorkbenchValidationError, GateBlockedError) as exc:
                self.fail(f'Revalidating historical handoff is read-only after G2: {exc}')
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_real_build_action_persists_same_formal_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            commands = ProjectCommandService(kernel)
            try:
                _, task, _ = commands.request_agent_action('native-faithful', kernel.load().revision,
                    action_type='build-native-first', target_refs=[kernel.load().artifact_heads['visual/compilation-plan']],
                    instructions='忠实转换定版图。')
            except (ContractValidationError, WorkbenchValidationError, GateBlockedError) as exc:
                self.fail(f'Real build-native-first must issue the finalized renderer payload: {exc}')
            context_pack = kernel.artifacts.resolve(ArtifactReference.parse(task['context_pack_ref']))['payload']
            renderer = context_pack['layers']['visual_handoff']['renderer_handoff']
            self.assertEqual(renderer['task_id'], task['task_id'])
            self.assertEqual(renderer['plan_ref'], task['target_refs'][0])
            self.assertEqual(kernel.load().gate_status['G2'], 'open')

    def test_formal_action_payload_is_accepted_by_actual_renderer_preflight(self):
        runtime = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
        node = os.environ.get('C2_RUNTIME_NODE') or shutil.which('node') or str(runtime / 'node/bin/node')
        modules = Path(os.environ.get('C2_RUNTIME_NODE_MODULES', str(runtime / 'node/node_modules')))
        if not Path(node).is_file() or not modules.is_dir():
            self.skipTest('Actual bundled Node runtime unavailable; renderer integration NotRun')
        with tempfile.TemporaryDirectory() as folder:
            kernel, _ = ready_fixture(Path(folder))
            _, task, _ = ProjectCommandService(kernel).request_agent_action(
                'renderer-preflight', kernel.load().revision, action_type='build-native-first',
                target_refs=[kernel.load().artifact_heads['visual/compilation-plan']], instructions='忠实转换。')
            pack = kernel.artifacts.resolve(ArtifactReference.parse(task['context_pack_ref']))['payload']
            renderer = pack['layers']['visual_handoff']['renderer_handoff']
            before = tree_snapshot(Path(folder))
            script = Path(__file__).resolve().parents[1] / 'scripts/image-led-native.mjs'
            runner = """import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const {preflight} = await import(pathToFileURL(process.argv[1]));
const h = JSON.parse(readFileSync(0, 'utf8'));
const result = await preflight(h, {projectRoot:process.argv[2], nodeModulesRoot:process.argv[3], pythonExecutable:process.argv[4]});
process.stdout.write(JSON.stringify({slides:result.handoff.slides.length,version:result.handoff.compiler_version}));"""
            result = subprocess.run([node, '--input-type=module', '-e', runner,
                str(script), str(kernel.project_root.resolve()), str(modules), sys.executable],
                input=json.dumps(renderer), text=True, capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'slides': 3, 'version': 'image-led-faithful-compiler/v1'})
            self.assertEqual(tree_snapshot(Path(folder)), before)


if __name__ == '__main__':
    unittest.main()
