# 隐私说明

## 分发包包含什么

分发包包含插件 manifest、本地 `stdio` MCP、AI PPT Studio Python 运行时代码、编译后的 Widget、Skill、生产 Node 依赖、启动与探针脚本，以及逐文件 SHA-256 manifest。

## 分发包不包含什么

本分发包不得包含：

- 客户名称、客户 PPTX、客户图片或客户项目 Runtime 数据；
- 本机用户绝对路径；
- API key、Bearer token、Cookie、私钥或其他凭据值；
- 当前开发者的本地 Codex 配置或插件 cache；
- OpenAI 公共目录审批证明。

机器可读隐私扫描回执位于 `validation/marketplace/privacy-scan.json`。

## 运行时数据

项目材料、生成结果、审核记录和 PPTX 保存在安装者本机的 AI PPT Workspace。插件通过本地 `stdio` 与 Codex 宿主通信；专业审核 Bridge 默认使用本机回环地址。

## 外部图片生成

只有在安装者配置并调用经过审核的图片生成适配器时，相关输入才会发送给外部接收方。安装插件、执行 manifest 验证和运行本地 MCP 探针不会自动发送客户材料或调用图片生成服务。

安装者应确认其拥有材料使用权，并根据实际供应方的条款和隐私政策决定可发送范围。
