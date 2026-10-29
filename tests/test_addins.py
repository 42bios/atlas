import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from addin_manager import AddinManager

class AddinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.manager=AddinManager(Path(self.temp.name)/'addins')
        self.manager.install('portainer')
    def tearDown(self):self.temp.cleanup()
    def config(self,**extra):return {'plugin':'portainer','name':'Test Portainer','upstreamUrl':'https://example.test:9443','credential':'private-upstream-token',**extra}
    def test_install_configure_redact_and_retain_credential_on_edit(self):
        id=self.manager.configure(self.config())
        data=self.manager.status(); x=data['instances'][0]
        self.assertNotIn('private-upstream-token',json.dumps(data))
        self.assertTrue(x['credentialsConfigured'])
        self.manager.configure(self.config(id=id,credential='',name='Updated'))
        self.assertEqual((self.manager.root/'instances'/id/'credential').read_text(),'private-upstream-token')
        self.assertTrue((self.manager.root/'packages/portainer/plugins/portainer/runtime.py').exists())
        self.assertEqual((self.manager.root/'instances'/id/'credential').stat().st_mode&0o777,0o600)
    def test_scoped_authorization_and_disable(self):
        id=self.manager.configure(self.config());source=self.manager.status()['instances'][0]['source']
        from types import SimpleNamespace
        token='awj_fixture';self.manager.jobs[id]=SimpleNamespace(token=token,terminate=lambda:None)
        self.assertTrue(self.manager.authorized({'Authorization':'Bearer '+token},source))
        self.assertFalse(self.manager.authorized({'Authorization':'Bearer '+token},'other-source'))
        self.manager.action('disable',id);self.assertFalse(self.manager.authorized({'Authorization':'Bearer '+token},source))
        with self.assertRaises(ValueError):self.manager.run(id)
        self.manager.action('enable',id);self.assertTrue(self.manager.authorized({'Authorization':'Bearer '+token},source))
    def test_adoption_preserves_source_id_and_rejects_other_plugin(self):
        reports=[{'connector':'portainer-main','plugin':'portainer'}]
        id=self.manager.configure(self.config(adoptSource='portainer-main'),reports)
        self.assertEqual(self.manager.status()['instances'][0]['source'],'portainer-main')
        with self.assertRaises(ValueError):self.manager.configure(self.config(adoptSource='portainer-main'),reports)
        with self.assertRaises(ValueError):self.manager.configure(self.config(adoptSource='snmp-main'),reports)
    def test_uninstall_removes_private_files_and_revokes_auth(self):
        id=self.manager.configure(self.config());self.manager.action('uninstall',plugin='portainer')
        self.assertEqual(self.manager.status()['instances'],[])
        self.assertFalse((self.manager.root/'instances'/id).exists())
        self.assertFalse(self.manager.status()['packages'][0]['installed'])
        self.assertFalse(self.manager.authorized({'Authorization':'Bearer x'},'invalid'))
    def test_worker_gets_only_own_configuration(self):
        id=self.manager.configure(self.config());x=self.manager.status()['instances'][0]
        with patch.dict('os.environ',{'ATLAS_CONNECTOR_KEYS_FILE':'/all-source-keys','OTHER_SECRET':'private'}):env=self.manager._environment(x)
        self.assertNotIn('OTHER_SECRET',env);self.assertNotIn('ATLAS_CONNECTOR_KEYS_FILE',env)
        self.assertEqual(env['RUN_ONCE'],'true')
        self.assertEqual(env['CONNECTOR_ID'],x['source'])
    def test_validation_before_writing_credentials(self):
        for extra in ({'interval':1},{'credential':''},{'upstreamUrl':'http://example.test'},{'id':'../../escape'},{'plugin':'unifi'}):
            with self.assertRaises(ValueError):self.manager.configure(self.config(**extra))
        self.assertEqual(self.manager.status()['instances'],[])
    def test_snmp_v3_accepts_formatted_json_but_not_config_injection(self):
        self.manager.install('snmp')
        config={'plugin':'snmp','name':'SNMP','targets':['192.0.2.0/24'],'snmpVersion':'3','credential':json.dumps({'SecurityName':'reader','SecurityLevel':'noAuthNoPriv'},indent=2)}
        id=self.manager.configure(config)
        with self.assertRaises(ValueError):self.manager.configure({**config,'id':id,'snmpVersion':'2c','credential':''})
        with self.assertRaises(ValueError):self.manager.configure({**config,'credential':json.dumps({'SecurityName':'reader\ndefCommunity private','SecurityLevel':'noAuthNoPriv'})})
