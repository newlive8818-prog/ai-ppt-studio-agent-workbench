# C2 可见原生文字描边最小合同

状态：2026-09-11 总控在同 C2 持续制作与必要修复授权内明确委托；允许与显式字距切片一同独审/封包，工程校样入口仍是主优先级。源码、SDK、包、真实图形对照及用户验收分别记录，不由规格宣布通过。

## 1. 已有证据与目标

公开 SDK `textStyle.outline` 能给原生文字配置有限描边。已封存探针保留原 U+258E `▎`、不透明文字填充、同一 Microsoft YaHei 字族和 noAutofit，在 20.2 px 字号配 10.8 px 同色描边时，真实 SDK 导出/重导入测得 15×36 px 墨迹；21.2 px 配 10.2 px 也为 15×36。实际原生 `a:t`、字号与 `a:ln` 均核验，未把文字转为形状或位图。这是改变声明字号并加描边后的载体候选，不是保持原声明字号的横向缩放，也不是客户源图已匹配的结论。

当前产品未承接 outline。只增加用户已授权的显式文字描边，保留原文来源和可见原生字符；不拓展任意文字效果、阴影、透明度、虚线、端帽、连接样式或字体非等比变换。

## 2. 字段与单位

仅 v3 的普通、fragment 和 table-cell run 可带可选字段：

```json
{"outline": {"color": "#102030", "width": 1}}
```

`outline` 恰好包含 color/width，不接受 null、空对象、额外键或隐式默认值；不用描边时省略。color 是明确的六位十六进制不透明颜色；width 使用与 region/bbox 相同的 96DPI CSS px。拒绝 bool、字符串、非有限数和非正值。`width * 9525` 必须是可精确表示的整数 EMU 且 `0 < 值 <= 20116800`，否则写前 CapabilityGap/合同失败，不静默舍入。上界来自微软 [Open-XML-SDK DrawingML 官方 schema](https://raw.githubusercontent.com/dotnet/Open-XML-SDK/main/data/schemas/schemas_openxmlformats_org_drawingml_2006_main.json) 中 `a:CT_LineProperties` 的 `:w` 范围。

旧 run 与版本保持闭合；无 outline 不写默认描边。color/fill 互斥规则、原文/字号/字族/粗细/字距/Unicode span 及 noAutofit 全部保持，不能为描边删除文字的可见 fill。传输与输入值由确切源区域转录/独立校样判断提供，不自动按宽高求参数。

## 3. 唯一 writer 与结果检查

renderer 仅在字段存在时传 `textStyle.outline={style:'solid',fill:color,width}`，沿用同一 SDK 原生文字 writer。结果读取实际 `a:rPr/a:ln`，只接受已实测的有限输出：明确整数 w、一个不透明 solidFill/srgbClr、一个 prstDash=solid；其他属性/孩子、多个描边、透明/替代 fill 或未知线效果一律拒绝。

实际宽度按精确整数 EMU 核对，颜色按原六位值核对，不用几何容差吞掉一 EMU 改动。字段存在而 XML 缺失/改值时失败；字段未选而附加 a:ln，即便零宽，也失败。原生 a:t、字体、字号、填充、位置与完整 item 回组继续验证。正式结果门仍不接受主要内容位图化。

## 4. 可见性与设计还原边界

描边是可编辑文字样式，但不能单凭 XML 合法就判定该字符仍清楚可见或与源图一致。保留原不透明填充与原文是必要条件，独立实际图形核对仍需判断中心笔画、描边外沿、总宽高、位置、背景光晕与整页阅读。不能隐藏字符、把填充透明、加背景覆盖层或换 Unicode 来伪装匹配。

总控额外要求的背景色 outline 缩细 `｜` 目前只是有界只读探针，不能据此预先宣称合规或还原。未找到可用公开 group 横向缩放；同family轻字重的有限 Canvas 样本仍未达到目标 1–2 px 宽。这些限制不阻塞受控工程校样，但必须保留差异与未建立状态，不得提升 G1/交付。

## 5. 必要验证

保留旧 schema/真实 XML 对 outline 的 RED；新增闭合类型/单位/精度/上界拒绝用例，普通文本/fragment/table 与显式字距/渐变组合的 SDK 导出/重导入；原文、字号、可见填充、精确 a:ln 及回读 proto 检查。实际 PPTX 的缺描边、增零宽描边、改一 EMU、改色、增加透明/未知线效果、删改原字/填充必须失败。检验原样旧输入未获得 outline、同一 writer 与相关回归保持。

该有限载体在独立源码/规格质量审查与完整封包后才能交给总控使用；本任务不修改选定图、客户 Runtime、已交包或并行旧基线，不将 SDK 可行性写成客户最终验收。
