"""Versioned connector snapshots. Connector code runs outside the web process."""
import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DIRECTORY = Path(os.environ.get('ATLAS_CONNECTORS', str(Path(__file__).resolve().parents[2] / 'connectors')))
SCHEMA = {
    'schemaVersion': 1, 'connector': 'my-source',
    'description': 'IDs are local to the connector and automatically namespaced. Missing records are marked, never deleted.',
    'devices': [{'id': 'host', 'name': 'Example host', 'kind': 'Server', 'ip': '', 'ports': 2}],
    'services': [{'id': 'app', 'name': 'Example app', 'kind': 'Container', 'host': 'host', 'group': 'Applications', 'image': 'example:1', 'port': '8080'}],
    'networks': [], 'links': [],
}


def installed():
    result = []
    for path in sorted(DIRECTORY.glob('*.connector.json')):
        try:
            manifest = json.loads(path.read_text())
            snapshot = DIRECTORY / Path(manifest['snapshot']).name
            result.append({'id': manifest['id'], 'name': manifest['name'], 'description': manifest.get('description', ''),
                           'available': snapshot.is_file(), 'updated': datetime.fromtimestamp(snapshot.stat().st_mtime, timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if snapshot.is_file() else None,
                           '_snapshot': str(snapshot)})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def merge(state, snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('schemaVersion') != 1:
        raise ValueError('Connector snapshot must use schemaVersion 1.')
    source = snapshot.get('connector', '')
    if not isinstance(source, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', source):
        raise ValueError('Connector ID must use lowercase letters, numbers, hyphens or underscores.')
    result = copy.deepcopy(state)
    now = snapshot.get('collectedAt') or datetime.now(timezone.utc).isoformat()
    prefix = 'connector:' + source + ':'
    count = 0
    for collection in ('devices', 'services', 'networks', 'links'):
        incoming = snapshot.get(collection, [])
        if not isinstance(incoming, list):
            raise ValueError('Connector collections must be lists.')
        index = {item['id']: item for item in result[collection]}
        seen = set()
        for record in incoming:
            if not isinstance(record, dict) or not isinstance(record.get('id'), str) or not record['id']:
                raise ValueError('Connector records need a stable string ID.')
            identifier = prefix + record['id']
            if identifier in seen:
                raise ValueError('Duplicate connector record ID.')
            seen.add(identifier)
            old = index.get(identifier)
            clean = {key: value for key, value in record.items() if key not in ('id', 'origin', 'lastSeen', 'missing', '_overrides', 'rack', 'unit', 'height', 'frontImage', 'rearImage')}
            for ref in ('host', 'source', 'target'):
                if clean.get(ref):
                    clean[ref] = prefix + clean[ref]
            if old:
                for key, value in clean.items():
                    if key not in old.get('_overrides', []) and key not in ('notes',):
                        old[key] = value
                old.update(lastSeen=now, missing=False)
            else:
                defaults = {'rack': '', 'unit': 1, 'height': 1, 'ports': 0} if collection == 'devices' else {}
                result[collection].append({**defaults, **clean, 'id': identifier, 'origin': source, 'lastSeen': now, 'missing': False})
            count += 1
        for old in result[collection]:
            if old.get('origin') == source and old['id'] not in seen:
                old['missing'] = True
    return result, count
