# C2 Image-led 输入 v2 正式修正规格

状态：已批准的有界技术决定，2026-09-10。属于同一 CHG-IL-C2、`codex/image-led-native-anchors` 独立 Worktree。总控已核定 TITLE / SEMANTIC / OPTIONAL / AUTH，实施无需再次征求一般许可。本文是这四项修正的唯一正式规格；临时设计与复现只作证据，不形成平行合同。实现、独立审查、本地提交、候选加载、真实生图与用户定版分别记录。

基准提交 `30ca3bcc2466519cde804333b679e8c55fc055b4` 已包含审核过期修复。本次不修改客户 r40、Blueprint、G0、材料原件；不生图、不安装或重启候选、不弹真实确认表单。当前已加载 `0949867` 不支持本规格，不能降级新包来继续。

## 1. 目标与事实边界

Image 2 接收完整已确认文案、当前来源派生语义、授权材料池、页目标与共同规范，自主设计正文。标题只出现于明确身份的可见项，不由 metadata 再增加一项。定版后原生转换继续忠实遵循完整图片和唯一 TargetBinding。

2026-09-11 精确型号增量已核定：Image 2 是整页设计责任角色，接收方/型号以核定配置和适用 scope 身份决定。本次只在旧 `CRS / gpt-image-2` 之外增加 `CRS / gpt-image-2.5-sunburst`，参数保持 `2048x1152 / high / PNG / n=1`；不接受 Flare、泛别名或自动降级，不新增任何 v3。具体 argv 与供应方响应接纳按[供应方准备规格](./2026-09-10-c2-image2-provider-preparation-design.md)执行，本次源码验证、独立审查及后续运行状态以 C2 唯一验证台账为准；不表示已安装、已生图或已发布。

四基线 v2.14 §1.6 的本轮选择为 `CRS / gpt-image-2`；Sunburst 的外部阻断只影响自身路由，不作为 Image 2 的前置。本次按[Image2Codex 兼容实施计划](../plans/2026-09-11-c2-image2-codex-output-compatibility.md)增加供应方观察与原图适用性，不更改本规格既有 v2 输入/schema、客户字段、输入 hash、policy/pack/grant 或 G0；请求身份与供应方回报分开保存，不把已批准的窄兼容扩大为通用注册器。

当前三页共有 16 / 36 / 19 个 blocks，共 71 项，原 ID、文字和顺序全部保持。标题 block 映射由当前权威 Blueprint / 来源核定，第二页标题在第二项；这不是“用户逐一确认了技术 block ID”。当前生产 v1 曾强制 title + 全 blocks，正确身份表示被拒绝；这是输入表示缺陷的生产入口复现，不是已经生成重复标题图片的证据。

持续授权意图已经存在；范围记录尚未绑定不等于用户撤销授权。当前发行 stdio 未装配可信历史消息 verifier；新增仅复用模式不能凭空提供该能力。

## 2. 唯一版本矩阵

| 层 | v1 兼容 | v2 |
| --- | --- | --- |
| pack | 无 pack_version，旧闭合 shape | `pack_version=image-led-input-pack/v2` |
| payload | 原闭合 6 字段 | `payload_version=image-led-image2-input/v2`，闭合 9 字段 |
| transport | `image-led-image2-transport/v1` | `image-led-image2-transport/v2` |
| selected copy | `{items}`，旧首项标题语义 | `copy_version=image-led-selected-copy/v2`、`title_item_id`、`items` |
| compiler | `image-led-faithful-compiler/v1` | `image-led-faithful-compiler/v2` |
| handoff | `codex-presentations-image-led/v1` | `codex-presentations-image-led/v2`，slide 保存完整 selected_copy |
| preflight | 原 v1 闭合请求/6字段响应 | v2 增加 `generation_protocol`，严格证明所需 transport |

artifact_type、candidate / selection 根结构不变，版本由绑定的 pack 和完整 copy 决定。未知版本、缺版本但混入新字段、协议不匹配必须拒绝，不能删字段降级。wrapper 返回保留 protocol/receiver/model/request_id/response_id/image_base64；已知 CRS command v2 增加必需的 `provider_observation` 并随归一返回传递，历史 v1 六字段回包仍可读。provider_observation 使用独立 `image-led-provider-observation/v1`，原图适用性使用 `image-led-output-fitness/v1`，两者不是新输入版本，也不新增 transport/preflight v3。protocol 逐请求精确匹配；旧二字段依赖注入结果不伪造观察，只有实际提供且校验通过才记录。CRS 认证 helper 只提供认证，不解释本协议，无需修改。

## 3. 标题身份、可见文案与共享投影

