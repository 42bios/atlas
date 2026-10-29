import json
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import connector_engine
import plugin_api
import connector_setup

def do_PUT(self, app):
    if self.path != '/api/state':
        return self.json_response(404, {'error': 'Not found'})
    origin = self.headers.get('Origin')
    if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
        return self.json_response(403, {'error': 'Origin rejected'})
    try:
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0 or length > 32000000:
            raise ValueError('Inventory must be smaller than 32 MB.')
        state = app.validate(json.loads(self.rfile.read(length)))
        with app.LOCK:
            previous = app.read_state()
            if state.get('_revision', 0) != previous.get('_revision', 0):
                return self.json_response(409, {'error': 'Inventory changed in another session. Reload before saving.'})
            state['_revision'] = previous.get('_revision', 0) + 1
            app.write_state(state)
        self.json_response(200, {'saved': True, 'revision': state['_revision']})
    except (ValueError, TypeError, KeyError) as error:
        self.json_response(400, {'error': str(error)})

def get_state(self, app):
    with app.LOCK: return self.json_response(200, app.read_state())

def get_inventory(self, app):
    with app.LOCK:
        state=app.read_state()
        return self.json_response(200,{key:state[key] for key in ('devices','services','networks','links')})
