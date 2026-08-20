# Content Review Optional Material Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许三种材料模式中的任意内容页合法地没有图片，并让活动内容审核前端在零图片页完全省略图片区域、将“页面实际文字”扩展到整行，同时保持证据治理、图片资源安全、PageDecision 和已验收有图布局不变。

**Architecture:** 以已验收前端为需求源，先放宽内部 `ReadingDeckBlueprint` 对单页 `material_views` 数量的错误约束，再用既有窄投影和 ViewModel 原样传递空数组。活动 React 表面仅以 `materialVisuals.length` 派生布局，不增加第二个布尔字段；Review Bridge 继续只对白名单中的非空 `asset_ref` 提供资源读取。实现证据分为合同测试、投影/安全回归、React DOM/资源读取测试、多视口与长稿本地验收，均不升级为真实宿主、AI 回执或 G0 证据。

**Tech Stack:** Python 3 `unittest`、Python Runtime contracts/services、TypeScript 5、React 19、Vitest + Testing Library、Node.js test runner、CSS Grid、Playwright 本地验收脚本、Git。

---

## 实施边界与工作区保护

- 实施工作区固定为 `/private/tmp/ai-ppt-v22-TmBomR`，分支固定为 `codex/review-surface-v22`；不得新建第二个 worktree。
- 当前 `git status --short` 中的 ` D AGENTS.md` 是既存、用户所有的无关改动。任何任务都不得恢复、暂存、删除、修改或提交它。
- 每次提交前只能对任务列出的精确路径执行 `git add`；禁止 `git add .` 和 `git add -A`。
- 不修改 PPT 运行数据 `/Users/defei/Documents/AI-PPT-Workspace`，不触碰并行 Web 产品空间。
- 不启动视觉审核 Slice F2，不修改视觉审核投影、视觉合同或锚点反馈。
- 不新增 `has_image`、`empty_reason` 或其他重复状态字段。布局真值只来自 `materialVisuals.length`。
- 不定义多图片最大数量、主图/辅图、排序、分组、网格、轮播或自动选择规则；有几条合法 `material_views` 就按当前稳定顺序渲染几条。
- 不用装饰图、网络图、无关截图、Image 2 或 AI 生成图片填充零图片页。
- 不改变 `evidence_bindings` 要求，不降低单条 `material_view` 的闭合字段、安全相对路径、页码、来源身份或 Review Bridge 白名单校验。
- 不重开已经通过的内容审核前端整体验收；本计划只实现 2026-08-20 新确认的零图片增量。

## 文件职责映射

| 文件 | 本切片职责 |
|---|---|
| `src/ai_ppt_studio/domains/content/contracts.py` | 删除“非 proposal 页每页至少一张图”的数量强制，保留证据绑定和单条画面验证 |
| `tests/test_v22_content_contracts.py` | 锁定三种材料模式都允许空数组，并锁定非 proposal 页仍需 evidence bindings |
| `tests/test_v22_content_repair_loop.py` | 为集成测试生成可指定零图片页的真实 ReadingDeckBlueprint fixture |
| `tests/test_v22_content_review_projection.py` | 证明同一审核投影可同时包含有图页和零图片页，且单条外部字段仍收窄 |
| `mcp/review-bridge.mjs` | 不改生产逻辑；既有逻辑应继续只收集实际存在的 `asset_ref` |
| `tests/review-bridge.test.mjs` | 锁定零图片页不扩大资源白名单、不触发项目资源读取 |
| `widget/src/content-review/content-review-page-view-model.test.tsx` | 锁定 adapter 把空 `material_views` 正常映射为空 `materialVisuals` |
| `widget/src/content-review/ContentReviewViewModelSurface.tsx` | 以数组长度派生有图/纯文字布局，并在零图片页完全省略图片组件 |
| `widget/src/content-review/ContentReviewMaterialVisuals.tsx` | 对空数组返回 `null`，移除大面积空状态；非空时保留延迟读取和失败恢复 |
| `widget/src/styles/content-review-view-model.css` | 为零图片页提供明确单栏 class，保留有图页宽屏双栏与窄屏单栏 |
| `widget/src/content-review/ContentReviewViewModelSurface.test.tsx` | 验证混合稿 DOM、可访问性、PageDecision、正文和资源读取隔离 |
| `widget/src/ReviewSurfaceRouter.test.tsx` | 从正式活动路由证明零图片投影不会恢复图片标题或旧后台模块 |
| `scripts/run-v22-ui-acceptance.mjs` | 在 5 个视口和 10/24/60 页混合长稿中验证布局、溢出和延迟读取 |
| `tests/v22-prototype-fidelity.test.mjs` | 锁定验收脚本确实覆盖混合稿与三个内容长稿长度 |
| 四份唯一基线与本设计规格 | 实现完成后只更新本地工程状态，不扩大真实能力或 Gate 结论 |

### Task 1: 放宽 ReadingDeckBlueprint 的单页图片数量合同

**Files:**
- Modify: `tests/test_v22_content_contracts.py:272-297`
- Modify: `src/ai_ppt_studio/domains/content/contracts.py:490-500`

- [ ] **Step 1: 把旧“每页必须有图”测试改为三种模式均允许空数组，并增加 evidence bindings 回归**

用以下两个测试替换当前 `test_material_modes_require_closed_material_views_and_preserve_them`；闭合字段测试继续留在同一个测试中，因此放宽数量不会绕过 `_material_view()`：

