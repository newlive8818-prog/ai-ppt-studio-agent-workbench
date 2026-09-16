"""Synthetic G0 tests for exact design input and persistent request identity."""
from __future__ import annotations
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from tests.test_image2_input_boundary import scope_payload, confirm_scope, tree_snapshot
from tests.v16_visual_fixtures import confirmed_g0
from ai_ppt_studio.application.image_led_service import ImageLedService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import ContractValidationError, ArtifactReferenceError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference


def input_fixture(root, slide_count=3):
    content, _, blueprint_ref = confirmed_g0(root, slide_count=slide_count)
    kernel = content.kernel
    service = ImageLedService(kernel)
    blueprint = kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))['payload']
    strings = set()
    for slide in blueprint['slides']:
        strings.update([slide['neutral_title'], slide['page_task']])
        strings.update(b['text'] for b in slide['visible_copy_blocks'])
    scope = scope_payload(kernel, [{'source_sha256': hashlib.sha256(t.encode('utf-8')).hexdigest(),
        'source_location': {'kind': 'whole-source'}, 'uses': ['content-source'], 'send_form': 'verbatim'}
        for t in sorted(strings)])
    scope_ref = service.commit_artifact('scope', kernel.load().revision, scope)
    grant = confirm_scope(kernel, scope_ref)
    heads = kernel.load().artifact_heads
    policy = {'artifact_type': 'image-led-input-policy', 'project_id': kernel.project_id,
        'reading_blueprint_ref': blueprint_ref, 'source_version': blueprint['source_version'],
        'material_inventory_ref': heads['materials'], 'evidence_book_ref': heads['content/evidence-book'],
        'g0_ref': heads['gate/G0/confirmation'], 'release_target_policy_ref': heads['release/target-policy'],
        'authorization_scope_ref': scope_ref, 'authorization_ref': grant,
        'receiver': scope['receiver'], 'model': scope['model'],
        'common_rules': {'typography_tokens': {'title': 'Arial', 'body': 'Arial'},
            'color_tokens': {'ink': '#123456'}, 'fallback_fonts': {'macOS': 'Arial'},
            'title_bar': '统一标题栏', 'background': '统一浅色背景'}}
    policy_ref = service.commit_artifact('policy', kernel.load().revision, policy)
    packs = []
    for slide in blueprint['slides']:
        payload = {'artifact_type': 'image-led-input-pack', 'project_id': kernel.project_id,
            'input_policy_ref': policy_ref, 'slide_id': slide['slide_id'], 'page_order': slide['order'],
            'confirmed_visible_copy': {'title': slide['neutral_title'], 'blocks': slide['visible_copy_blocks']},
            'page_goal': slide['page_task'], 'atoms': []}
        packs.append(service.commit_artifact('pack-' + slide['slide_id'], kernel.load().revision, payload))
    return service, policy, packs


