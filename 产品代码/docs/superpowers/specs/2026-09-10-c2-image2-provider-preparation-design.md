# C2 供应方准备 B：单次请求 wrapper 与不生图预检

日期：2026-09-10；Change：CHG-IL-C2；状态：[独立规格 Review 已通过](../../validation/c2-image-led/source-recovery-implementation/provider-spec-review.json)；实现、测试、打包、代码 Review 和宿主加载分别验证。已有授权覆盖源码、合成离线测试和可审阅加载方案；不调用真实认证helper、不读取凭据内容、不发送实际供应方请求、不改宿主配置或安装/加载。当前客户 Runtime、已认可文案与 G0 保持。

2026-09-11 核定增量：本规格按[Sunburst 精确型号适配计划](../plans/2026-09-11-c2-sunburst-exact-model-adaptation.md)窄同步，本次源码验证、独立审查及后续运行状态以 C2 唯一验证台账为准；上述既有 Review 不证明本次增量已通过。Image 2 是整页设计责任角色，具体 provider/model 由核定配置和匹配授权身份决定。原 G0、三页 71 项原 ID/原文/原序、材料与共同规范保持；旧 grant 不能改型号标签。源码实施不含真实 HTTP；总控在受审实际 wrapper 上执行的非客户组件级合成验证按 §5 的证明范围单独记录，不把源码、包、宿主、真实客户或发布状态合并。

2026-09-11 当前执行合同：按四基线 v2.14 §1.6 及[Image2Codex 兼容实施计划](../plans/2026-09-11-c2-image2-codex-output-compatibility.md)，用户本轮选择 `CRS / gpt-image-2`，Sunburst 保留但其外部阻断只适用于自身路由，不成为 Image 2 前置，也不建设通用模型注册器。下面的观察与原图适用性规则取代此前“所有供应方回报均须等于请求型号”的表述；请求/配置/授权身份继续严格匹配，历史回执与验证状态不改写。

## 1. 已核对的复用边界

[只读供应方调查](../../validation/c2-image-led/source-recovery-implementation/provider-discovery.json) 核对本机 C1 请求代码与已安装 CLI：认证helper输出被当作纯文本密钥，不是JSON；C1以max_retries=0显式关闭SDK重试，用gpt-image-2/2048x1152/high/n=1；成功图片为data[].b64_json。这是本地源码证据，不证明当前CRS网络或认证有效。

旧实验脚本带有冻结输入、预算、提示词和第二套结果账本，不直接复用。wrapper采用Python标准库urllib，不依赖系统OpenAI SDK或httpx，不引入安装要求。固定接收方标识 `CRS`，仅接受 `gpt-image-2` 与 `gpt-image-2.5-sunburst` 两个精确型号；旧默认不变，新型号必须显式配置。沿已核对入口 `https://sub.523869.xyz/v1/images/generations` 与 `/images/edits`；不接受 Flare、泛称 image2.5、前缀匹配或任意模型，不自动降级。调用方不能从prompt/payload指定新地址、认证helper或任意命令；TLS、helper、loader 和安装缓存不在本次适配范围。

## 2. 文件职责与调用合同

新增 `src/ai_ppt_studio/adapters/image2_crs.py`，可直接通过当前Python解释器加绝对脚本路径运行；使用标准库且不依赖启动cwd/PYTHONPATH。位于src内以进入既有两条打包路径，不另添漏入包的scripts工具。

保留 `image-led-image2-transport/v1` 与 `image-led-image2-transport/v2`，输入均为三字段 protocol/request_id/payload；v1 payload 是既有编译结果 receiver/model/confirmed_visible_copy/page_goal/common_rules/materials，v2 payload 按[输入 v2 规格](./2026-09-10-c2-image-led-input-v2-design.md)闭合 9 字段。两种精确型号都沿用对应输入版本，不新增 transport/preflight v3、不删字段降级。严格验证字段、类型及目的地；禁止路径型素材、任意额外payload字段或用户指令改变接收方。输入只从stdin接收；返回保留 protocol/receiver/model/request_id/response_id/image_base64，已知 CRS command v2 增加必需的闭合 provider_observation，归一结果也保留该观察，protocol 逐请求精确匹配。历史 v1 六字段回包可读；Runtime 依赖注入仍兼容旧二字段结果，但缺观察不能伪造供应方回报。错误时非零退出，stdout不写部分成功回执，不输出原始网络响应、异常、header、helper输出或客户文案到stderr。

生成 prompt 保留已编译的逐字文案、目标、共同规范和材料文字/用途说明，并在客户字段之外增加固定 `system_output_requirements={version:"image-led-system-output/v1",canvas:{aspect_ratio:"16:9"}}`。这是系统画布输出要求，不是客户正文或新的输入事实源；不写入原 v2 payload/schema、common_rules.background、copy/page_goal/materials，不改变原输入 hash、grant、G0 或客户枚举范围。它不预定正文列数、位置、布局或装饰；不引用C1旧图/旧提示词，不剪裁、改写文案或替换图片。图片输入保留编译材料顺序和原字节，按素材序号标明use，style-reference与real-material区别保留；不把本地路径、atom_id、hash或内部账本自动发出。

