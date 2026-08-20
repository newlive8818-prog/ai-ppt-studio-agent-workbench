# Content Review ViewModel Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改活动 React 路由、Runtime、MCP 或持久化合同的前提下，建立只输出已确认内容审核前端字段的 `ContentReviewPageViewModel` 与纯 adapter，并让缺少权威 `customerJudgment` 的输入明确失败。

**Architecture:** 新建一个只负责 ViewModel 类型和纯转换的前端模块；它继续接收现有 `ContentReviewProjection`，只复制页面渲染、审核状态和写入身份所需字段。当前正式投影与严格校验器仍不提供 `customerJudgment`，因此成功用例只证明 adapter 对显式权威字段的转换能力；生产路由接入留到上游字段合同和活动页面迁移的后续切片。

**Tech Stack:** TypeScript 5.7、Vitest 3、现有 Widget 内容审核类型。

---

## Scope and file ownership

**Create:**

- `产品代码/widget/src/content-review/content-review-page-view-model.ts`：定义前端专用 ViewModel、字段缺口错误和纯 adapter。
- `产品代码/widget/src/content-review/content-review-page-view-model.test.tsx`：冻结允许字段、映射规则、不可变性和失败关闭行为；使用 `.tsx` 后缀以符合当前 Vitest 收集规则。

**Do not modify:**

- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- `产品代码/widget/src/content-review/ContentMaterialView.tsx`
- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- `产品代码/widget/src/review-surface-validation.ts`
- `产品代码/widget/src/types/content-review.ts`
- `产品代码/src/ai_ppt_studio/**`
- `产品代码/mcp/**`
- PPT 运行数据目录

## Resolved design decisions

- Adapter 读取每页自有数据属性 `customerJudgment`；该属性必须是非空、已去除首尾空白的字符串。
- 不把 `customerJudgment` 加入当前 `ContentReviewProjection` 类型或严格校验字段清单，因为那属于后续 Runtime/MCP 投影迁移。
- `projectLabel` 在过渡期使用现有权威 `project_id`，同时保留 `projectId`、`reviewSessionId` 和 `readingBlueprintRef` 供后续写操作使用。
- `visible_copy_blocks` 暂时一律转换为 `paragraph`；旧投影没有可靠的 paragraph/bullet 类型，adapter 不猜测项目符号语义。
- 图片替代文字由已确认的 `neutral_title`、页面序号和图片序号确定性生成，不读取或暴露来源文件名等证据元数据。
- `batchState` 只输出 `open | submitted | withdrawn`；已提交批次关闭保存与提交动作，未提交或当前 adapter 不识别的状态统一保持 `open`，批次结构合法性仍由现有页面校验边界负责。
- `localDraftState` 只表示由权威已保存决定初始化的干净状态；浏览器本地草稿恢复仍由现有 draft store 在后续页面接入中处理。

### Task 1: Freeze the ViewModel contract with failing tests

**Files:**

- Create: `产品代码/widget/src/content-review/content-review-page-view-model.test.tsx`
- Test: `产品代码/widget/src/content-review/content-review-page-view-model.test.tsx`

- [ ] **Step 1: Write the fixture and allowed-field test**

Create a valid `ContentReviewProjection` fixture, attach an explicit own `customerJudgment` value to each test slide, call the wished-for API, and assert the exact ViewModel keys:

