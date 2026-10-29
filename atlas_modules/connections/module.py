"""connections feature registration."""
from atlas_core.modules import Module

def inventory(handler, app):
    with app.LOCK:
        state = app.read_state()
        return handler.json_response(200, {key: state.get(key, []) for key in ['links']})

module = Module('connections', {('GET', '/api/v1/connections'):inventory})
