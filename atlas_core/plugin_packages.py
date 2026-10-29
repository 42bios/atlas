"""Discover installed trusted feature packages; route code loads on first use."""
import importlib
import json
import re
import threading
from pathlib import Path
from .modules import Module

class PluginPackage:
    def __init__(self, manifest):
        self.manifest=manifest
        self.loaded=None
        self.lock=threading.RLock()
    def invoke(self, key, handler, app):
        with self.lock:
            if self.loaded is None:
                module=importlib.import_module('atlas_modules.'+self.manifest['id']+'.module').module
                expected={tuple(r) for r in self.manifest['backendRoutes']}
                if module.id!=self.manifest['id'] or set(module.routes)!=expected:
                    raise ValueError('Plugin implementation does not match its declared routes: '+self.manifest['id'])
                self.loaded=module
        return self.loaded.routes[key](handler,app)
    def registration(self):
        routes={}
        for method,path in self.manifest['backendRoutes']:
            key=(method,path)
            routes[key]=lambda handler,app,key=key:self.invoke(key,handler,app)
        return Module(self.manifest['id'],routes)

def discover(directory):
    manifests=[];assets=[];modules=[]
    for path in sorted(Path(directory).glob('*/plugin.json')):
        manifest=json.loads(path.read_text())
        id=manifest.get('id')
        if not isinstance(id,str) or not re.fullmatch(r'[a-z][a-z0-9_-]*',id) or id!=path.parent.name:
            raise ValueError('Plugin ID must match its package directory.')
        if manifest.get('pluginApi')!=1:raise ValueError('Unsupported feature plugin API: '+id)
        if not (path.parent/'module.py').is_file():raise ValueError('Plugin implementation is missing: '+id)
        manifests.append(manifest)
        for asset in manifest['assets']:
            if asset.get('owner')!=id:raise ValueError('Plugin asset owner mismatch: '+id)
            assets.append(asset)
        if id=='core':modules.append(importlib.import_module('atlas_modules.core.module').module)
        else:modules.append(PluginPackage(manifest).registration())
    return manifests,modules,assets
