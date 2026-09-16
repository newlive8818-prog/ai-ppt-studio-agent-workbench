"""Formal image-led compilation: synthetic identities, no visual acceptance claim."""
from copy import deepcopy
import unittest

from ai_ppt_studio.domains.visual import contracts as contracts_module
from ai_ppt_studio.domains.visual import compilation as compilation_module
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.artifacts import canonical_json
from tests.test_image_led_contracts import rich_fixture, ref
from tests.test_v23_visual_compilation import _inputs, BLUEPRINT_REF, BRIEF_REF, SYSTEM_REF, CONTRACT_REF, POLICY_REF


def fixture_for(selection, inventory, *, reading_blueprint=None,
                blueprint_ref=BLUEPRINT_REF, brief_ref=BRIEF_REF,
                system_ref=SYSTEM_REF, selection_ref=None, region_inventory_ref=None):
    """Build a full formal contract, preserving explicit G0 provenance fields."""
    brief, design, old_contracts = _inputs()
    brief['reading_blueprint_ref'] = blueprint_ref
    design.update(reading_blueprint_ref=blueprint_ref, visual_brief_ref=brief_ref)
    selection_ref = selection_ref or inventory['selection_ref']
    region_inventory_ref = region_inventory_ref or ref('image-led-region-inventory', 'e')
    if reading_blueprint is None:
        reading_blueprint = {'slides': []}
        for row in selection['slides']:
            slide = deepcopy(old_contracts['slide_contracts'][0])
            slide['slide_id'] = row['target_binding']['slide_id']
            slide['order'] = row['target_binding']['page_order']
            reading_blueprint['slides'].append(slide)
    contract = deepcopy(old_contracts)
    contract.update(reading_blueprint_ref=blueprint_ref, deck_design_system_ref=system_ref)
    contract['image_led'] = {'project_id': selection['project_id'], 'selection_ref': selection_ref,
                             'region_inventory_ref': region_inventory_ref}
    contract['slide_contracts'] = []
    for source, selected, regions in zip(reading_blueprint['slides'], selection['slides'], inventory['slides'], strict=True):
        slide = deepcopy(old_contracts['slide_contracts'][0])
        slide.update(deepcopy(source))
        items = selected['selected_copy']['items']
        slide['neutral_title'] = items[0]['text']
        slide['visible_copy_blocks'] = [
            {'block_id': item['item_id'], 'text': item['text'], 'identity': '定版可见文案'}
            for item in items if item['kind'] != 'relation'
            and not (item['kind'] == 'text' and item['role'] == 'title')]
        slide['image_led'] = {'target_binding': deepcopy(selected['target_binding']),
                              'selected_copy': deepcopy(selected['selected_copy']),
                              'canvas': deepcopy(regions['canvas']),
                              'source_image_size': deepcopy(regions['source_image_size'])}
        slide['regions'] = deepcopy(regions['regions'])
        contract['slide_contracts'].append(slide)
    return reading_blueprint, brief, design, contract


def inputs():
    selection, inventory = rich_fixture()
    blueprint, brief, design, contract = fixture_for(selection, inventory)
    return selection, inventory, blueprint, brief, design, contract


def validate_contract(contract, blueprint, selection, inventory):
    validator = contracts_module.validate_image_led_contract_set
    return validator(contract, blueprint, selection=selection, region_inventory=inventory,
                     selection_ref=inventory['selection_ref'],
                     region_inventory_ref=contract['image_led']['region_inventory_ref'])


def compile_plan(contract, selection, inventory, brief, design):
    values = dict(reading_blueprint_ref=BLUEPRINT_REF, visual_brief_ref=BRIEF_REF,
        deck_design_system_ref=SYSTEM_REF, visual_contract_set_ref=CONTRACT_REF,
        release_target_policy_ref=POLICY_REF, source_version='image-led-c2', source_revision=17,
        visual_brief=brief, design_system=design, contract_set=contract)
    compiler = compilation_module.compile_image_led_plan
    return compiler(**values, selection=selection, region_inventory=inventory,
        selection_ref=inventory['selection_ref'], region_inventory_ref=contract['image_led']['region_inventory_ref'])


