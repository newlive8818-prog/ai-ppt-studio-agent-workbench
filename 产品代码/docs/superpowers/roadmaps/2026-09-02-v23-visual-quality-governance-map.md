# AI PPT Studio v2.3 视觉质量攻关研发治理地图

**日期：** 2026-09-02

**状态：** 已获用户批准的规划治理补充；不是产品代码实现、真实 PPT 样本验证、目标 PowerPoint 检查或用户视觉认可事实

**适用分支：** `codex/v23-visual-quality-20260831`

**关联文档：**

- [v2.3 视觉质量攻关产品地图](./2026-09-01-v23-visual-quality-product-map.md)
- [v2.3 视觉质量攻关研发地图](./2026-09-01-v23-visual-quality-rnd-map.md)
- [v2.3 视觉质量与设计感攻关设计规格](../specs/2026-09-01-v23-visual-quality-semantic-compilation-design.md)

**当前状态快照（2026-09-06）：** R0–R3 已进入本地 v2.3 集成分支。R3 来源 HEAD 为 `97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9`，实现 tip 为 `69e87c140fb53898b5e57dbc97b9f53f055cf06c`；Review B2/C2 对同一冻结快照均为 P0–P3 全零。用户明确批准后，目标 `c8ed5e9` 与来源 `97d5b99` 通过普通 `--no-ff` merge `21cfe9ed719a313bead71b23b4aea5e6f44f4de2` 本地集成。merge candidate 上 Python `566/566`、Node `137/137`、Widget `755/755`、MCP `1/1`、typecheck、build 和 diff-check 通过。R4/R5 未启动。

本快照只记录 Git、自动化、Review 和本地集成状态，不更新四份权威基线，不把自动化或 Review 结果写成 E3 真实样本、E4 目标 PowerPoint 或 E5 用户视觉认可。完整证据见[R3 Change 退出报告](../../validation/2026-09-05-v23-r3-change-exit-report.md)；[token-map ledger](../../validation/2026-09-05-v23-r3-token-map-review-ledger.md)只保留为早期局部修复历史子记录。

## 1. 这份治理地图解决什么问题

外部拆解说明提出了一个正确的区分：产品能力、用户功能切片和工程研发单元不是同一层对象。v2.3 采用该区分，但不改变已经批准的产品目标、四份权威基线、R0–R5 Worktree 隔离或五层证据模型。

本文件新增四个规划对象：

```text
M0   问题与价值边界
FS   用户价值功能切片
CHG  研发变更对象
Trace 产品能力到证据的追踪矩阵
```

它们是研发治理对象，不是新的 Runtime 领域对象，不是新的 MCP 工具，也不是第二套 PPTX 编译器。

## 2. 推荐的分层模型

```text
M0 问题、用户与价值边界
        ↓
P1–P6 产品能力链
        ↓
FS-01…FS-06 用户价值功能切片
        ↓
CHG-V23-R0…CHG-V23-R5 研发变更对象
        ↓
R0–R5 Branch + Worktree + Commit
        ↓
Task 工程任务
        ↓
Test / Evidence / Review / Gate
        ↓
用户集成决定
```

各层职责必须保持分离：

| 层级 | 要回答的问题 | 不代表什么 |
|---|---|---|
| M0 | 为什么做、为谁做、改善什么 | 不是新的产品功能 |
| P1–P6 | 产品最终需要具备哪些能力 | 不等于六个独立用户功能 |
| FS | 用户能独立获得什么结果 | 不等于某个代码模块 |
| CHG / R | 本次工程变更的边界是什么 | 不等于用户已经验收 |
| Task | 具体改哪些文件、测试什么 | 不等于样本或 PowerPoint 通过 |
| Evidence | 哪个证据支撑哪个结论 | 不等于更高层级的证据 |
| Gate / Review | 谁在什么条件下作出什么决定 | 不自动代替用户判断 |

## 3. M0：问题、用户与价值边界

M0 是 v2.3 研发前置边界卡，不作为 P0 产品能力加入 Runtime。

### 3.1 已确认的问题

当前 v2.2 工程治理、内容流程和 UI 工作台基本成立，但生成 PPT 仍可能出现：

- AI 味明显、页面模板化和卡片化；
- 所有内容被平均分配，缺少视觉重心；
- 章节、目录和阅读顺序被压缩，读者结构化理解下降；
- 观点、证据、对象和构图之间的关系不清楚；
- 跨页缺少节奏变化，页面像独立模板而不是叙事序列；
- 自动化通过但真实阅读体验、PowerPoint 编辑性或售前可用性不足。

### 3.2 当前用户与场景边界

```text
主要生产／审核者：用户本人，承担目标、关键选择、反馈和最终视觉判断
AI：主要视觉策略、页面推理和 PPTX 生产者
系统：负责合同、版本、证据、Review 和 Gate 治理
最终阅读对象：售前解决方案汇报中的客户经营与数字化决策相关读者
一期场景：阅读优先的售前解决方案汇报
```

这张卡不新增未经批准的角色体系，不把客户决策者变成当前工作台的新操作用户。

### 3.3 价值假设与证据

