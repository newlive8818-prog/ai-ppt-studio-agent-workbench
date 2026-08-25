# AI PPT Studio v2.2 受控恢复 Worktree 边界与 MCP 打包 Python Runtime 设计

## 1. 文档身份

- 日期：2026-08-25
- 状态：`用户已批准设计`
- 适用范围：AI PPT Studio v2.2 受控恢复序列，以及当前第一个独立恢复单元 `MCP 打包 Python Runtime`
- 权威项目根：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
- 恢复集成分支：`codex/v22-recovery-integration-20260825`
- 当前恢复 HEAD：`94f0f609ee4288995cf60ef90fc218dfa48f0ee8`
- 当前功能分支：`codex/slice-mcp-runtime-20260825`
- 当前 linked worktree：`/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-mcp-runtime-20260825`
- 回滚点：`94f0f609ee4288995cf60ef90fc218dfa48f0ee8`
- 恢复治理依据：[版本隔离与恢复基线](../../validation/2026-08-25-version-quarantine-and-recovery-baseline.md)
- 非用途：本文不是实现提交、合并批准、发布说明、真实宿主能力证明或用户最终验收。

本文冻结两层设计：

1. 完整恢复序列如何判断和管理独立 branch/worktree；
2. 当前 `MCP 打包 Python Runtime` 单元的架构、错误、测试和完成边界。

权威产品合同仍为项目根目录四份基线。恢复文档与任务名称使用 v2.2，当前四份基线正文标记为 v2.8；本恢复以指定 Git HEAD 和四份已登记 SHA-256 为确定依据，不在本单元改名或修改基线。

## 2. 恢复事实边界

### 2.1 禁止继续开发的隔离现场

- checkout：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
- 分支：`codex/quarantine-mixed-worktree-20260825`
- 提交：`8c794fa85f015c1afa9c3db2f9145e6a749ed952`
- 用途：保留混合现场并提供只读提取来源。

禁止从该分支继续开发、整体 merge、整体 cherry-pick、发布或推断当前验收。`.superpowers/`、`.workbuddy/`、`分享材料/` 保持用户现场归属。

### 2.2 唯一恢复集成线

`codex/v22-recovery-integration-20260825` 是唯一恢复集成线。它只接收完成独立验证、经过复核并获得用户明确集成授权的恢复单元，不承担日常功能开发。

每个依赖单元只能从最新已授权恢复 HEAD 创建，不能从未集成的 sibling feature branch、quarantine 或复制目录继续分叉。

## 3. 独立 Worktree 判断原则

### 3.1 正式硬规则

> 每个具备独立能力结果、独立验收证据或独立回滚价值的恢复单元，必须使用独立 feature branch 和 linked worktree。单元内部的函数、文件、测试和实现步骤使用 Task 与原子 commit 管理，不继续拆成 worktree。依赖单元必须在前置单元完成验证并经授权集成后，才从新的恢复 HEAD 创建。

### 3.2 五问门

决定是否建立独立 worktree 时依次判断：

1. 能否形成独立、可描述、可验证的能力结果？
2. 能否独立回退并保留其他已经通过的结果？
3. 能否独立延期而不使其他结果失去意义？
4. 是否拥有不同的权威状态、用户表面、外部运行环境或验收证据？
5. 与其他单元混合后，是否会失去问题定位、修改归属或回滚能力？

任一回答为“是”，建立独立 worktree。全部为“否”，保留在同一功能单元，通过 Task、测试和原子 commit 拆解。

### 3.3 四级治理结构

| 层级 | 管理方式 | 含义 |
|---|---|---|
| 恢复功能单元 | 独立 branch + linked worktree | 可独立验收、提交和回退的能力 |
| 单元内原子结果 | 独立 commit | 测试、实现、验证文档等可解释结果 |
| 实施步骤 | 计划中的 Task | RED、最小实现、GREEN、回归、release、fresh host |
| 文件与函数 | 普通代码修改 | 具体配置、resolver、测试用例和辅助函数 |

