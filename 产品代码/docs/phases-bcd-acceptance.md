# AI PPT Studio Codex 原生工作台｜Phase B–D 验收记录

状态：已实现、已验收、已安装、已启用  
源码版本：`0.4.0`  
本地安装版本：`0.4.0+codex.20260802180158`  
验收日期：2026-08-03

## 1. 验收范围

本轮把 Phase A 的“项目总览”扩展为完整的五个稳定认知空间，并将页面、Agent 任务、版本化产物和 G0–G4 质量门连接到同一个项目真源：

1. 项目总览：呈现目标、听众、事实、推论、决定、风险、成果和当前主任务。
2. 材料工作台：接收用户提供的文件、目录、文本、图片与链接，由 AI 自动分类并提炼事实、案例和可用视觉素材。
3. 内容蓝图：先确认章节与逐页内容，再进入视觉设计；每页包含目标、主张、可见文字、来源与素材引用。
4. 视觉设计：比较视觉方向，生成 Visual Brief、工程样张和逐页 Scene Graph；样张审美与可编辑实现联合验收。
5. 制作与交付：使用 Codex Presentations 生成原生可编辑 PPTX，逐页渲染、检查并完成最终验收。

## 2. 已实现的治理机制

- 项目目录是唯一业务真源，Widget 不以 `localStorage` 保存业务状态。
- 所有写入携带 `expectedRevision`；陈旧请求返回 `REVISION_CONFLICT`，不会静默覆盖新状态。
- Agent 任务保存不可变的请求、编译上下文和结果证据；Agent 不能绕过工作台直接宣称阶段完成。
- 上下文编译器只暴露任务需要的结构化信息与受控资产引用，不把全部材料正文无限注入上下文。
- G0–G4 各自校验所需证据；确认、否决、重开范围和回滚都有事件记录。
- 视觉实现坚持“原生可编辑优先”：业务文字、数字、图表、表格和关系图保持可编辑，不允许整页位图冒充 PPT。
- AI 不主动搜索客户项目资料，只使用用户提供的材料与链接。

## 3. MCP 与 Widget 契约

原生工作台现提供九个 MCP 工具：

- `get_ai_ppt_project_snapshot`
- `render_ai_ppt_workbench`
- `read_ai_ppt_project_asset`
- `add_ai_ppt_material`
- `request_ai_ppt_agent_action`
- `commit_ai_ppt_artifact`
- `submit_ai_ppt_human_decision`
- `confirm_ai_ppt_gate`
- `reopen_ai_ppt_scope`

同一份 Widget 支持紧凑侧栏和完整宽屏；页面通过 MCP 读取快照、资产与证据，并把用户选择回写到同一项目状态。

## 4. 端到端验收项目

- 独立验收项目：`/Users/defei/Documents/AI-PPT-Workspace/projects/ai-ppt-studio-bcd-端到端验收-1785693698857-c5ad4fea`
- 真实参考项目（只读复验）：`/Users/defei/Documents/AI-PPT-Workspace/projects/ai-ppt-studio-智慧园区冒烟项目-c8a82730`
- 真实可编辑 PPTX：`/Users/defei/Documents/AI-PPT-Workspace/projects/ai-ppt-studio-智慧园区冒烟项目-c8a82730/ppt/智慧园区运营中台解决方案-可编辑演示.pptx`
- 机器可读验收结果：`output/acceptance/bcd-acceptance.json`

端到端脚本通过真实 MCP stdio 顺序完成 25 次受版本治理的操作：材料上传与分类、Agent 任务、产物提交、人工判断、G0–G4 确认和最终交付。最终状态为：

| 项目 | 验收结果 |
|---|---|
| revision | `25` |
| G0–G4 | 全部 `passed` |
| 材料 | 3 个来源，3 个提炼结果 |
| 内容蓝图 | 6 页 |
| 视觉设计 | 2 个方向，2 个工程样张，6 个 Scene Graph |
| PPTX | 原生可编辑，6 页渲染，QA 通过 |
| 整页位图 | `false` |

## 5. 自动化与视觉验收

- Node/MCP/包结构测试：10 个通过。
- React Widget 行为测试：17 个通过。
- Python 运行时与 Skill 工作流测试：60 个通过。
- 官方 Skill 快速校验与插件校验器：通过。
- 真实 stdio MCP 探针：九个工具均可发现，Widget 返回 MCP App HTML。
- PPTX ZIP 结构、逐页溢出检测和真实渲染：通过。
- 360、420、480、1440 像素视口：无横向溢出。
- 浏览器控制台：0 个错误、0 个警告。
- 五个认知空间均已完成人工视觉检查。

视觉证据：

- `output/playwright/bcd-accepted-overview-1440.png`
- `output/playwright/bcd-accepted-materials-1440.png`
- `output/playwright/bcd-accepted-blueprint-1440.png`
- `output/playwright/bcd-accepted-visual-1440.png`
- `output/playwright/bcd-accepted-delivery-1440.png`

## 6. 使用边界

- 本轮交付的是 Codex 原生个人工作台，不建设独立 Web 产品，也不修改平行的 Web 产品空间。
- 安装或更新插件后，需要新建 Codex 任务才能加载新的 MCP 工具定义；项目状态不会因此丢失。
- 视觉构想仍由 GPT 与 Image 2 协作产生；最终 PPTX 的读取、创建、编辑、渲染和检查只走 Codex Presentations。
- 项目反馈会被记录，但单次反馈不会自动升级为稳定通用规则。

## 7. 最终验收门

以下命令已在当前源码和实际安装插件上全部重新通过：

```text
npm run build
npm run test:node
npm run test:widget
python3 -m unittest discover -s tests -p 'test_*.py'
python3 /Users/defei/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ai-ppt-studio
python3 /Users/defei/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
npm run probe:mcp
npm run accept:bcd
```
