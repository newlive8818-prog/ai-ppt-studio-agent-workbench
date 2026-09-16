# C2 原生文本显式字距最小合同

状态：2026-09-11 总控在同一 C2 持续制作授权内明确委托实施与独审。提交基点 `cb3594c2318b9bc73aaa1c44a46ce06ecfcd0fe5`；本规格定义有限承接，不表示实现、真实页面还原、PowerPoint 或用户验收已完成。当前字体非等比能力核查与本字距合同分开记录，已交付 fragments/crops 包不修改。

## 1. 触发与责任

字体宽度调查暴露出当前 SDK 的公开 `textStyle.characterSpacing` 能保留原 Unicode、字体和字号并改变字符间距，但当前产品的闭合 run 和实际 XML 检查尚未承接。总控已明确授权同 C2 最小承接该能力。按定版图逐区域转录的显式字距属于忠实转换的有限样式，不赋予转换器重新排版、改字、计算自动适配参数或重新选图的权力。

本机 SDK 2.8.59 的真实导出/重导入探针显示：同一 24 码点原句在 20 px Microsoft YaHei 下，字距 -277 使测得墨迹由 403×20 变为 319×20；缩字号对照为 320×15。前者只证明载体能力，实际字符拥挤，不是与客户源图相符的证明。该参数不是客户默认值，不自动写入客户草稿。

总控随后回报独立实图测量：S05 首卡说明原文的源墨迹为 323×18，本机 16 px 微软雅黑的同原文为 324×18，20 px 为 406×20。因此仅比较 20 px advance 来认定草稿 16.1 px 会损失源字高不成立。该草稿应先做实际 renderer fit；字距实现不作为这句文字的既定前置，不自动套用 -277，也不改源 PNG。已封存探针保持其历史测量与范围，本规格按新证据纠正客户触发判断。

## 2. 闭合字段与单位

仅 v3 的既有文本 run 新增可选 `characterSpacing`，普通文本、source-mapped fragment 内的普通样式及既有 table cell 样式使用同一校验。其他字段仍闭合，旧版本不接受新字段。

```json
{
  "text": "原文示例",
  "fontFamily": "Microsoft YaHei",
  "fontSize": 20,
  "color": "#102030",
  "bold": false,
  "italic": false,
  "characterSpacing": -75
}
```

例子只说明字段，不是客户可提交的几何或数值。`characterSpacing` 是严格整数，单位为 1/100 pt；75 单位等于 1 个 96DPI CSS px。拒绝 bool、float、字符串、null、NaN 和超界值。有限范围为 `[-400000,400000]`，依据微软 [Open-XML-SDK DrawingML 官方 schema](https://raw.githubusercontent.com/dotnet/Open-XML-SDK/main/data/schemas/schemas_openxmlformats_org_drawingml_2006_main.json) 的 `:spc` NumberValidator；[公开 Spacing 属性](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.textcharacterpropertiestype.spacing?view=openxml-3.0.1) 对应实际 `spc`。

字段未给出时完全沿用原行为，不补默认值。明确 `0` 与未选择字段的合同身份不同，均不自动互转。原文、Unicode 码点区间、selected_copy/hash、字体、字号、粗细、颜色/渐变、图框、换行和原文覆盖均保持原规则。一个完整原 item 仍只覆盖一次。

## 3. 同一转换链和实际结果核验

既有 region → faithful plan → handoff 保留显式原值，不能在 compiler 中推算、补齐或丢弃。renderer 只在字段存在时将该整数传给公开 SDK `textStyle.characterSpacing`；继续 `noAutofit`，不使用 shrinkText、额外换行、负 margin、隐藏文本或形状替代字符。

结果门读取实际 PPTX 的每个原生 `a:rPr`：当该 run 明确选择字距时，必须有合法整数编码的 `spc`，且数值精确相同，不能用浮点容差、四舍五入或忽略一单位差异。删除、改动、改成非整数编码、转移到其他 run 都失败。未选择字距的旧 run 仍拒绝附加 `spc`，即便附加值为 0；不能为新能力普遍放开旧 XML 属性集。原 `a:t`、字号、字族、填充、位置、span 回组及整份输出 hash 检查继续执行。

## 4. 字形缩放与证明边界

字距改变字符之间的距离，不能改变单字符墨迹宽度。S05 原字符 `▎` 与 S06 原字符 `｜` 的字形非等比问题仍需另行检查 SDK 公开能力；不能以此字段宣布已解决，更不能换 Unicode、隐藏字符、手改输出 XML、把字符转成形状或位图。若后续公开 group 变换可被实际导出/重导入证明，将作为另一个明确受审的有限合同，不悄悄加入本字段。

本规格验证要求包括：先在旧代码观察真实合同/结果门拒绝，再验证明确字距的普通/fragment/table run 与旧字段保持；实际 SDK 导出、重导入保留原文/字号/字距；实际 PPTX 的删除、一单位改动、非整数编码、旧 run 注入 0、改原文/字号等反例必须拒绝。只跑受影响回归，源码与包分别独审。SDK 像素宽度接近、字距可编辑或结构门通过，都不能替代客户字形与排布对照、跨页共同规范、PowerPoint 和用户判断。

总控继续持有客户草稿、正式 Runtime、真实三页转换与验收记录。本源码任务负责有界实现、测试、独审、独立候选封包、本地提交和交接；不改平行四基线、客户定版图或已交候选包。