无图片时一次POST JSON至generations；有图片时一次POST multipart至edits，单图字段image，多图image[]。两条路径的 model 均取自同一次严格 argv 解析并核验 payload 一致的精确型号，参数保持 n=1、size=2048x1152、quality=high、output_format=png。两图可选素材池仍以原字节和原序发送；可选表示模型可决定是否采用，不能删图以绕过 edits。供应方当前支持仍待真实验证。输入图片MIME闭合验证与现有支持格式保持，并核对声明与文件头一致，不从路径读取素材。response需要data恰好1项且b64_json可严格base64解码为非空、具有PNG文件头的bytes；不接受URL/下载、第二幅图、空结果或格式错误。wrapper的文件头检查不等于完整图片解码；输入图片完整解码由既有材料编译器完成，输出在Runtime候选接纳前继续由现有Pillow校验，不把非空base64称为完整图像验证。

wrapper 回执原 model 字段始终表示本地核验且实际写入请求的路由型号，不改成供应方回报，也不能单独证明上游执行型号。仅 `CRS / gpt-image-2` 的回报许可集合为精确 `gpt-image-2` 与实测观察到并明确兼容的 `gpt-image-2-codex`；Sunburst 只接纳精确 `gpt-image-2.5-sunburst`。根 response.model 与唯一 data[0].model 中每处存在的值都必须有效，不能用一处合法值掩盖另一处未知、跨族或无效值；缺少 model 时不制造上游型号证明。command adapter 继续严格核验 transport 原 model 等于请求路由，并独立核验 provider_observation。回报超出该路由许可集合、观察无效或原 model 被改写都在发送后拒绝，原请求保留 unknown、不可重试，不能报告零 HTTP；配置、CLI、payload 或预检 model 不匹配则在入队/认证/HTTP 前拒绝。

没有可验证供应方response ID时，`response_id="local-response-sha256:"+SHA256(实际HTTP响应字节)`。该字段表示本地成功响应身份，不是供应方ID或远端幂等键；request_id始终原样回传，由现有Runtime管理恢复。请求头的用户可控内容不被伪装为远端回执。

2026-09-11 固定产品 User-Agent 修复：现有 JSON generations 与 multipart edits 共用的 Request 显式设置 `User-Agent: AI-PPT-Studio/0.4.0`，仅由 wrapper 固定常量提供；payload、宿主配置或环境变量不能自定义 header。已有 endpoint、TLS/无代理、helper、单次发送、无重试、闭合 schema 和请求正文保持。此增量基于总控同 key、同 GET `/v1/models` 的单变量诊断：urllib 默认 UA 返回 403、17 字节 text/plain、错误码 1010；仅改为诚实产品 UA 后返回 200，响应 hash 与既有 curl 路径相同。原真实 POST 只记录 HTTP 403，未采集到其 1010 错误码；GET 诊断不能改写为 POST 实录，也不证明修后生成成功。真实修后组件验证由总控使用新显式请求 ID 单独执行，保留原 failed-v1 目录与请求，不恢复或重发旧 ID。修复的专项验证、独审与提交状态以 C2 唯一台账为准；本增量不重新开启四基线、用户批准或已验收 UI。

### 2.1 供应方观察与请求身份

新增闭合 `provider_observation`：`version="image-led-provider-observation/v1"`；`reported={response:{},image:{}}` 分别只保留根回报和唯一图片条目中存在的 `model/quality/size/output_format`；其余字段为 `model_match`、`independent_engine_proof`、`response_sha256`、`observed_at_utc`。缺省的上游字段保持缺省，不能用请求目标补齐；观察时间是本地观察该回包的 UTC 时间，响应 hash 来自实际 HTTP 响应字节。

`model_match` 由上述全部显式型号计算：没有回报为 `not-reported`，全部精确等于请求路由为 `exact`，仅 Image 2 路由含合法 `gpt-image-2-codex` 回报时为 `compatible-image2-codex`。`independent_engine_proof` 固定为 false；该兼容是本次明确核定的接纳规则，不证明上游真正执行引擎，不扩成前缀、家族、别名表或 Sunburst 兼容。已知 CRS command v2 的观察缺失或篡改不能降级成旧响应；旧 v1/依赖注入未提供观察时保留证据缺口，只有实际提供并通过校验的观察才可落账。

### 2.2 原图完成保存与当前适用性

