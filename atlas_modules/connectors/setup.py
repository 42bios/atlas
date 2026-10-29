"""Prepare bundled connector installations; never run plugins or collect credentials."""
import io
import ipaddress
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = [
    dict(id='portainer', name='Portainer', summary='Docker environments, stacks, containers and startup ordering.', cadence='Periodic inventory snapshots', available=True),
    dict(id='snmp', name='SNMP discovery', summary='Discover equipment, interface speeds, VLAN facts and neighbor observations.', cadence='One discovery run per launch', available=True),
    dict(id='kubernetes', name='Kubernetes', summary='Clusters, namespaces, workloads, service endpoints and storage claims.', cadence='One inventory run per launch', available=True),
    dict(id='unifi', name='UniFi', summary='Controller devices, networks and wireless associations.', cadence='Adapter not yet available', available=False),
]


def url(value, label, https=False):
    if not isinstance(value, str) or len(value) > 500 or any(c.isspace() for c in value) or any(c in value for c in '$`\\\"\''):
        raise ValueError(label+' must be a plain URL without shell expressions.')
    parsed = urlsplit(value)
    if parsed.scheme not in (['https'] if https else ['http', 'https']) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(label+' must be an '+('HTTPS' if https else 'HTTP or HTTPS')+' URL without credentials, query or fragment.')
    try:
        parsed.port
    except ValueError:
        raise ValueError(label+' has an invalid port.') from None
    return value.rstrip('/')


def prepare(payload):
    if not isinstance(payload, dict):
        raise ValueError('Provide a connector setup object.')
    allowed = {'plugin', 'connector', 'atlasUrl', 'upstreamUrl', 'targets', 'snmpVersion', 'clusterName', 'tlsFingerprint'}
    if set(payload)-allowed:
        raise ValueError('Setup accepts configuration only. Put credentials in secret files on the Docker host.')
    plugin = payload.get('plugin')
    if plugin not in ('portainer', 'snmp', 'kubernetes'):
        raise ValueError('Choose an available bundled connector.')
    source = payload.get('connector', '')
    if not isinstance(source, str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,63}', source):
        raise ValueError('Connector ID must use 3–64 lowercase letters, digits or hyphens and start with a letter.')
    atlas = url(payload.get('atlasUrl', ''), 'Atlas URL')
    env = {'ATLAS_URL': atlas, 'CONNECTOR_ID': source}
    files = {}
    requirements = ['Dedicated Atlas token: secrets/atlas_token', 'Atlas host keys file must authorize this connector ID']
    if plugin == 'portainer':
        env['PORTAINER_URL'] = url(payload.get('upstreamUrl', ''), 'Portainer URL', https=True)
        fingerprint = payload.get('tlsFingerprint', '')
        if not isinstance(fingerprint, str) or fingerprint and not re.fullmatch(r'[a-fA-F0-9]{64}', fingerprint):
            raise ValueError('Certificate fingerprint must be 64 hexadecimal characters.')
        env.update(PORTAINER_TLS_SHA256=fingerprint.lower(), SYNC_INTERVAL='900')
        requirements.append('Portainer API access token: secrets/portainer_token')
    elif plugin == 'kubernetes':
        env['KUBERNETES_URL'] = url(payload.get('upstreamUrl', ''), 'Kubernetes API URL', https=True)
        cluster = payload.get('clusterName', 'Kubernetes')
        if not isinstance(cluster, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}', cluster):
            raise ValueError('Cluster name must be 1–80 letters, digits, spaces, dots, underscores or hyphens.')
        env.update(CLUSTER_NAME=cluster, RUN_ONCE='true')
        requirements += ['Read-only service-account token: secrets/kubernetes_token', 'Cluster CA certificate: secrets/cluster_ca', 'Review and apply the included read-only RBAC manifest']
    else:
        values = payload.get('targets', [])
        if not isinstance(values, list) or not 1 <= len(values) <= 16:
            raise ValueError('Provide 1–16 explicit IPv4 hosts or networks for discovery.')
        targets, addresses = [], set()
        for value in values:
            if not isinstance(value, str):
                raise ValueError('Discovery targets must be IPv4 hosts or prefixes.')
            network = ipaddress.ip_network(value, strict=False)
            if network.version != 4 or network.num_addresses > 1024:
                raise ValueError('Each discovery target must be IPv4 and contain at most 1024 addresses.')
            targets.append(str(network))
            addresses.update(str(a) for a in (network.hosts() if network.prefixlen < 31 else network))
            if len(addresses) > 1024:
                raise ValueError('The combined discovery scope must not exceed 1024 addresses.')
        version = payload.get('snmpVersion', '2c')
        if version not in ('2c', '3'):
            raise ValueError('Choose SNMP v2c or v3.')
        files['secrets/discovery_config'] = json.dumps({'targets': list(dict.fromkeys(targets)), 'version': version}, indent=2)+'\n'
        env['RUN_ONCE'] = 'true'
        requirements.append('SNMP community: secrets/snmp_community' if version == '2c' else 'SNMPv3 credential JSON: secrets/snmp_credentials')
    env_text = '\n'.join(k+'='+v for k, v in env.items())+'\n'
    project = 'atlas-'+source
    commands = [f'cd plugins/{plugin}', f'docker compose -p {project} config --quiet', f'docker compose -p {project} up -d --build', f'docker compose -p {project} logs --tail=30']
    return dict(plugin=plugin, connector=source, project=project, environment=env_text, requirements=requirements, commands=commands, files=files)


