# AI PPT Studio v2.2｜版本隔离与恢复基线（2026-08-25）

## 1. 文档身份

- 状态：`版本治理证据`
- 用途：记录混合工作区止血、恢复基线选择、当前冲突和后续恢复门禁。
- 非用途：本文不是产品验收、发布说明、合并批准或真实宿主能力证明。
- 权威产品合同仍为项目根目录四份 v2.2 基线；本文不能覆盖其业务含义。

## 2. 隔离快照

- 原工作目录：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
- 隔离分支：`codex/quarantine-mixed-worktree-20260825`
- 隔离提交：`8c794fa85f015c1afa9c3db2f9145e6a749ed952`
- 父提交：`d201442e8518a3bed6bc4017ab9756b26abd8536`
- 提交规模：68 files，7629 insertions，1049 deletions。
- 排除范围：`.superpowers/`、`.workbuddy/`、`分享材料/` 未进入隔离提交。
- 已知现场问题：`产品代码/widget/src/styles/evidence.css` 在提交时保留 EOF 尾部空行。

隔离提交只保存当前三层混合现场：当前分支历史、从其他分支复制但未正确纳入历史的文件，以及后续未提交修改。它禁止直接合并、发布或作为验收基线使用。

## 3. Git 引用修复

非法引用 `.git/refs/heads/codex/mvp-skill-app-design 2` 原指向：

```text
016c5a52941f97ba96bf95620d4a2ab725273ffb
```

已创建合法保全分支：

```text
codex/mvp-skill-app-design-2
```

原非法 ref 文件已移动到：

```text
/private/tmp/ppt-codex-app-invalid-ref-mvp-skill-app-design-2-20260825.bak
```

`git show-ref`、`git worktree list`、对象类型和合法分支解析已恢复。`git fsck --full --no-reflogs` 与 `git fsck --connectivity-only --no-reflogs` 均长时间无错误输出但未结束，已人工终止；因此不得写成“全量对象完整性检查通过”，后续需在独立维护窗口继续排查性能原因并完成检查。

## 4. 恢复基线

- 来源分支：`codex/main-worktree-v22-integration-20260821`
- 来源／恢复 HEAD：`cd7a5e9b8d3a35c4cd7bb94e95192e02f85d3cf3`
- 恢复分支：`codex/v22-recovery-integration-20260825`
- 恢复 worktree：`/Users/defei/.config/superpowers/worktrees/PPT-codex-app/v22-recovery-integration-20260825`
- merge-base（恢复线与隔离线）：`044c636a3ff68b4d53476d02545d1e34a42eea19`
- 分叉计数：恢复线独有 55 个提交，隔离线独有 22 个提交（含隔离快照）。

选择该来源的原因：它本身工作区干净，并保留已提交的内容／视觉审核生产 UI、正式 ViewModel、正式视觉审核投影、Review Bridge 和较完整的验收覆盖。恢复工作不得从隔离快照继续叠加。

四份基线 SHA-256：

```text
63c6312916db38ea6afe634632e011458ed689f4887550e27caf6052b6e5a8b4  00-唯一研发基线索引-v1.0.md
a0cb9c49a99eb4e2d0d54b84fe042cd9808c53f46301f81023a16452050c0530  01-产品需求基线-v1.0.md
3ee45b000ed197672fd56bf7293d0efb9b316c12ac111480da3ee87d06eada66  02-系统详细设计-v1.0.md
692271e253718c98b9dc971492dbbd42b7137d4030783641d7525835d6d6eb5f  03-UI设计与交互规范-v1.0.md
```

## 5. 恢复基线验证

在恢复 worktree、HEAD `cd7a5e9` 上重新安装锁定依赖并验证：

| 检查 | 结果 | 事实边界 |
|---|---:|---|
| TypeScript typecheck | 通过 | `tsc --noEmit` exit 0 |
| Python | 404/404 | `unittest` 通过 |
| Widget/Vitest | 577/577 | 15 个测试文件通过 |
| Widget build | 通过 | 生成 `widget/dist/index.html` |
| Node | 112/112 | 非沙箱环境重跑通过 |

Node 首轮在沙箱中因 `listen EPERM 127.0.0.1`、Vite 无法写 `node_modules/.vite-temp` 和缺少连锁构建产物而失败；非沙箱复跑通过。该首轮失败属于环境边界，不是代码失败；非沙箱通过也不构成用户 UI、真实宿主、G3/G4 或发布验收。

## 6. 已确认的冲突与回归风险

### P0：不得整体合并的结构性冲突

1. 隔离线删除正式 `visual_review_service.py`，视觉路由改经 legacy adapter，导致正式 VisualReviewPageViewModel 链路降级。
2. 隔离线的视觉锚点数据出现无图 `s1/s2` 和补位的“锚点缺口 3”，不能证明真实三图、矩形框选和多条反馈批次。
3. 隔离线删除或替换恢复线中的多项 content-review ViewModel、Controller、视觉测试和 `run-v22-ui-acceptance.mjs`。
4. 隔离线把 UI 验收收窄为少量静态场景，无法覆盖三张真实锚点图、开始标注、拖拽矩形、两条反馈、批次提交、长文档、冲突和恢复。
5. 当前视觉合同静态截图只能证明旧构建产物中合同视图可见，不能证明当前锚点运行链或源码可重建。

### 可恢复但必须拆分的变化

1. v2.2 内容权威对象、总师、内容硬门和全稿审核后端；
2. MCP 打包 Python Runtime、ReviewSession 和 typed tool catalog；
3. 内容审核关键证据图片：保留 `asset_ref`、真实图片直显、无图片页面合法、多图片／多材料稳定顺序；
4. 用户已验收的内容审核前端细节；
5. 用户已验收的完整视觉合同前端细节。

以上变化不能从隔离快照整包 cherry-pick；必须逐单元提取、补测试、复核基线和独立提交。

## 7. 后续 Git 门禁

1. 一个恢复单元对应一个 `codex/` 分支或独立 worktree；禁止在主 checkout 长期堆叠。
2. 开工前记录基线版本、来源分支、HEAD、目标文件、既有修改归属和回滚点。
3. 每个单元遵循：失败测试 → 最小实现 → typecheck/Python/Node/Widget/build → Browser 证据 → 必要时用户验收 → 原子提交。
4. 只精确暂存当前单元文件；禁止 `git add .`、混入用户目录或顺手格式化。
5. `已实现 != 已提交 != 已验证 != 已合并 != 已发布 != 已验收`，所有报告分别标注。
6. 未经明确授权不 amend、不 merge、不 push、不删除隔离分支或备份。
7. 合并前必须恢复 v22 验收覆盖，并对 07/08 已确认范围做真实 Browser 验证。

## 8. 建议恢复顺序

1. 工程门：保证 build、单文件 Vitest、全量 Vitest 和 Node/Python 基线持续可完成；
2. MCP 打包 Runtime；
3. ReviewSession 与 typed tool catalog；
4. v2.2 内容对象、总师、两个内容硬门；
5. 全稿内容审核后端；
6. 内容审核关键证据图片；
7. 内容审核前端对齐与用户验收证据；
8. 完整视觉合同前端对齐；
9. 视觉锚点真实三图、矩形框选、多条反馈和不可变批次；
10. 恢复完整验收覆盖；
11. 插件构建、安装、真实宿主回写和最终验收。

任何单元未过本单元门，不得推进下一单元或把隔离快照整体并回恢复线。
