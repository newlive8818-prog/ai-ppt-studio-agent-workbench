# AI PPT Studio v1.6 最终验收状态

**记录时间：** 2026-08-11T18:51:59+08:00  
**提交状态：** 未提交  
**总体结论：** 未达到 104/104；当前存在不可替代的 Codex Presentations 宿主能力缺口。

## 已完成的真实结果

- 最新完整插件 `ai-ppt-studio@defei-ai-ppt-studio-040` 已重装并启用，版本为 `0.4.0+codex.20260811084333`。
- 插件源码、本地市场和 Codex 缓存中的 `widget/dist/index.html` SHA-256 一致：`a7af3534eb9bf974c8f0a85b8e9da8854d4bdcf96994d048ca3c62007da8de5b`。
- 旧独立 Skill `/Users/defei/.codex/skills/ai-ppt-studio` 已清理，未保留临时备份。
- 真实项目保持 schema 3，G0 已通过。
- 内容蓝图、内容验收、Visual Brief、Deck Design System、12 页视觉合同、视觉收敛和 G1 独立审美审查制品均可解析。
- G1 已用当前视觉收敛与独立审美审查制品正式记录；项目从 revision 40 进入 revision 41。
- 当前 Gate 为 `G0 passed / G1 passed / G2 open / G3 locked / G4 locked`。
- OpenAI 官方 `presentations@openai-primary-runtime` 已通过正式 marketplace/CLI 流程安装并启用，版本 `26.805.11740`；源与安装缓存的 manifest SHA-256 同为 `6095433306daa22c6dcc8a6052843622831979b783ca8a757893402c7df3c217`。

## CapabilityGap

`CAP-2026-08-11-01`：OpenAI 官方 Presentations 已真实安装，但当前 Codex 任务创建于安装之前，尚未加载该插件的 bundled skill。AI PPT Studio runtime preflight 返回 `presentations=true` 只证明运行时合同声明存在，不能替代 PPTX 的真实创建、编辑、渲染和检查能力。

OpenAI 官方文档明确说明：插件安装后应启动新 chat，bundled skills 才会在新的 chat 或 CLI session 中可用。当前缺口因此从“插件未安装”收敛为“等待安装后的新任务加载”，但在新任务真实出现 Presentations 能力之前，G2 仍保持 `open`。

因此本轮明确停止以下动作：

- 不使用 PptxGenJS、python-pptx、LibreOffice、PowerPoint/WPS 脚本或自建编译器替代 Codex Presentations；
- 不创建原生锚点 PPTX；
- 不提交 `native-anchor-set`；
- 不制造 G2 审美、工程或四端同哈希证据；
- 不把开发渲染、浏览器渲染、历史实验或文件哈希冒充桌面应用实机证据。

结构化记录见 [`2026-08-11-codex-presentations-capability-gap.json`](../../requirements/evidence/2026-08-11-codex-presentations-capability-gap.json)。

## 必须在新任务复验的宿主证据

- 360–480px 真实 Codex compact Widget 截图；
- 真实视觉专业审阅资源截图；
- 同一项目 revision、Gate、制品身份在聊天、Widget 和专业审阅三处一致；
- 真正的 Codex Presentations 调用入口可用。

原型 06 只代表内容/视觉专业审阅表面，不代表 compact Widget。源码和缓存哈希一致不能替代真实宿主截图。

## 恢复条件

在安装完成后新建的 Codex 任务中恢复项目 revision 41。先核验 Presentations bundled skill 已真实加载，再按严格路线 B 创建 S02、S05、S10 三页原生锚点；之后对同一 PPTX SHA-256 取得 macOS PowerPoint、macOS WPS、Windows 11 PowerPoint 和 Windows 11 WPS 四份真实桌面证据。任何一端缺失或失败时，G2/G4 均保持阻断。
