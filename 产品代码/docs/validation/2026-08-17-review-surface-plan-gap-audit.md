# Review Surface 计划—现状差异审计

日期：2026-08-17

执行工作树：`/private/tmp/ai-ppt-v22-TmBomR`

执行分支：`codex/review-surface-v22`

审计起点：`05caff0 docs: sync confirmed 08 review interaction baseline`

对应计划：`2026-08-17-review-surface-prototype-fidelity-and-acceptance.md`

## 1. 审计目的与状态定义

本记录先比较计划与 checkpoint 中已经存在的实现，只实现真实缺口，不把既有 v22 成果重新改写为本轮成果。
状态含义如下：

- `implemented-and-tested`：已有对应实现，且存在当前自动化测试或确定性验收证据；
- `partially-implemented`：主要能力已存在，但计划点名的合同、结构或交互仍有真实缺口；
- `missing-deterministic-evidence`：实现可能存在，但计划要求的确定性测试、选择器、截图或记录缺失；
- `real-host-capability-gap`：本地代码和自动化不能证明真实宿主、宿主通知或 AI 回执；
- `not-applicable-or-superseded`：计划初稿中的路径或文件已被当前已批准合同中的等价实现取代，不应机械恢复。

## 2. 总结

| 计划任务 | 主要状态 | 结论 |
|---|---|---|
| Task 0 来源与权威冻结 | `implemented-and-tested` | linked worktree、单一责任所有者、07/08 权威边界和回滚协议已有记录；08 已确认补充已在独立提交同步 |
| Task 1 保真账本与投影合同 | `partially-implemented` | 账本和大部分闭合投影校验已存在，但账本声称的“三锚点、内容 slide 唯一性、章节顺序”尚未由 Widget 校验执行 |
| Task 2 单一活动路由 | `implemented-and-tested` | `main.tsx` 只进入 `ReviewSurfaceRouter`；当前投影只路由内容全稿或视觉专业审核；旧活动表面不在当前源码入口 |
| Task 3 08 内容全稿审核页 | `partially-implemented` | 连续全稿、完整正文/材料、PageDecision、草稿、批次、60 页和 360px 规则已实现；deck intro、章节导航、章节容器、最终 summary 仍缺失 |
| Task 4 07 视觉锚点审核页 | `partially-implemented` | 双视图、三锚点、矩形拖拽、图片下方 composer、记录区、批次和窄宽布局已存在；默认可见区域预设仍存在，顶栏也未达到计划点名的白色项目/AI/segmented 结构 |
| Task 5 07 完整视觉合同 | `partially-implemented` | Deck Design System、锚点身份、全部逐页合同、字段/选中文字标记和覆盖式抽屉已存在；合同 title page 和 `anchor-slide-evidence` 语义章节缺失 |
| Task 6 宿主通知与 AI 回执 | `implemented-and-tested` + `real-host-capability-gap` | Runtime、Review Bridge 和 Widget 已分离保存/宿主通知/AI 回执并覆盖重试、超时、幂等、冲突和重开；本地自动化不能证明真实宿主已发送或 AI 已接收 |
| Task 7 验收自动化与证据边界 | `partially-implemented` + `missing-deterministic-evidence` | 已覆盖 360/760/1000/1440、长文档、溢出、42px、2×2、材料和矩形几何，并明确 `proofEligible=false`；仍有过期选择器、缺少计划结构断言和指定交互态截图/最终验收记录 |

## 3. 逐项证据

### Task 0：来源与权威冻结

已满足：

- `2026-08-17-review-surface-source-selection.md` 记录主目录与 v22 worktree、责任矩阵、版本身份、禁止破坏性清理和回滚规则；
- 当前开发在 linked worktree 的 `codex/review-surface-v22` 分支进行；
- 主目录保持 `codex/content-blueprint-sidebar-review` 和既有用户改动，不做覆盖或清理；
- `05caff0` 只同步 `00`、`03` 和已确认 08 JPG，形成独立可回退提交；
- 四份基线共 22 个 Markdown 相对链接已复核存在，07/08 HTML 和 08 JPG 均存在，`UI-ACC-*` 无重复。

