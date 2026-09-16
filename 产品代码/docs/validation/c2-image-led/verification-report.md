# CHG-IL-C2 唯一执行记录

最新状态（2026-09-11 工程收尾）：**指定三页 PPTX 的用户验收已通过；原 b8e788f 窄差异独审已完成，证据补正待总控核定，C2 整体退出尚未成立。** 验收绑定 `1797900779255f539f659f806b9ae140b7490fbd5b245675f844ccb36096e2a6` 与旧区域清单 `2283dfe…`，不转授当前 `176423…`；实读 Runtime r107 / G0 passed / G1 open / G2–G4 locked。最终 Python 1011、Node 220、Widget 770、类型/构建和封存包验证通过；正式视觉链、PowerPoint、严格保存预览重放、同候选独审与集成仍有未闭合项。详见文末“C2 工程收尾与三页用户验收归档”。以下其余章节保留各自历史时点语义，不覆盖本次真实用户决定。

历史归档状态（2026-09-11，当时截止为客户 revision **46**）：**`real-host-passed-r46-inputs-registered-generation-blocked-by-client-auto-review`**。候选 `0.4.0+codex.c2.edb1284.20260910` 已由总控安装、重启并取得真实宿主本地协议 PASS；包继续绑定源码 `edb12848bad7b34cb0eb05c6a9b79097cf86422b`。92 项 scope 已登记于 r41，原生确认调用成功返回 r42 grant，正式 policy 与三页 packs 已登记至 r46。三页真实认可和 Batch submitted 保持，G0=`passed`、G1=`open`、G2–G4=`locked`。首张正式生图请求在工具执行前被客户端 auto-review 拒绝；现有 Runtime grant/policy/packs 未撤销，尚无生成队列、任务、请求或图像结果。历史消息 verifier 缺口仍保留，但本次范围已有实际原生确认 grant；当前外发阻断来自客户端审批层对精确敏感 payload/CRS 目的地的可信直接用户批准认定。总控承接该确切范围的说明和用户答复，本任务不重试、recover 或换接口。r40 的 111 文件未变证据仅覆盖登记前的安装/重启/预检；当前 r46 为 125 文件，不沿用此前整树未变结论。详见文末“真实宿主与 r46 登记/外发截止记录”，以下历史状态均保留其原时点语义。

## 开工回执

- change_id: `CHG-IL-C2`
- task_id: `01a084ee-d69d-7192-bc1b-0f7a1e64bfa9`
- cwd: `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app`
- branch: `codex/image-led-native-anchors`
- base_commit / initial HEAD: `0283b0d882b9838d58dd43c7b217e604d9b4f6d2`
- git-dir: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/.git/worktrees/PPT-codex-app8`
- common-dir: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/.git`
- clean_status: tracked clean; fork 携入两份 untracked 总控记录 `docs/validation/c2-dispatch/dispatch-prompt.md`、`dispatch-receipt.json`。原样保留，不作为 C2 进度事实。
- Runtime 根: `/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909`，接管检查不存在；尚未创建。测试使用临时根。
- first_action: 真实 Git 隔离/基线检查、创建已授权命名分支、依序读取四基线、交接包校验，随后审查现有入口与技术规格。
- 交接 manifest: SHA256 `d90b850724c7d1b09e4c0630cfc0454bfb8b39c83e0719074e2cac79a0297223`，17 成员全部 hash 匹配。
- C1 核心 manifest: SHA256 `8e6c94beb74dff8c89d83752b898c3d454b807b65bc6764dbc80a020ad9f60f3` 匹配；本次未重跑其固定包，不继承其 Gate/用户接受。
- 候选实现提交：`91ae801a36ad2af4c4d144b1574adb040b41be33`。
- 旧候选 E1 仅建立选择、纯域合同和独立 renderer，Runtime 集成未完成；E2 已运行的适用回归通过，另有 Node skip 与构建环境阻断；E3 两组三页 synthetic renderer 已实跑；E4 当前 PowerPoint、E5 用户视觉/G3、真实 C2 Runtime/G0/Image 2/客户材料验收仍未建立。
- 旧定向 Review 只覆盖其子范围；总控对精确候选复核发现 3 个 Important Runtime 流程断点，现已返回原 Change 修复，不能进入合并准备。
- 开工计时: 本任务执行回合开始 `2026-09-09T07:05:36+00:00`（原生 read_thread startedAt 1788937536）；此前 fork 等待不计为主动执行。首次回执前读取与工具区间可查本任务原始工具记录；不把 wall-clock 当作主动计算时长。

## 执行范围与事实边界

按主计划 §5 / §12.2 自主实施 IL02-T01～T05，技术 schema 在已批准目标内选择；不重开重复授权。C1 原件只读、历史 AC03/AC07 原样。总控候选合并、Push、安装、发布、C3 未执行。真实用户/G0/G3/宿主回执不由测试代签。

## 历史审查状态（c9e0137）：candidate-ready-for-controller-review

最终代码候选：`c9e01379821b2e1b3f79a3e9a1239489c6270532`。G-01、G-02 及独立审查发现的保留 ID 问题已完成工程修复和作者隔离关闭复核：**Critical=0 / Important=0 / Minor=0**。等待总控对固定候选复核；这不是合并、发布或真实 C2 验收。

总控固定审查绑定代码 `ba7efa760c93bf423ed4f932ea8d2c54fa16f157`、文档 HEAD `f87df14c855d1c6a9fc45cdd16662cda86e08c78`。原 3 项 Runtime 集成 Important 保留 **CLOSED**；旧候选全量 Python **703/703**、Node **149/149**、Widget **755/755（16 文件）** 与 tsc/build 通过的事实保持有效，不能概括为旧工作全部失败。新增 G-01/G-02 经总控独立复现，退回原 Change/分支/Worktree 修复；以下历史“无未关闭 Important”仅适用于当时已审范围。

- 固定总控审查：[controller-review.md](/private/tmp/c2-controller-ba7efa7-review/controller-review.md)；12 项证据 hash 清单：[controller-evidence-manifest.json](/private/tmp/c2-controller-ba7efa7-review/controller-evidence-manifest.json)。
- 原三断点关闭：[closure-review.md](/private/tmp/c2-ba7efa7-closure-rpalqr/closure-review.md)。
- 新增生图专项：[generation review](/private/tmp/c2-generation-ba7efa7-review.md) 与 [JSON](/private/tmp/c2-generation-ba7efa7-review.json)。G-01：公开 unknown 恢复仅刷新 revision 造成第二次 adapter 调用；G-02：外部返回期间无关 revision 更新使成功响应未保存。
- 本轮分工：主执行负责请求身份与 claim 级返回持久化；`trusted_confirmation` 固化真实 bridge 并发/撤销反例；`visual_spec_review` 固化默认公开 MCP 的恢复/明确新设计反例；`materials_review` 保留作者隔离独立审查身份。
- 当前修复的专项、全量工程回归和固定提交独立 Review 已通过，待总控复核；不自动合并、Push、发布或启动 C3；真实客户/provider/PowerPoint/G3 保持未建立。

### G-01/G-02 修复执行证据

- 总控证据清单 12/12 实际 SHA256 已核对匹配：`/private/tmp/c2-generation-controller-evidence-check.json`。
- G-01 持久 RED：新增 `tests/image-led-generation-recovery.test.mjs` 通过默认 MCP→真实 Python bridge→synthetic command adapter，仅刷新 revision 时实际 `adapter_calls=2`、两个 request ID；`/private/tmp/c2-g01-mcp-recovery-red.log`。随后七场景均在旧代码精确副本 RED，`/private/tmp/c2-g01-mcp-recovery-seven-red.log`。先前共享依赖读取超时记为环境问题，不计行为 RED。
- G-02 持久 RED：新增 `tests/test_image_led_generation_recovery.py`，adapter 等待期间公开普通 decision 成功后释放，原请求仍 `started` 而非 `completed`；`/private/tmp/c2-g02-core-red.log`。首次修复 GREEN 为 `/private/tmp/c2-g02-core-green.log`。
- G-01 实现：稳定默认请求身份与显式 `new/recover` 接入既有 action；同 ID 同输入只读、不同输入拒绝；恢复先读历史，缺 adapter、过期 revision、活动任务变化/撤销/旧 pack 不阻止历史读取。明确新 ID 同 pack 继续沿用已授权 scope。公开工具仍为 43。新 ID 测试曾发现 ContextCompiler 遗留 64 位限制，已限定在生图分支修正，其他任务约束保留。
- G-02 实现：原 request/claim/pack/payload 身份核验，逐次当前 revision CAS 只重试本地保全；完整返回 fingerprint 保护重放，同响应幂等、冲突响应拒绝。只写原历史槽，不恢复旧 active task/业务 heads；`generation_usability` 与响应分开，candidate 仍按当前依赖检查。
- 专项 GREEN：G-01 新增 9 项与既有默认 MCP 2 项共 11/11、0 skip，`/private/tmp/c2-g01-mcp-recovery-green.log`；G-02 9/9，`/private/tmp/c2-g02-cas-concurrency.log`。含 unknown 默认重试/显式新设计/同 ID 并发、无 adapter 历史恢复、无关公开 decision、撤销、公开材料变更、不同请求并发返回、同 claim 相同/冲突返回、连续两次真实 revision 冲突后本地保存、失效 candidate 零写拒绝。
- 全量阶段性 Python 712/712 已通过，但运行中修正了 ContextCompiler，因此重新执行稳定代码全量。首次 quality 的 Node 156/158：一项为 schema 新字段的旧快照摘要未更新，已补准确摘要与字段断言；另一项为验证脚本的 `AI_PPT_PYTHON` 覆盖干扰既有解释器失败测试，已移除该覆盖，不改产品逻辑/原测试。首次日志保留 `/private/tmp/c2-generation-quality-first.log`，最终结果与固定提交 Review 待下文记录。
- 稳定代码最终 Python：**712/712，115.100 秒，exit 0**；`/private/tmp/c2-generation-python-full.log` 与同名 `.json`。`npm run quality`：**exit 0**，TypeScript/build 通过，**Node 158/158、0 skip，Widget 16 文件/755/755**；`/private/tmp/c2-generation-quality-full.log` 与同名 `.json`。临时依赖副本的 373 个非 docs 源码/测试/Skill 文件与工作区 hash 全部匹配，`/private/tmp/c2-generation-quality-source-check.json`；未修改共享依赖或安装插件。
- 四基线及变更/Skill 链接：9 文件、66 个文件链接、6 个原型引用通过，`/private/tmp/c2-generation-links.json`；未把此检查称为 fragment anchor 校验。`git diff --check` 通过。真实 provider/客户/PowerPoint/G3 保持未建立，旧三项 CLOSED 继续有效。
- 首个修复候选 `ec4f8f5b9ec4ddb921a5bbdbd0abdd2e9a16ed3b` 的作者隔离 Review：510 tracked blobs 全匹配，独立 Python 25/25、默认 MCP 11/11 通过，但额外探针发现 G-01 保留 ID `active` 冲突 Important。公开 new(active) 的历史任务槽会与 `agent/task/active` 相撞，之后新任务覆盖该历史槽导致恢复失败。证据 `/private/tmp/c2-g0102-independent-probes.json`；该候选退回本轮修复，不以绿灯覆盖发现。原三个集成 CLOSED 与旧候选通过事实保留。
- ec4 固定独立报告：`/private/tmp/c2-g0102-ec4f8f5-independent-review.md` 与 `.json`，Critical=0 / Important=1 / Minor=0；后续修复不覆盖该历史结论。补修 RED 为 `/private/tmp/c2-active-id-mcp-red.log`（实际 adapter=1 且树改变）及 `/private/tmp/c2-active-id-runtime-red.log`（请求解析/任务创建/context 三入口均未拒绝）。四入口现在一致在写前拒绝保留 ID，不靠事后查找旧任务；普通短 ID 保留。
- 补修专项 GREEN：公开 MCP 新旧 **13/13、0 skip**，`/private/tmp/c2-active-id-mcp-green.log` / `c2-active-id-mcp-verification.json`；Runtime 请求 **10/10**，`/private/tmp/c2-active-id-runtime-green.log`。最终补修 Python 全量 **713/713，233.997 秒，exit 0**，`/private/tmp/c2-active-id-python-full.log` / `.json`。
- 补修并行全量 quality：Node160/160、tsc/build 通过；Widget753/755，两项既有等待测试失败（一项 findByRole 等待图片、一项5000ms timeout）。Widget 源码、测试及超时未改。原失败日志保留 `/private/tmp/c2-active-id-quality-concurrent.log` / `.json`；Python结束后以相同源码和相同质量命令单独重跑，结果待补录，不放宽阈值或跳过。
- 单独重跑又定位到既有 `mcp-runtime-bridge.test.mjs` 默认 `list-projects` 子进程长时间未返回，源码确认其读取宿主默认 Runtime。只停止已核实的本轮测试进程树，日志保留 `/private/tmp/c2-active-id-quality-ambient-stopped.log`；未关闭或改动用户应用。验证脚本改为临时空 Runtime 配置，源码、测试、超时阈值不变。最终 **`npm run quality` exit 0；Node160/160、0 skip；Widget16文件/755/755；tsc/build 通过**，`/private/tmp/c2-active-id-isolated-quality-full.log` / `.json`（含隔离配置路径）。该结果与713/713 Python绑定本次保留ID补修代码；环境异常不抹去历史日志，也不作为产品缺陷已修证明。
- 最终独立关闭复核绑定 **`c9e01379821b2e1b3f79a3e9a1239489c6270532`**，由未参与本轮生产/测试实现的 `/root/materials_review` 完成：[关闭报告](/private/tmp/c2-g0102-c9e0137-independent-closure-review.md) / [结构化证据](/private/tmp/c2-g0102-c9e0137-independent-closure-review.json)。Critical=0 / Important=0 / Minor=0；R-G01-RESERVED-ID、G-01、G-02 在 synthetic 工程范围 **CLOSED**，原三集成问题保持 **CLOSED**。
- 独立复核因全树 archive 读取等待，采用已验证 ec4 精确快照 + c9 的 9 个变动 Git blobs 重建，逐项比对 c9 的510个tracked blob IDs，测试后文件SHA保持不变；未把未完成的archive说成完成。独立Python **26/26**、默认MCP **13/13，0 skip**、额外串行探针 **5/5** 通过，新15项回归证据hash匹配。独立探针含保留ID写前拒绝、短ID重放、真实candidate登记、新任务后无adapter恢复旧图且active不变、错误pack恢复拒绝；G3始终locked。
- 最终补修质量副本中373个非docs源码/测试/Skill文件与候选hash匹配：`/private/tmp/c2-active-id-source-check.json`。17项最终证据清单：`/private/tmp/c2-c9-generation-repair-evidence.json`。本次只形成独立分支上的本地候选，材料真实来源/持续授权、定版图与文案权威、忠实转换及真实用户/PowerPoint Gate 边界保持。

## 历史进度（2026-09-09）

- **2026-09-09 真实材料审计与复杂三页候选**：在已完成工程修复的文档 HEAD `e3aa9bbed1d041d7743f29216f4bd0b2365b81a7` 上继续原 C2 分支/Worktree。用户授权九份真实来源本地阅读、选材及审计，并进一步要求将当前三页替换为 **C2-S04=M03 p12、C2-S05=M01 p25、C2-S06=M03 p18**。当前 `three-page-input-audit.json.pages` 已实际替换，旧 C1-S01/S02/S03 仅保留历史文案/验收对照，不计入新三页。
- 材料附件：[九源审计](../c2-real-material-audit/README.md)、[复杂三页说明](../c2-real-material-audit/complexity-selection.md)、[当前输入审计](../c2-real-material-audit/three-page-input-audit.json)。9 原件全部实际读取，4 PPTX ZIP CRC 通过，实际 177 页/493 媒体；逐页 XML、源文案、媒体/裁切身份及用途分开绑定。两份 MD 的 4 个确切切片保留原始 CRLF/LF，11 裁切只做本地候选；已无效的 20260731 文件不在读取清单。
- 新三页分别保留统一入口/四业务域/能力引擎/底座、数据中台四层与多源关系、MES/WMS 指令到设备执行与状态回传。用户给定的三页 XML hash 均与原件匹配；`current_confirmed_copy` 和 `current_selected_image_sha256` 为 null，精确源文案及 page_goal/common_rules 为审计候选，没有伪造新 G0/选稿。M03 p18 `image106.jpeg`（`0c19e88a…`）为装配线却标注仓储，按完整 hash 排除；image88/image90 仅作可选工业实物。M04 p21 成效页退为备选，量化效果与 40 场景/17 覆盖不混写。
- 本轮只增加审计文档、只读来源检查脚本及证据，**生产代码仍等于 `c9e01379821b2e1b3f79a3e9a1239489c6270532`**。本地原页渲染检查不等于 Image 2 生成或原生忠实转换；没有真实 Runtime/Gate 写入、Image 2 调用、来源修改、合并、Push、安装、发布或 C3。具体复核结果与文件散列见材料附件的验证和独立审查回执；既有工程测试与关闭状态保留，不把文档审计说成新一轮全量代码验证。

- IL02-T01: 已完成；规格与文档切片提交 `b53f201`，材料与视觉两路独立定向复核无未关闭 Critical/Important。
- IL02-T02: 候选工程实现已接入生产执行；默认 MCP→Python bridge→宿主 command adapter→确切图片响应已有 synthetic 子进程正例。材料复用、持续授权、未知请求不盲发保持；真实 provider 尚未配置/验证。
- IL02-T03: 本轮已接通 selection→regions 正式登记及独立审查、完整合同/独立版本计划原子发布、正式 action handoff 与 SDK 实物结果接入。当前证据为真实生产入口与 synthetic 内容/决定，不能称真实客户转换验收。
- IL02-T04: 本轮已接通结果→独立四维 Review→受控 anchors→现有 G2/ReviewSession/投影；补齐替换失效与定版文案投影。真实 G0、目标 PowerPoint、宿主 Review Bridge、用户 G3 仍未建立。
- IL02-T05: 本轮工程修复、最终回归、保留三页 Runtime 实物与冻结 SHA 独立复核已完成，代码候选 `ba7efa760c93bf423ed4f932ea8d2c54fa16f157`。真实正式案例与用户验收仍未建立；交回总控核验，不自动合并。

## 旧候选 E1–E5 历史结果（91ae801/fd03482）

- **E1 实现**：部分建立，旧候选未完成 Runtime 集成。候选代码覆盖 Image-led authorization scope 与 input-policy 分离、持久 `visual_workflow=image-led/v1`、持续授权复用与历史撤销、专用 action/ContextPack、材料只读桥接、唯一 TargetBinding、完整 `selected_copy → region → native object` 映射、失败保全和通用 Presentations renderer。renderer 预检先于 SDK 加载、输出目录创建和 PPTX 写入；失败保留 `failure.json`，不覆盖既有结果。
- **E2 回归**：Python Image-led 最终适用集 `94/94 OK`；Python 全量回归 `659/659 OK`；Node 适用集 `45 pass / 1 skip`。唯一 skip 是 renderer 完整 preflight 测试环境未设置 `C2_RUNTIME_NODE_MODULES`，属于环境未配置，不是业务测试失败。`npm run quality` 的 typecheck 在显式 bundled `@types/node` `typeRoots` 下通过；npm build 因共享 `node_modules` 只读/缺少 `@types/node` 被环境阻断，记为 `NotRun`，不宣称构建通过。`git diff --check` 通过。
- **E3 两组三页**：使用同一通用 renderer、不同页 ID、不同内容、不同几何和不同对象数量分别实跑三页。输出目录：`/private/tmp/c2-renderer-proof-20260909-new`。A 组 PPTX SHA256：`089f919a26db161f6772727a1849619613314e77da351691739ce87bb51614c4`；B 组 PPTX SHA256：`4b68401b8252eef3182c7976af65042c001f307a6c8f922472825d3dbea89ffa`。两组均标记 `visual_fidelity: not-established`、`user_acceptance: not-established`、`target_powerpoint: not-established`；synthetic 只证明通用工程路径和不同输入可运行，不能代替真实 Image 2 定版、客户材料、视觉保真、PowerPoint 或用户验收。
- **E4 当前 PowerPoint**：未建立。尚未对当前真实 C2 输出执行 `macos-powerpoint` 渲染、编辑、保存、重开或目标宿主证据；不得把 synthetic PPTX 或 C1 PPTX 代签当前 E4。
- **E5 用户视觉/G3**：未建立。尚未取得真实用户对 C2 三页的视觉判断，也没有真实 G0、当前 G2、ReviewSession、宿主通知、AI 接收回执或 G3 证据；工程测试、测试签名器和历史用户验收均不代签。
- **独立 Review**：材料桥接、可信确认、纯域合同、请求生命周期、三页 selection 和 renderer 已完成定向复核；复现的问题均已修复并复验通过，当前无未关闭 Critical/Important。该结论绑定候选实现和本记录的测试范围，不等于总控已批准合并。

## 工具与等待记录

本任务原始工具记录为逐次调用依据；测试命令另保存起止时间、退出码和日志。没有执行生图请求或 PowerPoint 操作；没有外部请求等待。

## 基线与第一个行为 RED

- 第一次全量 Python（bundled Python）：566 tests / 40.699s，1 error，原因是外部 skill validator 的 yaml 依赖缺失，非业务失败。
- 复用已有 PyYAML 到临时 dependency 路径后：566 tests / 41.559s / OK。未安装依赖、未改 bundled runtime。
- Node 使用原项目现有 node_modules 的只读链接；链接只在本 Worktree。
- 行为 RED：`python3 -m unittest tests.test_image_led_fidelity -v`（cwd=产品代码），1 test / 1 assertion failure，旧完整合同加入未验证 Image-led selection 后仍被 legacy validator 放行，未触发应有 ContractValidationError。首次误从 Git 根运行造成的 import error不计 RED；已改正确 cwd重跑。
- 设计文件：`docs/superpowers/specs/2026-09-09-c2-image-led-runtime-design.md`；实施计划：`docs/superpowers/plans/2026-09-09-c2-image-led-implementation.md`。
- 独立审查实例 `/root/materials_review` 与 `/root/visual_spec_review` 只读进行规格审查。材料接口调查另实际运行48项既有测试通过，不冒称新增机制已实现。

## 规格 Review 与初始边界

- 设计 SHA256 `aa738d4a7954f3df74b1cf1e4524a164ac1ca1d4ea7461824671b43b1140c62c`，材料与视觉两个独立实例定向复核均报告无未关闭 Critical/Important。仅为规格结论，不是代码验证。
- 材料首轮 1 Critical + 5 Important（generic确认不可信、scope/policy分离、source selector、用途/发送范围、发送字节TOCTOU、queued与执行预检）已修正规格；第二轮持久路线/撤销两项已关闭。
- 视觉5项（持久路线、selected items完整覆盖、构建检查/G2先后、deviations范围、renderer坐标/表达能力）已关闭。详细RegionInventory在用户定版之后。
- 初始代码RED：generic human decision可直接写入Image-led授权目标；新增专用可信确认guard后拒绝，完整业务树不变。
- 初始GREEN：`tests.test_image2_input_boundary` 4 tests / 0.293s / OK；`tests.test_image_led_fidelity` 初始未绑定合同反例已GREEN。可信正例使用测试签名器，只证明交易消费与binding，不代表真实用户授权或生产反伪造全覆盖。
- Node可信human-decision/bridge实现已分派到 `/root/trusted_confirmation`；纯域层内容→区域→对象合同实现分派到 `/root/visual_spec_review`。文件所有权隔离；主执行继续材料服务。

## 输入/请求切片的实现与独立工程 Review

- scope/policy/pack、实际源内容快照、持续授权/撤销、持久路线与generate-slide-images专用ContextPack已实现。公开工具仍43；Node/bridge只在既有human-decision新增可信分流。
- `/root/trusted_confirmation` 完成Node/bridge切片：适用Node43/43、Python新旧bridge8/8，公开伪签名不转发。HEAD旧server临时模块复现无宿主仍写入的行为RED；首次慢依赖导入不计RED。
- `/root/materials_review` 完成只读源桥接 20/20 定向复核（真实临时 source/finding/current refs、UTF-8 空白、image 裁剪、区域排除、path/symlink）；当时 PPTX 提取仍为初版 CapabilityGap。后续由 `/root/trusted_confirmation` 接入标准 Transitional OOXML 提取并完成定向测试，结果见下文；synthetic 输入不冒充真实客户材料验收。
- `/root/visual_spec_review` 完成纯域合同、旧 compilation 兼容、三页 selection 与通用 renderer；内容 items→regions→objects 逐字/geometry/appearance 映射已闭合。独立 Review 发现的 real-material 清空/转移绕过已修复并以 27/27 域合同测试复验通过。
- 主执行初始请求/授权12/12未覆盖竞态。独立Review复现3 Important：预检后撤销仍发送；visual清理恢复/并发回放重复发送；历史scope无法撤销。主执行新增行为回归（含transport真实调用2次的RED），修复后16/16 / 1.078s通过；原Review者四个原始探针复核均通过，无遗留Critical/Important（限定输入/请求范围，不是完整C2 Review）。
- 请求日志：`/private/tmp/c2-race-red.log`、`c2-concurrent-red.log`、`c2-historical-revoke-red.log`、`c2-request-review-green.log`、`c2-image-led-independent-review-recheck.log`。
- 候选/来源review/三页可信选稿已通过synthetic集3/3 / 0.488s；candidate结果原先不支持的正例RED已记录，现通过原Agent结果预演+原子发布。不是实际Image2、真实来源视觉检查或用户接受。
- 期间全量运行611项（40.870s）曾包含并行域代理用于 RED 的 scaffold，24 项为预期失败；该阶段性结果不作为最终回归。稳定实现后的最终回归见 E2。
- 阶段性记录：当时尚无 C2 真实 Runtime/G0/选稿/PowerPoint/G3；截至当前候选仍未建立这些真实 Gate。全程无合并、Push、安装或发布。

- `/root/trusted_confirmation` 接入标准 Transitional OOXML 只读提取：page/object 文本、唯一嵌入图片、未合并 table-range；9/9 OOXML synthetic tests 通过，source resolver + OOXML + scope/input 定向50/50。Strict OOXML、SmartArt/chart、合并表格、SVG/EMF/WMF、动画、多重备用图像保持 CapabilityGap。
- `/root/visual_spec_review` 通用 Presentations renderer 已按技能执行mark_artifact_operation_started一次，并用同一renderer实际渲染两组三页 synthetic：A PPTX sha `089f919a26db161f6772727a1849619613314e77da351691739ce87bb51614c4`，B sha `4b68401b8252eef3182c7976af65042c001f307a6c8f922472825d3dbea89ffa`；预检/路径/asset hash/尺寸/字体/endpoint/失败保全和3/3 Node tests通过。A/B视觉、用户、PowerPoint均`not-established`，输出位于`/private/tmp/c2-renderer-proof-20260909-new`。
- renderer源码 hash `669fd1aef9b8fd0f8c14feeb8a650ab25e5f86a793bdf29d6fb9f8ced1eae86b`；Node测试 hash `a386aa9bfe57bc38493521417029f99f469dbc7564c2c6996f9fe648a70c48b9`；synthetic fixture hash `2402146828ee4bfacceec41399f763b970fafcd2de799b514fe711491f204551`。
- 独立Review复现的真实材料载体Important已修复为27/27域合同测试：real-material必须有反向region覆盖，text逐字UTF8 hash，image/decoration asset hash，shape/table/connector含混绑定CapabilityGap；不强制style-reference/content-source出场。

## 2026-09-09 总控返回修复

- 修复起点：代码 `91ae801a36ad2af4c4d144b1574adb040b41be33`，执行记录 `fd03482a7af52ddebd8b182cce921bfc0d2bb32a`；原 Worktree/分支继续。
- Important 1：selection→regions 生产登记、独立审查、下游失效缺失。
- Important 2：regions→正式合同→独立版本计划→build-native-first handoff 缺失。
- Important 3：renderer 实物→结果接入→anchors→四维审核→当前 G2/既有审核链缺失。
- 另查 generate-slide-images 队列的实际执行/结果生产调用链；先真实入口 RED，再实现、反例/回归、独立 Review 和精确候选。
- 总控快照回报 Python 专项 94/94、全量 660/660、设置 bundled C2_RUNTIME_NODE_MODULES 后 Node 46/46。先前 659 与 45 pass/1 skip 保留其历史时点；discovery 差异待核对。绿灯不能关闭上述集成缺口。
- 以上为修复任务与外部核验回报，不表示修复完成或真实用户 Gate 已通过。

- 总控复现脚本 `/private/tmp/c2_il02_t03_t04_integration_repro.py` 与结果 `/private/tmp/c2-controller-integration-repro.result.json`：3 页 current selection/域 RegionInventory 通过，三个拒绝入口 revision 41→41 且零业务写入；合同 probe 只有 selection_ref，不是完整合同正例。
- 总控精确快照 `/private/tmp/c2-controller-fd03482-review`；Python 历史全量日志 `/private/tmp/c2-controller-python-full.log` 660/660；适用 Node `/private/tmp/c2-controller-node-46.log` 46 pass/0 skip。临时快照补齐 bundled `@types/node` 后 tsc exit 0，日志 `/private/tmp/c2-controller-typecheck-configured.log`；build 与更广 Node 尚待总控回传。
- 本轮已用完整 selection→regions→独立 region review→完整 brief/design/contracts 生产入口建立 RED；`/private/tmp/c2-runtime-regions-red.log` 两项正向断言因 IMAGE_LED_SCHEMA 失败，`/private/tmp/c2-runtime-contract-red.log` 完整合同链因旧 ROUTE guard 失败。首次 PATH Python 缺 PIL 导致 fixture generation unknown 不计业务 RED，已改 bundled Python 重跑。

- 总控旧候选审查收尾包：`/private/tmp/c2-controller-review-20260909/controller-review.md` 与 `evidence-manifest.json`；497 tracked blob匹配旧快照。旧候选 Python660/660、全量Node145/145、tsc和Widget build exit0；Node42项loopback EPERM复跑45/45、缺yaml/npm以既有依赖路径关闭。Widget suite在120s/240s只有Vitest RUN无完成结果，原因待定位。上述结果只绑定旧代码91ae801/fd03482，不代签本轮新修改。

## 本轮生产集成修复与独立反例

1. selection→regions：`ImageLedNativeService` 由既有 VisualService artifact dispatcher 接入，读取实际定版图 bytes/尺寸/hash，验证完整 inventory；独立 region review 必须有完成的真实任务及 context lineage。区域/审查变化清除正式合同和下游。RED 为 `c2-runtime-regions-red.log`，完整生产测试为 `tests/test_image_led_runtime.py`。
2. regions→contract/plan→build：完整 brief/design/contracts 在当前 selection/region review 下登记，以 `image-led-faithful-compiler/v1` 确定性派生并同事务发布；当前正式 G1、原 action 与 ContextCompiler 解析完整依赖。真实 renderer 输入为 `layers.visual_handoff.renderer_handoff`。完整合同与 G1 的 RED 为 `c2-runtime-contract-red.log`、`c2-runtime-g1-red.log`；正式 handoff 实际调用 Node preflight，无 mocked renderer。
3. 实物→结果→四维→G2：实际 Presentations SDK 输出通过原 producer 的 Agent result 接入；结果接入读取 PPTX、mapping、inspect、proto、layout、每页 render 与 comparisons bytes，核对对象身份、文案、外观和依赖。四维 Review 需独立工程任务，不能自审。anchors 仅接受 result/ref 两项身份后确定性派生支持证据，原 G2 双角色 Review/目标证据和现有 ReviewSession 接通，G3 不代签。实际结果可登记而旧 anchors 入口拒绝的 RED 为 `c2-runtime-g2-red.log`。
4. generation 执行：默认 MCP Server→真实 Python bridge→无 shell command adapter 子进程→持久图片响应已由 `tests/image-led-mcp-e2e.test.mjs` 固化；公开工具仍 43，`request_ai_ppt_agent_action` 单项 `openWorldHint=true`。宿主 adapter 缺失/receiver-model 不符在建队前零业务写入；未知执行不重发，返回图片不自动 candidate/selection。bridge/CLI 7/7 日志 `c2-execution-entry-green.log`，上述外部调用全为 synthetic adapter。

独立 Review 的附加问题与处理：

- G1 Review 被失败 Review 替换后仍能 build：先记录行为 RED，再清除输出并重开 G1/锁 G2；原审查者的原探针 `c2_runtime_review_probe_recheck.log` 3/3 PASS。
- convergence/source-review 替换后通过状态残留：新增真实入口 RED，修复失效；审核投影同时改为只读 selected_copy，legacy visible_copy/frozen_copy/anchor_title 无法覆盖定版标题正文，并保留精确空白。`c2-projection-convergence-red.log`、`c2-source-review-red.log`；Runtime/requests/selection/既有 projection 27/27 PASS（阶段性）。
- 撤销当前 scope 与更换 release policy：原审查者分别复现旧 G1/head 残留，修复后 G1=open/G2=locked，selection/contracts/plan 删除；无关历史撤销不影响当前链。`c2-policy-invalidation-red.log`、`c2-policy-invalidation-green.log` 33/33 PASS，并由原审查者两个原探针和五项替换矩阵独立复验。
- R-RESULT-01：真实 PPTX 文本框改为红色填充、只重算 PPTX hash、复用旧截图可被接受。修复为闭合载体属性检查，并从当前 PPTX 内存 bytes 用 SDK 重新导入/渲染、逐像素核对 render，从当前 target/render 重算并排/叠图/区域差异；假 render/overlay/MAE 重 hash 也拒绝。原红填充探针已被原审查者拒绝复验，结果+G2 11/11 PASS。像素一致只证明输出证据来源，不自动判定视觉达标。
- G2 Review/目标证据登记前字节变化：两条正式入口原先只验 current ref/plan，会为已变化 PPTX 写入旧证据；最终 G2 虽会拒绝，仍不满足写前拒绝。`c2-g2-evidence-prewrite-red.log` 复现两入口均未拒绝，补 current_anchors 实物复验后 `c2-g2-evidence-prewrite-green.log` 正例与两条零写入反例均通过（17.850 秒）。
- SDK 原导出未稳定保留 object name 和混合对象 z_order：改用官方 proto/load 固定身份与层叠，并读实际 OOXML 复验。`/private/tmp/c2-result-native-identity-proof.json` 保留旧输出被拒与新 14 个混合对象通过的对照。
- 最后载体实物覆盖：第二组可变三页包含 text/shape/image/gradient/native table/connector，结果接入通过；表格单元格文字/边距与连接线关联对象/连接点/箭头/翻转共六项重 hash 篡改拒绝，独立复验1/1 PASS。shadow 经 SDK 主题 effectRef 输出，现有核验不支持，明确写前 CapabilityGap；实际 preflight 用例确认未加载 SDK、未创建输出目录。结果11/11、Node renderer3/3、compileall/diff检查通过。
- Skill 操作检索先 RED：三文件没有七项正式入口、错误要求传旧 wrapper/禁止派生 copy/先连接后节点，容易跳过结果接入。更新现有 Skill 和两份 reference，明确自动生成、可信选稿、独立 regions review、实际 render()、result/four dimensions/anchor/G2；未安装插件。检索复验见独立回执。

