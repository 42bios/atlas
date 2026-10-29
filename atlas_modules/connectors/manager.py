"""Atlas add-ins: trusted bundled modules, private credentials, bounded import jobs."""
import hmac
import socket
import ssl
from urllib.parse import urlsplit
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid

from .setup import PLUGINS, ROOT, prepare
from .execution import ContainerExecutor, runner_status
from .repository_manager import RepositoryAddins
from . import repositories
from .migration import ConnectorMigration


class AddinManager(RepositoryAddins, ConnectorMigration):
    def __init__(self, root, atlas_url='http://127.0.0.1:8765'):
        self.root=Path(root); self.atlas_url=atlas_url
        self.lock=threading.RLock(); self.jobs={}
        self.stopping=threading.Event()
        self.executor=ContainerExecutor()
        self.recover_migrations()

    def read(self):
        path=self.root/'registry.json'
        return json.loads(path.read_text()) if path.exists() else {'installed':[], 'instances':[]}

    def write(self, data):
        self.root.mkdir(parents=True,exist_ok=True); self.root.chmod(0o700)
        path=self.root/'registry.json'; temporary=self.root/'registry.tmp'
        temporary.write_text(json.dumps(data));temporary.chmod(0o600);os.replace(temporary,path)

    def status(self):
        with self.lock:
            data=self.read()
            for x in data['instances']:
                x['running']=x['id'] in self.jobs
                if not x['running'] and x.get('result')=='Import running':x['result']='Previous import interrupted; run again'
                x['credentialsConfigured']=(self.root/'instances'/x['id']/'credential').exists()
            return {'execution':{k:v for k,v in runner_status(self.executor.root).items() if k!='workerSubnets'}, 'githubAccess':self.github_access(), 'packages':[{**p,'installed':p['id'] in data['installed']} for p in [*PLUGINS,*data.get('repositories',{}).values()]], 'instances':data['instances']}

    def install(self, plugin):
        if plugin not in ('portainer','snmp','kubernetes'):raise ValueError('Choose an available bundled add-in.')
        with self.lock:
            data=self.read()
            if plugin in data['installed']:return
            dest=self.root/'packages'/plugin/'plugins'
            for name in ('collector.py','runtime.py'):
                path=dest/plugin/name;path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/'plugins'/plugin/name,path)
            if plugin!='portainer':
                path=dest/'common/runtime.py';path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/'plugins/common/runtime.py',path)
            data['installed'].append(plugin);self.write(data)

    def configure(self, payload, existing_sources=()):
        if not isinstance(payload,dict):raise ValueError('Provide an instance configuration.')
        allowed={'id','plugin','name','upstreamUrl','targets','snmpVersion','clusterName','tlsFingerprint','credential','caCertificate','interval','adoptSource','config'}
        if set(payload)-allowed:raise ValueError('Unknown instance configuration field.')
        plugin=payload.get('plugin'); instance_id=payload.get('id')
        with self.lock:
            data=self.read()
            if plugin not in data['installed']:raise ValueError('Install this add-in first.')
            old=next((x for x in data['instances'] if x['id']==instance_id),None)
            if instance_id and not old:raise ValueError('Instance not found.')
            if old and old['plugin']!=plugin:raise ValueError('The instance add-in cannot be changed.')
            if old and old['id'] in self.jobs:raise ValueError('Wait for the current import to finish before editing.')
            adopt=payload.get('adoptSource')
            source=old['source'] if old else 'addin-'+plugin+'-'+uuid.uuid4().hex[:12]
            if adopt and not old:
                match=next((x for x in existing_sources if x['connector']==adopt and x['plugin'] in (plugin,'snmp-discovery' if plugin=='snmp' else plugin)),None)
                if not match:raise ValueError('Choose a reporting connector matching this add-in.')
                source=adopt
            if any(x['source']==source and x is not old for x in data['instances']):raise ValueError('This connector source is already managed by an add-in.')
            name=payload.get('name','')
            if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Instance name is required (up to 100 characters).')
            interval=payload.get('interval',0)
            if type(interval)!=int or interval not in (0,900,3600,21600,86400):raise ValueError('Choose a supported import schedule.')
            repository=data.get('repositories',{}).get(plugin)
            fields={k:payload.get(k) for k in ('upstreamUrl','targets','snmpVersion','clusterName','tlsFingerprint') if k in payload}
            if repository:
                fields=repositories.configuration(repository['manifest'],payload.get('config',{}))
                setup={'files':{'config.json':json.dumps(fields)}}
            else:
                if 'config' in payload:raise ValueError('Bundled connectors use their specific configuration fields.')
                setup=prepare({'plugin':plugin,'connector':source,'atlasUrl':self.atlas_url,**fields})
            credential=payload.get('credential','');ca=payload.get('caCertificate','')
            if not isinstance(credential,str) or len(credential)>20000 or not isinstance(ca,str) or len(ca)>20000:raise ValueError('Credential or certificate is invalid.')
            instance_id=old['id'] if old else uuid.uuid4().hex
            folder=self.root/'instances'/instance_id
            if folder.is_symlink() or folder.parent.is_symlink():raise ValueError('Symbolic instance directories are not allowed.')
            if folder.exists() and any(p.is_symlink() for p in folder.iterdir()):raise ValueError('Symbolic instance files are not allowed.')
            if not credential and not (folder/'credential').exists() and (not repository or repository['manifest'].get('credentialRequired')):raise ValueError('Provide the upstream credential for this instance.')
            if old and plugin=='snmp' and old['config'].get('snmpVersion','2c')!=fields.get('snmpVersion','2c') and not credential:raise ValueError('Provide new credentials when changing the SNMP version.')
            if credential and (plugin=='portainer' or plugin=='snmp' and fields.get('snmpVersion','2c')=='2c') and ('\n' in credential or '\r' in credential):raise ValueError('Credential must be a single line.')
            if plugin=='snmp' and fields.get('snmpVersion','2c')=='3' and credential:
                value=json.loads(credential)
                allowed_keys={'SecurityName','SecurityLevel','AuthType','AuthPassphrase','PrivType','PrivPassphrase'}
                if not isinstance(value,dict) or set(value)-allowed_keys or not value.get('SecurityName') or not value.get('SecurityLevel'):raise ValueError('Provide SNMPv3 security name, level and credential fields as JSON.')
                if any(not isinstance(v,str) or '\n' in v or '\r' in v for v in value.values()) or value['SecurityLevel'] not in ('noAuthNoPriv','authNoPriv','authPriv'):raise ValueError('Invalid SNMPv3 credential fields.')
                required={'SecurityName','SecurityLevel'}
                if value['SecurityLevel']!='noAuthNoPriv':required.update(('AuthType','AuthPassphrase'))
                if value['SecurityLevel']=='authPriv':required.update(('PrivType','PrivPassphrase'))
                if any(not value.get(k) for k in required):raise ValueError('Required SNMPv3 authentication or privacy fields are missing.')
            if plugin=='kubernetes' and not ca and not (folder/'cluster_ca').exists():raise ValueError('Provide the Kubernetes CA certificate.')
            if ca and ('-----BEGIN CERTIFICATE-----' not in ca or '-----END CERTIFICATE-----' not in ca):raise ValueError('Provide a PEM CA certificate.')
            folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
            for filename,value in [('credential',credential),('cluster_ca',ca),('atlas_token',secrets.token_urlsafe(48) if not old else '')]:
                if value:
                    path=folder/filename;path.write_text(value);path.chmod(0o600)
            for filename,value in setup['files'].items():
                path=folder/Path(filename).name;path.write_text(value);path.chmod(0o600)
            record={**(old or {}),'id':instance_id,'plugin':plugin,'source':source,'name':name.strip(),'config':fields,'interval':interval,'enabled':True if not old else old['enabled']}
            data['instances']=[record if x['id']==instance_id else x for x in data['instances']]
            if not old:data['instances'].append(record)
            self.write(data);return instance_id

    def authorized(self, headers, source):
        if not isinstance(source,str):return False
        with self.lock:
            instance=next((x for x in self.read()['instances'] if x['source']==source and x['enabled']),None)
            job=self.jobs.get(instance['id']) if instance else None
            return bool(job and hmac.compare_digest(headers.get('Authorization',''),'Bearer '+job.token))

    def filter_worker_records(self, snapshot):
        # Do not add a new ephemeral worker to application inventory on every run.
        # IDs are taken from trusted controller receipts, never guessed from names.
        ids=set()
        with self.lock:
            for job in self.jobs.values():
                try:
                    raw=(job.folder/'running.json').read_text()
                    if len(raw)>4096:continue
                    value=json.loads(raw).get('containerId','')
                    if re.fullmatch(r'[a-f0-9]{64}',value):ids.add(value)
                except (AttributeError,OSError,ValueError,TypeError):pass
        if not ids or not isinstance(snapshot.get('services',[]),list) or not isinstance(snapshot.get('links',[]),list):return snapshot
        removed={s.get('id') for s in snapshot.get('services',[]) if isinstance(s,dict) and isinstance(s.get('id'),str) and s.get('kind')=='Container' and any(s.get('id','')==id or s.get('id','').endswith('-container-'+id) for id in ids)}
        if not removed:return snapshot
        return {**snapshot,'services':[s for s in snapshot.get('services',[]) if not isinstance(s,dict) or s.get('id') not in removed],
                'links':[l for l in snapshot.get('links',[]) if not isinstance(l,dict) or l.get('source') not in removed and l.get('target') not in removed]}

    def _environment(self, x):
        folder=self.root/'instances'/x['id']
        env={**os.environ,'ATLAS_URL':self.atlas_url,'CONNECTOR_ID':x['source'],'ATLAS_TOKEN_FILE':str(folder/'atlas_token'),'RUN_ONCE':'true','PYTHONPATH':str(self.root/'packages'/x['plugin']/'plugins')}
        # Do not pass Atlas's external-source key file or unrelated environment credentials to workers.
        env={k:v for k,v in env.items() if k in ('PATH','LANG','PYTHONPATH','PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED','ATLAS_URL','CONNECTOR_ID','ATLAS_TOKEN_FILE','RUN_ONCE')}
        cfg=x['config']
        repository=self.read().get('repositories',{}).get(x['plugin'])
        if repository:
            env.update(PYTHONPATH=str(self.root/'packages'/x['plugin']),ADDIN_ID=x['plugin'],ADDIN_CONFIG_FILE=str(folder/'config.json'),ADDIN_CREDENTIAL_FILE=str(folder/'credential'))
            return env
        if x['plugin']=='portainer':env.update(PORTAINER_URL=cfg['upstreamUrl'],PORTAINER_TLS_SHA256=cfg.get('tlsFingerprint',''),PORTAINER_TOKEN_FILE=str(folder/'credential'))
        elif x['plugin']=='kubernetes':env.update(KUBERNETES_URL=cfg['upstreamUrl'],CLUSTER_NAME=cfg.get('clusterName','Kubernetes'),KUBERNETES_TOKEN_FILE=str(folder/'credential'),CA_FILE=str(folder/'cluster_ca'))
        else:env.update(DISCOVERY_CONFIG_FILE=str(folder/'discovery_config'),SNMP_COMMUNITY_FILE=str(folder/'credential'),SNMP_CREDENTIALS_FILE=str(folder/'credential'))
        return env

    def run(self, instance_id):
        with self.lock:
            data=self.read();x=next((x for x in data['instances'] if x['id']==instance_id),None)
            if not x:raise ValueError('Instance not found.')
            if not x['enabled']:raise ValueError('Enable this instance before importing.')
            if instance_id in self.jobs:raise ValueError('An import is already running for this instance.')
            if len(self.jobs)>=2:raise ValueError('Two imports are already running. Wait for one to finish.')
            repository=data.get('repositories',{}).get(x['plugin'])
            script=self.root/'packages'/x['plugin']/repository['manifest']['entrypoint'] if repository else self.root/'packages'/x['plugin']/'plugins'/x['plugin']/'runtime.py'
            package=self.root/'packages'/x['plugin']
            token='awj_'+secrets.token_urlsafe(48)
            process=self.executor.start(package,script.relative_to(package),self._environment(x),x['source'],x['id'],token,manifest=repository['manifest'] if repository else None,configuration_root=self.root/'instances'/x['id'])
            self.jobs[instance_id]=process;x['lastStarted']=time.time();x['result']='Import running'
            try:self.write(data);process.launch()
            except Exception:self.jobs.pop(instance_id,None);process.cleanup();raise
            threading.Thread(target=self._finish,args=(instance_id,process),daemon=True).start()

    def _finish(self, instance_id, process, output=None, reader=None):
        try:code=process.wait(timeout=3600)
        except subprocess.TimeoutExpired:
            process.kill()
            try:process.wait(timeout=30)
            except (subprocess.TimeoutExpired,OSError,ValueError):pass
            code=-1
        except (OSError,ValueError,TypeError):code=1
        if reader:reader.join(timeout=2)
        with self.lock:
            snapshot=next((x for x in self.read()['instances'] if x['id']==instance_id),{})
        failure=self.failure_message(snapshot,bytes(process.output if hasattr(process,'output') else output or b''),code) if code!=0 else ''
        with self.lock:
            self.jobs.pop(instance_id,None);data=self.read();x=next((x for x in data['instances'] if x['id']==instance_id),None)
            if x:
                x['result']='Import completed' if code==0 else failure if x['enabled'] else 'Disabled'
                x['lastFinished']=time.time();self.write(data)
        process.cleanup()

    def action(self, action, instance_id=None, plugin=None):
        if action=='run':return self.run(instance_id)
        if action=='install':raise ValueError('Bundled add-ins are legacy. Install a reviewed repository package through Marketplace.')
        with self.lock:
            data=self.read()
            selected=[x for x in data['instances'] if x['id']==instance_id] if action!='uninstall' else [x for x in data['instances'] if x['plugin']==plugin]
            if action not in ('enable','disable','remove','uninstall'):raise ValueError('Unknown add-in action.')
            if action!='uninstall' and not selected:raise ValueError('Instance not found.')
            if action=='uninstall' and plugin not in data['installed']:raise ValueError('Add-in is not installed.')
            for x in selected:
                if action=='enable':x['enabled']=True;continue
                x['enabled']=False
                if x['id'] in self.jobs:self.jobs[x['id']].terminate()
                if action in ('remove','uninstall'):
                    data['instances'].remove(x);shutil.rmtree(self.root/'instances'/x['id'],ignore_errors=True)
            if action=='uninstall':
                data.get('repositories',{}).pop(plugin,None)
                data['installed'].remove(plugin);shutil.rmtree(self.root/'packages'/plugin,ignore_errors=True);shutil.rmtree(self.root/'rollback'/plugin,ignore_errors=True)
            self.write(data)

    def start_scheduler(self):
        def loop():
            while not self.stopping.wait(30):
                with self.lock:
                    for x in self.read()['instances']:
                        if x['enabled'] and x['interval'] and time.time()-x.get('lastStarted',0)>=x['interval']:
                            try:self.run(x['id'])
                            except (OSError,ValueError):pass
        threading.Thread(target=loop,daemon=True).start()

    @staticmethod
    def failure_message(instance, output=b'', code=1):
        if code == -1:return 'Import timed out; reduce discovery targets or check upstream responsiveness.'
        text=output.decode('utf-8',errors='replace')
        if any(t in text for t in ('SSLCertVerificationError','CERTIFICATE_VERIFY_FAILED','fingerprint mismatch')):
            return 'TLS trust failed; verify the controller certificate, CA or pinned fingerprint.'
        if any(t in text for t in ('HTTPError','Upstream request rejected')):
            return 'Upstream request rejected; check API credentials and inventory permissions.'
        if any(t in text for t in ('TimeoutError','socket.timeout','timed out')):
            return 'Upstream timed out; check its address, port and network reachability.'
        if 'ConnectionRefusedError' in text:return 'Connection refused; check the controller port and service.'
        url=instance.get('config',{}).get('upstreamUrl','')
        try:
            parsed=urlsplit(url)
            if parsed.hostname:socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
        except socket.gaierror:
            return 'Host name could not be resolved; check the controller URL and DNS on the Atlas host.'
        except ValueError:
            return 'Invalid controller URL; check its host and port.'
        return 'Import failed; check configuration, credentials and upstream availability, then retry. No raw worker output is exposed.'
