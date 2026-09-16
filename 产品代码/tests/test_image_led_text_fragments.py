"""One selected item, exact Unicode spans, independent source-mapped native boxes."""
from copy import deepcopy
import unittest

from test_image_led_contracts import binding, objects_for, text_style
from test_image_led_native_v3_contracts import VERSION, v3_fixture
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, validate_faithful_objects
from ai_ppt_studio.errors import ContractValidationError


def fragment_fixture():
    selection,inventory=v3_fixture()
    text='A😀e\u0301｜Body'
    item=selection['slides'][0]['selected_copy']['items'][0];item['text']=text
    region=inventory['slides'][0]['regions'][0]
    region['content']['items']=[deepcopy(item)];region['bbox']=[20,30,550,150]
    fragments=[]
    for span,bbox in [([0,4],[60,30,450,60]),([4,5],[20,30,30,150]),([5,9],[60,100,450,60])]:
        fragments.append({'span':span,'bbox':bbox,'appearance':{**text_style(text[slice(*span)]),'wrap':'none'}})
    region['appearance']={'fragments':fragments}
    target=binding(selection['slides'][0]['selected_copy'])
    selection['slides'][0]['target_binding']=target;inventory['slides'][0]['target_binding']=deepcopy(target)
    return selection,inventory


class TextFragmentContractTests(unittest.TestCase):
    def accepted(self,selection,inventory):
        try:self.assertEqual(validate_region_inventory(inventory,selection),inventory)
        except ContractValidationError as error:self.fail('Exact source-mapped fragments rejected: '+str(error))

    def test_unicode_codepoint_spans_retain_one_original_item_and_spatial_order(self):
        selection,inventory=fragment_fixture();before=deepcopy(inventory)
        self.accepted(selection,inventory)
        region=inventory['slides'][0]['regions'][0];fragments=region['appearance']['fragments']
        self.assertEqual([f['appearance']['runs'][0]['text'] for f in fragments],['A😀e\u0301','｜','Body'])
        self.assertEqual(len(region['content']['items']),1)
        self.assertEqual(inventory,before)
        self.assertEqual(fragments[1]['bbox'][0],20)  # Source order need not equal x/y order.
        objects=objects_for(inventory['slides'][0]['regions'])
        self.assertEqual(validate_faithful_objects(inventory['slides'][0]['regions'],objects,region_version=VERSION),objects)

    def test_original_double_spaces_can_form_a_nonempty_whitespace_fragment(self):
        selection,inventory=fragment_fixture();item=selection['slides'][0]['selected_copy']['items'][0]
        item['text']='A😀e\u0301  ｜Body';region=inventory['slides'][0]['regions'][0];region['content']['items']=[deepcopy(item)]
        fragments=region['appearance']['fragments'];fragments[1]['span']=[6,7];fragments[2]['span']=[7,11]
        fragments.insert(1,{'span':[4,6],'bbox':[500,30,40,50],'appearance':{**text_style('  '),'wrap':'none'}})
        target=binding(selection['slides'][0]['selected_copy']);selection['slides'][0]['target_binding']=target
        inventory['slides'][0]['target_binding']=deepcopy(target)
        self.accepted(selection,inventory)
        self.assertEqual(''.join(r['text'] for f in fragments for r in f['appearance']['runs']),item['text'])

    def test_span_gaps_overlaps_bounds_types_and_utf16_offsets_reject(self):
        for index,span in [(0,[1,4]),(0,[0,0]),(0,[0,5]),(0,[False,4]),(0,[-1,4]),
                           (1,[5,6]),(1,[3,5]),(2,[5,8]),(2,[5,10]),(2,[5,9,10]),(2,['5',9])]:
            selection,inventory=fragment_fixture();inventory['slides'][0]['regions'][0]['appearance']['fragments'][index]['span']=span
            with self.subTest(index=index,span=span),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_missing_duplicate_empty_or_reordered_fragments_reject(self):
        for mutate in [lambda f:f.pop(),lambda f:f.append(deepcopy(f[-1])),lambda f:f.clear(),lambda f:f.reverse()]:
            selection,inventory=fragment_fixture();mutate(inventory['slides'][0]['regions'][0]['appearance']['fragments'])
            with self.subTest(mutate=mutate),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_fragment_text_cannot_be_changed_normalized_or_duplicated(self):
        for text in ['A😀é','A😀e\u0301｜','A😀e','', 'hidden']:
            selection,inventory=fragment_fixture();inventory['slides'][0]['regions'][0]['appearance']['fragments'][0]['appearance']['runs'][0]['text']=text
            with self.subTest(text=text),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_fragment_boxes_are_explicit_visible_and_contained_in_region(self):
        for bbox in [[0,30,450,60],[60,0,450,60],[60,30,700,60],[60,160,450,60],[60,30,0,60],[-1,30,450,60],[60,30,float('nan'),60]]:
            selection,inventory=fragment_fixture();inventory['slides'][0]['regions'][0]['appearance']['fragments'][0]['bbox']=bbox
            with self.subTest(bbox=bbox),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_schema_is_v3_only_closed_mutually_exclusive_and_not_recursive(self):
        for mutate in [lambda i:i.pop('region_version'),
            lambda i:i['slides'][0]['regions'][0]['appearance'].update(runs=[]),
            lambda i:i['slides'][0]['regions'][0]['appearance']['fragments'][0].update(text='extra'),
            lambda i:i['slides'][0]['regions'][0]['appearance']['fragments'][0].update(appearance={'fragments':[]})]:
            selection,inventory=fragment_fixture();mutate(inventory)
            with self.subTest(mutate=mutate),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_object_projection_cannot_move_drop_or_flatten_a_fragment(self):
        _,inventory=fragment_fixture();regions=inventory['slides'][0]['regions'];objects=objects_for(regions)
        for mutate in [lambda o:o[0]['appearance']['fragments'].pop(),
            lambda o:o[0]['appearance']['fragments'][0]['bbox'].__setitem__(0,65),
            lambda o:o[0].update(render_mode='bitmap')]:
            bad=deepcopy(objects);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(ContractValidationError):validate_faithful_objects(regions,bad,region_version=VERSION)

    def test_fragment_native_ids_cannot_collide_with_another_logical_object(self):
        _,inventory=fragment_fixture();regions=inventory['slides'][0]['regions'];objects=objects_for(regions)
        objects[1]['object_id']=objects[0]['object_id']+'::fragment:0:4'
        with self.assertRaises(ContractValidationError):validate_faithful_objects(regions,objects,region_version=VERSION)

    def test_region_relation_still_resolves_whole_item_not_an_arbitrary_fragment(self):
        selection,inventory=fragment_fixture();b=inventory['slides'][0]['regions'][-1]['appearance']['relation_binding']
        b.pop('from_item_id');b.pop('to_item_id');b.update(from_region_id='title',to_region_id='body')
        self.accepted(selection,inventory)
        for endpoint in ['title::fragment:0:4','object-title::fragment:0:4']:
            b['from_region_id']=endpoint
            with self.subTest(endpoint=endpoint),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_legacy_physical_connector_cannot_choose_one_fragment(self):
        from test_image_led_contracts import rich_fixture
        _,inventory=fragment_fixture();regions=inventory['slides'][0]['regions']
        connector=deepcopy(next(r for r in rich_fixture()[1]['slides'][0]['regions'] if r['kind']=='connector'))
        connector['z_order']=3;regions.append(connector)
        with self.assertRaisesRegex(ContractValidationError,'CapabilityGap.*fragment endpoint'):
            validate_faithful_objects(regions,objects_for(regions),region_version=VERSION)

    def test_compiler_retains_one_logical_object_with_full_item(self):
        from tests.test_image_led_compilation import fixture_for,compile_plan
        selection,inventory=fragment_fixture();_,brief,design,contract=fixture_for(selection,inventory)
        try:plan=compile_plan(contract,selection,inventory,brief,design)
        except ContractValidationError as error:self.fail('Fragment plan rejected: '+str(error))
        self.assertEqual(len(plan['slides'][0]['objects']),len(inventory['slides'][0]['regions']))
        self.assertEqual(plan['slides'][0]['objects'][0]['appearance'],inventory['slides'][0]['regions'][0]['appearance'])
        self.assertEqual(plan['slides'][0]['selected_copy'],selection['slides'][0]['selected_copy'])