```ts
import { expect, it } from "vitest";

import type { ContentReviewProjection, ContentReviewSlide } from "../types/content-review";
import {
  ContentReviewPageViewModelAdapterError,
  toContentReviewPageViewModel,
} from "./content-review-page-view-model";

type SlideWithCustomerJudgment = ContentReviewSlide & { customerJudgment?: string };

function projection(customerJudgment: string | null = "客户确认现状边界后，再判断是否进入联合方案验证。"): ContentReviewProjection {
  const value: ContentReviewProjection = {
    project_id: "p1",
    review_type: "content-full-deck",
    review_session_id: "review-1",
    review_session: {},
    source_version: "content-v1",
    revision: 7,
    authoritative_revision: 8,
    reading_blueprint_ref: `artifact://reading-deck-blueprint/${"a".repeat(64)}`,
    material_mode: "mixed-evidence",
    section_flow: ["现状判断"],
    slides: [{
      slide_id: "S01",
      order: 1,
      section_id: "problem",
      page_task: "确认当前流程断点及证据边界",
      reading_question: "现有材料能否支撑当前判断？",
      neutral_title: "当前流程断点与证据边界",
      visible_copy_blocks: [{ block_id: "copy-1", text: "当前流程存在三个待核实断点。", identity: "来源事实" }],
      identity_labels: ["来源事实"],
      evidence_bindings: [{ source_ref: "internal-only" }],
      material_views: [{
        material_view_id: "S01-M01",
        source_ref: "internal-source",
        asset_ref: "review-assets/content/S01-M01.png",
        source_file_name: "客户材料.pptx",
        page_number: 3,
        region_label: "整页",
        purpose: "证明流程断点",
        treatment: "只读呈现",
        evidence_identity: "来源事实",
      }],
      analysis_or_proposal_blocks: [{ block_id: "analysis-1", text: "内部建议", identity: "方案建议" }],
      solution_mapping_refs: ["mapping-1"],
      previous_relation: "",
      next_relation: "进入方案验证",
      speaker_notes: "内部演讲备注",
      reading_quality: { independently_readable: true, information_density: "moderate", review_note: "内部检查" },
      material_mode: "mixed-evidence",
    }],
    decisions: [],
    progress: { completed: 0, total: 1, remaining: 1, unsaved: 0 },
    batch: null,
    revision_plan: null,
    content_acceptance_ref: `artifact://content-acceptance/${"c".repeat(64)}`,
  };
  if (customerJudgment !== null) {
    Object.defineProperty(value.slides[0] as SlideWithCustomerJudgment, "customerJudgment", {
      configurable: true,
      enumerable: true,
      value: customerJudgment,
      writable: true,
    });
  }
  return value;
}

it("projects only the accepted content review frontend contract", () => {
  const viewModel = toContentReviewPageViewModel(projection());
  expect(Object.keys(viewModel).sort()).toEqual([
    "authoritativeRevision", "availableActions", "batchState", "progress", "projectId",
    "projectLabel", "readingBlueprintRef", "reviewSessionId", "revision", "sections", "slides",
    "sourceVersion",
  ].sort());
  expect(Object.keys(viewModel.slides[0]).sort()).toEqual([
    "customerJudgment", "draftContent", "localDraftState", "materialVisuals", "neutralTitle",
    "order", "pageGoal", "readingQuestion", "savedDecision", "sectionId", "slideId",
  ].sort());
  expect(viewModel.slides[0]).toMatchObject({
    slideId: "S01",
    pageGoal: "确认当前流程断点及证据边界",
    customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
    readingQuestion: "现有材料能否支撑当前判断？",
    draftContent: {
      title: "当前流程断点与证据边界",
      blocks: [{ blockId: "copy-1", type: "paragraph", text: "当前流程存在三个待核实断点。" }],
    },
    materialVisuals: [{
      visualId: "S01-M01",
      assetRef: "review-assets/content/S01-M01.png",
      altText: "第 1 页《当前流程断点与证据边界》页面画面 1",
    }],
  });
});
```

- [ ] **Step 2: Add forbidden-field, state-preservation and immutability tests**

Add the following helper and tests:

```ts
function collectKeys(value: unknown, keys = new Set<string>()): Set<string> {
  if (!value || typeof value !== "object") return keys;
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, keys));
    return keys;
  }
  Object.entries(value).forEach(([key, item]) => {
    keys.add(key);
    collectKeys(item, keys);
  });
  return keys;
}

it("does not expose rejected governance or material metadata fields", () => {
  const keys = collectKeys(toContentReviewPageViewModel(projection()));
  for (const field of [
    "analysis_or_proposal_blocks", "identity", "identity_labels", "evidence_bindings",
    "solution_mapping_refs", "previous_relation", "next_relation", "speaker_notes",
    "reading_quality", "source_file_name", "page_number", "region_label", "purpose",
    "treatment", "evidence_identity", "source_ref",
  ]) expect(keys).not.toContain(field);
});