结果仍保留 `engineering-output-unassessed`。`output.files` 明确绑定 handoff/mapping/inspect/authoring proto/reimport proto 与逐页 layout，`comparisons` 绑定同画幅并排、叠图和逐区未评估差异；`handoff_sha256` 是实际 handoff.json 字节 hash，不是另一个 JSON 归一化 hash。任何不支持的原生载体、属性或证据均不能由另写页面补齐。

## 本轮工程验证与实物保留

- 新工作树 Python 全量：`702/702 OK`，90.177 秒，`/private/tmp/c2-integration-python-full.log`；采用 bundled Python 3.12、当前源码和既有 YAML 依赖，renderer 使用 bundled Node modules，无 skip。后续若有载体覆盖修正，以最终回归回执为准。
- **最终源码回归**：载体/阴影/G2写前修正后 Python `703/703 OK`（101.396秒），`/private/tmp/c2-integration-python-final.log`；`npm run quality` exit0，日志 `/private/tmp/c2-quality-final.log`，包含 tsc、build、Node `149/149 / 0 skip`、Widget `16文件/755 PASS`（37.52秒）。临时快照499文件与最终验证时工作树 hash 完全一致。缓存解包未创建 bin 链接导致首次 quality 的 tsc command-not-found，已仅在临时依赖按 package bin 元数据补齐并完整重跑；未改源码/配置/共享安装。
- 共享依赖问题已通过独立环境复核定位：单独 Node import jsdom 在原共享目录沙箱内/外均超 25 秒；相同锁文件依赖从本机 npm 缓存按 integrity 恢复至 `/private/tmp/c2-widget-cache-mzt3e5dx` 后分别 326ms/289ms 导入成功。未修改仓库 Vitest 配置/worker、未改共享 node_modules、未联网安装。尚未定位具体 macOS 机制。
- 该快照新跑 Widget `16 文件/755 PASS/0 skip`（41.80 秒）、Node `149 PASS/0 skip`（16.59 秒）、tsc exit0、build exit0；499 源文件与264依赖包清单、命令和日志见该目录 `widget-diagnosis.md`、`source-manifest.json`、`dependency-manifest.json`。这些是运行时快照，最终变动文件须同步后做适用复核。
- 四基线相对文件链接 `60/60` 可解析；原型引用6次/3个实际文件均存在，`/private/tmp/c2-baseline-link-check.json`。该检查未宣称 Markdown fragment anchor 校验，也不代替 C0 冻结 hash。
- 保留三页真实入口工程实物：`/private/tmp/c2-production-runtime-proof-9m4clol9/proof-manifest.json`，64 条实际 Runtime events、S01/S02/S03、实际 PPTX sha `6300637f4a606c85f59fa80e33a3b6f83e787d622cea611744dfac1c58d51b8f`，包含 current result、四维 review、anchors、G2、现有 ReviewSession/投影及缺目标证据/改 PPTX 拒绝零写入。重放脚本 `/private/tmp/c2-preserve-runtime-proof.py`。全部 G0/选稿/四维/目标决定为 synthetic；fixture 的 G2=passed/G3=user-reviewable 绝不代表真实 PowerPoint 或用户验收。
- **最终源码实物重放**：`/private/tmp/c2-production-runtime-proof-wklgvm3t/proof-manifest.json`，65条实际事件，同三页实际 PPTX sha `dfec41b9ecb67ac56422e4f6fca00ff053cb5edc3974e635d2d79c2d1cdc425f`。新增 G2 Review/目标登记写前字节变化零写入，保留全部文件/hash/事件/四项拒绝步骤；日志 `/private/tmp/c2-production-runtime-proof-final.log`。与上一轮同样全为 synthetic 决定，真实 Gate 仍未建立。
- 旧659与总控660的差异仍保留历史原数：旧候选实际 test_image_led_contracts 含28项而早期定向记录为27项，但没有完整旧 discovery 清单可证明恰为该项导致，不推断补写。新候选以本轮完整日志为准。

E1 为本地生产集成候选；E2 为当前源码自动化；E3 为 synthetic 实际文件和 Runtime 链；真实 Image 2/客户材料/G0/定版、E4 PowerPoint、E5 视觉/G3均未建立。没有合并、Push、插件安装、发布或 C3。

## 冻结候选与最终独立 Review 回执

- 代码候选：`ba7efa760c93bf423ed4f932ea8d2c54fa16f157`，本轮父提交 `fd03482a7af52ddebd8b182cce921bfc0d2bb32a`；完整 C2 派生基线 `0283b0d882b9838d58dd43c7b217e604d9b4f6d2`。本轮33文件、3400增加/104删除。分支仍为 `codex/image-led-native-anchors`，执行 Worktree 不变。
- `/root/visual_spec_review` 对未参与的 Runtime/选择/结果接入/Gate/审核投影等模块完成独立 Review，原问题均关闭，未发现未关闭 Critical/Important；自己参与的域/compiler/context/早期 renderer/MCP metadata-e2e 明确只算自检。报告 `/private/tmp/c2-ba7efa7-visual-spec-final-review.md` 及同名 JSON；报告 SHA256 `1e8419aab4ac9791fd865f28c8857661455321883b64667a8fabb5ce2d7f1c2e`。
- 同一代码 SHA 的独立五项原探针 `5/5 PASS`，`/private/tmp/c2-final-independent-probes.json`；撤销scope、release policy、G2 review写前改bytes、target写前改bytes、红填充+新hash+旧截图均复验。两写入口 revision57→57，完整业务树不变。
- `/root/trusted_confirmation` 对未编写的 contracts/compilation/context/handoff 做独立专项，`Critical=0 / Important=0 / Minor=0`；46/46回归与3/3额外公开入口探针通过，7主要文件匹配Git blob。报告 `/private/tmp/c2-final-compiler-handoff-ba7efa7-review.md` 及同名JSON；该审查不包含其自己编写的 generation/adapter/bridge/MCP 模块。
- 已核对候选508 tracked blobs、7项证据hash、最终Runtime实物200文件hash与65事件；清单 `/private/tmp/c2-ba7efa7-candidate-evidence.json`、复核 `/private/tmp/c2-final-review-evidence-verification.json`。三份 Skill 最终操作走查完成；旧 before/after 文件原样保留，最后阴影能力说明另由最终Review直接读验，不把旧after中的handoff hash当最终hash。
- 本节所在后续提交只收口实施计划和本唯一执行记录；不改变上述已测试/已Review的代码。原有dispatch两份临时文件及node_modules链接继续不跟踪。最终总控交接将同时给出代码SHA与文档收口HEAD，避免循环自引用提交。

## 真实 C2 三页输入准备与宿主确认阻断（2026-09-09 至 09-10）

- 用户“继续呀”“确认”之后，总控明确转达：C2-S04=M03 p12、C2-S05=M01 p25、C2-S06=M03 p18 的 71 段已核验源文字、page_goal、common_rules 为当前已确认输入；既有材料和执行授权持续有效，不重开逐页/逐次生图许可。此决定与 Runtime 的可信确认回执分别记录。
- 审计来源为 `ee1e9f86356da62b25a5695f2c85a6e84db2ddda`。本轮通过当前源码 CLI 建立真实项目 `/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909`，并将本轮两份原件 M01/M03 复制登记到既有 MaterialInventory；MCP 保存 MissionDraft 后 revision=4。未修改客户原件，未把项目运行数据写入源码。
- 当前材料引用为 `artifact://material-inventory/d588082b32fb2583581a137950bb1bbaf359da01ca5899e40db8c41d1f05df92`；任务草稿为 `artifact://mission-draft/0a1050349d2633743c6f6f3bbc08b22d7a7d1fe67d0c7b55d13c1df800da91e0`。两份 Runtime 副本与审计原件 hash 一致。
- 派生输入位于项目内 `input/confirmed-three-page-input-v1/`；共 10 个文件，包含三页逐字输入、生产提取文本、共同规范、两张可选原图及完整阅读稿。`preparation-manifest.json` SHA256 为 `8aefe8818e03cfda7b48e8e3c8c4f743aae6dd558865ea1a418455715bf5c871`。三页实际生产 OOXML 提取分别与 16/36/19 段源文字完整一致；源文件、源页 XML、copy 数组及两张媒体 hash 均核对。共同规范通过现有 contract validator；正文布局指令为空。
- image88/image90 只保留可见工业场景用途；image106 按整图 hash 排除，未复制入派生输入。未将未知集成、接口、实施、性能或成效补成事实。源页码/章节标记作为已确认源文案保留，不解释成本轮页序。派生文件不是第二事实源或已登记的正式 VisualInputPack，不能被直接用于越过当前 G0 发请求。
- 当前真实输入独立复核 [65/65 PASS](./real-runtime-input-review.json)，Critical/Important/Minor 均为 0；复核同时匹配实际 Runtime 副本的 presentation 页序/shape 原文、生产提取器源码身份、媒体 hash、共同规范、空正文布局指令和 revision=4。报告 SHA256 `f1a9706d0a018b3e81e286d9aa3a0007a1b03f82662ac552bf13fb9943e5257c`；这是输入准备复核，不是正式双内容硬门。
- 已真实调用现有 `confirm_ai_ppt_mission`，返回 `HOST_CONFIRMATION_UNAVAILABLE`，`phase=host-form-response`、`transport=openai-form`。随后 MCP snapshot 和本地读验均确认 revision 仍为 4，无 MissionConfirmation/G0 确认制品。接口失败不表示用户撤销已确认输入；无失败后的重复表单请求。
- 独立宿主诊断见 [宿主确认诊断](./real-mission-host-diagnostic.json)。已安装版本与源码的 Mission 确认段相同；正式 stdio 启动未注入真实 message verifier。默认 60 秒请求超时及晚回包支持传输超时假设，但原异常未保留，不能称唯一根因已确证。安装版本不等于当前 C2 全部代码，直接替换同一确认段也不能证明恢复。
- 2026-09-10 总控复核后的明确口径：桌面表单实际回包为 `request_id=12, action=accept, content.confirmed=false, _meta=null`。该组合既不是确认成功，也不能据此认定用户明确拒绝或撤销已有聊天决定；最终接口错误仍为 `HOST_CONFIRMATION_UNAVAILABLE`。不得默认将 false 改成 true、第二次自动弹窗或盲目重试。
- 当前 `production_stdio_confirmationVerifier_injected=false`、`ready_message_verifier_route_found=false`。安装包 `mcp/tools/project-tools.mjs` SHA256 为 `d192421360778e9fd5b8bdc01a6dc5b554d6048f2f5f12f3da8723fc9d8ede52`，源码为 `bd89f177a3771fe4ff5f8d7a0d027dfa653b8a65a1a69f162045c4271949e98c`；两者不同，不能以局部 Mission 段相同推定整个已安装实现等同源码。本次不安装或切换插件，剩余 CapabilityGap 保持为宿主确认集成。只读复核 revision=4，既有材料/任务草稿 refs 保持原值；MissionConfirmation、四个正式内容对象、acceptance、review-batch 和 G0 确认 refs 继续为空。
- 总控已收到确切恢复事项：承接已有真实用户确认、核验输入版本绑定、修复宿主表单诊断与等待生命周期；不将宿主能力故障转成再次索取材料/内容/生图授权。当前未安装插件、未修改宿主、未伪造回执或直接改 Gate。
- 总控实际调用 `open_g0_review(expectedRevision=4)` 返回 `GATE_BLOCKED: content-review-evidence-missing`。源码核对：该值是缺少 `content/acceptance`、`content/reading-blueprint`、`content/review-batch` 的聚合错误标签，不是可单独登记的新制品类型。主任务实际只读调用 `MissionReadinessPolicy.require_ready()` 仍返回 `MISSION_NOT_CONFIRMED`；错误所说缺少确认指 Runtime 回执，不能覆盖已存在的用户决定。
- 按总控最新口径，补齐项目内 `input/content-chain-preparation-v1/`：71 条来源/shape/逐段引用映射、既有审核投影字段的 71 个文字块与 0/0/2 图片路径、当前内容链依赖和缺失记录。3 个草稿文件的 manifest SHA256 为 `c9c3a77e7a6357db5a3318ec60183e3d89f8a867d7b6a4aba05b4e018fc25247`。所有正式 evidence/blueprint/acceptance/review session 引用保持 null，decisions 为空、batch=null，状态字节与 revision 未变化。草稿不作为正式 PresalesEvidenceBook、ReviewSession、内容硬门或 G0 证明。
- 内容链准备增量独立复核 [46/46 PASS](./content-chain-preparation-review.json)，Critical/Important/Minor 均为 0，报告 SHA256 `58142705f7d393eb44417a941717c3e0cbc39f7f5df966867ddafa0bef83ff71`。核验确切 manifest/3 个 payload、71 段/shape/source_id 同值、真实图片路径、所有正式 ref=null、无 PageDecision/Batch 和 revision=4；同样不替代正式内容硬门。
- 当前结论：真实 Runtime 项目、材料登记、任务草稿和已确认三页派生输入已建立；Runtime Mission/G0 回执未建立，Image 2/用户定版/原生转换/PowerPoint/G3 均未执行或未建立。C2 未完成，未合并、Push 或发布。此轮不改生产代码，不重复声称此前自动化通过就是客户验收。

## C2 宿主确认承接源码修复（2026-09-10）

本节接续上节的只读诊断；总控最新转达的“确认”授权继续修复当前宿主承接。修复仍在 `codex/image-led-native-anchors` / `28a9` 独立 Worktree，父提交 `677f60b983c3c7abc8c799c5396c8fc4ab56049d`。本节记录的是源码候选与隔离验证，真实 Mission/G0 仍未恢复。

- **行为修复**：四类原生确认共享未完成语义。`accept + confirmed !== true` 返回 `HOST_CONFIRMATION_NOT_COMPLETED`；明确 decline/cancel 仍使用既有取消分类。两者均保留之前决定，不强制布尔转换，不签名或提交业务写入。公共工具目录/schema 不变。
- **等待与诊断**：内部默认 600000 ms，两个原生传输均继承上游取消信号；取消后、签名/bridge dispatch 前拒绝晚到结果，不自动重试或切换表单。诊断只输出安全分类、数字错误码、白名单错误名和请求/时间身份，不输出原始宿主报错或客户文本。此证据不证明宿主 UI 已关闭，也不承诺回滚已开始的事务。
- **消息校验**：Mission/Gate/修改方案 verifier 改为严格 `=== true`，与 Image-led 既有要求一致；Mission 传入确切 inventory 和 revision。verifier 异常返回安全能力错误，没有备用弹窗。没有加入虚构 verifier 或未接通的启动注入接口。
- **基线同步**：四基线同步既有决定保留、未完成/取消区分和承接限制；源码 Skill 与运行参考删除确认失败后无条件重试的指令。Python 既有说明文字精确断言曾失败，已保留原测试、修正等义措辞，并通过新一轮全量验证。没有修改材料、三页目标、共同视觉规范或忠实转换要求。
- **测试先失败再修复**：最初新增 11 项回归均按预期失败；扩展到 19 项时再暴露 5 个取消/verifier 异常缺口并修复。独立 Review 发现 HOST-M01：当前 SDK `$ZodError` 被错分为 transport-error。新增 [无效回包 RED](./host-confirmation-recovery/malformed-response-red.log) 实际复现后，安全归一为 `ZodError` / `invalid-response`；当前新增回归共 20 项，包含于最终全量测试。

| 本轮验证 | 最终结果 | 证据与范围 |
|---|---|---|
| 原有确认与新增恢复聚焦集 | 63/63，0 fail，0 skip | [聚焦日志](./host-confirmation-recovery/focused-final.log)；synthetic 协议与 bridge fixtures |
| 全 Node | 180/180，0 fail，0 skip | [完整日志](./host-confirmation-recovery/node-final.log)；当前源码散列一致的隔离副本 |
| 全 Python | 713/713 OK | [完整日志](./host-confirmation-recovery/python-final.log)；当前 Worktree 源码与既有本地 YAML 依赖 |
| Widget 构建 | PASS | [构建日志](./host-confirmation-recovery/build-final.log)；未修改 Widget 源码，本轮未另跑 typecheck/Vitest |
| 独立 Review | Critical 0 / Important 0 / Minor 0 | [完整报告](./host-confirmation-recovery/independent-review.json)；HOST-M01 CLOSED，原探针/新增回归/原 Skill 断言各独立复验 1/1 |

首轮全 Node 的 179 项为 134 pass / 44 fail / 1 skip；[独立失败分类](./host-confirmation-recovery/initial-failure-classification.json) 逐块确认 42 项为 `listen EPERM 127.0.0.1`、1 项为共享 `node_modules/.vite-temp` 写入 EPERM、1 项为缺少 `widget/dist/index.html` 的 ENOENT。首轮 Python 713 项有 1 文档字面断言 failure 和 1 缺 YAML 的 error，未把文档失败归为环境问题。后续复用同锁文件的私有依赖、离线 npm 缓存、独立测试 Runtime 配置和允许本机监听的执行上下文重新构建/全跑，全部通过；新增回包用例使 Node 总数变为 180，配置现有 renderer 依赖后原 skip 也实际通过。没有安装依赖到共享目录、改共享链接目标或安装/切换真实插件；release/install 测试只写临时 fixture。

[隔离快照清单](./host-confirmation-recovery/validation-snapshot-manifest.json) 的 529 个文件在测试后与原 Worktree 逐项 SHA256 一致；随后只有四基线与本节/证据文档同步，已测试源码与测试字节保持不变。修复后的 `mcp/server.mjs` SHA256 为 `cfa8c8b24d838dc4f9b7e8917a5beb7614a12b7e3a9e7733efb75a972d1ef79c`。执行命令、时间、日志 hash 和 proof 文件 hash 见 [结构化证据](./host-confirmation-recovery/evidence.json) 与 [Node 执行回执](./host-confirmation-recovery/node-execution.json)。

最终只读复验：真实 Runtime 仍为 revision **4**，state SHA256 **`1a8c79fa3eeb8d12d2dcc0d945a2bd4d1800a8dbe1724a3d45d6dc856fd95588`**；materials 与 mission/draft refs 保持上节原值，`consumed_user_confirmations={}`，MissionConfirmation/四内容对象/acceptance/review-batch/G0 refs 未建立。G0=`open`，G1–G4=`locked`，不等于通过。已确认 71 段、三页目标、规范和材料决定继续保留。

**剩余阻断属于真实宿主承接能力**：运行中的插件尚未加载本修复，正式 stdio 仍未注入可验证历史消息的真实供应方；本次不重开真实确认表单、不安装/切换插件、不制造回执。原始异常已被旧实现丢弃，因此不能把 60 秒超时假设改写成唯一确证根因。下一步由总控处理已审查代码的宿主加载/真实回执接入路径，再走真实 Mission → 四内容对象 → 双硬门 → ReviewSession/Batch → G0。当前源码修复不等于 C2 恢复，更不等于生图、忠实转换、PowerPoint 或 G3 验收；未合并、Push、发布或开始 C3。

## 用户授权后的插件安装与当前会话加载核验（2026-09-10）

总控线程 `01a07cae-3eae-7d12-abc5-eaa73addf881` 最新明确转达：用户已授权更新插件和真实宿主能力核验；总控已完成安装与 CLI cache 刷新。此新授权承接当前修复，先前“不安装”是当时的执行边界，不继续作为阻止已授权更新的理由。安装授权和安装结果不作为 Mission/G0 回执。

- 安装版本为 **`0.4.0+codex.c2.cfabfc1.20260910`**，cache 为 `/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/0.4.0+codex.c2.cfabfc1.20260910`。本执行实际读验 server SHA256 `cfa8c8b24d838dc4f9b7e8917a5beb7614a12b7e3a9e7733efb75a972d1ef79c`、Skill SHA256 `22da4dec65ecf5ec7e244756720ad595812ec9fbfdfe9c94d3dec6015525088a`、manifest SHA256 `718e1cb8bb879c4df642f1a7cffce0b50f8854d7185b11a556bc8025d7a793c8`，与提交/总控声明一致。
- 总控 [安装核验报告](./host-installation-cfabfc1/installation-verification.json) 记录安装目录和 cache 各 3761 个文件按 manifest 核对，0 mismatch，保留安装前备份；独立 cache 子进程 probe 在空 PATH 下可列出 43 个工具并读取 revision 4。这些是包与子进程证据，不等于当前桌面会话已经切换。137 个源码逐项一致属于总控转达，本执行仅独立重验上述关键文件与补件，不扩大自身核验范围。
- **打包遗漏记录**：原 release allowlist 漏掉 `scripts/image-led-native.mjs`，总控将 `cfabfc1` 中该文件按原字节补入发布包，并重新生成校验 manifest。[补件记录](./host-installation-cfabfc1/packaging.json) 与本执行 `git show cfabfc1:产品代码/scripts/image-led-native.mjs` 对照均匹配 SHA256 `1c81e15666656bc6422b06db4481dd934f1ac10c7a47455840645e51a86eca14`，未改变业务源码。当前包已包含补件；仓库 allowlist 本身仍待后续修正，本轮只核验/记录，不将人工补件说成打包代码缺陷已修复。
- **本会话仍旧**：本轮会话 Skill 目录仍公布旧 `0.4.0/skills/ai-ppt-studio/SKILL.md`，该旧路径在磁盘已不存在；手动读取新 Skill 文件不证明宿主自动加载。09:46 的进程核验中，桌面 app-server PID **1326** 下 10 个 `start-mcp.mjs` 进程的 cwd 全部为旧 cache `0.4.0`：11724、28980、44746、47689、63089、74122、78948、83903、86791、94736。没有发现 cwd 指向新版的候选。未能唯一关联当前线程到某个 PID，因此不猜测具体对应关系。
- 总控当前旧 MCP snapshot 返回 `spawn /usr/bin/python3 ENOENT`，可能与旧 cwd 在 cache 刷新后失效有关，未将该推断定为唯一根因。收到总控“不要对旧连接重试”的最新要求后，本执行未再调用旧 MCP snapshot 或确认。真实项目本地只读核验仍 revision **4**、state SHA256 `1a8c79fa3eeb8d12d2dcc0d945a2bd4d1800a8dbe1724a3d45d6dc856fd95588`、确认消耗为空，28 个项目文件前后 hash 一致；没有 Runtime 回滚或写入。
- 结论与下一步：**当前会话不具备新版加载证明，不能准备为可发真实表单状态**。已回传总控需要新加载任务或重建 MCP 连接，并在新会话核对 Skill/PID/cwd/真实只读 snapshot 后再统一安排一次 Mission 表单；本执行不先发。本轮未重启进程、重复安装插件、搜索历史供应方或写入确认/G0。

原始安装证据目录为 `/private/tmp/c2-install-cfabfc1-20260910`；本记录保留必要回执副本及 [本会话结构化核验](./host-installation-cfabfc1/current-session-verification.json)，配置文件与客户材料未复制进源码。当前 C2 仍未完成，三页既有内容、材料和共同规范授权保持。

### 新建验证任务仍未加载与重启续接

总控新建的“C2 插件更新后的真实宿主核验”任务 **`01a088ff-e1e7-78a3-9493-3dee67a8d21d`** 实际观察到工具目录 94 项，其中 AI PPT 工具 **0 项**，Skill 路径仍来自旧 App 缓存；未发送真实 Mission 表单。这是总控及该验证任务的真实回执，本执行按最新指令归档，不重复运行诊断或测试。最新版 [安装核验结果](./host-installation-cfabfc1/installation-verification-after-new-task.json) SHA256 `705302a43a1125c5e9d10a5ff6bc0e8d2da528aa949da0e128ae4b5123915636` 明确记录 `real_host_status=desktop_restart_required`；先前报告原样保留，避免覆盖当时证据。

下一步由用户**完整退出并重新打开 Codex API Client**，然后在上述验证任务回复“继续”。总控报告 CUA 明确禁止操作 `com.openai.codex` 自身，无法代点重启，不使用其他 UI 技术绕过该限制。重开后仍须先核验实际 Skill/MCP 来源及真实只读 snapshot，再安排一次统一的 Mission 确认；没有新加载证明不调用表单，也不重复索取已确认的材料、三页目标、共同规范或同范围执行授权。

[安装回执与续接](./host-installation-cfabfc1/安装回执与续接.md) 按原字节归档，SHA256 `a9d2070e4059b6deee24ee395be003318bde97d18cd91a5aa1bb151eeabb60ee`。该回执所述补件仅表示当前发布包包含同提交脚本；仓库 allowlist 代码缺陷仍按上一节保留待修正。本轮仅更新本记录与两份回执附件，未操作客户 Runtime；客户 state 保持 revision **4**，MissionConfirmation/G0 仍未建立。

### 新验证任务直接回执归档

验证任务 `01a088ff-e1e7-78a3-9493-3dee67a8d21d` 已直接回传 [正式核验报告](/Users/defei/Documents/Codex/2026-09-10/c2-fresh-host-cfabfc1-20260910/outputs/verification-report.md)，SHA256 `0ff5ee33e90c38598b8d0ef8c91be85eff67a01f6c40741d345339ba31b73fe1`。原报告及全部附件继续保留在该任务 outputs；本项目保存 [机器回执副本](./host-installation-cfabfc1/fresh-host-verification-receipt.json) 和 [证据身份索引](./host-installation-cfabfc1/fresh-host-evidence-index.json)，10 项原附件按 manifest 核对全部同 hash，不复制原始客户 state 进入产品源码，也不建立第二份执行 ledger。

直接宿主日志 15757818、15758167 明确为 `omitting MCP server without an exact ready client server_name=ai_ppt_studio`；15757694 仍解析 defei 插件为旧 `0.4.0`。09:51 的只读 ps/lsof、注入的旧 Skill 路径和 94/0 工具目录共同支持“当前宿主 MCP 客户端未就绪”。该任务没有启动替代 probe、调用旧连接、重装插件或修改产品代码。

正式 snapshot **NotRun（0 次）**，原生 Mission 表单 **0 次**，真实 Mission 回执无；state 文件前后 revision 4、SHA256 `1a8c79fa3eeb8d12d2dcc0d945a2bd4d1800a8dbe1724a3d45d6dc856fd95588`、字节及 mtime 均一致。此处只证明报告所观察的 state 文件未变化，不能表述为真实 MCP snapshot 零写验收通过。没有推进 G0、内容、Image 2 或 PPTX；重启后在该验证任务续接的安排保持不变。本执行仅归档文件证据，不追加宿主诊断、测试或表单调用。

## 来源引用与适配衔接只读诊断（2026-09-10，revision19）

总控任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 已转达：重启后的新版插件实际加载，真实 Mission、Browser 三页审核、提交 Batch 和宿主 G0 确认完成；本轮要求主执行独立只读定位生图前的来源/adapter 断点，提交最小修复方案并更新本唯一台账。**此轮不实施源码或客户 Runtime 修复**，不重新确认、生图、安装、合并或 Push；既有材料、三页内容、共同规范和同范围执行授权继续承接。

### 已建立的当前事实

- 本执行真实调用 `get_ai_ppt_project_snapshot` **成功**，读取 revision **19**，MissionConfirmation 有效引用存在，G0=`passed`、G1=`open`、G2–G4=`locked`；[仅身份与 Gate 的 snapshot 摘录](./source-reference-recovery/runtime-snapshot-references.json) 保留当前19个 heads，不复制客户完整 state。当前 Skill 注入已指向 `0.4.0+codex.c2.cfabfc1.20260910`。旧会话 snapshot NotRun/旧 cache 故障仍为历史记录，不能继续报告为当前状态。
- 本执行只读核对当前 Batch 为 `submitted`，approved=**3**，其余计数均0，页面恰为 C2-S04/S05/S06。Browser 实际逐页审核操作由总控回传；此处的本执行证明是当前正式制品与 snapshot，不冒称本执行重复操作了 Browser。
- 当前 MissionConfirmation：`artifact://mission-confirmation/a3ae8ab7bb93299c50a08059b499e3efccc7c4b6699646cab5d884bb646185b9`；当前 Blueprint：`artifact://reading-deck-blueprint/49959cc0f5d579a7e3d6df231ff0b8930fd754de52ed8255a7f9a744a9b0ae31`；当前 Batch：`artifact://content-review-batch/55cbbd3003ae413254e1c6547a35dec1be28c2020d4958101aa58e82f091f08d`；当前 G0：`artifact://g0-confirmation/acd5f8f764acf10929062287a20eba6535f1a7808b2c6573dc25efc5b89acc06`。source_version=`c2-content-v1-20260910`；其他完整 refs 见上述摘录。
- 三页当前 EvidenceBook 事实文字及 Blueprint 可见块与已确认输入逐字一致，**16+36+19=71/71**，页序和来源保持 M03 p12 / M01 p25 / M03 p18；[主执行探针](./source-reference-recovery/readonly-source-probe.json) 保存每页文案/page_task hash、材料绑定及计数，不保存客户原文。

### 当前断点与最小方案

| 断点 | 实际证据 | 待实施修复方向 |
|---|---|---|
| 来源引用未闭合 | 两个 source_refs 是 `source-*` 库存 ID，已安装 resolver 实际均报 Invalid artifact reference；25个制品中无支持 kind 的 finding，准备稿71个 finding ref均null | 在既有 add-material 工具内补固定 finding 正式登记分支，复用当前材料/OOXML；引用预检进入内容链，不能手写制品或放宽 resolver |
| 排除范围未结构化及同页对象误判 | image106=page18/object39 的排除仍在输入决定中，EvidenceBook.excluded refs为空；允许33/36与排除39的 `overlaps` 均错误返回true | 结构化登记排除 finding，修正已知对象身份比较，保留未知坐标/整页排除保护；禁止删排除或改文案绕过 |
| 真实 Image 2 供应方/配置未建立 | 包内有通用 command adapter，仅见 synthetic供应方；manifest 未声明3个必需adapter键，shell presence=false；实际MCP环境 NOT_OBSERVED | 接通符合协议的真实 wrapper 与宿主配置/转发，绑定真实MCP做不生图预检；不以 shell presence 或旧结果恢复证明真实调用可用 |

独立来源审查比较 **19个文件**，工作区/`cfabfc1`/已安装包字节全部一致，提供29处行号证据：[来源入口与失效审查](./source-reference-recovery/formal-source-route-review.json)。独立 adapter 审查比较5个关键安装文件同提交一致，核对配置声明与环境传递边界：[adapter 审查](./source-reference-recovery/adapter-review.json)。两位审查者仅只读核对各自子范围，未独立重做本执行客户 Runtime 探针。

[最小修复建议](./source-reference-recovery/diagnosis-and-minimal-plan.md) 已具体列出公开入口、字段/服务建议、选择器修正、内容等值要求、配置入口、失效阶段和必要回归，状态为**方案建议、未实施**。登记 finding 本身按拟议入口不改变 inventory/Mission/G0；随后重发内容引用按现有合同立即重开 G0，新 Blueprint 发布还会清除当前双硬门、PageDecision、Batch、acceptance、ReviewSession 和视觉下游等 heads。旧回执保留历史，但**没有可直接沿用旧 G0 的引用迁移入口**。新版本需真实对应审核回执，不伪造、不继承旧签名；这不表示用户撤销已确认内容或需要逐次重授同范围材料许可。本轮没有修改唯一四基线的已批准合同。

本轮只读探针前后客户 state SHA256 均为 `9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`，mtime_ns=`1789007522156646754`，revision19 未变。最终文档、链接、代码身份和 state 核验见[验证记录](./source-reference-recovery/validation.json)。这是 state 文件未变化及本轮零 Runtime 写命令的证据，不扩大成全 Runtime 每个文件均做前后比对。

当前代码候选仍为 `cfabfc1` 的业务实现；本轮只归档诊断和方案，未重跑源码全量测试，既有713/713、180/180证据仍按原提交与时间有效。C2 尚未完成；真实 Image 2、用户定版、忠实原生转换、PowerPoint 与 G3 均未建立，未开始 C3。

## 来源恢复 A / 供应方准备 B 接管（2026-09-10）

总控对精确候选 `ad1161170f90e3bba9972bd6413a2af9bad078ab` 接纳诊断事实，要求补齐 P1 图片内容排除后先独立规格Review，再按主计划§12.2既有授权连续实施 A，B 单独提交。总控审查派发回执位于其 `2a66` Worktree `产品代码/docs/validation/c2-dispatch/source-reference-recovery-controller-review-20260910.md`；该文件不替代本执行台账。

- 起点 HEAD=`ad1161170f90e3bba9972bd6413a2af9bad078ab`，分支=`codex/image-led-native-anchors`，Worktree=`28a9/PPT-codex-app`；git-dir 为共享仓库下 `.git/worktrees/PPT-codex-app8`，没有在 main、总控或C1目录实施。
- 已跟踪树干净，既有未跟踪两份总控分派文档原样保留：`dispatch-prompt.md` SHA256=`83c8329aca765b555c7c768a5bbfc3aa38ff08000af93007d342b91c884e54e1`，`dispatch-receipt.json` SHA256=`346170fb9f929ddaeb47daacdce1cc965827e8ce61708d5e119dd0cc76130365`。`产品代码/node_modules` 是指向原注册仓库同路径的共享依赖链接；不修改目标、不混入功能提交。
- A 补充规格：[正式finding与两层排除](../../superpowers/specs/2026-09-10-c2-source-finding-recovery-design.md)。固定登记入口及真实来源预检，与范围排除、明确图片内容排除同时进入正式链路；禁用字节从确切源重放提取，不能信任调用方hash或因更换对象/源文件而放行。规格独立Review尚待下文实录，不预写通过。
- B本轮仅真实入口只读定位、wrapper协议/单请求/unknown恢复、非敏感配置声明、不生图预检及离线验证、可审阅加载方案。真实配置、安装/加载、客户Runtime重发/G0、真实生图、merge/push均不执行。保留当前客户revision19、71段及真实G0；测试使用合成材料。

