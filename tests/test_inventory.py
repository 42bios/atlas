import copy
import unittest
from server import demo, validate
from connector_engine import merge, SCHEMA


class InventoryTests(unittest.TestCase):
    def test_fiber_connection_metadata(self):
        data = demo()
        link = next(x for x in data['links'] if x['type'] == 'Network')
        link.update(cableMedium='fiber', fiberType='OS2', fiberCount=2,
                    sourceConnector='LC/UPC', targetConnector='SC/APC', cableLength=3.5)
        self.assertEqual(validate(data)['links'], data['links'])
        link['fiberCount'] = 1.5
        with self.assertRaisesRegex(ValueError, 'Fiber count'):
            validate(data)

    def test_invalid_cable_length(self):
        data = demo()
        data['links'][0]['cableLength'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Cable length'):
            validate(data)

    def test_sample_is_valid(self):
        validate(demo())

    def test_rack_collision(self):
        data = demo()
        data['devices'][3]['unit'] = 16
        with self.assertRaisesRegex(ValueError, 'overlap'):
            validate(data)

    def test_rack_boundary(self):
        data = demo()
        data['devices'][3]['unit'] = 18
        with self.assertRaisesRegex(ValueError, 'fit'):
            validate(data)

    def test_duplicate_address(self):
        data = demo()
        data['addresses'][0]['ip'] = '10.0.10.10'
        with self.assertRaisesRegex(ValueError, 'already'):
            validate(data)

    def test_pdu_outlet_conflict(self):
        data = demo()
        data['links'][5]['targetPort'] = '3'
        with self.assertRaisesRegex(ValueError, 'outlet is already'):
            validate(data)

    def test_pdu_outlet_out_of_range(self):
        data = demo()
        data['links'][4]['targetPort'] = '99'
        with self.assertRaisesRegex(ValueError, 'valid PDU'):
            validate(data)

    def test_host_cycles(self):
        data = demo()
        data['services'][0]['host'] = 'photos'
        with self.assertRaisesRegex(ValueError, 'cycle'):
            validate(data)

    def test_import_idempotent_preserves_manual_placement(self):
        data, _ = merge(demo(), SCHEMA)
        host = next(d for d in data['devices'] if d['id'] == 'connector:my-source:host')
        host.update(rack='rack-1', unit=5, height=1, notes='Keep me', name='My chosen name', _overrides=['name'])
        again, _ = merge(data, SCHEMA)
        validate(again)
        imported = [d for d in again['devices'] if d['id'] == host['id']]
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]['unit'], 5)
        self.assertEqual(imported[0]['notes'], 'Keep me')
        self.assertEqual(imported[0]['name'], 'My chosen name')

    def test_missing_records_retained(self):
        data, _ = merge(demo(), SCHEMA)
        changed = copy.deepcopy(SCHEMA)
        changed['services'] = []
        data, _ = merge(data, changed)
        app = next(s for s in data['services'] if s['id'] == 'connector:my-source:app')
        self.assertTrue(app['missing'])
        validate(data)

    def test_invalid_schema(self):
        with self.assertRaisesRegex(ValueError, 'schemaVersion'):
            merge(demo(), {'connector': 'x', 'schemaVersion': 2})

    def test_connector_namespaces_references(self):
        data, _ = merge(demo(), SCHEMA)
        app = next(s for s in data['services'] if s['id'] == 'connector:my-source:app')
        self.assertEqual(app['host'], 'connector:my-source:host')


if __name__ == '__main__':
    unittest.main()

