"""Kubernetes inventory: ownership, scheduling and actual EndpointSlice targets.
Never reads Secrets, ConfigMaps, environment variables, logs or pod exec.
"""
from urllib.parse import urlencode

RESOURCES = {'Node':'/api/v1/nodes', 'Namespace':'/api/v1/namespaces', 'Pod':'/api/v1/pods', 'Service':'/api/v1/services', 'PersistentVolumeClaim':'/api/v1/persistentvolumeclaims', **{k:'/apis/apps/v1/'+v for k,v in {'Deployment':'deployments','StatefulSet':'statefulsets','DaemonSet':'daemonsets','ReplicaSet':'replicasets'}.items()}, 'Job':'/apis/batch/v1/jobs', 'CronJob':'/apis/batch/v1/cronjobs', 'Ingress':'/apis/networking.k8s.io/v1/ingresses', 'EndpointSlice':'/apis/discovery.k8s.io/v1/endpointslices'}

def collect(get, source, cluster_name='Kubernetes'):
    resources = {}
    for kind, path in RESOURCES.items():
        items, cursor, seen = [], '', set()
        while True:
            page = get(path+'?'+urlencode({'limit':500, **({'continue':cursor} if cursor else {})}))
            if not isinstance(page,dict) or not isinstance(page.get('items'),list):raise ValueError('Invalid Kubernetes resource page')
            items.extend(page['items'])
            if len(items) > 20000:
                raise ValueError('Resource inventory exceeds limit')
            cursor = page.get('metadata', {}).get('continue', '')
            if not cursor:
                break
            if cursor in seen:
                raise ValueError('Repeated Kubernetes pagination cursor')
            seen.add(cursor)
        resources[kind] = items
    services = [dict(id='cluster', name=cluster_name, kind='Kubernetes cluster', host='', role='Infrastructure', group=cluster_name)]
    index, namespaces, nodes, service_names = {}, {}, {}, {}
    for kind, items in resources.items():
        if kind == 'EndpointSlice':
            continue
        for item in items:
            m, spec = item['metadata'], item.get('spec', {})
            uid = m['uid']; index[uid] = uid
            ns = m.get('namespace', '')
            details = dict(cluster=cluster_name, namespace=ns, resourceKind=kind)
            if kind == 'Pod': details['node'] = spec.get('nodeName', '')
            if 'replicas' in spec: details['replicas'] = spec['replicas']
            if kind == 'Service': details['serviceType'] = spec.get('type', 'ClusterIP')
            rec = dict(id=uid, name=m['name'], kind='Kubernetes Service' if kind == 'Service' else kind, host='cluster', role='Infrastructure', group=ns or cluster_name, kubernetes=details)
            # Cluster/pod IPs can overlap other connectors: keep them as resource facts, not global IP assignments.
            if kind == 'Service': details['clusterIPs'] = spec.get('clusterIPs', [])
            if kind == 'Pod': details['podIPs'] = [p['ip'] for p in item.get('status', {}).get('podIPs', [])]
            services.append(rec)
            if kind == 'Namespace': namespaces[m['name']] = uid
            if kind == 'Node': nodes[m['name']] = uid
            if kind == 'Service': service_names[(ns,m['name'])] = uid
    records = {r['id']:r for r in services}
    links = [];link_ids=set()
    def link(a,b,kind):
        if a in records and b in records and a != b:
            lid=a+'-'+kind+'-'+b
            if lid not in link_ids:link_ids.add(lid);links.append(dict(id=lid, source=a, target=b, type=kind))
    for kind, items in resources.items():
        for item in items:
            m, spec = item['metadata'], item.get('spec', {})
            uid=m['uid']; ns=m.get('namespace', '')
            if kind != 'EndpointSlice':
                owners = [o['uid'] for o in m.get('ownerReferences', []) if o.get('controller') and o['uid'] in records]
                records[uid]['host'] = owners[0] if owners else namespaces.get(ns, 'cluster')
                records[uid]['kubernetes']['relationship'] = 'Owned by' if owners else 'In namespace' if ns else 'Part of'
            if kind == 'Pod':
                link(uid, nodes.get(spec.get('nodeName')), 'Scheduled on')
                for container in spec.get('containers', []) + spec.get('initContainers', []):
                    cid = uid+'-container-'+container['name']
                    services.append(dict(id=cid, name=container['name'], kind='Container', host=uid, role='Application', group=ns, containerRuntime='Kubernetes', image=container.get('image',''), kubernetes=dict(cluster=cluster_name, namespace=ns, resourceKind='Container',relationship='Runs in')))
                for vol in spec.get('volumes', []):
                    claim=vol.get('persistentVolumeClaim', {}).get('claimName')
                    target=next((p['metadata']['uid'] for p in resources['PersistentVolumeClaim'] if p['metadata'].get('namespace')==ns and p['metadata']['name']==claim),None)
                    link(uid,target,'Uses storage')
            if kind == 'EndpointSlice':
                svc=service_names.get((ns,m.get('labels', {}).get('kubernetes.io/service-name')))
                for endpoint in item.get('endpoints', []):
                    link(svc, endpoint.get('targetRef', {}).get('uid'), 'Routes to')
            if kind == 'Ingress':
                backends=[spec.get('defaultBackend', {})]+[p.get('backend', {}) for r in spec.get('rules', []) for p in r.get('http', {}).get('paths', [])]
                for backend in backends: link(uid,service_names.get((ns,backend.get('service', {}).get('name'))),'Routes to')
    return dict(schemaVersion=1,connector=source,devices=[],services=services,networks=[],links=links)