- A独立规格Review已通过，初审C/I=0/0、3处消歧已关闭，最终规格SHA256=`0e3bcc87d2d7100cc74c701b8e2a22dfbfd30209ce48609cd0892afb18141cde`；[审查与关闭记录](./source-recovery-implementation/source-spec-review.json)。实施前材料/OOXML/内容域基线45/45通过，仅作基线；A首轮RED及初始GREEN由实现子代理进行中，最终结果不预写。
- B采用标准库wrapper、纯文本helper、单次JSON/multipart请求与已识别wrapper专用不生图预检；独立规格Review两项精度建议已关闭，最终规格SHA256=`d71d749fbb3fa753afdcb640c06d7b025ec96931c536fcefcb7d5ec42913c5b2`。B规格/调查/审查将随B单独提交，当前不启动供应方请求或加载。

### A 固定实现与全量核验

A 业务候选基于 `ad116117`，由[25文件冻结清单](./source-recovery-implementation/source-code-freeze.json)逐项绑定，清单 SHA256=`7138cd5fb0570d5c8bdd6c7c13aa08ba1e60b362d526ae3ce2a39bf82db1f88b`。10份实现文件、15份测试/fixture文件；四基线、源码Skill与运行参考另行同步。此处不把代码完成、独立Review、本地提交、加载和真实生产验收混为同一状态。

- **正式入口**：既有 `add_ai_ppt_material` 增加闭合 finding 分支，明确要求项目及revision和六个来源字段；服务端核验当前inventory、真实源与selector，再派生content hash。固定 detached 事务只新增finding、事件与幂等回执，保留全部业务heads/Gate。text/url/bytes与proposal-led继续有效，不能重放的inline/URL来源保留CapabilityGap。
- **生产预检**：EvidenceBook、DecisionContext、Fit、Blueprint、两内容硬门及Image-led policy/pack/编译共同复验来源。空atoms也受保护；源字节被替换后不写pack/candidate、不触达adapter。公开MCP→Python→finding→四内容对象→双硬门→生产ReviewSession/批次→合成可信G0→逐字来源输入包的路径已实际执行，finding来自正式桥接事件，无Kernel预注入finding。该用例只证明合成环境，真实客户内容/G0没有重发。
- **两层排除**：源范围规则与明确图片内容禁用共同生效；禁止hash由当前排除finding重提取，不接受caller hash。33/36不同图片通过，39、同media其他对象、另一PPTX/独立图片同bytes拒绝；scope模式不扩大为内容禁用。页级declared可与局部排除共存，实际整页atom仍不能穿过排除范围。
- **调用内快照**：中间审查指出每finding保留独立完整源bytes的资源增长。新增计数反例后，8finding/3sources读取从8次降为3次；20atom完整编译从41次降为2次，分别是policy与batch的独立验证。快照不跨调用保存；下次改源仍报SOURCE_HASH，没有用长期缓存跳过复验。

新增18个Python测试方法、2个Node测试。首轮RED覆盖登记缺口、schema混用、符号引用、selector误判，追加P1、空atoms、调用内复用与公开projectRoot反例；[初始RED](./source-recovery-implementation/source-initial-red.log)、[schema RED](./source-recovery-implementation/source-schema-red.log)、[P1 RED](./source-recovery-implementation/source-p1-red.log)、[空包RED](./source-recovery-implementation/source-empty-pack-red.log)、[快照RED](./source-recovery-implementation/source-snapshot-red.log)、[批量RED](./source-recovery-implementation/source-batch-red.log)、[显式项目RED](./source-recovery-implementation/source-root-required-red.log)均保留。第二轮全Python720项的31个旧fixture错误分别为generation recovery inline来源9、framework discussion inline来源17、其他来源/符号ref5；改为合成真实源及正式finding服务后通过，未删业务断言、降低校验或新增skip。纯结构和明确损坏负例仍可使用符号制品。

| 固定源码验证 | 结果 | 原始证据 |
|---|---|---|
| 全Python | 731/731，OK | [日志](./source-recovery-implementation/source-python-final.log)，102.465s |
| 全Node | 182/182，0 fail / 0 skip | [日志](./source-recovery-implementation/source-node-final.log) |
| 前端Vitest | 755/755，16文件通过 | [日志](./source-recovery-implementation/source-vitest-final.log) |
| TypeScript | PASS | [日志](./source-recovery-implementation/source-typecheck-final.log) |
| Widget构建 | PASS | [日志](./source-recovery-implementation/source-build-final.log) |
| 相关Python / MCP聚焦 | 138 / 35通过 | [Python](./source-recovery-implementation/source-focused-final.log)、[MCP](./source-recovery-implementation/source-mcp-focused-final.log) |

[Python执行回执](./source-recovery-implementation/source-python-execution.json)和[质量执行回执](./source-recovery-implementation/source-quality-execution.json)保存命令、时间与日志hash。全量测试在 `/private/tmp/c2-source-recovery-validation-q0qmybek` 私有源码/依赖副本执行；未修改共享node_modules链接目标、真实插件或客户Runtime。首轮全量结束时[569文件清单](./source-recovery-implementation/source-tested-manifest.json)与原树逐项hash一致；随后文档/证据更新和I-01单测试增量按下段另记，最终25文件以更新冻结清单为准。该清单含未提交B文档的快照身份，不把它们算入A业务代码或A提交。

固定候选独立[规格Review](./source-recovery-implementation/source-final-spec-review.json)与[代码质量Review](./source-recovery-implementation/source-code-quality-review.json)均PASS，未关闭Critical/Important/Minor各0；规格审查保留I-01发现/关闭历史，另实际执行42 Python、2 MCP及1个新增P1集成用例。本轮只读客户state仍为revision19、SHA256=`9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`、mtime_ns=`1789007522156646754`，与接管前相同。此证据仅覆盖state文件，不冒称全Runtime树逐文件相等。实际供应方、当前宿主新协议、原生转换、PowerPoint及G3仍未由本轮建立。

固定规格审查曾发现 **I-01：P1别名在pack登记/生成入口的直接集成证据缺口**，分类为测试覆盖缺口而非已复现源码缺陷；[发现报告](./source-recovery-implementation/source-spec-interim-review.json)保留。实现者只补一个测试，使用正式finding/内容/硬门/ReviewSession/批次/合成可信G0和授权，三类图片别名在compile/register_pack/generate九种组合全部EXCLUDED，逐次完整测试Runtime文件快照相等，adapter factory计数0；33/36正例通过。[直接GREEN](./source-recovery-implementation/source-p1-boundary-direct-green.log)没有虚构RED。生成入口仅在negative setup放入旧/损坏current pack以验证消费者独立拒绝，不代表该pack曾通过生产登记，也未注入finding、禁止hash或mock resolver。[增量身份记录](./source-recovery-implementation/source-p1-supplement.json)证明其余24冻结文件原字节未变；此前730项全Python随后以731项重新全跑通过。Node、前端、类型和构建的业务源码与测试入口未变化，沿用同源码证据。

A提交前[最终核验](./source-recovery-implementation/source-final-validation.json)记录源码/文档/证据身份、相对文件链接和继承文件保留情况；B规格/调查/审查/加载方案及两份原分派文档和共享node_modules不进入A提交。A不修改客户Runtime，也不安装、真实生图、merge或push。

提交前对新跟踪文件执行staged whitespace检查时，发现reader尾部多一个空行及Vitest原始日志EOF空行。reader仅删除一个末尾换行，AST及其余24文件完全不变；[格式增量身份](./source-recovery-implementation/source-formatting-supplement.json)绑定前后hash，两位独立审查者均已补验当前身份并保持PASS，规格[独立格式核验](./source-recovery-implementation/source-spec-formatting-identity.json)同时归档；原731/182/755行为证据继续适用，不重复全套。原始日志保留精确字节，后续whitespace检查只排除本证据目录raw `.log`，不改写测试输出来迎合格式检查。

### B 供应方准备实施启动

A已本地提交为 `7b0a24a1ac1e568ccb0a9af18a018fbf052dec93`；提交后已跟踪树干净，B的规格/调查/审查/加载方案和三项继承未跟踪内容保持在提交外。B由新的实现代理在同一分支/Worktree承接，root维护四基线、Skill、加载方案与唯一台账。B按[已审正式规格](../../superpowers/specs/2026-09-10-c2-image2-provider-preparation-design.md)实现；本轮只使用假helper/HTTP及合成项目，真实认证、网络、生图、宿主配置、安装加载均不执行。

[加载方案](./source-recovery-implementation/provider-loading-plan.md)经只读审查补齐当次bridge解释器身份、nonce/包装器hash核对及公共`generationIntent`/`generationRequestId`恢复语义。候选代码和临时包身份在B完成后绑定，不将该准备方案标为已加载。B全量核验将使用独立私有源码/依赖副本及私有npm缓存，显式启用offline并关闭audit/fund；不修改共享依赖或真实插件。

总控已独立核验A提交对象中的65个文件hash和验证证据，允许进入代码审查/集成准备队列，并要求B提交前修复当前A Vitest日志的EOF空行。按最新指令仅删该日志末尾空行，原始字节继续保存在A不可变commit对象；[日志格式变更回执](./source-recovery-implementation/provider-a-log-format-followup.json)给出前后hash与读取命令，不改写A历史manifest或冒称重新运行A测试。当前四基线/Skill/台账及日志已含B后续变动，A的clean与hash一致性仅按A提交对象认定；B最终执行不排除日志的普通diff whitespace检查。


### B 固定实现、离线验证与临时包

B 承接 A `7b0a24a1ac1e568ccb0a9af18a018fbf052dec93`，继续同一 `codex/image-led-native-anchors` / 28a9 Worktree。最终代码与测试由[11 文件清单](./source-recovery-implementation/provider-code-freeze-final.json)固定，SHA256=`fef15d41bb64a561b051d26b7783e4eace04afa0fe7deacb056f007f43e6be8c`；原 10 文件冻结、旧 manifest 测试修订和最终路径夹具修订各自保留历史。四份基线、Skill 与运行流程同步本地预检及单请求边界，不新增已验收 UI 或同范围授权步骤。

- **包装器**：新增独立标准库 `image2_crs.py`；先验证闭合协议、固定 CRS / gpt-image-2、逐字文案及 MIME/base64，再进入认证。无图一次 JSON，有图一次 multipart；图片原字节、顺序、用途及共同规范保留，内部身份不进入外发提示词，不引入旧 C1 提示词或正文构图模板。仅真实生成分支可执行固定 helper，随后一次 HTTP；禁止重试、重定向、切换和 URL 图片下载。结果缺少有效远端请求 ID 时，只建立实际响应字节的本地 hash 收据。
- **当前进程预检**：既有 snapshot 增加可选布尔 `includeImage2Preflight`，工具数仍 43，默认及 false 兼容。只有当次 Python 解释器和当前包脚本的确切路径可启动 `--preflight`；同名伪装、陌生命令或多余参数不执行。闭合返回配置 presence、能力分类、wrapper hash 和 nonce；固定 `external_connection=not-tested`。预检不读 helper 内容、不执行 helper、不请求网络、不创建业务版本；manifest 只声明四键转发，没有写用户值。
- **恢复与证据边界**：既有 G-01/G-02 单次请求与 unknown 原 ID 恢复保持。23 项新增 Python 与 3 项新增 Node 测试使用合成输入；实际临时 MCP → Python → 包装器预检覆盖 manifest 传递、默认兼容、伪装拒绝及完整合成 Runtime 文件/目录树不变。包装器错误日志不回显凭据、客户文本或原始供应方响应；合成 helper 超时用例验证直接子进程已终止并回收，不声称递归终止全部后代。

| B 固定候选验证 | 结果 | 证据 |
|---|---|---|
| 全 Python | 754/754，OK | [日志](./source-recovery-implementation/provider-python-full.log)，110.121s |
| 最终全 Node | 185/185，0 fail / 0 skip | [日志](./source-recovery-implementation/provider-node-full-final.log) |
| Vitest | 755/755，16 文件 | [日志](./source-recovery-implementation/provider-vitest-full.log) |
| TypeScript / Widget 构建 | PASS / PASS | [类型](./source-recovery-implementation/provider-typecheck-full.log)、[构建](./source-recovery-implementation/provider-build-full.log) |
| 实现者最终聚焦 | Python 56 / Node 52 通过 | [冻结与执行信息](./source-recovery-implementation/provider-code-freeze.json) |
| 路径夹具修订 | 默认 macOS TMPDIR 与 /private/tmp 各 3/3 | [默认目录](./source-recovery-implementation/provider-path-default-green.log)、[规范目录](./source-recovery-implementation/provider-path-private-tmp-green.log) |
| 保留离线 Skill / Plugin 包 | 两包包装器同 hash；Plugin 3763 项全部核对 | [验证](./source-recovery-implementation/provider-package-validation.json)、[独立包复验](./source-recovery-implementation/provider-spec-package-verification.json) |

[测试身份核对](./source-recovery-implementation/provider-tested-identity.json)验证原树与私有副本的 356 份执行输入一致；初始快照后仅两份 Node 测试改变，最终全 Node 已在两项修订同步后执行。生产、Python、Widget 与 Skill 字节不变，因此沿用已通过的 754 Python、755 Vitest、typecheck/build 结果，不重复无影响的检查。全部全量检查在 `/private/tmp/c2-provider-preparation-validation-ztxhptxc` 私有源码/依赖与 offline 缓存中执行；共享 node_modules 链接及其目标不由本轮修改。

**发现及关闭历史**：B-M02：首轮全 Node 184/185，旧 `plugin-shape` 精确数组期望只列两个 Python 键；按已审合同补入四个 Image 2 键并保留 `deepEqual` 后通过，未加 skip 或放宽断言。独立规格审查发现 B-M01：默认 macOS 临时路径别名使成功夹具被生产严格路径规则正确拒绝；只将测试临时 base 规范化，默认和 /private/tmp 环境均复验通过，生产识别规则未改。[中间审查](./source-recovery-implementation/provider-interim-spec-review.json)保留发现，[日志索引](./source-recovery-implementation/provider-focused-log-index.json)区分真实实现 RED、旧 schema 期望、共享依赖导入超时与合成 helper 夹具失败；名为 recursion-red 的历史文件实际是 helper.pid 夹具缺失，不冒称深 JSON 产品 RED。

**原始日志身份**：B 的 `.log` 作为通过普通空白检查的人类可读视图；若去除行尾/EOF 空白改变字节，同名 `.raw.json` 保存原始 base64、原始 hash 和视图 hash。执行回执继续绑定原始日志 hash，不把格式处理冒称重新测试。A 的历史 manifest 与 commit 对象保持原样；仅按总控要求把当前 A Vitest 日志 EOF 空行修订随 B 提交。

[加载方案](./source-recovery-implementation/provider-loading-plan.md)绑定真实离线临时包、包装器及源码清单。打包没有安装、加载或修改宿主配置。历史 `scripts/image-led-native.mjs` release allowlist 缺口仍明确保留，后续完整原生部署前由总控处理；包装器入包不等于全原生发布路径完整。

B [独立规格 Review](./source-recovery-implementation/provider-final-spec-review.json)已 PASS，17 项要求核验，未关闭 C/I/M 为 0/0/0；[独立代码质量 Review](./source-recovery-implementation/provider-code-quality-review.json)亦 PASS，未关闭 C/I/M 为 0/0/0；其另行实跑 1 项深层畸形 JSON 用例通过。提交前[最终核验](./source-recovery-implementation/provider-final-validation.json)绑定本提交的源码、文档、日志、包和审查身份；本记录随 B 独立本地候选固定，确切 SHA 与提交后状态由 Git 对象及总控交接回执核验。当前桌面新预检、真实凭据/helper、CRS 网络/实际生图、客户 Runtime 来源迁移、用户图像定版、原生转换、PowerPoint/G3 均未由本轮建立；不合并或 Push。


B 提交前只读客户 state 再核对：revision 19，SHA256=`9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`，mtime_ns=`1789007522156646754`，与 A/B 接管前一致。该证据只覆盖 state 文件字节及修改时间；不扩大为全客户 Runtime 文件树相等。两份继承分派文档 hash 与共享 node_modules 链接目标仍保持，不进入 B 提交。最终 staged 空白检查覆盖全部文件与日志，不沿用 A 的 raw-log 排除方式。

## B 核验后的加载、宿主预检与来源迁移准备（2026-09-10）

总控任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 已独立接纳 A `7b0a24a1ac1e568ccb0a9af18a018fbf052dec93` 与 B `fe3fb613673c0c70e7633a384252939365d9b7fa`：A 65 项 commit-object 核验、B 11 文件 freeze 与 754 Python / 185 Node（0 skip）/ 755 Vitest / typecheck/build、规格 17/17 与质量 Review 均属既有固定候选证据。最新派发只要求**只读准备加载/宿主预检和来源迁移方案，固定文档、独立 Review，再回传总控**；不是本轮实施打包修复、安装或客户迁移的指令。继续同一 Change、`codex/image-led-native-anchors` 与 28a9 Worktree，不新开 Change，不重索已有材料或同范围授权。

[受控实施方案](../../superpowers/plans/2026-09-10-c2-controlled-loading-and-source-migration-plan.md)确定后续四阶段：L1 关闭 Plugin 原生发布清单缺口并固定新包；L2 受控加载及真实宿主只读预检；M1 六条正式 finding 登记与对账；M2 保持当前完整内容的引用迁移及新版本审核/G0。本轮以下核查不构成四阶段已执行的记录。

- **打包与候选身份**：[只读打包审计](./loading-migration-preparation/packaging-audit.json)核定 B Plugin/Skill 压缩包原 hash 未变，二者仍漏原生脚本。cfab cache 的脚本是历史同提交补件，构建器 allowlist 和 required-file 验证缺口仍存在。下次桌面加载收敛为 Plugin-only，未来只修发布清单/验证/测试，不修改 renderer 设计逻辑。Skill 的完整 native 因 `runtime` / `src` 布局差异继续为 NotReady，不把 wrapper 入包证明扩展成完整转换。后继候选必须有新的确切修复 commit、版本、逐文件映射、manifest 与压缩包 hash；不手改 B 冻结包后沿用旧身份。包内模块三页合成 render/verifyOutputSnapshots 及负例已列为未来验证，本轮只对审计中的脚本作 syntax-only 检查，未执行转换。
- **真实宿主观察**：本轮两次真实默认 `get_ai_ppt_project_snapshot` 均成功读取 revision 19、G0=`passed` / G1=`open` / G2–G4=`locked`，保存[身份快照](./loading-migration-preparation/native-snapshot.json)。[文件/进程记录](./loading-migration-preparation/host-files-and-processes.json)发现五个 Node 共用 cfab cache cwd；[snapshot 窗口采样](./loading-migration-preparation/host-snapshot-process-correlation.json)仅观察到 Python 65838 / 父 Node 48151。此为时间相关，不是工具请求与 PID 的唯一绑定，也不证明实际环境或 `sys.executable` 拼写。当前 cache 新 wrapper 不存在；本轮 `includeImage2Preflight=true` 为 **NotRun**。候选解释器的独立 `find_spec` 只探可解析性，不作为实际 MCP 环境证据。后续拟显式固定 B 验证用 bundled Python 3.12.14，真实进程重连后再用 nonce、wrapper hash、四键 presence 和 helper 可执行布尔建立本地预检；仍不执行 helper/HTTP。
- **真实来源等值**：[来源迁移审计](./loading-migration-preparation/source-migration-audit.json)核定两份真实 PPTX、三页及 71 个精确文本对象，与现行 EvidenceBook、Blueprint 及已认可准备输入逐字一致，三页段落数 16/36/19，原文、标题、页序、目标、阅读问题与共同规范保持。33/36 的可用图片及 39 禁用图片均按源重提取并验证 hash；S06 的 19 个文字对象与禁用图不相交，整页原子仍相交。六条登记是明确材料角色的方案，不是 schema 数学下限；71 段无需另登记 71 条 finding。144 项逐上下文映射与所有计划 refs=null 已固定，不能用预测 ref 冒充回执。
- **完整字段与失效边界**：172 项比较中 168 项相等，四项 whole-object 不等全部解释为准备稿缺少当前 `identity` 或 material view 来源/用途等字段，未解释业务差异为 0；不能用窄投影覆盖当前四对象。来源映射、上游 refs、统一版本、正式服务必要元数据与落实已认可禁图是具体技术差异，未来新 payload 等值验证仍为 **NotRun**。六 finding 登记保留 heads/G0；Evidence 发布立即 G0=open，Blueprint 随后清理当前九个审核/确认 head；Mission/materials/不可变历史保留。现有合同没有可信“换引用保留旧 G0”入口，需新版本真实 ReviewSession/PageDecision/Batch/G0。公开 add-material 没有 commandId；丢回执先读事件及 detached artifact 对账，不能声称能强制原 ID 重试、补写 Kernel 或回滚 state。

[作者自检](./loading-migration-preparation/author-check.json)和[只读身份验证](./loading-migration-preparation/pre-review-validation.json)区分作者检查与独立 Review。验证直接比较 B 提交对象中的 **356** 份源码、测试、四基线、Skill/MCP 等输入，0 字节差异；方案和四基线/唯一台账的相对文件链接均可解析，6 处原型引用存在。两份继承 dispatch 文档及共享 node_modules 链接原样保留。客户 state SHA256 仍为 `9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`、mtime_ns=`1789007522156646754`。本轮来源审计至身份验证的 **99** 项 Runtime 文件/目录投影 hash 前后均为 `74c787bfde6725ea37d0a30d697651435d38b9a36b927990782e01194806c2c8`，覆盖路径、模式、文件尺寸、mtime、内容 hash 与符号链接目标 hash；该全树证明始于本轮来源审计采样，不能反向扩展为整个 A/B 期间都做过全树对比。

本轮不重复 A/B 全量回归；其结果继续绑定原提交。生产修复、新包构建、真实安装/配置、helper/HTTP、客户 finding 登记/内容重发/迁移、真实生图/原生转换均 0 次。独立 Review 与最终固定回执在本节续记；不把方案交付说成 C2 完成、真实 PowerPoint/G3 或 C3 开始，不 merge/push。

最终方案独立审查15/15 **PASS**，未关闭C/I/M为0/0/0：[固定Review](./loading-migration-preparation/independent-review.json)，SHA256=`a482cbf08989e044b3353c0f91fdc259d7ddbd4b0b016ead19bebc4bfea6d74c`；绑定方案SHA256=`447c26749a22a3e06ad5dd83ae05d08738c161d591c9d076318adce040e0ba9c`。审查者未参与本方案及两份本轮审计写作，其历史B实现参与已披露；10项审查输入与14条源码证据（11个去重文件）hash一致。root收件时发现初稿将证据条目称为文件，审查者只更正计数标签和说明，未改变方案或PASS结论；[初稿](./loading-migration-preparation/independent-review-initial.json)原字节保留。

[最终文档验证](./loading-migration-preparation/final-validation.json)与[固定文件清单](./loading-migration-preparation/manifest.json)绑定本轮交接内容。此次只作独立本地文档提交，提交SHA及逐项commit-object复验由提交后回执交总控；L1/L2/M1/M2仍待其按既有Change安排。方案审查通过不自动触发安装、加载、迁移或新版本G0，也不要求重交已接受材料。

## L1 Plugin 原生发布完整性实施（2026-09-10）

总控核验 `b3cda4e03ed2ecaa62d63b393bb2adc726864fd9` 的方案、manifest、独立 Review 与空白检查后，按主计划§12.2派发本轮 **L1**。继续同一 C2 Change、`codex/image-led-native-anchors` 与 28a9 Worktree；允许发布清单/验证/打包与预检测试、私有回归及包内三页合成正反例、独立代码 Review 和新候选包身份固定。L2加载/配置、真实helper/HTTP、客户finding/内容/G0迁移、真实生图/客户原生转换/PowerPoint、merge/push均未授权为本轮执行项。已审方案中的合成native验证是明确测试范围，不作为客户原生制品或设计验收。

私有验证目录为 `/private/tmp/c2-l1-validation-b4pbxmd2`，源码起点由上述提交 `git archive` 提取，独立复制已验证依赖和offline npm缓存，客户Runtime及原B包不进入该目录。开始时客户revision19/G0 passed，99项目录投影hash仍为`74c787bfde6725ea37d0a30d697651435d38b9a36b927990782e01194806c2c8`。共享node_modules及两份继承dispatch文件保持，不纳入L1提交。

基线聚焦4/4、0skip通过。第一次工具自动审批复核超时未启动测试，随后启动器文件缺失已修正；首次实际运行的私有PATH缺少npm，3通过/1环境失败已单独保留，补入已有真实npm路径后4/4通过。以上均不作为产品RED。新增测试的正式RED为8项中5通过/3失败/0skip，分别命中包manifest缺native hash、builder未携带脚本和刷新合法manifest后缺文件未被拒绝；原始日志`l1-red.log` hash=`569bf1158a79c71a4079efb8a12696d1c493c9106804f6d6f8103b0c955d96d6`。生产仅按已审方案补发布allowlist与required-file项，最终GREEN、完整回归、审查与包身份以本节后续固定证据为准。

### L1 完整回归固定结果

生产变更仍仅为 builder allowlist 与 verifier required-file 两个列表项；另外两份测试改用真实offline npm构包，并从包内导出执行3页synthetic及本次PPTX重新核验。[四文件冻结](./plugin-native-release-l1/code-freeze.json)SHA256=`db9945ec535819516f07f2d823921322bfc0fc8a9949ea6f34b9f6fc7f959c23`，[实现报告](./plugin-native-release-l1/implementation-report.json)记录两种TMPDIR各8/8、0skip和全部反例。首次GREEN中的sharp未导出package.json、SDK stdout不能整体当JSON两处均为新增夹具错误，后续只修测试后通过；原始日志完整保留，未扩大生产修改。

[完整回归](./plugin-native-release-l1/full-regression.json)本轮实际通过：Python **754/754**，Node **186/186、0skip**，Vitest **755/755、16文件**，TypeScript与Widget构建均PASS。[356项执行输入清单](./plugin-native-release-l1/tested-source-manifest.json)在执行前后与Worktree、私有副本字节相同。全Node首轮185/186的唯一失败来自总协调测试runner设置的全局AI_PPT_PYTHON覆盖旧EACCES候选夹具，单变量复验在覆盖存在时失败、仅去掉该覆盖时通过；[诊断](./plugin-native-release-l1/node-env-diagnosis.json)与首轮完整日志保留。修改仅在/tmp runner，生产与测试字节未变，随后186项重新全跑通过。独立诊断按test-name筛选，不将其非目标项跳过混入最终0skip全套证明。

[日志索引](./plugin-native-release-l1/log-index.json)区分可读log与同名raw.json：后者保留原始base64与SHA256，执行回执继续绑定原始字节；可读视图仅去掉行尾/EOF空白，未改测试结果或冒称重跑。[独立规格Review](./plugin-native-release-l1/spec-review.json)23项PASS、C/I/M0，[独立只读包审计](./plugin-native-release-l1/spec-package-readonly-audit.json)核两份临时包各3764项manifest、无symlink，以及各21项输出hash与既有二进制输出字节。它们仍是0.4.0合成测试包；后继固定版本包将在代码审查通过并固定源码提交后另建，不冒称已加载。

独立[代码质量 Review](./plugin-native-release-l1/code-quality-review.json)已完成：14 项 PASS，未关闭 C/I/M=0/0/0，SHA256=`25bd42592d0f1aa269ecc79167a57294ff7b0220d21fbb7ef064d847a8f9cb17`。审查者重新核对四文件、356 项执行输入、两个临时包和15组原始/可读日志，未重跑功能套件；没有要求修改冻结实现。[源码阶段最终验证](./plugin-native-release-l1/code-phase-validation.json)核定相对链接/原型有效、客户99项完整投影和revision19/state时间身份保持、B两份旧压缩包及继承文件未变。随后先固定L1源码提交，再由该确切提交离线构建具有独立版本的新候选；包身份和包内合成复验将在后继证据提交中记录，不把0.4.0测试包当作该候选。

### L1 后继候选审查与打包补正

源码提交 `e01b98bdd1ae280bccb1e765b5252d169be638f1` 已通过53项commit-object复验。其新候选 `0.4.0+codex.c2.e01b98b.20260910` 的目录manifest为 `61cfd45de45f16482483d512bccd674a53b31d7f14183eeba6ea8f8b57124d51`，3764项匹配；包内3页synthetic及本次PPTX复验、9项native反例、2项required/tamper反例均通过，详见[原候选回执](./plugin-native-release-l1/fixed-candidate-e01b98b/candidate.json)。首次构包验证因外部validate_plugin.py缺少已有私有YAML依赖失败；修正仅限临时验证器env，native仍从empty cwd、无PYTHONPATH/PYTHONHOME执行。[源码提交回执](./plugin-native-release-l1/code-postcommit.json)及全部失败/成功日志保留。

**原候选不通过最终包验收**：独立包Review和root分别核实两项发布缺口。其一，mcp整目录allowlist继承带入唯一第一方测试 `mcp/test/get-visual-review-projection.test.mjs`，verifier只禁止根tests/；生产依赖另外含230项测试路径，不能对它们作未经验证的全局裁剪。其二，临时runner的macOS tar引入4361项AppleDouble，原压缩包SHA256=`93519862269c05a5e8c5d153343ca57020d9ebc2b2cbecd6538677b31f8b846c`，与目录manifest不能一一对应。原包和版本完整保留，不作为最终候选或L2输入。[归档诊断](./plugin-native-release-l1/fixed-candidate-e01b98b/archive-portability-diagnostic.json)验证Python tarfile可建立3765文件与manifest加自身的精确对应；这只是修复方法验证，不补写旧包PASS。

总控于2026-09-10按2a66执行记录第10节明确批准同一L1补正，无需新Change或用户重授权：仅builder按源根相对路径目录边界排除mcp/test及后代、verifier禁止mcp/test/、发布测试覆盖不同/嵌套测试注入后合法manifest仍拒绝；方案§2.2明确第一方排除与第三方完整保留。临时归档runner必须校验成员集合、重复项及逐项hash，保留旧tar为RED并新增额外成员拒绝反例。后继以新源码提交另建版本、manifest和archive，重新完整Node（0skip）、正式verifier/probe、包内3页和全部新旧反例；未变Python/Widget/类型/构建证据按精确输入身份复用。实现与最终包分别独立Review；仍不执行L2、客户转换/来源迁移/G0、helper/HTTP、安装配置、merge或push。

[补正三文件冻结](./plugin-native-release-l1/packaging-closure/code-freeze.json)SHA256=`8524adb4349e4b15a105c002c8cd6be5f8e67cf32c0dee0f850c3f8a60bdf260`，[实现回执](./plugin-native-release-l1/packaging-closure/implementation-report.json)记录RED7通过/3预期失败/0skip、两TMPDIR各10/10及仓库原MCP测试1/1；新临时包仅移除该第一方测试，3622项第三方依赖路径/hash与旧候选相同。[新全Node](./plugin-native-release-l1/packaging-closure/node-full-execution.json)实际188/188、0fail/0skip，31.973s；原始logSHA256=`b60fae41d68476701dea2905df63c29344085cdbf93f753cb27151305500bddc`。首次受沙盒127.0.0.1监听EPERM阻断，完整失败日志与回执已保留；只调整执行权限后重跑，无源码或测试变动。

[356输入身份](./plugin-native-release-l1/packaging-closure/tested-source-manifest.json)在新全Node前后均匹配Worktree和新私有副本，其中353项与首轮L1完全一致；按总控明确范围复用754Python、755Vitest及typecheck/build的既有固定证据，不冒称这些套件在补正后又全部重跑。[归档检查器](./plugin-native-release-l1/packaging-closure/archive-guard.py)是证据侧临时构包工具，非生产插件逻辑；旧AppleDouble归档明确拒绝，portable正例以及额外成员/重复成员/成员字节篡改三反例已实跑验证，后继最终包仍须重做同样验证。

补正[独立规格Review](./plugin-native-release-l1/packaging-closure/spec-review.json)18项PASS，SHA256=`d9c78d55ff7fad58a933792648d39e97f0de09392983aeba3fa36f48e41afe52`；[独立代码质量Review](./plugin-native-release-l1/packaging-closure/code-quality-review.json)12项PASS，SHA256=`426b7531fc4c3c6442b3863a63a3f03a4f91545dd02024347faca0bbd82bd5bc`，两轮未关闭C/I/M均0/0/0。它们绑定相同3个源码/测试文件、3个证据脚本和已核验的执行输入；不覆盖尚未产生的新版本候选。源码阶段随后以独立本地提交固定，再按新commit派生最终候选，并在后继证据提交中记录包Review及确切身份。

### L1 最终固定候选 0949867

补正源码提交为 `094986754df67384536117c0d3693cd8a18271c3`，[提交后回执](./plugin-native-release-l1/packaging-closure/code-postcommit.json)重新核对79项Git对象与普通空白检查。[后继候选报告](./plugin-native-release-l1/packaging-closure/final-candidate-0949867/candidate.json)SHA256=`0624b2bc07e8d30ed49ebb89ad856f061121d7dbb98e2308017e5c1f37ec6c90`，版本为 `0.4.0+codex.c2.0949867.20260910`，由该确切提交git archive后离线构建；源码映射140项，唯一包装语义差异为plugin.json.version。包目录manifest SHA256=`ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`，3763文件全部匹配，第一方mcp/test不存在，3622第三方依赖文件与旧候选字节一致。

最终压缩包位于 `/private/tmp/c2-l1-validation-b4pbxmd2/candidate-0949867-closure/ai-ppt-studio-0.4.0+codex.c2.0949867.20260910.tar.gz`，SHA256=`b6efefe6678052ab785f5596ede233fd94d487ec47d0b59de7ec2bb881291266`。标准库tarfile经冻结的证据侧guard生成；4359项成员中3764个普通文件恰等于manifest加自身，其余为预定对应目录，无额外/重复/不支持类型，无AppleDouble。新增额外成员、重复成员、成员字节篡改三反例在该确切新包上均按对应原因拒绝，原archive hash保持。

构建、刷新manifest、首次完整verifier/probe、包内Python来源、native正反例、包完整性反例、最终完整verifier、archive及archive反例共九条命令全部exit0。其间实际执行包内3页native render及当前PPTX复验、9项native反例、缺脚本刷新manifest/篡改/直接与嵌套测试注入4项包反例，以及3项归档反例。本次synthetic PPTX SHA256=`e395f26b6a21da5d65aee626c9036ee9cd7865b94e3a9881b445e9af603c08a9`，3页重新核验，仍为工程合成制品，用户验收和PowerPoint证据NotEstablished。执行命令、原始日志与可读视图均单独归档；独立最终包Review随后固定。本轮从未把旧e01b98b候选的两项FAIL改为PASS，也不把新包验证说成L2已安装/加载。

