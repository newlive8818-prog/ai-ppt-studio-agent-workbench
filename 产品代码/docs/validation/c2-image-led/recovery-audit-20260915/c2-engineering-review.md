# C2 独立工程证据复核（2026-09-15）

审查者：独立工程复核子代理；只读范围。根 AGENTS.md 和四份唯一基线已按顺序读取，根索引状态为“已批准，研发唯一基线”。本报告不修代码、Runtime、Gate、Git 或唯一台账；没有全量重跑、安装、启动新开发线、merge/push/发布/G4/C3。唯一写入为本文件。

## 结论

当前 1014 Python / 249 Node / 770 Widget、TypeScript/build、3772 文件候选包与 43 MCP tools **均找到了原始执行工具回执**，不是仅采信作者总结。候选包当前文件仍全部匹配原包 manifest；可映射的 145 个源码文件与当前 Worktree 一致。但当前缓存与候选包存在一个实际生产代码差异，Git HEAD 对象不可读，且 G3 passed 后项目状态投影仍错误要求完成视觉审核。因此可以进入带明确问题的集成复核，**不能据此给出无保留的工程 Review 通过或“精确冻结候选已可合并”结论**。

真实当前三页 `bc8df...` 已有原始 `current_anchors -> current_result -> preflight_output -> _verify_render_snapshots` 成功回执。旧 `179790...` 的严格重放失败不应继续当作当前 `bc8df...` 的失败证据。当前四个已通过 Gate 的真伪与用户意图由并行规格/Runtime复核负责，本报告不代签 G3。

## 固定审查路径

- 源码：`/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码`
- 当前 Runtime：`/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909`
- 候选包：`/private/tmp/c2-final-release-20260915-7d3e/ai-ppt-studio`
- 当前缓存：`/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/0.4.0+codex.c2.chat-confirm.20260914`
- 唯一台账：源码内 `docs/validation/c2-image-led/verification-report.md:1278-1305`。本报告没有修改台账。

## 工程发现

### E-01 — Important：G3 passed 后仍产生视觉审核待办（当前可复现）

`src/ai_ppt_studio/application/project_status_projection.py:78-91` 只在 G0 passed 时跳过 content-full-deck session；不存在相应 G3 passed 处理。`_review_candidate` 在 session 已打开、不是 submitted 时进入 `:160-165`，生成“需要你处理 / 完成视觉审核”。它不读取 Gate 状态。

本次以当前源码、bundled Python、`PYTHONDONTWRITEBYTECODE=1` 实际调用纯读取投影，结果：

- authoritative revision=142；G0/G1/G2/G3=passed，G4=open；
- 当前 session=`visual-professional-c24c85b250a883d18ae0`，status=opened，host_open_status=opened，open_policy=foreground-if-waiting；
- host_notification_status=not-requested，ai_receipt_status=pending，session revision=132；
- 对外投影却为 `status=需要你处理`、`next_action=完成视觉审核`、projection revision=142；
- kernel/state.json 调用前后 bytes 完全相同。

影响是用户已经完成的视觉选择仍被投影为待办，且高于普通进行中/成果可查看候选，误导下一动作。它不证明 G3 无效，也没有直接改变 Gate。`tests/test_v22_project_status_projection.py` 目前覆盖状态优先级、通知和回执等，没有 G3 passed + 旧 opened visual session 的服务级场景。本审查仅报告问题，不修复或让用户重复 G3。

该文件在源码、候选包和当前缓存完全一致，SHA256=`97be266a738ebbb6a1508515d89b166b0dc4db91267d0d1ab2d42fd211133b39`。

### E-02 — Important：当前加载缓存未完全包含最新工程候选

本次重算两个目录各自全部 3772 个 manifest 条目的 SHA256；二者都无缺项、无额外非pycache文件、无内部hash不一致。但两个 manifest 之间只有以下不同：

| 文件 | 候选/源码 | 当前缓存 | 实际差异 |
| --- | --- | --- | --- |
| `.codex-plugin/plugin.json` | version 0.4.0 | version 0.4.0+codex.c2.chat-confirm.20260914 | 安装版标记 |
| `src/ai_ppt_studio/application/project_service.py` | `e6fd8b7ae25ba06d2b9251f9fdb2bd71b82a72d10c2acc6155b77e98ec195938` | `417ae7ac11f29f7fd9b7227fb9bb9ba5941138e56e8b4020f9b61ce7b19deb6d` | 缓存缺 `cancel_unstarted_native_task` 整个方法 |

