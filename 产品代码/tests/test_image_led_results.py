"""Synthetic byte-backed renderer results. No customer or acceptance evidence."""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import ai_ppt_studio.application.image_led_results as image_led_results_module
from ai_ppt_studio.application.image_led_results import preflight_output
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference

CODE_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
NODE = Path(os.environ.get('C2_RUNTIME_NODE', str(BUNDLE / 'node/bin/node')))
MODULES = Path(os.environ.get('C2_RUNTIME_NODE_MODULES', str(BUNDLE / 'node/node_modules')))
PYTHON = Path(os.environ.get('C2_RUNTIME_PYTHON', str(BUNDLE / 'python/bin/python3')))


def render_runtime_fixture(root):
    from tests.test_image_led_runtime import g1_fixture
    from ai_ppt_studio.application.project_service import ProjectCommandService
    kernel, _ = g1_fixture(root)
    _, task, _ = ProjectCommandService(kernel).request_agent_action('native-result-producer', kernel.load().revision,
        action_type='build-native-first', target_refs=[kernel.load().artifact_heads['visual/compilation-plan']],
        instructions='Synthetic native-result integration, never a real visual or user approval')
    context = kernel.artifacts.resolve(ArtifactReference.parse(task['context_pack_ref']))['payload']
    handoff = context['layers']['visual_handoff']['renderer_handoff']
    runner = """
import fs from 'node:fs';import {render} from './scripts/image-led-native.mjs';
const h=JSON.parse(fs.readFileSync(0,'utf8'));
await render(h,{projectRoot:process.argv[1],nodeModulesRoot:process.argv[2],pythonExecutable:process.argv[3]});
"""
    completed = subprocess.run([str(NODE), '--input-type=module', '-e', runner, str(root), str(MODULES), str(PYTHON)],
        input=json.dumps(handoff), text=True, capture_output=True, cwd=CODE_ROOT, timeout=90)
    if completed.returncode:
        raise AssertionError('Synthetic renderer failed: ' + completed.stderr)
    output = json.loads((Path(handoff['output_paths']['directory']) / 'result.json').read_text())
    return kernel, task, handoff, output


