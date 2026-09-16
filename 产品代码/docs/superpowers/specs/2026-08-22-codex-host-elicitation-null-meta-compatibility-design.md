# Codex 宿主表单确认协议兼容设计

## 1. 状态与范围

- 日期：2026-08-22
- 状态：用户已批准修正方案
- 适用范围：AI PPT Studio Node MCP 中的宿主原生表单确认边界
- 不在范围：Gate 业务合同、Runtime 验签规则、UI、内容或视觉对象、非宿主备用确认通道
- 修正记录：第一版“只放宽插件侧标准 elicitation 结果 Schema”已被 TDD 证伪；本版以 Codex 的 `openai/form` 扩展为首选通道，并保留标准 MCP 回退

本设计只修复 Codex Desktop 与标准 MCP SDK 在表单响应解析上的协议兼容问题，不降低 G0/G3/G4、Mission 或整套内容修改方案确认的安全要求。

## 2. 已验证故障与证伪过程

### 2.1 真实宿主返回

当前正式调用的实际边界行为为：

1. Codex Desktop 声明 MCP form elicitation 能力；
2. AI PPT Studio 调用标准 `server.server.elicitInput(...)`；
3. 用户在真实宿主表单中确认；
4. Codex Desktop 回传：

   ```json
   {
     "action": "accept",
     "content": { "confirmed": true },
     "_meta": null
   }
   ```

5. `@modelcontextprotocol/sdk` 1.30.0 的 `ElicitResultSchema` 只允许 `_meta` 缺省或为对象；
6. SDK Client 在响应发回插件前拒绝 `_meta: null`，并产生 JSON-RPC `-32602`；
7. AI PPT Studio 只能收到协议错误，无法取得已经发生的真实用户确认；
8. Runtime 未收到确认断言，项目 revision 和 Gate 没有改变。

已用 SDK 真实 Schema 最小复现：

- 无 `_meta`：通过；
- `_meta: {}`：通过；
- `_meta: null`：失败，错误为 `expected object, received null`。

### 2.2 第一版插件 Schema 方案为什么失效

第一版尝试绕过 `elicitInput()`，改用：

```js
server.server.request(
  { method: "elicitation/create", params },
  HostElicitResultSchema,
);
```

这个方案仍然失败。原因不是插件的结果 Schema，而是 SDK Client 对 `elicitation/create` 注册了专门包装器：宿主返回值在发送到插件之前就必须通过 SDK 自带的 `ElicitResultSchema`。当 `_meta` 为 `null` 时，上游已把真实结果转换成 `Invalid elicitation result` 的 JSON-RPC 错误。插件侧再宽松的结果 Schema 也不能从错误中恢复原始确认。

因此，以下方案已明确废止：

- 继续用标准 `elicitation/create`，只修改插件侧结果 Schema；
- 从 `-32602` 错误文本推断用户已经确认；
- 在失败后自动弹出第二次确认表单。

### 2.3 当前 CRS API 客户端拓扑

本修复必须覆盖用户当前实际使用的 CRS 通道，而不是只覆盖一个假设的官方直连环境。2026-08-22 的本机只读取证据为：

- 当前 Codex 配置使用 `model_provider = "crs"`；
- 当前模型为 `gpt-5.6-sol`，CRS provider 使用 `wire_api = "responses"`；
- 当前前台宿主进程来自 `/Applications/ChatGPT.app`；
- MCP/App Server 子进程来自 `/Applications/ChatGPT.app/Contents/Resources/codex`；
- 旧的 `/Applications/Codex API Client.app` 已安装，但不是当前运行的 MCP 宿主进程；
- 当前宿主使用 `/Users/defei/Library/Application Support/Codex API Client/codex-home` 作为 Codex home；
- 同一个 `com.openai.codex` 桌面日志记录了 `mcpServer/elicitation/request` 以及 `{"action":"accept","content":{"confirmed":true},"_meta":null}`。

因此当前组件边界是：

```text
CRS Responses API
-> 模型推理与工具选择
-> ChatGPT/Codex App Server
-> 本地 MCP stdio
-> AI PPT Studio
```

