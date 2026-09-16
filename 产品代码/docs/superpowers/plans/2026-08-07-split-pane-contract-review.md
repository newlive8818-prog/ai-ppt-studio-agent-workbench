# Contract Review Collapsed Outline and Compact Header Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让合同审阅页在完整 PC、专业审阅、Codex 分屏和窄侧栏中都默认隐藏目录，并使用约 64px 的单行紧凑 Header，把可用空间优先交给正文。

**Architecture:** 保留单文件、单 DOM 和单交互状态。目录在所有视口中统一成为左侧覆盖抽屉；CSS 不再为目录预留布局列，JavaScript 只管理通用的打开、关闭、焦点和文档切换状态。Header 使用一行三段布局，通过信息优先级隐藏非核心文案，不增加第二行。

**Tech Stack:** 单文件 HTML/CSS/JavaScript、Playwright CLI 真实浏览器测试、Markdown UI 基线。

## Global Constraints

- 所有模式首次打开时目录均为关闭状态，不持久化上一次开启状态。
- 目录打开和关闭不得改变正文宽度、横向位置或当前滚动位置。
- Header 高度约 64px，内容/视觉切换不允许下沉为第二行。
- 目录入口、内容/视觉切换、标记入口和保存操作始终保留。
- 不改变内容、视觉合同、标记、保存、G0/G3 和最终 PPTX 验收合同。
- 不启用子智能体；在当前已确认的 `codex/mvp-skill-app-design` 分支内联执行。

---

### Task 1: 锁定跨视口失败行为

**Files:**
- Verify: `产品代码/prototypes/06-fullscreen-contract-review-exploration.html`

**Interfaces:**
- Consumes: `.app-header`, `.workspace`, `.document-outline`, `#outlineToggle`, `.reading-surface`。
- Produces: 1440×1100、1000×1000、760×1000 三档失败证据。

- [x] **Step 1: 启动本地静态服务器和 Playwright 会话**

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory 产品代码
PWCLI=/Users/defei/.codex/skills/playwright/scripts/playwright_cli.sh
"$PWCLI" -s=contract-review open http://127.0.0.1:8765/prototypes/06-fullscreen-contract-review-exploration.html
```

- [x] **Step 2: 在每个视口运行同一条行为断言**

```javascript
() => {
  const header = document.querySelector('.app-header').getBoundingClientRect();
  const workspace = getComputedStyle(document.querySelector('.workspace'));
  const outline = document.querySelector('.document-outline');
  const outlineStyle = getComputedStyle(outline);
  const toggle = document.querySelector('#outlineToggle');
  const result = {
    headerHeight: Math.round(header.height),
    workspaceDisplay: workspace.display,
    outlinePosition: outlineStyle.position,
    outlineVisible: outline.getBoundingClientRect().right > 0,
    outlineAriaHidden: outline.getAttribute('aria-hidden'),
    toggleVisible: getComputedStyle(toggle).display !== 'none',
  };
  if (result.headerHeight > 66 || result.workspaceDisplay !== 'block' ||
      result.outlinePosition !== 'fixed' || result.outlineVisible ||
      result.outlineAriaHidden !== 'true' || !result.toggleVisible) {
    throw new Error(JSON.stringify(result));
  }
  return result;
}
```

Expected before implementation: 1440px fails because the directory is a sticky layout column and the toggle is hidden; 1000px fails because Header is 78px; 760px fails because the old grid and 112px Header remain active.

### Task 2: 统一目录覆盖抽屉与单行 Header

**Files:**
- Modify: `产品代码/prototypes/06-fullscreen-contract-review-exploration.html`

**Interfaces:**
- Consumes: `#documentOutline`, `#outlineToggle`, `#outlineBackdrop`, `#closeOutline`, `#commentDrawer`。
- Produces: `setOutlineState(open, restoreFocus)`, `openOutline()`, `closeOutline()` 的全视口通用行为。

- [x] **Step 1: 实现最小 CSS 变化**

```css
:root { --header-h: 64px; }
.app-header { height: var(--header-h); }
.workspace { display: block; }
.outline-toggle { display: inline-flex; }
.document-outline {
  position: fixed;
  width: min(320px, calc(100vw - 24px));
  transform: translateX(-102%);
}
.document-outline.open { transform: translateX(0); }
```

将 1440px 的目录常驻列规则删除；在 1000px 和 760px 下隐藏英文副标题、长保存状态，必要时隐藏项目长标题，但保持目录、文档切换、标记和保存按钮可见。

- [x] **Step 2: 实现全视口目录状态**

```javascript
function setOutlineState(open, restoreFocus = false) {
  documentOutline.classList.toggle('open', open);
  outlineBackdrop.classList.toggle('open', open);
  outlineToggle.setAttribute('aria-expanded', String(open));
  documentOutline.setAttribute('aria-hidden', String(!open));
  if (!open && restoreFocus) outlineToggle.focus();
}
```

删除只对 900–1279px 生效的 `splitViewQuery` 分支；目录项定位后在所有视口关闭目录，内容/视觉切换后保持关闭。

- [x] **Step 3: 重跑 Task 1 的三档断言**

Expected: 三档均返回 Header 约 64px、`.workspace` 为 `block`、目录 `fixed` 且默认不可见、`aria-hidden=true`、目录按钮可见。

### Task 3: 验证交互、正文稳定性和 UI 基线

**Files:**
- Modify: `03-UI设计与交互规范-v1.0.md`
- Verify: `产品代码/prototypes/06-fullscreen-contract-review-exploration.html`
- Create: `产品代码/output/playwright/06-contract-review-collapsed-1440.png`
- Create: `产品代码/output/playwright/06-contract-review-collapsed-1000.png`
- Create: `产品代码/output/playwright/06-contract-review-collapsed-760.png`

**Interfaces:**
- Consumes: 已实现的目录抽屉、内容/视觉切换、标记抽屉和 `localStorage` 保存。
- Produces: UI 唯一基线中的默认折叠目录与 64px 单行 Header 合同、真实浏览器证据。

- [x] **Step 1: 验证目录不会挤压正文**

```javascript
() => {
  const paper = document.querySelector('.document-view:not([hidden])');
  const before = paper.getBoundingClientRect();
  document.querySelector('#outlineToggle').click();
  const after = paper.getBoundingClientRect();
  if (before.width !== after.width || before.x !== after.x) {
    throw new Error(JSON.stringify({ before, after }));
  }
  document.querySelector('.document-outline .outline-link').click();
  if (document.querySelector('.document-outline').classList.contains('open')) {
    throw new Error('outline did not close after navigation');
  }
  return { width: before.width, x: before.x };
}
```

- [x] **Step 2: 回归交互**

验证背景、关闭按钮和 `Escape` 均可关闭目录；目录与标记抽屉不能同时打开；内容/视觉切换后目录关闭且标签同步；新增标记可保存并在刷新后保留。

- [x] **Step 3: 同步 UI 唯一基线**

在 UI-03/UI-04 共用审阅规则中明确：目录默认折叠、所有模式按需覆盖、选择后关闭、不得挤压正文；Header 约 64px 单行，按优先级隐藏非核心文案。

- [x] **Step 4: 截图与最终检查**

在 1440×1100、1000×1000、760×1000 下截图；检查控制台 0 错误、页面无目录导致的横向溢出、提示遮罩不存在，并运行：

```bash
git diff --check
rg -n "正式审阅需要至少 1080px|请拖宽右侧审阅区至少 900px|body::before" 产品代码/prototypes/06-fullscreen-contract-review-exploration.html
```
