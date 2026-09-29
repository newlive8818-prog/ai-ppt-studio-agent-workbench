# CHG-IL-C3｜整套编排、三类修订、中断恢复与整套交付

## 1. 身份与状态

- Change 标识：`CHG-IL-C3`
- 状态：`最终 C3 本地发布候选已构建、验证并安装登记，待当前宿主重启验证`；当前未合并、未 push、未建立宿主加载回执；43 页完整原生还原、整套 PowerPoint 证据与最终交付仍为 `NotEstablished`
- 基线：`3fd07c1ac9931d062efaddec7ae822cdf94e1746`（tree `6f4dd3ff782bb23f408736b03994dc2bdb362a38`，687 文件）
- 基线来源：官方仓库分支 `codex/c2-baseline-20260917`；防灾副本 `/Users/defei/Documents/Codex-Recovery/ai-ppt-studio/c2-c3-line-20260917/PPT-codex-app`；bundle `/Users/defei/Documents/Codex-Recovery/ai-ppt-studio/c2-20260915/c2-controlled-integration-3fd07c1.bundle`
- 开发线：分支 `codex/c3-whole-deck-20260917`，Worktree `/Users/defei/.config/superpowers/worktrees/PPT-codex-app/c3-whole-deck-20260917`
- 上级计划：`产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md` §6（C3｜整套制作、局部修订、恢复与交付）
- 权威基线：项目根四份 v2.17 已批准基线；本记录不替代它们

## 2. 用户结果

产品正式能力目标仍是一份完整、认可、可继续编辑的售前 PPT；本 Change 的结项证据按用户最新决定收缩为四页代表性方法验证，不把代表页结果写成 43 页整套交付。

## 3. 范围

1. 整套编排与设计系统复用：完整蓝图每页都有合同和成果，不漏页、不重页，不把同一构图套到所有页面。
2. 三类修订：单页视觉修改、内容变更、整套风格修改，各自维护依赖、失效与当前审核身份。
3. 中断恢复与整套交付：中断不丢上一有效结果；外部请求结果不确定时保持 pending/blocked，不盲目重发；最终 hash 使用新的目标证据。
4. Delivery / G4 与整轮计时。

## 4. 验收条件（引自主计划 §6.3，未改写）

- [ ] IL03-AC01：实际完整蓝图全部页面和冻结内容被覆盖，页序正确；自动 12 页案例无漏页、重页和错绑定。
- [ ] IL03-AC02：用户接受整套视觉语言、页面变化和材料表达；字体/颜色在原生层落实，差异可解释且被接受。
- [ ] IL03-AC03：单页视觉修改后内容不变；其他页不因实现便利被重新设计；复用的输出仍有当前有效依据。
- [ ] IL03-AC04：改变数字/文案等内容时回到规定的内容与 G0 流程，旧视觉证据不能继续批准新版；没有后台改字保留旧 G0。
- [ ] IL03-AC05：整套风格修改使受影响合同、计划和审核过期；页面不可混用两套未经批准的设计系统。
- [ ] IL03-AC06：分别在生成返回、切图/构建、审核提交三个位置注入中断；恢复无业务重复写、无制品覆盖、无假完成；无法确定外部请求是否成功时明确 pending/blocked，不盲目重发。
- [ ] IL03-AC07：最终整套 PPTX 的当前 hash 完成适用目标 PowerPoint 检查及编辑/保存/重开；不复用 G2 或前版 PPTX 证据。
- [ ] IL03-AC08：文件真实交付，当前交付包、发送回执、目标证据和用户 G4 对应；代码合并或文件生成不替代 G4。
- [ ] IL03-AC09：整轮时间、人工等待、生成、重建、验证、返工次数均可追溯；没有每页临时手写脚本依赖。
- [ ] IL03-AC10：适用回归和组合验证通过，独立 Review 无未关闭 Critical/Important；用户明确接受当前完整文件。

## 5. 入口条件

真实客户试点进入正式内容与视觉流程须具备以下条件；独立工程和合成回归可先开展：

1. W1 导入成立：官方仓库 `codex/c2-baseline-20260917` 可解析，防灾副本可回读；
2. 当前真实材料可由 Runtime 重放、逐页证据与完整内容蓝图经正式审核并通过 G0；
3. 用户对试点和后续整套交付范围的授权。

第 1 项成立。代表性客户 43 页原件、六页试点和整套扩展是历史执行范围；2026-09-23 至 2026-09-24 用户明确改为以 P01/P19/P28/P41 四页代表样本验证方法，并以此作为 C3 结项边界。该决定不把 43 页完整交付、G4 或正式产品的全稿能力降为四页。

