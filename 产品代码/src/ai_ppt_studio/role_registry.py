"""中文角色注册表与角色合同。

所有用户可见的正式角色名称使用中文；稳定英文 roleId 仅存在于内部代码和 Schema。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


RoleGroup = Literal[
    "content", "visual", "review", "feedback", "experience", "delivery"
]
RoleAuthority = Literal["producer", "reviewer", "support"]
ExperienceAccess = frozenset[str]


@dataclass(frozen=True)
class RoleContract:
    """单个正式角色的合同定义。"""

    role_id: str
    display_name: str
    description: str
    role_group: RoleGroup
    authority: RoleAuthority
    isolation_group: str
    tags: frozenset[str] = field(default_factory=frozenset)
    experience_access: frozenset[str] = field(
        default_factory=lambda: frozenset({"mechanisms", "preferences"})
    )
    can_release_gate: bool = False
    can_self_approve: bool = False


class ProductionRole:
    """生产角色类型标记，供类型提示使用。"""
    pass


class ReviewRole:
    """审查角色类型标记。"""
    pass


class SupportRole:
    """支持角色类型标记。"""
    pass


# 已批准的正式角色列表
# 按基线 v1.5 定义：内容 5 生产 + 5 审查 + 总编辑；视觉 4 生产 + 3 审查；
# 反馈治理 1 + 经验进化 2；交付 1。
_APPROVED_ROLES: list[RoleContract] = [
    # ===== 内容生产 =====
    RoleContract(
        role_id="presales-content-strategist",
        display_name="售前内容策略师",
        description="定义售前汇报的受众、决策目标、核心主张和约束。",
        role_group="content",
        authority="producer",
        isolation_group="content-producers",
        tags=frozenset({"presales", "strategy", "reading-first"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="claim-evidence-analyst",
        display_name="主张证据分析师",
        description="将策略拆解为事实、推断、建议、缺口、冲突五类主张并绑定证据。",
        role_group="content",
        authority="producer",
        isolation_group="content-producers",
        tags=frozenset({"presales", "evidence", "reading-first"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="deck-narrative-architect",
        display_name="整deck叙事架构师",
        description="构建整 deck 的论点地图、章节结构和过渡逻辑。",
        role_group="content",
        authority="producer",
        isolation_group="content-producers",
        tags=frozenset({"presales", "narrative", "reading-first"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="slide-copywriter",
        display_name="逐页文案师",
        description="产出每页的标题、目的、主张、可见内容和演讲备注。",
        role_group="content",
        authority="producer",
        isolation_group="content-producers",
        tags=frozenset({"presales", "copywriting", "reading-first"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="content-repair-specialist",
        display_name="内容返工专员",
        description="根据修复计划定向修改内容，保留未受影响的已通过版本。",
        role_group="content",
        authority="producer",
        isolation_group="content-producers",
        tags=frozenset({"presales", "repair", "reading-first"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    # ===== 内容审查 =====
    RoleContract(
        role_id="presales-content-reviewer",
        display_name="售前专业审查师",
        description="独立审查售前决策目标、方案边界、异议处理和行动指向。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-reviewers",
        tags=frozenset({"presales", "decision", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms"}),
    ),
    RoleContract(
        role_id="content-fact-checker",
        display_name="事实核查师",
        description="独立核查每一条主张的证据来源、真实性和时效性。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-reviewers",
        tags=frozenset({"presales", "fact-check", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms"}),
    ),
    RoleContract(
        role_id="argument-logic-reviewer",
        display_name="论证逻辑审查师",
        description="独立审查论点地图的逻辑链、跳跃和冲突。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-reviewers",
        tags=frozenset({"presales", "logic", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms"}),
    ),
    RoleContract(
        role_id="audience-decision-reviewer",
        display_name="受众决策审查师",
        description="站在客户决策者视角审查说服力、可读性和行动指向。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-reviewers",
        tags=frozenset({"presales", "audience", "independent"}),
        experience_access=frozenset({"anti-patterns", "preferences"}),
    ),
    RoleContract(
        role_id="reading-experience-reviewer",
        display_name="阅读体验审查师",
        description="审查每页信息密度、节奏、层级和可读性。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-reviewers",
        tags=frozenset({"presales", "reading-experience", "independent"}),
        experience_access=frozenset({"anti-patterns", "preferences"}),
    ),
    RoleContract(
        role_id="deck-coherence-editor",
        display_name="总编辑（独立）",
        description="汇总所有内容审查意见，形成唯一的修复计划或内容验收记录。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-editors",
        tags=frozenset({"presales", "editorial", "independent", "aggregation"}),
        experience_access=frozenset({"anti-patterns", "mechanisms", "preferences"}),
        can_release_gate=True,
    ),
    # ===== 视觉生产 =====
    RoleContract(
        role_id="deck-designer",
        display_name="整 deck 设计师",
        description="制定整 deck 设计系统：主题、构图、栅格、层级、字体、配色。",
        role_group="visual",
        authority="producer",
        isolation_group="visual-producers",
        tags=frozenset({"strict-B", "design-system", "presales"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="slide-visual-designer",
        display_name="逐页视觉设计师",
        description="根据设计系统产出每页的视觉合同和锚点页。",
        role_group="visual",
        authority="producer",
        isolation_group="visual-producers",
        tags=frozenset({"strict-B", "slide-visual", "presales"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="native-first-engineer",
        display_name="原生首版工程师",
        description="使用 Codex Presentations 原生创建可编辑 PPTX 首版并冻结。",
        role_group="visual",
        authority="producer",
        isolation_group="visual-producers",
        tags=frozenset({"strict-B", "native-first", "presentations", "presales"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    RoleContract(
        role_id="image-asset-producer",
        display_name="图像资产生成师",
        description="在原生首版冻结后生成非语义 Image 2 资产（背景/纹理/插画/光效）。",
        role_group="visual",
        authority="producer",
        isolation_group="visual-producers",
        tags=frozenset({"strict-B", "image-2", "nonsemantic", "presales"}),
        experience_access=frozenset({"mechanisms", "preferences"}),
    ),
    # ===== 视觉审查 =====
    RoleContract(
        role_id="visual-aesthetic-reviewer",
        display_name="审美质量审查师",
        description="独立审查视觉设计的审美质量、品牌一致性和视觉层级。",
        role_group="visual",
        authority="reviewer",
        isolation_group="visual-reviewers",
        tags=frozenset({"strict-B", "aesthetic", "independent"}),
        experience_access=frozenset({"anti-patterns", "preferences"}),
    ),
    RoleContract(
        role_id="visual-engineering-reviewer",
        display_name="工程可编辑审查师",
        description="独立审查 PPTX 的原生可编辑性、分层结构和工程质量。",
        role_group="visual",
        authority="reviewer",
        isolation_group="visual-reviewers",
        tags=frozenset({"strict-B", "engineering", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms"}),
    ),
    RoleContract(
        role_id="target-render-verifier",
        display_name="目标渲染验证师",
        description="使用 PowerPoint 桌面版进行目标渲染验证，形成四重门证据。",
        role_group="visual",
        authority="reviewer",
        isolation_group="delivery-reviewers",
        tags=frozenset({"strict-B", "target-render", "independent", "g2", "g4"}),
        experience_access=frozenset({"anti-patterns"}),
        can_release_gate=True,
    ),
    # ===== 反馈治理 =====
    RoleContract(
        role_id="feedback-governance-analyst",
        display_name="反馈治理分析师",
        description="将用户反馈转化为治理记录，诊断根因，评估学习资格和执行风险。",
        role_group="feedback",
        authority="support",
        isolation_group="feedback-governance",
        tags=frozenset({"feedback", "governance", "F0-F3"}),
        experience_access=frozenset({"mechanisms", "preferences", "anti-patterns"}),
    ),
    # ===== 经验进化 =====
    RoleContract(
        role_id="experience-curator",
        display_name="经验策展人",
        description="从治理过的反馈中提炼合格机制、反模式和偏好信号候选。",
        role_group="experience",
        authority="support",
        isolation_group="experience-curation",
        tags=frozenset({"experience", "curation", "learning"}),
        experience_access=frozenset({"mechanisms", "preferences", "anti-patterns"}),
    ),
    RoleContract(
        role_id="experience-evaluator",
        display_name="经验评估师",
        description="评估候选经验的适用范围、反例和失败条件，决定是否入库。",
        role_group="experience",
        authority="reviewer",
        isolation_group="experience-review",
        tags=frozenset({"experience", "evaluation", "independent"}),
        experience_access=frozenset({"mechanisms", "preferences", "anti-patterns"}),
    ),
    # ===== 交付 =====
    RoleContract(
        role_id="delivery-coordinator",
        display_name="交付协调员",
        description="整合最终交付物，执行质量检查，准备交付包。",
        role_group="delivery",
        authority="support",
        isolation_group="delivery",
        tags=frozenset({"delivery", "quality-assurance"}),
        experience_access=frozenset({"mechanisms"}),
    ),
]

_V22_CONTENT_ROLES = (
    RoleContract(
        role_id="presales-solution-chief",
        display_name="售前方案总师",
        description="对证据重建、客户决策语境、问题方案映射和完整阅读稿负责。",
        role_group="content",
        authority="producer",
        isolation_group="presales-chief",
        tags=frozenset({"presales", "evidence-first", "reading-first"}),
    ),
    RoleContract(
        role_id="content-evidence-gate-reviewer",
        display_name="事实与证据硬门审查",
        description="独立检查来源、身份、追溯、因果跳跃、能力和承诺。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-evidence-gate",
        tags=frozenset({"presales", "evidence", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms"}),
    ),
    RoleContract(
        role_id="content-presales-reading-gate-reviewer",
        display_name="售前阅读与客户立场硬门审查",
        description="独立检查客户立场、问题完整性、中立标题、阅读性和方案边界。",
        role_group="content",
        authority="reviewer",
        isolation_group="content-presales-reading-gate",
        tags=frozenset({"presales", "reading-first", "independent"}),
        experience_access=frozenset({"anti-patterns", "mechanisms", "preferences"}),
    ),
)


class RoleRegistry:
    """已批准角色的注册表。"""

    def __init__(self, roles: list[RoleContract]) -> None:
        self._roles: dict[str, RoleContract] = {r.role_id: r for r in roles}

    @classmethod
    def default(cls) -> "RoleRegistry":
        non_content = [role for role in _APPROVED_ROLES if role.role_group != "content"]
        return cls([*_V22_CONTENT_ROLES, *non_content])

    @classmethod
    def legacy_v16(cls) -> "RoleRegistry":
        """Read old role identities only while the v1.6 importer still exists."""

        return cls(list(_APPROVED_ROLES))

    def get(self, role_id: str) -> RoleContract:
        if role_id not in self._roles:
            raise KeyError(f"Unknown role: {role_id}")
        return self._roles[role_id]

    def has(self, role_id: str) -> bool:
        return role_id in self._roles

    def all(self) -> list[RoleContract]:
        return list(self._roles.values())

    def by_group(self, group: str) -> list[RoleContract]:
        return [r for r in self._roles.values() if r.role_group == group]

    def by_authority(self, authority: str) -> list[RoleContract]:
        return [r for r in self._roles.values() if r.authority == authority]


__all__ = [
    "RoleContract",
    "RoleRegistry",
    "ProductionRole",
    "ReviewRole",
    "SupportRole",
]