`2048x1152 / high / output_format=png / n=1` 是两个请求入口的目标参数。供应方回报的质量、尺寸和格式是 metadata；Runtime 完整解码原始图像字节，保存实际 `image_size`、MIME 和图像 hash，不能由回报或请求覆盖解码结果。继续保留原图，不缩放、裁切或重采样伪装成请求尺寸；下游忠实转换使用实际源图比例与几何。

当前 v2 CRS 的 Image 2 与 Sunburst 两条路由均执行 `image-led-output-fitness/v1`：原图宽高为 w/h，必须满足 `abs(16*h-9*w)<=8` 且 `w>=1280 && h>=720`。比例允许的误差仅对应高度四舍五入至多半像素，不采用百分比放宽或单张图片尺寸白名单。最低分辨率只是横屏阅读候选的技术底线，不证明中文逐字可读、设计还原、编辑性或用户验收。

回包合法且原图完整解码后，请求以 completed 保全；比例或分辨率不合适时当前 `generation_usability` 的状态为 `needs-revision`，保留原结果并阻断候选/选稿，不冒充 unknown 外发故障或自动重发。候选登记和选稿前重新核验当前原图与适用性，不能信调用方自报 fit、缺失/改写观察或回填尺寸绕过几何门。旧请求恢复仍只读取原请求；仅新的明确设计意图可建立新请求身份。

## 3. 认证与单请求、unknown边界

真实generate分支才可调用固定helper `/Applications/Codex API Client.app/Contents/Resources/crs-auth-helper`，一次执行、30秒子进程超时、仅进程内捕获stdout；超时终止并回收直接子进程，不宣称递归终止其全部后代。密钥只用于HTTP Authorization header，不写文件/日志/argv/公共工具参数，不使用环境占位密钥，不输出helper原始错误。

HTTP调用显式一次、每次阻塞socket操作timeout=300秒；不将该参数称作整次生成的wall-clock上限。不重试、禁止HTTP重定向、禁自动切换端点/provider。认证或网络/回包错误由包装器返回安全失败，现有command adapter和请求账本维持unknown身份；不因为失败自发重发。先完成无凭据的schema/MIME/base64等本地验证，再进入helper/HTTP。现有Runtime G-01/G-02行为保持：同request读取历史，unknown不二次外发，新的显式设计请求才产生新调用。

本轮只以合成helper/假HTTP响应验证代码，不执行真实helper或实际供应方HTTP。测试不能将模拟credential写入真实宿主配置；日志只记录计数/安全分类。

## 4. 真实进程绑定的不生图预检入口

在现有只读 `get_ai_ppt_project_snapshot` 增加可选布尔 `includeImage2Preflight`，默认false，保持工具数43和默认snapshot形状。true时由当次实际MCP→Python bridge读取当前adapter配置，只以附加 `image2_preflight` 返回非敏感能力信息，不创建task/artifact/event、不改变revision，不调用任何确认。此能力不会自动出现在用户审核UI。

保留三个必需 `AI_PPT_IMAGE2_ADAPTER_COMMAND`、`AI_PPT_IMAGE2_RECEIVER`、`AI_PPT_IMAGE2_MODEL` 和可选 `AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST`；.mcp.json声明转发这四键，**仅声明，不写用户值或宿主配置**。Node→Python现有继承保持。helper自身管理凭据，不需要放宽子进程secret allowlist；现有host确认secret禁止传递保持。

不能对任意COMMAND追加--preflight就执行。只识别下列两种完整 JSON argv，receiver 必须为 `CRS`，configured model、payload model 与命令型号必须一致：

| 配置型号 | 精确 COMMAND argv |
| --- | --- |
| `gpt-image-2` | `[当前 sys.executable 的绝对路径, 本已加载包 image2_crs.py 的确切绝对路径]` |
| `gpt-image-2.5-sunburst` | `[同一当前 Python, 同一当前包 wrapper, "--model", "gpt-image-2.5-sunburst"]` |

预检只在已识别 argv 后追加 `--preflight`。wrapper CLI 仅接受 `[]`、`[--preflight]`、`[--model,gpt-image-2.5-sunburst]`、`[--model,gpt-image-2.5-sunburst,--preflight]`；空参数明确是旧型号。旧两项命令配新 model、新四项命令配旧 payload、额外参数或其他顺序都拒绝，不使用宽松解析或 shell。`compile_body` 默认关键字 model 保持旧 MODEL，新路径显式传入同一已核定 Sunburst。身份核对使用实际路径和当前包文件，不能只看basename或caller提供hash；相似路径、伪包装器或陌生命令仅报告protocol-probe-unsupported，不运行它。没有配置则只返回presence/安全分类。也不执行helper以探测凭据是否存在。

