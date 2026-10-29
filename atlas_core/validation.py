"""Shared record envelope; modules own domain validation."""

def validate_envelope(state):
    if not isinstance(state, dict):
        raise ValueError('Inventory must be a JSON object.')
    collections = ['racks', 'devices', 'networks', 'addresses', 'services', 'links', 'stencils']
    for key in collections:
        if not isinstance(state.get(key), list):
            raise ValueError('Missing inventory collection: ' + key)
    ids = set()
    for key in collections:
        for item in state[key]:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'] or item['id'] in ids:
                raise ValueError('Every record must have a unique ID.')
            ids.add(item['id'])
            if key != 'links' and not str(item.get('name', '')).strip():
                raise ValueError('Every record needs a name.')
            if key == 'stencils' and item.get('image') and len(item['image']) > 1_400_000:
                raise ValueError('Stencil previews must be smaller than 1 MB.')