| 价值假设 | 首要观察证据 | 需要避免的误判 |
|---|---|---|
| 读者更快形成页面主张 | 五秒测试中的 `perceived_message` 与 `next_reading_step` | 不能用字号、对齐或自动评分代替阅读判断 |
| 页面更少模板化 | 两页是否使用不同且合理的视觉机制；反模式记录 | 不能用“颜色不同”证明设计机制不同 |
| 观点与证据关系更清楚 | `primary_relationship`、证据角色和人工复核 | 不能把存在图表等同于有观点 |
| PPTX 更可交付 | 对象、编辑性、字体、裁切、连接器和目标 PowerPoint 结果 | 不能把渲染成功等同于目标环境可交付 |
| 用户更愿意接受 | 当前 PPTX 哈希绑定的 accepted / revise / rejected | 不能把代码完成或测试通过写成用户认可 |

## 4. P1–P6：产品能力链

P1–P6 继续保留，名称和职责如下：

```text
P1 视觉策略层
P2 页面视觉推理层
P3 视觉语义编译层
P4 原生 PowerPoint 实现层
P5 审查与证据层
P6 经验演化层
```

它们描述产品价值链，不分裂成六个独立 Worktree。具体能力定义仍以产品地图和已批准设计规格为准。

## 5. FS-01…FS-06：用户价值功能切片

功能切片必须有用户可感知结果、独立输入、独立输出、明确完成定义和可逆边界。以下六个切片用于追踪和验收，不表示六个切片必须各自拥有独立产品页面或独立研发分支。

### FS-01：系统提出并展示五秒读者判断

```text
输入：页面内容、受众、阅读场景
输出：页面主张、五秒第一判断、第一眼焦点和下一阅读步骤
用户动作：批准、修改或拒绝
完成定义：用户可以判断系统是否抓住页面第一目标
主要支撑：P1、P2；R0、R1、R4
```

### FS-02：单页视觉合同可审核

```text
输入：Visual Brief、Deck Design System、页面内容
输出：可查看的 Slide Visual Contract
合同重点：主张、读者判断、证据关系、视觉重心、构图、资产角色、密度、节奏、实现要求、反模式和证据计划
完成定义：合同字段闭合，且审查者能解释页面为什么这样设计
主要支撑：P2；R0、R1、R3、R4
```

### FS-03：视觉合同确定性派生为对象计划

```text
输入：当前有效的三层视觉合同
输出：不可变 VisualCompilationPlan 和 lineage
完成定义：相同规范化输入与编译器版本产生相同 payload；无效合同不能静默进入 PPTX 构建
主要支撑：P3；R1、R2、R4
```

### FS-04：由对象计划生成两页原生可编辑 PPTX

```text
输入：两页批准的视觉合同和对象计划
输出：两页原生 PowerPoint 实验成品
完成定义：页面可打开、显示、继续编辑；两页采用不同且可解释的视觉机制；对象计划可追溯到实现
主要支撑：P4；R2、R4
```

### FS-05：视觉审查、目标环境检查和用户判断闭合

```text
输入：PPTX、渲染图、自动化结果、审查投影
输出：自动审查、人工视觉审查、macOS PowerPoint 检查和用户决策记录
完成定义：五层证据分别记录；用户判断绑定当前 PPTX 哈希、页码和版本
主要支撑：P5；R3、R4
```

### FS-06：把验证有效的机制沉淀为 bounded same-type 经验候选

```text
输入：已审查样本、修订记录、用户结果
输出：包含适用范围、反例、失败边界和回滚方式的经验候选
完成定义：经验只在声明的 type signature 和场景边界内复用
主要支撑：P6；R4、R5
```

FS-01 和 FS-02 是面向用户的可审核结果，但不要求用户亲自完成所有视觉设计；系统应先提出，用户再作关键判断。

## 6. 设计哲学与合同边界

用户提出的阅读顺序、目录与章节焦点、电影／拍摄者视角、观点与证据关系、页面目标、布局和构图要求，作为 v2.3 的设计启发纳入以下对象：

### Deck Design System 的启发字段

```text
reading_spine
chapter_hierarchy
chapter_emphasis_rules
cross_slide_rhythm_rules
```

### Slide Visual Contract 的启发字段

```text
page_objective
evidence_to_judgment_relation
viewpoint_intent
composition_requirements
layout_requirements
```

其中：

- 页面主张、证据关系、第一眼焦点、视觉重心、构图要求和 PowerPoint 实现要求属于硬合同语义；
- 电影式视角、镜头感、视角切换、章节张力和视觉隐喻先作为非强制设计启发；
- “章节标题不得被缩小到失去结构焦点”先作为生成提示和人工审查项，不直接变成所有页面的统一字号规则；
- 经过 R4 真实样本和用户结果证明有稳定价值后，才考虑将某些启发升级为硬约束。

## 7. CHG-V23-R0…CHG-V23-R5：研发变更对象

每个 Change 绑定一个 R 研发单元，但不与 P 能力层一一对应。每个 Change 必须记录：

```text
change_id
goal
user_value
in_scope
out_of_scope
preconditions
branch
worktree
owned_files
verification_package
exit_conditions
rollback_boundary
integration_decision
status
```