CRS 替换的是模型 API 上游，不是本地 MCP 初始化者或宿主表单实现者。当前 `openai/form` 修复仍应落在 AI PPT Studio 与 ChatGPT/Codex App Server 的协议边界。真实验收必须保留当前 CRS provider 配置，证明修复在用户实际通道下成立；不能只用官方直连或测试客户端结果代替。

### 2.4 第二版直接 `openai/form` 方案为什么仍失效

第二版按 Codex 内置服务的模式，把请求 method 改为 `openai/form`，并为结果提供接受 `_meta:null` 的自定义 Schema。TDD 证明：

1. MCP SDK Server 已经发送 `openai/form` 请求；
2. 原始测试宿主已经收到请求并返回 `_meta:null`；
3. 但 SDK Server 的 Protocol 在调用请求专属结果 Schema 之前，先用通用 JSON-RPC Result Schema 判断消息类型；
4. 该通用 Schema 同样拒绝顶层 `result._meta:null`；
5. 响应因此没有进入 pending request resolver，最终表现为请求超时。

所以“只改 method + 自定义结果 Schema”仍是假修复。Codex 内置 `artifact-template-picker` 可用，是因为它使用自己的原始 JSON-RPC 循环，没有经过当前 MCP SDK 的通用响应分类。

最小实验已证明：在 transport 把消息交给 SDK Protocol 之前，只针对已发出的 `openai/form` request ID，把对应成功响应的顶层 `result._meta:null` 归一为字段缺省，响应可以正常进入自定义结果 Schema，并保留原始 `action` 和 `content`。

## 3. 方案选择

### 3.1 采用：`openai/form` 优先，标准 MCP 回退

AI PPT Studio 在初始化完成后读取客户端能力：

```text
capabilities.extensions["openai/form"]
capabilities.elicitation
```

请求规则固定为：

1. 若存在 `extensions["openai/form"]`，调用 Codex 扩展方法 `openai/form`；
2. 否则若存在标准 `elicitation` 能力，调用 SDK 的 `elicitInput()`，即标准 `elicitation/create`；
3. 两者都不存在时返回 `HOST_CONFIRMATION_UNAVAILABLE`；
4. 已选择的通道发生协议错误时不自动切换或重试，避免同一次工具调用制造第二个用户确认；
5. 下一次明确的用户工具调用可以重新按当前能力选择通道。

Codex Desktop 自带的 `artifact-template-picker/server.mjs` 已证明当前宿主的官方扩展方式：初始化时读取 `params.capabilities.extensions["openai/form"]`，再直接发送 `method: "openai/form"`。AI PPT Studio 复用同一扩展合同，不修改桌面应用、不修改 SDK，也不自行操作 stdio。

### 3.2 扩展请求和结果边界

扩展请求继续使用当前表单参数：

```json
{
  "message": "面向用户的当前确认上下文",
  "requestedSchema": {
    "type": "object",
    "properties": {
      "confirmed": { "type": "boolean" }
    },
    "required": ["confirmed"]
  }
}
```

插件为 `openai/form` 定义窄结果 Schema，并在 MCP transport 外围增加一个 request-ID 绑定的兼容层：

- 发出 `openai/form` 前记录本次 JSON-RPC request ID；
- 只对该 request ID 的成功响应检查顶层 `result._meta`；
- 当且仅当其严格等于 `null` 时，复制响应并删除该可选字段；
- 成功、错误、取消、超时或发送失败后清理 request ID；
- 普通 MCP 消息、标准 elicitation 和其他 request ID 不经过归一化；
- 错误响应不转换成成功响应；
- `action` 只能是 `accept | decline | cancel`；
- `content` 只接受表单可表达的对象；
- `_meta` 不参与用户身份、Gate 证据或业务判断；
- 业务接受条件仍是 `action === "accept" && content.confirmed === true`。

标准回退继续使用 SDK 原生 `elicitInput()` 和 SDK 标准结果校验，不试图为其他宿主放宽协议。

### 3.3 不采用的其他方案

不修改 SDK 或 `node_modules`：重新安装后会丢失，也会把宿主特定兼容逻辑混入第三方代码。兼容层由插件源码拥有并随发布物验证。

不从错误文本恢复确认：JSON-RPC 错误不是可信用户动作凭据，且无法证明返回内容、确认上下文或动作唯一性。

