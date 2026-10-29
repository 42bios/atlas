"""Private, bounded Atlas-data recovery archives; no secret-bearing HTTP download."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import tarfile
import tempfile
import time
import uuid

MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 20000

class HostBackups:
    def __init__(self, app):
        self.app = app
        self.data = Path(app.database()).parent
        self.root = self.data / 'backups'
        self.scratch = self.root

    def path(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'atlas-data-[0-9-]+-[a-f0-9]{8}\.tar\.gz', name):
            raise ValueError('Choose an Atlas backup from the host list.')
        path = self.root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Backup file is unavailable.')
        return path

    def create(self):
        with self.app.LOCK, self.app.addins().lock:
            if any(x.get('running') for x in self.app.addins().status()['instances']):
                raise ValueError('Wait for running imports to finish before creating a backup.')
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root.chmod(0o700)
            name = 'atlas-data-' + time.strftime('%Y-%m-%d-%H%M%S', time.gmtime()) + '-' + uuid.uuid4().hex[:8] + '.tar.gz'
            dest = self.root / name
            try:
                with tempfile.TemporaryDirectory(dir=self.root) as temp:
                    stage = Path(temp)
                    snapshot = stage / 'atlas.db'
                    source = sqlite3.connect(self.app.database())
                    target = sqlite3.connect(snapshot)
                    try: source.backup(target)
                    finally: target.close(); source.close()
                    snapshot.chmod(0o600)
                    files = [('atlas.db', snapshot)]
                    addins = self.data / 'addins'
                    if addins.exists():
                        for path in sorted(addins.rglob('*')):
                            if path.is_symlink(): raise ValueError('Backup stopped: symbolic links are not supported in add-in data.')
                            if path.is_file(): files.append((path.relative_to(self.data).as_posix(), path))
                    if len(files) > MAX_FILES or sum(p.stat().st_size for _, p in files) > MAX_BYTES:
                        raise ValueError('Atlas backup exceeds the supported 512 MiB / 20,000 file limit.')
                    manifest = {'schemaVersion': 1, 'kind': 'atlas-data', 'created': time.time(),
                                'modules': {m['id']:m['version'] for m in self.app.features().public()['modules']},
                                'files': {n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files}}
                    (stage/'manifest.json').write_text(json.dumps(manifest))
                    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
                        archive.add(stage/'manifest.json', arcname='manifest.json')
                        for member, path in files: archive.add(path, arcname=member, recursive=False)
                result = self.validate(name)
                return dict(result, name=name, bytes=dest.stat().st_size)
            except Exception:
                dest.unlink(missing_ok=True)
                raise

    def validate(self, name, destination=None):
        path = self.path(name)
        with tarfile.open(path, 'r:gz') as archive:
            members = archive.getmembers()
            names = [m.name for m in members]
            if len(names) != len(set(names)) or len(names)>MAX_FILES+1 or sum(m.size for m in members)>MAX_BYTES+1024*1024:
                raise ValueError('Archive has duplicate entries or exceeds recovery limits.')
            for member in members:
                parts = PurePosixPath(member.name)
                if not member.isfile() or parts.is_absolute() or '..' in parts.parts or '\\' in member.name:
                    raise ValueError('Unsafe archive member.')
                if member.name not in ('atlas.db','manifest.json') and not member.name.startswith('addins/'):
                    raise ValueError('Unexpected archive member.')
            if 'manifest.json' not in names or 'atlas.db' not in names: raise ValueError('Incomplete Atlas archive.')
            if archive.getmember('manifest.json').size>4*1024*1024:raise ValueError('Backup manifest exceeds recovery limits.')
            manifest = json.load(archive.extractfile('manifest.json'))
            if manifest.get('schemaVersion')!=1 or manifest.get('kind')!='atlas-data': raise ValueError('Unsupported backup format.')
            expected = manifest.get('files',{})
            if not isinstance(expected,dict) or any(not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{64}',v) for v in expected.values()):raise ValueError('Invalid backup checksums.')
            if set(expected)!=set(names)-{'manifest.json'}: raise ValueError('Backup manifest does not match its files.')
            current = {m['id']:m['version'] for m in self.app.features().public()['modules']}
            if any(key not in current or str(current[key]).split('.')[0]!=str(version).split('.')[0] for key,version in manifest.get('modules',{}).items()):
                raise ValueError('Backup module versions are incompatible with this Atlas runtime.')
            with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
                stage = Path(temp)
                for member in members:
                    if member.name=='manifest.json':continue
                    target = stage/member.name
                    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    digest=hashlib.sha256()
                    with archive.extractfile(member) as source, target.open('wb') as output:
                        while chunk:=source.read(1024*1024):
                            digest.update(chunk);output.write(chunk)
                    target.chmod(0o600)
                    if digest.hexdigest()!=expected[member.name]:raise ValueError('Backup file checksum mismatch.')
                con = sqlite3.connect(stage/'atlas.db')
                try:
                    if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup database failed integrity validation.')
                    row=con.execute('SELECT content FROM inventory WHERE id=1').fetchone()
                    if not row:raise ValueError('Backup inventory is missing.')
                    state=self.app.validate(json.loads(row[0]))
                finally:con.close()
                registry=stage/'addins/registry.json'
                connections=0
                if registry.exists():
                    config=json.loads(registry.read_text());connections=len(config.get('instances',[]))
                    for instance in config.get('instances',[]):
                        identifier=instance.get('id','')
                        if not re.fullmatch(r'[a-zA-Z0-9_-]+',identifier):raise ValueError('Invalid connection identifier in backup.')
                if destination is not None:
                    destination=Path(destination)
                    if destination.exists():raise ValueError('Restore destination must be a new directory. Existing installations are never overwritten.')
                    shutil.copytree(stage,destination)
                    destination.chmod(0o700)
                    for directory in destination.rglob('*'):
                        directory.chmod(0o700 if directory.is_dir() else 0o600)
                return {'valid':True,'created':manifest['created'],'files':len(expected),'connections':connections,
                        'inventory':{k:len(state.get(k,[])) for k in ('devices','services','racks','networks','links')},
                        'scope':'Atlas database and private add-in data. Deployment files and external snapshot mounts require a separate host backup.'}

    def list(self):
        if not self.root.exists():return []
        return [{'name':p.name,'bytes':p.stat().st_size,'created':p.stat().st_mtime} for p in sorted(self.root.glob('atlas-data-*.tar.gz'),reverse=True) if p.is_file() and not p.is_symlink()]

def status(handler, app): return handler.json_response(200, {'backups':HostBackups(app).list()})

def post(handler, app):
    origin=handler.headers.get('Origin')
    if origin and origin not in ('http://'+handler.headers.get('Host',''),'https://'+handler.headers.get('Host','')):
        return handler.json_response(403,{'error':'Origin rejected'})
    try:
        length=int(handler.headers.get('Content-Length',0))
        if not 0<length<=2000:raise ValueError('Provide a bounded backup request.')
        body=json.loads(handler.rfile.read(length))
        if not isinstance(body,dict):raise ValueError('Provide a JSON object.')
        backups=HostBackups(app)
        if body.get('action')=='create':result=backups.create()
        elif body.get('action')=='validate':result=backups.validate(body.get('name'))
        elif body.get('action')=='rehearse':
            backups.root.mkdir(mode=0o700,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=backups.root) as temp:
                result=backups.validate(body.get('name'),Path(temp)/'restored')
                result['rehearsed']=True
        else:raise ValueError('Choose create, validate or rehearse.')
        return handler.json_response(200,result)
    except (OSError,ValueError,TypeError,KeyError,tarfile.TarError,sqlite3.Error) as error:
        return handler.json_response(400,{'error':str(error)})