一个文件、函数、测试、按钮或命令不自动对应一个 worktree。worktree 数量不是安全目标；清晰来源、目标文件冻结、独立测试门、精确提交、串行依赖和用户控制集成共同形成安全边界。

### 3.4 同一 worktree 的合并条件

多个修改点同时满足以下条件时，保留在同一个功能 worktree：

- 共同形成一个不可再分的能力结果；
- 缺少任何一项都会使结果不可用；
- 共享同一回滚理由；
- 共享主要目标文件和测试；
- 必须一起发布或验收；
- 单独集成其中一项不会产生稳定中间状态。

## 4. 恢复序列与 Worktree 矩阵

| 顺序 | 恢复单元 | Worktree 决定 | 边界与进入条件 |
|---:|---|---|---|
| 0 | 工程门 | 默认不建立；真实代码基线失败时单独建立修复 worktree | 每个单元共享准入/退出门；依赖、沙箱和 CapabilityGap 先与代码失败区分 |
| 1 | MCP 打包 Python Runtime | 独立；当前已建立 | 只处理 MCP 清单、Python executable resolver 和聚焦测试 |
| 2A | ReviewSession 权威合同与服务 | 独立 | Python 领域合同、持久化、生命周期、revision、恢复与回执事实 |
| 2B | typed MCP tool catalog | 独立，晚于 2A | Node typed catalog、工具注册分组、schema 和一致性，不夹带 ReviewSession 业务实现 |
| 3A | v2.2 内容权威对象 | 独立 | EvidenceBook、DecisionContext、ProblemSolutionFitMap、ReadingDeckBlueprint 的完整合同链 |
| 3B | 售前方案总师与上下文编排 | 独立，晚于 3A | producer 权限、Context Compiler、Mission/材料输入和自动生产编排 |
| 3C | 两个内容硬门 | 独立，晚于 3B | 两个 reviewer、真实性证据、失败—修复—复验和 acceptance 聚合 |
| 4 | 全稿内容审核后端 | 独立 | PageDecision、Batch、Plan、新版复审、G0 与新内容对象连接；不改已验收前端 |
| 5 | 内容审核关键证据图片 | 独立 | `asset_ref`、真实图片读取、零图片合法、多图稳定顺序和资源安全 |
| 6 | 内容审核前端对齐 | 差异审计确认真实缺口后才建立 | 不因 quarantine 存在另一实现而重做，不自动重开既有用户验收 |
| 7 | 完整视觉合同前端对齐 | 差异审计确认真实缺口后才建立 | 核对恢复线已有已验收前端，内容 UI 与视觉 UI 不合并 |
| 8 | 视觉锚点完整审核链 | 独立 | 真实三图、矩形选区、多条反馈、不可变批次、冲突和回执状态 |
| 9 | 完整验收覆盖恢复 | 独立 | 跨模块测试与验收脚本，不顺手修改业务实现 |
| 10A | release packaging 代码修复 | 发现 build/manifest/installer 代码缺口时才建立 | 只处理 release 工具本身 |
| 10B | 插件安装、fresh host 与最终验收 | 不作为功能开发 worktree | 从精确集成 HEAD 构建发布候选，执行外部状态验证，不产生业务源码修改 |

### 4.1 工程门的例外

工程门不是常驻功能分支。若任何 feature 修改前的 fresh 基线测试出现真实代码失败，必须停止该功能单元，建立 `codex/slice-engineering-gate-repair-<date>` 独立修复并先完成集成。依赖未安装、沙箱 `EPERM` 或回环监听被禁止不能自动触发代码修改。

### 4.2 ReviewSession 与 typed catalog 分离

ReviewSession 决定权威会话状态、sourceVersion/revision、唯一 current session、打开/恢复/提交与回执事实；typed catalog 决定工具如何声明、注册、校验和对外暴露。前者可以在现有桥接上独立验证，后者可以在不改变业务语义的情况下独立重构，因此必须使用串行的两个 worktree。

### 4.3 内容后端分层

