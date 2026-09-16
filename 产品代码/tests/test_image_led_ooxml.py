"""Synthetic OOXML ZIP bytes only; no customer data or PowerPoint acceptance."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import sys
import unittest
import warnings
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from ai_ppt_studio.application.image_led_ooxml import extract_pptx
from ai_ppt_studio.errors import ContractValidationError

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PRESENTATION_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"


def relationships(items):
    return f'<Relationships xmlns="{REL}">' + "".join(
        f'<Relationship Id="{identity}" Type="{R}/{kind}" Target="{target}"{mode}/>'
        for identity, kind, target, mode in items) + "</Relationships>"


def paragraph(text):
    return f'<a:p><a:r><a:t xml:space="preserve">{escape(text)}</a:t></a:r></a:p>'


def shape(identity, text):
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{identity}" name="shape-{identity}"/></p:nvSpPr><p:txBody>{paragraph(text)}</p:txBody></p:sp>'


def slide(objects):
    return f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>{objects}</p:spTree></p:cSld></p:sld>'


def image_bytes():
    stream = BytesIO()
    Image.new("RGB", (3, 2), color=(31, 62, 93)).save(stream, format="PNG")
    return stream.getvalue()


def package_parts():
    return {
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Override PartName="/ppt/presentation.xml" ContentType="{PRESENTATION_TYPE}"/></Types>',
        "_rels/.rels": relationships([("rOffice", "officeDocument", "ppt/presentation.xml", "")]),
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="secondFile"/><p:sldId id="257" r:id="firstFile"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": relationships([
            ("firstFile", "slide", "slides/slide1.xml", ""),
            ("secondFile", "slide", "slides/slide9.xml", ""),
        ]),
        "ppt/slides/slide1.xml": slide(shape("2", "second visible page")),
        "ppt/slides/slide9.xml": slide(shape("2", " first visible page \n") + shape("3", "another object")),
    }


def archive(parts, extras=()):
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as file:
        for name, value in list(parts.items()) + list(extras):
            file.writestr(name, value)
    return stream.getvalue()


class ImageLedOoxmlTests(unittest.TestCase):
    def test_page_order_uses_presentation_relationships_and_retains_text(self):
        raw = archive(package_parts())
        result = extract_pptx(raw, {"kind": "page", "page": 1}, "text")
        self.assertEqual(result, {"data": b" first visible page \n\nanother object", "mime_type": "text/plain; charset=utf-8"})
        self.assertEqual(extract_pptx(raw, {"kind": "page", "page": 2}, "text")["data"], b"second visible page")

    def test_object_identity_selects_exact_shape_and_preserves_runs_breaks_tabs(self):
        parts = package_parts()
        text_shape = shape("7", "unused").replace(paragraph("unused"),
            '<a:p><a:r><a:t> 甲 </a:t></a:r><a:br/><a:r><a:t>乙\t </a:t></a:r><a:tab/><a:fld><a:t> 丙</a:t></a:fld></a:p><a:p/>')
        parts["ppt/slides/slide9.xml"] = slide(shape("2", "excluded object") + text_shape)
        result = extract_pptx(archive(parts), {"kind": "object", "page": 1, "object_id": "7"}, "text")
        self.assertEqual(result["data"].decode(), " 甲 \n乙\t \t 丙\n")

    def test_table_range_uses_tabs_newlines_without_stripping_cells(self):
        parts = package_parts()
        rows = [[" A ", "B"], ["C", " D\n"]]
        table = '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="8" name="table"/></p:nvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblGrid><a:gridCol w="10"/><a:gridCol w="10"/></a:tblGrid>'
        table += "".join("<a:tr>" + "".join(f"<a:tc><a:txBody>{paragraph(value)}</a:txBody></a:tc>" for value in row) + "</a:tr>" for row in rows)
        parts["ppt/slides/slide9.xml"] = slide(table + "</a:tbl></a:graphicData></a:graphic></p:graphicFrame>")
        selector = {"kind": "table-range", "page": 1, "object_id": "8", "row_start": 0, "row_end": 2, "col_start": 0, "col_end": 2}
        self.assertEqual(extract_pptx(archive(parts), selector, "text")["data"], b" A \tB\nC\t D\n")
        self.assertEqual(extract_pptx(archive(parts), {**selector, "col_start": 1}, "text")["data"], b"B\n D\n")
        with self.assertRaises(ContractValidationError):
            extract_pptx(archive(parts), {**selector, "col_end": 3}, "text")

    def test_embedded_picture_returns_identical_bytes_and_decoded_dimensions(self):
        parts = package_parts()
        picture = '<p:pic><p:nvPicPr><p:cNvPr id="9" name="image"/></p:nvPicPr><p:blipFill><a:blip r:embed="rPicture"/></p:blipFill></p:pic>'
        parts["ppt/slides/slide9.xml"] = slide(picture)
        parts["ppt/slides/_rels/slide9.xml.rels"] = relationships([("rPicture", "image", "../media/image1.png", "")])
        original = image_bytes()
        parts["ppt/media/image1.png"] = original
        result = extract_pptx(archive(parts), {"kind": "object", "page": 1, "object_id": "9"}, "image")
        self.assertEqual(result, {"data": original, "mime_type": "image/png", "width": 3, "height": 2})
        self.assertEqual(hashlib.sha256(result["data"]).hexdigest(), hashlib.sha256(original).hexdigest())
        parts["ppt/media/image1.png"] = b"not a real PNG"
        with self.assertRaises(ContractValidationError):
            extract_pptx(archive(parts), {"kind": "object", "page": 1, "object_id": "9"}, "image")
        parts["ppt/media/image1.png"] = original
        parts["ppt/slides/slide9.xml"] = parts["ppt/slides/slide9.xml"].replace(
            '<a:blip r:embed="rPicture"/>',
            '<a:blip r:embed="rPicture"><a:extLst><a:ext uri="svg"><svg:svgBlip xmlns:svg="http://schemas.microsoft.com/office/drawing/2016/SVG/main" r:embed="rPicture"/></a:ext></a:extLst></a:blip>')
        with self.assertRaises(ContractValidationError):
            extract_pptx(archive(parts), {"kind": "object", "page": 1, "object_id": "9"}, "image")

    def test_zip_slip_duplicates_macros_unknown_format_and_external_links_fail(self):
        selector = {"kind": "page", "page": 1}
        variants = []
        for name in ("../outside", "/absolute", "C:/drive", "ppt\\escape", "ppt/%2e%2e/escape"):
            variants.append(archive({**package_parts(), name: b"ignored"}))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            variants.append(archive(package_parts(), [("ppt/slides/slide9.xml", slide(shape("2", "duplicate")))]))
        parts = package_parts(); parts["ppt/vbaProject.bin"] = b"macro"
        variants.append(archive(parts))
        parts = package_parts(); parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(PRESENTATION_TYPE, "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml")
        variants.append(archive(parts))
        parts = package_parts(); parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(PRESENTATION_TYPE, "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
        variants.append(archive(parts))
        parts = package_parts(); parts["ppt/slides/_rels/slide9.xml.rels"] = relationships([("rExternal", "image", "https://example.invalid/private.png", ' TargetMode="External"')])
        variants.append(archive(parts))
        for raw in variants:
            with self.subTest(size=len(raw)), self.assertRaises(ContractValidationError):
                extract_pptx(raw, selector, "text")

    def test_missing_ambiguous_and_unsafe_relationships_fail(self):
        variants = []
        parts = package_parts(); del parts["ppt/slides/slide9.xml"]
        variants.append(parts)
        parts = package_parts(); parts["ppt/_rels/presentation.xml.rels"] = relationships([
            ("secondFile", "slide", "slides/slide9.xml", ""), ("secondFile", "slide", "slides/slide1.xml", "")])
        variants.append(parts)
        parts = package_parts(); parts["ppt/_rels/presentation.xml.rels"] = relationships([("secondFile", "slide", "../../outside.xml", "")])
        variants.append(parts)
        parts = package_parts(); parts["_rels/.rels"] = relationships([
            ("rOffice", "officeDocument", "ppt/presentation.xml", ""),
            ("rOffice2", "officeDocument", "ppt/presentation.xml", "")])
        variants.append(parts)
        for parts in variants:
            with self.subTest(parts=list(parts)), self.assertRaises(ContractValidationError):
                extract_pptx(archive(parts), {"kind": "page", "page": 1}, "text")

    def test_object_ambiguity_missing_page_and_incompatible_atom_fail(self):
        parts = package_parts(); parts["ppt/slides/slide9.xml"] = slide(shape("2", "one") + shape("2", "duplicate"))
        with self.assertRaises(ContractValidationError):
            extract_pptx(archive(parts), {"kind": "object", "page": 1, "object_id": "2"}, "text")
        for selector, atom_type in [
            ({"kind": "page", "page": 3}, "text"),
            ({"kind": "object", "page": 1, "object_id": "missing"}, "text"),
            ({"kind": "object", "page": 1, "object_id": "2"}, "image"),
            ({"kind": "page", "page": 1}, "image"),
            ({"kind": "whole-source"}, "text"),
        ]:
            with self.subTest(selector=selector), self.assertRaises(ContractValidationError):
                extract_pptx(archive(package_parts()), selector, atom_type)

    def test_xml_entities_and_non_zip_input_fail_without_io(self):
        parts = package_parts()
        parts["ppt/slides/slide9.xml"] = '<!DOCTYPE data [<!ENTITY secret SYSTEM "file:///private/secret">]>' + slide(shape("2", "&secret;"))
        for raw in (archive(parts), b"not a PPTX", b""):
            with self.assertRaises(ContractValidationError):
                extract_pptx(raw, {"kind": "page", "page": 1}, "text")

    def test_utf16_dtd_hidden_macro_relationship_and_unknown_objects_fail(self):
        variants = []
        parts = package_parts()
        parts["ppt/slides/slide9.xml"] = ('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE p:sld [<!ENTITY changed "injected">]>' + slide(shape("2", "text")).replace("text</a:t>", "&changed;</a:t>")).encode("utf-16")
        variants.append(parts)
        parts = package_parts(); parts["ppt/renamed.bin"] = b"macro"
        parts["ppt/_rels/presentation.xml.rels"] = parts["ppt/_rels/presentation.xml.rels"].replace("</Relationships>", '<Relationship Id="rMacro" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="renamed.bin"/></Relationships>')
        variants.append(parts)
        parts = package_parts(); parts["ppt/slides/slide9.xml"] = slide(shape("2", "known") + '<p:contentPart r:id="customContent"/>')
        variants.append(parts)
        parts = package_parts(); parts["ppt/presentation.xml"] = parts["ppt/presentation.xml"].replace(P, "http://purl.oclc.org/ooxml/presentationml/main")
        variants.append(parts)
        for index, parts in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ContractValidationError):
                extract_pptx(archive(parts), {"kind": "page", "page": 1}, "text")


if __name__ == "__main__":
    unittest.main()
