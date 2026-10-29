import json
import unittest
from device_catalog import catalog_url, parse_catalog, merge_catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.source = 'https://raw.githubusercontent.com/user/lab/main/catalog.json'
        self.item = dict(id='switch', name='Switch', manufacturer='Maker', model='Model',
                         kind='Switch', height=1, ports=24, frontImage='images/front.png')

    def parse(self):
        return parse_catalog(json.dumps(dict(version=1, devices=[self.item])), self.source)

    def test_image_frame_preserved_and_bounded(self):
        self.item['frontImageFrame'] = dict(x=100,y=200,width=800,height=75,canvasWidth=1000,canvasHeight=1000,rackSuitable=True)
        self.assertEqual(self.parse()[0]['frontImageFrame'],self.item['frontImageFrame'])
        for key,value in [('x',-1),('width',1001),('height',0),('y',float('nan')),('rackSuitable','yes')]:
            original=self.item['frontImageFrame'][key]
            self.item['frontImageFrame'][key]=value
            with self.assertRaises(ValueError):self.parse()
            self.item['frontImageFrame'][key]=original

    def test_repo_and_file_links(self):
        self.assertEqual(catalog_url('https://github.com/user/lab'), self.source)
        self.assertEqual(catalog_url('https://github.com/user/lab/blob/main/catalog.json'), self.source)

    def test_relative_images_and_hardware(self):
        result = self.parse()[0]
        self.assertEqual(result['frontImage'], self.source.replace('catalog.json', 'images/front.png'))
        self.assertEqual(result['ports'], 24)

    def test_external_image_rejected(self):
        self.item['frontImage'] = 'https://example.com/image.png'
        with self.assertRaises(ValueError):
            self.parse()

    def test_invalid_dimensions_rejected(self):
        self.item['height'] = 0
        with self.assertRaises(ValueError):
            self.parse()

    def test_non_github_source_rejected(self):
        with self.assertRaises(ValueError):
            catalog_url('https://localhost/catalog.json')

    def test_shelf_layout_fields_and_notes(self):
        self.item.update(kind='Rack shelf',shelfSpace=3,shelfWidth=50,notes='Thin floor included')
        record=self.parse()[0]
        self.assertEqual(record['shelfSpace'],3)
        self.assertEqual(record['shelfWidth'],50)
        self.assertEqual(record['notes'],'Thin floor included')
        self.item['shelfSpace']=0
        with self.assertRaises(ValueError):self.parse()

    def test_physical_dimensions_survive_import(self):
        self.item.update(widthMm=230,depthMm=223,heightMm=166)
        self.assertEqual(self.parse()[0]['widthMm'],230)
        self.item['heightMm']=float('nan')
        with self.assertRaises(ValueError):self.parse()

    def test_interface_definitions_are_reusable(self):
        self.item['interfaces'] = [dict(name='eth0', type='Ethernet', ips=['192.0.2.2'], lag='bond0'), dict(name='bond0', type='LAG', ips=[])]
        record = self.parse()[0]
        self.assertEqual(record['interfaces'][0]['name'], 'eth0')
        self.assertEqual(record['interfaces'][0]['ips'], [])
        self.assertEqual(record['interfaces'][0]['lag'], 'bond0')

    def test_invalid_catalog_interface(self):
        self.item['interfaces'] = [dict(name='eth0', type='Ethernet', ips=[], lag='missing')]
        with self.assertRaisesRegex(ValueError, 'LAG'):
            self.parse()


class MultiCatalogTests(unittest.TestCase):
    def test_independent_refresh_and_ids(self):
        a='https://raw.githubusercontent.com/a/devices/main/catalog.json'
        b='https://raw.githubusercontent.com/b/devices/main/catalog.json'
        model=dict(id='switch', name='Switch')
        state=dict(deviceCatalog=[], devices=[dict(id='installed',hardwareSpec=dict(model='Old'))])
        state=merge_catalog(state,a,[model])
        state=merge_catalog(state,b,[model])
        self.assertEqual(len(state['catalogSources']),2)
        self.assertEqual(len({m['id'] for m in state['deviceCatalog']}),2)
        state=merge_catalog(state,a,[dict(model,name='Updated')])
        self.assertEqual(sorted(m['name'] for m in state['deviceCatalog']),['Switch','Updated'])
        self.assertEqual(state['devices'][0]['hardwareSpec']['model'],'Old')

    def test_legacy_migration_and_disabled_source(self):
        a='https://raw.githubusercontent.com/a/devices/main/catalog.json'
        b='https://raw.githubusercontent.com/b/devices/main/catalog.json'
        state=merge_catalog(dict(catalogSource=a,deviceCatalog=[dict(id='legacy',name='Legacy')]),b,[dict(id='new',name='New')])
        self.assertEqual(len(state['deviceCatalog']),2)
        state['catalogSources'][1]['enabled']=False
        state=merge_catalog(state,b,[dict(id='new',name='Refresh')])
        self.assertFalse(state['catalogSources'][1]['enabled'])
        self.assertEqual(state['deviceCatalog'][0]['id'],'legacy')