最终[独立包Review](./plugin-native-release-l1/packaging-closure/final-candidate-0949867/independent-package-review.json) **PASS，16项通过，C/I/M=0/0/0**，SHA256=`3e1dab053b0a5b97e03cd3e2f554958a6ba1831142dd8a0e0e1c776127c66fc0`；[逐项只读审计](./plugin-native-release-l1/packaging-closure/final-candidate-0949867/independent-package-readonly-audit.json)SHA256=`00e6c4f7b78400fc4ec452edfbcc6ac8a8944b8f05d78d3c43a78d07d08699a2`。两项旧finding在0949867后继候选上关闭；原e01b98b候选FAIL和旧archive原样保留。审查独立核定source/140映射/3763manifest/3622依赖/3764归档文件、16个反例、当前3页PPTX/21输出及既有accepted.bin，无未关闭问题；未重跑功能套件或接触真实宿主、客户、HTTP/helper。候选构建回执中的pending仅为构建采样时状态，最终接受状态以此独立Review为准。

**L1工程候选已完成并可交总控核定**；本结论仅覆盖已固定源码、经审查的Plugin目录/压缩包及合成验证。客户最近一次完整字节核验为2026-09-10 07:17:21 UTC，当时revision19/G0 passed与99项文件/目录投影保持；收尾时当前全树内容哈希的可用性限制见下一段，不冒称已重复取得新鲜字节证明。L2安装/加载和真实宿主预检、M1正式finding登记、M2内容链迁移与新版本G0、实际Image2请求/客户原生转换/PowerPoint均为本轮NotRun，不merge/push。完整Skill native仍不属于本轮候选。后继证据提交只归档身份与最终验证，不改0949867源码或将新包重标为证据commit构建；确切证据commit及提交后Git-object核验另交总控。

**最终文件可用性限制**：[只读核对回执](./plugin-native-release-l1/packaging-closure/customer-final-read-limitation.json)于07:35:38 UTC核定99项路径/模式/大小/mtime及链接元数据仍与起点相等，但63个普通文件均带本机SDK定义的`SF_DATALESS=0x40000000`；尝试读取第一个已有artifact JSON等待后报`OSError errno89 Operation canceled`。因此本次收尾的全树内容hash为**NotEstablished**；07:17:21 UTC的完整字节校验记录保持有效历史身份，不能提升为07:35的新读证据。仅停止本任务3个等待中的验证子进程，并作1次有界非受限读取复核，同样收到errno89；未手动下载、恢复或改写客户文件，未调用真实MCP/供应方或改变Gate。最终工程核验分别记录源码/42组日志/链接/旧包保持与这项客户文件可用性限制；总控进入涉及客户文件的后续阶段前须先恢复可读并重新核验。

**总控最终接纳（07:37:30 UTC核验）**：总控已独立读取0949867实际候选，核定3763项manifest、3764个归档普通文件及595对应目录，无AppleDouble/额外/重复/类型/hash差异；已读取16项PASS、C/I/M0的独立最终包Review，并在总控说明第11节接纳新包核验。[总控原始核验回执](./plugin-native-release-l1/packaging-closure/final-candidate-0949867/controller-package-check.json)SHA256=`3e238b1f166ad56cf6fe62bf290091dadd22bfda423d49d2bfea0ce21485cd93`。其回执明确未读客户bytes，且总控本轮Git对象复核未完成；不替代执行方已完成的源码Review与提交对象核验，也不将metadata相等提升为新鲜内容hash。总控允许按现时可用性限制完成L1，不要求强行恢复/重读，不撤销或重开历史G0。最终包证据已由`7f598eba9d0bd0f2f6bd4cacb9a0fe48398603a5`固定，40项commit-object及普通空白检查通过；本条与总控回执仅作后继文档补充，不改变源码0949867、包版本或压缩包hash。

## L2 实际安装检查点与配置待决策（2026-09-10）

**历史检查点说明：** 以下为 08:38:40 UTC 的当时事实，原证据字节保留。其配置二选一、旧 catalog 与未应用配置描述已由下文新授权和实证更新，不作为当前阻断。

**状态：`installed-config-design-decision-pending`。** 总控于 `2026-09-10T08:38:40.160049+00:00` 固定[原始检查点](./host-installation-l2/l2-checkpoint.json)，SHA256=`153976095e557ff769669d0b15d93a0d491c493e0bc0c1c45e74fe0721cc15f3`。本次一次性更新唯一台账，并核验检查点引用的 **20/20 份证据文件 hash 全部一致**；对保存的 L1 与恢复后身份投影另作逐项比较。[安全身份核验摘要](./host-installation-l2/verified-evidence-summary.json)记录核验范围与结果。本次没有重读客户文件、调用现场 CLI/MCP、运行安装器或修改宿主；以下安装和真实读取事实来自已固定的总控证据，不冒称本任务重新执行。

| 检查项 | 已核定事实与证据边界 |
|---|---|
| 客户原文件可读性 | 63 个普通文件全部恢复可读，dataless 剩余 0；99 项路径、mode、size 与文件 SHA256 均与 L1 原投影相同。36 个 `mtime_ns` 差异为 **-119～+111 ns**，没有手改时间；这 36 项是时间戳差异计数，不等于目录计数。 |
| 客户树与业务身份 | 包含 mtime 的历史树 hash=`74c787bfde6725ea37d0a30d697651435d38b9a36b927990782e01194806c2c8`；恢复后树 hash=`c9bb0c3714f6eaae5bca3c3acbbae2f853d29d49509a5c5660c739bc77a1b25d`，不能称两者完全不变。state SHA256=`9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`，revision 19，G0 passed / G1 open / G2–G4 locked 保持。 |
| 新包物理安装 | 版本 `0.4.0+codex.c2.0949867.20260910`，3764 文件（含 release manifest）逐项匹配受审包；manifest SHA256=`ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`。首次安装校验因 bundled Python 缺 YAML，在写目标前失败；重试只在安装校验进程复用既有临时 YAML 6.0.3，未配置到真正宿主。 |
| 新缓存发现 | 新缓存 3764 文件与受审包匹配。总控准备复制前发现新目录已存在、旧目录已消失，停止复制；当时没有显式 `plugin add`。[缓存观察回执](./host-installation-l2/cache-refresh-observation.json)保留 `actor=NotEstablished`，不再追查或推定执行者。 |
| 旧路径恢复与版本发现 | 原旧安装与旧 cache 的 3762 项文件 hash 相等；总控用该备份在版本扫描树外建立 `old-cache`，旧版本原路径通过 symlink 指向相同字节恢复副本，未改版本、manifest 或源码。实际 desktop CLI 选择新 0949867 真实目录并返回六个 `env_vars`；旧链接仍能访问 3762 个相同文件。该链接按恢复点管理，不表述为 OS 强制只读。[缓存身份与恢复回执](./host-installation-l2/cache-identity-and-recovery.json)明确 CLI 发现不等于当前真实连接加载。 |
| 真实当前默认快照 | 当前真实 `get_ai_ppt_project_snapshot` 成功返回 revision 19、G0 passed、G1 open；既有三页决定、Batch 和 G0 confirmation 保持。[快照后身份回执](./host-installation-l2/customer-after-default-snapshot.json)确认安装及默认快照前后，恢复后的完整 99 项树（含 hash/mtime）相等。普通快照成功不代替新连接预检。 |
| 宿主配置与新连接 | `config.toml` 字节未变，SHA256=`be239566b49e4a6cd80030fd0de37bcb8a4f3ecbbb0769f9bf84b6a94df20600`。仅准备配置草案，未应用；当前工具 catalog 尚无 `includeImage2Preflight`，新实际连接加载 `NotEstablished`，两次 nonce 协议预检 `NotRun`，外部连接 `not-tested`。 |

**待用户决策的配置路线**：一是推荐在同一 C2 完善插件自身的持久配置加载，经源码审查后形成后继包；二是明确使用临时本机同名完整 transport。已核定后者会替换插件 transport，插件停用、插件服务器停用及插件工具名单不再直接约束该顶层项，停用、策略及后续升级需要同步维护；不能把它写成透明的环境变量覆盖。当前两条路线均未实施，不把待选择写成已批准，也不新增 Change 或任务。

**范围与归档边界**：本段承接总控 2a66 的 `source-reference-recovery-controller-review-20260910.md` §14，原始 20 份证据仍由 `/private/tmp/c2-l2-host-20260910/l2-checkpoint.json` 的精确 hash 绑定。仓库仅归档安全检查点、三份身份回执及按允许字段提取的核验摘要；不复制 config 备份、客户文件内容、原始客户快照、安装/恢复脚本或整个临时目录。L1 保持关闭，本次不新增接纳回执循环；helper、HTTP、生图、M1/M2、PowerPoint、merge/push 均未执行。**L2 整体尚未通过**，后续只在用户选择及对应实际证据建立后推进。

## L2 研发宿主准备完成检查点（2026-09-10）

**当时状态（09:23:45 UTC）：`development-startup-ready-awaiting-full-desktop-restart`。** 本次按总控明确授权在既有 28a9 分支窄同步六份文档并更新本唯一台账。文档来源固定为总控提交 `eb424ee8179d96dc496712b67edd4cc668fbeb49`；实际核对该提交恰含六文件，提交字节与总控最终验证清单相等。四基线只升级标题/元数据至 v2.13 并插入新 §1.5；索引原宿主确认修复节顺延为 §1.6，正文保持。已有来源 finding 恢复、材料排除、供应方准备、确认修复及其他后继合同保留，没有整文件覆盖或源码回退。主计划同步 §12.3 与授权表，新研发宿主执行计划取自该确切提交，含官方 ChatGPT 等同名实例的退出说明。

[本次安全 hash 与状态摘要](./host-installation-l2/development-startup-ready-summary.json)绑定六份原始证据，全部实读核对 hash 相等；原始 config 备份和客户快照不复制到源码。以下安装、进程和客户树事实来自总控固定回执及此前独立只读核验，不冒称本轮重新操作宿主。

| 核验项 | 当前证据与边界 |
|---|---|
| 真实新版工具与预检 | 当前真实工具 catalog 已观察到 43 项，新 snapshot 支持 `includeImage2Preflight`。总控顺序调用的 default 与 preflight 原始回执 hash 分别为 `53fe5d638c08f553c0886629a01053dead2f4d95dc2b9e378959fdcdfe3cd2b8`、`e2093a688ce6ecc5ee977a316484fb05fd3e44edeb0c9e7d2df4c8a37bfb8aa3`；两份 snapshot 投影相等，r19/G0 passed/G1 open。此时四项 presence 全 false、known_wrapper=false、protocol_probe=unavailable、helper_executable=null、external_connection=not-tested。真实 nonce=`3e7e593d180746039954fe1a94ea0167`，wrapper SHA256=`855fbb788400c0586b7d669560f048d19ccb0f4048e3606c7e67f686ad66ac20`。新版已返回与配置缺失均为实测，不再沿用旧 catalog 未观察口径。 |
| 已应用的最小配置 | setup receipt SHA256=`58b89fdaf24425a336fea1518d2b0b20aee3b8ffb254c6835b0c3c02d5cf12ce`，安装时点 `2026-09-10T09:22:39.492761+00:00`。config 从 `be239566b49e4a6cd80030fd0de37bcb8a4f3ecbbb0769f9bf84b6a94df20600` 变为 `f17290415216b13e28332f1f40048e53c88e28f854850f6fc66ed208ea5da32c`，仅 personal enabled true→false；其余 TOML 解析对象全等，受审候选 enabled=true，无顶层同名 MCP。 |
| 研发启动入口 | 正式路径 `/Users/defei/Library/Application Support/AI PPT Studio Development/c2/启动-C2研发验证.command`，SHA256=`4106be85dbab0d3edc33c1ef1f8b7b7204a175e67f19eae48a4c3dc35175f504`，实际权限 0700。六个非敏感 AI_PPT_* 值由该入口传给原 launcher；安装回执的实际 `--check` 为 passed，六键 exact、argv 与 sys.executable 相等。未建立新 Codex home、全局环境或数据隔离。 |
| 候选与原 launcher | 总控安装回执确认受审包 3764 项全等、manifest SHA256=`ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`、原 launcher 未变。L1 源码仍固定 `094986754df67384536117c0d3693cd8a18271c3`；本次仅同步文档，不重建包、不重复逐文件包检查。 |
| 客户状态保持 | boundary receipt SHA256=`23957b0ab827054d8a9231d613d5320d50bdad6575f17e789b81bdb42c6697b7`，核定时点 `2026-09-10T09:23:45.376815+00:00`。99 项客户树与恢复后树完整相等，tree SHA256=`c9bb0c3714f6eaae5bca3c3acbbae2f853d29d49509a5c5660c739bc77a1b25d`；既有三页认可、Batch、r19、G0 passed/G1 open 保持。此处比较基准是恢复后树，不改写历史 mtime 差异。 |
| 尚未建立的 L2 证据 | 完整桌面重启为 NotRun；新进程配置生效、两次通过且 nonce 不同的真实预检、L2 PASS 均为 NotEstablished。已有本地 `--check` 与缺配置的真实预检不能代替这些结果；外部连接仍为 not-tested。 |

**授权与下一步：** 主计划 §12.3 已覆盖旧配置二选一，沿用受审候选及专用启动入口，无需通用加载器或重复授权。总控负责一次完整退出/从正式入口重启的交接，并单一获取重启后进程与两次真实预检证据；其他同名 ChatGPT 桌面实例需正常退出，不由本任务终止。L1 不重开；本次不调用客户端/MCP/CLI/helper/HTTP，不生图，不改安装/cache/客户 Runtime，不运行 M1/M2、PowerPoint，不 merge/push。

**同步验证：** 验证限定为六文档的窄差异、既有合同保留、证据 hash、Markdown 相对链接/原型引用及 Git 提交内容。产品代码未修改，不重跑功能套件；此前已归档的五份 L2 历史 JSON 字节原样保留。本轮完成本地文档提交不表示 L2 或 C2 整体完成。

## L2 重启后启动配置缺失检查点（2026-09-10）

**当时状态（09:44:34 UTC）：`desktop-restarted-startup-configuration-missing`。** 文档收尾期间总控取得真实重启后证据；本次在同一尚未提交的窄同步中保留上述准备检查点，并追加当前差异。[重启后安全摘要](./host-installation-l2/postrestart-missing-configuration-summary.json)绑定新三份证据，实读 hash 全部相等；本任务没有重新检查现场进程或调用真实 MCP。

- **完整重启已观察。** 总控报告 desktop 从 PID 47526 变为 85778，app-server 从 47576 变为 85823；新 AI PPT MCP PID 86053/86290 均子于 85823，cwd 固定于受审 0949867 候选。不能继续称当前尚未重启。进程 presence 审计绑定这四个新 PID；父子/cwd 关系按总控此次交接记录保留，不冒称本任务独立重取。
- **真实预检仍缺配置。** 新 catalog 43 项及布尔预检存在。总控顺序调用 default 与一次 preflight，两份 snapshot 投影相等，r19/G0 passed/G1 open；原始 hash 分别为 `53fe5d638c08f553c0886629a01053dead2f4d95dc2b9e378959fdcdfe3cd2b8`、`172eeb619176a6d0ad50931ef96ba2d92fa72ec78db03771e18b8f7391342010`。本次 nonce=`a9fd36e2da7a4a0dad2c73f85496cc5e`；四项 presence=false、known_wrapper=false、protocol_probe=unavailable、helper_executable=null、external_connection=not-tested；wrapper SHA256=`855fbb788400c0586b7d669560f048d19ccb0f4048e3606c7e67f686ad66ac20`。因首项明确缺配置，第二次预检未调用；重启前后 nonce 不同不等于两次预检通过。
- **缺口位于桌面启动端，具体原因未定。** 审计 `postrestart-presence-and-boundary.json` SHA256=`bb998dfc7cc3a0e4874e229110461705d84574524a6a55a0a05e49d4f25f4084`，时点 `2026-09-10T09:44:34.908684+00:00`。总控仅读取进程环境并在内存提取存在布尔值，四个进程的六个 AI_PPT_* 全部不存在，PATH/HOME 等可见性对照存在；未保存配置值或完整进程输出。用户实际使用的启动入口已由总控异步询问但尚无回答；不能推断用户操作错误、启动方案架构失败或必须修改源码。
- **配置、候选与客户身份保持。** 同一审计确认 config SHA256=`f17290415216b13e28332f1f40048e53c88e28f854850f6fc66ed208ea5da32c`、personal=false/candidate=true、无同名顶层 MCP；launcher SHA256=`4106be85dbab0d3edc33c1ef1f8b7b7204a175e67f19eae48a4c3dc35175f504`、manifest SHA256=`ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`。99 项客户树与恢复后树全等，tree SHA256=`c9bb0c3714f6eaae5bca3c3acbbae2f853d29d49509a5c5660c739bc77a1b25d`；既有三页认可/Batch/G0 passed/G1 open 保留。

**当前边界：** 本次仅完成获授权的六文档窄同步、安全摘要、唯一台账及本地提交。L1 保持关闭；L2 PASS、两次通过的 nonce、配置传入成功、外部认证/HTTP/生图均未建立。完成文档提交后停在宿主核验边界，由总控继续确认启动路径；不重复 Review、包遍历、安装或现场调用，不新增源码修复或通用加载器，不 merge/push。

## L2 接纳与 M1 六条登记、M2 等值准备（2026-09-10）

### 本次授权、入口与 L2 证明

总控在真实自动重启和两次预检后正式接纳 L2 PASS，并派发本任务执行已审[受控加载与来源迁移计划](../../superpowers/plans/2026-09-10-c2-controlled-loading-and-source-migration-plan.md) §4 的六条 finding 登记及 §5 的发布前准备。本任务是本阶段客户业务唯一写入者，总控只读核验；持续材料/用途/模型/接收方授权保持，不新增 Change、任务或重复授权。M2 四对象发布尚未在本轮执行范围内。

[L2 固定完成回执](./source-migration-m1-m2/l2-completion.json)原字节 SHA256=`9fcd6b5d7133a453df996fdf9bc44dbb43bc9fa8fd7c81697bc885fdab4ffdd7`，其 6 份引用证据 hash 本轮全部核对。总控于 `2026-09-10T10:33:34.791782+00:00` 固定：新 desktop 89581、app-server 89618、受审 0949867 MCP 89860/89984；43 工具、布尔预检及 finding 分支存在。真实 default→preflight1→preflight2 三份 snapshot 投影相等、r19/G0 passed/G1 open；两次四项 presence、known_wrapper、helper_executable 均为 true，protocol_probe=passed，nonce 分别为 `1ea5d756e8064c7a9e6425e576241bf4` 与 `b40e0f686ced45b79c963ad2f4da8192`，wrapper SHA256=`855fbb788400c0586b7d669560f048d19ccb0f4048e3606c7e67f686ad66ac20`。这只证明当前宿主本地配置/协议，external_connection 仍 not-tested；本任务没有重复两次预检、重启、L1 或包遍历。

研发宿主计划仅移植总控 `2e20ff88ad2f4dcdb7306669a443cd7c7e270dda` 的单文件 diff，加入 §3.1 自动正常退出授权和失败处理边界；先核对 patch 父版本与本工作区相等，应用后与该提交对象逐字一致。未覆盖四基线或更晚源码合同。源代码及受审包仍固定 `094986754df67384536117c0d3693cd8a18271c3`。

### M1 真实登记与保持证据

登记前新调用真实默认 snapshot，得到 r19；[登记前安全身份摘要](./source-migration-m1-m2/m1-before-validation.json)核对 19 heads、全部 Gate、当前 inventory、25 个不可变制品、两份确切源文件、六处实际提取内容、10 份已确认输入文件和四个当前完整 payload。所有身份与已审来源审计相符，未按文件名搜索或重登记库存。

逐条只调用公开 `add_ai_ppt_material(materialType=finding)`，每次 expectedRevision 来自上次真实读取。成功回执后再次调用真实 snapshot，并用生产只读 resolver 重放当前源字节、核对 finding 字段/content hash 及对应正式事件；未调用 Kernel/shell 写入，未预测 artifact_ref，未发生不明响应重试。

| 计划键 | 实际登记后 revision | 真实 artifact_ref |
|---|---:|---|
| C2-S04-page-evidence | 20 | `artifact://material-finding/62c8d9bd34cc18fe64bd5144e3db62f8f2777f4c06529de9557b18dba2400878` |
| C2-S05-page-evidence | 21 | `artifact://material-finding/03f3279224145028d466956a5181b69cc099bb184126e095926b63b45a3d337e` |
| C2-S06-page-evidence | 22 | `artifact://material-finding/a4539ce2110982a64aa0dc8476c17bd21b7de68a02cf6aa8dafbf501a033d609` |
| C2-S06-image-33-optional | 23 | `artifact://material-finding/3357375c1ebaf7bb606a4aa9a1fb49a867c2befe2b15865b47ac63ab4933484b` |
| C2-S06-image-36-optional | 24 | `artifact://material-finding/f12107fcef18c4c64ce16bc187a1a3627f5b4a4d2ce6f7fde886296422ec915a` |
| C2-S06-image-39-excluded | 25 | `artifact://material-finding/a28ce60f691f70dab47f4b5d9257942d32c558f29b8ceae0abf55bd0c704194e` |

每一步 19 个业务 heads 和全部 Gate 都与登记前相等。M2 准备结束后的最后真实 snapshot 再确认 r25、G0 passed/G1 open/G2–G4 locked；Mission、inventory、三页认可、Batch、G0 confirmation 及消费历史保持。对登记前 63 个普通文件核对，除合法事务更新的 `kernel/state.json` 外，其余 62 个文件的 hash/mode/size/mtime 保持；仅新增 6 个 finding artifact 与 r20～r25 的 6 个事件文件，无旧文件删除。不能把本阶段有意发生的事务说成整个客户树未变。

### M2 具体准备差异与等值结果

[等值准备摘要](./source-migration-m1-m2/m1-m2-equivalence-summary.json)记录所有 **193 个实际差异 JSON Pointer 及前后字段 hash**、144 项逐上下文映射、191 个旧库存引用出现位置、六个真实 finding、完整对象前后 hash 和延后绑定路径。四份内存准备稿均从当前完整 payload 深拷贝派生；没有用历史窄投影覆盖，没有复制客户正文或图片到源码。

| 对象 | 本轮内存准备差异 | 后续待真实上游回执绑定 |
|---|---|---|
| EvidenceBook | 86 处：71 个 `/facts/*/source_refs/0`；`/evidence_gaps/*`、`/forbidden_extrapolations/*`、`/inferences/*`、`/unknowns/*` 各 3 处来源引用；根 `/source_refs` 改为 5 个可用 finding；`/excluded_material_refs` 增加禁图 39 finding；`/source_version` | 无上游内容引用变化，Mission/inventory 保持当前真实 ref |
| DecisionContext | 0 处，完整正文与字段保持 | `/evidence_book_ref` |
| ProblemSolutionFit | 33 处既有 `/.../*/evidence_refs/0`，涵盖原审计列出的 11 类节点/关系 | `/evidence_book_ref`、`/decision_context_ref` |
| ReadingBlueprint | 74 处：71 个 `/slides/*/evidence_bindings/*/source_refs/0`、2 个 `/slides/2/material_views/*/source_ref`、`/source_version` | `/evidence_book_ref`、`/decision_context_ref`、`/problem_solution_fit_ref` |

准备版本标识为 `c2-content-source-migration-v2-20260910`，尚未成为正式版本。EvidenceBook 与 Blueprint 的 `source_version` 一致；Context/Fit 合同没有该字段，通过真实上游链承接版本，不能擅自增字段。当前合同未要求改写事实行版本或生成元数据，因此本轮保留这些已有字段；后续如正式服务确需更新，须另列真实技术差异。6 处上游引用仍保留当前旧 ref 作为比较基线并明确标注待绑定，没有编造未来 ref；这四份内存结果不能直接整体提交。

等值核验实际通过：

- C2-S04/S05/S06 的 16/36/19 段，共 71 段，源 XML 的逐段文本、已确认输入、EvidenceBook statement 与完整 Blueprint 文本有序逐字一致；可见 block 的 `identity` 等完整字段保持。
- 标题、页序、page_task、reading_question 以及全部非白名单字段保持；反向还原允许差异后，四对象与原完整 payload 完全相等。
- 允许图片 33/36 的提取 bytes 分别与既有图片文件逐字节一致，material view ID/素材/用途/处理方式等字段只保留实际原值，唯一改动是绑定自己的正式对象 finding。
- 禁图 39 的确切内容 hash 和 `image-content` finding 已登记；其 ref 只进入准备稿的 `excluded_material_refs`，不进入 5 项可用来源或素材 view。当前正式 EvidenceBook 仍未发布更新，不能声称新的排除列表已成为当前 head。S06 的禁止外推文字继续绑定页文字证据，原 statement/identity/limitations 保持。
- 共同规范原文件 SHA256=`3611e3d651a5037634d9a8532ae2b8bf82375bd5b913eeca8aa44e553082144b` 保持，字体/配色/后备字体/标题栏/背景无变化，三页正文布局指令仍为空。
- 四个结构校验器通过，且规范化结果没有删改准备稿；生产只读来源验证、Fit/Blueprint 的来源引用检查通过。本轮未调用四个 build 服务，未触发新 Gate 或审核，不将只读校验冒称正式发布。

### 待总控确认的后续失效范围

当前 r25/19 heads 无 change-set。按现有源码只读核对：后续发布 EvidenceBook 即令 G0=open、G1–G4=locked，并移除当前 `content/decision-context`、`content/problem-solution-fit`、`content/reading-blueprint`；随后 Context/Fit 逐步用实际回执重建。发布新 Blueprint 会移除当前九个审核/下游 head：`content/acceptance`、`content/gate/evidence`、`content/gate/presales-reading`、`content/review-batch`、三页 `content/review/decision/*`、`gate/G0/confirmation`、`review/session/content-full-deck`。旧不可变制品和确认消费历史保留，旧认可不能替代新版本审核/G0。

本任务到 **M1 完成、M2 等值准备完成但未发布** 为止。下一步须由总控确认这些具体差异及 G0 失效范围，再按实际当前 revision 顺序发布并回填 6 处上游 ref；新版本的两个内容硬门、完整审核及可信 G0 另需真实证据。未运行 helper/HTTP/生图、原生构建、PowerPoint、merge/push，没有新建 Change 或任务。[执行证据 hash 清单](./source-migration-m1-m2/execution-evidence-manifest.json)绑定原始工具回执、只读检查脚本与本次安全摘要；原始客户快照仅留在临时受控证据位置，未归档入源码。

收尾校验：34 项原始回执、检查器及安全摘要 hash 全部匹配；193 处差异分类、6 处延后引用及登记前后 heads/Gates 与证据相符。152 份受跟踪 Markdown 共核对 347 个相对链接；四基线 66 个相对链接、6 个原型引用均可解析，本轮修改文档零缺失。全库既有 13 个缺失 output 链接仅位于未修改的 `docs/v1.5-three-surface-acceptance.md` 和 `docs/validation/2026-08-10-v16-slice-06-ui-acceptance.md`，无新增。`git diff --check` 通过；源码、四基线、两个既存未跟踪派发文件及 `node_modules` 链接保持。本次只提交两份文档与四份安全 JSON，不重跑源码测试或将历史测试计为本轮执行。

## M2 正式发布、独立语义审查与实际审核入口（2026-09-10）

总控已独立复算并接纳 `adca220` 的 193 处准备差异与六处延后绑定，授权本任务作为唯一客户业务写入者继续已审迁移计划 §5/§6。总控在 r29 又独立验证实际发布对象与准备稿等值；两份只读回执身份均绑定于[本轮安全证据摘要](./source-migration-m2-publication/publication-review-summary.json)。本次没有新增授权门、Change 或主执行任务，持续材料与生图授权保持。以下发布、语义审查、正式硬门、Browser 打开和用户判断分别记账。

### 四对象发布与状态变化

四对象全部从当前完整 payload 派生，使用原已审技术白名单。按真实默认 snapshot 的 revision 顺序调用正式 MCP build 入口，每一步成功后再次读取真实 snapshot，并核对实际不可变 payload、事件、全部 heads 和 Gates。没有预测 ref、修补 state、复制旧认可或用修复入口绕过上游失效。

| 对象 | 发布 revision | 实际 artifact_ref | 实际技术差异数 |
|---|---:|---|---:|
| EvidenceBook | 26 | `artifact://presales-evidence-book/bab7f8882f5c2b8611320e334071f07387ba9742518b3df4afc2f39814014efa` | 86 |
| DecisionContext | 27 | `artifact://customer-decision-context/736470c680a3b252b98c2639d4004b7b617fbda56fba6507b1f74082ee719538` | 1 |
| ProblemSolutionFit | 28 | `artifact://problem-solution-fit-map/6c14e72eba8606e739f9152560c333057951bb68ef600d7195a0ed875a793cf1` | 35 |
| ReadingBlueprint | 29 | `artifact://reading-deck-blueprint/1e7f1f86261882d495ed138fe225bc7219809c240aca983557378a12718da4da` | 77 |

实际总差异为 **193 + 6 = 199**，六个上游位置均使用前一步真实回执。新版本为 `c2-content-source-migration-v2-20260910`；仅 EvidenceBook/Blueprint 具有 `source_version`，Context/Fit 通过当前上游链承接。原 71 段文字、标题、页序、目标、阅读问题、完整 identity 字段、图片用途与共同字体/配色/标题栏/背景保持；三页正文布局指令仍为空。禁图 39 的 finding 现已进入正式 EvidenceBook 的 `excluded_material_refs`，没有进入允许来源或 material views。反向还原白名单与六处上游引用后，四份完整 payload 与原对象相等。

r26 的 EvidenceBook 发布仅清除旧 Context/Fit/Blueprint 三个主链 head，G0=open、G1–G4 locked；r27/r28 顺序恢复当前 Context/Fit，未产生额外删除。r29 新 Blueprint 按已审范围清除原九个审核/下游 heads。原 19 个 head 对应的历史制品仍可解析；Mission、库存、发布目标策略和确认消费历史保持。每一步均核验原 62 个非 state 文件的 hash/size/mode/mtime 保持，四次发布事件均未消费用户确认。旧认可和 G0 保留为历史，不能授权本版本。

### 真实隔离语义审查与正式硬门

主任务实际派发两个 `fork_turns=none` 子代理，分别独立读取完整 Mission、四对象和确切源页/图片，未继承生产者的通过结论；审查者没有客户业务写入权。证据任务 `/root/m2_evidence_semantic_review` 的 3 项语义检查通过，阅读任务 `/root/m2_reading_semantic_review` 的 4 项通过。报告分别绑定 SHA256 `368d0d9fa73c14e72def7f7937cd74d1a431a5883bf6a81901fa0f8275b0d3df`、`29f30019b6375511b3e0b888694c5a52af35570284492caeaecc8964db34ce5f`；隔离输入身份 hash 分别为 `78f36166393c6d18db100671914bbbf138eaadf7ecbe8fa167efbcef71486ef1`、`ea768a1185fe1c742676d6c151f6863ff2ffad1028142f8881c8f3e4d0985955`。主任务复核两份报告的输入文件与完整四 payload hash，并将各项结果原样用于正式硬门。

真实工具仅暴露 canonical task name，instance UUID 为 `NotExposed`。当前 Runtime 不提供 attested independent reviewer adapter，故正式调用使用 `reviewerMode=isolated-review-task`，不填造 `independentAgentInstanceId` 或 `outputRef`。真实子代理审查事实与 Runtime context-pack 证明分别保留，不能把外部派发升级为产品内部独立审查适配器已实现。

- r30 证据硬门：`artifact://content-hard-gate-record/1b058140f362feb0f0db947ee715ba62c33ae0120e370b1ff06e03ee684d1d8e`，4 项确定性检查、3 项语义检查均 passed。
- r31 阅读硬门：`artifact://content-hard-gate-record/dc53ff9ee8048d03fc7eb9600ebc728c051d52f81748c27386f6f621c2f0969d`，4 项确定性检查、4 项语义检查均 passed。
- r31 同事务产生内容接纳：`artifact://content-acceptance/15f24a54031c801d993e0c13054ee63b69e8097b5704cda0b9de889c2df63d63`，同时绑定当前 Blueprint、两个硬门及新 source version；不是用户验收。Gate 状态按合同进入 G0–G4 全 locked，等待正式内容审核。

语义审查按真实 Mission 的三页来源关系理解与转换样本范围判断，没有以缺少整套商业方案章节为失败，也没有使用历史认可代替新审查。源标题的主张性措辞、源章标及原页码仍按固定源文案保留；本次通过不能外推为新作整套方案的中立标题证明、现网实施证明、兼容性/SLA/成效承诺或视觉验收。正式 Runtime 检查项 `neutral-title-contract=passed` 按其真实返回记录，不覆盖这些语义与适用范围限制。

### ReviewSession、Browser 与用户判断边界

r32 正式创建 `content-full-deck-4b479471ec312099bb7a`，绑定源发布 revision **29** 及当前 Blueprint；初始 session ref 为 `artifact://review-session/7929c9b93adf89981d884dd867456fbc0e6b53cb47a4498d4618034e356f58d1`。实际返回 `review-session-ready / opened=false / open-scoped-url`。公开只读投影核验三页 16/36/19 段正文、标题、页目标、客户判断与两张图片引用均匹配完整 Blueprint；0/3 决定，Batch 与修订计划均为空。主任务将短期 scoped URL 交回总控后停止客户业务写入。

总控在其当前任务 Codex 内置 Browser **tab 1** 实际打开页面，完整 AX 显示新版、3 页、r33、0 完成；滚动后目视确认第三页两张真实图片，随后返回第一页并 handoff。总控安全回执 `/private/tmp/c2-controller-review-opened.json` 已绑定摘要；本任务只读核对正式 r33 `review.bridge-host-open-recorded` 事件和制品，未冒称自己目检 Browser。

