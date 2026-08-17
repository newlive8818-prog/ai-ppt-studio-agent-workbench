# AI PPT Studio v2.2 统一研发与源码简化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. 本计划遵守用户的单 Agent 要求，不分派子代理；未经用户单独授权，不执行任何 Git commit。

**Goal:** 在不改变四份 v2.2 已批准需求、不影响真实 PPT 项目和既有研发现场的前提下，迁移并完成对话唯一入口、两张按需专业审核页、售前方案总师内容链、统一 ReviewSession 和双层经验系统，同时删除五空间、常驻侧边栏、旧内容生产链及可证明的死代码。

**Architecture:** Python Runtime 继续作为唯一业务写入者，保留不可变 artifact、单调 revision、幂等 command identity、事务、Gate 和可信宿主确认；Node MCP/Review Bridge 只做声明式工具适配和受限宿主桥接；React 只渲染由 Runtime 生成的内容或视觉专业审核投影。迁移采用“新合同先建立、当前能力白名单迁移、历史只读适配、旧写路径一次性切断”的方式，不长期维护新旧双轨。

**Tech Stack:** Python 3 标准库 Runtime、Node.js ESM、MCP SDK、React 19、TypeScript 5、Vite/Vitest、loopback Review Bridge、Codex Presentations、macOS Microsoft PowerPoint。

---

## 0. 计划身份、执行权限与事实边界

本文件是统一实施计划，不是已完成声明，也不授权立即修改正式插件或真实 Runtime。执行前必须再次读取项目根目录四份 v2.2 基线；发生冲突时，用户最新明确决定和四份基线优先于本计划。

当前现场事实：

- 主工作区分支：`codex/content-blueprint-sidebar-review`；
- 审计基点：`3998a9694cd9c86cc3bf97b45de294c85a57109e`；
- 主工作区包含大量已跟踪修改和未跟踪文件，不能作为直接集成目录；
- 隔离 worktree `/private/tmp/ai-ppt-task5-a7f76a65` 保存旧内容审核实施链，当前 head `d7ff354`；
- `stash@{0}` 和 `stash@{1}` 保存并行重叠成果，禁止应用、删除或覆盖；
- 旧 12 提交链混合了可复用内容审核内核和已废止侧边栏产品身份，禁止整链 cherry-pick；
- 真实 PPT 运行数据默认位于 `/Users/defei/Documents/AI-PPT-Workspace`，本计划的自动实施和测试禁止写入；
- 并行 Web 产品空间 `../PPT  web app ` 不属于本计划范围；
- 正式插件安装、缓存刷新、真实 Browser 宿主验收、真实 PowerPoint 验收和真实文件发送均保持单独授权与单独 Gate。

### 不可妥协的简洁性定义

“简洁”指更少的产品概念、更少的真相源、更短的调用链、更明确的类型和更少的重复实现，不是机械压缩行数。以下内容不得为了少写代码而删除或合并：

- expectedRevision、command identity 和重放语义；
- 原子事务、失败回滚和不可变历史；
- 类型收窄、输入验证和稳定错误码；
- Gate、可信宿主确认、sourceVersion 和 revision 绑定；
- 历史项目只读兼容；
- 保存、宿主通知和 AI 接收回执的事实分离；
- 真实 Browser、Presentations、PowerPoint 和聊天交付证据边界；
- 对异常、冲突和能力缺失的准确报告；
- 能证明行为的测试。

新增或重写代码遵循：

1. 一个业务事实只有一个权威模型和一个 current head；
2. 一个公开工具只在一个声明式目录中定义；
3. 一个校验规则只在 Runtime 边界实现，MCP 和 React 不复制业务校验；
4. 只为真实复用提取函数，不创建 `Utils`、`Manager`、`Helper` 式万能层；
5. 可以直接返回表达的逻辑不引入临时变量、二次映射或包装对象；
6. 不用 feature flag 长期保留五空间/新架构双表面；
7. 历史读取代码只允许位于 `adapters/legacy/`，不得被新项目写路径导入；
8. 新增函数应聚焦一个动作；超过约 80 行时必须先证明无法按业务职责拆分；
9. 新增 React 页面组件不同时承担数据加载、领域变换、长文档渲染、编辑器和回执状态；
10. 以编译、测试和架构断言证明简化，不以“行数下降”替代正确性。

## 1. 全面审计结论

### 1.1 当前规模

| 范围 | 文件数 | 物理代码行 |
|---|---:|---:|
| Python Runtime | 62 | 21,446 |
| MCP | 5 | 2,547 |
| Widget 运行代码 | 23 | 5,476 |
| 产品运行代码合计 | 90 | 29,469 |
| 工程脚本 | 18 | 2,648 |
| 自动测试 | 88 | 22,653 |
| 全部程序代码 | 197 | 54,789 |

旧审计快照中的产品运行代码约 16,088 行；当前混合工作树已增长到约 29,469 行。增长不等于全部冗余，但足以证明不能继续在旧侧边栏架构上叠加 v2.2。

### 1.2 最高优先级问题

| 级别 | 问题 | 证据 | 目标处理 |
|---|---|---|---|
| P0 | 两套产品架构并存 | 五空间、`CompactWorkspace`、常驻侧边栏和项目仪表盘仍是生产路径 | 删除旧用户表面，只保留对话状态和两张按需审核页 |
| P0 | ReviewSession 不权威 | `createAuthoritativeReviewSession` 只在 Node 临时创建视觉 Browser bridge | 在 Python Runtime 建立统一、可恢复、可审计的 ReviewSession |
| P0 | 视觉审核新合同缺失 | 生产代码无 `AnchorRegionFeedback`、`AnchorFeedbackBatch`、`VisualContractReviewMarkSet` | 新建视觉审核合同、服务、投影和双视图 UI |
| P0 | 内容主链仍是旧方法 | 固定生产/审查角色、framework/expansion、观点先行对象仍可创建新任务 | 新项目切换到总师 + 四对象 + 两硬门；旧对象只读 |
| P0 | 材料模式冲突 | 多处仍接受 `proposal-only`，目标是三种模式 | 统一为 `material-backed | mixed-evidence | proposal-led` |
| P0 | 经验模型冲突 | candidate/personal/stable release candidate 仍是正式链 | 切换为 same-type/global、content/visual 和 retrospective |
| P1 | 内容审核实现未接正式表面 | `ContentReviewPanel` 等组件主要只有测试引用 | 迁移成按需内容全稿审核页并连接 ReviewSession |
| P1 | MCP 多真相源 | server、测试、probe、release verifier 分别硬编码工具数量和清单 | 建立单一工具目录，注册、探针、测试和发布读取同一目录 |
| P1 | 接受台账依赖魔法数字 | 固定章节 17/21/23 和 104 条 | 使用稳定 requirement ID 和权威文档一致性校验 |
| P1 | 类型边界过宽 | `HostBridge.callTool<T>` 允许调用方任意断言返回类型 | 使用 ToolName → Input/Output 映射或 `unknown` + 边界解析 |
| P1 | 单体文件与函数 | `content_review_service.py` 3064 行，`server.mjs` 1796 行，`ProfessionalReviewApp.tsx` 863 行 | 按业务职责拆分，不增加无意义层级 |
| P2 | 明确死代码 | `GateStrip.tsx`、`SlideContactSheet.tsx`、`SpaceConclusion.tsx` 无引用 | 删除并用 `noUnusedLocals`/架构测试防回归 |
| P2 | 无效参数与重复守卫 | 13 个 `textResult` 三参数调用的第三参数被忽略；多份 `_resolve_kind`/revision guard 重复 | 删除无效参数，提取最小 artifact/revision guard |

### 1.3 当前验证基线

- 134 个 Python 文件 AST 解析通过；
- 全部 `.mjs` 通过 `node --check`；
- `git diff --check` 和 `git diff HEAD --check` 通过；
- Python 全量测试：352 项，2 failures、3 errors；主要来自 v2.2 接受台账漂移和一个过期视觉 fixture；
- Node 测试：44 项，38 passed、6 failed；Review Bridge 11 个 loopback 安全测试全部通过，失败集中在工具目录与 Browser 返回合同漂移；
- Widget 测试：62 项，58 passed、4 failed；失败证明旧五空间/内容侧边栏仍是实际路由；
- `tsc --noEmit` 有 3 个错误：测试误用 Node 全局类型 2 个，`HostBridge.callTool<T>` mock 类型错误 1 个；
- 检查前后 Git 状态一致，审计没有写入真实项目或制造新的源码变化。

