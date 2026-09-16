"""Read-only source snapshots and faithful extraction shared by finding and input services."""
from __future__ import annotations
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat
from ai_ppt_studio.domains.materials.image_input_contracts import fail, location

MAX_SOURCE_BYTES = 64 * 1024 * 1024

class MaterialSourceReader:
    def __init__(self, kernel):
        self.kernel = kernel

    def extract(self, source: dict, selector: dict, content_kind: str, *, snapshots=None) -> dict:
        source_path = self._path(source["locator"], source_kind=source["kind"])
        key = (str(source_path), source["kind"], source["sha256"])
        raw = None if snapshots is None else snapshots.get(key)
        if raw is None:
            raw = self._read(source_path)
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                fail("SOURCE_HASH", "actual source bytes differ from the registered hash")
            if snapshots is not None:
                snapshots[key] = raw
        return {**self.extract_bytes(raw, selector, content_kind),
                "source_path": source_path, "source_bytes": raw}

    def extract_bytes(self, raw: bytes, selector: dict, content_kind: str) -> dict:
        """Extract from an already verified invocation-local source snapshot."""
        selector = location(selector)
        if content_kind not in {"text", "image"}:
            fail("TYPE", "only text and image extraction are supported")
        if selector["kind"] in {"page", "object", "table-range"}:
            from ai_ppt_studio.application.image_led_ooxml import extract_pptx
            result = extract_pptx(raw, selector, content_kind)
        elif content_kind == "text":
            result = {"data": self._text(raw, selector).encode("utf-8")}
        else:
            data, mime, width, height = self._image(raw, selector)
            result = {"data": data, "mime_type": mime, "width": width, "height": height}
        return {**result, "content_sha256": hashlib.sha256(result["data"]).hexdigest()}

    def _path(self, locator: str, *, source_kind: str = "file", project_relative=False) -> Path:
        if not isinstance(locator, str) or not locator or "\x00" in locator:
            fail("PATH", "source locator is missing or malformed")
        if source_kind in {"url", "directory"}:
            fail("CAPABILITY_GAP", "URL/directory material needs a verified local snapshot")
        if locator.startswith("project://"):
            locator = locator[len("project://"):]
            project_relative = True
        elif "://" in locator:
            fail("CAPABILITY_GAP", "source scheme has no replayable local snapshot")
        supplied = Path(locator)
        if ".." in supplied.parts or (project_relative and supplied.is_absolute()):
            fail("PATH", "project source locator cannot escape its project")
        path = supplied if supplied.is_absolute() else self.kernel.project_root / supplied
        # Do not resolve here: a resolve() would erase symlink evidence before open.
        return path

    @staticmethod
    def _read(path: Path) -> bytes:
        """Open each component relative to a no-follow directory descriptor."""
        flags = os.O_RDONLY | os.O_NOFOLLOW
        descriptor = None
        directory = None
        try:
            directory = os.open(path.anchor, flags | os.O_DIRECTORY)
            for component in path.parts[1:-1]:
                following = os.open(component, flags | os.O_DIRECTORY, dir_fd=directory)
                os.close(directory)
                directory = following
            descriptor = os.open(path.name, flags | os.O_NONBLOCK, dir_fd=directory)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                fail("CAPABILITY_GAP", "source is not a regular snapshot file")
            if metadata.st_size > MAX_SOURCE_BYTES:
                fail("CAPABILITY_GAP", "source exceeds the supported memory snapshot size")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                raw = stream.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                fail("CAPABILITY_GAP", "source exceeds the supported memory snapshot size")
            return raw
        except OSError:
            fail("PATH", "source is missing, unreadable, or crosses a symlink")
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if directory is not None:
                os.close(directory)

    @staticmethod
    def _text(raw: bytes, selector: dict) -> str:
        if selector["kind"] not in {"whole-source", "text-range"}:
            fail("LOCATION", "text extraction needs a whole-source or text-range selector")
        try:
            value = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            fail("CAPABILITY_GAP", "source is not a decodable UTF-8 text snapshot")
        if selector["kind"] == "text-range":
            if selector["end"] > len(value):
                fail("LOCATION", "text range extends outside the source")
            value = value[selector["start"]:selector["end"]]
        return value

    @staticmethod
    def _image(raw: bytes, selector: dict) -> tuple[bytes, str, int, int]:
        if selector["kind"] not in {"whole-source", "image-region"}:
            fail("LOCATION", "image extraction needs a whole-source or image-region selector")
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError:
            fail("CAPABILITY_GAP", "image extraction requires an available Pillow decoder")
        try:
            with Image.open(BytesIO(raw)) as source:
                source.load()
                mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(source.format)
                if not mime or getattr(source, "n_frames", 1) != 1:
                    fail("CAPABILITY_GAP", "only single-frame PNG/JPEG/WebP snapshots are supported")
                width, height = source.size
                if selector["kind"] == "whole-source":
                    return raw, mime, width, height
                x, y, w, h = (selector[key] for key in ("x", "y", "width", "height"))
                if x + w > width or y + h > height:
                    fail("LOCATION", "image region extends outside the source pixels")
                with source.crop((x, y, x + w, y + h)) as cropped:
                    output = BytesIO()
                    cropped.save(output, format="PNG")
                    return output.getvalue(), "image/png", w, h
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            fail("CAPABILITY_GAP", "image snapshot cannot be decoded/extracted faithfully")
