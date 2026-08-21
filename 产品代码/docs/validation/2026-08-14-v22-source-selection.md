# AI PPT Studio v2.2 隔离研发来源选择与现场保护清单

## 1. 执行身份

- 记录日期：2026-08-14
- 目标分支：`codex/v22-unified-runtime`
- 隔离 worktree：`/private/tmp/ai-ppt-v22-TmBomR`
- 干净基点：`3998a9694cd9c86cc3bf97b45de294c85a57109e`
- 测试 Runtime：`/private/tmp/ai-ppt-v22-runtime-4ptkJC`
- 测试 Runtime profile：`/private/tmp/ai-ppt-v22-runtime-4ptkJC/workspace-profile.json`
- 执行规则：单 Agent；未经用户单独授权不 commit、不合并、不安装正式插件。

## 2. 受保护现场

以下对象只读保留，不在本实施链应用、删除、覆盖或清理：

| 对象 | 身份 |
|---|---|
| 主工作区 | `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app` |
| 主工作区分支/HEAD | `codex/content-blueprint-sidebar-review` / `3998a9694cd9c86cc3bf97b45de294c85a57109e` |
| 旧 worktree 2 | `/private/tmp/ai-ppt-task2-85aacba` / `2813aaf` |
| 旧 worktree 3 | `/private/tmp/ai-ppt-task3-0f15fb1` / `b5879c0` |
| 旧 worktree 4 | `/private/tmp/ai-ppt-task4-Ui6yNZ` / `a7f76a65` |
| 旧 worktree 5 | `/private/tmp/ai-ppt-task5-a7f76a65` / `d7ff354` |
| stash 0 | `task4-preintegration-overlap` |
| stash 1 | `task3-preintegration-user-transactions` |
| 真实 PPT Runtime | `/Users/defei/Documents/AI-PPT-Workspace`，禁止写入 |
| 并行 Web 产品 | `../PPT  web app `，不在范围 |
| 正式插件与缓存 | 不安装、不刷新、不登记验收 |

## 3. 已迁入的权威产品制品

这些文件从主工作区逐文件机械复制到隔离 worktree；SHA-256 用于证明来源一致，复制不包含任何源码集成。

| 目标文件 | SHA-256 | 身份 |
|---|---|---|
| `../../../00-唯一研发基线索引-v1.0.md` | `c06d820ffa9e01df04635649d267dafd8c0218a87a08509aa138228c35f6ec17` | v2.2 唯一索引 |
| `../../../01-产品需求基线-v1.0.md` | `8ab99f99b61ec1b69a7d39de638c391cd040e880f320b18d3b4f2916f8b05d9b` | v2.2 产品需求 |
| `../../../02-系统详细设计-v1.0.md` | `eb2797962a9f10c995f77a8dfe33fc8e3bf87cc1af612ad221f176838eeb361a` | v2.2 系统设计 |
| `../../../03-UI设计与交互规范-v1.0.md` | `a8e29f063e20e11211001a0c1d7880b813bab1cd81145fd0b6b4967899c7370d` | v2.2 UI 规范 |
| `../superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md` | `b0e82866af89df3eebc01cec1e0ae09e14ca1d2e2af2c5871fb039f6eb85314f` | 仅内容审核闭环局部有效 |
| `../superpowers/specs/2026-08-14-presales-chief-agent-content-and-experience-design.md` | `4dd04892135673e41b20b827feddc2d6b5a8656185ee23ddb914e38b51ced3c3` | 内容与经验研发合同 |
| `../superpowers/plans/2026-08-14-v22-unified-development-and-simplification.md` | `b92818ad2f8acfd0b7ac41df85ba1383d964531a186e4b41d6df09d673be7327` | 当前统一实施计划 |
| `../../prototypes/07-visual-anchor-chat-collaboration-prototype.html` | `3b4e5a623fd0a2e9717d2015d1b3f03b5cd4baf9f9599cce2594df1abd911a4f` | 已确认视觉审核交互参考 |

## 4. 后续源码白名单

后续不整链 cherry-pick `d7ff354`，按下列业务语义重新吸收：

| 来源 | 保留语义 | 明确排除 |
|---|---|---|
| 当前主工作区 | 可信 Gate、ReleaseTargetPolicy、Review Bridge、ChatDeliveryReceipt 等已审计实现 | 五空间、常驻侧边栏、旧项目仪表盘 |
| `d7ff354` 实施链 | PageDecision、ContentReviewBatch、revision plan、全篇复审、G0 current-source lineage、长文档和草稿恢复 | framework confirmation、full-deck authorization、内容空间身份、侧边栏路由 |
| `stash@{0}` | 重叠服务成果仅作差异参考，按目标合同重写 | 直接应用 stash、覆盖当前文件 |
| `stash@{1}` | `kernel/transactions.py` 的事务成果仅在内核回归后逐段吸收 | 直接 pop/apply、改变事务顺序 |