r33 的 session ref 为 `artifact://review-session/320fed51d264a3ebb0bc2f022bca710b9ef8c6847a7748caab7672abba768cb9`，同一会话身份、同一源版本与源 revision，`host_open_status=opened`；真实 host-open 回执为 `artifact://review-host-open-receipt/ea878836e89ddbc4b6865b23a8a1aff2bd48200ccbe43e45b73495f2005c35b0`。相对 r32 仅当前 ReviewSession head 随正式打开更新；没有用户决定、Batch 或 G0 确认消费。G0–G4 均 locked，用户状态为需要处理内容审核。现有 snapshot 在全部 Gate locked 时将 `current_gate` 投影成 G4，此字段不代表进入交付或通过 G4；本轮保留原始值和限制，不顺带改产品源码。

下一步由用户在总控已打开的页面完成三页真实判断，后续 Batch 与可信 G0 由当前版本实际操作建立。主任务继续保持客户业务写入停止；后续用户或 Browser 新事件由总控承接，不用 r32/r33 回执冒充之后的当前状态。本轮没有生图、原生构建、PowerPoint、merge/push 或公开发布；短期 URL/token、客户全文和图片没有进入 Git。安全摘要绑定 29 份临时原始证据/检查脚本及三个总控回执身份；不重跑源码测试，也不另建进度账本。

本轮文档收尾核验：29 份原始证据/检查脚本及 3 份总控回执 hash 均匹配；152 份受跟踪 Markdown 共核对 348 个相对链接，四基线 66 个链接及 6 个原型引用有效。本轮零新增缺失，既有 13 个缺失 output 链接仍仅位于前述两份未修改历史文档。`git diff --check` 通过；产品源码相对受审 `0949867` 无变化，两个既存未跟踪派发文件与依赖链接保持。本次提交范围仅为唯一台账及一份安全证据摘要。

## 审核链接过期保存反馈修复、真实恢复与 G0（2026-09-10）

用户在 r33 旧审核页点击保存时，五分钟短期链接已经过期。根因不是按钮缺少点击处理：Bridge 到达硬 TTL 后永久停止该监听，关闭前请求可得 `REVIEW_SESSION_EXPIRED` / HTTP 410，关闭后只能产生网络失败；浏览器没有保存连接期限、心跳忽略 HTTP 状态；活动内容 Controller 的失败消息只在长稿顶部，页内持续显示“尚未保存”。本次授权限于同一 C2 分支/Worktree 的最小源码修复、回归、独立审查及本地提交，不安装或重启服务，不操作用户旧页，不并发写客户 Runtime。

### 源码结果与证据

- `/api/review` 返回已有的 `sessionExpiresAt`；客户端严格验证其可选字段、正安全整数和 Date 范围，初次/刷新必须同一期限。期限不进入业务投影，不延长 TTL 或替代鉴权；旧无期限连接仍兼容。
- 已知过期的请求在发送前失败；心跳 410 保留明确到期状态，旧连接的迟到心跳不污染新连接。已发出的写请求若在到期后丢失回执，显示“结果尚未确认”，同版本恢复后先核对 Runtime；完整有效成功回执晚于 TTL 到达仍按真实回执处理。普通到期提示限定“本次请求未执行”，不否定前一次未知写入。
- 单页保存中/失败在被点击页判断控件旁显示，批次消息在批次动作旁显示；立即尝试 flush 现有草稿，未闭合回执不清草稿、不增完成数。消息字典只取自身字符串属性，合法 `__proto__` / `constructor` 页 ID 不再命中原型。四基线同步传输期限、未知回执和恢复限制。
- 原页面及本地草稿保留；同版本正式重开沿用 `open_or_resume_review_session`。当前随机端口导致 Origin 变化，`sessionStorage` 不自动跨 Origin/tab 携带未保存草稿；明确告知缺口，不改变恢复目标、伪造迁移或撤销既有判断。

[验证摘要](./review-expiry-fix/validation.json)绑定基线提交 `d2f208d6d1558b6aeb1a3e308e0de9f9f79fe099`、本轮文件 hash、373 项测试输入清单及原始日志 hash。最终私有副本与 Worktree 的全部 373 项输入逐字相同，独立依赖不使用工作区共享 `node_modules`：

| 检查 | 最终本轮结果 |
|---|---|
| TypeScript / Widget build | PASS / PASS |
| 完整 Node | 189/189，0 fail，0 skip |
| 完整 Widget | 770/770，16 files |
| 完整 Python | 754/754 |
| 独立审查实例复跑 | 103/103，2 files |
| 四基线相对链接 / 原型引用 | 66 / 6，零缺失 |

测试先复现再修复；原始源码配当前反例集再次重放得到 10 fail / 93 pass，新增 Bridge 期限断言在原版失败。独立审查 `/root/review_expiry_fix` 发现并闭合两项 P2：到期后未知回执及再次点击语义、消息字典原型属性；最终无未闭合 P0/P1/P2。其独立 focused 复跑前后核对 8 份源码/测试 hash。一次独立运行恰遇主执行的原版 RED 阶段，已单独标记该快照，恢复最终源码后重新独立通过，不混算为最终失败。

全 Node 首轮因临时 runner 继承 `AI_PPT_PYTHON` 干扰既有 EACCES 夹具、缺少已有 native 依赖路径而失败；Python 首轮唯一错误为外部 Skill validator 未找到已存在的私有 PyYAML。仅修正临时 runner 环境后重跑上述全集，未修改这些生产代码或旧测试。原失败日志保留。部分历史 Git blob 当前为系统 dataless 文件，直接读取报 `mmap failed: Resource deadlock avoided`；原始源码改用已存在的私有副本，逐文件 Git blob SHA1 与 index 精确匹配后比较，未修写 Git object 数据库。此限制与源码测试结果分别记录。

### 总控实际恢复与当前用户状态

以下为总控任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 的真实操作回报，正式过程已记其交接 §22；不是本修复测试或本执行任务代填的用户判断：

1. 总控在同一 ReviewSession / Blueprint / 源版本下正式重开入口，r33 为 noop，实际 Browser 新入口打开形成 r34；已核实的用户选择在新页重试，用户完成另外两页与 Batch。旧页未被本修复刷新或关闭。
2. 用户明确表示“我已经审核完了”；r38 为三页 `approved`、Batch `submitted`、UI 3/3 已保存/已提交。总控随后 `open_g0_review` 得 r39 `user-reviewable`，正式原生确认工具收到真实“G0已确认”。
3. 当前该次确认结果为 r40、G0 `passed`、G1 `open`，G0 ref 为 `artifact://g0-confirmation/939837055aba081142bfedd5c6f6b4ce3dea1e74ef7930cdbf393a0b3de853cf`。不再要求用户重复三页审核，也不由此推断图像定版、原生转换或后续 Gate 通过。

运行插件仍为先前受审 `0949867` 源码，本节源码修复尚未安装或加载；真实恢复已独立完成，不等待本修复安装。这次没有生图、客户 Runtime 写入、原生构建或真实 PowerPoint 操作；Node 中的 packaged-native 仅为临时 synthetic 回归，不是客户交付。

### 技术迁移认可复用的只读建议

独立评估 `/root/technical_migration_acceptance_gap` 确认重复审核来自现行“新版不继承认可”的明确合同及身份链，不能仅取消 stale 检查。建议未来以严格等值证明和独立审核证据承接记录引用历史判断，保留原 PageDecision/Batch/G0 身份并由当前 GateEvaluator 核验；当前 G0 仍需新的真实可信确认，不复制或重置旧 challenge、nonce、消费账本。排除材料从空引用迁到 finding 必须证明忠实落实原禁用语义，不能仅因 71 段相同就忽略授权用途和范围。当前 Batch 枚举只有 `submitted | withdrawn`，不得把基线 applied 描述直接当新 status 写入。

该报告只形成建议，未修改认可复用合同或代码，不阻塞已通过 G0 的三页视觉主线；报告 hash 见本节验证摘要。总控派发的只读 scope / policy / 三页输入包准备已完成，沿用正式 r40、71 段、两允许图片、禁图 39 与共同规范。候选及 manifest 仅留在受控临时目录，客户 Runtime 未改变。现有代码的四个具体映射点交回总控核定：既有有效授权尚无可直接复用的结构化 grant；71 段已含标题而候选 intake 额外要求三条 title item；部分材料语义字段未进入供应方 prompt；两张“允许使用”的图片传入 pack 后被下游按全部需覆盖处理。不得以重复用户授权、静默删段/改写或擅自要求两图上版来掩盖缺口。正式 policy/pack 依赖仍为空，未登记、未外发，待总控核定后进入实际设计请求，不重开 L1/L2/M1/M2。

## C2 输入 v2：标题、来源语义、可选材料与授权承接（2026-09-10）

本轮由总控在同一 Change/分支/Worktree 核定实施，以 `30ca3bcc2466519cde804333b679e8c55fc055b4` 为基准；保存过期修复提交独立保留。唯一正式合同为[输入 v2 规格](../../superpowers/specs/2026-09-10-c2-image-led-input-v2-design.md)，执行按[对应计划](../../superpowers/plans/2026-09-10-c2-image-led-input-v2-implementation.md)。四基线及 Skill 的视觉/原生引用同步明确版本分派；去除“所有候选 schema 仍待设计”和“供应方无条件沿用 transport/v1”的冲突句，不改客户已确认内容、G0 或设计责任。

### 最终行为

1. pack v2 的 `confirmed_visible_copy.title_target` 解析明确原 block 身份；共享纯派生函数保留全量原 ID/原文/原序。请求、candidate/current_candidate、selection、compiler/handoff、JS native 和 Python result validator 都携带完整 selected-copy v2，hash 包括版本和 title_item_id，不从 regions 重造无版本的 items。标题可在第二项，同文不同身份不合并，已有 block_id="title" 也不被额外禁用。三页映射是权威来源核定的技术映射，不伪称用户逐一认可技术 ID。
2. 从当前 Blueprint/EB/material_views 确定性派生事实身份、限制和图片用途；当前页来源含 evidence bindings、material views、customer decision evidence refs。真实数组索引用于 provenance，不拿 page_order 猜数组下标。可见项和语义共用 text-0001/material-0001；旧 graph、布局和内部 source/block/path 身份不外发。全部新增客户文本及 v2 common_rules 的自由键值进入同一逐字 scope 枚举。
3. atoms 表示外发前已核验的可用池；candidate 记录实际使用子集 U，当前无可解析规范依据的非空 required_atom_ids 写前拒绝。selection 只冻结 U，regions/native 对全部已选真实素材的覆盖规则不放松；未用可选图不能在 native 阶段补入，禁图及同字节别名仍拒绝。v1 的 all-atoms 语义保持。
4. v2 payload/transport 与 preflight/v2 明确匹配，缺能力在入队前失败，禁止向旧 wrapper 降级；unknown 只恢复原请求。MCP 的 verified-message-only 在缺 verifier/ref、拒绝、异常或取消时零表单回退；true 沿原 HMAC/challenge/消费规则。scope 登记成功回执从实际 ref、项目、root、revision 和 scope head 生成显式仅复用 continuation。后处理缺身份时保留已登记成功事实，不提供可执行 call，不误报未写入。旧 allow-native 与非Image-led generic 行为兼容，参数本身不构成交互许可。

### 本轮工程验证

[验证摘要与精确文件身份](./input-v2-correction/validation.json)记录实际命令、计数、hash、审查与只读边界。主执行证据根为 `/private/tmp/c2-input-v2-implementation-20260910`；TITLE 专项根为 `/private/tmp/c2-input-contract-correction-implementation-20260910`。客户派生全文与 scope 草稿只留在临时证据中，不进入 Git。

| 验证 | 本轮结果 |
| --- | --- |
| 完整 Node | 202/202，0 fail，0 skip |
| 完整 Python | 774/774 |
| 完整 Widget | 770/770，16 files |
| TypeScript / build | PASS / PASS |
| v2 专项 / Node native | 20/20 / 4/4，包含真实临时 PPTX 与 Agent result 事务 |
| AUTH 独立复跑 / 独立攻击 | 50/50 / 35/35 |
| SEM 独立控制 / 真实来源内存控制 | 31/31 / 24/24 |
| 冻结测试快照 | 857 文件与 Worktree/私有副本逐字匹配；之后仅文档/证据收尾 |
| 独立代码质量终审 | PASS，5 项独立测试方法通过，无确定的 P1/P2 缺陷 |

AUTH 已独立通过规格和质量审查。其默认 MCP→真实 Python bridge 测试在临时项目只产生1次scope登记，后续新grant/确认消费/表单/provider调用均为0，Gates不变；不是只验证stub。SEM独立规格审查发现并关闭两项：SEM-R01/P1 共同规范自由文本漏授权、SEM-R02/P2 决策证据限制漏派生。主执行发现的乱序Blueprint provenance错误也已关闭。生产入口RED、收紧反例RED、GREEN及独立重放均保留；原始失败记录没有被成功日志覆盖。

最终[独立代码质量报告](./input-v2-correction/v2-code-quality-review.md)另行复核冻结的15份源码/测试，确认排队后5类输入漂移在发送前拒绝且零写入、3类current_candidate篡改拒绝且零写入、unknown恢复只保留原请求且未重复发送，以及非首标题和同文不同ID的完整copy经过三页实际SDK渲染和Python OOXML/result核验。3类copy metadata篡改在结果校验时拒绝。首次native独立测试因夹具使用项目依赖目录而缺sharp，改用已安装bundled runtime后仅补跑该项通过；没有修改产品源码。报告前后15份冻结文件hash一致；该审查和[AUTH报告](./input-v2-correction/auth-independent-review.md)、[SEM报告](./input-v2-correction/semantic-independent-review.md)分别保留各自证据与结论边界。

全套在私有验证副本、独立依赖和固定 Node/Python 下执行；没有在线安装或写工作区 node_modules。TITLE 首轮全Python唯一环境失败为外部Skill validator缺PyYAML，主执行使用既有 `/private/tmp/c2-python-deps` 后全集通过。AUTH真实桥补测的首次副本缺新增模块和一次fixture误用visual-brief路由分别保留为环境/夹具错误；修正后在基准Python与最终联合v2源码上都通过。未以这些错误修改生产路由。

### 当前三页与剩余真实边界

真实r40只读生产编译/序列化探针和独立材料解析均确认16/36/19个原块，共71项；S05标题仍在原第二项，S06两张允许图片字节不变。完整外发枚举为90个唯一UTF-8字符串hash加2项图片范围，共92项，比旧76项准备多16个hash。scope只是拟议、未签署、未登记；主执行三页编译探针隔离check_policy以单独验证输入表示，不能据此宣称正式授权已建立。独立来源/材料重放、负例和全部111个客户文件前后hash均通过，state仍为r40，SHA256=`713e3e04922bc62ecd166081f2f9aa7d20bcaec57aa530a0ff7366a0007e6d14`。

当前发行stdio未装配真实历史消息verifier，本修复让缺口以零表单的仅复用结果明确返回，并没有上线伪verifier。已有持续授权意图与精确范围技术记录分别保留；后续由总控衔接当前适用消息的真实验证能力或确切范围记录。本轮没有客户Runtime写入、生图、安装/重启、真实确认、PowerPoint或用户视觉验收，不重开三页内容审核与G0，不将临时native工程输出计为客户交付。

Git历史部分blob仍为dataless占位，diff读取会报mmap Resource deadlock avoided。470份基准保存字节已逐个计算Git blob SHA1并与index匹配；本轮使用该已核定基准进行完整明确文件的文本差异/空白检查，不修写Git对象库。最终提交及提交后身份校验见总控交接回执；不把摘要打印失败当成重复提交的理由。原c2-dispatch两份未跟踪文件和node_modules链接保持。

## edb12848 后继候选包与 r40 输入准备收尾（2026-09-10）

本轮按总控已授权边界，从已接纳的精确源码构建后继 Plugin，完成包内验证、作者原生验证、独立包审查和同一 r40 的 v2 输入准备。没有重开 Change、重跑已接纳的同一源码全量回归或请求重复授权；本节及附件是本次必要构建/验证证据，不另建业务状态账本。综合身份与原始证据 hash 见 [validation.json](./successor-candidate-edb12848/validation.json)。

### 候选身份、生产依赖与保存修复

- 源提交：`edb12848bad7b34cb0eb05c6a9b79097cf86422b`；唯一 parent：`30ca3bcc2466519cde804333b679e8c55fc055b4`。版本为 `0.4.0+codex.c2.edb1284.20260910`；后续证据文档提交不改变该源码/包身份，不据此重新打包或改版本。
- 候选目录：`/private/tmp/c2-candidate-edb12848-20260910/plugin-release/ai-ppt-studio`。
- [候选压缩包](/private/tmp/c2-candidate-edb12848-20260910/ai-ppt-studio-0.4.0+codex.c2.edb1284.20260910.tar.gz)：SHA256 `047aa74b30b83eac74d0ce450c989174432bb634b81ad51da852c4ff499ef522`；release manifest SHA256 `25df1450c9678334aee0a5ebbc7068bf1ac99e8ec53b1ca14688636e0ee7bde6`。
- 861 个 tracked 文件从 Worktree 读取，逐个计算 Git blob SHA1 并与 HEAD index 匹配后复制到私有源码快照；未使用 `git archive`，未修写历史 Git 对象。快照 SHA256 `4b501e20006f09311e860910fef72de210057bc80301a259f54a1b964e10f475`。
- 使用正式 `build-plugin-release.mjs` 及离线缓存执行真实 `npm ci --omit=dev --ignore-scripts`；只在包内 Plugin manifest 修改 version，再用正式机制刷新 release manifest。[源码映射](./successor-candidate-edb12848/source-package-mapping.json)覆盖 141 文件，除 Plugin version 外与精确源码逐字相同。
- 3,764 个 manifest 条目 = 141 源文件 + 3,622 生产依赖文件 + 1 个 rebuilt Widget；含 manifest 共 3,765 文件。98 个生产依赖包与 lockfile 对齐，3,622 依赖文件全部与旧受审包逐字一致，没有裁剪依赖内测试。压缩包 4,360 成员 = 3,765 文件 + 595 目录，无额外/重复/不支持成员。
- [相对旧包差异](./successor-candidate-edb12848/prior-candidate-diff.json)：新增 1、删除 0、修改 19、不变 3,744；唯一新增为 `src/ai_ppt_studio/domains/materials/image_input_v2.py`。
- 5 份已审保存过期修复生产源码 hash 均保持。Bridge 原字节入包；Widget 从该源码重新构建，SHA256 `e67a0909b2f3da6008d79e6544925c2b8888a82162982269847ac4c1cb538a8b`，与上一轮完整回归 bundle 逐字相同。这证明修复入包，不能代替真实宿主保存恢复回执。

### 包内验证与独立审查

| 验证范围 | 实际结果与边界 |
| --- | --- |
| 实际 stdio 子进程 | 空 cwd、独立 synthetic Runtime，真实启动候选 `start-mcp.mjs`；43 工具；schema SHA256 `4e7d91f5da614f67e2f2b1d6c09ef7a68044070397d40e18952014582180c9ea` |
| 默认/显式诊断 | default 与 explicitFalse snapshot 相同；两次 opt-in 保持业务 snapshot，nonce 不同、wrapper hash 正确；没有写客户项目 |
| 显式 v2 协议 | 包内 adapter 与真实 wrapper `--preflight` 通过，3 个错误协议反例按预期拒绝；公开 snapshot 验证的是默认预检，不宣称其携带 v2 generation_protocol |
| 包/压缩包负例 | 4 个包反例、3 个压缩包反例通过；独立审查重放相同拒绝控制 |
| 包内原生作者验证 | 两个真实 SDK render，各 3 页、14 个 native 映射对象；v1 兼容与 v2 的非首标题/同文不同 ID/全量有序 copy 身份保持；36/36 反例，全部在作者 SDK load 和输出写入前拒绝 |
| 独立包终审 | PASS，无确定 P1/P2；独立核验源码/包/依赖/实际 stdio/v2/反例；复核两份实际 synthetic PPTX 的包内 OOXML/result 路径，共 6 页通过；未重复 render 或源全量测试 |
| 主执行最终证据复核 | 独审 manifest 40/40、native manifest 67/67、core manifest 9/9、14 条执行日志 hash 全部匹配；3,765 个包文件和 archive 冻结一致 |

[作者原生报告](./successor-candidate-edb12848/packaged-native-author-report.md)与[独立包终审报告](./successor-candidate-edb12848/independent-final-package-review.md)分别保留责任边界；独审机器结论见 [review-result.json](./successor-candidate-edb12848/review-result.json)。独审报告 SHA256 `bbc7549051b7336fe02feba38771ac2af6cb137fa3565a3c181071f799c1b353`；独审 evidence manifest SHA256 `0285786efa78f7a014419267a947f800d9d6ecb442c456093cba1aea8252fc84`。全程 helper 仅检查文件存在/可执行，未执行真实认证或 HTTP。

独审保留一项范围观察：直接从 v2 payload 删除 `payload_version` 后，私有 `Image2CommandAdapter.preflight` 会进入历史 v1 轻预检，首次“该方法必须拒绝”的断言失败已保留。正式可达性检查确认缺 pack_version 在登记前拒绝，正式 dispatch 从当前 pack 派生完整 v2 payload，能力失败零入队/零调用，wrapper 对 v1/v2 envelope 均拒绝混合 shape；未建立公共降级缺陷，不列 P1/P2，也没有为此修改源码。不能将该私有轻预检方法单独称为任意 payload 完整 schema 校验器。

独审 Node `-e` argv 首次触发 verifier CLI guard 的环境失败保留 `.first-attempt`；只修临时调用后 4 个包反例通过。作者两次实际 render 没有意外环境失败。所有原生对象和目标均为 synthetic，输出仍为 `engineering-output-unassessed`；包外完整 SDK（含 sharp/skia-canvas）、Python/Pillow 与精确字体仍是宿主能力要求。

### 同一 r40 的三页 v2 输入草案

输入入口为 [README](/private/tmp/c2-edb12848-v2-input-preparation-20260910/README.md)，目录共 17 文件（manifest 记录 16 项及自身），manifest SHA256 `3fd44b1391f1a4c58179e3307a2af582a31eca5068f77e6da595c3594265bc91`。Git 仅保留[不含客户正文的摘要](./successor-candidate-edb12848/input-preparation-summary.json)，完整文案、材料语义、policy/pack 草案和 92 项披露清单留在受控临时目录。

- 三页分别 16/36/19 个原 blocks，共 71 项；原 ID/原文/原序保持。S05 标题显式绑定原第二项，不按文字或数组首项猜测。
- 共 90 个唯一文字 hash + 2 项图片允许范围 = 92 项，较旧 76 项增加 16 个文字 hash；129 次文字出现位置及 197 个原字段值逐项解析匹配。
- 两图仅为可选池 A，required=[]，实际使用子集 U 未建立；object39 及同字节排除保持。准备文件没有复制图片 bytes 或存储 serialized body。
- scope/grant/policy/pack 均未登记，相关 refs=null；使用正式纯派生、resolver 和本地 serializer，没有 mock check_policy、虚构 ref 或补签。主执行使用新候选包模块再次复核，copy/semantics/provenance 与草案一致；完整 1 个 policy + 3 个 pack + 3 个 service 入口均因 null 正式引用拒绝，符合不可执行草案边界。
- 临时交叉 checker 先后误认披露 kind、遗漏 ProjectKernel 构造 keyword 的两次 setup 错误保留；第三次完整检查通过，候选、源码及草案未因 checker 修正而变化。

客户 revision 保持 40，source revision 保持 29；state SHA256 `713e3e04922bc62ecd166081f2f9aa7d20bcaec57aa530a0ff7366a0007e6d14`，111 文件全部与本轮前快照相同。三页已认可、Batch submitted、G0 passed 是先前真实状态，本轮只读核对，不是重新确认。

### 回退点与总控承接

旧 cache `0.4.0+codex.c2.0949867.20260910` 的 3,764 文件（含 manifest）只读核验保持；manifest SHA256 `ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`。旧 [压缩包](/private/tmp/c2-l1-validation-b4pbxmd2/candidate-0949867-closure/ai-ppt-studio-0.4.0+codex.c2.0949867.20260910.tar.gz) SHA256 `b6efefe6678052ab785f5596ede233fd94d487ec47d0b59de7ec2bb881291266`。没有读取/改动敏感宿主配置，也没有执行回退；真实安装前总控仍须绑定当时的安装身份与配置备份。

本次交接使后继包达到可由总控接管加载的工程状态。新候选安装/重启/真实宿主加载、历史消息 verifier 与正式范围记录、真实 Image 2 生成、定版绑定、客户原生转换、PowerPoint、视觉/用户验收仍分别承接；不以包 PASS 或 synthetic 结果代替。没有 merge/push、客户 Runtime 写入或 Git 对象修复。生产源码与测试仍是 edb12848；本轮仓库变更仅为本台账及 7 份必要安全证据附件，原 3 个 untracked 项保留。

## 真实宿主与 r46 登记/外发截止记录（2026-09-11）

本节按总控实际执行回执更新同一 C2，截止点固定为 r46。主执行仅核验、归档和进行一次必要文档提交，没有安装、重启、客户事务、确认 UI、生图或 recover 调用；没有重复 3,765 文件包审查、重跑源码全量测试或修改生产代码。文档基准为 `a72255c1d0978fd3464fcac47e4be0627efa0f45`；包身份继续绑定 `edb12848`。综合记录及 18 份原始回执 hash 见 [validation.json](./real-host-edb12848-r46/validation.json)。

### 安装、恢复点和真实宿主

- 总控[安装回执](./real-host-edb12848-r46/installation-receipt.json)时间为 2026-09-11 00:04:57（北京时间），安装目录与新 cache 均匹配候选，包版本为 `0.4.0+codex.c2.edb1284.20260910`，manifest SHA256 `25df1450c9678334aee0a5ebbc7068bf1ac99e8ec53b1ca14688636e0ee7bde6`。安装回执原状态 `installed-not-host-loaded` 保留，不改写为后续宿主结果。
- 恢复点已实际建立于 `/Users/defei/Library/Application Support/AI PPT Studio Development/c2/rollback-before-edb12848-20260910`。本轮只读核验恢复清单及旧安装/旧缓存目录存在；完整复制与 hash 核验由安装脚本在升级前执行，其范围由安装回执记录，不重复全包审查。旧 cache 本次没有通过符号链接恢复，原字节保持；配置文件和原客户端入口保持，配置 hash 为 `aeef174112a1c9a2fbcfdeee0002406fef686c0e84e0b49ca831da03fc173f8b`。
- [自动重启回执](./real-host-edb12848-r46/automatic-restart-receipt.json)记录旧 PID `89581` 正常退出，新桌面 PID `7028` 启动，六项配置 presence 均为 true。该回执写明的 `real_mcp_preflight=NotRun` 仅表示重启脚本当时没有执行真实 MCP 预检，不否定随后独立形成的宿主回执。
- [真实宿主完成回执](./real-host-edb12848-r46/real-host-completion.json)时间为 2026-09-11 00:11:56（北京时间），绑定桌面 `7028` → app-server `7068` → Plugin Node `7352`，Node cwd 为新候选 cache。实际工具目录共 **43** 项，`confirmationMode` 可选 `verified-message-only / allow-native`。
- 默认 snapshot 和两次 opt-in snapshot 的业务部分相同；两次真实协议预检均 PASS，nonce 分别为 `f0119c34229048938a9ec453b32141f0`、`4ef68138c3124b5ebca7787a578ce3b3`，wrapper SHA256 均为 `2a9d6565efe82c826b72782b6a905b11723744080b146cf4eb3d144893edd97f`。公开 snapshot 证明本地默认预检，不把它改称显式 v2 generation transport 验证。
- 主执行重算宿主完成回执绑定的 **6/6** 文件 hash，独立核对三份 snapshot、两次 nonce 与真实工具目录一致。`external_connection=not-tested` 保持；本地预检不证明 provider 认证或实际 HTTP 生图成功。

安装/重启/真实预检阶段的客户目录保持 r40、111 文件/169 全部条目，state SHA256 为 `713e3e04922bc62ecd166081f2f9aa7d20bcaec57aa530a0ff7366a0007e6d14`。此整树未变结论截止于 scope 登记之前，不能延伸到 r41 或 r46。

### 范围、授权与三页正式输入

| 顺序 | 真实结果 |
| --- | --- |
| r40 → r41 | [scope 登记](./real-host-edb12848-r46/scope-registration-r40.json)成功；返回实际 ref 和 `verified-message-only` 仅复用调用 |
| r41 仅复用尝试 | [实际返回](./real-host-edb12848-r46/authorization-continuation-r41.json) `CAPABILITY_GAP / verified-message-adapter-unavailable`；未开表单、未签发 grant、未生成 |
| r41 → r42 | 总控说明并提供确切三页范围后，仅调用一次该 scope 的 `allow-native`；[原生确认回执](./real-host-edb12848-r46/native-scope-confirmation-r41.json)成功返回实际 grant |
| r42 → r43 | [正式 input policy](./real-host-edb12848-r46/input-policy-registration-r42.json)登记成功 |
| r43 → r44/r45/r46 | [S04](./real-host-edb12848-r46/input-pack-C2-S04-registration.json)、[S05](./real-host-edb12848-r46/input-pack-C2-S05-registration.json)、[S06](./real-host-edb12848-r46/input-pack-C2-S06-registration.json)三页 input packs 依次登记成功 |

精确业务身份如下；这些引用来自实际回执，不是预先计算或虚构的引用：

- scope：`artifact://image-led-authorization-scope/539491229457004a2025e076cdd7252441153f1ae5403ea8704c44c11b2f9c89`。
- grant：`artifact://image-led-authorization/48098339ddfc37e501f7501724134609143bb5cff407fe028bd672aa0e9dd9e6`。
- policy：`artifact://image-led-input-policy/3560d43ca1f15fff393256f74519d84f9d02671a1c788ba6e919d0fd6cba51f3`。
- S04 pack：`artifact://image-led-input-pack/7741967668edf6641b71ac47085ef3d216a3f2ee7697c26bf6ae5d497eaa9161`。
- S05 pack：`artifact://image-led-input-pack/0341ac86cc487e7b6e8b85951d70b04f1ff051ba663756eec67b9438b3b36bd8`。
- S06 pack：`artifact://image-led-input-pack/18f3c23c93923e5370eb472fdfea8f72dc77f2919d3de0667354b8e9741373b8`。

主执行有限只读核验实际存储的 scope，其 92 项 allowed 和 exclusion 与已准备稿逐项一致；90 个唯一文字 hash、2 项图片允许范围保持。完整客户文案与可读范围全文没有写入 Git。各登记回执中的既有内容认可、Batch 和 G0 引用保持，G0=`passed`、G1=`open`、G2–G4=`locked`。

r41 的历史消息 verifier 缺口仍为真实观察，不能改写成修复或可用；r42 已由实际原生确认调用建立本次范围的 Runtime grant，因此该缺口不再阻断此范围的 Runtime 登记。此事实不代替客户端审批层对用户授权来源的独立判断，也不得将 scope 登记本身当作 grant，或为每页/每次生成重复建立同范围授权。

### 首张生成在客户端审批层被拒绝，Runtime 保持 r46

总控拟执行的首张请求为 `generate-slide-images`，目标 S04 的正式 pack，request ID=`c2-edb12848-C2-S04-20260911-v1`、expectedRevision=46、generationIntent=`new`。[请求文件](./real-host-edb12848-r46/generation-C2-S04-request.json)是未获准执行的记录，不是可直接重放的授权。

[原始拒绝回执](./real-host-edb12848-r46/generation-C2-S04-result.json)来自客户端 auto-review，发生在实际工具执行之前。其理由为：认为完整敏感客户 payload 及精确第三方 `CRS/gpt-image-2` 缺少可信直接用户批准，并未将此前 Agent 发起的 `allow-native` 结果认定为清晰的用户批准行为。本节记录的是自动审批层的实际判断，不把它改写为 Runtime 撤销、用户否认既有决定、provider 请求失败或本地协议失败。

主执行[独立无副作用核验](./real-host-edb12848-r46/no-runtime-generation-write-review.json)与总控[原检查](./real-host-edb12848-r46/generation-rejection-no-runtime-write.json)分别保留：

- [拒绝后真实 snapshot](./real-host-edb12848-r46/after-generation-review-rejection.json)与最后 S06 pack 登记的 r46 snapshot 完全相同；实际 state SHA256 仍为 `b66b5eb21135546f01b646bc723e23e45f4d7633b816b9bc88555687e7939077`，与此前独立观察的 r46 hash 一致。
- 125 个当前文件中的 116 份 JSON、60 个制品对象完成有限只读检查；没有该 request ID 或 `generate-slide-images` 动作记录，没有 generation/queue/task 制品或活动 head；processed commands 为 46，事件最高 revision 为 46。没有新增生成队列、任务、请求或图像结果。
- 现有 scope、grant、policy 和三个 pack 引用保持；实际 grant 未撤销。相对 r40 新增 14 文件 = 6 个登记事件 + 8 个制品对象，删除 0、既有文件仅 `kernel/state.json` 变化。此差异与 r40 的安装阶段未变记录分别陈述；本次只读检查期间 125 文件前后 hash 相同。

本次最终状态为 **真实宿主本地协议通过；r46 正式输入已登记；首张外发未开始并被客户端 auto-review 阻断**。总控负责向用户说明该拒绝和精确范围/目的地，取得所需的可信直接答复之前不绕过、不换接口、不再外发。主执行不进入新代码变更、不执行生成或 recover，也不重复发起一般权限讨论。真实图像设计、定版绑定、客户原生转换、PowerPoint、视觉和用户验收继续为未建立。


## Sunburst 精确型号适配：源码与离线验证（2026-09-11）

本轮沿 CHG-IL-C2、`codex/image-led-native-anchors` 及 28a9 独立 Worktree 执行，起点为 `696b594049cbe61fa6f990681079303e283e73e2`。用户与总控已核定本次实现和独审；[有界计划](../../superpowers/plans/2026-09-11-c2-sunburst-exact-model-adaptation.md)不新增批准门。当前记录为已实现、全量离线验证与独立审查通过；精确提交及交接以提交后回执为准，不表示安装、真实供应方或客户验收。

仅修改两个生产适配器：旧 `gpt-image-2` 继续使用原两项 argv；新 `gpt-image-2.5-sunburst` 只接受当前 Python、当前包 wrapper、`--model`、精确新型号四项。配置、CLI、payload、scope/policy 引用及 probe 必须一致；未知型号、Flare、泛别名、额外/重排参数、伪 wrapper 和旧命令冒充新型号在写前拒绝。transport/preflight v1/v2、完整 v2 文案/语义/材料身份、固定参数 `2048x1152 / high / PNG / n=1`、TLS、helper、禁止重定向与单次发送保持。

