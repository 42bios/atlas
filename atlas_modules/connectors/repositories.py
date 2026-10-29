"""Download a bounded connector package from one commit in a public GitHub repository."""
import hashlib
import json
import math
import re
import urllib.request
import urllib.error
from urllib.parse import urlsplit, quote
from pathlib import PurePosixPath
from .setup import url as validate_url

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('Repository redirects are not accepted.')

def fetch(url, maximum=1000000, token=None, raw=False):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('api.github.com','raw.githubusercontent.com') or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError('Only verified HTTPS GitHub download hosts are accepted.')
    headers={'User-Agent':'Atlas-addins/1','Accept':'application/vnd.github.raw+json' if raw else 'application/vnd.github+json' if parsed.hostname=='api.github.com' else 'application/octet-stream'}
    if token:
        if parsed.hostname!='api.github.com':raise ValueError('Private repository credentials are restricted to the GitHub API.')
        headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=15) as response:
            body=response.read(maximum+1)
            if len(body)>maximum: raise ValueError('Add-in file exceeds the download limit.')
            return body
    except urllib.error.HTTPError as error:
        if error.code==404:raise ValueError('GitHub repository or file not found (404). Check repository access and token permissions.') from None
        raise ValueError('GitHub download rejected. Check public access and GitHub rate limits.') from None
    except OSError: raise ValueError('GitHub download failed. Check repository/ref, public access and GitHub rate limits.') from None

def repository(value):
    if not isinstance(value,str) or len(value)>300: raise ValueError('Provide a public GitHub repository URL.')
    parsed=urlsplit(value.strip());parts=parsed.path.strip('/').split('/')
    if parsed.scheme!='https' or parsed.hostname!='github.com' or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment or len(parts)!=2:
        raise ValueError('Use https://github.com/owner/repository.')
    owner,repo=parts;repo=repo.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}',owner) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',repo) or repo in ('.','..'):
        raise ValueError('Invalid GitHub repository name.')
    return owner+'/'+repo

