# AI PPT Studio Agent Workbench

AI PPT Studio 是面向 Codex 的阅读优先售前方案 PPT 工作台。插件通过本地 `stdio` MCP 启动，提供内容治理、整页设计、专业审核、原生可编辑 PPTX 转换和交付验证能力。

当前分支用于 **GitHub Marketplace 私测分发**。它不代表 OpenAI 公共 Plugins Directory 已收录，也不代表另一位真实 Codex 用户已经完成安装或宿主加载。

## 安装

```bash
codex plugin marketplace add newlive8818-prog/ai-ppt-studio-agent-workbench --ref codex/plugin-marketplace-0.4.0
codex plugin marketplace list
codex plugin add ai-ppt-studio@newlive8818-ai-ppt-studio
```

安装后请新建 Codex 对话，使新对话加载插件的 Skill 和 MCP 工具。完整步骤见 [安装说明](docs/INSTALL.md)。

## 当前分发身份

- Marketplace：`newlive8818-ai-ppt-studio`
- Plugin：`ai-ppt-studio`
- Plugin version：`0.4.0+codex.c3.release-20260928`
- MCP transport：本地 `stdio`
- 公开 MCP 工具：`61`
- Runtime 数据：保存在用户本机工作区，不进入本仓库

## 文档

- [安装](docs/INSTALL.md)
- [配置](docs/CONFIGURATION.md)
- [隐私](docs/PRIVACY.md)
- [升级](docs/UPGRADE.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [私测条款](docs/TERMS.md)
- [验证边界](docs/VALIDATION.md)

## 状态边界

源码推送、Marketplace 分支推送、包验证、插件安装、宿主加载、另一位用户验收和公共目录批准是不同状态。本分支的自动化验证只证明分发包及隔离安装链；真实用户安装和新宿主加载需要独立回执。
