"""B restoration check: synthetic preflight only, not a build/AC06/host proof."""
import tempfile
import unittest
from pathlib import Path
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError
from tests.test_image_led_runtime import g1_fixture
from tests.test_image2_input_boundary import tree_snapshot

class RecoveredAnchorPreflightTests(unittest.TestCase):
    def fixture(self,root,wrong_plan=False):
        kernel,_=g1_fixture(root)
        plan=kernel.load().artifact_heads['visual/compilation-plan']
        state=kernel.commit(command_id='synthetic-preflight-result',expected_revision=kernel.load().revision,
            event_type='test.fixture',artifact_updates={'visual/image-led/build-result':('image-led-build-result',{'output':{'plan_ref':('artifact://visual-compilation-plan/'+'0'*64) if wrong_plan else plan}})})
        result=state.artifact_heads['visual/image-led/build-result']
        slot='visual/image-led/result-review/'+result.rsplit('/',1)[1]
        state=kernel.commit(command_id='synthetic-preflight-review',expected_revision=state.revision,
            event_type='test.fixture',artifact_updates={slot:('image-led-result-review',{'target_ref':result,'test_only':True})})
        service=ProjectCommandService(kernel)
        _,task,_=service.request_agent_action('synthetic-promote-task',state.revision,action_type='build-native-first',target_refs=[plan],instructions='Synthetic preflight only')
        return kernel,service,task,{'artifact_type':'image-led-anchor-set','build_result_ref':result,'four_dimension_review_ref':state.artifact_heads[slot]}

    def test_exact_current_result_review_and_plan_are_accepted_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            k,s,t,p=self.fixture(Path(folder));before=tree_snapshot(Path(folder))
            try: got=s.preflight_noncontent_agent_result(task_id=t['task_id'],request_kind='native-anchor-set',payload=p,expected_revision=k.load().revision)
            except ContractValidationError as error:self.fail('Recovered exact-current anchor intake should pass preflight: '+str(error))
            self.assertEqual(got['task_id'],t['task_id']);self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_wrong_result_and_review_heads_are_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            k,s,t,p=self.fixture(Path(folder))
            for field,kind in [('build_result_ref','image-led-build-result'),('four_dimension_review_ref','image-led-result-review')]:
                with self.subTest(field=field):
                    before=tree_snapshot(Path(folder))
                    with self.assertRaises(ContractValidationError):s.preflight_noncontent_agent_result(task_id=t['task_id'],request_kind='native-anchor-set',payload={**p,field:'artifact://'+kind+'/'+'0'*64},expected_revision=k.load().revision)
                    self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_current_result_bound_to_wrong_plan_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            k,s,t,p=self.fixture(Path(folder),wrong_plan=True);before=tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):s.preflight_noncontent_agent_result(task_id=t['task_id'],request_kind='native-anchor-set',payload=p,expected_revision=k.load().revision)
            self.assertEqual(tree_snapshot(Path(folder)),before)

    def test_restored_route_does_not_remove_current_cancellation(self):
        with tempfile.TemporaryDirectory() as folder:
            k,s,t,_=self.fixture(Path(folder));old=k.load()
            after=s.cancel_unstarted_native_task('cancel-fixture',old.revision,task_id=t['task_id'],reason='B synthetic preflight complete')
            self.assertEqual(after.gate_status,old.gate_status)
            self.assertEqual(after.artifact_heads['visual/image-led/build-result'],old.artifact_heads['visual/image-led/build-result'])
            self.assertNotIn('agent/task/active',after.artifact_heads)

if __name__=='__main__':unittest.main(verbosity=2)
