#!/usr/bin/env python3
"""Installed-skill entry point; imports only the bundled runtime."""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
PLUGIN_SOURCE = Path(__file__).resolve().parents[3] / "src"
RUNTIME = SKILL_ROOT / "runtime"
if not RUNTIME.exists() and PLUGIN_SOURCE.exists():
    RUNTIME = PLUGIN_SOURCE
sys.path.insert(0, str(RUNTIME))

from ai_ppt_studio.cli import main  # noqa: E402

raise SystemExit(main())