该方法位于当前源码 :1043 起，负责只取消 queued、无输出的 build-native-first 任务并保留视觉 Gate。当前源码/测试调用它；检索 `src mcp skills` 未见正式桥接/MCP动作暴露该方法，只有服务实现（测试另有调用）。因此本次 r142 恢复是直接 Python 服务事务能力；缓存中的正式产品运行路径不能据此宣称已具备同样的恢复入口。缺失方法不等于 G3 verifier 未加载；`mcp/server.mjs`、`host-message-verifier.mjs`、Python bridge 在三处一致。

- 候选包 manifest SHA256=`81d342cc20dd78bcbf9a87dcbc9306ce719226f4844ad309492eaf09a611443b`。
- 当前缓存 manifest SHA256=`9dc42870cfd2ea535bdad2869f9a4071fa12b8a6f27b1ba5ae6a2a4d2e304804`。
- 145 个可映射生产源码/Skill/script/包配置文件：候选与源码全部一致；缓存只上述 project_service.py 不一致。比较排除了 node_modules、生成 widget/dist、assets 和由打包生成的插件/config标识。
- `output/c2-source-manifest-20260915.json` 的 9 项当前文件 hash 均匹配，但它只覆盖本轮增量，不是完整被测源码/测试清单快照。

磁盘缓存自洽不证明长驻 Node 进程已加载同一磁盘内容；本次未重启宿主，未伪称热更新已完成。

### E-03 — Important integration blocker：Git 引用可读但 HEAD 对象不可读

在同一 Worktree 以 `/Library/Developer/CommandLineTools/usr/bin/git --no-optional-locks` 实读：

- `rev-parse --show-toplevel --git-dir --git-common-dir HEAD` exit0；HEAD 引用为 `7572d2bbdae5b9b6f0f24d024b07758491623826`。
- git dir 为权威根 `.git/worktrees/PPT-codex-app8`，common dir 为权威根 `.git`。
- `cat-file -t HEAD` exit128：`fatal: git cat-file: could not get object info`。
- `status --short` exit128：`error: bad tree object HEAD`。

`/opt/homebrew/bin/git` 本机不存在；使用 CLT 直接可执行文件已绕开 /usr/bin/git 的 xcrun 调用链，故当前失败不只是 xcrun 架构问题。未运行 fsck修复、gc、reset、checkout或删除任何对象。

这证明当前不能建立有效提交/树身份、diff、干净工作区或集成拓扑，不能从 rev-parse 返回字符串推断提交对象真实存在。本报告是对当前磁盘文件及证据的有界独立复核，不是按不可变最终 SHA 完成的整条 C2 Review。

### E-04 — Evidence limit：AC06 两组三页历史证明的输出文件已不在原路径

`engineering-closeout-20260911/two-group-proof.json` 保留两组不同页ID/内容/对象数：A=4/5/5，B=5/5/5；明确标 synthetic、视觉/用户/PowerPoint 均 not-established。此次实际检查其两个 `/private/tmp/c2-closeout-20260911/generic-three-pages/.../native-anchors.pptx` 原路径，均不存在。不能当前重新核对两个原始 PPTX hash。

当前 renderer SHA256=`20844181dc9caf8e58e6f8c04ca2aead475670d7a8f2c39cd43b2286eb41dac3`；与 20260911 `accepted-render-diff.json` 记录的生产/测试快照 renderer 相同。字体脚本 hash 也相同。因此不是发现 renderer 已变更，但完整两组的输入、输出、被测依赖身份没有在当前候选清单中闭合。最新包装原生回归确有一组三页 synthetic verified_pages=3；不能单靠这一组替代“不同两组三页”的原件复核。

## 原始测试/包回执

真实执行者：`01a09953-ce03-7ab2-8da2-6dbf6e8012c2`。原始日志：

`/Users/defei/Library/Application Support/Codex API Client/codex-home/sessions/2026/09/13/rollout-2026-09-13T13-53-21-01a09953-ce03-7ab2-8da2-6dbf6e8012c2.jsonl`

读取时全文件 SHA256=`55da5725f111ccca289eddf4e68c0f9501f608792694f62904db58ab5e6bb82b`。日志会继续追加，以下另记单行JSON bytes（不含换行）hash，便于追溯原始回执而非作者最终回答。

