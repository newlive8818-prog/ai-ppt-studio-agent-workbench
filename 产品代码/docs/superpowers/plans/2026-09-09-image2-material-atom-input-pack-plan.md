# Image 2 原子材料输入层设计与实施准备

> **For agentic workers:** REQUIRED SUB-SKILL: 在具体 Change 获得执行授权后使用 `superpowers:executing-plans`。本计划属于 C2 正式三页锚点闭环的材料输入切片；不得把计划、单元测试或 C1 样本证据称为生产能力或用户验收。

**状态：** 用户已确认复用方向并明确要求执行、派发独立任务；本文件是完整 C2 的内部切片准备稿，不是已冻结的 schema 或生产进度账本。实际派发和最新授权见 [C2 交接](../../validation/c2-dispatch/README.md)。上一轮误写于总控的代码已经从源码目录移出并完整保全，见 [草稿保全与接管要求](../../validation/c2-material-input-preparation/README.md)。下列工作均由独立 C2 owner 完善和验证；总控负责基线、协调与核验。

**Goal:** 复用现有 `MaterialInventory`、`PresalesEvidenceBook`、`ReadingDeckBlueprint.material_views` 和视觉资产计划，为 Image 2 建立可追溯、受授权、可拒绝错误素材的 `MaterialAtom` 与 `VisualInputPack` 输入合同。

**Architecture:** 不新增平行素材库。`MaterialAtom` 是现有材料源、证据和页面素材的派生输入对象，必须引用现有 source/artifact 身份；`VisualInputPack` 把当前页已确认文案、本页目标、共同规范、可用原子、排除原子和授权范围组合成 Image 2 唯一输入。Image 2 只消费该输入包；用户定版后继续由既有 `TargetBinding` 绑定定版图、文案、材料角色和已接受差异，原生转换不回写或替换原子。

**Tech Stack:** Python Runtime、现有领域合同与 `ArtifactReference`、Python `unittest`。本切片不引入第二套 PPTX 编辑器，不修改内容审核 UI，不改变 Image 2 服务供应商或外发凭据路径。

---

## 1. 合同边界和复用关系

**Files:**
- Reference: `产品代码/src/ai_ppt_studio/domains/materials/contracts.py`（只复用现有来源校验，不把 Image 2 字段塞入 `MaterialInventory`）
- Create: `产品代码/src/ai_ppt_studio/domains/materials/image_input_contracts.py`
- Create: `产品代码/tests/test_image_input_contracts.py`
- Reference: `产品代码/src/ai_ppt_studio/domains/content/contracts.py`
- Reference: `产品代码/src/ai_ppt_studio/domains/visual/contracts.py`

- [ ] **Step 1: 写出失败测试，锁定原子材料的最小闭合合同。**

测试必须覆盖以下可观察行为：

- 来源身份缺失、实际内容 hash 不匹配、外部地址冒充制品时拒绝；
- 未登记、跨项目、过期材料被引用时拒绝；
- 已排除素材改 atom ID 后仍拒绝；
- 文案逐字保留，包括换行及首尾空白；
- 合法风格参考可用，但不得越权成为真实证据；
- 不同页面保留各自目标及材料角色，不要求预设布局。

这些是行为要求，具体可执行测试与接口由独立 C2 owner 在实际派生基线上冻结。

原子类型至少覆盖 `text | image | logo | table | relation | background`；用途至少区分 `content-source | real-material | style-reference | forbidden`。测试必须证明 `style-reference` 不能自动变成 `real-material`，`forbidden` 不能进入可用列表。

- [ ] **Step 2: 运行 RED 测试，确认失败原因来自缺少 Image 2 输入合同。**

Run from `产品代码/`:

```bash
PYTHONPATH=src python3 -m unittest tests/test_image_input_contracts.py -v
```

Expected: 测试执行到行为断言并失败，例如伪造来源被接受、已确认文案被改变或排除素材仍进入请求。模块缺失只证明尚未实现，不得充当行为 RED；环境导入错误须先修复。

- [ ] **Step 3: 实现最小 `MaterialAtom` 校验。**

实现只负责派生输入校验，不写入新的事实源。每个原子必须包含：

```text
atom_id
source_ref
source_sha256
source_location
atom_type
semantic_role
factual_status
visual_role
allowed_use
content_hash
```

`source_ref` 必须引用现有材料或证据身份；`source_sha256` 和 `content_hash` 必须是小写 SHA-256；`source_location` 必须非空；`allowed_use` 必须显式枚举；原子 ID 在一个输入包内唯一。不得按文件名、目录顺序或相似度补全来源。

- [ ] **Step 4: 实现最小 `VisualInputPack` 校验。**

输入包必须包含：

```text
project_id
slide_id
page_order
confirmed_visible_copy
page_goal
common_deck_rules
available_atoms
excluded_atoms
authorization_scope
source_version
```

校验规则：可用原子必须来自已登记材料；可用与排除集合不得交叉；`forbidden` 原子不得进入可用集合；包内页身份和来源版本必须非空；包不得携带旧 `frozen_copy` 作为替代文案；包不声明三栏、卡片数、图片位置或其他预设布局。

