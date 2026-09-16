"""Exact, explicitly chosen v3 character spacing; no inferred fit or defaults."""
from copy import deepcopy
import unittest

from test_image_led_contracts import binding, fixture, objects_for, text_style
from test_image_led_native_v3_contracts import VERSION, v3_fixture
from test_image_led_text_fragments import fragment_fixture
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, validate_faithful_objects
from ai_ppt_studio.errors import ContractValidationError


def spacing_fixture(carrier):
    selection, inventory = fragment_fixture() if carrier == 'fragment' else v3_fixture()
    slide = inventory['slides'][0]
    if carrier == 'table':
        item = {'item_id': 'spacing-cell', 'kind': 'table-cell', 'table_id': 'spacing-table',
                'row': 0, 'column': 0, 'text': 'Exact  A😀e\u0301'}
        selection['slides'][0]['selected_copy']['items'].append(deepcopy(item))
        slide['regions'].append({'region_id': 'spacing-table', 'kind': 'table', 'bbox': [800, 400, 300, 150],
            'z_order': 3, 'content': {'items': [item]}, 'material_binding': None,
            'appearance': {'row_heights': [150], 'column_widths': [300], 'cells': [
                {'row': 0, 'column': 0, 'item_id': item['item_id'],
                 'style': {**text_style(item['text']), 'wrap': 'none'}}]}})
        target = binding(selection['slides'][0]['selected_copy'])
        selection['slides'][0]['target_binding'] = target
        slide['target_binding'] = deepcopy(target)
        style = slide['regions'][-1]['appearance']['cells'][0]['style']
    elif carrier == 'fragment':
        style = slide['regions'][0]['appearance']['fragments'][0]['appearance']
    else:
        style = slide['regions'][0]['appearance']
    return selection, inventory, style['runs'][0]


class CharacterSpacingContracts(unittest.TestCase):
    def test_explicit_native_units_preserve_every_v3_carrier_and_complete_copy(self):
        for carrier in ('ordinary', 'fragment', 'table'):
            for spacing in (-400000, -277, 0, 75, 400000):
                selected, inventory, run = spacing_fixture(carrier)
                validate_region_inventory(inventory, selected)
                before_selected = deepcopy(selected)
                run['characterSpacing'] = spacing
                before_inventory = deepcopy(inventory)
                with self.subTest(carrier=carrier, spacing=spacing):
                    try:
                        checked = validate_region_inventory(inventory, selected)
                    except ContractValidationError as error:
                        self.fail('Explicit integer character spacing rejected: ' + str(error))
                    self.assertEqual(checked, before_inventory)
                    self.assertEqual(inventory, before_inventory)
                    self.assertEqual(selected, before_selected)
                    regions = inventory['slides'][0]['regions']
                    objects = objects_for(regions)
                    self.assertEqual(validate_faithful_objects(regions, objects, region_version=VERSION), objects)

    def test_wrong_types_and_out_of_schema_range_are_rejected_for_every_carrier(self):
        for carrier in ('ordinary', 'fragment', 'table'):
            for spacing in (True, False, -277.0, 0.0, '-277', None, [], {}, float('nan'), -400001, 400001):
                selected, inventory, run = spacing_fixture(carrier)
                run['characterSpacing'] = spacing
                with self.subTest(carrier=carrier, spacing=spacing), self.assertRaises(ContractValidationError):
                    validate_region_inventory(inventory, selected)

    def test_versionless_runs_cannot_acquire_character_spacing(self):
        selected, inventory = fixture()
        validate_region_inventory(inventory, selected)
        inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['characterSpacing'] = 0
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selected)

    def test_omitted_spacing_remains_absent_without_mutation(self):
        for carrier in ('ordinary', 'fragment', 'table'):
            selected, inventory, run = spacing_fixture(carrier)
            original = deepcopy(inventory)
            self.assertEqual(validate_region_inventory(inventory, selected), original)
            self.assertEqual(inventory, original)
            self.assertNotIn('characterSpacing', run)

    def test_spacing_coexists_with_gradient_without_loosening_fill_or_other_fields(self):
        selected, inventory, run = spacing_fixture('fragment')
        run.pop('color')
        run.update(characterSpacing=75, fill={'type': 'linear-gradient', 'angle': 90,
            'stops': [{'offset': 0, 'color': '#102030'}, {'offset': 1, 'color': '#A0B0C0'}]})
        try:
            validate_region_inventory(inventory, selected)
        except ContractValidationError as error:
            self.fail('Gradient text with explicit spacing rejected: ' + str(error))
        for field, value in (('color', '#102030'), ('horizontalScale', 0.9), ('autoFitScale', 0.9)):
            bad = deepcopy(inventory)
            bad['slides'][0]['regions'][0]['appearance']['fragments'][0]['appearance']['runs'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ContractValidationError):
                validate_region_inventory(bad, selected)

    def test_spacing_is_run_scoped_and_exact_faithful_projection_cannot_change_it(self):
        selected, inventory, run = spacing_fixture('fragment')
        run['characterSpacing'] = -277
        try:
            validate_region_inventory(inventory, selected)
        except ContractValidationError as error:
            self.fail('Source-bound spacing rejected: ' + str(error))
        regions = inventory['slides'][0]['regions']
        objects = objects_for(regions)
        objects[0]['appearance']['fragments'][0]['appearance']['runs'][0]['characterSpacing'] = -276
        with self.assertRaises(ContractValidationError):
            validate_faithful_objects(regions, objects, region_version=VERSION)
        run.pop('characterSpacing')
        inventory['slides'][0]['regions'][0]['appearance']['fragments'][0]['appearance']['characterSpacing'] = -277
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selected)


if __name__ == '__main__':
    unittest.main()