不在协议失败后自动回退到另一通道：第一次真实用户动作可能已经发生，自动重试会制造重复确认。

## 4. 架构与数据流

### 4.1 组件边界

`mcp/host-form-transport.mjs` 包装既有 MCP transport，职责仅为：

1. 跟踪本插件发出的 `openai/form` request ID；
2. 在 SDK Protocol 之前归一化对应成功响应的 `result._meta:null`；
3. 在响应、错误、取消、关闭或发送失败时清理跟踪状态；
4. 原样代理 transport 的 `start`、`send`、`close`、callback、session 和 protocol-version 合同。

`mcp/server.mjs` 增加共享宿主表单请求辅助函数，职责仅为：

1. 读取已经协商的客户端能力；
2. 选择 `openai/form` 或标准 elicitation；
3. 校验并返回表单动作和内容；
4. 给调用方提供实际协议通道，供错误诊断使用。

Mission、Gate 和整套内容修改方案三个调用方继续负责：

- 构造各自的当前确认上下文；
- 检查 `accept` 和 `confirmed === true`；
- 生成不可复用的本次宿主动作引用；
- 交给现有 `confirmationAuthority` 签发版本绑定断言。

Python Runtime 继续负责最终验签、revision/challenge 校验、防重放和权威写入。

CRS provider 不进入确认断言信任链。它可以影响模型推理与工具选择，但不能签发、修改或替代宿主动作、challenge、断言或 Runtime 写入。

### 4.2 成功数据流

```text
工具调用
-> Runtime 返回当前确认上下文和 challenge
-> Node MCP 检查宿主能力
-> Codex: openai/form；其他宿主: elicitation/create
-> 用户在真实宿主表单操作
-> openai/form transport 只归一化当前 request ID 的 result._meta:null
-> Node MCP 校验 action 和 confirmed
-> confirmationAuthority 签发当前上下文断言
-> Python Runtime 最终验签并单次消费
-> revision 前进并返回权威快照
```

### 4.3 失败数据流

任一以下情况都在断言签发或 Runtime 写入前终止：

- 两类能力均不存在；
- 宿主返回协议错误或结果结构不合法；
- 用户 `decline` 或 `cancel`；
- `action` 不是 `accept`；
- `confirmed` 缺失或不为布尔值 `true`；
- 断言签发失败；
- Runtime 验签、revision、challenge 或防重放检查失败。

## 5. 安全不变量

修复前后必须保持：

1. 普通聊天文字不能代替宿主用户动作；
2. AI 不能自行构造 `host-elicitation://` 后跳过宿主表单；
3. `accept` 但 `confirmed` 不为 `true` 时不得写入；
4. `decline` 或 `cancel` 时不得写入；
5. 表单解析失败时不得写入；
6. 宿主动作只能用于签发当前确认上下文的版本绑定断言；
7. 断言继续绑定 project/path、Gate 或 scope、sourceVersion、evidence refs、revision、challenge/nonce、expiry 和消费状态；
8. Python Runtime 继续负责最终验签、revision 检查和防重放；
9. 不直接修改正式项目 `state.json`；
10. 一次失败的宿主响应不得在后续自动复用；
11. 扩展能力存在时发生错误不得在同一次调用内自动重试标准通道；
12. transport 兼容层不得修改 `action`、`content`、错误响应或非 `openai/form` 消息；
13. request ID 必须在完成、错误、取消、关闭或发送失败后清理；
14. 自动化通过不得表述为真实 G0 已通过。

## 6. 代码边界

预计只修改：

- `mcp/host-form-transport.mjs`：新增 request-ID 绑定的 `openai/form` transport 兼容层；
- `mcp/server.mjs`：增加能力路由、`openai/form` 窄结果 Schema 和共享请求辅助函数；Mission、Gate 和内容修改方案确认共用；
- `tests/host-form-transport.test.mjs`：验证严格归一化范围、清理和透明代理；
- `tests/mcp-server.test.mjs`：用 transport 级原始宿主响应夹具验证 `_meta:null`、标准回退和失败不写入。

不修改：

