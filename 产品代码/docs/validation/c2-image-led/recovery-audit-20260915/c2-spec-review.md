# C2 当前退出矩阵独立规格复核 — 2026-09-15

复核者：`/root/c2_spec_audit`。范围：只读检查 C2 主计划 AC01–AC10 与 2026-09-15 最新退出矩阵的证据匹配，重点检查 AC06、AC10、历史 strict replay、S05 fill provenance 和 Review Bridge 边界。本回执不是整个 C2 冻结源码候选的全面规格 Review，不能用本回执本身把 AC10 改为 Passed。未运行全量测试、未操作 PowerPoint、未重建 PPTX、未修改 Runtime/源码/台账/Gate，只写本文件。

## 结论

当前可以确认真实三页成果和已存 G0/G1/G2/G3；不能确认 C2 全部技术退出条件已满足。最新矩阵的 AC06 `Passed (engineering boundary)` 缩小了完整 AC 的要求；AC10 仍缺同一冻结候选的独立规格与工程 Review。当前可提交总控审查和修复，不能据最新退出段直接认定“已满足主计划、允许申请集成”。G4 不属于 C2 必须退出条件，不应要求重开 G3、重做已接受三页或进入 C3 来填补工程证据。

## 权威来源和身份

- 执行 Worktree：`/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app`。
- 执行台账 `产品代码/docs/validation/c2-image-led/verification-report.md`：SHA256 `8efceefe5d3dc7fd8106e33c98e34c6a6f04f4bec9bc5e19a27cabf9650e0306`，本次末尾为第 1305 行。
- 主计划 `产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md`：SHA256 `fa9cfd26c27547c63d6471daadbeecb31af73faa035acde1a4a3a80f1e26d40e`。
- Runtime：`/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909`；实读 `kernel/state.json` 为 r142，SHA256 `e7b2042c0a279084540a449fb272054905104f606bf345ebb6d64655e5729e2d`。G0/G1/G2/G3 passed，G4 open，无 `agent/task/active`。
- `output/c2-final-closeout-20260915.json`：SHA256 `afad8a5d11a8593ea5f29a7fa6b72e424ddebccc7cce2f3fbae8e508fc01158a`。
- 实读当前 `979c61472fe84801cee593610c867614e9b75d14080e8ddcf0bb8c340971a722/native-anchors.pptx` 的 SHA256 为 `bc8df49178b1ae9e3831caf6a81bab5bfaa2c029aff056291d60bfc1421be5e5`，与当前 build-result、目标证据一致。
- 注册根四基线仍为 v2.2，执行 Worktree 四基线为 v2.14。执行索引第 9–11 行明确注册根为 quarantine，不作为本次执行基线。本复核采用父任务指定执行端资料，不以注册根旧的 Image 2 规则覆盖当前 Image-led 合同；本次没有完整消除执行端与后继总控基线差异，因此不作 AC01 全候选一致性通过声明。

## 发现

### I-01 / Important：AC06 用 renderer 合成边界替代正式入口验收

位置：执行台账第 1299 行；对应 `output/c2-final-closeout-20260915.json` 第 33 行。

主计划第 210 行要求“三页正式案例及另一份不同内容的三页泛化检查”，第 219 行 AC06 要求“正式构建无需临时编写专用页面脚本；不同内容和对象数能走同一路径，不靠三页固化答案通过”。第 322 行 P-AC05 进一步指定“正式 action/artifact 链、异内容样本”。

实际引用的 `engineering-closeout-20260911/two-group-proof.json` 第 2–3 行只定义同一 generic renderer 的两组合成三页，A 对象数为 4/5/5，B 为 5/5/5；两份 PPTX hash 不同。它没有记录第二组正常 Mission/G0→请求/选稿→合同/计划→正式 action→结果提交/锚点的链条，也没有当前候选的正式入口调用回执。无需把第二组升级为真实客户成功或要求其取得用户 G3，但至少应验证不同内容和对象数经正式机制进入同一路径。

执行台账第 1242 行明确这些合成输出不是第二真实案例，且委托工作选择仅限已授权 S04/S05/S06；第 1259 行当时用同一证据将完整 AC06 判为 NotEstablished。2026-09-15 新增了当前真实正式三页链，可以关闭第一组原“只有诊断路径”的缺口；没有看到第二组正式入口链的新证据。`output/c2-existing-result-review-20260915.md` 第 39 行也明确另一组不同内容三页的当前泛化证明仍未被该成果核验替代。

处置：AC06 恢复 `NotEstablished`，分项保留“同 renderer 异内容/异对象数工程证明 Passed；第一组正式链已建立”。由当前候选支持的正式入口完成第二组受控泛化，保留 action/context/plan/handoff/result/输出 hash 和无逐页专用脚本依赖的证据后再判完整 AC。

