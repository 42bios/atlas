"""Explicit migration from legacy built-ins to reviewed independent packages.

A private journal protects configuration conversion; startup recovery rolls back
an interrupted migration before schedules can run. No inventory IDs are rewritten.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
from . import repositories

OFFICIAL={'42bios/atlas-plugin-portainer':('portainer','portainer-connector'),
          '42bios/atlas-plugin-snmp-discovery':('snmp','snmp-connector'),
          '42bios/atlas-plugin-kubernetes':('kubernetes','kubernetes-connector')}

def atomic(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data));tmp.chmod(0o600);os.replace(tmp,path)

def private_copy(source,destination):
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob('*')):raise ValueError('Symbolic migration paths are not allowed.')
    shutil.copytree(source,destination)
    for p in [destination,*destination.rglob('*')]:p.chmod(0o700 if p.is_dir() else 0o600)

class ConnectorMigration:
    def migration_candidates(self,repository):
        known=OFFICIAL.get(str(repository).lower())
        if not known:return []
        with self.lock:return [{'id':x['id'],'name':x['name'],'source':x['source'],'interval':x['interval'],'enabled':x['enabled']} for x in self.read()['instances'] if x['plugin']==known[0]]

    def _migration_values(self,metadata,data):
        known=OFFICIAL.get(metadata['repositoryName'].lower())
        if not known or metadata['manifest']['id']!=known[1]:raise ValueError('Only the matching official repository can replace this legacy connector.')
        plugin=known[0];instances=[x for x in data['instances'] if x['plugin']==plugin]
        if not instances:raise ValueError('No legacy instances need migration.')
        values=[]
        for old in instances:
            if old['id'] in self.jobs:raise ValueError('Wait for all legacy imports to finish before migration.')
            folder=self.root/'instances'/old['id']
            if folder.is_symlink() or folder.parent.is_symlink() or any(p.is_symlink() for p in folder.rglob('*')):raise ValueError('Symbolic instance files cannot be migrated.')
            credential=(folder/'credential').read_text()
            if not credential.strip():raise ValueError('An existing upstream credential is required for migration.')
            config=copy.deepcopy(old['config'])
            if plugin=='snmp':config['targets']='\n'.join(config['targets'])
            if plugin=='kubernetes':
                ca=(folder/'cluster_ca').read_text()
                if not credential.strip() or '-----BEGIN CERTIFICATE-----' not in ca:raise ValueError('Kubernetes token and CA certificate are required for migration.')
                credential=json.dumps({'token':credential,'ca':ca})
            config=repositories.configuration(metadata['manifest'],config)
            values.append((old,config,credential))
        existing=data.get('repositories',{}).get(metadata['id'])
        if existing and existing['commit']!=metadata['commit']:raise ValueError('Update the installed repository package separately before migrating legacy instances.')
        return plugin,values

    def migration_preview(self,metadata):
        with self.lock:
            if not self.migration_candidates(metadata['repositoryName']):return None
            plugin,values=self._migration_values(metadata,self.read())
            return {'bundledPlugin':plugin,'instances':[{'id':x['id'],'name':x['name'],'source':x['source'],'interval':x['interval'],'enabled':x['enabled']} for x,_,_ in values]}

    def migrate_repository(self,review,trust):
        if not isinstance(review,str) or not re.fullmatch(r'[a-f0-9]{32}',review):raise ValueError('Choose a reviewed repository package.')
        with self.lock:
            review_file=self.root/'staging'/review/'review.json'
            metadata=json.loads(review_file.read_text())
            if metadata['expires']<time.time() or trust!=metadata['repositoryName']:raise ValueError('Review expired or repository confirmation does not match.')
            before=self.read();plugin,values=self._migration_values(metadata,before)
            migration=uuid.uuid4().hex;backup=self.root/'migrations'/migration;backup.mkdir(parents=True,mode=0o700);backup.parent.chmod(0o700)
            (backup/'instances').mkdir(mode=0o700)
            for old,_,_ in values:private_copy(self.root/'instances'/old['id'],backup/'instances'/old['id'])
            private_copy(self.root/'packages'/plugin,backup/'legacy-package')
            atomic(backup/'registry-before.json',before)
            journal={'id':migration,'phase':'applying','legacyPlugin':plugin,'targetPlugin':metadata['id'],'targetCommit':metadata['commit'],'instances':[x['id'] for x,_,_ in values],'created':time.time(),'afterConfig':{x['id']:cfg for x,cfg,_ in values},'credentialHash':{x['id']:hashlib.sha256(secret.encode()).hexdigest() for x,_,secret in values}}
            atomic(backup/'journal.json',journal)
            try:
                target=metadata['id']
                if target in before['installed']:
                    for file in metadata['manifest']['files']:
                        for base in (self.root/'staging'/review/'files',self.root/'packages'/target):
                            if hashlib.sha256((base/file['path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Repository package changed; review and reinstall it before migration.')
                else:target=self.install_repository(review,trust)
                data=self.read()
                for old,config,credential in values:
                    folder=self.root/'instances'/old['id']
                    for name,value in [('config.json',json.dumps(config)),('credential',credential)]:
                        tmp=folder/(name+'.migrating');tmp.write_text(value);tmp.chmod(0o600);os.replace(tmp,folder/name)
                    instance=next(x for x in data['instances'] if x['id']==old['id'])
                    instance.update(plugin=target,config=config,migratedFrom=plugin,migrationId=migration)
                data['installed']=[id for id in data['installed'] if id!=plugin]
                self.write(data)
                journal['phase']='committed';atomic(backup/'journal.json',journal)
            except Exception:
                self._restore_interrupted(backup);raise
            # Old files live only in the protected recovery bundle after commit.
            shutil.rmtree(self.root/'packages'/plugin,ignore_errors=True)
            return {'plugin':target,'migration':migration,'instances':journal['instances']}

    def _restore_interrupted(self,backup):
        before=json.loads((backup/'registry-before.json').read_text());journal=json.loads((backup/'journal.json').read_text())
        for id in journal['instances']:
            folder=self.root/'instances'/id;shutil.rmtree(folder,ignore_errors=True);private_copy(backup/'instances'/id,folder)
        old=self.root/'packages'/journal['legacyPlugin']
        if not old.exists():private_copy(backup/'legacy-package',old)
        self.write(before);journal['phase']='rolled-back';atomic(backup/'journal.json',journal)
        if journal['targetPlugin'] not in before['installed']:shutil.rmtree(self.root/'packages'/journal['targetPlugin'],ignore_errors=True)

    def recover_migrations(self):
        for file in (self.root/'migrations').glob('*/journal.json'):
            phase=json.loads(file.read_text()).get('phase')
            if phase=='applying':self._restore_interrupted(file.parent)
            elif phase=='rollback-applying':self._complete_rollback(file.parent)

    def rollback_migration(self,migration):
        if not isinstance(migration,str) or not re.fullmatch(r'[a-f0-9]{32}',migration):raise ValueError('Choose a valid migration recovery ID.')
        with self.lock:
            backup=self.root/'migrations'/migration;journal=json.loads((backup/'journal.json').read_text())
            if journal['phase']!='committed':raise ValueError('This migration is not active.')
            before=json.loads((backup/'registry-before.json').read_text());data=self.read()
            for id in journal['instances']:
                current=next((x for x in data['instances'] if x['id']==id),None)
                old=next(x for x in before['instances'] if x['id']==id)
                if id in self.jobs:raise ValueError('Wait for running imports before restoring the legacy connector.')
                if not current or current.get('migrationId')!=migration or current['plugin']!=journal['targetPlugin']:raise ValueError('Instance changed after migration; refusing to overwrite it.')
                for key in ('name','source','interval','enabled'):
                    if current[key]!=old[key]:raise ValueError('Instance settings changed after migration; review them before restoring.')
                if current['config']!=journal['afterConfig'][id] or hashlib.sha256((self.root/'instances'/id/'credential').read_bytes()).hexdigest()!=journal['credentialHash'][id]:raise ValueError('Configuration or credentials changed after migration; refusing to overwrite them.')
            for id in journal['instances']:
                old=next(x for x in before['instances'] if x['id']==id)
                data['instances']=[copy.deepcopy(old) if x['id']==id else x for x in data['instances']]
            if journal['legacyPlugin'] not in data['installed']:data['installed'].append(journal['legacyPlugin'])
            atomic(backup/'rollback-target.json',data);journal['phase']='rollback-applying';atomic(backup/'journal.json',journal)
            self._complete_rollback(backup)
            return {'restored':True,'instances':journal['instances']}

    def _complete_rollback(self,backup):
        journal=json.loads((backup/'journal.json').read_text())
        for id in journal['instances']:
            folder=self.root/'instances'/id;shutil.rmtree(folder,ignore_errors=True);private_copy(backup/'instances'/id,folder)
        legacy=self.root/'packages'/journal['legacyPlugin']
        if not legacy.exists():private_copy(backup/'legacy-package',legacy)
        self.write(json.loads((backup/'rollback-target.json').read_text()));journal['phase']='rolled-back';atomic(backup/'journal.json',journal)
