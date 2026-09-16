"""Real-font renderer and fresh Python-to-Node snapshot integration; synthetic slide only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from tests.test_image_led_results import NODE, MODULES, PYTHON, CODE_ROOT
from ai_ppt_studio.application.image_led_ooxml import NS

REGULAR = Path.home() / 'Library/Fonts/AI-PPT-e4b3b9d05875-msyh.ttc'
BOLD = Path.home() / 'Library/Fonts/AI-PPT-06e1a30f687a-msyhbd.ttc'
FONT_FILES = [
    {'path': str(REGULAR), 'sha256': 'e4b3b9d058750fb80899c24f68e35beda606ca92694eff0e9f7f91eec7a846aa'},
    {'path': str(BOLD), 'sha256': '06e1a30f687ab7d39f533447b21e84d51e0cecdaa6bfa060c87136b168811bdc'},
]
AVAILABLE = NODE.exists() and PYTHON.exists() and (MODULES / '@oai/artifact-tool').exists() and REGULAR.is_file() and BOLD.is_file()
SETUP = r"""
import assert from 'node:assert/strict';import fs from 'node:fs/promises';
import {createRequire} from 'node:module';import path from 'node:path';
import {preflight,render} from './scripts/image-led-native.mjs';
import {nativeV3Handoff} from './tests/fixtures/image-led-native-v3.mjs';
const root=process.argv[1],h=nativeV3Handoff(root),s=h.slides[0];
const styles=r=>r.kind==='text'?(r.appearance.fragments?r.appearance.fragments.map(f=>f.appearance):[r.appearance]):r.kind==='table'?r.appearance.cells.map(c=>c.style):[];
const fontFamily=family=>{for(const key of ['regions','objects'])for(const r of s[key])for(const style of styles(r))for(const run of style.runs)run.fontFamily=family;};
fontFamily('Microsoft YaHei');
const options={projectRoot:root,nodeModulesRoot:process.env.C2_RUNTIME_NODE_MODULES,pythonExecutable:process.env.C2_RUNTIME_PYTHON};
const req=createRequire(path.join(options.nodeModulesRoot,'__font_integration__.cjs'));
const {FontLibrary}=createRequire(req.resolve('@oai/artifact-tool'))('skia-canvas');
"""


def environment(fonts=FONT_FILES):
    return {**os.environ, 'C2_RUNTIME_NODE': str(NODE), 'C2_RUNTIME_NODE_MODULES': str(MODULES),
            'C2_RUNTIME_PYTHON': str(PYTHON), 'C2_RUNTIME_FONT_FILES': json.dumps(fonts),
            'PYTHONPATH': str(CODE_ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}


def node(root, ending, fonts=FONT_FILES):
    result = subprocess.run([str(NODE), '--input-type=module', '-e', SETUP + ending, str(root)],
                            cwd=CODE_ROOT, env=environment(fonts), text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise AssertionError('Font renderer integration failed: ' + result.stderr[-6000:])
    return json.loads(result.stdout.strip().splitlines()[-1])


@unittest.skipUnless(AVAILABLE, 'bundled SDK or exact local YaHei font fixtures unavailable')
class ImageLedFontsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-real-font-integration-')
        cls.root = Path(cls.directory.name).resolve()
        try:
            cls.result = node(cls.root, r"""
const before=structuredClone(h),p=await preflight(h,options);
await assert.rejects(fs.stat(h.output_paths.directory),{code:'ENOENT'});
assert.deepEqual(h,before);
const output=await render(h,options);
assert.deepEqual(h,before);
console.log(JSON.stringify({handoff:h,output,fontEvidence:p.fontEvidence,registered:FontLibrary.family('Microsoft YaHei')}));
""")
        except Exception:
            cls.directory.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_renderer_exports_one_page_with_real_regular_and_bold_yahei(self):
        evidence = self.result['fontEvidence']
        self.assertEqual([(f['path'], f['sha256']) for f in evidence],
                         [(f['path'], f['sha256']) for f in FONT_FILES])
        self.assertTrue(any(f['family'] == 'Microsoft YaHei' and f['weight'] == 400 for f in evidence[0]['faces']))
        self.assertTrue(any(f['family'] == 'Microsoft YaHei' and f['weight'] == 700 for f in evidence[1]['faces']))
        registered_weights = self.result['registered']['weights']
        self.assertIn(400, registered_weights)
        self.assertIn(700, registered_weights)
        handoff, output = self.result['handoff'], self.result['output']
        self.assertEqual(len(handoff['slides']), 1)
        with ZipFile(output['pptx_path']) as archive:
            tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            runs = tree.findall('.//a:r/a:rPr', NS)
            self.assertTrue(runs)
            for run in runs:
                for tag in ('a:latin', 'a:ea', 'a:cs'):
                    self.assertEqual(run.find(tag, NS).get('typeface'), 'Microsoft YaHei')
            self.assertTrue(any(run.get('b') == '1' for run in runs))
            self.assertTrue(any(run.get('b', '0') == '0' for run in runs))
        self.assertEqual(output['visual_fidelity'], 'not-established')
        self.assertEqual(output['user_acceptance'], 'not-established')

    def verify_in_fresh_python(self, fonts):
        script = """
