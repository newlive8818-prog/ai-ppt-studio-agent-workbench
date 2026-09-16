import json, subprocess, tempfile, unittest
from pathlib import Path

from ai_ppt_studio.application.image_led_results import preflight_output

ROOT = Path(__file__).resolve().parents[1]
NODE = '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'

class DiagnosticSdkRendererTests(unittest.TestCase):
    def test_diagnostic_render_writes_reimport_and_snapshot_bound_outputs(self):
        script = r'''
import fs from 'node:fs';
import {nativeV3Handoff} from './fixtures/image-led-native-v3.mjs';
import {render} from '../scripts/image-led-native.mjs';
const root=process.argv[2];
const h=nativeV3Handoff(root);
h.handoff_version='codex-presentations-image-led-diagnostic/v1';
h.compiler_version='image-led-diagnostic-compiler/v1';
h.purpose='region-diagnostic';
h.diagnostic_ref='artifact://image-led-native-diagnostic-input/'+'a'.repeat(64);
delete h.plan_ref;
h.output_paths={directory:root+'/diagnostic/'+h.task_id,pptx:root+'/diagnostic/'+h.task_id+'/native-diagnostic.pptx'};
const result=await render(h,{projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON});
console.log(JSON.stringify(result));
'''
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'diagnostic').mkdir()
            path=ROOT / 'tests' / '_diagnostic_renderer_probe.mjs'; path.write_text(script, encoding='utf-8')
            try:
                env={'C2_RUNTIME_NODE_MODULES':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules', 'C2_RUNTIME_PYTHON':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'}
                result=subprocess.run([NODE,str(path),tmp],cwd=ROOT,text=True,capture_output=True,env={**__import__('os').environ,**env})
                self.assertEqual(result.returncode, 0, result.stderr)
                payload=json.loads(result.stdout.strip().splitlines()[-1])
                self.assertEqual(payload['artifact_type'], 'image-led-native-diagnostic-result')
                self.assertEqual(payload['status'], 'engineering-output-unassessed')
                self.assertNotIn('plan_ref', payload)
                output=Path(tmp, 'diagnostic', payload['task_id'])
                for name in ('native-diagnostic.pptx','handoff.json','mapping.json','inspect.ndjson','authoring.proto.json','reimport.proto.json','result.json','slide-1.png','slide-1.layout.json','compare-1-side-by-side.png','compare-1-overlay.png','compare-1-regions.json'):
                    self.assertTrue((output / name).is_file(), name)
                self.assertEqual(payload['files']['handoff.json']['path'], str(output / 'handoff.json'))
                self.assertEqual(payload['pptx_path'], str(output / 'native-diagnostic.pptx'))
                handoff=json.loads((output / 'handoff.json').read_text(encoding='utf-8'))
                checked=preflight_output(payload, handoff, Path(tmp))
                self.assertEqual(checked['pptx_sha256'], payload['pptx_sha256'])
            finally: path.unlink(missing_ok=True)

    def test_diagnostic_handoff_is_accepted_without_formal_plan_ref(self):
        script = r'''
import {nativeV3Handoff} from './fixtures/image-led-native-v3.mjs';
import {preflight} from '../scripts/image-led-native.mjs';
const root=process.argv[2], h=nativeV3Handoff(root);
const d=structuredClone(h); d.handoff_version='codex-presentations-image-led-diagnostic/v1'; d.compiler_version='image-led-diagnostic-compiler/v1'; d.purpose='region-diagnostic'; d.diagnostic_ref='artifact://image-led-native-diagnostic-input/'+'a'.repeat(64); delete d.plan_ref;
d.output_paths={directory:root+'/diagnostic/'+d.task_id,pptx:root+'/diagnostic/'+d.task_id+'/native-diagnostic.pptx'};
const p=await preflight(d,{projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON}); console.log(p.handoff.purpose);
'''
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'diagnostic').mkdir()
            path=ROOT / 'tests' / '_diagnostic_renderer_probe.mjs'; path.write_text(script, encoding='utf-8')
            try:
                env={'C2_RUNTIME_NODE_MODULES':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules', 'C2_RUNTIME_PYTHON':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'}
                result=subprocess.run([NODE,str(path),tmp],cwd=ROOT,text=True,capture_output=True,env={**__import__('os').environ,**env})
                self.assertEqual(result.returncode, 0, result.stderr)
            finally: path.unlink(missing_ok=True)

    def test_placeholder_red_until_diagnostic_contract_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'diagnostic').mkdir()
            path=ROOT / 'tests' / '_diagnostic_renderer_red.mjs'
            path.write_text(script_for_red(), encoding='utf-8')
            try:
                env={'C2_RUNTIME_NODE_MODULES':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules', 'C2_RUNTIME_PYTHON':'/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'}
                result=subprocess.run([NODE,str(path),tmp],cwd=ROOT,text=True,capture_output=True,env={**__import__('os').environ,**env})
                self.assertNotEqual(result.returncode, 0)
            finally:
                path.unlink(missing_ok=True)

def script_for_red():
    return "import {nativeV3Handoff} from './fixtures/image-led-native-v3.mjs';\nimport {preflight} from '../scripts/image-led-native.mjs';\nconst h=nativeV3Handoff(process.argv[1]); h.handoff_version='codex-presentations-image-led-diagnostic/v1'; h.compiler_version='image-led-diagnostic-compiler/v1'; h.purpose='region-diagnostic'; h.diagnostic_ref='artifact://image-led-native-diagnostic-input/'+'a'.repeat(64); delete h.plan_ref; await preflight(h,{projectRoot:process.argv[1],nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON});"

if __name__ == '__main__': unittest.main()
