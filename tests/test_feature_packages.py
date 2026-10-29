import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from atlas_core.frontend import active_assets, plugin_script
from atlas_core.plugin_packages import discover, PluginPackage
from atlas_modules.registry import registry

class FeaturePackageTests(unittest.TestCase):
    def test_optional_backend_not_imported_at_startup(self):
        code='import atlas_modules.registry,sys; assert not any("atlas_modules."+id+".module" in sys.modules for id in ["hardware","ipam","applications","connections","topology","catalogs"])'
        subprocess.run([sys.executable,'-c',code],check=True)
    def test_missing_optional_packages_do_not_break_core(self):
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            for id in ['core','overview','settings','connectors']:
                shutil.copytree(Path('atlas_modules')/id,Path(folder)/id)
            manifests,modules,assets=discover(folder)
            from atlas_core.modules import ModuleRegistry
            subset=ModuleRegistry(manifests,modules,assets)
            self.assertEqual(set(subset.modules),{'core','overview','settings','connectors'})
            from atlas_core.sample import demo
            subset.validate(demo())
    def test_only_active_assets_are_served(self):
        manifest=registry.public()
        manifest['modules']=[dict(m,enabled=m['id'] in ['core','overview','settings','connectors']) for m in manifest['modules']]
        self.assertTrue(all(a['owner'] in ['core','overview','settings','connectors'] for a in active_assets(manifest)))
    def test_every_file_declares_private_binding_interface(self):
        root=Path('static')
        for m in registry.manifests.values():
            self.assertEqual(m['pluginApi'],1)
            for a in m['assets']:
                self.assertEqual(a['owner'],m['id'])
                self.assertIn(a['path'],m['bindings'])
                wrapped=plugin_script((root/a['path'].lstrip('/')).read_text(),m['id'],m['bindings'][a['path']])
                self.assertTrue(wrapped.startswith('AtlasPluginHost.load('))
    def test_lazy_route_implementation_must_match_manifest(self):
        manifest=dict(registry.manifests['ipam'],backendRoutes=[])
        package=PluginPackage(manifest)
        with self.assertRaisesRegex(ValueError,'declared routes'):package.invoke(('GET','/api/v1/ipam'),None,None)