### I-02 / Important：AC10 仍缺同一冻结候选的整体双审

位置：执行台账第 1303–1305 行；对应 `output/c2-final-closeout-20260915.json` 第 37–39 行。

主计划第 223 行要求“同一冻结候选的独立规格 Review 与工程 Review无未关闭 Critical/Important；用户接受三页正式结果，总控确认可申请集成”；第 377 行要求 Review 前冻结精确候选提交并让测试和双审绑定该候选；第 381–386 行要求全部 AC 证据、必需缺证不放行、两类审查闭合、工作区/提交/manifest 对应和总控明确判断。

本次所述独审实例 `01a0a0ce-95d6-73d1-b6c1-1e08d1c6102b` 只审聊天确认适配。执行台账第 1286 行和已有结果报告第 43 行均明确“不替代 C2 整体 Review”。发布包 verifier/43 工具通过是包的检查，不提供整个 C2 同一候选的规格与工程 Review。

第 1270 行历史独审绑定 `9f24dde..b8e788fcf01d3e71cfc4844617b04d75ef7ca209`，不可转授后继；其链接 `/private/tmp/c2-closeout-independent-review-20260911.md` 当前已不存在，本复核只能确认台账历史描述，不能独立重新阅读该报告。第 1287 行又明确当前 Git `bad tree object HEAD`，未能建立新冻结提交，不能将此仅描述为“最后不能 merge”，因为当前候选固定和审查绑定本身也受影响。

处置：完整 AC10 为 `NotEstablished`。可称“当前成果/修复已准备提交总控复核”，不能称“AC10 已满足、允许申请集成”。先保全并恢复/建立准确候选身份，完成针对同一候选的独立规格及工程 Review（允许按明确范围合并旧审查和新差异审查，但须证明字节/范围覆盖），清除 Important 后由总控判断。若确需以 hash 固定包替代主计划要求的提交冻结，要显式解释该流程差异，不能悄悄改验收标准。

### E-01：AC01/AC09 当前同候选证据仍需工程核定

第 1294 行 AC01 的 `Ready-for-integration-review` 是流程状态，不是 AC 完成状态。第 1302 行和 closeout JSON 第 15–25 行报告 Python1014/Node249/Widget770、typecheck 和发布包3772/43工具通过；这些是作者报告。本独立规格复核未重跑套件，也未取得完整原始命令/日志与当前全源码清单逐字对应证明，因此不把数字本身认定为当前冻结候选全部通过。

旧工程闭合证据在台账第 1236–1246 行有独立测试快照、命令日志、来源清单和适用 build 的详细绑定；新退出条目需建立同等可追溯关系，尤其 `build` 是 AC09 明文要求，3772 文件发布包验证不能自行替代 Widget/前端 build。交工程复核确认现存日志及清单后可保留原实际运行通过，无必要盲目重跑无关全量测试。

## 不能抹掉、也不能误用的历史边界

### Strict replay：历史失败与当前新文件须分开

台账第 1218 行旧用户接受的诊断 PPTX 为 `179790…`，第 1231 行其完整 preflight 失败原因仍为 `Submitted render is not the current PPTX rendering`。第 1273–1276 行明确统计复算不是完整 preflight 通过，并未证明唯一根因。该历史失败仍留在台账，没有看到被原地改为 PASS。

当前正式成果为 `bc8df…`，是另一文件、另一个正式 handoff（`ddf22f5…`），不能把旧失败套到当前文件，也不能因当前 `current_anchors`/G2 成功反写旧失败成功。代码 `application/image_led_native.py` 第 365–375 行的 current_anchors 调用当前 _anchor_projection，后者读取当前 build；`application/image_led_results.py` 第 550–676 行 preflight_output 最后执行 `_verify_render_snapshots`。因此，父任务在正确字体环境中取得当前 current_anchors/G2 成功，可作为当前严格检查证据，须保存当前 PPTX/输入/源码/字体身份。

父任务本轮首先因未显式字体得到 `Exact font unavailable: Microsoft YaHei`，正在用真实 msyh.ttc/msyhbd.ttc 重新只读验证。这是环境 CapabilityGap，不能据此推翻已存 G2/G3，更不能放宽阈值或重新生成已接受三页来规避。

### S05 fill provenance：差异存在，当前 G3 接受有独立身份

历史 `2283dfe8…` 与当前 `1764231174…` 区域清单在 `S05-header-field`、`S05-strategy-left-field` 两处 fill 不同：角度由 0/0 改为 136/57，且 stops 改变。已实读当前 handoff，确实使用后两种 fill；当前 build-result 的第 4277–4279 行绑定当前 PPTX和当前区域清单。

