# C2 来源恢复 A：正式 finding 与两层排除合同

日期：2026-09-10；Change：CHG-IL-C2；起点：ad1161170f90e3bba9972bd6413a2af9bad078ab。状态：独立规格 Review 无 Critical/Important，三处表述消歧已补齐，按主计划 §12.2 既有授权实施；代码和真实运行证据另记。此文细化[已诊断方案](../../validation/c2-image-led/source-reference-recovery/diagnosis-and-minimal-plan.md)，并以本节精确合同补齐总控 P1；不变更用户目标或新增批准门。

## 1. 范围与顺序

公开材料工具 → 正式 finding 登记 → 当前内容引用预检 → 有真实来源的原子/输入包。A 单独提交；B Image2 wrapper/配置/离线协议准备后续独立提交。两切片不写客户 Runtime，不重发其内容/G0，不接触凭据内容，不安装/改宿主配置、不发送真实图片请求、不合并/Push。当前真实 revision19 的71段认可文案和G0保持；测试材料全部合成。

实施顺序：规格独立 Review → 新行为 RED → 正式来源服务与闭合公共分支 → 内容入口和材料解析共用校验 → 排除规则与真实公开路径 GREEN → 适用全量回归 → 固定候选独立规格/代码 Review → 本地候选提交。

## 2. 固定 finding 生产入口

保持43个公开工具，扩展 `add_ai_ppt_material.materialType="finding"`。该分支必需闭合输入为既有公开 projectRoot/expectedRevision 加 `materialInventoryRef`、`sourceId`、`sourceSha256`、`sourceLocation`、`contentKind`（text/image）、`exclusionMode`（scope/image-content）。`sourceLocation` 沿用闭合 typed selector，不接受自由文本定位。image-content 只允许 image。不得接受调用方 content hash、任意 artifact kind/payload、value/dataBase64/filename/mimeType/label 等导入字段；text/url/bytes 分支也不能夹带 finding 字段。未知字段在 MCP、直接 bridge/service 入口均拒绝。

command_id 由现有 bridge 根据完整请求派生，不新增公开 commandId；完全相同请求和原 expectedRevision 的重试沿用原命令身份，不能将刷新 revision 的新请求混称相同命令。

专用服务固定登记 kind=`material-finding`。规范化 payload 闭合字段为 schema_version=1、artifact_type=`material-finding`、project_id、material_inventory_ref、source_id、source_sha256、source_location、content_kind、exclusion_mode，以及**服务端从实际提取字节派生**的 content_sha256。不保存第二份客户原文、图像或素材库；这些都是当前材料清单和确切源字节的派生引用。

登记前验证当前 inventory/ref、同项目 source_id、注册hash和真实文件hash一致、selector真实存在且可重放提取。页级text finding证明页/提取的有效性，不代表整页所有图片均可使用；object/image须确切唯一对象，支持能力沿用 OOXML/图片/文本提取器。URL、inline 文本或其他不能重放的来源应明确 CapabilityGap，不凭库存hash放行。既有 text/url/bytes 导入行为保持；本切片不伪造这些来源的可重放快照。

以现有 Kernel CAS/事件/幂等登记**固定 detached artifact**并返回其引用；调用方不能传入 detached_artifacts 或任意槽位。不增加/修改 inventory、Mission、四内容对象或任何 Gate/head；只增加本次事件、制品和命令幂等记录。相同 command/相同语义返回原ref不写；相同command不同语义拒绝。新的陈旧revision命令失败前不写任何源副本、artifact、event或state。记录读取快照对应的revision并用CAS提交，避免核验后将旧inventory证据写入新revision。

## 3. 当前来源引用与写入前预检

共用正式来源读取/提取服务，ImageLedMaterialResolver 和内容写入服务不各自实现相互矛盾的规则。

新生产 EvidenceBook 中 material-backed/mixed-evidence 的 declared 和 excluded refs 全部必须是可解析的正式finding，逐项核验当前inventory、source字节hash、typed selector、实际提取hash。proposal-led 无材料场景仍有效，不要求空想finding；其已有禁止客户事实规则不变。DecisionContext、Fit、Blueprint及内容硬门再次校验当前证据来源，保留现有严格lineage与逐页declared membership规则，不能通过更晚入口消费历史无效引用。

旧不可变制品可只读保留；旧kind/旧payload的只读兼容不得被当作新生产证明。现有通用合同测试可仍使用符号ref测试纯结构；涉及生产服务、Gate或材料发送的合成fixture需建立正式finding，不允许以跳过校验使旧fixture“通过”。至少一条公开MCP全路径成功用例由公开add-material/finding生产所有finding，不能Kernel预注入。source范围变化/库存替换使旧finding失效。

**页级 declared finding 与页内 excluded object finding 可以共存。** EvidenceBook 登记只验证两侧引用有效和引用集合不相交，不因为几何交集把整页证据禁掉。真正派生atom时才对本次实际发送selector做范围/内容排除；页级atom不能因为上游declared合法而越过页内排除。

