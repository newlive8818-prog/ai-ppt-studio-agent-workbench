# C2 Image-led 输入 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 修复重复标题身份、非可见语义丢失、可选图片被强制覆盖与授权承接意外弹窗，贯穿正式生产及原生核验入口。

**Architecture:** 共用显式 v2 pack/copy/payload/transport，全链以同一个纯派生函数和 alias 映射表达文案与材料。现有 Kernel、授权签名和定版保真保持；AUTH 在 MCP 层限制交互回退。当前已批准范围直接实施，不重新寻求一般许可。

**Tech Stack:** Python domain/application/adapters，Node MCP/wrapper/native renderer，unittest / node:test / Vitest。

唯一规格：[C2 输入 v2](../specs/2026-09-10-c2-image-led-input-v2-design.md)。执行根为本计划所属 Git Worktree；以下路径均相对此根 `产品代码/`。实施开始 HEAD=30ca3bcc；证据根 `/private/tmp/c2-input-v2-implementation-20260910` 已保存470个源文件基准和111个客户文件hash。不得修改客户数据、生图、安装/重启、真实确认或 Git 对象数据库；最终仅提交本次明确文件。

## 1. 冻结规格及窄基线同步（主执行）

- [x] 将 TITLE/SEM/OPTIONAL/AUTH 汇总到同一个正式规格，消除 title_target 位置与 alias 冲突。
- [x] 四基线 §1.4 同步输入身份、语义/授权、可选素材和仅复用行为；保留现有批准状态与证据边界。
- [x] 在独立临时目录保存命令、返回码和 RED/GREEN，不向 Git 写客户派生语句。

## 2. v2 全链实现（TITLE 主实现，SEM 独立审查）

文件：`src/ai_ppt_studio/domains/materials/image_input_contracts.py`、新增 `image_input_v2.py`；`domains/visual/image_led.py`；`application/image_led_service.py`、`image_led_selection.py`、`image_led_native.py`、`image_led_results.py`、`context_compiler.py`；`adapters/image2_command.py`、`image2_crs.py`；`scripts/image-led-native.mjs`；相关现有合同、编译与只读 preflight 入口。

- [x] 先写真实 validate_pack / compile_request_payload / register_candidate / wrapper / native 入口测试，确认 v2 在当前代码 RED。固定案例：标题在第二项、同文不同ID、standalone、16/36/19 项计数。
- [x] 按规格实现共享派生与闭合 v2 校验，核心行为为：

```python
items = [{"item_id": b["block_id"], "kind": "text",
          "role": "title" if b["block_id"] == title_id else "body", "text": b["text"]}
         for b in blocks]
copy = {"copy_version": "image-led-selected-copy/v2", "title_item_id": title_id, "items": items}
text_aliases = {item["item_id"]: f"text-{i:04d}" for i, item in enumerate(items, 1)}
material_aliases = {atom["atom_id"]: f"material-{i:04d}" for i, atom in enumerate(atoms, 1)}
```

- [x] 从精确当前来源派生语义；枚举全部客户字符串并逐条 authorize_atom；非空 required 当前写前拒绝。编译/候选当前性使用同一 copy 派生，按池序核验实际素材子集。
- [x] adapter/wrapper 从 payload_version 明确分派 transport；v2 preflight 核对 generation_protocol，在入队前拒绝旧 wrapper。保留 v1 与 unknown 恢复语义。
- [x] compiler/handoff v2 保存完整 copy，renderer/results 核验 hash 与 regions 双向匹配；不从 regions 重新构造丢版本的 copy。
- [x] 聚焦命令 GREEN：固定 Python `-m unittest discover -s tests -p 'test_image_led*.py'`、`test_image2*.py`；固定 Node `--test tests/image-led-*.test.mjs tests/image2-provider-preflight.test.mjs`。新测试不得依赖客户 Runtime 写入或真实 provider。

## 3. AUTH 真实调用与防回退（主执行）