两条 HTTP 路径由同一核定型号生成真实正文：无图 JSON generations，有图 multipart edits；单图 image、双图 image[] 保留原字节/顺序。上游顶层或 data item 显式 model 不符时，实际发送已经发生，只拒绝接纳并保留 unknown；transport 回执不符也不得重发。上游未提供 model 时，不把本地请求标签说成独立执行型号证明。Image 2 的整页设计责任、定版权威、G0、三页正文和共同规范没有因型号适配改变。

| 验证 | 本轮结果与证据 |
| --- | --- |
| 最小 RED | [wrapper 4 个断言失败](./sunburst-model-adaptation/red-provider.log)、[新命令预检 1 项失败](./sunburst-model-adaptation/red-preflight.log)，均为旧实现拒绝新增路径 |
| 传输/预检专项 | [40 项通过](./sunburst-model-adaptation/provider-preflight-expanded.log)，含新旧 v2 无图/单图/双图实际 body 与 schema、模型/argv 不匹配、上游返回型号及 stat-only 子进程 |
| Runtime 相关专项 | [35 项通过](./sunburst-model-adaptation/runtime-tests.log)，真实 policy/dispatch/adapter/wrapper 生产函数，helper/HTTP 合成；完整来源文字材料与 v2 身份、授权串绑、旧 pack、新 policy、排队后漂移、unknown 恢复不重发 |
| 离线包与 MCP 专项 | [3/3 通过](./sunburst-model-adaptation/node-provider-focused.log)，真实离线 builder、包内 MCP→Python→wrapper 预检；不是当前桌面宿主或真实生图 |
| 完整 Python | [792/792，exit 0](./sunburst-model-adaptation/python-full.log) |
| 完整 npm run quality | [typecheck/build、Node 202/202、Widget 770/770（16 文件），exit 0](./sunburst-model-adaptation/quality-full.log) |
| 环境失败保留 | [首轮沙箱禁止 loopback listen 的原日志](./sunburst-model-adaptation/quality-sandbox-listen-blocked.log)；同源码在允许本机监听后重跑 quality 通过，未重跑已通过的 Python |
| 独立审查 | [PASS](./sunburst-model-adaptation/independent-code-review.md)，审查者独立执行 68 项 Python 与 250 组身份矩阵，无剩余已确定阻断 |
| 文档和保护边界 | [四基线 73 个/范围内 79 个相对链接及锚点、3 原型和 8 references 均有效](./sunburst-model-adaptation/doc-checks.json)；[3 个原有未跟踪条目保持](./sunburst-model-adaptation/protected-files-check.json) |

[固定文件与验证清单](./sunburst-model-adaptation/validation.json)绑定两生产文件、四测试文件、八指导文档及计划的审查快照。全量运行使用私有临时源码副本和私有依赖，未写共享 node_modules。测试后只将文档阶段短句统一指向本台账并登记计划执行项，生产与测试 bytes 全部等于全量快照；提交前所有原文件 bytes 均对照 Git index blob 验证。Git 部分历史 blob 的 dataless mmap 读取限制用已核验原字节 diff 完成核对，没有修复或替换对象数据库。

总控的非客户在线组件 runner 已做只读安全审查，固定 hash 为 `327e5f4c636f086544b11c6e6eeb4f7d10a38f17123d11a830e0a2d3d4cf1085`。运行后源码检查已覆盖失败分支，优化 Python 模式显式拒绝；两项问题已关闭。该 runner 不在本次源码任务中执行。后续使用[全部生产 Python 清单](./sunburst-model-adaptation/production-python-manifest.json)核验实际受审 wrapper，先验证无图 generations 和双图 edits；单图真实测试可选，不新增为当前客户用途门槛。组件成功只证明真实 HTTP 形态/响应解码，不能冒称 OS exact-argv、当前桌面宿主、正式客户 Runtime 或视觉验收。

本轮没有真实认证、外发、客户事务、确认 UI、生图/recover、安装/重启、merge 或 push。r46 的旧型号授权链保持其历史身份，不能改标签；后续精确新型号授权记录与真实三页由总控沿正式入口承接。本次提交不结束 C2 的真实客户验收目标。


## 固定产品 User-Agent：403 后的窄传输修复（2026-09-11）

总控接纳父提交 `9c61dd8794f713181ef51be93e3cadcba57aca15` 后，真实非客户无图 POST 返回 HTTP 403；[原失败回执](./user-agent-transport-fix/original-generation-403-receipt.json)保留，未取得图片、未重试，原双图分支未执行。此回执仅有 POST 的 HTTP403，runner 的终态 AssertionError 来自非零退出后的成功条件校验，不能另算供应方错误或补写未采集的响应内容。

总控[只读 GET 诊断](./user-agent-transport-fix/readonly-transport-diagnosis.json)在同 key、同 `/v1/models`、正常 TLS/无代理条件下记录：urllib 默认 UA→403、17 字节 text/plain、错误码1010；原系统 curl→200 JSON；仅将 urllib User-Agent 改为诚实产品标识后→200，响应 hash 与 curl 完全相同。这支持当前固定头字段修复，不把 GET1010 当作原 POST 实录，也不表示修后生图成功。所有真实调用均由总控执行，源码任务只读取这些安全回执。

本轮按总控明确授权在同 C2 / 同分支 / 同 Worktree 实施，生产仅修改 `image2_crs.py`：固定 `USER_AGENT = 'AI-PPT-Studio/0.4.0'`，统一加入现有 JSON generations 与 multipart edits 共用 Request headers。payload、配置和环境变量不提供自定义 header 入口。endpoint、TLS/无代理、helper、单次请求、无重试、协议/schema、权限与正文保持；未改四基线、UI、loader 或 curl 后备。

| 本轮新证据 | 结果 |
| --- | --- |
| [生产 Request 缺头 RED](./user-agent-transport-fix/user-agent-red.log) | 2 个方法、13 个断言失败；12 组新旧型号×v1/v2×0/1/2图请求均缺固定 User-Agent |
| [Python 相关专项](./user-agent-transport-fix/python-focused.log) | 70/70 PASS：provider、preflight、v2 Runtime、v2 合同与既有执行入口；实际请求头、固定参数、单次 helper/HTTP、stat-only 零helper/零HTTP、严格型号与 unknown 不重发 |
| [Node 相关专项](./user-agent-transport-fix/node-focused.log) | 16/16 PASS：离线包内 wrapper/MCP 预检、执行展示与 generation recovery；不冒称当前宿主或真实供应方 |
| [独立窄审查](./user-agent-transport-fix/independent-review.md) | PASS，核对唯一生产头字段差异及相关测试，包含总控新 runner 的最小 diff |
| [静态检查](./user-agent-transport-fix/local-checks.json) | 四份未改基线与窄规格的77个相对目标、6次原型引用存在；git diff --check PASS |

父提交的完整 Python792、Node202、Widget770 与 typecheck/build 作为已核验父基线保留。本轮仅运行上表相关专项，未重跑无关 UI 全量，也不把父基线数量改称修复后的全量结果。三个受审文件与本轮私有 Node 测试快照字节一致；全部104生产.py中仅 wrapper 一份变化，见[新生产清单](./user-agent-transport-fix/production-python-manifest.json)和[验证清单](./user-agent-transport-fix/validation.json)。精确新提交与提交后核验以本轮 postcommit 回执为准。

总控新 runner 为 `run-synthetic-provider-ua-fix.py`，SHA256 `de3099258e0281eb38df7439b6d077b7315e717450681d1b6f063245bf570eeb`；[准备记录](./user-agent-transport-fix/ua-fix-fixture-preparation.json)表明两个 fixture 仅换为明确的 `-ua-fix-v2` request ID，payload 保持。新 runner 使用独立 ua-fix-v2 结果根并检查/记录实际 User-Agent；原 runner、failed-v1 目录和旧请求保持。修后真实组件验证由总控在新受审源码提交上明确执行，不重试旧 ID；源码任务未执行真实 HTTP/helper、客户读写、安装、生产包、merge 或 push。

## 392642f 静态候选包与供应方能力缺口（2026-09-11）

本轮按总控授权，从精确源码 `392642f2a34afd856b07228d97ce2b3180fdc961` 构建候选 `0.4.0+codex.c2.392642f.20260911`。状态为 **`local-package-ready-provider-blocked`**，仅表示本地包与隔离预检就绪；供应方要求尚未满足，禁止安装、重启、发布或客户写入。未改变生产源码、严格型号合同、固定尺寸或既有 Image 2 设计责任，不新增 Change；本节及必要证据提交不改变包的源码身份。

| 本地验证 | 结果与证据 |
| --- | --- |
| 精确来源 | [921 个跟踪文件快照](./successor-candidate-392642f/source-snapshot-manifest.json)逐字节计算 Git blob SHA1 与 index 相等；index 对应固定 HEAD。104 个生产 Python 全部等于已审清单；历史对象的 dataless 读取限制仍保留，没有使用 `git archive` 或修复对象库 |
| 正式离线构建 | [执行记录](./successor-candidate-392642f/build-execution.json)：私有依赖、离线正式 builder，只有包内 plugin.version 变更；源输入构建后不变 |
| 文件与依赖 | [来源映射](./successor-candidate-392642f/source-package-mapping.json)：141 个源文件（仅插件版本允许变更）+1 个本次编译 Widget+3,622 个锁文件安装的依赖；[完整清单](./successor-candidate-392642f/complete-file-manifest.json)共3,765文件，含release manifest |
| 正式插件与归档核验 | [PASS](./successor-candidate-392642f/package-integrity-result.json)：官方插件validator、正式verifier、43工具stdio；4个包拒绝反例和3个归档拒绝反例通过；归档3,765文件/4,360成员均与冻结包相等 |
| 双型号包内预检 | [PASS](./successor-candidate-392642f/both-model-protocol-result.json)：旧型号两项argv、新型号四项argv分别实跑stdio，v1/v2 adapter及wrapper预检正确；共27次本地进程检查，含16次预期拒绝。预检只有stat路径，没有调用认证helper或HTTP；合成Runtime的2文件与包字节不变 |
| 独立包审查 | 见[独立报告](./successor-candidate-392642f/independent-package-review.md)及[本轮验证清单](./successor-candidate-392642f/validation.json)；不引用父源码全量数量冒称本轮重跑 |

包目录为 `/private/tmp/c2-candidate-392642f-20260911/plugin-release/ai-ppt-studio`；归档为同一临时根下的 `ai-ppt-studio-0.4.0+codex.c2.392642f.20260911.tar.gz`。release manifest SHA256=`3d35eeeeb3e1b9d89090fa67d5add9b9de0ad76facb66faf965500a724067caf`；归档 SHA256=`575a768dbc8a43148b0cab069117aa8ca0b0417471b5c49169c390d117f7fdf4`；包内 wrapper SHA256=`b97a56cebff7d07c648e54aaa868f3c8f4eda8b613bef21f87493d8e8509d48f`。完整文件、源码映射、日志及独审分别保留hash；本轮没有重跑源码全量，也没有当前桌面加载证明。

总控执行的三次 User-Agent 修复后非客户实测均为单次请求、正常TLS、原样受审wrapper，源后检均passed；本执行任务只读核验安全回执，并独立完整解码诊断PNG：

| 总控实测 | 实际结果 |
| --- | --- |
| [ua-fix-v2 无图 generation](./successor-candidate-392642f/ua-generation-receipt.json) | HTTP200；实际请求型号/参数正确，显式model存在但至少一个不匹配。原回执仅保留聚合布尔，不能反推具体返回值、字段位置或图像有效性；wrapper exit1/InvalidTransport，没有输出图片 |
| [ua-fix-v2 双图 edits](./successor-candidate-392642f/ua-double-edit-receipt.json) | HTTP200；双图image[]的原字节与顺序正确，其余同样型号身份不满足，exit1/InvalidTransport，没有输出图片 |
| [新图例诊断 v3](./successor-candidate-392642f/model-diagnostic-receipt.json) | 明确不同文案/目标/配色的新非客户样本；请求Sunburst、2048×1152/high，HTTP200；回包自报 `gpt-image-2-codex`，未接纳PNG完整解码为1536×1024，hash=`0c092fbc21a6add7c9ad6f6b6a2e8cb73c1406ff10a096d605b978ab146d032e`。型号与尺寸均不满足；wrapper仍严格拒绝 |

v3字段不等于请求的Sunburst或总控查得的官方日期快照，但上游自报metadata仍不能独立证明真正执行的后端引擎，亦不能追溯替代旧两次聚合回执。诊断图片只保留在回执所指临时证据路径，`accepted=false`，不进入候选、定版或客户Runtime。[只读合同审查](./successor-candidate-392642f/response-model-contract-review.md)确认根model与唯一data[0].model逐字匹配，没有获批alias映射；不放宽白名单接纳该值，不缩小尺寸，不继续追加HTTP，不恢复或重发旧请求。原403回执及历史结论保持。此处能力缺口来自实际供应方返回不符合要求，不是用户授权缺失；安装、真实宿主、正式客户生产及视觉验收均未由本轮建立。

## Image 2 Codex 回包兼容与原图适用性（2026-09-11）

用户本轮明确选择 `CRS / gpt-image-2` 推进三页，总控授权在同一 C2 Change、命名分支和 28a9 Worktree 实施最小修复。起点为证据提交 `6aabea117df8c372d3b09f689db0f1d96b183ba0`，其生产源码对应受审 `392642f`。本次状态为 **`source-reviewed-offline-verified`**；精确提交与候选包由提交后回执另行绑定。本节更新当前选择，不改写上节 Sunburst 请求及旧 rejected/unknown 证据。

旧 wrapper 的实际拦截点是根与图片条目 `model` 必须等于请求型号；Runtime 此前没有固定 2048×1152 的像素门。按[本次实施计划](../../superpowers/plans/2026-09-11-c2-image2-codex-output-compatibility.md)，仅 Image 2 路由接纳实测观察到并明确兼容的 `gpt-image-2-codex`，Sunburst、未知和跨族标识继续严格拒绝。请求 `model` 不改含义，新增闭合 `provider_observation/v1` 分别保存两处原始型号/quality/size/output_format、本地观察 UTC 时间与响应 hash；它不提供独立引擎证明。

系统仅在 provider prompt 独立增加 `system_output_requirements` 的 16:9 画布字段，不回写原客户 v2 payload、浅色背景共同规范、文案、目标、材料、语义、授权 hash、grant 或 G0。2048×1152/high/png 保持请求目标。Runtime 完整解码并保留原字节、实际尺寸/MIME/hash；当前两个 CRS v2 路由按 `abs(16*h-9*w)<=8` 及最低 1280×720 判断技术候选适用性。合法图片未达标仍 completed 保全，但 usability 为 needs-revision，候选与选稿重新检查并拒绝；恢复只查询，不能缩裁或重采样伪装合格。技术门不代替文案、文字清晰度、设计、跨页一致、原生编辑性或 PowerPoint 检查。

| 本轮验证 | 实际结果与证据 |
| --- | --- |
| 测试先行 | [RED](./image2-codex-output-compatibility/red.log)：28 方法中包含 21 既有 provider 方法和最初 7 项新测试，15 个失败断言复现旧型号拒绝、观测丢失与系统输出要求缺失；没有执行真实外发 |
| 最小增量与相关回归 | [84 项定向通过](./image2-codex-output-compatibility/focused.log)；[最终 10 项兼容测试通过](./image2-codex-output-compatibility/compat-final.log)，故意让原始 reported 选项与实际 PNG/尺寸不同以核对完整穿透、原字节不变与几何独立判断 |
| 全 Python | [804/804，exit 0](./image2-codex-output-compatibility/python-full.log)；[执行记录](./image2-codex-output-compatibility/python-execution.json)与起止 manifest 证明运行期间源码及测试不变 |
| Node / typecheck / build | [私有副本 typecheck、build 通过](./image2-codex-output-compatibility/verification-summary.json)；[全 Node 首轮](./image2-codex-output-compatibility/node-full.log)202 项中159通过、43项因沙箱禁止 loopback 监听失败；同源码只补跑[review-bridge 文件46/46通过](./image2-codex-output-compatibility/review-bridge-loopback.log)，包含这43项及3项原已过，剩余已知失败0。不是单次全Node绿；本轮未重跑无关 Widget 全量 |
| 独立代码审查 | [PASS](./image2-codex-output-compatibility/independent-code-review.md)，独立13/13（10项当前测试及3项自写边界），覆盖162双位置型号组合、13观测破坏、172几何案例，以及旧已选三页被重新核验拒绝且零写入 |
| 原图与下游 | 1672×941、1366×768、1280×720、1920×1080、2048×1152保持原始字节；1536×1024、1672×942及低分辨率保全但不能成为候选。真实服务的合成三页验证接受1672×941源几何、拒绝强改canvas为2048×1152；原native/输入v2/授权生产文件hash未变 |
| 保护边界 | [原有3个未跟踪条目保持](./image2-codex-output-compatibility/protected-files-check.json)；共享node_modules未写入，Node仅使用私有副本；源码与测试等于受审清单，Node快照后仅有必要文档措辞和流程同步 |
| 文档终检 | [9份指导文档核查通过](./image2-codex-output-compatibility/doc-checks.json)：四基线75个/修改范围90个相对链接及锚点、3原型、8references有效；四基线逆变换可逐字还原既有合同；[最终Skill工作流测试通过](./image2-codex-output-compatibility/skill-workflow-final.log) |

[完整105生产Python清单](./image2-codex-output-compatibility/reviewed-production-python-manifest.json)绑定5份生产修改和1份新增合同，其余99份原样；[观测样例](./image2-codex-output-compatibility/observation-example.json)是明示合成的离线示例，不是总控实测回执。四基线只窄同步 v2.14 §1.6 新决定与冲突句，原宿主确认段保留到索引 §1.7；既有来源恢复、统一输入v2、授权承接及历史证据保持。[验证清单](./image2-codex-output-compatibility/validation.json)绑定完整变更/日志hash，提交后身份另行核验。

本源码任务没有执行真实 HTTP、认证 helper、客户材料或 Runtime 读写、安装/重启、发布、merge 或 push。总控准备的两个新非客户 postfix 用例将在受审精确源码上独立验证；其结果不能由本轮离线通过代替。Sunburst 外部阻断仅约束自身路由，不再作为本轮 Image 2 三页的前置。当前没有新增真实三页、定版、原生 PPTX 或用户验收结论。

## 467b4e2 候选包与源码交接（2026-09-11）

Image2Codex 修复已提交为 `467b4e2bafde0ca44b301ddb6f3fe934c79bc920`，parent 为 `6aabea117df8c372d3b09f689db0f1d96b183ba0`。总控已接纳精确源码与 105 生产文件清单，并独立推进两个非客户 postfix 用例；本任务不代写其真实回执。候选版本为 `0.4.0+codex.c2.467b4e2.20260911`，源码不随本节证据提交改变。

| 候选核验 | 本轮实际证据 |
| --- | --- |
| 源码提交后 | [PASS](./successor-candidate-467b4e2/source-postcommit.json)：55个新提交blob全部读取匹配、1034个index文件逐字节核对、tracked clean且保留原3个untracked。历史递归树/旧blob的dataless mmap限制保持；不修Git、不声称完整历史树核验 |
| 精确构建 | [1034个跟踪文件快照](./successor-candidate-467b4e2/source-snapshot-manifest.json)与index blob相等；[正式离线构建和refresh](./successor-candidate-467b4e2/build-execution.json)通过，仅包内plugin.version替换；构建后快照输入不变 |
| 包文件来源 | [142个直接来源文件](./successor-candidate-467b4e2/source-package-mapping.json)+1个本次编译Widget+3622个依赖+release manifest，共3766个文件；[完整清单](./successor-candidate-467b4e2/complete-file-manifest.json)绑定全部hash。105生产Python完全等于独审清单，依赖全部等于已核验前包 |
| 正式包与归档 | [PASS](./successor-candidate-467b4e2/package-integrity-result.json)：官方插件validator、正式verifier与43工具stdio通过；归档4361成员/3766文件、内容与权限匹配。未重复运行未改守卫的旧归档负例；包负例已由该源码全Node覆盖，不将旧负例冒称本包重跑 |
| 双型号协议 | [11次本地过程检查](./successor-candidate-467b4e2/both-model-protocol-result.json)：1次临时Runtime初始化、2次包内MCP stdio、两型号×v1/v2×adapter和wrapper共8次预检。两文件合成Runtime与所有包字节不变，只有stat分支，真实helper/HTTP为0；不是当前桌面加载证明 |
| 源码台账复核 | [26项检查、16链接通过](./successor-candidate-467b4e2/source-ledger-checks.json)，重新按测试名称核算202个唯一Node通过、19变更/35源证据hash与105Python构成；不重复计数 |
| 总控真实非客户组件 | [两项PASS汇总](./successor-candidate-467b4e2/provider-capability-result.json)：无图generation与双图edits均单次HTTP200、wrapper exit0，实收Image2Codex/auto/png，完整解码1672×941；原prompt字段及双image[]字节顺序、105源码前后检查均通过。本任务只读[复核回执和原图hash/格式/尺寸](./successor-candidate-467b4e2/provider-evidence-check.json)，未发起HTTP |
| 独立包审查 | [PASS](./successor-candidate-467b4e2/independent-package-review.md)：独立核对3766文件/4361归档成员、1034源码/index、142来源映射、105Python、3622依赖及4组stat-only；15条既有执行日志逐项核对。不冒称负例重跑、真实宿主或独立引擎证明 |

包目录：`/private/tmp/c2-candidate-467b4e2-20260911/plugin-release/ai-ppt-studio`。归档：同根 `ai-ppt-studio-0.4.0+codex.c2.467b4e2.20260911.tar.gz`。release manifest SHA256 为 `3e88d785551c28909e8a66c5de6af4099e7ec5f5ef22b36696b2891d61e33c32`，归档 SHA256 为 `d928bb7f13bab4dc7f94987d806d706d6ad019c1cb4571eec38b6544ae2c2398`，wrapper SHA256 为 `06a859241b1cc3e29697426dcb2a57cc3cf5cac630e1fb759d84b50e11bfaffb`。

当前候选状态为 **`local-candidate-reviewed-image2-component-verified`**，可以交总控执行其已授权的后续接续。[本轮验证清单](./successor-candidate-467b4e2/validation.json)绑定包、归档、独审及总控组件回执；本轮Image 2外部组件条件已满足，不沿用旧Sunburst阻断作为全局前置。没有安装、重启、发布、客户读取或写入；没有为本包重跑源码或Widget全量。供应方自报仍不构成独立后端引擎证明，当前宿主、正式客户三页、选稿、原生PPTX、PowerPoint与用户验收仍按后续实际证据判断，不能由包就绪代替。


## 安全失败诊断与 C2 三页委托工作选定（2026-09-11）

本轮延续原 C2 / 命名分支 / 28a9 Worktree，基于 `50ad9f7bdb1ac3f757be7ceb8e552d1b6b33f6a7`。总控已同意[失败诊断小合同](../../superpowers/specs/2026-09-11-c2-image2-safe-failure-diagnostic.md)，并以其四基线 v2.15 §1.7 / 主计划 §12.4 的精确文档提交 `77f195c54dbceff5371149c11c8d4f1b23057d9e` 授权本 C2 三页的[AI 委托工作选定](../../superpowers/specs/2026-09-11-c2-delegated-working-selection-design.md)。该总控文档未整体 cherry-pick 到本源码工作区；本地系统/索引仅窄补诊断合同引用，委托规格明确引用已批准总控身份。

正式客户旧 S04 为 unknown/RuntimeError。总控对照不支持凭据、CA 集合、中文 stdin 或 Node maxBuffer/主动超时的猜测。诊断缺口在于包装器/父适配器/Runtime 丢失失败阶段；旧事实不回填，不重发旧 ID。本轮增加固定失败 stdout envelope：实际 stdin UTF-8 字节 hash 绑定、<=2048 bytes、重复键/额外字段/未知枚举/布尔冒充整数/状态矛盾/子进程自报 exit 均拒绝，仅已知 wrapper 路由非零退出可接纳；parent 补实际 exit。stderr 仍丢弃，未验证回包只记 not-established，不将请求尝试写成服务方已收到。成功协议、业务输入、模型、TLS、无代理、单次调用、原图和授权保持。

工作选择通过原公开 visual-contract commit 入口与 kernel 原子提交；仅允许 C2-S04/1、C2-S05/2、C2-S06/3，空 accepted_deviations、当前已复核图文/素材/共同规范。来源是 agent-recorded-user-instruction / agent-context-only，两个 human approval/acceptance 字段固定 NotEstablished；无用户确认回执、无 G3/G4 升格。原用户定版路径不变，外层 handoff 保留 selection_provenance，最终结果接纳时重算并比较。早期 HMAC 草案已废弃，自动复核在补齐新授权证据后通过同一工具重审，未旁路执行。

| 工程验证 | 当前实际结果 |
| --- | --- |
| 诊断 RED → GREEN | [原14方法/28断言失败](./safe-failure-diagnostic/red.log)；最终24诊断方法及相关专项[92/92 PASS](./safe-failure-diagnostic/focused.log)，包含实际新解释器、最小环境和 OS pipe 的纯离线发送前失败 |
| 诊断独审 | [PASS](./safe-failure-diagnostic/independent-review.md)：35项现有专项+5项独立检查；已审4生产文件，未知来源/原始异常不进入新增诊断 |
| 委托工作选择 RED → GREEN | [受控缺路由反例](./delegated-working-selection/red-disabled-route.log)的当前 v1/v2 两个公开入口用例均按预期失败；原4个HMAC AttributeError只作[历史说明](./delegated-working-selection/red-history.md)。最终10专属、[47相关 PASS](./delegated-working-selection/green-related-47.json)，冻结源码未改 |
| 委托独审 | [PASS](./delegated-working-selection/independent-review.md)：33项工作/旧链回归、21项原G3/G4可信确认回归、[17项独立探针](./delegated-working-selection/independent-probe.json)。默认v2合成三页实际本地renderer生成PPTX字节→preflight→正式result commit走通，删除来源/伪造认可/改原生文案/过期依赖均拒绝且零写入 |
| 联合 Python | [838/838 PASS](./diagnostic-working-combined/python-all.log)，[生产106文件测试前后未变](./diagnostic-working-combined/python-all-result.json) |
| 联合 Node | [202个唯一测试均已覆盖通过](./diagnostic-working-combined/node-verification-result.json)，不是单次全绿。初轮154 pass/46 fail/2 skip；43项loopback EPERM通过授权本地复验，私有快照补build/显式SDK环境后补过bundle/package/native，EACCES用例清除继承的AI_PPT_PYTHON覆盖后默认沙箱通过。原生产Python选择优先级未修改 |
| 构建与类型 | 私有快照[build](./diagnostic-working-combined/build.log)/[typecheck](./diagnostic-working-combined/typecheck.log)通过；共享node_modules未写，未重跑无关Widget全量 |
| 文档 | [6文件81相对链接/3原型通过](./safe-failure-diagnostic/doc-checks.json)，既有11项acceptance-ledger检查通过。待联合收尾时再加入新增证据链接检查 |

此前诊断专属828项快照回归有4项因父目录四基线未及时复制而失败，补齐环境后的11项所属模块全部通过；这不作为单次828全绿，已由上述当前联合838全绿覆盖。并行工作区最初832项中的4项废弃HMAC红测同样不作为生产故障或当前反例。

[联合106生产清单](./diagnostic-working-combined/reviewed-combined-production-manifest.json)绑定新增diagnostics、3个诊断修改文件、2个工作选择修改文件（service重叠范围分别独审）与100个未改文件。两独审的合并接点只有service内新增4行路由，联合测试在相同最终源码上完成。

总控已在诊断专属106源快照上完成[正式CommandAdapter非客户实测](./safe-failure-diagnostic/command-path-receipt.json)：实际fresh Python/minimal env/OS pipe/源码包cwd，单次35.7秒完成，返回Image2Codex/auto/png，原图1672×941、SHA256 `9d996db546d5d888ab9a496168f0e5f2b0acc3313f09cfdac92713c61cd77d31`，完整解码/fitness通过，106源码前后未变。源码任务只读复核receipt/原图hash；该成功不证明当前插件加载、客户旧S04根因或任何用户验收。

诊断专属包已在 `/private/tmp/c2-safe-diagnostic-20260911/plugin-release/ai-ppt-studio` 封存，version `0.4.0+codex.c2.diag.d3f07c3a.20260911`。它不含工作选择增量；正式verify、43工具stdio、双型号v1/v2 stat-only与包内诊断反例通过，全部3622依赖和Widget等于旧包。联合提交与联合候选身份以下续接；不可把诊断包误认为联合包。当前没有新增客户图、客户PPTX、PowerPoint证据、G3/G4或最终用户接受。


### 联合源码与候选立即交接

源码已提交为 `05071409aa93975ae455132d784d23db4b56a472`。[提交后核验](./diagnostic-working-combined/source-postcommit.json)证明当前1121个index文件与工作区字节相等、tracked clean且原三个untracked保留；未遍历历史Git树。

联合包 `/private/tmp/c2-candidate-05071409-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.05071409.20260911`，release manifest SHA256 `30d2fa5c3ed3f6053bccb4e78d7617177957a171352bb04a97919f9ef161e82c`。完整106生产source manifest SHA256为 `ab5697ae384af4e5f1701d29cd60aca1b0d8cc5872d6dc29376f69e2627d3ae5`。正式离线构建/verify已通过；[主执行另行独立核验](./diagnostic-working-combined/main-independent-package-check.json)3767实际文件/106.py/无symlink全部匹配，和诊断包相比仅plugin.version及selection/context/service三个源码文件改变，3622依赖与Widget不变。

包身份已直接交总控，供其在现有授权下安装并接续客户三页；本地归档与证据提交不作为其额外前置。此段只证明受审源码及包的状态，不表示新联合包已经在当前宿主加载、客户三页已经制作或用户已接受。


联合包[最终验证报告](./diagnostic-working-combined/package-validation-report.md)与[摘要](./diagnostic-working-combined/candidate-summary.json)已完成：官方verify、两型号43工具stdio/schema、双型号v1/v2 adapter/wrapper共11次stat-only检查全部通过，合成Runtime及包前后字节不变。归档 `/private/tmp/c2-candidate-05071409-20260911/ai-ppt-studio-0.4.0+codex.c2.05071409.20260911.tar.gz` SHA256为 `05c996a57042fd441f07cb3ca47022b736ad6696df3f047bb0989531e1a1dc48`。[主执行独立归档核验](./diagnostic-working-combined/main-independent-archive-check.json)证明3767文件逐项等于当前包、无额外/重复/不支持成员。联合源、包、两独审、测试和归档均已交总控；当前源码任务未安装或操作客户Runtime，宿主与客户制作状态由总控后续真实回执单独建立。


## 固定供应方内容权威要求修复（2026-09-11）

总控已接纳小合同并更新其 2a66 四基线 v2.16 §1.8；本执行分支只承接源码、测试和本台账，不复制或改写旧四基线。执行分支历史规格的 system-output/v1 描述不代表此次新合同。总控授权仍为原 C2 / 当前 Worktree / 命名分支，依据主计划 §12.4；不重新请求用户许可，不新增通用反馈平台。

**合同与实际差异**：真实 S05 原图及获准输入包只读核对发现新增口号、额外标签、标题身份/标题栏和字符变化。原图/输入不改。wrapper 的固定 `system_output_requirements` 从仅 16:9 升级为 `image-led-system-output/v2`：指定可见文案逐项完整、原始 Unicode/标点/圈号/分隔符/数字/单位及显式重复次数保持；v2 title_item_id 引用 role=title 的确切标题进入共同标题栏，章节标签不能替代且引用不新增第二份渲染；page_goal、非可见语义和材料说明不作为新增文案。字体/备用字体/配色/标题栏/背景落实共同规范，正文布局和无字设计仍自主。v1 全部材料按用途使用，v2 素材池可选；真实素材内原文字按授权角色保留，不从风格参考提炼新增口号或标签。

**instructions 路径事实**：本地 task 和请求指纹保存 action.instructions，生图专用 ContextCompiler、generation_context 只按已授权 pack 编译，execute_generation 只发出该 payload。instructions 当前不会进入供应方；它没有经过 v2 字符串 hash 授权，不直接外发，不宣称自由修订反馈已送达。新设计使用明确新请求身份；历史 completed/unknown 不重写、不重发。

最终唯一生产修改为 `src/ai_ppt_studio/adapters/image2_crs.py`，SHA256 `6ca2a277b45f032154378b38f1b96513a56c981652de8d536333821e91ac2a01`；106生产清单其余105文件保持。客户 payload/schema/hash、G0/grant、协议/型号、HTTP/helper、失败诊断、预检、原图与恢复逻辑保持。

| 验证 | 当前证据 |
| --- | --- |
| 初始 RED | 4方法中14断言失败，缺少固定内容要求；额外自由字段拒绝反例已通过 |
| 初轮全量 Python | 842/842 PASS，106生产文件前后不变；对应初审85c9版本，不能冒称最终版本全量 |
| 独审修复 RED | v1 all-atoms 被错误指令为可选的反例失败；按输入版本区分，保持旧域校验器不变 |
| 最终 Python 专项 | 83/83 PASS，含5个新增方法、双型号/双协议/无图单图双图、原文/图片/授权/unknown恢复 |
| 独立源码审查 | PASS；12个实际编译矩阵与基准相比仅系统要求改变，5合同方法通过；AST去掉系统赋值后完全相同 |
| 四基线引用 | 四基线相对链接及原型存在性只读检查通过；本轮基线改动已撤回 |

临时完整证据目录 `/private/tmp/c2-provider-content-contract-20260911` 包含 red.log、review-fix-red.log、focused-final.log、python-all.log/result、instructions-path-audit.md、independent-review.md、independent-probe-results.json 与冻结106清单。独审报告 SHA256 `3f62bce92187b869cdd8a28088871838cc252dec390b6c5a8abaa93c7d13bf9a`。这些测试证明约束实际送入请求与既有边界保留，不证明模型已遵循。下一包以固定候选包根正式 stdio 接续，由总控完成新nonce预检和真实三页审核；不将安装或GUI重启设为前置，不声称已发布或用户验收。

Native调查另行并行，报告 `/private/tmp/c2-native-path-audit-20260911.md`（SHA256 `aa50331c2a3c624271a02b5a4aeba1687b6bc9afb009a9d9b1cfaed33a2bf162`）。已找到真实text-only输入与relation对象合同、宽渐变路径及自然折行/文本片段映射缺口；本轮未改renderer，是否实现按修正版图确认，不阻塞prompt候选。


