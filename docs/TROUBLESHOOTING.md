# 故障排查

## Marketplace 无法添加

先检查 GitHub 认证和仓库访问：

```bash
gh auth status -h github.com
git ls-remote --heads https://github.com/newlive8818-prog/ai-ppt-studio-agent-workbench.git refs/heads/codex/plugin-marketplace-0.4.0
```

不要把访问 token 粘贴到日志或问题报告中。

## 找不到插件

```bash
codex plugin marketplace list --json
codex plugin list --available --json
```

确认 Marketplace 名为 `newlive8818-ai-ppt-studio`，插件名为 `ai-ppt-studio`。

## MCP 启动失败

从安装后的插件根目录检查：

```bash
node ./scripts/start-mcp.mjs
```

该命令会保持 `stdio` 服务运行；手工诊断时可使用包内探针，通过隔离工作区验证 61 个工具。若报告缺少 Node 依赖，应重新安装插件，不要手工修改 cache。

## Python 不兼容

设置 `AI_PPT_PYTHON` 指向兼容的 Python；必要时设置 `AI_PPT_PYTHONPATH`。不要将机器专用绝对路径提交到仓库。

## 新工具没有出现在旧对话

新建 Codex 对话。若新对话仍加载旧 cache，再重启 Codex。插件登记、cache 内容和当前宿主实际加载是三个不同状态。

## 外部图片生成不可用

本地 MCP 可用不代表外部接收方已认证。检查 `AI_PPT_IMAGE2_*` 配置、适配器探针和真实供应方连接状态；不要自动降级型号或重复发送未知状态请求。
