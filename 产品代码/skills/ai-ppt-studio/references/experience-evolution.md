# Two-layer content and visual experience evolution

AI is the principal learner; humans provide goals, directives, rejection, revision, and outcome evidence.

## Two reusable layers

- `same-type`: a sanitized mechanism, anti-pattern, or preference bound to one `type_signature`, scene, audience, slide task, conditions, and counterexamples.
- `global`: a sanitized mechanism that may apply across types because the user explicitly made it global or real success evidence covers at least two different type signatures.

Project-only facts and raw feedback remain in the project. Never move customer names, facts, numbers, files, screenshots, logos, full-page designs, Gate overrides, or permission rules into reusable experience.

## Two experience domains

- `content`: evidence reconstruction, decision context, problem diagnosis, problem-solution fit, neutral titles, reading structure, and content anti-patterns.
- `visual`: hierarchy, composition, density, page-family variation, typography, color, diagrams, imagery, evidence display, editability, and real PowerPoint behavior.

An experience may reference a cross-domain relationship without creating a third layer.

## Evidence over example libraries

Prefer explicit user feedback, before/after artifacts, later acceptance, Gate evidence, render evidence, editability evidence, and failures over static example libraries. Record template feel, visual drift, weak focus, unreadable density, fact change, crop failure, and editability loss as evidence-backed anti-patterns when reusable.

Positive references belong to an isolated inspiration pool. Extract a mechanism; never copy a concrete work or promote a rule merely because a designer, local deck, course, or Skill is available.

## Persistent Runtime records

Keep learning in a separate Runtime data plane:

- `personal-memory/experience-index.json`: current index;
- `personal-memory/same-type/<experience-id>/vNNNN.json`: immutable same-type versions;
- `personal-memory/global/<experience-id>/vNNNN.json`: immutable global versions;
- `evaluation/applications.jsonl`: exact version used by each project;
- `evaluation/evaluations.jsonl`: success, mixed, or failure evidence;
- `evaluation/promotions.jsonl`: global promotion and rollback decisions.

These paths stay below the managed Runtime root and outside source and installed Skill bundles.

## Operating loop

1. After Mission and material mode are known, call `recommend_experience` with scene, audience, slide task, conditions, and `type_signature`.
2. Inspect exact version, layer, scope, applicability, counterexamples, privacy, evidence, and match reason. Do not silently apply weak or conflicting advice.
3. When an item materially influences output, call `record_experience_application` with its exact version and target project references.
4. After any clear valid page decision, comment, hard-gate failure, rejected mechanism, real render/editability defect, or accepted repair, absorb a bounded mechanism or anti-pattern into `same-type` immediately when warranted. It may influence the current page, remaining work, next revision, and next matching project without waiting for global promotion.
5. After real user acceptance, rejection, or material revision, record outcome evidence. Never turn a fixture or test Runtime into customer success.
6. On G4, formal project close, or abort, automatically run `summarize_project_experience` for the queued `ProjectExperienceRetrospective`.

The retrospective must cover content findings, visual findings, accepted mechanisms, rejected patterns, before/after refs, user outcome refs, Gate/render refs, `same_type_changes`, `global_changes`, and next-project recommendations. An abort creates an abort retrospective and never success evidence. Project completion remains durable if retrospective generation fails, but Runtime must write `experience-retrospective-pending`, retain failure/retry evidence, and retry; it must not silently close learning.

## Same-type matching

Content matching uses mission, audience, decision stage, material mode, page task, and business-problem type. Visual matching uses mission, reading context, audience level, material mode, page family, information density, brand constraints, and delivery target. Industry is a modifier, not an exact-equality requirement.

## Promotion, conflict, and rollback

- Absorb a new reusable lesson into `same-type` first unless the user supplied an explicit global directive.
- Promote to `global` only from that directive or real accepted success in at least two different type signatures.
- One explicit counterexample stops automatic application in its conflicting scope; narrow, split, disable, or demote the item.
- Disabled or retired items are excluded from recommendation.
- Rollback creates a new latest version and retains all prior immutable versions plus the reason.

A visual success requires explicit user visual acceptance, page-task/readability success, and real render evidence. No-overflow or editability evidence alone is insufficient.

Confidence is derived from distinct real applications, outcomes, and evidence refs. It is not a free-form model score and never overrides a Gate.

## Privacy and proof

1. Require `sanitized_for_reuse: true`, mechanism-only privacy, bounded applicability, source refs, and counterexamples.
2. Do not flatten conflicting contexts into a universal rule.
3. Do not claim learning success until later evidence shows reduced rejection, rework, or engineering degradation.
4. Do not let Runtime experience rewrite product policy or the installed Skill automatically.

Legacy candidate and personal-experience records remain immutable history. Migration may create a new same-type version only after privacy, scope, applicability, and counterexample validation; historical promotion never auto-creates global experience.