内容对象、总师、硬门、全稿审核是四个不同回滚单元。四个内容权威对象本身形成一条不可分割的数据合同，保留在一个 worktree；总师、双硬门和人类审核后端分别建立独立 worktree。两个硬门共享同一输入、reviewer 真实性、修复状态机和 acceptance 聚合，保留在一个硬门 worktree 内按 Task 与 commit 分解。

### 4.4 UI 单元先审计

恢复线已经保留用户验收的内容/视觉生产前端、ViewModel、正式视觉投影和 Review Bridge。内容 UI 与视觉 UI 先做只读差异审计；没有真实缺口时只记录验证证据，不建立 worktree。存在缺口时分别建立独立 worktree，不以技术恢复动作自动重开用户已经完成的前端验收。

### 4.5 发布动作与代码单元分离

build、manifest 或 installer 的代码缺陷属于独立源码修复单元。构建 release、安装、更新 cache、重启 MCP、真实调用和记录结果属于发布/验收动作。安装失败不能自动授权修改业务代码，也不能把“已安装”解释为“已集成、已发布或已验收”。

## 5. 分支推进与集成门

每个功能单元遵循：

```text
已授权恢复 HEAD Rn
-> feature branch + linked worktree
-> 启动审计
-> RED
-> 最小实现
-> 聚焦 GREEN
-> 全量工程门
-> 必要 Browser/release/fresh-host 证据
-> 原子提交 Cn
-> 复核
-> 用户明确授权集成
-> 恢复 HEAD Rn+1
```

硬规则：

1. 禁止在恢复集成 worktree 直接开发；
2. 禁止从未集成 sibling feature branch 继续分叉；
3. 禁止两个活动 worktree 无计划地修改同一核心文件；
4. 禁止 `git add .`，只精确暂存当前单元文件；
5. 禁止整体 merge/cherry-pick quarantine；
6. 未经用户明确授权不 amend、merge、push；
7. `已实现 != 已提交 != 已验证 != 已集成 != 已发布 != 已验收`；
8. 失败单元不能成为后续依赖单元的来源 HEAD；
9. 已集成或放弃的 worktree 只有在确认保留证据和恢复路径后才清理。

## 6. 当前单元：MCP 打包 Python Runtime

### 6.1 问题定义

调用链：

```text
Codex 插件宿主
-> Node STDIO MCP
-> mcp/runtime-bridge/python-runtime.mjs
-> Python Runtime
-> AI PPT Studio 权威项目状态
```

当前 `.mcp.json` 不转发 `AI_PPT_PYTHON`、`AI_PPT_PYTHONPATH`。`python-runtime.mjs` 在没有显式 Python 时只检查系统路径，不认识当前 bundled Node 所属的 Codex runtime。在插件隔离环境中，系统 `/usr/bin/python3` 即使作为文件存在，也可能在 Node `spawn` 时返回 `ENOENT`。

问题发生在 Node MCP 到 Python Runtime 的 executable 绑定边界，不证明 Python 业务服务、项目状态、artifact、revision、Gate、内容审核或视觉审核损坏。

### 6.2 目标解析顺序

```text
options.pythonExecutable
-> AI_PPT_PYTHON
-> 当前 Codex bundled Node 对应的 bundled Python
-> 现有平台系统 Python 候选
-> python3/py 命令名兜底
```

显式 `options.pythonExecutable` 或 `AI_PPT_PYTHON` 是确定选择，不参加自动默认候选重试链。只有未显式配置时，默认候选才逐项处理可启动性。

### 6.3 MCP 清单

修改 `产品代码/.mcp.json`，在 `ai_ppt_studio` STDIO server 中声明：

```json
"env_vars": [
  "AI_PPT_PYTHON",
  "AI_PPT_PYTHONPATH"
]
```

清单只允许宿主已有变量进入 MCP，不保存路径或凭据。`AI_PPT_PYTHON` 指定 executable；`AI_PPT_PYTHONPATH` 只指定 Python 模块根，不参与 executable 推导。

### 6.4 bundled Python 纯解析函数

在 `产品代码/mcp/runtime-bridge/python-runtime.mjs` 增加：

```js
resolveBundledPythonExecutable(
  nodeExecutable = process.execPath,
  platform = process.platform,
)
```

