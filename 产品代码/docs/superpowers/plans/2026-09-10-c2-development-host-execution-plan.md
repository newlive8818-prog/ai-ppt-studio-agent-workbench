# C2 研发宿主启动配置实施计划

> **For agentic workers:** 使用 `superpowers:executing-plans` 按本计划执行；环境修改由总控单一执行，源码与唯一台账由既有 C2 主执行维护。

**Goal:** 保持受审候选包与插件原有策略，通过明确的研发启动入口完成真实 L2 不生图预检。

**Architecture:** 用户已同意以当前需求和新完整插件为目标，允许处理历史安装。现有专用客户端作为研发测试宿主，禁用重复历史插件，只在其进程树注入六个 AI_PPT_* 值；沿用原账户、任务和 Runtime。无需新 Change、新线程或通用加载器。

**Tech Stack:** macOS zsh 启动脚本、现有 Codex API Client 启动器、原插件 env_vars、固定 bundled Python、现有 MCP/Python 预检。

授权与产品边界见[主计划 §12.3](2026-09-07-image-led-visual-upgrade-program-plan.md#123-2026-09-10-研发主线与候选宿主授权)及四基线 v2.13 §1.5。执行事实进入主执行 Worktree 的唯一台账，定位见 [C2 派发入口](../../validation/c2-dispatch/README.md)，复选框本身不证明已完成。

## 1. 核定候选与准备恢复点

- [ ] 读取当前 config，仅核对 AI PPT 插件开关；备份原字节到受控宿主目录，禁止输出或复制凭据到源码。
- [ ] 核对 0949867 候选 manifest、3764 个实际文件及原 launcher 身份；原包不改字节、不伪造更大版本。
- [ ] 以实际当前解释器获取 `sys.executable`，确保与适配器 JSON argv 第一项逐字一致。

候选根固定为 `/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/defei-ai-ppt-studio-040/ai-ppt-studio/0.4.0+codex.c2.0949867.20260910`；manifest SHA256 为 `ae9d472325b36968bc17c677f86bea9351f34888f27c3956452637331ff10097`，wrapper SHA256 为 `855fbb788400c0586b7d669560f048d19ccb0f4048e3606c7e67f686ad66ac20`。本机解释器为 `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。

## 2. 设置研发入口及旧版隔离

- [ ] 在 `/Users/defei/Library/Application Support/AI PPT Studio Development/c2` 保存 `启动-C2研发验证.command`、使用说明和私有配置备份。
- [ ] 脚本只导出 `AI_PPT_PYTHON`、`AI_PPT_PYTHONPATH`、`AI_PPT_IMAGE2_ADAPTER_COMMAND`、`AI_PPT_IMAGE2_RECEIVER=CRS`、`AI_PPT_IMAGE2_MODEL=gpt-image-2`、`AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST=[]`。包内路径从固定候选根派生；不声明新的 CODEX_HOME、不写全局环境、不复制账号、不注入临时 YAML。
- [ ] 脚本核对 manifest，`--check` 校验解释器和 argv；默认发现 ChatGPT 桌面进程仍在时拒绝启动，避免旧进程吞掉新环境。校验通过后 exec 原 `/Applications/Codex API Client.app/Contents/MacOS/Codex API Client`。
- [ ] 仅将 `plugins."ai-ppt-studio@personal".enabled` 从 true 改为 false。解析比较证明其余 config 全等；保持受审插件 enabled，不建立顶层同名用户 MCP。
- [ ] 检查脚本语法、实际子进程六键接收和参数身份；这些准备结果不能替代真实桌面预检。

## 3. 重启与真实 L2

- [ ] 保存重启前相关 PID/PPID/入口与包身份，不输出完整进程环境。
- [ ] 按 §3.1 最新授权由总控处理当前专用客户端的受控正常退出和自动重开；用户手动启动保留为失败后的恢复方式，不再重复要求用户自行重启。只操作已核定实例，不能强制结束其他任务或官方客户端。
- [ ] 重新确认真实新进程、候选路径及工具表 43 项；snapshot 包含布尔 `includeImage2Preflight`，材料 finding 分支存在。
- [ ] 同一客户项目顺序调用普通 snapshot、两次 `includeImage2Preflight=true`。要求四个 presence=true、known_wrapper=true、protocol_probe=passed、helper_executable=true、两个真实 nonce 不同、固定 wrapper hash、external_connection=not-tested。
- [ ] 核对当前客户 revision、Gate、heads 和完整树未因配置/读取改变；保留已有认可。真实回执与进程身份共同记录，shell 结果不升级为桌面证明。

### 3.1 用户要求代理自行处理启动（2026-09-10）

用户明确表示已重启过一次，要求总控自行处理启动问题；该授权覆盖此前仅由用户手动退出的执行安排。总控先保存当前任务续接说明，再由一次性独立进程正常退出确切的专用客户端 PID，并调用已核定研发入口。临时执行器不属于产品插件，不改原入口、受审包、账户、认证、全局环境或客户 Runtime。

执行前及延时后都必须核对当前实例的可执行路径、专用 user-data-dir、AppKit 身份、唯一目标集合、启动器/包/当前配置的固定 hash。只使用正常退出请求，拒绝强制结束，超时保留失败记录。一次性执行锁的所有者才能写回执；重复调用和锁前失败不得覆盖原记录。启动器提前退出即使返回 0 也不能认定桌面已重开，须记为未确认并非零退出，保留同一研发入口的恢复指令。

新进程身份与环境存在性只是启动证据；存在性检查须有可见性对照，不可读记 NotEstablished。重新进入当前任务后仍执行真实 MCP 默认快照及两次预检，不能用执行器或 shell 结果代替 L2。退出可能中断当前 Agent 回合，启动后从保存的同一任务续接，不新建任务或转用终端 Codex 账户。

## 4. 后继工作与恢复

L2 完成后回到既有 C2 功能检查点。此环境适配不发布内容、不登记 finding、不运行真实认证 helper/HTTP/生图、不打开 PowerPoint、不合并或 Push。正式产品配置与交付体验在完整插件验收中闭合，研发启动脚本不自动冒充最终安装方案。

回退时先核对其间用户配置变化，只恢复需要的旧插件开关；原图标启动不具有此脚本注入的配置。保留原包和已存在的恢复点，禁止删除客户 Runtime 或复制旧 Gate。候选升级必须重新固定脚本路径/hash并复验。
