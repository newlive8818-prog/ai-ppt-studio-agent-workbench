# AI PPT Studio v1.6 最终验收状态

**最近复核：** 2026-08-13
**提交状态：** 用户已明确授权在 37/104 状态提交一个阶段性版本；该提交不代表最终验收通过
**严格台账：** 37/104 passed，67/104 unproven
**总体结论：** P0 MissionConfirmation 死锁修复、纠偏实现、本地回归、确定性发布与安装已经完成，但产品尚未达到最终验收；真实 Codex 侧边栏、Codex 内置 Browser 打开/保存、真实宿主原生任务确认、真实项目重跑及四目标同哈希桌面证据均不可由本地测试替代。

## 已完成且可复现

- 已把自动确认任务书纠正为 `MissionDraft -> MissionConfirmation`：字段齐全只到 `confirmable`，无当前真实用户确认凭据时 Python 服务拒绝正式内容任务和内容制品提交。
- 已修复生产启动路径在没有注入 `confirmationVerifier` 时的死锁：`OK / 确认 / 采纳 / 继续` 及明确同义表达只在当前完整 `confirmable` 任务卡且确认是唯一待处理高影响动作时触发宿主原生确认；只有宿主 `accept` 且 `confirmed=true` 才调用 Python。短词不进入可信引用，普通讨论不误确认。
- 原生确认摘要固定再次显示主题、汇报对象、期望判断/行动和材料摘要；无材料任务再次显示 proposal-only 身份。`decline`、`cancel`、`confirmed=false`、宿主能力不可用和 verifier 拒绝均零业务写入并保留当前 revision。
- 用户确认无材料后进入 `proposal-only`；诊断假设、方案建议、待联合验证身份由 Python 内容合同强制，虚构客户事实、数字、案例、能力、结果或承诺会硬失败。
- 普通 MCP 工具已改为纯数据结果，发布包中聊天 UI template 数为 0；真实侧边栏或 Browser 能力缺失时分别返回 `HOST_SIDEBAR_UNAVAILABLE` / `BROWSER_REVIEW_UNAVAILABLE`，不回退聊天 Widget。
- 专业审阅 Header 保留内容/视觉双切换；跨类型切换由同源、Bearer 鉴权的 Review Bridge 从 Python 权威投影解析目标版本并换发新的单类型短时会话，未保存标记会阻断切换。
- 2026-08-13 新鲜完整回归为 Python 136/136、Node 32/32、Widget 38/38；Node 结果包括 7 个 Review Bridge loopback 安全用例，以及宿主原生确认 accept、decline、cancel、`confirmed=false`、能力不可用和 verifier 兼容/拒绝路径。既有 UI 15 个场景覆盖 360/420/480px 侧边栏投影、760/1000/1440px、100%/200% 与 60/120 页长文档。
- 官方 Skill validator、Plugin validator、确定性 release/install/recovery 均通过。
- 已安装并启用插件版本 `0.4.0+codex.20260813010800`；安装 manifest SHA-256 为 `bc7d9d1edda247a3b789397f33c269ad6944ff95d8f39cf7dd84df00d4baadea`，安装源与 Codex 缓存中的 MCP server/Skill 哈希一致。安装缓存现场探测提供 17 个纯数据工具、0 个聊天 UI template，且 `host_native_fallback=true`、`mission_summary_exposed=true`。

对应结构化证据：

- [`2026-08-12-corrected-automated-regression.json`](../../requirements/evidence/2026-08-12-corrected-automated-regression.json)
- [`2026-08-12-corrected-contract-runtime.json`](../../requirements/evidence/2026-08-12-corrected-contract-runtime.json)
- [`2026-08-12-corrected-runtime-install.json`](../../requirements/evidence/2026-08-12-corrected-runtime-install.json)
- [`2026-08-12-corrected-browser-viewport.json`](../../requirements/evidence/2026-08-12-corrected-browser-viewport.json)

## 当前 67 项未证明证据缺口

缺失证据种类按台账计数如下；同一 requirement 可同时缺多种证据，因此数字会重叠：

