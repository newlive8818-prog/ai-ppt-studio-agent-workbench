"""Source-image path endpoints may bind real same-slide regions, never guessed items."""
from copy import deepcopy
import unittest

from test_image_led_contracts import binding, objects_for, text_item, text_style
from test_image_led_native_v3_contracts import VERSION, v3_fixture
from ai_ppt_studio.domains.visual.image_led import validate_region_inventory, validate_faithful_objects
from ai_ppt_studio.errors import ContractValidationError


def container_fixture():
    selection, inventory = v3_fixture()
    slide = inventory['slides'][0]
    regions = slide['regions']
    prototype = regions.pop()
    # The common visible bar carries no new text. Original selected items stay
    # in their own text regions rather than being collapsed into one endpoint.
    regions.append({'region_id':'common-bar','kind':'shape','bbox':[10,10,620,200],
        'z_order':2,'content':{'items':[]},'material_binding':None,
        'appearance':{'geometry':'rect','corner_radius':0,
            'fill':{'type':'solid','color':'#CCE4F5'},'line':None,'shadow':None}})
    copy = selection['slides'][0]['selected_copy']
    for index in range(4):
        item = text_item('domain-'+str(index),'Domain '+str(index))
        copy['items'].append(item)
        regions.append({'region_id':'domain-region-'+str(index),'kind':'text',
            'bbox':[20+index*300,300,250,80],'z_order':3+index,
            'content':{'items':[deepcopy(item)]},'material_binding':None,
            'appearance':{**text_style(item['text']),'wrap':'none'}})
    target = binding(copy)
    selection['slides'][0]['target_binding'] = target
    slide['target_binding'] = deepcopy(target)
    for index in range(4):
        arrow = deepcopy(prototype)
        arrow.update(region_id='arrow-'+str(index),z_order=7+index)
        arrow['appearance']['relation_binding'] = {
            'origin':'source-image-derived','target_image_sha256':target['target_image_sha256'],
            'kind':'directed-edge','from_region_id':'common-bar',
            'to_region_id':'domain-region-'+str(index),'direction':'forward'}
        regions.append(arrow)
    return selection, inventory


class RegionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.selection, self.inventory = container_fixture()

    def accepted(self, inventory=None):
        value = self.inventory if inventory is None else inventory
        try:
            return validate_region_inventory(value,self.selection)
        except ContractValidationError as error:
            self.fail('A source-bound same-slide container endpoint was rejected: '+str(error))

    def reject(self, change):
        value = deepcopy(self.inventory)
        change(value['slides'][0])
        with self.assertRaises(ContractValidationError):
            validate_region_inventory(value,self.selection)

    def test_four_paths_share_real_container_without_inventing_from_item(self):
        before = deepcopy(self.inventory)
        result = self.accepted()
        self.assertEqual(result,before)
        self.assertEqual(self.inventory,before)
        regions = result['slides'][0]['regions']
        self.assertEqual([i for r in regions for i in r['content']['items']],self.selection['slides'][0]['selected_copy']['items'])
        self.assertEqual([r['appearance']['relation_binding']['from_region_id'] for r in regions[-4:]],['common-bar']*4)
        self.assertEqual([r['appearance']['relation_binding']['to_region_id'] for r in regions[-4:]],
                         ['domain-region-0','domain-region-1','domain-region-2','domain-region-3'])

    def test_region_endpoint_supports_real_text_region_without_layout_snap(self):
        value = deepcopy(self.inventory)
        value['slides'][0]['regions'][-1]['appearance']['relation_binding']['from_region_id'] = 'title'
        self.assertEqual(self.accepted(value),value)

    def test_old_item_endpoint_contract_stays_compatible(self):
        selection, inventory = v3_fixture()
        self.assertEqual(validate_region_inventory(inventory,selection),inventory)

    def test_missing_cross_page_and_non_region_ids_are_rejected(self):
        for identity in ('missing','other-slide/common-bar','domain-0','',True):
            with self.subTest(identity=identity):
                self.reject(lambda s,identity=identity:s['regions'][-1]['appearance']['relation_binding'].update(from_region_id=identity))

    def test_actual_region_on_another_slide_cannot_resolve_locally(self):
        selection, inventory = deepcopy(self.selection),deepcopy(self.inventory)
        second, second_selection = deepcopy(inventory['slides'][0]),deepcopy(selection['slides'][0])
        second['target_binding']['slide_id']='second';second['target_binding']['page_order']=2
        second_selection['target_binding']=deepcopy(second['target_binding'])
        second['regions'][2]['region_id']='other-bar'
        for r in second['regions'][-4:]:r['appearance']['relation_binding']['from_region_id']='other-bar'
        inventory['slides'].append(second);selection['slides'].append(second_selection)
        inventory['slides'][0]['regions'][-1]['appearance']['relation_binding']['from_region_id']='other-bar'
        with self.assertRaises(ContractValidationError):validate_region_inventory(inventory,selection)

    def test_endpoint_pair_is_closed_and_exclusive(self):
        for change in (
            lambda b:b.pop('from_region_id'),
            lambda b:b.update(from_item_id='title'),
            lambda b:b.update(from_item_id='title',to_item_id='body'),
            lambda b:b.update(from_region_id={'region_id':'common-bar'}),
            lambda b:b.update(meaning='invented label'),
        ):
            with self.subTest(change=change):self.reject(lambda s,change=change:change(s['regions'][-1]['appearance']['relation_binding']))

    def test_self_edge_and_path_as_endpoint_are_rejected(self):
        for key,identity in (('to_region_id','common-bar'),('from_region_id','arrow-3'),('from_region_id','arrow-0')):
            with self.subTest(key=key,identity=identity):
                self.reject(lambda s,key=key,identity=identity:s['regions'][-1]['appearance']['relation_binding'].update({key:identity}))

    def test_invisible_or_decorative_container_cannot_supply_a_real_endpoint(self):
        for change in (
            lambda r:r['appearance'].update(fill=None,line=None),
            lambda r:r.update(kind='decoration',appearance={'asset_ref':'artifact://image-led-crop/'+'a'*64,'asset_sha256':'b'*64,'crop':[0,0,1,1]}),
        ):
            with self.subTest(change=change):self.reject(lambda s,change=change:change(s['regions'][2]))

    def test_wrong_target_hash_and_guessed_origin_are_rejected(self):
        for change in ({'target_image_sha256':'d'*64},{'origin':'model-guessed'}):
            with self.subTest(change=change):self.reject(lambda s,change=change:s['regions'][-1]['appearance']['relation_binding'].update(change))

    def test_faithful_object_mapping_preserves_region_endpoints_and_paths(self):
        regions=self.inventory['slides'][0]['regions'];objects=objects_for(regions)
        try:actual=validate_faithful_objects(regions,objects,region_version=VERSION)
        except ContractValidationError as error:self.fail('Faithful region endpoint mapping rejected: '+str(error))
        self.assertEqual(actual,objects)
        for change in (
            lambda o:o[-1]['appearance']['relation_binding'].update(to_region_id='title'),
            lambda o:o[-1]['appearance']['paths'][0]['commands'][0]['moveTo'].update(x=1),
            lambda o:o[-1].update(render_mode='bitmap'),
        ):
            with self.subTest(change=change):
                bad=deepcopy(objects);change(bad)
                with self.assertRaises(ContractValidationError):validate_faithful_objects(regions,bad,region_version=VERSION)


if __name__ == '__main__':unittest.main()
