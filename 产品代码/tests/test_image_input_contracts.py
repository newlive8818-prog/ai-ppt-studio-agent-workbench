"""Closed authorization selectors: source coordinates and use never broaden."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_ppt_studio.domains.materials.image_input_contracts import (
    authorize_atom, contains, location, overlaps, text, validate_scope,
)
from ai_ppt_studio.errors import ContractValidationError


def table(page=2, object_id="8", row_start=1, row_end=5, col_start=2, col_end=6):
    return {"kind": "table-range", "page": page, "object_id": object_id,
        "row_start": row_start, "row_end": row_end, "col_start": col_start, "col_end": col_end}


def scope(selector, *, uses=None, excluded=None):
    return validate_scope({"artifact_type": "image-led-authorization-scope", "project_id": "p1",
        "receiver": "synthetic-provider", "model": "gpt-image-2", "allowed": [{
            "source_sha256": "a" * 64, "source_location": selector,
            "uses": uses or ["content-source"], "send_form": "verbatim"}],
        "excluded": [] if excluded is None else [{"source_sha256": "a" * 64, "source_location": excluded}]}, "p1")


def atom(selector, use="content-source", atom_id="one"):
    return {"atom_id": atom_id, "source_sha256": "a" * 64,
            "source_location": selector, "use": use}


class ImageInputContractTests(unittest.TestCase):
    def test_page_object_and_table_containment_is_precise(self):
        page = {"kind": "page", "page": 2}
        obj = {"kind": "object", "page": 2, "object_id": "8"}
        inner = table(row_start=2, row_end=4, col_start=3, col_end=5)
        for outer, selected in [(page, obj), (page, table()), (obj, table()), (table(), inner)]:
            with self.subTest(outer=outer, selected=selected):
                self.assertTrue(contains(outer, selected))
                authorize_atom(scope(outer), atom(selected))
        for outer, selected in [(obj, page), (table(), obj), (page, {**obj, "page": 3}),
            (obj, table(object_id="9")), (table(), table(row_start=0)),
            (table(), table(col_end=7)), (table(), table(page=3))]:
            self.assertFalse(contains(outer, selected))
            with self.assertRaises(ContractValidationError):
                authorize_atom(scope(outer), atom(selected))

    def test_source_exclusion_survives_atom_rename_and_propagates_page_object(self):
        page = {"kind": "page", "page": 2}
        obj = {"kind": "object", "page": 2, "object_id": "8"}
        for excluded, selected in [(page, obj), (page, table()), (obj, table()), (table(), table(row_start=3)),
                                   ({"kind": "whole-source"}, page)]:
            for alias in ("original", "different-atom-id"):
                with self.subTest(excluded=excluded, alias=alias), self.assertRaises(ContractValidationError):
                    authorize_atom(scope({"kind": "whole-source"}, excluded=excluded), atom(selected, atom_id=alias))

    def test_disjoint_objects_pages_and_table_cells_do_not_overlap(self):
        pairs = [
            ({"kind": "page", "page": 2}, {"kind": "object", "page": 3, "object_id": "8"}),
            ({"kind": "object", "page": 2, "object_id": "8"}, table(object_id="9")),
            (table(), table(row_start=5, row_end=7)),
            (table(), table(col_start=6, col_end=8)),
        ]
        for left, right in pairs:
            self.assertFalse(overlaps(left, right))
            self.assertFalse(overlaps(right, left))
            authorize_atom(scope({"kind": "whole-source"}, excluded=left), atom(right))

    def test_unknown_coordinate_relationships_are_conservative(self):
        values = [{"kind": "text-range", "start": 0, "end": 3},
                  {"kind": "image-region", "x": 0, "y": 0, "width": 3, "height": 2},
                  {"kind": "page", "page": 2}]
        for index, left in enumerate(values):
            for right in values[index + 1:]:
                self.assertFalse(contains(left, right))
                self.assertFalse(contains(right, left))
                self.assertTrue(overlaps(left, right))
                self.assertTrue(overlaps(right, left))
                with self.assertRaises(ContractValidationError):
                    authorize_atom(scope({"kind": "whole-source"}, excluded=left), atom(right))

    def test_style_permission_does_not_authorize_content_or_real_material(self):
        selector = {"kind": "page", "page": 2}
        allowed = scope(selector, uses=["style-reference"])
        authorize_atom(allowed, atom(selector, "style-reference"))
        for use in ("content-source", "real-material"):
            with self.assertRaises(ContractValidationError):
                authorize_atom(allowed, atom(selector, use))

    def test_chinese_whitespace_hash_is_exact_and_not_normalized(self):
        original = "  重庆机电\n 客户原文🙂 \t"
        self.assertEqual(text(original, "copy"), original)
        hashed = hashlib.sha256(original.encode("utf-8")).hexdigest()
        allowed = scope({"kind": "whole-source"})
        allowed["allowed"][0]["source_sha256"] = hashed
        exact_atom = {**atom({"kind": "whole-source"}), "source_sha256": hashed}
        authorize_atom(allowed, exact_atom)
        for rewritten in (original.strip(), original.replace("\n", " "), original.replace(" \t", "")):
            with self.assertRaises(ContractValidationError):
                authorize_atom(allowed, {**exact_atom, "source_sha256": hashlib.sha256(rewritten.encode()).hexdigest()})

    def test_scope_and_selector_fields_remain_closed(self):
        selected = table()
        for bad in ({**selected, "layout": "cards"}, {**selected, "row_end": selected["row_start"]},
                    {**selected, "page": True}, {**selected, "object_id": " "}):
            with self.assertRaises(ContractValidationError):
                location(bad)
        value = scope({"kind": "whole-source"})
        with self.assertRaises(ContractValidationError):
            validate_scope({**deepcopy(value), "approved": True}, "p1")


if __name__ == "__main__":
    unittest.main()