台账第 1224 行的“尚未进入已验收PPTX”只对旧 `179790…` 时点有效。当前 `output/c2-existing-result-review-20260915.md` 第 35 行保留了两处 fill 差异，说明用户接受前已点名；当前 G3 制品绑定 `ac26cf54…`、当前 anchors和真实消息。可以记录“新正式三页在说明差异后整体接受”，不可由此宣称逐像素一致、历史文件相同或把未来输出自动接受。

当前 handoff 第 32794 行的 S05 `accepted_deviations` 仍为 `[]`。不建议补写历史 TargetBinding 来伪造逐项差异许可；整体 G3 接受与定版时的逐项 deviation 应保持各自发生时间和身份。

### Review Bridge：真实打开已成立，反馈通知/AI 接收尚未建立

当前 `artifacts/objects/97/97a43efae40012678b76c62c15f7316e4cf2addb7b5b1496e537d0ea6051d802.json`：第 4 行 ai_receipt=pending，第 6 行 host_notification=not-requested，第 8 行 host_open=opened，第 11 行 persistence=saved，第 17–18 行 status=opened/submitted_at=null。当前未见锚点反馈批次/合同标记提交链的 current head。

由聊天确认 G3 合法，不要求用户为同一接受结果制造一次反馈批次；上述尚未运行链也不能推翻已存 G3。但“有 G3”不证明专业审核页批次保存→真实宿主通知→AI 接收这一链已验收。主计划第 209 行仍要求状态分离和真实证据边界；必须在最终交接中保留这个能力/验证缺口，不能称整个 Bridge 已完全闭环。

## 可采纳的当前保守矩阵

状态针对完整 AC；表内工程分项通过不自动升级整体退出。

| AC | 建议当前状态 | 证据及边界 |
|---|---|---|
| AC01 | NotEstablished | 核心职责合同一致性已有证据；执行端/后继基线与当前源码/Skill/handoff 的同候选完整衔接和审查仍需闭合。 |
| AC02 | Passed（已存当前正式三页链） | Runtime142 G0/G1/G2/G3 passed；G3当前7项 refs、真实消息 ref和当前PPTX hash一致；不重用旧实验Gate，不要求G4。当前只读重放由父任务另附结果。 |
| AC03 | Passed（已有工程证据边界） | 既有项目/版本/内容/材料/图像/假选择拒绝回归和当前refs支撑；当前同候选输入身份由工程核定，29条消息测试本身不能替代所有零写入反例。 |
| AC04 | Passed（已有工程证据边界） | 既有缺字/错数/关系/换图/位图/未授权对象负例可复用其准确源身份；不是仅凭本组三页无错误宣称所有反例通过。 |
| AC05 | Passed（已有工程证据边界） | 确定派生、篡改/路径/过期引用拒绝和当前handoff对应；历史179790严格重放FAIL另列，当前bc8df重放另证。 |
| AC06 | NotEstablished | 两组renderer合成Passed；第二组经正式入口、正式artifact/action链和无临时编排依赖的当前泛化证据缺失。 |
| AC07 | Passed（已存current G2/G3与工程失效规则） | 当前refs一致，真实G3；当前字体环境下独立重放另附；不延伸为Review Bridge反馈通知/AI回执已验收。 |
| AC08 | Passed（已有工程证据边界） | legacy读取与不自动升级回归；没有真实旧项目原地迁移。 |
| AC09 | NotEstablished（本规格复核尚未独立确认当前同候选全量/构建绑定） | 作者报告1014/249/770及typecheck/包验证；待工程核对原始日志、build与精确当前输入清单；无需为补该矩阵机械重跑全部。 |
| AC10 | NotEstablished | 用户接受已成立；定向消息适配审查不可替代同一冻结候选的规格/工程双审；Git候选身份和总控允许申请集成均待建立。 |

## 集成判断

建议总控结论：**返回工程证据补齐/定向修复，保留正式三页和已存G3。** 本次允许把当前成果、候选包和本复核作为集成审查输入；尚不满足主计划第 223 行、第 377–386 行“允许申请集成”的完整条件。必要下一检查点为：准确冻结候选身份 → 关闭正式入口异内容泛化缺口 → 同候选测试/build与来源绑定 → 独立规格/工程Review无未闭合Important → 总控判断。无需将G4作为C2阻断；主计划第227行明定C2不证明G4，第248–259行将整套交付/G4归C3。

## 本轮查阅的记忆用途

只用 `MEMORY.md` 第 167–227 行定位“证据身份分层、旧strict replay、S05、正式入口泛化与候选审查”问题，再以当前台账/源码/Runtime独立核对。未把旧r137/G3待确认状态当当前事实。相关历史rollout：`01a09326-dc3d-74c3-b931-fef75847ccd7`、`01a092b1-a26d-7603-bbdc-a68e2982e98f`。未修改任何记忆。
