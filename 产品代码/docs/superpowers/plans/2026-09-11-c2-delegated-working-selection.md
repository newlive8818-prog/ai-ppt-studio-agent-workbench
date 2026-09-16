# C2 委托工作选定实施计划

依据：[最小合同](../specs/2026-09-11-c2-delegated-working-selection-design.md)，四基线 v2.15 §1.7 的总控文档提交 `77f195c54dbceff5371149c11c8d4f1b23057d9e`。同一 C2 内的必要候选通路，不新增用户审批或 verifier 前置，不代签用户确认。

1. 先用合成公共请求证明原 Runtime 拒绝 image-led-working-selection，固定三页以外的 proposal 拒绝、来源不能声称可信、用户确认/验收字段不可由调用者设置。
2. selection 服务增加闭合 Agent 工作来源、当前三页严格核验、同次事务发布及重新解析；ImageLedService 增加专用分派。原用户定版分支保留。
3. ContextCompiler 外层带来源/待验收状态，结果提交重建比较；renderer v1/v2 和 TargetBinding 不改。
4. 运行专属测试、原 selection/runtime/handoff 回归以及 v2 公共桥接和内容身份检查。新增范围收窄与来源污染反例；不访问客户、认证 helper 或真实 HTTP。
5. 主任务安排独立 review、统一完整回归、提交和候选构建；总控处理安装、实际生成、原生还原和 PowerPoint。测试状态只进入 C2 唯一验证台账，本文件不复制动态通过数字。

交接时提供改动文件、测试命令/结果、范围及限制。源码实现不等于真实生成、用户定版、G3/G4 或最终人类验收。
