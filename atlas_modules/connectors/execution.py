"""Private filesystem queue for an external, container-only connector runner."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid


def atomic_json(path, data):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w') as stream:json.dump(data,stream)
    temporary.chmod(0o600);os.replace(temporary,path)


def runner_status(root=None):
    root=Path(root or os.environ.get('ATLAS_WORKER_QUEUE','/worker-jobs'))
    try:
        data=json.loads((root/'runner.json').read_text())
        ready=data.get('ready') is True and 0<=time.time()-data['updated']<20
        return {'mode':'isolated-containers','available':ready,'message':'Isolated runner ready' if ready else 'Isolated runner unavailable; imports are blocked', 'workerSubnets':data.get('workerSubnets',[])}
    except (OSError,ValueError,TypeError,KeyError):
        return {'mode':'isolated-containers','available':False,'message':'Isolated runner unavailable; imports are blocked','workerSubnets':[]}


def docker_gateway_addresses():
    # Hairpin connections to a published Docker port can be SNATed to the
    # receiving container's gateway. These anonymous container-origin requests
    # must not gain broader access than a directly identified worker.
    result=[]
    try:
        for row in Path('/proc/net/route').read_text().splitlines()[1:]:
            fields=row.split()
            if len(fields)>=4 and fields[1]=='00000000' and int(fields[3],16)&2:
                result.append(str(ipaddress.ip_address(bytes.fromhex(fields[2])[::-1]))+'/32')
    except (OSError,ValueError):pass
    return result


def worker_request(address, headers):
    # Restricted bearer tokens never grant general UI/API access. The subnet check
    # also blocks a worker that intentionally omits its Authorization header.
    if headers.get('Authorization','').startswith('Bearer awj_'):return True
    try:
        ip=ipaddress.ip_address(address)
        networks=runner_status()['workerSubnets']+os.environ.get('ATLAS_WORKER_SUBNETS','').split()+docker_gateway_addresses()
        return any(ip in ipaddress.ip_network(net) for net in networks)
    except ValueError:return False


class ContainerJob:
    def __init__(self, folder, token):
        self.folder=folder;self.token=token;self.output=bytearray();self.stdout=None
    def wait(self, timeout):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                raw=(self.folder/'result.json').read_bytes()
                if len(raw)>65536:raise ValueError('Invalid runner result')
                result=json.loads(raw);self.output[:]=str(result.get('output','')).encode()[:16384]
                return int(result['code'])
            except FileNotFoundError:time.sleep(.2)
        raise subprocess.TimeoutExpired('isolated connector',timeout)
    def launch(self):atomic_json(self.folder/'ready.json',{'ready':True})
    def terminate(self):atomic_json(self.folder/'cancel.json',{'cancel':True})
    def kill(self):self.terminate()
    def cleanup(self):
        # Runner acknowledges termination before the job's private files disappear.
        if (self.folder/'result.json').exists() or not (self.folder/'ready.json').exists():shutil.rmtree(self.folder,ignore_errors=True)


class ContainerExecutor:
    def __init__(self,root=None):self.root=Path(root or os.environ.get('ATLAS_WORKER_QUEUE','/worker-jobs'))
    def start(self, package, entrypoint, environment, source, instance, token, manifest=None, configuration_root=None):
        if not runner_status(self.root)['available']:raise ValueError('Isolated runner unavailable. Start the connector-runner service before importing.')
        self.root.mkdir(parents=True,exist_ok=True)
        folder=self.root/uuid.uuid4().hex;folder.mkdir(mode=0o700)
        try:
            package=Path(package)
            if package.is_symlink() or package.parent.is_symlink():raise ValueError('Symbolic package roots are not allowed.')
            package=package.resolve()
            if any(p.is_symlink() for p in package.rglob('*')):raise ValueError('Connector packages cannot contain symbolic links.')
            if manifest:
                (folder/'package').mkdir()
                for file in manifest['files']:
                    path=Path(file['path']);original=package/path
                    if path.is_absolute() or '..' in path.parts:raise ValueError('Invalid package path')
                    raw=original.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=file['sha256']:raise ValueError('Installed add-in changed; review and reinstall the repository.')
                    destination=folder/'package'/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw)
            else:shutil.copytree(package,folder/'package')
            entry=Path(entrypoint)
            if entry.is_absolute() or '..' in entry.parts or not (folder/'package'/entry).is_file():raise ValueError('Invalid connector entrypoint.')
            secrets=folder/'secrets';secrets.mkdir(mode=0o700)
            safe={};total=0
            for key,value in environment.items():
                if key=='PYTHONPATH':continue
                if key.endswith('_FILE') or key=='CA_FILE':
                    path=Path(value)
                    if key=='ATLAS_TOKEN_FILE':raw=token.encode()
                    else:
                        if path.is_symlink() or path.parent.is_symlink():raise ValueError('Symbolic credential files are not allowed.')
                        if configuration_root and not path.resolve().is_relative_to(Path(configuration_root).resolve()):raise ValueError('Connector file is outside its instance.')
                        optional=key=='ADDIN_CREDENTIAL_FILE' and manifest and not manifest.get('credentialRequired')
                        if not path.is_file() and not optional:raise ValueError('Required connector file is missing.')
                        raw=path.read_bytes() if path.is_file() else b''
                    total+=len(raw)
                    if total>200000:raise ValueError('Connector configuration is too large.')
                    target=secrets/key;target.write_bytes(token.encode() if key=='ATLAS_TOKEN_FILE' else raw);target.chmod(0o600)
                    safe[key]='/work/secrets/'+key
                elif key in ('ATLAS_URL','CONNECTOR_ID','RUN_ONCE','ADDIN_ID','PORTAINER_URL','PORTAINER_TLS_SHA256','KUBERNETES_URL','CLUSTER_NAME'):safe[key]=value
            safe['ATLAS_URL']=os.environ.get('ATLAS_CONNECTOR_CALLBACK_URL',environment['ATLAS_URL'])
            safe.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',RUN_ONCE='true')
            atomic_json(folder/'request.json',{'schemaVersion':1,'source':source,'instance':instance,'entrypoint':entry.as_posix(),'environment':safe,'created':time.time()})
            return ContainerJob(folder,token)
        except Exception:
            shutil.rmtree(folder,ignore_errors=True);raise
