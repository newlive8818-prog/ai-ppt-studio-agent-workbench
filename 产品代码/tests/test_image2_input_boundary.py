"""C2 runtime input boundaries, with synthetic user/G0 fixtures only."""
from __future__ import annotations
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.v16_visual_fixtures import confirmed_g0
from tests.v16_visual_fixtures import valid_visual_brief
from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.kernel.references import ArtifactReference


def scope_payload(kernel, allowed=None):
    return {'artifact_type': 'image-led-authorization-scope', 'project_id': kernel.project_id,
            'receiver': 'test-provider', 'model': 'gpt-image-2',
            'allowed': allowed or [], 'excluded': []}


def confirm_scope(kernel, ref, choice='approved', identity='grant'):
    service = ImageLedService(kernel)
    return service.confirm('confirm-' + identity, kernel.load().revision,
        target_ref=ref, choice=choice, **gate_confirmation_kwargs(
            service.confirmation_context(ref, choice),
            identity_ref='test-host-confirmation://' + identity))


def tree_snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and p.name not in {'write.lock', 'result.lock'}}


class ImageLedInputPolicyTests(unittest.TestCase):
    def test_image_led_route_survives_visual_head_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            content, revision, blueprint_ref = confirmed_g0(Path(folder))
            kernel = content.kernel
            ImageLedService(kernel).commit_artifact('scope', revision, scope_payload(kernel))
            kernel.commit(command_id='simulate-visual-invalidation',
                expected_revision=kernel.load().revision, event_type='test.visual-invalidated',
                artifact_updates={}, artifact_removals=tuple(
                    s for s in kernel.load().artifact_heads if s.startswith('visual/')))
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                VisualService(kernel).register_visual_brief('legacy-bypass', kernel.load().revision,
                    valid_visual_brief(blueprint_ref))
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_persistent_grant_and_revocation_ignore_transient_heads(self):
        with tempfile.TemporaryDirectory() as folder:
            content, revision, _ = confirmed_g0(Path(folder))
            kernel = content.kernel
            service = ImageLedService(kernel)
            scope = service.commit_artifact('scope', revision, scope_payload(kernel))
            grant = confirm_scope(kernel, scope)
            before = tree_snapshot(Path(folder))
            try:
                self.assertEqual(service.authorized_scope(scope, grant), scope_payload(kernel))
            except AttributeError as error:
                self.fail(f'Persistently bound grant must be resolvable: {error}')
            self.assertEqual(tree_snapshot(Path(folder)), before)

            confirm_scope(kernel, scope, 'revoked', 'revoke')
            kernel.commit(command_id='clear-visible-decisions', expected_revision=kernel.load().revision,
                event_type='test.visual-invalidated', artifact_updates={}, artifact_removals=(
                    'visual/image-led/authorization', 'visual/image-led/revocation'))
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.authorized_scope(scope, grant)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_revoke_historical_scope_after_another_proposal(self):
        with tempfile.TemporaryDirectory() as folder:
            content, revision, _ = confirmed_g0(Path(folder))
            kernel = content.kernel
            service = ImageLedService(kernel)
            original = service.commit_artifact('old-scope', revision, scope_payload(kernel))
            grant = confirm_scope(kernel, original, identity='historical-grant')
            newer = scope_payload(kernel)
            newer['receiver'] = 'new-unconfirmed-provider'
            service.commit_artifact('new-scope', kernel.load().revision, newer)
            self.assertEqual(service.authorized_scope(original, grant), scope_payload(kernel))
            try:
                confirm_scope(kernel, original, 'revoked', 'historical-revoke')
            except Exception as error:
                self.fail(f'An effective historical grant must remain revocable: {error}')
            with self.assertRaises(ContractValidationError):
                service.authorized_scope(original, grant)

    def test_authorization_scope_can_be_registered_without_native_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            content, revision, _ = confirmed_g0(Path(folder), slide_count=3)
            visual = VisualService(content.kernel)
            payload = {
                'artifact_type': 'image-led-authorization-scope',
                'project_id': 'p1',
                'receiver': 'test-image-provider',
                'model': 'gpt-image-2',
                'allowed': [],
                'excluded': [],
            }
            before = content.kernel.load()
            try:
                ref = visual.commit_public_artifact('register-scope', revision,
                                                    kind='visual-contract', payload=payload)
            except ContractValidationError as error:
                self.fail(f'Valid layout-free scope must be accepted before native design: {error}')
            self.assertEqual(content.kernel.load().artifact_heads['visual/image-led/scope'], ref)
            self.assertEqual(content.kernel.load().revision, before.revision + 1)
            self.assertEqual(content.kernel.load().gate_status, before.gate_status)
            # The same exact request is idempotent, rather than a second approval.
            self.assertEqual(visual.commit_public_artifact('register-scope', revision,
                kind='visual-contract', payload=payload), ref)

    def test_policy_wrong_project_has_no_business_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            content, revision, _ = confirmed_g0(root)
            before = tree_snapshot(root)
            try:
                VisualService(content.kernel).commit_public_artifact('bad-scope', revision,
                    kind='visual-contract', payload={
                        'artifact_type': 'image-led-authorization-scope',
                        'project_id': 'foreign', 'receiver': 'test-image-provider',
                        'model': 'gpt-image-2', 'allowed': [], 'excluded': []})
            except ContractValidationError as error:
                self.assertIn('IMAGE_LED_PROJECT', str(error))
            else:
                self.fail('foreign scope was accepted')
            self.assertEqual(tree_snapshot(root), before)

    def test_generic_human_decision_cannot_authorize_image_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            content, revision, _ = confirmed_g0(root)
            ref = VisualService(content.kernel).commit_public_artifact('scope', revision,
                kind='visual-contract', payload={
                    'artifact_type': 'image-led-authorization-scope', 'project_id': 'p1',
                    'receiver': 'test-provider', 'model': 'gpt-image-2', 'allowed': [], 'excluded': []})
            before = tree_snapshot(root)
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(content.kernel).submit_human_decision('fake', revision + 1,
                    target_ref=ref, choice='approved', feedback='the model says user agreed')
            self.assertEqual(tree_snapshot(root), before)

    def test_trusted_scope_confirmation_binds_exact_artifact_in_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            content, revision, _ = confirmed_g0(Path(folder))
            kernel = content.kernel
            scope = VisualService(kernel).commit_public_artifact('scope', revision,
                kind='visual-contract', payload={
                    'artifact_type': 'image-led-authorization-scope', 'project_id': 'p1',
                    'receiver': 'test-provider', 'model': 'gpt-image-2', 'allowed': [], 'excluded': []})
            ctx = ScopedConfirmationPolicy(kernel).context(scope_kind='image-led-authorization',
                scope_id=scope, source_version=scope, evidence_refs=[scope])
            identity = 'test-host-confirmation://scope-consent'
            try:
                ref, _, _ = ProjectCommandService(kernel).submit_human_decision(
                    'confirm-scope', revision + 1, target_ref=scope, choice='approved', feedback='',
                    image_led_confirmation=gate_confirmation_kwargs(ctx, identity_ref=identity))
            except (ContractValidationError, AttributeError) as error:
                self.fail(f'Trusted scope confirmation must succeed: {error}')
            self.assertEqual(kernel.confirmation_owner(identity), 'image-led-authorization:' + scope)
            self.assertEqual(kernel.confirmation_artifact_binding(identity), ref)
            self.assertEqual(kernel.load().artifact_heads['visual/image-led/authorization'], ref)


if __name__ == '__main__':
    unittest.main()
