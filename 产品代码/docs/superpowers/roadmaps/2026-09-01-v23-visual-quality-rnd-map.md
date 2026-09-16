# AI PPT Studio v2.3 视觉质量攻关研发地图

**日期：** 2026-09-01

**状态：** 已批准设计的实施拆解；下方状态快照仅记录当前研发单元的 Git／自动化／Review 状态，不是样本验收、PowerPoint 检查或用户视觉认可事实

**产品地图：** [v2.3 视觉质量攻关产品地图](./2026-09-01-v23-visual-quality-product-map.md)

**研发治理补充：** [v2.3 视觉质量攻关研发治理地图](./2026-09-02-v23-visual-quality-governance-map.md)

**设计规格：** [v2.3 视觉质量与设计感攻关设计规格](../specs/2026-09-01-v23-visual-quality-semantic-compilation-design.md)

## 1. 研发组织原则

本计划采用“一个研发单元，一个分支，一个 Worktree，一个验证包，一个集成决定”。不同单元不得在同一实现 Worktree 混合修改。

现有 v2.3 Worktree：

```text
/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/6fe4/PPT-codex-app
```

只承担：

- 产品地图、研发地图和计划文档；
- v2.3 受控集成分支；
- 已批准研发单元的顺序集成；
- 不直接混合执行 R0–R4。

当前分支和核验 HEAD：

```text
branch: codex/v23-visual-quality-20260831
integration merge: 21cfe9ed719a313bead71b23b4aea5e6f44f4de2
parents: c8ed5e97c99c9e6031300ef5a118ca750ab284f3 97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9
freeze: b874d6581c14c8fb26bf498848f37c9456a42482
tag:    ai-ppt-studio-v2.2-engineering-freeze-20260831
status after merge verification: clean
```

本轮治理证据提交后 HEAD 会再次前移；执行任一后续研发单元时必须重新读取真实 HEAD，不能复用本文记录值。

### 2.1 当前研发状态快照（2026-09-06）

本快照在更新本地图前以 Git 只读命令重新核验，记录的是当前事实，不替代下游 Review 或用户决定：

| 对象 | 当前事实 | 证据边界 |
|---|---|---|
| v2.3 集成分支 | `codex/v23-visual-quality-20260831`，R3 merge `21cfe9ed719a313bead71b23b4aea5e6f44f4de2` | parents 为 `c8ed5e9` 与 `97d5b99`；保留双方历史的普通本地 `--no-ff` merge |
| R3 实现分支 | `codex/v23-visual-review-projection-20260901` @ `97d5b9944d3f97c279aa9f63a0c12b7ee255b0a9` | 实现 tip `69e87c1`，退出报告 commit `97d5b99`，Worktree clean |
| R3 自动化 | Python `566/566`；Node `137/137`；Widget `755/755`（16 files，文字锚定 `17/17`）；MCP `1/1`；typecheck/build/diff-check | 在实际 merge candidate `21cfe9e` fresh 执行；只构成 E2／本地集成证据 |
| R3 独立 Review | Review B2/C2 对同一冻结双 SHA 均 `P0–P3=0` | 独立 Review 已完成，不代表 E3–E5 或用户视觉认可 |
| R3 集成 | 已本地集成 | 用户明确批准；未 push、未发布、未启动 R4/R5 |

R3 的唯一完整退出与集成证据见[R3 Change 退出报告](../../validation/2026-09-05-v23-r3-change-exit-report.md)；[token-map ledger](../../validation/2026-09-05-v23-r3-token-map-review-ledger.md)保留为早期局部修复历史子记录。

## 2. Worktree 拓扑

