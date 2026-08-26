# C3 内容全稿审核后端与 G0 闭环设计

## 1. 设计身份

- 功能单元：`C3 - Full-deck review backend and G0 closure`
- 分支：`codex/slice-content-review-runtime-g0-20260826`
- linked worktree：`/Users/defei/.config/superpowers/worktrees/PPT-codex-app/slice-content-review-runtime-g0-20260826`
- 直接父提交与回滚点：`5a4cb36712d29bff911a8d4f1ddf6ad5ee4da470`
- 权威产品基线：`v2.8 / 已批准，研发唯一基线`
- 上游权威链：C0 四个内容对象、C1 售前总师、C2 两个 current-source 内容硬门与 `content/acceptance`
- 前端事实：内容审核前端 UI 已由用户验收，本单元不重新设计或修改视觉页面

本设计只定义 C3 的后端权威、恢复和 G0 readiness。它不确认真实 G0，不进入视觉生产、视觉审核、G3、PPTX、交付、G4、发布或安装。

## 2. 问题与设计结论

现有实现已经具备 ReviewSession、PageDecision、不可变 Batch、修订计划和可信 Gate 确认的主体骨架，140 个相邻测试通过。缺口不是“重新做一套内容审核”，而是部分入口和 Gate 重验仍可能依赖服务调用顺序，未把新的 C0/C1/C2 current authority 作为所有关键操作的共同前置。

采用“收窄式加固”方案：保留现有服务边界和已验收前端投影，在 C3 后端增加少量 exact-current 验证，并用一个 real-like 长文档场景证明从 current acceptance 到 `G0=user-reviewable` 的完整链路。

不采用以下方案：

1. 不重写现有内容审核服务。重写会扩大回归面，并可能破坏已经验收的 UI 与 v16 兼容测试。
2. 不复用 legacy `FrameworkConfirmation` 或 `FullDeckExpansionAuthorization` 作为新链权威。它们只允许作为只读迁移输入，不能打开 C3 ReviewSession 或 G0。
3. 不把 `ContentHardGateService.inspect()` 的投影状态当成唯一业务验证器。投影适合状态展示，但关键写操作仍需精确重验 artifact kind、current slot、sourceVersion、hash、revision 和 lineage。

## 3. 权威状态机

```text
current ReadingDeckBlueprint
  + current passed evidence gate
  + current passed presales-reading gate
  + exact current content/acceptance
    -> current content-full-deck ReviewSession
      -> one completed PageDecision per current slide
        -> immutable submitted ContentReviewBatch
          -> all approved
            -> G0=user-reviewable
              -> real trusted-user confirmation only
                -> G0=passed
          -> any change request
            -> chief whole-deck revision plan
              -> trusted current plan confirmation
                -> change set
                  -> new ReadingDeckBlueprint sourceVersion
                    -> invalidate session, decisions, batch, gates, acceptance and downstream
                      -> rerun both gates and fully re-review every slide
```

保存 PageDecision、提交或撤回 Batch、保存或确认修订方案、Host 通知和 AI 回执均不得通过 G0。

## 4. 组件设计

### 4.1 Current content review authority

`content_review/_shared.py` 继续作为 C3 服务的共同 exact-source 边界。它必须验证：

- current `ReadingDeckBlueprint` 是闭合合同；
- Blueprint 精确绑定 current C0 三个上游对象；
- 两个 hard gate 均为 current、passed，并绑定同一 Blueprint hash 与 sourceVersion；
- `content/acceptance` 字段闭合，且精确绑定 Blueprint 和两个 current passed gate；
- current ReviewSession 绑定同一项目、review type、Blueprint ref、sourceVersion 和 Blueprint 权威发布 revision；
- superseded 或 expired session 不可继续投影、保存或提交。

`ReviewSessionService.open_or_resume()` 对 `content-full-deck` 增加前置验证：没有 exact current `content/acceptance` 时，不得创建或恢复内容 ReviewSession。视觉 ReviewSession 行为保持不变。

