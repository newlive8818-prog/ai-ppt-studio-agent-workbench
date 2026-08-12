# v1.6 Slice 04 Delivery, Four-Target G4, and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the authoritative G3-to-G4 delivery chain for a complete native editable PPTX, per-slide and deck hard gates, four formal desktop target exports for one exact hash, chat delivery, user acceptance, and recoverable repair.

**Architecture:** `DeliveryService` owns ordered schema 3 delivery commands but cannot mutate Gates directly; `GateEvaluator` resolves current immutable artifacts before issuing G4 mutations. The existing rich `TargetRenderEvidence` contract is reused for full-deck evidence, while build, QA, package, repair, and chat receipt objects remain content-addressed project artifacts. Automated tests prove enforcement only and never claim that simulated captures are real desktop compatibility evidence.

**Tech Stack:** Python standard library, `unittest`, JSON/SHA-256, existing Node MCP thin adapter, existing React projections.

---

## File map

- `src/ai_ppt_studio/domains/delivery/contracts.py`: complete build, slide/deck QA, repair, delivery package, and chat receipt validators.
- `src/ai_ppt_studio/application/delivery_service.py`: revision-safe G3-to-G4 command facade and target evidence registration.
- `src/ai_ppt_studio/application/gate_evaluator.py`: delivery-ready, chat-user-reviewable, and chat-only G4 evaluation.
- `src/ai_ppt_studio/application/v16_bridge.py`: existing public artifact, chat delivery, delivery projection, and G4 routing.
- `tests/v16_delivery_fixtures.py`: valid complete-deck builders and simulated contract fixtures explicitly labeled non-real.
- `tests/test_v16_delivery_contracts.py`: complete PPTX and editability rules.
- `tests/test_v16_delivery_g4.py`: page/deck hard gates, four-target matrix, chat receipt, and G4.
- `tests/test_v16_delivery_recovery.py`: failed attempts, last-valid build, stale evidence, and recovery.
- `tests/test_v16_delivery_bridge.py`: existing MCP public operations against schema 3.

### Task 1: Complete native-editable PresentationBuild

**Files:**
- Create: `src/ai_ppt_studio/domains/delivery/__init__.py`
- Create: `src/ai_ppt_studio/domains/delivery/contracts.py`
- Create: `src/ai_ppt_studio/application/delivery_service.py`
- Create: `tests/v16_delivery_fixtures.py`
- Create: `tests/test_v16_delivery_contracts.py`

- [x] **Step 1: Write failing build tests**

Create a project with G3 passed and assert the wished-for API below rejects early G3, a non-current visual contract, route A/C, a slide count/order that differs from the frozen contract, a whole-slide bitmap, missing native-editability evidence, a source PPTX hash mismatch, or preflight evidence presented as target evidence.

```python
build_ref = delivery.register_build(
    "build-full-deck",
    revision,
    {
        "visual_contract_ref": visual_contract_ref,
        "production_route": "strict-B",
        "source_pptx_ref": final_pptx_ref,
        "pptx_sha256": sha256,
        "slide_ids": ["s1", "s2"],
        "native_editability_evidence_refs": [editability_ref],
        "preflight_render_refs": [preflight_ref],
        "preflight_identity": "preflight-only",
        "whole_slide_bitmap": False,
        "semantic_objects_native": True,
        "image_assets_independent": True,
        "tool_name": "Codex Presentations",
        "tool_version": "presentations/test-contract-version",
    },
)
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_delivery_contracts -v`

Expected: FAIL because `DeliveryService` and delivery validators do not exist.

- [x] **Step 3: Implement complete build validation**

Implement `validate_presentation_build(payload, visual_contract)` so it requires `G3=passed`, exact current visual-contract lineage, `strict-B`, every final slide once in final order, one `final-pptx` artifact whose declared lowercase SHA-256 matches, non-empty editability and preflight refs, `preflight_identity="preflight-only"`, `whole_slide_bitmap=False`, native semantic objects, independent optional bitmaps, and explicit Codex Presentations identity/version. Persist it as the `delivery/build` head with kind `presentation-build`.

- [x] **Step 4: Run GREEN and regress G3**

Run: `python3 -m unittest tests.test_v16_delivery_contracts tests.test_v16_visual_review -v`

Expected: all tests PASS; registering a build leaves `G4=open`.

### Task 2: Per-slide four gates, deck rhythm, and directed repair

**Files:**
- Modify: `src/ai_ppt_studio/domains/delivery/contracts.py`
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Test: `tests/test_v16_delivery_g4.py`
- Test: `tests/test_v16_delivery_recovery.py`

