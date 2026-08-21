# Review Surface 研发来源选择与版本协议

日期：2026-08-17
对应计划：`2026-08-17-review-surface-prototype-fidelity-and-acceptance.md`
产品基线：`v2.2`（已批准，研发唯一基线）

## 1. 来源选择

本计划的源码执行对象选择 `/private/tmp/ai-ppt-v22-TmBomR`，原因是计划已经明确将
`codex/v22-unified-runtime` 登记为实现候选，并且该工作树承载 v2.2 迁移候选实现。

本项目主目录 `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
继续作为产品基线、计划、验证记录和用户现有工作的保护性工作区。主目录和 v22 工作树均为脏工作树；
本记录不把任何既有修改视为本轮修改，也不允许用 `reset`、`clean`、强制覆盖或全仓格式化清除它们。

执行边界：

| 责任 | 唯一当前所有者 |
|---|---|
| React 审核入口 | v22 工作树中的单一路由；旧侧边栏只作兼容适配 |
| 内容/视觉投影 | v22 工作树中与当前 `ReviewSession` 绑定的正式投影 |
| 权威写入 | schema-3 Python Runtime |
| Browser/宿主交互 | 唯一 Review Bridge/MCP 适配路径 |
| 产品合同 | 主目录四份 v2.2 基线 |
| 原型交互参考 | `07`/`08` 原型的结构、层级、位置和响应行为；示例数据与旧命名不进入产品数据 |

在 v22 工作树的已有修改没有完成归属确认和 checkpoint 前，不推进会改变相同文件的第二轮实现；
新任务必须使用新的 `codex/...` 分支或明确标记的任务提交，不能直接叠加到未识别的混合改动上。

## 2. 版本身份

每一个研发变更、审核会话和交付证据都使用以下身份组，不用聊天上下文或文件修改时间猜版本：

```text
planId          = 2026-08-17-review-surface-prototype-fidelity-and-acceptance
baselineVersion = v2.2
sourceVersion   = 当前业务/视觉制品的不可变来源版本
revision        = Runtime 单调 revision
commit          = 包含该变更的 Git commit
artifactHash    = 相关 artifact/PPTX/构建输出的 SHA-256（适用时）
```

写入必须携带 `expectedRevision` 和幂等 command identity；revision 冲突要返回当前 revision 与影响范围，
不得静默覆盖。新的 `sourceVersion` 或 revision 会使旧 ReviewSession 只读并保留历史；恢复只能显式重新绑定，
不能把旧草稿直接提交到新对象。

## 3. 研发变更流程

```text
读取四份基线
  -> 检查 git status 并确认既有改动归属
  -> 一个计划阶段 / 一个 codex 分支或 worktree
  -> 限定文件范围
  -> 先写失败测试或结构验证
  -> 实现
  -> git diff --check + 类型/单测/构建
  -> git diff 与暂存区 diff 审查
  -> 一个可回滚的原子提交
  -> 记录 commit、revision、证据和残余 CapabilityGap
```

提交粒度按阶段出口控制：来源冻结、投影合同、内容审核页、视觉锚点页、完整合同页、回执、自动化验收、
最终回归分别保持可独立回退。未通过阶段门时不进入下一阶段，不用“顺手修复”扩大范围。

## 4. 防重复修改与回滚

- 任何新改动开始前先记录 `git status --short --branch`、当前 HEAD 和目标文件清单。
- 同一文件若已有他人/既有未提交修改，先做 diff 归属；本轮只修改得到授权的区段。
- 禁止 `git reset --hard`、`git clean -fd`、强制 push 和覆盖式复制来“整理”工作树。
- 共享分支或已发布版本出现问题时优先 `git revert <bad-commit>`；不改写历史。
- 发布或验收记录绑定 commit、测试、构建、真实宿主证据和必要的制品 hash；旧证据不能自动证明新版本。
- 代码版本、产品基线版本、Runtime revision、PPTX hash 是四个不同概念，必须分别显示和记录。

## 5. 当前阶段结论

Stage 0 仅完成来源登记和版本协议；在 v22 工作树已有修改完成 checkpoint、确认新分支/提交边界前，
不把内容页或视觉页实现宣称为本计划成果。后续每个阶段的验证记录必须引用本文件的版本身份与回滚规则。