- Python Runtime Gate 验签实现；
- Gate 上下文和 challenge 数据结构；
- 正式项目数据；
- 两张审核页的前端布局或字段；
- 安装包中的第三方 SDK 源码；
- Codex Desktop 应用文件。

## 7. 错误处理

- 两类能力均未声明：返回 `HOST_CONFIRMATION_UNAVAILABLE`；
- `openai/form` 或标准 elicitation 协议失败：不写入 Runtime，错误 details 记录 `phase: "host-form-response"` 和实际 `transport`；
- 用户拒绝或取消：返回 `HOST_CONFIRMATION_DECLINED`，不写入；
- `accept` 但 `confirmed` 缺失或不为 `true`：按未确认处理，不写入；
- 用户确认成功但断言签发失败：不写入 Runtime，不重复弹出表单；
- Runtime 验签或 revision 检查失败：保留 Runtime 原始业务错误，不改写为宿主不可用；
- 错误 details 不记录原始表单内容、签名断言、secret 或用户敏感数据。

## 8. 测试和验收

### 8.1 协议级 RED 证据

保留一个窄测试证明：标准 `elicitation/create` 配合 SDK Client 返回 `_meta:null` 时产生 `-32602 Invalid elicitation result`。该测试用于锁定第一版方案为何无效，不要求生产代码把它变绿。

### 8.2 `openai/form` 定向回归

测试必须在 SDK Client Protocol 之前拦截原始 `openai/form` 请求并返回原始 JSON-RPC 结果，不能用 SDK Client 的自定义 request handler 冒充真实宿主。必须证明：

1. 客户端声明 `extensions["openai/form"]` 后，插件发送且只发送一次 `openai/form`；
2. `accept + confirmed:true + _meta:null` 可完成断言签发和一次 Runtime 写入；
3. 断言仍绑定当前 sourceVersion、evidence refs、revision 和 challenge；
4. 标准 elicitation handler 不会在扩展路径被调用；
5. `decline`、`cancel`、`confirmed:false`、缺少 `confirmed` 均不调用权威写入；
6. 扩展协议错误不触发标准通道自动重试。

transport 单元测试还必须证明：

1. 只有 tracked `openai/form` 成功响应的顶层 `result._meta:null` 被删除；
2. 其他 request ID、嵌套 `content._meta`、`_meta:{}` 和错误响应原样保留；
3. 响应、错误、取消、发送失败和关闭都会清理 pending ID；
4. transport callbacks、session ID 和 protocol version 原样代理。

### 8.3 标准回退与共享调用方回归

必须证明：

1. 不声明 `openai/form`、只声明标准 elicitation 时，现有标准成功响应继续工作；
2. `_meta` 缺省和 `_meta:{}` 的标准响应继续工作；
3. 两类能力都没有时仍不写入；
4. Mission 和内容修改方案确认仍保留各自上下文、拒绝语义和断言绑定。

### 8.4 工程回归

代码变更后运行：

- MCP server 定向测试；
- 完整 MCP server 测试；
- `npm run quality`；
- `npm run test:python`；
- `git diff --check`。

自动化通过只能证明工程回归通过，不等于真实 G0 通过。

### 8.5 真实宿主验收

1. 构建并安装当前插件发布候选；
2. 保持 `model_provider = "crs"` 和 `wire_api = "responses"`，不切换成另一 API 通道规避问题；
3. 完全重启 Codex/MCP，证明新任务加载当前插件；
4. 复核当前运行宿主仍是 ChatGPT/Codex App Server，并记录插件加载证据；
5. 重新读取正式项目的当前 revision 和 G0，不沿用历史 revision 假设；
6. 只发起一次当前 revision 的 G0 宿主确认；
7. 用户在真实宿主表单中确认；
8. 再次读取项目权威快照；
9. 只有工具成功、revision 前进、G0 在权威快照中为 confirmed/passed，且 Runtime history 绑定本次 challenge，才能宣布当前 CRS 通道下的真实宿主验收通过并进入视觉阶段。

## 9. 非根因项

当前日志另有 `ai-ppt-studio@personal` 与正式插件 MCP server 同名警告。加载器已跳过后发现的重复项，它不是本次 `_meta:null` 解析失败的根因。旧插件清理应作为独立变更处理，不与本次协议修复合并。