```text
v2.2 freeze b874d658
        │
        └── v2.3 integration / planning
            codex/v23-visual-quality-20260831
            .../codex-home/worktrees/6fe4/PPT-codex-app
                 │
                 ├── R0 baseline contract
                 │   codex/v23-baseline-contract-20260901
                 │   ~/.config/superpowers/worktrees/PPT-codex-app/v23-baseline-contract-20260901
                 │        │ user review → approved fast-forward only
                 │        ▼
                 ├── R1 semantic core
                 │   codex/v23-semantic-core-20260901
                 │   ~/.config/superpowers/worktrees/PPT-codex-app/v23-semantic-core-20260901
                 │        │ review → approved fast-forward only
                 │        ▼
                 ├── R2 Presentations handoff
                 │   codex/v23-presentations-handoff-20260901
                 │   ~/.config/superpowers/worktrees/PPT-codex-app/v23-presentations-handoff-20260901
                 │        │ review → approved fast-forward only
                 │        ▼
                 ├── R3 visual review projection
                 │   codex/v23-visual-review-projection-20260901
                 │   ~/.config/superpowers/worktrees/PPT-codex-app/v23-visual-review-projection-20260901
                 │        │ review → approved history-preserving merge
                 │        ▼
                 └── R4 two-slide experiment
                     codex/v23-two-slide-experiment-20260901
                     ~/.config/superpowers/worktrees/PPT-codex-app/v23-two-slide-experiment-20260901
```

以上路径中，R0 原始 Worktree 和 successor Worktree 均已保留；R0 successor、R1、R2 已进入当前 v2.3 集成分支。R3 已完成独立实现、自动化、Review B2/C2，并按用户明确批准以普通 `--no-ff` merge `21cfe9e` 本地集成；来源和目标 Worktree／分支均保留。R4 尚未创建，R5 未授权。任何下游单元仍必须从用户批准时重新核验的精确集成 HEAD 建立。

## 3. 创建与集成协议

执行每个研发单元时必须按以下顺序：

1. 用户明确指定要执行的计划；
2. 核验 v2.3 集成 Worktree 的分支、HEAD、冻结祖先和 clean 状态；
3. 核验所有前置研发单元已经由用户批准并进入集成分支；
4. 使用 `superpowers:using-git-worktrees` 检测隔离状态；
5. 优先使用平台原生 Worktree；若平台没有原生能力，再使用 Git Worktree fallback；
6. 从集成分支当时的精确 HEAD 创建该单元分支和专属 Worktree；
7. 在新 Worktree 运行基线测试，失败即停止，不自行跨计划修复；
8. 只修改该计划文件清单中的文件；
9. 按 RED → 最小 GREEN → 回归 → 提交执行；不 amend；
10. 单独报告实现、自动化、样本、PowerPoint 和用户认可五种状态；
11. 等用户决定是否集成；
12. 仅批准后执行集成；默认 fast-forward。若新鲜拓扑证明双方因独立治理提交而分叉，必须先报告 merge-base、双方独有提交与路径／冲突分析，只有用户明确批准后才可使用保留历史的普通 `--no-ff` merge；
13. 下一个依赖单元只能从新的集成 HEAD 创建。

禁止：

- 在现有 `6fe4` linked Worktree 内创建嵌套 Worktree；
- 从旧计划文本中的 HEAD 猜测创建基点；
- 在两个 Worktree 同时检出同一分支；
- 将 R2、R3 提前从 R1 之前的 HEAD 创建；
- 通过 merge commit、cherry-pick 或手工复制掩盖错误基点；若无法 fast-forward，先停止并解释差异；
- 清理、回退或借用 quarantine Worktree；
- 修改、移动或删除 v2.2 冻结标签、集成分支、历史 Worktree 和用户文件。

R3 的 `21cfe9e` 不属于上述“掩盖错误基点”：合并前共同基准为 `25d04e3`，目标独有 2、来源独有 14，双方路径无交集且无修改 merge-tree 冲突扫描为空；用户在获得该拓扑后明确批准普通 `--no-ff` 本地 merge。

## 4. 研发单元总览