| 缺失证据 | 条目数 | 含义 |
|---|---:|---|
| `real-project` | 42 | 尚未以当前 MissionConfirmation 与 proposal-only 合同重跑真实售前项目 |
| `runtime-evidence` | 34 | 尚缺真实宿主、真实项目或真实交付运行证据 |
| `target-evidence` | 15 | 尚缺 macOS/Windows 上 PowerPoint/WPS 四目标同哈希实机记录 |
| `automated-test` | 13 | 对应端到端要求仍没有覆盖全部真实条件的自动化证明 |
| `viewport-evidence` | 11 | 仍需真实 Codex 宿主视口而非本地 Chromium 投影 |

全部 27 条系统端到端要求都要求真实项目证据，所以当前 SDD 21.3 仍为 0/27 passed。当前 37 条通过项只证明已映射的合同、运行时和本地视口行为，不证明真实侧边栏、Browser、用户确认、PPTX 或桌面软件通过。

## 真实宿主阻塞

- 当前任务启动时加载的仍是旧版 MCP Schema，工具元数据继续暴露旧 `render_ai_ppt_workbench` / `render_ai_ppt_review`，且不存在新版 `confirm_ai_ppt_mission`；已安装的新插件能力需要新 Codex 任务重新加载后才能真实验收。
- 新插件当前诚实探测为 `HOST_SIDEBAR_UNAVAILABLE` 和 `BROWSER_REVIEW_UNAVAILABLE`。本地 React/Chromium 通过不能证明 Codex 真实侧边栏或内置 Browser。
- 自动化和安装探测已经证明 host-native fallback 合同存在，但没有显示真实 Codex 原生确认弹窗；因此本任务不能安全制造真实 `MissionConfirmation`、侧边栏截图、Browser 打开/保存证据或宿主消息引用。

## 真实项目保持只读

项目：`/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案`

- 当前 revision：51；Gate 为历史 `G0 passed / G1 passed / G2 open / G3 locked / G4 locked`。
- 没有当前合同要求的 `mission/draft` 或 `mission/confirmation`；旧 `mission` / `mission-brief` 与旧 G0 只作历史输入。
- 唯一 PPTX 仍为 `acceptance/g2/native-anchor-r42/经营一体化解决方案-G2-原生锚点-r42.pptx`，SHA-256 为 `4bdc25debb335521540e0e390f920c4cffb97c41f70cf12a0a394976c8d5c511`。
- 当前纠偏未改 revision 51、未恢复 G0/G2、未修改 PPTX、未登记伪造的侧边栏、Browser、用户确认或桌面目标证据。

## 对当前使用的影响

底层 schema 3 项目、合同校验、版本恢复、纯数据 MCP 和已存在历史 PPTX 不因验收继续而被破坏；验收过程本身保持真实项目和 PPTX 只读。此前“无材料可继续但无法取得 MissionConfirmation”的代码死锁已经修复并安装，待新任务真实弹窗验证；当前任务仍受旧 MCP 生命周期影响。真实侧边栏和内置 Browser 入口也尚未证明可用。因此可以继续做只读查看、合同/测试开发和历史产物使用；新任务若成功加载原生确认可继续正式内容链，但在真实宿主和台账补齐前仍不能声明完整可用或最终验收通过。

## 继续顺序

1. 新建 Codex 任务并确认加载 `0.4.0+codex.20260813010800`；完整展示当前 `confirmable` 任务卡后分别验证 `OK / 确认 / 采纳 / 继续` 会触发 Codex 原生确认，而普通讨论不会误触发。
2. 验证原生确认接受后生成当前 `MissionConfirmation`；验证拒绝/取消后 revision 不变，再验证真实侧边栏、内置 Browser 打开/保存与内容/视觉切换。
3. 在新的真实验收链中按 proposal-only 重跑内容治理与 G0，再生成完整视觉合同与 G1。
4. 仅使用 Codex Presentations 执行严格路线 B；本次不使用 Image 2。
5. 对同一锚点 PPTX 和最终 PPTX 分别取得 macOS PowerPoint、macOS WPS、Windows PowerPoint、Windows WPS 四目标同哈希实机证据。
6. 完成 G3、完整成稿、聊天文件发送与 G4，再重算台账；本次 37/104 阶段性版本已经用户明确授权提交，最终完成版本仍须达到 104/104。
