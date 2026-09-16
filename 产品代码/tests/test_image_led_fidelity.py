"""C2 regression guards. Synthetic contracts never represent user acceptance."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ai_ppt_studio.domains.visual.contracts import validate_visual_contract_set
from ai_ppt_studio.errors import ContractValidationError
from tests.v16_visual_fixtures import valid_contract_set


class ImageLedLegacyBypassTests(unittest.TestCase):
    def test_unbound_image_led_contract_cannot_pass_legacy_text_checks(self):
        contracts = valid_contract_set('artifact://deck-design-system/' + 'd' * 64,
                                       'artifact://reading-deck-blueprint/' + 'b' * 64)
        blueprint = {'slides': copy.deepcopy(contracts['slide_contracts'])}
        self.assertEqual(validate_visual_contract_set(contracts, blueprint)['slide_contracts'][0]['slide_id'], 'S01')
        contracts['image_led'] = {
            'design_authority': 'finalized-image',
            'selection_ref': 'artifact://image-led-selection/' + 'f' * 64,
        }
        # Old text and all ordinary visual fields still match. No resolved
        # finalized image, trusted selection or region mapping has been supplied.
        with self.assertRaises(ContractValidationError):
            validate_visual_contract_set(contracts, blueprint)


if __name__ == '__main__':
    unittest.main()
