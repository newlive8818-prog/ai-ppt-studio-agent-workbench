# AI PPT Studio v1.6 最终验收状态

**最近复核：** 2026-08-13
**提交状态：** 用户已明确授权在 37/104 状态提交一个阶段性版本；该提交不代表最终验收通过
**严格台账：** 37/104 passed，67/104 unproven
**总体结论：** P0 MissionConfirmation 死锁修复和 Browser 两段式交接已实现并安装；真实 Codex 内置 Browser 已证明 scoped URL 打开、权威投影读取与标记保存。真实侧边栏、真实宿主原生任务确认、真实项目完整重跑及当前发布策略下的完整桌面证据仍未完成，因此产品尚未达到最终验收，严格台账暂不重算。

## 2026-08-13 发布目标范围变更

用户批准 v1.6 当前发布目标仅为 macOS Microsoft PowerPoint；`macos-wps`、`windows-powerpoint` 与 `windows-wps` 延期，不作为当前 G2/G4 阻断项，也不构成通过、失败、不支持或兼容声明。系统继续保留四个 supported profile；当前项目绑定的 `ReleaseTargetPolicy.required_target_ids` 是 Gate 必需目标的唯一来源，Agent 无权按项目临时缩减或扩大。

本次只重建 104 个稳定 requirement 的文本与 proof contract，不删除 requirement、不减少分母，也不把策略专项自动化或已有 G2 macOS PowerPoint 记录提前登记为整产品通过证据。在 Task 10 以新策略重新验证真实项目、策略 lineage 和正式桌面记录前，旧 `37/104` 数字保持不变，G2 仍不得声明已在新策略下通过。

## 2026-08-13 真实项目策略迁移与 G0 历史凭据阻断

- 真实验收项目 `/Users/defei/Documents/AI-PPT-Workspace/projects/v16-final-real-acceptance-proposal-only` 已通过正式 revision-safe 命令从 revision 56 迁移到 57，并绑定 `artifact://release-target-policy/a94b558e67d011626ce0364428075a91d16e6b8084fa97749365c2e56a6794e5`。当前 required 仅为 `macos-powerpoint`；其余三个 profile 保持 deferred，未创建 WPS/Windows 证据。
- 已重新计算锚点 PPTX、PowerPoint PDF 和三张逐页 PNG 的文件哈希，分别与已入库的 immutable artifact graph 完全一致。当前 PPTX SHA-256 为 `1aa97f42c41adc0cf9f6eb4f989d88586598f8cf9cc0d9c7c510459e54e07de3`；PowerPoint 16.112、macOS 26.5.2 的正式记录保持 `simulation=false`、`proof_eligible=true`、`overall_result=passed`。导入前临时 `evidence-package.json` 未保留在外部验收目录，因此不能重新运行目录导入 verifier；这不等于已入库证据内容失败，也不应伪造或重生成原始包。
- 使用 revision 57 和七个精确授权 refs 调用正式 G2 evaluator 时，运行时以 `current-G0-confirmation-lineage-stale` 拒绝；项目未写入。根因是 revision 34 的真实 G0 确认采用可信宿主断言引入前旧格式，而当前内容 acceptance/blueprint 引用并未漂移。
- 已新增受限 `legacy-credential-upgrade`：只有旧 G0 确认冻结的 acceptance/blueprint 仍精确等于当前 heads，且凭据严格属于旧格式时，才允许当前宿主针对当前 revision 和 sourceVersion 重新确认。成功只替换 G0 确认凭据，保持 G1/G2 状态和全部视觉 heads；任何 lineage 漂移都拒绝，旧消息字符串本身永不被升级为可信凭据。相关全量 Python 回归为 179/179。
- 新 release 已构建、验证并安装；manifest SHA-256 为 `2bf46591c92fb9a898faef13580077b51e641ef93d2bfbf2d21fb95e148f04b2`，磁盘 manifest 版本为 `0.4.0+codex.20260813101041`，release probe 为 18 个工具、0 个聊天 UI template。当前任务已加载的旧 17-tool stdio 进程没有热更新，仍在确认调用前尝试 `/usr/bin/python3` 并返回 `ENOENT`；因此没有形成真实宿主原生确认，也没有进行 G0 凭据升级。
- 截止本次记录，真实项目仍为 revision 57：`G0 passed / G1 passed / G2 open / G3 locked / G4 locked`。不得声明 G2 已在新策略下通过；严格台账仍为 37/104。

