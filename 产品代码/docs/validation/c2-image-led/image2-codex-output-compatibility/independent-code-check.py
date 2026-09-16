from pathlib import Path
import hashlib, json, sys, unittest, tempfile
from copy import deepcopy
from io import BytesIO, StringIO
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码')
OUT = Path('/private/tmp/c2-image2-compat-20260911')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from ai_ppt_studio.domains.visual.image_output import validate_provider_observation, output_fitness
from ai_ppt_studio.errors import ContractValidationError
from tests.test_image2_output_compatibility import ProviderCompatibilityTests, OutputRuntimeTests
from tests.test_image_led_v2_runtime import v2_selection_fixture
from tests.test_image2_input_boundary import tree_snapshot
from PIL import Image

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(): return {p.relative_to(ROOT / 'src').as_posix(): sha(p) for p in sorted((ROOT / 'src').rglob('*.py'))}
before = manifest()
test_before = sha(ROOT / 'tests/test_image2_output_compatibility.py')
counts = {'model_combinations': 0, 'malformed_observations': 0, 'geometry_cases': 0}

def observation(root, item, match):
    return {'version': 'image-led-provider-observation/v1', 'reported': {'response': root, 'image': item},
        'model_match': match, 'independent_engine_proof': False, 'response_sha256': 'a' * 64,
        'observed_at_utc': '2026-09-11T00:00:00+00:00'}

class IndependentBoundaryTests(unittest.TestCase):
    def test_model_origin_matrix_and_closed_observations(self):
        missing = object()
        labels = [missing, 'gpt-image-2', 'gpt-image-2-codex', 'gpt-image-2.5-sunburst',
                  'gpt-image-2.5-sunburst-2026-09-08', 'unknown', None, [], False]
        for requested in ('gpt-image-2', 'gpt-image-2.5-sunburst'):
            permitted = [requested] + (['gpt-image-2-codex'] if requested == 'gpt-image-2' else [])
            for root in labels:
                for item in labels:
                    reported = [x for x in [root, item] if x is not missing]
                    valid = all(isinstance(x, str) and x in permitted for x in reported)
                    match = 'compatible-image2-codex' if 'gpt-image-2-codex' in reported else ('exact' if reported else 'not-reported')
                    value = observation({} if root is missing else {'model': root}, {} if item is missing else {'model': item}, match)
                    if valid:
                        copied = validate_provider_observation(value, receiver='CRS', model=requested)
                        self.assertEqual(copied, value)
                        self.assertIsNot(copied, value)
                    else:
                        with self.assertRaises((ValueError, TypeError)):
                            validate_provider_observation(value, receiver='CRS', model=requested)
                    counts['model_combinations'] += 1
        base = observation({'model':'gpt-image-2-codex'}, {}, 'compatible-image2-codex')
        mutations = [lambda v:v.update(extra='x'), lambda v:v.pop('response_sha256'),
            lambda v:v.update(response_sha256='A'*64), lambda v:v.update(independent_engine_proof=0),
            lambda v:v.update(independent_engine_proof=True), lambda v:v.update(model_match='exact'),
            lambda v:v.update(observed_at_utc='2026-09-11T00:00:00+08:00'),
            lambda v:v.update(observed_at_utc='2026-02-30T00:00:00+00:00'),
            lambda v:v['reported'].update(other={}), lambda v:v['reported']['response'].update(secret='x'),
            lambda v:v['reported']['image'].update(size=1), lambda v:v['reported']['image'].update(quality='x\nvalue'),
            lambda v:v['reported']['image'].update(output_format='x'*65)]
        for mutate in mutations:
            value = deepcopy(base); mutate(value)
            with self.assertRaises((ValueError, TypeError)):
                validate_provider_observation(value, receiver='CRS', model='gpt-image-2')
            counts['malformed_observations'] += 1

    def test_geometry_formula_and_scoped_routes(self):
        widths = [1, 1279, 1280, 1281, 1366, 1672, 1920, 2048, 4096]
        for model in ['gpt-image-2', 'gpt-image-2.5-sunburst']:
            payload = {'payload_version':'image-led-image2-input/v2','receiver':'CRS','model':model}
            for width in widths:
                expected_height = round(width * 9 / 16)
                for height in sorted({max(1,expected_height+i) for i in range(-2,3)} | {719,720,721,941,942,1024}):
                    expected = 'eligible' if abs(16*height-9*width)<=8 and width>=1280 and height>=720 else 'needs-revision'
                    self.assertEqual(output_fitness(payload, [width,height])['status'],expected)
                    counts['geometry_cases'] += 1
            for dims in ([True,720],[1280,False],[1280.0,720],[1280,720,1],None,[0,720]):
                with self.assertRaises(ValueError): output_fitness(payload,dims)
        for payload in ({'receiver':'CRS','model':'gpt-image-2'},
            {'payload_version':'image-led-image2-input/v2','receiver':'Other','model':'gpt-image-2'},
            {'payload_version':'image-led-image2-input/v2','receiver':'CRS','model':'other'}):
            self.assertIsNone(output_fitness(payload,[1536,1024]))

    def test_historical_finalized_selection_rechecks_without_observation(self):
        stream=BytesIO(); Image.new('RGB',(1536,1024),'#203040').save(stream,format='PNG'); raw=stream.getvalue()
        class LegacyTransport:
            def generate(self, **kwargs): return {'response_id':'independent-old-result','image_bytes':raw}
        with tempfile.TemporaryDirectory(prefix='c2-independent-selection-') as folder:
            # Test-only simulation of a selection accepted before the new gate.
            # Production code and external state are not patched on disk.
            with patch('tests.test_image_led_v2_runtime.SyntheticTransport',LegacyTransport), patch(
                'ai_ppt_studio.application.image_led_selection.output_fitness',return_value=None):
                service, selection_ref = v2_selection_fixture(Path(folder))
            before_tree = tree_snapshot(Path(folder))
            with self.assertRaisesRegex(ContractValidationError,'OUTPUT_FITNESS'):
                service.current_selection(selection_ref)
            self.assertEqual(tree_snapshot(Path(folder)),before_tree)

suite=unittest.TestSuite()
for cls in [ProviderCompatibilityTests, OutputRuntimeTests, IndependentBoundaryTests]:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
log=StringIO()
run=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(OUT/'independent-offline-tests.log').write_text(log.getvalue())
after=manifest()
frozen={'status':'reviewed-source-snapshot','source_root':str(ROOT/'src'),'files':before,
    'production_python_count':len(before),'source_unchanged_during_independent_execution':after==before,
    'test_file':'tests/test_image2_output_compatibility.py','test_sha256_before':test_before,
    'test_sha256_after':sha(ROOT/'tests/test_image2_output_compatibility.py')}
(OUT/'independent-production-manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
summary={'status':'PASS' if run.wasSuccessful() and before==after else 'FAIL',
    'tests_run':run.testsRun,'failures':len(run.failures),'errors':len(run.errors),'independent_case_counts':counts,
    'production_manifest_sha256':sha(OUT/'independent-production-manifest.json'),
    'independent_log_sha256':sha(OUT/'independent-offline-tests.log'), 'checker_sha256':sha(Path(__file__)),
    'source_unchanged':before==after, 'real_http':'NotRun','actual_auth_helper':'NotRun','installation':'NotRun',
    'customer_runtime':'NotTouched','full_source_ui_suites':'NotRun',
    'ended_at':datetime.now(timezone.utc).isoformat()}
(OUT/'independent-code-checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
if summary['status']!='PASS': print(log.getvalue()); raise SystemExit(1)
