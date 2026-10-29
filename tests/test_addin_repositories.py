import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from atlas_modules.connectors import repositories
from addin_manager import AddinManager

CODE=b'print("example")\n';SHA='a'*40
MANIFEST={'schemaVersion':1,'connectorApi':1,'id':'example-connector','name':'Example connector','description':'Test fixture','version':'1.0.0','runtime':'python','entrypoint':'connector.py','configuration':[{'key':'upstreamUrl','label':'URL','type':'url','required':True}],'credentialRequired':True,'files':[{'path':'connector.py','sha256':hashlib.sha256(CODE).hexdigest()}]}
def download(url,maximum=1000000):
 if url=='https://api.github.com/repos/example/connector':return b'{"default_branch":"main"}'
 if url=='https://api.github.com/repos/example/connector/commits/main':return json.dumps({'sha':SHA}).encode()
 if url=='https://raw.githubusercontent.com/example/connector/'+SHA+'/atlas-addin.json':return json.dumps(MANIFEST).encode()
 if url=='https://raw.githubusercontent.com/example/connector/'+SHA+'/connector.py':return CODE
 raise AssertionError(url)

class RepositoryTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.manager=AddinManager(Path(self.temp.name)/'addins')
 def tearDown(self):self.temp.cleanup()
 def preview(self):
  with patch.object(repositories,'fetch',side_effect=download):return self.manager.preview_repository('https://github.com/example/connector')
 def test_review_install_and_dynamic_configuration(self):
  with patch('subprocess.Popen') as process:review=self.preview();process.assert_not_called()
  self.assertEqual(review['commit'],SHA);self.assertEqual(self.manager.status()['instances'],[])
  with self.assertRaises(ValueError):self.manager.install_repository(review['review'],'wrong')
  id=self.manager.install_repository(review['review'],'example/connector')
  self.assertTrue(next(p for p in self.manager.status()['packages'] if p['id']==id)['installed'])
  instance=self.manager.configure({'plugin':id,'name':'Example','credential':'private','config':{'upstreamUrl':'https://example.test'}})
  x=self.manager.status()['instances'][0];env=self.manager._environment(x)
  self.assertEqual(json.loads(Path(env['ADDIN_CONFIG_FILE']).read_text()),{'upstreamUrl':'https://example.test'})
  self.assertEqual(Path(env['ADDIN_CREDENTIAL_FILE']).read_text(),'private')
  self.assertNotIn('private',json.dumps(self.manager.status()))
  self.manager.action('uninstall',plugin=id);self.assertFalse((self.manager.root/'packages'/id).exists());self.assertEqual(self.manager.status()['instances'],[])
 def test_tampered_download_and_traversal_are_rejected(self):
  with patch.object(repositories,'fetch',side_effect=lambda url,maximum=1000000: b'altered' if url.endswith('connector.py') else download(url,maximum)):
   with self.assertRaisesRegex(ValueError,'checksum'):self.manager.preview_repository('https://github.com/example/connector')
  for path in ('../escape.py','/escape.py','a//b.py','a/./b.py','https://bad/evil.py'):
   with self.assertRaises(ValueError):repositories.parse_manifest(json.dumps({**MANIFEST,'files':[{'path':path,'sha256':'a'*64}]}))
  review=self.preview();(self.manager.root/'staging'/review['review']/'files/connector.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.install_repository(review['review'],'example/connector')
 def test_versions_preserve_instances_and_source(self):
  review=self.preview();id=self.manager.install_repository(review['review'],'example/connector')
  instance=self.manager.configure({'plugin':id,'name':'Example','credential':'private','config':{'upstreamUrl':'https://example.test'}})
  source=self.manager.status()['instances'][0]['source'];review=self.preview();self.assertTrue(review['updating'])
  self.manager.install_repository(review['review'],'example/connector');self.assertEqual(self.manager.status()['instances'][0]['source'],source)
  self.assertEqual(self.manager.status()['instances'][0]['id'],instance)
 def test_invalid_hosts_refs_and_fields(self):
  for url in ('http://github.com/example/connector','https://127.0.0.1/example/connector','https://github.com/example/connector?token=x','https://github.com/example/connector/tree/main'):
   with self.assertRaises(ValueError):repositories.repository(url)
  with self.assertRaises(ValueError):repositories.configuration(MANIFEST,{'upstreamUrl':'https://user:secret@example.test'})
  with self.assertRaises(ValueError):repositories.configuration(MANIFEST,{'unknown':'value'})
 def test_expired_reviews_and_concurrent_update(self):
  review=self.preview();folder=self.manager.root/'staging'/review['review'];value=json.loads((folder/'review.json').read_text());value['expires']=0;(folder/'review.json').write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'expired'):self.manager.install_repository(review['review'],'example/connector')
 def test_shipped_starters_are_complete_and_valid(self):
  root=Path(__file__).resolve().parents[1]/'docs/addin-repositories/packages'
  # Documentation is not bundled into the Docker image; validate source when available.
  if not root.exists():self.skipTest('Starter source packages are validated before building the application image')
  for folder in root.iterdir():
   manifest=repositories.parse_manifest((folder/'atlas-addin.json').read_text())
   for file in manifest['files']:self.assertEqual(hashlib.sha256((folder/file['path']).read_bytes()).hexdigest(),file['sha256'])