### 4.2 PageDecision 与 Batch

保留现有四种互斥决定：

- `approved`
- `modify`
- `evidence`
- `merge-or-delete`

非 approved comment 必填且最多 1200 Unicode code points。保存只产生一个不可变 PageDecision 新版本，不改内容、不通知、不改变 Gate。

Batch 仍按 Blueprint 页序收集一页一个 current decision。提交后：

- Batch 和其 decision set 冻结；
- ReviewSession 状态变为 `submitted`；
- 只有尚未形成 current revision plan 的 submitted Batch 可撤回；
- 撤回保存新不可变 Batch 历史，不覆盖旧 bytes，并恢复 ReviewSession 为 ready；
- changed command replay、stale revision、stale source 或跨 session decision 均为零写失败。

### 4.3 Whole-deck revision plan

只有含至少一个非 approved decision 的 current submitted Batch 才能生成修订计划。全 approved Batch 只能进入 G0 readiness，不能制造无意义的修订循环。

修订计划必须表示整稿重审：`rereview_scope` 规范化为唯一值 `['all']`。局部 slide id 或空范围均拒绝。该字段是可审计承诺；真正的完整性仍由新 Blueprint 发布时清除全部旧 decision/session/batch，再由新 Batch 强制一页一个新 decision 双重保证。

计划确认继续使用 project-bound、sourceVersion-bound、revision-bound、single-use challenge 和真实 Host assertion。确认修订计划不等于 G0。

### 4.4 G0 readiness 与真实 G0

`GateEvaluator` 在将 G0 置为 `user-reviewable` 前重新验证完整 lineage，而不是只信任 Batch 中的引用：

- acceptance、Blueprint、Batch 和 ReviewSession 均为 current；
- Batch project、session、sourceVersion、Blueprint、页序和 counts 精确一致；
- ReviewSession 绑定 Blueprint 权威发布 revision，状态为 submitted；
- 每个 Batch decision ref 都是对应 slide 的 current head；
- 每个 decision 的 project、session、sourceVersion、Blueprint、slide id、order、title snapshot、status 和 approved 状态精确匹配；
- decision 的 supersedes lineage 不得循环或跨 slide/source/session；
- 两个 acceptance gate ref 仍解析为 current passed hard-gate records，并绑定同一 Blueprint hash/sourceVersion。

任何缺口只返回 governed blockers，不写 Gate。

真实 `confirm_g0` 继续要求当前 single-use challenge 与 Host 验证身份。工程测试只证明错误输入被拒绝和可信 fixture 可驱动状态机，不能声称发生了真实用户 G0。

### 4.5 Projection、素材和长文档

不改变已验收前端字段和 DOM。后端投影继续：

- 按 Blueprint slide order 输出；
- 保留每页 `material_views` 原顺序；
- `material_views=[]` 合法，不补图片、不读资源、不生成空图片区；
- 只输出 UI 已使用的页面文字、客户判断、素材 asset ref、current decisions、进度、Batch、计划和 ReviewSession 状态；
- 不输出 speaker notes、证据身份、完整内部映射或后台字段目录。

新增 real-like 长文档测试使用不少于 120 页的 mixed 内容，混合零图片页和多素材页，证明：

- 首次投影页序、section 顺序和 material order 稳定；
- 中途 revision conflict 不丢已保存 decisions；
- 刷新后可继续完成剩余页面；
- Batch 顺序与全部 current decision 精确一致；
- 只有 all-approved 完整 Batch 才达到 `G0=user-reviewable`。

### 4.6 Host 与 AI 事实分离

ReviewSession 中以下事实保持独立：

- `persistence_status`
- `host_open_status`
- `host_notification_status`
- `ai_receipt_status`

创建/保存/提交不得自动把 Host 或 AI 状态写成成功。`opened`、`sent`、`received` 必须分别有正确 kind、current session identity 和状态的不可变 receipt。`failed`、`unavailable`、`unverified`、`rejected` 是可持久化事实，但不得升级为成功。

