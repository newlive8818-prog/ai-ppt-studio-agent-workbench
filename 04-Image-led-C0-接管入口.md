# Image-led C0 冻结包｜新总控接管入口

本文件是启动导航，不是第二份产品基线或动态进度账本。**C0 当前是否通过只查 [唯一执行记录](./产品代码/docs/validation/c0-image-led-freeze/verification-report.md)**。新总控回执前不得写“已接管”或派发 C1。

## 0. 2026-09-09 后续执行必须读取的修正

用户最新已要求独立派发 C2，启动直接进入 [C2 执行交接](./产品代码/docs/validation/c2-dispatch/README.md)，授权见 [主计划 §12.2](./产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md#122-2026-09-09-c2-独立任务执行授权)。本文件较早 C0 接管条件保留作历史协议，不取消该最新授权。

用户已明确要求 Image 2 承担设计责任：定版图及其绑定文案约束全部下游，原生环节不得重新设计或回退旧内容。当前后续执行以 [四基线 v2.12 的唯一入口](./00-唯一研发基线索引-v1.0.md) 和 [主计划版本 3 / §12.1](./产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md) 为准。新任务和恢复任务均须读取这些更新，不能只读取旧冻结包中的“视觉参考”解释。


## 0.1 Image-led 定版身份链（当前强制规则）

C0 及其后续任务不得把定版图当作风格参考或从目录猜测标的。任何转换必须携带 `project_id / slide_id / page_order / target_image_sha256 / selected_copy_sha256 / material_roles / accepted_deviations`，并声明 `design_authority=finalized-image`、`conversion_mode=faithful-native`。错页、旧 hash、缺区域映射、缺依赖或已有输出时，必须在写入前阻断；不能重新设计、回退旧文案、覆盖已验收制品或把失败结果提交为候选。跨页共同规范只做检查，不得改写单页定版构图。

下文 §1–§5 是 C0 原始 v2.10 冻结/首次接管协议及其历史现场，不是当前 C1 进度，也不取消已获得的后续授权。C0 原提交、manifest、验证脚本与验收事实保持原样；`verify_freeze.py` 仅用于验证该原始精确提交，不能对修订后的 v2.12 工作区直接运行并要求其满足旧词句或旧 AC hash。本次基线修订须保留自身提交与检查证据，不借用 C0 冻结证明；正式生产新规则仍待 C2 实现。

## 1. 先核验，再读取

旧总控应提供完整候选 SHA。新总控必须基于该精确提交建立或恢复自己的原生任务现场；不要使用不存在的默认 main，也不要从旧总控/quarantine 派生。第一项可执行动作是只读核验：

```bash
pwd
git rev-parse --show-toplevel --git-dir --git-common-dir
git rev-parse HEAD
git status --short
git merge-base --is-ancestor d77854385b830d5796b6da2b86e3c44021095398 HEAD
```

HEAD 必须等于旧总控验收的完整候选 SHA，工作区干净，目录属于预期独立现场。来源错误、脏状态或初始化失败时停止写入并回报；不就地改旧现场。为避免提交自引用，本文件不预写自己的冻结 SHA；候选身份从旧总控回执与 Git 精确读取交叉核对。

阅读顺序：

1. 当前根目录 AGENTS.md。
2. [00 唯一基线索引](./00-唯一研发基线索引-v1.0.md) → [01 产品需求](./01-产品需求基线-v1.0.md) → [02 系统设计](./02-系统详细设计-v1.0.md) → [03 UI 规范](./03-UI设计与交互规范-v1.0.md)，首次 C0 冻结中的四份均为 v2.10；后续执行还须按 §0 读取 v2.12 修正，原冻结身份不被改写。
3. [产品代码指引](./产品代码/AGENTS.md)。
4. [已迁入版本控制的主计划](./产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md)，尤其 §3.1 C0、§4 C1 和 §12 权限顺序。
5. [证据索引](./产品代码/docs/validation/c0-image-led-freeze/evidence-index.md)、[机器快照](./产品代码/docs/validation/c0-image-led-freeze/evidence-snapshot.json)、[唯一执行记录](./产品代码/docs/validation/c0-image-led-freeze/verification-report.md)。
6. 按索引只读查验 B0/R4 精确 Git 文件与所需外部 Runtime；不得将外部材料复制入源码。

## 2. 唯一权威关系

用户最新明确决定 → 00 → 01 → 02 → 03 → 无冲突专项。主计划保存 Change 定义和顺序；每个 Change 的唯一执行记录保存事实和 Gate；Git 保存代码、差异及提交事实。证据索引/快照只是来源清单，不维护另一套状态。既有 R3/R4 执行记录只在各自范围有效。

旧 9155 未跟踪主计划是迁移来源，已核对读取前 SHA-256 `fa023ab7c19c0e090cf5d60e356088954426cce47fb72ebcce5c8e7cdf9be6dd`；后续启动直接读本包主计划。旧 v2.3 专项中原生先于整页探索的时序已被四基线取代；细粒度 Image-led schema 尚待 C1 验证/C2 正式设计。

## 3. 任务和 Worktree 事实映射

| 角色 | 真实任务 ID | Worktree | Branch / 精确来源 |
|---|---|---|---|
| C0 唯一主任务 | `01a07c47-b1dd-7bd3-a1b3-69e01186ec62` | `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/dcf2/PPT-codex-app` | `codex/c0-image-led-handoff-freeze-20260907`；精确 B0 `d77854385b830d5796b6da2b86e3c44021095398` |
| 旧总控，协调/验收 | `01a06fe8-4e95-75c1-b348-9dd3a317c6a2` | `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/9155/PPT-codex-app` | detached `8c794fa85f015c1afa9c3db2f9145e6a749ed952`；dirty，全排除 |
| B0 / R3 | `01a057d6-bda4-7cb1-baab-b98fa0ccb8d5` | `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/6fe4/PPT-codex-app` | `codex/v23-visual-quality-20260831`；`d77854385b830d5796b6da2b86e3c44021095398` |
| R4 实验输入 | `01a07514-6885-7363-86cf-c66acac295f6` | `/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/4fab/PPT-codex-app` | `codex/v23-two-slide-experiment-20260901`；`8a58b98ecc1bccb7c66a55a44b4c1ca9cf873e93` |
| 新总控 | 正式任务 ID `NotEstablished` | 尚未接管 | 旧请求 `client-new-thread:d7bb6657-9d20-48a1-9d1a-cc54a8a833b6` 不是正式 ID |

新总控期望题名“AI PPT Studio｜Image-led 升级总控”。旧总控于本任务补充说明：其默认从 main 创建失败，2026-09-07 14:12:17 UTC，exit 128；本地与远端 main 引用查询亦失败。这是旧总控提供的启动诊断，C0 不冒充独立重验，不创建重复任务；旧总控在候选验收后按精确提交恢复启动。

## 4. 权限、停止线与下一 Gate

C0 已授权四基线/计划/交接/验证资料更新、本地分支与提交及独立取出验证。禁止产品逻辑修改、合并旧脏改动、整体合入 R4、安装依赖/插件、发布/Push、运行材料迁移、生图、上传、PowerPoint 重跑或自动化变更。旧心跳 `ai-ppt-studio-v2-3` 的 PAUSED 状态来自委派说明，C0 未修改或独立查询它。

顺序固定：C0 → 旧总控验收冻结包 → 新总控真实读取并回执 → C1 → C2 → C3 → C4。该首次 C0 接管时点的下一 Gate 是旧总控候选验收及 C0-AC08；不是当前 C1 动态进度，也不是 G3/G4 或 C1 实验完成。

接管后第一个业务动作是准备 C1 的确切三页输入（复杂关系、真实材料结合、数据/表格或方案表达），列内容 hash、材料/参考角色、允许外发范围和实验资源边界。未确认输入不生图；C2–C4 仍需各自前置和授权。代码读取/测试从 `产品代码/` 运行。

新总控必须将以下真实回执发送到旧总控任务：

- 正式 task ID、真实 cwd、branch、base/HEAD、干净状态及刚执行的核验命令；
- 完整冻结候选 SHA，B0 与候选关系；
- 已实际读取的主计划路径、版本与 SHA-256，四基线版本；
- 首个可执行动作、允许/禁止事项、下一 Gate；
- 明确“读取完成”与“执行 C1”是两个状态。

旧总控核验该回执后才能判定 AC08。C0 主执行者与 reviewer 都无权代签。

## 5. 回滚和外部运行材料

源码完整保留在 `产品代码/`。C0 不迁移 Runtime、不复制客户原件；原始 B0 保留，C0 是独立本地文档增量。若候选需修订，保留提交和证据后形成新候选；不 reset、不覆盖其他任务、不清理隔离目录。集成后的撤销需要另行授权普通 revert。

外部 Runtime：`/Users/defei/Documents/AI-PPT-Workspace/projects/v23-visual-quality-two-slide-experiment-20260901`。重点读取 `revisions/image2-s05-rebuild-20260907/` 与 `revisions/image2-s08-fast-rebuild-20260907/`，文件路径和 hash 见证据索引。S05 当前 PPTX/报告 hash 不同、S08 临时 source_copy 缺失；因此本包自包含源码/基线/计划，**不自包含 R4 原始实验运行材料或可复跑环境**。

以下为 C0 原始冻结版本的只读验证命令；修订后的工作区不适用，历史验证应使用原确切提交的独立取出目录或下述 `--commit`：

```bash
python3 产品代码/docs/validation/c0-image-led-freeze/verify_freeze.py --root .
```

冻结后将接管回执中的完整 SHA 传给同脚本 `--commit` 参数，可在新临时目录独立取出全树并逐文件校验；不会创建 Git Worktree、安装依赖或运行 PPT/产品逻辑。