## 6. 明确不做

- 不关闭 G4、不 push；本地提交与安全集成按 2026-09-24 结项授权执行。
- 不修改 C2 已认可的 Runtime 项目、三页锚点或 G3；C3 源码变更仅在本独立 Worktree，不能冒充正式宿主已加载。
- 不重复创建开发线；不在官方仓库主检出（`codex/quarantine-mixed-worktree-20260825`）上开发。
- 不删除或伪造 14 个缺失 refs、12 个不可恢复 worktree、已知 `DIST-NOT-REPRODUCIBLE` 偏差。
- 不用合成 12 页回归冒充真实客户验收。

## 7. 回滚与停止

先隔离新项目，保留原始材料、历史制品、上一有效交付和恢复点；失败不重置整个项目、不清空用户反馈。集成/安装/发布另行批准。

## 8. 2026-09-24 结项边界与用户决定

1. 用户明确表示不再完成 43 页全部原生还原，以 P01、P19、P28、P41 四页代表样本继续验证即可；随后进一步明确“这是为 C3 通过”，要求检查剩余代码并尽快结项。
2. 本次 C3 通过证明以下能力链已形成并可由代表性页面验证：
   - 定版设计图可以按区域拆解为原生文字、业务容器、关系线和独立图片层；
   - 截图、Logo、复杂背景等适合保真复用的内容保持独立图片对象，不以整页位图冒充可编辑交付；
   - 现有稿路线必须覆盖全部当前来源页后，才能建立 selection、native plan、native result、逐页 QA 和 delivery candidate；四页样本不能绕过整套交付门；
   - 内部选图明确记录 `human_image_approval=NotEstablished`，不冒充用户逐页定版。
3. 代表样本 PPTX SHA-256 为 `59782e2a4892314400f509ed4d479cc9a5e62d6e9be53777883ef36ffc695150`，共 4 页：P01、P19、P28、P41。验证统计和对照图保存在 `docs/validation/c3-whole-deck/representative-native-sample-20260923/`。
4. 仍未建立且不得冒称完成：代表性客户 43/43 selection、43/43 原生还原、43/43 QA、同一最终 PPTX 的 PowerPoint/LibreOffice 人工编辑保存重开、正式 delivery、G4 和 43 页完整文件用户验收。
5. 原 §4 的 IL03-AC01–AC10 保留为完整产品/整套交付验收合同；用户本次仅收缩 C3 Change 的实物结项范围，不修改正式现有稿优化能力的全页覆盖和完整交付门。

## 9. 2026-09-24 历史源码结项验证

- 历史 bundled Python 全量回归：`1327/1327` 通过；无失败、无错误。该结果绑定 2026-09-24 当时的 bundled 依赖，不再作为当前集成 Gate。
- 完整 `npm run quality`：TypeScript typecheck、Widget build 通过；Node `265/265`，Widget `774/774`，均无失败或跳过。
- 61 个公开 MCP 工具的目录、handler 和 Python operation 一致性通过；现有稿专用完整交付门继续拒绝部分页结果冒充 delivery。
- 四基线 80 个相对链接中保留 14 个既有历史缺口，6 个原型引用全部存在；`git diff --check` 通过。
- 本 Change 可在用户确认的四页代表性方法验证边界内提交并建立本地集成分支；不 push、不关闭 G4，不宣称代表性客户 43 页完整交付完成。

## 10. 2026-09-28 Artifact Tool 2.8.77 收尾修正