### 内容权威修复源码、候选与最终必要验证

源提交 `ab13760f946969a8181a04b2e88c89691c36b350`，提交后tracked/index clean、原dispatch两文件hash和node_modules软链接保持。总控v2.16§1.8已提交为 `2f6d05ce2e6a60799721b5966a3048ea057e2034`；执行分支旧四基线未改。

正式候选 `/private/tmp/c2-candidate-ab13760f-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.ab13760f.20260911`，release manifest SHA256 `e523f54518113f8f698dd2685e571762aae57f6e36091c5147061d1ea9ce1881`，106清单SHA256 `b4c050440c016cadaa594d166470d62e08784c04a3e8c03c5bfe21f9ccec276d`。3766 manifest entries加manifest自身为3767实际文件；不是3767个entries。全部实际字节、106源码、无symlink和直接来源映射通过。对05071409包仅plugin.version/wrapper改变，3622依赖与Widget不变；正式build/refresh/verify及43工具stdio probe通过。

最终必要Node复验 **14/14 PASS、0skip**，日志 `/private/tmp/c2-provider-content-contract-20260911/node-focused-final.log`。初轮共享依赖目录5pass/9fail（7个子进程40s超时、2个Vite .vite-temp EPERM）；首次私有快照12pass/2fail（精简PATH遗漏npm）；补齐npm路径后同14方法单轮通过。没有为环境错误修改产品，未进一步单变量定位各个初轮超时，不以私有复验替代其根因证据。最终83Python专项和独审保持，未扩测无关模块。

归档 `/private/tmp/c2-candidate-ab13760f-20260911/ai-ppt-studio-0.4.0+codex.c2.ab13760f.20260911.tar.gz` SHA256 `aff8ca94463e39c50837bd9c064542cd17005978fb21594f58e1a918fa7b37c0`，3767普通文件逐项与当前包一致、无额外/重复/特殊成员。该目录的package-validation-report.md、candidate-summary.json、build-execution.json、official-plugin-verification.json、source-snapshot-manifest.json、source-package-mapping.json、old-package-comparison.json和archive-verification.json提供完整候选证据。

包根与固定身份已立即交总控；其回报已独立核验完整包和两个实际stdio nonce，客户r55保持并继续S04新设计。本源码任务未读写客户state、未HTTP、未安装/重启，不把总控回报写成本任务重新执行，不把当前制作中写成三页已完成。

候选包独立最终审查 PASS，报告 `/private/tmp/c2-provider-content-contract-20260911/independent-package-review.md` 和同名 JSON：3767 实际文件、3766 发布清单项逐一核验，106 Python 同时匹配受审清单与 ab13760f Git blob；144 来源映射匹配，旧包仅版本与 wrapper 改变；实际导入 43 工具目录及无图 JSON/双图 multipart 编译通过。此证据不代表宿主加载或真实模型输出已遵循。该固定提示词包不再修改；后续 Native 必要能力已获总控同 C2 授权，与新图制作并行实施，独立形成后续源码提交和候选。


## Native v3 最小必要表达与正式链路（2026-09-11）

总控在原 C2 / 当前分支 / 28a9 Worktree 内明确授权立即实施，不等待客户新图定版才研发。权威四基线由总控 2a66 维护，本执行分支仅更新源码、测试、调用参考与本台账。固定 ab137 提示词包保持不变，后续能力另行提交封包。

**已实现合同**：RegionInventory 显式 `image-led-region-inventory/v3`，原 `selected-copy/v2` 及完整 hash 不变。新增 `relation-path` 以区域自身身份承载 `source-image-derived` 绑定、确切定版图 SHA256、原始 text/table-cell 端点或单锚反馈；不插入 relation 文案，不虚构物理回边。有限 `moveTo/lineTo/close` 数值轮廓、线性面渐变、同 path 反向内孔和普通 polygon 进入一对一区域/对象精确映射。freeform 可编辑但无动态端点吸附承诺。v3 文本/表格显式 wrap none/square，保留原始 Unicode runs/noAutofit，不以新增换行改写文案。未扩大为任意 SVG/XML/公式/曲线/外链、文本多框 fragment 或非空阴影。

区域独审在原四项之外新增 `source-image-derived-relations`，检查关系真实性、原端点/单锚含义及语义箭头未被藏为普通装饰。compiler/handoff 派生显式 v3、逐页携带 region_version；结果接纳验证实际 OOXML 点列、命令顺序、内孔绕序、渐变、wrap 与原文字，并重导入同一 PPTX 验证渲染。旧版无 region_version 时保持既有 v1/v2 合同。

| 必要验证 | 实际证据 |
| --- | --- |
| SDK 实物 | [实际导出/再导入及像素验证](./native-v3/sdk-verification.json)通过：artifact-tool 2.8.59、闭合路径/渐变、反向孔像素、文本与表格 Unicode/noAutofit；[说明](./native-v3/sdk-probe-report.md)记录 custom geometry 不能传 borderRadius，即使 0 |
| RED | [compiler/第五审查维度](./native-v3/compiler-review-red.log)两项因能力缺失失败；[结果链 RED](./native-v3/result-red.log)因未贯通 region_version 拒绝实际新 PPTX，不能将其中宽泛拒绝误称精准 XML 反例 |
| 合成正式链与相关回归 | [104/104 Python PASS](./native-v3/python-related.log)，80.489 秒：text-only v2 输入→候选/选定→v3 区域/五项独审→正式合同/compiler/handoff→实际 SDK PPTX→标准 OOXML→重导入渲染→正式 result commit。已先检查合法原包通过，再验证 10 类 XML 修改拒绝且零写入。旧版区域/编译/Runtime/工作选择/结果/G2相关回归通过 |
| renderer | [7/7 Node PASS、0skip](./native-v3/node-related.log)：新 v3 实际路径/孔/折行与既有 v1/v2；私有完整依赖运行，未写共享 node_modules |
| 已冻结子范围独审 | [domain 24 反例](./native-v3/independent-domain-review.json)、[renderer 9 反例及新旧正例](./native-v3/independent-renderer-review.json)通过；全链独审另行续接，不把子范围 PASS 扩成全链结论 |
| 字段交接 | [完整纯合成 JSON 示例](./native-v3/synthetic-contract-example.json)已提前交总控供三页转录准备，不是客户定版几何；[验证摘要](./native-v3/verification-summary.json)绑定日志与文件 hash。79 个当前相关文档链接通过 |

这里仅建立工程表达、绑定与自动化核验能力；原图关系是否提取得当仍由真实图文独审判断。未操作客户 Runtime、未真实 HTTP、未安装/重启、未合并/发布，未生成客户 PPTX 或建立 PowerPoint/G3/G4/最终用户接受。总控真实新 S04-v2/S05-v2 返回 HTTP524 的状态不回填到旧 unknown；流式能力实测与最小传输修复另行记录。

全链独立审查随后 **PASS**：[独立实际链路报告](./native-v3/independent-chain-review.json)验证三页/15个原生对象及13个新增反例。反转/删除内孔、改为第二条填充路径、附加动态stCxn、改命令顺序/渐变、增加handle/preset均由实际OOXML检查拒绝；同时修改regions与objects的关系虽能过孤立结构检查，正式Context重建仍按注册来源拒绝。第五审查项缺失、重复、failed、not-established不能放行，所有反例后Runtime文件不变。[已测试生产清单](./native-v3/tested-production-source-manifest.json)固定Native验证源码，流式wrapper后续改动独立审查，不混称Native复测。

Native 源码已提交为 `9817d054bc9b80c063a0a61098a075afcc7cbcc5`。[终稿独审](./native-v3/independent-review.md)绑定[最终143文件清单](./native-v3/independent-final-source-manifest.json)，SHA256 `ffd617c14a47e78bb8327255efa8a6cfe889249273731165180caa551c43d71f`；与测试清单只差两处澄清“无显式v3区域才沿用v2编译”的参考文字，无生产变更。[提交后逐blob核验](./native-v3/source-postcommit.json)确认143文件精确匹配此提交。


## Image 2 流式传输与可调用候选（2026-09-11）

总控在同一 C2 授权最小传输修复，优先供真实三页继续生图。总控的纯合成[generations实测](./stream-transport/generation-capability-receipt.json)与[双图edits实测](./stream-transport/edits-capability-receipt.json)均收到 HTTP200 / text/event-stream，分别观察 `image_generation.completed`（66.079秒）与 `image_edit.completed`（65.36秒），完整PNG为1672×941。它们不读取客户资料，也不证明客户新请求必定成功；旧unknown不回填为新的524诊断。本源码任务只读核对这些回执，未重复HTTP。

仅 `gpt-image-2` 请求增加 `stream=true`、`partial_images=1` 和 SSE Accept；同 endpoint/helper/TLS/无代理/一次POST，外部 transport v1/v2、授权、pack、原文/材料hash及固定system-output/v2保持，Sunburst原路不变。解析支持已观察的两种准确事件族、注释心跳、data/event、合法id/retry与DONE；id/retry不持久化、不作为来源、不触发重试。只有一个最终图片可交付，拒绝error/重复或缺失终态/畸形/错型号及超限；所有显式model逐处检查，无model不补造回报。DONE立即停止，响应hash只覆盖实际消费前缀。单行/单事件32MiB、总96MiB、256事件，Image2新增独立进程900秒总期限，保留300秒socket超时和30秒helper超时。普通JSON响应保持原校验，wrapper仍只检查base64/PNG头，Runtime承担完整像素解码。

流式源码提交 `d1d058b360ccf1b52c551b6257e151843f8c678d`，仅wrapper及两份测试；wrapper SHA256 `68c1979032012dac3821daad780d9cfbfd22a034665d8ea2ad0ca237b53a8040`。[68/68专项](./stream-transport/focused.log)、独审重新执行68项及[8个独立检查](./stream-transport/independent-probes.log)通过，12组原输入对照证明prompt/材料字节与顺序不变。真实短SIGALRM子进程证明阻塞可中断并恢复处理器/计时器。[独审PASS](./stream-transport/independent-review.md)与[机器回执](./stream-transport/review-receipt.json)固定三文件hash；没有扩大无关全量测试。

**已交付最小流式候选**：`/private/tmp/c2-stream-candidate-68c19790-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.stream68c19790.20260911`。它从固定ab137基包按已审wrapper hash叠加，`source_status=reviewed-hash-pinned-overlay`，**不含Native v3**。release manifest SHA256 `57d8028042f78898e34f46fe27cc46514f70c6f3e857da75c201a2fd6962540e`，106清单SHA256 `9e9aac009daec64e78193e5b0f856a05f7bfed229410971290c6147bb60a8926`，归档SHA256 `ac5e4e2980d877a07f4e1ed4f1c38e7b8373558e703e45a09fde6c6742259438`。[正式摘要](./stream-transport/minimal-candidate-summary.json)与[独立验包PASS](./stream-transport/minimal-package-review.md)证明3766清单项加manifest为3767实际文件，payload只变wrapper/version，105其余Python、3622依赖、Widget及旧包保持；官方refresh/verify43工具通过，归档逐文件相等且无额外/重复/特殊成员。

精确Git快照联合builder在只读取树时长时间无输出，默认权限已执行而非等待审批，根因未建立。已精确终止本任务builder56161及其Git子进程56179，session67557最终退出1；`/private/tmp/c2-candidate-d1d058b3-20260911`只留空build-source，**不是可调用候选**。总控明确接受按受审hash先封包，不等待Git/文档。源码已提交与此最小包的来源分别记录，不把叠加包冒称完整新commit快照；[来源与证据清单](./stream-transport/source-and-evidence.json)保留状态。实际客户生图、选稿、区域转录、PowerPoint和最终验收由总控后续建立。

### Native v3 + stream 完整候选交付与最终独审

完整候选目录为 `/private/tmp/c2-native-stream-candidate-68c19790-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.nativev3stream68c19790.20260911`；已交总控用于后续原生转换。最小 stream 包继续作为独立已封存候选保留，不因完整包交付而改写。完整包同样为 `reviewed-hash-pinned-overlay`，不冒称完整新 Git snapshot。Native 源码提交 `9817d054bc9b80c063a0a61098a075afcc7cbcc5`、stream 源码提交 `d1d058b360ccf1b52c551b6257e151843f8c678d` 与包内已审字节分别绑定。

| 完整候选身份 | SHA256 |
| --- | --- |
| Release manifest | `c7977eedfd69b91ec391abd8ea883d0a38a750ff77beabec3942c4571d41b1cc` |
| [106 Python 清单](./stream-transport/native-stream-production-python-manifest.json) | `5801b430eed6af8055d90ce4be4c19468a418a9dab745c08dacbc2ad18f13154` |
| tar.gz 归档 | `f71ecfceee4423da5c133c98d78a61f151012edc09d26e97daeda19495a56c8d` |
| [最终独立报告](./stream-transport/native-stream-package-review.md) | `84e08172a1c3a8363e1e743c85e3c6c0675dabd1c9693f8aa9d684f07b805c16` |

[候选摘要](./stream-transport/native-stream-candidate-summary.json)、[独审机器报告](./stream-transport/native-stream-package-review.json)与[完整文件清单](./stream-transport/native-stream-package-full-manifest.json)确认全部3767实际文件及归档字节一致；相对ab137，变化精确限于5个Native Python文件、stream wrapper、renderer、2份调用参考与插件版本，其他100个Python文件、3622个依赖及Widget保持。Native 143项独审清单中实际发布126项，仅wrapper被随后受审stream字节替换；8个Native覆盖文件逐项匹配。[正式离线执行](./stream-transport/native-stream-build-execution.json)、[官方verify](./stream-transport/native-stream-official-plugin-verification.json)、[归档核验](./stream-transport/native-stream-archive-verification.json)与[旧包差分](./stream-transport/native-stream-old-package-comparison.json)记录均归档，43个工具身份一致；本次归档未重复构建或源码测试。

[包内入口小例子](./stream-transport/native-stream-package-entry-check.json)已由独审实际执行并PASS：Image 2的JSON输出使用布尔`true`/整数`1`，multipart序列化为`true`/`1`；Sunburst两种编码均不添加流式字段；v2 selected_copy原文保持，v3区域输入派生v3 compiler/handoff且支持relation-path。检查在helper与HTTP被阻断的条件下进行，执行前后整包字节一致。它证明包内导入和本地编译入口，不代替真实客户图、原生还原、PowerPoint或用户验收。stream独审原68项执行日志另保留为[reviewed-focused.log](./stream-transport/reviewed-focused.log)，区别于主执行的68项日志。

### 总控最新回报与安全收口

以下为总控任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 的最新委托回报，已写入其台账§47；本源码任务没有重新读取客户Runtime或执行外发。[回报归档](./stream-transport/controller-latest-boundary.json)保留此证据来源：总控另行核验完整包3767文件/106 Python、8个Native覆盖hash、143项最终清单和tar，并用完整包成功执行真实只读snapshot，项目仍为r61，证据位于客户项目的`output/native-preparation/native-stream-readonly-snapshot.json`。这证明该次包内只读入口可运行，不表示插件已安装到桌面、客户图片已生成或原生PPTX已完成。

真实S04的新stream生成在exec创建进程前被平台自动审批连续拒绝，因此该次没有HTTP、请求ID、新任务ID或输出目录，r61保持。总控已核对scope/grant及客户字符串范围，并恢复原始详细外发授权问题和用户确认；平台最新仍因历史日志证据不被接受为可信用户输入而拒绝。**既有用户授权和G0没有被撤销；平台执行拦截单独记录。** 不将它写成客户生成失败、供应方故障或旧unknown的新结果，也不将此前合成HTTP200转为本次客户请求证据。

按总控最新指令，本源码任务停止增加测试、候选包或新任务，保留两个已就绪包与原始数据；不代发客户内容，不换接口、子任务或权限通道重试，不写客户Runtime。仅完成既有证据归档、文档检查和本地文档提交。三页真实PPTX的目标仍未完成，后续执行需平台接受可信用户许可或外部审批状态变化；本地源码、独审、封包和文档提交不能替代该条件。

本次[文档收口检查](./stream-transport/closeout-document-checks.json)覆盖四基线、唯一台账及新增审核文档的相对链接与锚点、3个原型引用、25份归档证据hash、106生产文件与3份stream受审文件身份；143项Native清单仅有已单独受审的wrapper增量。`git diff --check`通过，四基线、生产源码及共享依赖未修改，原dispatch两文件与node_modules软链接保留。此次只核对已形成的证据与文件身份，未重跑源码测试或重新构建候选。

## Image 2 解码精确诊断增量（2026-09-11）

总控随后取得当前可信用户许可并实际发出S04新设计v3；此前平台进程前拦截是历史事实，不再作为本次请求状态。本次沿用同一C2 / 28a9 / `codex/image-led-native-anchors`，以`e2a4fd2b7624a2ff99afe201e009bccb401f7411`为源码起点，按总控明确授权实施最小诊断修复，未另建Change。

[只读安全证据](./decode-diagnostics/source-observation.json)确认request `c2-stream-C2-S04-20260911-design-v3`、payload SHA256 `86d60319efaa74c52688fdf803910d494f81367bb8da54115a1f907c7022ba53`对应r64的unknown回执；HTTP200后为`provider-decode-failed`。旧wrapper的SSE/JSON、事件格式、metadata、图片编码以及解码期间整次期限可能落入同一标签，不能据此认定具体原因或供应方已出图。CommandAdapter不持久保留失败stdout原文，Runtime失败分支没有原始HTTP正文、SSE事件或图片字节；现有recover只查询原回执，不能离线重解码，也不能将unknown改成completed。

总控后续回报同一旧stream包的S05 v3、S06 v2均completed；其内容独审又发现额外标签或漏字，并另行启动S05新设计v4。此处为明确归因的总控回报，本源码任务未读取这些新图或执行其请求。生成成功、内容质量与S04传输解码失败分别记录，不将质量问题改写为传输故障，不把文案删改交给Native环节。

