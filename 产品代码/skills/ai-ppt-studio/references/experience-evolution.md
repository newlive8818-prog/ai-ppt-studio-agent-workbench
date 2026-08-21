# Two-layer content and visual experience evolution

AI learns continuously from real project evidence. Humans provide corrections, choices, acceptance, rejection, and outcome feedback.

## Only two layers

1. `same-type`: experience bounded to matching presales contexts;
2. `global`: experience applicable to all reading-first presales work.

Product policy, evidence truthfulness, Gate authority, privacy, and role permissions are contracts, not a third experience layer. Runtime experience cannot rewrite them.

## Two domains

Every experience has one domain:

- `content`: evidence reconstruction, decision context, problem diagnosis, problem-solution fit, neutral titles, reading structure, and content anti-patterns;
- `visual`: hierarchy, composition, density, page-family variation, typography, color, diagrams, imagery, evidence display, editability, and real PowerPoint behavior.

An experience may reference a cross-domain relationship without creating another layer.

## Two absorption rhythms

### Real-time absorption

Extract reusable mechanisms and anti-patterns immediately from:

- user page decisions and comments;
- content or visual hard-gate failures;
- rejected titles, weak problem explanations, and fit mismatches;
- rejected hierarchy, density, template feel, imagery, charts, or page rhythm;
- actual PowerPoint render or editability defects;
- accepted repairs and before/after evidence.

One clear, valid feedback item may create or update same-type experience. Apply it to the current page, remaining pages, the next revision, and the next matching project. Do not wait for cross-project promotion before same-type use.

### Project-completion retrospective

After G4, formal close, or abort, automatically create `ProjectExperienceRetrospective`. The user does not need to request or approve the retrospective.

The retrospective records:

- project type signature and material mode;
- content successes, rework, failures, and user outcomes;
- visual successes, rejected patterns, render and engineering outcomes;
- before/after refs;
- hard-gate, G0/G3/G4, and target-render refs;
- same-type additions, merges, splits, or disables;
- global promotions, demotions, or rollbacks;
- experience recommended for the next matching project.

An aborted project produces an abort retrospective and never creates success evidence.

If retrospective generation fails, do not block delivery. Write `experience-retrospective-pending`, preserve evidence, and retry. A project must not close silently without a retrospective record or pending task.

## Same-type matching

Content matching uses:

```text
deck mission + audience + decision stage + material mode + page task + business problem type
```

Visual matching uses:

```text
deck mission + reading context + audience level + material mode + page family + information density + brand constraints + delivery target
```

Industry is a modifier, not an exact-equality requirement.

## Global promotion

An experience becomes global through either route:

1. the user explicitly declares it a global preference or instruction; or
2. the same mechanism succeeds in at least two distinct type signatures, passes applicable hard gates, has accepted user outcomes, and has no clear counterexample.

A visual success requires user visual acceptance, page-task/readability success, and real rendered evidence. Technical no-overflow/editability alone is insufficient.

## Failure, demotion, and rollback

- Same-type counterexample: narrow or split its type signature.
- Global counterexample: stop auto-application in the conflicting scope and demote to same-type or split.
- Disabled and retired versions are excluded from recommendations.
- Rollback creates a new latest version and preserves history.
- Exact applied experience versions and later outcomes are always recorded.

## Privacy and reuse

Store mechanisms, preferences, and anti-patterns, not customer facts or copied works.

Never reuse customer names, data, logos, screenshots, proprietary assets, brand systems, or complete page designs. Every reusable item must be sanitized and keep source, scope, counterexamples, failure boundaries, version, applications, results, and rollback state.

## Runtime records

Experience stays below the managed runtime root, outside source and installed Skill files:

```text
personal-memory/same-type/<experience-id>/vNNNN.json
personal-memory/global/<experience-id>/vNNNN.json
personal-memory/experience-index.json
evaluation/applications.jsonl
evaluation/evaluations.jsonl
evaluation/promotions.jsonl
evaluation/retrospectives.jsonl
```

Legacy candidate/personal records remain immutable history. During migration they may become same-type only after privacy and scope validation; they never become global merely because they were previously promoted.
