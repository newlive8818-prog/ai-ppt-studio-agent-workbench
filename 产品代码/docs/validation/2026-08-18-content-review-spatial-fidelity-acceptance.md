# 内容全稿审核页空间保真验收记录

## 1. 记录身份

- 验收日期：2026-08-18
- 参考原型：`prototypes/08-content-full-deck-review-v7-inline-feedback.html`
- 代表性截图：`prototypes/08-content-full-deck-review-v7-inline-feedback.jpg`
- 设计规格：`docs/superpowers/specs/2026-08-18-content-review-spatial-fidelity-design.md`
- 实施计划：`docs/superpowers/plans/2026-08-18-content-review-spatial-fidelity-implementation.md`
- 隔离 worktree：`/private/tmp/ai-ppt-v22-TmBomR`
- 分支：`codex/review-surface-v22`
- 实现基线：`c2abde3 docs: plan content review spatial restore`
- 提交状态：本记录与 7 个实现/测试文件共同构成一个独立、可 `git revert` 的实现提交；不修改共享历史。

本记录只验收第一轮“内容全稿审核页结构还原”。视觉锚点页、完整视觉合同页、Runtime、MCP、Review Bridge、宿主通知、AI 接收回执和 PPT 运行数据均不在本轮修改范围。

## 2. 证据边界与当前结论

```yaml
implementationStatus: implemented-and-locally-verified
evidenceScope: local-development-preview
proofEligible: false
realHostEvidence: false
userUiAcceptance: pending
prototypeUiAcceptance: accepted-in-separate-record
```

这里的 `userUiAcceptance: pending` 专指首轮生产 React 实现页面。用户已于 2026-08-18 验收通过修正后的 08 HTML 原型，详见 [内容审核原型用户 UI 验收记录](./2026-08-18-content-review-prototype-ui-acceptance.md)；原型通过不自动改变本记录的生产实现验收状态。

| 证据层 | 当前状态 | 可以证明 | 不能证明 |
|---|---|---|---|
| 单元、DOM、响应式源码合同 | 通过 | 结构顺序、语义标识、空间合同失败关闭、PageDecision 与既有业务回归 | 浏览器实际几何或用户视觉认可 |
| 本地受控 Chromium | 通过 | 当前构建在指定视口的真实 bounding box、无横向溢出、首屏进入第一页正文 | 真实 Codex 宿主打开、宿主通知、AI 接收或用户验收 |
| 用户 UI 验收 | 待验收 | 用户是否认可与 08 原型确认范围的还原程度 | Runtime 或 Review Bridge 真实性 |
| 真实宿主 / AI 回执 | 本轮未获取 | 本记录不作任何通过声明 | 真实 ReviewSession、宿主通知和 AI 回执 |

只有用户在当前实现页面上明确接受，`userUiAcceptance` 才能从 `pending` 更新为 `accepted`。自动化、截图或本地 HTTP 页面不得替代该决定。

## 3. 本轮空间合同

参考视口固定为 `1280 × 720 CSS px`：

- 项目头高度不超过 `96px`；
- 章节定位条高度不超过 `64px`；
- deck intro 高度不超过 `160px`；
- 页面区域必须保持“项目头 -> 章节定位 -> deck intro -> 第一章标题 -> 第一页标题 -> 第一页阅读正文”的顺序；
- 第一页 `.content-slide-reading-grid` 顶部必须进入 720px 高的首屏；
- `scrollWidth` 不得大于 `clientWidth`；
- 不得通过删减正文、隐藏状态、修改 PageDecision 业务规则或改变投影数据换取空间。

既有 PageDecision 合同继续保留：最小高度 `42px`、低于 `380px` 时为 `2 × 2`、标签不换行。

## 4. TDD：RED 到 GREEN

### 4.1 纯空间合同

先在 `tests/v22-prototype-fidelity.test.mjs` 导入尚不存在的：

```text
CONTENT_REVIEW_SPATIAL_CONTRACT
assertContentReviewSpatialFidelity
```

RED 结果：Node 测试因模块没有导出 `CONTENT_REVIEW_SPATIAL_CONTRACT` 失败。

随后在 `scripts/v22-ui-acceptance-evidence.mjs` 实现固定视口、三项高度上限、页面顺序、第一正文首屏可见和横向溢出失败关闭。GREEN 结果：`tests/v22-prototype-fidelity.test.mjs` 全部通过。

### 4.2 DOM 与响应式结构

先新增以下失败断言：

- 紧凑页头、细进度轨、章节定位、deck intro 和唯一第一页 reading grid 的稳定语义标识；
- deck intro 使用“本稿阅读导语”，不再使用“本轮审核说明”；
- 章节定位必须是单行横向条，章节项不得恢复为 `flex: 1 1 320px` 的多行卡片墙。

RED 结果：`ContentFullDeckReviewPage` 1 个失败、`ContentReviewResponsive` 2 个失败，共 3 个预期失败。

实现语义 DOM、细进度轨和紧凑 CSS 后，定向 Widget 测试 GREEN。未改写保存、批次提交、revision、材料、证据层或 PageDecision 事件处理。

## 5. 自动化验证

完成前重新运行以下命令，以最新输出为准：

```text
git diff --check
npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive ContentReviewLongDeck
node --test tests/v22-prototype-fidelity.test.mjs
npm run test:widget
npm run typecheck
npm run build
npm run accept:v22-ui
```

