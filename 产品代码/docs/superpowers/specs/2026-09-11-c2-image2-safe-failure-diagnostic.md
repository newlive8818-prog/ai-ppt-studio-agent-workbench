# C2 Image 2 安全失败诊断小合同

状态：2026-09-11 总控已授权同一 C2 必要修复；本合同先回传，再准备失败测试。工程通过不代表正式 S04 根因已定位。执行位置沿用 `codex/image-led-native-anchors` / 28a9。

正式 S04 只有 `unknown / RuntimeError`。旧包装器统一输出固定 stderr，父适配器丢弃 stderr，Runtime 仅保存异常类别。总控对照不支持凭据或 CA 环境差异假设；runpy 成功不能证明正式子进程路径成功。旧请求仅 recover，不重发或补造历史。

## 选择与边界

采用固定包装器 stdout 的闭合失败 envelope，stderr 继续 DEVNULL。开放原始日志会泄漏数据；仅增加父进程 exit 则不能定位阶段。成功协议、请求字节、模型、授权、TLS、无代理、单次 HTTP 和原图处理保持。诊断不增加用户批准门，不产生重试权限，不改变 UI。

失败 envelope 固定为 `protocol=image-led-command-failure/v1`、`request_sha256`、`failure_diagnostic`。SHA256 对实际 stdin UTF-8 字节计算；不能用重序列化结果。只在已知绝对包装器路由、非零退出、长度不超过 2048 bytes、请求 hash 匹配时接受；重复键、额外字段、类型错误、矛盾状态、未知枚举全部拒绝。preflight 保持既有 stat-only 协议。

`failure_diagnostic` 全部字段闭合：

| 字段 | 合同 |
| --- | --- |
| version | `image-led-failure-diagnostic/v1` |
| stage | `input`, `compile`, `credential-helper`, `http-open`, `response-read`, `provider-decode`, `wrapper-receipt`, `adapter-receipt`, `image-decode`, `subprocess` |
| transport_state | `before-send`, `send-attempted`, `response-received`, `not-established` |
| http_attempted | false、true、null，分别对应 before-send、两个已尝试状态、not-established |
| reason | 固定类别见下表；禁止动态异常消息和类名 |
| http_status | null 或严格整数 100..599；只有 response-received 可非空 |
| subprocess_exit_code | null 或实际父进程取得的退出码；包装器自报必须 null；负数表示信号 |

| stage | 固定 reason | 合法 transport_state |
| --- | --- | --- |
| input | invalid-input | before-send |
| compile | compile-failed | before-send |
| credential-helper | helper-failed, helper-timeout | before-send |
| http-open | http-error, tls-error, connection-error, timeout, unknown-failure | send-attempted；HTTPError 为 response-received |
| response-read | response-read-failed, timeout | response-received |
| provider-decode | provider-decode-failed | response-received |
| wrapper-receipt | wrapper-receipt-failed | response-received |
| adapter-receipt | adapter-receipt-invalid | not-established |
| image-decode | image-decode-failed | not-established |
| subprocess | subprocess-failed | not-established |

调用 `opener.open` 之前为 before-send；进入调用只证明 send-attempted，不证明服务方收到。返回 HTTP 响应对象或 HTTPError 才记录 response-received，随后区分读取、供应方解码、包装器回执。父进程无可信 envelope 时只记录 subprocess/adapter-receipt 与 not-established；Runtime 本地图像解码独立记录，不对注入 transport 推断 HTTP。

父适配器只接受固定包装器 envelope，把实际退出码补入经验证的内部失败对象。Runtime 只提取确切内部类型的闭合诊断，任意异常上的同名属性不得透传。既有 `ContractValidationError` 分类保留；原 RuntimeError 分支仍记录 RuntimeError。新增 `failure_diagnostic` 仅属于未来 unknown 回执，request/claim/pack 身份沿用现有父回执。成功回执不增加字段。

不得记录凭据、helper stdout、原始 stderr/traceback、客户文案、环境值、HTTP headers/body 或供应方全文。现有 unknown 历史不变、recover 不写、不重发；失败诊断不能成为候选或用户定版证据。

## 验证

用合成材料和模拟 helper/HTTP 证明：发送前失败、TLS/连接失败、HTTPError、响应读取、JSON/图片解码、回执损坏、负退出码；超长/重复键/额外字段/错误 hash/布尔冒充整数/矛盾 attempted/未知枚举拒绝；秘密哨兵不进入输出与持久化；失败保持原 claim 且 recover 零写入、零重发。补充真实新解释器的纯离线输入失败，覆盖 stdin pipe 和最小环境，但不把它作为真实 HTTP 成功。

实现和证据只记入 [唯一台账](../../validation/c2-image-led/verification-report.md)，计划见 [执行计划](../plans/2026-09-11-c2-image2-safe-failure-diagnostic.md)。旧 S04、客户数据和安装包不在本轮源码任务读写范围。