每项迁移都必须先写目标 v2.2 失败测试，再写最小实现；不得以“旧代码已经存在”为理由跳过 TDD。

## 5. 干净基线证据

- Python：`286 tests`，全部通过；
- Node：`32 tests`，全部通过；
- Widget：`38 tests`，全部通过；
- Review Bridge loopback：沙箱内因 `listen EPERM 127.0.0.1` 被准确阻断；权限匹配重跑后全部通过；
- `git status --short`：基线测试后为空；
- `git diff --check`：通过。

这些结果只证明 `3998a96` 隔离源码基线可执行，不证明 v2.2 已实现，也不构成真实 Browser、PowerPoint、插件安装或客户项目验收。

## 6. Task 1 完成复核

- 八个迁入制品已在主工作区与隔离 worktree 分别重新计算 SHA-256，结果逐项一致，并与第 3 节记录一致；
- 四份基线共检查 17 个本地相对链接，`missing=0`；`07-visual-anchor-chat-collaboration-prototype.html` 已确认存在，大小为 `226446 bytes`；
- `RuntimeConfig.from_workspace_file` 已只读加载测试 profile，得到的 Runtime 为 `/private/tmp/ai-ppt-v22-runtime-4ptkJC`，source/install/upstream 三个 protected roots 均位于 `/private/tmp`；配置不包含 `/Users/defei/Documents/AI-PPT-Workspace`；
- 主工作区仍位于 `codex/content-blueprint-sidebar-review@3998a9694cd9c86cc3bf97b45de294c85a57109e`；四个旧 worktree 仍分别位于 `2813aaf`、`b5879c0`、`a7f76a65`、`d7ff354`；
- `stash@{0}` 仍为 `e67fa96e377f28bed1c4f7dbbed81ceb8ded0034`，`stash@{1}` 仍为 `f3bf56ae62c1e789a32d7f1cc240a16a1362a2ed`；
- `git diff --check` 通过；本任务没有 commit、stash apply/pop、正式插件安装或真实 Runtime 写入。

## 7. Task 2 质量门与接受台账复核

- RED：`npm run typecheck` 先以 `Missing script: "typecheck"` 失败；旧接受台账测试因权威文档漂移、固定 `104 requirements` 和过时章节断言失败；新增显式 ID、空台账、身份漂移、文本漂移和动态工具目录测试后，旧实现按预期失败；
- TypeScript 直接基线检查原本已通过；计划中预想的 Node 全局类型问题在当前基点不存在，因此未对 Widget 测试或 `tsconfig` 制造无依据修改；
- `package.json` 现已提供独立 `typecheck`、`test:python` 和不隐式混入 Python/外部探针的 `quality`；
- PRD、SDD、UI 三份权威验收章节分别登记 25、43、30 个显式 requirement ID，共 98 个；ID 不再由章节号生成，台账同时保存来源文件、语义小节和原文；
- 新增 `v2.2-acceptance-ledger.json` 与空的 `v2.2-evidence.json`。旧 v1.6 proof 没有自动继承，98 项当前均诚实保持 `unproven`；
- 发布校验不再要求固定 104 项或固定工具数；其拒绝空台账、ID 漂移和同 ID 文本漂移，并要求 probe 工具数组无重复、`tool_count` 与数组长度一致、probe catalog hash 与安装 manifest 一致；
- 活动 `src/`、`scripts/`、`tests/` 和 v2.2 台账中扫描不到 `104`、固定 `tool_count 17/18`、`section_prefix` 或 `PRD-17` / `SDD-21` / `UI-23` 依赖；
- GREEN：目标 Python 测试 12/12，通过；Python 全量 290/290，通过；`npm run quality` 通过，其中 Node 32/32、Widget 38/38、TypeScript 和构建均通过；
- Review Bridge 在普通沙箱内仍因 loopback `EPERM 127.0.0.1` 被阻断；按相同权限边界重跑后 7/7 通过。该结果只证明本地自动回归，不构成真实 Browser、PowerPoint、插件安装或客户验收；
- `git diff --check` 通过；本任务仍没有 commit、stash apply/pop、正式插件安装或真实 Runtime 写入。
