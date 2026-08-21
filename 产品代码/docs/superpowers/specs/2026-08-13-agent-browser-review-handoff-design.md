# AI PPT Studio Agent Browser 审阅交接设计

## 1. 背景与根因

当前生产入口通过独立 stdio MCP 进程启动：

```js
export async function startServer() {
  const server = createAiPptMcpServer();
  await server.connect(new StdioServerTransport());
}
```

`createAiPptMcpServer()` 的测试注入接口允许传入 `browserSurfaceAdapter`，但正式启动入口没有宿主桥接协议可以构造这个进程内 JavaScript 对象。因此生产路径中的 `browserSurfaceAdapter` 恒为 `null`。旧实现又在创建 Review Bridge 前要求 `browserSurfaceAdapter.canOpen/canSave`，导致已经具备完整读取与保存能力的 loopback Review Bridge 永远无法启动，并把“插件进程没有宿主适配器”误报为“Codex 宿主没有 Browser”。

此外，`canSave` 的职责放置错误。标记保存由专业审阅页通过同源 Origin、Bearer、`sourceVersion` 和 `expectedRevision` 调用 Review Bridge，再由 Python 权威运行时持久化；Browser 打开适配器不承担保存。

## 2. 方案比较

### 方案 A：为 stdio 子进程注入宿主 JavaScript 适配器

优点是保留 MCP 工具“一次调用即打开”的旧接口。缺点是当前插件启动协议没有跨进程宿主 RPC，普通函数参数无法穿过 stdio 进程边界；为此新建专用宿主协议会扩大范围，也不能由插件单方面实现。

### 方案 B：Review Bridge 与 Agent Browser 两段式交接（采用）

MCP 工具验证权威投影并启动短时 scoped Review Bridge，返回只供当前 Agent 立即使用的 URL。AI PPT Studio Skill 随后要求 Agent 调用当前已连接的 Codex In-app Browser 打开该 URL。页面读取与保存仍全部经过 Review Bridge 和 Python 权威运行时。

该方案与权威系统架构中“`MCP 创建 scoped Review URL → Codex Agent 请求 Browser Surface Adapter 打开`”一致，不要求 MCP 子进程操纵 Codex UI，也不回退为聊天 Widget 或外部浏览器。

### 方案 C：MCP 子进程调用系统默认浏览器

实现简单，但无法证明目标是 Codex 内置 Browser，违反已批准产品合同，因此不采用。

## 3. 正式合同

`open_ai_ppt_browser_review` 执行以下步骤：

1. 从 Python 权威运行时读取指定 `reviewType` 的当前投影；
2. 校验调用方 `sourceVersion`，不匹配时返回 `REVIEW_SOURCE_STALE`，且不创建会话；
3. 创建只绑定 `127.0.0.1`、单项目、单审阅类型、单源版本和单 revision 的短时 Review Bridge；
4. 若显式注入的兼容 adapter 成功打开 URL，返回 `status=opened`、`opened=true`、`openMode=host-adapter`；
5. 若没有 adapter，或 adapter 不能/未能打开，保留会话并返回 `status=review-session-ready`、`opened=false`、`openMode=agent-browser`、`browserAction=open-scoped-url` 与 scoped URL；
6. Agent 必须立即使用 Codex In-app Browser 打开返回 URL。只有 Browser 工具实际打开后，才可以对用户表述为“已打开”；
7. 若 Agent 没有 Browser 工具或打开失败，由 Agent 报告准确的 Browser 能力缺口。MCP 不再把“未注入进程内 adapter”等同于宿主 Browser 缺失。

scoped URL 包含短时 fragment 令牌，只出现在本次工具结构化结果和 Browser 导航参数中；不得写入项目状态、事件、日志、验证证据或持久文档。

## 4. 保存与错误语义

- 保存能力属于 Review Bridge，不属于 Browser 打开 adapter。
- 页面首次读取必须使用 Bearer；写入还必须通过同源 Origin、Bearer、`sourceVersion`、`expectedRevision` 和 Python revision 校验。
- `BROWSER_REVIEW_SAVE_UNAVAILABLE` 只表示 Review Bridge / 权威保存链路确实不可用，不能由缺少 `browserSurfaceAdapter.canSave` 推导。
- `BROWSER_REVIEW_UNAVAILABLE` 只表示 Agent 实际没有可调用的 Codex In-app Browser，或 Browser 实际拒绝/无法打开 scoped URL；MCP stdio 进程未注入 adapter 不是该错误的充分条件。
- 创建 Review Bridge、读取权威投影或生成审阅壳失败时返回对应的 Review Bridge / source 错误，不伪装成宿主 Browser 缺失。

## 5. 生命周期

两段式交接增加一次 Agent 工具往返。会话保持五分钟硬过期，但在首次带 Bearer 的 API 请求前使用“启动宽限”，不会沿用页面活跃期的 30 秒 lease 提前清理。首次读取/心跳后，会话进入现有短 lease 管理；最后一个活跃 lease 结束或硬 TTL 到期后停止。

HTML shell 的匿名同源 GET 不获得业务数据；真正激活会话的是携带正确 Bearer 的 API 请求。URL fragment 在页面加载后仍按现有前端合同从地址栏移除，只保存在页面内存。

## 6. 兼容性

- 保留 `browserSurfaceAdapter.openUrl()` 注入接口，供未来真实宿主桥接或测试使用。
- 不再要求 adapter 声明 `canSave`。
- 工具名与输入 Schema 不变，避免插件调用方迁移。
- 输出增加 `status`、`opened`、`openMode`、`browserAction` 和两段式路径所需的 `url`；旧的成功直开路径仍保留 `opened=true`。
- 普通 MCP 工具继续只返回纯数据，不附带 MCP UI template。

## 7. 验收

自动化必须证明：

1. 无 adapter 的正式服务器可创建 scoped Review URL，结果不再是 `BROWSER_REVIEW_UNAVAILABLE`；
2. 返回结果不宣称已打开，并明确要求 Agent Browser 动作；
3. 注入 adapter 的兼容路径仍能直开；adapter 打开失败时可退回 Agent 交接而不销毁会话；
4. 旧 `canSave=false` 不再阻断，因为保存由 Review Bridge 负责；
5. sourceVersion 过期时不创建会话；
6. 未首次加载的会话在短 lease 后仍存活，但在硬 TTL 后停止；首次激活后继续遵守短 lease；
7. Review Bridge 的 loopback、Host、Origin、Bearer、路径、方法、revision 与切换隔离测试全部通过；
8. 发布探测把生产状态记录为 `review-session-ready` / `BROWSER_REVIEW_AVAILABLE`，同时保持 `browser_real_host_evidence=false`，直到真实 Codex In-app Browser 打开与保存成功；
9. Skill 明确执行“调用 MCP 准备会话 → 使用 Codex In-app Browser 打开 URL”，不得把 URL 交给系统默认浏览器或聊天 UI。

真实验收还必须在当前 Codex 任务中证明：scoped URL 被 Codex In-app Browser 打开，专业审阅投影读取成功，显式保存一条可撤销测试标记后 Python revision 增长，并清理该测试标记或使用专用验收项目，避免污染真实业务状态。

