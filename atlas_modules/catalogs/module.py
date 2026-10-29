"""catalogs feature registration."""
from atlas_core.modules import Module
from .api import import_post

def inventory(handler, app):
    with app.LOCK:
        state = app.read_state()
        return handler.json_response(200, {key: state.get(key, []) for key in ['deviceCatalog', 'catalogSources']})

module = Module('catalogs', {('POST', '/api/catalog/import'):import_post, ('GET', '/api/v1/catalogs'):inventory})
