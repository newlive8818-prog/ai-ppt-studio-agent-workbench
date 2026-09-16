"""Chosen visible run outlines use a closed color/width contract, never a fit policy."""
from copy import deepcopy
import unittest

from test_image_led_character_spacing import spacing_fixture
from test_image_led_contracts import fixture, objects_for
from test_image_led_native_v3_contracts import VERSION
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, validate_faithful_objects
from ai_ppt_studio.errors import ContractValidationError


class TextOutlineContracts(unittest.TestCase):
    def test_exact_positive_outline_width_preserves_all_v3_carriers_and_selected_copy(self):
        for carrier in ('ordinary', 'fragment', 'table'):
            for width in (0.04, 1, 10.8, 2112):
                selected, inventory, run = spacing_fixture(carrier)
                before_selected = deepcopy(selected)
                run['outline'] = {'color': '#003060', 'width': width}
                original = deepcopy(inventory)
                with self.subTest(carrier=carrier, width=width):
                    try:
                        self.assertEqual(validate_region_inventory(inventory, selected), original)
                    except ContractValidationError as error:
                        self.fail('Explicit outline rejected: ' + str(error))
                    self.assertEqual(inventory, original)
                    self.assertEqual(selected, before_selected)
                    regions = inventory['slides'][0]['regions']
                    objects = objects_for(regions)
                    self.assertEqual(validate_faithful_objects(regions, objects, region_version=VERSION), objects)

    def test_invalid_width_and_nonopaque_or_unclosed_outline_are_rejected_on_all_carriers(self):
        invalid = [None, {}, {'color': '#003060'}, {'width': 1},
                   {'color': '#003060', 'width': 1, 'dash': 'solid'},
                   {'color': '#003060', 'width': 1, 'join': 'round'},
                   {'color': '#003060', 'width': 1, 'opacity': 1}]
        invalid += [{'color': '#003060', 'width': value} for value in
                    (True, False, None, '1', 0, -1, .1, 2112.04, 10**1000,
                     float('inf'), float('-inf'), float('nan'), 1e305)]
        invalid += [{'color': value, 'width': 1} for value in
                    ('#00306080', '#036', 'transparent', 'none', '', None)]
        for carrier in ('ordinary', 'fragment', 'table'):
            for outline in invalid:
                selected, inventory, run = spacing_fixture(carrier)
                run['outline'] = outline
                with self.subTest(carrier=carrier, outline=outline), self.assertRaises(ContractValidationError):
                    validate_region_inventory(inventory, selected)

    def test_versionless_run_and_non_run_fields_cannot_acquire_outline(self):
        selected, inventory = fixture()
        inventory['slides'][0]['regions'][0]['appearance']['runs'][0]['outline'] = {'color': '#003060', 'width': 1}
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selected)
        selected, inventory, _ = spacing_fixture('fragment')
        inventory['slides'][0]['regions'][0]['appearance']['fragments'][0]['appearance']['outline'] = {'color': '#003060', 'width': 1}
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selected)

    def test_omitted_outline_is_not_added_or_defaulted(self):
        for carrier in ('ordinary', 'fragment', 'table'):
            selected, inventory, run = spacing_fixture(carrier)
            before = deepcopy(inventory)
            self.assertEqual(validate_region_inventory(inventory, selected), before)
            self.assertEqual(inventory, before)
            self.assertNotIn('outline', run)

    def test_outline_can_coexist_with_explicit_spacing_and_visible_gradient(self):
        selected, inventory, run = spacing_fixture('fragment')
        run.pop('color')
        run.update(outline={'color': '#003060', 'width': 10.8}, characterSpacing=75,
                   fill={'type': 'linear-gradient', 'angle': 90, 'stops': [
                       {'offset': 0, 'color': '#102030'}, {'offset': 1, 'color': '#A0B0C0'}]})
        try:
            validate_region_inventory(inventory, selected)
        except ContractValidationError as error:
            self.fail('Outline with visible gradient/spacing rejected: ' + str(error))
        for field, value in (('color', '#003060'), ('horizontalScale', .9), ('shadow', {}), ('autoFitScale', .9)):
            bad = deepcopy(inventory)
            bad['slides'][0]['regions'][0]['appearance']['fragments'][0]['appearance']['runs'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ContractValidationError):
                validate_region_inventory(bad, selected)
        run['fill'] = None
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selected)

    def test_faithful_projection_cannot_change_chosen_outline(self):
        selected, inventory, run = spacing_fixture('fragment')
        run['outline'] = {'color': '#003060', 'width': 1}
        try:
            validate_region_inventory(inventory, selected)
        except ContractValidationError as error:
            self.fail('Source-bound outline rejected: ' + str(error))
        regions = inventory['slides'][0]['regions']
        for field, value in (('width', 1.04), ('color', '#003061')):
            objects = objects_for(regions)
            objects[0]['appearance']['fragments'][0]['appearance']['runs'][0]['outline'][field] = value
            with self.subTest(field=field), self.assertRaises(ContractValidationError):
                validate_faithful_objects(regions, objects, region_version=VERSION)


if __name__ == '__main__':
    unittest.main()
