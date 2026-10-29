import json
import tempfile
from pathlib import Path
import unittest
from atlas_core.features import FeatureState
from atlas_core.storage import InventoryStore
from atlas_modules.registry import registry

class BuiltinAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'atlas.db'
        self.features=FeatureState(self.path,registry)
    def test_all_builtin_features_always_available(self):
        self.assertTrue(all(m['enabled'] and m['required'] for m in self.features.public()['modules']))
        self.assertFalse(self.path.exists())
    def test_legacy_disabled_settings_are_ignored_without_data_changes(self):
        store=InventoryStore(self.path);before=store.read()
        with store.connection() as con:
            con.execute('CREATE TABLE feature_state (id INTEGER PRIMARY KEY, revision INTEGER, disabled TEXT)')
            con.execute('INSERT INTO feature_state VALUES (1, 5, ?)',(json.dumps(['hardware','ipam','applications']),))
        self.assertTrue(all(m['enabled'] for m in self.features.public()['modules']))
        self.assertEqual(store.read(),before)
        with store.connection() as con:
            self.assertEqual(con.execute('SELECT revision FROM feature_state').fetchone()[0],5)
    def test_inventory_validation_remains_active(self):
        invalid=InventoryStore(self.path).read();invalid['networks'][0]['cidr']='invalid'
        with self.assertRaises(ValueError):registry.validate(invalid)