## 已完成且可复现

- 已把自动确认任务书纠正为 `MissionDraft -> MissionConfirmation`：字段齐全只到 `confirmable`，无当前真实用户确认凭据时 Python 服务拒绝正式内容任务和内容制品提交。
- 已修复生产启动路径在没有注入 `confirmationVerifier` 时的死锁：`OK / 确认 / 采纳 / 继续` 及明确同义表达只在当前完整 `confirmable` 任务卡且确认是唯一待处理高影响动作时触发宿主原生确认；只有宿主 `accept` 且 `confirmed=true` 才调用 Python。短词不进入可信引用，普通讨论不误确认。
- 原生确认摘要固定再次显示主题、汇报对象、期望判断/行动和材料摘要；无材料任务再次显示 proposal-only 身份。`decline`、`cancel`、`confirmed=false`、宿主能力不可用和 verifier 拒绝均零业务写入并保留当前 revision。
- 用户确认无材料后进入 `proposal-only`；诊断假设、方案建议、待联合验证身份由 Python 内容合同强制，虚构客户事实、数字、案例、能力、结果或承诺会硬失败。
- 普通 MCP 工具保持纯数据结果，发布包中聊天 UI template 数为 0；真实侧边栏缺失时返回 `HOST_SIDEBAR_UNAVAILABLE`。Browser 审阅改为两段式交接：MCP 建立 loopback Review Bridge 并返回 `review-session-ready` scoped URL，Agent 使用 Codex 内置 Browser 打开；缺少 MCP 进程内函数级适配器不再误报宿主缺少 Browser，且不回退聊天 Widget。
- 真实 Codex In-app Browser 已打开 20 页内容审阅：HTML shell 正常执行，URL fragment 令牌在 bootstrap 后移除，Bearer `GET /api/review` 读取 Python 权威投影成功，项目名、精确 sourceVersion、目录、正文、标记和保存控件均呈现。
- 已从 Codex 实际缓存的 `0.4.0+codex.20260812185044` 启动新鲜 scoped 会话，在真实 Browser 添加并显式保存一条临时标记，页面显示“所有标记已保存”，权威 revision 从 36 变为 37。随后仅在 revision 37 且唯一标记精确匹配测试文本时，通过同一权威 Kernel 事务提交空 `ReviewMarkSet`；最终 revision 38、`marks=[]`、status `draft`，content sourceVersion 保持不变。没有残留测试批注。
- 专业审阅 Header 保留内容/视觉双切换；跨类型切换由同源、Bearer 鉴权的 Review Bridge 从 Python 权威投影解析目标版本并换发新的单类型短时会话，未保存标记会阻断切换。
- 2026-08-13 新鲜完整回归为 Python 136/136、Node 35/35、Widget 40/40；Node 结果包括 9 个 Review Bridge loopback 安全/生命周期用例，以及宿主原生确认 accept、decline、cancel、`confirmed=false`、能力不可用和 verifier 兼容/拒绝路径。UI 自动化覆盖 360/420/480px 侧边栏投影、760/1000/1440px、100%/200% 与 60/120 页长文档，并新增侧边栏 handoff 诚实状态和 Browser 保存会话过期恢复。
- 官方 Skill validator、Plugin validator、确定性 release/install/recovery 均通过。
- 已发布、原子安装并由 Codex marketplace 刷新为 `0.4.0+codex.20260812185044`；release manifest SHA-256 为 `247331215b93ce0e2ff9e66c0d1dbef38b6c0c3687bddd249d7f142a3e460953`。安装源与 Codex 实际缓存均通过官方插件结构校验和 release 清单复验；缓存对现有受管项目的生产 stdio 探测提供 17 个纯数据工具、0 个聊天 UI template，并返回 `status=review-session-ready`、`openMode=agent-browser`。

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
| `target-evidence` | 15 | 尚缺在当前发布策略下重新绑定并逐项登记的 macOS Microsoft PowerPoint G2/G4 同哈希实机记录；延期 profile 不计入当前 Gate，也不声明兼容 |
| `automated-test` | 13 | 对应端到端要求仍没有覆盖全部真实条件的自动化证明 |
| `viewport-evidence` | 11 | 仍需真实 Codex 宿主视口而非本地 Chromium 投影 |

