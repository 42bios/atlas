"""Homelab Atlas: a local, standard-library-only inventory application."""
import argparse
import json
import os
import connector_engine
from addin_manager import AddinManager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('ATLAS_DB', str(ROOT / 'data' / 'atlas.db')))
from atlas_core.sample import demo
from atlas_core.runtime import Application
from atlas_core.frontend import plugin_script, active_assets
from atlas_modules.registry import registry
from atlas_modules.connectors.download import connector_package_response
from urllib.parse import urlsplit
from atlas_modules.connectors.execution import worker_request

application = Application(lambda: DB, registry, AddinManager, connector_engine)
LOCK = application.LOCK
ADDIN_MANAGERS = application.managers
# Compatibility surface for adapters and tests; modules receive Application explicitly.
addins = application.addins
connection = application.connection
read_state = application.read_state
validate = application.validate
write_state = application.write_state
sync_snapshots = application.sync_snapshots

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)
    @property
    def application(self): return application
    def json_response(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers(); self.wfile.write(data)
    def connector_package_response(self, payload):
        return connector_package_response(self, payload, self.application)
    def reject_worker_access(self):
        if worker_request(self.client_address[0],self.headers):
            path=urlsplit(self.path).path
            if self.command!='POST' or path not in ('/api/v1/connectors/snapshot','/api/v1/connectors/status'):
                self.json_response(403,{'error':'Connector workers can only submit their own snapshot and status.'})
                return True
        return False
    def do_GET(self):
        if self.reject_worker_access():return
        path = urlsplit(self.path).path
        if path=='/api/v1/modules': return self.json_response(200,self.application.features().public())
        if path.startswith('/help/'):
            name = path.removeprefix('/help/')
            allowed = {p.name for p in (ROOT/'docs/handbook').glob('*.md')}
            if name not in allowed:return self.json_response(404,{'error':'Documentation page not found'})
            data=(ROOT/'docs/handbook'/name).read_bytes()
            self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if registry.dispatch('GET',self,self.application): return
        if path in ('/','/index.html'):
            template=(ROOT/'static/index.html').read_text()
            configuration=self.application.features().public()
            manifest=json.dumps(configuration).replace('<','\u003c')
            scripts='<script src="/core/module-registry.js?v=workflow-20261029b"></script><script>AtlasModules.configure('+manifest+')</script><script src="/core/plugin-host.js?v=workflow-20261029b"></script><script>AtlasPluginHost.configure('+manifest+'.modules)</script>'
            scripts+=''.join('<script src="'+a['path']+'?v=workflow-20261029b"></script>' for a in active_assets(configuration))
            data=template.replace('<!-- ATLAS_MODULE_ASSETS -->',scripts).encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.write(data);return
        # Legacy static URLs remain usable by existing bookmarks and cached clients.
        alias=next((a['path'] for a in registry.assets if a.get('legacy')==path),None)
        if alias:self.path=alias
        asset=next((a for a in registry.assets if a['path']==urlsplit(self.path).path),None)
        if asset:
            manifest=self.application.features().public()
            if asset not in active_assets(manifest):return self.json_response(409,{'error':'Plugin is disabled','module':asset['owner']})
            bindings=registry.manifests[asset['owner']]['bindings'][asset['path']]
            data=plugin_script((ROOT/'static'/asset['path'].lstrip('/')).read_text(),asset['owner'],bindings).encode()
            self.send_response(200);self.send_header('Content-Type','text/javascript; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.write(data);return
        return super().do_GET()
    def do_POST(self):
        if self.reject_worker_access():return
        if not registry.dispatch('POST',self,self.application):self.json_response(404,{'error':'Not found'})
    def do_PUT(self):
        if self.reject_worker_access():return
        if not registry.dispatch('PUT',self,self.application):self.json_response(404,{'error':'Not found'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    read_state()
    print(f'Atlas is available at http://{args.host}:{args.port}', flush=True)
    http = ThreadingHTTPServer((args.host, args.port), Handler)
    addins().atlas_url = 'http://127.0.0.1:'+str(args.port)
    addins().start_scheduler()
    http.serve_forever()
