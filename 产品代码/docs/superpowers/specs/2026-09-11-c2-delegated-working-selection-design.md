# C2 三页委托工作选定最小合同

状态：按总控 2026-09-11 明确委托实施；源码和合成测试不构成客户运行、用户验收或发布证明。

权威依据是总控 2a66 Worktree 的四基线 v2.15 §1.7 和主计划 §12.4，文档提交 `77f195c54dbceff5371149c11c8d4f1b23057d9e`。沿用同一 `CHG-IL-C2`、28a9 Worktree 与 `codex/image-led-native-anchors` 分支，不创建新 Change。精确页面为 `C2-S04 / 1`、`C2-S05 / 2`、`C2-S06 / 3`。

## 问题与结果

现有 `image-led-selection` 只能从用户图片确认产生，因此无法表达用户已明确委托 AI 持续制作、但尚未看过新图的内部工作选择。新增单独的工作候选操作；它固定下游设计依据，不声称已经获得用户图片确认。不修改原 `finalize`、ScopedConfirmationPolicy、HMAC/verifier 或 G3/G4 用户验收规则。

输入仍先通过原 G0、材料授权、候选原图/原文核验和独立来源复核。只有以上三页精确 proposal 可进入本通路；任何 `accepted_deviations` 非空均拒绝。工作选择不能代替用户接受内容或设计偏差。

## 正式入口与闭合数据

复用 `commit_ai_ppt_artifact`：`kind=visual-contract`，无需 `taskId` 或用户确认参数。Python 公共路由 `VisualService → ImageLedService → ImageLedSelectionService.register_working_selection` 完成校验与 kernel 事务；不得直接写 Runtime 文件。

请求 payload 仅有：

```json
{
  "artifact_type": "image-led-working-selection",
  "project_id": "当前项目 ID",
  "proposal_ref": "当前三页 image-led-selection-proposal 精确引用",
  "delegation": {
    "source_type": "agent-recorded-user-instruction",
    "verification": "agent-context-only",
    "source_thread_id": "实际来源任务的标准小写 UUID",
    "instruction": "Agent 从当前对话记录的原始用户指令，逐字保留"
  }
}
```

`instruction` 必须非空且不超过 4096 字符。来源任务 ID 只做格式核验，不宣称查验宿主消息；原文也不被解释成执行代码或机器权限。这是 Agent 工作上下文记录，允许明确披露其不可独立认证性，不能填写 `verified-message`、`host-action`、用户已认可等额外字段。本轮实际用户原句含“乘客编辑”语音笔误，记录原文，理解其目标为可编辑 PPT；不得把润色句冒充原话。

Runtime 同一次原子事务发布：

- `visual/image-led/working-delegation` → `image-led-working-delegation`：项目、proposal、固定 scope 与原始 delegation。
- `visual/image-led/selection` → 既有 `image-led-selection` kind 的新显式工作来源形态：项目、proposal_ref、delegation_ref、slides，以及固定 `scope=CHG-IL-C2-three-page-working-candidate`、`selection_origin=delegated-ai-working-selection`、`human_image_approval=NotEstablished`、`final_human_acceptance=NotEstablished`。

selection 不含 `confirmation_ref`，不产生 `image-led-selection-confirmation`，不消费或签发用户确认凭据。每页从当前候选重算原始图片 hash、完整可见文案 hash、材料角色和共同规范引用。已有 command 指纹负责相同输入重复提交；同一 command 不同输入拒绝。过期 proposal、跨项目、错误页序、欠缺来源审核、额外字段或伪造接纳状态在写入前失败。

## 下游与失效

`current_selection` 只在明确工作来源时进入独立复核分支，重新解析当前 delegation、proposal、候选及来源复核并重算整个 selection。原用户 selection 的精确形态和可信确认检查不变。原区域映射、忠实原生 plan、renderer v1/v2 和结果检查继续使用同一 selection_ref / TargetBinding；共同规范不得反向改版。

ContextCompiler 在 `visual_handoff` 外层增加工作来源专属 `selection_provenance`，包括选择来源、精确 delegation_ref、原 delegation 与两个 `NotEstablished` 状态。renderer_handoff 的 v1/v2 闭合合同保持。结果接纳时重建并逐项比较完整外层 handoff，不能删除来源、替换指令或把待验收改成已通过。旧用户选择不增加此字段。

本操作使用既有上游变动失效机制，不推进 G3/G4；变更候选、来源评估、输入或材料授权仍使下游选择/计划失效。最终文件是待用户验收的工作候选，不能以 Agent 来源记录或工程测试声明用户逐图认可、G3/G4 或最终交付接受。

## 验证范围

合成测试覆盖公共 artifact 路由、v1/v2 文案身份、固定三页、独立来源审核继承、来源字段闭合、错误项目/伪造接纳零写入、幂等、区域注册、正式 G1 后 handoff 和结果前重核、来源复核替换失效以及原用户确认路径兼容。合成 G0/图像/评估全部是测试夹具。真实客户三页、实际 Native/PowerPoint 和最终用户验收由总控分别核验。