v2 pack 沿用既有根字段，并新增 pack_version 与 required_atom_ids。`confirmed_visible_copy` 严格为：

```json
{"title":"设备情况","title_target":{"kind":"block","block_id":"b2"},"blocks":[{"block_id":"b1","text":"运行概况","identity":"来源事实"},{"block_id":"b2","text":"设备情况","identity":"来源事实"}]}
```

`title_target` 只在 confirmed_visible_copy 内，不在 pack 顶层。其闭合 union 为 `{kind:"block",block_id}` 或 `{kind:"standalone",item_id:"title"}`。block 模式明确解析同页唯一 ID 后逐字核对目标 text 与 title；不按字符串选目标、不默认第一项、不删同文异 ID 项。standalone 模式保留独立 title 再复制全 blocks，固定 title ID 冲突时拒绝。

一个共享纯派生函数供请求编译、candidate 登记和当前性校验使用。block 模式每个原 block 恰一项，原序复制 `{item_id,kind:"text",role,text}`，唯一目标 role=title，其余 body。standalone 模式只增加确实独立的标题项。完整 copy 是：

```json
{"copy_version":"image-led-selected-copy/v2","title_item_id":"b2","items":[{"item_id":"b1","kind":"text","role":"body","text":"运行概况"},{"item_id":"b2","kind":"text","role":"title","text":"设备情况"}]}
```

canonical hash 覆盖整个对象，包括版本、标题身份及 ordered items。所有下游必须保持该对象；不能从 regions 重造 `{items}` 丢失元数据。内容投影按 title_item_id 查找标题，只排除该 item 自身；同文异 ID 正文保留。来源顺序是核验顺序，不规定页面坐标。

内部用真实 item/atom ID，外发统一按顺序映射为 `text-0001` / `material-0001`。可见文案、title_item_id、语义注释、必用列表及材料序号共用一个映射函数。真实项目身份、source refs、文件路径、hash、block IDs 留在内部 binding，不进入 provider prompt。

## 4. 非可见材料语义

payload 根闭合为 payload_version/receiver/model/confirmed_visible_copy/page_goal/common_rules/materials/required_atom_ids/non_visible_semantics。pack 不接受自由 semantic_context、任意 pointer 或旧整页输入。

provider prompt 在这些客户字段之外增加固定 `system_output_requirements={version:"image-led-system-output/v1",canvas:{aspect_ratio:"16:9"}}`。该系统输出要求不写回 payload/pack，不拼入 `common_rules.background`、copy/page_goal/materials 或非可见语义，不改变原客户字符串枚举、输入 hash、grant 或 G0；不携带客户事实，也不指定正文布局。2048×1152/high/PNG 继续是请求目标，实际图片另行完整解码记录。

non_visible_semantics 闭合字段：

- `context_version=image-led-semantic-context/v1`；`purpose=constraints-only-not-visible-copy`。
- relationship_summary：当前页 page_task 原文。
- rules：固定四项 preserve-source-memberships-and-stated-flow、do-not-invent-unstated-interfaces-or-endpoints、do-not-infer-implemented-results、do-not-treat-source-layout-as-template。
- copy_facts：按实际 item 身份关联的 `{item_id,identity,limit_ids}`。
- limitations：原文去重的 `{limit_id,text}`，不裁剪、不改写客户文本。
- material_use：`{material_id,image_number,use,presence,purpose,identity,limitations}`，与实际允许池同序一一对应。

编译器从 policy 已绑定的当前 Blueprint / EvidenceBook / material_views 派生。按 evidence_bindings.content_ref 与正式 EB 对应身份桶的 item_id 精确匹配，并核对 source refs 和身份；有歧义、缺失或不一致时拒绝。当前页 forbidden extrapolation 只由当前页精确 source refs 关联；该集合与既有材料 resolver 一致，包含 evidence_bindings.source_refs、material_views.source_ref 和 customer_decision_item.evidence_refs，不能按页面名/文件前缀猜测。图片用途和 treatment 取当前唯一匹配 view，必要时只允许可精确解析的 EB 来源；不自编新用途。未知事实身份拒绝，不能借 identity 自由文本绕过授权。

生产派生必须精确覆盖每一个原 block 的事实身份；独立 metadata 标题没有来源事实时不伪造一条事实。编译侧语义校验使用当前 pack 的完整 block ID 集合验证 copy_facts。wrapper 没有权威 Blueprint，结构校验要求所有 body items 有唯一事实项，标题事实项可存在或缺省；标题来源是否完整由生产派生和执行前 payload/binding 重编译证明，wrapper 不能单独证明。不得为猜测标题来源而禁用已有 block_id="title" 或增加未经定义的 copy 字段。

