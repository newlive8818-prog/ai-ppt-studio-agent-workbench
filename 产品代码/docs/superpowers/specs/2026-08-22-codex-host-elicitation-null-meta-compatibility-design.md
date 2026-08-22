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

插件为 `openai/form` 定义窄结果 Schema：

- `_meta` 可缺省、为对象或为 `null`；
- `action` 只能是 `accept | decline | cancel`；
- `content` 只接受表单可表达的对象；
- `_meta` 不参与用户身份、Gate 证据或业务判断；
- 业务接受条件仍是 `action === "accept" && content.confirmed === true`。

标准回退继续使用 SDK 原生 `elicitInput()` 和 SDK 标准结果校验，不试图为其他宿主放宽协议。

### 3.3 不采用的其他方案

不修改 SDK 或 `node_modules`：重新安装后会丢失，也会把宿主特定兼容逻辑混入第三方代码。

不从错误文本恢复确认：JSON-RPC 错误不是可信用户动作凭据，且无法证明返回内容、确认上下文或动作唯一性。

不在协议失败后自动回退到另一通道：第一次真实用户动作可能已经发生，自动重试会制造重复确认。

## 4. 架构与数据流

### 4.1 组件边界

`mcp/server.mjs` 增加一个共享宿主表单请求辅助函数，职责仅为：

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

### 4.2 成功数据流

```text
工具调用
-> Runtime 返回当前确认上下文和 challenge
-> Node MCP 检查宿主能力
-> Codex: openai/form；其他宿主: elicitation/create
-> 用户在真实宿主表单操作
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
12. 自动化通过不得表述为真实 G0 已通过。

## 6. 代码边界

预计只修改：

- `mcp/server.mjs`：增加能力路由、`openai/form` 窄结果 Schema 和共享请求辅助函数；Mission、Gate 和内容修改方案确认共用；
- `tests/mcp-server.test.mjs`：增加自定义 `openai/form` 协议对端、`_meta:null` 回归、标准回退和失败不写入检查。

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

使用带自定义 `openai/form` Request Schema 的测试客户端，证明：

1. 客户端声明 `extensions["openai/form"]` 后，插件发送且只发送一次 `openai/form`；
2. `accept + confirmed:true + _meta:null` 可完成断言签发和一次 Runtime 写入；
3. 断言仍绑定当前 sourceVersion、evidence refs、revision 和 challenge；
4. 标准 elicitation handler 不会在扩展路径被调用；
5. `decline`、`cancel`、`confirmed:false`、缺少 `confirmed` 均不调用权威写入；
6. 扩展协议错误不触发标准通道自动重试。

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
2. 完全重启 Codex/MCP，证明新任务加载当前插件；
3. 重新读取正式项目的当前 revision 和 G0，不沿用历史 revision 假设；
4. 只发起一次当前 revision 的 G0 宿主确认；
5. 用户在真实宿主表单中确认；
6. 再次读取项目权威快照；
7. 只有工具成功、revision 前进、G0 在权威快照中为 confirmed/passed，且 Runtime history 绑定本次 challenge，才能宣布真实宿主验收通过并进入视觉阶段。

## 9. 非根因项

当前日志另有 `ai-ppt-studio@personal` 与正式插件 MCP server 同名警告。加载器已跳过后发现的重复项，它不是本次 `_meta:null` 解析失败的根因。旧插件清理应作为独立变更处理，不与本次协议修复合并。
