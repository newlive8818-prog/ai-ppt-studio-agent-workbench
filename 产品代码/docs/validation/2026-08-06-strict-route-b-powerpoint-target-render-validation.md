# 严格路线 B 与 PowerPoint 目标渲染验证记录

**日期：** 2026-08-06

**状态：** `已验证（当前实验）`

**结论边界：** 本记录证明严格路线 B 的生产顺序和 PowerPoint for macOS 目标渲染证据链在本次重庆机电实验中可行；不证明产品增量已研发实现，不证明跨项目、Windows 或 WPS 已稳定兼容。

**对应设计：** [Presentations 主导生产与目标渲染治理设计](../superpowers/specs/2026-08-06-presentations-led-production-and-target-render-governance-design.md)

## 1. 验证问题

1. 完整视觉合同形成后，由 Presentations 直接完成原生视觉设计和 PPTX 实现，是否可以形成质量更稳定的正式生产路线？
2. Image 2 在原生首版后只生成非语义资产，是否可以增强背景而不改变业务结构和真实证据？
3. 开发渲染通过之后，能否用 Microsoft PowerPoint 桌面版实机导出证明字体、换行、层叠和几何没有再次掉级？

## 2. 严格路线 B 八页实验

### 2.1 路线政策

权威外部运行数据：

`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/route-policy.json`

政策固定顺序：

1. 独立视觉团队依据冻结内容形成可执行视觉合同，不使用 Image 2 整页结果；
2. Codex Presentations 依据视觉合同直接完成八页原生设计；
3. 首轮原生渲染后，Image 2 仅生成非语义背景、纹理、插画或装饰资产；
4. Codex Presentations 将受控资产加入原生页面并完成最终渲染。

禁止项包括：Image 2 改变页面结构、信息层级或业务关系；读取路线 A/C；用生成图替代真实证据；使用整页位图作为最终页面。

### 2.2 关键产物

- 视觉合同：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/03-visual-contract.txt`
- 原生首版：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/native-first.pptx`
- 原生首版全页渲染：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/native-first-render/`
- Image 2 资产状态：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/image2-asset-pack/status.txt`
- 最终 PPTX：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/重庆机电智能制造全域数字化解决方案-路线B-Presentations主导.pptx`
- 最终 QA：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/routes/B-Presentations主导/output/qa-record/final-qa-summary.txt`

### 2.3 Image 2 资产结果

共接受两项资产：

| 资产 | SHA-256 | 接受用途 |
|---|---|---|
| `industrial-blueprint-paper.png` | `7ea0e31e03c2ebb516f3bfa3e34d075b5db9bb0efd0fcdad69082ad66f3126d5` | E02/E04/E07/E08 非语义背景 |
| `cyan-yellow-industrial-veil.png` | `e2097a9bf19034b4e2ec2ff0f5f6438b3d8f98cfd9fa3822311b0470e2c76f1b` | E03 非语义背景 |

检查记录明确未观察到文字、数字、符号、Logo、箭头、业务关系、机器、工厂、系统截图、人物或水印。资产只在原生首版冻结后生成，并以独立图层加入。

### 2.4 最终 QA 结果

- 8 页、16:9、8 张 1920×1080 最终渲染通过；
- Presentations `slides_test` 无溢出，PPTX 压缩包完整；
- 8 页均含 `[Sources]` 讲者备注；
- 原生首版 SHA-256：`1c387c9709bd1af22eb5c0baf8e3f22b3df04af86343fc4059723cc8b952d73b`；最终版 SHA-256：`c437590ff191ac9d922b0567ad88004e38e3f4069aa90f5461db332e28032b1c`；
- 标题、正文、标签、阶段、断点、箭头、架构层级、结论、页码和品牌对象保持原生可编辑；
- 真实照片、系统截图、Logo 和案例证据均未被生成资产替代；
- Image 2 只改变 E02/E03/E04/E07/E08 的背景纹理/光效，E01/E05/E06 未使用 Image 2 层；
- 原生首版到最终版未改变页面顺序、冻结事实、能力、业务关系和真实证据。

当前证据支持“严格路线 B 的介质边界可执行”，但本八页 QA 主要来自 Presentations 开发渲染，不能单独承担目标软件真相源。

## 3. 三页锚点 PowerPoint 实机验证

### 3.1 冻结输入

