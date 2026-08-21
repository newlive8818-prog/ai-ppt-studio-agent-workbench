# Review Surface v22 现有改动范围与完整回归

采集日期：`2026-08-17`
执行工作树：`/private/tmp/ai-ppt-v22-TmBomR`
分支：`codex/v22-unified-runtime`
HEAD：`3998a9694cd9c86cc3bf97b45de294c85a57109e`
结论：`eligible-for-checkpoint-commit`，尚未提交、合并、打 tag 或发布

## 1. 改动归属结论

当前 v22 工作区与以下既有计划和验证记录的文件边界一致：

- `2026-08-14-v22-unified-development-and-simplification.md`；
- `2026-08-15-review-prototype-fidelity-remediation.md`；
- `2026-08-14-v22-source-selection.md`；
- `2026-08-14-v22-automated-validation.md`。

路径、对象和测试表明，这批改动主要是 v2.2 统一 Runtime、内容/视觉审核、ReviewSession、MCP、Widget、
旧表面下线、经验迁移和验收自动化的未提交成果，不是 2026-08-17 Review Surface 计划新产生的独立补丁。

由于这些文件尚无对应 commit，不能从 Git 历史证明逐文件作者和时间；本记录只将它们统一分类为
`pre-existing-v22-working-state`。后续 checkpoint 的目的正是冻结这一既有状态，不把它伪装成 8 月 17 日新实现。

## 2. 变更范围分类

以下数量按 tracked diff 与 untracked files 合并统计；目录型 untracked 状态已展开到真实文件：

| 范围 | 文件数 | 说明 |
|---|---:|---|
| 四份产品基线 | 4 | v2.2 当前权威合同 |
| docs | 9 | 既有计划、规格和验证记录，含本轮控制记录 |
| requirements | 2 | v2.2 acceptance/evidence 数据 |
| prototypes | 2 | 07/08 原型 |
| Runtime source | 71 | schema-3、内容、视觉、ReviewSession、经验、发布等 |
| MCP | 8 | server、Review Bridge、tool catalog 与 tools |
| scripts | 11 | build、preview、acceptance、probe |
| Skill | 12 | Skill 合同与引用 |
| tests | 72 | Python、Node 与 acceptance tests |
| Widget | 68 | 单一入口、内容/视觉审核、types、styles、draft recovery |
| package metadata | 1 | `产品代码/package.json` |

未发现并行 Web 产品目录、PPT Runtime 项目数据或分享材料混入当前 v22 diff。

## 3. 静态安全检查

| 检查 | 结果 |
|---|---|
| `git diff --check` | PASS，无空白错误 |
| 冲突标记扫描 | PASS，源码、MCP、Widget、测试、脚本和 Skill 未命中 |
| 四份基线相对链接 | PASS，4/4 可解析 |
| 07/08 原型路径 | PASS，两份文件存在 |
| 测试后 tracked diff hash | 与测试前一致：`31138cb1ad8c93c33553c0fb383ea1e327765ea5826b8d9f8f9d57de3625c3a1` |
| 排除本轮 checkpoint 文件后的 status hash | 与测试前一致：`7742033758eb308b635bfcc2d1ad33b818bd9a2089d932c2bea15a098f1d2fee` |

测试和构建没有改写既有源码状态。当前总状态为 217 条，比盘点时多出的 1 条仅为
`2026-08-17-review-surface-worktree-checkpoint.md`。

## 4. 2026-08-17 新鲜回归证据

| 验证 | 结果 |
|---|---|
| TypeScript typecheck | PASS |
| Widget production build | PASS，生成 `widget/dist/index.html` |
| Widget full suite | PASS，12 files / 504 tests |
| Python full suite | PASS，369 tests |
| Node full suite | PASS，87 tests |
| v22 UI acceptance | PASS，`ok: true` |
| UI viewports | 360 / 760 / 1000 / 1440 CSS px |
| UI surfaces | content review / visual review / read-only evidence layer |
| UI console errors | 0 |

Node Review Bridge 和 Playwright 验收因需要本机回环与 Chromium，以批准的受限本机权限执行；没有访问外部网络、
没有修改真实 PPT Runtime 项目，也没有安装或发布插件。

Checkpoint 提交前再次从完整暂存工作树复核：

- `npm run quality`：PASS；TypeScript 与生产构建通过，Node 87/87，Widget 504/504；
- `npm run test:python`：PASS，369/369；
- `npm run accept:v22-ui`：PASS，`ok: true`，8 组 viewport/surface 结果，console errors 为 0；
- 普通沙箱中的第一次 `npm run quality` 仅有 38 个 Review Bridge 测试因 `listen EPERM 127.0.0.1` 失败；
  使用已批准的受限本机回环权限重跑同一命令后 87/87 通过，因此该次失败归类为沙箱能力限制，不是代码回归。

当前 UI acceptance 报告：

```text
checkedAt       = 2026-08-17T14:38:43.982Z
resultCount     = 8
proofEligible   = false
realHostEvidence = false
```

## 5. 证据边界

以上结果证明当前未提交 v22 工作区在本机确定性软件回归中为绿色，可作为 checkpoint 候选。
它不证明：

- 真实 Codex Browser/Review Bridge 宿主通知已经成功；
- AI 已收到反馈；
- Codex Presentations 或 Microsoft PowerPoint 已验收；
- G0、G3、G4 或用户正式验收已经通过；
- 当前工作区可以直接发布。

## 6. 下一 Gate

当前状态已满足“请求 checkpoint 授权”的条件，但本记录不构成 Git 提交授权。下一步需要用户明确确认后才执行：

1. 将当前 v22 完整状态作为一个不可发布 checkpoint 暂存；
2. 审查 `git diff --cached --stat` 与 staged file list，确认没有项目外文件；
3. 创建原子 checkpoint commit，建议消息：
   `chore: checkpoint v2.2 unified runtime before review-surface plan`；
4. 从该 commit 创建 `codex/review-surface-v22`；
5. 将 2026-08-17 计划文件加入新分支，然后从尚未满足的阶段继续，不重复现有绿色实现。
