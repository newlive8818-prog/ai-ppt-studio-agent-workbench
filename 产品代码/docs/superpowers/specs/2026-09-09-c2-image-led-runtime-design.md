# C2 Image-led Runtime 技术设计

状态：目标已批准；本文件为 IL02-T01 技术接口设计，独立规格 Review 后在同一 Change 内实施。四基线 v2.12 §1.1–1.4 与主计划 §5/§12.2 为上位依据。仅启用隔离项目，旧项目保留原读取边界。

## 责任和方案选择

采用现有 Python Runtime 的派生制品与可信确认扩展。材料、内容、G0、事务、审核仍由原对象负责；新增专用 Image-led 输入、候选、选择、映射。公开 MCP 工具数量维持 43，新增内容通过既有 artifact/action 与 human decision 通道传递。另建素材库会复制事实源；把定版身份塞入 token-map 会污染 UI 与 R3 合同，均不采用。

三个时段严格分离：设计输入只提供逐字文案、目标、材料用途与共同规范；候选转录/来源核对先于真实用户定版；定版后的合同与对象计划只描述确切图片。编译器不推导布局。视觉保真无法用 hash 或字数证明，工程校验和图像区域独立 Review 分开。

## 材料派生与持续授权

`visual/image-led/input-policy` (`image-led-input-policy`) 为 G0 后轻量请求前的项目配置，绑定 project_id、当前 reading_blueprint_ref / source_version、material_inventory_ref（无材料可空）、evidence_book_ref、g0_ref、release_target_policy_ref。共同规范只有 `typography_tokens / color_tokens / fallback_fonts / title_bar / background`；前三者复用 R3 string map 规则，后两者为非空文字描述。不得携带正文位置、列数或对象几何。

政策列出本次允许源区域及用途：source_id、source_sha256、source_location、allowed_uses、constraints；政策另固定 receiver/model 与 redaction 范围；排除以源 sha + 区域或整源身份表达，不能用 atom_id 作边界。`source_location` 为判别联合：whole-source；text-range（start/end，Unicode 字符范围，end不含）；image-region（pixel bbox，原始像素坐标）；page（正整数page）；object（page/object_id）；table-range（page/object_id/row_start/row_end/col_start/col_end）。各型字段闭合、范围非空。第一版直接支持可解码 text/image 的可重建提取；PPT page/object/table 在当前实现经只读 OOXML 提取器支持标准 Transitional PPTX 的页序、原生文本、唯一对象文本/单图和未合并表格范围；Strict OOXML、SmartArt/chart、合并表格、SVG/WMF/EMF、动画/多帧和多重备用图像仍报 CapabilityGap。所有选择器必须有确切源字节绑定和可重放提取证据，不能凭自由文本位置放行。同源排除整源向页/对象/子区传播；可比较区域相交即拒绝，表示无法比较亦拒绝，不按文件名/原子 ID 放行。EvidenceBook 的排除 source_refs 同时适用。

当前 input-policy 与不可变 authorization-scope 分离：前者绑定 G0/当前蓝图/共同规范，后者只描述源内容 hash、来源选择器、用途、provider/model/receiver、发送形态和脱敏边界。通过 ScopedConfirmationPolicy 对 scope ref 绑定可信宿主决定，记录 `image-led-input-authorization` 与 kernel consumption ledger。支持沿用同一政策的持久授权：每页/每次请求只读取并核对 ledger 与精确 scope，并证明输入政策的每个发送项都在已授权 scope 内，不重新消耗/询问。字体、普通 revision、当前 G0/蓝图或发布目标变化须重验制作依赖，不自动撤销授权。仅实际材料/用途/接收方/脱敏范围扩展或撤销才需要新的授权依据。生产代码不接受自填 `approved=true` 或任意授权字符串。没有可信宿主适配时报告 CapabilityGap，不能用测试签名器代替。

