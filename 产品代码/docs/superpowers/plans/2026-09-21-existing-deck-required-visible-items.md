# Existing Deck Required Visible Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an existing-deck revision request bind selected source text identities that CRS must render as independent visible structures, so an internally rejected design can be corrected without changing copy, common rules, materials, or the native reconstruction stage.

**Architecture:** Add one optional `requiredVisibleItemIds` field to the existing-deck request tool. The Python Runtime validates that every ID is a unique non-title item on the same source page, canonicalizes them in source order, stores the identities in the request, and derives a bounded provider instruction from the corresponding exact source text. The field is immutable inside the request hash and does not create free-form prompting.

**Tech Stack:** Python 3 Runtime, Node MCP with Zod, Node test runner, Python unittest.

**Spec:** Parent baselines §1.8/§1.7 and the current existing-deck source-bound request contract.

## Global Constraints

- Keep `common_rules` immutable for the whole deck.
- Do not add free-form revision text or new customer facts.
- Required items must resolve to exact current source-page visible-copy identities and cannot include the title.
- The generated image remains the visual authority; native reconstruction cannot invent missing modules.
- Existing requests without required items remain byte-compatible in behavior.

---

### Task 1: Freeze the behavior in baselines and tests

**Files:**
- Modify: `../../00-唯一研发基线索引-v1.0.md`
- Modify: `../../01-产品需求基线-v1.0.md`
- Modify: `../../02-系统详细设计-v1.0.md`
- Modify: `tests/test_existing_deck_selection.py`
- Modify: `tests/optimization-mcp.test.mjs`

- [ ] Add the identity-bound revision requirement to the existing-deck baseline sections.
- [ ] Add a Python test proving exact source IDs become mandatory independent structures in `page_goal`.
- [ ] Add a Python test proving unknown/title/duplicate IDs fail before a Runtime write.
- [ ] Add an MCP test proving `requiredVisibleItemIds` is converted to `required_visible_item_ids`.
- [ ] Run the focused tests and confirm they fail because the field is unsupported.

### Task 2: Implement the minimal request contract

**Files:**
- Modify: `mcp/tools/optimization-tools.mjs`
- Modify: `src/ai_ppt_studio/application/optimization_bridge.py`
- Modify: `src/ai_ppt_studio/application/image_led_selection.py`
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`

- [ ] Add the optional bounded public array.
- [ ] Pass it through the bridge.
- [ ] Validate and canonicalize source IDs in source order.
- [ ] Store the canonical identities and derive the provider instruction from exact source text.
- [ ] Revalidate the identities whenever a request is loaded.
- [ ] Document that revisions use identities, not free-form prompt changes.
- [ ] Run focused Python and Node tests until green.

### Task 3: Package, load, and exercise the current host

**Files:**
- Modify only generated candidate package/install outputs required by the existing C3 installer.

- [ ] Run the existing focused and contract consistency suites.
- [ ] Build/install the candidate plugin through the existing C3 installer path.
- [ ] Restart only the loaded AI PPT Studio MCP process if it still points to an obsolete package.
- [ ] Confirm current-host tool schema and snapshot/preflight.
- [ ] Supersede P12 r3, register P12 r4 with the three exact source item IDs, execute once, and inspect the result.
