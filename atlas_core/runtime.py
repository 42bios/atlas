"""Explicit services passed to modules; no feature imports the HTTP host."""
import json
import threading
from pathlib import Path
from .storage import InventoryStore

class Application:
    def __init__(self, database, registry, manager_factory, connector_engine):
        self.database = database
        self.registry = registry
        self.manager_factory = manager_factory
        self.connector_engine = connector_engine
        self.LOCK = threading.RLock()
        self.managers = {}
    def features(self):
        from .features import FeatureState
        return FeatureState(self.database(), self.registry)
    def connection(self): return InventoryStore(self.database()).connection()
    def read_state(self): return InventoryStore(self.database()).read()
    def validate(self, state): return self.registry.validate(state)
    def write_state(self, state):
        self.validate(state)
        InventoryStore(self.database()).write(state)
    def addins(self):
        with self.LOCK:
            key = str(self.database())
            if key not in self.managers:
                self.managers[key] = self.manager_factory(Path(key).parent/'addins')
            return self.managers[key]
    def sync_snapshots(self):
        with self.LOCK:
            state = self.read_state()
            if state.get('demo'):
                raise ValueError('Start a fresh workspace before importing live inventory. Your sample layout will be removed only when you choose Start fresh.')
            count = 0
            for connector in self.connector_engine.installed():
                if connector['available']:
                    state, imported = self.connector_engine.merge(state, json.loads(Path(connector['_snapshot']).read_text()))
                    count += imported
            state['_revision'] = state.get('_revision', 0) + 1
            self.write_state(state)
            return count
