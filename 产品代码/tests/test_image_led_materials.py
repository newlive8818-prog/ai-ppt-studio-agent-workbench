"""Real-source, zero-write tests for the Image-led material bridge (no G0 claims)."""
from __future__ import annotations

import base64
import copy
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from PIL import Image
except ImportError:
    Image = None

from ai_ppt_studio.application.image_led_materials import ImageLedMaterialResolver
from ai_ppt_studio.application.material_finding_service import MaterialFindingService
from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
from ai_ppt_studio.domains.materials.contracts import validate_material_inventory
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import blueprint, evidence_book


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class MaterialFixture:
    def __init__(self, root: Path, raw: bytes = "  原文\n换行🙂\n ".encode()):
        self.root = root
        self.kernel = ProjectKernel.initialize(root, project_id="material-test")
        self.path = root / "materials" / "source.dat"
        self.path.parent.mkdir()
        self.path.write_bytes(raw)
        self.source = {"source_id": "source-one", "origin": "user-provided", "kind": "file",
                       "locator": "project://materials/source.dat", "sha256": digest(raw)}
        self.finding = {"source_id": "source-one", "source_sha256": digest(raw),
            "content_kind": "image" if raw.startswith(b"\x89PNG") else "text"}
        self.allow_corrupt_finding = False
        self.extra: tuple[tuple[str, dict], ...] = ()
        self.evidence = evidence_book()
        self.blueprint = blueprint()
        self.blueprint["project_id"] = "material-test"
        self.publish()

    def publish(self):
        inventory = validate_material_inventory({"sources": [self.source]})
        self.inventory_ref = str(self.kernel.artifacts.reference_for("material-inventory", inventory))
        if self.kernel.load().artifact_heads.get("materials") != self.inventory_ref:
            self.kernel.commit(command_id=f"fixture-inventory-{self.kernel.load().revision}",
                expected_revision=self.kernel.load().revision,event_type="test.inventory",
                artifact_updates={"materials": ("material-inventory", inventory)})
        def register(value):
            request = {"material_inventory_ref": self.inventory_ref, "source_id": value["source_id"],
                "source_sha256": value["source_sha256"], "source_location": value.get("source_location", {"kind": "whole-source"}),
                "content_kind": value.get("content_kind", "text"), "exclusion_mode": value.get("exclusion_mode", "scope")}
            service = MaterialFindingService(self.kernel)
            try:
                ref = service.register(f"fixture-finding-{self.kernel.load().revision}", self.kernel.load().revision, request)
                return ref, self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]
            except ContractValidationError:
                if not self.allow_corrupt_finding:
                    raise
                # These tests intentionally corrupt current sources and selectors;
                # a forged artifact tests the consumer's fail-closed boundary.
                payload = {"schema_version": 1, "artifact_type": "material-finding", "project_id": self.kernel.project_id,
                    **request, "content_sha256": value.get("content_sha256", self.source["sha256"])}
                ref = str(self.kernel.artifacts.reference_for("material-finding", payload))
                self.kernel.commit(command_id=f"corrupt-finding-{self.kernel.load().revision}",
                    expected_revision=self.kernel.load().revision,event_type="test.corrupt-finding",artifact_updates={},
                    detached_artifacts=(("material-finding",payload),))
                return ref,payload
        self.finding_ref, self.finding = register(self.finding)
        for kind, value in self.extra:
            old_ref = str(self.kernel.artifacts.reference_for(kind,value))
            new_ref, _ = register(value)
            self.evidence["excluded_material_refs"] = [new_ref if ref == old_ref else ref for ref in self.evidence["excluded_material_refs"]]
        self.evidence["material_inventory_ref"] = self.inventory_ref
        self.evidence["source_refs"] = [self.finding_ref]
        for bucket in ("facts", "user_confirmed_facts", "inferences", "conflicts", "unknowns", "evidence_gaps", "forbidden_extrapolations"):
            for row in self.evidence[bucket]:
                row["source_refs"] = [self.finding_ref]
        self.evidence_ref = str(self.kernel.artifacts.reference_for("presales-evidence-book", self.evidence))
        self.blueprint["evidence_book_ref"] = self.evidence_ref
        self.blueprint["slides"][0]["evidence_bindings"][0]["source_refs"] = [self.finding_ref]
        self.blueprint["slides"][0]["material_views"][0]["source_ref"] = self.finding_ref
        self.blueprint["slides"][0]["material_views"][0]["asset_ref"] = "materials/source.dat"
        self.kernel.commit(command_id=f"publish-{self.kernel.load().revision}",
                           expected_revision=self.kernel.load().revision, event_type="test.sources-published",
                           artifact_updates={
                               "materials": ("material-inventory", inventory),
                               "content/evidence-book": ("presales-evidence-book", self.evidence),
                               "content/reading-blueprint": ("reading-deck-blueprint", self.blueprint)},
                           )
        self.slide = copy.deepcopy(self.blueprint["slides"][0])
        self.atom = {"atom_id": "atom-one", "origin_kind": "evidence", "origin_id": "fact-1",
                     "source_ref": self.finding_ref, "source_id": self.source["source_id"],
                     "source_sha256": self.source["sha256"], "source_location": {"kind": "whole-source"},
                     "atom_type": "text", "use": "content-source", "content_sha256": self.source["sha256"]}

    def resolve(self, atom=None, **kwargs):
        return ImageLedMaterialResolver(self.kernel).resolve_atom(
            self.atom if atom is None else atom,
            inventory_ref=kwargs.get("inventory_ref", self.inventory_ref),
            evidence_ref=kwargs.get("evidence_ref", self.evidence_ref),
            slide=kwargs.get("slide", self.slide))

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()}


class ImageLedMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = MaterialFixture(Path(self.temp.name).resolve())

    def rejected_without_writes(self, pattern, atom=None, **kwargs):
        before = self.fixture.snapshot()
        with self.assertRaisesRegex((ContractValidationError, ArtifactReferenceError), pattern):
            self.fixture.resolve(atom, **kwargs)
        self.assertEqual(self.fixture.snapshot(), before)

    def use_pptx(self, parts=None, *, finding_selector=None):
        from tests.test_image_led_ooxml import archive, package_parts
        raw = archive(package_parts() if parts is None else parts)
        self.fixture.path.write_bytes(raw)
        self.fixture.source["sha256"] = digest(raw)
        self.fixture.finding["source_sha256"] = digest(raw)
        self.fixture.finding["source_location"] = finding_selector or {"kind": "page", "page": 1}
        self.fixture.publish()
        return raw

    def test_pptx_page_and_object_replay_real_source_bytes_without_writes(self):
        self.use_pptx(finding_selector={"kind": "page", "page": 1})
        before = self.fixture.snapshot()
        for selector, expected in [
            ({"kind": "page", "page": 1}, " first visible page \n\nanother object"),
            ({"kind": "object", "page": 1, "object_id": "2"}, " first visible page \n"),
        ]:
            atom = {**self.fixture.atom, "source_location": selector,
                    "content_sha256": digest(expected.encode())}
            self.assertEqual(self.fixture.resolve(atom)["text"], expected)
        self.assertEqual(self.fixture.snapshot(), before)

    def test_pptx_native_table_range_replays_cells_from_object_finding(self):
        from tests.test_image_led_ooxml import package_parts, slide, paragraph
        parts = package_parts()
        table = '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="8" name="table"/></p:nvGraphicFramePr><a:graphic><a:graphicData><a:tbl><a:tblGrid><a:gridCol w="10"/><a:gridCol w="10"/></a:tblGrid><a:tr>'
        table += ''.join('<a:tc><a:txBody>' + paragraph(value) + '</a:txBody></a:tc>' for value in [" 未删空白 ", "第二列"])
        parts["ppt/slides/slide9.xml"] = slide(table + '</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
        self.use_pptx(parts, finding_selector={"kind": "object", "page": 1, "object_id": "8"})
        expected = " 未删空白 \t第二列"
        atom = {**self.fixture.atom, "source_location": {"kind": "table-range", "page": 1,
            "object_id": "8", "row_start": 0, "row_end": 1, "col_start": 0, "col_end": 2},
            "content_sha256": digest(expected.encode())}
        before = self.fixture.snapshot()
        self.assertEqual(self.fixture.resolve(atom)["text"], expected)
        self.assertEqual(self.fixture.snapshot(), before)

    def test_pptx_picture_and_view_must_match_exact_embedded_bytes(self):
        from tests.test_image_led_ooxml import package_parts, slide, image_bytes, relationships
        parts = package_parts(); raw_image = image_bytes()
        parts["ppt/slides/slide9.xml"] = slide('<p:pic><p:nvPicPr><p:cNvPr id="9" name="image"/></p:nvPicPr><p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>')
        parts["ppt/slides/_rels/slide9.xml.rels"] = relationships([("rPicture", "image", "../media/picture.png", "")])
        parts["ppt/media/picture.png"] = raw_image
        self.fixture.finding["content_kind"] = "image"
        self.use_pptx(parts, finding_selector={"kind": "object", "page": 1, "object_id": "9"})
        view_path = self.fixture.root / "materials" / "view.png"
        view_path.write_bytes(raw_image)
        self.fixture.blueprint["slides"][0]["material_views"][0]["asset_ref"] = "materials/view.png"
        self.fixture.kernel.commit(command_id="pptx-view", expected_revision=self.fixture.kernel.load().revision,
            event_type="test.view-bound", artifact_updates={
                "content/reading-blueprint": ("reading-deck-blueprint", self.fixture.blueprint)})
        self.fixture.slide = copy.deepcopy(self.fixture.blueprint["slides"][0])
        atom = {**self.fixture.atom, "atom_type": "image", "origin_kind": "material-view",
            "origin_id": "S01-M01", "use": "real-material", "content_sha256": digest(raw_image),
            "source_location": {"kind": "object", "page": 1, "object_id": "9"}}
        before = self.fixture.snapshot()
        result = self.fixture.resolve(atom)
        self.assertEqual(base64.b64decode(result["data_base64"]), raw_image)
        self.assertEqual((result["mime_type"], result["width"], result["height"]), ("image/png", 3, 2))
        self.assertEqual(self.fixture.snapshot(), before)
        view_path.write_bytes(png(Image.new("RGB", (3, 2), "blue")))
        self.rejected_without_writes("VIEW", atom)

    def test_pptx_source_and_page_changes_cannot_reuse_old_selection(self):
        from tests.test_image_led_ooxml import archive, package_parts, slide, shape
        parts = package_parts(); original = self.use_pptx(parts)
        atom = {**self.fixture.atom, "source_location": {"kind": "page", "page": 1},
            "content_sha256": digest(b" first visible page \n\nanother object")}
        self.assertEqual(self.fixture.resolve(atom)["text"], " first visible page \n\nanother object")
        self.rejected_without_writes("ORIGIN", {**atom, "source_location": {"kind": "page", "page": 2}})
        parts["ppt/slides/slide9.xml"] = slide(shape("2", "changed customer number"))
        self.fixture.path.write_bytes(archive(parts))
        self.rejected_without_writes("SOURCE_HASH", atom)
        self.use_pptx(parts)
        self.rejected_without_writes("CONTENT_HASH", {**self.fixture.atom,
            "source_location": atom["source_location"], "content_sha256": atom["content_sha256"]})

    def test_pptx_external_relationship_is_rejected_without_business_writes(self):
        self.fixture.allow_corrupt_finding = True
        from tests.test_image_led_ooxml import package_parts, relationships
        parts = package_parts()
        parts["ppt/slides/_rels/slide9.xml.rels"] = relationships([
            ("rExternal", "image", "https://example.invalid/confidential.png", ' TargetMode="External"')])
        self.use_pptx(parts)
        self.rejected_without_writes("CAPABILITY_GAP", {**self.fixture.atom,
            "source_location": {"kind": "page", "page": 1},
            "content_sha256": digest(b" first visible page \n\nanother object")})

    def test_text_is_exact_utf8_in_memory_without_paths_or_writes(self):
        before = self.fixture.snapshot()
        result = self.fixture.resolve()
        self.assertEqual(result, {"atom_id": "atom-one", "type": "text", "use": "content-source",
                                  "content_sha256": self.fixture.source["sha256"], "text": "  原文\n换行🙂\n "})
        self.fixture.path.write_text("later changed")
        self.assertEqual(result["text"], "  原文\n换行🙂\n ")
        self.fixture.path.write_bytes("  原文\n换行🙂\n ".encode())
        self.assertEqual(self.fixture.snapshot(), before)

    def test_text_range_uses_unicode_characters_and_checks_exact_extraction_hash(self):
        atom = {**self.fixture.atom, "source_location": {"kind": "text-range", "start": 3, "end": 9},
                "content_sha256": digest("文\n换行🙂\n".encode())}
        resolved = self.fixture.resolve(atom)
        self.assertIsInstance(resolved, dict)
        self.assertEqual(resolved["text"], "文\n换行🙂\n")
        atom["content_sha256"] = "0" * 64
        self.rejected_without_writes("CONTENT_HASH", atom)

    def test_style_reference_snapshot_never_promotes_itself_to_factual_evidence(self):
        atom = {**self.fixture.atom, "use": "style-reference"}
        before = self.fixture.snapshot()
        result = self.fixture.resolve(atom)
        self.assertEqual(result, {"atom_id": "atom-one", "type": "text", "use": "style-reference",
                                  "content_sha256": atom["content_sha256"], "text": self.fixture.path.read_text()})
        self.assertNotIn("statement", result)
        self.assertNotIn("evidence_identity", result)
        self.assertEqual(self.fixture.snapshot(), before)

    def test_mutated_source_and_claimed_hash_are_rejected(self):
        self.fixture.path.write_bytes(b"changed source")
        self.rejected_without_writes("SOURCE_HASH")

    def test_stale_inventory_evidence_or_slide_cannot_supply_current_inputs(self):
        old_inventory, old_evidence = self.fixture.inventory_ref, self.fixture.evidence_ref
        self.fixture.source["label"] = "new inventory"
        self.fixture.publish()
        self.rejected_without_writes("CURRENT", inventory_ref=old_inventory)
        self.rejected_without_writes("CURRENT", evidence_ref=old_evidence)
        for field, value in (("slide_id", "S99"), ("order", 2), ("neutral_title", "forged title")):
            with self.subTest(field=field):
                self.rejected_without_writes("SLIDE", slide={**self.fixture.slide, field: value})

    def test_unknown_origin_and_unbound_source_cannot_be_selected(self):
        for changes, error in (({"origin_id": "unknown"}, "ORIGIN"),
                               ({"source_id": "unknown"}, "SOURCE"),
                               ({"source_sha256": "0" * 64}, "SOURCE_HASH"),
                               ({"source_ref": "artifact://material-finding/" + "a" * 64}, "ORIGIN|SOURCE|Artifact")):
            with self.subTest(changes=changes):
                self.rejected_without_writes(error, {**self.fixture.atom, **changes})

    def test_finding_payload_cannot_bind_a_different_inventory_source(self):
        self.fixture.allow_corrupt_finding = True
        self.fixture.finding["source_id"] = "foreign-source"
        self.fixture.publish()
        self.rejected_without_writes("SOURCE")

    def test_tampered_artifact_envelope_fails_before_source_use(self):
        artifact = self.fixture.kernel.artifacts.path_for(ArtifactReference.parse(self.fixture.finding_ref))
        artifact.write_text('{}')
        self.rejected_without_writes("Artifact hash mismatch")

    def test_excluded_finding_propagates_to_same_source_with_different_atom_and_finding_ids(self):
        excluded_payload = {**self.fixture.finding, "source_location": {"kind": "text-range", "start": 0, "end": 2}}
        excluded_ref = str(self.fixture.kernel.artifacts.reference_for("material-finding", excluded_payload))
        self.fixture.evidence["excluded_material_refs"] = [excluded_ref]
        self.fixture.extra = (("material-finding", excluded_payload),)
        self.fixture.publish()
        self.rejected_without_writes("EXCLUDED", {**self.fixture.atom, "atom_id": "new-identity"})

    def test_unresolvable_excluded_source_fails_closed(self):
        self.fixture.evidence["excluded_material_refs"] = ["artifact://material-finding/" + "c" * 64]
        self.fixture.publish()
        self.rejected_without_writes("Artifact|EXCLUDED")

    def test_local_finding_exclusion_blocks_overlap_but_not_disjoint_text(self):
        excluded_payload = {**self.fixture.finding, "source_location": {"kind": "text-range", "start": 0, "end": 2}}
        excluded_ref = str(self.fixture.kernel.artifacts.reference_for("material-finding", excluded_payload))
        self.fixture.evidence["excluded_material_refs"] = [excluded_ref]
        self.fixture.extra = (("material-finding", excluded_payload),)
        self.fixture.publish()
        atom = {**self.fixture.atom, "source_location": {"kind": "text-range", "start": 3, "end": 9},
                "content_sha256": digest("文\n换行🙂\n".encode())}
        try:
            result = self.fixture.resolve(atom)
        except ContractValidationError as error:
            self.fail(f"Disjoint source region must remain usable: {error}")
        self.assertEqual(result["text"], "文\n换行🙂\n")
        atom.update(atom_id="renamed-atom", source_location={"kind": "text-range", "start": 1, "end": 3},
                    content_sha256=digest(" 原".encode()))
        self.rejected_without_writes("EXCLUDED", atom)

    def test_atom_cannot_expand_beyond_its_finding_source_selector(self):
        self.fixture.finding["source_location"] = {"kind": "text-range", "start": 2, "end": 9}
        self.fixture.publish()
        self.rejected_without_writes("ORIGIN|LOCATION", self.fixture.atom)

    def test_foreign_project_finding_and_nonmaterial_kind_cannot_authorize_sources(self):
        fake = {"source_id": "source-one"}
        fake_ref = str(self.fixture.kernel.artifacts.reference_for("mission-draft", fake))
        self.fixture.kernel.commit(command_id="fake-kind", expected_revision=self.fixture.kernel.load().revision,
                                   event_type="test.nonmaterial", artifact_updates={},
                                   detached_artifacts=(("mission-draft", fake),))
        self.rejected_without_writes("SOURCE", {**self.fixture.atom, "source_ref": fake_ref})
        from ai_ppt_studio.kernel.artifacts import ArtifactRepository
        foreign = ArtifactRepository(self.fixture.root, project_id="foreign")
        foreign_ref = str(foreign.put("material-finding", fake))
        self.rejected_without_writes("SOURCE", {**self.fixture.atom, "source_ref": foreign_ref})
        before = self.fixture.snapshot()
        with self.assertRaisesRegex(ArtifactReferenceError, "another project"):
            MaterialFindingService(self.fixture.kernel).resolve(foreign_ref, inventory_ref=self.fixture.inventory_ref)
        self.assertEqual(before, self.fixture.snapshot())

    def test_symlink_file_parent_and_project_path_escape_are_rejected(self):
        self.fixture.allow_corrupt_finding = True
        original = self.fixture.path.read_bytes()
        outside = self.fixture.root.parent / (self.fixture.root.name + "-outside")
        outside.write_bytes(original)
        self.addCleanup(outside.unlink, missing_ok=True)
        self.fixture.path.unlink()
        self.fixture.path.symlink_to(outside)
        self.rejected_without_writes("PATH")
        self.fixture.path.unlink()
        self.fixture.path.write_bytes(original)
        for locator in ("project://../" + outside.name, "../" + outside.name):
            self.fixture.source["locator"] = locator
            self.fixture.publish()
            self.rejected_without_writes("PATH")
        directory = self.fixture.root / "alias"
        directory.symlink_to(self.fixture.path.parent, target_is_directory=True)
        self.fixture.source["locator"] = "project://alias/source.dat"
        self.fixture.publish()
        self.rejected_without_writes("PATH")

    def test_registered_absolute_regular_file_is_readable(self):
        self.fixture.source["locator"] = str(self.fixture.path)
        self.fixture.publish()
        resolved = self.fixture.resolve()
        self.assertIsInstance(resolved, dict)
        self.assertEqual(resolved["text"], self.fixture.path.read_text())

    def test_url_directory_and_unreplayable_page_report_capability_gap(self):
        self.fixture.allow_corrupt_finding = True
        for locator in ("https://example.invalid/client.docx", str(self.fixture.path.parent)):
            self.fixture.source["locator"] = locator
            self.fixture.publish()
            self.rejected_without_writes("CAPABILITY_GAP")
        self.fixture.source["locator"] = "project://materials/source.dat"
        self.fixture.publish()
        self.rejected_without_writes("CAPABILITY_GAP", {**self.fixture.atom, "source_location": {"kind": "page", "page": 1}})

    def test_invalid_utf8_and_out_of_bounds_range_fail_without_normalization(self):
        self.fixture.allow_corrupt_finding = True
        self.fixture.path.write_bytes(b"\xff\xfe")
        self.fixture.source["sha256"] = digest(b"\xff\xfe")
        self.fixture.finding["source_sha256"] = self.fixture.source["sha256"]
        self.fixture.publish()
        self.rejected_without_writes("CAPABILITY_GAP")

    def test_closed_atom_schema_and_type_use_selectors_are_validated(self):
        for changes in ({"extra": "unsafe"}, {"atom_type": "pptx"}, {"use": "forbidden"},
                        {"source_location": {"kind": "text-range", "start": 0, "end": 999}},
                        {"source_location": {"kind": "image-region", "x": 0, "y": 0, "width": 1, "height": 1}}):
            with self.subTest(changes=changes):
                self.rejected_without_writes("SCHEMA|TYPE|USE|LOCATION|CAPABILITY_GAP", {**self.fixture.atom, **changes})

    @unittest.skipIf(Image is None, "Pillow decoder unavailable on this interpreter")
    def test_image_whole_preserves_actual_file_and_crop_uses_real_pixels(self):
        source = Image.new("RGB", (6, 4), "red")
        source.putpixel((2, 1), (0, 255, 0))
        raw = png(source)
        self.fixture.path.write_bytes(raw)
        self.fixture.source["sha256"] = digest(raw)
        self.fixture.finding["source_sha256"] = digest(raw)
        self.fixture.finding["content_kind"] = "image"
        self.fixture.publish()
        atom = {**self.fixture.atom, "atom_type": "image", "origin_kind": "material-view", "origin_id": "S01-M01", "use": "real-material"}
        whole = self.fixture.resolve(atom)
        self.assertIsInstance(whole, dict)
        self.assertEqual(base64.b64decode(whole["data_base64"]), raw)
        self.assertEqual((whole["width"], whole["height"], whole["mime_type"]), (6, 4, "image/png"))
        expected = png(source.crop((1, 1, 4, 3)))
        atom.update(source_location={"kind": "image-region", "x": 1, "y": 1, "width": 3, "height": 2}, content_sha256=digest(expected))
        cropped = self.fixture.resolve(atom)
        self.assertEqual(base64.b64decode(cropped["data_base64"]), expected)
        self.assertEqual((cropped["width"], cropped["height"]), (3, 2))
        atom["source_location"]["width"] = 30
        self.rejected_without_writes("LOCATION", atom)

    @unittest.skipIf(Image is None, "Pillow decoder unavailable on this interpreter")
    def test_view_asset_cannot_silently_substitute_another_image(self):
        raw = png(Image.new("RGB", (3, 2), "red"))
        self.fixture.path.write_bytes(raw)
        self.fixture.source["sha256"] = digest(raw)
        self.fixture.finding["source_sha256"] = digest(raw)
        self.fixture.finding["content_kind"] = "image"
        self.fixture.publish()
        other = self.fixture.root / "other.png"
        other.write_bytes(png(Image.new("RGB", (3, 2), "blue")))
        self.fixture.blueprint["slides"][0]["material_views"][0]["asset_ref"] = "other.png"
        # Publish preserves an explicitly different project asset for this check.
        self.fixture.kernel.commit(command_id="replace-view", expected_revision=self.fixture.kernel.load().revision,
                                   event_type="test.view-replaced", artifact_updates={
                                       "content/reading-blueprint": ("reading-deck-blueprint", self.fixture.blueprint)})
        self.fixture.slide = copy.deepcopy(self.fixture.blueprint["slides"][0])
        atom = {**self.fixture.atom, "atom_type": "image", "origin_kind": "material-view", "origin_id": "S01-M01", "use": "real-material"}
        self.rejected_without_writes("CONTENT_HASH|VIEW", atom)


if __name__ == "__main__":
    unittest.main()