关系只通过当前 page_task、原序完整 blocks 与固定保持规则表达，不转发旧 graph、层级布局或旧审计独有推断。不新增正文列数、几何、位置、卡片或图形约束。非可见限制不是上版文字。

内部 semantic_binding 保留每条派生语义的当前 ref、允许字段位置、条目身份和 UTF-8 hash；请求 digest 覆盖完整 v2 payload。generation_context 执行前重新派生并比较 payload/binding，源语义变化必须令旧任务失效。

## 5. 授权枚举与可选材料

一个枚举器覆盖所有外发客户字符串：可见 text、page_goal / relationship_summary、limitations.text、material purpose / treatment，以及 common_rules 中所有实际外发的自由字符串（token map 的自由 keys/values、字体列表、title_bar、background）。这些字段不能可靠地区分普通设计指令与嵌入的客户句子，因此 v2 一律纳入同一范围枚举，不用关键词黑名单、模板猜测或模型判断跳过；v1 保持历史语义。逐字 UTF-8 hash 通过现有 scope 的 content-source 范围核验。固定版本、alias 和闭合身份枚举是引擎语义；不得将新增客户句子藏入 common_rules 或枚举以跳过范围核验。原 76 行准备 scope 尚未包含新增语义字符串，不可直接执行。

pack.atoms 在 v2 表示已经授权可以外发的池 A。全部 A 都先核验来源、当前用途、字节、提取/解码和排除，无论图片最终是否使用。source 范围排除与同字节禁图两条规则保持；更换 source/path/object ID 不解除禁用。

`required_atom_ids` 是明确必用集合 R；当前尚无可解析规范来源承接非空必用决定，因此当前生产分支非空一律在写前拒绝 `MATERIAL_REQUIREMENT_NOT_ESTABLISHED`。当前 r40 使用空列表。域级 synthetic 子集测试仅证明算法，不能宣称已支持泛化必用登记。

candidate.material_roles 为实际使用集合 U，满足 `R ⊆ U ⊆ A`；角色的 atom_id/source_ref/content_sha256/use 精确一致、唯一，按池序规范化。实际图转录及独立 candidate-source 审核核对 U、禁用内容和来源；不能复制 A 充当使用证明。register_candidate 与 current_candidate 都重新核验。

selection / TargetBinding 只冻结 U。现有全部已选 real-material 必须有完整 region / hash 覆盖的规则不变。native 只能加载定版区域引用的素材，不得补入 A\U、换图或删除 U。旧 v1 保持 all-atoms 语义，不静默改写历史。

## 6. 既有授权的仅复用承接

公共 `submit_ai_ppt_human_decision` 新增可选 `confirmationMode: "verified-message-only" | "allow-native"`。缺省保持旧兼容 allow-native；该值本身不授予表单交互许可。

- Image-led verified-message-only 缺可信 verifier 或非空真实消息引用：表单前返回只读 CAPABILITY_GAP，分别标注 verified-message-adapter-unavailable / verified-message-reference-unavailable；零表单、零签名、零业务写入。
- verifier 必须严格返回 true；false、异常、过期上下文、取消不得回退表单。错误不泄露 provider/用户内容。
- true 沿原 exact context / HMAC / challenge / 原子消费路径；不自签 rollout，不使用测试 verifier 上线，不复用 Mission/G0 的消费身份。
- 已签发且未撤销的适用 scope/grant 继续通过 authorized_scope 只读复用，不消费新消息或弹窗。
- 非 Image-led generic 分支保持原兼容行为。

精确型号变化不能修改旧 grant 标签或把旧 scope 解释成模型家族授权。由正式入口按真实型号选择及有效批准承接匹配的新 scope/grant，再派生绑定的 policy/packs；沿引用链核对 model，不要求 grant/pack 新增重复型号字段。原 G0、71 项原 ID/原文/原序、来源与排除关系、共同规范保持；现有用户决定不因技术适配撤销，不增加逐页/逐次批准。

新承接不能只写 Skill 提醒。`commit_ai_ppt_artifact` 成功登记 Image-led scope 后，从**实际返回** artifact_ref、snapshot revision 和项目根生成结构化 `authorization_continuation`；其中 tool call 显式固定 confirmationMode=verified-message-only、choice=approved，调用方只能补充真实适用 userMessageRef，不能沿默认分支调用。回执缺少可核验身份时不生成可执行 call，不猜 revision/ref。该 handoff 本身不自动执行、不确认 scope、不签名；真实 handler 回归消费此 call，证明在当前缺 verifier 条件下零表单。后续是否提供真实 host adapter 或精确 scope 原生记录由总控衔接，本次不触发。

