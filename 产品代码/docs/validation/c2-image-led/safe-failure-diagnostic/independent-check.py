import hashlib,json,subprocess,sys,unittest
from copy import deepcopy
from pathlib import Path
from ai_ppt_studio.adapters.image2_diagnostics import (diagnostic,encode_failure,parse_failure,validate_diagnostic,CommandFailure,CommandContractFailure,command_failure,error_category)
ROOT=Path('/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码')

class IndependentChecks(unittest.TestCase):
    def test_stage_matrix_and_rejected_state_combinations(self):
        matrix={'input':['invalid-input'],'compile':['compile-failed'],'credential-helper':['helper-failed','helper-timeout'],'http-open':['http-error','tls-error','connection-error','timeout','unknown-failure'],'response-read':['response-read-failed','timeout'],'provider-decode':['provider-decode-failed'],'wrapper-receipt':['wrapper-receipt-failed'],'adapter-receipt':['adapter-receipt-invalid'],'image-decode':['image-decode-failed'],'subprocess':['subprocess-failed']}
        for stage,reasons in matrix.items():
            for reason in reasons:
                value=diagnostic(stage,reason,status=403 if reason=='http-error' else None)
                for state,attempted in [('before-send',False),('send-attempted',True),('response-received',True),('not-established',None)]:
                    wrong={**value,'transport_state':state,'http_attempted':attempted}
                    if wrong!=value:
                        with self.assertRaises(ValueError):validate_diagnostic(wrong)
                for attempted in [0,1,{},[],"true"]:
                    with self.assertRaises(ValueError):validate_diagnostic({**value,'http_attempted':attempted})
    def test_hash_raw_byte_binding_size_and_nested_duplicates(self):
        raw=b'{ "synthetic" : "a" }\n';value=diagnostic('input','invalid-input');encoded=encode_failure(raw,value)
        self.assertEqual(parse_failure(encoded,raw,-15)['subprocess_exit_code'],-15)
        with self.assertRaises(ValueError):parse_failure(encoded,b'{"synthetic":"a"}',1)
        self.assertEqual(len(encoded+b' '*(2048-len(encoded))),2048)
        parse_failure(encoded+b' '*(2048-len(encoded)),raw,1)
        for bad in [encoded+b' '*(2049-len(encoded)),encoded.replace(b'"stage":',b'"stage":"compile","stage":'),encoded.replace(b'"request_sha256":',b'"request_sha256":"bad","request_sha256":')]:
            with self.assertRaises(ValueError):parse_failure(bad,raw,1)
        for code in [0,True,False,1.0,'1',None]:
            with self.assertRaises(ValueError):parse_failure(encoded,raw,code)
    def test_no_self_reported_exit_or_local_wrapper_stage(self):
        raw=b'synthetic';valid=diagnostic('http-open','http-error',status=503)
        encoded=encode_failure(raw,valid)
        for status in [True,False,99,600,200.0,'200']:
            envelope=json.loads(encoded);envelope['failure_diagnostic']['http_status']=status
            with self.assertRaises(ValueError):parse_failure(json.dumps(envelope).encode(),raw,1)
        for code in [0,-9,True,'1']:
            envelope=json.loads(encoded);envelope['failure_diagnostic']['subprocess_exit_code']=code
            with self.assertRaises(ValueError):parse_failure(json.dumps(envelope).encode(),raw,1)
        for stage,reason in [('subprocess','subprocess-failed'),('adapter-receipt','adapter-receipt-invalid'),('image-decode','image-decode-failed')]:
            envelope=json.loads(encoded);envelope['failure_diagnostic']=diagnostic(stage,reason)
            with self.assertRaises(ValueError):parse_failure(json.dumps(envelope).encode(),raw,1)
    def test_exact_type_carrier_and_content_free_error_category(self):
        class Evil(RuntimeError):
            @property
            def failure_diagnostic(self):raise AssertionError('MUST-NOT-READ-SYNTHETIC-SECRET')
        self.assertIsNone(command_failure(Evil('SYNTHETIC-SECRET')))
        self.assertEqual(error_category(type('SYNTHETIC-SECRET',(RuntimeError,),{})()),'Exception')
        class Subclass(CommandFailure):pass
        self.assertIsNone(command_failure(Subclass(diagnostic('input','invalid-input'))))
        error=CommandFailure(diagnostic('input','invalid-input'));error.failure_diagnostic['reason']='SYNTHETIC-SECRET'
        self.assertIsNone(command_failure(error))
        self.assertNotIn('SYNTHETIC-SECRET',str(error))
    def test_fresh_interpreter_actual_pipe_invalid_utf8_and_raw_json(self):
        for raw in [b'\xffSYNTHETIC-SECRET',b'{ "invalid" : true }\n',b'[{']:
            result=subprocess.run([sys.executable,str(ROOT/'src/ai_ppt_studio/adapters/image2_crs.py')],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C','PYTHONDONTWRITEBYTECODE':'1'},cwd='/private/tmp',check=False)
            self.assertEqual(result.returncode,1)
            diag=parse_failure(result.stdout,raw,result.returncode)
            self.assertIn(diag['stage'],['input','compile'])
            self.assertEqual(diag['transport_state'],'before-send')
            self.assertEqual(diag['http_attempted'],False)
            self.assertNotIn(b'SYNTHETIC-SECRET',result.stdout+result.stderr)
            self.assertEqual(result.stderr,b'IMAGE2_CRS_SAFE_FAILURE\n')

if __name__=='__main__':unittest.main(verbosity=2)
