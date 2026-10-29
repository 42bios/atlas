import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from atlas_modules.connectors.execution import ContainerExecutor, ContainerJob, runner_status, worker_request
from addin_manager import AddinManager

class ExecutionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.queue=self.root/'queue';self.queue.mkdir()
  (self.queue/'runner.json').write_text(json.dumps({'ready':True,'updated':time.time(),'workerSubnets':['172.30.250.0/24']}))
  self.manager=AddinManager(self.root/'private-addins');self.manager.executor=ContainerExecutor(self.queue)
  self.manager.install('portainer')
  self.instance=self.manager.configure({'plugin':'portainer','name':'Own','upstreamUrl':'https://example.test','credential':'OWN_SECRET'})
  self.x=self.manager.status()['instances'][0]
 def tearDown(self):self.temp.cleanup()
 def prepare(self):
  package=self.manager.root/'packages/portainer'
  return self.manager.executor.start(package,'plugins/portainer/runtime.py',self.manager._environment(self.x),self.x['source'],self.instance,'awj_EPHEMERAL')
 def test_only_own_files_and_ephemeral_token_are_staged(self):
  self.manager.configure({'plugin':'portainer','name':'Other','upstreamUrl':'https://other.test','credential':'OTHER_SECRET'})
  (self.manager.root/'github-access.json').write_text('GITHUB_SECRET')
  job=self.prepare();request=json.loads((job.folder/'request.json').read_text())
  content=''.join(p.read_text() for p in job.folder.rglob('*') if p.is_file())
  self.assertIn('OWN_SECRET',content);self.assertNotIn('OTHER_SECRET',content);self.assertNotIn('GITHUB_SECRET',content)
  self.assertEqual((job.folder/'secrets/ATLAS_TOKEN_FILE').read_text(),'awj_EPHEMERAL')
  self.assertNotIn(str(self.manager.root),json.dumps(request))
  self.assertFalse((job.folder/'ready.json').exists());job.launch();self.assertTrue((job.folder/'ready.json').exists())
 def test_runner_unavailable_fails_closed_without_executing_code(self):
  (self.queue/'runner.json').unlink()
  with patch('subprocess.Popen') as process:
   with self.assertRaisesRegex(ValueError,'runner unavailable'):self.manager.run(self.instance)
   process.assert_not_called()
  self.assertEqual(self.manager.jobs,{})
 def test_job_result_cancellation_and_cleanup(self):
  job=self.prepare();job.launch();job.terminate();self.assertTrue((job.folder/'cancel.json').exists())
  (job.folder/'result.json').write_text(json.dumps({'code':0,'output':'ok'}))
  self.assertEqual(job.wait(1),0);job.cleanup();self.assertFalse(job.folder.exists())
 def test_symlinks_and_mutated_reviewed_code_rejected(self):
  package=self.root/'package';package.mkdir();(package/'main.py').write_text('print("safe")')
  manifest={'files':[{'path':'main.py','sha256':hashlib.sha256(b'print("safe")').hexdigest()}]}
  (package/'main.py').write_text('print("changed")')
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.executor.start(package,'main.py',{},'test',self.instance,'awj_test',manifest=manifest)
  (package/'link').symlink_to(self.manager.root)
  with self.assertRaisesRegex(ValueError,'symbolic'):self.manager.executor.start(package,'main.py',{},'test',self.instance,'awj_test')
 def test_worker_access_rule_survives_stale_heartbeat(self):
  (self.queue/'runner.json').write_text(json.dumps({'ready':True,'updated':0,'workerSubnets':['172.30.250.0/24']}))
  with patch.dict(os.environ,{'ATLAS_WORKER_QUEUE':str(self.queue)}):
   self.assertFalse(runner_status()['available']);self.assertTrue(worker_request('172.30.250.2',{}))
   self.assertFalse(worker_request('192.0.2.1',{}));self.assertTrue(worker_request('192.0.2.1',{'Authorization':'Bearer awj_test'}))
 def test_broker_fixed_container_permissions(self):
  with patch.dict(os.environ,{'ATLAS_WORKER_HOST_QUEUE':'/private/worker-jobs'}):
   spec=importlib.util.spec_from_file_location('broker',Path(__file__).resolve().parents[1]/'runner/service.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  args=m.worker_args(Path('/jobs/'+'a'*32));joined=' '.join(args)
  for value in ['--read-only','--cap-drop ALL','no-new-privileges:true','--pids-limit 64','--memory 256m','--cpus 1','readonly']:self.assertIn(value,joined)
  self.assertNotIn('docker.sock',joined);self.assertNotIn('/data',joined);self.assertNotIn('--privileged',joined);self.assertNotIn('--network host',joined)
  with self.assertRaises(ValueError):m.worker_args(Path('/jobs/../../escape'))

 def test_docker_hairpin_gateway_is_also_restricted(self):
  route='Iface Destination Gateway Flags\neth0 00000000 010011AC 0003\n'
  with patch('pathlib.Path.read_text',return_value=route):
   from atlas_modules.connectors.execution import docker_gateway_addresses
   self.assertEqual(docker_gateway_addresses(),['172.17.0.1/32'])
  with patch('atlas_modules.connectors.execution.docker_gateway_addresses',return_value=['172.17.0.1/32']):
   self.assertTrue(worker_request('172.17.0.1',{}))

 def test_ephemeral_worker_inventory_filtered_by_verified_id(self):
  job=self.prepare();cid='a'*64
  (job.folder/'running.json').write_text(json.dumps({'containerId':cid}))
  self.manager.jobs[self.instance]=job
  snapshot={'services':[{'id':'docker-container-'+cid,'kind':'Container'},{'id':'normal','kind':'Container','name':'atlas-worker-user-device'}],'links':[{'source':'normal','target':'docker-container-'+cid}]}
  filtered=self.manager.filter_worker_records(snapshot)
  self.assertEqual([s['id'] for s in filtered['services']],['normal']);self.assertEqual(filtered['links'],[])
  self.assertEqual(len(snapshot['services']),2)

 def test_credentials_cannot_link_to_another_instance(self):
  credential=self.manager.root/'instances'/self.instance/'credential';credential.unlink()
  other=self.root/'other-secret';other.write_text('DO_NOT_STAGE');credential.symlink_to(other)
  with self.assertRaisesRegex(ValueError,'Symbolic credential'):self.prepare()
  self.assertEqual(other.read_text(),'DO_NOT_STAGE')