函数只接受非 Windows 的绝对路径结构：

```text
<runtime>/dependencies/node/bin/<node executable>
```

并推导：

```text
<runtime>/dependencies/python/bin/python3
```

判定必须同时满足：

- platform 不是 `win32`；
- node executable 非空且为绝对路径；
- executable 父目录名称为 `bin`；
- 再上一级目录名称为 `node`；
- 再上一级目录名称为 `dependencies`。

结构不匹配时返回 `undefined`，不得猜测父目录。纯函数只推导候选，统一候选阶段负责存在性检查。

### 6.5 候选解析

默认 macOS/Linux 候选顺序：

1. bundled Python；
2. `/usr/local/bin/python3`；
3. `/opt/homebrew/bin/python3`；
4. `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`；
5. `/usr/bin/python3`。

候选统一去重，只保留绝对且存在的路径。没有可用绝对候选时保持现有平台命令名兜底。Windows 保持当前候选规则，不新增 bundled 推导，也不形成 Windows 兼容声明。`options.nodeExecutable` 只用于测试注入，生产默认使用 `process.execPath`。

### 6.6 保持不变的合同

本单元不改变：

- `PLUGIN_ROOT`；
- `AI_PPT_PYTHONPATH` 的模块根语义；
- `PYTHONPATH` 拼装；
- `PYTHONDONTWRITEBYTECODE=1`；
- bridge module 和 stdin/stdout JSON；
- Python Runtime 业务 operation；
- revision、幂等、artifact、Gate 和可信确认；
- release 中现有 Python 源码打包策略。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| 显式 `options.pythonExecutable` 不可启动 | 原样失败，不静默切换 |
| 显式 `AI_PPT_PYTHON` 不可启动 | 原样失败，不掩盖配置错误 |
| bundled Node 路径结构不匹配 | 忽略 bundled 推导，继续系统候选 |
| bundled Python 文件不存在 | 在存在性过滤中移除，继续系统候选 |
| 默认 candidate 启动报 `ENOENT` | 仍有候选时继续下一项 |
| candidate 启动报其他错误 | 立即返回 |
| Python 返回合法业务错误 JSON | 返回 `PythonBridgeError`，不切解释器 |
| Python 返回无效 JSON | 返回内部错误，不解释为 executable 缺失 |
| 所有默认候选无法启动 | 返回明确解释器启动失败 |

## 8. 严格文件范围

实现只修改：

1. `产品代码/.mcp.json`
2. `产品代码/mcp/runtime-bridge/python-runtime.mjs`
3. `产品代码/tests/mcp-runtime-bridge.test.mjs`
4. `产品代码/tests/plugin-shape.test.mjs`

只读验证：

- `产品代码/package.json`
- `产品代码/scripts/build-plugin-release.mjs`
- `产品代码/scripts/verify-plugin-release.mjs`
- `产品代码/scripts/install-plugin.mjs`
- `产品代码/src/ai_ppt_studio/workbench_bridge.py`

禁止修改：

- `scripts/probe-mcp.mjs`、tool catalog、MCP server 和 review bridge；
- Python Runtime 业务服务、领域合同和项目状态；
- Widget、内容审核、视觉审核和四份权威基线；
- quarantine checkout 及其用户未跟踪目录。

如果 RED 或回归证明必须修改第五个生产文件，立即停止并重新审批范围。

## 9. TDD 与验证设计

### 9.1 RED

先只修改两份测试文件，证明：

1. 当前代码不能从模拟 bundled Node 发现 sibling Python；
2. 非 Codex Node 布局被拒绝；
3. `AI_PPT_PYTHON` 优先；
4. `options.pythonExecutable` 最高优先；
5. bundled Python 缺失时回退系统候选；
6. Python 业务错误不触发第二解释器；
7. `.mcp.json` 缺少两个 `env_vars`。

RED 必须指向缺失 resolver/manifest forwarding，两个生产文件保持零 diff。

### 9.2 GREEN

最小实现只增加两个环境变量声明、一个纯 resolver、bundled 默认候选、`nodeExecutable` 注入点和 candidate 去重。不重构整个 bridge，不移动文件，不新增平台抽象层。

