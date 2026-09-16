"""Explicit adapter for names retained from retired v1.6 regression suites.

Each migrated test method remains discoverable under its historical name, while
delegating to one named v2.2 scenario that exercises the current authoritative
contract.  This avoids reintroducing retired production shims and keeps the
old security intent traceable during the one-way migration.
"""

from __future__ import annotations

import unittest


class MigratedRegressionCase(unittest.TestCase):
    def assert_current_scenario(
        self,
        case_type: type[unittest.TestCase],
        method_name: str,
    ) -> None:
        case_type(method_name).debug()


__all__ = ["MigratedRegressionCase"]
