from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v22_experience_fixtures import experience_item


class V22ExperienceContextTests(unittest.TestCase):
    def test_content_context_injects_only_matching_top_n_exact_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="project-context")
            service = ExperienceService(kernel)
            first_ref, _, state = service.absorb_same_type(
                command_id="absorb-first",
                expected_revision=0,
                payload=experience_item(),
            )
            unrelated = experience_item(
                experience_id="exp-unrelated",
                type_signature="presales:finance:decision",
            )
            _, _, state = service.absorb_same_type(
                command_id="absorb-unrelated",
                expected_revision=state.revision,
                payload=unrelated,
            )

            pack = ContextCompiler(kernel).compile_role_task(
                role_id="presales-solution-chief",
                task_type="build-presales-evidence-book",
                project_revision=state.revision,
                target_refs=[],
                instructions="只使用当前证据构建事实账本。",
                experience_type_signature="presales:transport:decision",
                experience_applicability={"conditions": ["阅读优先"]},
                experience_limit=1,
            )

            experience_slice = pack["layers"]["experience_slice"]
            self.assertEqual(experience_slice["status"], "available")
            self.assertEqual(experience_slice["domain"], "content")
            self.assertEqual(
                [item["experience_ref"] for item in experience_slice["items"]],
                [first_ref],
            )
            self.assertEqual(experience_slice["limit"], 1)


if __name__ == "__main__":
    unittest.main()
