#!/usr/bin/env python3
"""Installed-skill entry point; imports only the bundled runtime."""

from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

from ai_ppt_studio.cli import main  # noqa: E402

raise SystemExit(main())
