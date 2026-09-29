"""Read-only, replayable OOXML text and embedded-image extraction.

No directory extraction, external resource resolution, OCR, or rendering. Page
order is presentation order; native text order is XML paragraph/run order.
"""
from __future__ import annotations

from io import BytesIO
import posixpath
import re
from urllib.parse import unquote, urlsplit
import warnings
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from PIL import Image, UnidentifiedImageError

from ai_ppt_studio.domains.materials.image_input_contracts import fail, location

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"p": P, "a": A, "r": R}
PRESENTATION_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
TEXT_MIME = "text/plain; charset=utf-8"
MAX_PART_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_BYTES = 512 * 1024 * 1024


def unsupported(message):
    fail("CAPABILITY_GAP", message)


def xml(raw):
    # Removing NULs only for declaration detection also covers UTF-16/32 XML;
    # parsing still receives the original bytes and honors the XML encoding.
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", raw.replace(b"\x00", b""), re.I):
        unsupported("OOXML declarations with entities or DTDs are unsupported")
    return ET.fromstring(raw)


def safe_name(name):
    decoded = unquote(name)
    if (not name or decoded != name or "\\" in name or "\x00" in name
            or name.startswith("/") or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        unsupported("unsafe or ambiguous ZIP member name")
    return name


def relationship_target(source, target):
    parsed = urlsplit(target)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or "\\" in target or "\x00" in target):
        unsupported("external or ambiguous OOXML relationship target")
    decoded = unquote(parsed.path)
    if not decoded or unquote(decoded) != decoded:
        unsupported("empty or multiply encoded OOXML relationship target")
    # A relationship may legitimately use ../media; normalization must stay
    # within the package. It never becomes a filesystem path.
    relative = decoded[1:] if decoded.startswith("/") else posixpath.join(posixpath.dirname(source), decoded)
    return safe_name(posixpath.normpath(relative))


class Package:
    def __init__(self, raw):
        self.file = ZipFile(BytesIO(raw))
        entries = self.file.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > MAX_PACKAGE_BYTES:
            unsupported("PPTX package exceeds supported in-memory extraction size")
        self.names = set()
        for entry in entries:
            name = entry.filename.rstrip("/") if entry.is_dir() else entry.filename
            safe_name(name)
            if name in self.names:
                unsupported("duplicate ZIP member identity")
            if (entry.flag_bits & 1 or entry.compress_type not in {ZIP_DEFLATED, ZIP_STORED}
                    or entry.file_size > MAX_PART_BYTES):
                unsupported("encrypted, unsupported, or oversized ZIP member")
            self.names.add(name)
            if "vbaproject" in name.lower() or "vbasignature" in name.lower():
                unsupported("macro-bearing PowerPoint packages are unsupported")
        self.rels = {}
        for name in sorted(self.names):
            if not name.endswith(".rels"):
                continue
            if name == "_rels/.rels":
                source = ""
            else:
                prefix, marker, filename = name.rpartition("/_rels/")
                if not marker or not filename.endswith(".rels"):
                    unsupported("relationship part has an invalid package location")
                source = prefix + "/" + filename[:-5]
                if source not in self.names:
                    unsupported("relationship source part is missing")
            root = self.read_xml(name)
            if root.tag != f"{{{REL}}}Relationships":
                unsupported("unsupported relationship document namespace")
            records = {}
            for item in root:
                identity, kind, target = (item.get(field) for field in ("Id", "Type", "Target"))
                if (item.tag != f"{{{REL}}}Relationship" or not identity or identity in records
                        or not kind or not target or item.get("TargetMode", "Internal") != "Internal"):
                    unsupported("external, missing, or ambiguous relationship identity")
                if "vba" in kind.lower() or "macro" in kind.lower():
                    unsupported("macro-bearing PowerPoint relationships are unsupported")
                resolved = relationship_target(source, target)
                if resolved not in self.names:
                    unsupported("unresolved OOXML relationship")
                records[identity] = (kind, resolved)
            self.rels[source] = records

    def read_xml(self, name):
        if name not in self.names:
            unsupported("required PPTX part is missing")
        return xml(self.file.read(name))

    def target(self, source, identity, kind):
        value = self.rels.get(source, {}).get(identity)
        if not value or value[0] != R + "/" + kind:
            unsupported("selected OOXML reference is missing or has the wrong type")
        return value[1]

    def slide(self, page):
        content_types = self.read_xml("[Content_Types].xml")
        if content_types.tag != f"{{{CT}}}Types":
            unsupported("unknown OOXML package format")
        overrides = {}
        for item in content_types:
            value = item.get("ContentType", "")
            if "macro" in value.lower() or "vba" in value.lower():
                unsupported("macro-bearing PowerPoint packages are unsupported")
            if item.tag == f"{{{CT}}}Override":
                part = item.get("PartName", "")
                if not part.startswith("/") or part in overrides:
                    unsupported("ambiguous content type override")
                overrides[part] = value
            elif item.tag != f"{{{CT}}}Default":
                unsupported("unknown content type declaration")
        main = [target for kind, target in self.rels.get("", {}).values() if kind == R + "/officeDocument"]
        if len(main) != 1 or overrides.get("/" + main[0]) != PRESENTATION_TYPE:
            unsupported("only unambiguous standard PPTX presentations are supported")
        presentation = self.read_xml(main[0])
        if presentation.tag != f"{{{P}}}presentation":
            unsupported("unknown presentation format")
        lists = presentation.findall("p:sldIdLst", NS)
        if len(lists) != 1:
            unsupported("missing or ambiguous presentation slide sequence")
        slides, seen_ids, seen_refs = [], set(), set()
        for item in lists[0]:
            identity, ref = item.get("id"), item.get(f"{{{R}}}id")
            if (item.tag != f"{{{P}}}sldId" or not identity or not ref
                    or identity in seen_ids or ref in seen_refs):
                unsupported("ambiguous presentation slide identity")
            seen_ids.add(identity); seen_refs.add(ref)
            slides.append(self.target(main[0], ref, "slide"))
        if len(set(slides)) != len(slides) or page > len(slides):
            unsupported("requested presentation page is missing or ambiguous")
        name = slides[page - 1]
        root = self.read_xml(name)
        trees = root.findall("p:cSld/p:spTree", NS)
        if root.tag != f"{{{P}}}sld" or len(trees) != 1:
            unsupported("unknown or ambiguous slide shape tree")
        return name, trees[0]