文档中的旧 checkpoint 分支/HEAD 是历史采集身份，不应静默改写；本记录补充当前执行身份。

### Task 1：保真账本与投影合同

已满足：

- `2026-08-17-review-surface-prototype-fidelity-ledger.md` 已登记计划点名的 07/08 区域和当前组件所有者；
- `review-surface-validation.ts` 已闭合字段、artifact kind、session/source/revision、锚点 ID/资产映射、逐页视觉合同顺序和回执引用；
- `ReviewSurfaceRouter.test.tsx` 已覆盖错误 artifact kind、开放对象、深层多余字段、lineage 变化和 remount。

真实缺口：

- `validateAnchors()` 只验证数组项目和重复 ID，没有执行 `anchors.length === 3`；当前合法路由样例甚至使用 `anchors: []`；
- `validateContentProjection()` 没有拒绝重复 `slide_id`；
- `validateContentProjection()` 没有验证 `slides` 的 `order` 必须连续，也没有验证 `section_flow` 唯一性及 slide section 的存在/顺序；
- 账本因此把尚未实现的约束写成了已完成结论，必须以测试和代码纠正，而不是保留声明。

首个 TDD 修复：先在现有 `ReviewSurfaceRouter.test.tsx` 增加 2/4 锚点、重复内容 slide、非法章节顺序的失败测试，再最小化修改 `review-surface-validation.ts`。

### Task 2：单一活动路由

已满足：

- `widget/src/main.tsx` 只渲染 `ReviewSurfaceRouter`；
- `ReviewSurfaceRouter` 只选择 `ContentFullDeckReviewPage` 或 `VisualProfessionalReviewPage`；
- 旧 `App.tsx`、`ProfessionalReviewApp.tsx` 和活动 `content-sidebar-progress` 路由在当前 v22 Widget 源码中不存在；
- 路由测试已验证内容页、视觉双视图和无五空间导航；内容页测试已验证证据只通过只读辅助层打开。

`not-applicable-or-superseded`：计划中的“evidence review”不应扩展成第三种 ReviewSession。当前基线只有内容全稿和视觉专业两类按需审核页；来源证据是内容页上的只读辅助层。

### Task 3：08 内容全稿审核页

已满足：

- `[data-content-slide]` 保持最终连续阅读顺序；完整可见正文、身份、演讲备注、证据关系和材料视图均在当前页面；
- 材料读取具备视口惰性加载、手动读取、失败重试和不使用 `file:`/内部 asset URI 的边界；
- 四类 PageDecision、非认可意见、草稿恢复、原子单页保存、全页完成后批次提交和 revision 冲突保护已实现；
- CSS 和测试覆盖 42 CSS px、360px 2×2、无换行方向、60 页完整 DOM 和无旧产品 chrome；
- 当前页证据为只读辅助层，关闭后保留上下文。

真实缺口：

- 计划点名的 `.content-review-head`、`.content-review-chapter-nav`、`.content-review-deck-intro`、`[data-content-chapter]` 和 `.content-review-summary` 未出现在实现中；
- 当前只有 `.content-review-header`、按页数字定位和扁平 slides 列表，尚未恢复 `header → progress → chapter navigation → deck intro → chapters → summary`；
- `ContentReviewProjection` 只有 `section_flow: string[]` 与 slide `section_id`，缺少计划要求的章节编号、标题、任务和显式 slide membership 合同。

### Task 4：07 视觉锚点审核页

已满足：

- 两个审核视图、三锚点标签、主工作区和右侧记录区已实现；
- 正式反馈依赖正面积矩形拖拽，单点不会生成反馈；composer 位于图片下方；
- 跨锚点多条草稿、不可变批次、版本对比、草稿恢复、读图失败和窄宽主区在前/记录区在后均有测试；
- 记录区表达保存、宿主通知、AI 回执和恢复动作，没有聊天记录或 Gate 按钮。

真实缺口：

- `RegionFeedbackEditor.tsx` 仍默认渲染 `整页/上半区/下半区/左侧/右侧` 预设，与 Task 4 Step 3 明确要求冲突；
- 现有测试还把“键盘可操作预设”当作期望，需要改成“默认 UI 不出现预设且矩形拖拽仍可操作”；
- `.visual-professional-header` 当前是深色顶栏和下划线 tab，未实现计划要求的白色顶栏、AI 标记和 segmented 两视图结构。