`MaterialAtom` 是现有 EvidenceBook row 或 material_views 的引用派生；不额外保存客户事实。包含 atom_id、origin_kind、origin_id、source_ref、source_id、source_sha256、source_location、atom_type、use、content_sha256。解析当前 inventory / evidence / blueprint，在请求前重新读取真实源字节、实际提取内容/图片字节。source artifact 的 envelope hash 与文件 hash 独立校验。路径只解析登记来源和明确 project 内副本，禁止目录扫描、符号链接逃逸、任意 URL 自动拉取。URL/目录没有可核对快照时报能力缺口。正文 text 保留换行/空白；空白检查不执行内容归一化。

`VisualInputPack` 每页派生并绑定输入政策/授权/G0/当前内容/材料/evidence refs、slide_id/order、confirmed_visible_copy（逐字 title 与 blocks）、page_goal、共同规范、atoms。无图/无材料页面合法。用户可指定必要材料，系统从当前材料视图和证据行生成候选；不得把旧 PPT 默认当风格模板。角色用途变更必须落在政策范围内。

## 请求、候选与定版

本轮 G-01/G-02 修复设计：既有公开 action 增加 `generationIntent=new|recover`、`generationRequestId`。缺省两字段时以 project、exact pack、instructions 派生稳定请求身份；刷新 expectedRevision 或 command_id 不建立新外发意图。明确再次设计使用 `new` 与新的 ID；同 ID、同输入只读回放，同 ID 换输入拒绝，仍复用有效材料 scope，不增加逐次许可或次数限制。`recover` 按原 ID 只读查询，可以传空目标/说明，不依赖当前 revision、active task、有效 scope 或 adapter 配置；未曾外发的 queued 任务仅返回 pending 回执，不能借恢复自动补发。

返回保全独立于候选晋级：只在原 `project/image-led/request/<request_id>` 槽按 request/claim/pack/payload 身份提交 started→completed/unknown。使用当前 revision 的 CAS，冲突只重试本地保全事务，逐次重验 claim；不得重试 provider。相同确切响应幂等，冲突 claim/响应拒绝覆盖，提交语义绑定完整响应摘要。保全不恢复旧业务 heads/active task。公开回执分别表达历史响应与 `generation_usability`，后者仅为读取时的当前资格提示，提交 candidate 仍独立核验当前 G0/任务/来源/授权。测试和 Review 结果只维护于唯一执行记录。

请求 ID 使用 1–128 位 ASCII 字母、数字、下划线或横线，保留字 `active` 在公开 schema、请求解析、任务创建和生图 context 编译入口一致拒绝，避免覆盖内部活动任务槽。不得以事后恢复兜底代替写前拒绝；普通短 ID 与既有 64 位 ID 均保持可用。

`generate-slide-images` 复用 image-asset-producer 和原 Agent task 事务，前置为 G0 与当前合法 VisualInputPack。ContextCompiler 在该 action 使用专用闭合 context，不携带旧原生几何或无关内部材料。外发 payload 仅包含文案、目标、共同规范、允许的文本/图片及用途标签，不包含本地路径、凭据、排除材料正文或授权账本。

生产 `request_ai_ppt_agent_action(generate-slide-images)` 经真实 Python bridge 预检当前输入包和宿主适配器后建任务，再调用 `execute_generation`。宿主用 `AI_PPT_IMAGE2_ADAPTER_COMMAND` 配置绝对 executable 的 JSON argv，`AI_PPT_IMAGE2_RECEIVER / AI_PPT_IMAGE2_MODEL` 必须匹配当前授权；公开请求不能传 argv、endpoint 或凭据。command adapter 以无 shell 子进程通过 stdin/stdout 的 `image-led-image2-transport/v1` 交换单次请求和确切图片 bytes；可选环境 allowlist 不传宿主确认密钥。缺配置或不匹配在建队前零业务写入。内部 `execute-image-led-generation` bridge/CLI 负责既有任务恢复，未增加公开工具。

