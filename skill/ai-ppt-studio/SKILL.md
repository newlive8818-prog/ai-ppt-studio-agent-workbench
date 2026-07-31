---
name: ai-ppt-studio
description: Create, resume, review, and validate isolated AI PowerPoint projects in Codex for sales-solution presentations. Use when a user asks to make, redesign, continue, inspect, render, or deliver an editable PPT/PPTX through the AI PPT Studio workflow.
---

# AI PPT Studio

Operate through the managed AI PPT workspace. Never write into the current working directory unless it is already the configured managed project directory.

## Required startup

1. Read isolation-policy.md before any file write, using `references/isolation-policy.md`.
2. Read `references/runtime-workflow.md` before creating or resuming a project.
3. Run the runtime preflight before initialization, material import, state changes, rendering, or delivery.
4. Treat user-provided source materials as read-only.
5. Stop when a write target is protected, unresolved, overly broad, or outside the managed runtime root.

## Current capability boundary

The runtime foundation can initialize isolated projects, register or copy user-provided materials, report G0–G4 state, and resume work. Do not claim that visual conception, Image 2 generation, Slide Scene Graph, PPT compilation, or experience promotion exists until the corresponding runtime modules and acceptance tests are present.