## 2. 保留、迁移、兼容、删除、新增矩阵

### 2.1 直接保留并回归

| 能力 | 当前主要文件 | 处理 |
|---|---|---|
| artifact 引用与不可变存储 | `src/ai_ppt_studio/kernel/artifacts.py`, `references.py` | 保持公开合同 |
| revision、事务、重放、回滚 | `kernel/transactions.py`, `state.py` | 先保持行为，最后按纯职责拆分 |
| G0–G4 和下游 current head 清理 | `kernel/gates.py`, `application/gate_confirmation.py`, `gate_evaluator.py` | 保持 Gate 真实性和原子性 |
| 可信 Mission/G0/G3/G4 确认 | `mcp/host-confirmation-assertion.mjs`, `application/scoped_confirmation.py` | 保持一次性、版本绑定和宿主验证 |
| ReleaseTargetPolicy | `domains/presentation/release_policy.py`, `application/release_policy_service.py` | 保持 macOS PowerPoint 为当前 required target |
| 目标渲染与交付真实性 | `domains/presentation/targets.py`, `domains/delivery/contracts.py`, `delivery_service.py` | 保持 same-PPTX-hash、ChatDeliveryReceipt 和 G4 |
| Review Bridge 安全基础 | `mcp/review-bridge.mjs` | 保留 loopback、token、Origin、CSP、TTL、body limit 和原子 Runtime 写入 |
| PageDecision/Batch 已实现内核 | `domains/content/review_contracts.py`, `content_review_service.py`, `content_batch_planning_service.py` | 保留语义，拆分并迁移到新内容审核页 |
| 长文档、草稿和冲突测试资产 | `widget/src/components/content-review/`, `widget/src/content-review/` | 白名单迁移并正式接入 |

### 2.2 保留但迁移或更名

| 当前能力 | 目标身份 |
|---|---|
| `get_content_sidebar_review_projection` | `get_content_review_projection` |
| 内容侧边栏投影 | 按需 `content-full-deck` 专业审核投影 |
| 通用 `ReviewMarkSet` 视觉能力 | `VisualContractReviewMarkSet` |
| Node 临时 review session | Runtime `ReviewSession` + Node bridge transport |
| `WorkspaceProjectionService` 中有价值的状态推导 | 四种 `ProjectUserStatusProjection`，不保留空间结构 |
| 旧经验的可复用机制与证据 | `same-type` 经验版本；不得直接转 global |
| `PresalesContentStrategy` 等旧内容结果 | 一次性转换输入；转换后必须重新过两个硬门 |

### 2.3 历史只读兼容

目标目录：

- `src/ai_ppt_studio/adapters/legacy/content_v16.py`
- `src/ai_ppt_studio/adapters/legacy/experience_v16.py`
- `src/ai_ppt_studio/adapters/legacy/workspace_v16.py`

只允许：

- 解析旧 roleId、framework/expansion artifact、strategy/claim/argument/draft；
- 解析 candidate/personal/stable 历史经验；
- 生成显式迁移预览；
- 生成新权威 artifact 后重新执行目标硬门；
- 保留历史引用和审计证据。

禁止：

- 为新项目创建旧 artifact；
- 从 legacy adapter 写 Gate；
- 让新项目 orchestration 导入旧 role/action policy；
- 把历史 candidate/personal 直接标成 global；
- 将旧五空间投影继续返回给正式 Widget。

### 2.4 废止并删除

在对应替代能力通过回归后删除：

- `src/ai_ppt_studio/application/workspace_projection.py`
- `src/ai_ppt_studio/application/framework_discussion_service.py`
- `src/ai_ppt_studio/domains/content/framework.py`
- 旧 `content_action_policy.py` 固定阶段/角色链
- 旧 `content_service.py` 中 strategy/claim/argument/draft 正式写路径
- `widget/src/App.tsx`
- `widget/src/components/CompactWorkspace.tsx`
- `widget/src/components/StableNavigation.tsx`
- `widget/src/components/GateStrip.tsx`
- `widget/src/components/SlideContactSheet.tsx`
- `widget/src/components/SpaceConclusion.tsx`
- `widget/src/lib/sidebar-host-client.ts`
- `CompactWorkspace.v16.test.tsx` 及只验证五空间/侧边栏身份的测试
- MCP 工具 `get_ai_ppt_sidebar_projection`
- MCP 迁移名 `get_content_sidebar_review_projection`
- 新项目工具 `save_content_framework_draft`、`confirm_content_framework`、`authorize_full_deck_expansion`
- candidate/personal/stable release candidate 的新建、晋级和正式推荐写路径
- 13 处 `textResult` 无效第三参数
- `.superpowers/`、`.workbuddy/` 不进入产品提交；当前不删除用户现场文件。

### 2.5 v2.2 新增

- `ReviewSession` 合同与 Runtime 服务；
- 四种 Codex 用户状态投影；
- `PresalesEvidenceBook`、`CustomerDecisionContext`、`ProblemSolutionFitMap`、`ReadingDeckBlueprint`；
- 售前方案总师、两个硬门和按需顾问路由；
- `AnchorRegionFeedback`、`AnchorFeedbackBatch`、`VisualContractReviewMarkSet`；
- 同页双视图视觉审核 UI；
- 保存、宿主通知、AI 回执独立记录；
- `ExperienceItem` same-type/global 双层双域模型；
- `ProjectExperienceRetrospective` 和失败重试；
- 声明式 MCP 工具目录；
- 稳定 requirement ID 驱动的接受台账；
- TypeScript typecheck 和未使用代码质量门。

## 3. 目标文件结构

新增或重构后的关键结构：

```text
产品代码/
├── mcp/
│   ├── server.mjs                       # 依赖注入、建服、注册各工具组
│   ├── tool-catalog.mjs                 # 唯一公开工具名、schema、handler key
│   ├── tools/
│   │   ├── project-tools.mjs            # 项目、Mission、材料、对话状态
│   │   ├── content-tools.mjs            # 总师内容链和内容审核
│   │   ├── review-tools.mjs             # ReviewSession、宿主与 AI 回执
│   │   ├── visual-tools.mjs             # 视觉投影与两类反馈
│   │   └── delivery-experience-tools.mjs# 交付、策略、经验与复盘
│   └── review-bridge.mjs                # 受限 transport，不拥有业务状态
├── src/ai_ppt_studio/
│   ├── application/
│   │   ├── artifact_guards.py           # exact ref/kind/revision 最小共享守卫
│   │   ├── mission_material_service.py  # Mission 与材料模式，不拥有内容生产
│   │   ├── feedback_service.py          # capture/govern/decide/change-set
│   │   ├── project_status_projection.py # 四种 Codex 用户状态
│   │   ├── review_session_service.py    # current session、恢复、回执、supersede
│   │   ├── presales_content_service.py  # 总师四对象与修复版本
│   │   ├── content_hard_gate_service.py # 两个不可补偿硬门
│   │   ├── content_review/
│   │   │   ├── projection_service.py
│   │   │   ├── decision_service.py
│   │   │   ├── batch_service.py
│   │   │   └── planning_service.py
│   │   ├── visual_review_service.py
│   │   ├── experience_service.py        # 新双层经验正式实现
│   │   └── retrospective_service.py
│   ├── domains/
│   │   ├── content/contracts.py         # 只含 v2.2 内容对象
│   │   ├── content/page_decisions.py
│   │   ├── content/review_batches.py
│   │   ├── content/revision_plans.py
│   │   ├── review/contracts.py
│   │   ├── visual/review_contracts.py
│   │   └── experience/contracts.py      # 只含 same-type/global
│   └── adapters/legacy/
│       ├── content_v16.py
│       ├── experience_v16.py
│       └── workspace_v16.py
└── widget/src/
    ├── ReviewSurfaceRouter.tsx           # content/visual/evidence 三种表面
    ├── types/
    │   ├── tool-contracts.ts
    │   ├── review-session.ts
    │   ├── content-review.ts
    │   └── visual-review.ts
    ├── review-session/useReviewSession.ts
    ├── content-review/ContentFullDeckReviewPage.tsx
    ├── visual-review/
    │   ├── VisualProfessionalReviewPage.tsx
    │   ├── AnchorResultsView.tsx
    │   ├── RegionFeedbackEditor.tsx
    │   ├── VisualContractView.tsx
    │   └── ReviewOverlayDrawer.tsx
    ├── evidence/ContentEvidenceView.tsx
    └── styles/
        ├── base.css
        ├── content-review.css
        ├── visual-review.css
        └── evidence.css
```