请求执行前再次解析 current 输入包，先预检后调用 transport。请求身份沿用 Agent task_id。started/unknown 查询原请求，不盲目重发。PNG/JPEG/WebP 单帧原始 bytes 验证后持久化并由现有 MCP ImageContent 返回，不能自动转录、选稿或升 Gate。候选登记走 Agent result 同一事务，记录 request/pack/image 实际 hash、页身份、转录可见文案、使用材料角色及来源核对差异。图像保存在项目内不可变制品，登记时读取字节；不能由文件名选择。

`image-led-selection-proposal` 绑定三页确切 candidate refs、每页 TargetBinding、逐字 selected_copy、accepted_deviations 。详细区域转录在可信选稿后进行，不作为用户选稿前置。候选来源核对必须完成；新事实不在 G0 中时不能直接入选，差异要明确显示并由对应用户决定处理。在既有 `submit_ai_ppt_human_decision` 工具中新增 Image-led 专用可信分支消费真实宿主凭据生成 `image-led-selection`。选稿不是 G3。任意模型提交的 selection 对象无 ledger 绑定拒绝。

当前 generic submitHumanDecision 没有可信确认能力，不能沿用它的记录作为授权。新专用分支先从 Runtime 只读取得 target_ref 对应 scoped context；Node 以已验证消息/native action 通过真实 confirmationVerifier 后签名；Python 通过 ScopedConfirmationPolicy 验证并在同一 kernel.commit 写确认及 consumption。用户传入的 assertion 字符串不能经过公开 JSON 直接注入。缺真实 verifier 时返回 CapabilityGap，不降回 generic 分支。非 Image-led 的普通 human decision 保持原语义。

TargetBinding 闭合字段：project_id、slide_id、page_order、candidate_ref、target_image_ref、target_image_sha256、selected_copy_sha256、material_roles、common_rules_ref、accepted_deviations、design_authority=finalized-image、conversion_mode=faithful-native。所有下游携带 selection ref 和这组身份，不能凭文件路径补全。

## 区域、编译和构建

定版区域清单是对应图片的只读转录制品，绑定 target image/copy hash。region 包含 region_id、kind（text/shape/image/connector/table/decoration）、bbox、z_order、content（逐字文字/单元格/关系）、material_binding、appearance。appearance 描述原图色彩、字体、线条、渐变、阴影、路径等，禁止编译器自行补视觉。区域清单必须有独立检查记录，逐区证明可见内容/覆盖；不声称仅凭结构能自动识别图像中的全部区域。

对象映射默认每个 region 一对一，可表达同 region 的多个原生子对象，但必须明确分片 bbox/内容及覆盖；本次先支持一对一完整对象，复杂区域可在转录时拆成更细 region，并保持目标图片身份。所有 region 必须被对象引用且每个对象必须有 region；原生对象的内容、bbox、z_order、appearance、材料和关系必须等于清单，禁止改字/删段/改数字/箭头/换图/位移/简化装饰。不能将 text/table/connector 映射为位图；复杂无字 decoration 可以独立图片层。

复用 visual/contracts 与 visual/compilation-plan 原子发布。已有合同保留用户可读语义及 R3 UI 字段；Image-led 专用身份附在专用字段中，编译计划使用独立版本 `image-led-faithful-compiler/v1` / handoff `codex-presentations-image-led/v1`。legacy 原版本继续按旧 validator 读取，不能静默添加新能力。当前 Image-led 项目禁止通过 legacy 发布绕开 selection。正文内容取 selected copy，G0 只提供事实追溯，不回填旧 frozen_copy。

ContextCompiler 为 build-native-first 解析当前计划及全部定版依赖，生成只执行的 handoff。输出目录必须在当前项目、包含 task_id、尚未存在；预检完成前不创建目录/加载写入 SDK。泛化 Presentations renderer 只执行 region/object 数据，禁止页面 ID 特判或新写专页脚本。支持对象无法表达时报 CapabilityGap，不降成全页贴图。仅通过 Codex Presentations 的 SDK 生成/导入/渲染/检查 PPTX。

