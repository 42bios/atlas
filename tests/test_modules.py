import json
from pathlib import Path
import unittest
from atlas_core.modules import Module, ModuleRegistry
from atlas_modules.registry import registry

class ModuleTests(unittest.TestCase):
    def manifests(self, *ids):
        return [{'id':id,'requires':[],'pages':[]} for id in ids]
    def test_dependencies_resolve_before_consumers(self):
        data=self.manifests('consumer','provider');data[0]['requires']=['provider']
        r=ModuleRegistry(data,[Module('consumer'),Module('provider')],[])
        self.assertEqual(r.order,['provider','consumer'])
    def test_missing_dependencies_and_cycles_fail_at_startup(self):
        data=self.manifests('a');data[0]['requires']=['missing']
        with self.assertRaisesRegex(ValueError,'Missing module dependency'):ModuleRegistry(data,[Module('a')],[])
        data=self.manifests('a','b');data[0]['requires']=['b'];data[1]['requires']=['a']
        with self.assertRaisesRegex(ValueError,'cycle'):ModuleRegistry(data,[Module('a'),Module('b')],[])
    def test_route_and_page_collisions_fail_at_startup(self):
        data=self.manifests('a','b');route={('POST','/api/test'):lambda *args:None}
        with self.assertRaisesRegex(ValueError,'Duplicate module route'):ModuleRegistry(data,[Module('a',route),Module('b',route)],[])
        for m in data:m['pages']=[{'id':'same'}]
        with self.assertRaisesRegex(ValueError,'Duplicate page'):ModuleRegistry(data,[Module('a'),Module('b')],[])
    def test_all_production_assets_exist_and_have_one_owner(self):
        root=Path(__file__).resolve().parents[1]
        for asset in registry.assets:
            self.assertTrue((root/'static'/asset['path'].lstrip('/')).is_file(),asset['path'])
            self.assertIn(asset['owner'],registry.modules)
        self.assertEqual(len(registry.routes),len(set(registry.routes)))
        self.assertEqual(len([p for m in registry.manifests.values() for p in m['pages']]),10)
    def test_domain_validation_cannot_be_bypassed_by_unknown_route(self):
        class Request:path='/api/missing'
        self.assertFalse(registry.dispatch('POST',Request(),None))
