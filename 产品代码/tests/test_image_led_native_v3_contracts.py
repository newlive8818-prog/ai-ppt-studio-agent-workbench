"""V3 frozen path relations and wrapping, without changing selected visible copy."""
from copy import deepcopy
import unittest

from test_image_led_contracts import fixture, rich_fixture, binding, objects_for
from ai_ppt_studio.domains.visual.image_led import (
    selected_copy_sha256, validate_region_inventory, validate_faithful_objects,
    handoff_selected_copy,
)
from ai_ppt_studio.errors import ContractValidationError

VERSION = 'image-led-region-inventory/v3'


def v3_fixture():
    selection, inventory = fixture()
    copy = selection['slides'][0]['selected_copy']
    copy.update(copy_version='image-led-selected-copy/v2', title_item_id='title')
    target = binding(copy)
    selection['slides'][0]['target_binding'] = target
    inventory['region_version'] = VERSION
    slide = inventory['slides'][0]
    slide['target_binding'] = deepcopy(target)
    for region in slide['regions']:
        region['appearance']['wrap'] = 'none'
    points = [[0, 20], [60, 20], [60, 0], [100, 40], [60, 80], [60, 60], [0, 60]]
    path = {'width': 100, 'height': 80,
            'commands': [{'moveTo': {'x': points[0][0], 'y': points[0][1]}}] +
                        [{'lineTo': {'x': x, 'y': y}} for x, y in points[1:]] + [{'close': {}}]}
    region = {'region_id': 'flow-path', 'kind': 'relation-path', 'bbox': [650, 70, 100, 80],
              'z_order': 2, 'content': {'items': []}, 'material_binding': None,
              'appearance': {'paths': [path], 'fill': {'type': 'linear-gradient', 'angle': 0,
                  'stops': [{'offset': 0, 'color': '#FFFFFF'}, {'offset': 1, 'color': '#0066CC'}]},
                  'line': None, 'relation_binding': {'origin': 'source-image-derived',
                  'target_image_sha256': target['target_image_sha256'], 'kind': 'directed-edge',
                  'from_item_id': 'title', 'to_item_id': 'body', 'direction': 'forward'}}}
    slide['regions'].append(region)
    return selection, inventory


def path_region(inventory):
    return inventory['slides'][0]['regions'][-1]