it("preserves stable review identity and initializes frontend state without mutating input", () => {
  const input = projection();
  input.decisions = [{
    page_decision_id: "decision-1",
    project_id: "p1",
    review_session_id: "review-1",
    source_version: "content-v1",
    reading_blueprint_ref: input.reading_blueprint_ref,
    slide_id: "S01",
    slide_order: 1,
    slide_title_snapshot: "当前流程断点与证据边界",
    decision: "modify",
    comment: "请补充现状依据。",
    status: "completed",
    saved_at: "2026-08-20T09:00:00+08:00",
    supersedes_decision_ref: "",
  }];
  input.progress = { completed: 1, total: 1, remaining: 0, unsaved: 0 };
  input.batch = { status: "submitted" };
  const before = structuredClone(input);

  const viewModel = toContentReviewPageViewModel(input);

  expect(viewModel).toMatchObject({
    projectId: "p1",
    projectLabel: "p1",
    reviewSessionId: "review-1",
    readingBlueprintRef: input.reading_blueprint_ref,
    sourceVersion: "content-v1",
    revision: 7,
    authoritativeRevision: 8,
    progress: { completed: 1, total: 1, remaining: 0, unsaved: 0 },
    batchState: "submitted",
    availableActions: { savePageDecision: false, submitReviewBatch: false },
    sections: [{ sectionId: "problem", title: "现状判断", slideIds: ["S01"] }],
  });
  expect(viewModel.slides[0].savedDecision).toEqual(input.decisions[0]);
  expect(viewModel.slides[0].savedDecision).not.toBe(input.decisions[0]);
  expect(viewModel.slides[0].localDraftState).toEqual({
    decision: "modify",
    comment: "请补充现状依据。",
    dirty: false,
  });
  expect(input).toEqual(before);
});
```

- [ ] **Step 3: Add fail-closed customerJudgment tests**

Add the following tests. They distinguish a genuine projection fact from missing, blank, inherited or accessor-backed data and prove that unrelated text is not used as a fallback:

```ts
it.each([null, "", " 未去除空白 "])(
  "fails when customerJudgment is not an authoritative nonblank value: %s",
  (customerJudgment) => {
    const input = projection(customerJudgment);
    expect(() => toContentReviewPageViewModel(input)).toThrow(ContentReviewPageViewModelAdapterError);
    try {
      toContentReviewPageViewModel(input);
    } catch (error) {
      expect(error).toMatchObject({
        code: "CONTENT_REVIEW_CUSTOMER_JUDGMENT_MISSING",
        slideId: "S01",
        fieldPath: "slides[0].customerJudgment",
      });
      expect(String(error)).not.toContain(input.slides[0].neutral_title);
      expect(String(error)).not.toContain(input.slides[0].reading_question);
      expect(String(error)).not.toContain(input.slides[0].page_task);
    }
  },
);

it("rejects inherited or accessor-backed customerJudgment without invoking a getter", () => {
  const inherited = projection(null);
  Object.setPrototypeOf(inherited.slides[0], { customerJudgment: "继承值" });
  expect(() => toContentReviewPageViewModel(inherited)).toThrow(ContentReviewPageViewModelAdapterError);

  const accessor = projection(null);
  Object.defineProperty(accessor.slides[0], "customerJudgment", {
    enumerable: true,
    get() { throw new Error("getter must not run"); },
  });
  expect(() => toContentReviewPageViewModel(accessor)).toThrow(ContentReviewPageViewModelAdapterError);
});
```

- [ ] **Step 4: Run the focused test and verify RED**

Run from `产品代码/`:

```bash
npm run test:widget -- widget/src/content-review/content-review-page-view-model.test.tsx
```

Expected: FAIL because `content-review-page-view-model.ts` does not exist.

### Task 2: Implement the minimal pure adapter

**Files:**

- Create: `产品代码/widget/src/content-review/content-review-page-view-model.ts`
- Test: `产品代码/widget/src/content-review/content-review-page-view-model.test.tsx`

- [ ] **Step 1: Define focused readonly ViewModel types**

Create these focused interfaces; do not reuse `ContentReviewSlide` as an output type:

```ts
import type {
  ContentDecisionChoice,
  ContentPageDecision,
  ContentReviewProjection,
  ContentReviewSlide,
} from "../types/content-review";