**实现范围**：仅`image2_crs.py`与`image2_diagnostics.py`两份生产文件。闭合合同见[安全诊断规格的本日增量](../../superpowers/specs/2026-09-11-c2-image2-safe-failure-diagnostic.md#2026-09-11-解码诊断增量同一-c2-已授权)。外层command-failure/v1及2048-byte上限保持，旧diagnostic/v1仍可读。HTTP200后的读取/解码失败使用diagnostic/v2，原七字段之外只增加四项闭合decode_context：解析分支、实际read/readline已返回的字节数、空行结束的SSE块数、通过完成事件metadata/base64/PNG头检查的标记。后者不等于像素完整解码、流读取完毕或交付成功；JSON的两个SSE字段固定null。

固定reason分别识别SSE分帧/UTF8/JSON/事件形态与类型、供应方error、完成前后关系、model/metadata、base64/PNG头、EOF与限制；JSON fallback有独立前缀。整次signal deadline使用确切内部异常类型，并识别urlopen对该类型的URLError包装，与普通socket timeout区分。无任意provider文本、headers/body、密钥或输入信息进入诊断。成功接纳条件、输入/Prompt/材料字节、一次POST、TLS、无代理与unknown不重试均保持。wrapper与validator必须成对交付。

| 定向验证 | 证据及实际边界 |
| --- | --- |
| 初始反例 | [9方法/42失败断言](./decode-diagnostics/red.log)复现实际拒绝条件坍缩、v2未被父适配器接纳和Runtime无法保留精确原因；无缺失模块/属性错误 |
| urlopen包裹期限 | [单项RED](./decode-diagnostics/deadline-wrapped-red.log)证明内部期限曾被报为普通timeout；增加确切内部类型识别后通过 |
| 最终受影响专项 | [78/78 PASS](./decode-diagnostics/related-final.log)，6.715秒，覆盖新诊断、原SSE/provider/输出兼容/失败诊断；没有重跑无关项目全量或Native |
| Runtime链 | 新纯合成wire实际经过固定wrapper→父Adapter→正式Runtime，unknown保存精确原因；recover原回执相等、文件树不变、HTTP/helper各只有原一次，不能成为候选。既有无诊断历史回执不补写测试保持通过 |
| 源码身份 | [五份源码/测试清单](./decode-diagnostics/source-manifest.json)固定本轮文件；旧专项仅更新3个v2回执精确预期及真实短期限的新reason预期，未削弱断言 |

本增量证明的是诊断可区分，**真实S04失败根因仍为NotEstablished**；没有补造该历史请求的响应格式、事件计数或终态，没有客户HTTP/helper、客户Runtime写入、安装、重启、merge或push。独立源码审查和受审候选包身份随后续接，客户后续新请求仍由总控串行执行。

### 解码诊断独审与候选交付

[源码独审PASS](./decode-diagnostics/independent-review.md)与[机器回执](./decode-diagnostics/review-receipt.json)已完成：独立11/11方法包括68组旧HEAD/新wrapper接纳结果和成功回执比对、6处解码deadline注入、257块界限、完成事件后超时、v2严格字段/2048上限反例；另独立复验新增10/10专项。两生产文件始终匹配已审hash，未发现范围内阻断。此结论不证明真实S04原因已修复。

诊断候选已立即交总控：`/private/tmp/c2-decode-candidate-62813b48-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.decode62813b48.20260911`，`source_status=reviewed-hash-pinned-overlay`，保留Native v3。[候选摘要](./decode-diagnostics/candidate-summary.json)分别绑定源码独审与[包独审PASS](./decode-diagnostics/package-review.md)；包报告的source pending只描述独审职责当时的边界，不取代独立源码结论。

| 候选固定身份 | SHA256 |
| --- | --- |
| wrapper | `62813b4899eee62e86aa30635c21ebc7ffd3c4adfba07dccf9937f171848d977` |
| diagnostics validator | `f77fb238a826cdf0977cc4af381cbfe9d63d358297f068c42fe31fc2af84e96f` |
| Release manifest | `d374e43b1897dd339e9e12977c38de8d0fd1c62d7f28d9ec3bffb185b923193b` |
| [106 Python清单](./decode-diagnostics/production-python-manifest.json) | `d04ef1b2ed9a597e024adade09d71755f3ffbc8e94fd2f5eb18514a92ea916e1` |
| tar.gz | `66cf507e36e18a88188473f2313586e9b42f58dc4806691f188ed78dc62d86a5` |

[独立包回执](./decode-diagnostics/package-review.json)与[全文件清单](./decode-diagnostics/package-full-manifest.json)核对3767文件及归档一致，内容差异仅上述两份Python和插件版本/manifest；其余104 Python、Native8、3622依赖、Widget与旧完整包不变。[官方verify](./decode-diagnostics/official-plugin-verification.json)43工具通过；第一次因私有Python依赖路径遗漏而缺yaml，补入已有`/private/tmp/c2-python-deps`后成功，[初次失败说明](./decode-diagnostics/initial-attempt.json)与stderr保留，没有安装依赖或改产品。包内纯合成472-byte v2失败envelope编码/解析及父exit补入通过，导入后包字节不变。

诊断候选无需等待后续修订反馈能力，可供总控按持续授权推进S04下一张新设计；这不是旧unknown自动重发。本源码任务只做本地实现/验证/封包，客户请求与状态由总控独占写入。后续结构化修订反馈作为同一C2必要切片另行记录，不回改本已审诊断包。

[文档核验](./decode-diagnostics/docchecks.json)同时检查四基线、规格和唯一台账的相对链接/锚点及原型引用。总控已另行核验本诊断包全部文件并启动S04新设计v4；本任务仅记录此委托回报，实际结果待总控新证据，不据启动声称生成成功。

## 定版前 Image 2 原图修订闭环（2026-09-11）

沿用当前 C2 与总控四基线 v2.17 §1.9 的持续制作/必要修复授权，以 `6df9251f2fb8a50ac8a0591a1e87ae1e579d7e8a` 为本切片基点；不另建 Change，不修改本 Worktree 的平行四基线。总控回报 S04 v4 已 completed 并形成 candidate/source-review，客户 r79；该真实执行不是本源码任务完成，也不能倒推旧 S04 unknown 根因。S05/S06 修订效果及客户 Native/PPTX 验收仍未建立。

[最小规格](../../superpowers/specs/2026-09-11-c2-image-led-repair-feedback.md)落实为独立 `image-led-content-diagnostic/v1` 与 `image-led-image2-repair-input/v1` / `image-led-image2-repair-transport/v1`。独立 reviewer 以确切 completed response 为 target，通过原 `visual-contract` 正式结果事务登记问题；不要求先把错误图登记为正确候选。原图源 task/context/request slot、原文材料包、当前来源和有效授权、hash/尺寸/完整 PNG 解码逐项重验；源图独立排除检查非 passed 时在新任务入队前拒绝，即使纠错目的本身是删除排除内容也不能先发图。观察与生成图不是新事实源，不改旧 grant，不外发自由 instructions/observed_text/detail，不加逐次许可。

修订沿用完整原 v2 输入，原图为图片1，原材料按原字节/顺序/用途随后排列并同步偏移两处图片序号；可选材料不强迫全部上版。missing/replace 仅引用原文案item，common-rule仅指原五类共同规范，bbox仅定位实图差异，Image 2仍负责设计与必要构图。当前共同规则没有排他色板原文，不将辅助色自动判错或强制清除。历史 completed 图可以明确选用，修订输出也可继续修订；本次诊断必须当前，已执行祖先诊断后来替换不抹掉历史生成链。

正式修订任务必须新的显式请求ID，request/response同时保存原pack、诊断、直接源response与完整repair payload hash。recover不依赖当前授权或诊断可用性，零写入、零重发、unknown不回填；不能把请求已发解释为模型已收到或执行。输出fitness按原base核验，新candidate仍以原pack及新图登记，不能继承旧source-review/selection/区域/TargetBinding。Native不删补内容兜底。调用顺序见[正式调用说明](./repair-feedback/invocation-guide.md)。

| 验证范围 | 已形成的证据 |
| --- | --- |
| Runtime RED/GREEN | [初始13项/12失败](./repair-feedback/runtime-red.log)确认旧流程缺口；最终新增18项及旧请求/selection/recovery/两型号Bridge共[49/49 PASS](./repair-feedback/runtime-focused-green.log)，10.976秒，包含真实Bridge/Adapter/包装器与合成外部替身贯通 |
| Provider RED/GREEN | [初始16项、3失败/12错误](./repair-feedback/provider-red.log)，包括尚不存在模块与协议；新增20项及对应旧transport/output/preflight/SSE/diagnostics共[117/117 PASS](./repair-feedback/provider-green.log)；实际`python -S`无Pillow编译与stat-only preflight通过 |
| 原行为保持 | [12种旧协议/型号/图片数请求](./repair-feedback/legacy-wire-comparison.json)与6df9251逐字节相同。一个旧Runtime断言遗漏已存在stream字段，在[封存decode包上同样失败](./repair-feedback/legacy-stream-assertion-baseline.log)后修正两型号期望，产品传输未回退 |
| 独立源码审查 | [Scoped PASS / spec PASS / code quality PASS](./repair-feedback/independent-review.md)，[12/12独立探针](./repair-feedback/independent-probes.log)，包括历史完成任务、不同真实图像字节的多轮修订、排除/撤销写前拒绝、未知恢复、伪造源输入、截断/APNG与新候选无继承；[16文件冻结清单](./repair-feedback/source-manifest.json)与[独审回执](./repair-feedback/review-receipt.json)一致 |

### 修订候选交接

受审候选已直接交总控：`/private/tmp/c2-repair-candidate-c5dad25b-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.repairc5dad25b.20260911`，`source_status=reviewed-hash-pinned-overlay`。本地源码提交另行绑定，不冒称此包是完整新Git快照。调用器不需要新增工具或参数schema；原pack-only假定改为本次diagnostic target，candidate仍填原pack。总控已自行准备并独审两个caller，客户写入/HTTP/加载由总控串行持有。

| 固定身份 | SHA256 |
| --- | --- |
| wrapper | `4933c32d3f083ceb8cf78585213a638e555d51eb7e64b656adf9a141d1724b7e` |
| Release manifest | `5069897793f8eec016419d895a3316f2c09a684d2478609c7b35c6043f60985b` |
| [108 Python清单](./repair-feedback/production-python-manifest.json) | `ebacf5e10f540ad7aa928398f59ff02ec00661d5d1c7fbf3d725662fef916e2d` |
| tar.gz | `dcdac2905d2dddb28ede9ebfce21caedebdd3942391f60256881a0143962c4ed` |
| 源码独审回执 | `162ac75b4209515b3a3e67b09891323d41579a32dce03bd8016af53324589788` |
| 包独审回执 | `7a159f549971786834a0b2b455d07b5793de040ba4dab5c5e53606ad23024e72` |

[封包独审PASS](./repair-feedback/package-review.md)核对候选实际3769文件、完整清单及tar路径/字节/权限一致，release manifest为3768项，差异严格为9份Python+2份引用说明+版本/manifest，仅新增两模块；其他99 Python、3622依赖与Widget保持原字节。[官方verify](./repair-feedback/official-plugin-verification.json)43工具通过，独立包内合成编译/stat-only preflight通过。[候选摘要](./repair-feedback/candidate-summary.json)分别绑定源码和包独审。

此前交接中的“Native8均原字节”已明确纠正：旧Native8集合中6份字节不变，context_compiler.py与visual-workflow.md属于本次受审repair接线/说明覆盖；新共同容器端点/渐变文字增量的三份生产文件未混入本包。封存decode清单中3767原文件均一致，其目录后来多13个pyc缓存，来源未在本次建立；核验如实单列、不删除、不复制到候选，不能声称基包整个目录仍与历史清单完全相等。

本任务没有真实HTTP/helper、客户Runtime写入、安装/重启、merge/push，也没有以源码/包通过替代两页真实修订质量或三页PPTX。并行Native容器端点与文本渐变将单独测试、独审、提交及后续封包，未阻住本修订候选先行交付。

修订闭环随后已本地提交为 `04dab1d4afc30e293bfabf8f45cab4858c2557d0`；[51个提交blob逐字节核验](./repair-feedback/source-postcommit.json)PASS，parent为6df9251，暂存区空，独立Native改动当时仍未提交。原始unittest日志的三处行尾空格作为原始证据保留，源码/参考严格diff检查通过，包含日志的提交检查仅关闭blank-at-eol。总控随后回报S05正式诊断r81与repair v5单次请求在运行；这是总控真实执行回报，结果未回，不能写成修订图已正确。

## C2 共同容器端点与可编辑渐变文字（2026-09-11）

总控在S04实际转录中确认两处已有忠实转换目标下的表达缺口：共同横条包含两个文案item，向下箭头不能物理猜测起点item；页码12为纵向渐变文字，不能改实色或烘图。沿同一C2并行最小实现，不增加新Change/产品入口，也未阻住repair候选先交付。本地提交基点为04dab1d，Native五文件的初始hash与冻结hash另列于[清单](./native-region-text-fill/native-increment-manifest.json)，其作者冻结时HEAD仍6df9251。

**最终实现**：v3 source-image-derived directed-edge保持旧item端点，新增闭合互斥的from_region_id/to_region_id对，解析到同页同target_image_sha256的既有text/table/shape/image区域。无区域、跨页、自环、关系路径/connector/decoration端点及无可见填充/线的空shape均拒绝。文本item仍由原区域承载，容器不推断成员或给其中一个词增加语义；现有paths坐标与原生对象映射保持，不新增布局或吸附。

v3文字run的fill与旧color严格二选一，保留原文/font/bold/italic，显式fill仅既有solid/有限linear-gradient。新文字渐变在区域登记前拒绝offset×100000不是精确整数的输入，标为CapabilityGap，不静默舍入；旧shape/solid域分支保持。原renderer复用fill转换交给artifact-tool textStyle.fill，未加入第二PPTX writer。结果检查同时确认可编辑a:t、a:rPr/a:gradFill和实际填充；角度/停点按SDK的OOXML整数编码核对，拒绝一个单位篡改，CSS几何容差本身不变。SDK线性角度编码为degree×60000截断整数；这是当前有限格式的明确边界。

| 已形成的验证 | 证据 |
| --- | --- |
| 功能反例与SDK限制 | [初始18项/7预期失败](./native-region-text-fill/red.log)、[一个停点单位篡改RED](./native-region-text-fill/red-sdk-one-unit-gradient-tolerance.log)、[不可表示新文字停点RED](./native-region-text-fill/red-new-text-stop-sdk-limit.log)均保留；环境/探针初次失败日志保留，不伪装成产品GREEN |
| 最终专项 | [79/79 Python PASS](./native-region-text-fill/green-sdk-runtime-results.log)、[7/7 Node renderer PASS](./native-region-text-fill/green-node-renderer.log)，限定生产diff检查通过 |
| 真实SDK而非文档推测 | [创建/导出/重导入证据](./native-region-text-fill/sdk-evidence-report.json)：20原生对象，12为可编辑a:t与90度gradFill，停点0/100000，颜色637F9E/B4D8F0，authoring/reimport一致；4个共同容器箭头分别是原生路径。[当前生产结果检查](./native-region-text-fill/retained-sdk-proof-verification.log)通过 |
| 独立源码审查 | [Scoped PASS / spec PASS / code quality PASS](./native-region-text-fill/independent-review.md)，[7/7独立探针](./native-region-text-fill/independent-probes.log)，实际PPTX的11种角度/停点/颜色/alpha/重复fill篡改全部拒绝，5冻结文件不变；独审初次误以为保留SDK样本有表格渐变，核对handoff后更正探针，原日志保留，生产未改 |
| 调用参考 | [新增两段说明独审PASS](./native-region-text-fill/supplement-review.md)，只描述已实现有限能力与证据边界；[正式交接说明](./native-region-text-fill/HANDOFF.md)包含闭合字段示例 |

合成PPTX `4487b9bfcc9e78c3cd5c0a6f49cc69f36d055ee40e6ef77d5fe259b4f42922fc`保留于`/private/tmp/c2-region-endpoints/sdk-proof/b4698dbd327f6ffb328d6d6cf82c471e0b7051cb739d518d90cc70c640d8fa79/native-anchors.pptx`；它只证明有限carrier能力，不是客户S04或三页PPTX。客户重建/PowerPoint实机为NotRun，客户视觉还原与用户验收为NotEstablished。

### 包含repair的完整后续候选

候选 `/private/tmp/c2-native-exact-candidate-04319fcc-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.nativeexact04319fcc.20260911`，已完成源码、调用参考与[包独审PASS](./native-region-text-fill/package-review.md)，[candidate-summary](./native-region-text-fill/candidate-summary.json)绑定三份确切回执并已交总控。原repair包与在途请求身份未更改、不重发。

| 固定身份 | SHA256 |
| --- | --- |
| Release manifest | `e6c6e9fa2e818d9f30284c204d75214f2a2b73a8f0dbbc3822a0b47ff8b233f4` |
| [108 Python清单](./native-region-text-fill/production-python-manifest.json) | `17306e467c7ac1ac57a95adf3c0ed3571794050cef6dc77dc0722b7523746d37` |
| [受审6文件封包源清单](./native-region-text-fill/package-source-manifest.json) | `6264300c21396bc6e80f51b616b4d5fc9a62d8add41aa2ef84ac7d70cd6ad2e3` |
| 源码独审回执 | `e837fed2030d7cc3f44877b8151aee35d6a095b5c8d61c62b065803f3a91c1f6` |
| 调用参考补充回执 | `f16af26064ba8befb1873103aab9db1f18e9fe314cd75864a8e0b1ad07ee9a45` |
| 包独审回执 | `0e5e5e44b90c0171fc85271a80214c23b60d44d0ea7214aff775a841dc9c8607` |
| tar.gz | `1765670957de7e8cc9a182ca0a0cb3a1edcb7ec765a2297c5a95220a98b48e50` |

候选与基包各3769实际文件；release manifest为3768项，tar逐路径/字节/权限一致，无新增删除/链接/重复或越界。仅3生产、1调用参考与插件版本/manifest共6项改变；108Python中106项不变，依赖与Widget不变，repair全部9Python+2引用说明仍与冻结源及基包逐字节一致，wrapper保持4933c32d。[官方verify](./native-region-text-fill/official-plugin-verification.json)仍为43工具。包独查只核字节/元数据，不重复SDK和源码功能测试。

本源码任务未真实HTTP/helper、客户Runtime写入、安装/重启、merge/push。后续客户图像核对、工作选定、区域登记、Native转换与最终验收均由总控依据实际新回执接续；源码、合成SDK、独审和封包PASS不替代这些真实结果。

## S05 修订动作表达补强（2026-09-11）

上节Native增量已本地提交`92cb155c47f3b2964e96fcbb44cead8203a2d4fb`，本切片从该点继续。总控回报S05 repair v5已completed但四个额外标签仍在，36项原文原行完整。按明确委托只读确切不可变ContextPack、response、原图/诊断身份，并以当时`4933c32d`wrapper纯离线重编译；[旧wire审计](./repair-operation-clarity/old-wire-audit.json)确认原payload、源图字节/尺寸、四bbox与原文一致，旧generic删除指令已经存在。不是错图或漏传问题的证据；未抓取原HTTP报文，不能据此判定模型内部失败原因。

已补齐的可读性缺口：修订公共投影置前，逐issue派生中文补回/替换/删除/原共同规范纠正指令；定义源图xywh、左上原点、轴方向、原尺寸与输出size区别。删除只针对额外的这一次呈现，同时保留完整合法原item及同文不同项，不准挪到别处/换标签继续保留，也不设全页禁词。调用方传输payload仍闭合，供应方公共投影新增固定派生`instruction`；不外发observed_text、排除detail或自由prompt。正文构图自主性保持，Native不删补内容。[新wire审计](./repair-operation-clarity/new-wire-audit.json)绑定同一原始payload，说明前置/逐项变化，不代表已发送新请求。

| 核验 | 确切证据 |
| --- | --- |
| RED/GREEN | [3项预期失败](./repair-operation-clarity/red-validated-fixture.log)后修复；[23项transport/合同](./repair-operation-clarity/green-transport-contracts.log)和[145项相关provider/repair](./repair-operation-clarity/green-provider-repair.log)PASS。初始fixture遗漏copy_facts的错误[原样保留](./repair-operation-clarity/red.log)，未当作功能RED |
| 请求保持 | [12种普通wire逐字节一致，3种repair原数据不变](./repair-operation-clarity/wire-equivalence.json)；没有扩测Native/全项目 |
| 独立源码 | [Scoped PASS / spec PASS / code quality PASS](./repair-operation-clarity/independent-review.md)，[7/7独立探针](./repair-operation-clarity/independent-probes.log)；repair提示以外AST与92cb155相同，认证/网络/重试分支未变。独审两处探针自身假设错误保留，不是产品故障 |
| 规格澄清 | [补审PASS](./repair-operation-clarity/spec-review.md)明确传输字段与供应方派生instruction的区别，规格hash`6dc09cbb4ba7d98755ed1f074b243f64388a15a4c319e8a79b5b0fbe479eb441`；未修改平行四基线或包内refs |
| 完整候选 | [封包独审PASS](./repair-operation-clarity/package-review.md)，3769实际文件、3768项manifest、tar路径/字节/权限一致，[官方verify](./repair-operation-clarity/official-plugin-verification.json)43工具。基于上节完整Native包，仅wrapper/版本/manifest三项改变，其他107 Python及全部Native/refs/依赖/Widget原字节 |

已交总控候选`/private/tmp/c2-repair-candidate-475baf9f-20260911/plugin-release/ai-ppt-studio`，version`0.4.0+codex.c2.repairclarity475baf9f.20260911`；wrapper`475baf9fc4991702fc6ea60ec8a68a792ea4ebedeccb5c86b8ba2c7b06e0a766`，manifest`0dfe0f15c876c5524d1fe68af0d893e11c9f52ac7fcc2bc3d5815f2b94cc38c4`，tar`410160d94be057a5e71a521bf2b27613b895e0c862dee85aa5603df95a9d6269`。[交接说明](./repair-operation-clarity/HANDOFF.md)含全部身份与证据边界；[候选摘要](./repair-operation-clarity/candidate-summary.json)在包独审后只追加了两份已审回执，因此其最终hash与包审时摘要hash分开记录，包目录与tar均未改变。

本任务没有HTTP/helper、客户Runtime写入、安装、merge/push。S05新的真实删除效果仍待新图完整独审；不能以源码/包通过、改变图片hash或S06另次修订通过替代。新Native文本片段与定版照片裁切由另代理独占实现，未混入本包、未在此宣布能力已完成或三页验收。


## C2 原文片段与定版图裁切的忠实原生转换（2026-09-11）

上节 S05 修订表达已本地提交 `4cab684fee73e394075a3800742f9f706cb5e190`，其 [37 个提交 blob 核验](./native-text-fragments-crops/prior-repair-clarity-source-postcommit.json) 原样归档。本增量沿用同一 C2、命名分支与持续制作授权，落实总控四基线 v2.17 §1.3/§1.9；不更新本 Worktree 的平行旧基线。S06 实图转录发现完整原 item 内的文字有独立位置，真实照片需保留定版图中的呈现，原合同缺少对应载体；具体见 [最小规格](../../superpowers/specs/2026-09-11-c2-native-source-fragments-and-crops.md)。

**最终行为。** v3 文本 region 仍拥有一个完整原 item 一次，逻辑 plan 仍为一个对象；可用闭合、互斥、非递归 fragments，按 Unicode 码点 `[start,end)` 连续完整覆盖原文。每片段的 runs 必须逐字等于原 span，bbox 来自同一实图区域。renderer 仅在原生载体层展开稳定子对象身份，结果读取实际 PPTX 每个子对象的文字、样式和位置，并完整回组原 item。空格、分隔符、组合字符和 emoji 不归一化、不删改；伪造映射即使重算 hash 也拒绝。source-image relation-path 保持整 region/item 引用；旧物理 connector 指向 fragments 时写前 CapabilityGap，不猜子框或隐式父框。

v3 real-material image 可保留原四字段 material_binding，并显式选择 `render_source=selected-image-crop`。事实身份仍是原材料，呈现来源必须是本页 TargetBinding 的整张确切选定图原字节加明确 crop；原材料角色、来源与覆盖继续核验。不允许无绑定、错页、任意预裁图或将 decoration 冒充材料。无 marker 的原材料字节规则保持，不能静默恢复原 JPEG 改变设计。

真实 SDK 验证发现 `fit=contain` 与 `fit=cover` 在默认比例锁下都会改写明确 crop/frame。对已通过 crop/bbox 比例核验的显式局部裁切，使用公开 `lockAspectRatio=false` 保留确切裁切与图框；必要修复同时覆盖普通无字 decoration 的 partial crop，原全幅行为保持。没有新增 writer、重采样源图或把主要文字烘图。

| 核验范围 | 已形成的证据 |
| --- | --- |
| RED 与原因 | [合同 RED](./native-text-fragments-crops/red-contracts-and-crops.log)、[SDK contain](./native-text-fragments-crops/red-sdk-contain-crop.log)/[cover](./native-text-fragments-crops/red-sdk-automatic-cover.log)、[旧 partial decoration](./native-text-fragments-crops/red-sdk-legacy-partial-crop.log)、[bool span 映射](./native-text-fragments-crops/red-mapping-span-type.log) 均保留，不把初轮探针假设错误算产品故障 |
| 相关回归 | 冻结生产源上 [102/102 Python](./native-text-fragments-crops/green-focused-suite.log) PASS；随后只增加纯双空格测试，最终两测试文件 [24/24](./native-text-fragments-crops/green-whitespace-and-sdk.log) PASS；[Node 7/7](./native-text-fragments-crops/green-node-renderer.log) PASS。三组分别记录，不累加重叠项或重复无关全项目测试 |
| 实际 SDK 载体 | [导出/重导入报告](./native-text-fragments-crops/sdk-evidence-report.json)：10 逻辑对象/14 原生对象，5 个片段完整回组含 emoji、组合字符和分隔符的 22 码点原 item，`[16,18)` 两原空格独立可编辑；2 个同原材料 role crop 和普通 partial decoration 的嵌入图 hash、几何、裁切及样本像素正确。作者 9 个实际 PPTX 篡改均拒绝 |
| 独立源码审查 | [Scoped PASS / spec PASS / quality PASS](./native-text-fragments-crops/independent-review.md)，[8/8 独立探针](./native-text-fragments-crops/independent-probes.log)；新增 6 种实际 PPTX 与 3 种重 hash 映射篡改全部拒绝，2 次冻结 renderer 本地 SDK 重导入/快照通过，七文件和原成功制品均未改 |
| S06 只读适配 | [确切草稿检查](./native-text-fragments-crops/s06-final-draft-contract-check.json) 绑定草稿 `07be083fc50e8d5a53e282da9270db42584ca1123ec8119ef2bc0a01a5414b78`，86 region、19 完整原 item 原序一次覆盖、6 个分片区域/26 片段。44 个 image/decoration = 3 个材料 crop + 41 个普通 partial crop；不是正式 inventory 或视觉验收 |

### 完整候选与交付身份

已交总控 `/private/tmp/c2-native-exact-candidate-7cb3857f-20260911/plugin-release/ai-ppt-studio`，version `0.4.0+codex.c2.nativefragments7cb3857f.20260911`。[封包独审](./native-text-fragments-crops/package-review.md) PASS，3769 实际文件、3768 manifest 项，tar 路径/字节/权限一致；只变 3 生产文件、1 调用参考、版本/manifest 共 6 项。其他 106 Python、repair/wrapper、依赖、Widget 与其他参考原字节保持；[官方核验](./native-text-fragments-crops/official-plugin-verification.json) 43 工具通过。

| 固定身份 | SHA256 |
| --- | --- |
| 七文件冻结清单 | `28bd83b11eb3dab6383cbfd110f295773e226742853a57e58d31617f9d2523a7` |
| wrapper（保持） | `475baf9fc4991702fc6ea60ec8a68a792ea4ebedeccb5c86b8ba2c7b06e0a766` |
| Release manifest | `cf5a95ec62300084a2c13a78e465e12c73f13a49212e683eb52c075a19898381` |
| 108 Python 清单 | `7018710fee3866b15b01806927fb23813dfd10d77f4d4307de1a3dcbfd06ba17` |
| tar.gz | `c67a6b89a6b7efc5dc5077786fb4cd2d9fc3ee1a870947967d8e49dbade72d7b` |
| 源码独审回执 | `12c07840d95ab20f807ef8e2591f374b804b8990c40c8431c7f78ccd155e7a18` |
| 包独审回执 | `92053d287125e22868d9785d381fca58b9d869a46ba60cbca72d2ed0ff0d56ca` |

[候选摘要](./native-text-fragments-crops/candidate-summary.json) 在包审结束后只追加外部状态与回执，摘要 hash 从包审时 `b2c2e578b2803a0032c982ea858878521e8541efb0b4bda8a8da897aa9482231` 变为 `273bf7d625967f97f2b938418949f046631c8ca4efb5d21753dd84ab2c299007`，封存包及 tar 未改，[交接核验](./native-text-fragments-crops/review-and-handoff-verification.json) 记录该差异。候选在本地 Native 提交前已交总控，属于受审确切覆盖包，不冒称完整 Git 快照。

总控随后回报 [S05 v6 实际结果](./native-text-fragments-crops/controller-s05-v6-result.json)：完整 36 项及来源四项 passed，candidate r96 已正式入链，图 SHA `9607b6d10217d4576b327888f104357ed86cf9246b711db3c31e584e8f96da08`；source task r97 正绑定，最终引用尚未回到本任务。它是总控实际执行回报，不是本源码任务独立生成或客户验收。新发现的 S05/S06 字体横向 fit 风险另作 SDK 只读能力调查，不修改这批冻结源或候选，也不静默缩字换字符。

本源码任务未真实 HTTP/helper、客户 Runtime 写入、安装/重启、merge/push。合成 SDK/PPTX、独审、封包与草稿字段通过不能代替客户三页还原、字体墨迹匹配、PowerPoint 或用户最终验收。客户正式区域登记与三页原生输出由总控继续串行持有。


## C2 完整三页 Native 资源与真实字体修复（2026-09-11）

从 `64a57d0601ae96ecabc18fdd9ed5a46fac0ce500` 继续同一隔离 Change。原三页 550 regions / 576 native objects 在导出阶段因重复嵌入整页 PNG 触发 WASM OOM；现于深拷贝的公开 export proto 按实际 bytes 去重，每个对象仍独立，真实材料三页导出、回读、inspect、render 及正式 byte-backed preflight / 新 Node snapshot 全部通过。具体根因、失败探针与纠正、图片单对象替换隔离、真实微软雅黑与精确字号编码见 [修复报告](./native-resource-recovery/recovery-report.md)；原始日志、源字节身份及后继独审/候选回执见 [验证清单](./native-resource-recovery/validation.json)。

实物为 4,774,124 bytes 的隔离 `native-diagnostic.pptx`，SHA256 `ecec539ca6f3ced9b13f6ce203a57d0440b858348403272fe9ed3039c280d012`；三个 media 完整保持选定原图 bytes。只有 task_id / 输出目录派生，原 TargetBinding、文案、550 regions、裁切与层次均保持。真实 Microsoft YaHei Regular/Bold 400/700 的文件 hash 与加载证据固定，STHeiti alias 旧探针不再作为字体证据。字号精确比较实际 SDK centipoint 编码，坐标与梯度检查未放宽。

Node 六文件22/22，随后只改 helper 的 live metadata 丢失保护并通过对应 SDK 回归1/1；Python 相关33/33与 diagnostic/font集成13/13分别通过，全部零skip，不累加重叠项或冒称全项目回归。资源共享后的普通 SDK `replace` 会连带改变其他对象，受保护 helper 仅在独立 proto 中替换目标；任何不能往返保留的属性明确失败，原 presentation 不变。新字体模块列入构建allowlist和包验证必需文件，候选必须有完整运行依赖及实际 MCP probe 回执。

本结果属于真实客户材料的隔离诊断验证，客户 Runtime 正式注册及 Gate 由总控持有。S05两个渐变接缝按总控独立视觉定位继续区域修订，不在本轮擅改；工程通过不替代视觉忠实、PowerPoint或用户验收。没有客户 Runtime写入、安装/重启、merge/push或新增生图。最终源提交与可运行候选身份由同目录冻结交接记录维护。

## C2 工程收尾与三页用户验收归档（2026-09-11）

本轮由总控明确交回原 C2 owner，在同一 `codex/image-led-native-anchors` / `28a9` Worktree 收尾；起始 HEAD `9f24ddebed63b1bc103e61344f53755a82a65756`，生产源码仍为 `25af79b28f291d3e59538c1f08970c5fdd92bc44`。已按顺序核对执行端四基线、主计划 §5/§12.2/§12.4、派发入口及总控未提交的验收交接。后者只读作为真实决定来源，没有整体复制成第二执行台账。执行端四基线为已批准 v2.14；后续委托工作选择、诊断与原文片段等规格引用总控后继批准版本，该跨分支基线衔接保留为集成前事项，不擅改平行权威基线。

### 已发生的用户验收及确切制品

用户在总控当前对话明确说：“生成的可编辑的 PPT 验收通过 接下来下一步呢做啥呢”。总控交接任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 将该决定绑定此前交付文件；本执行再次实读以下身份，**该文件的用户验收状态为 accepted**。不重复索取同文件验收，不为了额外视觉精修替换该成果。

| 身份 | 本轮核对结果 |
| --- | --- |
| 项目 / 页面 | `c2-image-led-native-anchors-20260909` / `C2-S04、C2-S05、C2-S06` |
| 文件 | `/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909/diagnostics/97ceb010d5665a23e4d0ad9e94cebcd6b981d2bc4f6f44fde02e3671952def7e/native-diagnostic.pptx` |
| PPTX SHA256 / 大小 | `1797900779255f539f659f806b9ae140b7490fbd5b245675f844ccb36096e2a6` / 4,774,124 bytes |
| selection | `artifact://image-led-selection/0deb8a26780fba4cf51c5cdc675a7c46c9b930bc1dbd1762a5edbeb6d849488f` |
| 本文件 handoff 的区域清单 | `artifact://image-led-region-inventory/2283dfe8a1aa9fd23b46a43109139d3edd809a86854c856e092ca452c41820a1` |
| 当前 Runtime 区域清单 | `artifact://image-led-region-inventory/1764231174a2a36e86f7b7c95bd56b53c10d116b78a34b8e3494dd461d6983a3` |
| 当前 Runtime | r107，G0 `passed`，G1 `open`，G2/G3/G4 `locked` |

两份区域清单的实际差异仅为 S05 两个 region 的 `appearance.fill` 角度和 stops；尚未进入已验收 PPTX。本次验收不转授当前清单的未来输出，不自动创建逐项 `accepted_deviations`，不补写用户逐图确认。诊断输入/结果正式 refs 已存在，但正式 `visual/contracts`、`visual/compilation-plan`、原生锚点/正式 build-result 与 G2/G3 当前通过未建立。具体 refs、文件 hash 和前后检查见[本轮 Runtime 身份](./engineering-closeout-20260911/runtime-identity.json)。

历史 `result.json` 的 `engineering-output-unassessed` 及三个 `not-established` 是生成时的不可变记录，保持原字节；后来的用户验收单独在本节记载。诊断制品、用户验收、正式构建结果、PowerPoint 目标证据和 Runtime Gate 各自保持身份与时间，不互相代签。前一节 `ecec539c…` 隔离诊断制品也不是本次 `179790…` 已验收文件。

### 当前制品的工程检查与缺口

- [原生 OOXML 和实际映射检查](./engineering-closeout-20260911/accepted-structure.json)通过：3 页、550 regions、576 原生对象。检查由当前源码直接读取此 PPTX，包括文字片段、样式、几何、关系、图片 bytes/crop 及实际对象映射，不能据此替代目标 PowerPoint 操作或用户审美判断。
- [完整 preflight 重放](./engineering-closeout-20260911/accepted-preflight.json)在最后 fresh-render 像素比对失败：`Submitted render is not the current PPTX rendering`。前面的文件身份和 OOXML 阶段已执行；单独结构检查通过不改写完整 preflight 为 PASS。[只读渲染差异](./engineering-closeout-20260911/accepted-render-diff.json)绑定确切微软雅黑 Regular/Bold 和当前 SDK，三页每通道平均绝对差为约 0.103 / 0.090 / 0.118，最大差 43 / 84 / 131。该统计仅用于定位，未批准任何新容差，也不宣称已经证明唯一根因。
- 已验收 PPTX、handoff、result、mapping 与 state 共 5 个指定文件的前后 hash/mtime 一致，r107/Gate 不变；这是这些文件的只读证据，不冒称全 Runtime 树已逐文件重验。本轮所有新渲染、合成输出和测试数据仅写临时隔离目录，客户原文件不变。

### 本轮回归、最小修复与包核验

全量 Python 在 bundled Python 上 **1011/1011，0 fail、0 skip**，185.724 秒。最初使用系统 Python 的一轮因 x86_64 进程加载 arm64 Pillow 扩展而失败：843 项、6 failures/63 errors/2 skips；连带候选失败不直接认定为生产缺陷。保留失败日志和解释器差异，改用现有 bundled Python、只读来源复制的纯 Python YAML 依赖后完整重跑，没有安装依赖或修改业务代码。

Node 首轮受 sandbox 禁止本机监听影响；获准本机 Review Bridge 测试环境后，唯一剩余失败为 MCP schema 旧快照。只移除新增 `build-native-diagnostic` actionType 枚举即可精确恢复旧 schema 摘要，证明其他 43 工具 schema 未变，见[schema 差异证据](./engineering-closeout-20260911/schema-audit.json)。本轮仅修正 `tests/mcp-server.test.mjs` 的固定摘要及精确动作列表；保留初始摘要 RED 和后继枚举 RED，聚焦 **33/33 PASS**。没有改生产行为、删除测试、放宽合同或扩充公开工具。

最终 `npm run quality` **exit 0**：TypeScript、Widget build 通过，**Node 220/220、0 skip；Widget 16 文件 / 770/770**。R3 token-map、text-anchor、ReviewMark 与既有审核回归包含在全量中。日志和执行命令见[质量回执](./engineering-closeout-20260911/quality.json)及[Python 回执](./engineering-closeout-20260911/python.json)，各自完整成功日志随附；quality 归档视图仅移除末尾空白行，原始日志与 hash 保留在执行回执中。

[异内容双组三页验证](./engineering-closeout-20260911/two-group-proof.json)使用当前同一通用 renderer 实跑 A/B：对象数分别 4/5/5 和 5/5/5，页 ID、文字、数字及几何不同；两份 PPTX hash 不同，均为合成工程输出。它证明当前通用构建路径不依赖三页固定内容，不是第二个真实客户项目/G3/PowerPoint。当前委托工作选择入口按其明确批准规格限制 S04/S05/S06；不把该临时授权范围误报成任意页面委托选择能力。

[封存包官方验证](./engineering-closeout-20260911/package-verification.json)与 stdio probe 通过：manifest 3771 条、43 工具。版本 `0.4.0+codex.c2.native-resources.20260911`，manifest SHA256 `2e4dc176f90b922a84e1558327c2847e6f344f44819529e316f80464a76fe677`，原 tar.gz SHA256 `9aa293548ae46dcf7f3be51ce6b0f42702f005afd0c071600d3ac95f266686d1`。历史已使用的包目录多了 6 个 `__pycache__` 文件，受 manifest 管理的内容零修改/零缺失；保留其目录和失败记录，从该 hash 固定 tar 安全解出洁净副本再验，不删除历史缓存来伪装原包从未改变。本轮无生产修改，未重标包版本或声称由本次文档/测试提交重新构建。

[静态审计](./engineering-closeout-20260911/static-audit.json)中 148 个封包来源与当前源码 hash 一致，四基线 78 个文件链接及 6 个原型引用可解析；不冒称 fragment anchors 已检查。所有回归在 1435 个 tracked 文件的隔离快照、私有依赖副本和空测试 Runtime 配置中运行；最终只将这一个测试文件及本轮台账/安全证据纳入候选。原工作区 `node_modules` 是既有未跟踪链接，保留且不提交。

### IL02-AC01..AC10 当前证据矩阵

状态针对 AC 的完整文字；分项通过不能提升包含真实 Gate/独审条件的整项。

| AC | 当前完整状态 | 已证明及尚缺事项 |
| --- | --- | --- |
| IL02-AC01 | `NotEstablished` | 基本设计/内容/原生责任与生产拒绝回归成立；执行端 v2.14 与总控后继基线的完整同候选衔接、当前真实结果严格重放仍需闭合，不能以单个切片独审替代整体一致性 |
| IL02-AC02 | `NotEstablished` | 真实 G0、图像、工作选择、诊断 PPTX 和用户验收已有；r107 未形成正式合同→锚点→当前 G2→真实 G3 全链 |
| IL02-AC03 | `Passed`（工程边界） | 当前全量回归覆盖项目/页序/内容/材料/图像身份、假选择和错版本零业务写入；本轮实物 selection/旧 region/PPTX hash 已核对，不转授历史决定 |
| IL02-AC04 | `Passed`（工程边界） | 当前合同、regions、Runtime 与实际 PPTX 反例覆盖缺漏、改数字、关系端点和真实材料替换；主要文字/表格/关系不可借位图放行 |
| IL02-AC05 | `Passed`（工程边界） | 确定派生与篡改、过期引用、图像替换、路径越界、既有输出保留反例通过；渲染重放的真实制品缺口另列，不改写为接受旧证据 |
| IL02-AC06 | `NotEstablished` | 当前通用 renderer 双组三页合成实跑通过，无页内容固化分支；真实三页目前是诊断路径，完整正式构建的无临时编排依赖尚待正式链证明 |
| IL02-AC07 | `NotEstablished` | 当前源码 G2 lineage/失效/假回执反例通过；客户 G2/G3 未通过，不能以 synthetic G2/ReviewSession 代签实际宿主 |
| IL02-AC08 | `Passed`（工程边界） | legacy 兼容、旧制品不自动获新路线验收和保持历史边界的当前回归通过；本轮没有旧项目原地迁移，客户读验与测试 Runtime 分离 |
| IL02-AC09 | `Passed` | 同一生产源码下 Python 1011、Node 220、Widget 770 全部通过，typecheck/build 通过；本轮只改既有 schema 回归预期，无生产修改 |
| IL02-AC10 | `NotEstablished` | 指定三页 PPTX 用户接受已成立；历史分段独审保留原 SHA/范围，尚需总控对本次精确冻结候选的规格/工程独立 Review，及明确可申请集成结论 |

**未闭合项与集成边界：** 本地工程候选可交总控独立 Review；C2 整体退出、正式 G2/G3、目标 PowerPoint 当前文件打开/编辑/保存/重开、当前保存 PNG 的严格重放、完整后继基线衔接仍未建立。真实 PowerPoint 本轮 `NotRun`；其证据为 `NotEstablished`，未据缺回执假称宿主一定无能力。作者不能对自己完成独立 Review。不得将用户验收转成 Gate，也不得要求用户重复验收同一文件来掩盖工程缺口。本轮未 merge、push、安装、重启、发布插件或启动 C3。提交 SHA 由本次 Git 对象和总控交接回执绑定，避免台账自引用。


## C2 收尾证据 Minor 补正（2026-09-11）

作者隔离审查绑定 `9f24dde..b8e788fcf01d3e71cfc4844617b04d75ef7ca209`，结果 **Critical 0 / Important 0 / Minor 2**；[原始独审报告](/private/tmp/c2-closeout-independent-review-20260911.md)保持原 SHA/范围，不追认后继提交已被独审。本轮只处理 M-01/M-02 记录问题，不改生产代码、测试、客户 Runtime/PPTX/PNG、Gate 或校验阈值；不重跑全量套件。

- **M-01 已补正**：[source-verification.json](./engineering-closeout-20260911/source-verification.json)按原始 1435 路径重新比较。相对原始清单的最终修改为派发 README、唯一台账、schema 测试；相对已测试快照的两个文档例外为 README 与台账。旧“只排除台账后无差异”字段现在明确仍有 README，新字段只在排除这两份事后文档后报告无差异。它不把后来新增证据附件算入原始 1435 路径。
- **M-02 已补正**：[accepted-render-diff.json](./engineering-closeout-20260911/accepted-render-diff.json)新增 PPTX/handoff、六张保存/新渲染 PNG 的绝对路径和实读 SHA256、原运行入口、生产 renderer/测试快照 renderer/字体加载器、Node、artifact-tool 2.8.59、sharp 0.35.4、skia-canvas 3.0.8 的确切路径和入口/包文件 hash。执行依赖的补记明确标为本轮实读，版本与独审观察相符，不伪造原执行时的二进制签证。历史入口直接调用 SDK 导入/导出，与生产 render() 构建器分别说明。
- [只读统计复核入口](./engineering-closeout-20260911/reproduce-render-statistics.mjs)先检查确切文件 hash，仅读取现有 PNG、重算 RGBA 0–255 差异并输出 stdout，不重渲染、不写文件、不调用 Runtime。`bbox` 明确为左上原点、整数像素的双端含边界 `[min_x,min_y,max_x,max_y]`；统计用 sharp.ensureAlpha().raw()，不额外转换色彩空间。[本轮聚焦回执](./engineering-closeout-20260911/render-statistics-verification.json)三页数字与原记录完全一致，六 PNG hash 与独审报告一致。

[evidence-manifest.json](./engineering-closeout-20260911/evidence-manifest.json)同步上述两个 JSON 及新增入口/回执 hash。原始全量测试通过事实、用户接受 `179790…`、Runtime r107、当前严格重放失败和 AC 矩阵保持原边界；本次统计重现不是完整 preflight 通过，不证明字体/SDK/色彩等唯一根因。两项记录问题已由作者修正，后继候选仍由总控核定；C2 正式链、当前 G2/G3、目标 PowerPoint、严格渲染重放及后继基线衔接仍未闭合。原独审只允许有条件集成申请准备，不授权无条件集成、merge、安装、发布或 C3。

## C2 已有三页复用与对话确认补强（2026-09-15）

- 当前真实 Runtime r142：G0/G1/G2/G3 passed，G4 open，agent/task/active 已移除。此前 r141 误排的 836055b4… native-anchor 重建任务没有输出，经 Python 事务取消，历史保留；不重建或重新验收既有三页。
- 正式 native-anchors.pptx SHA256 为 bc8df49178b1ae9e3831caf6a81bab5bfaa2c029aff056291d60bfc1421be5e5。它与 current build-result/anchors/G2 macos-powerpoint 目标证据一致。本轮 current_anchors、validate_current_g2_evidence 在 bundled Python 实际重放通过，现有三张 render 已实际查看。
- G3 在 r140 写入，ref 为 artifact://g3-confirmation/0f24ca092952ebe5bd136cf5db8568a3390dbae12965e5aa129acba74bbace68，绑定 r139 和真实用户消息 msg_01a09f7d-1a86-7e81-903c-1633d735368f。补强后的日志核验再次匹配紧邻审核说明、project/source/revision 和 7 项证据；不重写原回执。
- 前几轮把 G4 当作 C2 退出条件、放宽 G3 后全部视觉写入保护、把 build-native-first 用作交付构建均属错误推进方向；两处冻结条件已恢复，未重新打开 G3。C2 的证明边界以主计划 §5 为准，G4/整套交付仍属 C3。
- 消息核验器新增 scoped message ref、正式快照与显示上下文检查、否定/引用/嵌入/旧版/跨项目/继承/重复/撤回拒绝，生产 G3 独立 adapter 不再借用通用 verifier。详见[本轮合同](../../superpowers/specs/2026-09-15-c2-chat-g3-confirmation.md)。本机日志读取不等于防恶意本机重写的密码学证明。
- 定向验证：消息绑定 29/29；MCP server 33/33；Python bridge 14/14；Python visual bridge/review/cancellation 21/21；四基线 80 个相对链接可解析。未把早期 1011/220/770 全量测试计作本轮结果。
- 独立代码审查实例 01a0a0ce-95d6-73d1-b6c1-1e08d1c6102b：两项 Important 分别通过自然对话合同澄清和独立 verifier 隔离修复关闭；结论限本轮消息适配，不替代 C2 整体 Review。
- 当前源码在已登记 28a9 Worktree；Git 报 bad tree object HEAD，无法声明新冻结提交、工作区干净或已集成。本轮补强写入源码及当前缓存/市场文件并更新 manifest；未重启/退出宿主，也不把磁盘更新等同于全部长驻 Node 进程已热加载。
- 用户结论报告：[已有三页核验](</Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909/output/c2-existing-result-review-20260915.md>)。已解决历史矩阵 AC02/AC07 中“没有真实 G2/G3”的具体缺口。AC01/AC06/AC09/AC10 的当前候选一致性、异内容三页泛化、全量回归和总控集成判断仍需闭合；不宣布 C2 整体完成。

## C2 最终退出核验（2026-09-15）

| AC | 当前结论 | 依据 |
| --- | --- | --- |
| IL02-AC01 | Ready-for-integration-review | 当前四基线、C2 规格、Skill、Runtime 和 Image-led 职责一致；聊天 G3 合同、bundled Python、冻结保护已补强。Git 仓库对象损坏，无法形成新的提交身份。 |
| IL02-AC02 | Passed | 真实项目 G0/G1/G2/G3 均 passed；G3 回执绑定当前视觉合同、三页 anchors、compilation plan、目标证据和真实用户消息。 |
| IL02-AC03 | Passed | 当前 selection、regions、合同、计划、anchors、PPTX 和用户确认均为项目内精确 artifact ref；消息核验 29/29。 |
| IL02-AC04 | Passed | 当前 C2 Image-led 合同、原生结果和既有负例测试覆盖缺字、错数、错关系、换图、整页位图和未授权对象。 |
| IL02-AC05 | Passed | 当前 compilation plan、handoff、结果和输出路径经过精确引用与 hash 检查；发布包原生回归通过。 |
| IL02-AC06 | Passed (engineering boundary) | 已有两组三页不同页 ID、内容、几何和对象数的同 renderer 合成证明；真实正式成果沿用三页结果，不以泛化样本冒充用户验收。 |
| IL02-AC07 | Passed | current G2/G3 lineage 已实际重放；旧 G2 目标证据和新 G3 回执均未被改写，误排重建任务已取消。 |
| IL02-AC08 | Passed (engineering boundary) | legacy 读取与旧制品不自动升级的回归通过；没有旧项目原地迁移。 |
| IL02-AC09 | Passed | Python 1014/1014、Node 249/249、Widget 770/770、TypeScript 通过；发布包 3772 文件和 43 工具校验通过；bundled Python 架构正确。 |
| IL02-AC10 | Ready-for-integration-review | 当前三页已接受，独立定向 Review 无 Critical/Important；新的候选发布包已校验。由于 Git HEAD/tree 对象损坏，暂不能形成可合并提交或声明已集成，交总控作集成判断。 |

最终 C2 交接结论：三页正式成果、真实 G3、当前工程验证和候选包均已完成；C2 可交总控申请集成。本次不执行 merge、push、发布、G4 或 C3。

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