C3 只验证这一分离合同，不修改 Review Bridge 的视觉回执绑定协议，也不制造真实 Host/AI 成功凭据。

## 5. 错误和恢复合同

| 场景 | 结果 | 写入 |
|---|---|---|
| acceptance 缺失、stale 或 malformed | `GateBlockedError` / governed stop | 无 |
| sourceVersion 或 ReviewSession 不 current | `ReviewSourceStaleError` | 无 |
| expectedRevision stale | `RevisionConflictError` | 无 |
| 相同 command id、相同语义 | exact replay | 无新增 revision |
| 相同 command id、不同语义 | command conflict | 无 |
| Batch 未完成 | 明确剩余页 blocker | 无 |
| submitted Batch 后改 decision | `CONTENT_REVIEW_BATCH_FROZEN` | 无 |
| plan 前撤回 submitted Batch | 新 withdrawn 历史，session ready | 一次原子写 |
| plan 后撤回 | `CONTENT_REVIEW_BATCH_FROZEN` | 无 |
| 新 Blueprint 发布 | 清除旧 review/gates/G0/downstream current heads，保留 immutable history | 一次原子写 |
| Host/AI capability 缺失 | `failed/unavailable/unverified/rejected` 事实 | 不伪造成功 receipt |

所有失败路径必须比较前后 KernelState、event files 和 artifact heads，证明零写或预期的一次原子写。

## 6. 目标文件

预计只修改：

- `产品代码/src/ai_ppt_studio/application/content_review/_shared.py`
- `产品代码/src/ai_ppt_studio/application/content_review/planning_service.py`
- `产品代码/src/ai_ppt_studio/application/review_session_service.py`
- `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`
- `产品代码/tests/test_v22_content_review_runtime_g0.py`（新增）

只有 RED 证明现有边界不能由这些文件修复时，才允许收窄增加其他 C3 后端文件。不得修改 Widget、视觉审核、视觉合同、PPTX、交付或 release 文件。

## 7. 测试与通过标准

### Focused RED/GREEN

新增 C3 测试至少覆盖：

1. content acceptance 前直接打开 ReviewSession 被拒绝且零写；
2. session publication revision、project/source/target 任一不 current 时投影与写入被拒绝；
3. all-approved Batch 不能生成 revision plan；
4. 非 `['all']` rereview scope 被拒绝；
5. G0 重验 current session、current decision heads、完整 decision snapshots 和 current passed gate lineage；
6. 新 source 清除旧 review authority，并要求完整重审；
7. 120+ 页 mixed/zero-image/multi-material 顺序与 conflict recovery；
8. persistence、Host open、Host notification、AI receipt 分离；
9. legacy framework/expansion artifacts 不能替代 C2 acceptance 或 C3 Batch；
10. isolated real-like project 只能到 `G0=user-reviewable`，不自造 G0 confirmation。

### Final engineering acceptance

- C3 focused tests 全部通过；
- 相邻 C0/C1/C2/C3 tests 全部通过；
- 全量 Python suite 通过；
- TypeScript typecheck 通过；
- Widget build 通过；
- 全量 Node suite 通过；
- 全量 Widget suite 通过；
- `git diff --check` 通过；
- 独立代码审查 `Critical=0, Important=0`；
- C3 worktree clean；
- 不 merge、不 push、不 release、不 install；
- 不把工程 fixture、Browser preview 或测试 Host assertion 记成真实 G0、Host 通知、AI 回执或用户验收。

## 8. 自审

- 无占位符、未完成章节或待定技术选型；
- 设计只覆盖 C3，不包含视觉及后续 slice；
- 与四基线、恢复计划和 C0/C1/C2 current authority 一致；
- 复用现有服务并最小加固，不整体搬运 quarantine；
- 退出状态明确为 `G0=user-reviewable`，不越权确认真实 G0。
