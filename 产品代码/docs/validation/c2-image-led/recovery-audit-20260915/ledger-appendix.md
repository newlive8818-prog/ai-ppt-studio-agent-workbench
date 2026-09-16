
## C2 上游故障恢复与独立收口复核补记（2026-09-15，r142）

本段由独立恢复任务 `01a0a2c6-57d7-7670-9b04-9b8d1788351a` 追加，保留以上全部历史。它补充并校准上一段“最终退出核验”的证明边界，不修改 Runtime、G0–G4、用户决定、源码、已接受 PPTX 或旧制品。本轮完成故障定位和独立证据复核；**不宣布 C2 所有退出条件均已满足，也不作可直接合并或发布结论**。

### 故障定位与本次恢复

- “Upstream request failed”实际记录于执行任务 `01a09953-ce03-7ab2-8da2-6dbf6e8012c2` 的三个模型回合：北京时间 2026-09-15 09:16:23、09:16:46、09:17:31；日志类型 `upstream_error`。三个失败回合均未发出工具调用，故这三次失败位于模型采样上游，尚未进入 C2 MCP/Python 业务请求。原始 rollout 行 26696/26702/26709 及单行哈希见[诊断回执](./recovery-audit-20260915/upstream-diagnosis.json)。本地错误未给出 HTTP 状态/提供方内部原因，不能断言账户、限流、上下文、call_id 或 Runtime 损坏是根因。
- 新恢复任务已持续得到模型响应，当前真实 MCP snapshot/status 成功；没有重放失败回合、修改模型配置或上游服务。真实执行任务已 idle/interrupted，委派任务明确停止 Runtime 写入，随后也已 idle/completed；旧 28a9 任务 notLoaded/interrupted。进程快照未见在运行的 Python/C2 renderer 业务写进程。没有获取或抢占 Runtime 写锁，因为本次没有业务写入需要。
- bundled Python 为 `3.12.14 / arm64`。沙箱直接读取 projection 会在原生重放层报 `Exact font unavailable: Microsoft YaHei`；显式加载 PowerPoint 内置字体或用户目录三字体后可以进入渲染，但严格像素比较失败。两组同名字体 bytes 不同，显式字体注册也不等于完整原生宿主字体环境；未安装字体、改字体文件或放宽比较。
- 通过正常执行权限机制在原生宿主中使用同一 bundled Python、同一当前缓存、系统字体发现进行只读复验，`current_authority`、`current_anchors`、`validate_current_g2_evidence`、`VisualReviewService.project` 全部通过。结论是当前三页和 projection 在该具体宿主环境可重放，**不推广为沙箱/任意字体环境均通过**。成功见[原生宿主回执](./recovery-audit-20260915/runtime-replay-native-host.json)；失败见[PowerPoint 字体沙箱回执](./recovery-audit-20260915/runtime-replay.json)、[用户字体沙箱回执](./recovery-audit-20260915/runtime-replay-user-fonts.json)。

### 当前权威状态和证据

- Runtime 始终 r142；G0/G1/G2/G3=`passed`，G4=`open`；`agent/task/active` 不存在。G4/整套交付依主计划 §5 属于 C3，本轮不推进。
- state SHA256=`e7b2042c0a279084540a449fb272054905104f606bf345ebb6d64655e5729e2d`。原生宿主复验前后 378 个 kernel/artifact 文件汇总 SHA256 同为 `965badcd3a60cf2121022b2a5e58a38a5028fa0a6f964508d592ec40397cdfd6`。20 个当前构建文件逐一匹配其登记哈希。
- 当前 `native-anchors.pptx` SHA256=`bc8df49178b1ae9e3831caf6a81bab5bfaa2c029aff056291d60bfc1421be5e5`；build-result、anchors、G2 macOS PowerPoint 证据相互绑定。
- G2 审美 ref=`artifact://visual-review-record/c7e1ea98f34dbda9464ff4cd7199e587868597a996f80cd51295314123e29940`；工程 ref=`artifact://visual-review-record/6cd143ca1e7af971c2c39cb012a2216cce9761d911d3f7b1e5913a3ae40f2159`；两者 `overall_result=passed`，其中 reference-implementation 层历史失败/风险仍原样保留。
- ReleaseTargetPolicy ref=`artifact://release-target-policy/ca4a2a3af0c13f4366aeb6f039c8064abe6fbbae570a31d65f11e57e329dd250`；仅 `macos-powerpoint` 必需，另外三目标 deferred。当前 G2 target ref=`artifact://target-render-evidence/f40655d95a7d4843b4f3a483450097eba4328fe117356eb4da6aeb15dfdc9515`，三页检查与同一 PPTX hash 通过。本次读验已有目标凭据，没有新增 PowerPoint 桌面操作，不将 G2 凭据移作 G4。
- G3 已于 r140 记录，ref=`artifact://g3-confirmation/0f24ca092952ebe5bd136cf5db8568a3390dbae12965e5aa129acba74bbace68`。本次核对 `challenge_revision=139`、7 项证据均仍为 current heads，并在原始会话核到紧邻审核说明后的用户消息 `msg_01a09f7d-1a86-7e81-903c-1633d735368f`（“接受 达到要求”）。不再次确认或消费消息。
- 当前 session ref=`artifact://review-session/97a43efae40012678b76c62c15f7316e4cf2addb7b5b1496e537d0ea6051d802`；逻辑 ID=`visual-professional-c24c85b250a883d18ae0`。源 revision=132、authoritative revision=142；projection 返回 3 anchors + 3 slide contracts，`review_status.G3=passed`。session 仍 `opened/saved`、notification=`not-requested`、AI receipt=`pending`、submitted_at=null。host-open 为已有真实回执，本轮没有重新导航或新增打开回执。

