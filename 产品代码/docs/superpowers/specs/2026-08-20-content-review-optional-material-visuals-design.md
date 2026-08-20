# 内容审核页可选图片材料与零图片布局设计

## 1. 文档状态

- 日期：2026-08-20
- 状态：`用户已确认设计，待形成实施计划，尚未实现`
- 决策来源：用户明确确认“没有图片的页面不用一定要求证据图片”，并在两种零图片前端处理方式中选择“隐藏图片区，页面实际文字扩展到整行”
- 适用范围：AI PPT Studio 内容全稿审核页、ReadingDeckBlueprint 的页面材料画面合同、ContentReviewProjection、ContentReviewPageViewModel 及其活动 React 表面
- 不改变：内容审核页既有用户验收结论、四类 PageDecision、ContentReviewBatch、内部证据治理、真实客户 ReviewSession 能力边界

## 2. 问题与结论

当前目标合同和 Python validator 把整套 `material-backed | mixed-evidence` 材料模式错误地下沉为“每一页必须至少存在一个 `material_view`”。这会让合理的纯文字页被迫配置图片，并把“证据充分”与“存在证据图片”混为一件事。

正式结论：

1. 页面是否有充分证据，由内容身份、`evidence_bindings`、来源关系和事实与证据硬门判断；
2. `material_views[]` 只表达这张页面是否存在对用户审核有直接价值的图片材料或页面画面；
3. 所有材料模式中的单页都允许 `material_views = []`；
4. 没有图片不能自动产生 `evidence` PageDecision，也不能阻断 ReadingDeckBlueprint；
5. 前端收到空 `materialVisuals[]` 时，不渲染图片区、图片区标题或大面积空状态，页面实际文字扩展到整行；
6. 只有存在至少一个真实可审核画面时，才显示“文字与图片材料一起审核”及对应画面；
7. 系统不得用通用装饰图、无关截图、网络图片或 AI 生成图片填补空位。

## 3. 前端行为

### 3.1 零图片页面

输入：

```text
materialVisuals = []
```

页面行为：

- 保留“这一页的目标”“希望客户形成的判断”“页面实际文字”、阅读问题和 PageDecision；
- 不渲染“文字与图片材料一起审核”标题；
- 不渲染虚线空框、“本页暂无可审核的页面画面”或补图提示；
- 正文容器从双栏切换为单栏，并占满该页面可用阅读宽度；
- 不改变当前页序、章节节奏、保存状态或审核动作；
- 读屏结构中不存在一个没有内容的图片区 region。

### 3.2 有图片页面

输入：

```text
materialVisuals.length >= 1
```

页面行为继续遵守已验收前端合同：

- 宽视口使用“页面实际文字 / 文字与图片材料一起审核”双栏；
- 窄视口按正文在前、图片在后的单栏顺序呈现；
- 图片近视口加载；
- 前端只读取 ViewModel 明确提供的画面，不显示来源文件、页码、区域、用途、处理方式或证据身份目录；
- 图片读取失败只表示该画面当前不可读，不改变本页证据判断或 PageDecision。

本设计不确定多图片的最大展示数量、分组或网格策略；该问题继续作为下一项独立产品选择，不能由实现自行增加轮播、抽屉、材料浏览器或隐藏上限。

## 4. 数据与服务边界

### 4.1 内部 ReadingDeckBlueprint

`material_views[]` 保持可追溯的内部材料画面记录。每个存在的画面仍必须满足当前闭合字段、项目内安全路径、来源身份和页码等验证；本设计只删除“material-backed/mixed-evidence 每页至少一张”的数量强制，不删除单条画面的真实性和安全验证。

`evidence_bindings[]` 与 `material_views[]` 分工如下：

| 对象 | 负责 | 不负责 |
|---|---|---|
| `evidence_bindings[]` | 页面文字、判断和来源事实的可追溯证据 | 决定前端必须显示图片 |
| `material_views[]` | 对审核当前页面有直接价值的图片材料或页面画面 | 证明全部文字证据充分 |

