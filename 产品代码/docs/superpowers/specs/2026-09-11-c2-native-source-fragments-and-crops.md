# C2 原文片段映射与定版图素材呈现最小合同

状态：同一 C2 Change 内获授权的三页忠实转换能力细化；实现、独立审查、封包及真实页面效果分别以唯一验证台账记录，本文不表示已经通过。依据总控四基线 §1.3 的映射下拆分组合与定版图设计权威，以及 2026-09-11 对 S06 实图缺口的明确委托。继续现有 Python 业务内核、v3 region/plan/handoff 与 Codex Presentations 唯一 writer；不改原文、材料用途、用户验收或 Gate。

## 1. 完整原文的可定位片段

触发：完整原 item 内的标题、分隔符、正文或包含原空格的文字，在确切选定图中具有独立位置；顺序 runs 和自然换行不能忠实表达。一个 text region 的 content.items 继续恰好拥有一个完整原 item，selected_copy 与其 hash 不改变。计划中的逻辑对象仍对应该完整 region，不新建事实项或猜测字符串。

仅 v3 text region 增加互斥分支：

```json
{
  "appearance": {
    "fragments": [
      {
        "span": [0, 2],
        "bbox": [10, 20, 40, 24],
        "appearance": {
          "runs": [{"text": "示例", "fontFamily": "Arial", "fontSize": 20,
                    "color": "#102030", "bold": false, "italic": false}],
          "alignment": "left", "verticalAlignment": "middle",
          "insets": [0, 0, 0, 0], "lineSpacing": 1, "wrap": "none"
        }
      }
    ]
  }
}
```

该例仅说明字段，不能作为客户几何。外层 appearance 只允许 fragments，不能混入旧 runs/其他样式。每个 fragment 恰为 span/bbox/appearance，不递归；其内部 appearance 复用既有有限文本样式和 color/fill 互斥规则。

- span 是 Unicode 码点索引的左闭右开区间 `[start,end)`，不是 UTF-16 单元。Python 与 JavaScript 必须使用相同码点语义；不得归一化、删改组合字符、符号或空格。
- span 以原字符串顺序从 0 连续覆盖到完整长度，每段非空，无重叠、缺口、重复、倒序或越界。每段 runs.text 拼接必须逐字等于完整原 item 的该 span；冗余 runs.text 不成为第二文案来源。
- bbox 使用与所属 region 相同的绝对 96DPI 画布坐标，须在该 region 和画布内；由实图转录与独审提供，不由文字排序、自动布局或经验模板生成。
- 原 item 的身份/内容覆盖只计算一次；分片不改变跨页文案顺序、标题身份、材料角色或 TargetBinding。

renderer 在原生输出层按原 span 顺序生成可编辑文本子对象，稳定身份为 `<原object_id>::fragment:<start>:<end>`；输出映射和结果证据在这些子对象行增加 span，旧非fragment行字段不变。写前验证展开身份唯一，原 region 的 z_order 与页内对象顺序继续约束输出；未建立跨 region 交错堆叠或自动避让能力。

结果检查依据确切 handoff，逐子对象核验原生文字载体、身份、span、坐标与既有全部有限外观，随后按 span 回组并与完整原 item 比较。缺字、改字、多字、重复对象、漏对象、错误映射、隐藏文字或任意换字体/填充均不能作为通过。几何合同与实际字体栅格的视觉还原仍须独立对照。

source-image-derived relation-path 继续绑定完整 region/item，按原路径绘制，不猜片段端点。旧物理 connector 若指向包含 fragments 的 region，须在写前报 CapabilityGap，不能选择第一个子框冒充原端点。表格、旧 runs、原生渐变文字及其他既有载体规则保持。

## 2. 原材料事实身份与定版图呈现来源

触发：Image 2 使用获授权真实材料形成已选图的实际视觉呈现；Native 必须还原该呈现，不能因为要求 asset hash 等于原 JPEG 就静默换回原图。

仅 v3、kind=image、带已选 real-material 的原 material_binding 时，可使用：

```json
{
  "material_binding": {
    "atom_id": "原材料身份",
    "source_ref": "原来源引用",
    "content_sha256": "原材料字节SHA256",
    "use": "real-material"
  },
  "appearance": {
    "asset_ref": "本页TargetBinding.target_image_ref",
    "asset_sha256": "本页TargetBinding.target_image_sha256",
    "crop": [0.1, 0.2, 0.3, 0.4],
    "render_source": "selected-image-crop"
  }
}
```

示例仅表示字段来源，不是可直接提交的有效 ref/hash。material_binding 四字段保持原材料事实/用途身份，仍须逐项属于本页选定 material_roles，所有已用真实材料仍须区域覆盖。新分支不得置空绑定、伪造原图 hash、创造 MaterialAtom 或跳过原来源/授权/独立来源核对。

appearance 的 asset_ref/hash 必须严格等于本页确切 TargetBinding，实际资产为整张选定图的原字节；不得接受任意预裁切图、其他页图、其他 asset 或仅凭相似度选择。crop 仍是该整张图上的归一化 `[x,y,width,height]`，由实图区域转录；真实尺寸、完整解码、字节 hash、裁切边界和 crop/bbox 比例逐项验证。允许一个已选原材料角色按实图出现位置有多个不同 crop。无 marker 的既有分支仍要求呈现素材字节等于绑定的原材料 hash。marker 不适用于无绑定图、非 real-material 或 decoration，不成为规避来源覆盖的入口。

## 3. 显式裁切的原生实现

真实 SDK 探针发现默认图片比例锁可能按整张源图重算显式 crop/图框；fit=contain 或 cover 本身不足以证明忠实裁切。对经过既有 crop/bbox 等比例前置校验的明确局部裁切，使用 SDK 公开属性保留确切图框和 crop，不改源图字节，不新增图片 writer 或静默裁切文件。此必要修复也覆盖既有无字 decoration 的局部裁切：S06 实际草稿同样使用整张选定图与明确 crop。

结果读取实际 PPTX，确认完整嵌入资产字节 hash、图框、裁切值和未改的原生载体；新 marker 还确认其选定图身份和比例行为。SDK 局部像素对照属于载体证据，不代替客户照片在实图中是否真正对应原材料的独立判断，也不允许把主要文字烘在无字装饰图中。

## 4. 验证与交接边界

先保留合同和真实 SDK 的 RED，再验证新片段、完整 Unicode 回组、原生可编辑性、选定图完整字节/裁切、旧部分裁切、相同原角色多次呈现与拒绝路径。旧 runs、端点/渐变和非片段输出字段需要相关回归；不重复无关网络或全项目测试。独审须使用实际 PPTX 篡改反例核验结果门禁，并独立核对冻结源与候选差分。

客户草稿在转录中可变化，适配核验必须记录实际读取的 hash；只通过 schema 不等于正式 inventory、完整视觉通过或 PowerPoint 验收。最终候选在上一份受审完整 Native+repair+修订表达包上覆盖受审的有限改动，原包和在途请求不改。客户 Runtime、正式对象提交与真实三页输出继续由总控串行持有。
