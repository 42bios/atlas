"""Connector contract: external processes push source-scoped inventory snapshots."""
import hmac
import json
import os
from pathlib import Path

ROLES = ['Application', 'Reverse proxy', 'Database', 'Cache', 'Storage', 'Identity', 'Infrastructure', 'Other']
CONTRACT = {'version': 1, 'snapshotEndpoint': '/api/v1/connectors/snapshot', 'statusEndpoint': '/api/v1/connectors/status', 'authentication': 'Bearer token scoped to connector ID', 'runtimeTypes': ['Virtual machine', 'Container', 'LXC', 'Stack', 'Service', 'External service', 'Kubernetes cluster', 'Namespace', 'Node', 'Deployment', 'StatefulSet', 'DaemonSet', 'ReplicaSet', 'Job', 'CronJob', 'Pod', 'Kubernetes Service', 'Ingress', 'PersistentVolumeClaim'], 'roles': ROLES, 'installation': 'Separate container or process; no plugin code executes in Atlas.', 'snapshot': {'schemaVersion': 1, 'connector': 'portainer-main', 'devices': [], 'services': [], 'networks': [], 'links': []}}


def authorized(headers, source):
    file = os.environ.get('ATLAS_CONNECTOR_KEYS_FILE')
    if not file or not isinstance(source, str):
        return False
    try:
        expected = json.loads(Path(file).read_text()).get(source)
    except (OSError, ValueError):
        return False
    header = headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return False
    token = header.removeprefix('Bearer ')
    return isinstance(expected, str) and len(expected) >= 32 and hmac.compare_digest(token, expected)
