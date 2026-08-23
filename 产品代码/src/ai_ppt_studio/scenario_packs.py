"""场景包注册表：不同业务场景下的角色路线和任务编排模板。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PresalesScenarioPack:
    """售前阅读优先汇报场景包。"""

    pack_id: str
    scene: str
    task_type: str
    display_name: str
    description: str
    production_roles: tuple[str, ...]
    review_roles: tuple[str, ...]
    editor_role: str
    risk_specialist_role_pattern: str
    g0_required: bool = True
    g1_required: bool = True
    g2_required: bool = True
    g3_required: bool = True
    g4_required: bool = True


_SCENARIO_PACKS: dict[tuple[str, str], PresalesScenarioPack] = {}


def _register(pack: PresalesScenarioPack) -> None:
    key = (pack.scene, pack.task_type)
    if key in _SCENARIO_PACKS:
        raise ValueError(f"Scenario pack already registered: {key}")
    _SCENARIO_PACKS[key] = pack


_register(PresalesScenarioPack(
    pack_id="presales-reading-first-v1",
    scene="presales",
    task_type="reading-first",
    display_name="售前阅读优先解决方案汇报",
    description="面向客户决策者的阅读优先售前方案汇报，内容先于视觉，G0/G3 需用户确认。",
    production_roles=(
        "presales-solution-chief",
        "deck-designer",
        "slide-visual-designer",
        "native-first-engineer",
        "image-asset-producer",
    ),
    review_roles=(
        "content-evidence-gate-reviewer",
        "content-presales-reading-gate-reviewer",
        "visual-aesthetic-reviewer",
        "visual-engineering-reviewer",
        "target-render-verifier",
    ),
    editor_role="content-presales-reading-gate-reviewer",
    risk_specialist_role_pattern="presales-risk-specialist/*",
))


class ScenarioPackRegistry:
    """场景包注册表。"""

    @classmethod
    def default(cls) -> "ScenarioPackRegistry":
        return cls()

    def resolve(self, *, scene: str, task_type: str) -> PresalesScenarioPack:
        key = (scene, task_type)
        if key not in _SCENARIO_PACKS:
            raise KeyError(f"Unknown scenario: {scene}/{task_type}")
        return _SCENARIO_PACKS[key]

    def all(self) -> list[PresalesScenarioPack]:
        return list(_SCENARIO_PACKS.values())


__all__ = ["PresalesScenarioPack", "ScenarioPackRegistry"]