class NativeV3ContractTests(unittest.TestCase):
    def setUp(self):
        self.selection, self.inventory = v3_fixture()

    def assert_invalid(self, change):
        inventory = deepcopy(self.inventory)
        change(inventory)
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, self.selection)

    def test_text_only_selection_accepts_native_path_without_copy_changes(self):
        before = deepcopy(self.selection)
        result = validate_region_inventory(self.inventory, self.selection)
        self.assertEqual(result, self.inventory)
        self.assertEqual(self.selection, before)
        original_copy = before['slides'][0]['selected_copy']
        self.assertEqual(selected_copy_sha256(original_copy),
                         result['slides'][0]['target_binding']['selected_copy_sha256'])
        self.assertEqual([i for r in result['slides'][0]['regions'] for i in r['content']['items']],
                         original_copy['items'])
        result['slides'][0]['regions'][-1]['appearance']['paths'][0]['commands'][0]['moveTo']['x'] = 1
        self.assertEqual(path_region(self.inventory)['appearance']['paths'][0]['commands'][0]['moveTo']['x'], 0)

    def test_explicit_v3_objects_preserve_binding_path_and_gradient(self):
        regions = self.inventory['slides'][0]['regions']
        objects = objects_for(regions)
        self.assertEqual(validate_faithful_objects(regions, objects, region_version=VERSION), objects)
        for change in (
            lambda p: p[-1]['appearance']['relation_binding'].update(to_item_id='title'),
            lambda p: p[-1]['appearance']['paths'][0]['commands'][0]['moveTo'].update(x=1),
            lambda p: p[-1]['appearance']['fill']['stops'][1].update(color='#0066CD'),
            lambda p: p[-1].update(render_mode='bitmap'),
            lambda p: p[-1].update(kind='decoration'),
            lambda p: p[-1].update(z_order=8),
            lambda p: p.pop(),
        ):
            with self.subTest(change=change):
                mutated = deepcopy(objects); change(mutated)
                with self.assertRaises(ContractValidationError):
                    validate_faithful_objects(regions, mutated, region_version=VERSION)

    def test_plain_polygon_has_closed_visual_fields_and_no_semantic_content(self):
        region = path_region(self.inventory)
        paths = deepcopy(region['appearance']['paths'])
        region['kind'] = 'shape'
        region['appearance'] = {'geometry': 'polygon', 'paths': paths, 'corner_radius': 0,
            'fill': {'type': 'solid', 'color': '#0066CC'}, 'line': None, 'shadow': None}
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)
        for change in (
            lambda r: r['appearance'].update(corner_radius=1),
            lambda r: r['appearance'].update(relation_binding={}),
            lambda r: r['appearance'].update(geometry='rect'),
            lambda r: r['appearance'].pop('paths'),
            lambda r: r['content']['items'].append(deepcopy(self.selection['slides'][0]['selected_copy']['items'][0])),
        ):
            self.assert_invalid(lambda i: change(path_region(i)))

    def test_feedback_anchors_one_original_item_without_invented_return_edge(self):
        a = path_region(self.inventory)['appearance']
        a['relation_binding'] = {'origin': 'source-image-derived',
            'target_image_sha256': self.inventory['slides'][0]['target_binding']['target_image_sha256'],
            'kind': 'feedback-symbol', 'anchor_item_id': 'body'}
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)
        for bad in ({'from_item_id': 'body'}, {'to_item_id': 'title'}, {'direction': 'both'},
                    {'anchor_item_id': 'invented'}):
            self.assert_invalid(lambda i, b=bad: path_region(i)['appearance']['relation_binding'].update(b))

    def test_relation_origin_hash_endpoints_and_kind_are_closed(self):
        for field, value in (
            ('origin', 'model-guessed'), ('target_image_sha256', 'd' * 64),
            ('target_image_sha256', True), ('from_item_id', 'missing'),
            ('to_item_id', 'flow-path'), ('to_item_id', 'title'),
            ('direction', 'clockwise'), ('direction', True), ('kind', 'arbitrary'),
            ('meaning', 'new customer fact'), ('source_ref', 'invented'),
        ):
            with self.subTest(field=field, value=value):
                self.assert_invalid(lambda i: path_region(i)['appearance']['relation_binding'].update({field: value}))
        self.assert_invalid(lambda i: path_region(i)['content']['items'].append(
            deepcopy(i['slides'][0]['regions'][0]['content']['items'][0])))
        self.assert_invalid(lambda i: path_region(i).update(material_binding={}))

    def test_paths_require_bounded_closed_finite_numeric_polygon_data(self):
        changes = (
            lambda a: a.update(paths=[]),
            lambda a: a.update(paths=a['paths'] * 17),
            lambda a: a['paths'][0].update(width=99),
            lambda a: a['paths'][0].update(width=True),
            lambda a: a['paths'][0].update(xml='<a:custGeom/>'),
            lambda a: a['paths'][0]['commands'].pop(),
            lambda a: a['paths'][0]['commands'][0].update(lineTo={'x': 1, 'y': 1}),
            lambda a: a['paths'][0]['commands'][0].update(moveTo={'x': True, 'y': 20}),
            lambda a: a['paths'][0]['commands'][0].update(moveTo={'x': float('nan'), 'y': 20}),
            lambda a: a['paths'][0]['commands'][0].update(moveTo={'x': float('inf'), 'y': 20}),
            lambda a: a['paths'][0]['commands'][0].update(moveTo={'x': 10 ** 400, 'y': 20}),
            lambda a: a['paths'][0]['commands'][0].update(moveTo={'x': -1, 'y': 20}),
            lambda a: a['paths'][0]['commands'][1].update(lineTo={'x': 101, 'y': 20}),
            lambda a: a['paths'][0]['commands'].append({'close': {'extra': 1}}),
            lambda a: a['paths'][0].update(commands=[{'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 1, 'y': 1}}, {'close': {}}]),
            lambda a: a['paths'][0].update(commands=[{'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 1, 'y': 1}}, {'lineTo': {'x': 2, 'y': 2}}, {'close': {}}]),
            lambda a: a['paths'][0].update(commands=[{'moveTo': {'x': 0, 'y': 0}}, {'cubicBezTo': {}}]),
            lambda a: a.update(fill=None),
            lambda a: a.update(shadow=None),
            lambda a: a.update(paths=a['paths'] * 16) or a['paths'][0].update(commands=a['paths'][0]['commands'] * 300),
        )
        for change in changes:
            with self.subTest(change=change):
                self.assert_invalid(lambda i: change(path_region(i)['appearance']))

    def test_multiple_closed_contours_preserve_an_inner_hole_winding(self):
        a = path_region(self.inventory)['appearance']
        outer = [{'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 100, 'y': 0}},
                 {'lineTo': {'x': 100, 'y': 80}}, {'lineTo': {'x': 0, 'y': 80}}, {'close': {}}]
        inner = [{'moveTo': {'x': 20, 'y': 20}}, {'lineTo': {'x': 20, 'y': 60}},
                 {'lineTo': {'x': 80, 'y': 60}}, {'lineTo': {'x': 80, 'y': 20}}, {'close': {}}]
        a['paths'][0]['commands'] = outer + inner
        actual = validate_region_inventory(self.inventory, self.selection)
        self.assertEqual(path_region(actual)['appearance']['paths'][0]['commands'], outer + inner)

    def test_v3_natural_wrap_preserves_exact_unicode_and_no_added_breaks(self):
        first = self.inventory['slides'][0]['regions'][0]
        first['appearance']['wrap'] = 'square'
        original = deepcopy(self.selection)
        self.assertEqual(validate_region_inventory(self.inventory, self.selection), self.inventory)
        self.assertEqual(self.selection, original)
        for bad in ('shrinkText', 'automatic', True, None):
            self.assert_invalid(lambda i: i['slides'][0]['regions'][0]['appearance'].update(wrap=bad))
        self.assert_invalid(lambda i: i['slides'][0]['regions'][0]['appearance'].pop('wrap'))
        self.assert_invalid(lambda i: i['slides'][0]['regions'][0]['appearance'].update(autoFit='shrinkText'))
        self.assert_invalid(lambda i: i['slides'][0]['regions'][0]['appearance']['runs'][0].update(text='other\ntext'))

    def test_table_cell_wrapping_is_explicit_and_keeps_cell_content_identity(self):
        selection, inventory = rich_fixture()
        copy = selection['slides'][0]['selected_copy']
        copy.update(copy_version='image-led-selected-copy/v2', title_item_id='title')
        target = binding(copy)
        selection['slides'][0]['target_binding'] = target
        inventory['slides'][0]['target_binding'] = deepcopy(target)
        inventory['region_version'] = VERSION
        for region in inventory['slides'][0]['regions']:
            if region['kind'] == 'text':
                region['appearance']['wrap'] = 'none'
            if region['kind'] == 'table':
                for cell in region['appearance']['cells']:
                    cell['style']['wrap'] = 'square'
        before = deepcopy(copy)
        self.assertEqual(validate_region_inventory(inventory, selection), inventory)
        self.assertEqual(copy, before)
        table = next(r for r in inventory['slides'][0]['regions'] if r['kind'] == 'table')
        table['appearance']['cells'][0]['style'].pop('wrap')
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(inventory, selection)

    def test_unclosed_subpath_and_command_after_close_are_rejected(self):
        for commands in (
            [{'lineTo': {'x': 1, 'y': 2}}, {'close': {}}],
            [{'moveTo': {'x': 0, 'y': 0}}, {'moveTo': {'x': 1, 'y': 2}}],
            [{'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 100, 'y': 0}},
             {'lineTo': {'x': 0, 'y': 80}}, {'close': {}}, {'lineTo': {'x': 1, 'y': 2}}],
            [{'moveTo': {'x': 0, 'y': 0}}, {'lineTo': {'x': 100, 'y': 0}},
             {'lineTo': {'x': 0, 'y': 80}}, {'close': {}}, {'close': {}}],
        ):
            self.assert_invalid(lambda i, cmds=commands: path_region(i)['appearance']['paths'][0].update(commands=cmds))

    def test_new_fields_cannot_silently_enter_legacy_or_unknown_version(self):
        for value in ('image-led-region-inventory/v2', 'v3', '', True, None):
            self.assert_invalid(lambda i, v=value: i.update(region_version=v))
        self.assert_invalid(lambda i: i.pop('region_version'))
        regions = self.inventory['slides'][0]['regions']
        with self.assertRaises(ContractValidationError):
            validate_faithful_objects(regions, objects_for(regions))
        with self.assertRaises(ContractValidationError):
            validate_faithful_objects(regions, objects_for(regions), region_version='unknown')
        old_selection, old_inventory = fixture()
        self.assertEqual(validate_region_inventory(old_inventory, old_selection), old_inventory)
        old_regions = old_inventory['slides'][0]['regions']
        self.assertEqual(validate_faithful_objects(old_regions, objects_for(old_regions)), objects_for(old_regions))

    def test_v3_requires_original_v2_copy_and_handoff_reads_same_identity(self):
        slide = deepcopy(self.inventory['slides'][0])
        slide['selected_copy'] = deepcopy(self.selection['slides'][0]['selected_copy'])
        self.assertEqual(handoff_selected_copy(slide, 'codex-presentations-image-led/v3'), slide['selected_copy'])
        copy = self.selection['slides'][0]['selected_copy']
        copy.pop('copy_version'); copy.pop('title_item_id')
        target = binding(copy)
        self.selection['slides'][0]['target_binding'] = target
        self.inventory['slides'][0]['target_binding'] = deepcopy(target)
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(self.inventory, self.selection)


if __name__ == '__main__':
    unittest.main()
