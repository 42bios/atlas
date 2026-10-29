import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
import sys
import plugin_api

# The plugin module is tested as an independent adapter, not loaded into Atlas.
PLUGIN = Path(__file__).parent.parent / 'plugins/portainer/collector.py'


class PluginTests(unittest.TestCase):
    def test_scoped_auth(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'keys.json'
            path.write_text(json.dumps({'portainer-main':'a'*40, 'other':'b'*40}))
            with patch.dict(os.environ, {'ATLAS_CONNECTOR_KEYS_FILE':str(path)}):
                self.assertTrue(plugin_api.authorized({'Authorization':'Bearer '+'a'*40},'portainer-main'))
                self.assertFalse(plugin_api.authorized({'Authorization':'Bearer '+'a'*40},'other'))
                self.assertFalse(plugin_api.authorized({},'portainer-main'))

    @unittest.skipUnless(PLUGIN.exists(), 'Plugin sources not mounted')
    def test_portainer_stacks_roles_and_dependencies(self):
        spec = importlib.util.spec_from_file_location('portainer_collector', PLUGIN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data={'/api/endpoints':[{'Id':1,'Name':'Docker','Type':1}],'/api/endpoints/1/docker/images/json':[{'Id':'sha256:db','RepoTags':None,'RepoDigests':['postgres@sha256:digest']}], '/api/stacks':[{'Id':5,'Name':'photos','EndpointId':1}], '/api/endpoints/1/docker/containers/json?all=1':[
            {'Id':'web','Names':['/photos-web'],'Image':'caddy:2','Labels':{'com.docker.compose.project':'photos','com.docker.compose.service':'web','com.docker.compose.depends_on':'db:service_started','secret':'DO NOT EXPORT'},'Ports':[]},
            {'Id':'db','Names':['/photos-db'],'Image':'sha256:db','Labels':{'com.docker.compose.project':'photos','com.docker.compose.service':'db'},'Ports':[]}]}
        result=module.collect(data.__getitem__,'portainer-main')
        self.assertEqual(result['services'][0]['kind'],'Stack')
        self.assertEqual(result['services'][1]['role'],'Reverse proxy')
        self.assertEqual(result['services'][2]['role'],'Database')
        self.assertEqual(result['services'][1]['host'],result['services'][0]['id'])
        self.assertEqual(result['links'][0]['type'],'Starts after')
        self.assertNotIn('DO NOT EXPORT',json.dumps(result))
        self.assertEqual(module.role('postgres',{'atlas.role':'Application'}),('Application','Label'))

    @unittest.skipUnless(PLUGIN.exists(), 'Plugin sources not mounted')
    def test_tls_pin_rejects_before_credentials_are_sent(self):
        collector_spec=importlib.util.spec_from_file_location('collector',PLUGIN)
        collector=importlib.util.module_from_spec(collector_spec)
        collector_spec.loader.exec_module(collector)
        spec=importlib.util.spec_from_file_location('portainer_runtime',PLUGIN.with_name('runtime.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'collector':collector}):
            spec.loader.exec_module(module)
        connection=MagicMock()
        connection.sock.getpeercert.return_value=b'wrong-certificate'
        with patch.dict(os.environ,{'PORTAINER_URL':'https://example.test:9443','PORTAINER_TLS_SHA256':'a'*64}), patch.object(module.http.client,'HTTPSConnection',return_value=connection):
            with self.assertRaises(ValueError):
                module.request('https://example.test:9443/api/endpoints',{'X-API-Key':'sensitive'})
        connection.request.assert_not_called()
        connection.close.assert_called_once()
