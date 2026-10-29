import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import server
from atlas_modules.settings.backups import HostBackups

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=server.DB;server.DB=Path(self.temp.name)/'atlas.db'
        server.write_state({**server.demo(),'demo':False,'_revision':0})
        self.manager=server.addins();self.manager.write({'installed':[],'instances':[{'id':'example','plugin':'community','name':'Test','source':'stable-source','enabled':True,'interval':900}]})
        secret=self.manager.root/'instances/example/credential';secret.parent.mkdir(parents=True);secret.write_text('fixture-private-token')
        self.backups=HostBackups(server.application)
    def tearDown(self):
        server.DB=self.previous;self.temp.cleanup()
    def test_roundtrip_rehearsal_retains_private_files_and_inventory(self):
        result=self.backups.create();self.assertTrue(result['valid']);self.assertEqual(result['connections'],1)
        archive=self.backups.path(result['name']);self.assertEqual(archive.stat().st_mode&0o777,0o600)
        destination=Path(self.temp.name)/'rehearsal';self.backups.validate(result['name'],destination)
        self.assertEqual((destination/'addins/instances/example/credential').read_text(),'fixture-private-token')
        con=sqlite3.connect(destination/'atlas.db');saved=json.loads(con.execute('SELECT content FROM inventory').fetchone()[0]);con.close()
        self.assertEqual(saved,server.read_state())
        self.assertNotIn('fixture-private-token',json.dumps(result))
        self.assertEqual(json.loads((destination/'addins/registry.json').read_text())['instances'][0]['source'],'stable-source')
        with self.assertRaisesRegex(ValueError,'new directory'):self.backups.validate(result['name'],destination)
    def test_running_import_blocks_snapshot(self):
        with patch.object(self.manager,'status',return_value={'instances':[{'running':True}]}):
            with self.assertRaisesRegex(ValueError,'running imports'):self.backups.create()
    def test_checksums_and_unsafe_paths_are_rejected(self):
        result=self.backups.create();path=self.backups.path(result['name'])
        with tarfile.open(path) as tar:files={m.name:tar.extractfile(m).read() for m in tar.getmembers()}
        files['atlas.db']+=b'tampered'
        with tarfile.open(path,'w:gz') as tar:
            for name,data in files.items():
                entry=tarfile.TarInfo(name);entry.size=len(data);tar.addfile(entry,io.BytesIO(data))
        with self.assertRaisesRegex(ValueError,'checksum'):self.backups.validate(result['name'])
        files['../outside']=b'unsafe'
        with tarfile.open(path,'w:gz') as tar:
            for name,data in files.items():
                entry=tarfile.TarInfo(name);entry.size=len(data);tar.addfile(entry,io.BytesIO(data))
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.backups.validate(result['name'])
        with self.assertRaises(ValueError):self.backups.validate('../../registry.json')
    def test_incompatible_backup_is_not_restored(self):
        result=self.backups.create();path=self.backups.path(result['name'])
        with tarfile.open(path) as tar:files={m.name:tar.extractfile(m).read() for m in tar.getmembers()}
        manifest=json.loads(files['manifest.json']);manifest['modules']['core']='999.0.0';files['manifest.json']=json.dumps(manifest).encode()
        with tarfile.open(path,'w:gz') as tar:
            for name,data in files.items():
                entry=tarfile.TarInfo(name);entry.size=len(data);tar.addfile(entry,io.BytesIO(data))
        with self.assertRaisesRegex(ValueError,'incompatible'):self.backups.validate(result['name'])

if __name__=='__main__':unittest.main()
