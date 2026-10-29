import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from addin_manager import AddinManager
from atlas_modules.connectors import repositories
from atlas_modules.connectors.migration import OFFICIAL

CODE=b'raise RuntimeError("Migration must never execute package code")\n';SHA='a'*40
class MigrationTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.manager=AddinManager(Path(self.tmp.name)/'addins')
 def tearDown(self):self.tmp.cleanup()
 def legacy(self,plugin='portainer',**extra):
  self.manager.install(plugin);payload={'plugin':plugin,'name':'Existing '+plugin,'interval':3600,'credential':'PRIVATE_TEST_CREDENTIAL'}
  if plugin=='portainer':payload.update(upstreamUrl='https://example.test:9443',tlsFingerprint='a'*64)
  elif plugin=='kubernetes':payload.update(upstreamUrl='https://cluster.test',clusterName='Existing cluster',caCertificate='-----BEGIN CERTIFICATE-----\nPRIVATE_TEST_CA\n-----END CERTIFICATE-----')
  else:payload.update(targets=['192.0.2.0/30','192.0.2.9'],snmpVersion='2c')
  payload.update(extra);id=self.manager.configure(payload);return next(x for x in self.manager.read()['instances'] if x['id']==id)
 def review(self,plugin='portainer',repository=None):
  repo=repository or next(repo for repo,(id,_) in OFFICIAL.items() if id==plugin);manifest_id=OFFICIAL.get(repo,(plugin,'custom-connector'))[1]
  fields=[{'key':'upstreamUrl','label':'URL','type':'url','required':True}]
  if plugin=='portainer':fields.append({'key':'tlsFingerprint','label':'Fingerprint','type':'text'})
  elif plugin=='kubernetes':fields.append({'key':'clusterName','label':'Cluster','type':'text'})
  else:fields=[{'key':'targets','label':'Targets','type':'text','required':True},{'key':'snmpVersion','label':'Version','type':'text'}]
  manifest={'schemaVersion':1,'connectorApi':1,'id':manifest_id,'name':'Independent connector','description':'Migration test package','version':'1.0.0','runtime':'python','entrypoint':'connector.py','files':[{'path':'connector.py','sha256':hashlib.sha256(CODE).hexdigest()}],'configuration':fields,'credentialRequired':True}
  def fetch(url,maximum=1000000):
   if '/commits/' in url:return json.dumps({'sha':SHA}).encode()
   if url.endswith('/atlas-addin.json'):return json.dumps(manifest).encode()
   if url.endswith('/connector.py'):return CODE
   return b'{"default_branch":"main"}'
  with patch.object(repositories,'fetch',side_effect=fetch):return self.manager.preview_repository('https://github.com/'+repo)
 def migrate(self,review):return self.manager.migrate_repository(review['review'],review['repositoryName'])
 def test_portainer_identity_schedule_credential_and_fingerprint_preserved(self):
  old=self.legacy();self.manager.action('disable',old['id']);old=copy.deepcopy(self.manager.read()['instances'][0]);review=self.review();plan=self.manager.migration_preview(review)
  self.assertNotIn('PRIVATE_TEST',json.dumps(plan))
  with patch('subprocess.Popen') as execute:result=self.migrate(review);execute.assert_not_called()
  new=self.manager.read()['instances'][0]
  for key in ('id','source','name','interval','enabled','config'):self.assertEqual(old[key],new[key])
  self.assertEqual(new['plugin'],result['plugin']);self.assertNotIn('portainer',self.manager.read()['installed']);self.assertEqual(len(self.manager.read()['instances']),1)
  folder=self.manager.root/'instances'/old['id'];self.assertEqual((folder/'credential').read_text(),'PRIVATE_TEST_CREDENTIAL');self.assertEqual(json.loads((folder/'config.json').read_text()),old['config'])
  self.assertEqual((folder/'credential').stat().st_mode&0o777,0o600);self.assertFalse((self.manager.root/'packages/portainer').exists());self.assertTrue((self.manager.root/'migrations'/result['migration']/'legacy-package').exists())
 def test_kubernetes_ca_and_token_converted_to_private_json(self):
  old=self.legacy('kubernetes');ca=(self.manager.root/'instances'/old['id']/'cluster_ca').read_text();self.migrate(self.review('kubernetes'))
  credential=json.loads((self.manager.root/'instances'/old['id']/'credential').read_text());self.assertEqual(credential,{'token':'PRIVATE_TEST_CREDENTIAL','ca':ca});self.assertEqual(self.manager.read()['instances'][0]['source'],old['source'])
  self.assertNotIn('PRIVATE_TEST',json.dumps(self.manager.status()))
 def test_snmp_targets_and_v3_secret_preserved(self):
  credential=json.dumps({'SecurityName':'test','SecurityLevel':'noAuthNoPriv'})
  old=self.legacy('snmp',snmpVersion='3',credential=credential);self.migrate(self.review('snmp'));new=self.manager.read()['instances'][0]
  self.assertEqual(new['config']['targets'],'192.0.2.0/30\n192.0.2.9');self.assertEqual(new['config']['snmpVersion'],'3');self.assertEqual((self.manager.root/'instances'/old['id']/'credential').read_text(),credential)
 def test_running_untrusted_repository_and_wrong_confirmation_block(self):
  old=self.legacy();review=self.review();self.manager.jobs[old['id']]=SimpleNamespace()
  with self.assertRaisesRegex(ValueError,'finish'):self.migrate(review)
  self.manager.jobs.clear()
  with self.assertRaises(ValueError):self.manager.migrate_repository(review['review'],'wrong/repo')
  with self.assertRaisesRegex(ValueError,'official'):self.migrate(self.review(repository='example/lookalike'))
  self.assertEqual(self.manager.read()['instances'][0]['plugin'],'portainer')
 def test_tampered_staging_and_failed_registry_commit_restore_all(self):
  old=self.legacy();review=self.review();(self.manager.root/'staging'/review['review']/'files/connector.py').write_text('tampered')
  with self.assertRaisesRegex(ValueError,'changed'):self.migrate(review)
  self.assertEqual(self.manager.read()['instances'][0]['plugin'],'portainer')
  review=self.review();original=self.manager.write
  def failing(data):
   if any(x['plugin'].startswith('repo-') for x in data['instances']):raise OSError('Simulated registry failure')
   return original(data)
  with patch.object(self.manager,'write',side_effect=failing):
   with self.assertRaises(OSError):self.migrate(review)
  self.assertEqual(self.manager.read()['instances'][0]['plugin'],'portainer');self.assertEqual((self.manager.root/'instances'/old['id']/'credential').read_text(),'PRIVATE_TEST_CREDENTIAL')
 def test_process_restart_recovers_interrupted_conversion(self):
  old=self.legacy('kubernetes');result=self.migrate(self.review('kubernetes'));file=self.manager.root/'migrations'/result['migration']/'journal.json';journal=json.loads(file.read_text());journal['phase']='applying';file.write_text(json.dumps(journal))
  recovered=AddinManager(self.manager.root);self.assertEqual(recovered.read()['instances'][0]['plugin'],'kubernetes');self.assertEqual((recovered.root/'instances'/old['id']/'credential').read_text(),'PRIVATE_TEST_CREDENTIAL')
 def test_rollback_checks_all_instances_before_overwriting_any(self):
  old1=self.legacy();old2=self.legacy(name='Second');result=self.migrate(self.review());data=self.manager.read();data['instances'][1]['name']='Edited after migration';self.manager.write(data)
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.rollback_migration(result['migration'])
  self.assertTrue(all(x['plugin']==result['plugin'] for x in self.manager.read()['instances']))
  data['instances'][1]['name']='Second';self.manager.write(data);self.manager.rollback_migration(result['migration']);self.assertTrue(all(x['plugin']=='portainer' for x in self.manager.read()['instances']));self.assertEqual(len(self.manager.read()['instances']),2)
 def test_rollback_rejects_changed_config_or_credential(self):
  old=self.legacy();result=self.migrate(self.review());folder=self.manager.root/'instances'/old['id'];(folder/'credential').write_text('USER_CHANGED_SECRET')
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.rollback_migration(result['migration'])
  self.assertEqual((folder/'credential').read_text(),'USER_CHANGED_SECRET')