class ShelfTests(unittest.TestCase):
    def inventory(self, numbering='bottom'):
        data=demo()
        data['racks'].append({'id':'shelf-rack','name':'Shelf rack','units':12,'numbering':numbering})
        data['devices'].append({'id':'shelf','name':'Shelf','kind':'Rack shelf','rack':'shelf-rack','unit':1 if numbering=='bottom' else 12,'height':1,'shelfClearance':4,'ports':0})
        for suffix in ('a','b'):
            data['devices'].append({'id':'nas-'+suffix,'name':'NAS '+suffix,'kind':'NAS','rack':'','unit':0,'height':4,'shelfId':'shelf','shelfWidth':50,'ports':2})
        return data

    def test_two_nas_share_shelf(self):
        validate(self.inventory())
        validate(self.inventory('top'))

    def test_width_overflow(self):
        data=self.inventory();data['devices'][-1]['shelfWidth']=51
        with self.assertRaisesRegex(ValueError,'available width'):validate(data)

    def test_clearance_too_small(self):
        data=self.inventory();data['devices'][-1]['height']=5
        with self.assertRaisesRegex(ValueError,'clearance'):validate(data)

    def test_clearance_blocks_other_rack_devices(self):
        for numbering in ('bottom','top'):
            data=self.inventory(numbering)
            data['devices'].append({'id':'collision','name':'Collision','kind':'Switch','rack':'shelf-rack','unit':3 if numbering=='bottom' else 10,'height':1,'ports':24})
            with self.assertRaisesRegex(ValueError,'overlap'):validate(data)

    def test_clearance_must_fit_in_rack(self):
        data=self.inventory();data['devices'][-3]['unit']=10
        with self.assertRaisesRegex(ValueError,'fit'):validate(data)

    def test_shelf_reference_is_required_and_cannot_nest(self):
        data=self.inventory();data['devices'][-1]['shelfId']='missing'
        with self.assertRaisesRegex(ValueError,'existing rack-mounted shelf'):validate(data)
        data=self.inventory();data['devices'][-1]['kind']='Rack shelf'
        with self.assertRaisesRegex(ValueError,'rack accessories'):validate(data)

    def test_thin_shelf_does_not_add_an_extra_unit(self):
        for numbering in ('bottom', 'top'):
            data=self.inventory(numbering)
            shelf=data['devices'][-3]
            shelf['shelfSpace']=3
            shelf.pop('shelfClearance')
            for child in data['devices'][-2:]: child['height']=3
            data['devices'].append({'id':'adjacent','name':'Adjacent','kind':'Switch','rack':'shelf-rack','unit':4 if numbering=='bottom' else 9,'height':1,'ports':24})
            validate(data)
            data['devices'][-1]['unit']=3 if numbering=='bottom' else 10
            with self.assertRaisesRegex(ValueError,'overlap'): validate(data)

    def test_total_space_limits_devices_and_rack_bounds(self):
        data=self.inventory();data['devices'][-3]['shelfSpace']=3
        with self.assertRaisesRegex(ValueError,'clearance'):validate(data)
        data=self.inventory();data['devices'][-3]['shelfSpace']=0
        with self.assertRaisesRegex(ValueError,'Total shelf space'):validate(data)

    def measured_inventory(self):
        data=self.inventory()
        data['devices'][-3].update(shelfSpace=4,usableWidthMm=480,usableDepthMm=300)
        for index,child in enumerate(data['devices'][-2:]):
            child.update(widthMm=230,depthMm=223,heightMm=166,shelfXmm=index*240,shelfYmm=0)
        return data

    def test_measured_positions_and_touching_edges(self):
        data=self.measured_inventory();validate(data)
        data['devices'][-1]['shelfXmm']=230;validate(data)

    def test_measured_width_depth_and_height_limits(self):
        for key,value,error in [('shelfXmm',251,'usable shelf area'),('shelfYmm',78,'usable shelf area'),('heightMm',180,'physical height')]:
            data=self.measured_inventory();data['devices'][-1][key]=value
            with self.assertRaisesRegex(ValueError,error):validate(data)

    def test_measured_footprints_cannot_overlap(self):
        data=self.measured_inventory();data['devices'][-1]['shelfXmm']=220
        with self.assertRaisesRegex(ValueError,'footprints overlap'):validate(data)

    def test_devices_can_share_width_at_different_depths(self):
        data=self.measured_inventory();data['devices'][-3]['usableDepthMm']=500
        data['devices'][-1].update(shelfXmm=0,shelfYmm=230,shelfWidth=100)
        data['devices'][-2]['shelfWidth']=100
        validate(data)

    def test_measured_layout_requires_all_dimensions(self):
        data=self.measured_inventory();del data['devices'][-1]['depthMm']
        with self.assertRaisesRegex(ValueError,'need width'):validate(data)
        data=self.measured_inventory();del data['devices'][-3]['usableDepthMm']
        with self.assertRaisesRegex(ValueError,'both usable'):validate(data)

    def test_dimension_types_and_invalid_coordinates(self):
        for value in (True, '230', float('nan'), float('inf'), -1):
            data=self.measured_inventory();data['devices'][-1]['widthMm']=value
            with self.assertRaisesRegex(ValueError,'finite millimetre'):validate(data)
        data=self.measured_inventory();data['devices'][-1]['shelfXmm']=-1
        with self.assertRaisesRegex(ValueError,'finite millimetre'):validate(data)
