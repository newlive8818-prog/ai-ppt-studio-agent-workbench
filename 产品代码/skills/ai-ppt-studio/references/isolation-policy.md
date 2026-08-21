# Isolation policy

Read this policy before any file write.

## Four zones

1. The upstream Web product design directory is read-only to the Skill App.
2. The Skill source repository may contain code, tests, specifications, and release assets only. Never store customer materials, project outputs, or reusable Runtime memory there.
3. The Codex installation directory contains only a replaceable installed Skill. Never store project state or rendered artifacts there.
4. All project state, generated HTML, images, PPTX files, renders, evaluation data, and reusable experience belong under the configured managed Runtime root.

## Protected paths

Before every write, resolve the real absolute target and reject it when it is:

- inside a configured protected root;
- outside the managed runtime root;
- a symlink or traverses a symlink;
- unresolved, ambiguous, overly broad, or the filesystem root.

Protected roots include the upstream Web product, this source repository, the installed Skill, user-declared source libraries, and any additional protected paths in `workspace.json`.

## Source materials

User-provided materials are read-only. Record their source, hash, read time, and intended use. Keep a reference when reading is enough; copy into the managed project before OCR, conversion, cropping, annotation, extraction, or any transformation. Never overwrite, rename, move, or delete an original. Never create writable symlinks to originals.

All production writes must remain under the managed runtime root. Delivery outside that root requires an explicit user-selected destination and a separate export action.