目录是职责边界，不要求为每个三行函数新建文件。实施时如两个相邻文件始终同时变化且合并后仍保持单一职责，允许合并；不得反向把多个领域重新塞进 `server.mjs`、`ProfessionalReviewApp.tsx` 或 `content_review_service.py`。

## 4. 实施任务

### Task 1: 冻结现场并创建新的隔离执行基点

**Files:**

- Create: `产品代码/docs/validation/2026-08-14-v22-source-selection.md`
- Do not modify: 现有主工作区源码、`stash@{0}`、`stash@{1}`、旧 worktree、真实 Runtime

- [ ] **Step 1: 记录只读现场身份**

运行：

```bash
git status --short
git rev-parse HEAD
git worktree list --porcelain
git stash list
```

Expected: 主工作区仍指向已记录 head；两个 stash 和四个 worktree 均存在；暂存区为空。

- [ ] **Step 2: 使用 `superpowers:using-git-worktrees` 创建新隔离 worktree**

以 `3998a9694cd9c86cc3bf97b45de294c85a57109e` 为起点，创建 `codex/v22-unified-runtime` worktree。路径必须是新建的 `/private/tmp/ai-ppt-v22-*` 子目录，不能复用旧 worktree。

Expected: 新 worktree 初始干净，旧 worktree 和 stash 未改变。

- [ ] **Step 3: 写白名单来源清单**

清单逐项记录：来源是主工作区、`d7ff354`、`stash@{0}`、`stash@{1}` 或重新实现；目标文件；保留的业务语义；明确排除的旧 UI/上游规则。至少覆盖 PageDecision、ContentReviewBatch、revision plan、G0、Review Bridge、ReleaseTargetPolicy、ChatDeliveryReceipt、长文档组件和 07 原型。

- [ ] **Step 4: 建立测试 Runtime 配置**

所有执行期 Runtime profile 指向 `/private/tmp/ai-ppt-v22-runtime-*`，通过 `AI_PPT_WORKSPACE_CONFIG` 传入。配置中的 source/install/runtime roots 必须相互隔离，禁止出现 `/Users/defei/Documents/AI-PPT-Workspace`。

- [ ] **Step 5: 建立无提交检查点**

```bash
git status --short
git diff --check
```

Expected: 只有清单和后续明确迁移文件；未经授权不运行 `git commit`。

### Task 2: 先修正质量门和接受台账的真相源

**Files:**

- Modify: `产品代码/package.json`
- Modify: `产品代码/widget/tsconfig.json`
- Modify: `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`
- Modify: `产品代码/widget/src/PhaseB.test.tsx`
- Modify: `产品代码/src/ai_ppt_studio/acceptance/ledger.py`
- Modify: `产品代码/scripts/build_acceptance_ledger.py`
- Modify: `产品代码/scripts/acceptance/verify_release.py`
- Modify: `产品代码/tests/test_acceptance_ledger.py`
- Modify: `产品代码/tests/test_v16_final_acceptance_verifier.py`
- Modify: `01-产品需求基线-v1.0.md`
- Modify: `02-系统详细设计-v1.0.md`
- Modify: `03-UI设计与交互规范-v1.0.md`

- [ ] **Step 1: 写失败的质量脚本测试**

要求 `package.json` 暴露：

```json
{
  "scripts": {
    "typecheck": "tsc -p widget/tsconfig.json --noEmit",
    "test:python": "PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests",
    "quality": "npm run typecheck && npm run build && npm run test:node && npm run test:widget"
  }
}
```

Python 全量测试单独运行，避免 npm 在不同宿主上隐式选择 Python；发布/探针仍是独立外部能力检查。

- [ ] **Step 2: 运行 TypeScript 检查并确认当前失败**

```bash
npm run typecheck
```

Expected: 当前 Node 全局类型和任意泛型 HostBridge mock 错误可重现。

- [ ] **Step 3: 删除测试对 Node 全局类型的依赖**

将响应式测试改为静态导入受测 JSON fixture，不在浏览器 tsconfig 中引入 `node:fs` 或 `process`。HostBridge mock 暂时返回 `unknown`，Task 4 再切到映射类型。

- [ ] **Step 4: 给权威验收项增加稳定 ID**

不改变已批准语义，只为现有验收条目加唯一前缀，例如：

```markdown
1. [PRD-ACC-PRODUCT-001] 用户可以在同一 Codex 项目对话中完成主闭环。
1. [SDD-ACC-INTEGRATION-001] Mission 确认后无双授权直接生成完整内容。
1. [UI-ACC-REVIEW-001] 内容审核页连续显示完整全稿。
```

解析器读取显式 ID、原文和来源文件；拒绝重复 ID、缺失正文和同 ID 文本漂移。不得再从章节号推导 ID。

- [ ] **Step 5: 删除 104 和 18 魔法数字**

`verify_release.py` 改为：

```python
if not checked_in.requirements:
    raise ValueError("Final acceptance ledger is empty")
if checked_in.requirement_ids != expected.requirement_ids:
    raise ValueError("Acceptance requirement identities drifted")
```

工具数量由 Task 4 的 `tool-catalog.mjs` 生成的 probe 事实和 catalog hash 校验；Python verifier 只验证 probe 的工具数组无重复、数量与数组长度一致、catalog hash 与已安装 manifest 一致。

- [ ] **Step 6: 运行基础质量门**

```bash
npm run typecheck
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_acceptance_ledger tests.test_v16_final_acceptance_verifier
git diff --check
```

Expected: 全部 PASS；台账条数允许随权威文档变化，但 ID 和证据必须严格一致。

- [ ] **Step 7: 记录授权门**

默认只保存工作树变更。若用户后来授权提交，建议 commit message：`test: establish v2.2 quality and acceptance gates`。

### Task 3: 建立 Python 权威 ReviewSession 和四种用户状态

**Files:**

- Create: `产品代码/src/ai_ppt_studio/domains/review/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/domains/review/contracts.py`
- Create: `产品代码/src/ai_ppt_studio/application/review_session_service.py`
- Create: `产品代码/src/ai_ppt_studio/application/project_status_projection.py`
- Modify: `产品代码/src/ai_ppt_studio/kernel/state.py`
- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Create: `产品代码/tests/test_v22_review_session.py`
- Create: `产品代码/tests/test_v22_project_status_projection.py`

- [ ] **Step 1: 写 ReviewSession 合同失败测试**

最小合法 payload：

```python
session = {
    "review_session_id": "content-session-01",
    "review_type": "content-full-deck",
    "project_id": "project-01",
    "target_artifact_ref": reading_blueprint_ref,
    "source_version": "content-v3",
    "revision": 17,
    "status": "ready",
    "open_policy": "notify-only",
    "host_open_status": "not-requested",
    "persistence_status": "saved",
    "host_notification_status": "not-requested",
    "ai_receipt_status": "pending",
    "created_at": now,
    "last_opened_at": None,
    "submitted_at": None,
}
```

测试拒绝错误 review type、旧 sourceVersion、未来 revision、缺失 target ref、前端直接声明 `opened/sent/received`。

- [ ] **Step 2: 写 current session 唯一性和恢复测试**

覆盖：同 identity 重开返回同一 session；不增加第二个 current head；新 sourceVersion/revision 原子 supersede 旧 session；提交后 session 保持 current 且页面不自动关闭；证据辅助层不创建业务 session。

- [ ] **Step 3: 实现 validator 和 ReviewSessionService**

公开方法限定为：

```python
open_or_resume(...)
record_host_open_receipt(...)
record_host_notification_receipt(...)
record_ai_receipt(...)
mark_submitted(...)
supersede_current(...)
```

服务自己解析 current artifact 和 expectedRevision；Node 不拼接 session 状态。

- [ ] **Step 4: 写四状态投影测试**

投影类型：