文件：`mcp/server.mjs`、`mcp/tools/project-tools.mjs`、`tests/image-led-confirmation.test.mjs`、`tests/mcp-server.test.mjs`。

- [x] 先在真实 MCP InMemoryTransport fixture 中调用 `{...input,confirmationMode:"verified-message-only",userMessageRef:"chat://verified"}`，native fixture 仅模拟。断言缺 verifier/ref 时 forms.length=0、calls 仅 get-image-led-confirmation-context，当前应 RED。
- [x] schema 新增：

```javascript
confirmationMode: z.enum(["verified-message-only", "allow-native"]).optional()
```

- [x] 在解析 exact context 后、任何 form 前加入：

```javascript
if (input.confirmationMode === "verified-message-only" &&
    (!confirmationVerifier || !userMessageRef)) {
  return toolErrorResult({code:"CAPABILITY_GAP",
    message:"既有授权的范围记录尚未绑定；当前仅复用路径未触发表单。",
    details:{capability:"image-led-host-confirmation", targetRef:input.targetRef,
      reason:!confirmationVerifier ? "verified-message-adapter-unavailable" : "verified-message-reference-unavailable"}});
}
```

- [x] scope commit 成功回执从实际 artifact_ref / snapshot revision / resolved project root 生成 `authorization_continuation.call={name:"submit_ai_ppt_human_decision",arguments:{projectRoot,expectedRevision,targetRef,choice:"approved",confirmationMode:"verified-message-only"}}`；不自动调用，缺可信回执字段不给 call。
- [x] 通过真实 commit MCP handler 取得 call，再通过真实 submit handler 消费它，证明不存在只写 Skill 的假闭环；覆盖 scope 以外无 continuation、无效回执不猜测、缺 verifier/ref、false/异常、严格 true、stale、取消、allow-native 旧兼容与非Image-led generic。
- [x] 聚焦 `node --test tests/image-led-confirmation.test.mjs tests/mcp-server.test.mjs` GREEN；更新确切公开 schema SHA256，工具仍43项。

## 4. 集成验证与独立 review（主执行+独立代理）

- [x] 所有生产修改稳定后复制到私有验证根，使用已有私有依赖，不写原 node_modules 缓存、不在线安装。清除 AI_PPT_PYTHON，设置 C2_RUNTIME_NODE_MODULES/C2_RUNTIME_PYTHON，Python PYTHONPATH 仅加入私有 PyYAML。
- [x] 按 package.json 完成 typecheck/build、Node全套、Widget全套、Python全套；Node loopback 如需要仅申请测试端口沙箱权限。保留环境错误，不能当产品回归。
- [x] 独立代理先核对正式规格，再检查实现质量；AUTH、SEM 与最终代码质量报告均通过，发现项及修复重放分别记录。结论仅限受审源码和隔离验证。
- [x] 核验四基线相对链接、prototype 引用与空间边界；核验 Runtime111文件hash未变；冻结测试所用文件manifest并与当前源字节对比。

## 5. 本地提交与总控交接（主执行）

- [x] 唯一 ledger 添加本次状态、计数、证据路径、审查结果和能力边界，不将 source proof 写成宿主加载或真实生图。
- [x] 准备明确的提交集合和逐文件身份，保留原 c2-dispatch 两文件和 node_modules 未跟踪状态。提交方式为独立本地 commit，不 merge/push/amend；若 Git 打印摘要因 dataless 历史对象报错，先核验 HEAD/parents/blob/状态，不能盲目再次 commit。
- [x] 整理父提交、逐文件 manifest、测试和独审证据，以及仍未装配的真实 verifier 缺口；真实生图和候选安装在修正受审后由总控衔接。

本计划和验证摘要是提交前冻结文件，实际 commit、父提交复核、暂存区清空及总控消息发送结果以提交后回执为准：`/private/tmp/c2-input-v2-implementation-20260910/postcommit-receipt.json` 与 `controller-handoff-receipt.json`。不得以以上准备项勾选推断提交或消息已成功，也不为把本提交自身SHA写回而另造提交。
