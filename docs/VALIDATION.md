# 验证边界

分发验证覆盖：

- 插件 manifest；
- Marketplace catalog；
- `release-manifest.json` 逐文件 SHA-256；
- 本地 `stdio` MCP 探针；
- 61 个公开工具；
- launcher `--check`；
- 隔离 `CODEX_HOME` 下的本地 Marketplace add、plugin add 和启动前检查；
- 客户名、本机绝对路径、客户文件和高置信凭据扫描；
- 安装与升级文档中的命令合同。

验证不自动建立：

- 另一位真实 Codex 用户已经安装；
- 另一台桌面宿主已经加载；
- 外部图片生成供应方已经认证或产生图片；
- 客户 Runtime、Gate、PPTX 或最终验收已经改变；
- OpenAI 公共 Plugins Directory 已批准。

最终机器回执位于 `validation/marketplace/`。