### Task 5：07 完整视觉合同

已满足：

- `Deck Design System`、锚点身份、全部 `.visual-slide-contract` 按顺序连续渲染；
- 技术 artifact ref 折叠在“技术信息”，没有替代可读合同字段；
- 字段标记、选中文字标记、多标记草稿、编辑/删除、统一保存、冲突保护与锚点批次隔离已有实现和测试；
- 目录与标记记录使用 `.visual-overlay-drawer` 覆盖打开，不永久压缩正文。

真实缺口：

- 缺少 `.visual-contract-title-page`；当前工具栏直接进入技术信息和 Deck Design System；
- 锚点部分只有“锚点身份”，缺少计划指定的 `[data-contract-logical-object="anchor-slide-evidence"]` 和用户可读的 `Anchor Slide Evidence` 章节；
- 计划点名的 `tests/test_v22_visual_review_projection.py` 不存在。其部分职责已由其他 Python 测试承担，但新增的 title/anchor evidence 结构仍需 Widget/验收测试覆盖。

### Task 6：宿主通知与 AI 回执

已满足：

- ReviewSession、视觉反馈批次和合同标记合同绑定 session、保存 artifact、source version、revision、receipt ref 和时间；
- 成功保存不会自动把宿主通知或 AI 回执设为成功；无适配器时显示不可用/未验证；
- Review Bridge 覆盖自动通知、独立重试、AI 验证、HTTP 超时、丢失响应后幂等重放、旧响应、stale source/revision 和能力探测；
- Python/Node/Widget 测试覆盖重开、唯一 session、receipt 绑定、不可用、超时、失败恢复和两类视觉保存槽隔离。

`real-host-capability-gap`：上述证据只证明确定性软件合同。当前没有真实 Codex Browser 宿主发送 receipt 或真实 AI 接收 receipt，因此不得标记真实回执通过。

### Task 7：验收自动化与证据边界

已满足：

- `run-v22-ui-acceptance.mjs` 在 360/760/1000/1440 CSS px 检查两类审核页；
- 已检查横向溢出、内容材料加载、PageDecision 42px/360px 2×2、三锚点、矩形几何、760px sticky 记录区、完整逐页合同和目录定位；
- 已检查内容 60 页和视觉合同 120 页；
- 每个视口生成 production `content-visibility:auto` 原始截图与 acceptance-only 展开截图；
- 报告明确 `proofEligible: false`、`realHostEvidence: false`，不会把本地 Playwright 当成真实宿主验收。

真实缺口与缺失证据：

- `assertVisualContractTextReadable()` 仍查询不存在的 `.visual-contract-title-page code`，且在每个 slide 循环中重复查询整页 selector；
- 验收脚本没有对 08 deck intro、章节导航、章节节点、review summary 做失败关闭断言；
- 验收脚本没有对 07 title page、Anchor Slide Evidence 和两个 overlay drawer 的完整结构做失败关闭断言；
- 当前截图是各视口 raw/expanded 全页截图，不等于计划点名的内容反馈前后、矩形反馈前后、目录 drawer、mark drawer、saved/unverified receipt 等交互状态截图；
- `tests/v22-prototype-fidelity.test.mjs` 与 `docs/validation/2026-08-17-review-surface-acceptance.md` 均不存在。

## 4. 实施顺序与提交边界

后续按以下顺序推进，每一阶段先有失败测试，再做最小实现，并保持独立提交：

1. Task 1 投影不变量：三锚点、内容 slide 唯一/连续顺序、章节成员与顺序；
2. Task 3 内容章节合同与 08 页面结构；
3. Task 4 移除未确认预设并恢复 07 顶栏结构；
4. Task 5 title page 与 Anchor Slide Evidence；
5. Task 7 语义选择器、结构/响应式/交互态证据和最终验收记录；
6. Task 6 只运行回归，不在没有失败证据时重复修改回执实现。

真实宿主联调保持独立 Gate。若当前宿主路径不可用，最终记录 `CapabilityGap`，不以本地预览、截图或自动化测试替代。