- PPTX：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/experiments/视觉合同多智能体-v1-v2对照/output/v3/anchor-v3/锚点页-v3.pptx`
- SHA-256：`10f20be16d8042174eb657e29941bd96a2f3425321f77dae50c0a70a0b5fbf14`
- QA 目录：`/Users/defei/Documents/AI-PPT-Workspace/projects/重庆机电视觉生产三路对照实验-v1-459b0dcb/experiments/视觉合同多智能体-v1-v2对照/output/v3/qa/20260806T175558+0800/`

### 3.2 目标环境

- 操作系统：macOS 26.5.2，Build 25F84；
- 目标软件：Microsoft PowerPoint for macOS 16.111.2；
- 实机导出时间：2026-08-06 17:57 +08:00；
- 导出物：3 页 PDF（960×540 pt）和 3 张 1920×1080 PNG；
- PPTX 导出前、导出后和 QA 副本 SHA-256 完全一致。

### 3.3 字体证据

本机实际存在：

- PingFang SC Regular / Medium / Semibold；
- Noto Sans CJK SC Regular；
- Verdana Regular。

PowerPoint for macOS 实机渲染未观察到静默替代、自动缩字、额外换行、遮字或截断。

平台边界：`PingFang SC` 在 Windows 不保证存在，可能替换为微软雅黑并改变字宽、换行和溢出。因此本次结果不能外推为 Windows 已通过。

### 3.4 结构与文件检查

- 3 页共 60 个文本框、61 个形状、9 个图片对象和 3 个 notes；每页 notes 含 `[Sources]`；
- 自动适配：`a:normAutofit=0`、`a:spAutoFit=0`、`a:noAutofit=74`；
- 模板计划和模板一致性：`pass`，issueCount=0；
- `slides_test.py`：`Test passed. No overflow detected.`；
- `unzip -t`：无错误；
- 实机目标渲染审查：`passed`，无定向返工。

### 3.5 逐页关键结果

- E02：两行主标题、副标题、六阶段业务带、三个黄色断点、影响轴线/节点和两行决策结论均完整；未重现浅灰无语义残线。
- E06：MES 中央主视窗、APS/WMS 两翼、输入箭头和黄色回流箭头位置正确；箭头接触 APS 底边且不进入截图关键内容。
- E08：冻结结论保持指定两行，右侧统一案例信息面、青色证据脊柱和分隔完整，未退回三卡片。

## 4. 四重硬门结论

| 质量门 | 本次结论 | 证据摘要 |
|---|---|---|
| 业务语义 | 通过 | 冻结文字、业务关系、真实证据和页面主张保持 |
| 视觉完成度 | 通过 | 三页关键构图、层级、共享边界、箭头和信息面在实机导出中成立 |
| 排版工程 | 通过 | 无溢出、自动缩字、裁切、对象丢失；模板和 PPTX 结构检查通过 |
| 目标软件渲染 | 通过 | PowerPoint for macOS 16.111.2 实机 PDF/PNG 导出并逐页复核，哈希未变 |

## 5. 可采纳结论

### 已确认

1. 一期默认严格路线 B 是当前更合适的正式生产关系。
2. 视觉合同是设计意图、专业边界和质量要求来源；Presentations 是原生视觉设计与 PPTX 实现执行者。
3. Image 2 的正式职责应收窄为原生首版后的非语义资产，不承担构图和业务语义。
4. 开发渲染不能替代目标 PowerPoint 实机证据。
5. G2 和 G4 应使用业务语义、视觉完成度、排版工程、目标软件渲染四门共同放行。
6. 当前生产平台实机通过即可满足默认项目；跨平台明确要求时追加目标平台复验。

### 待验证

1. 严格路线 B 在不同客户、不同页面家族和 24–60 页完整售前方案中的稳定性；
2. 多轮视觉智能体讨论能否在跨项目中持续提高视觉合同质量，而不是只增加文字和轮次；
3. PowerPoint for Windows 中的字体替代、字宽、异常换行和几何稳定性；
4. macOS 与 Windows 双平台交付的成本、自动化和返工阈值；
5. WPS 独立兼容性。

## 6. 证据治理要求

- 本记录只引用 `/Users/defei/Documents/AI-PPT-Workspace` 中的外部运行数据，不把 PPT 运行产物复制进产品仓库；
- 外部运行数据仍属于 PPT 运行空间，产品需求、系统设计、源码和运行数据目录边界保持不变；
- 后续真实项目若出现反例，应新增验证记录并重开受影响产品合同，不静默覆盖本记录；
- 任何“跨平台兼容”“WPS 兼容”或“跨项目稳定”声明必须有新的独立证据。
