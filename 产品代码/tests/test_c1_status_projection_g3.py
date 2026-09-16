import unittest
from unittest.mock import patch
from types import SimpleNamespace
from ai_ppt_studio.application.project_status_projection import ProjectStatusProjectionService
class G3StatusProjectionTests(unittest.TestCase):
 def test_g3_passed_does_not_leave_old_open_visual_session_as_user_todo(self):
  state=SimpleNamespace(revision=142,gate_status={'G0':'passed','G3':'passed'},review_session_ref=lambda kind:'artifact://review-session/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' if kind=='visual-professional' else '',artifact_heads={})
  kernel=SimpleNamespace(load=lambda:state,artifacts=SimpleNamespace(resolve=lambda ref:{'payload':{'review_type':'visual-professional','host_open_status':'opened','host_notification_status':'not-requested','ai_receipt_status':'pending','status':'opened','open_policy':'foreground-if-waiting'}}))
  with patch('ai_ppt_studio.application.project_status_projection.validate_review_session',side_effect=lambda payload, trusted_receipts:payload):
   result=ProjectStatusProjectionService(kernel).project()
  self.assertEqual(result['object_type'],'runtime-task');self.assertNotEqual(result.get('next_action'),'完成视觉审核')
if __name__=='__main__':unittest.main()
