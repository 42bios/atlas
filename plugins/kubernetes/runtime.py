import os
from urllib.parse import urlsplit
from common.runtime import run, request, secret
from collector import collect

def snapshot(source):
    url=os.environ['KUBERNETES_URL'].rstrip('/')
    if urlsplit(url).scheme != 'https': raise ValueError('Kubernetes requires HTTPS')
    headers={'Authorization':'Bearer '+secret('KUBERNETES_TOKEN_FILE')}
    return collect(lambda path:request(url+path,headers,ca=os.environ.get('CA_FILE')),source,os.environ.get('CLUSTER_NAME','Kubernetes'))

if __name__=='__main__': run('kubernetes',snapshot)