class ImageLedResultTests(unittest.TestCase):
    def test_generated_proto_json_rejects_duplicate_properties(self):
        raw = '{"slides":[],"slides":[1]}'
        with self.assertRaises(ContractValidationError):
            image_led_results_module._generated_json(raw)

    def test_generated_proto_json_accepts_ordinary_generated_json(self):
        raw = '{"slides":[{"id":1}],"title":"Generated fixture"}'
        self.assertEqual(
            image_led_results_module._generated_json(raw),
            {"slides": [{"id": 1}], "title": "Generated fixture"},
        )

    def test_unassessed_result_cannot_self_promote_with_boolean(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = {'status': 'passed', 'approved': True,
                       'pptx_path': str(Path(folder) / 'missing.pptx'),
                       'pptx_sha256': 'a' * 64}
            before = list(Path(folder).rglob('*'))
            with self.assertRaises(ContractValidationError):
                preflight_output(payload, {}, Path(folder))
            self.assertEqual(list(Path(folder).rglob('*')), before)


@unittest.skipUnless(NODE.exists() and (MODULES / '@oai/artifact-tool').exists(), 'bundled renderer runtime unavailable')
class ImageLedByteResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='image-led-result-')
        cls.root = Path(cls.directory.name).resolve()
        cls.kernel, cls.task, cls.handoff, cls.output = render_runtime_fixture(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_native_output_has_exact_object_and_file_identity(self):
        with patch.object(
            image_led_results_module,
            "_generated_json",
            wraps=image_led_results_module._generated_json,
        ) as generated_json:
            self.assertEqual(
                image_led_results_module.preflight_output(
                    self.output, self.handoff, self.root
                ),
                self.output,
            )
        self.assertEqual(generated_json.call_count, 2)
        self.assertEqual(self.output['status'], 'engineering-output-unassessed')

    def test_each_generated_proto_file_rejects_duplicate_properties(self):
        for filename in ('authoring.proto.json', 'reimport.proto.json'):
            with self.subTest(filename=filename):
                path = Path(self.output['files'][filename]['path'])
                original = path.read_bytes()
                try:
                    path.write_bytes(b'{"slides": [], "slides": []}')
                    forged = deepcopy(self.output)
                    forged['files'][filename]['sha256'] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    with self.assertRaises(ContractValidationError):
                        preflight_output(forged, self.handoff, self.root)
                finally:
                    path.write_bytes(original)

    def test_theme_referenced_shadow_is_capability_gap_before_output(self):
        with tempfile.TemporaryDirectory(prefix='image-led-shadow-gap-') as folder:
            root = Path(folder).resolve()
            runner = """
import fs from 'node:fs';
import {render} from './scripts/image-led-native.mjs';
import {syntheticHandoff} from './tests/fixtures/image-led-synthetic.mjs';
const h=syntheticHandoff(process.argv[1], 'B');
for(const key of ['regions','objects']) h.slides[0][key].find(x=>x.region_id==='background').appearance.shadow=
  {color:'#000000',opacity:0.3,blur:4,offset_x:2,offset_y:3};
let sdkLoaded=false,message='';
try {await render(h,{projectRoot:process.argv[1],nodeModulesRoot:process.argv[2],pythonExecutable:process.argv[3],
  loadSdk:async()=>{sdkLoaded=true;throw Error('Renderer reached SDK before capability rejection');}});}catch(error){message=error.message;}
console.log(JSON.stringify({message,sdkLoaded,outputExists:fs.existsSync(h.output_paths.directory)}));
"""
            completed = subprocess.run([str(NODE), '--input-type=module', '-e', runner, str(root), str(MODULES), str(PYTHON)],
                text=True, capture_output=True, cwd=CODE_ROOT, timeout=90)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertIn('IMAGE_LED_CAPABILITY_GAP:', result['message'])
            self.assertIn('shadow', result['message'])
            self.assertFalse(result['sdkLoaded'])
            self.assertFalse(result['outputExists'])
            self.assertEqual(list(root.iterdir()), [])

    def test_renderer_preserves_mixed_table_connector_image_and_gradient(self):
        with tempfile.TemporaryDirectory(prefix='image-led-result-mixed-') as folder:
            root = Path(folder).resolve()
            runner = """
import {render} from './scripts/image-led-native.mjs';
import {syntheticHandoff,digest} from './tests/fixtures/image-led-synthetic.mjs';
const h=syntheticHandoff(process.argv[1], 'B'),s=h.slides[0];
const style=text=>({runs:[{text,fontFamily:'Arial',fontSize:24,color:'#183A52',bold:false,italic:false}],
  alignment:'left',verticalAlignment:'middle',insets:[3,4,5,6],lineSpacing:1.2});
const items=['Metric','42'].map((text,column)=>({item_id:'table-cell-'+column,kind:'table-cell',table_id:'metrics',row:0,column,text}));
const table={region_id:'metrics',kind:'table',bbox:[100,540,500,60],z_order:10,
  content:{items},material_binding:null,appearance:{row_heights:[60],column_widths:[220,280],
    cells:items.map(item=>({row:0,column:item.column,item_id:item.item_id,style:style(item.text)}))}};
const connector={region_id:'relation',kind:'connector',bbox:[520,130,10,110],z_order:11,
  content:{items:[{item_id:'relation',kind:'relation',text:'Title supports body',from_item_id:'title-0',to_item_id:'body-0',direction:'forward'}]},
  material_binding:null,appearance:{from_region_id:'title-0',to_region_id:'body-0',start:[530,130],end:[520,240],
    line:{color:'#183A52',width:2,dash:'solid'},arrow:'forward',meaning:'Title supports body'}};
for(const region of [table,connector]){s.regions.push(region);s.objects.push({...structuredClone(region),object_id:'o-'+region.region_id,render_mode:'native'});}
const canonical=v=>JSON.stringify(v&&typeof v==='object'?Array.isArray(v)?v.map(x=>JSON.parse(canonical(x))):
  Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(canonical(v[k]))])):v);
s.target_binding.selected_copy_sha256=digest(canonical({items:s.regions.flatMap(r=>r.content.items)}));
await render(h,{projectRoot:process.argv[1],nodeModulesRoot:process.argv[2],pythonExecutable:process.argv[3]});
"""
            completed = subprocess.run([str(NODE), '--input-type=module', '-e', runner, str(root), str(MODULES), str(PYTHON)],
                text=True, capture_output=True, cwd=CODE_ROOT, timeout=90)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            files = list(root.glob('*/result.json'))
            self.assertEqual(len(files), 1)
            output = json.loads(files[0].read_text())
            handoff = json.loads((files[0].parent / 'handoff.json').read_text())
            self.assertEqual(preflight_output(output, handoff, root), output)
            # Native shapes and bitmap materials must retain stable explicit names,
            # even though the SDK changes numeric ids during PPTX export/import.
            self.assertEqual({r['kind'] for r in output['mapping']}, {'text', 'shape', 'image', 'table', 'connector'})
            # Inspect exported standard OOXML, not the author's schema or proto.
            from xml.etree import ElementTree as ET
            from ai_ppt_studio.application.image_led_ooxml import NS
            path = Path(output['pptx_path']); original = path.read_bytes()
            with ZipFile(BytesIO(original)) as package:
                members = {name: package.read(name) for name in package.namelist()}
            slide = ET.fromstring(members['ppt/slides/slide1.xml'])
            table = slide.find('.//a:tbl', NS)
            self.assertIsNotNone(table)
            self.assertEqual([node.text for node in table.findall('.//a:t', NS)], ['Metric', '42'])
            for cell in table.findall('a:tr/a:tc/a:tcPr', NS):
                self.assertEqual([int(cell.get(k)) / 9525 for k in ['marT','marR','marB','marL']], [3,4,5,6])
                self.assertEqual(cell.get('anchor'), 'ctr')
            self.assertIsNotNone(slide.find('.//p:cxnSp', NS))
            mutations = {'table-text': 'native visible text differs', 'table-margin': 'native object geometry changed',
                         'connector-endpoint': 'native relation endpoints changed', 'connector-site': 'native relation connection site changed',
                         'connector-arrow': 'native relation arrow changed', 'connector-reflection': 'native relation geometry changed'}
            for mutation, reason in mutations.items():
                with self.subTest(mutation=mutation):
                    try:
                        slide = ET.fromstring(members['ppt/slides/slide1.xml'])
                        if mutation == 'table-text':
                            slide.find('.//a:tbl/a:tr/a:tc/a:txBody/a:p/a:r/a:t', NS).text = 'Invented KPI'
                        elif mutation == 'table-margin':
                            slide.find('.//a:tbl/a:tr/a:tc/a:tcPr', NS).set('marL', '0')
                        elif mutation == 'connector-endpoint':
                            slide.find('.//p:cxnSp/p:nvCxnSpPr/p:cNvCxnSpPr/a:endCxn', NS).set('id', '98765')
                        elif mutation == 'connector-site':
                            slide.find('.//p:cxnSp/p:nvCxnSpPr/p:cNvCxnSpPr/a:endCxn', NS).set('idx', '0')
                        elif mutation == 'connector-arrow':
                            slide.find('.//p:cxnSp/p:spPr/a:ln/a:tailEnd', NS).set('type', 'none')
                        else:
                            slide.find('.//p:cxnSp/p:spPr/a:xfrm', NS).set('flipH', '0')
                        buffer = BytesIO()
                        with ZipFile(buffer, 'w') as rewritten:
                            for name, raw in members.items():
                                rewritten.writestr(name, ET.tostring(slide) if name == 'ppt/slides/slide1.xml' else raw)
                        changed = buffer.getvalue(); path.write_bytes(changed)
                        payload = deepcopy(output); payload['pptx_sha256'] = hashlib.sha256(changed).hexdigest()
                        with self.assertRaisesRegex(ContractValidationError, reason):
                            preflight_output(payload, handoff, root)
                    finally:
                        path.write_bytes(original)

    def test_wrong_current_page_plan_and_asserted_success_are_rejected_read_only(self):
        from tests.test_image2_input_boundary import tree_snapshot
        for key, value in (('selection_ref', 'artifact://image-led-selection/' + '0' * 64),
                           ('plan_ref', 'artifact://visual-compilation-plan/' + '0' * 64),
                           ('visual_fidelity', 'passed'), ('user_acceptance', True)):
            payload = deepcopy(self.output); payload[key] = value
            before = tree_snapshot(self.root)
            with self.subTest(key=key), self.assertRaises(ContractValidationError):
                preflight_output(payload, self.handoff, self.root)
            self.assertEqual(tree_snapshot(self.root), before)

    def test_mutated_file_bytes_and_symlinks_never_pass_self_reported_hash(self):
        from tests.test_image2_input_boundary import tree_snapshot
        for filename in ('pptx_path', 'render', 'mapping', 'comparison'):
            path = Path(self.output['pptx_path'] if filename == 'pptx_path' else
                        self.output['renders'][0]['path'] if filename == 'render' else
                        self.output['files']['mapping.json']['path'] if filename == 'mapping' else
                        self.output['comparisons'][0]['overlay']['path'])
            original = path.read_bytes()
            try:
                path.write_bytes(original + b'changed')
                before = tree_snapshot(self.root)
                with self.subTest(filename=filename), self.assertRaises(ContractValidationError):
                    preflight_output(self.output, self.handoff, self.root)
                self.assertEqual(tree_snapshot(self.root), before)
            finally:
                path.write_bytes(original)
        path = Path(self.output['renders'][0]['path']); backup = path.with_suffix('.saved')
        path.rename(backup); path.symlink_to(backup)
        try:
            with self.assertRaises(ContractValidationError):
                preflight_output(self.output, self.handoff, self.root)
        finally:
            path.unlink(); backup.rename(path)

    def test_rehashed_pptx_cannot_change_copy_geometry_or_object_identity(self):
        path = Path(self.output['pptx_path']); original = path.read_bytes()
        with ZipFile(BytesIO(original)) as package:
            members = {name: package.read(name) for name in package.namelist()}
        native_xml = members['ppt/slides/slide1.xml']
        from xml.sax.saxutils import escape
        title = escape(self.handoff['slides'][0]['objects'][0]['content']['items'][0]['text']).encode()
        for before, after in ((b'x="228600"', b'x="238125"'),
                              (title, b'Unauthorized replacement text'),
                              (b'name="object-title"', b'name="wrong-object"')):
            # Select actual named object data; fixture page ids are deliberately arbitrary.
            if before not in native_xml:
                if b'name="' in before:
                    import re
                    match = re.search(br'name="([^"]+)"', native_xml)
                    matches = list(re.finditer(br'name="([^"]+)"', native_xml))
                    self.assertTrue(matches)
                    before, after = matches[0].group(), b'name="wrong-object"'
                else:
                    self.fail('synthetic fixture geometry unexpectedly changed')
            try:
                stream = BytesIO()
                with ZipFile(stream, 'w') as rewritten:
                    for name, raw in members.items():
                        rewritten.writestr(name, raw.replace(before, after, 1) if name == 'ppt/slides/slide1.xml' else raw)
                changed = stream.getvalue(); path.write_bytes(changed)
                payload = deepcopy(self.output); payload['pptx_sha256'] = hashlib.sha256(changed).hexdigest()
                with self.assertRaises(ContractValidationError):
                    preflight_output(payload, self.handoff, self.root)
            finally:
                path.write_bytes(original)

    def test_rehashed_text_carrier_fill_cannot_reuse_old_render_evidence(self):
        from xml.etree import ElementTree as ET
        from ai_ppt_studio.application.image_led_ooxml import A, NS
        from tests.test_image2_input_boundary import tree_snapshot
        path = Path(self.output['pptx_path']); original = path.read_bytes()
        try:
            with ZipFile(BytesIO(original)) as package:
                members = {name: package.read(name) for name in package.namelist()}
            root = ET.fromstring(members['ppt/slides/slide1.xml'])
            props = root.find('p:cSld/p:spTree/p:sp/p:spPr', NS)
            props.remove(props.find('a:noFill', NS))
            red_fill = ET.SubElement(props, '{' + A + '}solidFill')
            ET.SubElement(red_fill, '{' + A + '}srgbClr', {'val': 'FF0000'})
            members['ppt/slides/slide1.xml'] = ET.tostring(root)
            buffer = BytesIO()
            with ZipFile(buffer, 'w') as rewritten:
                for name, raw in members.items():
                    rewritten.writestr(name, raw)
            changed = buffer.getvalue(); path.write_bytes(changed)
            payload = deepcopy(self.output); payload['pptx_sha256'] = hashlib.sha256(changed).hexdigest()
            before = tree_snapshot(self.root)
            with self.assertRaises(ContractValidationError):
                preflight_output(payload, self.handoff, self.root)
            self.assertEqual(tree_snapshot(self.root), before)
        finally:
            path.write_bytes(original)

    def test_rehashed_render_and_comparisons_must_be_derived_from_current_bytes(self):
        from PIL import Image
        for kind in ('render', 'overlay', 'region_differences'):
            with self.subTest(kind=kind):
                output = deepcopy(self.output)
                entry = output['renders'][0] if kind == 'render' else output['comparisons'][0][kind]
                path = Path(entry['path']); original = path.read_bytes(); restored = {path: original}
                try:
                    if kind == 'region_differences':
                        data = json.loads(original)
                        data['regions'][0]['mean_absolute_error'] = 255 - data['regions'][0]['mean_absolute_error']
                        changed = json.dumps(data).encode()
                    else:
                        image = Image.open(BytesIO(original)).convert('RGB')
                        image.putpixel((0, 0), (255, 0, 1))
                        raw = BytesIO(); image.save(raw, format='PNG'); changed = raw.getvalue()
                    path.write_bytes(changed); entry['sha256'] = hashlib.sha256(changed).hexdigest()
                    if kind == 'render':
                        differences = output['comparisons'][0]['region_differences']
                        diff_path = Path(differences['path']); restored[diff_path] = diff_path.read_bytes()
                        value = json.loads(restored[diff_path]); value['render_sha256'] = entry['sha256']
                        raw = json.dumps(value).encode(); diff_path.write_bytes(raw)
                        differences['sha256'] = hashlib.sha256(raw).hexdigest()
                    with self.assertRaises(ContractValidationError):
                        preflight_output(output, self.handoff, self.root)
                finally:
                    for filename, raw in restored.items():
                        filename.write_bytes(raw)

    def test_text_carrier_visual_properties_are_closed_beyond_the_reported_fill(self):
        from xml.etree import ElementTree as ET
        from ai_ppt_studio.application.image_led_ooxml import A, NS
        path = Path(self.output['pptx_path']); original = path.read_bytes()
        with ZipFile(BytesIO(original)) as package:
            members = {name: package.read(name) for name in package.namelist()}
        for mutation in ('geometry', 'effects', 'body-rotation', 'hidden-object', 'line'):
            with self.subTest(mutation=mutation):
                try:
                    root = ET.fromstring(members['ppt/slides/slide1.xml'])
                    obj = root.find('p:cSld/p:spTree/p:sp', NS)
                    props = obj.find('p:spPr', NS)
                    if mutation == 'geometry':
                        props.find('a:prstGeom', NS).set('prst', 'ellipse')
                    elif mutation == 'effects':
                        effects = ET.SubElement(props, '{' + A + '}effectLst')
                        ET.SubElement(effects, '{' + A + '}glow', {'rad': '95250'})
                    elif mutation == 'body-rotation':
                        obj.find('p:txBody/a:bodyPr', NS).set('rot', '5400000')
                    elif mutation == 'hidden-object':
                        obj.find('p:nvSpPr/p:cNvPr', NS).set('hidden', '1')
                    else:
                        props.find('a:ln', NS).set('w', '95250')
                    buffer = BytesIO()
                    with ZipFile(buffer, 'w') as rewritten:
                        for name, raw in members.items():
                            rewritten.writestr(name, ET.tostring(root) if name == 'ppt/slides/slide1.xml' else raw)
                    changed = buffer.getvalue(); path.write_bytes(changed)
                    output = deepcopy(self.output); output['pptx_sha256'] = hashlib.sha256(changed).hexdigest()
                    with self.assertRaises(ContractValidationError):
                        preflight_output(output, self.handoff, self.root)
                finally:
                    path.write_bytes(original)

    def test_runtime_result_needs_completed_producer_and_independent_four_dimensions(self):
        from ai_ppt_studio.application.project_service import ProjectCommandService
        from ai_ppt_studio.application.image_led_results import ImageLedResultService, DIMENSIONS
        from tests.test_image2_input_boundary import tree_snapshot
        kernel = self.kernel; service = ImageLedResultService(kernel); commands = ProjectCommandService(kernel)
        payload = {'artifact_type': 'image-led-build-result', 'project_id': kernel.project_id, 'output': deepcopy(self.output)}
        before = tree_snapshot(self.root)
        with self.assertRaises(ContractValidationError):
            service.register_build_result('public-forgery', kernel.load().revision, payload)
        self.assertEqual(tree_snapshot(self.root), before)
        result_ref, _ = commands.commit_noncontent_agent_result(command_id='native-result',
            expected_revision=kernel.load().revision, task_id=self.task['task_id'],
            request_kind='visual-contract', raw_request_payload=payload)
        self.assertEqual(service.current_result(result_ref, require_review=False)['output'], self.output)
        with self.assertRaises(Exception):
            service.current_result(result_ref)
        self.assertNotIn('visual/anchors', kernel.load().artifact_heads)
        self.assertIn('visual/review/G1/aesthetic', kernel.load().artifact_heads)
        _, task, _ = commands.request_agent_action('result-review', kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[result_ref], instructions='Synthetic review only')
        review = {'artifact_type': 'image-led-result-review', 'project_id': kernel.project_id,
            'target_ref': result_ref, 'reviewer_kind': 'engineering', 'reviewer_role': 'visual-engineering-reviewer',
            'checks': [{'criterion': kind, 'result': 'passed', 'detail': 'Synthetic assertion, no real visual acceptance'} for kind in sorted(DIMENSIONS)]}
        before = tree_snapshot(self.root)
        with self.assertRaises(ContractValidationError):
            service.register_review('public-review-forgery', kernel.load().revision, review)
        self.assertEqual(tree_snapshot(self.root), before)
        incomplete = deepcopy(review); incomplete['checks'].pop()
        with self.assertRaises(ContractValidationError):
            commands.commit_noncontent_agent_result(command_id='incomplete-review', expected_revision=kernel.load().revision,
                task_id=task['task_id'], request_kind='visual-contract', raw_request_payload=incomplete)
        self.assertEqual(tree_snapshot(self.root), before)
        unassessed = deepcopy(review); unassessed['checks'][0]['result'] = 'not-established'
        unassessed_ref, _ = commands.commit_noncontent_agent_result(command_id='unassessed-review',
            expected_revision=kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract', raw_request_payload=unassessed)
        with self.assertRaises(ContractValidationError):
            service.current_result(result_ref)
        _, task, _ = commands.request_agent_action('result-review-revised', kernel.load().revision,
            action_type='review-visual-engineering', target_refs=[result_ref], instructions='Synthetic revised assessment only')
        review_ref, _ = commands.commit_noncontent_agent_result(command_id='native-reviewed',
            expected_revision=kernel.load().revision, task_id=task['task_id'], request_kind='visual-contract', raw_request_payload=review)
        self.assertEqual(service.current_result(result_ref, review_ref=review_ref)['output'], self.output)
        self.assertNotIn('visual/anchors', kernel.load().artifact_heads)
        self.assertNotEqual(kernel.load().gate_status['G3'], 'passed')
        with self.assertRaises(ContractValidationError):
            service.current_result(result_ref, review_ref=unassessed_ref)
        path = Path(self.output['renders'][0]['path']); original = path.read_bytes()
        try:
            path.write_bytes(b'broken render after review')
            with self.assertRaises(ContractValidationError):
                service.current_result(result_ref)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
