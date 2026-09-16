"""Preflight must expose a safe current-process capability without Runtime writes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_ppt_studio.adapters import image2_command
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel

WRAPPER = Path(image2_command.__file__).resolve().with_name('image2_crs.py')
KEYS = ('AI_PPT_IMAGE2_ADAPTER_COMMAND','AI_PPT_IMAGE2_RECEIVER','AI_PPT_IMAGE2_MODEL','AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST')
PROTOCOL = 'image-led-image2-preflight/v1'


def tree_snapshot(root):
    # Every directory and file, including lock files: no exclusions for a read.
    return {str(p.relative_to(root)): ('directory' if p.is_dir() else p.read_bytes())
            for p in root.rglob('*')}


def configured():
    return {KEYS[0]:json.dumps([sys.executable,str(WRAPPER)]), KEYS[1]:'CRS', KEYS[2]:'gpt-image-2', KEYS[3]:'[]'}


class Image2PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base/'runtime'/'projects'/'p1'
        ProjectKernel.initialize(self.project,project_id='p1')
        self.runtime = self.base/'runtime'
        self.env = self.enterContext(patch.dict(os.environ, {}, clear=True))

    def snapshot(self, **changes):
        return dispatch_v16({'operation':'get-project-snapshot','project_root':str(self.project),**changes})

    def preflight(self):
        result=self.snapshot(include_image2_preflight=True)
        self.assertIn('image2_preflight',result,'opt-in preflight is absent from the real Python snapshot handler')
        value=result['image2_preflight']
        self.assertEqual(set(value),{'configuration_presence','known_wrapper','protocol_probe','helper_executable','external_connection','wrapper_sha256','probe_nonce'})
        self.assertEqual(set(value['configuration_presence']),set(KEYS))
        self.assertTrue(all(type(v) is bool for v in value['configuration_presence'].values()))
        self.assertIs(type(value['known_wrapper']),bool)
        self.assertIn(value['protocol_probe'],('passed','unsupported','unavailable','failed'))
        self.assertIn(value['helper_executable'],(None,False,True))
        self.assertEqual(value['external_connection'],'not-tested')
        self.assertRegex(value['probe_nonce'],r'^[a-f0-9]{32}$')
        self.assertEqual(value['wrapper_sha256'],hashlib.sha256(WRAPPER.read_bytes()).hexdigest())
        return value

    def test_default_and_false_preserve_snapshot_without_loading_adapter(self):
        before=tree_snapshot(self.runtime)
        with patch.object(image2_command.subprocess,'run',side_effect=AssertionError('must not execute')) as run:
            default=self.snapshot()
            explicit=self.snapshot(include_image2_preflight=False)
        self.assertEqual(default,explicit)
        self.assertNotIn('image2_preflight',default)
        self.assertEqual(tree_snapshot(self.runtime),before)
        run.assert_not_called()

    def test_missing_configuration_has_false_presence_and_no_process(self):
        before=tree_snapshot(self.runtime)
        with patch.object(image2_command.subprocess,'run') as run:
            value=self.preflight()
        self.assertEqual(value['configuration_presence'],dict.fromkeys(KEYS,False))
        self.assertEqual(value['protocol_probe'],'unavailable')
        self.assertFalse(value['known_wrapper'])
        self.assertIsNone(value['helper_executable'])
        run.assert_not_called()
        self.assertEqual(tree_snapshot(self.runtime),before)

    def test_recognized_wrapper_runs_real_preflight_child_without_runtime_writes(self):
        os.environ.update(configured())
        before=tree_snapshot(self.runtime)
        value=self.preflight()
        self.assertEqual(value['configuration_presence'],dict.fromkeys(KEYS,True))
        self.assertTrue(value['known_wrapper'])
        self.assertEqual(value['protocol_probe'],'passed')
        self.assertIs(type(value['helper_executable']),bool)
        self.assertEqual(tree_snapshot(self.runtime),before)

    def test_exact_sunburst_command_runs_real_probe_without_runtime_writes(self):
        os.environ.update(configured())
        os.environ[KEYS[0]] = json.dumps([
            sys.executable, str(WRAPPER), '--model', 'gpt-image-2.5-sunburst'])
        os.environ[KEYS[2]] = 'gpt-image-2.5-sunburst'
        before = tree_snapshot(self.runtime)
        value = self.preflight()
        self.assertTrue(value['known_wrapper'])
        self.assertEqual(value['protocol_probe'], 'passed')
        self.assertEqual(value['external_connection'], 'not-tested')
        self.assertEqual(tree_snapshot(self.runtime), before)

    def test_unknown_and_counterfeit_basename_commands_are_never_executed(self):
        marker=self.base/'marker'
        counterfeit=self.base/'image2_crs.py'
        counterfeit.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
        for command in ([sys.executable,str(counterfeit)], [sys.executable,str(WRAPPER),'extra'],
                        ['python3',str(WRAPPER)], ['/bin/sh','-c','touch '+str(marker)]):
            os.environ.update(configured()); os.environ[KEYS[0]]=json.dumps(command)
            before=tree_snapshot(self.runtime)
            with patch.object(image2_command.subprocess,'run') as run:
                value=self.preflight()
            self.assertEqual(value['protocol_probe'],'unsupported')
            self.assertFalse(value['known_wrapper'])
            run.assert_not_called()
            self.assertFalse(marker.exists())
            self.assertEqual(tree_snapshot(self.runtime),before)

    def test_sunburst_exact_command_model_matrix_rejects_before_any_child(self):
        sun = 'gpt-image-2.5-sunburst'
        old = [sys.executable, str(WRAPPER)]
        new = [*old, '--model', sun]
        for command, model in ((old, sun), (new, 'gpt-image-2'),
                (old, 'gpt-image-2.5-flare'), ([*old, '--model', 'gpt-image-2.5-flare'], 'gpt-image-2.5-flare'),
                ([*old, '--model', 'gpt-image-2.5'], 'gpt-image-2.5'),
                ([*new, 'extra'], sun), ([*old, '--preflight', '--model', sun], sun),
                ([sys.executable, str(self.base / 'image2_crs.py'), '--model', sun], sun)):
            with self.subTest(command=command, model=model):
                os.environ.update(configured())
                os.environ.update({KEYS[0]: json.dumps(command), KEYS[2]: model})
                before = tree_snapshot(self.runtime)
                with patch.object(image2_command.subprocess, 'run') as run:
                    value = self.preflight()
                self.assertFalse(value['known_wrapper'])
                self.assertEqual(value['protocol_probe'], 'unsupported')
                run.assert_not_called()
                self.assertEqual(tree_snapshot(self.runtime), before)

    def test_sunburst_v1_v2_probes_bind_model_nonce_schema_and_adapter_identity(self):
        sun = 'gpt-image-2.5-sunburst'
        os.environ.update(configured())
        os.environ.update({KEYS[0]: json.dumps([sys.executable, str(WRAPPER), '--model', sun]), KEYS[2]: sun})
        before = tree_snapshot(self.runtime)
        for protocol in (None, 'image-led-image2-transport/v2'):
            def reply(command, **options):
                self.assertEqual(command, [sys.executable, str(WRAPPER), '--model', sun, '--preflight'])
                self.assertEqual(options['timeout'], 10)
                self.assertFalse(any(k.startswith('AI_PPT_') for k in options['env']))
                probe = json.loads(options['input'])
                probe.update(receiver='CRS', model=sun, helper_executable=False, external_connection='not-tested')
                return SimpleNamespace(returncode=0, stdout=json.dumps(probe).encode())
            for change in ({}, {'model': 'gpt-image-2'}, {'request_id': 'wrong'},
                           {'protocol': 'image-led-image2-preflight/v3'}, {'extra': True}, {'helper_executable': 1}):
                def altered(command, **options):
                    result = reply(command, **options)
                    value = json.loads(result.stdout); value.update(change)
                    result.stdout = json.dumps(value).encode(); return result
                with patch.object(image2_command.subprocess, 'run', side_effect=altered) as run:
                    result = image2_command.image2_preflight(generation_protocol=protocol)
                self.assertEqual(result['protocol_probe'], 'failed' if change else 'passed')
                run.assert_called_once()
        # Captured execution identity may not probe a different environment model.
        identity = ((sys.executable, str(WRAPPER)), 'CRS', 'gpt-image-2')
        with patch.object(image2_command.subprocess, 'run') as run:
            value = image2_command.image2_preflight(_expected_identity=identity)
        self.assertEqual(value['protocol_probe'], 'unsupported'); run.assert_not_called()
        self.assertEqual(tree_snapshot(self.runtime), before)

    def test_empty_or_malformed_is_explicitly_failed_and_never_echoes_values(self):
        for key,invalid in ((KEYS[0],''),(KEYS[0],'synthetic-secret'),(KEYS[0],'{}'),
                            (KEYS[1],''),(KEYS[2],''),(KEYS[3],'{broken'),(KEYS[3],'["AI_PPT_HOST_CONFIRMATION_SECRET"]')):
            os.environ.update(configured()); os.environ[key]=invalid
            with patch.object(image2_command.subprocess,'run') as run:
                value=self.preflight()
            self.assertEqual(value['configuration_presence'],dict.fromkeys(KEYS,True))
            self.assertEqual(value['protocol_probe'],'failed')
            self.assertNotIn('synthetic-secret',json.dumps(value))
            self.assertNotIn(str(WRAPPER),json.dumps(value))
            run.assert_not_called()

    def test_wrong_destination_cannot_probe(self):
        for key in (KEYS[1],KEYS[2]):
            os.environ.update(configured()); os.environ[key]='other-destination'
            with patch.object(image2_command.subprocess,'run') as run:
                value=self.preflight()
            self.assertEqual(value['protocol_probe'],'unsupported')
            self.assertFalse(value['known_wrapper'])
            run.assert_not_called()

    def test_protocol_nonce_exact_types_timeout_and_safe_environment(self):
        os.environ.update(configured())
        os.environ.update({'AI_PPT_HOST_CONFIRMATION_SECRET':'synthetic-confirmation-secret', 'OTHER_SECRET':'synthetic-provider-secret',
                           'PYTHONPATH':'/tmp/synthetic-untrusted-python','PYTHONHOME':'/tmp/synthetic-untrusted-home'})
        os.environ[KEYS[3]]='["OTHER_SECRET","PYTHONPATH","PYTHONHOME"]'
        before=tree_snapshot(self.runtime)
        calls=[]
        def reply(command,**kwargs):
            calls.append((command,kwargs))
            nonce=json.loads(kwargs['input'])['request_id']
            return SimpleNamespace(returncode=0, stdout=json.dumps({'protocol':PROTOCOL,'request_id':nonce,
                'receiver':'CRS','model':'gpt-image-2','helper_executable':False,'external_connection':'not-tested'}).encode())
        with patch.object(image2_command.subprocess,'run',side_effect=reply):
            value=self.preflight()
        self.assertEqual(value['protocol_probe'],'passed')
        self.assertFalse(value['helper_executable'])
        command,options=calls[0]
        self.assertEqual(command,[sys.executable,str(WRAPPER),'--preflight'])
        self.assertEqual(options['timeout'],10)
        self.assertEqual(options['stderr'],subprocess.DEVNULL)
        self.assertNotIn('AI_PPT_HOST_CONFIRMATION_SECRET',options['env'])
        self.assertNotIn('PYTHONPATH',options['env'])
        self.assertNotIn('PYTHONHOME',options['env'])
        self.assertNotIn('OTHER_SECRET',options['env'],'preflight does not need credential allowlist values')
        self.assertEqual(options['env']['PYTHONDONTWRITEBYTECODE'],'1')
        for mutate in (lambda r:r.update(protocol='wrong'),lambda r:r.update(request_id='other-nonce'),
                       lambda r:r.update(receiver='other'),lambda r:r.update(model='other'),
                       lambda r:r.update(helper_executable=1),lambda r:r.update(helper_executable='false'),
                       lambda r:r.update(external_connection='tested'),lambda r:r.update(extra='synthetic-secret')):
            def malformed(command,**kwargs):
                completed=reply(command,**kwargs); data=json.loads(completed.stdout); mutate(data)
                completed.stdout=json.dumps(data).encode(); return completed
            with patch.object(image2_command.subprocess,'run',side_effect=malformed):
                value=self.preflight()
            self.assertEqual(value['protocol_probe'],'failed')
            self.assertIsNone(value['helper_executable'])
            self.assertTrue(value['known_wrapper'])
        for effect in (subprocess.TimeoutExpired('safe',10,output=b'synthetic-secret'),OSError('synthetic-secret')):
            with patch.object(image2_command.subprocess,'run',side_effect=effect) as run:
                value=self.preflight()
            self.assertEqual(value['protocol_probe'],'failed')
            self.assertNotIn('synthetic-secret',json.dumps(value))
            run.assert_called_once()
        self.assertEqual(tree_snapshot(self.runtime),before)

    def test_non_boolean_snapshot_opt_in_rejected_without_process_or_writes(self):
        before=tree_snapshot(self.runtime)
        for value in (None,0,1,'true',[],{}):
            with patch.object(image2_command.subprocess,'run') as run:
                with self.assertRaises(ContractValidationError):
                    self.snapshot(include_image2_preflight=value)
            run.assert_not_called()
        self.assertEqual(tree_snapshot(self.runtime),before)

    def test_optional_allowlist_missing_does_not_block_a_known_local_probe(self):
        os.environ.update(configured())
        del os.environ[KEYS[3]]
        value = self.preflight()
        self.assertEqual(value['protocol_probe'], 'passed')
        self.assertFalse(value['configuration_presence'][KEYS[3]])

    def test_bad_probe_json_duplicate_keys_and_nonzero_exit_stay_safe(self):
        os.environ.update(configured())
        before = tree_snapshot(self.runtime)
        for completed in (SimpleNamespace(returncode=1, stdout=b'synthetic-secret'),
                          SimpleNamespace(returncode=0, stdout=b'{broken synthetic-secret'),
                          SimpleNamespace(returncode=0, stdout=b'[]'),
                          SimpleNamespace(returncode=0, stdout=b'{"protocol":"a","protocol":"b"}')):
            with patch.object(image2_command.subprocess, 'run', return_value=completed) as run:
                value = self.preflight()
            self.assertEqual(value['protocol_probe'], 'failed')
            self.assertIsNone(value['helper_executable'])
            self.assertNotIn('synthetic-secret', json.dumps(value))
            run.assert_called_once()
        self.assertEqual(tree_snapshot(self.runtime), before)

    def test_deeply_malformed_probe_and_configuration_return_safe_failure(self):
        os.environ.update(configured())
        malformed = ('[' * 4000 + ']' * 4000).encode()
        with patch.object(image2_command.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=malformed)):
            self.assertEqual(self.preflight()['protocol_probe'], 'failed')
        os.environ[KEYS[0]] = malformed.decode()
        with patch.object(image2_command.subprocess, 'run') as run:
            self.assertEqual(self.preflight()['protocol_probe'], 'failed')
        run.assert_not_called()