def package(payload):
    setup = prepare(payload)
    plugin = setup['plugin']
    prefix = 'plugins/'+plugin+'/'
    readme = f'''# {plugin} connector setup: {setup['connector']}

This package contains bundled Atlas connector source and configuration only.
Downloading it does not install a plugin, authorize a source or test a connection.
Extract it into a new directory on your Docker host, separate from an existing installation.

1. Review {prefix}.env and compose.yaml. Atlas must be reachable from the connector container.
2. Authorize this source in the Atlas host keys file. Run the helper below as the host user with UID 1000; it preserves other source keys and reuses an existing key for this ID. It never prints tokens:

   python3 provision_token.py --keys /absolute/path/to/atlas/secrets/connector-keys.json --connector {setup['connector']} --output {prefix}secrets/atlas_token

   Atlas needs ATLAS_CONNECTOR_KEYS_FILE=/run/secrets/connector-keys.json and a read-only mount of this host file. Use the override example below if not configured. Recreate the Atlas container after changing its key file or mount; retain all existing overrides and environment settings.
3. Provide the upstream secret files listed below. Create files on the host, not in the browser. They must be readable by container UID 1000; use mode 600 and do not commit them. For SNMPv3, credential JSON keys are SecurityName, SecurityLevel, AuthType, AuthPassphrase, PrivType and PrivPassphrase, matching your agent configuration. For Kubernetes, review rbac.yaml before applying it and obtain a service-account token and cluster CA. For Portainer, use an API token rather than an account password. A self-signed Portainer certificate requires a SHA-256 fingerprint verified through a trusted channel.
4. Validate Compose, then start the connector using the commands below. Starting it performs a real collection within the configured scope. SNMP and Kubernetes run once; Portainer refreshes every 15 minutes.
5. In Atlas, open Sources & settings and Refresh status. Check this exact connector ID, a report newer than launch, and 'Last snapshot imported'. Open its imported inventory. A downloaded package or Compose start alone does not prove upstream connectivity.

Required files/configuration:
'''+''.join('- '+r+'\n' for r in setup['requirements'])+'''
Atlas host override example (merge into existing configuration):

```yaml
services:
  atlas:
    environment:
      ATLAS_CONNECTOR_KEYS_FILE: /run/secrets/connector-keys.json
    volumes:
      - ./secrets/connector-keys.json:/run/secrets/connector-keys.json:ro
```

Commands, after preparing secret files:

```sh
'''+ '\n'.join(setup['commands'])+f'''
```

Stop/remove the connector container with `docker compose -p {setup['project']} down` from its directory. Imported records remain documented in Atlas. Do not remove a source token while its connector is still running. Atlas does not install or run arbitrary community plugin code.
'''
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('Dockerfile', 'compose.yaml', 'collector.py', 'runtime.py'):
            z.writestr(prefix+name, (ROOT/prefix/name).read_bytes())
        if plugin in ('snmp', 'kubernetes'):
            z.writestr('plugins/common/runtime.py', (ROOT/'plugins/common/runtime.py').read_bytes())
        if plugin == 'kubernetes':
            z.writestr(prefix+'rbac.yaml', (ROOT/prefix/'rbac.yaml').read_bytes())
        z.writestr(prefix+'.env', setup['environment'])
        for name, content in setup['files'].items():
            z.writestr(prefix+name, content)
        z.writestr(prefix+'secrets/README.txt', 'Put secret files here. Never commit or share this directory. See the package README.\n')
        z.writestr('.gitignore', '**/secrets/*\n**/.env\n')
        z.writestr('README.md', readme)
        z.writestr('provision_token.py', (ROOT/'plugins/common/provision_token.py').read_bytes())
    return setup['connector']+'.zip', data.getvalue()