```python
    def test_all_material_modes_allow_empty_material_views_and_preserve_closed_views(self) -> None:
        expected = material_view()
        for mode in ("material-backed", "mixed-evidence", "proposal-led"):
            with self.subTest(mode=mode, material_views="empty"):
                without_views = blueprint(mode)
                without_views["slides"][0]["material_views"] = []
                validated = validate_reading_deck_blueprint(without_views)
                self.assertEqual(validated["slides"][0]["material_views"], [])

        for mode in ("material-backed", "mixed-evidence"):
            with self.subTest(mode=mode, material_views="present"):
                validated = validate_reading_deck_blueprint(blueprint(mode))
                self.assertEqual(validated["slides"][0]["material_views"], [expected])

        for field in expected:
            with self.subTest(missing_field=field):
                invalid = blueprint()
                del invalid["slides"][0]["material_views"][0][field]
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)

        invalid = blueprint()
        invalid["slides"][0]["material_views"][0]["unexpected"] = "not closed"
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(invalid)

    def test_material_modes_still_require_evidence_bindings_when_views_are_empty(self) -> None:
        for mode in ("material-backed", "mixed-evidence"):
            with self.subTest(mode=mode):
                invalid = blueprint(mode)
                invalid["slides"][0]["material_views"] = []
                invalid["slides"][0]["evidence_bindings"] = []
                with self.assertRaisesRegex(
                    ContractValidationError,
                    rf"{mode} slides require evidence bindings",
                ):
                    validate_reading_deck_blueprint(invalid)
```

- [ ] **Step 2: 运行新合同测试，确认它因旧数量强制失败**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v tests.test_v22_content_contracts.V22ContentContractTests.test_all_material_modes_allow_empty_material_views_and_preserve_closed_views
```

Expected: `FAIL` 或 `ERROR`，异常包含 `material-backed slides require material views` 或 `mixed-evidence slides require material views`。失败必须来自待删除的数量强制，而不是 fixture 字段缺失。

- [ ] **Step 3: 只删除非 proposal 页的 material_views 非空判断**

在 `validate_reading_deck_blueprint()` 中把模式分支改成下面的精确结构；不要修改 `_material_view()`、`_v22_objects()` 或 `evidence_bindings` 逻辑：

```python
        if mode == "proposal-led":
            required = {"诊断假设", "方案建议", "待联合验证"}
            if not required.issubset(slide["identity_labels"]):
                raise ContractValidationError("proposal-led slides require hypothesis, recommendation, and validation identities")
            if slide["evidence_bindings"]:
                raise ContractValidationError("proposal-led slides cannot cite project evidence")
        elif not slide["evidence_bindings"]:
            raise ContractValidationError(f"{mode} slides require evidence bindings")
```

`material_views` 仍由下列既有代码逐条验证和原序保留，不能删除或绕开：

```python
        material_views = [
            _material_view(material_view)
            for material_view in _v22_objects(row, "material_views")
        ]
```

- [ ] **Step 4: 运行合同测试，确认空数组与安全校验同时通过**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v tests.test_v22_content_contracts
```

Expected: `Ran ... tests` 后为 `OK`。其中三种模式空数组测试、evidence bindings 测试、闭合字段测试、`asset_ref` 安全路径测试、正整数页码测试和 evidence identity 测试全部通过。

- [ ] **Step 5: 检查并提交合同切片**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git status --short
git diff -- 产品代码/src/ai_ppt_studio/domains/content/contracts.py 产品代码/tests/test_v22_content_contracts.py
git add 产品代码/src/ai_ppt_studio/domains/content/contracts.py 产品代码/tests/test_v22_content_contracts.py
git commit -m "fix: allow zero-image content slides"
```

Expected: 提交只包含上述两个文件；`AGENTS.md` 仍显示为未暂存的 ` D AGENTS.md`。

### Task 2: 锁定空数组投影与 Review Bridge 资源边界

**Files:**
- Modify: `tests/test_v22_content_repair_loop.py:21-87`
- Modify: `tests/test_v22_content_review_projection.py:71-176`
- Modify: `tests/review-bridge.test.mjs:173-214,326-370`
- Verify unchanged: `src/ai_ppt_studio/application/content_review/projection_service.py:22-52`
- Verify unchanged: `mcp/review-bridge.mjs:109-128,753-904`

- [ ] **Step 1: 让真实内容 fixture 可按页生成空 material_views**

把 `build_content()` 签名改为：

```python
def build_content(
    kernel: ProjectKernel,
    source_version: str = "content-v1",
    slide_count: int = 1,
    empty_material_view_orders: frozenset[int] = frozenset(),
) -> str:
```

把循环中的 `material_views` 赋值替换为：

```python
            material_views=(
                []
                if order in empty_material_view_orders
                else [
                    {
                        **material,
                        "material_view_id": f"S{order:02d}-M{index:02d}",
                        "asset_ref": f"review-assets/content/S{order:02d}-M{index:02d}.png",
                        "page_number": material["page_number"] + order - 1,
                        "purpose": (
                            material["purpose"]
                            if slide_count == 1
                            else f"{material['purpose']}（S{order:02d}）"
                        ),
                    }
                    for index, material in enumerate(
                        template["material_views"], start=1
                    )
                ]
            ),
