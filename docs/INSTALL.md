# 安装说明

## 前置条件

- 已安装支持 `codex plugin` 命令的 Codex CLI。
- 可以访问 GitHub 仓库 `newlive8818-prog/ai-ppt-studio-agent-workbench`。
- 本机已有 Node.js 和 Python 运行能力；插件包含生产 Node 依赖与 Python 包源码。

## 从 GitHub Marketplace 私测分支安装

```bash
codex plugin marketplace add newlive8818-prog/ai-ppt-studio-agent-workbench --ref codex/plugin-marketplace-0.4.0
codex plugin marketplace list
codex plugin add ai-ppt-studio@newlive8818-ai-ppt-studio
```

检查安装登记：

```bash
codex plugin list --json
```

在输出中确认：

- `pluginId` 为 `ai-ppt-studio@newlive8818-ai-ppt-studio`；
- `version` 为 `0.4.0+codex.c3.release-20260928`；
- `enabled` 为 `true`。

安装后新建 Codex 对话。已经打开的对话通常不会热加载新安装的 Skill 和 MCP 工具。是否必须重启整个 Codex 应用取决于宿主版本；先新建对话，若仍未出现工具，再重启 Codex。

## 当前验证边界

分发分支构建与隔离配置安装成功，不等于另一位真实用户已经安装，也不等于真实桌面宿主已经加载 61 个工具。真实安装验收应单独记录插件身份、工具数和 MCP 启动结果。