验收范围要求：

- 定向 Widget 测试通过；
- 全量 Widget 测试通过；
- Node 原型/空间合同测试通过；
- TypeScript 类型检查通过；
- 生产构建通过；
- 本地 Chromium UI 验收报告 `ok = true`；
- 360、760、1000、1280 和 1440 CSS px 的内容审核页无横向溢出；
- 浏览器控制台无错误。

### 5.1 2026-08-18 完成前新鲜结果

```text
git diff --check
passed

npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive ContentReviewLongDeck
3 test files passed
123 tests passed / 123 total

node --test tests/v22-prototype-fidelity.test.mjs
6 tests passed / 6 total

npm run test:widget -- --reporter=dot
12 test files passed
516 tests passed / 516 total

npm run typecheck
passed

npm run build
passed

npm run accept:v22-ui
ok = true in the approved controlled environment
10 responsive results total
```

第一次全量 Widget 运行识别出页头 `h1` 和 deck intro `h2` 同名“完整售前阅读稿”，使路由测试的唯一 heading 查询失败。根因是本轮 deck intro 文案与既有页头标题重复；将导语标题最小化修正为“按最终页序连续阅读完整稿”后，相关 159 个路由/内容页测试通过。

之后一次把全量 Widget、typecheck 和 build 同时并行运行时，未修改范围内的视觉回执异步测试出现 1 次超时。该用例独立重跑通过；在不与构建争抢资源的条件下重新运行全量 Widget，最终稳定结果为 `12/12` 文件、`516/516` 测试通过。未因此修改视觉审核页。

## 6. 1280 × 720 浏览器几何实测

本地 Chromium runner 从当前构建采集的通过值：

| 区域或指标 | 实测值 | 阈值或结论 |
|---|---:|---|
| 页头高度 | `87.03125px` | `<= 96px`，通过 |
| 章节定位条高度 | `40px` | `<= 64px`，通过 |
| deck intro 高度 | `122.953125px` | `<= 160px`，通过 |
| 第一页 reading grid 顶部 | `443.078125px` | `< 720px`，正文进入首屏 |
| `scrollWidth` | `1280px` | 与 `clientWidth` 相等 |
| `clientWidth` | `1280px` | 无横向溢出 |
| console errors | `0` | 通过 |

本轮新鲜 UI 验收运行完成后，以报告中的 `checkedAt`、`runDirectory` 和截图路径为最终运行证据；历史运行不能代替本轮完成前验证。

最新报告身份：

```text
checkedAt: 2026-08-18T09:47:12.187Z
runDirectory: /private/tmp/ai-ppt-v22-TmBomR/产品代码/output/playwright/v22-ui/runs/run-f4e9cfc7-6d42-4c0b-8c2a-c81ecb70cbc3
resultCount: 10
```

## 7. 报告与截图

- 验收报告：`/private/tmp/ai-ppt-v22-TmBomR/产品代码/output/playwright/v22-ui/v22-ui-acceptance.json`
- 1280 × 720 首屏截图：`/private/tmp/ai-ppt-v22-TmBomR/产品代码/output/playwright/v22-ui/runs/run-f4e9cfc7-6d42-4c0b-8c2a-c81ecb70cbc3/content-review@1280x720-first-viewport.png`
- 截图只用于本地视觉对照；它不是用户验收、真实宿主打开或 AI 回执。

## 8. Chromium CapabilityGap

在普通 macOS sandbox 中运行 `npm run accept:v22-ui` 时，Chromium 在进入页面断言前被系统权限阻止：

```text
mach_port_rendezvous_mac.cc ... Permission denied (1100)
```

这是执行环境的 `CapabilityGap`，不是页面断言失败。相同命令随后在已批准的受控环境中运行并通过。受控环境结果仍只属于本地开发预览，不升级为 `realHostEvidence`。

## 9. 文件与边界审计

本轮只允许下列文件进入实现提交：

```text
scripts/run-v22-ui-acceptance.mjs
scripts/v22-ui-acceptance-evidence.mjs
tests/v22-prototype-fidelity.test.mjs
widget/src/content-review/ContentFullDeckReviewPage.test.tsx
widget/src/content-review/ContentFullDeckReviewPage.tsx
widget/src/content-review/ContentReviewResponsive.test.tsx
widget/src/styles/content-review.css
docs/validation/2026-08-18-content-review-spatial-fidelity-acceptance.md
```

明确未修改：

- `widget/src/visual-review/**`；
- `widget/src/styles/visual-review.css`；
- `src/ai_ppt_studio/**`；
- `mcp/**`；
- `/Users/defei/Documents/AI-PPT-Workspace`；
- 主项目脏工作树中的用户改动。

## 10. 阶段结论

工程出口条件为：结构、测试、类型、构建与本地几何验收全部通过，差异范围受控，并生成可供用户查看的当前实现页面。

达到工程出口后，本页只能表述为“实现完成，等待用户验收”。在用户明确认可之前：

- 不标记 `UI fidelity accepted`；
- 不开始视觉审核页整改；
- 不把本地预览描述为真实宿主 ReviewSession；
- 不把保存状态描述为宿主通知或 AI 已接收。

2026-08-18 的后续用户确认只接受了修正后的 08 HTML 原型，不是对本记录所指首轮生产 React 页面的追认；因此本记录的 `userUiAcceptance` 仍为 `pending`。