export type ContentReviewDraftBlockType = "paragraph" | "bullet";
export type ContentReviewBatchState = "open" | "submitted" | "withdrawn";

export interface ContentReviewDraftBlockViewModel {
  readonly blockId: string;
  readonly type: ContentReviewDraftBlockType;
  readonly text: string;
}

export interface ContentReviewDraftContentViewModel {
  readonly title: string;
  readonly blocks: readonly ContentReviewDraftBlockViewModel[];
}

export interface ContentReviewMaterialVisualViewModel {
  readonly visualId: string;
  readonly assetRef: string;
  readonly altText: string;
}

export interface ContentReviewLocalDraftStateViewModel {
  readonly decision: ContentDecisionChoice | "";
  readonly comment: string;
  readonly dirty: false;
}

export interface ContentReviewSlideViewModel {
  readonly slideId: string;
  readonly order: number;
  readonly sectionId: string;
  readonly neutralTitle: string;
  readonly pageGoal: string;
  readonly customerJudgment: string;
  readonly readingQuestion: string;
  readonly draftContent: ContentReviewDraftContentViewModel;
  readonly materialVisuals: readonly ContentReviewMaterialVisualViewModel[];
  readonly savedDecision: ContentPageDecision | null;
  readonly localDraftState: ContentReviewLocalDraftStateViewModel;
}

export interface ContentReviewSectionViewModel {
  readonly sectionId: string;
  readonly title: string;
  readonly slideIds: readonly string[];
}

export interface ContentReviewPageViewModel {
  readonly projectId: string;
  readonly projectLabel: string;
  readonly reviewSessionId: string;
  readonly readingBlueprintRef: string;
  readonly sourceVersion: string;
  readonly revision: number;
  readonly authoritativeRevision: number;
  readonly progress: Readonly<ContentReviewProjection["progress"]>;
  readonly sections: readonly ContentReviewSectionViewModel[];
  readonly slides: readonly ContentReviewSlideViewModel[];
  readonly batchState: ContentReviewBatchState;
  readonly availableActions: Readonly<{
    savePageDecision: boolean;
    submitReviewBatch: boolean;
  }>;
}
```

- [ ] **Step 2: Add the explicit field-gap error**

```ts
export class ContentReviewPageViewModelAdapterError extends Error {
  readonly code = "CONTENT_REVIEW_CUSTOMER_JUDGMENT_MISSING" as const;
  constructor(readonly slideId: string, readonly fieldPath: string) {
    super(`Content review projection is missing authoritative ${fieldPath} for slide ${slideId}.`);
    this.name = "ContentReviewPageViewModelAdapterError";
  }
}
```

- [ ] **Step 3: Implement descriptor-safe mapping**

Add the complete pure mapping below. It reads `customerJudgment` only through an own enumerable data descriptor. Blank/untrimmed values throw the field-gap error; no other field is consulted as a substitute.

```ts
function customerJudgmentOf(slide: ContentReviewSlide, index: number): string {
  const descriptor = Object.getOwnPropertyDescriptor(slide, "customerJudgment");
  const value = descriptor && descriptor.enumerable && "value" in descriptor
    ? descriptor.value
    : undefined;
  if (typeof value !== "string" || !value || value !== value.trim()) {
    throw new ContentReviewPageViewModelAdapterError(
      slide.slide_id,
      `slides[${index}].customerJudgment`,
    );
  }
  return value;
}

function batchStateOf(batch: ContentReviewProjection["batch"]): ContentReviewBatchState {
  if (batch?.status === "submitted") return "submitted";
  if (batch?.status === "withdrawn") return "withdrawn";
  return "open";
}

function sectionsOf(projection: ContentReviewProjection): ContentReviewSectionViewModel[] {
  const sections: Array<{ sectionId: string; title: string; slideIds: string[] }> = [];
  for (const slide of projection.slides) {
    const current = sections.at(-1);
    if (current?.sectionId === slide.section_id) {
      current.slideIds.push(slide.slide_id);
      continue;
    }
    sections.push({
      sectionId: slide.section_id,
      title: projection.section_flow[sections.length] ?? slide.section_id,
      slideIds: [slide.slide_id],
    });
  }
  return sections;
}