```python
{
    "status": "AI 正在处理|需要你处理|成果已可查看|任务受阻",
    "object_type": "content-review|visual-review|gate|delivery|runtime-task",
    "object_ref": "artifact or task ref",
    "reason": "用户可读的具体事实",
    "next_action": "唯一下一步",
    "revision": 17,
}
```

验证优先级 `任务受阻 > 需要你处理 > 成果已可查看 > AI 正在处理`，以及 `notify-only` 例外不能被提前投影为“需要你处理”。

- [ ] **Step 5: 接入 bridge 读写操作**

新增 `open-or-resume-review-session`、`record-review-host-open`、`record-review-host-notification`、`record-review-ai-receipt` 和 `get-project-user-status` operation。此时先保持现有 dispatcher，Task 4 再换注册表。

- [ ] **Step 6: 运行专项测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_review_session tests.test_v22_project_status_projection tests.test_kernel_transactions
```

Expected: PASS；失败事务 revision/head/event/confirmation consumption 均不变化。

### Task 4: 建立单一 MCP 工具目录和精确 HostBridge 类型

最终公开工具目录固定为下列语义集合；catalog 数量由数组派生，不再手写数字：

```text
create_ai_ppt_project
get_ai_ppt_project_snapshot
get_ai_ppt_project_status
add_ai_ppt_material
save_ai_ppt_mission_draft
confirm_ai_ppt_mission
request_ai_ppt_agent_action
submit_ai_ppt_human_decision
commit_ai_ppt_artifact
confirm_ai_ppt_gate
reopen_ai_ppt_scope
record_internal_gate
get_delivery_status_projection
record_chat_delivery
set_ai_ppt_release_target_policy
read_ai_ppt_project_asset
build_presales_evidence_book
build_customer_decision_context
build_problem_solution_fit
build_reading_deck_blueprint
run_content_evidence_gate
run_content_presales_reading_gate
repair_reading_deck_blueprint
get_content_review_projection
save_content_page_decision
submit_content_review_batch
withdraw_content_review_batch
save_content_batch_revision_plan
confirm_content_batch_revision_plan
create_content_batch_change_set
open_or_resume_review_session
record_review_host_open_receipt
record_review_host_notification_receipt
record_review_ai_receipt
open_content_evidence_browser
get_visual_review_projection
submit_visual_anchor_feedback_batch
save_visual_contract_review_marks
recommend_experience
record_experience_application
summarize_project_experience
```

`commit_ai_ppt_artifact` 只保留给已绑定 AgentTask 的视觉/交付等现有受治理 artifact 写入，不得成为四个内容对象、ReviewSession、审核反馈或经验的第二条写路径。后续若所有调用者都已迁移为精确工具，应通过独立兼容评审再删除，不能在本计划中无证改变仍被使用的视觉/交付合同。

**Files:**

- Create: `产品代码/mcp/tool-catalog.mjs`
- Create: `产品代码/mcp/tools/project-tools.mjs`
- Create: `产品代码/mcp/tools/content-tools.mjs`
- Create: `产品代码/mcp/tools/review-tools.mjs`
- Create: `产品代码/mcp/tools/visual-tools.mjs`
- Create: `产品代码/mcp/tools/delivery-experience-tools.mjs`
- Modify: `产品代码/mcp/server.mjs`
- Modify: `产品代码/scripts/probe-mcp.mjs`
- Modify: `产品代码/tests/mcp-server.test.mjs`
- Create: `产品代码/widget/src/types/tool-contracts.ts`
- Modify: `产品代码/widget/src/types.ts`
- Modify: `产品代码/widget/src/main.tsx`

- [ ] **Step 1: 写目录一致性失败测试**

断言：工具名唯一；每个工具有 schema 和 handler key；server、probe 和 tests 导入同一个 `PUBLIC_TOOL_CATALOG`；正式 probe 不再维护第二份 `requiredTools` 数组。

- [ ] **Step 2: 定义声明式目录**

以下代码展示目录形状；正式数组必须逐项覆盖本 Task 开头列出的全部工具。每项只包含真正共享的元数据：

```js
export const PUBLIC_TOOL_CATALOG = Object.freeze([
  { name: "get_ai_ppt_project_snapshot", group: "project", handler: "getSnapshot" },
  { name: "get_ai_ppt_project_status", group: "project", handler: "getUserStatus" },
  { name: "open_or_resume_review_session", group: "review", handler: "openOrResume" },
  { name: "get_content_review_projection", group: "content", handler: "getReviewProjection" },
  { name: "submit_visual_anchor_feedback_batch", group: "visual", handler: "submitAnchorBatch" },
  { name: "save_visual_contract_review_marks", group: "visual", handler: "saveContractMarks" }
]);
```

Zod schema 与 handler 可以在对应 group 文件中，catalog 不复制业务实现。

- [ ] **Step 3: 拆分 server 注册逻辑**

`server.mjs` 只保留依赖解析、共享确认流程、server 构造和五个 `register*Tools` 调用。删除 13 个被静默忽略的 `textResult` 第三参数；`textResult` 保持单一签名。

- [ ] **Step 4: 建立 ToolContractMap**

```ts
export interface ToolContractMap {
  get_content_review_projection: {
    input: { projectRoot: string; reviewSessionId: string };
    output: ContentReviewProjection;
  };
  submit_visual_anchor_feedback_batch: {
    input: SubmitAnchorFeedbackBatchInput;
    output: SubmitAnchorFeedbackBatchResult;
  };
}

export interface HostBridge {
  callTool<K extends keyof ToolContractMap>(
    name: K,
    args: ToolContractMap[K]["input"],
  ): Promise<ToolContractMap[K]["output"]>;
}
```

未经映射的动态宿主返回先是 `unknown`，通过边界 parser 后再进入 React；调用方不能用任意泛型伪造类型。

- [ ] **Step 5: 运行工具和类型测试**

```bash
npm run typecheck
node --test tests/mcp-server.test.mjs tests/mcp-runtime-bridge.test.mjs
```

Expected: PASS；工具数量来自 catalog 长度，不出现 18/26 等硬编码。

### Task 5: 建立 v2.2 内容对象、三种材料模式和总师角色

**Files:**

- Replace: `产品代码/src/ai_ppt_studio/domains/content/contracts.py`
- Create: `产品代码/src/ai_ppt_studio/application/presales_content_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/mission_readiness.py`
- Create: `产品代码/src/ai_ppt_studio/application/mission_material_service.py`
- Create: `产品代码/src/ai_ppt_studio/application/feedback_service.py`
- Modify: `产品代码/src/ai_ppt_studio/role_registry.py`
- Modify: `产品代码/src/ai_ppt_studio/scenario_packs.py`
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Create: `产品代码/tests/test_v22_content_contracts.py`
- Create: `产品代码/tests/test_v22_presales_chief.py`
- Modify: `产品代码/tests/test_role_registry.py`
- Modify: `产品代码/tests/test_context_compiler_governance.py`

- [ ] **Step 1: 写四对象 validator 失败测试**

按 SDD 第 8 节逐字段验证四对象。重点拒绝：`desiredCustomerJudgment`、`coreClaim`、无来源事实、错误 material mode、无证强结论标题、映射缺失问题/要求/方案/身份/证据。

- [ ] **Step 2: 写三种模式全链测试**

参数化测试：

```python
for mode in ("material-backed", "mixed-evidence", "proposal-led"):
    result = service.build_reading_blueprint(..., material_mode=mode)
    self.assertEqual(result["material_mode"], mode)
