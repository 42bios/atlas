import json
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from . import engine as connector_engine
from . import contract as plugin_api
from . import setup as connector_setup

def addin_post(self, app):
    origin = self.headers.get('Origin')
    if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
        return self.json_response(403, {'error': 'Origin rejected'})
    try:
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 60000:
            raise ValueError('Add-in configuration must be smaller than 60 KB.')
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError('Provide an add-in configuration object.')
        if self.path.endswith('/migration/rollback'):
            return self.json_response(200,app.addins().rollback_migration(payload.get('migration')))
        if self.path.endswith('/repository/access'):
            return self.json_response(200,app.addins().configure_github_access(payload))
        if self.path.endswith('/repository/preview'):
            return self.json_response(200, app.addins().preview_repository(payload.get('url'), payload.get('ref','')))
        if self.path.endswith('/repository/install'):
            plugin=app.addins().install_repository(payload.get('review'),payload.get('trust'))
            return self.json_response(200, {'installed':True, 'plugin':plugin})
        if self.path.endswith('/configure'):
            with app.connection() as con:
                con.execute('CREATE TABLE IF NOT EXISTS plugin_status (id TEXT PRIMARY KEY, body TEXT)')
                sources = [json.loads(row[0]) for row in con.execute('SELECT body FROM plugin_status')]
            instance = app.addins().configure(payload, sources)
            return self.json_response(200, {'saved': True, 'instance': instance})
        app.addins().action(payload.get('action'), payload.get('id'), payload.get('plugin'))
        return self.json_response(200, {'updated': True})
    except (OSError, ValueError, TypeError, KeyError) as error:
        return self.json_response(400, {'error': str(error)})

def connector_setup_post(self, app):
    origin = self.headers.get('Origin')
    if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
        return self.json_response(403, {'error': 'Origin rejected'})
    try:
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 5000:
            raise ValueError('Connector setup must be smaller than 5 KB.')
        payload = json.loads(self.rfile.read(length))
        if self.path.endswith('/preview'):
            return self.json_response(200, connector_setup.prepare(payload))
        return self.connector_package_response(payload)
    except (OSError, ValueError, TypeError, KeyError) as error:
        self.json_response(400, {'error': str(error)})

def connector_post(self, app):
    try:
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 8000000:
            raise ValueError('Snapshot must be smaller than 8 MB.')
        payload = json.loads(self.rfile.read(length))
        source = payload.get('connector') if isinstance(payload, dict) else None
        if not (plugin_api.authorized(self.headers, source) or app.addins().authorized(self.headers, source)):
            return self.json_response(403, {'error': 'Connector credentials rejected.'})
        if self.path.endswith('/status'):
            phase = payload.get('phase')
            if phase not in ('waiting-configuration', 'imported', 'error'):
                raise ValueError('Invalid connector phase.')
            status = dict(connector=source, phase=phase, plugin=str(payload.get('plugin', 'community'))[:100], version=str(payload.get('version', ''))[:40], updated=time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()))
            with app.LOCK, app.connection() as con:
                con.execute('CREATE TABLE IF NOT EXISTS plugin_status (id TEXT PRIMARY KEY, body TEXT)')
                con.execute('INSERT OR REPLACE INTO plugin_status VALUES (?, ?)', (source, json.dumps(status)))
            return self.json_response(200, {'saved': True})
        with app.LOCK:
            previous = app.read_state()
            if previous.get('demo'):
                return self.json_response(409, {'error': 'Live imports require an empty workspace or an explicitly restored non-demo inventory.'})
            (state, count) = connector_engine.merge(previous, app.addins().filter_worker_records(payload))
            state['_revision'] = previous.get('_revision', 0) + 1
            app.write_state(state)
        return self.json_response(200, {'imported': count})
    except (OSError, ValueError, TypeError, KeyError) as error:
        return self.json_response(400, {'error': str(error)})

def snapshot_post(self, app):
    origin = self.headers.get('Origin')
    if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
        return self.json_response(403, {'error': 'Origin rejected'})
    try:
        with app.LOCK:
            if self.path == '/api/sync':
                count = app.sync_snapshots()
            else:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 8000000:
                    raise ValueError('Snapshot must be smaller than 8 MB.')
                previous = app.read_state()
                if previous.get('demo'):
                    raise ValueError('Start a fresh workspace before importing live inventory.')
                (state, count) = connector_engine.merge(previous, json.loads(self.rfile.read(length)))
                state['_revision'] = previous.get('_revision', 0) + 1
                app.write_state(state)
        return self.json_response(200, {'message': f'Imported {count} inventory records.'})
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        return self.json_response(400, {'error': str(error)})