`--preflight` 独立分支只验证固定运行能力和stat helper存在/可执行，**不读取helper内容、不执行helper、不创建文件、不请求网络**。stdin为闭合 `{protocol:"image-led-image2-preflight/v1",request_id}`；stdout闭合 `{protocol,request_id,receiver,model,helper_executable,external_connection:"not-tested"}`，逐字段/nonce严格核验；预检子进程timeout=10秒，超时终止并回收直接子进程，返回安全失败。正常返回仅表示已知本地协议可执行；helper不存在是能力缺口，不是用户授权失败。reader不输出COMMAND、路径、任意环境值、allowlist具体值或原始异常。

v2 输入使用既有 `image-led-image2-preflight/v2`，请求与响应均增加闭合 `generation_protocol` 并精确核验所需 `image-led-image2-transport/v2`；不新增 v3。两种型号的 probe model 都必须匹配同次已识别配置和 CLI 选择，协议/model/nonce 不符在入队及外发前拒绝。不能用旧 v1 ready 代替 v2 能力。

主入口附加结果含：四个已知配置键的presence布尔、known_wrapper布尔、protocol_probe（passed/unsupported/unavailable/failed）、helper_executable（未知时null）、external_connection固定not-tested；运行身份可保存当前wrapper代码hash和本次nonce，不包含凭据/客户内容。确切字段在实现时保持闭合一致，不能输出任意provider JSON。

已加载的真实MCP本轮不会更新，因此真实当前宿主的新预检 **NotRun**；隔离MCP和合成配置的结果只证明源码协议。shell presence绝不能替代真实MCP进程观察。未来经总控安排加载后再用此工具验证当前进程，无需真正生图来检查本地协议。

## 5. 离线 RED/GREEN 与加载交接

- wrapper输入/输出协议、原request_id/receiver/model、逐字文案/材料顺序、单图与多图multipart、无图JSON；恶意字段、路径素材、错目的地/base64/MIME在helper/HTTP之前失败。
- 旧两项与新四项 argv 分别覆盖 v1/v2；配置/CLI/payload/probe model 不一致在入队/认证/发送前拒绝，Flare/泛别名/额外参数/伪包装器不执行。核验实际 JSON 和解析后的 multipart model，不仅检查本地标签；回报超出当前路由许可集合、观察无效或 transport 原 model 不符是发送后拒绝、unknown 不重试，缺上游 model 保留证据缺口。
- 覆盖 Image 2 的精确/兼容/未回报、Sunburst 精确与跨族拒绝、根和图片每处显式字段、观察篡改与已知 CRS v2 缺失观察。独立系统输出要求不改客户 payload/hash/grant；实际原图按公式/最低尺寸检查，失败原图 completed 保全且 needs-revision、候选/选稿重检拒绝，恢复零重发，不能用缺观察绕过。
- 合成认证helper与假HTTP计数：正常一次helper/一次HTTP；失败/HTTP错误/重定向/超时/坏JSON/多图/空图均无重试，stdout/stderr没有synthetic密钥或客户文案。返回image原bytes不重编码；local-response-sha256只作本地身份。
- `--preflight`和snapshot预检的HTTP/helper调用计数严格0；陌生COMMAND的marker程序不被执行；缺键、错误argv/目的地、malformed probe安全返回且Runtime目录文件快照前后不变。默认snapshot仍兼容。
- 已知wrapper在隔离真实MCP→Python子进程路径运行preflight，manifest四键进入Python；合成脚本冒充basename不通过。协议错误不能被解释为真实provider失败或重新授权。
- 保留既有G-01/G-02单请求/unknown恢复测试；适用全Node/Python、Widget/typecheck/build，固定候选独立代码Review。
- 新wrapper须由release测试证明进入Skill和Plugin包；只写临时测试包，不安装到真实cache。加载方案列出固定提交/包hash、配置示例和确认实际进程来源的方法，不写实际用户配置，不承诺认证/网络/G3通过。

总控的在线验证是独立的组件级供应方集成试验：用纯本地合法 v2 envelope、非客户合成文本和图片驱动受审的实际 wrapper，不读客户，不虚构正式 Runtime/G0/grant 或接受记录。本轮按明确选择使用 `CRS / gpt-image-2`，当前用途需覆盖无图 generations 与双图 image[] edits，请求目标为 2048x1152 / high / PNG / n=1；单图 image 分支先离线覆盖，真实单图仅可选追加，不是当前客户用途前置门。Sunburst 历史实测及阻断保留，不阻塞 Image 2 路由。保存实际请求、原始 reported 观察、完整解码尺寸/格式/hash 与 output_fitness；接纳兼容回报不等于独立引擎证明。该试验不证明正式 Runtime 闭环、客户输入正确性、两张图均被模型采用或设计质量，真实三页另由总控沿正式入口验证；本轮源码任务不执行真实 HTTP/helper/安装或客户读写。

此B为供应方准备，不包含客户Runtime迁移、真实生成、图像定版、原生转换、PowerPoint/G3、安装加载或合并发布。
