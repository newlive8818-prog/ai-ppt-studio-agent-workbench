# AI PPT Studio Codex 原生工作台｜Phase A 验收记录

状态：已实现、已安装、已启用  
插件版本：`0.3.1`  
验收日期：2026-08-02

## 已交付

- Codex 个人插件 `ai-ppt-studio@personal`，安装根目录为 `/Users/defei/plugins/ai-ppt-studio`。
- 原生 MCP App Widget：同一份页面适配 Codex 紧凑侧栏与完整宽屏。
- 三个 MCP 工具：读取项目快照、提交人工判断、打开原生工作台。
- 项目目录是唯一业务真源；页面不使用 `localStorage` 保存业务状态。
- 人工判断采用 revision 乐观锁，成功写入后追加不可变决定和事件；旧 revision 返回 `REVISION_CONFLICT`。
- 页面先保存决定，再尝试更新 Agent 上下文并继续 Codex 对话；宿主能力缺失时明确提示“已保存，待对话”。

## 当前可用范围

Phase A 已真实接通“项目总览”：交付目标、听众、问题、事实、AI 推论、已确认决定、不确定性、成果状态、质量门、产物和一个当前判断。

材料工作台、内容蓝图、视觉设计、制作与交付保留为稳定认知空间，但当前明确显示 Phase B–D 尚未接通，不伪造数据。

## 如何使用

安装完成后，新建一个 Codex 任务并输入：

> 打开 AI PPT Studio 原生工作台，继续我最近的项目。

也可以输入：

> 查看当前 AI PPT 项目的认知地图和最需要我判断的问题。

已打开的旧任务通常不会热加载新安装的 MCP 工具；新建任务即可加载。这不影响项目数据，所有状态仍保存在 `/Users/defei/Documents/AI-PPT-Workspace`。

## 验收证据

- Python：47 个测试通过。
- Node/MCP/包结构：8 个测试通过。
- React Widget：4 个行为测试通过。
- 官方插件校验器：通过。
- 真实 stdio MCP：3 个工具可用；Widget MIME 为 `text/html;profile=mcp-app`。
- 双向回写：验收项目 revision `0 → 1`；旧 revision 写入返回 `REVISION_CONFLICT`。
- 响应式：360、420、480、1440 像素宽度均无横向溢出。
- 浏览器：0 个控制台错误，紧凑和完整形态均已人工查看。

本地视觉证据位于 `output/playwright/`，机器可读结果见 `phase-a-acceptance-report.json`。