```

`proposal-led` 必须输出诊断假设、方案建议、验证问题和联合动作；不得生成客户事实、数字、案例或效果承诺。删除新流程中的 `proposal-only`。

- [ ] **Step 3: 重写正式角色表**

新建任务只允许：

```python
presales-solution-chief
content-evidence-gate-reviewer
content-presales-reading-gate-reviewer
presales-risk-specialist/*
```

旧 roleId 只由 legacy adapter 解析，不进入 `scenario_packs.py` 的正式 production/review 列表。

- [ ] **Step 4: 实现四对象顺序写入**

每次写入验证 exact upstream refs 和 expectedRevision，更新目标 current head。总师不能写硬门 passed、可信确认或视觉 artifact。

同时把当前 `content_service.py` 中 Mission draft/confirmation、材料登记与反馈 capture/govern/decide/change-set 分别迁入 `mission_material_service.py` 和 `feedback_service.py`；保持现有可信确认、反馈治理和 G0/G3 回归测试，不让新总师服务重新吞并这些职责。

- [ ] **Step 5: 收窄 ContextCompiler**

总师上下文只含 Mission/材料、当前上游对象、sourceVersion、匹配经验、硬门修复、当前审核批次/方案、排除项和权限；移除旧固定角色表、说服命题和 desired judgment。

- [ ] **Step 6: 运行内容对象和角色测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_contracts tests.test_v22_presales_chief tests.test_role_registry tests.test_context_compiler_governance
```

Expected: PASS；三种模式都能生成完整 `ReadingDeckBlueprint`。

### Task 6: 实现两个不可补偿内容硬门和修复循环

**Files:**

- Create: `产品代码/src/ai_ppt_studio/application/content_hard_gate_service.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/content/contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/application/presales_content_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/project_service.py`
- Create: `产品代码/tests/test_v22_content_hard_gates.py`
- Create: `产品代码/tests/test_v22_content_repair_loop.py`

- [ ] **Step 1: 写硬门真实性测试**

`ContentHardGateRecord` 的 `overall_result` 只能是 passed/failed；任一适用 hard item failed 则整体 failed。`reviewer_mode=independent-agent` 必须有实例 ID、context hash、input hash 和输出 ref；证据缺失时只能标为 `isolated-review-task`。

- [ ] **Step 2: 写 reviewer 权限失败测试**

审查任务只能提交 `content-hard-gate-record`，尝试写 `ReadingDeckBlueprint` 必须得到稳定权限错误，且事务零写入。

- [ ] **Step 3: 实现两个 gate evaluator**

事实与证据硬门覆盖来源、排除、身份、诊断/方案追溯、选择性取证、因果跳跃、能力/承诺和模式诚实性。售前阅读硬门覆盖客户立场、问题完整性、映射、中立标题、独立阅读、连贯性、重复、边界、风险和下一步。

- [ ] **Step 4: 实现总师修复循环**

失败记录只提供结构化 `repair_requirements`；总师写新 sourceVersion；受影响硬门按依赖重跑；两个 current gate record 都 passed 后才写 `content/acceptance`。

- [ ] **Step 5: 运行专项与 G0 防绕过测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_hard_gates tests.test_v22_content_repair_loop tests.test_v16_content_acceptance tests.test_v16_gate_confirmation
```

Expected: PASS；旧内容 acceptance 不能绕过两个新硬门进入 G0。

### Task 7: 把现有内容审核内核迁移为按需全稿审核页

**Files:**

- Create: `产品代码/src/ai_ppt_studio/domains/content/page_decisions.py`
- Create: `产品代码/src/ai_ppt_studio/domains/content/review_batches.py`
- Create: `产品代码/src/ai_ppt_studio/domains/content/revision_plans.py`
- Create: `产品代码/src/ai_ppt_studio/application/content_review/projection_service.py`
- Create: `产品代码/src/ai_ppt_studio/application/content_review/decision_service.py`
- Create: `产品代码/src/ai_ppt_studio/application/content_review/batch_service.py`
- Create: `产品代码/src/ai_ppt_studio/application/content_review/planning_service.py`
- Remove after cutover: `产品代码/src/ai_ppt_studio/application/content_review_service.py`
- Remove after cutover: `产品代码/src/ai_ppt_studio/application/content_batch_planning_service.py`
- Remove after callers migrate: `产品代码/src/ai_ppt_studio/domains/content/review_contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/application/gate_confirmation.py`
- Create: `产品代码/tests/test_v22_content_review_projection.py`
- Migrate: `产品代码/tests/test_v16_content_page_decisions.py`
- Migrate: `产品代码/tests/test_v16_content_review_batch.py`
- Migrate: `产品代码/tests/test_v16_content_batch_planning.py`
- Migrate: `产品代码/tests/test_v16_content_revision_round.py`

- [ ] **Step 1: 写新上游投影失败测试**

只有 current `ReadingDeckBlueprint` 且两个 gate record passed、`content/acceptance` current 时可投影。测试明确证明 framework confirmation 和 full-deck authorization 均不存在仍可进入 review ready。

- [ ] **Step 2: 白名单迁移 PageDecision 语义**

保持：四选一、非 approved comment 必填、1200 Unicode code points、单页原子保存、无模型调用、无治理、无蓝图修改、无 Gate 变化、重放幂等和 sourceVersion/revision 冲突。

- [ ] **Step 3: 白名单迁移 Batch/Plan/G0 语义**

保持：全页完成才提交、submitted 不可改、撤回/替代 lineage、总师先给整套方案、可信方案确认、生成新 sourceVersion、全篇复审、不继承旧决定、最终 current-source applied batch 才开放 G0 context。

- [ ] **Step 4: 拆分 3064 行服务和 1237 行合同**

按投影、单页判断、批次、整套方案四个职责拆分。共享只提取 `artifact_guards.py` 中的 exact ref/kind/revision；领域规则留在对应模块，禁止形成万能 base service。

- [ ] **Step 5: 连接 ReviewSession**

投影输入必须含 `review_session_id`，并验证 session target ref/sourceVersion/revision。发布新蓝图时原子 supersede 旧内容 session；已保存 PageDecision 保留历史，前端未保存草稿提示重新绑定。

- [ ] **Step 6: 运行内容审核全链测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_content_review_projection tests.test_v16_content_page_decisions tests.test_v16_content_review_batch tests.test_v16_content_batch_planning tests.test_v16_content_revision_round tests.test_v16_gate_confirmation
```

Expected: PASS；没有 framework/expansion 前置门，G0 仍严格绑定最终 current source。

### Task 8: 将现有内容组件接入正式 ContentFullDeckReviewPage

**Files:**

- Create: `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- Migrate: `产品代码/widget/src/components/content-review/*.tsx`
- Modify: `产品代码/widget/src/lib/content-review-client.ts`
- Create: `产品代码/widget/src/types/content-review.ts`
- Modify: `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- Create: `产品代码/widget/src/styles/content-review.css`
- Create: `产品代码/widget/src/styles/evidence.css`
- Modify: `产品代码/widget/src/styles.css`（迁移期入口，Task 14 删除）
- Migrate: `产品代码/widget/src/content-review/*.test.tsx`

- [ ] **Step 1: 写按需页面路由失败测试**

输入 `surface=content-full-deck` 和 current ReviewSession 时渲染全稿；没有五空间导航、项目仪表盘、内容空间标题、聊天复制或 Gate 按钮。

- [ ] **Step 2: 迁移完整阅读组件**

保持最终顺序、完整可见文字、真实材料、来源定位、用途、证据身份/缺口、备注、阅读质量和跨页关系。显示 `neutral_title`，不显示 desired customer judgment。

- [ ] **Step 3: 迁移逐页编辑和批次提交**

保存失败保留选择和文本；revision/source conflict 显示稳定错误；页面提交后不自动关闭；整套提交只冻结 batch 并显示真实 persistence receipt。

- [ ] **Step 4: 保持证据层只读**

证据页绑定 parent review session、slide/evidence/material refs；关闭后恢复滚动、编辑器草稿和当前页；不得建立第二套 PageDecision。

- [ ] **Step 5: 验证 60 页和响应式**

```bash
npx vitest run widget/src/content-review/ContentReviewDocument.test.tsx widget/src/content-review/PageDecisionEditor.test.tsx widget/src/content-review/ContentReviewLongDeck.test.tsx widget/src/content-review/ContentReviewResponsive.test.tsx widget/src/content-review/ContentEvidenceBrowser.test.tsx
npm run typecheck
```

Expected: PASS；宽屏使用全部可用宽度，窄屏无横向溢出，长稿不丢草稿。

### Task 9: 建立视觉审核领域合同与 Runtime 服务

**Files:**

- Create: `产品代码/src/ai_ppt_studio/domains/visual/review_contracts.py`
- Create: `产品代码/src/ai_ppt_studio/application/visual_review_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/visual_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/review_session_service.py`
- Create: `产品代码/tests/test_v22_visual_review_contracts.py`
- Create: `产品代码/tests/test_v22_visual_review_service.py`

- [ ] **Step 1: 写 AnchorRegionFeedback 失败测试**

验证 normalized region 的 x/y/width/height 均在 0–1，区域有可感知最小宽高，comment trim 后非空，anchor ref、visual sourceVersion 和 revision 精确匹配；单点坐标合同必须失败。

- [ ] **Step 2: 写不可变 AnchorFeedbackBatch 测试**

多条草稿可编辑/删除；提交后 items 顺序固定且不可变；空批次失败；source conflict 零写入。状态初始：

```python
{
    "persistence_status": "saved",
    "host_notification_status": "not-requested",
    "ai_receipt_status": "pending",
    "immutable_after_submit": True,
}
```

- [ ] **Step 3: 写 VisualContractReviewMarkSet 测试**

支持 `contract-field | text-range`；保存时保留 selected text、上下文、target key 和当前 visual contract identity。它使用独立 slot、command identity 和保存操作，不能覆盖 AnchorFeedbackBatch。

- [ ] **Step 4: 实现 VisualReviewProjection**

从同一 current visual contract/DeckDesignSystem/G1/G2/anchor artifacts 投影两个 view；包含真实 host submission capability 和 ai receipt capability；不从前端内存或 timer 推断状态。

- [ ] **Step 5: 运行视觉领域测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_visual_review_contracts tests.test_v22_visual_review_service tests.test_v16_visual_contracts tests.test_v16_visual_gates
```

Expected: PASS；保存两类反馈均不改变 G3。

### Task 10: 实现视觉双视图专业审核页

**Files:**

- Create: `产品代码/widget/src/types/visual-review.ts`
- Create: `产品代码/widget/src/visual-review/VisualProfessionalReviewPage.tsx`
- Create: `产品代码/widget/src/visual-review/AnchorResultsView.tsx`
- Create: `产品代码/widget/src/visual-review/RegionFeedbackEditor.tsx`
- Create: `产品代码/widget/src/visual-review/VisualContractView.tsx`
- Create: `产品代码/widget/src/visual-review/ReviewOverlayDrawer.tsx`
- Create: `产品代码/widget/src/visual-review/*.test.tsx`
- Remove after callers migrate: `产品代码/widget/src/ProfessionalReviewApp.tsx`
- Remove after callers migrate: `产品代码/widget/src/components/review/ReviewDocumentSections.tsx`
- Create: `产品代码/widget/src/styles/visual-review.css`
- Modify: `产品代码/widget/src/styles.css`（迁移期入口，Task 14 删除）
- Reference only: `产品代码/prototypes/07-visual-anchor-chat-collaboration-prototype.html`

- [ ] **Step 1: 写双视图和无导航失败测试**

页面顶部只有 `3 页锚点成果` / `完整视觉合同` 两个审核对象；不显示五空间图标、常驻侧边栏、聊天流、PPTX 下载和 Gate 按钮。

- [ ] **Step 2: 实现矩形框选和就地输入**

pointer drag 生成 normalized rectangle；小于最小尺寸的 drag 取消；输入框紧邻当前幻灯片；一条记录必须同时有区域和非空意见；提交前可编辑/移除；支持多条统一提交。

- [ ] **Step 3: 实现完整合同连续阅读**

先显示 Deck Design System，再按稳定页序显示全部逐页合同；目录为覆盖式 drawer，不压缩正文；字段和选中文字标记进入覆盖式 mark drawer；顶部统一保存。

- [ ] **Step 4: 隔离两类草稿与保存状态**

切换视图不丢草稿；anchor batch 和 contract marks 使用独立 reducer/local draft key/Runtime action；任一保存不能清空另一类草稿。

- [ ] **Step 5: 显示三种真实状态**

UI 分别显示 persistence、host notification、AI receipt。只有 Runtime 返回 `saved` 才显示已保存；只有真实 receipt 才显示 `sent/received`；能力不存在时显示 unavailable/unverified。

- [ ] **Step 6: 运行视觉 UI 测试**

```bash
npx vitest run widget/src/visual-review/*.test.tsx
npm run typecheck
npm run build
```

Expected: PASS；21 页以上合同可连续阅读，选择定位和两个 drawer 行为稳定。

### Task 11: 扩展 Review Bridge，但不把业务状态搬到 Node

**Files:**

- Modify: `产品代码/mcp/review-bridge.mjs`
- Modify: `产品代码/mcp/tools/review-tools.mjs`
- Modify: `产品代码/mcp/tools/visual-tools.mjs`
- Modify: `产品代码/widget/src/lib/browser-review-client.ts`
- Modify: `产品代码/tests/review-bridge.test.mjs`
- Modify: `产品代码/tests/mcp-server.test.mjs`

- [ ] **Step 1: 写安全回归和新 route 失败测试**

保留现有 11 个 loopback 安全断言，并新增内容 decision/batch、anchor batch、contract marks、host open receipt 和 AI receipt route。未知 route、跨 Origin、错误 token、过大 body、过期 session 和 stale revision 都必须失败。

- [ ] **Step 2: 让 bridge 持有 transport identity，不持有业务 state**

所有 POST 只将经过 scope 校验的 request 转为一次 Python operation。Runtime 返回 authoritative result 后才响应成功；Node 不本地推进 batch/session/receipt 状态。

- [ ] **Step 3: 记录真实打开事实**

Browser 成功加载 scoped page 并读取 `/api/review` 后，bridge 可提交带 bridge session identity 的 host-open receipt；仅创建 URL 不得标记 opened。host adapter 返回失败或能力缺失时分别记录 failed/unavailable。

- [ ] **Step 4: 约束通知与 AI 回执**

没有宿主 notification adapter 时，保存仍可成功，但 notification=unavailable、AI receipt=unverified。`received` 只接受宿主验证的 receipt identity，不能由 timer、页面轮询或“保存成功”推导。

- [ ] **Step 5: 运行 loopback 测试**

```bash
node --test tests/review-bridge.test.mjs tests/mcp-server.test.mjs
```

Expected: 全部 PASS；如沙箱禁止 loopback，使用匹配权限重跑，不改源代码规避安全测试。

### Task 12: 切换到 same-type/global 双层双域经验系统

**Files:**

- Replace: `产品代码/src/ai_ppt_studio/domains/experience/contracts.py`
- Replace: `产品代码/src/ai_ppt_studio/application/experience_service.py`
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Modify: `产品代码/src/ai_ppt_studio/experience_models.py`
- Modify: `产品代码/src/ai_ppt_studio/experience_store.py`
- Create: `产品代码/src/ai_ppt_studio/adapters/legacy/experience_v16.py`
- Create: `产品代码/tests/test_v22_experience_contracts.py`
- Create: `产品代码/tests/test_v22_experience_realtime.py`
- Create: `产品代码/tests/test_v22_experience_promotion.py`

- [ ] **Step 1: 写新 ExperienceItem 合同测试**

只允许 `layer=same-type|global`、`domain=content|visual`、`result_type=mechanism|anti-pattern|preference`；要求 source refs、before/after refs、hard gate/user outcomes、privacy 和 `sanitized_for_reuse=true`。

- [ ] **Step 2: 写隐私和事实隔离测试**

客户名称、事实、数字、Logo、截图、图片和整页造型进入可复用 experience 必须失败。经验不能修改产品制度、Gate、权限和事实硬门。

- [ ] **Step 3: 实现实时 same-type 吸收**

从 PageDecision/Batch、hard gate、G0/G3/G4、视觉 marks、PowerPoint 渲染缺陷和中止原因提炼可复用机制；记录精确应用版本和后续结果；一次明确有效反馈即可影响当前后续工作和下一匹配项目。

- [ ] **Step 4: 实现 global 进入和反例回退**

global 只允许用户明确全局指令，或至少两个不同 type signature 的真实成功且无反例。一次明确反例停止冲突 scope 自动应用，并创建降级/拆分/回退新版本。

- [ ] **Step 5: 实现旧经验只读迁移**

candidate/personal 可转换为 same-type 草稿，保留来源和旧 ref；stable release candidate 不自动变 global；未正式评价的旧应用不计成功。删除新建/晋级 stable capability 的正式路径。

- [ ] **Step 6: 运行经验测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_experience_contracts tests.test_v22_experience_realtime tests.test_v22_experience_promotion tests.test_experience_store
```

Expected: PASS；旧数据可读，新项目不写旧层级。

### Task 13: 实现项目完结/关闭/中止复盘

**Files:**

- Create: `产品代码/src/ai_ppt_studio/application/retrospective_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/delivery_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/project_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/project_status_projection.py`
- Create: `产品代码/tests/test_v22_project_retrospective.py`

- [ ] **Step 1: 写三个触发路径测试**

G4 passed、用户正式关闭和项目中止分别进入 `queued -> running -> completed`。同一完成 identity 重放不创建重复 retrospective。

- [ ] **Step 2: 写失败和重试测试**

复盘失败不回滚 G4/关闭结果；写 `pending-retry` 或 `failed-with-evidence`；用户状态能准确显示自动重试或真实受阻；不得静默完成。

- [ ] **Step 3: 实现 retrospective 输出**

包含 project type signature、content/visual findings、接受/拒绝机制、before/after、用户结果、Gate/render、same-type/global 变更和下一项目建议。`completion_kind=aborted` 时禁止生成 success evaluation。

- [ ] **Step 4: 运行复盘测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_project_retrospective tests.test_v16_delivery_g4
```

Expected: PASS；复盘与交付事务边界正确。

### Task 14: 下线五空间、常驻侧边栏和旧内容写路径

**Files:**

- Remove: `产品代码/src/ai_ppt_studio/application/workspace_projection.py`
- Remove: `产品代码/src/ai_ppt_studio/application/framework_discussion_service.py`
- Remove: `产品代码/src/ai_ppt_studio/domains/content/framework.py`
- Remove after new call sites pass: `产品代码/src/ai_ppt_studio/application/content_action_policy.py`
- Remove after Mission、材料、反馈、总师与 G0 call sites migrate: `产品代码/src/ai_ppt_studio/application/content_service.py`
- Create: `产品代码/src/ai_ppt_studio/adapters/legacy/content_v16.py`
- Create: `产品代码/src/ai_ppt_studio/adapters/legacy/workspace_v16.py`
- Remove: `产品代码/widget/src/App.tsx`
- Remove: `产品代码/widget/src/components/CompactWorkspace.tsx`
- Remove: `产品代码/widget/src/components/StableNavigation.tsx`
- Remove: `产品代码/widget/src/components/GateStrip.tsx`
- Remove: `产品代码/widget/src/components/SlideContactSheet.tsx`
- Remove: `产品代码/widget/src/components/SpaceConclusion.tsx`
- Remove: `产品代码/widget/src/lib/sidebar-host-client.ts`
- Remove after type modules migrate: `产品代码/widget/src/types.ts`
- Remove after CSS imports migrate: `产品代码/widget/src/styles.css`
- Create: `产品代码/widget/src/styles/base.css`
- Modify: `产品代码/widget/src/main.tsx`
- Remove/replace: 五空间与侧边栏身份测试
- Create: `产品代码/tests/test_v22_source_shape.py`
- Create: `产品代码/widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: 写 source-shape 失败测试**

生产源码不得出现正式 `SpaceId`、overview/materials/blueprint/visual/delivery 导航表、`CompactWorkspace`、`get_ai_ppt_sidebar_projection`、新项目 framework/expansion operation。legacy adapter 中的历史字符串允许，但不得被正式 service/bridge import。

- [ ] **Step 2: 切换正式入口**

`main.tsx` 只路由：`content-full-deck`、`visual-professional`、`content-evidence-read-only`。无 ReviewSession 的普通 Codex 对话不挂载 AI PPT Studio Widget。

- [ ] **Step 3: 删除旧用户表面和明确死代码**

删除上列 React 组件、旧 CSS selector、fixture 和只验证旧导航的测试；`main.tsx` 直接导入 `base.css` 及当前专业表面样式。保留 release target 证据的 Runtime/Review 投影，不因删除 Delivery 页而删除交付能力。

- [ ] **Step 4: 切断旧内容写路径**

新项目 dispatcher、MCP catalog、role registry 和 scenario pack 不再暴露 framework/expansion/strategy/claim/argument/draft 写入。历史 resolver 移入 legacy adapter；一次性迁移后重新过目标硬门。

- [ ] **Step 5: 启用未使用代码检查**

在 `widget/tsconfig.json` 启用：

```json
{
  "noUnusedLocals": true,
  "noUnusedParameters": true,
  "noFallthroughCasesInSwitch": true
}
```

不要用下划线、空引用或禁用注释掩盖真死代码；确需保留的回调参数应由接口证明。

- [ ] **Step 6: 运行架构与 UI 路由测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_source_shape tests.test_legacy_importer
npx vitest run widget/src/ReviewSurfaceRouter.test.tsx widget/src/content-review/*.test.tsx widget/src/visual-review/*.test.tsx
npm run typecheck
```

Expected: PASS；生产路径只剩一套 v2.2 产品表面。

### Task 15: 拆分 Python dispatcher、kernel 热点和重复守卫

**Files:**

- Create: `产品代码/src/ai_ppt_studio/application/artifact_guards.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/project.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/content.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/review.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/visual.py`
- Create: `产品代码/src/ai_ppt_studio/application/bridge/delivery_experience.py`
- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `产品代码/src/ai_ppt_studio/kernel/transactions.py`
- Create: `产品代码/src/ai_ppt_studio/kernel/persistence.py`
- Create: `产品代码/src/ai_ppt_studio/kernel/confirmation_history.py`
- Modify: `产品代码/src/ai_ppt_studio/application/visual_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/delivery_service.py`
- Modify: `产品代码/tests/test_v16_bridge.py`
- Modify: `产品代码/tests/test_kernel_transactions.py`

- [ ] **Step 1: 写行为等价测试**

对每个公开 operation 断言：同 input、同 result shape、同 error code、同 revision/head/event side effects；command replay 返回原结果；失败保持零写入。

- [ ] **Step 2: 将 141 分支 dispatcher 改为显式 handler map**

```python
HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "get-project-user-status": get_project_user_status,
    "open-or-resume-review-session": open_or_resume_review_session,
    "build-presales-evidence-book": build_presales_evidence_book,
}
```

未知 operation 返回单一稳定错误；不得用动态 import、反射或名称拼接隐藏可审计性。

- [ ] **Step 3: 提取最小 artifact guards**

只提取完全重复的 exact ref/kind/head 和 expectedRevision 检查；领域 lineage、Gate 和业务状态校验留在服务内。删除 visual/delivery/experience 的重复 `_resolve_kind`、`_require_exact_ref` 和 revision guard。

- [ ] **Step 4: 拆分事务持久化与历史迁移纯职责**

`ProjectKernel.commit` 保持唯一公开事务入口；文件写入/rollback 进入 `kernel/persistence.py`，旧 confirmation/framework 迁移解析进入 `confirmation_history.py`。不改变锁范围、落盘顺序、回滚和 state snapshot 校验。

- [ ] **Step 5: 运行内核和 bridge 全量回归**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_kernel_transactions tests.test_v16_bridge tests.test_v16_project_service tests.test_v16_delivery_bridge tests.test_v16_visual_bridge
```

Expected: PASS；`ProjectKernel.commit` 行为完全一致，dispatcher 不再包含长 if/elif 链。

### Task 16: 更新 Skill、文档、原型引用、探针和发布合同

**Files:**

- Modify: `产品代码/skills/ai-ppt-studio/SKILL.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/experience-evolution.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/review-and-feedback.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/visual-workflow.md`
- Modify: `产品代码/scripts/create-widget-preview.mjs`
- Modify: `产品代码/scripts/run-v16-ui-acceptance.mjs`
- Modify: `产品代码/scripts/probe-mcp.mjs`
- Modify: `产品代码/tests/test_skill_workflow.py`
- Modify: `产品代码/tests/test_v16_support_scripts.py`
- Create: `产品代码/docs/validation/2026-08-14-v22-automated-validation.md`

- [ ] **Step 1: 写禁止旧产品语言的测试**

Skill 和正式 references 不得指导使用五空间、常驻侧边栏、framework confirmation、full deck authorization、固定内容多智能体、proposal-only、candidate/personal/stable 经验。历史 spec 可以保留但必须标明废止身份。

- [ ] **Step 2: 更新正式工作流**

写清：Codex 对话唯一入口、四种状态、两个按需审核页、三种材料模式、总师四对象、两个硬门、内容 Batch/Plan/G0、视觉双视图、两类反馈、same-type/global、retrospective、Presentations 和 ReleaseTargetPolicy。

- [ ] **Step 3: 更新 preview 和 UI acceptance**

preview 只生成内容审核、视觉审核和证据层，不再生成五空间 Widget。视觉 preview 复用 07 原型的已确认交互，不复制示例客户数据为 Runtime fixture。

- [ ] **Step 4: 更新 probe 能力边界**

probe 从 tool catalog 读取清单；报告 ReviewSession、content/visual professional review、host open/notification/AI receipt capability；没有真实宿主时准确显示 unavailable/unverified，不宣称验收通过。

- [ ] **Step 5: 验证相对链接和原型**

```bash
test -f 'prototypes/07-visual-anchor-chat-collaboration-prototype.html'
rg -n '\]\(\./产品代码/prototypes/07-visual-anchor-chat-collaboration-prototype.html\)' '../03-UI设计与交互规范-v1.0.md'
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_skill_workflow tests.test_v16_support_scripts tests.test_package_shape tests.test_skill_bundle
```

Expected: 文件存在、相对链接可解析、Skill/package tests PASS。

### Task 17: 隔离全量验证与删减审计

**Files:**

- Create/Update: `产品代码/docs/validation/2026-08-14-v22-automated-validation.md`
- Do not write: `/Users/defei/Documents/AI-PPT-Workspace`

- [ ] **Step 1: 运行静态和类型检查**

```bash
git diff --check
npm run typecheck
python3 -c 'import ast,pathlib; [ast.parse(p.read_text(encoding="utf-8"), filename=str(p)) for p in pathlib.Path("src").rglob("*.py")]'
find mcp scripts tests -name '*.mjs' -exec node --check {} \;
```

Expected: 全部零退出；不生成受保护目录写入。

- [ ] **Step 2: 运行 Python 全量测试**

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests
```

Expected: 全部 PASS，无 acceptance ledger 漂移，无过期 G2 fixture。

- [ ] **Step 3: 运行 Node、Widget 和 build**

```bash
npm run build
npm run test:node
npm run test:widget
```

Expected: 全部 PASS；Review Bridge loopback 安全测试保持通过。

- [ ] **Step 4: 运行隔离 Runtime E2E**

在 `/private/tmp/ai-ppt-v22-runtime-*` 分别创建 material-backed、mixed-evidence、proposal-led 三个项目，覆盖四对象、两个硬门、内容 ReviewSession、PageDecision/Batch/Plan/新版/G0、视觉双视图投影、两类反馈、G3、交付和 retrospective。不得把 fixture 结果登记为真实客户或正式宿主证据。

- [ ] **Step 5: 运行代码删减审计**

验证：

```bash
rg -n 'CompactWorkspace|StableNavigation|get_ai_ppt_sidebar_projection|content-sidebar|proposal-only|awaiting-full-deck-authorization' src mcp widget/src skills/ai-ppt-studio
rg -n 'candidate|personal|stable-release-candidate' src/ai_ppt_studio/application src/ai_ppt_studio/domains
```

Expected: 第一组在正式生产路径零命中；第二组只允许 legacy adapter、迁移测试或普通英文“候选值”语义，不存在旧经验正式写路径。

- [ ] **Step 6: 比较运行代码规模和职责**

记录迁移前后产品运行代码行数、删除文件、最大文件/函数、公共工具数和重复守卫数。成功条件不是任意压到某个行数，而是：旧表面和旧写链实际删除、单一 catalog、单一 ReviewSession、无死组件、热点按职责缩小，且全量测试通过。

- [ ] **Step 7: 确认真实项目零影响**

对照 Task 1 清单确认：主工作区、旧 worktree、两个 stash、真实 PPT Runtime、并行 Web 产品线和正式插件均未被测试修改。只读读取真实状态也不得在本阶段转成 formal acceptance。

- [ ] **Step 8: 请求代码审查并等待用户授权下一 Gate**

使用 `superpowers:requesting-code-review` 检查整个隔离 diff，重点审查事务回归、历史读取、Gate/receipt 真实性、旧路径是否真正切断和新增抽象是否必要。未经用户单独授权，不 commit、不合并、不安装插件、不写真实项目。

## 5. v2.2 需求覆盖矩阵

| 需求 | 任务 |
|---|---|
| MIS-001/002：Mission 与可信确认 | Tasks 3–5、15–17 |
| MIS-003：三种材料模式 | Tasks 5、17 |
| MAT-001/002/003：材料、来源、冲突/缺口/排除 | Tasks 5–6、17 |
| CNT-001–006：总师、四对象、三种模式身份 | Task 5 |
| CNT-007–009：两个硬门与修复 | Task 6 |
| CNT-010/011：按需顾问与高影响 RevisionProposal | Tasks 5–6 |
| CNT-012：中立标题 | Tasks 5–6、8 |
| REV-001–008：全稿、PageDecision、Batch、Plan、新版、证据、G0 | Tasks 7–8 |
| REV-009：按需内容审核会话 | Tasks 3、7–8、11 |
| VIS-001/002：视觉合同和 G1/G2 | Tasks 9–11，保留既有 VisualService/Gate 回归 |
| VIS-003–005：视觉双视图、矩形批次、合同标记 | Tasks 9–11 |
| VIS-006：按需视觉审核会话 | Tasks 3、9–11 |
| DEL-001：Presentations 唯一路线 | Tasks 16–17，保留现有执行合同 |
| DEL-002：ReleaseTargetPolicy | Tasks 2、15–17，保留现有服务 |
| DEL-003：G4 真实证据与聊天交付 | Tasks 13、15–17，保留现有真实性链 |
| EXP-001–004：same-type/global 与实时应用 | Task 12 |
| EXP-005：ProjectExperienceRetrospective | Task 13 |
| EXP-006：冲突、降级和回退 | Task 12 |
| 对话唯一入口和四种状态 | Tasks 3、14、16 |
| 删除五空间、常驻侧边栏和旧页面 | Task 14 |
| 保存/通知/AI 回执事实分离 | Tasks 3、9–11 |
| 单一工具清单和精确类型 | Tasks 2、4 |
| 历史只读兼容 | Tasks 12、14–15、17 |
| 代码简洁、去重、死代码删除 | Tasks 4、7、10、14–15、17 |

## 6. 计划自审结果

### 6.1 需求覆盖

四份 v2.2 基线的 P0/P1 功能均映射到具体任务。视觉角色组织方式没有被擅自重构；真实宿主行为、AI 回执格式、长文档性能阈值、经验 top-N 和硬门成本上限仍通过自动测试与后续真实 Gate 验证，不被写成已证明事实。

### 6.2 单一真相源

- 产品主入口只有 Codex 当前项目对话；
- 用户结构化表面只有内容全稿审核页和视觉专业审核页；
- 证据页是父 session 的只读辅助层；
- Runtime 是业务写入真相；
- MCP 工具只有一个 catalog；
- 内容对象只有四个 v2.2 权威对象；
- 经验只有 same-type/global；
- 历史兼容只读且隔离。

### 6.3 命名一致性

统一使用：

- `content-full-deck | visual-professional`
- `foreground-if-waiting | notify-only`
- `material-backed | mixed-evidence | proposal-led`
- `approved | modify | evidence | merge-or-delete`
- `AnchorRegionFeedback | AnchorFeedbackBatch`
- `VisualContractReviewMark | VisualContractReviewMarkSet`
- `same-type | global`
- `content | visual`
- `ProjectExperienceRetrospective`

旧 `content-sidebar-*`、`proposal-only`、framework/expansion 和 candidate/personal/stable 仅可出现在 legacy adapter、历史文档或迁移测试。

### 6.4 安全边界

本计划没有授权操作真实 PPT 项目、安装/刷新正式插件、伪造 Browser/AI/PowerPoint/聊天证据、改变 ReleaseTargetPolicy、删除 stash/worktree 或提交 Git。实施若需要任何一项，必须另行向用户说明准确目标和风险并取得授权。

### 6.5 执行方式

按用户要求仅提供一种执行方式：在本任务中使用 `superpowers:executing-plans`，单 Agent、分批执行、每批结束运行对应测试并汇报；Git commit、合并和正式安装均保持授权门。
