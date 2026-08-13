# Content Blueprint Sidebar Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a framework-first, maximum-width content-blueprint sidebar in which the user reads the complete evidence-backed deck, saves one decision per page, submits one frozen review batch, confirms Codex's whole-deck revision plan, re-reviews every new blueprint, and only then confirms G0.

**Architecture:** Python schema 3 remains the only business writer and gains separate framework, page-decision, review-batch, and batch-plan aggregates. Node MCP remains a thin revision-safe adapter with action-specific host confirmation scopes, while React reads formal framework/full-deck projections and never owns completion or Gate truth. Existing `ReviewMarkSet` and the Browser professional-review contract remain intact for G3 visual review; content Browser use is narrowed to evidence enlargement and comparison.

**Tech Stack:** Python 3.11+ dataclasses and content-addressed JSON artifacts, schema 3 `ProjectKernel`, Node.js ESM MCP server with Zod, React 19 + TypeScript + Vite, Vitest/Testing Library, `unittest`, scoped loopback Browser bridge.

---

## 1. Confirmed implementation decisions

1. `PageDecision` is a new content-domain object. It does not extend `ReviewMarkSet`; `ReviewMarkSet` remains available for G3 visual Browser review and historical content marks.
2. Framework confirmation, full-deck expansion authorization, review-batch submission, batch-plan confirmation, and G0 use distinct action scopes and one-time confirmation identities. None can consume or replay another scope's identity.
3. The current project heads are:
   - `content/framework-draft` → `content-framework-draft`
   - `content/framework-confirmation` → `content-framework-confirmation`
   - `content/full-deck-expansion-authorization` → `full-deck-expansion-authorization`
   - `content/page-decisions` → `content-page-decision-set`
   - `content/review-batch` → `content-review-batch`
   - `content/batch-revision-plan` → `content-batch-revision-plan`
   - `content/batch-plan-confirmation` → `content-batch-plan-confirmation`
   - `content/review-batch-withdrawal` → `content-review-batch-withdrawal`
4. Each decision save creates a new immutable decision artifact and a new immutable decision-set aggregate. Only the latest set is a project head; prior artifacts remain addressable through event/artifact history.
5. A submitted batch is frozen. Later lifecycle changes create a new `content-review-batch` artifact with the same `review_batch_id`, a `supersedes_ref`, and unchanged `decision_refs`; the submitted artifact is never overwritten.
6. A batch revision plan contains `requires_blueprint_revision`. If false, confirmed application can mark the current batch `applied` without creating a new blueprint. If true, the confirmed plan authorizes governance, a `ContentChangeSet`, a new immutable blueprint, and a fresh full-deck review with zero inherited decisions.
7. G0 confirmation context is available only when the current blueprint has an `applied` review batch for the exact same `source_version`, all decisions are complete, and no newer unprocessed plan/batch exists.
8. The sidebar fetches a dedicated content-review projection after entering the blueprint space. The compact project snapshot carries stage/status and framework summary; it does not duplicate a 60-page full projection.
9. At 900 CSS pixels and above, every slide section uses a 43%/57% content/evidence grid. Below 900 pixels it becomes one column. The document remains `width: 100%` with no centered narrow-column cap.
10. Existing content Browser review routes remain readable during migration but are removed as the primary UI-03 action. The new evidence route cannot write page decisions; G3 visual Browser regression tests stay mandatory.
11. A user may withdraw only a `submitted` batch before a plan is proposed. Withdrawal creates a superseding `superseded` lifecycle artifact plus a new draft batch ID and new immutable decisions for the same blueprint; it never edits the submitted artifact. Once status is `plan-proposed` or later, the user must finish or supersede the plan instead of withdrawing the batch.

## 2. Target file map

### Product baseline and acceptance

- Modify `00-唯一研发基线索引-v1.0.md`: register the approved design and current implementation status.
- Modify `01-产品需求基线-v1.0.md`: replace the old UI-03 Browser-first and immediate-governance requirements.
- Modify `02-系统详细设计-v1.0.md`: add aggregates, services, operations, state transitions, errors, and test contracts.
- Modify `03-UI设计与交互规范-v1.0.md`: define framework-only and full-deck sidebar states, page decisions, layout, and Browser evidence assistance.
- Modify `产品代码/docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md`: set the approved written-spec status.
- Modify `产品代码/requirements/v1.6-evidence.json`: remove stale proof-to-requirement mappings for materially replaced UI-03 contracts; do not delete proof files or requirements.
- Regenerate `产品代码/requirements/v1.6-acceptance-ledger.json` without deleting requirement IDs or proof obligations.
- Modify `产品代码/tests/test_acceptance_ledger.py`: assert the new content-review wording, 104 stable requirements, and the lower strict passed count produced after stale evidence is invalidated.

### Python domain and application services

- Create `产品代码/src/ai_ppt_studio/domains/content/framework.py`: framework and action-authorization validators.
- Create `产品代码/src/ai_ppt_studio/domains/content/review_contracts.py`: page decision, frozen batch, and batch revision-plan validators.
- Modify `产品代码/src/ai_ppt_studio/domains/content/contracts.py`: require the complete reading-first slide contract.
- Create `产品代码/src/ai_ppt_studio/application/scoped_confirmation.py`: generic action-scoped confirmation challenge and assertion verification.
- Create `产品代码/src/ai_ppt_studio/application/framework_discussion_service.py`: framework draft, confirmation, and expansion authorization.
- Create `产品代码/src/ai_ppt_studio/application/content_review_service.py`: full projection, page saves, completion statistics, batch submission, and lifecycle transitions.
- Create `产品代码/src/ai_ppt_studio/application/content_batch_planning_service.py`: plan persistence, confirmation, governance/change-set authorization, and applied state.
- Modify `产品代码/src/ai_ppt_studio/application/content_service.py`: framework/authorization lineage, new-blueprint lineage, no inherited decisions, and confirmed-plan-only revisions.
- Modify `产品代码/src/ai_ppt_studio/application/project_service.py`: action-specific preconditions.
- Modify `产品代码/src/ai_ppt_studio/application/workspace_projection.py`: framework-only, producing, full-review, batch-submitted, and plan states.
- Modify `产品代码/src/ai_ppt_studio/application/gate_confirmation.py`: require the final applied current-source batch for G0.
- Modify `产品代码/src/ai_ppt_studio/application/v16_bridge.py`: expose the new Python operations.
- Modify `产品代码/src/ai_ppt_studio/context_compiler.py`: bind framework, authorization, batch, plan, and confirmation refs into the correct Agent tasks.
- Modify `产品代码/src/ai_ppt_studio/errors.py` and `产品代码/src/ai_ppt_studio/workbench_bridge.py`: preserve stable content-workflow error codes and details.

### MCP and Browser adapter

- Modify `产品代码/mcp/host-confirmation-assertion.mjs`: sign generic `scope_kind` / `scope_id` contexts while retaining Gate compatibility.
- Modify `产品代码/mcp/server.mjs`: register framework, full-deck, decision, batch, plan, and evidence Browser tools.
- Modify `产品代码/mcp/review-bridge.mjs`: support a read-only evidence session scoped to project/source/slide/material.
- Modify `产品代码/mcp/runtime-bridge/python-runtime.mjs`: preserve the Python error code/detail envelope for all new operations.
- Modify `产品代码/tests/mcp-server.test.mjs`, `产品代码/tests/mcp-runtime-bridge.test.mjs`, and `产品代码/tests/review-bridge.test.mjs`: tool/schema/confirmation/evidence-route contracts.

### React sidebar

- Create `产品代码/widget/src/lib/content-review-client.ts`: typed calls for projection, decisions, batch submission, and evidence Browser.
- Create `产品代码/widget/src/components/content-review/ContentFrameworkPanel.tsx`: framework-only projection with no slide leakage.
- Create `产品代码/widget/src/components/content-review/ContentReviewDocument.tsx`: continuous full-deck reader.
- Create `产品代码/widget/src/components/content-review/ContentReviewDirectory.tsx`: compact chapter navigation and next-incomplete navigation.
- Create `产品代码/widget/src/components/content-review/ContentSlideSection.tsx`: complete page text/evidence/notes/quality/relationship section.
- Create `产品代码/widget/src/components/content-review/PageDecisionEditor.tsx`: four mutually exclusive decisions and inline comment editor.
- Create `产品代码/widget/src/components/content-review/ReviewBatchFooter.tsx`: exact completion blockers and frozen-batch submission.
- Modify `产品代码/widget/src/types.ts`, `产品代码/widget/src/App.tsx`, `产品代码/widget/src/components/CompactWorkspace.tsx`, `产品代码/widget/src/lib/sidebar-host-client.ts`, and `产品代码/widget/src/styles.css`: route UI-03 to the complete sidebar document.
- Create focused tests and fixtures under `产品代码/widget/src/content-review/` and `产品代码/widget/src/__fixtures__/content-sidebar-review.json`.

### Skill, preview, performance, and evidence

- Modify `产品代码/skills/ai-ppt-studio/SKILL.md` and the content/native/review workflow references so Codex follows the new checkpoints.
- Modify `产品代码/scripts/seed-v16-ui-project.py`, `产品代码/scripts/create-widget-preview.mjs`, and `产品代码/scripts/run-v16-ui-acceptance.mjs` for 10/24/60-page content-review states.
- Modify `产品代码/scripts/probe-mcp.mjs` to probe all new tools without manufacturing confirmations.
- Create `产品代码/docs/validation/2026-08-14-content-sidebar-review-acceptance.md` for automated, preview, and real-host evidence identities.

## 3. Public data contracts

The implementation must use these stable snake-case Python/artifact fields and camel-case MCP arguments.

```python
CONTENT_PAGE_DECISIONS = frozenset(
    {"approved", "modify", "evidence", "merge-or-delete"}
)
COMMENT_REQUIRED_DECISIONS = frozenset(
    {"modify", "evidence", "merge-or-delete"}
)
CONTENT_REVIEW_BATCH_STATUSES = frozenset(
    {
        "draft",
        "ready",
        "submitted",
        "plan-proposed",
        "plan-confirmed",
        "applied",
        "superseded",
    }
)
MAX_PAGE_DECISION_COMMENT_LENGTH = 1200
```

```ts
export type ContentPageDecisionKind =
  | "approved"
  | "modify"
  | "evidence"
  | "merge-or-delete";

export interface SaveContentPageDecisionArgs {
  projectRoot: string;
  expectedRevision: number;
  sourceVersion: string;
  reviewBatchId: string;
  slideId: string;
  decision: ContentPageDecisionKind;
  comment: string;
}
```

Every write returns the authoritative project `snapshot`; page-decision writes also return `page_completion` and `review_progress`. Only `submit_content_review_batch` returns a `follow_up_message`, and only the caller of that successful submission may ask the host to start the Codex follow-up.

---

### Task 1: Synchronize the four formal baselines and acceptance ledger

**Files:**
- Modify: `00-唯一研发基线索引-v1.0.md`
- Modify: `01-产品需求基线-v1.0.md`
- Modify: `02-系统详细设计-v1.0.md`
- Modify: `03-UI设计与交互规范-v1.0.md`
- Modify: `产品代码/docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md`
- Modify: `产品代码/tests/test_acceptance_ledger.py`
- Modify: `产品代码/requirements/v1.6-evidence.json`
- Regenerate: `产品代码/requirements/v1.6-acceptance-ledger.json`

- [ ] **Step 1: Update status and conflict statements**

Change the approved design status to `已获用户书面批准，待实现`, add it as item 11 in the unique baseline index, and explicitly state that it replaces only the old UI-03 content-review rules. Preserve G3 Browser, UI-01/UI-02/UI-04/UI-05, the managed runtime root, and the parallel Web product boundary.