| 单元 | 目标 | 前置 | 分支 | 当前状态 | 独立退出条件 |
|---|---|---|---|---|---|
| R0 | 四份权威基线精确迁移 | 规划文档批准 + 用户单独批准基线差异 | `codex/v23-baseline-contract-successor-20260902` | 已集成 | 四基线一致、链接有效、未把目标写成实现事实 |
| R1 | 视觉合同和确定性编译核心 | R0 已集成 | `codex/v23-semantic-core-20260901` | 已提交、已自动化验证、已集成 | 新合同、原子 plan、失效、legacy 与 G1/G2/G3 lineage 全部测试通过 |
| R2 | Agent／Context／Presentations handoff | R1 已集成 | `codex/v23-presentations-handoff-20260901` | 已提交、已自动化验证、已集成 | `build-native-first` 只消费当前 plan，43 个公开工具不增加，Skill 合同一致 |
| R3 | 后端投影和最小 Widget 增量 | R2 已集成 | `codex/v23-visual-review-projection-20260901` | 已提交、自动化验证已通过、Review B2/C2 已通过、已本地集成 | 新视觉语义可审核，exact-field validation 闭合，已验收布局和交互不变；不代表 E3–E5 |
| R4 | 两页独立机制实验 | R3 已集成 | `codex/v23-two-slide-experiment-20260901` | 未开始；本次 R3 集成未创建 Worktree | V0–V3 分层完成；未获用户认可不得扩展 |
| R5 | 3–5 个真实售前样本 | R4 V0–V3 均通过 + 用户另批新设计 | 未创建 | 未授权 | 当前不写计划、不创建 Worktree、不执行 |

## 5. 依赖图

```text
R0 baseline contract
        ↓
R1 semantic core
        ↓
R2 governed handoff
        ↓
R3 review projection
        ↓
R4 two-slide experiment
        ↓  only if V0-V3 passed and user authorizes
R5 real presales samples
```

本轮选择线性集成而不是并行开发。R2 与 R3 技术上可在 R1 后部分并行，但它们共享视觉合同字段、fixtures、投影和最终视觉合同 lineage；提前并行会增加错基点、重复 fixture 和冲突合并风险。用户当前优先目标是避免搞乱，因此采用顺序 Worktree。

## 6. 跨计划接口登记

以下名字是跨计划稳定接口，后续计划不得自行改名：

### 6.1 Artifact 与 head

```text
artifact kind: visual-compilation-plan
current head:  visual/compilation-plan
compiler:      visual-semantic-compiler/v1
handoff:       codex-presentations-handoff/v23-v1
```

`source_revision` 固定表示 `visual/contracts` 与 `visual/compilation-plan` 在同一原子事务中的发布 revision（即提交前 `expected_revision + 1`），不是随后会继续增长的项目当前 revision。后续校验必须从事件历史证明两个 head 在该 revision 同时首次成为当前值；不得用 `source_revision == state.revision` 判断计划是否仍然 current。

### 6.2 Visual Brief 新字段

```text
decision_task
design_stance
emotional_boundary
brand_boundary
density_strategy
forbidden_patterns
five_second_test_contract
design_philosophy_refs    # optional, non-gating
```

### 6.3 Deck Design System 新字段

```text
density_rhythm
cross_slide_rhythm_rules
emphasis_budget
image_language
diagram_language
five_second_test_rules
```

### 6.4 Slide Visual Contract 新字段

```text
reader_judgment
primary_relationship
secondary_relationship
visual_mechanism
focal_point
asset_roles
forbidden_patterns
previous_rhythm_relation
next_rhythm_relation
text_density_budget
powerpoint_implementation_requirements
acceptance_evidence_plan
```

### 6.5 VisualCompilationPlan 每页字段

```text
slide_id
primary_relationship
visual_mechanism
focal_point
reading_path
object_plan
connector_semantics
asset_plan
layout_constraints
native_bitmap_routing
powerpoint_constraints
anti_pattern_checks
acceptance_evidence_plan
```

`VisualCompilationPlan` 只能由当前合同确定性派生。R2 不创建第二份计划，R3 不把它展开成用户模块，R4 不手工修改其内容。

### 6.6 Presentations handoff 闭合字段

`build-native-first` 的 `layers.visual_handoff` 除当前计划及其绑定输入外，必须包含由任务 ID 派生的项目内绝对输出路径、任务创建后的精确结果写入 revision、授权动作／结果 kind／三页锚点范围、G1 授权身份以及禁止整套构建和禁止自动推进 Gate 的边界。输出路径、expected revision 和授权范围不得只留在自由文本 instructions 中。

## 7. 文件所有权地图

### R0 独占

- `00-唯一研发基线索引-v1.0.md`
- `01-产品需求基线-v1.0.md`
- `02-系统详细设计-v1.0.md`
- `03-UI设计与交互规范-v1.0.md`

### R1 主要拥有