## 4. 两层排除及 P1 图片内容身份

### 4.1 范围层（所有有效排除都保留）

EvidenceBook.excluded_material_refs 中的finding，无论exclusion_mode为何，都以真实source_sha256和source_location保护被禁区域。scope模式表示按出现区域限制，相交内容所有use均拒绝；不增加用途排除例外或新字段，用途许可仍由allowed.uses独立核验。不自动把相同图像在其他有效来源的出现全部禁用。授权scope原有sourcehash+selector排除仍是独立的限制，不能被EvidenceBook放宽。

选择器相同对象须比较page/object_id；同页不同对象应不相交。table-range同样先比较page/object_id，再比较行列区间。whole-source、page对子对象、同对象、同表范围的相交排除保持；未知跨坐标关系仍失败关闭。比较对称。合法页级证据不免除实际整页atom的拒绝。

### 4.2 内容层（明确 image-content 排除）

仅当一个有效image finding **被当前 EvidenceBook列入excluded_material_refs** 且exclusion_mode=image-content，表示本次禁止这张图片的确切内容。单纯登记finding不自行写入排除决定；有效的排除finding登记本身是成功路径。

解析器从当前inventory与该finding绑定的真实来源**重新提取图片字节**，核验来源、selector和服务端存储hash，再派生可信禁止集合。禁止集合仅存在于当前项目/当前调用的已核验内存快照，不是全局黑名单或平行素材库。不得相信调用方声称的 content_sha256，不得只读元数据hash后免去真实提取。

候选image atom也必须实际提取并核验hash；其**实际提取字节SHA256** 命中可信禁止集合时，使用既有EXCLUDED类别在外发及业务候选/输入包写入前拒绝，无论atom_id、object_id、source_id、source文件hash、文件名、路径或用途如何变化。无需两个来源hash相同。拒绝别名不依赖调用方是否选用了同一个finding ref。无任何图片相似度、OCR、重新编码等价或文本短句匹配。

范围层与内容层均须通过。禁止对象自身保留范围拒绝；不同真实图片33/36与禁止图片39应分开。更换对象但引用同media、另一个PPTX含同media bytes、独立图片文件同bytes全部仍拒绝。不同压缩/编码但像素相似不属于本轮“完全相同bytes”的识别承诺；原有范围排除不因此失效。

当前授权scope的闭合schema无需添加自报hash字段。明示的跨来源图片内容禁用通过可信finding与当前EvidenceBook排除集合承载；旧授权范围排除继续独立核验，持续授权不被此技术实现替换或伪造。

## 5. RED/GREEN 与回归矩阵

1. 公开工具finding成功：返回正式ref，实际提取hash正确；登记前后inventory/Mission/content/Gate heads逐项相等。目录文件快照证明无额外材料副本；幂等重复零写，不同语义及陈旧revision拒绝。
2. 公共schema与直接bridge/service反例：混合两分支字段、未知字段、错误ref kind/不存在ref/跨项目/旧inventory/错sourcehash/错误selector/不存在对象/不支持提取/自报hash均在写入前拒绝。
3. 内容入口正反例：Evidence→Context→Fit→Blueprint→双硬门→合成受信审核/G0→输入包；finding由公开入口产生。库存ID、缺失/旧finding、篡改真实源bytes不能通过任一生产入口。proposal-led和既有text/url/bytes导入回归。
4. 独立同页对象和表范围的对称正反例；整页declared与对象excluded共存成功，合法对象atom通过，页级atom不能绕过局部排除。
5. P1：合成33/36为不同图片正常通过，39为禁止图片；同media别对象、同bytes别PPTX/source_id、独立图片别路径拒绝；改变atom/ref/id/调用方hash不能解除。scope模式的不同对象同bytes不会被擅自升级为内容层排除。禁止finding的源bytes被替换或所需提取失败时不能跳过排除继续发送。
6. pack登记/生成前预检集成：禁止图片命中时state/event/artifact和adapter调用计数不变；既有unknown恢复不重发语义保持。引用修正的真实失效机制、旧G0不能跨新Blueprint复用保持，本切片不实现G0迁移。
7. 全量适用Python、Node、Widget、typecheck/build，隔离私有依赖不写共享node_modules。固定候选独立规格/代码Review，证据进入唯一ledger；不把合成Gate/transport当真实客户或provider验收。

## 6. 基线与 Skill 同步

四基线§1.4细化固定finding归属、库存ID与证据引用区别、范围/图片内容两层排除及持续授权边界；运行Skill说明正式生产顺序、同图换对象不可绕过、能力缺口与零写入。共同规范不能反向布局、Image2定版权威和逐字忠实转换不变。B配置与不生图预检单独规格/提交，避免将离线配置就绪描述成真实provider已连通。
