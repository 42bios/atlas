import json
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import connector_engine
import plugin_api
import connector_setup

def import_post(self, app):
    origin = self.headers.get('Origin')
    if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
        return self.json_response(403, {'error': 'Origin rejected'})
    try:
        from .repository import fetch_catalog, merge_catalog
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 5000:
            raise ValueError('Provide a GitHub catalog URL.')
        request = json.loads(self.rfile.read(length))
        if not isinstance(request, dict):
            raise ValueError('Provide a JSON object with a GitHub catalog URL.')
        (source, records) = fetch_catalog(request.get('url', ''))
        with app.LOCK:
            state = app.read_state()
            state = merge_catalog(state, source, records)
            state['_revision'] = state.get('_revision', 0) + 1
            app.write_state(state)
        return self.json_response(200, {'imported': len(records), 'source': source})
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        return self.json_response(400, {'error': str(error)})
