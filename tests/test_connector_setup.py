import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from connector_setup import prepare, package
from plugins.common.provision_token import provision


class ConnectorSetupTests(unittest.TestCase):
    def settings(self, plugin='portainer'):
        return dict(plugin=plugin, connector=plugin+'-test', atlasUrl='http://192.0.2.1:8097', upstreamUrl='https://controller.example:9443')

    def test_packaged_sources_are_buildable_layout_and_exclude_secrets(self):
        for plugin in ('portainer', 'snmp', 'kubernetes'):
            payload=self.settings(plugin)
            if plugin=='snmp': payload['targets']=['192.0.2.0/24']
            filename, body=package(payload)
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                names=z.namelist()
                self.assertIn('plugins/'+plugin+'/Dockerfile', names)
                self.assertIn('plugins/'+plugin+'/compose.yaml', names)
                self.assertIn('plugins/'+plugin+'/.env', names)
                self.assertNotIn('plugins/'+plugin+'/secrets/atlas_token', names)
                self.assertIn('provision_token.py', names)
                self.assertFalse(any(n.startswith('/') or '..' in n.split('/') for n in names))
                if plugin!='portainer': self.assertIn('plugins/common/runtime.py', names)
                if plugin=='kubernetes': self.assertIn('plugins/kubernetes/rbac.yaml', names)
                if plugin=='snmp': self.assertEqual(json.loads(z.read('plugins/snmp/secrets/discovery_config'))['targets'], ['192.0.2.0/24'])
                self.assertIn('does not install', z.read('README.md').decode())
            self.assertEqual(filename, plugin+'-test.zip')

    def test_rejects_secret_fields_and_unavailable_plugins(self):
        for change in ({'password':'secret'}, {'token':'secret'}, {'plugin':'unifi'}, {'plugin':'../../etc'}):
            with self.assertRaises(ValueError): prepare({**self.settings(), **change})

    def test_configuration_cannot_inject_shell_or_environment(self):
        for key, value in [('connector','bad;curl'), ('atlasUrl','http://example.test/$(touch)'), ('atlasUrl','http://example.test\nEXTRA=x'), ('upstreamUrl','https://user:password@example.test'), ('upstreamUrl','http://example.test'), ('tlsFingerprint','no-verification'), ('atlasUrl','http://example.test:bad')]:
            with self.assertRaises(ValueError): prepare({**self.settings(),key:value})
        with self.assertRaises(ValueError): prepare({**self.settings('kubernetes'),'clusterName':'x\nEVIL=y'})

    def test_snmp_scope_is_bounded_across_networks(self):
        for targets in ([],['0.0.0.0/0'],['2001:db8::/64'],['192.0.2.0/22','198.51.100.0/24'],['not-an-ip']):
            with self.assertRaises(ValueError): prepare({**self.settings('snmp'),'targets':targets})
        result=prepare({**self.settings('snmp'),'targets':['192.0.2.10','192.0.2.0/24'],'snmpVersion':'3'})
        self.assertIn('secrets/snmp_credentials',' '.join(result['requirements']))

    def test_tls_fingerprint_is_preserved_and_run_modes_match_plugins(self):
        p=prepare({**self.settings(),'tlsFingerprint':'A'*64})
        self.assertIn('PORTAINER_TLS_SHA256='+'a'*64,p['environment'])
        self.assertIn('SYNC_INTERVAL=900',p['environment'])
        self.assertIn('RUN_ONCE=true',prepare(self.settings('kubernetes'))['environment'])

    def test_token_helper_preserves_sources_and_reuses_matching_token(self):
        with tempfile.TemporaryDirectory() as folder, patch('os.getuid',return_value=1000):
            keys=Path(folder)/'keys.json'; output=Path(folder)/'plugin/atlas_token'
            keys.write_text(json.dumps({'other-source':'a'*40}))
            provision(keys,'new-source',output)
            saved=json.loads(keys.read_text()); token=output.read_text().strip()
            self.assertEqual(saved['other-source'],'a'*40)
            self.assertEqual(saved['new-source'],token)
            self.assertGreaterEqual(len(token),32)
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            provision(keys,'new-source',output)
            self.assertEqual(json.loads(keys.read_text()),saved)

    def test_token_helper_rejects_conflicting_output_without_changing_keys(self):
        with tempfile.TemporaryDirectory() as folder, patch('os.getuid',return_value=1000):
            keys=Path(folder)/'keys.json'; output=Path(folder)/'atlas_token'
            original=json.dumps({'existing-source':'a'*40});keys.write_text(original);output.write_text('b'*40)
            with self.assertRaises(ValueError): provision(keys,'existing-source',output)
            self.assertEqual(keys.read_text(),original)
            with self.assertRaises(ValueError): provision(keys,'existing-source',keys)