def selected_crop_fixture():
    selection,inventory=v3_fixture()
    role={'atom_id':'original-photo','source_ref':'artifact://material-source/'+'e'*64,
          'content_sha256':'f'*64,'use':'real-material'}
    target=selection['slides'][0]['target_binding'];target['material_roles']=[role]
    slide=inventory['slides'][0];slide['target_binding']=deepcopy(target)
    slide['regions'].append({'region_id':'selected-photo','kind':'image','bbox':[900,400,128,72],
        'z_order':3,'content':{'items':[]},'material_binding':deepcopy(role),
        'appearance':{'asset_ref':target['target_image_ref'],'asset_sha256':target['target_image_sha256'],
                      'crop':[0.25,0.25,0.5,0.5],'render_source':'selected-image-crop'}})
    return selection,inventory


class SelectedImageCropContractTests(unittest.TestCase):
    def test_selected_pixels_and_original_material_identity_remain_distinct(self):
        selection,inventory=selected_crop_fixture();before=deepcopy(inventory)
        try:self.assertEqual(validate_region_inventory(inventory,selection),inventory)
        except ContractValidationError as error:self.fail('Exact selected crop rejected: '+str(error))
        photo=inventory['slides'][0]['regions'][-1]
        self.assertNotEqual(photo['appearance']['asset_sha256'],photo['material_binding']['content_sha256'])
        self.assertEqual(inventory,before)
        regions=inventory['slides'][0]['regions']
        self.assertEqual(validate_faithful_objects(regions,objects_for(regions),region_version=VERSION),objects_for(regions))

    def test_arbitrary_asset_wrong_hash_unbound_decoration_and_nonreal_role_reject(self):
        changes=[lambda p:p['appearance'].update(asset_ref='artifact://image-led-crop/'+'c'*64),
            lambda p:p['appearance'].update(asset_sha256=p['material_binding']['content_sha256']),
            lambda p:p['appearance'].update(render_source='original-material'),
            lambda p:p['appearance'].update(crop=[0.7,0,0.5,1]),
            lambda p:p.update(material_binding=None),lambda p:p.update(kind='decoration'),
            lambda p:p['material_binding'].update(use='style-reference'),
            lambda p:p['material_binding'].update(content_sha256=p['appearance']['asset_sha256'])]
        for change in changes:
            selection,inventory=selected_crop_fixture();change(inventory['slides'][0]['regions'][-1])
            with self.subTest(change=change),self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_old_image_still_requires_exact_original_material_bytes(self):
        selection,inventory=selected_crop_fixture();photo=inventory['slides'][0]['regions'][-1]
        photo['appearance'].pop('render_source')
        with self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)
        photo['appearance']['asset_sha256']=photo['material_binding']['content_sha256']
        self.assertEqual(validate_region_inventory(inventory,selection),inventory)

    def test_same_material_can_have_multiple_independently_bound_crops(self):
        selection,inventory=selected_crop_fixture();photo=deepcopy(inventory['slides'][0]['regions'][-1])
        photo.update(region_id='selected-photo-2',z_order=4);photo['appearance']['crop']=[0,0,0.25,0.25]
        inventory['slides'][0]['regions'].append(photo)
        try:self.assertEqual(validate_region_inventory(inventory,selection),inventory)
        except ContractValidationError as error:self.fail('Two exact crops of one real-material role rejected: '+str(error))

    def test_cross_slide_selected_asset_cannot_replace_current_selected_image(self):
        selection,inventory=selected_crop_fixture()
        second=deepcopy(inventory['slides'][0]);selected=deepcopy(selection['slides'][0])
        target=second['target_binding'];target.update(slide_id='s2',page_order=2,target_image_ref='artifact://image-led-image/'+'d'*64,target_image_sha256='d'*64)
        selected['target_binding']=deepcopy(target)
        second['regions'][-2]['appearance']['relation_binding']['target_image_sha256']=target['target_image_sha256']
        second['regions'][-1]['appearance'].update(asset_ref=target['target_image_ref'],asset_sha256=target['target_image_sha256'])
        inventory['slides'].append(second);selection['slides'].append(selected)
        inventory['slides'][0]['regions'][-1]['appearance'].update(asset_ref=target['target_image_ref'],asset_sha256=target['target_image_sha256'])
        with self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)


if __name__=='__main__':unittest.main()