### 独立规格/工程复核与 AC01–AC10 校准

本轮已分别完成[独立规格复核](./recovery-audit-20260915/c2-spec-review.md)和[独立工程证据复核](./recovery-audit-20260915/c2-engineering-review.md)。这是当前证据及退出声明的独立审查，发现未关闭 Important；不能把本轮两份回执冒充“精确冻结提交的完整 C2 双审已通过”。

| AC | 本轮可采纳状态 | 当前证据与边界 |
|---|---|---|
| IL02-AC01 | NotEstablished-final-candidate | 执行端 v2.14 基线和基本职责可查，但与根 quarantine v2.2、最终可解析提交/树及完整被测候选的衔接未闭合。 |
| IL02-AC02 | Passed-current-three-slides | 当前正式三页 G0→G1→G2→G3 已成立；本次原生宿主独立重放成功。 |
| IL02-AC03 | Passed-engineering-boundary | 当前 artifact/hash 身份成立，已有拒绝负例及已核验测试可采信；不扩大为所有环境/最终候选全链完成。 |
| IL02-AC04 | Passed-engineering-boundary | 既有内容/对象/关系/材料负例与本次当前文件身份复核；无新产品修改。 |
| IL02-AC05 | Passed-engineering-boundary | 当前计划、结果与文件哈希一致；当前原生宿主严格重放通过，历史诊断文件失败保留。 |
| IL02-AC06 | NotEstablished | 同 renderer 异内容双组合成证据存在，但两组原始 PPTX 临时路径已不存在；第二组正式 action/context/contract/plan/handoff/result 链未建立。 |
| IL02-AC07 | Passed-current-lineage | 当前 G2/G3及精确依赖已独立重放；不等于 Review Bridge 提交→通知→AI回执或任意宿主泛化已通过。 |
| IL02-AC08 | Passed-engineering-boundary | 原有 legacy/不自动升级回归可采信；本轮未原地迁移真实旧项目。 |
| IL02-AC09 | Passed-observed-tests; final-candidate-binding incomplete | 原始工具回执确证 Python1014、Node249、Widget770、typecheck/build成功；包3772文件重算匹配，145项可映射源码匹配。完整最终测试输入快照/可解析候选绑定仍未闭合。 |
| IL02-AC10 | NotEstablished | 用户接受已成立；Git对象损坏、未关闭Important及同一冻结候选整体双审/总控集成结论仍阻断正式退出。 |

原始测试并非本任务重新运行：独立工程报告固定原始 rollout 行号与单行哈希。候选包 manifest=`81d342cc20dd78bcbf9a87dcbc9306ce719226f4844ad309492eaf09a611443b`，当前缓存 manifest=`9dc42870cfd2ea535bdad2869f9a4071fa12b8a6f27b1ba5ae6a2a4d2e304804`。二者各自3772文件自洽，当前缓存缺候选/源码中的 `cancel_unstarted_native_task` 方法；该恢复方法也未见正式MCP动作。不能声称最新候选完整加载到当前宿主。

### 残余问题、最小后续动作

1. **状态投影缺陷（Important）：** G3 passed 后仍返回“需要你处理/完成视觉审核”。`project_status_projection.py` 只对 G0通过跳过内容审核，未对G3通过跳过旧opened视觉session。本次纯读复现，不修改session来掩盖问题，不要求用户重复G3。应在恢复可验证候选身份后修复该投影及其服务级回归。
2. **候选身份和Git（Important）：** 28a9 HEAD 引用为 `7572d2bbdae5b9b6f0f24d024b07758491623826`，但直接CLT Git `cat-file -t HEAD`失败，`status`报bad tree object HEAD；这独立于/usr/bin/git的xcrun架构问题。先保全可读源码、基线、测试及已核验包，做有界Git/来源恢复；禁止由引用字符串推断提交对象完整，不在本轮重写Git。
3. **正式入口泛化（Important）：** 为第二组不同内容保留完整正式入口、输入、依赖、输出和原始文件证明；历史renderer合成记录不能单独关闭AC06。
4. **历史边界继续保留：** 旧 `179790...` 严格重放失败、S05两处fill provenance差异及空accepted_deviations、三页密度/阅读距离风险、Review Bridge路由与反馈通知/AI回执边界均不改写。当前 `bc8df...` 原生重放成功和后续真实G3整体接受作为新事实分层记录。
5. **下一检查点：** 来源保全/恢复→统一最终候选、缓存与测试身份→修复状态投影并补正式入口双组证明→同一冻结候选必要复验与整体规格/工程双审→总控集成判断。无需再次请求G3；不触发G4或C3。

本次实际变更仅为诊断回执、独立审查回执及本台账追加；Runtime和已接受成果零业务写入。当前可以提交总控审查问题与恢复方案，**尚不满足AC01/AC06/AC10完整退出条件**。
