"""Trusted Docker controller. No HTTP API, shell commands or caller-supplied mounts."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

QUEUE=Path(os.environ.get('ATLAS_WORKER_QUEUE','/jobs'))
HOST_QUEUE=Path(os.environ['ATLAS_WORKER_HOST_QUEUE'])
IMAGE=os.environ.get('ATLAS_WORKER_IMAGE','atlas-connector-worker:1')
NETWORK=os.environ.get('ATLAS_WORKER_NETWORK','atlas-connector-workers')
JOBS={};STOP=threading.Event();SUBNETS=[]
OWNER=hashlib.sha256(str(HOST_QUEUE).encode()).hexdigest()[:16]


def atomic(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data));tmp.chmod(0o600)
    os.replace(tmp,path)


def command(*args,**kwargs):return subprocess.run(['docker',*args],capture_output=True,text=True,timeout=15,**kwargs)


def worker_args(job):
    if not re.fullmatch(r'[a-f0-9]{32}',job.name):raise ValueError('Invalid job identity')
    # This bind is always exactly one job. Never accept paths or Docker flags in a request.
    return ['docker','run','--name','atlas-worker-'+job.name,'--label','atlas.connector-worker=true','--label','atlas.job='+job.name,'--label','atlas.runner-owner='+OWNER,
        '--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges:true','--pids-limit','64',
        '--memory','256m','--memory-swap','256m','--cpus','1','--init','--network',NETWORK,
        '--log-driver','none','--ulimit','nofile=256:256','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,uid=1000,gid=1000',
        '--tmpfs','/work:rw,noexec,nosuid,size=16m,uid=1000,gid=1000',
        '--mount','type=bind,src='+str(HOST_QUEUE/job.name)+',dst=/job,readonly',IMAGE]


def validate(job):
    if job.is_symlink():raise ValueError('Symlink job rejected')
    request=job/'request.json'
    if request.stat().st_size>60000:raise ValueError('Invalid job request')
    data=json.loads(request.read_text())
    if not re.fullmatch(r'[a-f0-9]{32}',data.get('instance','')):raise ValueError('Invalid instance identity')
    if set(data)!={'schemaVersion','source','instance','entrypoint','environment','created'} or data['schemaVersion']!=1:raise ValueError('Invalid job schema')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',data['source']):raise ValueError('Invalid connector source')
    entry=Path(data['entrypoint'])
    if entry.is_absolute() or '..' in entry.parts or entry.suffix!='.py':raise ValueError('Invalid job entrypoint')
    if any(p.is_symlink() for p in job.rglob('*')):raise ValueError('Symlink content rejected')
    if not (job/'package'/entry).is_file():raise ValueError('Missing entrypoint')
    if not isinstance(data['environment'],dict) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]*',k) or not isinstance(v,str) or len(v)>5000 for k,v in data['environment'].items()):raise ValueError('Invalid job environment')
    if time.time()-data['created']>120:raise ValueError('Expired queued job')
    return data


def run(job):
    name='atlas-worker-'+job.name;output=bytearray();process=None
    try:
        validate(job)
        args=worker_args(job);args[1]='create'
        created=subprocess.run(args,capture_output=True,text=True,timeout=30)
        container_id=created.stdout.strip()
        if created.returncode or not re.fullmatch(r'[a-f0-9]{64}',container_id):raise ValueError('Worker container creation failed')
        atomic(job/'running.json',{'started':time.time(),'mode':'isolated-containers','containerId':container_id})
        process=subprocess.Popen(['docker','start','--attach',name],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        def drain():
            while chunk:=process.stdout.read(1024):
                if len(output)<16384:output.extend(chunk[:16384-len(output)])
            process.stdout.close()
        reader=threading.Thread(target=drain,daemon=True);reader.start()
        deadline=time.monotonic()+3600
        cancelled=False
        while process.poll() is None:
            if STOP.is_set() or (job/'cancel.json').exists() or time.monotonic()>deadline:
                command('rm','-f',name);cancelled=True;break
            time.sleep(.2)
        try:code=process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait();code=-1
        reader.join(timeout=2)
        if cancelled:code=-1
        atomic(job/'result.json',{'code':code,'output':output.decode('utf-8',errors='replace')[:16384],'finished':time.time()})
    except Exception:
        if job.exists():atomic(job/'result.json',{'code':1,'output':'Isolated runner could not start the job','finished':time.time()})
    finally:
        command('rm','-f',name)
        JOBS.pop(job.name,None)


def health():
    inspected=command('network','inspect',NETWORK)
    if inspected.returncode:
        created=command('network','create','--label','atlas.connector-workers=true',NETWORK)
        if created.returncode:raise ValueError('Worker network unavailable')
        inspected=command('network','inspect',NETWORK)
    global SUBNETS
    subnets=[x['Subnet'] for x in json.loads(inspected.stdout)[0]['IPAM']['Config'] if x.get('Subnet')]
    SUBNETS=subnets
    ready=command('image','inspect',IMAGE).returncode==0
    atomic(QUEUE/'runner.json',{'ready':ready,'updated':time.time(),'workerSubnets':subnets,'mode':'isolated-containers'})
    return ready


def main():
    if not HOST_QUEUE.is_absolute() or str(HOST_QUEUE)=='/' or ',' in str(HOST_QUEUE):raise ValueError('Set an absolute private worker-jobs host directory using the setup script')
    QUEUE.mkdir(parents=True,exist_ok=True)
    # A controller restart cannot leave untracked workers holding live credentials.
    leftover=command('ps','-aq','--filter','label=atlas.connector-worker=true','--filter','label=atlas.runner-owner='+OWNER)
    if leftover.stdout.strip():command('rm','-f',*leftover.stdout.split())
    for job in QUEUE.iterdir():
        if re.fullmatch(r'[a-f0-9]{32}',job.name) and (job/'running.json').exists() and not (job/'result.json').exists():
            atomic(job/'result.json',{'code':1,'output':'Previous isolated import interrupted','finished':time.time()})
    while not STOP.is_set():
        try:
            if health():
                for job in QUEUE.iterdir():
                    if len(JOBS)>=2:break
                    if re.fullmatch(r'[a-f0-9]{32}',job.name) and job.is_dir() and (job/'ready.json').exists() and not (job/'result.json').exists() and job.name not in JOBS:
                        thread=threading.Thread(target=run,args=(job,),daemon=True);JOBS[job.name]=thread;thread.start()
        except (OSError,ValueError,subprocess.SubprocessError):
            atomic(QUEUE/'runner.json',{'ready':False,'updated':time.time(),'workerSubnets':SUBNETS,'mode':'isolated-containers'})
        STOP.wait(2)
    for thread in list(JOBS.values()):thread.join(timeout=20)
    atomic(QUEUE/'runner.json',{'ready':False,'updated':time.time(),'workerSubnets':SUBNETS,'mode':'isolated-containers'})

if __name__=='__main__':
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:STOP.set())
    main()