- [ ] **Step 2: Replace the PRD's UI-03 requirements without renumbering acceptance IDs**

Update sections 7.2, 7.3, 8.1, 9.3, 10.3, 12, 17.1, 17.2, and 17.5 so they explicitly require:

```markdown
任务书与目录框架先在 Codex 对话中讨论；框架未确认且未取得独立全稿展开授权时，不得生成或展示逐页内容。获得授权后，最大宽度侧边栏连续展示完整全稿、实际文字、真实材料、来源定位、使用方式、证据身份/缺口、完整逐字稿、阅读质量与跨页关系。用户逐页保存四选一判断，全部完成后提交冻结批次；Codex 先形成整套修改方案，用户确认方案后才允许治理、ContentChangeSet 和新蓝图。新蓝图必须全篇复审，最终当前版本审核完成后才能在 Codex 对话确认 G0。
```

Keep the existing numbered acceptance-item positions so IDs such as `PRD-17.1-03`, `PRD-17.2-06`, and `PRD-17.5-04` remain stable; revise their text instead of inserting or deleting list items.

- [ ] **Step 3: Replace the SDD's old Browser-first system contract**

Add the exact artifact heads, service boundaries, action scopes, state machine, projection contract, and error codes from sections 1–3 of this plan. In section 21, preserve all numbered IDs while rewriting the affected E2E items to cover framework separation, complete page data, page-save non-effects, frozen batches, confirmed plans, new-version re-review, G0 lineage, and G3 regression.

- [ ] **Step 4: Replace UI-03 layout and interaction rules**

Update the UI principles, surface-responsibility table, width rules, UI-03 section, component table, section 23 key tasks, real-content tests, and screenshot gate. State `900px+ = 43% / 57%`, `width: 100%`, no centered max-width, no horizontal overflow, 10/24/60-page cases, and a compact non-persistent directory.

- [ ] **Step 5: Invalidate old proof mappings for replaced requirement semantics**

The 2026-08-12 automated/runtime/viewport evidence predates this approved design and cannot prove the new page-decision, frozen-batch, plan-confirmation, maximum-width-sidebar, or full-re-review semantics. Remove these IDs from every existing proof's `requirement_ids` array:

```python
REPLACED_REQUIREMENT_IDS = {
    "PRD-17.1-04",
    "PRD-17.2-03",
    "PRD-17.2-04",
    "PRD-17.2-05",
    "PRD-17.2-06",
    "PRD-17.2-07",
    "PRD-17.2-08",
    "PRD-17.2-09",
    "PRD-17.2-10",
    "PRD-17.5-04",
    "PRD-17.5-07",
    "UI-23.2-05",
    "UI-23.2-07",
    "UI-23.2-08",
    "UI-23.2-09",
}
```

Keep the requirements themselves and all `required_evidence` kinds. Do not reuse a historical Browser viewport, old review-mark runtime record, or local prototype as proof of the new behavior. This changes the strict baseline from 37 to 22 passed until Tasks 13–16 add genuine new evidence.

- [ ] **Step 6: Strengthen the checked-in ledger test before regenerating**

Add exact wording assertions while retaining the strict counts:

```python
self.assertEqual(len(ledger.requirements), 104)
self.assertEqual(
    sum(item.status == "passed" for item in ledger.requirements), 22
)
self.assertIn("目录框架", by_id["PRD-17.2-03"].text)
self.assertIn("冻结批次", by_id["PRD-17.2-09"].text)
self.assertIn("最大宽度侧边栏", by_id["UI-23.2-04"].text)
self.assertIn("全部页面", by_id["UI-23.2-07"].text)
self.assertIn("修改方案", by_id["SDD-21.3-13"].text)
for requirement_id in REPLACED_REQUIREMENT_IDS:
    self.assertEqual(by_id[requirement_id].status, "unproven")
```

- [ ] **Step 7: Regenerate and verify the ledger**

Run from `产品代码/`:

```bash
python3 scripts/build_acceptance_ledger.py
python3 -m unittest discover -s tests -p 'test_acceptance_ledger.py' -v
```

Expected: `wrote 104 requirements`; all ledger tests pass; the checked-in ledger reports exactly 22 passed; every replaced content-sidebar requirement is `unproven` until new proof is registered.

- [ ] **Step 8: Validate links and commit only the baseline slice**

Run from the project root:

```bash
test -f 产品代码/docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md
test -d 产品代码/prototypes
git diff --check -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md 产品代码/tests/test_acceptance_ledger.py 产品代码/requirements/v1.6-evidence.json 产品代码/requirements/v1.6-acceptance-ledger.json
git add 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md 产品代码/tests/test_acceptance_ledger.py 产品代码/requirements/v1.6-evidence.json 产品代码/requirements/v1.6-acceptance-ledger.json
git commit -m "docs: adopt content sidebar review baseline"
```

Expected: the commit contains only these eight paths; do not stage unrelated pre-existing worktree changes.

---

### Task 2: Add framework and complete reading-first page contracts

**Files:**
- Create: `产品代码/src/ai_ppt_studio/domains/content/framework.py`
- Create: `产品代码/tests/test_v16_content_framework.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/content/contracts.py`
- Modify: `产品代码/tests/test_v16_content_chain.py`
- Create: `产品代码/tests/v16_content_fixtures.py`

- [ ] **Step 1: Write failing framework-contract tests**

Add tests that accept chapters without slide titles/copy and reject slide-level leakage:

```python
def valid_framework() -> dict[str, object]:
    return {
        "framework_id": "framework-v1",
        "mission_confirmation_ref": "artifact://mission-confirmation/" + "1" * 64,
        "core_proposition": "先证明经营断点，再确认一期联合验证路径。",
        "persuasion_path": ["形成问题共识", "建立方案可信度", "促成一期行动"],
        "chapters": [
            {
                "chapter_id": "C01",
                "title": "为什么现在需要改变",
                "task": "把分散系统问题转成经营判断。",
                "expected_judgment": "现状需要跨系统治理。",
                "transition": "从问题共识进入建设原则。",
            }
        ],
        "structural_risks": ["现有材料尚不能证明定量收益。"],
        "highest_impact_question": "是否将一期决策作为全篇收束点？",
        "status": "discussion",
    }

def test_framework_forbids_slide_level_content(self) -> None:
    with self.assertRaisesRegex(ContractValidationError, "slide-level"):
        validate_framework_draft({**valid_framework(), "slides": [{"title": "提前生成"}]})
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_framework.py' -v
```

Expected: import failure for `ai_ppt_studio.domains.content.framework`.

- [ ] **Step 3: Implement the framework validators**

Create these public functions and normalized fields:

```python
FRAMEWORK_FORBIDDEN_FIELDS = frozenset(
    {"slides", "slide_titles", "visible_copy", "speaker_notes", "materials"}
)

def validate_framework_draft(payload: dict[str, Any]) -> dict[str, Any]:
    if FRAMEWORK_FORBIDDEN_FIELDS.intersection(payload):
        raise ContractValidationError(
            "FrameworkDraft cannot contain slide-level content"
        )
    chapters = _objects(payload, "chapters")
    for chapter in chapters:
        for field in (
            "chapter_id", "title", "task", "expected_judgment", "transition"
        ):
            chapter[field] = _text(chapter, field)
    return {
        **payload,
        "framework_id": _text(payload, "framework_id"),
        "mission_confirmation_ref": _text(payload, "mission_confirmation_ref"),
        "core_proposition": _text(payload, "core_proposition"),
        "persuasion_path": _strings(payload, "persuasion_path"),
        "chapters": chapters,
        "structural_risks": _strings(payload, "structural_risks"),
        "highest_impact_question": _text(payload, "highest_impact_question"),
        "status": "discussion",
    }
```

Also add validators for `FrameworkConfirmation` and `FullDeckExpansionAuthorization`; both must bind `project_id`, exact framework ref, current revision, challenge identity, and confirmed timestamp. The authorization validator additionally requires the exact framework-confirmation ref.

- [ ] **Step 4: Write failing complete-slide-contract tests**

Define a valid reading-first slide and assert each required field independently fails when removed. The normalized slide shape must be:

```python
{
    "slide_id": "S01",
    "chapter_id": "C01",
    "order": 1,
    "title": "系统在线不等于经营闭环已经形成",
    "page_purpose": "把技术系统问题提升为经营协同问题。",
    "customer_judgment": "需要统一经营口径和跨系统闭环。",
    "communication_goal": "建立改变现状的必要性。",
    "core_claim": "分散在线系统仍会造成经营断点。",
    "visible_copy": [
        {"copy_id": "title", "role": "title", "text": "系统在线不等于经营闭环已经形成"},
        {"copy_id": "body-1", "role": "body", "text": "数据口径、流程责任和决策节奏仍然分散。"},
        {"copy_id": "source-1", "role": "source", "text": "来源：用户材料 A，第 3 页"},
    ],
    "evidence_items": [
        {
            "evidence_id": "E01",
            "evidence_kind": "material",
            "material_ref": "artifact://material-inventory/" + "2" * 64,
            "asset_ref": "project://materials/case-a-p03.png",
            "source_file": "案例 A.pptx",
            "source_page_or_region": "第 3 页，右侧流程区",
            "used_region": "订单—计划—交付断点图",
            "supports_claim": "跨系统流程存在责任断点",
            "treatment": "crop",
            "fact_identity": "source-fact",
            "evidence_gap": "当前只能证明流程断点，不能证明收益幅度。",
        }
    ],
    "speaker_notes": "先让客户确认问题性质，再说明本页不推导收益数字。",
    "reading_quality": {
        "independently_readable": True,
        "information_density": "moderate",
        "claim_reason_evidence_boundary_complete": True,
        "review_note": "去掉讲稿后仍可读懂主张、理由、证据和边界。",
    },
    "sequence": {
        "previous_slide_id": "",
        "next_slide_id": "S02",
        "transition_from_previous": "封面后直接建立问题共识。",
        "transition_to_next": "从问题性质进入一期建设原则。",
    },
    "user_judgment_prompt": "这页是否足以让客户接受问题不是单系统缺陷？",
    "source_refs": ["artifact://material-inventory/" + "2" * 64],
}
```

- [ ] **Step 5: Run and verify the old minimal contract is rejected**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_chain.py' -v
```

Expected: failures identify missing `page_purpose`, `customer_judgment`, `evidence_items`, `reading_quality`, `sequence`, and `user_judgment_prompt`.

- [ ] **Step 6: Implement complete slide validation**

In `validate_content_stage("slide-draft-set", payload)`, require integer positive unique `order`, structured `visible_copy`, at least one material or planned-gap evidence item, complete speaker notes, the four reading-quality fields, sequence fields, and the judgment prompt. A planned gap uses:

```python
{
    "evidence_id": "E-GAP-01",
    "evidence_kind": "planned-gap",
    "material_ref": "",
    "asset_ref": "",
    "source_file": "待补",
    "source_page_or_region": "待补",
    "used_region": "待补客户现状证据",
    "supports_claim": "客户当前流程确有重复录入",
    "treatment": "to-supply",
    "fact_identity": "joint-validation-required",
    "evidence_gap": "G0 前需补材料，或将主张降级为诊断假设。",
}
```

Reject `reading_quality.independently_readable is not True`, a false `claim_reason_evidence_boundary_complete`, unknown density values, an empty evidence gap for `planned-gap`, and any slide whose order set is not exactly `1..N`.

- [ ] **Step 7: Update fixtures and run the full content-contract slice**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_*.py' -v
```