- `产品代码/src/ai_ppt_studio/domains/visual/contracts.py`
- `产品代码/src/ai_ppt_studio/domains/visual/compilation.py`（新建）
- `产品代码/src/ai_ppt_studio/application/visual_invalidation.py`（新建）
- `产品代码/src/ai_ppt_studio/application/visual_service.py`
- `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`
- `产品代码/src/ai_ppt_studio/application/release_policy_service.py`
- `产品代码/tests/v16_visual_fixtures.py`
- v2.3 核心合同、原子性和 lineage 测试

### R2 主要拥有

- `产品代码/src/ai_ppt_studio/context_compiler.py`
- `产品代码/src/ai_ppt_studio/application/project_service.py`
- `产品代码/src/ai_ppt_studio/domains/visual/contracts.py` 中 anchor 的 compilation ref 绑定
- `产品代码/skills/ai-ppt-studio/references/visual-workflow.md`
- `产品代码/skills/ai-ppt-studio/references/presentations-handoff.md`
- MCP 目录只做稳定性回归；首轮不增加公开工具

### R3 主要拥有

- `产品代码/src/ai_ppt_studio/application/visual_review_service.py`
- `产品代码/widget/src/types/visual-review.ts`
- `产品代码/widget/src/review-surface-validation.ts`
- `产品代码/widget/src/visual-review/visual-contract-field-contract.ts`
- `产品代码/widget/src/visual-review/visual-review-page-view-model.ts`
- `产品代码/widget/src/visual-review/VisualContractView.tsx`
- 相关 Python/Vitest fixtures 与测试

### R4 主要拥有

- `产品代码/scripts/experiments/v23-two-slide/`（实验构建和证据脚本）
- `产品代码/tests/test_v23_two_slide_experiment.py`
- 独立 Runtime 项目中的实验制品和证据，不进入源码 Git 历史

若执行中发现必须修改另一研发单元的独占文件，必须停下，说明原因，并由用户决定调整计划或重新排列单元；不得悄悄跨范围修改。

## 8. R0：权威基线差异与合同迁移

### 研发目标

把已批准设计中的产品、系统和 UI 变化写入唯一权威基线，同时保留 v2.2 冻结身份和五层证据边界。

### 特殊批准门

计划批准不等于基线修改批准。R0 执行开始后先生成四文件逐项差异清单，用户明确批准差异后才写入。未批准时 R0 Worktree 保持 clean 或只含差异说明，不修改四基线。

### 非目标

不修改产品代码、Skill、MCP、Widget、Runtime、版本标签或冻结分支。

## 9. R1：视觉合同与语义编译核心

### 研发目标

扩展三层视觉合同并把 `VisualCompilationPlan` 实现为原子、确定、不可变的派生 artifact；同时建立 legacy、失效和 G1/G2/G3 lineage 边界。

### 核心决定

采用服务端原子派生，而不是新增独立 Agent action 或公开 MCP 工具：

```text
register_visual_contract_set(normalized contracts)
  -> compute visual-contract-set ref without writing
  -> derive normalized compilation payload
  -> one ProjectKernel.commit(
       visual/contracts,
       visual/compilation-plan
     )
```

### 非目标

不修改 Widget，不生成真实 PPTX，不公开插件，不把旧 artifact 自动补成 v2.3 已评估。

## 10. R2：Agent／Context／Presentations handoff

### 研发目标

让 `build-native-first` 只能以当前 `visual/compilation-plan` 为唯一入口，ContextPack 再解析并携带其绑定的当前三层视觉合同、ReleaseTargetPolicy、对象／连接语义、反模式和 PowerPoint 约束。

### 公开接口边界

- 继续复用 `request_ai_ppt_agent_action`；
- 继续复用 `commit_ai_ppt_artifact` 提交 `native-anchor-set`；
- 公开 MCP 工具总数保持 43；
- 不新增 `compile_visual_plan`、`get_visual_plan` 或其他公开工具；
- Node MCP 仍只做 schema 和协议桥接，Python Runtime 仍是唯一业务写入者。

## 11. R3：视觉审核投影与最小 Widget 增量

### 研发目标

只把用户审核真正需要的新视觉语义加入当前完整视觉合同正文，继续由闭合 ViewModel 和 exact-field validation 控制。

### UI 保持不变