function cloneDecision(decision: ContentPageDecision | undefined): ContentPageDecision | null {
  return decision ? { ...decision } : null;
}

export function toContentReviewPageViewModel(
  projection: ContentReviewProjection,
): ContentReviewPageViewModel {
  const decisions = new Map(projection.decisions.map((decision) => [decision.slide_id, decision]));
  const batchState = batchStateOf(projection.batch);
  const slides = projection.slides.map((slide, slideIndex): ContentReviewSlideViewModel => {
    const savedDecision = cloneDecision(decisions.get(slide.slide_id));
    return {
      slideId: slide.slide_id,
      order: slide.order,
      sectionId: slide.section_id,
      neutralTitle: slide.neutral_title,
      pageGoal: slide.page_task,
      customerJudgment: customerJudgmentOf(slide, slideIndex),
      readingQuestion: slide.reading_question,
      draftContent: {
        title: slide.neutral_title,
        blocks: slide.visible_copy_blocks.map((block) => ({
          blockId: block.block_id,
          type: "paragraph",
          text: block.text,
        })),
      },
      materialVisuals: slide.material_views.map((material, materialIndex) => ({
        visualId: material.material_view_id,
        assetRef: material.asset_ref,
        altText: `第 ${slide.order} 页《${slide.neutral_title}》页面画面 ${materialIndex + 1}`,
      })),
      savedDecision,
      localDraftState: {
        decision: savedDecision?.decision ?? "",
        comment: savedDecision?.comment ?? "",
        dirty: false,
      },
    };
  });
  return {
    projectId: projection.project_id,
    projectLabel: projection.project_id,
    reviewSessionId: projection.review_session_id,
    readingBlueprintRef: projection.reading_blueprint_ref,
    sourceVersion: projection.source_version,
    revision: projection.revision,
    authoritativeRevision: projection.authoritative_revision,
    progress: { ...projection.progress },
    sections: sectionsOf(projection),
    slides,
    batchState,
    availableActions: {
      savePageDecision: batchState !== "submitted",
      submitReviewBatch: batchState !== "submitted",
    },
  };
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run from `产品代码/`:

```bash
npm run test:widget -- widget/src/content-review/content-review-page-view-model.test.tsx
```

Expected: the focused adapter test file passes with zero failures and no warnings.

- [ ] **Step 5: Run typecheck**

Run from `产品代码/`:

```bash
npm run typecheck
```

Expected: TypeScript exits 0 with no diagnostics.

### Task 3: Verify scope and establish the rollback point

**Files:**

- Verify: `产品代码/docs/superpowers/plans/2026-08-20-content-review-view-model-adapter-implementation.md`
- Verify: `产品代码/widget/src/content-review/content-review-page-view-model.ts`
- Verify: `产品代码/widget/src/content-review/content-review-page-view-model.test.tsx`

- [ ] **Step 1: Verify the complete Widget regression suite**

Run from `产品代码/`:

```bash
npm run test:widget
```

Expected: all Widget tests pass with zero failures.

- [ ] **Step 2: Verify diff hygiene and scope**

Run from the worktree root:

```bash
git diff --check
git status --short --branch
git diff -- 产品代码/docs/superpowers/plans/2026-08-20-content-review-view-model-adapter-implementation.md 产品代码/widget/src/content-review/content-review-page-view-model.ts 产品代码/widget/src/content-review/content-review-page-view-model.test.tsx
```

Expected: only the plan, adapter and adapter test are new task files; the unrelated ` D AGENTS.md` remains unstaged and unmodified by this task.

- [ ] **Step 3: Stage only task-owned files and inspect the index**

```bash
git add 产品代码/docs/superpowers/plans/2026-08-20-content-review-view-model-adapter-implementation.md 产品代码/widget/src/content-review/content-review-page-view-model.ts 产品代码/widget/src/content-review/content-review-page-view-model.test.tsx
git diff --cached --check
git diff --cached --name-status
```

Expected: the cached diff contains exactly three added files and never contains `AGENTS.md`.

- [ ] **Step 4: Commit the isolated adapter slice**

```bash
git commit -m "feat: add content review page view model adapter"
```

Expected: one new commit containing only the three task-owned files. The next slice remains activity-page and route integration; Runtime/MCP remains later still.