Expected: all content contract/chain tests pass; fixture changes contain actual copy/evidence metadata rather than empty filler values.

- [ ] **Step 8: Commit the domain-contract slice**

```bash
git add src/ai_ppt_studio/domains/content/framework.py src/ai_ppt_studio/domains/content/contracts.py tests/test_v16_content_framework.py tests/test_v16_content_chain.py tests/v16_content_fixtures.py
git commit -m "feat: define framework and reading-first content contracts"
```

The shared fixture file is required so Tasks 4–10 consume the same complete reading-first slide data instead of duplicating weaker fixtures.

---

### Task 3: Persist framework discussion and separate expansion authorization

**Files:**
- Create: `产品代码/src/ai_ppt_studio/application/scoped_confirmation.py`
- Create: `产品代码/src/ai_ppt_studio/application/framework_discussion_service.py`
- Create: `产品代码/tests/test_v16_framework_discussion.py`
- Modify: `产品代码/src/ai_ppt_studio/errors.py`
- Modify: `产品代码/src/ai_ppt_studio/kernel/transactions.py`

- [ ] **Step 1: Write failing service tests for three separate states**

Cover: save draft; confirm exact current draft; reject stale draft; authorize expansion only after confirmation; reject reuse of the framework-confirmation identity; preserve G0 as `open`; and expose no page content.

```python
framework_ref, state = service.save_draft(
    command_id="framework-1",
    expected_revision=revision,
    payload=valid_framework(),
)
self.assertEqual(state.gate_status["G0"], "open")

confirmation_context = service.confirmation_context()
self.assertEqual(confirmation_context["scope_kind"], "content-framework")

confirmation_ref, state = service.confirm_framework(
    command_id="framework-confirm-1",
    expected_revision=state.revision,
    source_version=framework_ref,
    challenge_id=confirmation_context["challenge_id"],
    challenge_revision=confirmation_context["challenge_revision"],
    host_confirmation_assertion=signed_assertion(confirmation_context),
)

authorization_context = service.expansion_authorization_context()
self.assertEqual(
    authorization_context["scope_kind"], "full-deck-expansion"
)
self.assertNotEqual(
    authorization_context["challenge_id"], confirmation_context["challenge_id"]
)
```

- [ ] **Step 2: Run and verify missing services**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_framework_discussion.py' -v
```

Expected: imports for `scoped_confirmation` and `framework_discussion_service` fail.

- [ ] **Step 3: Add stable workflow errors**

Add one structured exception used by all new services:

```python
class ContentWorkflowError(AiPptError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)
```

The service must emit `CONTENT_FRAMEWORK_NOT_CONFIRMED`, `FULL_DECK_EXPANSION_NOT_AUTHORIZED`, and `CONTENT_REVIEW_CONFLICT` with current refs/revisions in `details`.

- [ ] **Step 4: Implement generic scoped confirmation**

`ScopedConfirmationPolicy.context()` must hash this complete body:

```python
challenge_body = {
    "project_id": state.project_id,
    "project_root": str(kernel.project_root),
    "scope_kind": scope_kind,
    "scope_id": scope_id,
    "source_version": source_version,
    "evidence_refs": list(evidence_refs),
    "challenge_revision": state.revision,
}
```

`confirmation_payload()` verifies the HMAC assertion, requires exactly one `host-action` or `verified-message`, consumes that identity through `ProjectKernel.commit(confirmation_consumptions=...)`, and rejects a scope/source/challenge/revision mismatch. Keep Gate verification behavior compatible by letting `GateConfirmationPolicy` delegate its HMAC parsing in Task 8.

- [ ] **Step 5: Implement `FrameworkDiscussionService`**

The exact public interface is:

| Method | Required arguments | Return |
|---|---|---|
| `save_draft` | `command_id`, `expected_revision`, `payload` | `(framework_ref, state)` |
| `confirmation_context` | none | scoped-confirmation context |
| `confirm_framework` | `command_id`, `expected_revision`, `source_version`, `challenge_id`, `challenge_revision`, `host_confirmation_assertion` | `(confirmation_ref, state)` |
| `expansion_authorization_context` | none | scoped-confirmation context |
| `authorize_full_deck_expansion` | `command_id`, `expected_revision`, `source_version`, `challenge_id`, `challenge_revision`, `host_confirmation_assertion` | `(authorization_ref, state)` |

Use this complete transaction shape for `save_draft`; the two confirmed writes use the same commit boundary plus the scoped policy's exact payload and confirmation-consumption tuple:

```python
def save_draft(
    self,
    command_id: str,
    expected_revision: int,
    payload: dict[str, Any],
) -> tuple[str, KernelState]:
    normalized = validate_framework_draft(payload)
    readiness = MissionReadinessPolicy(self.kernel).require_ready()
    if normalized["mission_confirmation_ref"] != readiness.confirmation_ref:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "FrameworkDraft does not bind the current MissionConfirmation",
            {
                "expected_confirmation_ref": readiness.confirmation_ref,
                "actual_confirmation_ref": normalized[
                    "mission_confirmation_ref"
                ],
            },
        )
    state = self.kernel.commit(
        command_id=command_id,
        expected_revision=expected_revision,
        event_type="content.framework-draft-saved",
        artifact_updates={
            "content/framework-draft": (
                "content-framework-draft",
                normalized,
            )
        },
        artifact_removals=(
            "content/framework-confirmation",
            "content/full-deck-expansion-authorization",
        ),
    )
    return state.artifact_heads["content/framework-draft"], state
```

`confirmation_context()` uses `scope_kind="content-framework"`, `scope_id=framework_ref`, source/evidence refs containing the current framework and mission confirmation. `expansion_authorization_context()` uses `scope_kind="full-deck-expansion"`, `scope_id=framework_ref`, and evidence refs containing framework, framework confirmation, and mission confirmation. A new framework draft removes the two current confirmation/authorization heads but preserves immutable history and keeps G0 open.

- [ ] **Step 6: Run service and transaction regressions**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_framework_discussion.py' -v
python3 -m unittest discover -s tests -p 'test_v16_gate_confirmation.py' -v
```

Expected: framework tests pass; existing Gate confirmation identity-consumption tests remain green.

- [ ] **Step 7: Commit**

```bash
git add src/ai_ppt_studio/application/scoped_confirmation.py src/ai_ppt_studio/application/framework_discussion_service.py src/ai_ppt_studio/errors.py src/ai_ppt_studio/kernel/transactions.py tests/test_v16_framework_discussion.py
git commit -m "feat: govern content framework authorization"
```

---

### Task 4: Gate full-deck production and publication on the exact authorization

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/project_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/content_service.py`
- Modify: `产品代码/src/ai_ppt_studio/context_compiler.py`
- Modify: `产品代码/src/ai_ppt_studio/role_registry.py`
- Modify: `产品代码/tests/test_v16_project_service.py`
- Modify: `产品代码/tests/test_context_compiler_governance.py`
- Modify: `产品代码/tests/test_v16_content_acceptance.py`

- [ ] **Step 1: Write failing action-precondition tests**

Add `build-content-framework`, `expand-full-content-blueprint`, `propose-content-batch-revision-plan`, and `apply-content-batch-revision` to the action registry. Assert:

```python
self.commands.request_agent_action(
    "framework-task", revision,
    action_type="build-content-framework",
    target_refs=[mission_confirmation_ref],
    instructions="形成只到章节层的目录框架。",
)

with self.assertRaisesRegex(
    ContentWorkflowError, "FULL_DECK_EXPANSION_NOT_AUTHORIZED"
):
    self.commands.request_agent_action(
        "early-full-deck", next_revision,
        action_type="build-slide-draft-set",
        target_refs=[framework_ref],
        instructions="生成逐页内容。",
    )
```

Also assert that strategy/claim/argument/draft/review/aggregate/internal-repair actions cannot run before expansion authorization, while the framework task can.

- [ ] **Step 2: Run action tests and verify failure**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_v16_project_service.py' -v
```

Expected: unsupported action or missing authorization assertion failures.

- [ ] **Step 3: Implement action-family preconditions**

Define separate sets:

```python
FRAMEWORK_ACTIONS = frozenset({"build-content-framework"})
FULL_DECK_CONTENT_ACTIONS = frozenset(
    {
        "build-presales-strategy",
        "build-claim-evidence-map",
        "build-deck-argument-map",
        "build-slide-draft-set",
        "repair-content",
        "review-content-presales",
        "review-content-decision-maker",
        "review-content-evidence",
        "review-content-narrative",
        "review-content-editorial",
        "aggregate-content-reviews",
    }
)
BATCH_PLAN_ACTIONS = frozenset({"propose-content-batch-revision-plan"})
BATCH_APPLY_ACTIONS = frozenset({"apply-content-batch-revision"})
```

Mission readiness gates framework work. Exact current expansion authorization gates full-deck work. A submitted current-source batch gates plan work. A confirmed current plan gates apply work.

- [ ] **Step 4: Bind the new lineage into Context Packs**

For framework tasks include mission/material identity and exclude all `content/draft`, `content/blueprint`, and page-decision heads. For full-deck tasks include current framework draft, framework confirmation, and expansion authorization. For plan tasks include the frozen batch, current blueprint, framework, evidence map, and sequence fields. For apply tasks additionally include the exact plan-confirmation ref.

Assert the context layer contains:

```python
"content_workflow": {
    "framework_ref": framework_ref,
    "framework_confirmation_ref": confirmation_ref,
    "full_deck_expansion_authorization_ref": authorization_ref,
    "review_batch_ref": batch_ref,
    "batch_revision_plan_ref": plan_ref,
    "batch_plan_confirmation_ref": plan_confirmation_ref,
}
```

Unavailable values are empty strings, not invented refs.

- [ ] **Step 5: Make content registration and acceptance enforce lineage**

Before registering any formal full-deck content stage or review, call `FrameworkDiscussionService.require_expansion_authorized()`. Store all three framework refs in `SlideDraftSet`, `ContentAcceptanceRecord`, and `ContentBlueprint`. `accept_content()` must refuse a draft whose authorization does not match the current framework and must not publish any reviewable blueprint before authorization.

- [ ] **Step 6: Run focused content/action/context tests**

```bash
python3 -m unittest discover -s tests -p 'test_v16_project_service.py' -v
python3 -m unittest discover -s tests -p 'test_context_compiler_governance.py' -v
python3 -m unittest discover -s tests -p 'test_v16_content_acceptance.py' -v
```

Expected: all pass; no test can publish a blueprint from Mission readiness alone.

- [ ] **Step 7: Commit**

```bash
git add src/ai_ppt_studio/application/project_service.py src/ai_ppt_studio/application/content_service.py src/ai_ppt_studio/context_compiler.py src/ai_ppt_studio/role_registry.py tests/test_v16_project_service.py tests/test_context_compiler_governance.py tests/test_v16_content_acceptance.py
git commit -m "feat: require full-deck expansion authorization"
```

---

### Task 5: Add independent page-decision persistence and completion rules

**Files:**
- Create: `产品代码/src/ai_ppt_studio/domains/content/review_contracts.py`
- Create: `产品代码/src/ai_ppt_studio/application/content_review_service.py`
- Create: `产品代码/tests/test_v16_content_page_decisions.py`
- Modify: `产品代码/src/ai_ppt_studio/errors.py`

- [ ] **Step 1: Write failing decision-contract tests**

Cover the four decisions, comment requirements, whitespace, 1200/1201 characters, mutually exclusive replacement, stable slide snapshots, stale source, revision conflict, and frozen sets.