def paragraphs(body):
    result = []
    for paragraph in body.findall("a:p", NS):
        chunks = []
        for item in paragraph.iter():
            if item.tag == f"{{{A}}}t":
                chunks.append(item.text or "")
            elif item.tag == f"{{{A}}}br":
                chunks.append("\n")
            elif item.tag == f"{{{A}}}tab":
                chunks.append("\t")
        result.append("".join(chunks))
    return "\n".join(result)


def table_cells(obj):
    tables = obj.findall("a:graphic/a:graphicData/a:tbl", NS)
    if len(tables) != 1:
        unsupported("only an unambiguous native table is supported")
    table = tables[0]
    columns = table.findall("a:tblGrid/a:gridCol", NS)
    rows = []
    for row in table.findall("a:tr", NS):
        cells = row.findall("a:tc", NS)
        if not columns or len(cells) != len(columns):
            unsupported("table grid and cells disagree")
        values = []
        for cell in cells:
            if (any(cell.get(key, "1") != "1" for key in ("gridSpan", "rowSpan"))
                    or any(cell.get(key, "false") not in {"false", "0"} for key in ("hMerge", "vMerge"))):
                unsupported("merged table ranges need explicit grid reconstruction")
            bodies = cell.findall("a:txBody", NS)
            if len(bodies) != 1:
                unsupported("native table cell has no unambiguous text body")
            values.append(paragraphs(bodies[0]))
        rows.append(values)
    if not rows:
        unsupported("native table has no cells")
    return rows


def object_text(obj):
    if obj.tag == f"{{{P}}}graphicFrame":
        return "\n".join("\t".join(row) for row in table_cells(obj))
    bodies = obj.findall("p:txBody", NS)
    if len(bodies) != 1:
        unsupported("selected object has no unique native text body")
    return paragraphs(bodies[0])


def embedded_picture(package, part, obj):
    if obj.tag != f"{{{P}}}pic":
        unsupported("image extraction requires a native embedded picture")
    blips = obj.findall("p:blipFill/a:blip", NS)
    if len(blips) != 1 or blips[0].get(f"{{{R}}}link"):
        unsupported("linked or ambiguous picture data is unsupported")
    if any(item is not blips[0] and (
            item.get(f"{{{R}}}embed") is not None or item.get(f"{{{R}}}link") is not None)
            for item in obj.iter()):
        unsupported("picture has multiple embedded or linked representations")
    target = package.target(part, blips[0].get(f"{{{R}}}embed"), "image")
    data = package.file.read(target)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as decoded:
            if decoded.format not in {"PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"} or getattr(decoded, "n_frames", 1) != 1:
                unsupported("embedded image format needs an unavailable decoder")
            decoded.load()
            result = {"data": data, "mime_type": Image.MIME[decoded.format],
                      "width": decoded.width, "height": decoded.height}
        with Image.open(BytesIO(data)) as checked:
            checked.verify()
    return result


