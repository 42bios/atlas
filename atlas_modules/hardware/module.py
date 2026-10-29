"""hardware feature registration."""
from atlas_core.modules import Module
from .api import import_post

def inventory(handler, app):
    with app.LOCK:
        state = app.read_state()
        return handler.json_response(200, {key: state.get(key, []) for key in ['devices', 'racks']})

module = Module('hardware', {('POST', '/api/stencils/import-vssx'):import_post, ('GET', '/api/v1/hardware'):inventory})
