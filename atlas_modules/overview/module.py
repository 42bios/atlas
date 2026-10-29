"""overview feature registration."""
from atlas_core.modules import Module


def overview(handler, app):
    with app.LOCK:
        state = app.read_state()
        return handler.json_response(200, {key: len(state[key]) for key in ("devices", "racks", "services", "networks", "addresses", "links")})

module = Module('overview', {('GET', '/api/v1/overview'):overview})
