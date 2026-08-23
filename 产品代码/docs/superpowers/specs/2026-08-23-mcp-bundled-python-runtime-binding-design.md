# AI PPT Studio MCP Bundled Python Runtime 绑定设计

## 1. 状态与范围

- 日期：2026-08-23
- 状态：用户已批准方案 3，等待书面规格复核后实施
- 目标：修复 AI PPT Studio Node MCP 在 Codex 插件隔离环境中调用 Python Runtime 时出现的 `spawn /usr/bin/python3 ENOENT`
- 范围：MCP 启动配置、Python executable 解析、聚焦回归、release 构建、插件安装和 fresh-process 验证
- 不在本次范围：验收台账迁移、视觉 reviewer fixture、MCP 工具数量探针、G4 业务确认、项目关闭和经验复盘

## 2. 已确认根因

AI PPT Studio 插件由 Codex 启动 Node STDIO MCP，Node MCP 再为每次业务调用启动 Python bridge。当前 `.mcp.json` 没有转发 `AI_PPT_PYTHON` 或 `AI_PPT_PYTHONPATH`；`python-runtime.mjs` 在缺少显式 Python 时只查找系统路径，最终选择 `/usr/bin/python3`。该路径在普通终端可见，但在当前插件 MCP 隔离执行环境中不可启动，因而 `spawn` 返回 `ENOENT`。

项目 Runtime、PPTX、artifact、revision 和业务状态没有因此损坏。直接使用 Codex bundled Python 调用同一 Python Runtime 已成功，故修复应发生在 Node MCP 到 Python Runtime 的 executable 绑定边界。

## 3. 采用方案

采用用户批准的双保险方案：

1. `.mcp.json` 声明转发 `AI_PPT_PYTHON` 与 `AI_PPT_PYTHONPATH`；
2. `AI_PPT_PYTHON` 保持最高优先级；
3. 未提供显式变量时，从当前 Node executable 推导同一 Codex bundled runtime 中的 Python；
4. bundled Python 不存在时，才回退到现有平台系统候选；
5. 所有候选均保持 ENOENT 逐个重试；非 ENOENT 错误立即返回，不掩盖真实 Python Runtime 失败。

不得写死 `/Users/defei/...`、用户名、当前 cachebuster 或某个 Python patch 版本。

## 4. 解析顺序

macOS/Linux 的 Python executable 顺序固定为：

1. 调用方显式传入的 `options.pythonExecutable`；
2. MCP 环境中的 `AI_PPT_PYTHON`；
3. 从 `options.nodeExecutable` 或 `process.execPath` 推导的 bundled Python：
   - 输入形态：`<runtime>/dependencies/node/bin/node`
   - 目标形态：`<runtime>/dependencies/python/bin/python3`
4. `/usr/local/bin/python3`；
5. `/opt/homebrew/bin/python3`；
6. `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`；
7. `/usr/bin/python3`；
8. 如果没有绝对候选存在，则回退命令名 `python3`。

Windows 维持现有候选规则；本次不新增 Windows bundled runtime 推导，也不作 Windows 兼容声明。

推导逻辑只接受符合 `.../dependencies/node/bin/<node executable>` 结构的 Node 路径。若结构不匹配，返回空候选并继续系统回退，不能根据不确定的父目录拼接 Python 路径。

## 5. 组件改动

### 5.1 MCP 清单

文件：`.mcp.json`

在 `ai_ppt_studio` STDIO server 配置中增加：

```json
"env_vars": [
  "AI_PPT_PYTHON",
  "AI_PPT_PYTHONPATH"
]
```

它只允许宿主已有变量进入 MCP，不保存机器路径或凭据。

### 5.2 Python executable 解析

文件：`mcp/runtime-bridge/python-runtime.mjs`

新增一个纯解析函数，根据 Node executable 返回 bundled Python 候选。`resolvePythonExecutables` 在显式环境变量之后、系统候选之前插入该候选，并保持去重和存在性检查。为可测试性，解析入口接受 `options.nodeExecutable`；生产默认使用 `process.execPath`。

不改变：

- Python module root 选择；
- `PYTHONPATH` 拼装；
- `PYTHONDONTWRITEBYTECODE`；
- bridge request/response JSON 合同；
- Python Runtime 的业务写入规则；
- Gate、revision、artifact 或 host confirmation 逻辑。

## 6. 错误处理

- 候选 executable `ENOENT`：继续尝试下一候选；
- 候选存在但 Python bridge 返回业务错误：立即原样返回，不切换解释器；
- bundled Node 路径结构不匹配：忽略该推导候选，继续系统回退；
- 所有候选不可启动：保留明确的 Python interpreter 启动错误；
- 不用 `/usr/bin/python3` 失败自动证明 Codex bundled Python 失败。

## 7. TDD 与验证矩阵

先新增失败测试，再修改生产代码。最低测试矩阵：

1. `options.pythonExecutable` 覆盖全部候选；
2. `AI_PPT_PYTHON` 覆盖 bundled 和系统候选；
3. 从模拟的 `<runtime>/dependencies/node/bin/node` 发现 `<runtime>/dependencies/python/bin/python3`；
4. Node 路径结构不匹配时不产生错误的 bundled 候选；
5. bundled Python 缺失时回退现有系统候选；
6. 第一个 candidate 抛 `ENOENT` 时继续尝试下一 candidate；
7. 非 `ENOENT` 错误不重试；
8. `.mcp.json` 包含两个环境变量转发项；
9. 在普通 `PATH` 为空时，使用 Codex bundled Node 启动 bridge 仍能完成真实只读 Runtime 调用；
10. release 包中的 `.mcp.json` 和 `python-runtime.mjs` 与源码修复一致。

## 8. 安装与真实验收

实现通过后：

1. 构建新的插件 release；
2. 校验 release manifest；
3. 安装到插件源目录；
4. 生成新的 cachebuster 并重新 `codex plugin add`；
5. 独立进程以受限环境调用 Python bridge，确认不再选择不可执行的系统 Python；
6. 重启 Codex 当前 MCP；
7. 在 fresh MCP 进程中真实调用 `get_ai_ppt_project_snapshot`；
8. 只有 fresh MCP 调用成功，才把本项标记为完成。

磁盘安装、工具清单存在、单元测试或独立 Python Service 成功，均不能单独替代第 7 步。

## 9. 版本与回滚

- 本修复使用当前分支 `codex/main-worktree-freeze-20260821`；
- 设计规格和实现分别形成可识别提交，或在实施计划明确的原子提交中保持边界；
- 不 amend 既有 `2d832fb`；
- 不修改用户无关未跟踪目录 `.superpowers/`、`.workbuddy/`、`分享材料/`；
- 回滚使用 `git revert <本修复提交>`，不使用破坏性 reset 或 clean；
- Runtime 项目 revision 在代码修复和安装阶段保持不变。

## 10. 完成标准

本项只有同时满足以下条件才算完成：

- 失败测试先证明旧逻辑无法发现 bundled Python；
- 修复后聚焦测试和相关 Node/MCP 回归通过；
- release 构建和 manifest 校验通过；
- 新插件版本完成安装；
- fresh Codex MCP 成功调用真实项目快照；
- 不再出现 `spawn /usr/bin/python3 ENOENT`；
- Git diff 仅包含本项文件且 `git diff --check` 通过；
- 形成独立、可回滚的 Git 提交。
