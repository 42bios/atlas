import copy,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from atlas_core.runtime import Application
from atlas_modules.registry import registry
from addin_manager import AddinManager
from atlas_modules.connectors import engine,repositories
from atlas_modules.connectors.marketplace import Marketplace,parse_index,icon_package

SHA='a'*40
ENTRY={'id':'test-icons','type':'icon-pack','name':'Test icons','description':'A test pack','repository':'https://github.com/example/icons','ref':SHA,'version':'1.0.0','license':'MIT'}
class MarketplaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=Application(lambda:Path(self.tmp.name)/'atlas.db',registry,AddinManager,engine);self.market=Marketplace(self.app)
  data=self.market.read();data['sources'][0]['packages']=parse_index(json.dumps({'schemaVersion':1,'packages':[ENTRY]}),'example/index',SHA);self.market.write(data)
  self.key='atlas-official/test-icons'
 def test_connector_progress_is_scoped_and_does_not_disclose_configuration(self):
  entry=dict(ENTRY,id='connector',type='connector',repository='https://github.com/example/connector');data=self.market.read();data['sources'][0]['packages']=parse_index(json.dumps({'schemaVersion':1,'packages':[entry]}),'example/index',SHA);self.market.write(data)
  self.app.addins().write({'installed':['repo-test'],'repositories':{'repo-test':{'id':'repo-test','name':'Test','repositoryName':'example/connector','repository':'https://github.com/example/connector','version':'1.0.0','commit':SHA}},'instances':[{'id':'one','plugin':'repo-test','name':'Main','source':'source-one','enabled':True,'interval':0,'config':{'privateMarker':'not-for-marketplace'},'result':'Import completed','lastFinished':1}]})
  state=self.app.read_state();state['services'].append({'id':'progress-app','name':'Imported app','kind':'Container','origin':'source-one'});self.app.write_state(state)
  package=self.market.status()['packages'][0]
  self.assertEqual(package['connections'][0]['name'],'Main');self.assertEqual(package['connections'][0]['applicationCount'],1)
  self.assertNotIn('not-for-marketplace',json.dumps(package));self.assertNotIn('config',package['connections'][0])
 def tearDown(self):self.tmp.cleanup()
 def icon_review(self,color='red'):
  out=io.BytesIO();Image.new('RGB',(32,32),color).save(out,format='PNG');content=out.getvalue()
  manifest={'schemaVersion':1,'icons':[{'id':'database','name':'Database','file':'db.png','sha256':hashlib.sha256(content).hexdigest(),'match':['postgres']}]}
  with patch('atlas_modules.connectors.marketplace.raw',side_effect=lambda repo,commit,file,maximum=1000000: json.dumps(manifest).encode() if file=='atlas-icons.json' else content):return self.market.preview(self.key)
 def install(self,review):return self.market.install({'review':review['review'],'trust':'example/icons'})
 def test_preview_is_data_only_and_install_requires_trust_and_one_use_review(self):
  before=copy.deepcopy(self.app.read_state())
  with patch('subprocess.Popen') as run:
   review=self.icon_review();run.assert_not_called()
  self.assertEqual(self.market.icons(),[]);self.assertEqual(self.app.read_state(),before)
  with self.assertRaises(ValueError):self.market.install({'review':review['review'],'trust':'wrong'})
  self.install(review);icons=self.market.icons();self.assertEqual(len(icons),1);self.assertTrue(icons[0]['image'].startswith('data:image/png;base64,'));self.assertEqual(self.app.read_state(),before)
  with self.assertRaises(ValueError):self.install(review)
 def test_manual_updates_rollback_and_remove_retain_inventory(self):
  self.install(self.icon_review());old=self.market.icons()[0]['image'];data=self.market.read();data['sources'][0]['packages'][0]['ref']='b'*40;data['sources'][0]['packages'][0]['version']='1.1.0';self.market.write(data)
  self.assertTrue(self.market.status()['packages'][0]['updateAvailable']);self.install(self.icon_review('blue'));self.assertNotEqual(self.market.icons()[0]['image'],old)
  self.market.rollback(self.key);self.assertEqual(self.market.icons()[0]['image'],old)
  before=self.app.read_state();self.market.remove(self.key);self.assertEqual(self.market.icons(),[]);self.assertEqual(self.app.read_state(),before)
 def test_removed_source_retains_installed_and_disable_rejects_review(self):
  review=self.icon_review();self.market.source({'action':'toggle','id':'atlas-official'})
  with self.assertRaises(ValueError):self.install(review)
  self.market.source({'action':'toggle','id':'atlas-official'});self.install(self.icon_review());self.market.source({'action':'remove','id':'atlas-official'})
  self.assertTrue(self.market.status()['packages'][0]['installed']);self.assertEqual(len(self.market.icons()),1)
 def test_failed_refresh_retains_cached_index(self):
  before=self.market.read()['sources'][0]['packages']
  with patch('atlas_modules.connectors.marketplace.resolve',side_effect=ValueError('rate limit')):
   with self.assertRaises(ValueError):self.market.refresh('atlas-official')
  self.assertEqual(self.market.read()['sources'][0]['packages'],before);self.assertTrue(self.market.status()['sources'][0]['error'])
 def test_index_validation_blocks_non_github_mutable_commits_paths_and_duplicates(self):
  for entry in [dict(ENTRY,repository='https://127.0.0.1/private'),dict(ENTRY,ref='main'),dict(ENTRY,manifest='../x'),dict(ENTRY,type='script')]:
   with self.assertRaises(ValueError):parse_index(json.dumps({'schemaVersion':1,'packages':[entry]}),'example/index',SHA)
  with self.assertRaises(ValueError):parse_index(json.dumps({'schemaVersion':1,'packages':[ENTRY,ENTRY]}),'example/index',SHA)
 def test_icon_checksum_and_executable_image_types_rejected(self):
  for file in ['evil.svg','../db.png','db.png']:
   manifest={'schemaVersion':1,'icons':[{'id':'x','name':'Test','file':file,'sha256':'0'*64}]}
   with patch('atlas_modules.connectors.marketplace.raw',return_value=b'wrong'):
    with self.assertRaises(ValueError):icon_package(json.dumps(manifest),'example/icons',SHA)
 def test_catalog_update_keeps_model_identity_and_device_placements(self):
  entry=dict(ENTRY,id='models',type='device-catalog',repository='https://github.com/example/models');data=self.market.read();data['sources'][0]['packages']=parse_index(json.dumps({'schemaVersion':1,'packages':[entry]}),'example/index',SHA);self.market.write(data);key='atlas-official/models'
  def review(ports):
   with patch('atlas_modules.connectors.marketplace.raw',return_value=json.dumps({'version':1,'devices':[{'id':'switch','name':'Switch','manufacturer':'Example','model':'S1','kind':'Switch','height':1,'ports':ports}]}).encode()):return self.market.preview(key)
  before=copy.deepcopy(self.app.read_state());r=review(8);self.market.install({'review':r['review'],'trust':'example/models'});model=self.app.read_state()['deviceCatalog'][0]['id'];r=review(16);self.market.install({'review':r['review'],'trust':'example/models'});state=self.app.read_state();self.assertEqual(len(state['deviceCatalog']),1);self.assertEqual(state['deviceCatalog'][0]['id'],model);self.assertEqual(state['devices'],before['devices']);self.assertEqual(state['racks'],before['racks']);self.market.rollback(key);self.assertEqual(self.app.read_state()['deviceCatalog'][0]['ports'],8)
 def test_bundled_portainer_is_recognized_as_installed(self):
  self.app.addins().install('portainer');data=self.market.read();entry=dict(ENTRY,id='portainer',type='connector',repository='https://github.com/42bios/atlas-plugin-portainer');data['sources'][0]['packages']=parse_index(json.dumps({'schemaVersion':1,'packages':[entry]}),'example/index',SHA);self.market.write(data);self.assertTrue(self.market.status()['packages'][0]['installed']);self.assertEqual(self.market.status()['packages'][0]['plugin'],'portainer')

 def test_duplicate_packages_across_sources_are_deduplicated(self):
  self.install(self.icon_review());data=self.market.read();second=copy.deepcopy(data['sources'][0]);second['id']='second';second['name']='Second';data['sources'].append(second);self.market.write(data)
  self.assertEqual(len(self.market.status()['packages']),1)
  self.market.source({'action':'remove','id':'atlas-official'});status=self.market.status();self.assertEqual(len(status['packages']),1);self.assertTrue(status['packages'][0]['installed']);self.assertEqual(len(self.market.icons()),1)

 def test_pinned_documentation_is_bounded_cached_and_unknown_package_rejected(self):
  with patch('atlas_modules.connectors.marketplace.raw',return_value=b'# Package documentation') as fetch:
   result=self.market.details(self.key);self.assertIn('documentation',result['readme']);self.market.details(self.key);self.assertEqual(fetch.call_count,1)
  with self.assertRaises(ValueError):self.market.details('unknown')
  data=self.market.read();data['documents']={};self.market.write(data)
  with patch('atlas_modules.connectors.marketplace.raw',side_effect=ValueError('unavailable')):self.assertIn('error',self.market.details(self.key))
 def test_github_metadata_cached_and_failure_does_not_hide_catalog(self):
  index=json.dumps({'schemaVersion':1,'packages':[ENTRY]}).encode()
  with patch('atlas_modules.connectors.marketplace.resolve',return_value=('example/index',SHA)),patch('atlas_modules.connectors.marketplace.raw',return_value=index),patch.object(repositories,'fetch',return_value=b'{"stargazers_count":12,"pushed_at":"2026-10-25T12:00:00Z"}') as fetch:
   result=self.market.refresh('atlas-official');self.assertEqual(result['packages'][0]['github']['stars'],12);self.market.refresh('atlas-official');self.assertEqual(fetch.call_count,1)
  data=self.market.read();data['sources'][0]['packages'][0].pop('github');self.market.write(data)
  with patch('atlas_modules.connectors.marketplace.resolve',return_value=('example/index',SHA)),patch('atlas_modules.connectors.marketplace.raw',return_value=index),patch.object(repositories,'fetch',side_effect=ValueError('Rate limited')):
   result=self.market.refresh('atlas-official');self.assertEqual(len(result['packages']),1);self.assertNotIn('github',result['packages'][0])