全部 27 条系统端到端要求都要求真实项目证据，所以当前 SDD 21.3 仍为 0/27 passed。当前 37 条通过项只证明已映射的合同、运行时和本地视口行为，不证明真实侧边栏、Browser、用户确认、PPTX 或桌面软件通过。

## 仍存在的真实宿主证据缺口

- 当前任务已加载 17 个新版纯数据 MCP 工具并可调用 `confirm_ai_ppt_mission` 与 `open_ai_ppt_browser_review`；新 cachebuster `0.4.0+codex.20260812185044` 已进入 Codex 实际缓存。已存在的工具进程是否热切换到最新缓存不能仅由安装动作证明，后续宿主实机验收应以工具元数据和版本现场复核为准。
- 真实 Codex 内置 Browser 打开、读取与保存已证明；真实侧边栏仍为 `HOST_SIDEBAR_UNAVAILABLE`。
- 自动化和安装探测已经证明 host-native fallback 合同存在，但没有显示真实 Codex 原生确认弹窗；因此仍不能安全制造真实 `MissionConfirmation`、侧边栏截图或宿主确认消息引用。

## 真实项目保持只读

项目：`/Users/defei/Documents/AI-PPT-Workspace/projects/v16-真实售前验收-经营一体化方案`

- 当前 revision：51；Gate 为历史 `G0 passed / G1 passed / G2 open / G3 locked / G4 locked`。
- 没有当前合同要求的 `mission/draft` 或 `mission/confirmation`；旧 `mission` / `mission-brief` 与旧 G0 只作历史输入。
- 唯一 PPTX 仍为 `acceptance/g2/native-anchor-r42/经营一体化解决方案-G2-原生锚点-r42.pptx`，SHA-256 为 `4bdc25debb335521540e0e390f920c4cffb97c41f70cf12a0a394976c8d5c511`。
- 当前纠偏未改 revision 51、未恢复 G0/G2、未修改 PPTX、未登记伪造的侧边栏、Browser、用户确认或桌面目标证据。

## 对当前使用的影响

底层 schema 3 项目、合同校验、版本恢复、纯数据 MCP 和已存在历史 PPTX 不因验收继续而被破坏。此前“无材料可继续但无法取得 MissionConfirmation”的代码死锁已经修复；Browser 打开、读取和保存链也已取得真实 Codex 证据。真实侧边栏、原生确认、真实项目完整链和当前策略所需的 G2/G4 macOS PowerPoint 证据映射仍未闭合；在这些台账补齐前不能声明完整可用或最终验收通过，也不能声明 WPS/Windows 兼容。

## 继续顺序

1. 让 Codex 为当前任务重新启动已安装的 `0.4.0+codex.20260813101041` 插件 stdio 进程，并现场确认工具表包含 `set_ai_ppt_release_target_policy` 且总数为 18；仅磁盘安装或 cachebuster 不能代替进程现场证据。
2. 对 revision 57 的当前 G0 `legacy-credential-upgrade` challenge 执行一次真实宿主原生确认；接受后应只产生 revision 58 的凭据升级事件，保持 G1 passed、G2 open 和全部视觉 heads 不变。拒绝、取消或能力不可用必须保持 revision 57。
3. 在 revision 58 重新提交七个精确授权 refs；只有正式 evaluator 通过后才声明 G2 passed。随后发布当前视觉合同到 Browser 专业审阅，验证其只显示 macOS PowerPoint required 与三项 deferred，不显示 WPS/Windows/cross-platform 通过。
4. 获取用户对当前视觉合同的真实 G3 确认；在此之前不得构建完整 12 页。G3 后仅使用 Codex Presentations 执行严格路线 B，本次不使用 Image 2。
5. 为最终 PPTX 取得一份全新的 macOS PowerPoint G4 正式记录；不得复用 G2 锚点记录，也不创建 WPS/Windows 伪证据。
6. 完成聊天文件发送与 G4，再进行 privacy-safe proof mapping 和严格台账重算；真实侧边栏仍须单独取得宿主证据。最终完成版本仍须达到 104/104。
