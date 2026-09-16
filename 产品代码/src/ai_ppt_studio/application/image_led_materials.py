"""Read-only, current-project material extraction into verified memory snapshots.

This bridge does not grant authorization, create G0, or call a transport. The
caller must additionally enforce its trusted authorization scope. Image crops
are hashed as the exact PNG bytes returned here; whole images retain their bytes.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from typing import Any

from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
from ai_ppt_studio.application.material_finding_service import MaterialFindingService
from ai_ppt_studio.domains.materials.contracts import validate_material_inventory
from ai_ppt_studio.domains.materials.image_input_contracts import (
    USES, contains, exact, fail, location, overlaps, sha, text,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


ATOM_FIELDS = frozenset({
    "atom_id", "origin_kind", "origin_id", "source_ref", "source_id",
    "source_sha256", "source_location", "atom_type", "use", "content_sha256",
})
EVIDENCE_BUCKETS = (
    "facts", "user_confirmed_facts", "inferences", "conflicts", "unknowns",
    "evidence_gaps", "forbidden_extrapolations",
)
class ImageLedMaterialResolver(MaterialSourceReader):
    """Resolve one declared atom without writing or re-reading its payload later."""

    def __init__(self, kernel: ProjectKernel):
        self.kernel = kernel

    def resolve_atom(self, atom: dict, *, inventory_ref: str, evidence_ref: str,
                     slide: dict) -> dict[str, Any]:
        return self.resolve_atoms([atom], inventory_ref=inventory_ref,
                                  evidence_ref=evidence_ref, slide=slide)[0]

    def resolve_atoms(self, atoms: list[dict], *, inventory_ref: str, evidence_ref: str,
                      slide: dict) -> list[dict[str, Any]]:
        """One current source verification for the whole invocation-local batch."""
        if not isinstance(atoms, list):
            fail("SCHEMA", "material atoms must be a list")
        state = self.kernel.load()
        inventory = validate_material_inventory(self._current(
            state, "materials", inventory_ref, "material-inventory"))
        evidence = self._current(state, "content/evidence-book", evidence_ref,
                                 "presales-evidence-book")
        if evidence.get("material_inventory_ref") != inventory_ref:
            fail("CURRENT", "evidence does not bind the current material inventory")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        blueprint = self._current(state, "content/reading-blueprint", blueprint_ref,
                                  "reading-deck-blueprint")
        if (blueprint.get("project_id") != state.project_id
                or blueprint.get("evidence_book_ref") != evidence_ref
                or blueprint.get("source_version") != evidence.get("source_version")):
            fail("CURRENT", "reading blueprint and evidence lineage disagree")
        if not isinstance(slide, dict):
            fail("SLIDE", "current slide is required")
        matches = [row for row in self._rows(blueprint, "slides")
                   if row.get("slide_id") == slide.get("slide_id")]
        if len(matches) != 1 or matches[0] != slide:
            fail("SLIDE", "slide does not equal its exact current blueprint page")

        verified = MaterialFindingService(self.kernel).validate_evidence(evidence)
        return [self._resolve_verified_atom(atom, evidence, slide, verified) for atom in atoms]

    def _resolve_verified_atom(self, atom, evidence, slide, verified):
        exact(atom, set(ATOM_FIELDS), "material atom")
        atom = deepcopy(atom)
        for key in ("atom_id", "origin_id", "source_ref", "source_id"):
            text(atom[key], key)
        if atom["origin_kind"] not in {"evidence", "material-view"}:
            fail("ORIGIN", "unsupported atom origin")
        if atom["atom_type"] not in {"text", "image"}:
            fail("TYPE", "only text and image extraction are supported")
        if atom["use"] not in USES:
            fail("USE", "material use is unsupported")
        sha(atom["source_sha256"])
        sha(atom["content_sha256"])
        selector = location(atom["source_location"])

        declared = self._refs(evidence, "source_refs")
        if atom["source_ref"] not in declared:
            fail("SOURCE", "source reference is not declared by current evidence")
        finding = verified[atom["source_ref"]]
        source = finding["source"]
        if source["source_id"] != atom["source_id"]:
            fail("SOURCE", "finding belongs to a different inventory source")
        if source["sha256"] != atom["source_sha256"]:
            fail("SOURCE_HASH", "atom does not bind the registered source hash")
        if not contains(finding["finding"]["source_location"], selector):
            fail("ORIGIN", "atom expands beyond its finding source selector")
        banned_image_hashes = set()
        for excluded in self._refs(evidence, "excluded_material_refs"):
            resolved = verified[excluded]
            excluded_finding = resolved["finding"]
            if (resolved["source"]["sha256"] == atom["source_sha256"]
                    and overlaps(excluded_finding["source_location"], selector)):
                fail("EXCLUDED", "source content intersects an excluded source range")
            if excluded_finding["content_kind"] == "image" and excluded_finding["exclusion_mode"] == "image-content":
                banned_image_hashes.add(resolved["content_sha256"])
        view = self._origin(atom, evidence, slide)
        source_path, raw = finding["source_path"], finding["source_bytes"]
        if (selector == finding["finding"]["source_location"]
                and atom["atom_type"] == finding["finding"]["content_kind"]):
            extracted = finding
        else:
            extracted = self.extract_bytes(raw, selector, atom["atom_type"])
        extracted_bytes = extracted["data"]
        if atom["atom_type"] == "image" and extracted["content_sha256"] in banned_image_hashes:
            fail("EXCLUDED", "actual image bytes match a current image-content exclusion")
        if extracted["content_sha256"] != atom["content_sha256"]:
            fail("CONTENT_HASH", "actual extracted bytes differ from the selected content hash")
        result: dict[str, Any] = {
            "atom_id": atom["atom_id"], "type": atom["atom_type"], "use": atom["use"],
            "content_sha256": extracted["content_sha256"],
        }
        if atom["atom_type"] == "text":
            result["text"] = extracted_bytes.decode("utf-8")
        else:
            result.update(data_base64=base64.b64encode(extracted_bytes).decode("ascii"),
                          mime_type=extracted["mime_type"], width=extracted.get("width"), height=extracted.get("height"))
        if view is not None:
            view_path = self._path(view.get("asset_ref"), project_relative=True)
            view_bytes = raw if view_path == source_path else self._read(view_path)
            if view_bytes not in (raw, extracted_bytes):
                fail("VIEW", "material view bytes do not match the source or replayed extraction")
        return result

    def _current(self, state, slot: str, reference: str, kind: str) -> dict:
        if not reference or state.artifact_heads.get(slot) != reference:
            fail("CURRENT", f"{slot} must be the exact current artifact")
        parsed = ArtifactReference.parse(reference)
        if parsed.kind != kind:
            fail("CURRENT", f"{slot} has the wrong artifact kind")
        return self._payload(parsed)

    def _payload(self, parsed: ArtifactReference) -> dict:
        payload = self.kernel.artifacts.resolve(parsed)["payload"]
        if not isinstance(payload, dict):
            fail("SCHEMA", "artifact payload must be an object")
        return payload

    @staticmethod
    def _rows(payload: dict, field: str) -> list[dict]:
        values = payload.get(field)
        if not isinstance(values, list) or any(not isinstance(row, dict) for row in values):
            fail("SCHEMA", f"{field} must be an object list")
        return values

    @staticmethod
    def _refs(payload: dict, field: str) -> list[str]:
        values = payload.get(field)
        if (not isinstance(values, list) or any(not isinstance(ref, str) or not ref for ref in values)
                or len(set(values)) != len(values)):
            fail("SCHEMA", f"{field} must be a unique reference list")
        return values

    def _origin(self, atom: dict, evidence: dict, slide: dict) -> dict | None:
        if atom["origin_kind"] == "material-view":
            matches = [row for row in self._rows(slide, "material_views")
                       if row.get("material_view_id") == atom["origin_id"]]
            if (len(matches) != 1 or matches[0].get("source_ref") != atom["source_ref"]
                    or matches[0].get("evidence_identity") == "禁止使用"):
                fail("ORIGIN", "material view does not bind this exact source")
            return matches[0]
        matches = [(bucket, row) for bucket in EVIDENCE_BUCKETS
                   for row in self._rows(evidence, bucket) if row.get("item_id") == atom["origin_id"]]
        if len(matches) != 1:
            fail("ORIGIN", "evidence origin must identify exactly one current row")
        bucket, row = matches[0]
        if bucket == "forbidden_extrapolations" or row.get("identity") == "禁止使用":
            fail("EXCLUDED", "forbidden evidence cannot become a usable atom")
        if atom["source_ref"] not in self._refs(row, "source_refs"):
            fail("ORIGIN", "evidence row does not reference this source")
        page_refs = {ref for binding in self._rows(slide, "evidence_bindings")
                     for ref in self._refs(binding, "source_refs")}
        page_refs.update(view.get("source_ref") for view in self._rows(slide, "material_views"))
        decision = slide.get("customer_decision_item", {})
        if not isinstance(decision, dict):
            fail("SCHEMA", "customer decision must be an object")
        page_refs.update(self._refs(decision, "evidence_refs"))
        if atom["source_ref"] not in page_refs:
            fail("ORIGIN", "evidence source is not bound to this current page")
        return None



__all__ = ["ImageLedMaterialResolver"]