```python
def test_required_comments_and_limit(self) -> None:
    for decision in ("modify", "evidence", "merge-or-delete"):
        with self.subTest(decision=decision):
            with self.assertRaisesRegex(
                ContentWorkflowError, "CONTENT_PAGE_COMMENT_REQUIRED"
            ):
                validate_page_decision({**valid_decision(), "decision": decision, "comment": "   "})

    accepted = validate_page_decision(
        {**valid_decision(), "decision": "modify", "comment": "改" * 1200}
    )
    self.assertTrue(accepted["completed"])
    with self.assertRaisesRegex(ContractValidationError, "1200"):
        validate_page_decision(
            {**valid_decision(), "decision": "modify", "comment": "改" * 1201}
        )
```

- [ ] **Step 2: Run and verify missing review contracts**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_page_decisions.py' -v
```

Expected: import failure for `review_contracts` or `ContentReviewService`.

- [ ] **Step 3: Implement normalized decision artifacts**

`validate_page_decision()` returns:

```python
{
    "page_decision_id": page_decision_id,
    "review_batch_id": review_batch_id,
    "project_id": project_id,
    "review_type": "content",
    "source_version": source_version,
    "slide_id": slide_id,
    "slide_order": slide_order,
    "slide_title_snapshot": slide_title_snapshot,
    "visible_copy_snapshot_ref": visible_copy_snapshot_ref,
    "decision": decision,
    "comment": normalized_comment,
    "completed": decision == "approved" or bool(normalized_comment),
    "saved_at": saved_at,
    "supersedes_decision_ref": supersedes_decision_ref,
}
```

`approved` normalizes its comment to an empty string. Three required-comment decisions reject whitespace and more than 1200 Unicode code points.

- [ ] **Step 4: Implement atomic decision save**

Expose `save_page_decision(*, command_id: str, expected_revision: int, source_version: str, review_batch_id: str, slide_id: str, decision: str, comment: str) -> tuple[dict[str, Any], dict[str, Any], KernelState]`.

The implementation resolves the exact current blueprint, finds the authoritative slide/order/title, stores a content-addressed visible-copy snapshot, creates the decision artifact, replaces only the current ref for that slide in a new decision set, appends an audit event, and commits only `content/page-decisions`. It must assert before and after commit that `content/blueprint`, `content/acceptance`, `feedback/governance`, and `content/change-set` heads are unchanged.

Return `page_completion` and this progress shape:

```python
{
    "total": 29,
    "completed": 23,
    "remaining": 6,
    "saved_comment_count": 8,
    "next_incomplete_slide_id": "S24",
    "counts": {
        "approved": 15,
        "modify": 5,
        "evidence": 2,
        "merge_or_delete": 1,
    },
}
```

- [ ] **Step 5: Prove single-page saves have no side effects**

The test must compare head maps and event types before/after save and assert:

```python
self.assertNotIn("feedback/governance", after.artifact_heads)
self.assertNotIn("content/change-set", after.artifact_heads)
self.assertEqual(after.artifact_heads["content/blueprint"], source_version)
self.assertEqual(after.gate_status["G0"], "user-reviewable")
self.assertNotIn("follow_up_message", result)
```

- [ ] **Step 6: Run tests**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_page_decisions.py' -v
python3 -m unittest discover -s tests -p 'test_v16_review_marks.py' -v
```

Expected: both pass; legacy mark behavior remains isolated from page decisions.

- [ ] **Step 7: Commit**

```bash
git add src/ai_ppt_studio/domains/content/review_contracts.py src/ai_ppt_studio/application/content_review_service.py src/ai_ppt_studio/errors.py tests/test_v16_content_page_decisions.py
git commit -m "feat: persist content page decisions"
```

---

### Task 6: Validate, freeze, and submit the complete review batch

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/domains/content/review_contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/application/content_review_service.py`
- Create: `产品代码/tests/test_v16_content_review_batch.py`

- [ ] **Step 1: Write failing completion and freeze tests**

Cover missing decisions, unsaved required comment represented by an incomplete decision, wrong page count, stale source, wrong batch ID, revision conflict, duplicate slide refs, submission identity reuse, frozen mutation, and exact counts.

```python
with self.assertRaisesRegex(
    ContentWorkflowError, "CONTENT_REVIEW_BATCH_INCOMPLETE"
) as caught:
    service.submission_context(
        source_version=blueprint_ref,
        review_batch_id=batch_id,
    )
self.assertEqual(caught.exception.details["remaining"], 2)
self.assertEqual(caught.exception.details["next_incomplete_slide_id"], "S03")
```

- [ ] **Step 2: Run and verify batch methods are missing**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_review_batch.py' -v
```

Expected: `submission_context` or `submit_review_batch` is missing.

- [ ] **Step 3: Implement the batch validator**

`validate_content_review_batch()` must require the exact set of slide IDs from the blueprint, one completed decision ref per slide in page order, `expected_slide_count == len(decision_refs)`, accurate four-way counts, source version, user-action identity, submission timestamp, and a valid status. It must reject mutation of `decision_refs`, counts, or source after status `submitted`.

- [ ] **Step 4: Implement submission context and transaction**

Expose `submission_context(*, source_version: str, review_batch_id: str) -> dict[str, Any]` and `submit_review_batch(*, command_id: str, expected_revision: int, source_version: str, review_batch_id: str, challenge_id: str, challenge_revision: int, host_confirmation_assertion: str) -> tuple[str, str, KernelState]`.

The action context uses `scope_kind="content-review-batch"`, `scope_id=review_batch_id`, evidence refs `[source_version, decision_set_ref, *decision_refs]`, and current revision. The transaction writes only `content/review-batch`, consumes the distinct identity, and returns:

```python
follow_up = (
    "读取已冻结的内容审核批次，结合当前完整蓝图、目录框架、证据地图和跨页关系，"
    "先提出整套修改方案；在用户确认方案前，不生成 ContentChangeSet 或新蓝图。"
)
```

- [ ] **Step 5: Reject post-submit decision changes**

Before `save_page_decision()` writes, resolve the current same-source batch. If its status is `submitted`, `plan-proposed`, `plan-confirmed`, or `applied`, raise `CONTENT_REVIEW_BATCH_FROZEN` and return the batch ref/status in details. Do not silently create a new draft batch from the same source.

- [ ] **Step 6: Add an audited pre-plan withdrawal path**

Add `withdrawal_context(*, source_version: str, review_batch_id: str) -> dict[str, Any]` and `withdraw_review_batch(*, command_id: str, expected_revision: int, source_version: str, review_batch_id: str, reason: str, challenge_id: str, challenge_revision: int, host_confirmation_assertion: str) -> tuple[str, KernelState]`. Require a non-empty reason, current status exactly `submitted`, and `scope_kind="content-review-batch-withdrawal"`. In one transaction:

1. write `content/review-batch-withdrawal` with the old batch ref, reason, action identity, and timestamp, and create a superseding lifecycle artifact for the old batch with status `superseded` and original decisions unchanged;
2. generate a new `review_batch_id`;
3. clone each current decision into a new immutable decision artifact whose `supersedes_decision_ref` points to the prior decision;
4. save a new draft decision-set head bound to the new batch ID and same source;
5. return the new batch ID and current progress without starting a Codex turn.

Reject withdrawal at `plan-proposed`, `plan-confirmed`, `applied`, or `superseded`. Tests must prove the submitted artifact bytes do not change and the new draft can be edited and submitted independently.

- [ ] **Step 7: Run decision/batch tests**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_page_decisions.py' -v
python3 -m unittest discover -s tests -p 'test_v16_content_review_batch.py' -v
```

Expected: all pass; submission creates no governance/change-set/new-blueprint head.

- [ ] **Step 8: Commit**

```bash
git add src/ai_ppt_studio/domains/content/review_contracts.py src/ai_ppt_studio/application/content_review_service.py tests/test_v16_content_review_batch.py
git commit -m "feat: freeze complete content review batches"
```

---

### Task 7: Add whole-deck revision plans and confirmed-plan-only change sets

**Files:**
- Create: `产品代码/src/ai_ppt_studio/application/content_batch_planning_service.py`
- Create: `产品代码/tests/test_v16_content_batch_planning.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/content/review_contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/application/content_service.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/feedback/contracts.py`

- [ ] **Step 1: Write failing plan-contract tests**

The valid plan contains all mandated whole-deck decisions:

```python
{
    "plan_id": "plan-v1",
    "plan_version": 1,
    "review_batch_ref": batch_ref,
    "review_batch_id": batch_id,
    "source_version": blueprint_ref,
    "direct_actions": [{"slide_ids": ["S02"], "action": "改写结论标题"}],
    "cross_page_actions": [{"slide_ids": ["S04", "S05"], "action": "合并重复建设原则"}],
    "merge_delete_actions": [{"source_slide_ids": ["S08"], "target_slide_id": "S07", "preserve": "案例证据", "remove": "重复背景"}],
    "evidence_actions": [{"slide_ids": ["S11"], "action": "降级为待联合验证", "required_material": "客户现状截图"}],
    "revised_chapters": [{"chapter_id": "C02", "title": "一期路径", "slide_ids": ["S06", "S07"]}],
    "estimated_slide_count": 11,
    "preserve_items": ["任务目标", "已核验来源事实"],
    "conflicts_and_risks": ["删页意见与保留完整案例证据存在冲突"],
    "required_user_decisions": ["确认案例证据合并到 S07"],
    "re_review_scope": "new-blueprint-full-deck",
    "requires_blueprint_revision": True,
    "status": "proposed",
}
```

Reject plans that omit any category, bind another batch/source, claim partial user re-review, or have a non-positive estimated count.

- [ ] **Step 2: Run and verify failure**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_batch_planning.py' -v
```

Expected: planning service import or validator failure.

- [ ] **Step 3: Implement plan persistence and lifecycle update**

`save_revision_plan()` requires a current `submitted` batch and exact source, writes `content/batch-revision-plan`, and creates a superseding batch artifact with status `plan-proposed` and unchanged decisions/counts. It cannot create feedback governance or a change set.

- [ ] **Step 4: Implement plan confirmation with its own action scope**

The confirmation context uses:

```python
{
    "scope_kind": "content-batch-plan",
    "scope_id": f"{review_batch_id}:{plan_version}",
    "source_version": plan_ref,
    "evidence_refs": [batch_ref, blueprint_ref, plan_ref],
}
```

`confirm_revision_plan()` consumes a new host identity, writes `content/batch-plan-confirmation`, and advances a superseding batch artifact to `plan-confirmed`. It is not G0 and does not change Gate status.

- [ ] **Step 5: Make governance and ContentChangeSet require the confirmation**

Add `create_governance_and_change_set(*, command_id: str, expected_revision: int, plan_confirmation_ref: str) -> tuple[str, str, KernelState]`.

The transaction resolves the confirmed plan and frozen decisions, creates one governed raw-feedback aggregate preserving each exact user comment and decision type, creates an executable `FeedbackGovernanceRecord` bound to the plan confirmation, and creates a `ContentChangeSet` containing `review_batch_ref`, `revision_plan_ref`, `plan_confirmation_ref`, affected/preserved refs, full re-review route, and source blueprint. Any direct call to `ContentService.create_content_change_set()` without the current plan confirmation raises `CONTENT_BATCH_PLAN_NOT_CONFIRMED`.

- [ ] **Step 6: Handle the no-revision plan path**

If `requires_blueprint_revision` is false, `apply_no_revision_plan()` verifies that every batch decision is `approved`, creates a superseding batch artifact with status `applied`, records the plan confirmation as its application result, and leaves the blueprint unchanged. If any decision requests a change or evidence, reject the no-revision path.

