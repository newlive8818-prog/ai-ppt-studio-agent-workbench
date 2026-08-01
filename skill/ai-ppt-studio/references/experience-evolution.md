# Experience evolution

AI is the principal learner; humans provide goals, choices, rejection, revision, and outcome feedback.

## Evidence priority

Project feedback and engineering outcomes outweigh static example libraries. Failure memory is especially valuable: template feel, visual drift, weak focus, unreadable density, fact change, crop failure, and editability loss.

Positive examples enter an isolated inspiration pool. The model extracts mechanisms rather than copying a concrete work. A well-known designer, local deck, course, or existing Skill never becomes a rule merely because it is available.

## Promotion levels

1. raw project event;
2. project-only preference or lesson;
3. candidate experience with scene, audience, slide task, conditions, evidence, and counterexample;
4. repeatedly validated personal experience;
5. stable Skill capability only through a versioned product release.

A single response never changes the stable Skill core. Later matching projects may automatically apply low-risk, repeatedly validated personal experience and must record what was used. High-impact, conflicting, or weak experience remains a suggestion.

Every candidate experience stores source events, raw feedback references, model interpretation, before/after references, usage count, success count, failure count, latest validation time, confidence, scope, counterexamples, privacy, and rollback state. Users can inspect, disable, retire, demote, or roll back experience.

## Persistent runtime records

Personal learning is a separate data plane, not text scattered through slide code:

- `personal-memory/experience-index.json` is the inspectable current index;
- `personal-memory/experiences/<experience-id>/vNNNN.json` stores immutable versions;
- `personal-memory/experiences/<experience-id>/latest.json` points to the current version;
- `evaluation/applications.jsonl` records which exact experience version influenced which target project;
- `evaluation/evaluations.jsonl` records success, mixed, or failure outcomes and user acceptance;
- `evaluation/promotion-decisions.jsonl` records automatic and manual level changes and rollbacks.

These paths are below the managed runtime root. They survive project deletion and Skill reinstall. Never write personal data into the source repository or installed Skill bundle.

## Required operating loop

Create a candidate only after separating reusable mechanism from customer-specific facts. The JSON must declare `sanitized_for_reuse: true`, bounded `scope`, local `source_refs`, privacy, and portability.

```bash
python3 scripts/ai_ppt_runtime.py experience-create \
  --project PROJECT_ROOT --input candidate.json
```

Once mission context is known—and again after a material audience, scene, slide-task, or condition change—request matching experience:

```bash
python3 scripts/ai_ppt_runtime.py experience-recommend \
  --input context.json --limit 5
```

Inspect `match_reasons`, level, confidence, privacy, and exact version. Do not silently apply weak or conflicting experience. When it materially influences the work, bind that exact version to the target project:

```bash
python3 scripts/ai_ppt_runtime.py experience-apply \
  --project PROJECT_ROOT --experience EXP-ID --input context.json
```

After the user accepts, rejects, or materially revises the influenced output, evaluate the application. Do not invent success for a real customer project.

```bash
python3 scripts/ai_ppt_runtime.py experience-evaluate \
  --application APP-ID --input evaluation.json
```

An evaluation contains `outcome` (`success`, `mixed`, or `failure`), boolean `user_accepted`, evidence references, notes, and optional metrics.

## Evidence-based governance

Confidence is recalculated from a 0.30 base, distinct accepted-success target projects, failures, and evidence references. It is not a free-form model score.

- `candidate -> personal`: two accepted successful applications in distinct target projects;
- `personal -> candidate`: two failures after promotion;
- disabled and retired experience is excluded from recommendations;
- stable Skill core: runtime experience can never promote itself into it; only a versioned product release can change it.

Manual changes require an explicit reason:

```bash
python3 scripts/ai_ppt_runtime.py experience-set-level \
  --experience EXP-ID --level disabled --reason "Conflicts with the current brand system"
```

Rollback never overwrites history. It restores a selected version as a new latest version and logs the decision:

```bash
python3 scripts/ai_ppt_runtime.py experience-rollback \
  --experience EXP-ID --version 1 --reason "Restore the narrower proven scope"
```

Use `experience-list`, optionally with `--level`, and `experience-show --experience EXP-ID` to inspect all current evidence and scope before relying on it.

## Privacy and proof rules

1. Keep customer names, content, files, and images in private local references; sanitize the mechanism statement.
2. One project creates a candidate, not a personal rule.
3. A test runtime may demonstrate the mechanics, but it must not be written back as real customer success.
4. The proof of learning is later reduced rejection, rework, or engineering degradation recorded in target-project evaluations.
5. Conflicting contexts remain separate experiences; do not flatten them into a universal rule.
