# CHG-IL-C0 唯一执行记录

记录日期：2026-09-07。本文件是 C0 唯一事实/AC 记录；主计划只保存冻结定义，入口和证据索引只导航。本文件所在 Git 提交与最终交接回执确定候选身份，不为把 SHA 写回正文反复生成冻结提交。

## 1. 定义与现场

- 定义：[主计划 §3.1](../../superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md)；只执行 C0-T01～T04。
- 唯一 owner：`01a07c47-b1dd-7bd3-a1b3-69e01186ec62`，Worktree `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/dcf2/PPT-codex-app`。
- Branch：`codex/c0-image-led-handoff-freeze-20260907`；精确 B0：`d77854385b830d5796b6da2b86e3c44021095398`。
- 根目录四基线按 00→01→02→03 完整读取，原状态 v2.9 已批准；随后读取产品代码 AGENTS.md。主执行者读取 change-map、executing-plans、using-git-worktrees、verification-before-completion、requesting-code-review。
- 初始 Git/status、来源与哈希见 [证据索引](./evidence-index.md) 和 [机器快照](./evidence-snapshot.json)。
- 开工回执已通过 send_message_to_thread 发至旧总控 `01a06fe8-4e95-75c1-b348-9dd3a317c6a2`，包含真实命令、task/cwd/branch/base 和下一产出。
- 首次分支创建被 Git 公共目录沙箱拒绝；原生授权重试成功，未回旧现场开发。

## 2. 执行范围与证据限制

T01 完成采集；T02 四基线更新 v2.10；T03 主计划迁入并增加 C0，C1–C4 原验收条款逐条保持；T04 两轮独立取出与 Review 完成，首轮发现项已关闭。本次只收口执行记录；末次提交的完整 SHA、独立取出与记录增量复核由最终交接回执绑定，避免提交自引用。全程只变更文档与验证资料，未安装依赖、调用生图、上传、修改 Runtime 或生产逻辑。

S05 当前 PPTX 与报告 hash 不同、S08 source_copy 缺失，均如实登记；S08 PowerPoint 只列 R4 自报告和文件证据，C0 独立重验 NotRun。S05 “效果好但慢”来自用户委派，S08 没有新的用户接受。代码测试历史与 C0 本轮验证分开。

## 3. 本轮验证

2026-09-07 15:31:16 UTC，本轮在 C0 根目录执行 `python3 产品代码/docs/validation/c0-image-led-freeze/verify_freeze.py --root .`，exit 0，result=PASS：

- 10 文件白名单精确匹配，`git diff --check B0` 无错误。
- 78 个 Markdown 相对链接可解析，6 处原型引用存在；四份基线版本/日期与方向边界一致。
- C1–C4 原有 35 条 AC 逐字保持，串联文本 SHA-256 `0f942cdef6bf8b1e0a18693eec72a42fcab42b9a08f291c93fee9283b7f46a49`。
- B0→R4 祖先关系、12 个精确 Git 输入文件可解析；生产 src/mcp/widget/tests/scripts/skills 树与 B0 保持。
- 26 个现存外部来源与采集 hash 匹配，1 个已登记的临时输入缺失；旧迁移计划和附件是溯源项，不是启动依赖。
- 产品测试、PowerPoint、Browser/宿主、用户验收均为 NotRun；没有把历史 R3 绿色结果写成本轮通过。

首个候选 `b227869e9edf17e3448e298c7bbd44ce968debf1` 的 parent 精确为 B0。本地提交遇到 index.lock 沙箱限制后经原生授权成功；无产品逻辑或依赖安装。

主执行者于 2026-09-07 15:44:54 UTC 执行 `python3 产品代码/docs/validation/c0-image-led-freeze/verify_freeze.py --root . --commit b227869e9edf17e3448e298c7bbd44ce968debf1`，exit 0，PASS。独立取出目录 `/private/tmp/c0-freeze-readback-cp6zb2rc`，全部 467 个跟踪 Git blob 与取出字节逐一匹配；不是仅检查目录存在。源码/四基线/主计划/入口完整，78 链接/6 原型可解析，外部引用保留明确缺失。旧总控四个 dirty 文件复核均与开工采集 hash 一致。

修订后 2026-09-07 15:52:35 UTC 再运行工作树检查，exit 0，PASS：79 个相对链接、6 处原型、35 条原 AC；新增行内路径核验共 25 项接入引用，其中 20 项在本冻结源码树、5 项仅存在于精确 R4 Git 输入。拟新增路径仍为提案，不冒充已存在文件。

修订候选 `8e385d38f5dfa862db0f7960e1eb48d7e5daa31b`：主执行者于 2026-09-07 15:54:22 UTC 使用同脚本 `--commit 8e385d38f5dfa862db0f7960e1eb48d7e5daa31b` 独立取出到 `/private/tmp/c0-freeze-readback-ty0hwoug`，exit 0，467 blobs/79 链接/6 原型/25 既有路径/10 白名单全部通过。主计划 SHA-256 为 `27d8fe429d3195203acc2430ea44cf8e3096d624008d2e57cc6e3b32b95cf6e9`。

