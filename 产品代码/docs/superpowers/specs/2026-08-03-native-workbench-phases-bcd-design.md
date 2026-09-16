# AI PPT Studio Native Workbench Phases B–D Design

**Date:** 2026-08-03  
**Status:** Approved for implementation by the user's instruction to complete Phases B–D through acceptance  
**Authority:** `00-唯一研发基线索引-v1.0.md`, `01-产品需求基线-v1.0.md`, `02-系统详细设计-v1.0.md`, `03-UI设计与交互规范-v1.0.md`

## 1. Objective

Extend the installed Phase A Codex plugin into one end-to-end, project-backed AI PPT workbench that can:

1. accept user-provided files, text, images, and links;
2. expose AI classification and material findings with provenance;
3. display and confirm a narrative and per-slide content blueprint before visual work;
4. request Image 2 concept exploration through Codex and compare real concept artifacts;
5. expose editable implementation constraints, engineering evidence, Visual Contract, and Scene Graph;
6. request Presentations production through Codex, display real renders and QA evidence, and gate delivery;
7. persist every intent, artifact, gate, decision, version, and recovery state in the managed project.

The Widget remains a governed decision surface. It does not become a browser PPT editor, a hidden model runtime, or a second PPTX compiler.

## 2. Chosen Architecture

Use the existing Python runtime as the only domain writer, the Node MCP server as the protocol layer, and the responsive React Widget as a projection and intent surface.

```text
Widget action
  -> MCP tool with expectedRevision
  -> Python WorkbenchStore / AgentTaskStore / ArtifactStore / StateStore
  -> atomic project write + event + new revision
  -> refreshed all-space projection
  -> optional updateModelContext + sendMessage to Codex
  -> Codex uses Image 2 or Presentations
  -> structured artifact/result committed through the same runtime
```

Project files remain authoritative. Browser memory may hold selected rows, expanded nodes, and decoded thumbnails only; it never owns business state.

## 3. Runtime Units

### 3.1 SpaceProjectionBuilder

Creates compact, sanitized projections for `materials`, `blueprint`, `visual`, and `delivery`. It reads source records, latest immutable artifacts, gate state, decisions, active task, render evidence, and delivery files. It never invents completion or classification.

### 3.2 AgentTaskStore and ContextCompiler

`request-agent-action` creates an immutable task request, a reproducible context pack, and `state/active-task.json`. Supported actions are:

- `classify-materials`
- `generate-blueprint`
- `revise-blueprint`
- `explore-concepts`
- `build-engineering-samples`
- `freeze-visual-contract`
- `build-pptx`
- `qa-render`
- `repair-pptx`

The result includes a concise follow-up message that tells Codex which project, revision, context pack, output artifact, and tool route to use. Image 2 and Presentations are not invoked inside the MCP process.

### 3.3 Workbench write service

The existing `WorkbenchStore` lock and revision remain the project concurrency boundary. New writes are:

- add material;
- request Agent action;
- commit versioned artifact;
- confirm gate;
- reopen scope.

Each write validates `expectedRevision`, performs all domain writes, appends events, increments the workbench revision exactly once, and returns a fresh snapshot. A conflict has no partial writes.

### 3.4 Project asset reader

An app-only MCP tool reads images or text evidence from a resolved path inside the selected managed project. It returns MIME type plus base64 data. It rejects traversal, protected roots, directories, oversized files, and unsupported types. PPTX download remains represented by an absolute managed-project path because the Codex host owns local file opening.

## 4. Data Contracts

### 4.1 Material findings artifact

Add `material-findings` as a versioned artifact under `cognition/material-findings/`:

```json
{
  "summary": "string",
  "findings": [
    {
      "finding_id": "string",
      "finding_type": "fact|case|data|screenshot|diagram|conflict|gap",
      "content": "string",
      "source_ref": "sources/<id>.json",
      "locator": "page/paragraph/region or supplied context",
      "fact_status": "source-fact|ai-connective|needs-confirmation",
      "purposes": ["customer-needs", "solution", "case", "evidence"]
    }
  ],
  "source_assignments": [
    {
      "source_id": "string",
      "purposes": ["string"],
      "summary": "string",
      "status": "usable|partial|conflict|unreadable"
    }
  ],
  "conflicts": [],
  "gaps": []
}
```

Without this artifact, sources are shown as received and `等待 AI 提炼`; no fake purpose labels are generated.

### 4.2 Engineering samples artifact

Add `engineering-samples` as a versioned artifact under `visual/engineering-samples/`:

```json
{
  "summary": "string",
  "samples": [
    {
      "sample_id": "string",
      "slide_refs": ["slide-id"],
      "render_ref": "renders/sample.png",
      "native_element_ratio": 0.92,
      "editable": true,
      "notes": "string"
    }
  ],
  "native_coverage": {
    "text": true,
    "shape": true,
    "chart": true,
    "image_crop": true,
    "whole_slide_bitmap": false
  },
  "qa_status": "passed|partial|failed"
}
```

G2 reads this artifact directly. A concept image, screenshot, or existence of a PPTX alone is not engineering proof.

### 4.3 Space projections

`ProjectSnapshot.space_projections` contains:

- `materials`: counts, source rows, finding summary, conflicts, gaps, action state;
- `blueprint`: narrative summary, chapters, slide rows, selected-slide details, source coverage, blockers;
- `visual`: Visual Brief, concept directions, sample asset refs, selected direction, feasibility evidence, Visual Contract summary, Scene Graph coverage;
- `delivery`: G0–G4 strip, build summary, render refs, QA issues, editability evidence, delivery files, acceptance state.

Only summaries enter model-visible structured content. Binary data and long notes are loaded on demand.

### 4.4 Agent task

Tasks live under `tasks/<task-id>.json`; contexts under `context/<task-id>.json`; `state/active-task.json` points to the latest active task. Completed, failed, cancelled, and partial tasks remain immutable evidence.

## 5. MCP Contract

Retain Phase A tools and add:

| Tool | Purpose |
|---|---|
| `add_ai_ppt_material` | Add one text, URL, or base64 file from the user and request classification |
| `request_ai_ppt_agent_action` | Persist a governed Agent task and return Codex follow-up/context |
| `commit_ai_ppt_artifact` | Save one validated immutable artifact and complete the producing task |
| `confirm_ai_ppt_gate` | Pass G0–G4 only when required project evidence exists |
| `reopen_ai_ppt_scope` | Reopen one gate with a reason and mark downstream work affected |
| `read_ai_ppt_project_asset` | App-only, read one project-contained image/text asset |

All writes require `expectedRevision`. Tool errors use stable codes including `REVISION_CONFLICT`, `GATE_BLOCKED`, `SOURCE_UNREADABLE`, and `VALIDATION_ERROR`.

## 6. Gate Evidence Rules

- **G0:** confirmed Mission and nonempty Content Blueprint with source/material references.
- **G1:** Concept Set with at least two structural directions and a recorded human concept decision.
- **G2:** an `engineering-samples` artifact exists, declares at least one existing rendered sample, records native element coverage, sets `whole_slide_bitmap=false`, and has `qa_status=passed`.
- **G3:** Visual Contract and Slide Scene Graph both exist.
- **G4:** Delivery artifact says `qa_status=passed`, declared PPTX exists, every declared render exists, and whole-slide bitmap is not declared as the implementation route.

The runtime checks evidence, but only the user can pass a gate. Reopen creates a new revision and never erases history.

## 7. Page Designs

### 7.1 Materials workspace

P0 order: material conclusion → unified input → dense source list → findings/conflicts/gaps → one action. Files use the host file picker and are transferred as bounded base64 payloads. Text and links can be supplied directly. The page states that AI only uses user-provided material and does not search externally.

### 7.2 Content blueprint

P0 order: readiness conclusion → narrative thesis → chapter tree + dense slide table → selected slide inspector → G0 decision. Before G0, no color, layout, image treatment, or visual score appears. Complex revisions create a `revise-blueprint` Agent task and continue in Codex.

### 7.3 Visual workspace

P0 order: visual strategy → structurally distinct directions → shared sample/engineering evidence → implementation contract → current gate action. Concept assets are labelled `Image 2 视觉构想`; rendered editable samples are labelled `PPTX 工程样张`. Direction selection is stored as a human decision before Codex continues.

### 7.4 Delivery workspace

P0 order: delivery conclusion → G0–G4 strip → contact sheet → selected render → QA/editability inspector → delivery files → one acceptance action. The page never equates file existence with delivery success.

### 7.5 Responsive behavior

At 360–480px each space becomes a vertical decision thread, hides dense columns, keeps conclusion and primary action visible, and loads at most one selected preview. At 1080px and above, the stable navigation, main surface, and optional inspector are shown.

## 8. Error and Recovery

- Source parse unavailable: preserve source row, mark it `等待 AI 读取`, offer retry/Codex action.
- Image 2 unavailable: preserve task and last concept set; allow retry or engineering-first exploration.
- Presentations failure: preserve last valid build and completed renders; show failed stage and retry action.
- Host bridge unavailable: persist intent first, then show `已保存，请返回 Codex 对话继续`.
- Revision conflict: retain user input locally, fetch latest projection, do not overwrite.
- Invalid gate: return missing evidence refs and keep the current gate open.

## 9. Acceptance

Completion requires all of the following:

1. all five spaces render real project-backed content in inline and fullscreen modes;
2. mixed material input creates source records and a classification task;
3. content blueprint is visible, source-bound, and G0 cannot pass without evidence;
4. visual directions, real sample assets, engineering evidence, contract, and G1–G3 are visible and gateable;
5. a real editable PPTX, real renders, QA result, and delivery files are visible and G4-gated;
6. accepted and stale revision writes are proven over stdio MCP;
7. the existing six-slide智慧园区 project is rendered through all five Widget spaces without modifying its business artifacts;
8. 360/420/480/1440 widths have no horizontal overflow or console errors;
9. Python, Node, Widget, type, plugin, PPTX archive, render, and installed-bundle probes pass;
10. the upgraded personal plugin is installed and enabled, and a new Codex task can load its MCP schema.

## 10. Self-review

- No product scope beyond the approved presales-reading MVP is introduced.
- No second model or PPTX engine is introduced.
- Material automation is represented honestly as an Agent task, not deterministic fake AI output.
- Every write has revision, event, version, and recovery behavior.
- All five gates remain human approval points.
- Existing project and Web product isolation remains unchanged.
