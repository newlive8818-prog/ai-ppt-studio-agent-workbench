# Review Surface 工作树 Checkpoint

采集时间：`2026-08-17T21:54:16+0800`
计划 ID：`2026-08-17-review-surface-prototype-fidelity-and-acceptance`
产品基线：`v2.2`

## 1. 隔离状态

v22 已经是 linked worktree，不创建嵌套 worktree：

```text
path       = /private/tmp/ai-ppt-v22-TmBomR
branch     = codex/v22-unified-runtime
HEAD       = 3998a9694cd9c86cc3bf97b45de294c85a57109e
git_dir    = <project-root>/.git/worktrees/ai-ppt-v22-TmBomR
common_dir = <project-root>/.git
submodule  = false
```

主目录保持保护状态：

```text
path   = /Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app
branch = codex/content-blueprint-sidebar-review
HEAD   = 9aa08089ca192f54d9693ede2d265ecc6562e8e9
```

`3998a96` 是 `9aa0808` 的祖先；主目录比 v22 HEAD 多 7 个提交，v22 没有只存在于提交历史中的领先提交。
v22 的新实现主要存在于未提交工作区，因此不能从 `3998a96` 直接新建干净 worktree 后假定实现已经被带入。

## 2. 写入前状态快照

以下摘要和 hash 在创建本 checkpoint 文件之前采集，用于识别后续状态漂移，不代表这些改动均属于本计划。

| 工作树 | 状态摘要 | 已跟踪 diff | status SHA-256 | tracked diff SHA-256 | untracked manifest SHA-256 |
|---|---|---|---|---|---|
| 主目录 | 91 modified, 33 untracked, total 124 | 91 files, +9085/-4050 | `074f17f257713c8e526e20fa8e9dda1c870d43f642d614c22593f24d17ac8f39` | `93c231880549a2c055af5b6263232035e74cd63164f9bbca61d6396c95fbc59a` | `dbf08c383a26c813f300b3bf4a7b35039c85e2fedc41df617311df6001760a03` |
| v22 | 95 modified, 36 deleted, 85 untracked, total 216 | 131 files, +17598/-28413 | `7742033758eb308b635bfcc2d1ad33b818bd9a2089d932c2bea15a098f1d2fee` | `31138cb1ad8c93c33553c0fb383ea1e327765ea5826b8d9f8f9d57de3625c3a1` | `ded7d8fdca2a8852abb32e21ce36c49d793a9507ebd7877bbf203486a6712b18` |

计划文件目前只存在于主目录，执行时以该文件内容 hash 锁定：

```text
计划文件 SHA-256 = 3d5e881288c1883a79af5ebc52b781cc4373b964ddad23fa0e5107b4b59c1a36
```

已创建的两份 Stage 0/1 控制记录：

```text
source-selection SHA-256 = 155af8afc4583c1f247e935da1e69988f43521be4e28accb8661c657a1a0b414
fidelity-ledger SHA-256 = 1329a9321c5a298344bb94768be101ef0a3b478f488db3021828f52ad6686d20
```

## 3. 计划范围重叠

v22 当前状态中至少 45 条记录落在 Review Surface 计划的核心路径，包括：

- `widget/src/main.tsx`、`ReviewSurfaceRouter`、`content-review/`、`visual-review/`、types、styles 和 validation；
- `review_session_service.py`、`visual_review_service.py`、内容审核与 review domain；
- `mcp/review-bridge.mjs`、MCP review tools；
- v22 UI acceptance scripts；
- Review Bridge、v22 content/visual/review session 测试。

这些不是可以绕开的旁支改动，而是计划准备修改的同一批文件。没有 checkpoint 就继续开发，会使旧实现、计划补丁和新修复无法可靠区分。

## 4. 保护规则

- 主目录不接收本计划源码修改。
- v22 是唯一实现候选；不再创建另一个包含不同业务真相的实现分支。
- 不执行 `git reset --hard`、`git clean -fd`、覆盖式复制、强制 push 或全仓格式化。
- checkpoint 之前不修改上述重叠源码；只允许更新本计划的验证和盘点记录。
- 不把本地测试、截图或历史 proof 认定为真实宿主、AI 回执、G3 或 G4。
- 未经用户确认，不提交、合并、打 tag 或清理当前混合改动。

## 5. Checkpoint 暂存区审查

用户在后续对话中明确授权：暂存当前 v22 完整改动、审查暂存区、创建不可发布 checkpoint commit，
再从该 commit 创建 `codex/review-surface-v22`；未授权 push、merge、tag 或发布。

暂存后审查结果：

- 共 261 个文件：95 modified、130 added、36 deleted；
- 范围只有四份唯一基线和 `产品代码/`，没有项目外路径；
- 没有 `分享材料/`、PPT Runtime 数据、并行 Web 产品、`node_modules`、`dist`、`build` 或 `coverage`；
- `git diff --cached --numstat` 未发现二进制文件；大改动均位于已盘点的 Runtime、Widget、测试、基线和迁移路径；
- 首次 `git diff --cached --check` 捕获 4 份本轮验证记录中的 10 处 Markdown 行尾空格；仅删除这些行尾空格并重新暂存后复查通过。

该审查只证明 checkpoint 范围可控且暂存格式检查通过，不把它提升为发布、真实宿主、AI 回执、G0、G3 或 G4 验收。

## 6. 第一阶段结论

工作树保护和版本盘点已经完成，但 v22 还不是可继续开发的干净 checkpoint。下一步必须先决定如何保存当前 v22 的 216 条状态项：

1. 对现有 v22 改动做范围审查和完整基线回归；
2. 验证通过后，经用户确认创建一个不可发布的 checkpoint commit；
3. 从该 checkpoint 创建 `codex/review-surface-v22`，再按计划逐阶段形成原子提交；
4. 如果现有改动未通过回归，则保持原状，先记录失败，不进入 Review Surface 新修改。

本文件不是提交授权，也不是实现验收。
