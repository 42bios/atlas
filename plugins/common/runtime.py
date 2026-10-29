"""Read-only plugin transport. Secrets stay in mounted files; TLS is always verified."""
import json
import os
import ssl
import time
import urllib.request
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirects are not permitted for authenticated requests')

def secret(name):
    return Path(os.environ[name]).read_text().strip()

def request(url, headers, body=None, ca=None):
    req = urllib.request.Request(url, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca)))
    with opener.open(req, timeout=30) as response:
        raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError('Response exceeds inventory limit')
        return json.loads(raw)

def run(plugin, collect):
    source = os.environ['CONNECTOR_ID']
    atlas = os.environ['ATLAS_URL'].rstrip('/')
    while True:
        headers = None
        try:
            headers = {'Authorization': 'Bearer '+secret('ATLAS_TOKEN_FILE'), 'Content-Type': 'application/json'}
            snapshot = collect(source)
            request(atlas+'/api/v1/connectors/snapshot', headers, snapshot)
            request(atlas+'/api/v1/connectors/status', headers, {'connector': source, 'plugin': plugin, 'version': '1.0.0', 'phase': 'imported'})
            print('Snapshot imported', flush=True)
        except Exception as error:
            print('Import failed: '+type(error).__name__, flush=True)
            if headers:
                try:
                    request(atlas+'/api/v1/connectors/status', headers, {'connector': source, 'plugin': plugin, 'version': '1.0.0', 'phase': 'error'})
                except Exception:
                    pass
            if os.environ.get('RUN_ONCE', 'true').lower() == 'true':
                raise SystemExit(1)
        if os.environ.get('RUN_ONCE', 'true').lower() == 'true':
            return
        time.sleep(max(300, int(os.environ.get('SYNC_INTERVAL', '3600'))))
