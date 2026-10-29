"""Exercise the actual HTTP handler against an isolated temporary SQLite database."""
import copy
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server
from connector_engine import SCHEMA

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_db = server.DB
        server.DB = Path(cls.temp.name) / 'atlas.db'
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        server.DB = cls.old_db
        cls.temp.cleanup()

    def setUp(self):
        server.write_state({**server.demo(), 'demo': False, '_revision': 0})

    def test_protected_backup_endpoints_and_rehearsal(self):
        self.assertEqual(self.request('/api/v1/backups','POST',{'action':'create'},{'Origin':'https://other.test'})[0],403)
        status,result=self.request('/api/v1/backups','POST',{'action':'create'})
        self.assertEqual(status,200);self.assertTrue(result['valid']);name=result['name']
        self.assertNotIn('credential',json.dumps(result))
        self.assertIn(name,[x['name'] for x in self.request('/api/v1/backups')[1]['backups']])
        status,result=self.request('/api/v1/backups','POST',{'action':'rehearse','name':name})
        self.assertEqual(status,200);self.assertTrue(result['rehearsed'])
        self.assertEqual(self.request('/api/v1/backups','POST',{'action':'validate','name':'../../private'})[0],400)
        self.assertEqual(self.request('/api/v1/backups','GET',headers={'Authorization':'Bearer awj_invalid'})[0],403)

    def test_marketplace_http_routes_origin_and_bounded_requests(self):
        status,body=self.request('/api/v1/marketplace')
        self.assertEqual(status,200);self.assertIn('sources',body)
        self.assertEqual(self.request('/api/v1/icon-library'),(200,[]))
        path='/api/v1/marketplace/source'
        payload={'action':'add','name':'HTTP test','repository':'https://github.com/example/catalog'}
        self.assertEqual(self.request(path,'POST',payload,{'Origin':'https://other.test'})[0],403)
        status,result=self.request(path,'POST',payload);self.assertEqual(status,200)
        source=next(s for s in result['sources'] if s['name']=='HTTP test')
        self.assertEqual(self.request('/api/v1/marketplace','GET',headers={'Authorization':'Bearer awj_invalid'})[0],403)
        self.assertEqual(self.request('/api/v1/icon-library','GET',headers={'Authorization':'Bearer awj_invalid'})[0],403)
        self.assertEqual(self.request('/api/v1/marketplace/install','POST',{'review':'expired','trust':'example/catalog'})[0],400)
        self.assertEqual(self.request(path,'POST',{'action':'remove','id':source['id']})[0],200)

    def test_private_github_access_api(self):
        path='/api/v1/addins/repository/access'
        payload={'token':'private-test-token','repositories':['example/private']}
        self.assertEqual(self.request(path,'POST',payload,{'Origin':'https://other.test'})[0],403)
        status,result=self.request(path,'POST',payload)
        self.assertEqual(status,200)
        self.assertTrue(result['configured'])
        self.assertNotIn('private-test-token',json.dumps(self.request('/api/v1/addins')[1]))
        self.assertEqual(self.request(path,'POST',{'token':'','repositories':['example/private']})[0],200)
        self.assertEqual(self.request(path,'POST',{'remove':True})[0],200)
        self.assertFalse(self.request('/api/v1/addins')[1]['githubAccess']['configured'])

    def request(self, path, method='GET', data=None, headers=None):
        payload = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=payload, method=method,
                                     headers={'Content-Type':'application/json', **(headers or {})})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            if 'application/json' in response.headers.get('Content-Type', ''):
                body = json.loads(body)
            return response.status, body

    def test_builtin_features_are_permanent(self):
        before=self.request('/api/state')[1]
        with server.connection() as con:
            con.execute('CREATE TABLE IF NOT EXISTS feature_state (id INTEGER PRIMARY KEY, revision INTEGER, disabled TEXT)')
            con.execute('INSERT OR REPLACE INTO feature_state VALUES (1, 3, ?)', (json.dumps(['ipam','applications']),))
        manifest=self.request('/api/v1/modules')[1]
        self.assertTrue(all(m['enabled'] and m['required'] for m in manifest['modules']))
        self.assertEqual(self.request('/api/v1/modules','POST',{'id':'ipam','enabled':False,'revision':0})[0],404)
        self.assertEqual(self.request('/api/v1/ipam')[0],200)
        self.assertEqual(self.request('/api/state')[1],before)
        html=self.request('/')[1].decode()
        self.assertIn('<script src="/modules/ipam/',html)
        self.assertNotIn('/module-information.js',html)
        self.assertEqual(self.request('/modules/ipam/ipam.js')[0],200)

    def test_repository_install_configure_and_scoped_runner_import(self):
        import hashlib
        import time
        from atlas_modules.connectors import repositories
        from test_addin_repositories import MANIFEST, SHA
        code = b"import json,os,urllib.request\nsource=os.environ['CONNECTOR_ID']\nheaders={'Authorization':'Bearer '+open(os.environ['ATLAS_TOKEN_FILE']).read().strip(),'Content-Type':'application/json'}\npayload={'schemaVersion':1,'connector':source,'devices':[{'id':'repository-device','name':'Repository worker device','kind':'Server','height':1,'ports':0}],'services':[],'networks':[],'links':[]}\nrequest=urllib.request.Request(os.environ['ATLAS_URL']+'/api/v1/connectors/snapshot',data=json.dumps(payload).encode(),headers=headers)\nwith urllib.request.urlopen(request) as response: response.read()\n"
        manifest={**MANIFEST,'files':[{'path':'connector.py','sha256':hashlib.sha256(code).hexdigest()}]}
        def downloaded(url,maximum=1000000):
            if url.endswith('/commits/main'):return json.dumps({'sha':SHA}).encode()
            if url.endswith('/atlas-addin.json'):return json.dumps(manifest).encode()
            if url.endswith('/connector.py'):return code
            return b'{"default_branch":"main"}'
        with patch.object(repositories,'fetch',side_effect=downloaded):
            status,review=self.request('/api/v1/addins/repository/preview','POST',{'url':'https://github.com/example/connector'})
        self.assertEqual(status,200)
        self.assertEqual(self.request('/api/v1/addins/repository/install','POST',{'review':review['review'],'trust':'wrong'})[0],400)
        status,result=self.request('/api/v1/addins/repository/install','POST',{'review':review['review'],'trust':'example/connector'})
        self.assertEqual(status,200)
        status,result=self.request('/api/v1/addins/configure','POST',{'plugin':result['plugin'],'name':'Repository fixture','credential':'test-credential','config':{'upstreamUrl':'https://example.test'}})
        self.assertEqual(status,200)
        manager=server.addins();old_url=manager.atlas_url;manager.atlas_url=self.base
        from types import SimpleNamespace
        import threading
        class FixtureJob:
            token='awj_fixture'
            output=bytearray()
            def launch(self):pass
            def wait(job,timeout):
                headers={'Authorization':'Bearer '+job.token}
                source=next(x['source'] for x in manager.status()['instances'] if x['id']==result['instance'])
                snapshot={'schemaVersion':1,'connector':source,'devices':[{'id':'repository-device','name':'Repository worker device','kind':'Server','ports':0}],'services':[],'networks':[],'links':[]}
                status,_=self.request('/api/v1/connectors/snapshot','POST',snapshot,headers)
                return 0 if status==200 else 1
            def cleanup(self):pass
        try:
            with patch.object(manager.executor,'start',return_value=FixtureJob()):
                self.assertEqual(self.request('/api/v1/addins/action','POST',{'action':'run','id':result['instance']})[0],200)
                for _ in range(200):
                    instance=next(x for x in manager.status()['instances'] if x['id']==result['instance'])
                    if not instance['running']:break
                    time.sleep(.01)
            self.assertEqual(instance['result'],'Import completed')
            self.assertTrue(any(x['name']=='Repository worker device' for x in self.request('/api/state')[1]['devices']))
            self.assertEqual(self.request('/api/state',headers={'Authorization':'Bearer awj_fixture'})[0],403)
        finally:manager.atlas_url=old_url

    def test_module_manifest_and_domain_routes(self):
        status,manifest=self.request('/api/v1/modules')
        self.assertEqual(status,200)
        self.assertEqual(manifest['schemaVersion'],1)
        self.assertEqual(len(manifest['modules']),10)
        for route,keys in [('/api/v1/hardware',('devices','racks')),('/api/v1/applications',('services',)),('/api/v1/ipam',('networks','addresses')),('/api/v1/connections',('links',)),('/api/v1/topology',('devices','services','links','racks')),('/api/v1/catalogs',('deviceCatalog','catalogSources'))]:
            status,body=self.request(route)
            self.assertEqual(status,200)
            self.assertEqual(set(body),set(keys))
        self.assertEqual(self.request('/api/v1/hardware','POST',{})[0],404)

    def test_static_routes_and_health(self):
        for path in ('/', '/app.js', '/theme.css', '/patchpanel-24-1u.svg', '/catalog.example.json', '/api/connectors', '/api/connector-schema'):
            self.assertEqual(self.request(path)[0], 200, path)

    def test_connector_setup_is_read_only_and_returns_a_real_package(self):
        import io
        import zipfile
        before=self.request('/api/state')[1]
        status, available=self.request('/api/v1/connector-packages')
        self.assertEqual(status,200)
        self.assertFalse(next(p for p in available if p['id']=='unifi')['available'])
        payload={'plugin':'portainer','connector':'portainer-test','atlasUrl':'http://192.0.2.1:8097','upstreamUrl':'https://example.test:9443'}
        status, preview=self.request('/api/v1/connector-setup/preview','POST',payload)
        self.assertEqual(status,200)
        self.assertIn('CONNECTOR_ID=portainer-test',preview['environment'])
        status, body=self.request('/api/v1/connector-setup/package','POST',payload)
        self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            self.assertIn('plugins/portainer/compose.yaml',z.namelist())
        from urllib.parse import urlencode
        status, direct=self.request('/api/v1/connector-setup/package?'+urlencode({'configuration':json.dumps(payload)}))
        self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(direct)) as z:
            self.assertIn('plugins/portainer/.env',z.namelist())
        self.assertEqual(self.request('/api/state')[1],before)

    def test_native_addin_credential_redaction_scoped_import_and_retained_inventory(self):
        self.assertEqual(self.request('/api/v1/addins/action','POST',{'action':'install','plugin':'portainer'})[0],400)
        # Existing legacy installations remain supported until explicitly migrated.
        server.addins().install('portainer')
        payload={'plugin':'portainer','name':'Native test','upstreamUrl':'https://example.test:9443','credential':'private-test-credential'}
        status, result=self.request('/api/v1/addins/configure','POST',payload)
        self.assertEqual(status,200)
        id=result['instance'];public=self.request('/api/v1/addins')[1]
        self.assertNotIn('private-test-credential',json.dumps(public))
        instance=next(x for x in public['instances'] if x['id']==id)
        from types import SimpleNamespace
        token='awj_native_fixture';server.addins().jobs[id]=SimpleNamespace(token=token,terminate=lambda:None)
        headers={'Authorization':'Bearer '+token}
        snapshot={'schemaVersion':1,'connector':instance['source'],'devices':[{'id':'native-device','name':'Native device','kind':'Server'}],'services':[],'networks':[],'links':[]}
        self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',snapshot,headers)[0],200)
        self.assertEqual(self.request('/api/v1/addins/action','POST',{'action':'disable','id':id})[0],200)
        self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',snapshot,headers)[0],403)
        self.assertEqual(self.request('/api/v1/addins/action','POST',{'action':'uninstall','plugin':'portainer'})[0],200)
        self.assertTrue(any(x['name']=='Native device' for x in self.request('/api/state')[1]['devices']))

    def test_addin_configuration_rejects_foreign_origin(self):
        self.assertEqual(self.request('/api/v1/addins/action','POST',{'action':'install','plugin':'portainer'},{'Origin':'https://elsewhere.test'})[0],403)

    def test_connector_setup_rejects_foreign_origins_credentials_and_unknown_plugins(self):
        payload={'plugin':'snmp','connector':'snmp-test','atlasUrl':'http://192.0.2.1:8097','targets':['192.0.2.0/24']}
        self.assertEqual(self.request('/api/v1/connector-setup/package','POST',payload,{'Origin':'https://elsewhere.test'})[0],403)
        for changed in ({'community':'secret'},{'plugin':'community-image'},{'targets':['0.0.0.0/0']}):
            self.assertEqual(self.request('/api/v1/connector-setup/preview','POST',{**payload,**changed})[0],400)

    def test_write_read_revision_and_conflict(self):
        _, state = self.request('/api/state')
        stale = copy.deepcopy(state)
        state['services'].append({'id':'qa-app','name':'QA app','kind':'Service','host':'docker','url':'http://example.test'})
        status, result = self.request('/api/state', 'PUT', state)
        self.assertEqual(status,200)
        self.assertEqual(result['revision'],1)
        self.assertEqual(self.request('/api/state','PUT',stale)[0],409)
        _, saved = self.request('/api/state')
        self.assertEqual(saved['services'][-1]['id'],'qa-app')

    def test_rejected_validation_is_atomic(self):
        _, original = self.request('/api/state')
        invalid = copy.deepcopy(original)
        invalid['devices'][0]['unit']=99
        self.assertEqual(self.request('/api/state','PUT',invalid)[0],400)
        self.assertEqual(self.request('/api/state')[1],original)
        invalid = copy.deepcopy(original)
        invalid['devices'][0]['ip']=None
        self.assertEqual(self.request('/api/state','PUT',invalid)[0],400)

    def test_origin_rejection(self):
        self.assertEqual(self.request('/api/state','PUT',server.demo(),{'Origin':'http://outside.test'})[0],403)
        self.assertEqual(self.request('/api/sync','POST',{}, {'Origin':'http://outside.test'})[0],403)

    def test_connector_merge_idempotency(self):
        self.assertEqual(self.request('/api/import','POST',SCHEMA)[0],200)
        once = self.request('/api/state')[1]
        self.assertEqual(self.request('/api/import','POST',SCHEMA)[0],200)
        twice = self.request('/api/state')[1]
        for key in ('devices','services','links'):
            self.assertEqual(len(once[key]),len(twice[key]))
        self.assertGreater(twice['_revision'],once['_revision'])

    def test_catalog_and_backup_preserve_inventory(self):
        template={'id':'test','name':'Test switch','kind':'Switch','height':1,'ports':24}
        with patch('device_catalog.fetch_catalog',return_value=('https://raw.githubusercontent.com/example/devices/main/catalog.json',[template])):
            self.assertEqual(self.request('/api/catalog/import','POST',{'url':'https://github.com/example/devices'})[0],200)
        current = self.request('/api/state')[1]
        self.assertEqual(len(current['devices']),7)
        self.assertEqual(current['deviceCatalog'][0]['modelId'],template['id'])
        self.assertEqual(len(current['catalogSources']),1)
        self.assertEqual(self.request('/api/state','PUT',current)[0],200)
        self.assertEqual(self.request('/api/state')[1]['deviceCatalog'],current['deviceCatalog'])

    def test_malformed_imports_return_errors(self):
        for data in ([],{'url':None},{'url':123},{'url':'http://localhost/file'}):
            self.assertEqual(self.request('/api/catalog/import','POST',data)[0],400)
        self.assertEqual(self.request('/api/import','POST',{})[0],400)
        self.assertEqual(self.request('/api/stencils/import-vssx','POST',{})[0],400)
        self.assertEqual(self.request('/api/no-such-route','POST',{})[0],404)

    def test_demo_import_requires_explicit_reset(self):
        server.write_state(server.demo())
        self.assertEqual(self.request('/api/import','POST',SCHEMA)[0],400)
        self.assertEqual(self.request('/api/sync','POST',{})[0],400)
        self.assertTrue(self.request('/api/state')[1]['demo'])

    def test_plugin_rest_auth_atomicity_and_status(self):
        keyfile = Path(self.temp.name)/'connector-keys.json'
        keyfile.write_text(json.dumps({'my-source':'x'*40}))
        with patch.dict(os.environ, {'ATLAS_CONNECTOR_KEYS_FILE':str(keyfile)}):
            auth = {'Authorization':'Bearer '+'x'*40}
            before = self.request('/api/state')[1]
            self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',SCHEMA)[0],403)
            self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',{**SCHEMA,'connector':'other'},auth)[0],403)
            self.assertEqual(self.request('/api/v1/connectors/status','POST',{'connector':'my-source','phase':'imported','plugin':'fixture','version':'1'},auth)[0],200)
            self.assertEqual(self.request('/api/state')[1],before)
            self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',SCHEMA,auth)[0],200)
            saved = self.request('/api/state')[1]
            invalid={**SCHEMA,'services':[{'id':'bad','name':'Bad','kind':'Virtual machine','host':'not-existing'}]}
            self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',invalid,auth)[0],400)
            self.assertEqual(self.request('/api/state')[1],saved)
            server.write_state(server.demo())
            self.assertEqual(self.request('/api/v1/connectors/snapshot','POST',SCHEMA,auth)[0],409)
            self.assertEqual(self.request('/api/v1/connector-contract')[0],200)