- [ ] **Step 7: Run planning and feedback regressions**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_batch_planning.py' -v
python3 -m unittest discover -s tests -p 'test_context_compiler_governance.py' -v
```

Expected: no change set exists before plan confirmation; the confirmed path creates governed artifacts with exact lineage.

- [ ] **Step 8: Commit**

```bash
git add src/ai_ppt_studio/application/content_batch_planning_service.py src/ai_ppt_studio/domains/content/review_contracts.py src/ai_ppt_studio/application/content_service.py src/ai_ppt_studio/domains/feedback/contracts.py tests/test_v16_content_batch_planning.py tests/test_context_compiler_governance.py
git commit -m "feat: govern batch content revision plans"
```

---

### Task 8: Publish immutable revised blueprints, reset review, and harden G0

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/content_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/content_review_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/gate_confirmation.py`
- Modify: `产品代码/src/ai_ppt_studio/application/scoped_confirmation.py`
- Modify: `产品代码/src/ai_ppt_studio/application/gate_evaluator.py`
- Create: `产品代码/tests/test_v16_content_revision_round.py`
- Modify: `产品代码/tests/test_v16_gate_confirmation.py`

- [ ] **Step 1: Write failing revised-version and G0 tests**

Build a v1 reviewed/confirmed plan, publish v2, and assert:

```python
self.assertNotEqual(v2_ref, v1_ref)
self.assertEqual(v2["supersedes_blueprint_ref"], v1_ref)
self.assertEqual(
    v2["batch_plan_confirmation_ref"], plan_confirmation_ref
)
self.assertEqual(review_service.progress(v2_ref)["completed"], 0)
self.assertEqual(review_service.progress(v2_ref)["remaining"], len(v2["slides"]))

with self.assertRaises(GateBlockedError) as caught:
    GateConfirmationPolicy(kernel).context("G0")
self.assertIn("content-review-batch-current-source-incomplete", caught.exception.missing_evidence)
```

Also assert that a fully approved, no-revision, applied v2 batch unlocks the G0 context and that batch submission/plan confirmation did not themselves pass G0.

- [ ] **Step 2: Run and verify current G0 is too permissive**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_revision_round.py' -v
python3 -m unittest discover -s tests -p 'test_v16_gate_confirmation.py' -v
```

Expected: G0 context is currently available without a current applied review batch, or v2 inherits old review state.

- [ ] **Step 3: Bind revised draft/acceptance/blueprint lineage**

When a blueprint already exists, `register_content_stage("slide-draft-set")` requires the current confirmed batch-plan ref. `accept_content()` writes `supersedes_blueprint_ref`, `review_batch_ref`, `batch_revision_plan_ref`, and `batch_plan_confirmation_ref` into acceptance and blueprint. First-version publication instead binds framework confirmation and expansion authorization and leaves revision-plan fields empty.

- [ ] **Step 4: Start a fresh decision aggregate per source**

`ContentReviewService.current_decision_set(source_version)` returns an empty draft set when the current decision head targets another source. Saving the first v2 decision creates a new `review_batch_id`; it never copies a v1 decision/comment/completion flag. The projection may expose v1 processing results in `previous_round`, but those fields are read-only context and are not counted toward v2 completion.

- [ ] **Step 5: Advance the previous batch without confusing current review truth**

When a revision-required plan has produced and internally accepted v2, create a superseding v1 batch lifecycle artifact with status `applied` and `result_blueprint_ref=v2_ref`. The current G0 policy still rejects it because its `source_version` is v1. The next v2 batch must be completed and applied independently.

- [ ] **Step 6: Require final current-source applied batch for G0**

For G0, evidence refs become:

```python
evidence_refs = [
    acceptance_ref,
    source_version,
    current_review_batch_ref,
    current_plan_ref,
    current_plan_confirmation_ref,
]
```

The batch must have `status == "applied"`, exact source version, expected count equal to current slide count, complete decision refs, and no later submitted/proposed plan. Update the G0 review summary to state the page count, completed review round, and whether the final plan made no content change.

- [ ] **Step 7: Delegate Gate HMAC parsing to the generic scope verifier**

Make Gate contexts include `scope_kind="gate"` and `scope_id=gate`, while still accepting the existing Node assertion payload during one compatibility release. Tests must reject a framework, expansion, batch, or plan assertion when passed to G0.

- [ ] **Step 8: Run revision/G0 and visual Gate regressions**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_revision_round.py' -v
python3 -m unittest discover -s tests -p 'test_v16_gate_confirmation.py' -v
python3 -m unittest discover -s tests -p 'test_v16_visual_gates.py' -v
```

Expected: all pass; G3/G4 behavior remains unchanged.

- [ ] **Step 9: Commit**

```bash
git add src/ai_ppt_studio/application/content_service.py src/ai_ppt_studio/application/content_review_service.py src/ai_ppt_studio/application/gate_confirmation.py src/ai_ppt_studio/application/scoped_confirmation.py src/ai_ppt_studio/application/gate_evaluator.py tests/test_v16_content_revision_round.py tests/test_v16_gate_confirmation.py
git commit -m "feat: require final content review before G0"
```

---

### Task 9: Build authoritative framework/full-deck sidebar projections

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/content_review_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/workspace_projection.py`
- Create: `产品代码/tests/test_v16_content_sidebar_projection.py`
- Modify: `产品代码/tests/test_v16_workspace_projection.py`

- [ ] **Step 1: Write failing projection-state tests**

Cover these exact phases:

```python
phases = (
    "framework-discussion",
    "framework-confirmed",
    "awaiting-full-deck-authorization",
    "full-deck-producing",
    "full-deck-review-ready",
    "review-batch-submitted",
    "batch-plan-proposed",
    "batch-plan-confirmed",
)
```

For the first three, assert the serialized projection has no `slides`, `slide_titles`, `speaker_notes`, or `evidence_items` key anywhere. For review-ready, assert every source slide maps exactly once in order and every required complete field is present without truncation.

- [ ] **Step 2: Run and verify projection failure**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_sidebar_projection.py' -v
```

Expected: the new projection method or phases are missing.

- [ ] **Step 3: Implement the framework-only projection**

Return:

```python
{
    "display_policy": "content-sidebar-framework",
    "phase": phase,
    "project_id": state.project_id,
    "revision": state.revision,
    "mission_summary": mission_summary,
    "framework": {
        "source_version": framework_ref,
        "core_proposition": framework["core_proposition"],
        "persuasion_path": framework["persuasion_path"],
        "chapters": framework["chapters"],
        "structural_risks": framework["structural_risks"],
        "highest_impact_question": framework["highest_impact_question"],
        "confirmed": bool(framework_confirmation_ref),
        "expansion_authorized": bool(authorization_ref),
    },
    "next_action": "continue-framework-discussion",
}
```

Do not reuse `ReviewService.content_projection()` for this state.

- [ ] **Step 4: Implement the full-deck projection**

Return a continuous document with `chapters`, complete ordered `slides`, `review_progress`, current decisions, current batch/plan statuses, and `previous_round`. Each slide must copy complete visible-copy blocks and evidence records byte-for-byte from the blueprint, and include `decision_state` with `selected`, `comment`, `completed`, `saved`, and `frozen`.

- [ ] **Step 5: Update the compact workspace projection**

Replace `saved_mark_count` and `open-content-review` with:

```python
{
    "phase": phase,
    "framework_ref": framework_ref,
    "framework_confirmed": bool(framework_confirmation_ref),
    "expansion_authorized": bool(authorization_ref),
    "review_available": phase == "full-deck-review-ready",
    "source_version": blueprint_ref,
    "slide_count": slide_count,
    "completed_page_count": progress["completed"],
    "remaining_page_count": progress["remaining"],
    "current_batch_status": batch_status,
    "primary_action": {"kind": "continue-chat", "label": label, "enabled": True},
}
```

The React blueprint component itself renders the document; `primary_action` is only used for framework discussion and non-review production states.

- [ ] **Step 6: Run projections and no-leak checks**

```bash
python3 -m unittest discover -s tests -p 'test_v16_content_sidebar_projection.py' -v
python3 -m unittest discover -s tests -p 'test_v16_workspace_projection.py' -v
```

Expected: all phases pass; framework JSON contains no per-page data; full-deck JSON equals the authoritative source text and evidence metadata.

- [ ] **Step 7: Commit**

```bash
git add src/ai_ppt_studio/application/content_review_service.py src/ai_ppt_studio/application/workspace_projection.py tests/test_v16_content_sidebar_projection.py tests/test_v16_workspace_projection.py
git commit -m "feat: project complete content sidebar review"
```

---

### Task 10: Expose revision-safe Python bridge operations and stable errors

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `产品代码/src/ai_ppt_studio/workbench_bridge.py`
- Modify: `产品代码/tests/test_v16_bridge.py`
- Modify: `产品代码/tests/test_v16_experience_bridge.py` only if its operation enumeration is shared

- [ ] **Step 1: Write failing dispatch tests for every new operation**

Cover:

```python
NEW_OPERATIONS = (
    "save-content-framework-draft",
    "get-content-framework-confirmation-context",
    "confirm-content-framework",
    "get-full-deck-expansion-authorization-context",
    "authorize-full-deck-expansion",
    "get-content-sidebar-review-projection",
    "save-content-page-decision",
    "get-content-review-batch-submission-context",
    "submit-content-review-batch",
    "get-content-review-batch-withdrawal-context",
    "withdraw-content-review-batch",
    "save-content-batch-revision-plan",
    "get-content-batch-plan-confirmation-context",
    "confirm-content-batch-revision-plan",
    "create-content-batch-change-set",
)
```

Assert read operations do not mutate revision, every write requires `expected_revision`, and only batch submission returns a follow-up message. Withdrawal returns a new draft batch ID and no follow-up.

- [ ] **Step 2: Run and verify unsupported operations**

```bash
python3 -m unittest discover -s tests -p 'test_v16_bridge.py' -v
```

Expected: new operations are unrecognized.

- [ ] **Step 3: Add thin dispatch branches**

Instantiate `FrameworkDiscussionService`, `ContentReviewService`, and `ContentBatchPlanningService` once in `dispatch_v16()`. Each branch maps request fields to the service without duplicating validation. All successful writes return:

```python
{
    "ok": True,
    "operation": operation,
    "selected_project_root": str(project_root),
    "result": {
        "artifact_ref": artifact_ref,
        "snapshot": _snapshot(state, project_root),
    },
}
```

Decision saves add `page_completion` and `review_progress`; batch submission adds `follow_up_message`.

- [ ] **Step 4: Preserve workflow error codes at the process boundary**

Before generic validation mapping in `_error_payload`, add:

```python
if isinstance(exc, ContentWorkflowError):
    return 2, {
        "ok": False,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        },
    }
```

Test all ten codes from the approved design, including stale/frozen/save-failed/conflict details. Do not collapse them to `VALIDATION_ERROR`.

- [ ] **Step 5: Run bridge and process-boundary tests**

```bash
python3 -m unittest discover -s tests -p 'test_v16_bridge.py' -v
python3 -m unittest discover -s tests -p 'test_v16_*bridge.py' -v
```

Expected: all pass; JSON stdout remains the only bridge output.

- [ ] **Step 6: Commit**

```bash
git add src/ai_ppt_studio/application/v16_bridge.py src/ai_ppt_studio/workbench_bridge.py tests/test_v16_bridge.py tests/test_v16_experience_bridge.py
git commit -m "feat: expose content review runtime operations"
```

Omit `tests/test_v16_experience_bridge.py` if it did not require a change.

---