### 9.3 聚焦验证

```bash
node --test tests/mcp-runtime-bridge.test.mjs tests/plugin-shape.test.mjs
node --check mcp/runtime-bridge/python-runtime.mjs
node -e 'JSON.parse(require("node:fs").readFileSync(".mcp.json", "utf8"))'
git diff --check
```

### 9.4 真实 bundled runtime

使用实际 bundled Node、清空普通 `PATH`，resolver 必须选择同一 runtime 的 `dependencies/python/bin/python3`，并完成只读 `list-projects`。通过条件是 executable 正确且 bridge 返回 `ok: true`；项目数量不作为固定值。

### 9.5 完整工程门

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

历史测试计数只作为恢复参考，最终报告记录当前 worktree 的 fresh 通过数、失败数和 exit code。

### 9.6 release 传播

构建隔离 release 到 `/private/tmp`，验证 manifest、official plugin validator、`.mcp.json` 和 resolver 传播、受限 PATH bridge，以及禁止的测试、文档、Widget 源码和 Git 数据未进入 release。release/build/install 脚本只读使用。

### 9.7 fresh MCP 与零写入

安装已验证 release、生成新 cache、启动新的插件进程，真实调用只读项目 snapshot。必须证明：

- 返回结构化 snapshot；
- 不再出现 `spawn /usr/bin/python3 ENOENT`；
- 使用新的 release/cache；
- 调用前后 revision、`last_transaction_id`、Gate 和项目状态不变。

历史计划中的具体项目 revision 不作为当前固定值，验收以前置现场读取值为准。源码测试、磁盘安装、cache 存在或工具列表可见都不能代替 fresh MCP 调用。

## 10. 状态与完成边界

| 状态 | 成立条件 |
|---|---|
| 设计已批准 | 用户批准本文设计 |
| 设计已提交 | 本文形成独立 Git commit |
| 计划已批准 | 用户复核后续实施计划 |
| 已实现 | 四个目标文件完成最小修复 |
| 已提交 | 四文件形成独立实现 commit |
| 工程已验证 | 聚焦和完整工程门 fresh 通过 |
| release 已验证 | build、manifest、validator、受限 PATH 通过 |
| 已安装 | release 进入插件安装目录并生成新 cache |
| fresh MCP 已验证 | 新进程 snapshot 和零写入通过 |
| 已集成 | 用户授权后进入恢复集成线 |
| 已发布 | 另行满足发布流程 |
| 已验收 | 用户明确接受对应范围 |

技术完成门：

```text
四文件实现提交
+ 全量工程门通过
+ release 传播通过
+ fresh MCP snapshot 通过
+ 零业务写入
```

本单元不证明 ReviewSession、typed catalog、内容对象、硬门、内容/视觉 UI、G3/G4、完整插件恢复、发布或用户最终产品验收。

## 11. Git 与回滚

本单元文档与实现分离提交：

1. 设计规格提交；
2. 实施计划提交；
3. 四文件实现提交；
4. 只有必要且不改变实现身份时，追加验证证据提交。

只允许 `git add -- <明确文件列表>`。禁止 `git add .`、amend、未经授权 merge/push、破坏性 reset/clean，以及整体 cherry-pick quarantine。

实现回滚使用 `git revert <四文件实现提交>`。设计与计划保留为审计证据。恢复集成线只有在用户明确授权后前进。

## 12. 规格自检结果

- 占位符：未发现未决标记或空缺代码段；条件性 worktree 均有明确触发条件。
- 一致性：全局 worktree 规则、当前四文件范围、错误模型、验证门和回滚设计一致。
- 范围：本文覆盖全局恢复治理和第一个 MCP 单元设计；只有 MCP 单元进入下一份实施计划，其他单元各自需要后续独立设计与计划。
- 歧义：已明确“功能点”指可独立验收/回退的能力单元，不指文件、函数、测试或 Task。
- 能力边界：设计批准和本地工程证据均不自动形成集成、发布或用户验收状态。