- [ ] **Step 5: 运行 GREEN 测试。**

```bash
PYTHONPATH=src python3 -m unittest tests/test_image_input_contracts.py -v
```

Expected: all focused tests pass，且测试能证明不同页面可以使用不同材料角色而不被同一布局约束。

## 2. 接入现有材料和视觉边界

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/domains/materials/__init__.py`
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/visual/contracts.py`
- Test: `产品代码/tests/test_image_input_contracts.py`
- Test: `产品代码/tests/test_v23_visual_compilation.py`

- [ ] **Step 1: 写出来源桥接 RED 测试。**

测试现有 `MaterialInventory`、证据行和 `material_views[]` 能生成原子引用，但不能把审核投影字段误当成完整 Image 2 输入；缺少授权范围、排除关系或来源 hash 时必须失败。测试还要证明 `VisualCompilationPlan.asset_plan` 继续消费视觉合同中的资产角色，不直接从目录扫描素材。

- [ ] **Step 2: 运行 RED 测试并确认缺少正式桥接。**

```bash
PYTHONPATH=src python3 -m unittest tests/test_image_input_contracts.py tests/test_v23_visual_compilation.py -v
```

- [ ] **Step 3: 实现只读桥接。**

从当前材料和内容制品读取来源，不复制或改写事实。桥接应把：

```text
MaterialInventory.source → source identity
EvidenceBook row → text/relation atom
material_views[] → image/table atom
visual asset_roles → downstream visual role
```

桥接必须保留排除材料，不能因为页面当前没有 `material_views` 就自动判定证据不足，也不能自动为 Image 2 增加一张图片。

- [ ] **Step 4: 运行 focused GREEN 和既有视觉合同回归。**

```bash
PYTHONPATH=src python3 -m unittest tests/test_image_input_contracts.py tests/test_v23_visual_compilation.py -v
```

## 3. Image 2 请求边界和定版绑定

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Modify: `产品代码/src/ai_ppt_studio/application/visual_service.py`
- Create: `产品代码/tests/test_image2_input_boundary.py`
- Reference: `产品代码/src/ai_ppt_studio/application/artifact_guards.py`

- [ ] **Step 1: 写出请求边界 RED 测试。**

至少加入以下负例：错页图片、同目录相似图片、未授权图片、过期 source hash、排除原子、缺少本页目标、缺少共同规范、空的可见文案、将整页旧 PPT 背景标成 `style-reference` 后越权作为 `real-material` 使用。每个失败必须发生在外部请求或 PPTX 写入前，并且不得产生业务状态、事件或输出制品。

- [ ] **Step 2: 运行 RED。**

```bash
PYTHONPATH=src python3 -m unittest tests/test_image2_input_boundary.py -v
```

- [ ] **Step 3: 接入 Image 2 输入包。**

请求编译器只能从 `VisualInputPack` 生成请求；它不得扫描目录、回取旧请求、按文件名挑选图片或从旧 frozen 文案恢复内容。已授权的重复使用沿用同一授权范围，不为同一持续有效绑定重复创建授权动作；新增材料或外发范围变化必须形成新绑定。

- [ ] **Step 4: 在定版记录中复用唯一 `TargetBinding`。**

请求返回后，定版记录只追加 `target_image_sha256`、`selected_copy_sha256`、`material_roles` 和 `accepted_deviations` 到既有身份链；不建立第二套“原子定版”权威。区域映射和材料角色缺失时拒绝进入原生构建。

- [ ] **Step 5: 运行 GREEN。**

```bash
PYTHONPATH=src python3 -m unittest tests/test_image2_input_boundary.py -v
```

## 4. 材料切片验证与 C2 总体验收的关系

- [ ] **Step 1: 运行材料和视觉相关 Python 回归。**

```bash
PYTHONPATH=src python3 -m unittest \
  tests/test_image_input_contracts.py \
  tests/test_image2_input_boundary.py \
  tests/test_v22_content_contracts.py \
  tests/test_v23_visual_semantic_contracts.py \
  tests/test_v23_visual_compilation.py -v
```

- [ ] **Step 2: 验证反例没有写入。**

对每个拒绝用例检查 Runtime revision、事件、artifact heads 和外部请求记录均未改变；失败输出如有生成必须保留为失败制品，不能覆盖已验收输出。

- [ ] **Step 3: 对三页真实样本做输入包审计。**

审计 C1 三页：每个客户事实、两张真实图片、排除材料、共同规范和页面目标都能回到来源；不得把 C1 的手工清单直接称为通用自动选择能力。

- [ ] **Step 4: 完成独立 Review 后再决定是否进入正式 C2 生产闭环。**

本切片的验收条件是：现有材料源和证据合同继续通过；Image 2 输入包闭合；负例在写入前拒绝；定版绑定沿用唯一 `TargetBinding`；三页输入审计通过。没有这些证据时，状态保持未完成，并按实际失败原因记录具体缺口，不声称 Image 2 原子材料层已生产完成。

本切片完成不等于 C2 退出。完整 C2 仍需按主计划验证正式三页、G2/G3、独立 Review，再由总控核验具体候选并按授权合并；合并后重新运行组合验证。
