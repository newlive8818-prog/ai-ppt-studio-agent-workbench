# AI PPT Studio v2.2 ReviewSession 权威合同与服务恢复设计

## 1. 文档身份

- 日期：2026-08-26
- 状态：`用户已批准设计`
- 适用范围：AI PPT Studio v2.2 受控恢复序列的第二个独立研发单元 `2A ReviewSession 权威合同与服务`
- 权威项目根：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`
- 来源恢复分支：`codex/v22-recovery-integration-20260825`
- 来源恢复 HEAD：`6c458f7b0c2f81a1f85db3afea9a917a161b1124`
- 计划中的功能分支：`codex/slice-review-session-authority-20260826`
- 计划中的 linked worktree：`/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826`
- 实现回滚点：`6c458f7b0c2f81a1f85db3afea9a917a161b1124`
- 恢复依据：[版本隔离与恢复基线](../../validation/2026-08-25-version-quarantine-and-recovery-baseline.md)
- 相关恢复设计：[受控恢复 Worktree 边界与 MCP 打包 Python Runtime 设计](2026-08-25-v22-controlled-recovery-worktree-and-mcp-runtime-design.md)
- 非用途：本文不是实现提交、实现批准、合并批准、发布说明、真实宿主能力证明或用户最终产品验收。

本文已在恢复集成 worktree 中经过分段设计确认。本文提交只记录设计，不创建实现 worktree，不修改业务代码，不修改 quarantine checkout。

## 2. 背景与恢复原则

### 2.1 当前恢复线是唯一实现基线

当前恢复线已经包含一套比 quarantine 历史提交更成熟的 ReviewSession 实现。现有实现已经覆盖：

- `content-full-deck` 与 `visual-professional` 两类审核会话；
- current target 与 target kind 校验；
- sourceVersion 校验；
- 从事件历史解析权威 target publication revision；
- 历史、未来和伪造 revision 拒绝；
- deterministic session ID；
- 同一 current session 的重开与恢复；
- 新 source 对旧 session 的原子 supersede；
- host-open、host-notification、AI receipt 的可信引用；
- visual saved artifact 与 receipt 的精确绑定；
- command fingerprint、幂等回放和 revision conflict；
- stale/invalid 请求的零写入保护；
- Python bridge 和项目用户状态投影。

因此，本单元不重放、不覆盖、不 cherry-pick quarantine 的历史 ReviewSession 提交：

```text
826d290
903171c
5c08916
a215249
```

这些提交只作为只读历史证据。实现必须以本设计指定的恢复 HEAD 为基线，在现有加固实现上补齐权威合同与服务缺口。

### 2.2 本单元目标

本单元只解决 Python Runtime 内 ReviewSession 的：

1. 权威状态合同完整性；
2. 生命周期、恢复和 current 唯一性；
3. sourceVersion/revision 的真实性与过期保护；
4. 宿主打开、宿主通知和 AI 回执的独立事实；
5. 能力缺失、失败和未验证状态的诚实持久化；
6. 稳定错误码和 Python bridge/workbench 错误边界；
7. 项目用户状态投影；
8. 对应的零写入、幂等和回归测试。

本单元不解决 typed MCP tool catalog、Node MCP 注册、Review Bridge HTTP 协议、内容审核业务对象、视觉审核前端或真实宿主验收。

## 3. 设计选择

### 3.1 方案比较

#### 方案 A：在当前加固实现上补齐权威合同（采用）

保留当前恢复线已有的 revision 防伪、trusted receipt、saved-artifact 绑定、replay 和零写入保护，只扩大合同和补齐缺失的服务、错误和测试路径。

优点：

- 不丢失后续安全加固；
- 变更面最小；
- 可在 Python Runtime 内独立验证；
- 回滚点清晰；
- 不会将 2A 与 2B 的问题混在一起。

#### 方案 B：重放 quarantine 的四提交实现（不采用）

历史实现的状态枚举更宽，但早于当前恢复线的 revision 防伪、可信回执绑定和更严格幂等加固；覆盖当前文件会重新引入已修复风险。

#### 方案 C：2A 与 2B 一起恢复（不采用）

违反 `2A -> 2B` 串行边界，增加失败定位和回滚难度，也会把 Python 业务合同、Node schema 和工具注册混为一个能力结果。

### 3.2 核心原则

> ReviewSession 是 Python Runtime 的权威业务事实；Node、Widget、MCP catalog 和 Review Bridge 只能通过正式 bridge 读取或请求改变事实，不能建立第二套 current session 或通过定时器推断成功状态。

## 4. 权威架构与数据流

### 4.1 唯一事实链

```text
Codex/Review Bridge/未来 typed catalog
        |
        v
