#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$project_dir"
docker build -f runner/Worker.Dockerfile -t atlas-connector-worker:1 .
python3 - "$project_dir" <<'PY'
import os
import json
from pathlib import Path
import subprocess
import sys
root=Path(sys.argv[1]);queue=root/'worker-jobs';queue.mkdir(exist_ok=True)
socket=Path('/var/run/docker.sock')
if not socket.exists():raise SystemExit('Run setup on the Docker host with /var/run/docker.sock available.')
# Bind mounts hide the image's owned /data directory. Prepare only a new or
# empty data directory; never recursively change an existing inventory.
data=root/'data';data.mkdir(exist_ok=True)
if data.stat().st_uid!=1000 and not any(data.iterdir()):
 subprocess.run(['docker','run','--rm','--network','none','--user','0','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','FOWNER','--mount','type=bind,src='+str(data)+',dst=/data','--entrypoint','python','atlas-connector-worker:1','-c','import os;os.chown("/data",1000,1000);os.chmod("/data",0o700)'],check=True)
(root/'connectors').mkdir(exist_ok=True)
if queue.stat().st_uid!=1000:
 subprocess.run(['docker','run','--rm','--network','none','--user','0','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','FOWNER','--mount','type=bind,src='+str(queue)+',dst=/jobs','--entrypoint','python','atlas-connector-worker:1','-c','import os;os.chown("/jobs",1000,1000);os.chmod("/jobs",0o700)'],check=True)
else:queue.chmod(0o700)
env=root/'.env';lines=env.read_text().splitlines() if env.exists() else []
current={line.split('=',1)[0]:line.split('=',1)[1] for line in lines if '=' in line and not line.startswith('#')}
network=os.environ.get('ATLAS_WORKER_NETWORK',current.get('ATLAS_WORKER_NETWORK','atlas-connector-workers'))
if subprocess.run(['docker','network','inspect',network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 subprocess.run(['docker','network','create','--label','atlas.connector-workers=true',network],check=True)
inspected=json.loads(subprocess.check_output(['docker','network','inspect',network],text=True))[0]
subnets=' '.join(p['Subnet'] for p in inspected['IPAM']['Config'] if p.get('Subnet'))
values={'ATLAS_WORKER_HOST_QUEUE':str(queue),'ATLAS_DOCKER_GID':str(socket.stat().st_gid),'ATLAS_WORKER_NETWORK':network,'ATLAS_WORKER_SUBNETS':subnets}
if not current.get('ATLAS_CONNECTOR_CALLBACK_URL'):values['ATLAS_CONNECTOR_CALLBACK_URL']='http://atlas-connector-callback:8765'
lines=[line for line in lines if not any(line.startswith(k+'=') for k in values)]
lines.extend(k+'='+v for k,v in values.items());env.write_text('\n'.join(lines)+'\n');env.chmod(0o600)
print('Private worker queue, Docker network and runner settings prepared.')
PY
docker compose up -d --build atlas connector-runner