1. 总控在当前 bundled Artifact Tool `2.8.77` 上复现了 `df7e0d88` 的全量失败。独立归档副本再现确认：测试发现数仍为 `1327`；执行时 `test_image_led_g2.ImageLedG2Tests.setUpClass` 在其唯一测试开始前失败，因此 unittest 报告 `Ran 1326 tests`，另记一个类级错误。完整结果为 `18 errors / 3 failures`，均由 `native slide inherited unselected visual objects` 引起。`1327 → 1326` 不是测试被删除。
2. 根因是结果校验器遍历 PPTX 包内所有 layout/master，而 `2.8.77` 会同时打包未使用的默认 layout，其中包含标题、页脚等占位形状。修正后从每张实际 slide 出发，只沿其唯一 `slideLayout` 及该 layout 的唯一 `slideMaster` 检查活动继承闭包；缺失、多重关系继续失败关闭，活动 layout 或 master 出现未选定可见对象仍会拒绝。
3. 测试先行回归已记录旧实现 RED；修正后证明“未使用默认 layout 含占位形状”可通过，并对活动 layout 和 master 分别注入形状证明仍会拒绝。相关 Python 回归 `249/249`；当前完整发现和执行均为 `1329/1329`，`OK`。
4. 当前同一工作树的 `npm run quality` 通过：TypeScript typecheck 和 Widget build 成功，Node `265/265`，Widget `16 files / 774/774`，无失败或跳过。
5. 四页代表样本原始 PPTX 已找回，字节 SHA-256 精确等于历史摘要中的 `59782e2a4892314400f509ed4d479cc9a5e62d6e9be53777883ef36ffc695150`，并持久保存在 `/Users/defei/Documents/Codex-Recovery/ai-ppt-studio/c3-20260924/代表性客户方案-4页原生可编辑还原验证-20260923-v3.pptx`。PPTX 不进入产品 Git。
6. 当前已启用插件仍是 `0.4.0+codex.c3.historical-import-20260921`，目录合同为 60 工具；当前 C3 源码为 61 工具。最终 C3 包的构建、安装、重启和 61 工具宿主回读必须等总控复核后完成，当前不得写成已发布、已安装或已加载。
7. 客户验证画面仍在本地 C3 Git 历史中。当前不 push；进入远程仓库前必须确认保留授权，若不允许则需在本分支上先完成历史级证据外置。
8. 当前结论只能是“C3 收尾修正候选已准备，待总控复核”。官方 C2 分支未移动，未合并、未 push，G4 仍为 `open`，43 页完整交付仍为 `NotEstablished`。

## 11. 2026-09-28 总控复核通过后的本地正式发布候选

1. 总控独立复核 `30e879c8d2783dbe098d03d1943f522b9f276363` / tree `2bcf219f240077930561eb1d85172e46333d1ab6`，确认 Artifact Tool 活动继承链修正、`16/16` 定向回归和四页 PPTX hash，并授权进入本机正式发布候选构建与受控安装。本地 `codex/c3-integration-20260924` 已快进到该提交，旧 `df7e0d88` 仍作为祖先保留；官方 C2 分支未移动。
2. 从该精确源码身份构建独立本地 release，只在发布副本将 `plugin.json.version` 标记为 `0.4.0+codex.c3.release-20260928`，然后重算封闭 manifest。包内源码、Skill、MCP 和启动文件与 `30e879c8` 对应源文件字节相同，没有反向修改产品源码。
3. 最终包路径为 `/Users/defei/Library/Application Support/Codex API Client/codex-home/visualizations/2026/09/17/01a0b036-c2db-7781-9598-9a5fe1f47673/代表性客户PPT优化/内部验证/c3-final-release-20260928/ai-ppt-studio`；manifest 覆盖 `3776` 个文件，SHA-256 为 `3a2d0875f34c6bdc92a0a8848ae76c92c37de63b2c87d0dcec83b806c6846967`。独立 verifier 和 stdio probe 通过，实际暴露 `61` 工具，工具目录 hash 为 `158951ecad9b1c5e761264c3e6b92f286c61d0aa966b34ebc6fe2fe1afb5420a`。
4. `mcp/review-bridge.mjs` 的源码、release 和安装 cache hash 均为 `cc1617a716cf589d08fc7436e984dc3fe97378fc8af3e17dd859ce273ec8c742`。“默认连接无时限”、`content-full-deck` 空闲 7 天和 `visual-professional` 空闲 7 天三项服务测试 `3/3` 通过；默认 `ttlMs/leaseMs` 仍为 `null`。
5. 受控安装入口在任何插件配置写入前备份权威 `config.toml`，备份目录为 `/Users/defei/Library/Application Support/AI PPT Studio Development/c3/install-backups/20260928-170501`。随后只通过 Codex 官方插件 CLI 更新本地 marketplace 和安装登记，没有手工覆盖 cache。
6. 安装后只有一个启用的 AI PPT Studio，版本为 `0.4.0+codex.c3.release-20260928`。安装 cache 的 manifest、Review Bridge、tool catalog、Artifact Tool 结果校验器、selection、Skill、CRS wrapper 和 MCP 启动文件均与受审 release/源码字节相同；cache 目录合同为 `61` 工具。
7. 安装登记和 cache 身份不代表当前已运行桌面进程已加载新包。当前会话仍是安装前启动的进程；必须 Command+Q 完整退出后，从 `启动-C3当前宿主.command` 重开，再由新宿主回执验证最终版本、manifest/hash、61 tools 及 Review Bridge 两种审核默认无时间限制。
8. 本轮没有读写客户 Runtime/PPTX/Gate，没有生成 43 页结果，没有合并或 push。G4 仍为 `open`，43 页完整交付仍为 `NotEstablished`；约 36 MB 客户验证图的远程授权仍未决定，所以继续禁止 push。
