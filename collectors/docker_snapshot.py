#!/usr/bin/env python3
"""Read Docker inventory without collecting environment variables or secrets."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
from datetime import datetime, timezone


def run(*args):
    return subprocess.check_output(args, text=True, timeout=60)


def collect():
    ids = run('docker', 'ps', '-aq').split()
    fmt = '{"name":{{json .Name}},"image":{{json .Config.Image}},"ports":{{json .NetworkSettings.Ports}},"networks":{{json .HostConfig.NetworkMode}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"depends":{{json (index .Config.Labels "com.docker.compose.depends_on")}}}'
    records = [json.loads(line) for line in run('docker', 'inspect', '--format', fmt, *ids).splitlines()] if ids else []
    services = []
    names = {(r['project'], r['service']): r['name'].lstrip('/') for r in records if r.get('service')}
    links = []
    for record in records:
        name = record['name'].lstrip('/')
        ports = []
        for container_port, bindings in (record.get('ports') or {}).items():
            for binding in bindings or []:
                ports.append(binding['HostPort'] + ' → ' + container_port)
        services.append({'id': name, 'name': name, 'kind': 'Container', 'host': 'host', 'image': record['image'], 'port': ', '.join(sorted(set(ports))), 'group': record.get('project') or 'Docker containers', 'dockerNetwork': record.get('networks') or '', 'ip': ''})
        for dependency in (record.get('depends') or '').split(','):
            target = names.get((record.get('project'), dependency.split(':')[0]))
            if target and target != name:
                links.append({'id': name + '-starts-after-' + target, 'source': name, 'target': target, 'type': 'Starts after', 'sourcePort': '', 'targetPort': ''})
    return {'schemaVersion': 1, 'connector': 'docker-host', 'collectedAt': datetime.now(timezone.utc).isoformat(),
            'devices': [{'id': 'host', 'name': socket.gethostname(), 'kind': 'Server', 'model': 'Docker host', 'ip': '', 'ports': 0}], 'services': services, 'links': links, 'networks': []}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = collect()
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(content, indent=2))
    os.replace(temporary, output)
    print(f'Collected {len(content["services"])} containers and {len(content["links"])} declared startup dependencies.')
