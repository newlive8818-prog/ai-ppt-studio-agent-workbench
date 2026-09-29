# 配置说明

AI PPT Studio 使用本地 `stdio` MCP。插件入口为：

```text
node ./scripts/start-mcp.mjs
```

插件可以继承以下非凭据配置变量：

| 变量 | 用途 |
|---|---|
| `AI_PPT_PYTHON` | 指定兼容的 Python 可执行文件 |
| `AI_PPT_PYTHONPATH` | 指定 Python 模块搜索路径 |
| `AI_PPT_IMAGE2_ADAPTER_COMMAND` | 指定经过审核的图片生成适配器命令 |
| `AI_PPT_IMAGE2_RECEIVER` | 指定已核定接收方身份 |
| `AI_PPT_IMAGE2_MODEL` | 指定已核定模型；当前生产路线要求精确型号 |
| `AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST` | 限制适配器可以继承的环境变量 |

不要把 API key、Bearer token、Cookie 或其他凭据写入本仓库、插件 manifest、Marketplace catalog 或项目文件。外部供应方认证应由本机凭据帮助程序或被允许的进程环境提供。

默认工作区名称为用户主目录下的 `Documents/AI-PPT-Workspace`。仓库与分发包不包含该目录中的项目、PPTX、图片、审核数据或 Runtime 状态。

图片生成并非安装验证的一部分。未配置外部适配器时，本地 MCP 和不需要供应方的能力仍可启动；涉及外部生成的调用应按真实配置状态失败或返回能力缺口。
