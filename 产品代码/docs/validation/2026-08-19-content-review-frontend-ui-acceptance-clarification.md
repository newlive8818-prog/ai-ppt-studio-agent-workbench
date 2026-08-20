# 内容审核前端 UI 验收口径澄清记录

## 1. 用户最新决定

- 日期：2026-08-19
- 用户明确说明：`这我已经验收了 内容审核页的前端`
- 验收对象：`产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.html`
- 绑定提交：`2607bed docs: restore confirmed content review labels`
- 文件 SHA-256：`18e680304a7218e86e0e553067123aa24f42b7d12da3e64fe3d94ca9989b7692`
- 当前实现分支：`codex/review-surface-v22`

该决定澄清了 2026-08-18 验收记录的对象身份：用户验收的是内容审核页前端本身，不是一个仍需另做“生产 React UI 验收”的临时原型。

## 2. 当前状态

```yaml
contentReviewFrontendUiAcceptance: accepted
acceptedFrontendArtifact: 产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.html
acceptedFrontendCommit: 2607bed
acceptedFrontendSha256: 18e680304a7218e86e0e553067123aa24f42b7d12da3e64fe3d94ca9989b7692
activeProductionRouteIntegration: pending
runtimeMcpAcceptance: not-in-scope
realHostEvidence: false
hostNotificationEvidence: false
aiReceiptEvidence: false
gateConfirmation: none
```

`prototypeUiAcceptance / productionReactUiAcceptance` 的双状态口径自本记录起废止。当前只区分：

1. 内容审核前端 UI 已验收；
2. 当前活动路由尚未忠实接入；
3. Runtime/MCP、真实宿主和 AI 回执尚未完成或待验证。

## 3. 已验收前端范围

- 紧凑项目头、进度和章节定位；
- deck intro、章节与页面连续阅读节奏；
- “这一页的目标”及其内容；
- “希望客户形成的判断”及其内容；
- “页面实际文字”栏及完整标题、段落和要点；
- “文字与图片材料一起审核”栏及页面画面；
- 四类 `PageDecision`；
- 非认可意见页内输入；
- 全页完成后集中提交；
- 已确认的响应式和可用性最低要求。

以下模块继续禁止进入前端：演讲备注、证据身份/来源入口、分析/建议、问题—方案映射、跨页关系、阅读质量和材料元数据目录；也不能转移到折叠区、抽屉、tooltip、hover 或“高级信息”。

## 4. 工程迁移边界

当前 `ContentFullDeckReviewPage` 仍属于旧 React 候选实现，它与已验收前端不一致。后续工程任务是：

```text
已验收 08 前端
-> ContentReviewPageViewModel
-> 纯 adapter
-> 当前活动审核路由
-> Runtime/MCP 投影反向收窄
```

该迁移不得重新设计前端，也不得要求用户为同一 UI 再通过一个“生产 React”验收门。活动路由与已验收前端存在差异时，按工程缺陷处理并回到已验收合同修复。

## 5. 能力真实性边界

本次前端验收不证明：

- ReviewSession 已由真实宿主创建、打开或恢复；
- PageDecision 或 ContentReviewBatch 已通过当前活动页面写入 Python Runtime；
- 宿主通知已发送；
- AI 已取得接收回执；
- G0、G3、G4 或任何产品 Gate 已确认；
- 长文档和真实项目端到端已经通过。

上述能力必须使用各自独立计划、提交、证据和回退点完成。
