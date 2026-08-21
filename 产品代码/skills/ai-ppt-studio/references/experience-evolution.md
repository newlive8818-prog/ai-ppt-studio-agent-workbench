# Experience evolution

AI is the principal learner; humans provide goals, directives, rejection, revision, and outcome evidence.

## Two reusable layers

- `same-type`: a sanitized mechanism, anti-pattern, or preference bound to one `type_signature`, scene, audience, slide task, conditions, and counterexamples.
- `global`: a sanitized mechanism that may apply across types because the user explicitly made it global or real success evidence covers at least two different type signatures.

Project-only facts and raw feedback remain in the project. Never move customer names, facts, numbers, files, screenshots, logos, full-page designs, Gate overrides, or permission rules into reusable experience.

## Evidence priority

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
4. After real user acceptance, rejection, or material revision, record outcome evidence. Never turn a fixture or test Runtime into customer success.
5. On project delivery, close, or abort, run `summarize_project_experience` for the queued `ProjectExperienceRetrospective`.

The retrospective must cover content findings, visual findings, accepted mechanisms, rejected patterns, before/after refs, user outcome refs, Gate/render refs, `same_type_changes`, `global_changes`, and next-project recommendations. Project completion remains durable even if retrospective generation fails; retain retry or failure evidence separately.

## Promotion, conflict, and rollback

- Absorb a new reusable lesson into `same-type` first unless the user supplied an explicit global directive.
- Promote to `global` only from that directive or real accepted success in at least two different type signatures.
- One explicit counterexample stops automatic application in its conflicting scope; narrow, split, disable, or demote the item.
- Disabled or retired items are excluded from recommendation.
- Rollback creates a new latest version and retains all prior immutable versions plus the reason.

Confidence is derived from distinct real applications, outcomes, and evidence refs. It is not a free-form model score and never overrides a Gate.

## Privacy and proof

1. Require `sanitized_for_reuse: true`, mechanism-only privacy, bounded applicability, source refs, and counterexamples.
2. Do not flatten conflicting contexts into a universal rule.
3. Do not claim learning success until later evidence shows reduced rejection, rework, or engineering degradation.
4. Do not let Runtime experience rewrite product policy or the installed Skill automatically.