import json,sys
from ai_ppt_studio.application.image_led_results import preflight_output
value=json.load(sys.stdin)
result=preflight_output(value['output'],value['handoff'],value['root'])
print(json.dumps({'pptx_sha256':result['pptx_sha256'],'pages':len(result['renders'])}))
"""
        return subprocess.run([str(PYTHON), '-c', script], cwd=CODE_ROOT, env=environment(fonts), text=True,
            input=json.dumps({**self.result, 'root': str(self.root)}), capture_output=True, timeout=90)

    def test_fresh_python_snapshot_node_inherits_same_fonts_and_verifies_pixels(self):
        completed = self.verify_in_fresh_python(FONT_FILES)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        verified = json.loads(completed.stdout)
        self.assertEqual(verified, {'pptx_sha256': self.result['output']['pptx_sha256'], 'pages': 1})

    def test_missing_exact_font_fails_before_sdk_and_output_directory(self):
        with tempfile.TemporaryDirectory(prefix='native-missing-font-') as folder:
            root = Path(folder).resolve()
            result = node(root, r"""
// An OS that already provides YaHei still must reject a truly unavailable exact family.
const requested=FontLibrary.has('Microsoft YaHei')?'ImageLed Missing Exact Family 20260911':'Microsoft YaHei';
fontFamily(requested);let sdkLoads=0,message='';
await assert.rejects(render(h,{...options,loadSdk:async()=>{sdkLoads++;throw Error('unexpected SDK load');}}),error=>{message=error.message;return message.includes('IMAGE_LED_CAPABILITY_GAP: Exact font unavailable: '+requested);});
assert.equal(sdkLoads,0);await assert.rejects(fs.stat(h.output_paths.directory),{code:'ENOENT'});
assert.deepEqual(await fs.readdir(root),[]);
console.log(JSON.stringify({message,sdkLoads,requested}));
""", [])
            self.assertEqual(result['sdkLoads'], 0)
            self.assertIn('Exact font unavailable: ' + result['requested'], result['message'])
            self.assertEqual(list(root.iterdir()), [])

    def test_wrong_font_hash_fails_before_sdk_and_any_output(self):
        bad = [{**FONT_FILES[0], 'sha256': '0' * 64}, FONT_FILES[1]]
        with tempfile.TemporaryDirectory(prefix='native-wrong-font-hash-') as folder:
            root = Path(folder).resolve()
            result = node(root, r"""
let sdkLoads=0,message='';
await assert.rejects(render(h,{...options,loadSdk:async()=>{sdkLoads++;throw Error('unexpected SDK load');}}),error=>{message=error.message;return message.includes('IMAGE_LED_FONT: Font SHA-256 does not match actual bytes');});
assert.equal(sdkLoads,0);await assert.rejects(fs.stat(h.output_paths.directory),{code:'ENOENT'});
assert.deepEqual(await fs.readdir(root),[]);
console.log(JSON.stringify({message,sdkLoads}));
""", bad)
            self.assertEqual(result['sdkLoads'], 0)
            self.assertEqual(list(root.iterdir()), [])

    def test_snapshot_wrong_font_configuration_rejects_without_rewriting_artifacts(self):
        before = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        completed = self.verify_in_fresh_python([{**FONT_FILES[0], 'sha256': '0' * 64}])
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Font SHA-256 does not match actual bytes', completed.stderr)
        after = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