class ImageLedRequestsTests(unittest.TestCase):
    def test_reserved_active_id_is_rejected_before_task_history_can_be_shadowed(self):
        from ai_ppt_studio.context_compiler import ContextCompiler
        for entry in ('intent', 'task', 'context'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as folder:
                service, _, packs = input_fixture(Path(folder))
                kernel = service.kernel
                before = tree_snapshot(Path(folder))
                with self.assertRaises(ContractValidationError):
                    if entry == 'intent':
                        service.generation_intent(target_refs=[packs[0]], instructions='',
                            intent='new', request_id='active')
                    elif entry == 'task':
                        ProjectCommandService(kernel).request_agent_action('reserved-id', kernel.load().revision,
                            action_type='generate-slide-images', target_refs=[packs[0]], instructions='',
                            generation_request_id='active')
                    else:
                        ContextCompiler(kernel).compile_role_task(role_id='image-asset-producer',
                            task_type='generate-slide-images', project_revision=kernel.load().revision,
                            target_refs=[packs[0]], instructions='', task_id='active')
                self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_three_pages_reuse_one_grant_without_writing_or_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service, _, packs = input_fixture(root)
            before = tree_snapshot(root)
            for _ in range(2):
                for ref in packs:
                    payload = service.compile_request(ref)
                    self.assertEqual(set(payload), {'receiver', 'model', 'confirmed_visible_copy',
                        'page_goal', 'common_rules', 'materials'})
                    self.assertEqual(payload['materials'], [])
                    self.assertNotIn('layout', str(payload))
                    self.assertNotIn(folder, str(payload))
            self.assertEqual(tree_snapshot(root), before)

    def test_font_update_reuses_grant_but_old_pack_becomes_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service, policy, packs = input_fixture(root)
            kernel = service.kernel
            consumption_ref = kernel.load().artifact_heads['kernel/confirmation-consumptions']
            policy['common_rules']['typography_tokens']['title'] = 'PingFang SC'
            service.commit_artifact('change-font', kernel.load().revision, policy)
            self.assertEqual(kernel.load().artifact_heads['kernel/confirmation-consumptions'], consumption_ref)
            before = tree_snapshot(root)
            with self.assertRaises(ArtifactReferenceError):
                service.compile_request(packs[0])
            self.assertEqual(tree_snapshot(root), before)

    def test_wrong_receiver_and_extra_layout_have_zero_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service, policy, _ = input_fixture(root)
            for change in ({'receiver': 'another-provider'}, {'layout': 'three cards'}):
                wrong = {**copy.deepcopy(policy), **change}
                before = tree_snapshot(root)
                with self.assertRaises(ContractValidationError):
                    service.commit_artifact('bad-policy', service.kernel.load().revision, wrong)
                self.assertEqual(tree_snapshot(root), before)

    def test_generation_action_has_only_current_pack_and_dedicated_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service, _, packs = input_fixture(root)
            kernel = service.kernel
            try:
                _, task, _ = ProjectCommandService(kernel).request_agent_action('generate-page', kernel.load().revision,
                    action_type='generate-slide-images', target_refs=[packs[0]], instructions='Design freely')
            except ContractValidationError as error:
                self.fail(f'Current G0 pack should queue Image 2 without native-first precondition: {error}')
            context = kernel.artifacts.resolve(ArtifactReference.parse(task['context_pack_ref']))['payload']
            self.assertEqual(context['layers']['image_led_request']['payload'], service.compile_request(packs[0]))
            self.assertNotIn('project_facts', context['layers'])
            self.assertNotIn('visual_handoff', context['layers'])
            self.assertEqual(task['status'], 'queued')

    def test_unknown_request_is_not_blindly_resent(self):
        class UncertainTransport:
            calls = 0
            def generate(self, *, request_id, payload):
                self.calls += 1
                raise TimeoutError('provider may have accepted the request')
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = input_fixture(Path(folder))
            kernel = service.kernel
            _, task, _ = ProjectCommandService(kernel).request_agent_action('generate-unknown', kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            transport = UncertainTransport()
            try:
                response_ref = service.execute_generation(task['task_id'], transport=transport)
            except AttributeError as error:
                self.fail(f'Generation lifecycle must preserve an unknown request: {error}')
            response = kernel.artifacts.resolve(ArtifactReference.parse(response_ref))['payload']
            self.assertEqual(response['status'], 'unknown')
            self.assertEqual(response['request_id'], task['task_id'])
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.execute_generation(task['task_id'], transport=transport)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_revocation_after_queue_prevents_transport_and_writes(self):
        class RecordingTransport:
            calls = 0
            def generate(self, **kwargs):
                self.calls += 1
                raise AssertionError('revoked material must never reach transport')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service, policy, packs = input_fixture(root)
            kernel = service.kernel
            _, task, _ = ProjectCommandService(kernel).request_agent_action('generate-revoked', kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            confirm_scope(kernel, policy['authorization_scope_ref'], 'revoked', 'after-queue')
            before = tree_snapshot(root)
            transport = RecordingTransport()
            try:
                with self.assertRaises(ContractValidationError):
                    service.execute_generation(task['task_id'], transport=transport)
            except AttributeError as error:
                self.fail(f'Execution must revalidate revoked scope: {error}')
            self.assertEqual(transport.calls, 0)
            self.assertEqual(tree_snapshot(root), before)

    def test_revocation_between_preflight_and_atomic_claim_prevents_send(self):
        class Transport:
            calls = 0
            def generate(self, **kwargs):
                self.calls += 1
                raise TimeoutError()
        with tempfile.TemporaryDirectory() as folder:
            service, policy, packs = input_fixture(Path(folder))
            kernel = service.kernel
            _, task, _ = ProjectCommandService(kernel).request_agent_action('racing-send', kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            original = service.generation_context
            def racing_context(task_id):
                value = original(task_id)
                confirm_scope(kernel, policy['authorization_scope_ref'], 'revoked', 'race')
                return value
            service.generation_context = racing_context
            transport = Transport()
            with self.assertRaises(RevisionConflictError):
                service.execute_generation(task['task_id'], transport=transport)
            self.assertEqual(transport.calls, 0)

    def test_restoring_policy_does_not_erase_unknown_request_identity(self):
        class Transport:
            calls = 0
            def generate(self, **kwargs):
                self.calls += 1
                raise TimeoutError()
        with tempfile.TemporaryDirectory() as folder:
            service, policy, packs = input_fixture(Path(folder))
            kernel = service.kernel
            pack = kernel.artifacts.resolve(ArtifactReference.parse(packs[0]))['payload']
            _, task, _ = ProjectCommandService(kernel).request_agent_action('unknown-before-font', kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            transport = Transport()
            service.execute_generation(task['task_id'], transport=transport)
            changed = copy.deepcopy(policy)
            changed['common_rules']['typography_tokens']['title'] = 'PingFang SC'
            service.commit_artifact('font-one', kernel.load().revision, changed)
            service.commit_artifact('font-restore', kernel.load().revision, policy)
            service.commit_artifact('pack-restore', kernel.load().revision, pack)
            before = tree_snapshot(Path(folder))
            with self.assertRaises(ContractValidationError):
                service.execute_generation(task['task_id'], transport=transport)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(tree_snapshot(Path(folder)), before)

    def test_concurrent_replay_of_claim_does_not_send_twice(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        class Transport:
            calls = 0
            def generate(self, **kwargs):
                self.calls += 1
                raise TimeoutError()
        with tempfile.TemporaryDirectory() as folder:
            service, _, packs = input_fixture(Path(folder))
            kernel = service.kernel
            _, task, _ = ProjectCommandService(kernel).request_agent_action('concurrent-send', kernel.load().revision,
                action_type='generate-slide-images', target_refs=[packs[0]], instructions='')
            commit = kernel.commit
            barrier = threading.Barrier(2)
            def synchronized_commit(**kwargs):
                if kwargs['event_type'] == 'image-led.request-started':
                    barrier.wait(timeout=5)
                return commit(**kwargs)
            kernel.commit = synchronized_commit
            transport = Transport()
            def send():
                try:
                    return service.execute_generation(task['task_id'], transport=transport)
                except ContractValidationError:
                    return 'duplicate-rejected'
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: send(), range(2)))
            self.assertEqual(transport.calls, 1)
            self.assertEqual(results.count('duplicate-rejected'), 1)


if __name__ == '__main__':
    unittest.main()