def parse_manifest(raw):
    data=json.loads(raw)
    allowed={'schemaVersion','id','name','version','description','connectorApi','runtime','entrypoint','files','configuration','credentialRequired'}
    if not isinstance(data,dict) or set(data)-allowed or data.get('schemaVersion')!=1 or data.get('connectorApi')!=1 or data.get('runtime')!='python':
        raise ValueError('Expected schemaVersion 1, connectorApi 1 and runtime python.')
    for key,pattern in [('id',r'[a-z][a-z0-9-]{2,47}'),('version',r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?')]:
        if not isinstance(data.get(key),str) or not re.fullmatch(pattern,data[key]) or len(data[key])>80: raise ValueError('Invalid add-in '+key+'.')
    for key,maximum in [('name',100),('description',1000)]:
        if not isinstance(data.get(key),str) or not data[key].strip() or len(data[key])>maximum: raise ValueError('Invalid add-in '+key+'.')
    files=data.get('files')
    if not isinstance(files,list) or not 1<=len(files)<=30: raise ValueError('Declare 1–30 add-in files.')
    paths=set()
    for file in files:
        if not isinstance(file,dict) or set(file)!={'path','sha256'}:raise ValueError('Each file needs path and sha256.')
        path=file['path'];digest=file['sha256']
        if not isinstance(path,str) or len(path)>180 or not re.fullmatch(r'[A-Za-z0-9_./-]+',path) or any(part in ('','..','.') for part in path.split('/')) or PurePosixPath(path).is_absolute() or PurePosixPath(path).suffix not in ('.py','.json','.md','.txt') or path in paths:
            raise ValueError('Invalid or duplicate package path.')
        if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('Declare a SHA-256 checksum for each file.')
        paths.add(path)
    if data.get('entrypoint') not in paths or not data['entrypoint'].endswith('.py'):raise ValueError('Entrypoint must be a declared Python file.')
    fields=data.get('configuration',[])
    if not isinstance(fields,list) or len(fields)>20:raise ValueError('Declare up to 20 configuration fields.')
    names=set()
    for field in fields:
        if not isinstance(field,dict) or set(field)-{'key','label','type','required','default'}:raise ValueError('Invalid configuration field.')
        if not isinstance(field.get('key'),str) or not re.fullmatch(r'[a-z][A-Za-z0-9_]{0,39}',field['key']) or field['key'] in names:raise ValueError('Configuration keys must be unique.')
        names.add(field['key'])
        if not isinstance(field.get('label'),str) or not 1<=len(field['label'])<=100 or field.get('type') not in ('text','url','number') or type(field.get('required',False)) is not bool:raise ValueError('Unsupported configuration field.')
        if 'default' in field:validate_config_value(field,field['default'])
    if type(data.get('credentialRequired',False)) is not bool:raise ValueError('credentialRequired must be boolean.')
    return data

def validate_config_value(field,value):
    if field['type']=='number':
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1000000000:raise ValueError(field['label']+' must be a finite non-negative number.')
    elif not isinstance(value,str) or len(value)>2000 or '\x00' in value:raise ValueError(field['label']+' must be text up to 2000 characters.')
    if field.get('required') and value=='':raise ValueError(field['label']+' is required.')
    if field['type']=='url' and value:validate_url(value,field['label'])
    return value

def configuration(manifest,values):
    if not isinstance(values,dict) or set(values)-{f['key'] for f in manifest.get('configuration',[])}:raise ValueError('Unknown add-in configuration field.')
    result={}
    for field in manifest.get('configuration',[]):
        value=values.get(field['key'],field.get('default'))
        if value is None:
            if field.get('required'):raise ValueError(field['label']+' is required.')
            continue
        result[field['key']]=validate_config_value(field,value)
    return result

def download(value,ref='',token=None):
    repo=repository(value)
    if not isinstance(ref,str) or len(ref)>150 or '\x00' in ref:raise ValueError('Invalid Git ref.')
    def get(url,maximum=1000000,raw=False):
        return fetch(url,maximum,token=token,raw=raw) if token else fetch(url,maximum)
    if not ref:ref=json.loads(get('https://api.github.com/repos/'+repo))['default_branch']
    commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+quote(ref,safe='')))['sha']
    if not isinstance(commit,str) or not re.fullmatch(r'[a-f0-9]{40}',commit):raise ValueError('GitHub did not return a valid commit.')
    base='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'
    def file_get(path,maximum=1000000):
        if token:return get('https://api.github.com/repos/'+repo+'/contents/'+quote(path,safe='/')+'?ref='+commit,maximum,raw=True)
        return fetch(base+path,maximum)
    try:raw=file_get('atlas-addin.json',60000)
    except ValueError as error:
        if '404' in str(error):raise ValueError('No atlas-addin.json at the selected commit. Choose an Atlas connector repository.') from None
        raise
    manifest=parse_manifest(raw)
    files={};total=0
    for file in manifest['files']:
        content=file_get(file['path']);total+=len(content)
        if total>4000000:raise ValueError('Add-in package must be smaller than 4 MB.')
        if hashlib.sha256(content).hexdigest()!=file['sha256']:raise ValueError('Package checksum mismatch: '+file['path'])
        files[file['path']]=content
    # Namespacing allows other authors to use the same add-in ID without collisions.
    id='repo-'+hashlib.sha256((repo.lower()+':'+manifest['id']).encode()).hexdigest()[:16]
    metadata={'id':id,'name':manifest['name'],'summary':manifest['description'],'version':manifest['version'],'available':True,'repository':'https://github.com/'+repo,'repositoryName':repo,'ref':ref,'commit':commit,'manifest':manifest,'packageHash':hashlib.sha256(raw+b''.join(files[p] for p in sorted(files))).hexdigest()}
    return metadata,files