def extract_pptx(raw: bytes, selector: dict, atom_type: str) -> dict:
    """Return exact selected text or embedded image bytes; no external I/O.

    Page numbers are 1-based; table ranges are 0-based and end-exclusive.
    Unsupported/ambiguous constructs raise IMAGE_LED_CAPABILITY_GAP. Callers
    verify the complete source hash before this function and hash returned data.
    """
    selector = location(selector)
    if not isinstance(raw, bytes) or not raw or atom_type not in {"text", "image"}:
        unsupported("PPTX extraction requires package bytes and a supported atom type")
    if selector["kind"] not in {"page", "object", "table-range"}:
        unsupported("PPTX requires an explicit page, object, or native table range")
    try:
        package = Package(raw)
        try:
            part, tree = package.slide(selector["page"])
            ids = [item.get("id") for item in tree.iter(f"{{{P}}}cNvPr")]
            if any(not identity for identity in ids) or len(set(ids)) != len(ids):
                unsupported("missing or ambiguous native object identity")
            if any(item.tag.endswith("}AlternateContent") for item in tree.iter()):
                unsupported("alternate OOXML object representations need an explicit choice")
            paths = {"sp": "nvSpPr", "pic": "nvPicPr", "graphicFrame": "nvGraphicFramePr", "cxnSp": "nvCxnSpPr", "grpSp": "nvGrpSpPr"}
            supported_children = {f"{{{P}}}{kind}" for kind in paths} | {
                f"{{{P}}}nvGrpSpPr", f"{{{P}}}grpSpPr", f"{{{P}}}extLst"}
            for group in [tree, *tree.iter(f"{{{P}}}grpSp")]:
                if any(child.tag not in supported_children for child in group):
                    unsupported("slide contains an unsupported native object")
            objects = {}
            for item in tree.iter():
                for kind, parent in paths.items():
                    if item.tag == f"{{{P}}}{kind}":
                        identity = item.find(f"p:{parent}/p:cNvPr", NS)
                        if identity is None or not identity.get("id"):
                            unsupported("native object identity is missing")
                        objects[identity.get("id")] = item
            if selector["kind"] == "page":
                if atom_type != "text":
                    unsupported("page image extraction requires rendering and is unsupported")
                values = [object_text(obj) for obj in objects.values()
                          if obj.tag in {f"{{{P}}}sp", f"{{{P}}}graphicFrame", f"{{{P}}}cxnSp"}
                          and (obj.tag == f"{{{P}}}graphicFrame" or obj.find("p:txBody", NS) is not None)]
                return {"data": "\n".join(values).encode("utf-8"), "mime_type": TEXT_MIME}
            obj = objects.get(selector["object_id"])
            if obj is None:
                unsupported("requested native object does not exist")
            if selector["kind"] == "table-range":
                if atom_type != "text" or obj.tag != f"{{{P}}}graphicFrame":
                    unsupported("table ranges require a native text table")
                rows = table_cells(obj)
                if selector["row_end"] > len(rows) or selector["col_end"] > len(rows[0]):
                    unsupported("requested table range exceeds native cell coordinates")
                selected = [row[selector["col_start"]:selector["col_end"]]
                            for row in rows[selector["row_start"]:selector["row_end"]]]
                return {"data": "\n".join("\t".join(row) for row in selected).encode("utf-8"), "mime_type": TEXT_MIME}
            if atom_type == "image":
                return embedded_picture(package, part, obj)
            if obj.tag not in {f"{{{P}}}sp", f"{{{P}}}cxnSp", f"{{{P}}}graphicFrame"}:
                unsupported("selected object does not provide supported native text")
            return {"data": object_text(obj).encode("utf-8"), "mime_type": TEXT_MIME}
        finally:
            package.file.close()
    except (BadZipFile, ET.ParseError, OSError, RuntimeError, ValueError, KeyError,
            UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        unsupported("PPTX package or embedded image cannot be decoded: " + type(error).__name__)
