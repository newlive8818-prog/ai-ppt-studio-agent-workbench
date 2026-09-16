from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_ppt_studio.domains.visual.image_led import (
    selected_copy_sha256, validate_target_binding, validate_selected_copy,
    validate_region_inventory, validate_faithful_objects,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.artifacts import canonical_json


def ref(kind, letter="a"):
    return f"artifact://{kind}/" + letter * 64


def text_item(identity, text, role="body"):
    return {"item_id": identity, "kind": "text", "role": role, "text": text}


def text_style(text):
    return {
        "runs": [{"text": text, "fontFamily": "Arial", "fontSize": 24,
                  "color": "#123456", "bold": False, "italic": False}],
        "alignment": "left", "verticalAlignment": "top",
        "insets": [0, 0, 0, 0], "lineSpacing": 1.2,
    }


def binding(copy=None, slide_id="s1", order=1):
    if copy is None:
        copy = {"items": [text_item("title", " 标题\n", "title"),
                          text_item("body", " 说明 42 万元\n\n保留尾空格 ")]}
    return {
        "project_id": "project-a", "slide_id": slide_id, "page_order": order,
        "candidate_ref": ref("image-led-candidate"),
        "target_image_ref": ref("image-led-image", "b"),
        "target_image_sha256": "c" * 64,
        "selected_copy_sha256": hashlib.sha256(canonical_json(copy)).hexdigest(),
        "material_roles": [], "common_rules_ref": ref("image-led-input-policy", "d"),
        "accepted_deviations": [], "design_authority": "finalized-image",
        "conversion_mode": "faithful-native",
    }


def fixture():
    copy = {"items": [text_item("title", " 标题\n", "title"),
                      text_item("body", " 说明 42 万元\n\n保留尾空格 ")]}
    target = binding(copy)
    regions = [{
        "region_id": item["item_id"], "kind": "text",
        "bbox": [20, 20 + i * 100, 600, 80], "z_order": i,
        "content": {"items": [deepcopy(item)]}, "material_binding": None,
        "appearance": text_style(item["text"]),
    } for i, item in enumerate(copy["items"])]
    selection = {"project_id": "project-a", "slides": [
        {"target_binding": target, "selected_copy": copy}]}
    inventory = {
        "artifact_type": "image-led-region-inventory",
        "selection_ref": ref("image-led-selection"), "project_id": "project-a",
        "slides": [{"target_binding": deepcopy(target),
                    "canvas": {"width": 1280, "height": 720, "dpi": 96},
                    "source_image_size": {"width": 1280, "height": 720},
                    "regions": regions}],
    }
    return selection, inventory


def objects_for(regions):
    return [{**deepcopy(region), "object_id": f"object-{region['region_id']}",
             "render_mode": "bitmap" if region["kind"] in {"image", "decoration"}
             else "native"} for region in regions]


def rich_fixture():
    selection, inventory = fixture()
    copy = selection["slides"][0]["selected_copy"]
    cells = [{"item_id": f"cell-{c}", "kind": "table-cell", "table_id": "metrics",
              "row": 0, "column": c, "text": text}
             for c, text in enumerate(["收入", "42 万元"])]
    relation = {"item_id": "flow", "kind": "relation", "text": "说明支持结论",
                "from_item_id": "title", "to_item_id": "body", "direction": "forward"}
    copy["items"].extend(cells + [relation])
    selection["slides"][0]["target_binding"] = binding(copy)
    inventory["slides"][0]["target_binding"] = deepcopy(selection["slides"][0]["target_binding"])
    regions = inventory["slides"][0]["regions"]
    def add(identity, kind, content, appearance, box):
        regions.append({"region_id": identity, "kind": kind, "bbox": box,
                        "z_order": len(regions), "content": {"items": deepcopy(content)},
                        "material_binding": None, "appearance": appearance})
    add("metrics", "table", cells, {
        "row_heights": [60], "column_widths": [200, 200],
        "cells": [{"row": i["row"], "column": i["column"], "item_id": i["item_id"],
                   "style": text_style(i["text"])} for i in cells],
    }, [20, 300, 400, 60])
    add("flow", "connector", [relation], {
        "from_region_id": "title", "to_region_id": "body", "start": [620, 60],
        "end": [620, 160], "line": {"color": "#123456", "width": 2, "dash": "solid"},
        "arrow": "forward", "meaning": relation["text"],
    }, [619, 60, 2, 100])
    add("panel", "shape", [], {"geometry": "rect", "corner_radius": 0,
        "fill": {"type": "linear-gradient", "angle": 45,
                 "stops": [{"offset": 0, "color": "#FFFFFF"}, {"offset": 1, "color": "#123456"}]},
        "line": None, "shadow": {"color": "#000000", "opacity": 0.3, "blur": 4,
                                   "offset_x": -2, "offset_y": 3}}, [800, 50, 100, 100])
    for identity, kind, x in [("photo", "image", 920), ("ornament", "decoration", 1040)]:
        add(identity, kind, [], {"asset_ref": ref("image-led-crop"),
            "asset_sha256": "f" * 64, "crop": [0, 0, 1, 1]}, [x, 50, 100, 100])
    return selection, inventory


class ImageLedContractTests(unittest.TestCase):
    def setUp(self):
        self.selection, self.inventory = fixture()
        self.copy = self.selection["slides"][0]["selected_copy"]
        self.binding = self.selection["slides"][0]["target_binding"]

    def assert_rejected(self, callback, *args, **kwargs):
        with self.assertRaises(ContractValidationError):
            callback(*args, **kwargs)

    def test_verbatim_copy_and_independent_return(self):
        original = deepcopy(self.copy)
        normalized = validate_selected_copy(self.copy)
        self.assertEqual(normalized, original)
        normalized["items"][0]["text"] = "mutated"
        self.assertEqual(self.copy, original)
        self.assertEqual(selected_copy_sha256(self.copy), self.binding["selected_copy_sha256"])

    def test_copy_rejects_duplicate_missing_title_unknown_and_empty(self):
        for change in (
            lambda p: p["items"].append(deepcopy(p["items"][0])),
            lambda p: p["items"][0].update(role="body"),
            lambda p: p["items"][0].update(text=" \n"),
            lambda p: p["items"][0].update(layout="left-column"),
            lambda p: p.update(frozen_copy="old"),
        ):
            with self.subTest(change=change):
                changed = deepcopy(self.copy); change(changed)
                self.assert_rejected(validate_selected_copy, changed)

    def test_binding_checks_context_and_exact_copy(self):
        self.assertEqual(validate_target_binding(
            self.binding, expected_project_id="project-a", expected_slide_id="s1",
            expected_page_order=1, selected_copy=self.copy), self.binding)
        for kw in ({"expected_project_id": "other"}, {"expected_slide_id": "s2"},
                   {"expected_page_order": 2}):
            with self.subTest(kw=kw):
                self.assert_rejected(validate_target_binding, self.binding, **kw)
        changed = deepcopy(self.copy); changed["items"][1]["text"] = "旧文案"
        self.assert_rejected(validate_target_binding, self.binding, selected_copy=changed)

    def test_binding_rejects_malformed_identity_and_unknown_fields(self):
        for key, value in (("page_order", True), ("page_order", 0),
                           ("target_image_sha256", "f" * 63),
                           ("target_image_ref", ref("reading-deck-blueprint")),
                           ("design_authority", "reference"),
                           ("conversion_mode", "redesign"), ("layout", "grid")):
            with self.subTest(key=key, value=value):
                changed = deepcopy(self.binding); changed[key] = value
                self.assert_rejected(validate_target_binding, changed)

    def test_material_roles_are_closed_and_unique(self):
        role = {"atom_id": "logo", "source_ref": ref("material-source"),
                "content_sha256": "f" * 64, "use": "real-material"}
        self.binding["material_roles"] = [role]
        self.assertEqual(validate_target_binding(self.binding), self.binding)
        for role_change in (dict(role, approved=True), dict(role, use="forbidden")):
            changed = deepcopy(self.binding); changed["material_roles"] = [role_change]
            self.assert_rejected(validate_target_binding, changed)
        self.binding["material_roles"].append(deepcopy(role))
        self.assert_rejected(validate_target_binding, self.binding)

    def test_deviations_only_bind_selected_item_and_exact_image(self):
        deviation = {"candidate_ref": self.binding["candidate_ref"],
                     "image_sha256": self.binding["target_image_sha256"],
                     "item_id": "body", "difference_kind": "text",
                     "before": "旧文案", "after": self.copy["items"][1]["text"],
                     "decision_ref": ref("human-decision")}
        self.binding["accepted_deviations"] = [deviation]
        self.assertEqual(validate_target_binding(self.binding, selected_copy=self.copy), self.binding)
        for key, value in (("item_id", "other-page"), ("after", "未来可以改"),
                           ("image_sha256", "e" * 64),
                           ("difference_kind", "any-layout"), ("allow_native_changes", True)):
            changed = deepcopy(self.binding); changed["accepted_deviations"][0][key] = value
            self.assert_rejected(validate_target_binding, changed, selected_copy=self.copy)

    def test_proposed_deviation_has_no_user_decision_and_rejects_open_style_or_material(self):
        proposed = {
            "candidate_ref": self.binding["candidate_ref"],
            "image_sha256": self.binding["target_image_sha256"],
            "item_id": "body", "difference_kind": "text",
            "before": "旧文案", "after": self.copy["items"][1]["text"],
            "decision_ref": "",
        }
        binding = deepcopy(self.binding)
        binding["accepted_deviations"] = [proposed]
        self.assertEqual(
            validate_target_binding(binding, selected_copy=self.copy,
                                    allow_proposed_deviations=True), binding)
        self.assert_rejected(validate_target_binding, binding, selected_copy=self.copy)

        for difference_kind, before, after in (
            ("style", "原样式", "视觉优化"),
            ("material", "旧图片", "图片可替换"),
        ):
            changed = deepcopy(self.binding)
            changed["accepted_deviations"] = [{
                "candidate_ref": changed["candidate_ref"],
                "image_sha256": changed["target_image_sha256"],
                "item_id": "body", "difference_kind": difference_kind,
                "before": before, "after": after,
                "decision_ref": ref("human-decision"),
            }]
            self.assert_rejected(validate_target_binding, changed, selected_copy=self.copy)

    def test_inventory_accepts_bound_verbatim_complete_regions(self):
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)
        self.assertEqual(validate_region_inventory(self.inventory, self.selection,
                         selection_ref=self.inventory["selection_ref"]), self.inventory)
        self.assert_rejected(validate_region_inventory, self.inventory, self.selection,
                             selection_ref=ref("image-led-selection", "f"))

    def test_missing_duplicate_extra_reordered_and_changed_content_rejected(self):
        for change in (
            lambda r: r.pop(), lambda r: r.append(deepcopy(r[0])),
            lambda r: r.reverse(),
            lambda r: r[1]["content"]["items"][0].update(text="说明 43 万元"),
            lambda r: r[1]["content"]["items"][0].update(item_id="new"),
        ):
            changed = deepcopy(self.inventory); change(changed["slides"][0]["regions"])
            self.assert_rejected(validate_region_inventory, changed, self.selection)

    def test_regions_and_objects_cannot_together_omit_selected_content(self):
        self.inventory["slides"][0]["regions"].pop()
        regions = self.inventory["slides"][0]["regions"]
        self.assertEqual(validate_faithful_objects(regions, objects_for(regions)), objects_for(regions))
        self.assert_rejected(validate_region_inventory, self.inventory, self.selection)

    def test_inventory_rejects_wrong_project_slide_order_hash_canvas(self):
        mutations = [
            lambda p: p.update(project_id="other"),
            lambda p: p["slides"][0]["target_binding"].update(slide_id="s2"),
            lambda p: p["slides"][0]["target_binding"].update(target_image_sha256="d" * 64),
            lambda p: p["slides"][0]["canvas"].update(dpi=72),
            lambda p: p["slides"][0]["canvas"].update(width=float("nan")),
            lambda p: p["slides"][0]["source_image_size"].update(height=500),
        ]
        for change in mutations:
            changed = deepcopy(self.inventory); change(changed)
            self.assert_rejected(validate_region_inventory, changed, self.selection)

    def test_geometry_typography_and_unknown_capabilities_fail_closed(self):
        for change in (
            lambda r: r.update(bbox=[-1, 0, 20, 20]),
            lambda r: r.update(bbox=[0, 0, 2000, 20]),
            lambda r: r.update(bbox=[0, 0, True, 20]),
            lambda r: r.update(z_order=-1),
            lambda r: r["appearance"].update(autoFit=True),
            lambda r: r["appearance"]["runs"][0].update(text="被改写"),
            lambda r: r["appearance"]["runs"][0].update(fontFamily=""),
            lambda r: r["appearance"]["runs"][0].update(fontSize=float("inf")),
            lambda r: r["appearance"]["runs"][0].update(color="red"),
        ):
            changed = deepcopy(self.inventory); change(changed["slides"][0]["regions"][0])
            self.assert_rejected(validate_region_inventory, changed, self.selection)

    def test_faithful_objects_reject_all_mutations_and_bitmap_text(self):
        regions = self.inventory["slides"][0]["regions"]
        good = objects_for(regions)
        self.assertEqual(validate_faithful_objects(regions, good), good)
        for change in (
            lambda p: p.pop(), lambda p: p.append(deepcopy(p[0])),
            lambda p: p[0].update(region_id="other"),
            lambda p: p[0].update(bbox=[21, 20, 600, 80]),
            lambda p: p[0].update(z_order=7),
            lambda p: p[0].update(render_mode="bitmap"),
            lambda p: p[0]["appearance"]["runs"][0].update(fontSize=18),
            lambda p: p[0]["content"]["items"][0].update(text="另一个标题"),
            lambda p: p[0].update(native_override="redesign"),
        ):
            changed = deepcopy(good); change(changed)
            self.assert_rejected(validate_faithful_objects, regions, changed)

    def test_all_declared_carriers_accept_and_preserve_rich_schema(self):
        selection, inventory = rich_fixture()
        try:
            actual = validate_region_inventory(inventory, selection)
        except ContractValidationError as error:
            self.fail(f"valid supported carriers were rejected: {error}")
        self.assertEqual(actual, inventory)
        regions = inventory["slides"][0]["regions"]
        self.assertEqual(validate_faithful_objects(regions, objects_for(regions)), objects_for(regions))

    def test_relationship_table_material_and_gradient_mutations_rejected(self):
        for region_id, change in (
            ("flow", lambda r: r["appearance"].update(arrow="none")),
            ("flow", lambda r: r["appearance"].update(from_region_id="body")),
            ("flow", lambda r: r["appearance"].update(end=[-1, 0])),
            ("flow", lambda r: r["appearance"].update(meaning="别的关系")),
            ("metrics", lambda r: r["appearance"]["cells"].pop()),
            ("metrics", lambda r: r["appearance"]["cells"][0].update(item_id="cell-1")),
            ("metrics", lambda r: r["appearance"].update(column_widths=[1, 1])),
            ("panel", lambda r: r["appearance"]["fill"].update(type="radial-gradient")),
            ("panel", lambda r: r["appearance"]["fill"]["stops"][1].update(offset=2)),
            ("panel", lambda r: r["appearance"].update(path="invented-svg")),
            ("photo", lambda r: r["appearance"].update(crop=[0.5, 0, 1, 1])),
            ("photo", lambda r: r["content"]["items"].append(text_item("hidden", "正文"))),
            ("ornament", lambda r: r["content"]["items"].append(text_item("hidden", "正文"))),
        ):
            with self.subTest(region=region_id, mutation=change):
                selection, inventory = rich_fixture()
                region = next(r for r in inventory["slides"][0]["regions"] if r["region_id"] == region_id)
                change(region)
                self.assert_rejected(validate_region_inventory, inventory, selection)

    def test_table_and_relationship_are_never_bitmap_carriers(self):
        _, inventory = rich_fixture()
        regions = inventory["slides"][0]["regions"]
        for kind in ("table", "connector"):
            objects = objects_for(regions)
            next(o for o in objects if o["kind"] == kind)["render_mode"] = "bitmap"
            self.assert_rejected(validate_faithful_objects, regions, objects)

    def test_contract_handles_arbitrary_three_page_ids_and_object_counts(self):
        selection, inventory = fixture()
        for i in range(2, 4):
            s, v = rich_fixture()
            s["slides"][0]["target_binding"].update(slide_id=f"different-{i}", page_order=i)
            v["slides"][0]["target_binding"] = deepcopy(s["slides"][0]["target_binding"])
            selection["slides"].extend(s["slides"]); inventory["slides"].extend(v["slides"])
        try:
            self.assertEqual(validate_region_inventory(inventory, selection), inventory)
        except ContractValidationError as error:
            self.fail(f"three distinct page identities were rejected: {error}")

    def test_real_material_image_hash_cannot_be_substituted(self):
        selection, inventory = rich_fixture()
        role = {"atom_id": "photo", "source_ref": ref("material-source"),
                "content_sha256": "e" * 64, "use": "real-material"}
        selection["slides"][0]["target_binding"]["material_roles"] = [role]
        inventory["slides"][0]["target_binding"] = deepcopy(selection["slides"][0]["target_binding"])
        photo = next(r for r in inventory["slides"][0]["regions"] if r["kind"] == "image")
        photo["material_binding"] = role
        self.assert_rejected(validate_region_inventory, inventory, selection)
        photo["appearance"]["asset_sha256"] = role["content_sha256"]
        self.assertEqual(validate_region_inventory(inventory, selection), inventory)

    def real_photo_fixture(self):
        selection, inventory = rich_fixture()
        role = {"atom_id": "customer-photo", "source_ref": ref("material-source"),
                "content_sha256": "e" * 64, "use": "real-material"}
        selection["slides"][0]["target_binding"]["material_roles"] = [role]
        inventory["slides"][0]["target_binding"] = deepcopy(selection["slides"][0]["target_binding"])
        photo = next(r for r in inventory["slides"][0]["regions"] if r["kind"] == "image")
        photo["material_binding"] = deepcopy(role)
        photo["appearance"]["asset_sha256"] = role["content_sha256"]
        return selection, inventory, role, photo

    def test_selected_real_material_cannot_lose_all_region_bindings(self):
        selection, inventory, _role, photo = self.real_photo_fixture()
        self.assertEqual(validate_region_inventory(inventory, selection), inventory)
        photo["material_binding"] = None
        with self.assertRaisesRegex(ContractValidationError, "real material.*region|material.*cover"):
            validate_region_inventory(inventory, selection)

    def test_clearing_photo_binding_cannot_authorize_replacement_image(self):
        selection, inventory, _role, photo = self.real_photo_fixture()
        photo["material_binding"] = None
        photo["appearance"].update(asset_ref=ref("image-asset", "d"), asset_sha256="d" * 64)
        with self.assertRaisesRegex(ContractValidationError, "real material.*region|material.*cover"):
            validate_region_inventory(inventory, selection)

    def test_photo_role_cannot_be_moved_onto_unrelated_native_title(self):
        selection, inventory, role, photo = self.real_photo_fixture()
        photo["material_binding"] = None
        regions = inventory["slides"][0]["regions"]
        regions[0]["material_binding"] = deepcopy(role)
        with self.assertRaisesRegex(ContractValidationError, "text.*material|material.*text"):
            validate_region_inventory(inventory, selection)
        with self.assertRaisesRegex(ContractValidationError, "text.*material|material.*text"):
            validate_faithful_objects(regions, objects_for(regions))

    def test_material_binding_to_ambiguous_shape_table_connector_is_capability_gap(self):
        for kind in ("shape", "table", "connector"):
            with self.subTest(kind=kind):
                selection, inventory, role, photo = self.real_photo_fixture()
                photo["material_binding"] = None
                regions = inventory["slides"][0]["regions"]
                next(r for r in regions if r["kind"] == kind)["material_binding"] = deepcopy(role)
                with self.assertRaisesRegex(ContractValidationError, "CapabilityGap"):
                    validate_region_inventory(inventory, selection)
                with self.assertRaisesRegex(ContractValidationError, "CapabilityGap"):
                    validate_faithful_objects(regions, objects_for(regions))

    def test_real_text_material_hash_is_exact_utf8_not_normalized(self):
        regions = self.inventory["slides"][0]["regions"]
        original = regions[0]["content"]["items"][0]["text"]
        role = {"atom_id": "customer-wording", "source_ref": ref("material-source"),
                "content_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                "use": "real-material"}
        self.binding["material_roles"] = [deepcopy(role)]
        self.inventory["slides"][0]["target_binding"] = deepcopy(self.binding)
        regions[0]["material_binding"] = deepcopy(role)
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)
        normalized_hash = hashlib.sha256(original.strip().encode("utf-8")).hexdigest()
        self.binding["material_roles"][0]["content_sha256"] = normalized_hash
        self.inventory["slides"][0]["target_binding"] = deepcopy(self.binding)
        regions[0]["material_binding"]["content_sha256"] = normalized_hash
        with self.assertRaisesRegex(ContractValidationError, "text.*material|material.*text"):
            validate_region_inventory(self.inventory, self.selection)

    def test_source_and_style_roles_need_not_appear_as_visual_objects(self):
        self.binding["material_roles"] = [
            {"atom_id": use, "source_ref": ref("material-source"),
             "content_sha256": "e" * 64, "use": use}
            for use in ("content-source", "style-reference")]
        self.inventory["slides"][0]["target_binding"] = deepcopy(self.binding)
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)

    def test_real_material_can_appear_in_multiple_verified_image_regions(self):
        selection, inventory, role, _photo = self.real_photo_fixture()
        regions = inventory["slides"][0]["regions"]
        ornament = next(r for r in regions if r["kind"] == "decoration")
        ornament["material_binding"] = deepcopy(role)
        ornament["appearance"]["asset_sha256"] = role["content_sha256"]
        self.assertEqual(validate_region_inventory(inventory, selection), inventory)
        self.assertEqual(validate_faithful_objects(regions, objects_for(regions)), objects_for(regions))

    def test_empty_table_cell_preserved_without_silent_text_fill(self):
        selection, inventory = rich_fixture()
        copy = selection["slides"][0]["selected_copy"]
        next(i for i in copy["items"] if i["item_id"] == "cell-1")["text"] = ""
        selection["slides"][0]["target_binding"] = binding(copy)
        inventory["slides"][0]["target_binding"] = deepcopy(selection["slides"][0]["target_binding"])
        table = next(r for r in inventory["slides"][0]["regions"] if r["kind"] == "table")
        table["content"]["items"][1]["text"] = ""
        table["appearance"]["cells"][1]["style"]["runs"][0]["text"] = ""
        try:
            self.assertEqual(validate_region_inventory(inventory, selection), inventory)
        except ContractValidationError as error:
            self.fail(f"empty visible table cell was not preserved: {error}")

    def test_raw_object_mapping_rejects_unclosed_selected_item(self):
        regions = self.inventory["slides"][0]["regions"]
        regions[0]["content"]["items"][0]["hidden_layout"] = "new-design"
        self.assert_rejected(validate_faithful_objects, regions, objects_for(regions))

    def test_native_changes_cannot_use_selected_deviation_as_exemption(self):
        deviation = {"candidate_ref": self.binding["candidate_ref"],
            "image_sha256": self.binding["target_image_sha256"], "item_id": "body",
            "difference_kind": "text", "before": "旧文案",
            "after": self.copy["items"][1]["text"],
            "decision_ref": ref("image-led-selection-confirmation")}
        self.binding["accepted_deviations"] = [deviation]
        self.inventory["slides"][0]["target_binding"] = deepcopy(self.binding)
        validate_region_inventory(self.inventory, self.selection)
        regions = self.inventory["slides"][0]["regions"]
        objects = objects_for(regions)
        objects[1]["content"]["items"][0]["text"] = "旧文案"
        objects[1]["appearance"]["runs"][0]["text"] = "旧文案"
        self.assert_rejected(validate_faithful_objects, regions, objects)


if __name__ == "__main__":
    unittest.main()