### Task 11: Add MCP tools and action-specific host confirmations

**Files:**
- Modify: `产品代码/mcp/host-confirmation-assertion.mjs`
- Modify: `产品代码/mcp/server.mjs`
- Modify: `产品代码/mcp/runtime-bridge/python-runtime.mjs`
- Modify: `产品代码/tests/mcp-server.test.mjs`
- Modify: `产品代码/tests/mcp-runtime-bridge.test.mjs`
- Modify: `产品代码/tests/host_confirmation_fixtures.py`

- [ ] **Step 1: Write failing tool-list and schema tests**

Assert the public tool set adds:

```js
[
  "save_content_framework_draft",
  "confirm_content_framework",
  "authorize_full_deck_expansion",
  "get_content_sidebar_review_projection",
  "save_content_page_decision",
  "submit_content_review_batch",
  "withdraw_content_review_batch",
  "save_content_batch_revision_plan",
  "confirm_content_batch_revision_plan",
  "create_content_batch_change_set",
  "open_content_evidence_browser",
]
```

`save_content_page_decision` must expose exactly `projectRoot`, `expectedRevision`, `sourceVersion`, `reviewBatchId`, `slideId`, `decision`, and `comment`; decision enum values must match the Python contract. `withdraw_content_review_batch` adds required `reason`. All confirmed writes bind exact current artifact refs and a host-derived confirmation context.

- [ ] **Step 2: Run and verify missing tools**

```bash
node --test tests/mcp-server.test.mjs
```

Expected: tool-list/schema assertions fail.

- [ ] **Step 3: Generalize signed confirmation payloads**

Replace the Gate-only payload identity with:

```js
const payload = {
  project_id: context.project_id,
  project_root: context.project_root,
  scope_kind: context.scope_kind || "gate",
  scope_id: context.scope_id || context.gate,
  gate: context.gate || "",
  source_version: context.source_version,
  evidence_refs: context.evidence_refs,
  challenge_id: context.challenge_id,
  challenge_revision: context.challenge_revision,
  identity_type: identityType,
  identity_ref: identityRef.trim(),
  nonce: randomUUID(),
  issued_at: issuedAt,
  expires_at: issuedAt + lifetimeSeconds,
};
```

Add a generic `requestHostScopedConfirmation(server, context)` whose prompt names the action, source, and statement that the confirmation cannot be reused. Keep `requestHostGateConfirmation` as a wrapper for existing Gate wording.

- [ ] **Step 4: Register read and unconfirmed write tools**

`get_content_sidebar_review_projection` maps directly to the read operation. `save_content_framework_draft`, `save_content_page_decision`, `save_content_batch_revision_plan`, and `create_content_batch_change_set` map fields, return structured results, and never call `sendFollowUp` inside the MCP server.

- [ ] **Step 5: Register five separately confirmed action tools**

For framework confirmation, expansion authorization, batch submission, pre-plan batch withdrawal, and plan confirmation:

1. Fetch the corresponding Python context.
2. Verify source/revision against input.
3. Obtain a verified message or host-native elicitation.
4. Issue the scope-specific assertion.
5. Call the write operation with raw action/message refs empty.

Batch submission returns its `follow_up_message` to the sidebar. Withdrawal returns the replacement draft batch ID and no follow-up. The MCP server must not start a model turn by itself.

- [ ] **Step 6: Test cross-scope rejection and page-save silence**

Add tests that decode issued assertions and prove unique `scope_kind`/`scope_id`, that a framework assertion fails expansion, that a batch assertion fails withdrawal/plan confirmation/G0, and that `save_content_page_decision` performs one Python call with no elicitation and no follow-up call.

- [ ] **Step 7: Run Node contracts**

```bash
node --test tests/mcp-server.test.mjs
node --test tests/mcp-runtime-bridge.test.mjs
```

Expected: all pass; existing mission and G0/G3/G4 confirmations remain green.

- [ ] **Step 8: Commit**

```bash
git add mcp/host-confirmation-assertion.mjs mcp/server.mjs mcp/runtime-bridge/python-runtime.mjs tests/mcp-server.test.mjs tests/mcp-runtime-bridge.test.mjs tests/host_confirmation_fixtures.py
git commit -m "feat: publish content review MCP tools"
```

---

### Task 12: Route UI-03 to framework/full-deck sidebar data