## 7. 入队、重放与原生全链

v2 在创建生图任务/请求前完成 required transport 的 preflight/v2；旧 wrapper 的通用 ready 不足以证明 v2。能力不匹配零入队、零 provider 请求。已有 unknown 请求只恢复原 request，不因迁移产生重发。

两个精确型号都保持上述 transport/preflight v1/v2 矩阵。旧型号只用当前 sys.executable 与当前包固定 image2_crs.py 两项 argv；新 Sunburst 才在同一前缀后加 `--model gpt-image-2.5-sunburst`，预检再追加 `--preflight`。配置、CLI、payload、probe model 及 scope/policy 引用身份不匹配时写前拒绝；不能把四项新命令绑定旧 model，或用两项旧命令配新标签。真实 HTTP 中的每处显式型号按当前路由许可集合核验：Image 2 只允许精确 Image 2 或实测观察到并明确兼容的 Image2Codex，Sunburst 仍精确；transport 原 model 始终保持请求路由。非法回报、无效观察或回执请求身份不符只能发送后拒绝接纳，保留 unknown 且不可重试，不计为零 HTTP；上游缺少 model 时不制造独立上游执行证明。

provider_observation 闭合保留 `reported.response` 与 `reported.image` 中实际存在的 model/quality/size/output_format，另存 `version`、计算的 `model_match=exact|compatible-image2-codex|not-reported`、固定 `independent_engine_proof=false`、响应字节 `response_sha256` 和本地 `observed_at_utc`。不将请求目标填入缺失回报。Runtime 完整解码原图并保留实际 image_size/MIME/hash；当前 v2 CRS 两条路由按 `image-led-output-fitness/v1` 检查 `abs(16*h-9*w)<=8` 且 `w>=1280 && h>=720`，只允许整数高度四舍五入半像素误差。该底线不证明文字清晰或设计验收。合法原图即使不合适也 completed 保全、当前可用性 needs-revision；候选/选稿前重算并拒绝不适用原图，缺失/改写观察不能绕过几何门。不得缩裁、重采样或回填目标尺寸；下游按实际源图比例与几何转换，原 selected-copy 与 TargetBinding 规则不变。

candidate / selection 保存完整 v2 copy；compiler / handoff slide 携带 exact selected_copy；region items 双向完整匹配；JS renderer 和 Python result verifier 同时核验完整 copy hash 与区域映射，禁止丢版本或改标题。标题、文本、素材、设计还原、编辑性与跨页一致性分别检查，不用类型检查或 synthetic PPTX 宣称真实 PowerPoint/用户验收。

新候选包应同步包含 adapter、wrapper、preflight、renderer、Python validators 和新纯模块，manifest 固定确切源码 hash。仅源码修复不表示当前已加载实例支持 v2。本次完成受审源码与本地提交，真实候选安装另行衔接。

## 8. 验收与证据

必须保留真实生产入口 RED→GREEN：第二项标题、同文异 ID、standalone、完整 selected-copy hash/region/native；缺/错目标、跨版本和额外可见标题拒绝；身份与 limitations/purpose/treatment 全量外发授权、旧图结构/内部标识不外发；池为空/部分使用可过，未选/替换/漏映射素材拒绝；非空 required 无真实依据拒绝；旧 wrapper 的 v2 preflight 在入队前失败；AUTH 缺 verifier/ref、false、异常、stale、取消零回退及严格 true 原消费兼容。

旧 v1 回归、全套 Node/Python/Widget、typecheck/build、四基线相对链接及原型存在性、独立规格与代码质量审查都写入 [唯一验证台账](../../validation/c2-image-led/verification-report.md)。客户 Runtime 111 文件前后 hash 核对保持不变。保存过期修复提交独立保留；本次不得重复提交它、不合并、不 push、不改 Git 对象库。

本轮源码修复以离线测试核验系统输出要求与原授权输入分离、观察闭合和模型窄兼容、实际原图保存、适用性失败的 completed/needs-revision 分离、候选/选稿阻断及恢复零重发；不执行真实 HTTP/helper/安装或客户读写。总控后续按已选 `CRS / gpt-image-2` 在受审实际 wrapper 上使用纯本地合法 v2 envelope 作非客户验证，无需虚构正式 Runtime/G0/grant。当前用途需覆盖零图 generations 与双图 edits；单图先离线覆盖，真实单图可选追加、不作为当前用途前置门。两图属于允许池也须以原字节/顺序进入 image[] 请求，不能删图规避 edits。Sunburst 历史证据与自身阻断保持；组件级 HTTP、完整解码、原图技术适用性、正式 Runtime、真实三页与用户设计验收分别记录。
