"""Module contracts and dependency-aware composition; no module imports the HTTP host."""
from dataclasses import dataclass, field
from typing import Callable

@dataclass(frozen=True)
class Module:
    id: str
    routes: dict = field(default_factory=dict)
    validators: tuple = ()

class ModuleRegistry:
    def __init__(self, manifests, modules, assets):
        self.manifests = {m['id']: dict(m) for m in manifests}
        self.modules = {m.id: m for m in modules}
        if len(self.manifests) != len(manifests) or len(self.modules) != len(modules):
            raise ValueError('Duplicate module ID.')
        if self.manifests.keys() != self.modules.keys():
            raise ValueError('Module manifests and implementations must match.')
        self.order = self._resolve()
        self.routes = {}
        self.route_owners = {}
        pages = set()
        for id in self.order:
            for page in self.manifests[id]['pages']:
                if page['id'] in pages: raise ValueError('Duplicate page ID: '+page['id'])
                pages.add(page['id'])
            for key, handler in self.modules[id].routes.items():
                if key in self.routes: raise ValueError('Duplicate module route: '+str(key))
                self.routes[key] = handler
                self.route_owners[key] = id
        self.assets = sorted(assets, key=lambda a:a['order'])
        if len({a['path'] for a in assets}) != len(assets): raise ValueError('Duplicate frontend asset.')
        for asset in assets:
            if asset['owner'] not in self.modules: raise ValueError('Unknown asset owner.')
    def _resolve(self):
        result, visiting = [], set()
        def visit(id):
            if id not in self.manifests: raise ValueError('Missing module dependency: '+id)
            if id in visiting: raise ValueError('Module dependency cycle: '+id)
            if id in result: return
            visiting.add(id)
            for dependency in self.manifests[id]['requires']: visit(dependency)
            visiting.remove(id); result.append(id)
        for id in self.manifests: visit(id)
        return result
    def public(self):
        return {'schemaVersion':1,'modules':[self.manifests[id] for id in self.order], 'assets':self.assets}
    def dispatch(self, method, handler, application):
        from urllib.parse import urlsplit
        path = urlsplit(handler.path).path
        route = self.routes.get((method, path))
        if route is None: return False
        if application is not None:
            owner = self.route_owners[(method, path)]
            enabled = {m["id"]:m["enabled"] for m in application.features().public()["modules"]}
            if not enabled[owner]:
                handler.json_response(409, {"error":"Module is disabled. Enable it in Sources & settings.", "module":owner})
                return True
        route(handler, application)
        return True
    def validate(self, state):
        from .validation import validate_envelope
        validate_envelope(state)
        for id in self.order:
            for validator in self.modules[id].validators: validator(state)
        return state
