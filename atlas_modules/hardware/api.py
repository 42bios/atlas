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
        from .visio import import_library
        from urllib.parse import unquote
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 20000000:
            raise ValueError('VSSX libraries must be smaller than 20 MB.')
        filename = unquote(self.headers.get('X-Filename', 'Visio library.vssx'))[:200]
        (records, skipped) = import_library(self.rfile.read(length), filename)
        with app.LOCK:
            state = app.read_state()
            existing = {s['id'] for s in state['stencils']}
            added = [s for s in records if s['id'] not in existing]
            state['stencils'].extend(added)
            state['_revision'] = state.get('_revision', 0) + 1
            app.write_state(state)
        return self.json_response(200, {'imported': len(added), 'duplicates': len(records) - len(added), 'skipped': skipped, 'thumbnails': sum((r['previewQuality'] == 'Visio thumbnail' for r in records))})
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        return self.json_response(400, {'error': str(error)})
