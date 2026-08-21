# AI PPT Studio Cross-Project Experience Evolution Design

> **Document status: historical and superseded.** The candidate/personal/stable progression is no longer the target product contract. The current two-layer content-and-visual experience design is [2026-08-14-presales-chief-agent-content-and-experience-design.md](./2026-08-14-presales-chief-agent-content-and-experience-design.md). Keep this file only for legacy-data migration and provenance.

**Date:** 2026-08-01  
**Status:** Historical and superseded; not approved for new implementation
**Scope:** Local personal installation only; no automatic stable-kernel mutation

## 1. Goal

Turn project feedback into a durable, inspectable, versioned personal experience system that can be reused and evaluated in later presentation projects. The system must prove learning through later application outcomes, not by claiming that a feedback file exists.

## 2. Non-goals

- Do not automatically edit the installed `SKILL.md` or stable capability kernel.
- Do not publish customer names, customer materials, screenshots, or confidential content as public experience.
- Do not copy a successful slide as a universal template.
- Do not treat a single acceptance as general proof.
- Do not build a remote service or cross-user synchronization layer.

## 3. Runtime boundaries

All personal experience data stays below the managed runtime root:

```text
AI-PPT-Workspace/
├── personal-memory/
│   ├── experience-index.json
│   └── experiences/<experience-id>/
│       ├── v0001.json
│       ├── v0002.json
│       └── latest.json
├── evaluation/
│   ├── applications.jsonl
│   ├── evaluations.jsonl
│   └── promotion-decisions.jsonl
└── projects/<project>/reviews/feedback/
```

Source repositories and installed Skill directories contain code, schemas, tests, and documentation only. Project deletion does not silently delete personal experience. Skill reinstall does not overwrite personal experience.

## 4. Knowledge levels

| Level | Meaning | Entry rule | Exit rule |
|---|---|---|---|
| `candidate` | A bounded hypothesis extracted from one or more projects | Explicit creation from a project feedback source | Promote after later cross-project validation, or disable/retire |
| `personal` | A personal mechanism repeatedly validated across projects | Two accepted successful applications in distinct target projects | Demote after two later failures, or manually change |
| `disabled` | Retained but excluded from recommendations | Manual disable or governance decision | Manual restore to candidate/personal |
| `retired` | Historical only | Manual retirement | Manual rollback/change only |

The stable capability kernel remains release-managed and is not a runtime level.

## 5. Candidate experience contract

Each immutable experience version records:

- identity, name, type, version, timestamps, level, enabled state;
- mechanism statement and model interpretation;
- source projects, source feedback/events, raw feedback references;
- applicability scope: scenes, audiences, slide tasks, and conditions;
- supporting evidence, before/after references, and counterexamples;
- usage, accepted successes, failures, target-project history, and latest validation time;
- transparent confidence score and the inputs used to calculate it;
- privacy level and portability boundary;
- previous version and rollback origin.

Customer-specific facts may be referenced by local path, but the reusable mechanism statement must be sanitized so the experience itself can be matched without leaking customer content.

## 6. Matching and recommendation

A target context contains `scene`, `audience`, `slide_task`, and `conditions`. Recommendation:

1. excludes disabled, retired, and non-enabled experiences;
2. requires at least one matching value when the candidate declares a value for a dimension;
3. scores exact scope matches deterministically;
4. ranks `personal` above `candidate` only after applicability score;
5. exposes the match reasons, level, confidence, and version so the model can decide whether to apply it.

No experience is silently applied. Applying one creates an `ExperienceApplication` record tied to the target project and exact experience version.

## 7. Evaluation and evolution

An application is evaluated as `success`, `mixed`, or `failure`, with `user_accepted`, evidence references, notes, and optional metrics.

Confidence is explainable and recalculated from evidence:

```text
0.30 base
+ 0.20 per distinct accepted-success target project, capped at +0.40
- 0.20 per failure, capped at -0.40
+ 0.05 when there are supporting evidence references
clamped to 0.05..0.95
```

Automatic governance:

- `candidate -> personal` after accepted successes in at least two distinct target projects;
- `personal -> candidate` after at least two failures recorded after promotion;
- no runtime transition can promote an experience into the stable capability kernel;
- all promotions and demotions append a decision record;
- manual level changes require a reason;
- rollback creates a new immutable version from a selected prior version and records why.

## 8. Proof of learning

The minimum acceptance demonstration is:

1. create a bounded candidate from the Huaxi project feedback;
2. request recommendations for two other managed project contexts;
3. record use of the same candidate in each target project;
4. record accepted successful outcomes;
5. observe automatic promotion to `personal` with two project IDs and two evaluation records;
6. verify `experience-list`, immutable versions, application/evaluation logs, and promotion decision log;
7. verify a disabled experience is no longer recommended and a rollback restores prior content as a new version.

## 9. CLI surface

```text
experience-create --project PATH --input JSON
experience-list [--level LEVEL]
experience-show --experience ID
experience-recommend --input JSON [--limit N]
experience-apply --project PATH --experience ID --input JSON
experience-evaluate --application ID --input JSON
experience-set-level --experience ID --level LEVEL --reason TEXT
experience-rollback --experience ID --version N --reason TEXT
```

`preflight` reports evidence-backed readiness paths and supported operations; it must not use an unconditional boolean claim.

## 10. Acceptance criteria

- All experience writes are constrained to managed runtime directories.
- Version files are immutable and latest state is recoverable.
- Recommendation works across project boundaries without copying project feedback files.
- Application and evaluation records are append-only.
- Promotion, demotion, disabling, and rollback are tested.
- Customer-private mechanisms are not promoted into a public layer.
- The installed portable Skill exposes the commands and usage guidance.
- Full test suite and installed-runtime smoke checks pass.