class ImageLedCompilationTests(unittest.TestCase):
    def test_visible_ui_projection_does_not_turn_relation_meaning_into_extra_text(self):
        selection, _ = rich_fixture()
        fields = contracts_module.image_led_visible_fields(selection['slides'][0]['selected_copy'])
        self.assertEqual([row['block_id'] for row in fields['visible_copy_blocks']],
                         ['body', 'cell-0', 'cell-1'])

    def test_formal_contract_accepts_selected_copy_and_preserves_g0_provenance(self):
        selection, inventory, blueprint, _, _, contract = inputs()
        try:
            result = validate_contract(contract, blueprint, selection, inventory)
        except ContractValidationError as exc:
            self.fail(f'Complete finalized contract must enter formal validation: {exc}')
        self.assertEqual(result, contract)
        self.assertNotEqual(result['slide_contracts'][0]['neutral_title'], blueprint['slides'][0]['neutral_title'])
        self.assertEqual(result['slide_contracts'][0]['evidence_bindings'], blueprint['slides'][0]['evidence_bindings'])

    def test_independent_compiler_is_deterministic_and_never_reinterprets_regions(self):
        selection, inventory, _, brief, design, contract = inputs()
        result = compile_plan(contract, selection, inventory, brief, design)
        self.assertEqual(result['compiler_version'], 'image-led-faithful-compiler/v1')
        self.assertEqual(result['handoff_version'], 'codex-presentations-image-led/v1')
        self.assertEqual(canonical_json(result), canonical_json(compile_plan(contract, selection, inventory, brief, design)))
        for slide, source in zip(result['slides'], inventory['slides'], strict=True):
            self.assertEqual({k: v for k, v in slide.items() if k != 'objects'}, source)
            for region, obj in zip(source['regions'], slide['objects'], strict=True):
                self.assertEqual({k: v for k, v in obj.items() if k not in {'object_id', 'render_mode'}}, region)
        self.assertEqual(result['slides'][0]['regions'][0]['content']['items'][0]['text'], ' 标题\n')

    def test_contract_rejects_unbound_identity_and_old_copy_fallback(self):
        selection, inventory, blueprint, _, _, contract = inputs()
        changes = [lambda p: p['image_led'].update(selection_ref=ref('image-led-selection', 'f')),
                   lambda p: p['slide_contracts'][0].update(neutral_title='旧标题'),
                   lambda p: p['slide_contracts'][0]['regions'][0]['bbox'].__setitem__(0, 200),
                   lambda p: p['slide_contracts'][0].update(evidence_bindings=['changed']),
                   lambda p: p['slide_contracts'][0]['image_led'].update(selected_copy={'items': []})]
        for change in changes:
            changed = deepcopy(contract); change(changed)
            with self.subTest(change=change), self.assertRaises(ContractValidationError):
                validate_contract(changed, blueprint, selection, inventory)

    def test_plan_rejects_rewritten_objects_stale_refs_versions_and_open_schema(self):
        selection, inventory, _, brief, design, contract = inputs()
        plan = compile_plan(contract, selection, inventory, brief, design)
        validator = compilation_module.validate_image_led_compilation_plan
        changes = [lambda p: p.update(compiler_version=compilation_module.COMPILER_VERSION),
                   lambda p: p.update(selection_ref=ref('image-led-selection', 'f')),
                   lambda p: p.update(layout='redesign'),
                   lambda p: p['slides'][0]['objects'][0]['bbox'].__setitem__(0, 999),
                   lambda p: p['slides'][0]['objects'].pop(),
                   lambda p: p['slides'][0]['objects'][0].update(object_id='non-deterministic'),
                   lambda p: p.update(source_revision=True)]
        for change in changes:
            changed = deepcopy(plan); change(changed)
            with self.subTest(change=change), self.assertRaises(ContractValidationError):
                validator(changed, contract_set=contract, selection=selection, region_inventory=inventory,
                          selection_ref=inventory['selection_ref'], region_inventory_ref=contract['image_led']['region_inventory_ref'])


if __name__ == '__main__':
    unittest.main()