## 结果、失效与审核

结果核对执行计划、当前 selection/TargetBinding、实际 PPTX sha、渲染 sha 和对象检查输出；文字/表格/关系/材料/几何逐项检查。视觉证据必须有同画幅并排、叠图与区域差异，并由独立 Review 分别报告 content / visual / editability / common-rules 四维度，不能用平均相似度自动放行。目标 PowerPoint 仍走既有 TargetRenderEvidence；新 hash 不继承 C1 验收。

结果不通过则保留失败文件及差异，不能进入 visual/anchors 或当前交付候选；不覆盖原图、已接受 PPTX 或已有输出。前置拒绝不写 revision/event/artifact，不调用 transport/renderer。过程日志不冒充业务成功。

GateEvaluator 的 current plan 读取增加新版本校验与 selection/当前 G0/材料/政策依赖检查；G1/G2/G3 沿原质量/目标/用户确认流程。新输入政策/候选选择/视觉合同变化使下游锚点、检查、review 和任务过期；G0 重开清理所有 visual 下的 Image-led heads。已有不可变历史可读。

UI 仍为已验收的锚点/完整合同双视图，无新增工作台。Runtime 在投影前确保新路线 selected copy 存在，禁止旧字段 fallback；token-map、ReviewMark、text-anchor 保持既有规则。

## 验证与退出

行为 RED 通过现有公开入口或可执行兼容 stub 捕获实际不正确结果，不把 import error 当 RED。最低反例：无 G0、未登记/跨项目/旧材料、源文件/提取字节变化、同源换 ID、用途越权、空白丢失、无图、伪选稿、错页/相似图、旧文案、缺段/错数、未授权图片、缺区域、多余对象、移动标题、简化装饰、关系删改、全页位图、过期 handoff、已有输出、后置失败晋级。逐个断言前置零业务写入与 transport/renderer 零调用。

两组三页使用不同页 ID、内容、几何和对象数，验证同 renderer 与不同输出。自动化 fixture 标 synthetic，不借用真实 Gate。真实 C2 项目需要当前 G0、Image 2 返回、实际用户定版、原生结果、PowerPoint 和真实 G3；任何缺口单独记录，不把 C1 接受转授。工程候选完成后独立规格/工程 Review、全量 Python/Node/Widget/typecheck/build，再本地候选提交和总控核验；无自动合并/发布。

## 生命周期的具体保留与防绕过

