# Retired Legacy G0 Contract Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Remove the unreachable legacy-credential-upgrade public workflow promise and dead payload branch while retaining current fail-closed, current-evidence Gate confirmation.

**Architecture:** Current G0/G3/G4 services remain the only Gate authorities. GateConfirmationPolicy may remain as a scoped compatibility entry, but emits only the current confirm-gate payload and never inherits a historical Gate. Historical projects remain read-only or require a separately authorized future migration.

**Tech Stack:** Python 3 unittest, Markdown Skill instructions, Git.

---

## Scope and rollback boundary

This is a separate cleanup commit after F2. It does not restore deleted v1.6 services, change current Gate evidence rules, convert old confirmations, merge, push, install, or publish.

### Task 1: Verify the failing public-contract assertion

**Files:**

- Test: tests/test_v22_source_shape.py
- Inspect: skills/ai-ppt-studio/SKILL.md
- Inspect: skills/ai-ppt-studio/references/runtime-workflow.md
- Inspect: src/ai_ppt_studio/application/gate_confirmation.py

- [ ] **Step 1: Keep the source-shape assertion**

    skill_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    self.assertNotIn("legacy-credential-upgrade", skill_text)
    self.assertNotIn("legacy_confirmation_ref", skill_text)

- [ ] **Step 2: Run RED**

    cd 产品代码
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest -v tests.test_v22_source_shape

Expected: failure because public instructions and Python compatibility code still contain retired legacy names.

### Task 2: Remove the unreachable legacy workflow

**Files:**

- Modify: skills/ai-ppt-studio/SKILL.md
- Modify: skills/ai-ppt-studio/references/runtime-workflow.md
- Modify: src/ai_ppt_studio/application/gate_confirmation.py
- Test: tests/test_v22_source_shape.py

- [ ] **Step 1: Delete public legacy instructions**

Remove every instruction to request, submit, or recover through legacy-credential-upgrade. Preserve current-source, current-revision, single-use, trusted-host G0 confirmation.

- [ ] **Step 2: Delete dead Python payload data and branch**

GateConfirmationPolicy.context() and confirmation_payload() must no longer emit or inspect:

    legacy_confirmation_ref
    supersedes_confirmation_ref
    confirmation_mode == legacy-credential-upgrade

Keep current scoped payload construction and delegation to owning G0/G3/G4 services.

- [ ] **Step 3: Run focused Gate and source-shape tests GREEN**

    cd 产品代码
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest -v         tests.test_v22_source_shape         tests.test_v22_gate_command_semantics

Expected: all selected tests pass.

### Task 3: Verify and commit the independent cleanup

- [ ] **Step 1: Verify retired terms and whitespace**

    cd 产品代码
    rg -n 'legacy-credential-upgrade|legacy_confirmation_ref'       skills/ai-ppt-studio/SKILL.md       skills/ai-ppt-studio/references/runtime-workflow.md       src/ai_ppt_studio/application/gate_confirmation.py
    git diff --check

Expected: rg has zero matches and git diff --check succeeds.

- [ ] **Step 2: Commit**

Stage only this plan, the two Skill files, gate_confirmation.py, and the source-shape test, then run:

    git commit -m "chore: remove retired legacy g0 workflow"

Expected: one local commit after F2; no merge, push, install, or publish.
