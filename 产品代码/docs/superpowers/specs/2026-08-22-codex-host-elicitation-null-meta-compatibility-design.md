# Codex 宿主确认 `_meta: null` 协议兼容设计

## 1. 状态与范围

- 日期：2026-08-22
- 状态：用户已批准
- 适用范围：AI PPT Studio Node MCP 中的宿主原生表单确认边界
- 不在范围：Gate 业务合同、Runtime 验签规则、UI、内容或视觉对象、非宿主备用确认通道

本设计只修复 Codex Desktop 与当前 MCP SDK 对同一个可选元数据字段的解析差异，不降低 G0/G3/G4 或其他可信确认的安全要求。

## 2. 已验证故障

当前正式调用的实际边界行为为：

1. Codex Desktop 客户端声明 MCP form elicitation 能力；
2. AI PPT Studio 调用 `server.server.elicitInput(...)`；
3. 用户在宿主表单中确认；
4. Codex Desktop 回传：

   ```json
   {
     "action": "accept",
     "content": { "confirmed": true },
     "_meta": null
   }
   ```

5. `@modelcontextprotocol/sdk` 1.30.0 的 `ElicitResultSchema` 只允许 `_meta` 缺省或为对象；
6. SDK 在 `elicitInput()` 返回前拒绝 `_meta: null`；
7. AI PPT Studio 的 catch 将解析错误误报为 `HOST_CONFIRMATION_UNAVAILABLE`；
8. Runtime 未收到确认断言，项目 revision 和 Gate 因此没有改变。

已用 SDK 真实 Schema 最小复现：

- 无 `_meta`：通过；
- `_meta: {}`：通过；
- `_meta: null`：失败，错误为 `expected object, received null`。

## 3. 方案选择

### 3.1 采用：插件边界的窄兼容 Schema

AI PPT Studio 在发起宿主表单请求时，使用一个本地、窄范围的确认结果 Schema：

- `_meta` 可缺省；
- `_meta` 可为对象；
- `_meta` 可为 `null`，并且不参与用户身份或 Gate 证据判断；
- `action` 只能是 `accept | decline | cancel`；
- `content` 仍只是表单返回数据；
- 对当前确认表单，业务代码仍必须显式验证 `action === "accept"` 且 `content.confirmed === true`。

实现应绕过 SDK `elicitInput()` 内置的过严结果 Schema，但仍通过 SDK Server 的公开 `request()` 发送标准 `elicitation/create` 请求。不自行操作 stdio，不修改 JSON-RPC 传输层。

### 3.2 不采用：直接修改 SDK 或 `node_modules`

原因：重新安装后会丢失，无法成为可验证发布物，也会把宿主特定兼容逻辑混入第三方代码。

### 3.3 不采用：失败后重试第二次表单

原因：第一次真实用户动作已经发生，盲目重试会制造重复确认，并且不能修复解析根因。

## 4. 安全不变量

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
10. 一次失败的宿主响应不得在后续自动复用。

## 5. 代码边界

预计只修改：

- `mcp/server.mjs`：增加宿主确认请求的窄兼容边界，并让 Mission、Gate 和内容修改方案确认共用；
- `tests/mcp-server.test.mjs`：新增 `_meta:null` 回归和失败不写入检查。

不修改：

- Python Runtime Gate 验签实现；
- Gate 上下文和 challenge 数据结构；
- 正式项目数据；
- 两张审核页的前端布局或字段；
- 安装包中的第三方 SDK 源码。

## 6. 错误处理

- 客户端未声明 form elicitation：继续返回 `HOST_CONFIRMATION_UNAVAILABLE`；
- 客户端拒绝或取消：继续返回对应 declined 结果；
- 返回结构无法解析：不写入 Runtime，在错误 details 中记录 `phase: "elicitation-response"`；
- 用户确认成功但断言签发失败：不写入 Runtime，不重复弹出表单；
- Runtime 验签或 revision 检查失败：保留 Runtime 返回的原始业务错误，不改写为宿主不可用。

## 7. 测试和验收

### 7.1 定向回归

必须证明：

1. `accept + confirmed:true + _meta:null` 可完成断言签发和一次 Runtime 写入；
2. `_meta` 缺省和 `_meta:{}` 仍可正常工作；
3. `decline`、`cancel`、`confirmed:false`、缺少 `confirmed` 均不调用 `confirm-gate`；
4. 客户端没有 elicitation 能力时仍不写入；
5. 签发断言仍绑定当前 sourceVersion、evidence refs、revision 和 challenge；
6. Mission 和内容修改方案确认不被共享辅助函数破坏。

### 7.2 工程回归

代码变更后运行：

- MCP server 定向测试；
- `npm run quality`；
- `npm run test:python`；
- `git diff --check`。

自动化通过只能证明工程回归通过，不等于真实 G0 通过。

### 7.3 真实宿主验收

1. 构建并安装当前插件发布候选；
2. 重启 Codex/MCP，证明新任务加载当前插件；
3. 读取正式项目的当前 revision 和 G0；
4. 只发起一次当前 revision 的 G0 宿主确认；
5. 用户在宿主表单中确认；
6. 再次读取项目快照；
7. 只有快照证明 G0 已确认、revision 已前进，才能宣布真实宿主验收通过并进入视觉阶段。

## 8. 非根因项

当前日志另有 `ai-ppt-studio@personal` 与正式插件 MCP server 同名警告。加载器已跳过后发现的重复项，它不是本次 `_meta:null` 解析失败的根因。旧插件清理应作为独立变更处理，不与本次修复合并。
