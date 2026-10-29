"""Repository package lifecycle. Preview downloads code; installation requires explicit trust."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
from . import repositories

class RepositoryAddins:
    def github_access(self):
        path=self.root/'github-access.json'
        with self.lock:
            data=json.loads(path.read_text()) if path.exists() else {}
            return {'configured':bool(data.get('token')), 'repositories':data.get('repositories',[])}

    def configure_github_access(self,payload):
        if set(payload)-{'token','repositories','remove'}:raise ValueError('Unknown GitHub access field.')
        with self.lock:
            path=self.root/'github-access.json'
            if payload.get('remove') is True:
                path.unlink(missing_ok=True)
                return self.github_access()
            names=payload.get('repositories')
            if not isinstance(names,list) or not 1<=len(names)<=50 or any(not isinstance(name,str) for name in names):raise ValueError('Specify 1–50 GitHub repositories.')
            names=list(dict.fromkeys(repositories.repository('https://github.com/'+name) for name in names if isinstance(name,str)))
            if not names:raise ValueError('Specify GitHub repository names as owner/repository.')
            token=payload.get('token','')
            if not isinstance(token,str) or len(token)>1000 or any(c.isspace() for c in token):raise ValueError('Provide a valid GitHub token without spaces.')
            old=json.loads(path.read_text()) if path.exists() else {}
            token=token or old.get('token','')
            if not token:raise ValueError('A GitHub token is required.')
            self.root.mkdir(parents=True,exist_ok=True);self.root.chmod(0o700)
            temporary=self.root/'github-access.tmp'
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:json.dump({'token':token,'repositories':names},stream)
            temporary.chmod(0o600);os.replace(temporary,path)
            return self.github_access()

    def preview_repository(self,url,ref=''):
        repo=repositories.repository(url)
        access=self.github_access()
        token=None
        if repo.lower() in {r.lower() for r in access['repositories']} and access['configured']:
            token=(self.root/'github-access.json').read_text()
            token=json.loads(token)['token']
        metadata,files=repositories.download(url,ref,token=token) if token else repositories.download(url,ref)
        with self.lock:
            data=self.read();existing=data.get('repositories',{}).get(metadata['id'])
            if existing:
                for x in data['instances']:
                    if x['plugin']==metadata['id']:repositories.configuration(metadata['manifest'],x['config'])
            # One bounded review per manager; superseded previews are removed without running code.
            shutil.rmtree(self.root/'staging',ignore_errors=True)
            review=uuid.uuid4().hex;folder=self.root/'staging'/review;folder.mkdir(parents=True,mode=0o700);folder.chmod(0o700)
            for path,content in files.items():
                target=folder/'files'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            metadata.update(review=review,expires=time.time()+3600,updating=bool(existing))
            (folder/'review.json').write_text(json.dumps(metadata))
            return metadata

    def install_repository(self,review,trust):
        if not isinstance(review,str) or len(review)!=32 or any(c not in '0123456789abcdef' for c in review):raise ValueError('Choose a downloaded add-in review.')
        with self.lock:
            folder=self.root/'staging'/review
            if not (folder/'review.json').exists():raise ValueError('Review no longer available. Download the repository again.')
            metadata=json.loads((folder/'review.json').read_text())
            if metadata['expires']<time.time():raise ValueError('Review expired. Download the repository again.')
            if trust!=metadata['repositoryName']:raise ValueError('Confirm trust by typing the exact owner/repository name.')
            data=self.read();id=metadata['id'];previous_metadata=data.get('repositories',{}).get(id)
            if any(x['plugin']==id and x['id'] in self.jobs for x in data['instances']):raise ValueError('Wait for running imports before updating this add-in.')
            manifest=repositories.parse_manifest(json.dumps(metadata['manifest']))
            for x in data['instances']:
                if x['plugin']==id:repositories.configuration(manifest,x['config'])
            for file in manifest['files']:
                if hashlib.sha256((folder/'files'/file['path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Downloaded package changed; download again.')
            dest=self.root/'packages'/id;temporary=self.root/'packages'/('.new-'+review);backup=self.root/'packages'/('.old-'+review)
            temporary.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(folder/'files',temporary)
            if dest.exists():os.replace(dest,backup)
            try:
                os.replace(temporary,dest)
                data.setdefault('repositories',{})[id]={k:v for k,v in metadata.items() if k not in ('review','expires','updating')}
                if id not in data['installed']:data['installed'].append(id)
                self.write(data)
            except Exception:
                shutil.rmtree(dest,ignore_errors=True)
                if backup.exists():os.replace(backup,dest)
                raise
            if backup.exists() and previous_metadata:
                rollback=self.root/'rollback'/id;shutil.rmtree(rollback,ignore_errors=True);rollback.mkdir(parents=True,mode=0o700)
                os.replace(backup,rollback/'files');(rollback/'metadata.json').write_text(json.dumps(previous_metadata))
            else:shutil.rmtree(backup,ignore_errors=True)
            shutil.rmtree(folder,ignore_errors=True)
            return id

    def rollback_repository(self,id,expected_commit=None):
        with self.lock:
            folder=self.root/'rollback'/id
            if not (folder/'metadata.json').is_file():raise ValueError('No previous package is available.')
            metadata=json.loads((folder/'metadata.json').read_text());manifest=metadata['manifest'];data=self.read()
            if expected_commit and metadata['commit']!=expected_commit:raise ValueError('Previous package changed outside Marketplace. Review the repository version directly.')
            if any(x['plugin']==id and x['id'] in self.jobs for x in data['instances']):raise ValueError('Wait for running imports before rolling back.')
            for x in data['instances']:
                if x['plugin']==id:repositories.configuration(manifest,x['config'])
            for file in manifest['files']:
                if hashlib.sha256((folder/'files'/file['path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Previous package checksum failed.')
            current=data['repositories'][id];package=self.root/'packages'/id;temporary=self.root/'packages'/('.rollback-'+uuid.uuid4().hex)
            os.replace(package,temporary)
            try:
                os.replace(folder/'files',package);data['repositories'][id]=metadata;self.write(data)
            except Exception:
                if package.exists():os.replace(package,folder/'files')
                os.replace(temporary,package);raise
            os.replace(temporary,folder/'files');(folder/'metadata.json').write_text(json.dumps(current))
            return id
