# C2 Image 2 Safe Failure Diagnostic Implementation Plan

> **For agentic workers:** 按 `superpowers:executing-plans` 在已授权 C2 Worktree 执行；独立 Review 沿既有分派授权，不创建新的用户任务。

**Goal:** 未来失败回执能区分发送前、请求尝试、收到响应、解码和回执处理，同时不泄漏材料或授权数据。

**Architecture:** 固定包装器输出请求 hash 绑定的闭合失败对象；适配器验证并补入真实 exit；Runtime 保存到原 claim 的 unknown 回执。原成功协议和全部业务输入保持。

**Tech Stack:** Python 标准库、现有 unittest / 临时合成 Runtime。

## Tasks

- [ ] 先在 `tests/test_image2_failure_diagnostics.py` 写失败测试；模拟外部调用，断言 `failure_diagnostic` 存在且含准确阶段，运行并保存 RED。不得调用真实 helper/HTTP。
- [ ] 新建 `adapters/image2_diagnostics.py`：闭合 schema、阶段/类别兼容表、严格整数/布尔与状态关系、重复键拒绝、<=2048 bytes envelope、SHA256 绑定和内部安全失败类型。入口 `validate_diagnostic(value)` / `parse_failure(raw, request_bytes, returncode)` / `CommandFailure`。未知输入固定 ValueError，不回显内容。
- [ ] 修改 `adapters/image2_crs.py`：用逐阶段状态记录原单次操作；在 `main` 失败分支写固定 envelope，preflight 仍旧协议。输出处理不可使 stderr 泄漏；任何无法取得可信诊断的崩溃由父进程降级。
- [ ] 修改 `adapters/image2_command.py`：保存实际序列化 bytes；非零退出仅对已知路由解 envelope，失败默认 not-established；zero-exit 解析错误定位 adapter-receipt。既有 ContractValidationError 仍保持分类。
- [ ] 修改 `application/image_led_service.py`：只接受内部可信失败类型的诊断，实际图像解码失败另建固定诊断；保留现有 claim/CAS/unknown/no-retry/recover 行为。
- [ ] 更新既有 provider 失败断言和合成 wrapper shim，使安全 stdout 允许闭合 envelope，shim 必须原样传递实际 stdin bytes，不能重序列化改变 hash。
- [ ] 运行新测试及 provider/preflight/input-v2/output/Runtime/recovery 相关专项，再运行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:/private/tmp/c2-python-deps python3 -m unittest discover -s tests`。仅新失败有依据时扩大排查。
- [ ] 独立 Review 校验秘密泄漏、阶段真实性、旧历史/no-retry、模型/授权/图片设计边界；修复发现后复验，更新系统基线引用和唯一台账，检查相对链接及原型。
- [ ] 提交受审源码和证据，交总控准确提交/文件 hash 与能力边界。没有安装、真实 helper/HTTP、客户读写、merge/push 或旧 S04 根因结论。

小合同：[安全失败诊断](../specs/2026-09-11-c2-image2-safe-failure-diagnostic.md)。详细 RED 测试代码为本计划第一步落盘的 `tests/test_image2_failure_diagnostics.py`，作为后续实现的可执行验收合同。