### 当前 Change 登记

| Change | 研发单元 | 当前状态 | 用户结果边界 |
|---|---|---|---|
| `CHG-V23-R0` | 权威基线差异与合同迁移 | 已集成 | 只证明合同变更已形成，不证明视觉机制或用户认可 |
| `CHG-V23-R1` | 视觉合同与确定性编译核心 | 已提交、已自动化验证、已集成 | 只证明机制和 lineage，不证明 PPTX 或样本有效 |
| `CHG-V23-R2` | Agent / Context / Presentations handoff | 已提交、已自动化验证、已集成 | 只证明交接协议，不证明目标 PowerPoint 可用 |
| `CHG-V23-R3` | 视觉审核投影与最小 Widget 增量 | 已提交、自动化验证已通过、Review B2/C2 已通过、已本地集成 | 只证明用户可审核新增语义及其本地工程闭合，不证明视觉质量已接受 |
| `CHG-V23-R4` | 两页 Runtime 机制实验 | 未开始；本次 R3 集成未创建 Worktree | 只有 V0–V3 才能形成样本和用户判断证据 |
| `CHG-V23-R5` | 3–5 个真实售前样本扩展 | 未授权 | 不得创建计划、分支、Worktree 或样本实验 |

负责人、工期、任务追踪 ID 如未由用户指定，不填写为事实；后续可以作为管理字段追加，但不能伪造。

## 8. P → FS → R → Test → Evidence → Gate 追踪矩阵

| 产品能力 | 用户功能切片 | 研发单元 | 关键文件／范围 | 测试与检查 | 证据对象 | 退出判断 |
|---|---|---|---|---|---|---|
| P1 视觉策略 | FS-01 | R0、R1、R4 | 四基线、Visual Brief、Design System | 合同闭合、阅读顺序和五秒字段检查 | visual brief / contract ref | 策略可被页面引用 |
| P2 页面视觉推理 | FS-02 | R1、R3、R4 | Slide Visual Contract、review projection | 字段闭合、证据关系、反模式审查 | contract artifact、review ref | 页面判断可审核 |
| P3 视觉语义编译 | FS-03 | R1、R2、R4 | `compilation.py`、ContextPack、lineage | 确定性、原子性、失效和版本绑定 | compilation-plan ref | 允许进入原生实现 |
| P4 原生实现 | FS-04 | R2、R4 | Presentations handoff、实验构建器 | 对象、渲染、编辑性、字体和连接器 | PPTX hash、render evidence | 完成 V1/V2 |
| P5 审查与证据 | FS-05 | R3、R4 | review projection、evidence ledger | 自动、人工、目标 PowerPoint 检查 | review / decision ref | 完成 V2/V3 |
| P6 经验演化 | FS-06 | R4、R5 | experience evidence | 适用边界、反例、用户结果和回滚 | experience candidate ref | 是否授权 R5 |

## 9. 研发状态词汇

后续路线文档不得只使用“待执行／已完成”两个状态。统一使用：

```text
设计已批准
实施已开始
修改已产生
自动化验证已通过
已提交
已 Review
已集成
真实样本已验证
目标 PowerPoint 已检查
用户已认可
未授权
```

一个单元可以同时处于多个不同层级，例如：

```text
R0：修改已产生、自动化验证已通过、已提交、已集成
R4：尚未开始；没有样本、PowerPoint 或用户证据
```

任何高层级状态都不能由低层级状态自动推断。

## 10. Worktree 与隔离决策

P1–P6 和 FS-01–FS-06 不各自建立 Worktree。Worktree 仍按 R0–R5 研发变更单元隔离：

```text
一个 Change
→ 一个 R 单元
→ 一个 Branch
→ 一个 Worktree
→ 一个验证包
→ 一个集成决定
```

当前原始 R0 Worktree 和 successor Worktree 均已保留，R0–R3 已进入本地集成分支；R3 来源分支和 Worktree 继续保留，R4 尚未创建，R5 未授权。v2.3 规划／集成 Worktree 只承载路线文档、治理文档和用户批准后的顺序集成，不直接承担后续 R4/R5 实现。

## 11. 当前停止点

本治理地图状态快照更新后，项目获得的是可追踪的研发事实，不是新的实现授权或视觉验收结论。

当前仍然禁止：

- 在 v2.3 集成 Worktree 中修改 R3 产品代码；
- 修改四份权威基线；
- 重复合并或重写已集成 R0；
- 重复集成、重写或清理 R3 来源分支、merge、Worktree 或历史；
- 继续推进 v2.2 Runtime 项目的 G3/G4；
- 把 R4 机制实验写成正式全量交付；
- 启动 R5；
- 安装、发布或公开插件。

R3 本地集成整包到此只建立 E1/E2、独立 Review 和本地 merge 事实。E3、E4、E5、真实 Runtime、G3/G4、PPTX、PowerPoint、发布和用户视觉认可仍未建立。本次任务不启动 R4/R5；任何后续单元仍需独立授权，并重新核验精确 HEAD、前置集成状态和目标 Worktree。