```

默认值是不可变 `frozenset()`，所以现有调用保持原行为。

- [ ] **Step 2: 让内容审核集成 fixture 把空图片页传入真实制品链**

把 `accepted_review()` 的签名和第一条调用改为：

```python
def accepted_review(
    kernel: ProjectKernel,
    slide_count: int = 1,
    empty_material_view_orders: frozenset[int] = frozenset(),
):
    blueprint_ref = build_content(
        kernel,
        slide_count=slide_count,
        empty_material_view_orders=empty_material_view_orders,
    )
```

其余硬门、ReviewSession 和返回值代码保持不变。

- [ ] **Step 3: 增加有图/无图混合投影测试**

在 `ContentReviewProjectionTests` 中增加：

```python
    def test_projection_preserves_mixed_empty_and_non_empty_material_views(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_review(
                kernel,
                slide_count=2,
                empty_material_view_orders=frozenset({2}),
            )

            projection = ContentReviewProjectionService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                projection["slides"][0]["material_views"],
                [{
                    "material_view_id": "S01-M01",
                    "asset_ref": "review-assets/content/S01-M01.png",
                }],
            )
            self.assertEqual(projection["slides"][1]["material_views"], [])
            self.assertEqual(
                [slide["slide_id"] for slide in projection["slides"]],
                ["S01", "S02"],
            )
            self.assertEqual(
                set(projection["slides"][0]["material_views"][0]),
                CONTENT_REVIEW_MATERIAL_FIELDS,
            )
            self.assertTrue(
                CONTENT_REVIEW_FORBIDDEN_FIELDS.isdisjoint(nested_keys(projection))
            )
```

- [ ] **Step 4: 运行真实投影测试**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v tests.test_v22_content_review_projection.ContentReviewProjectionTests.test_projection_preserves_mixed_empty_and_non_empty_material_views
```

Expected: `OK`。这一步验证 Task 1 的合同放宽能够穿过真实制品、硬门、ReviewSession 和窄投影；不需要修改 `projection_service.py`。

- [ ] **Step 5: 增加 Review Bridge 空页白名单回归**

在 `tests/review-bridge.test.mjs` 的内容材料资源测试后增加：

