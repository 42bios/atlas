"""GitHub catalog discovery and reviewed, commit-pinned data package installation."""
import base64
import copy
import hashlib
import io
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlsplit
from PIL import Image
from . import repositories
from atlas_modules.catalogs.repository import parse_catalog, merge_catalog, catalog_url

DEFAULT_REPOSITORY='https://github.com/42bios/atlas-marketplace'
TYPES=('connector','device-catalog','icon-pack')

def text(value,maximum=200):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):raise ValueError('Invalid marketplace text.')
    return value.strip()

def path(value):
    if not isinstance(value,str) or len(value)>180 or not re.fullmatch(r'[A-Za-z0-9_./-]+',value) or any(p in ('','.','..') for p in value.split('/')):raise ValueError('Use a relative repository file path.')
    return value

def resolve(repository,ref=''):
    repo=repositories.repository(repository)
    ref=text(ref,150) if ref else json.loads(repositories.fetch('https://api.github.com/repos/'+repo))['default_branch']
    commit=json.loads(repositories.fetch('https://api.github.com/repos/'+repo+'/commits/'+quote(ref,safe='')))['sha']
    if not re.fullmatch(r'[a-f0-9]{40}',commit):raise ValueError('Invalid GitHub commit.')
    return repo,commit

def raw(repo,commit,file,maximum=1000000):return repositories.fetch('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+path(file),maximum)

def parse_index(payload,repo,commit):
    data=json.loads(payload)
    if not isinstance(data,dict) or data.get('schemaVersion')!=1 or not isinstance(data.get('packages'),list) or len(data['packages'])>200:raise ValueError('Expected schemaVersion 1 with up to 200 packages.')
    result=[];seen=set()
    for item in data['packages']:
        if not isinstance(item,dict) or item.get('type') not in TYPES:raise ValueError('Unsupported marketplace package type.')
        id=text(item.get('id'),64)
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',id) or id in seen:raise ValueError('Package IDs must be unique lower-case slugs.')
        seen.add(id);package_repo=repositories.repository(item.get('repository'))
        ref=text(item.get('ref'),150)
        # Index entries are explicit immutable releases, never an unreviewed moving branch.
        if not re.fullmatch(r'[a-f0-9]{40}',ref):raise ValueError('Marketplace entries must pin a full Git commit.')
        permissions=item.get('permissions',[])
        if not isinstance(permissions,list) or len(permissions)>12:raise ValueError('Invalid permission list.')
        entry={k:text(item.get(k),limit) for k,limit in [('name',100),('description',1000),('version',80),('license',150)]}
        entry.update(id=id,type=item['type'],repository='https://github.com/'+package_repo,repositoryName=package_repo,ref=ref,permissions=[text(x,250) for x in permissions],manifest=path(item.get('manifest',{'connector':'atlas-addin.json','device-catalog':'catalog.json','icon-pack':'atlas-icons.json'}[item['type']])),documentation=path(item.get('documentation','README.md')),icon=item.get('icon','box') if item.get('icon','box') in ('portainer','snmp-discovery','kubernetes','unifi','proxmox','rack','icons','box') else 'box',color=item.get('color','#316b83') if re.fullmatch(r'#[a-fA-F0-9]{6}',str(item.get('color',''))) else '#316b83')
        if entry['type']=='connector' and entry['manifest']!='atlas-addin.json':raise ValueError('Connector manifests must be at atlas-addin.json.')
        preview=item.get('preview','')
        if preview:entry['preview']='https://raw.githubusercontent.com/'+package_repo+'/'+ref+'/'+path(preview)
        result.append(entry)
    return result

def icon_package(payload,repo,commit):
    data=json.loads(payload)
    if not isinstance(data,dict) or data.get('schemaVersion')!=1 or not isinstance(data.get('icons'),list) or not 1<=len(data['icons'])<=200:raise ValueError('Expected schemaVersion 1 and 1–200 icons.')
    icons=[];seen=set();total=0
    for icon in data['icons']:
        if not isinstance(icon,dict):raise ValueError('Invalid icon.')
        id=text(icon.get('id'),64)
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',id) or id in seen:raise ValueError('Icon IDs must be unique slugs.')
        seen.add(id);file=path(icon.get('file'))
        if not file.lower().endswith(('.png','.jpg','.jpeg','.webp')):raise ValueError('Icon packs accept PNG, JPEG or WebP images; no executable SVG or HTML.')
        content=raw(repo,commit,file,150000);total+=len(content)
        if total>4000000:raise ValueError('Icon pack exceeds 4 MB.')
        if hashlib.sha256(content).hexdigest()!=icon.get('sha256'):raise ValueError('Icon checksum mismatch.')
        with Image.open(io.BytesIO(content)) as image:
            if image.width>1024 or image.height>1024 or getattr(image,'n_frames',1)!=1:raise ValueError('Use static icons up to 1024 × 1024 pixels.')
            image=image.convert('RGBA');image.thumbnail((128,128));output=io.BytesIO();image.save(output,format='PNG')
        matches=icon.get('match',[])
        if not isinstance(matches,list) or len(matches)>15:raise ValueError('Invalid icon matching names.')
        icons.append(dict(id=id,name=text(icon.get('name'),100),match=[text(m,80).lower() for m in matches],image='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()))
    return icons

class Marketplace:
    def __init__(self,app):self.app=app
    def read(self):
        with self.app.connection() as con:
            con.execute('CREATE TABLE IF NOT EXISTS marketplace (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
            row=con.execute('SELECT body FROM marketplace WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {'sources':[{'id':'atlas-official','name':'Atlas community catalog','repository':DEFAULT_REPOSITORY,'ref':'main','enabled':True,'packages':[]}],'installed':{},'reviews':{}}
    def write(self,data):
        with self.app.connection() as con:
            con.execute('INSERT OR REPLACE INTO marketplace VALUES (1,?)',(json.dumps(data),))
    def icons(self):
        return [dict(icon,id=key+':'+icon['id'],pack=entry['entry']['name']) for key,entry in self.read()['installed'].items() if entry['entry']['type']=='icon-pack' for icon in entry.get('content',[])]
    def status(self):
        with self.app.LOCK:
            data=self.read();native_status=self.app.addins().status();native=native_status['packages'];state=self.app.read_state();items=[];seen=set()
            for source in data['sources']:
                if not source['enabled']:continue
                for entry in source.get('packages',[]):
                    identity=(entry['type'],entry['repositoryName'].lower())
                    if identity in seen:continue
                    seen.add(identity)
                    key=next((key for key,value in data['installed'].items() if (value['entry']['type'],value['entry']['repositoryName'].lower())==identity),source['id']+'/'+entry['id']);installed=data['installed'].get(key)
                    existing=next((p for p in native if p.get('repositoryName','').lower()==entry['repositoryName'].lower() and p.get('installed')),None)
                    bundled_id={'42bios/atlas-plugin-portainer':'portainer','42bios/atlas-plugin-snmp-discovery':'snmp','42bios/atlas-plugin-kubernetes':'kubernetes'}.get(entry['repositoryName'].lower())
                    if not existing and bundled_id:existing=next((p for p in native if p['id']==bundled_id and p.get('installed')),None)
                    device=next((s for s in state.get('catalogSources',[]) if '/'+entry['repositoryName'].lower()+'/' in s.get('url','').lower()),None) if entry['type']=='device-catalog' else None
                    is_installed=bool(existing) if entry['type']=='connector' else bool(device) if entry['type']=='device-catalog' else bool(installed)
                    installed_ref=(existing or {}).get('commit') if entry['type']=='connector' and existing else installed.get('entry',{}).get('ref') if installed else None
                    items.append(dict(entry,key=key,sourceName=source['name'],sourceId=source['id'],installed=is_installed,installedVersion=((existing or {}).get('version') or (installed or {}).get('entry',{}).get('version')) if is_installed else None,updateAvailable=bool(is_installed and installed_ref and installed_ref!=entry['ref']),migration=self.app.addins().migration_candidates(entry['repositoryName']) if entry['type']=='connector' else [],installedPermissions=(installed or {}).get('entry',{}).get('permissions',[]),managed=bool(installed and is_installed),rollback=bool(installed and is_installed and installed.get('previous')),plugin=(existing or {}).get('id')))
            # Installed packages remain manageable even when their index source was removed/disabled.
            keys={x['key'] for x in items}
            for key,installed in data['installed'].items():
                if key not in keys:
                    entry=installed['entry'];exists=entry['type']=='icon-pack' or entry['type']=='connector' and any(p.get('repositoryName','').lower()==entry['repositoryName'].lower() and p.get('installed') for p in native) or entry['type']=='device-catalog' and any('/'+entry['repositoryName'].lower()+'/' in s.get('url','').lower() for s in state.get('catalogSources',[]))
                    if exists:items.append(dict(entry,key=key,sourceName='Removed or disabled source',installed=True,managed=True,migration=self.app.addins().migration_candidates(entry['repositoryName']) if entry['type']=='connector' else [],rollback=bool(installed.get('previous')),updateAvailable=False))
            for entry in items:
                if entry['type']!='connector':continue
                package=next((p for p in native if p.get('repositoryName','').lower()==entry['repositoryName'].lower() and p.get('installed')),None)
                entry['connections']=[{**{k:x.get(k) for k in ('id','name','source','enabled','running','lastFinished','result')},'deviceCount':sum(1 for o in state.get('devices',[]) if o.get('origin')==x['source'] and not o.get('missing')),'applicationCount':sum(1 for o in state.get('services',[]) if o.get('origin')==x['source'] and not o.get('missing'))} for x in native_status.get('instances',[]) if package and x['plugin']==package['id']]
            return {'schemaVersion':1,'packages':items,'sources':[{k:v for k,v in s.items() if k!='packages'}|{'count':len(s.get('packages',[]))} for s in data['sources']],'iconCount':len(self.icons())}
    def refresh(self,id):
        source=next((s for s in self.read()['sources'] if s['id']==id),None)
        if not source:raise ValueError('Marketplace source not found.')
        try:
            repo,commit=resolve(source['repository'],source['ref']);items=parse_index(raw(repo,commit,'catalog.json'),repo,commit)
            previous={p['repositoryName']:p for p in source.get('packages',[])}
            def enrich(item):
                old=previous.get(item['repositoryName'],{}).get('github',{})
                if old and time.time()-old.get('checked',0)<21600:item['github']=old;return item
                try:
                    info=json.loads(repositories.fetch('https://api.github.com/repos/'+item['repositoryName'],150000))
                    stars=info.get('stargazers_count');activity=info.get('pushed_at')
                    if type(stars) is not int or stars<0 or not isinstance(activity,str):raise ValueError('Invalid GitHub metadata')
                    item['github']={'stars':stars,'activity':activity[:40],'checked':time.time()}
                except (ValueError,OSError,KeyError,TypeError):
                    if old:item['github']=old
                return item
            with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(enrich,items))
        except (ValueError,OSError,KeyError,TypeError):
            with self.app.LOCK:
                data=self.read();saved=next((s for s in data['sources'] if s['id']==id),None)
                if saved:saved['error']='Unable to refresh. Check the public repository, catalog.json format and GitHub rate limits. The last successful catalog is retained.';self.write(data)
            raise ValueError('Unable to refresh marketplace source. Check repository, format and GitHub rate limits.') from None
        with self.app.LOCK:
            data=self.read();saved=next((s for s in data['sources'] if s['id']==id),None)
            if not saved:raise ValueError('Source was removed during refresh.')
            saved.update(packages=items,commit=commit,updated=time.time(),error='');self.write(data)
        return self.status()
    def source(self,payload):
        action=payload.get('action')
        with self.app.LOCK:
            data=self.read()
            if action=='add':
                repo=repositories.repository(payload.get('repository'));id=hashlib.sha256(repo.lower().encode()).hexdigest()[:16]
                if len(data['sources'])>=20:raise ValueError('Use up to 20 marketplace sources.')
                if any(s['repository'].lower()=='https://github.com/'+repo.lower() for s in data['sources']):raise ValueError('Source already added.')
                data['sources'].append(dict(id=id,name=text(payload.get('name',repo),100),repository='https://github.com/'+repo,ref=text(payload.get('ref') or 'main',150),enabled=True,packages=[]))
            else:
                source=next((s for s in data['sources'] if s['id']==payload.get('id')),None)
                if not source:raise ValueError('Source not found.')
                if action=='remove':data['sources'].remove(source)
                elif action=='toggle':source['enabled']=not source['enabled']
                else:raise ValueError('Unknown source action.')
            self.write(data)
        return self.status()
    def preview(self,key):
        entry=next((p for p in self.status()['packages'] if p['key']==key),None)
        if not entry or entry.get('sourceName')=='Removed or disabled source':raise ValueError('Refresh and enable the package source before installing.')
        repo=entry['repositoryName'];commit=entry['ref'];content=None;native=None
        if entry['type']=='connector':
            native=self.app.addins().preview_repository(entry['repository'],commit)
            native['migration']=self.app.addins().migration_preview(native)
            if native['version']!=entry['version']:raise ValueError('Catalog version does not match add-in manifest.')
        elif entry['type']=='device-catalog':
            url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+entry['manifest'];content=parse_catalog(raw(repo,commit,entry['manifest']),url)
        else:content=icon_package(raw(repo,commit,entry['manifest']),repo,commit)
        review=uuid.uuid4().hex
        with self.app.LOCK:
            data=self.read();data['reviews']={review:{'key':key,'entry':entry,'content':content,'nativeReview':native['review'] if native else None,'expires':time.time()+3600}};self.write(data)
        return dict(entry,review=review,count=len(content) if content else len(native['manifest']['files']),permissions=entry['permissions'],native=native,icons=content[:12] if entry['type']=='icon-pack' else [],migration=native.get('migration') if native else None)
    def install(self,payload):
        with self.app.LOCK:
            data=self.read();review=data['reviews'].get(payload.get('review'))
            if type(payload.get('migrate',False)) is not bool:raise ValueError('Migration requires an explicit boolean choice.')
            if not review or review['expires']<time.time():raise ValueError('Review expired. Download and review the package again.')
            entry=review['entry'];key=review['key']
            if payload.get('trust')!=entry['repositoryName']:raise ValueError('Confirm the exact owner/repository before installation.')
            source=next((s for s in data['sources'] if s['id']==entry['sourceId'] and s['enabled']),None)
            if not source:raise ValueError('Package source was removed or disabled. Review again.')
            previous=data['installed'].get(key) if entry.get('managed') else None
            if payload.get('migrate'):
                if entry['type']!='connector':raise ValueError('Only a connector can migrate existing instances.')
                migrated=self.app.addins().migrate_repository(review['nativeReview'],payload['trust']);plugin=migrated['plugin']
            elif entry['type']=='connector':plugin=self.app.addins().install_repository(review['nativeReview'],payload['trust'])
            else:plugin=None
            if entry['type']=='device-catalog':
                state=self.app.read_state();url='https://raw.githubusercontent.com/'+entry['repositoryName']+'/main/'+entry['manifest']
                source=next((s for s in state.get('catalogSources',[]) if '/'+entry['repositoryName'].lower()+'/' in s.get('url','').lower()),None)
                state=merge_catalog(state,source['url'] if source else url,review['content']);state['_revision']=state.get('_revision',0)+1;self.app.write_state(state)
            data['installed'][key]={'entry':entry,'content':review['content'],'plugin':plugin,'installedAt':time.time(),'previous':{k:v for k,v in previous.items() if k!='previous'} if previous else None};data['reviews']={};self.write(data)
        return self.status()
    def remove(self,key):
        with self.app.LOCK:
            data=self.read();entry=data['installed'].get(key)
            if not entry:raise ValueError('This package is managed outside Marketplace. Use Sources & settings or Device catalogs.')
            if entry['entry']['type']=='connector' and any(p['id']==entry['plugin'] and p.get('installed') for p in self.app.addins().status()['packages']):self.app.addins().action('uninstall',plugin=entry['plugin'])
            elif entry['entry']['type']=='device-catalog':
                state=self.app.read_state();repo='/'+entry['entry']['repositoryName'].lower()+'/'
                ids={s['id'] for s in state.get('catalogSources',[]) if repo in s.get('url','').lower()}
                state['catalogSources']=[s for s in state.get('catalogSources',[]) if s['id'] not in ids];state['deviceCatalog']=[m for m in state.get('deviceCatalog',[]) if m.get('catalogId') not in ids];state['_revision']=state.get('_revision',0)+1;self.app.write_state(state)
            del data['installed'][key];self.write(data)
        return self.status()
    def rollback(self,key):
        with self.app.LOCK:
            data=self.read();current=data['installed'].get(key);previous=current.get('previous') if current else None
            if not previous:raise ValueError('No previous installed version is available.')
            entry=previous['entry']
            if entry['type']=='connector':self.app.addins().rollback_repository(current['plugin'],expected_commit=entry['ref'])
            elif entry['type']=='device-catalog':
                state=self.app.read_state();source=next((s for s in state.get('catalogSources',[]) if '/'+entry['repositoryName'].lower()+'/' in s.get('url','').lower()),None)
                url=source['url'] if source else 'https://raw.githubusercontent.com/'+entry['repositoryName']+'/main/'+entry['manifest']
                state=merge_catalog(state,url,previous['content']);state['_revision']=state.get('_revision',0)+1;self.app.write_state(state)
            data['installed'][key]=dict(previous,previous={k:v for k,v in current.items() if k!='previous'});self.write(data)
        return self.status()
    def details(self,key):
        entry=next((p for p in self.status()['packages'] if p['key']==key),None)
        if not entry:raise ValueError('Marketplace package not found.')
        cache_key=entry['repositoryName']+'@'+entry['ref']+'/'+entry['documentation']
        with self.app.LOCK:cached=self.read().get('documents',{}).get(cache_key)
        if cached and time.time()-cached['updated']<21600:return dict(cached,package=entry)
        try:
            readme=raw(entry['repositoryName'],entry['ref'],entry['documentation'],150000).decode('utf-8')
        except (OSError,ValueError,UnicodeError):
            return {'package':entry,'readme':'','error':'Repository documentation could not be loaded. Open the pinned documentation on GitHub or try again later.'}
        result={'readme':readme,'updated':time.time()}
        with self.app.LOCK:
            data=self.read();documents=data.setdefault('documents',{});documents[cache_key]=result
            while len(documents)>30:documents.pop(next(iter(documents)))
            self.write(data)
        return dict(result,package=entry)
