# v1.6 Slice 06 三表面 UI 验收记录

**日期：** 2026-08-10

**状态：** `已通过（schema 3 合同、组件、构建与浏览器自动化）`

**证据边界：** 本记录证明 schema 3 权威投影、360/420/480px Native Widget、760/1000/1440px 专业审阅页、200% 缩放、60/120 页长文档、键盘/抽屉交互和构建产物通过本地确定性验收。它不证明真实 Codex 宿主长期侧栏能力，不证明真实售前项目完成，也不证明 macOS/Windows PowerPoint/WPS 四目标桌面实机兼容。

## 1. 验收对象

- Widget：360px、420px、480px；
- 内容与视觉专业审阅：760px、1000px、1440px；
- 审阅可访问性复验：上述三种宽度分别按 200% 缩放检查；
- 长文档：60 页内容审阅、120 页视觉合同；
- 正式运行时合同：schema 3 `WorkspaceProjectionService`、`ReviewService`、exact review mark、host-aware review routing；
- 视觉合同阅读结构：整套 PPT 框架、Deck Design System、原生可编辑锚点页身份、四目标桌面证据矩阵、逐页冻结内容与实现合同。

## 2. 新鲜回归结果

| 检查 | 结果 |
|---|---|
| `python3 -m unittest discover -s tests` | 184/184 通过 |
| `npm run test:node` | 11/11 通过 |
| `npm run test:widget -- --reporter=dot` | 33/33 通过 |
| `npx tsc -p widget/tsconfig.json --noEmit` | 通过 |
| `npm run build` | 通过，生成自包含 Widget HTML |
| `npm run accept:v16-ui` | 通过，15 张截图、1 份 JSON 报告 |
| `python3 scripts/build_acceptance_ledger.py` | 恰好生成 104 条稳定要求 |
| `python3 -m unittest tests.test_acceptance_ledger -v` | 3/3 通过 |
| `git diff --check` | 通过 |

浏览器验收报告：[v16-ui-acceptance.json](../../output/playwright/v16-ui/v16-ui-acceptance.json)。报告中的证据范围固定为 `deterministic schema 3 browser contract evidence; not real Codex host or desktop PowerPoint/WPS proof`。

## 3. Widget 与专业审阅结果

### 3.1 Native Widget

| 宽度 | 首次挂载 | 横向溢出 | 主操作 | 控制台错误 |
|---:|---:|---:|---:|---:|
| 360px | 117.6ms | 0 | 1 | 0 |
| 420px | 86.1ms | 0 | 1 | 0 |
| 480px | 85.7ms | 0 | 1 | 0 |

五空间均直接消费正式工作台投影；React 不根据展示字段推断 Gate。交付空间保留 macOS PowerPoint、macOS WPS、Windows PowerPoint、Windows WPS 四条独立目标行。

### 3.2 专业审阅

- 内容与视觉审阅在 760/1000/1440px、100%/200% 共 12 个组合中均无横向溢出、无控制台错误；
- 64px 单行顶栏、目录与标记抽屉互斥、Escape 关闭、焦点进入与恢复、稳定锚点定位全部通过；
- 2 页普通审阅不启用长文档占位，截图中不存在 `content-visibility` 导致的大段空白；
- 状态来自正式 `gate_status` 与权威投影；G2 失败时不会显示“合同通过”“四门全部通过”等通过结论；
- artifact 引用、PPTX SHA-256、目标环境、应用版本、字体引用、锚点身份和证据身份完整保留，不做截断；
- schema 3 确定性夹具不再被描述为真实客户项目或桌面软件证据。

截图目录：[v16-ui](../../output/playwright/v16-ui/)。关键截图包括 `content-review-760.png`、`content-review-1440.png`、`visual-review-760.png` 和 `visual-review-1440.png`。

### 3.3 长文档

| 审阅类型 | 页数 | 挂载时间 | 唯一锚点 | 横向溢出 | 控制台错误 |
|---|---:|---:|---:|---:|---:|
| 内容审阅 | 60 | 177.1ms | 60 | 0 | 0 |
| 视觉合同 | 120 | 183.6ms | 120 | 0 | 0 |

24 页以上启用 `content-visibility:auto` 与 `contain-intrinsic-size:auto 720px`；完整长中文、文件名、无断点字符串、讲解稿和来源仍存在于连续文档中，没有分页依赖或字段截断。

## 4. 宿主能力降级合同

- 宿主可用宽度至少 760px 时，同一审阅资源在支持的宿主显示模式中打开；
- 侧栏宽度不足 760px 或不支持持久宽区域时，先请求 fullscreen/独立形态，再渲染同一资源与同一保存合同；
- fullscreen 或宿主能力调用失败时，不修改项目状态，不压缩出第二套审阅 UI，只显示明确的继续操作提示；
- 宿主能力只作为临时上下文，不写入项目状态或浏览器本地存储。

上述行为已有组件和 Node 合同测试，真实 Codex 宿主交互仍属于 Slice 07 的待验证证据。

## 5. 账本、链接与目录边界

- 三份权威需求源重新生成 104 条要求，ID 唯一；本阶段未把自动化证据冒充最终通过，因此 104 条仍保持 `unproven`，待后续按证据种类闭合；
- 四份基线共检查 58 个相对链接，缺失 0；其中 8 个唯一原型引用全部存在；
- 最终专业审阅原型 `产品代码/prototypes/06-fullscreen-contract-review-exploration.html` 存在；
- 确定性 UI seed 位于系统临时目录，浏览器报告与截图只写入 `产品代码/output/playwright/v16-ui/`；
- 本轮命令没有把产品源码或测试运行数据写入并行 `PPT  web app`，也没有写入默认 `/Users/defei/Documents/AI-PPT-Workspace`。

## 6. 后续阻断项

以下证据未在 Slice 06 中宣称完成：

1. 插件正式包装、安装、重装与恢复；
2. 真实 Codex 宿主中的侧栏与独立打开双形态；
3. 一个真实售前项目从输入到聊天文件交付回执的完整闭环；
4. 同一真实 PPTX SHA-256 在 macOS PowerPoint、macOS WPS 桌面版、Windows 11 PowerPoint、Windows 11 WPS 的 G2/G4 四门实机证据；
5. 104 条 Requirement Ledger 按自动测试、运行时、真实项目和目标软件证据逐条闭合。

这些项目直接进入 Slice 07，不以本记录替代。
