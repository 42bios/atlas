"""Read-only Portainer collector. Never exports environment variables or credentials."""
import hashlib
from urllib.parse import quote


def role(image, labels):
    explicit = labels.get('atlas.role')
    allowed = ['Application', 'Reverse proxy', 'Database', 'Cache', 'Storage', 'Identity', 'Infrastructure', 'Other']
    if explicit in allowed:
        return explicit, 'Label'
    text = image.lower()
    for names, value in [(['traefik', 'caddy', 'nginx-proxy'], 'Reverse proxy'), (['postgres', 'mariadb', 'mysql', 'mongo'], 'Database'), (['redis', 'memcached', 'valkey'], 'Cache'), (['authentik', 'keycloak', 'authelia'], 'Identity')]:
        if any(n in text for n in names):
            return value, 'Image suggestion'
    return 'Application', 'Default'


def collect(get, source):
    endpoints = get('/api/endpoints')
    # Fetch all inventory before publishing: a failed environment must not mark records missing.
    stacks = get('/api/stacks')
    devices, services, links = [], [], []
    for endpoint in endpoints:
        if endpoint.get('Type') not in (1, 2, 4):
            continue  # Docker environments only; Kubernetes needs a separate adapter.
        eid = str(endpoint['Id'])
        host = 'environment-' + eid
        devices.append(dict(id=host, name=endpoint['Name'], kind='Server', model='Portainer Docker environment', ports=0, ip=''))
        containers = get('/api/endpoints/' + quote(eid, safe='') + '/docker/containers/json?all=1')
        images = get('/api/endpoints/' + quote(eid, safe='') + '/docker/images/json')
        image_names = {image['Id']: (image.get('RepoTags') or image.get('RepoDigests') or [image['Id']])[0] for image in images}
        stack_ids = {}
        for stack in stacks:
            if str(stack.get('EndpointId')) == eid:
                sid = host + '-stack-' + str(stack['Id'])
                stack_ids[stack['Name']] = sid
                services.append(dict(id=sid, name=stack['Name'], kind='Stack', host=host, role='Application', group=stack['Name']))
        container_ids = {}
        for item in containers:
            labels = item.get('Labels') or {}
            cid = host + '-container-' + item['Id']
            project = labels.get('com.docker.compose.project')
            if project and project not in stack_ids:
                sid = host + '-compose-' + hashlib.sha256(project.encode()).hexdigest()[:12]
                stack_ids[project] = sid
                services.append(dict(id=sid, name=project, kind='Stack', host=host, role='Application', group=project))
            container_ids[(project, labels.get('com.docker.compose.service'))] = cid
            name = (item.get('Names') or [item['Id'][:12]])[0].lstrip('/')
            image = image_names.get(item.get('Image', ''), item.get('Image', ''))
            r, origin = role(image, labels)
            ports = sorted({str(p['PublicPort'])+' → '+str(p['PrivatePort'])+'/'+p.get('Type', 'tcp') for p in item.get('Ports', []) if p.get('PublicPort')})
            services.append(dict(id=cid, name=name, kind='Container', containerRuntime='Docker', host=stack_ids.get(project, host), role=r, roleSource=origin, group=project or 'Docker containers', image=image, port=', '.join(ports)))
        for item in containers:
            labels = item.get('Labels') or {}
            for dependency in labels.get('com.docker.compose.depends_on', '').split(','):
                target = container_ids.get((labels.get('com.docker.compose.project'), dependency.split(':')[0]))
                cid = host + '-container-' + item['Id']
                if target and target != cid:
                    links.append(dict(id=cid+'-after-'+target, source=cid, target=target, type='Starts after', sourcePort='', targetPort=''))
    return dict(schemaVersion=1, connector=source, devices=devices, services=services, networks=[], links=links)