Python bridge
        |
        v
ReviewSessionService
        |
        v
ProjectKernel.commit
        |
        +--> kernel/state.json
        +--> event history
        +--> immutable artifact store
        +--> review/session/{review_type} current head
```

不新增 ReviewSession 专用数据库、Node 内存态 registry、Widget 本地 current session 真相、独立 session cache 或第二套 revision 来源。

### 4.2 current head

继续使用当前 Kernel slot：

```text
review/session/content-full-deck
review/session/visual-professional
```

同一 `project_id + review_type + target_artifact_ref + source_version + revision` 只能有一个 current session。旧 session 保留为不可变历史，通过 `superseded` 或 `expired` 表示不再 current。

### 4.3 写入规则

所有 session 变化必须经过 `ProjectKernel.commit`，并同时接受 expected revision、current target、session identity、trusted receipt、command fingerprint/replay 和 artifact reference 校验。

任何校验、stale、冲突或伪造失败都必须保持零写入。宿主/AI 外部能力失败则作为失败事实安全写入，具体见第 7 节。

## 5. ReviewSession 合同

### 5.1 最小字段

```text
review_session_id
review_type: content-full-deck | visual-professional
project_id
target_artifact_ref
source_version
revision
status
open_policy: foreground-if-waiting | notify-only
host_open_status
persistence_status
host_notification_status
ai_receipt_status
created_at
last_opened_at
submitted_at
```

允许的历史/回执绑定字段继续受 trusted service 上下文保护：

```text
host_open_receipt_ref
host_notification_receipt_ref
host_notification_receipts
ai_receipt_ref
ai_receipts
superseded_at
expired_at
```

`expired_at` 是本单元为 `expired` 状态补充的明确生命周期字段；不能用 `superseded_at` 代替。

### 5.2 主状态

完整合同为：

```text
preparing
ready
opened
submitted
superseded
expired
```

语义：

- `preparing`：会话已进入准备阶段，但准备工作尚未完成；用于恢复、导入或未来分阶段准备；
- `ready`：target/source 已验证，会话已保存并等待打开或用户处理；
- `opened`：已获得真实宿主打开回执；
- `submitted`：用户已提交审核结果，保留后续宿主/AI 回执；
- `superseded`：新的 sourceVersion/revision 已成为 current，旧会话失效；
- `expired`：明确的 Runtime 生命周期命令使会话过期；不由自动定时器推断。

当前 `open-or-resume` 继续原子完成准备和保存，默认直接产生 `ready`；本单元不把已有同步行为改成强制异步两步提交。

允许的业务转移：

```text
preparing -> ready
ready -> opened
ready/opened -> submitted
ready/opened/submitted -> superseded
ready/opened/submitted -> expired
```

`superseded` 和 `expired` 不再是 current，不能接受新的打开、通知或 AI 回执。

### 5.3 独立事实维度

Host open：

```text
not-requested
pending
opened
failed
unavailable
```

Host notification：

```text
not-requested
pending
sent
failed
unavailable
```

AI receipt：

```text
pending
received
rejected
unverified
```

状态之间不得相互推断：

- `persistence_status=saved` 不等于 host 已打开；
- host 已打开不等于通知已发送；
- 通知已发送不等于 AI 已接收；
- `unverified` 不得升级为 `received`；
- Browser 关闭不等于 session expired。

### 5.4 初始化策略

| open_policy | 初始 host_open_status | 初始 host_notification_status |
|---|---|---|
| `foreground-if-waiting` | `pending` | `not-requested` |
| `notify-only` | `not-requested` | `pending` |

初始 `ai_receipt_status` 为 `pending`。

### 5.5 persistence_status

ReviewSession 进入权威 Runtime 时只允许：

```text
persistence_status = saved
```

`saving` 是事务内部瞬时状态，`failed` 代表写入未成功，不能被持久化成一条假的 ReviewSession。Kernel commit 失败时 revision、current head、半成品 session 和 event 都不应发生变化，`kernel/state.json` 必须保持字节级不变。

该语义只适用于 ReviewSession，不修改视觉审核批次已有的 `saving/failed` 合同。

## 6. 生命周期与恢复

### 6.1 open-or-resume

调用必须验证：

1. review type 是两个专业审核类型之一；
2. target 是对应 current source slot 的当前 artifact；
3. source revision 等于 target 的真实 publication revision；
4. source version 与 target payload 匹配；
5. expected revision 等于当前 Kernel revision；
6. open policy 合法。

完全相同 identity 的请求返回现有 current session，不增加 revision。若 identity 相同但 open policy 等关键请求参数不兼容，则返回 `REVIEW_SESSION_ALREADY_CURRENT` 并零写入。

### 6.2 supersede

新 sourceVersion/revision 成为 current 时，在一个 Kernel commit 中写入新 current session、将旧 current session 标为 `superseded`、保留旧不可变 artifact 和历史事件，并禁止旧 session 继续写入。

### 6.3 expire

`expired` 只由明确的服务命令产生，要求 current session identity 和 expected revision 正确，记录 `expired_at`，从 current slot 移除或替换为新的 current，保留不可变历史，且不能将过期自动归因于 Browser 关闭或本地进程退出。

### 6.4 Browser 关闭与恢复

Browser/宿主关闭不改变主状态。稍后重开时查找同一 sourceVersion/revision 的 current session，恢复审核对象、已保存状态和已记录回执；只有真实 host-open receipt 才将 host open 状态设为 `opened`，不创建第二个 current session。

## 7. 失败、能力缺失与稳定错误

### 7.1 稳定错误码

本单元在 Python Runtime 与 workbench/bridge 边界提供：

```text
REVIEW_SESSION_STALE
REVIEW_SESSION_ALREADY_CURRENT
REVIEW_HOST_OPEN_UNAVAILABLE
REVIEW_HOST_OPEN_FAILED
REVIEW_AI_RECEIPT_UNVERIFIED
```

### 7.2 校验失败与外部失败的差异

以下属于校验/一致性失败，必须零写入：

```text
REVIEW_SESSION_STALE
REVIEW_SESSION_ALREADY_CURRENT
REVISION_CONFLICT
invalid target
invalid receipt
wrong saved artifact
wrong source version
wrong session identity
```

以下属于已经发生的外部能力结果，可以写入失败事实：

```text
REVIEW_HOST_OPEN_UNAVAILABLE
REVIEW_HOST_OPEN_FAILED
REVIEW_AI_RECEIPT_UNVERIFIED
```

写入失败事实后，bridge 仍然返回错误 envelope，而不是成功 envelope。错误响应必须包含稳定 code，并在可用时包含当前 session 和 revision，方便调用方恢复。

### 7.3 host open

- `pending -> opened`：必须绑定真实 host-open receipt，更新 `last_opened_at`，必要时将主状态从 `ready` 变为 `opened`；
- `pending -> failed`：宿主已尝试但失败，持久化 `failed` 并返回 `REVIEW_HOST_OPEN_FAILED`；
- `pending -> unavailable`：宿主能力不存在或不可用，持久化 `unavailable` 并返回 `REVIEW_HOST_OPEN_UNAVAILABLE`；
- failed/unavailable 不能被解释为 opened；
- receipt identity 不匹配时零写入。

### 7.4 host notification

- `pending -> sent`：必须有真实 notification receipt；
- `pending -> failed`：记录发送失败；
- `pending -> unavailable`：记录能力缺失；
- `pending` 不能投影为“成果已可查看”；
- `sent` 才能满足后台成果已通知事实。

### 7.5 AI receipt

- `pending -> received`：必须有可验证 AI/宿主回执；
- `pending -> rejected`：收到明确拒绝结果；
- `pending -> unverified`：验证器不可用、超时、身份不完整或证据不足；
- `unverified` 不得自动升级为 `received`；
- `unverified` 返回 `REVIEW_AI_RECEIPT_UNVERIFIED`；
- AI receipt 不改变 `submitted` 主状态。

## 8. 项目用户状态投影

用户界面仍只接收：

```text
任务受阻
需要你处理
成果已可查看
AI 正在处理
```

建议投影：

| Runtime 事实 | 用户状态 |
|---|---|
| foreground + host open pending | 需要你处理 |
| notify-only + notification pending | AI 正在处理 |
| notification sent | 成果已可查看 |
| host open failed/unavailable | 任务受阻 |
| AI receipt rejected/unverified | 任务受阻 |
| submitted + AI receipt pending | AI 正在处理 |
| superseded/expired 非 current | 不作为 current 候选 |

`unavailable` 和 `unverified` 不得降级为普通处理中。投影必须使用当前 Kernel state，输出当前 revision，不读取 Widget 本地状态，不使用定时器推断，不把历史 session 当作 current，也不改变业务事实。

## 9. 文件边界

### 9.1 2A 允许修改

实现 worktree 创建后，只允许修改：

```text
产品代码/src/ai_ppt_studio/domains/review/contracts.py
产品代码/src/ai_ppt_studio/application/review_session_service.py
产品代码/src/ai_ppt_studio/application/project_status_projection.py
产品代码/src/ai_ppt_studio/application/bridge/review.py
产品代码/src/ai_ppt_studio/errors.py
产品代码/src/ai_ppt_studio/workbench_bridge.py
```

以及与这些 Python 合同直接对应的测试文件：

```text
产品代码/tests/test_v22_review_session.py
产品代码/tests/test_review_session_authoritative_revision.py
产品代码/tests/test_v22_project_status_projection.py
产品代码/tests/test_v16_bridge.py
```

如果 RED 或回归证明必须修改第五个生产文件，必须停止并重新取得范围批准。不得因为测试方便而扩大到 Node 或 Widget。

### 9.2 明确排除

本单元不得修改：

```text
产品代码/mcp/tool-catalog.mjs
产品代码/mcp/server.mjs
产品代码/mcp/review-bridge.mjs
产品代码/widget/
```

也不得顺手修改内容审核对象、内容审核前端、视觉审核前端、售前方案总师、内容硬门或 G0/G3/G4 推进。

## 10. 测试矩阵

### 10.1 合同测试

覆盖六个主状态、host open 的 pending/unavailable、host notification 的 pending/unavailable、AI receipt 的 rejected/unverified、success receipt 的 trusted reference 要求、submitted_at/superseded_at/expired_at 约束、未受信任调用保护以及 `persistence_status=saved` 不变量。

### 10.2 Service 测试

覆盖 current 唯一性、完全相同请求幂等恢复、不兼容重复请求的 `REVIEW_SESSION_ALREADY_CURRENT`、source publication revision 防伪、sourceVersion stale、原子 supersede、明确 expire、Browser 关闭后的同 session 恢复、两种 open policy 初始状态、host open 三种结果、notification 三种结果、AI receipt 三种结果、submitted 保持、receipt 绑定、command replay、revision conflict、零写入和外部失败事实持久化。

### 10.3 Project status projection 测试

覆盖四种用户状态优先级、foreground pending、notify-only pending、sent 后成果可查看、host failed/unavailable、AI rejected/unverified、submitted + AI pending、superseded/expired 过滤、空候选默认状态、revision 绑定以及不从 UI/定时器推断事实。

### 10.4 Bridge/workbench 错误边界测试

覆盖 Python bridge 正式 ReviewSession 操作、五个稳定错误码、错误 envelope 的 `ok/code/message/details`、已持久化失败事实的当前 session/revision、raw Kernel state 禁止作为公共写入接口、错误不退化为 `VALIDATION_ERROR` 以及不创建 Node/Widget 第二套事实。

## 11. TDD 与验证门

### 11.1 RED

在 feature worktree 中先增加失败测试，再写最小实现。RED 必须证明当前实现缺少完整状态枚举、pending/unavailable/unverified/rejected 事实、五个稳定错误码、explicit expired 生命周期、能力失败与零写入的区分以及对应项目状态投影。

### 11.2 GREEN

实现只增加当前合同和服务所需的最小代码，不重构无关领域，不修改 Node catalog、Review Bridge 或 Widget。

### 11.3 聚焦验证

预计运行：

```bash
cd /Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826/产品代码

PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest \
  tests.test_v22_review_session \
  tests.test_review_session_authoritative_revision \
  tests.test_v22_project_status_projection \
  tests.test_v16_bridge

git diff --check
```

实际测试数量以 feature worktree 的 fresh 输出为准，不沿用历史计数。

### 11.4 完整工程门

按照恢复基线继续运行：

```bash
npm run typecheck
npm run test:python
npm run test:node
npm run test:widget
npm run build
```

必要时运行 `npm run quality`。这些命令证明本地工程回归，不证明真实宿主、真实 Browser、真实 AI receipt、Gate、PowerPoint、发布或用户验收。

## 12. 通过标准

2A 只有在以下条件全部满足时，才能标记为 feature 本地完成：

1. 权威 ReviewSession 合同通过状态和 receipt 验证；
2. current、resume、supersede、expire、stale、revision conflict 全部通过；
3. host open 的 opened/failed/unavailable 全部通过；
4. host notification 的 sent/failed/unavailable 全部通过；
5. AI receipt 的 received/rejected/unverified 全部通过；
6. 五个稳定错误码在 Python bridge/workbench 边界可观测；
7. 校验、stale、冲突、伪造请求零写入；
8. 外部能力失败被诚实持久化且不能形成成功事实；
9. 项目状态投影与权威事实一致；
10. Python、Node、Widget、typecheck、build 回归通过；
11. 修改范围只属于 2A；
12. 设计、实现、测试和回滚证据可独立审查。

本单元最终状态必须分别报告：

```text
已设计
已提交
已实现
已验证
已集成
已发布
已验收
```

不得把前四项自动升级为后三项。

## 13. Git、Worktree 与回滚

### 13.1 Worktree 创建时机

设计规格提交并经用户复核、实施计划获批后，才从：

```text
codex/v22-recovery-integration-20260825
```

创建：

```text
分支：codex/slice-review-session-authority-20260826
目录：/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-review-session-authority-20260826
```

在此之前不得在恢复集成 worktree 开始实现。

### 13.2 提交边界

设计与实现分离：

```text
docs: design ReviewSession authority recovery
feat: complete ReviewSession authority contract
```

只允许精确暂存目标文件，禁止 `git add .`。未经明确授权不得 amend、merge、push。

### 13.3 回滚

本单元实现回滚点为：

```text
6c458f7b0c2f81a1f85db3afea9a917a161b1124
```

实现提交后如需回滚，使用该 feature commit 的可审计 revert；不 reset/clean 共享或 quarantine checkout。恢复集成线只有在用户明确授权后才前进。

## 14. 范围外事项

以下事项明确留给后续单元或真实验收：

- 2B typed MCP tool catalog；
- Node tool registration 和 schema 一致性；
- Review Bridge HTTP/Browser 的真实宿主行为；
- 内容审核后端和前端；
- 视觉审核后端和前端；
- G0/G3/G4；
- 真实宿主通知协议；
- 真实 AI 接收回执格式、超时和重试；
- PowerPoint、发布和用户最终验收。

## 15. 规格自检

- 占位符：无未决 TODO、TBD 或空缺实现要求。
- 一致性：状态机、独立事实维度、错误边界、投影、测试和 Git 边界一致。
- 范围：只覆盖 2A；2B、内容审核和视觉审核明确排除。
- 事实边界：本地测试、bridge fixture、安装或 build 不会被描述为真实宿主或用户验收。
- 回滚：设计提交、实现提交和恢复集成分别可定位；实现回滚点固定为 `6c458f7b…`.
