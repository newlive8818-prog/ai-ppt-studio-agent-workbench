"""Evidence checks for human-controlled G0-G4 quality gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .errors import GateBlockedError, ProjectNotFoundError
from .models import ArtifactKind, Gate
from .paths import PathPolicy, is_within


class GateEvidenceChecker:
    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.artifacts = ArtifactStore(self.project_root, policy)

    def require(self, gate: Gate) -> tuple[str, ...]:
        evidence, missing = self.inspect(gate)
        if missing:
            raise GateBlockedError(gate.value, tuple(missing))
        return tuple(evidence)

    def inspect(self, gate: Gate) -> tuple[list[str], list[str]]:
        if gate is Gate.G0:
            return self._g0()
        if gate is Gate.G1:
            return self._g1()
        if gate is Gate.G2:
            return self._g2()
        if gate is Gate.G3:
            return self._g3()
        return self._g4()

    def _g0(self) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        missing: list[str] = []
        mission = self._artifact(ArtifactKind.MISSION)
        blueprint = self._artifact(ArtifactKind.CONTENT_BLUEPRINT)
        if mission:
            evidence.append(self._ref(mission.path))
        else:
            missing.append("mission")
        if blueprint:
            evidence.append(self._ref(blueprint.path))
            slides = blueprint.payload.get("slides", [])
            if not any(
                isinstance(slide, dict)
                and (slide.get("source_refs") or slide.get("material_refs"))
                for slide in slides
            ):
                missing.append("content-blueprint.source-refs")
        else:
            missing.append("content-blueprint")
        return evidence, missing

    def _g1(self) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        missing: list[str] = []
        concept = self._artifact(ArtifactKind.CONCEPT_SET)
        if concept:
            directions = concept.payload.get("directions", [])
            ids = {
                str(item.get("id"))
                for item in directions
                if isinstance(item, dict) and item.get("id")
            }
            if len(ids) < 2:
                missing.append("concept-set.two-structural-directions")
            evidence.append(self._ref(concept.path))
        else:
            missing.append("concept-set")
        decision = self._latest_concept_decision()
        if decision:
            evidence.append(f"decision://{decision}")
        else:
            missing.append("human-concept-decision")
        return evidence, missing

    def _g2(self) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        missing: list[str] = []
        engineering = self._artifact(ArtifactKind.ENGINEERING_SAMPLES)
        if not engineering:
            return evidence, ["engineering-samples"]
        evidence.append(self._ref(engineering.path))
        payload = engineering.payload
        samples = payload.get("samples", [])
        if not samples:
            missing.append("engineering-samples.sample")
        for index, sample in enumerate(samples, start=1):
            if not isinstance(sample, dict) or not sample.get("editable"):
                missing.append(f"engineering-samples.sample-{index}.editable")
                continue
            render_ref = str(sample.get("render_ref", ""))
            if not self._exists(render_ref):
                missing.append(f"engineering-samples.sample-{index}.render")
        coverage = payload.get("native_coverage") or {}
        if not isinstance(coverage, dict) or not any(
            coverage.get(key) for key in ("text", "shape", "chart", "image_crop")
        ):
            missing.append("engineering-samples.native-coverage")
        if not isinstance(coverage, dict) or coverage.get("whole_slide_bitmap") is not False:
            missing.append("engineering-samples.no-whole-slide-bitmap")
        if payload.get("qa_status") != "passed":
            missing.append("engineering-samples.qa-passed")
        return evidence, missing

    def _g3(self) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        missing: list[str] = []
        for kind, label in (
            (ArtifactKind.VISUAL_CONTRACT, "visual-contract"),
            (ArtifactKind.SLIDE_SCENE_GRAPH, "slide-scene-graph"),
        ):
            artifact = self._artifact(kind)
            if artifact:
                evidence.append(self._ref(artifact.path))
            else:
                missing.append(label)
        return evidence, missing

    def _g4(self) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        missing: list[str] = []
        handoff = self._artifact(ArtifactKind.PRESENTATION_HANDOFF)
        delivery = self._artifact(ArtifactKind.DELIVERY)
        if handoff:
            evidence.append(self._ref(handoff.path))
            contract = handoff.payload.get("editability_contract") or {}
            if not isinstance(contract, dict) or not contract.get("native_business_content"):
                missing.append("presentation-handoff.native-business-content")
            if not isinstance(contract, dict) or contract.get("whole_slide_bitmap") is not False:
                missing.append("presentation-handoff.no-whole-slide-bitmap")
        else:
            missing.append("presentation-handoff")
        if not delivery:
            missing.append("delivery")
            return evidence, missing
        evidence.append(self._ref(delivery.path))
        if delivery.payload.get("qa_status") != "passed":
            missing.append("delivery.qa-passed")
        pptx_ref = str(delivery.payload.get("pptx", ""))
        if not self._exists(pptx_ref):
            missing.append("delivery.pptx")
        renders = delivery.payload.get("renders", [])
        if not isinstance(renders, list) or not renders:
            missing.append("delivery.renders")
        else:
            for index, render_ref in enumerate(renders, start=1):
                if not self._exists(str(render_ref)):
                    missing.append(f"delivery.render-{index}")
        return evidence, missing

    def _artifact(self, kind: ArtifactKind):
        try:
            return self.artifacts.latest(kind)
        except ProjectNotFoundError:
            return None

    def _latest_concept_decision(self) -> str:
        path = self.project_root / "cognition" / "decisions.jsonl"
        if not path.is_file():
            return ""
        selected = ""
        for line in path.read_text("utf-8").splitlines():
            try:
                item: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("target_ref", "")).startswith("concept://"):
                selected = str(item.get("decision_id", ""))
        return selected

    def _exists(self, value: str) -> bool:
        if not value:
            return False
        path = Path(value)
        candidate = (
            path.resolve(strict=False)
            if path.is_absolute()
            else (self.project_root / path).resolve(strict=False)
        )
        return is_within(candidate, self.project_root) and candidate.is_file()

    def _ref(self, value: str) -> str:
        path = Path(value)
        try:
            return path.resolve(strict=False).relative_to(self.project_root).as_posix()
        except ValueError:
            return str(value)


__all__ = ["GateEvidenceChecker"]
