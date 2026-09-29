"""Fixed detached finding registration and current-source production verification."""
from __future__ import annotations
from copy import deepcopy
import json
from ai_ppt_studio.application.artifact_guards import require_revision
from ai_ppt_studio.application.material_source_reader import MaterialSourceReader
from ai_ppt_studio.application.review_commands import fingerprint, replay_state
from ai_ppt_studio.domains.materials.contracts import validate_material_inventory
from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, location, sha, text
from ai_ppt_studio.kernel.references import ArtifactReference

FINDING_INPUT_FIELDS = frozenset({'material_inventory_ref', 'source_id', 'source_sha256',
    'source_location', 'content_kind', 'exclusion_mode'})
FINDING_FIELDS = FINDING_INPUT_FIELDS | {'schema_version', 'artifact_type', 'project_id', 'content_sha256'}


class MaterialFindingService:
    def __init__(self, kernel):
        self.kernel = kernel
        self.reader = MaterialSourceReader(kernel)

    @staticmethod
    def validate_input(payload):
        exact(payload, set(FINDING_INPUT_FIELDS), 'material finding input')
        for key in ('material_inventory_ref', 'source_id'):
            text(payload[key], key)
        sha(payload['source_sha256'])
        location(payload['source_location'])
        if payload['content_kind'] not in ('text', 'image'):
            fail('TYPE', 'finding content_kind must be text or image')
        if payload['exclusion_mode'] not in ('scope', 'image-content'):
            fail('EXCLUSION', 'unsupported finding exclusion_mode')
        if payload['exclusion_mode'] == 'image-content' and payload['content_kind'] != 'image':
            fail('EXCLUSION', 'image-content exclusion requires an image finding')
        return deepcopy(payload)

    def inventory(self, reference):
        state = self.kernel.load()
        if not reference or state.artifact_heads.get('materials') != reference:
            fail('CURRENT', 'finding requires the exact current material inventory')
        parsed = ArtifactReference.parse(reference)
        if parsed.kind != 'material-inventory':
            fail('SOURCE', 'finding inventory has the wrong artifact kind')
        payload = validate_material_inventory(self.kernel.artifacts.resolve(parsed)['payload'])
        return {row['source_id']: row for row in payload['sources']}

    def _source(self, payload, sources):
        source = sources.get(payload['source_id'])
        if source is None:
            fail('SOURCE', 'finding source is absent from the current project inventory')
        if source['sha256'] != payload['source_sha256']:
            fail('SOURCE_HASH', 'finding source hash disagrees with the current inventory')
        return source

    def register(self, command_id, expected_revision, payload):
        if type(expected_revision) is not int or expected_revision < 0:
            fail("SCHEMA", "expected_revision must be a nonnegative integer")
        normalized = self.validate_input(payload)
        command_fingerprint = fingerprint('register-material-finding', normalized)
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            event = json.loads((self.kernel.events_root / f'r{replay.processed_commands[command_id]:08d}.json').read_text())
            refs = event.get('detached_artifact_refs', [])
            if len(refs) != 1 or ArtifactReference.parse(refs[0]).kind != 'material-finding':
                fail('REPLAY', 'original material finding receipt is unavailable')
            self.kernel.artifacts.resolve(ArtifactReference.parse(refs[0]))
            return refs[0]
        # Bind the exact revision that was inspected before any source I/O.
        require_revision(self.kernel, expected_revision)
        sources = self.inventory(normalized['material_inventory_ref'])
        source = self._source(normalized, sources)
        extracted = self.reader.extract(source, normalized['source_location'], normalized['content_kind'])
        finding = {'schema_version': 1, 'artifact_type': 'material-finding',
            'project_id': self.kernel.project_id, **normalized,
            'content_sha256': extracted['content_sha256']}
        reference = str(self.kernel.artifacts.reference_for('material-finding', finding))
        self.kernel.commit(command_id=command_id, expected_revision=expected_revision,
            event_type='materials.finding-registered', artifact_updates={},
            detached_artifacts=(('material-finding', finding),), command_fingerprint=command_fingerprint)
        return reference

    def resolve(self, reference, *, inventory_ref):
        return self._resolve(reference, inventory_ref, self.inventory(inventory_ref), {})

    def _resolve(self, reference, inventory_ref, sources, snapshots):
        parsed = ArtifactReference.parse(reference)
        if parsed.kind != 'material-finding':
            fail('SOURCE', 'production evidence requires a formal material-finding')
        payload = self.kernel.artifacts.resolve(parsed)['payload']
        exact(payload, set(FINDING_FIELDS), 'formal material finding')
        if type(payload['schema_version']) is not int or payload['schema_version'] != 1 or payload['artifact_type'] != 'material-finding':
            fail('SCHEMA', 'unsupported formal finding version/type')
        if payload['project_id'] != self.kernel.project_id:
            fail('PROJECT', 'finding belongs to another project')
        if payload['material_inventory_ref'] != inventory_ref:
            fail('CURRENT', 'finding belongs to a stale material inventory')
        self.validate_input({key: payload[key] for key in FINDING_INPUT_FIELDS})
        sha(payload['content_sha256'])
        source = self._source(payload, sources)
        extracted = self.reader.extract(source, payload['source_location'], payload['content_kind'], snapshots=snapshots)
        if extracted['content_sha256'] != payload['content_sha256']:
            fail('CONTENT_HASH', 'finding extracted bytes differ from its registered hash')
        return {'finding': payload, 'source': source, **extracted}

    def validate_evidence(self, evidence):
        if evidence.get('material_mode') == 'proposal-led':
            return {}
        inventory_ref = evidence.get('material_inventory_ref')
        sources = self.inventory(inventory_ref)
        declared = evidence.get('source_refs')
        excluded = evidence.get('excluded_material_refs')
        for values in (declared, excluded):
            if not isinstance(values, list) or any(not isinstance(ref, str) or not ref for ref in values) or len(set(values)) != len(values):
                fail('SCHEMA', 'evidence requires unique finding reference lists')
        if set(declared) & set(excluded):
            fail('EXCLUDED', 'declared and excluded finding references must be disjoint')
        # Geometry is checked against each actual atom, not against a declared page.
        snapshots = {}  # One invocation only; never persisted or reused on a later call.
        return {ref: self._resolve(ref, inventory_ref, sources, snapshots)
                for ref in declared + excluded}