**Files:**
- Create: `产品代码/widget/src/lib/content-review-client.ts`
- Create: `产品代码/widget/src/components/content-review/ContentFrameworkPanel.tsx`
- Create: `产品代码/widget/src/content-review/ContentFrameworkPanel.test.tsx`
- Modify: `产品代码/widget/src/types.ts`
- Modify: `产品代码/widget/src/App.tsx`
- Modify: `产品代码/widget/src/components/CompactWorkspace.tsx`
- Modify: `产品代码/widget/src/test-fixtures.ts`
- Modify: `产品代码/widget/src/CompactWorkspace.v16.test.tsx`
- Modify: `产品代码/widget/src/PhaseB.test.tsx`
- Modify: `产品代码/widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: Write failing framework-only UI tests**

Render each pre-full-deck phase and assert chapter framework is readable, discussion continues through Codex, and forbidden slide text/buttons/images are absent.

```tsx
expect(screen.getByText("为什么现在需要改变")).toBeInTheDocument();
expect(screen.getByText("目录框架讨论中")).toBeInTheDocument();
expect(screen.queryByText("页面实际文字")).not.toBeInTheDocument();
expect(screen.queryByRole("button", { name: /认可本页/ })).not.toBeInTheDocument();
expect(screen.queryByRole("button", { name: "打开内容审阅" })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run and verify failure**

```bash
npx vitest run widget/src/content-review/ContentFrameworkPanel.test.tsx widget/src/CompactWorkspace.v16.test.tsx widget/src/PhaseB.test.tsx
```

Expected: missing component/types and old Browser action expectations fail.

- [ ] **Step 3: Add exact TypeScript projection types**

Define discriminated unions:

```ts
export type ContentSidebarReviewProjection =
  | ContentFrameworkProjection
  | ContentFullDeckProjection;

export interface ContentFrameworkProjection {
  display_policy: "content-sidebar-framework";
  phase: ContentWorkflowPhase;
  project_id: string;
  revision: number;
  mission_summary: Record<string, string>;
  framework: ContentFrameworkSummary;
  next_action: "continue-framework-discussion" | "await-expansion-authorization";
}

export interface ContentFullDeckProjection {
  display_policy: "content-sidebar-full-deck";
  phase: ContentWorkflowPhase;
  project_id: string;
  revision: number;
  source_version: string;
  review_batch_id: string;
  chapters: ContentReviewChapter[];
  slides: ContentReviewSlide[];
  review_progress: ContentReviewProgress;
  batch: ContentReviewBatchProjection | null;
  previous_round: PreviousContentReviewRound | null;
}
```

Use required fields for all complete slide data; do not make actual copy/evidence/notes optional to hide invalid runtime data.

- [ ] **Step 4: Implement the typed client**

`load()` calls `get_content_sidebar_review_projection`. `saveDecision()` calls `save_content_page_decision` and returns the new snapshot/progress. `submitBatch()` calls `submit_content_review_batch`. `openEvidence()` is added in Task 14. Normalize no fields in React; allow Python/MCP errors to reach the UI with their stable codes.

- [ ] **Step 5: Route the blueprint space without Browser**

When active space is `blueprint`, `App` fetches the content projection and renders `ContentFrameworkPanel` or the full-deck document. Remove the content branch from `openReview`; retain `openReview("visual")` unchanged. After a successful decision or batch write, replace the current project snapshot and refetch the exact projection.

- [ ] **Step 6: Implement framework visual organization**

Show mission summary, core proposition, compact persuasion path, chapter rows with task/judgment/transition, structural risk, and one highest-impact question. Its only action calls `continueChat()` with a framework-specific focus. There is no framework confirmation or expansion button in the sidebar because those decisions occur in Codex with independent host confirmation.

- [ ] **Step 7: Update old UI-03 route tests**

Replace assertions expecting `open_ai_ppt_browser_review(content)` with `get_content_sidebar_review_projection`. Retain `PhaseC` visual Browser assertions unchanged. Assert no test sends a follow-up on projection load or page save.

- [ ] **Step 8: Run UI routing tests**

```bash
npx vitest run widget/src/content-review/ContentFrameworkPanel.test.tsx widget/src/CompactWorkspace.v16.test.tsx widget/src/PhaseB.test.tsx widget/src/ReviewSurfaceRouter.test.tsx widget/src/PhaseC.test.tsx
```

Expected: framework/UI-03 tests pass; visual Browser tests remain green.

- [ ] **Step 9: Commit**

```bash
git add widget/src/lib/content-review-client.ts widget/src/components/content-review/ContentFrameworkPanel.tsx widget/src/content-review/ContentFrameworkPanel.test.tsx widget/src/types.ts widget/src/App.tsx widget/src/components/CompactWorkspace.tsx widget/src/test-fixtures.ts widget/src/CompactWorkspace.v16.test.tsx widget/src/PhaseB.test.tsx widget/src/ReviewSurfaceRouter.test.tsx
git commit -m "feat: route content review into the sidebar"
```

---

### Task 13: Render the complete maximum-width deck and inline page decisions

**Files:**
- Create: `产品代码/widget/src/components/content-review/ContentReviewDocument.tsx`
- Create: `产品代码/widget/src/components/content-review/ContentReviewDirectory.tsx`
- Create: `产品代码/widget/src/components/content-review/ContentSlideSection.tsx`
- Create: `产品代码/widget/src/components/content-review/PageDecisionEditor.tsx`
- Create: `产品代码/widget/src/components/content-review/ReviewBatchFooter.tsx`
- Create: `产品代码/widget/src/content-review/ContentReviewDocument.test.tsx`
- Create: `产品代码/widget/src/content-review/PageDecisionEditor.test.tsx`
- Create: `产品代码/widget/src/content-review/ContentReviewLongDeck.test.tsx`
- Create: `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`
- Create: `产品代码/widget/src/__fixtures__/content-sidebar-review.json`
- Modify: `产品代码/widget/src/components/ProjectAssetImage.tsx`
- Modify: `产品代码/widget/src/styles.css`

- [ ] **Step 1: Write failing complete-reading tests**

Use a three-page fixture whose title, body, label, footnote, source, evidence location, treatment, gap, notes, quality, and transitions are unique strings. Assert all strings are visible in one render, no ellipsis CSS is applied to content text, and no page tab/carousel is present.

```tsx
for (const text of [
  "系统在线不等于经营闭环已经形成",
  "数据口径、流程责任和决策节奏仍然分散。",
  "来源：用户材料 A，第 3 页",
  "第 3 页，右侧流程区",
  "当前只能证明流程断点，不能证明收益幅度。",
  "去掉讲稿后仍可读懂主张、理由、证据和边界。",
  "从问题性质进入一期建设原则。",
]) {
  expect(screen.getByText(text)).toBeInTheDocument();
}
expect(screen.queryByRole("tab")).not.toBeInTheDocument();
```

- [ ] **Step 2: Write failing decision/editor tests**

Cover mutual exclusion, approved without comment, three inline editors, whitespace rejection, live `N/1200` count, 1201-character blocking, save failure draft retention, revision/source conflict draft retention, edit saved comment, and merge/delete wording.

- [ ] **Step 3: Run and verify missing components**

```bash
npx vitest run widget/src/content-review/ContentReviewDocument.test.tsx widget/src/content-review/PageDecisionEditor.test.tsx
```

Expected: imports fail.

- [ ] **Step 4: Implement the continuous document and compact directory**

The document header shows source version and `completed / total`; the directory shows compact chapter chips, optional page navigation, state labels, and `定位下一页未判断`. Use anchors `content-slide-${slide_id}` and `element.scrollIntoView({ block: "start" })`. Do not reserve a permanent directory column.

- [ ] **Step 5: Implement the complete slide section**

The top grid is:

```tsx
<div className="content-slide-main-grid">
  <section className="content-slide-copy-column">
    <PagePurpose />
    <CustomerJudgment />
    <VisibleCopy blocks={slide.visible_copy} />
  </section>
  <section className="content-slide-evidence-column">
    <EvidenceGallery items={slide.evidence_items} />
  </section>
</div>
<section className="content-slide-wide-details">
  <SpeakerNotes />
  <ReadingQuality />
  <SequenceRelationship />
  <DecisionPrompt />
  <PageDecisionEditor />
</section>
```

Use `ProjectAssetImage` for every non-empty `asset_ref`; planned gaps render a clearly labeled evidence-gap block, never a generic illustration.

- [ ] **Step 6: Implement decision saving without follow-up**

`PageDecisionEditor` saves through `client.saveDecision()`. On success it displays the full saved comment and edit action. On any failure it keeps the selected decision and text in component draft state, displays the stable error message, and marks the page incomplete. It never calls `bridge.sendFollowUp`, `updateModelContext`, feedback governance, or any Gate tool.

- [ ] **Step 7: Implement batch footer and the only follow-up trigger**

The footer disables submission whenever `remaining > 0`, a local editor is dirty, a save is pending/failed, or projection revision/source differs. It displays exact blockers such as `还剩 6 页未判断 · 2 条意见尚未保存`. After a successful batch submit, freeze all controls, update the snapshot, and call `bridge.sendFollowUp(result.follow_up_message)` exactly once. If follow-up delivery fails, the batch remains visibly submitted and offers a retry of the message only, not a second batch submit. The frozen banner states `如需改意见，请在 Codex 中撤回尚未进入修改方案的批次`; it does not mutate the submitted batch locally.

- [ ] **Step 8: Implement width, typography, and lazy image CSS**

Add:

```css
.content-review-document {
  width: 100%;
  min-width: 0;
  max-width: none;
  overflow-x: clip;
}

.content-slide-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 43fr) minmax(0, 57fr);
  gap: clamp(18px, 2.4vw, 32px);
}

@media (max-width: 899px) {
  .content-slide-main-grid { grid-template-columns: minmax(0, 1fr); }
}

.content-visible-copy,
.content-speaker-notes,
.content-evidence-meta {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  text-overflow: clip;
}
```

Do not set `line-clamp`, `white-space: nowrap`, hidden overflow, or a centered document max-width on review content. Modify `ProjectAssetImage` to observe a placeholder with `IntersectionObserver` and call `read_ai_ppt_project_asset` only when it enters a 600px root margin; after resolution, render the real image with `loading="lazy"` and `decoding="async"`. In environments without `IntersectionObserver`, load immediately so accessibility and tests do not leave permanent placeholders.

- [ ] **Step 9: Test 10/24/60 pages and responsive behavior**

Generate deterministic fixtures in test memory and assert all slide sections exist, only near-viewport images call the asset reader, the next-incomplete target is correct, and class/style contracts switch at 900px. Mock `IntersectionObserver`, move one evidence placeholder into the 600px root margin, and prove only that asset is requested. At 480, 900, 1200, and 1440 CSS-pixel containers, assert `scrollWidth <= clientWidth`.

- [ ] **Step 10: Run the complete Widget slice**

```bash
npx vitest run widget/src/content-review/ContentReviewDocument.test.tsx widget/src/content-review/PageDecisionEditor.test.tsx widget/src/content-review/ContentReviewLongDeck.test.tsx widget/src/content-review/ContentReviewResponsive.test.tsx
npm run build
```

Expected: all pass; production build succeeds.

- [ ] **Step 11: Commit**

```bash
git add widget/src/components/content-review widget/src/content-review widget/src/__fixtures__/content-sidebar-review.json widget/src/components/ProjectAssetImage.tsx widget/src/styles.css
git commit -m "feat: build full-deck sidebar review UI"
```

---

### Task 14: Narrow content Browser to read-only evidence assistance and protect G3

**Files:**
- Modify: `产品代码/mcp/review-bridge.mjs`
- Modify: `产品代码/mcp/server.mjs`
- Modify: `产品代码/tests/review-bridge.test.mjs`
- Modify: `产品代码/tests/mcp-server.test.mjs`
- Modify: `产品代码/widget/src/lib/content-review-client.ts`
- Modify: `产品代码/widget/src/components/content-review/ContentSlideSection.tsx`
- Create: `产品代码/widget/src/content-review/ContentEvidenceBrowser.test.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewApp.test.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewApp.e2e.test.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewLongDocument.test.tsx`

- [ ] **Step 1: Write failing evidence-session scope tests**

The route accepts exact `projectRoot`, `sourceVersion`, `slideId`, and `materialRef`, binds a short-lived loopback token, permits only the selected project asset/comparison projection, and has no save endpoint.

```js
assert.equal(session.scope.reviewType, "content-evidence");
assert.equal(session.scope.slideId, "S03");
assert.equal(session.scope.materialRef, "project://materials/case-a-p03.png");
assert.equal(session.capabilities.savePageDecision, false);
assert.equal(session.capabilities.saveReviewMarks, false);
```

- [ ] **Step 2: Run and verify unsupported evidence scope**

```bash
node --test tests/review-bridge.test.mjs tests/mcp-server.test.mjs
```

Expected: evidence session/tool tests fail.

- [ ] **Step 3: Implement `open_content_evidence_browser`**

Validate the material ref exists on the selected slide in the exact current source. Start a read-only session with allowed actions `view-original`, `view-crop-region`, `compare-source-and-slide`, and `compare-adjacent-slides`. Return the existing two-stage `opened` or `review-session-ready` contract. Do not route through `save_review_marks` or `save_content_page_decision`.

- [ ] **Step 4: Add the per-evidence UI action**

Show `放大查看原材料` only for actual assets. The client calls the evidence tool and presents the same honest handoff notices as visual Browser opening. Closing/opening Browser does not mutate the page decision or local editor.

- [ ] **Step 5: Remove content as the primary professional-review mode without breaking visual review**

Keep `ProfessionalReviewApp` able to render historical content review fixtures during migration, but remove content-mode entry from the sidebar and Browser mode switch for new UI-03 sessions. Preserve visual mode, exact-text marks, right-top save, G3 source binding, and 760/1000/1440 responsive behavior.

- [ ] **Step 6: Run Browser and visual regression tests**

```bash
node --test tests/review-bridge.test.mjs tests/mcp-server.test.mjs
npx vitest run widget/src/content-review/ContentEvidenceBrowser.test.tsx widget/src/ProfessionalReviewApp.test.tsx widget/src/ProfessionalReviewApp.e2e.test.tsx widget/src/ProfessionalReviewLongDocument.test.tsx widget/src/ProfessionalReviewResponsive.test.tsx
```

Expected: evidence Browser is read-only; every G3 visual review test passes unchanged or with only content-mode routing assertions updated.

- [ ] **Step 7: Commit**

```bash
git add mcp/review-bridge.mjs mcp/server.mjs tests/review-bridge.test.mjs tests/mcp-server.test.mjs widget/src/lib/content-review-client.ts widget/src/components/content-review/ContentSlideSection.tsx widget/src/content-review/ContentEvidenceBrowser.test.tsx widget/src/ProfessionalReviewApp.test.tsx widget/src/ProfessionalReviewApp.e2e.test.tsx widget/src/ProfessionalReviewLongDocument.test.tsx
git commit -m "feat: add read-only content evidence Browser"
```

---

### Task 15: Update the AI PPT Studio Skill and operational workflow

**Files:**
- Modify: `产品代码/skills/ai-ppt-studio/SKILL.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/review-and-feedback.md`
- Modify: `产品代码/skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `产品代码/tests/test_skill_workflow.py`

- [ ] **Step 1: Write failing workflow-text tests**

Assert the Skill and references name all five distinct user actions, state that framework discussion precedes page generation, prohibit single-page save from triggering governance, require a frozen batch and confirmed plan, and preserve G3 Browser.

```python
for required in (
    "confirm_content_framework",
    "authorize_full_deck_expansion",
    "save_content_page_decision",
    "submit_content_review_batch",
    "confirm_content_batch_revision_plan",
):
    self.assertIn(required, combined_skill_text)
self.assertIn("单页保存不触发 Codex", combined_skill_text)
self.assertIn("新版本全篇重新审核", combined_skill_text)
self.assertIn("G3 视觉合同仍在 Codex 内置 Browser", combined_skill_text)
```

- [ ] **Step 2: Run and verify old workflow text fails**

```bash
python3 -m unittest discover -s tests -p 'test_skill_workflow.py' -v
```

Expected: new checkpoint/tool strings are absent.

- [ ] **Step 3: Rewrite the content production order**

The Skill must instruct Codex to:

1. Confirm Mission/material identity.
2. Discuss and save framework drafts in Codex text.
3. Obtain exact framework confirmation.
4. Obtain a separate full-deck expansion authorization.
5. Produce and internally review the full complete blueprint.
6. Let the sidebar save all page decisions without starting a model turn.
7. Start one follow-up only after frozen batch submission.
8. Save a whole-deck plan and obtain its separate confirmation.
9. Permit an explicitly requested batch withdrawal only before any plan is proposed; use the new draft batch ID and never rewrite the submitted artifact.
10. Apply the plan, publish a new immutable version, and require full re-review.
11. Confirm G0 only against the final current applied review round.

State that content-stage Browser is only evidence assistance and that G3 visual Browser remains the professional-review contract.

- [ ] **Step 4: Add explicit non-bypass rules**

Document all stable content-workflow error codes, `expectedRevision` refresh behavior, confirmation identity separation, 1200-character page-comment limit, no automatic experience promotion, and preservation of the managed workspace/project boundaries.

- [ ] **Step 5: Run Skill tests and link checks**

```bash
python3 -m unittest discover -s tests -p 'test_skill_workflow.py' -v
python3 -c 'from pathlib import Path; root=Path("skills/ai-ppt-studio"); assert all((root / p).is_file() for p in ["references/content-workflow.md", "references/native-workbench.md", "references/review-and-feedback.md", "references/runtime-workflow.md"])'
```

Expected: tests pass and all referenced files resolve.

- [ ] **Step 6: Commit**

```bash
git add skills/ai-ppt-studio/SKILL.md skills/ai-ppt-studio/references/content-workflow.md skills/ai-ppt-studio/references/native-workbench.md skills/ai-ppt-studio/references/review-and-feedback.md skills/ai-ppt-studio/references/runtime-workflow.md tests/test_skill_workflow.py
git commit -m "docs: teach the framework-first content workflow"
```

---

### Task 16: Extend previews, acceptance automation, performance, and real-host evidence

**Files:**
- Modify: `产品代码/scripts/seed-v16-ui-project.py`
- Modify: `产品代码/scripts/create-widget-preview.mjs`
- Modify: `产品代码/scripts/run-v16-ui-acceptance.mjs`
- Modify: `产品代码/scripts/probe-mcp.mjs`
- Modify: `产品代码/tests/test_v16_ui_seed.py`
- Modify: `产品代码/tests/test_v16_support_scripts.py`
- Create: `产品代码/docs/validation/2026-08-14-content-sidebar-review-acceptance.md`
- Modify: `产品代码/docs/validation/2026-08-11-v16-final-acceptance.md`
- Modify: `产品代码/requirements/v1.6-evidence.json` only after genuine new proof exists
- Regenerate: `产品代码/requirements/v1.6-acceptance-ledger.json` after any evidence-index change

- [ ] **Step 1: Write failing deterministic seed tests**

The seed must produce separate projects/states for framework discussion, awaiting expansion authorization, 10-page complete review, 24-page mixed decisions, 60-page long review, save failure, source conflict, submitted batch, proposed plan, and new-version zero-decision review. All examples must be marked `deterministic-contract-fixture-not-real-project-proof`.

- [ ] **Step 2: Run and verify missing states**

```bash
python3 -m unittest discover -s tests -p 'test_v16_ui_seed.py' -v
python3 -m unittest discover -s tests -p 'test_v16_support_scripts.py' -v
```

Expected: new scenario names/fields are absent.

- [ ] **Step 3: Implement preview and screenshot scenarios**

Generate preview URLs/artifacts for maximum-width 1200 and 1440 containers plus 900 and 480 fallbacks. Capture at least:

- framework-only with no slide leakage;
- complete copy/evidence/notes page;
- inline modify, evidence, and merge/delete editors;
- 23/24 incomplete and 24/24 submit-ready states;
- submitted/frozen state;
- v2 zero-inherited-decision state;
- 60-page long document;
- existing G3 visual Browser at 760/1000/1440.

The local preview remains non-proof and must never be recorded as real Codex sidebar evidence.

- [ ] **Step 4: Extend UI acceptance assertions**

Measure `scrollWidth <= clientWidth`, document width equals available sidebar content width within padding, 43/57 columns at 900+, one column below 900, all page sections present, actual copy untruncated, image requests lazy, dirty-editor submission disabled, and exact follow-up count after submit.

- [ ] **Step 5: Extend the MCP probe without inventing approvals**

Probe tool discovery and read projections directly. For confirmation tools, verify schema/context-read readiness only; do not synthesize a user action, accept a host prompt, or mark a batch/plan/G0 confirmed. Report those rows as `awaiting-real-host-action`.

- [ ] **Step 6: Run automated acceptance**

```bash
npm run build
npm run test:node
npm run test:widget
npm run accept:v16-ui
npm run probe:mcp
python3 -m unittest discover -s tests -v
```

Expected: all automated suites pass; the acceptance output distinguishes deterministic preview evidence, automated proof, and missing real-host proof.

- [ ] **Step 7: Perform real Codex host acceptance without changing product scope**

In a managed test project under `/Users/defei/Documents/AI-PPT-Workspace`, verify with the real maximum-width sidebar:

1. framework confirmation and expansion authorization are separate native actions;
2. the full 10-page deck renders with real project asset images;
3. four page decisions persist across sidebar close/reopen;
4. saving a page starts no Codex turn;
5. only the completed batch starts one follow-up;
6. Codex proposes a whole-deck plan before any change set;
7. plan confirmation is separate from G0;
8. a new blueprint shows zero completed pages;
9. final applied current-source batch unlocks G0;
10. G3 visual Browser remains usable.

Do not mark this step passed from local HTML, mocked adapters, deterministic fixtures, or a historical project that lacks the new action lineage.

- [ ] **Step 8: Record evidence and strict ledger status**

Write exact commands, versions, project ID, source refs, revisions, screenshot paths, outcome, unresolved host gaps, and proof identity to the new validation record. Add proof refs to `requirements/v1.6-evidence.json` only when files are content-addressed and all required evidence kinds genuinely exist. Regenerate the ledger and report its real passed count; do not retain `37` if valid new proof changes it, and do not increase it from preview-only evidence.

- [ ] **Step 9: Commit automation and evidence separately**

```bash
git add scripts/seed-v16-ui-project.py scripts/create-widget-preview.mjs scripts/run-v16-ui-acceptance.mjs scripts/probe-mcp.mjs tests/test_v16_ui_seed.py tests/test_v16_support_scripts.py
git commit -m "test: cover full-deck sidebar review"
git add docs/validation/2026-08-14-content-sidebar-review-acceptance.md docs/validation/2026-08-11-v16-final-acceptance.md requirements/v1.6-evidence.json requirements/v1.6-acceptance-ledger.json
git commit -m "docs: record content sidebar acceptance"
```

Include the evidence/ledger files in the second commit only if real evidence was actually registered; otherwise commit only the validation records with their explicit unproven rows.

---

### Task 17: Final specification coverage and release regression

**Files:**
- Verify all files changed by Tasks 1–16
- Modify only a file whose failed assertion demonstrates an actual defect

- [ ] **Step 1: Run the complete quality suite from `产品代码/`**

```bash
npm run quality
python3 -m unittest discover -s tests -v
python3 scripts/build_acceptance_ledger.py
git diff --check
```

Expected: build, Node tests, Widget tests, MCP probe, Python tests, ledger regeneration, and whitespace check all pass.

- [ ] **Step 2: Run the 24-point approved-spec coverage audit**

Create a temporary checklist from section 15 of `docs/superpowers/specs/2026-08-14-content-blueprint-sidebar-review-design.md` and map every numbered criterion to at least one automated test plus any required real-host/viewport proof. The mapping must explicitly name criteria 1–24; no criterion may be grouped under a generic catch-all row.

- [ ] **Step 3: Scan for plan/implementation gaps and forbidden placeholders**

Run:

```bash
rg -n 'T[B]D|T[O]DO|implement later|similar to Task|appropriate error handling|handle edge cases' src mcp widget tests skills scripts docs requirements
rg -n 'open-content-review|打开内容审阅|360–480px|pending-governance' 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md src mcp widget skills
```

Expected: the first scan has no hits in new implementation content. The second scan has only explicitly labeled historical compatibility, G3 visual Browser, or non-UI-03 contexts; no current UI-03 primary action or page-decision path uses those old contracts.

- [ ] **Step 4: Verify type and operation-name consistency**

Run exact-name searches for all public Python operations, MCP tool names, TypeScript method calls, action scopes, artifact heads, decision enums, batch statuses, and stable error codes. Each producer name must have at least one consumer and one test; there must be no camel/snake mismatch such as `mergeOrDelete` in persisted artifacts.

- [ ] **Step 5: Verify repository boundaries and staged paths**

```bash
git status --short
git diff --cached --name-only
```

Expected: no source/runtime data was written under `/Users/defei/Documents/AI-PPT-Workspace` into Git, no file in `../PPT  web app ` changed, and unrelated pre-existing worktree changes are not staged.

- [ ] **Step 6: Request code review before integration**

Use `superpowers:requesting-code-review` against the full feature diff. Review must focus on authorization replay, stale-source/revision races, frozen-batch immutability, no inherited decisions, G0 lineage, full-text/material completeness, page-save silence, maximum-width layout, and G3 regression.

- [ ] **Step 7: Apply review findings and rerun affected plus full suites**

For every accepted finding, first add or tighten a failing regression test, implement the smallest correction, run the focused test, then rerun Step 1. Record rejected findings with concrete evidence in the review handoff; do not accept suggestions that weaken the confirmed product contract.

- [ ] **Step 8: Commit final verified corrections**

```bash
git diff --name-only
git commit -m "fix: close content review acceptance gaps"
```

After `git diff --name-only`, stage each exact verified-fix path one at a time with `git add`, excluding unrelated pre-existing changes, and inspect `git diff --cached --name-only` before running the shown commit. Skip this commit when review finds no defect. Do not create an empty commit.

## 4. Approved-spec coverage self-review

| Acceptance criterion | Implemented and verified by |
|---|---|
| 1. No page content before framework confirmation | Tasks 2, 3, 9, 12; Python no-leak and React absence tests |
| 2. Framework confirmation and expansion authorization are separate | Tasks 3, 4, 10, 11; distinct scope/challenge tests |
| 3. Expansion, batch, plan, and G0 actions cannot be reused | Tasks 3, 6–8, 11; cross-scope HMAC rejection tests |
| 4. Every current slide renders once in final order | Tasks 2, 9, 13; source/projection equality and long-deck tests |
| 5. Actual visible copy is complete and untruncated | Tasks 2, 9, 13; byte-for-byte fields, DOM text, and CSS scans |
| 6. Goal, judgment, material, source/use, gap, notes, quality, relationship all render | Tasks 2, 9, 13; complete fixture field assertions |
| 7. Slide reads independently without notes | Tasks 2 and 4; hard content-contract/acceptance rejection |
| 8. Maximum width, 43/57, one-column fallback, no overflow | Tasks 1, 13, 16; 480/900/1200/1440 measurements |
| 9. Four exclusive decisions and three inline editors | Tasks 5 and 13; decision-domain and interaction tests |
| 10. Blank/failed/unsaved comment stays incomplete without losing draft | Tasks 5, 10, 13; error and draft-retention tests |
| 11. Page save triggers no Codex/governance/change set/source change | Tasks 5, 10, 11, 13; head/event and mock-call assertions |
| 12. Directory locates the next incomplete page with correct states | Tasks 5, 9, 13; progress and anchor-navigation tests |
| 13. Batch submit remains disabled until every hard condition passes | Tasks 6 and 13; completion/blocker tests |
| 14. Submitted batch freezes decisions with version/snapshot/count/action identity | Tasks 5, 6, 10, 11; immutable batch tests |
| 15. Codex proposes a whole-deck plan before a new blueprint | Tasks 7, 10, 11, 15; plan-first lineage tests |
| 16. Plan covers direct, cross-page, merge/delete, evidence, page count, preserve, conflicts, re-review | Task 7; complete plan-contract validation |
| 17. Unconfirmed plan cannot write change set or blueprint | Tasks 7 and 8; Python precondition tests |
| 18. Confirmed plan creates immutable new version and preserves history | Tasks 7 and 8; supersession/lineage tests |
| 19. New version inherits zero decisions but may show previous results | Tasks 8, 9, 13; fresh-set/projection tests |
| 20. Batch/plan are not G0; final current review is required | Tasks 6–8 and 11; Gate-state and G0-context tests |
| 21. Complete content review works inside the maximum-width sidebar | Tasks 9, 12, 13, 16; full interaction and host acceptance |
| 22. Browser enlarges/compares evidence without a second decision store | Task 14; read-only session and no-save tests |
| 23. G3 visual Browser remains unchanged | Tasks 8, 12, 14, 16; visual Browser regression suite |
| 24. Chat/sidebar/Browser share project revision and source truth | Tasks 9–14 and 16; projection, conflict, bridge, and remount tests |

## 5. Completion definition

The feature is complete only when all of the following are true:

- the four formal baselines and checked-in ledger express the approved contract;
- no page content exists before exact framework confirmation and separate expansion authorization;
- every reviewable page contains complete visible copy, real material or an explicit gap, source/use/treatment identity, full notes, reading-quality result, and sequence relationship;
- page saves are revision-safe, survive remount, and trigger no Codex turn/governance/change set;
- incomplete or dirty reviews cannot submit;
- submitted batches are immutable and version-bound;
- a pre-plan withdrawal preserves the submitted batch and creates a new auditable draft batch rather than editing history;
- Codex saves a whole-deck plan before changes, and the user confirms that plan with a separate identity;
- new blueprints are immutable and start with zero inherited decisions;
- G0 requires the final applied review round for the current exact blueprint;
- the maximum-width sidebar renders the whole deck continuously with no truncation or horizontal overflow;
- content Browser is evidence assistance only, while G3 visual Browser behavior remains verified;
- automated proof, deterministic preview, and real-host evidence are never conflated;
- no unrelated user worktree changes are staged or committed.