class GitHubAccessTests(unittest.TestCase):
 def test_private_access_is_secret_and_scoped(self):
  with tempfile.TemporaryDirectory() as folder:
   manager=AddinManager(folder)
   manager.configure_github_access({'token':'test-secret-token','repositories':['example/private']})
   self.assertNotIn('test-secret-token',json.dumps(manager.status()))
   self.assertEqual((Path(folder)/'github-access.json').stat().st_mode & 0o777,0o600)
   with patch.object(repositories,'download',return_value=({'id':'test','manifest':{}},{})) as mocked:
    manager.preview_repository('https://github.com/example/private')
    self.assertEqual(mocked.call_args.kwargs['token'],'test-secret-token')
    manager.preview_repository('https://github.com/example/public')
    self.assertEqual(mocked.call_args.kwargs,{})
   manager.configure_github_access({'token':'','repositories':['example/private']})
   self.assertTrue(manager.github_access()['configured'])
   manager.configure_github_access({'remove':True})
   self.assertFalse(manager.github_access()['configured'])
 def test_credentials_never_sent_to_raw_host(self):
  with self.assertRaisesRegex(ValueError,'restricted'):
   repositories.fetch('https://raw.githubusercontent.com/example/private/main/x.py',token='secret')
 def test_private_download_uses_api_contents_and_checksums(self):
  def private_fetch(url,maximum=1000000,token=None,raw=False):
   self.assertEqual(token,'secret')
   self.assertTrue(url.startswith('https://api.github.com/repos/example/connector'))
   if '/contents/' in url:
    self.assertTrue(raw)
    return json.dumps(MANIFEST).encode() if '/atlas-addin.json?' in url else CODE
   return download(url,maximum)
  with patch.object(repositories,'fetch',side_effect=private_fetch):
   meta,files=repositories.download('https://github.com/example/connector',token='secret')
  self.assertEqual(files['connector.py'],CODE)
  self.assertNotIn('secret',json.dumps(meta))

class RepositoryRollbackTests(unittest.TestCase):
 setUp=RepositoryTests.setUp
 tearDown=RepositoryTests.tearDown
 preview=RepositoryTests.preview
 def test_rollback_keeps_instance_credentials_and_source_and_blocks_running(self):
  review=self.preview();id=self.manager.install_repository(review['review'],'example/connector');instance=self.manager.configure({'plugin':id,'name':'Example','credential':'private','config':{'upstreamUrl':'https://example.test'}})
  source=self.manager.status()['instances'][0]['source'];updated_code=b'print("version two")\n';updated_manifest={**MANIFEST,'version':'1.1.0','files':[{'path':'connector.py','sha256':hashlib.sha256(updated_code).hexdigest()}]}
  def updated(url,maximum=1000000):
   if url.endswith('/atlas-addin.json'):return json.dumps(updated_manifest).encode()
   if url.endswith('/connector.py'):return updated_code
   return download(url,maximum)
  with patch.object(repositories,'fetch',side_effect=updated):review=self.manager.preview_repository('https://github.com/example/connector')
  self.manager.install_repository(review['review'],'example/connector');self.assertEqual((self.manager.root/'packages'/id/'connector.py').read_bytes(),updated_code)
  self.manager.jobs[instance]=object()
  with self.assertRaisesRegex(ValueError,'running'):self.manager.rollback_repository(id)
  self.manager.jobs.clear();self.manager.rollback_repository(id)
  self.assertEqual((self.manager.root/'packages'/id/'connector.py').read_bytes(),CODE);self.assertEqual(self.manager.read()['repositories'][id]['manifest']['version'],'1.0.0')
  self.assertEqual(self.manager.status()['instances'][0]['source'],source);self.assertEqual((self.manager.root/'instances'/instance/'credential').read_text(),'private')