```javascript
test("Review Bridge keeps zero-image content pages out of the asset allowlist", async () => {
  const allowedRef = "review-assets/content/S01-M01.png";
  const absentRef = "review-assets/content/S02-M01.png";
  const reads = [];
  const { bridge, session } = await startedBridge({
    review: {
      ...review,
      slides: [{
        ...review.slides[0],
        material_views: [{ material_view_id: "S01-M01", asset_ref: allowedRef }],
      }, {
        ...review.slides[0],
        slide_id: "S02",
        order: 2,
        material_views: [],
      }],
    },
    readProjectAsset: ({ projectRoot, assetRef }) => {
      reads.push({ projectRoot, assetRef });
      return {
        assetRef,
        mimeType: "image/png",
        bytes: 3,
        dataBase64: "YWJj",
      };
    },
  });
  try {
    await fetch(`${session.origin}/api/review`, { headers: bearer(session) });

    const allowed = await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(allowedRef)}`,
      { headers: bearer(session) },
    );
    const absent = await fetch(
      `${session.origin}/api/asset?assetRef=${encodeURIComponent(absentRef)}`,
      { headers: bearer(session) },
    );

    assert.equal(allowed.status, 200);
    assert.equal(absent.status, 404);
    assert.deepEqual(reads, [{
      projectRoot: "/managed/project",
      assetRef: allowedRef,
    }]);
  } finally {
    await bridge.stop();
  }
});
```

同时在 `collectProjectionAssetRefs` fixture 的 `slides` 中加入第二页：

```javascript
    }, {
      slide_id: "S02",
      material_views: [],
```

期望集合仍只有显式非空内容图片和三个视觉锚点引用，不新增任何零图片页引用。

- [ ] **Step 6: 运行投影与 Bridge 回归**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v tests.test_v22_content_repair_loop tests.test_v22_content_review_projection
node --test --test-name-pattern="collectProjectionAssetRefs|content material assets|zero-image content pages" tests/review-bridge.test.mjs
```

Expected: 两条命令均退出码 `0`。Bridge 新测试的 `readProjectAsset` 只调用一次，空页候选引用得到 `404`。

- [ ] **Step 7: 检查并提交投影安全回归**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git status --short
git diff -- 产品代码/tests/test_v22_content_repair_loop.py 产品代码/tests/test_v22_content_review_projection.py 产品代码/tests/review-bridge.test.mjs
git add 产品代码/tests/test_v22_content_repair_loop.py 产品代码/tests/test_v22_content_review_projection.py 产品代码/tests/review-bridge.test.mjs
git commit -m "test: lock optional material projection security"
```

Expected: `projection_service.py` 和 `review-bridge.mjs` 无生产改动；提交只包含三个测试/fixture 文件。

### Task 3: 锁定 ContentReviewPageViewModel 的空数组语义

**Files:**
- Modify: `widget/src/content-review/content-review-page-view-model.test.tsx:66-137`
- Verify unchanged: `widget/src/content-review/content-review-page-view-model.ts:119-171`

- [ ] **Step 1: 增加空 material_views adapter 回归测试**

在现有 ViewModel 测试中增加：

```typescript
it("maps empty material views to normal zero-image ViewModel state", () => {
  const input = projection();
  input.slides[0].material_views = [];

  const viewModel = toContentReviewPageViewModel(input);

  expect(viewModel.slides[0].materialVisuals).toEqual([]);
  expect(viewModel.slides[0]).toMatchObject({
    pageGoal: "确认当前流程断点及证据边界",
    customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
    readingQuestion: "现有材料能否支撑当前判断？",
    draftContent: {
      title: "当前流程断点与证据边界",
      blocks: [{
        blockId: "copy-1",
        type: "paragraph",
        text: "当前流程存在三个待核实断点。",
      }],
    },
  });
});
```

- [ ] **Step 2: 运行 adapter 测试，确认既有实现已满足合同**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
npm run test:widget -- widget/src/content-review/content-review-page-view-model.test.tsx
```

Expected: `PASS`。这是对既有正确 adapter 行为的回归锁定；不要为此增加 adapter error、CapabilityGap 或 `hasImage` 字段。

- [ ] **Step 3: 提交 ViewModel 回归测试**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git add 产品代码/widget/src/content-review/content-review-page-view-model.test.tsx
git commit -m "test: preserve empty content material view models"
```

Expected: 仅提交一个测试文件；`content-review-page-view-model.ts` 保持不变。

### Task 4: 在活动 React 表面实现零图片单栏与 DOM 省略

**Files:**
- Modify: `widget/src/content-review/ContentReviewViewModelSurface.test.tsx:126-165,226-254`
- Modify: `widget/src/ReviewSurfaceRouter.test.tsx:231-272`
- Modify: `widget/src/content-review/ContentReviewViewModelSurface.tsx:167-218`
- Modify: `widget/src/content-review/ContentReviewMaterialVisuals.tsx:81-111`
- Modify: `widget/src/styles/content-review-view-model.css:51-70,102-105`

- [ ] **Step 1: 先把混合稿 DOM、布局和资源读取要求写成失败测试**

把 `ContentReviewViewModelSurface.test.tsx` 首个测试中图片标题数量改为 `1`，并在现有断言后增加：

```typescript
  expect(screen.getAllByText("文字与图片材料一起审核")).toHaveLength(1);
  expect(screen.queryByText("本页暂无可审核的页面画面。")).not.toBeInTheDocument();

  const firstPage = screen.getByLabelText("S01 内容审核");
  const secondPage = screen.getByLabelText("S02 内容审核");
  expect(within(firstPage).getByRole("region", {
    name: "S01 文字与图片材料一起审核",
  })).toBeInTheDocument();
  expect(within(secondPage).queryByRole("region", {
    name: "S02 文字与图片材料一起审核",
  })).not.toBeInTheDocument();
  expect(within(secondPage).getByRole("region", {
    name: "S02 页面实际文字",
  })).toBeInTheDocument();
  expect(within(secondPage).getByText("本页阅读判断：")).toBeInTheDocument();
  expect(within(secondPage).getAllByRole("radio")).toHaveLength(4);

  const grids = container.querySelectorAll(".content-review-vm-reading-grid");
  expect(grids[0]).toHaveClass("content-review-vm-reading-grid--with-visuals");
  expect(grids[1]).toHaveClass("content-review-vm-reading-grid--text-only");
```

保留现有目标、客户判断、实际文字、章节顺序和已删除后台模块断言。

在延迟读取测试末尾增加：

```typescript
  expect(callTool).toHaveBeenCalledTimes(1);
  expect(screen.queryByLabelText("S02 文字与图片材料一起审核")).not.toBeInTheDocument();
```

再增加一条有图读取失败不改变页面判断的回归：

```typescript
it("keeps PageDecision unchanged when an existing material image fails", async () => {
  const intersections = installIntersectionObserver();
  const initial = pageViewModel();
  const viewModel = {
    ...initial,
    slides: initial.slides.map((slide, index) => index === 0 ? {
      ...slide,
      localDraftState: {
        decision: "modify" as const,
        comment: "保留当前修改判断。",
        dirty: true,
      },
    } : slide),
  } satisfies ContentReviewPageViewModel;
  const callTool = vi.fn(async () => {
    throw new Error("material image unavailable");
  });
  render(
    <ContentReviewViewModelSurface
      viewModel={viewModel}
      bridge={bridge(callTool)}
      projectRoot="/managed/project"
      {...actionProps()}
    />,
  );

  act(() => intersections.intersectAll());

  const firstPage = screen.getByLabelText("S01 内容审核");
  expect(await within(firstPage).findByRole("button", {
    name: /预览暂不可读，点击重试/,
  })).toBeInTheDocument();
  expect(within(firstPage).getByRole("radio", { name: "需要修改" })).toBeChecked();
  expect(within(firstPage).getByRole("radio", { name: "证据不足" })).not.toBeChecked();
});
```

该测试只观察图片读取失败和既有受控 PageDecision；不要让图片组件调用判断变更回调。

把 `ReviewSurfaceRouter.test.tsx` 的默认 `contentSlide()` 零图片路由断言改为：

```typescript
    expect(screen.queryByText("文字与图片材料一起审核")).not.toBeInTheDocument();
    expect(screen.queryByText("本页暂无可审核的页面画面。")).not.toBeInTheDocument();
    expect(
      container.querySelector(".content-review-vm-reading-grid--text-only"),
    ).toBeInTheDocument();
```

页面目标、客户判断、实际文字、阅读问题、四个 radio 和保存/提交按钮断言继续保留。

- [ ] **Step 2: 运行两个测试文件，确认当前空状态和双栏行为被捕获**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
npm run test:widget -- widget/src/content-review/ContentReviewViewModelSurface.test.tsx widget/src/ReviewSurfaceRouter.test.tsx
```

Expected: `FAIL`，至少包含以下差异：图片栏标题仍有 `2` 个、零图片页仍有 region/空状态、布局缺少 `content-review-vm-reading-grid--text-only`。

- [ ] **Step 3: 在活动表面只根据 materialVisuals.length 派生布局**

在 `slides.map()` 内、`return` 之前增加：

```typescript
                    const hasMaterialVisuals = slide.materialVisuals.length > 0;
                    const readingLayoutClass = hasMaterialVisuals
                      ? "content-review-vm-reading-grid--with-visuals"
                      : "content-review-vm-reading-grid--text-only";
```

把阅读区 opening tag 改为：

```tsx
                        <div className={`content-review-vm-reading-grid ${readingLayoutClass}`}>
```

把无条件图片组件改为：

```tsx
                          {hasMaterialVisuals ? (
                            <ContentReviewMaterialVisuals
                              bridge={bridge}
                              projectRoot={projectRoot}
                              slideId={slide.slideId}
                              visuals={slide.materialVisuals}
                              readsDisabled={readsDisabled}
                            />
                          ) : null}
```

不要改变目标、客户判断、实际文字、阅读问题或 `PageDecisionControl` 的位置和 props。

- [ ] **Step 4: 让图片组件对空数组安全地不产生 DOM**

把 `ContentReviewMaterialVisuals()` 函数体改为：

```tsx
export function ContentReviewMaterialVisuals({
  bridge,
  projectRoot,
  slideId,
  visuals,
  readsDisabled = false,
}: ContentReviewMaterialVisualsProps) {
  if (visuals.length === 0) return null;
  return (
    <section
      className="content-review-vm-visuals"
      aria-label={`${slideId} 文字与图片材料一起审核`}
    >
      <span className="content-review-vm-label">文字与图片材料一起审核</span>
      <div className="content-review-vm-visual-list">
        {visuals.map((visual) => (
          <LazyMaterialVisual
            key={visual.visualId}
            bridge={bridge}
            projectRoot={projectRoot}
            visual={visual}
            readsDisabled={readsDisabled}
          />
        ))}
      </div>
    </section>
  );
}
```

这会彻底删除“本页暂无可审核的页面画面。”分支，但保留每条非空画面的 IntersectionObserver、手动读取 fallback、真实读取失败和重试行为。

- [ ] **Step 5: 增加纯文字单栏 CSS 并删除空状态样式**

在现有 `.content-review-vm-reading-grid` 之后增加：

```css
.content-review-vm-reading-grid--text-only { grid-template-columns: minmax(0, 1fr); }
```

保留现有宽屏双栏定义：

```css
.content-review-vm-reading-grid { display: grid; grid-template-columns: minmax(340px, .9fr) minmax(500px, 1.1fr); gap: 16px; align-items: start; padding: 16px; }
```

保留 `@media (max-width: 860px)` 中有图页回落单栏的现有规则。删除已无调用方的整条 `.content-review-vm-visual-empty` 规则，不新增任何替代空框或补图提示。

- [ ] **Step 6: 运行 React、路由、类型和构建验证**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
npm run test:widget -- widget/src/content-review/ContentReviewViewModelSurface.test.tsx widget/src/ReviewSurfaceRouter.test.tsx
npm run typecheck
npm run build
```

Expected: 三条命令退出码均为 `0`。混合稿只有 S01 产生图片读取；S02 没有图片区 region、标题、空状态或资源调用，但仍有正文、阅读问题、四类判断和保存行为。

- [ ] **Step 7: 检查并提交活动前端增量**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git status --short
git diff -- 产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx 产品代码/widget/src/content-review/ContentReviewMaterialVisuals.tsx 产品代码/widget/src/styles/content-review-view-model.css 产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx 产品代码/widget/src/ReviewSurfaceRouter.test.tsx
git add 产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx 产品代码/widget/src/content-review/ContentReviewMaterialVisuals.tsx 产品代码/widget/src/styles/content-review-view-model.css 产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx 产品代码/widget/src/ReviewSurfaceRouter.test.tsx
git commit -m "feat: collapse zero-image content review pages"
```

Expected: 提交只包含五个前端文件；没有 `ContentMaterialView.tsx` legacy 页面或视觉审核文件。

### Task 5: 扩展多视口与 10/24/60 页混合稿本地验收

**Files:**
- Modify: `tests/v22-prototype-fidelity.test.mjs:135-145`
- Modify: `scripts/run-v22-ui-acceptance.mjs:64-99,140-165,291-410,625-655`

- [ ] **Step 1: 先锁定验收脚本必须包含混合稿和三个内容长稿长度**

在 `tests/v22-prototype-fidelity.test.mjs` 增加：

```javascript
test("browser runner covers mixed image and zero-image content reviews", () => {
  assert.match(runnerSource, /mixedContentProjectionHtml/);
  assert.match(runnerSource, /content-review-vm-reading-grid--text-only/);
  assert.match(runnerSource, /content-review-vm-reading-grid--with-visuals/);
  assert.match(runnerSource, /本页暂无可审核的页面画面/);
  for (const count of [10, 24, 60]) {
    assert.match(runnerSource, new RegExp(`\\["content", ${count}\\]`));
  }
});
```

- [ ] **Step 2: 运行 source-contract 测试，确认当前验收脚本尚未覆盖这些场景**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
node --test --test-name-pattern="mixed image and zero-image" tests/v22-prototype-fidelity.test.mjs
```

Expected: `FAIL`，首先缺少 `mixedContentProjectionHtml` 或纯文字布局 selector。

- [ ] **Step 3: 生成确定性的三页混合预览和交替长稿**

在 `transformPreviewPayload()` 后增加：

```javascript
function mixedContentProjectionHtml(sourceHtml) {
  return transformPreviewPayload(sourceHtml, "mixed content review", (data) => {
    assert(data.review.slides.length >= 2, "Mixed content review needs at least two pages");
    data.review.slides[1].material_views = [];
  });
}
```

在 `longProjectionHtml()` 的 content slide clone 中增加：

```javascript
        material_views: index % 2 === 0
          ? structuredClone(template.material_views)
          : [],
```

两类页面交替出现；不得给空页生成替代图片，也不得改写 PageDecision 或正文。

在两个正式预览生成完成后，把 content 预览转换为混合稿：

```javascript
const contentPreviewPath = previewPath("ai-ppt-content-review-preview.html");
const contentPreviewHtml = await readFile(contentPreviewPath, "utf8");
await writeFile(
  contentPreviewPath,
  mixedContentProjectionHtml(contentPreviewHtml),
  "utf8",
);
```

把长稿生成列表改为：

```javascript
for (const [reviewType, count] of [
  ["content", 10],
  ["content", 24],
  ["content", 60],
  ["visual", 120],
]) {
```

- [ ] **Step 4: 把标准内容验收从“每页必须有图”改为混合布局合同**

用下面的逻辑替换当前 `every content page needs a material image` 到空 placeholder 检查这一段：

```javascript
      const textOnlyGrids = page.locator(".content-review-vm-reading-grid--text-only");
      const visualGrids = page.locator(".content-review-vm-reading-grid--with-visuals");
      const textOnlyPageCount = await textOnlyGrids.count();
      const visualPageCount = await visualGrids.count();
      assert(textOnlyPageCount === 1, `${identity}: expected one zero-image page`);
      assert(
        textOnlyPageCount + visualPageCount === objectCount,
        `${identity}: content layout classes do not cover every page`,
      );
      assert(
        await page.locator(".content-review-vm-visuals").count() === visualPageCount,
        `${identity}: zero-image page rendered a material region`,
      );
      assert(
        await page.getByText("文字与图片材料一起审核", { exact: true }).count()
          === visualPageCount,
        `${identity}: material title count does not match image pages`,
      );
      assert(
        await page.getByText("本页暂无可审核的页面画面。", { exact: true }).count() === 0,
        `${identity}: zero-image empty state returned`,
      );
      const textOnlyGeometry = await textOnlyGrids.first().evaluate((grid) => {
        const text = grid.querySelector(".content-review-vm-text");
        if (!text) throw new Error("Zero-image page is missing actual text");
        const style = getComputedStyle(grid);
        return {
          availableWidth: grid.clientWidth
            - Number.parseFloat(style.paddingLeft)
            - Number.parseFloat(style.paddingRight),
          textWidth: text.getBoundingClientRect().width,
        };
      });
      assert(
        Math.abs(textOnlyGeometry.availableWidth - textOnlyGeometry.textWidth) <= 1,
        `${identity}: zero-image text does not fill the reading row ${JSON.stringify(textOnlyGeometry)}`,
      );

      const materialCards = page.locator(".content-review-vm-image-slot");
      assert(
        await materialCards.count() >= visualPageCount,
        `${identity}: an image page has no material image`,
      );
      for (let index = 0; index < await materialCards.count(); index += 1) {
        const card = materialCards.nth(index);
        await card.scrollIntoViewIfNeeded();
        await card.locator("img.content-review-vm-image").waitFor();
      }
      await assertLoadedImages(page.locator("img.content-review-vm-image"), `${identity} material`);
      const materialSources = await page.locator("img.content-review-vm-image").evaluateAll(
        (images) => images.map((image) => image.currentSrc || image.src),
      );
      materialSourceCount = new Set(materialSources).size;
      assert(
        materialSourceCount >= visualPageCount,
        `${identity}: image pages reuse the same rendered material ${JSON.stringify(materialSources)}`,
      );
      assert(
        await page.locator(".content-review-vm-image-slot .asset-placeholder").count() === 0,
        `${identity}: material placeholder remained after loading`,
      );
```

在 `results.push()` 中加入 `textOnlyPageCount`，仅 content 路径赋值；初始化时使用 `let textOnlyPageCount = 0;`：

```javascript
      ...(textOnlyPageCount ? { textOnlyPageCount } : {}),
```

- [ ] **Step 5: 让长稿验收检查混合布局、无空框、溢出和近视口加载**

在 `checkLongReview()` 的基础计数后、通用 overflow 检查前增加：

```javascript
    if (reviewType === "content") {
      const textOnlyPages = page.locator(".content-review-vm-reading-grid--text-only");
      const visualPages = page.locator(".content-review-vm-reading-grid--with-visuals");
      const textOnlyCount = await textOnlyPages.count();
      const visualCount = await visualPages.count();
      assert(textOnlyCount > 0 && visualCount > 0, `${reviewType}-${count}: mixed layouts missing`);
      assert(
        textOnlyCount + visualCount === count,
        `${reviewType}-${count}: layout count mismatch`,
      );
      assert(
        await page.getByText("文字与图片材料一起审核", { exact: true }).count() === visualCount,
        `${reviewType}-${count}: visual title leaked onto zero-image pages`,
      );
      assert(
        await page.getByText("本页暂无可审核的页面画面。", { exact: true }).count() === 0,
        `${reviewType}-${count}: zero-image empty state returned`,
      );
      const imageSlots = page.locator(".content-review-vm-image-slot");
      const initialLoadedImages = await page.locator("img.content-review-vm-image").count();
      assert(await imageSlots.count() >= visualCount, `${reviewType}-${count}: image page missing slot`);
      assert(
        initialLoadedImages < await imageSlots.count(),
        `${reviewType}-${count}: every long-deck image loaded eagerly`,
      );
      const finalImageSlot = imageSlots.last();
      await finalImageSlot.scrollIntoViewIfNeeded();
      await finalImageSlot.locator("img.content-review-vm-image").waitFor();
      assert(
        await page.locator("img.content-review-vm-image").count() > initialLoadedImages,
        `${reviewType}-${count}: near-viewport image did not load`,
      );
    }
```

把内容长稿调用改为：

```javascript
      for (const count of [10, 24, 60]) await checkLongReview("content", count);
      await checkLongReview("visual", 120);
```

保留现有五个视口：`360×900`、`760×900`、`1000×900`、`1280×720`、`1440×900`。

- [ ] **Step 6: 运行验收脚本合同测试和完整本地 UI 验收**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
node --test tests/v22-prototype-fidelity.test.mjs
npm run accept:v22-ui
```

Expected:

- Node tests 全部通过；
- `accept:v22-ui` 退出码 `0`；
- 5 个 content viewport 结果各记录 `objectCount: 3` 和 `textOnlyPageCount: 1`；
- 10/24/60 页内容长稿和 120 页视觉长稿均无横向溢出或 console error；
- 本地验收报告仍明确 `proofEligible: false`、`realHostEvidence: false`，不声称 Browser/宿主/AI/G0。

- [ ] **Step 7: 检查并提交验收覆盖**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git status --short
git diff -- 产品代码/scripts/run-v22-ui-acceptance.mjs 产品代码/tests/v22-prototype-fidelity.test.mjs
git add 产品代码/scripts/run-v22-ui-acceptance.mjs 产品代码/tests/v22-prototype-fidelity.test.mjs
git commit -m "test: cover mixed content review decks"
```

Expected: 只提交验收脚本和其 source-contract 测试，不提交 `output/playwright/` 生成物或临时项目数据。

### Task 6: 将零图片增量状态更新为 implemented-local

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md:3-9,103-118`
- Modify: `../00-唯一研发基线索引-v1.0.md:36-45`
- Modify: `../01-产品需求基线-v1.0.md:12-17,555-567`
- Modify: `../02-系统详细设计-v1.0.md:1058-1065`
- Modify: `../03-UI设计与交互规范-v1.0.md:3-12,655-661,731-741,780-789`

- [ ] **Step 1: 更新专项设计状态，但保留真实能力边界**

把状态行改为：

```markdown
- 状态：`用户已确认设计；本地工程实现完成，真实客户 ReviewSession、宿主通知、AI 接收和 G0 尚未验证`
```

把“问题与结论”开头的实现现状改为过去时，避免实现完成后仍把 validator 写成当前错误：

```markdown
本设计确认时，目标合同和 Python validator 曾把整套 `material-backed | mixed-evidence` 材料模式错误地下沉为“每一页必须至少存在一个 `material_view`”。本地工程实现已经删除该数量强制；证据充分性与图片存在性继续按本设计分离。
```

把“当前实现差距”章节改为：

```markdown
## 5. 本地实现结果与剩余边界

已完成本地工程实现：

- Python `validate_reading_deck_blueprint()` 允许三种材料模式中的单页 `material_views = []`，同时保留 evidence bindings 与单条 material view 的闭合、安全和来源验证；
- `ContentReviewProjection` 与 `ContentReviewPageViewModel` 原序保留非空画面，并把空数组作为正常状态传递；
- 活动 React 表面对零图片页不渲染图片区、标题或空状态，“页面实际文字”使用整行单栏；
- 有图片页继续使用已验收正文/画面结构和近视口读取；
- Review Bridge 只允许读取投影中实际存在的非空 `asset_ref`；
- 合同、投影、Bridge、React、路由、多视口和 10/24/60 页混合长稿均有本地自动化回归。

仍不属于本地实现结论：

- 真实客户材料解析、图片提取、页面关联与选择机制；
- 真实客户 ReviewSession 打开与恢复、宿主通知、AI 接收、G0 或其他 Gate；
- 多图片数量、分组、排序、网格、主辅角色或自动选择策略。
```

- [ ] **Step 2: 同步四份唯一基线中的实现状态**

只替换零图片增量的状态语句，保留产品合同和其他待实现项：

```markdown
# 00 索引中的状态句
该零图片增量已经完成本地工程实现，不重开既有前端整体验收结论；该实现不证明真实客户 ReviewSession、宿主打开/通知、AI 接收、G0 或其他 Gate。

# 01 产品需求中的状态句
- 零图片页面增量合同：……确认所有材料模式均允许单页无图；无图时隐藏图片区并让实际文字扩展，已完成本地工程实现

- `已完成本地工程实现`：三种材料模式允许单页 `material_views = []`；活动 React 表面隐藏零图片页的图片区及标题并让正文扩展，Review Bridge 不为零图片页开放资源读取；该状态不证明真实客户 ReviewSession、宿主、AI 或 G0。

# 02 Slice C3 状态句
- 本地工程状态：`已完成`；不重开既有内容审核前端整体验收，也不证明真实客户 ReviewSession、宿主通知、AI 接收或 G0；

# 03 UI 状态登记
`contentReviewOptionalMaterialVisuals = implemented-local`：三种材料模式允许单页无图；活动 React 表面在零图片页隐藏图片区、标题和空状态并让实际文字扩展到整行；本地合同、投影、资源安全、React、多视口和混合长稿回归已通过。该状态不证明真实客户 ReviewSession、宿主通知、AI 接收或 G0。
```

同时把 `03-UI设计与交互规范-v1.0.md` 顶部状态、08 原型说明和“当前实现状态”中“已确认但尚未实现/当前尚未实现”的零图片专属措辞改为 `implemented-local`。不得改变 `contentReviewFrontendUiAcceptance = accepted`，不得把长稿本地自动化写成真实客户长文档性能验收。

- [ ] **Step 3: 验证基线相对链接和状态边界**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
test -f 00-唯一研发基线索引-v1.0.md
test -f 01-产品需求基线-v1.0.md
test -f 02-系统详细设计-v1.0.md
test -f 03-UI设计与交互规范-v1.0.md
test -f 产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.html
test -f 产品代码/docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md
rg -n "contentReviewOptionalMaterialVisuals = implemented-local|Slice C3|本地工程实现完成" 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md
rg -n "realHostEvidence = false|aiReceiptEvidence = false|gateConfirmation = none|真实客户 ReviewSession" 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md
git diff --check
```

Expected: 所有 `test -f` 成功；实现状态和真实能力边界都能检索到；无 Markdown 空白错误。

- [ ] **Step 4: 检查并提交状态文档**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git status --short
git diff -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md
git add 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-20-content-review-optional-material-visuals-design.md
git commit -m "docs: record optional material visuals implementation"
```

Expected: 提交只包含四份基线和本专项规格；不包含 `AGENTS.md` 或验收输出。

### Task 7: 全量回归、差异审计与交付边界确认

**Files:**
- Verify: all files changed in Tasks 1-6
- Preserve untouched: `AGENTS.md`
- Preserve untouched: visual review source and visual Slice F2 contracts

- [ ] **Step 1: 运行完整 Python 内容合同与内容审核回归**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest -v tests.test_v22_content_contracts tests.test_v22_content_repair_loop tests.test_v22_content_review_projection
npm run test:python
```

Expected: 两条命令退出码 `0`。三种材料模式、硬门、ReviewSession、PageDecision、ContentReviewBatch 和其他 Python 回归无退化。

- [ ] **Step 2: 运行完整 Node、React、类型和构建回归**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
node --test tests/review-bridge.test.mjs tests/v22-prototype-fidelity.test.mjs
npm run test:widget -- widget/src/content-review/content-review-page-view-model.test.tsx widget/src/content-review/ContentReviewViewModelSurface.test.tsx widget/src/ReviewSurfaceRouter.test.tsx
npm run quality
```

Expected: 所有命令退出码 `0`；正式路由、窄投影验证、Bridge 安全和视觉审核既有测试保持通过。

- [ ] **Step 3: 重跑本地多视口与长稿验收**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR/产品代码
npm run accept:v22-ui
```

Expected: 退出码 `0`；content 5 个视口、10/24/60 页混合长稿和 visual 既有验收均通过。输出只能描述 `local-development-preview`，不能升级为真实 Browser/宿主/AI/Gate 证据。

- [ ] **Step 4: 审计最终差异、提交历史和用户改动隔离**

Run:

```bash
cd /private/tmp/ai-ppt-v22-TmBomR
git diff --check
git status --short
git log --oneline -12
git diff --stat 60020df..HEAD
git diff --name-only 60020df..HEAD
```

Expected:

- `git diff --check` 无输出；
- 工作区只剩既存未暂存的 ` D AGENTS.md`；
- 从 `60020df` 之后的提交按顺序包含合同、投影安全、ViewModel、React、验收和文档状态的独立回退点；
- 文件清单中没有视觉审核生产文件、PPT 运行数据、并行 Web 产品文件或 `output/playwright/` 生成物。

- [ ] **Step 5: 形成实施交付说明，不扩大验收结论**

交付说明必须逐项区分：

```text
已完成本地工程实现：
- 三种材料模式允许单页 material_views = []；
- 零图片页隐藏图片区/标题/空状态，实际文字整行；
- 有图片页结构与近视口读取保持；
- 空页不进入资源白名单，非空资源安全规则保持；
- 合同、投影、Bridge、React、路由、多视口和混合长稿本地回归通过。

未由本切片证明：
- 真实客户材料解析、图片提取与图片选择；
- 真实 ReviewSession 打开/恢复；
- 宿主通知与 AI 接收；
- G0 或其他 Gate；
- 视觉审核 Slice F2；
- 多图片产品规则。
```

不要把本地自动化结果写成用户再次验收通过；用户既有内容审核前端验收继续有效，本次仅交付已确认增量的本地实现证据。
