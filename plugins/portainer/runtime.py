import json
import hashlib
import hmac
import http.client
import os
import ssl
import time
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from collector import collect


def secret(name):
    try:
        return Path(os.environ.get(name, '/nonexistent')).read_text().strip()
    except OSError:
        return ''


def request(url, headers, body=None):
    fingerprint = os.environ.get('PORTAINER_TLS_SHA256', '').replace(':', '').lower()
    target = urlsplit(url)
    if fingerprint and target.scheme == 'https' and url.startswith(os.environ.get('PORTAINER_URL', '').rstrip('/')+'/'):
        if len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
            raise ValueError('Invalid certificate fingerprint')
        connection = http.client.HTTPSConnection(target.hostname, target.port or 443, timeout=30, context=ssl._create_unverified_context())
        try:
            connection.connect()
            actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if not hmac.compare_digest(actual, fingerprint):
                raise ValueError('Certificate fingerprint mismatch')
            connection.request('POST' if body is not None else 'GET', target.path+('?' + target.query if target.query else ''), body=json.dumps(body).encode() if body is not None else None, headers=headers)
            response = connection.getresponse()
            if response.status >= 300:
                raise ValueError('Upstream request rejected')
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError('Response exceeds snapshot limit')
            return json.loads(raw)
        finally:
            connection.close()
    context = ssl.create_default_context(cafile=os.environ.get('CA_FILE') or None)
    req = urllib.request.Request(url, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError('Response exceeds snapshot limit')
        return json.loads(raw)


def run():
    source = os.environ.get('CONNECTOR_ID', 'portainer-main')
    atlas = os.environ['ATLAS_URL'].rstrip('/')
    token = secret('ATLAS_TOKEN_FILE')
    upstream = os.environ.get('PORTAINER_URL', '').rstrip('/')
    upstream_token = secret('PORTAINER_TOKEN_FILE')
    headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
    while True:
        phase = 'waiting-configuration'
        try:
            if upstream and upstream_token and token:
                get = lambda path: request(upstream+path, {'X-API-Key': upstream_token})
                snapshot = collect(get, source)
                request(atlas+'/api/v1/connectors/snapshot', headers, snapshot)
                phase = 'imported'
            request(atlas+'/api/v1/connectors/status', headers, {'connector': source, 'phase': phase, 'plugin': 'portainer', 'version': '1.0.0'})
            print(phase, flush=True)
        except Exception as error:
            # Upstream bodies/URLs may contain sensitive details; only log the exception class.
            phase = 'error'
            print('Sync failed: '+type(error).__name__, flush=True)
            try:
                request(atlas+'/api/v1/connectors/status', headers, {'connector': source, 'phase': 'error', 'plugin': 'portainer', 'version': '1.0.0'})
            except Exception:
                pass
        if os.environ.get('RUN_ONCE', 'false').lower() == 'true':
            if phase != 'imported':
                raise SystemExit(1)
            return
        time.sleep(max(60, int(os.environ.get('SYNC_INTERVAL', '900'))))


if __name__ == '__main__':
    run()
