# C2 Image 2 Codex 回包兼容与原图适用性

状态：2026-09-11 总控已授权在原 C2 Change / `codex/image-led-native-anchors` / 28a9 Worktree 实施；不新增批准轮次。起点 `6aabea117df8c372d3b09f689db0f1d96b183ba0`（生产源码对应已审 `392642f2a34afd856b07228d97ce2b3180fdc961`）。

## 范围与责任

本轮选择 `CRS / gpt-image-2`，只为该路由明确接纳 `gpt-image-2-codex`。Sunburst 继续精确匹配；未知标识、跨族回报、无效或冲突的每一处显式标识仍拒绝。请求 `model` 不改成供应方回报。复用现有适配器注入，不以通用注册器为前置。

原 v2 输入、客户 `common_rules.background`、文案、目标、材料顺序、语义、来源授权、G0、policy/pack/grant 身份不变。仅 provider prompt 新增固定 `system_output_requirements = {version: image-led-system-output/v1, canvas: {aspect_ratio: 16:9}}`，不指定正文布局。`2048x1152/high/png` 是请求目标，不能回填成实测输出。

返回增量 `provider_observation` 为闭合 `image-led-provider-observation/v1`：`reported.response` 与 `reported.image` 分别保存存在的 `model/quality/size/output_format`；另存 `response_sha256`、本地 `observed_at_utc`、计算得到的 `model_match`（exact / compatible-image2-codex / not-reported）和固定 `independent_engine_proof=false`。已知 CRS v2 command 必须返回该增量；v1 历史六字段回包可读。Runtime 的依赖注入仍可提供旧二字段返回，不能伪造观测：只有实际提供并通过校验才记录。

Runtime 完整解码原字节并保存实际 hash、尺寸与 MIME。当前 v2 CRS 已接入路由增加 `image-led-output-fitness/v1`：`abs(16*h-9*w)<=8`（整数高度四舍五入，误差至多半像素）且 `w>=1280 && h>=720`。这是横屏阅读候选的最低技术分辨率，不是逐字可读、设计还原或用户验收证明；不针对单次 1672×941 白名单。原图未达标仍保全为 completed，当前可用性为 needs-revision，候选/选稿重新核验后拒绝。缺/改观测不能绕过几何门。原生转换严格使用原图实际几何，禁止缩放、裁切或重采样掩盖差异。

## 执行顺序

1. 红测：窄型号兼容、根/条目观测、字段篡改、独立 prompt 输出要求、原授权输入不变；原图不同尺寸、错误比例/分辨率保全、候选阻断和恢复不重发。
2. 最小实现：wrapper → command → Runtime 观测传递；Runtime / candidate 适用性；准确 follow-up；不更改 native 几何合同。
3. 窄同步四基线 v2.14 和当前供应方/input v2/Skill 操作说明，保留所有已接受 C2 章节与历史证据。
4. 离线定向测试与项目要求的 Python 回归；Node 相关桥接/插件测试使用私有依赖，独立代码与文档审查；有失败则修复并重验相关范围。
5. 将红绿日志、审查、变更身份写入 C2 唯一台账；限定本地提交和提交后核验，交总控真实验证。

本任务不执行真实 HTTP、认证 helper、安装、重启、发布、合并、推送或客户材料/运行数据读写。真实非客户 provider tests 由总控在受审修复后另行绑定；本轮离线通过不能改写历史 unknown / rejected 回执，不能表示宿主、三页或 PPTX 已验收。