- [x] **Step 1: Write failing QA and repair tests**

Assert one current build requires exactly one QA record per slide. Each record must bind the current build/hash and contain binary semantic, aesthetic, engineering, and preflight results with real artifact references. Any failure requires a reason and directed repair instruction and prevents deck acceptance. A deck review must cover sequence, rhythm, page-family variation, repetition, density, footer/pagination, and overall coherence without numeric scores.

```python
qa_ref = delivery.register_slide_qa(
    "qa-s1",
    revision,
    {
        "build_ref": build_ref,
        "pptx_sha256": sha256,
        "slide_id": "s1",
        "semantic_result": "passed",
        "aesthetic_result": "passed",
        "engineering_result": "passed",
        "preflight_result": "passed",
        "evidence_refs": [render_ref, object_report_ref],
        "reviewer_roles": ["独立审美审查智能体", "PPT 工程审查智能体"],
        "overall_result": "passed",
    },
)
```

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_delivery_g4 tests.test_v16_delivery_recovery -v`

Expected: FAIL because slide QA, deck QA, failed attempt, and repair APIs are absent.

- [x] **Step 3: Implement binary QA and recovery artifacts**

Persist slide heads at `delivery/qa/slide/<slide_id>`, the deck result at `delivery/qa/deck`, failed build attempts at `delivery/failed-attempt`, and repair instructions at `delivery/repair`. Reject `score`, `rating`, `average`, `weight`, `vote`, and `conditional-pass`. A failed attempt must reference `last_valid_build_ref`; it never replaces `delivery/build`. A successful replacement build records the prior build in `last_valid_build_ref` and makes all old QA/target evidence stale by lineage, without deleting it.

- [x] **Step 4: Run GREEN**

Run the two focused modules; expected all tests PASS and failed commands leave revision and valid heads unchanged except for explicit failed-attempt/repair records.

### Task 3: Full-deck four-target evidence and internal delivery-ready G4

**Files:**
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `src/ai_ppt_studio/domains/presentation/targets.py`
- Test: `tests/test_v16_delivery_g4.py`

- [x] **Step 1: Write failing same-hash G4 tests**

Register full-deck rich target evidence for `macos-powerpoint`, `macos-wps`, `windows-powerpoint`, and `windows-wps`. Require every target to bind the current `presentation-build`, final PPTX, exact hash, every final slide, correct OS/application pair, versions, fonts, substitution plan, exports, page images, executor/time/tool, and per-slide semantic/aesthetic/engineering/target-render pass results. Assert missing, failed, stale, duplicate, preflight-only, mixed-hash, partial-page, or anchor-stage evidence blocks delivery-ready without a revision increment.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_v16_delivery_g4 -v`

Expected: the wished-for `register_target_render_evidence(... stage="G4")` and `finalize_delivery` paths are missing.

- [x] **Step 3: Implement G4 target registration and delivery-ready evaluation**

Reuse `TargetRenderEvidence.from_payload`, resolve every referenced artifact, require `stage="G4"` plus `presentation_build_ref`, and persist four target heads at `delivery/target-evidence/G4/<target-id>`. `GateEvaluator.delivery_ready()` must resolve the current build, every current slide QA head, deck QA, and four full-deck targets; verify one exact hash and all-pass binary results; then issue only `G4=delivery-ready`.

- [x] **Step 4: Run GREEN**

Expected: G4 remains blocked until every full-deck contract is current and passed; a complete simulated matrix changes only the internal state to `delivery-ready`, not user acceptance.

### Task 4: Delivery package, chat send, and chat-only G4 confirmation

**Files:**
- Modify: `src/ai_ppt_studio/domains/delivery/contracts.py`
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Test: `tests/test_v16_delivery_g4.py`

- [x] **Step 1: Write failing package/chat tests**

Require a delivery package with the current build/PPTX/hash, preview refs, source manifest, font/platform report, QA report, and all four target identities. A chat receipt must use `delivery_type="pptx"`, a `chat://message/...` send message, `send_status="sent|failed"`, current package/build refs, hash, timestamp, and retry identity. Failed sends preserve the passing build and keep `G4=delivery-ready`; successful sends produce `G4=user-reviewable`. Only a separate explicit user acceptance chat message can pass G4.

- [x] **Step 2: Run RED**

Expected: package, receipt, and `confirm_g4` APIs do not exist.

- [x] **Step 3: Implement package/chat Gate separation**

