"""Built-in application features are always available; legacy toggles are ignored."""

class FeatureState:
    def __init__(self, database, registry):
        self.registry = registry
    def public(self):
        result = self.registry.public()
        result['revision'] = 0
        result['modules'] = [dict(m, enabled=True, required=True) for m in result['modules']]
        return result