Image-led 上游集合为 `visual/image-led/input-policy`、`visual/image-led/authorization`、`visual/image-led/pack/<slide-id>`、`visual/image-led/candidate/<slide-id>`、`visual/image-led/selection-proposal`、`visual/image-led/selection`。更新 policy 时清理全部下游但保留新的 policy；更新 pack/candidate 清理受影响选择及全部正式视觉下游；选稿时保留已绑定 policy/authorization/packs/candidates；发布 full brief/design/contracts 时只保留当前 selection 的精确上游集合，不调用默认 keep 集合误删。G0/材料变化仍清理所有 visual/*；若可信材料授权政策未扩张，可依据历史 ledger 复用授权语义，重新绑定新当前输入政策需要证明请求仍为旧范围子集，不能重新消费旧用户 identity。

防错检查同时进入 VisualService.register_visual_contract_set、register_anchor_set、ProjectCommandService 的 agent result preflight、ContextCompiler、GateEvaluator._current_visual_compilation_plan 与 G2/视觉审核发布；不能只保护 Agent result 而留下直接 public artifact 入口。Image-led 路线身份由持久项目配置 `project/visual-workflow` 的 `visual_workflow=image-led/v1` 明确标识，不能仅靠 current policy 存在推断。该配置不随 G0/材料的 visual/* 清理删除，普通 artifact/action 不能降级；前置清理后仍拒绝 legacy brief/contract/plan/action 生产发布。current anchors 必须绑定新路线验证结果、当前 selection/plan/PPTX，旧布尔 editability 或自填 hash 不能替代完整结果。只读 legacy resolver 不授予新路线生产通过。

## 材料规格 Review 修正（第一轮）

allowed_uses 为 `content-source | real-material | style-reference`，forbidden仅属排除。授权项同时声明 `send_form=verbatim | redacted`；redacted必须绑定实际输出hash与可重放变换来源，暂不能验证的变换报CapabilityGap。style-reference从不进入事实文案/evidence角色；请求的每一项文本/图片都从已验证来源快照编译。

预检返回完整内存 bytes/text 与 payload digest，transport只接受这些已验证值，禁止按路径二次读取。queued task创建前完成全部输入预检，失败相对于该命令入口零revision/event/artifact；task执行前再次核验当前refs与发送快照，失败保留此前合法queued历史、不新增业务写入或调用transport。调用已发生后的未知/失败不冒称前置零写入：保留request id和查询依据，可记执行失败，但不得晋级候选/锚点。candidate登记后每次读图重验内容hash；图像写入目录不允许覆盖原图。

## 视觉规格 Review 的执行细化

授权授予/撤销保存在不可变确认制品与 kernel ledger/event历史中，清理 visual heads 不删除历史决定。读取历史grant时除scope包含关系和ledger精确绑定，还扫描同scope后续可信revocation；被撤销grant不得恢复。head缺失不等于撤销，历史grant存在不等于当前有效。

选择记录只冻结候选图、可见文案与材料核对，不要求详细区域清单。后续 RegionInventory 绑定 selection_ref、每页 image hash / copy hash 及自身 artifact hash。selected_copy 为有序 items：item_id、kind=text/table-cell/relation、逐字 text（关系另带端点/方向），标题为显式 item。每个内容item恰对应一个region；region不能丢项、重复或自造内容，文字逐字且保持顺序/空白。region->object同样完整且不重复；清单和plan一起改错也必须因不等于selected copy而失败。独立region检查绑定 selection/image/copy/region_inventory hash，变更即失效。

accepted_deviations 使用闭合条目：candidate_ref、image_sha256、item_id、difference_kind、before、after、decision_ref。空列表合法。只记录选稿时具体图内现状差异；不能授权native新改动。模糊的“标题允许调整”、越页/越item使用、未知差异类型拒绝。native出现新差异只走新revision与对应决定，不自动放行。

构建结果与 G2 Review 分步登记。公开 Agent result 的 `image-led-build-result` payload 只接受 `artifact_type / project_id / output`；producer/task/context 由 Runtime 解析。`output` 是 renderer 的 `result.json`，携带 selection/regions/plan 身份、实际 PPTX 与 renders、files、comparisons；`handoff_sha256` 指向实际 `handoff.json` 文件字节。`files` 包含 handoff/mapping/inspect/authoring proto/reimport proto 和逐页 layout。结果不预先携带四维 Review ref，以免循环依赖。

随后独立 `review-visual-engineering` 任务提交 `image-led-result-review`，以 result ref 为 target，四项 criterion 为 `content / visual / editability / common-rules`，状态为 `passed / failed / not-established`。Runtime 绑定完成的 reviewer task/context 及输入输出身份，生产者不能自审。只有四项通过的 current result 能用 `image-led-anchor-set` 最小 payload（`artifact_type / build_result_ref / four_dimension_review_ref`）提升为现有 anchors；PPTX/editability/preflight 支持制品由已核验实物确定性派生，调用方不能自填布尔或 hash。然后既有 aesthetic/engineering G2 Review 与目标 PowerPoint 证据绑定该 anchors，G2 current 重新验证全部依赖和实际 bytes。

`layers.visual_handoff` 为治理包装，实际 renderer 输入是其中 `renderer_handoff`，版本为 `codex-presentations-image-led/v1`。编译计划版本为 `image-led-faithful-compiler/v1`，固定 region→`object-<region_id>`，不引入布局算法。SDK 导出以官方 proto/load 保留 object name 与 z_order；结果接入读取实际 OOXML 复验载体、文案和外观。渲染/对照图只证明其来源和差异文件真实，独立视觉判断仍不可省略。

候选来源 Review、selection proposal、region Review、正式合同、convergence、G1 Review 或结果更换时清除对应下游；旧通过状态不得继续有效。撤销当前使用 scope 时保留输入政策/包供排队请求准确报告撤销，清除 selection 及正式视觉成果并锁住后续 Gate；撤销无关历史 scope 不影响当前设计。更换发布目标政策时 Image-led 输入/选择/合同均须重验；旧路线保留原有行为。现有审核页面的标题与正文从 selected_copy 投影，忽略 legacy visible_copy/frozen_copy/anchor_title，保留确切文案空白和换行。

renderer坐标为96DPI CSS pixels，canvas={width,height}与source_image_size={width,height}绑定；region bbox/路径统一换算，不推算新布局。文本schema区分textbox bbox与字体run：text原样、fontFamily、fontSize、color、bold、italic、alignment、verticalAlignment、insets、lineSpacing；无隐式auto-fit/字体替代。shape含geometry、fill（solid/linear-gradient）、line、shadow、可选path；image含确切asset_ref/hash和crop（normalized）；connector含端点region_id/端点坐标、线条、箭头方向与业务meaning；table含逐cell item_id/text/style/行列尺寸。未知字段/类型、不可表达渐变/路径、超出画布、字体不可用、核心文字位图、溢出均在支持检查或postflight拒绝并记录CapabilityGap。第一版支持范围由这些schema的可执行白名单决定，不能以改布局补齐。两组三页必须覆盖所声明支持类型，真实样本覆盖不足时单独记未验证。

当前 SDK 实物验证收窄：原生 table/connector 需要实际输出与结果检查覆盖；非 null shadow 目前通过主题 effectRef 间接导出，尚无法用现有闭合证据核验，renderer 须在写入前报 CapabilityGap。schema 能描述定版阴影不等于当前转换器支持；禁止删除阴影或自行换效果后继续。真实 C2 客户页若依赖未支持载体，必须保留其确切定版身份和未完成状态。

## 实现期补充的可执行身份边界

当前G0文案标题/正文块/page_goal按实际UTF-8字节hash列入同一authorization-scope的whole-source/content-source允许项；它们仍逐次从当前blueprint派生，不另建MaterialInventory记录。三页可在一次范围确认中列全，普通revision/字体/颜色变化不改变材料许可；实际新增外发文案才需对应有效授权依据。共同规范是项目设计指令，不逐字加入材料许可hash白名单。

请求登记使用持久`project/image-led/request/<task_id>`，避免visual清理丢失未知请求身份。执行权以预检前捕获revision原子申请，随机claim_id只允许首次事务所有者外发；同command的kernel幂等回放不自动授予发送权。started/unknown必须查询原request_id，不盲发；completed只返回已有结果。撤销可面向已可信授权的历史scope，在G0重开/G2已过时仍可撤销，不能因生产门禁阻止停止使用材料。

候选图原始bytes封装于项目内不可变`image-led-image`制品（base64、mime、尺寸、sha），仍是原图不是重绘；源字节hash与artifact envelope hash分别验证。selection proposal列候选/来源Review/明确差异；一次可信选择事务同时写标准scoped confirmation和派生selection。TargetBinding的accepted_deviations.decision_ref指向该confirmation ref，避免自引用hash循环。读取selection时重算proposal+可信confirmation派生结果；自填selection或普通human-decision无法授权。