材料模式继续作用于整套证据身份和禁止外推规则，但不决定每页图片数量。

### 4.2 正式外部投影

`ContentReviewProjection.slides[].material_views` 继续是数组并允许为空。外部单条字段仍保持：

```text
material_view_id
asset_ref
```

投影不增加 `has_image`、`empty_reason` 或其他与数组长度重复的字段。前端以 `material_views.length` 形成确定性布局，不保存第二套事实。

### 4.3 ContentReviewPageViewModel

`materialVisuals[]` 继续由 adapter 从 `material_views[]` 原序转换。零长度是正常成功状态，不是 adapter error、CapabilityGap 或证据缺口。

前端布局规则：

```text
materialVisuals.length === 0 -> text-only page layout
materialVisuals.length > 0   -> text-and-visual page layout
```

### 4.4 资源安全

只有非空 `material_views[].asset_ref` 进入 Review Bridge 资源白名单。空数组不触发项目资源读取。已有项目根约束、符号链接拒绝、文件类型、大小和精确引用检查保持不变。

## 5. 当前实现差距

已存在：

- TypeScript ViewModel 可以表达空 `materialVisuals[]`；
- 活动 React 表面能接收空数组；
- Review Bridge 能处理没有内容图片引用的投影；
- 外部内容审核投影已经收窄，不需要恢复来源元数据。

尚未实现：

- Python `validate_reading_deck_blueprint()` 仍强制 material-backed/mixed-evidence 每页至少一个 `material_view`；
- 活动 React 表面仍渲染“文字与图片材料一起审核”和大面积空状态；
- CSS 仍默认建立正文/图片区双栏；
- 基于旧规则的合同、集成和 UI 测试仍需要更新；
- 真实客户材料解析、图片提取、页面关联与选择机制仍是独立研发能力，不能由本设计声称完成。

## 6. 错误和状态

- 零图片页面：正常状态，不显示错误、警告或补图动作；
- 图片引用存在但读取失败：只在对应图片区显示真实读取失败和重试，不转为“证据不足”；
- 图片引用非法或越界：投影/资源读取失败，不能静默替换为通用图片；
- 页面文字证据不足：由事实硬门或用户 `evidence` 判断处理，与图片数量无关；
- sourceVersion/revision 冲突：继续使用现有审核会话冲突与恢复合同。

## 7. 验收标准

1. material-backed、mixed-evidence、proposal-led 三种模式均允许某一页 `material_views = []`；
2. 有图片的其他页面仍保留完整、安全、稳定顺序的材料画面投影；
3. 零图片页 DOM 不出现“文字与图片材料一起审核”、图片区 region、空状态框或补图提示；
4. 零图片页“页面实际文字”占满页面内容宽度，正文、阅读问题和 PageDecision 完整；
5. 有图片页继续显示已确认的图片栏标题和画面；
6. 零图片不会触发资源读取；
7. 图片读取失败不会改变 PageDecision 或证据状态；
8. 不出现来源元数据目录、证据入口或其他已删除后台模块；
9. 360、760、1000、1280×720、1440 CSS px 无横向溢出；
10. 10、24、60 页混合有图/无图长稿仍可连续阅读，图片继续近视口加载；
11. 当前内容审核 UI 既有验收结论不被重新解释为 Runtime、真实宿主、AI 回执或 G0 通过。

## 8. 非本设计范围

- 多图片最大展示数量；
- 多图片主图/辅助图、网格、排序或分组；
- 用户可见来源标签或证据 Browser；
- 自动材料解析、图片提取和图片选择服务；
- Image 2 视觉资产；
- 视觉专业审核页；
- ReviewSession、宿主通知、AI 接收回执或 G0。

以上事项必须单独确认，不得在实现零图片布局时顺带增加。