- 单一紧凑顶栏；
- `3 页锚点成果 / 完整视觉合同` 双视图；
- 锚点空状态无批次大面板，反馈后画布下方内联；
- 目录左侧覆盖、标记右侧覆盖；
- 文字范围标记只在真实选择后出现；
- 不显示 `VisualCompilationPlan` 技术模块；
- 不显示 G1/G2/revision 技术账本；
- 不重开已验收布局、功能和交互。

## 12. R4：两页独立 Runtime 机制实验

### 研发目标

对批准样本第 5、8 页完成 V0–V3。该单元同时拥有独立 Git Worktree 和独立 Runtime 项目，任何结果都不写入原 v2.2 Runtime 项目。

目标 Runtime 项目：

```text
/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901
```

源文件继续只读：

```text
/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx
SHA-256 da54a46ea9dd91aa7643f502f09970c1bdf72c59a7a08e59928db647ce134cd1
```

R4 使用机制实验身份，不把合成 fixture Gate、自动化结果或分享型样本表述为真实售前 G0/G3/G4。G3/G4 仍只属于正式产品合同；R4 的用户结果记录为实验页面的视觉判断。

## 13. R5：正式样本扩展

R5 当前只有地图节点。只有 R4 的 V0、V1、V2、V3 全部满足且用户明确授权，才重新进入 brainstorming，选择 3–5 个真实售前样本并形成新设计规格和新计划。

当前不得：

- 为 R5 创建分支或 Worktree；
- 预选客户事实或未授权素材；
- 把两页机制样本通过自动推断为正式样本策略成功；
- 复用 R4 的用户认可作为其他页面认可。

## 14. 验证矩阵

| 单元 | 机制实现 | 自动化 | 真实样本 | 目标 PowerPoint | 用户视觉认可 |
|---|---|---|---|---|---|
| R0 | 基线合同变更 | 链接／冲突／一致性检查 | 不适用 | 不适用 | 只确认合同文本，不是视觉认可 |
| R1 | 是 | Python 单元／集成／原子性 | 否 | 否 | 否 |
| R2 | 是 | Python + Node + Skill 包回归 | 否 | 否 | 否 |
| R3 | 是 | merge candidate `21cfe9e`：Python `566/566`；Node `137/137`；Widget `755/755`（16 files，文字锚定 `17/17`）；MCP `1/1`；typecheck/build/diff-check | 否 | 否 | 旧交互未重开验收；新增视觉质量仍需真实样本和用户判断 |
| R4 | 使用已实现机制 | 构建／渲染／对象／溢出检查 | 是，第 5、8 页 | 是，macOS PowerPoint | 是或否，必须由用户明确给出 |

## 15. 基线测试和失败策略

每个实现 Worktree 建立后先执行：

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src \
  python3 -m unittest discover -s tests
npm run typecheck
npm run test:node
npm run test:widget -- --configLoader runner
npm run build
```

若某项基线因当前平台能力而不能运行，必须保留完整错误输出并登记为 `CapabilityGap`；不得用跳过测试或修改无关代码制造绿色结果。若出现真实基线失败，停止当前研发单元，由用户决定调查、换基点或取消。

## 16. 提交与回滚

- 每个研发单元使用小而独立的提交；
- 不 amend；
- 不删除历史分支、Worktree 或标签；
- 不在研发单元中发布或安装插件；
- 每个单元最终提交前执行 `git diff --check`、范围核验和全量回归；
- 用户未批准集成时，v2.3 集成分支不前移；
- 已集成单元发生问题时，以新的修复或 `git revert` 形成可追溯回滚，不重写历史。

## 17. 当前停止点

本研发地图只定义分支、Worktree、依赖、文件所有权和验收边界。截至 2026-09-06，R0–R3 已进入本地 v2.3 集成分支；R3 来源 `97d5b99` 经用户批准由 merge `21cfe9e` 集成，完整自动化和 Review B2/C2 已闭合，原分支与两个 Worktree 均保留。R4 尚未创建实现 Worktree，R5 未授权；E3、E4、E5、G3/G4、真实 Runtime、PPTX、PowerPoint、发布和用户视觉认可均未建立。开始任一后续单元前必须取得对应授权并重新核验精确 HEAD、前置集成状态和目标 Worktree。
