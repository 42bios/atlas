"""Worker bootstrap: copy only this job's configuration to private tmpfs."""
import json
import os
from pathlib import Path
import runpy
import shutil
import sys

job=Path('/job');request=json.loads((job/'request.json').read_text())
work=Path('/work');work.mkdir(exist_ok=True)
shutil.copytree(job/'secrets',work/'secrets')
os.environ.clear();os.environ.update(PATH='/usr/local/bin:/usr/bin:/bin',**request['environment'])
package=job/'package';sys.path[:0]=[str(package),str(package/'plugins')]
entry=(package/request['entrypoint']).resolve()
if not entry.is_relative_to(package):raise ValueError('Invalid worker entrypoint')
sys.path.insert(0,str(entry.parent))
runpy.run_path(str(entry),run_name='__main__')