| 原始行 | 含义 | 单行 SHA256 |
| --- | --- | --- |
| 26532 | Node/Widget/定向Python启动；Widget含typecheck/build | `1de8f2b015e17842114396404ba70fc8f82df3fa01cd7775e2630ce47927c169` |
| 26554 | Widget16文件770测试；exit0 | `c9242520d9c36f922853408ffbaef1d7c2e347a00e592cf1d94608497d4b1191` |
| 26573 | Python全量启动与运行环境 | `ff4cf0528547706b42d11a058a0aa28fc8cd0a6b7381ace3509b4bd3ecb6a4bb` |
| 26609 | Python1014测试170.379秒OK；exit0 | `368f6d851a853cbbd1210325138775ef3aca968e81945326fb6d211df1095dd6` |
| 26615 | 正确C2运行环境下Node全量启动 | `efe56e461f2a94c446e3a6e81e91a3f7fb2d547973b5ab669da172f23881abae` |
| 26626 | Node249/pass249/fail0/skipped0；build exit0 | `f267dc4a65b757bed3e147e422f90e5f3082e44d6635605b7d7eac1133b75204` |
| 26641 | 候选包正式verify-plugin-release启动 | `8c9384220477fef9446250befa9d6e6a9f9a1f2186ca7a7ed8cb6d4c91af5374` |
| 26652 | 候选包3772/43tools/manifest hash；exit0 | `fd1bc327b296996ff9a0c4aa306b7363753d96caa6b9c5d7894981a2e7677de3` |
| 26197 | 实际结果审计脚本及bundled Python启动 | `24ac4675044445530ac84cc4caae686cf0063db6b4fe8c800723277bea57b450` |
| 26220 | current_anchors/G2重放passed；bc8df；r141 | `ef37922bd102783272931ed9525e22f041218ce452b2c53330c45fbe44b62c91` |
| 26582 | 包装原生回归4测试通过；synthetic三页verified | `b4c8bcc3966e6f05bd4e63533e6358a31f2ccb17f7875bd724ff5a8cc2ea09af` |

校准：第一次 Node 全量在 line26541 是 exit1，235 pass / 1 fail / 13 skipped，因缺 C2_RUNTIME_NODE_MODULES。随后仅打包测试在正确环境4/4通过（line26582），再完整 Node 重跑最终249/249且无skips（line26626）。所以最终249可采信，但不可抹掉初次环境失败。Widget运行命令为 `npm run typecheck && npm run build && npm run test:widget`，终态exit0，足以证实前两项也完成。Python全量使用bundled Python并通过PYTHONPATH引入本地Python3.14 site-packages；这证明该具体环境运行通过，不证明任意系统Python可运行。

打包verify最终出口 `ok=true`、3772文件、manifest81d342...、probe tool_count=43；此次重算包内容仍对得上该原始manifest。probe是临时release-probe Runtime：真实host_open仍 `unavailable/BROWSER_REVIEW_UNAVAILABLE`，host_notification与ai_receipt仍unverified、realHostEvidence=false。这份43工具校验不能证明真实桌面打开、通知、AI回执或当前客户整条生产流程。

## 严格重放与正式入口边界

当前 `bc8df...` 三页有本轮原始严格输出校验成功证据。26197行的脚本调用 `ImageLedNativeService.current_anchors()` 和 `GateEvaluator.validate_current_g2_evidence()`；26220行exit0并输出当前PPTX hash、三页和通过。源码链：`image_led_native.py:312-317` 调 `current_result`；`image_led_results.py:790-800`核验completed producer task/role/refs/context后调用preflight_output；`:61-85`与`:676`真实重导入精确PPTX bytes并检查保存render/comparison。这不是仅看历史Gate标签。

历史 `accepted-preflight.json` 的失败对象为 `1797900779255f539f659f806b9ae140b7490fbd5b245675f844ccb36096e2a6`，身份与当前 `bc8df49178b1ae9e3831caf6a81bab5bfaa2c029aff056291d60bfc1421be5e5` 不同，不应转移为当前失败。本次独立工程审查没有再次进行fresh-render重放；已阅读原始执行记录和具体校验调用链，当前现场是否重放由Runtime复核归口。

依然有限制：完整正式入口不等于Python API可调用。当前cancel方法未暴露正式MCP路径、当前缓存缺它；release probe主动报告真实Browser/通知/AI回执未验证；真实三页正式lineage证明不自动证明在当前候选包/当前宿主中从头生产另一套内容完全不需临时编排。不能用工具总数、单个synthetic包回归或已接受三页推导全入口、跨环境泛化完成。

## 集成判断建议

1. 接受1014/249/770、typecheck/build、3772/43作为具体执行环境下真实工程结果，保留原始行与hash。
2. 将 E-01 作为具体状态投影缺陷登记；用户无需再做一次G3来让旧session变成submitted。
3. 统一拟集成候选与缓存的工程能力边界，明确是否只把cancel当临时运维API。缓存一致性与驻留进程加载分别验证。
4. 在获授权的独立Git恢复范围中建立可解析候选对象/树后，补最终差异身份及必要独立Review；此次不修Git。
5. AC06历史双组三页记录可作历史工程证据，当前原件/同候选绑定的不足保留；需要严格重现时从真实输入重新验证并固化输出，不能改旧记录标签。

本审查没有发现足以推翻当前三页hash或真实G3的工程证据；也没有据局部工程结果宣布C2整体退出、可直接merge、发布或C3开始。