## 2026-09-11 解码诊断增量（同一 C2 已授权）

总控真实S04新请求收到HTTP200后为`provider-decode-failed/unknown`；其已持久回执没有原始响应正文、SSE事件或失败图片字节，无法靠现有recover离线重解码。随后总控回报同一stream包的S05成功，不能概括为整个stream能力失效。本增量只修复拒绝点无法辨认的诊断缺口，不宣称真实S04根因已经定位。

外层`image-led-command-failure/v1`、2048-byte上限、实际stdin hash、已知包装器身份、父进程实际退出码及旧`image-led-failure-diagnostic/v1`保持。新请求在HTTP200后选择响应解析分支，若在`response-read`或`provider-decode`失败，则采用显式`image-led-failure-diagnostic/v2`：保留原七字段，增加且仅增加闭合的`decode_context`。其他阶段继续原七字段；旧回执不补写。

| decode_context字段 | 精确含义与校验 |
| --- | --- |
| response_format | `sse`或`json-fallback`，表示本次选择的解析分支；不证明body本身是有效的对应格式，不保存原始Content-Type |
| response_bytes_observed | 严格整数0..2^53-1；实际read/readline已返回给wrapper的bytes长度累计，包含触发拒绝的返回bytes；读取抛异常而未返回的底层网络字节不在此数内 |
| sse_blocks_seen | SSE为严格整数0..257；以空行结束并已进入分派的块数，包括空块、注释心跳及DONE，不等于有效图片事件数。JSON分支必须null |
| sse_final_seen | SSE为严格布尔；只有符合请求endpoint的完成事件通过metadata、base64和PNG头检查后为true。它不表示完整像素解码、后续流结束或成功交付；此时blocks必须非零。JSON分支必须null |

新v2只允许上述两个阶段且http_status必须为严格整数200。枚举、额外字段、数值范围、布尔冒充计数、JSON/SSE字段矛盾和reason格式前缀不匹配全部拒绝。父适配器仍只接受确切受信失败载体，Runtime与MCP沿现有安全回执路径透传，无新增写者、路由或UI。wrapper和诊断validator必须成对交付；只更新wrapper会使旧validator拒绝新诊断，不属于有效候选。

`provider-decode`保留原`provider-decode-failed`作未知内部错误回退，并增加以下固定原因；不记录原始异常消息、供应方event/type/model文本、headers、正文、图片或输入信息：

| 拒绝范围 | 固定reason |
| --- | --- |
| SSE读取与界限 | `sse-read-type-invalid`, `sse-line-limit`, `sse-total-limit`, `sse-event-limit`, `sse-block-limit` |
| SSE分帧/编码 | `sse-incomplete-event`, `sse-line-ending-invalid`, `sse-utf8-invalid`, `sse-control-character`, `sse-done-with-event`, `sse-json-invalid` |
| SSE事件形态 | `sse-event-shape-invalid`, `sse-provider-error`, `sse-event-envelope-unsupported`, `sse-event-name-mismatch`, `sse-event-type-unsupported`, `sse-empty-event-invalid` |
| SSE终态与图片 | `sse-duplicate-final`, `sse-partial-after-final`, `sse-heartbeat-image`, `sse-final-missing`, `sse-base64-invalid`, `sse-png-header-invalid` |
| SSE字段/metadata | `sse-field-invalid`, `sse-retry-invalid`, `sse-event-name-invalid`, `sse-model-invalid`, `sse-metadata-invalid` |
| JSON fallback | `json-parse-invalid`, `json-response-shape-invalid`, `json-image-shape-invalid`, `json-model-invalid`, `json-metadata-invalid`, `json-base64-invalid`, `json-png-header-invalid` |
| 整次期限 | `deadline-exceeded`，仅由本进程signal抛出的确切内部TimeoutError子类识别；同时识别urlopen包装该确切类型的URLError。可在credential-helper/http-open/response-read/provider-decode出现；普通socket超时保持`timeout` |

本次不放宽任何成功接纳条件：两种准确事件族、唯一完成图、model白名单、base64/PNG头、SSE大小/数量限制、DONE消费前缀语义、原始输入、单次POST、TLS和无代理均保持。未知事件只标记固定原因，不猜测或自动接纳；provider error只记录存在性对应的固定原因，不保存其内容。原始响应保全/离线图片恢复没有接入；已有unknown继续仅查询、不能重发或改写completed。

验证限定为合成wire反例、旧协议/诊断兼容、内部deadline与socket区分、父Adapter和Runtime真实本地链穿透及recover零写入零重发，以及已审候选差分。客户实测由总控在受审诊断候选上执行，不把本地验证冒称客户请求恢复或三页PPTX完成。
