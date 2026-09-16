"""Read-only C2 artifact audit. JSON is printed; no project writes are made."""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.image_led_native import ImageLedNativeService

root = Path(sys.argv[1]).resolve()
raw = json.loads((root / "kernel/state.json").read_text())
kernel = ProjectKernel(root, project_id=raw["project_id"])
state_before = (root / "kernel/state.json").read_bytes()
heads = kernel.load().artifact_heads

def payload(ref):
    return kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]

anchors = ImageLedNativeService(kernel).current_anchors()
g2 = GateEvaluator(kernel).validate_current_g2_evidence()
native = payload(heads["visual/image-led/native-pptx"])
pptx = Path(native["path"])
digest = hashlib.sha256(pptx.read_bytes()).hexdigest()
assert digest == anchors["pptx_sha256"] == native["pptx_sha256"]
target = payload(heads["visual/target-evidence/G2/macos-powerpoint"])
assert target["pptx_sha256"] == digest and target["overall_result"] == "passed"
g3 = payload(heads["gate/G3/confirmation"])
assert g3["visual_contract_ref"] == heads["visual/contract"]
assert heads["visual/anchors"] in g3["evidence_refs"]
assert heads["visual/compilation-plan"] in g3["evidence_refs"]
ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
pages = []
with zipfile.ZipFile(pptx) as z:
    assert z.testzip() is None
    slide_files = sorted(n for n in z.namelist()
                         if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
    assert len(slide_files) == len(anchors["slide_ids"]) == 3
    for slide_id, filename in zip(anchors["slide_ids"], slide_files):
        xml = ET.fromstring(z.read(filename))
        pages.append({"slide_id": slide_id,
                      "native_shapes": len(xml.findall(".//p:sp", ns)),
                      "text_runs": len(xml.findall(".//a:t", ns)),
                      "pictures": len(xml.findall(".//p:pic", ns)),
                      "connectors": len(xml.findall(".//p:cxnSp", ns))})
assert state_before == (root / "kernel/state.json").read_bytes()
print(json.dumps({
    "audit_kind": "existing-c2-result-readonly", "revision": raw["revision"],
    "gate_status": raw["gate_status"], "pptx": str(pptx), "pptx_sha256": digest,
    "current_anchors": "passed", "current_g2_revalidation": "passed",
    "g2_target_evidence": heads["visual/target-evidence/G2/macos-powerpoint"],
    "g3_confirmation": heads["gate/G3/confirmation"],
    "g3_user_message_ref": g3["user_message_ref"],
    "g3_reviewed_revision": g3["challenge_revision"],
    "g3_source": g3["source_version"], "pages": pages,
    "project_state_unchanged": True,
    "conclusion": "reuse existing three-page result for C2",
    "limits": ["This run reads existing PowerPoint evidence; no new desktop run.",
               "C2 source/release/generalization/independent review exit remains separate.",
               "G4 belongs to C3; no G4 claim."]
}, ensure_ascii=False, indent=2))