首次暂存补查发现入口及证据索引各有一个 EOF 空行；已用 apply_patch 移除，再执行暂存 diff 检查。该格式问题没有被早期未跟踪文件的 diff 检查覆盖，最终以完整暂存/候选检查为准。

实际 changed-file 白名单：根目录 00/01/02/03 四基线、04 接管入口；`产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md`；本目录 `evidence-index.md`、`evidence-snapshot.json`、`verification-report.md`、`verify_freeze.py`。无 Runtime 原件或产品实现文件。

## 4. 独立 Review

只读独立 reviewer：`/root/c0_readonly_reviewer`，绑定首个候选 `b227869e9edf17e3448e298c7bbd44ce968debf1`。本人独立完整读取所需基线、计划、入口及证据；独立运行相同 `--commit` 命令，2026-09-07 15:47:29 UTC，exit 0，467 blobs/78 链接/6 原型通过，取出目录 `/private/tmp/c0-freeze-readback-vbpfdsdx`。起止 HEAD/branch/clean 一致，六个生产子树与 B0 一致。

第一轮结论：Critical=0、Important=1、Minor=2，候选返回修订；生产代码无需调整。

| 发现 | 文档修订 | 当前复验边界 |
|---|---|---|
| Important：02 §11.2 把 26 项 token map 保留身份写成仅六项 | 明确继承 B0 完整 26 项集合与规范化精确匹配，六项仅为示例；列出两处精确源码定义 | 第二轮独立复核关闭；生产 validator 未改 |
| Minor：计划 Python 接入点缺少包根 | 已补全 `src/ai_ppt_studio/`，新增/既有路径的身份分开 | 第二轮关闭；25 项既有路径通过，35 条 AC 不变 |
| Minor：00 把 quarantine 原注册目录称为执行权威根 | 改为冻结包所在 Git 根与产品代码；原路径仅供定位，禁止作为派生基线 | 第二轮关闭；新总控仍须核对精确提交与独立现场 |

已使用 receiving-code-review 技能按实际文件/Git 证据判断并修复，未修改产品逻辑。

第二轮 reviewer 绑定 `8e385d38f5dfa862db0f7960e1eb48d7e5daa31b`，2026-09-07 15:55:37 UTC 独立执行 `python3 产品代码/docs/validation/c0-image-led-freeze/verify_freeze.py --root . --commit 8e385d38f5dfa862db0f7960e1eb48d7e5daa31b`，exit 0、PASS；取出目录 `/private/tmp/c0-freeze-readback-2lqlasep`，467 blobs/79 链接/6 原型/25 既有路径通过。独立静态 AST/文本核对 Python 与 Widget 保留集合均为 26 项且相同，起止精确 HEAD/branch/clean 稳定。

第二轮结论：**Critical=0、Important=0、Minor=0；三项发现全部关闭，可作为 C0 候选冻结。** 该结论不包含 AC08、merge、发布、C1 或产品真实验收。本报告收口提交只改本文件；最后的完整 SHA 与记录增量核验以最终回执为准，不把第二轮 Review 冒充新提交自动通过。

## 5. AC 与停止状态

| AC | 当前状态 | 证据/限制 |
|---|---|---|
| AC01 | PASS | B0 与已提交候选可识别；最终完整 SHA 由交接回执绑定，不写回自身 |
| AC02 | PASS | 精确 10 文件白名单，旧 dirty/Runtime 无混入，产品子树不变 |
| AC03 | PASS | 批准方向/实现/过渡分层；第二轮独立 Review 0/0/0，原发现全部关闭 |
| AC04 | PASS | 主计划自首个候选进入 Git，启动不依赖旧未跟踪文件 |
| AC05 | PASS | reviewer 已核对分层；S05 hash 差异、S08 临时输入缺失明确登记 |
| AC06 | PASS | 两轮主执行者和 reviewer 分别独立 archive 467 blobs；末次记录提交也须绑定最终回执；外部材料明确非自包含 |
| AC07 | PASS | 本轮文档/链接/路径/diff/启动证据具备；末次提交检查由最终回执绑定；代码与 PowerPoint NotRun |
| AC08 | 接管待验 | 新总控正式任务尚未就绪，无真实读取回执；C0 不代签 |

整体状态：**候选冻结、接管待验；C0 未全部完成。** AC01–07 已具备候选证据，AC08 未通过；最终记录提交/精确 SHA 复验后仍停在此边界，不派发 C1。旧总控负责候选验收、恢复新总控启动并核验 AC08；本任务不修改自动化、不创建重复总控。

回报通道：首个开工回执已成功；后续两次 send_message_to_thread 更新被自动审批拒绝，理由为目的任务归属/披露授权不足。第一次拒绝后已通过 read_thread 确认该任务是 local、同项目 9155 的旧总控，并在重试中引用用户两次明确回报委派，仍被拒绝。禁止改用其他通道或 reviewer 代发绕过；冻结工作继续，最终发送须由用户/原生审批处理，不能声称候选已送达。

## 6. 回退

保留 B0 与 C0 分支；本轮没有数据迁移。候选不通过则在本 Change 内修订并重新验证；不 reset、不清理其他现场、不 merge/Push/发布。未来集成与撤销另行批准。
