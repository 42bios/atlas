import base64
import io
import unittest
import zipfile
from PIL import Image
from vssx_import import import_library, V, R


class VisioImportTests(unittest.TestCase):
    def library(self):
        picture = io.BytesIO()
        Image.new('RGB', (80, 20), 'silver').save(picture, 'BMP')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('visio/masters/masters.xml', f'<Masters xmlns="{V[1:-1]}" xmlns:r="{R[1:-1]}"><Master ID="1" Name="Device"><Rel r:id="m1"/></Master></Masters>')
            z.writestr('visio/masters/_rels/masters.xml.rels', '<Relationships><Relationship Id="m1" Target="master1.xml"/></Relationships>')
            z.writestr('visio/masters/master1.xml', f'<MasterContents xmlns="{V[1:-1]}" xmlns:r="{R[1:-1]}"><ForeignData><Rel r:id="image"/></ForeignData></MasterContents>')
            z.writestr('visio/masters/_rels/master1.xml.rels', '<Relationships><Relationship Id="image" Target="../media/device.bmp"/></Relationships>')
            z.writestr('visio/media/device.bmp', picture.getvalue())
        return archive.getvalue()

    def test_embedded_bitmap_and_stable_ids(self):
        content = self.library()
        records, skipped = import_library(content, 'Test.vssx')
        again, _ = import_library(content, 'Renamed.vssx')
        self.assertEqual(skipped, [])
        self.assertEqual(records[0]['name'], 'Device')
        self.assertEqual(records[0]['id'], again[0]['id'])
        self.assertEqual(records[0]['previewQuality'], 'Embedded artwork')
        with Image.open(io.BytesIO(base64.b64decode(records[0]['image'].split(',')[1]))) as image:
            self.assertEqual(image.size, (80, 20))

    def test_invalid_file(self):
        with self.assertRaises(ValueError):
            import_library(b'not a Visio library', 'broken.vssx')

    def test_zip_without_masters(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('unrelated.txt', 'data')
        with self.assertRaisesRegex(ValueError, 'no Visio master'):
            import_library(archive.getvalue(), 'other.zip')