Persist `delivery/package` and `chat-delivery/pptx`. `GateEvaluator.delivery_user_reviewable()` must require `G4=delivery-ready` and a sent current receipt. `GateEvaluator.confirm_g4()` must require `G4=user-reviewable`, the current package/receipt, and a distinct `chat://message/...` user outcome stored in `g4-confirmation`; it then issues `G4=passed`. File download, message read, review save, or send success alone cannot pass G4.

- [x] **Step 4: Run GREEN**

Run the G4 suite; expected all tests PASS and no implicit user confirmation path exists.

### Task 5: Hash invalidation, targeted retry, and last-valid recovery

**Files:**
- Modify: `src/ai_ppt_studio/application/delivery_service.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Test: `tests/test_v16_delivery_recovery.py`

- [x] **Step 1: Write failing invalidation and recovery tests**

Assert a new PPTX hash makes all prior slide/deck/target/package/chat evidence stale, even if those artifact heads still exist for audit. Changing only one target environment while the PPTX hash is unchanged permits replacing only that target head, but the full matrix must be re-evaluated. Assert idempotent retry, stale revision, tampered artifact, and failed chat send never destroy the last valid build or duplicate events.

- [x] **Step 2: Run RED**

Expected: stale evidence is still accepted or recovery operations are absent.

- [x] **Step 3: Implement lineage-based invalidation and restore**

Every evaluator comparison must include both `build_ref` and `pptx_sha256`. `restore_build` creates a new `presentation-build` artifact with `restored_from`, `last_valid_build_ref`, and the same verified payload; it never mutates history. Reopening G4 locks only downstream chat confirmation and preserves all immutable evidence for inspection.

- [x] **Step 4: Run GREEN**

Expected: recovery tests PASS and current state always points to a verifiable build or an explicit no-valid-build condition.

### Task 6: Existing public MCP bridge coverage

**Files:**
- Modify: `src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Test: `tests/test_v16_delivery_bridge.py`
- Test: `tests/mcp-server.test.mjs`

- [x] **Step 1: Write failing bridge tests**

Exercise existing `commit-artifact`, `get-delivery-status-projection`, `record-chat-delivery`, `confirm-gate`, and `reopen-scope` operations on a schema 3 project. Assert no new v16 tool name is exposed and unsupported legacy writes fail explicitly.

- [x] **Step 2: Run RED**

Expected: delivery operations are unsupported by `dispatch_v16`.

- [x] **Step 3: Implement thin routing and compact delivery projection**

Map public payload names to `DeliveryService`; keep validation, artifact kinds, roles, Gate decisions, target identities, and hash rules in Python services/evaluators. Return only phase, completed/total slides, four internal gates, highest blocker, four target statuses/hash identity, and chat send status from the compact projection—never contact sheets, page images, or a duplicate download area.

- [x] **Step 4: Run GREEN**

Run Python bridge and Node MCP tests; expected all public names and input schemas remain stable.

### Task 7: Slice verification and evidence labeling

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-v16-slice-04-delivery-g4.md`

- [x] **Step 1: Run focused Slice 04 tests**

Run all delivery modules with `-v`; expected zero failures.

- [x] **Step 2: Run full regressions**

Run: `python3 -m unittest discover -s tests -v` and `npm test`.

Expected: Python, Node, Widget, and build suites all pass.

- [x] **Step 3: Verify ledger and hygiene**

Run: `python3 scripts/build_acceptance_ledger.py`, `git diff --check`, and inspect generated build residue.

Expected: exactly 104 deterministic requirements and no whitespace errors. Build residue is recorded for Slice 07 cleanup if not yet fixed.

- [x] **Step 4: Mark only contract enforcement proven**

Check off implemented/tested contract tasks, but keep all four real desktop evidence rows and the real-project G4 outcome unproven until actual macOS PowerPoint, macOS WPS, Windows PowerPoint, and Windows WPS exports for the same final PPTX hash are present.

No intermediate commits are made in this plan because the user explicitly requested one unified commit only after the full v1.6 acceptance scope is complete.

## Verification evidence (2026-08-09)

- Focused Slice 04 Python suite: 11 tests passed.
- Full Python regression: 168 tests passed.
- Node MCP suite: 11 tests passed.
- Widget suite: 13 tests passed across 6 files.
- Acceptance ledger generator: exactly 104 deterministic requirements.
- `git diff --check`: passed.
- Contract enforcement is proven by automated tests. The four real desktop target rows and real-project G4 outcome remain unproven until one current PPTX hash has genuine macOS PowerPoint, macOS WPS, Windows PowerPoint, and Windows WPS export evidence.
- Existing `widget/.dist-raw-*` build residue remains explicitly deferred to Slice 07 packaging cleanup and must not be included in the final commit.
