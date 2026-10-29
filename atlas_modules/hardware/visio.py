"""Extract embedded master artwork, with explicit Visio-icon fallbacks."""
import base64
import hashlib
import io
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image

V = '{http://schemas.microsoft.com/office/visio/2012/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def import_library(payload, filename):
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise ValueError('This file is not a valid VSSX library.')
    with archive as z:
        if len(z.infolist()) > 3000 or sum(x.file_size for x in z.infolist()) > 80_000_000:
            raise ValueError('The expanded library is too large.')
        def xml(path):
            raw = z.read(path)
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
                raise ValueError('Unsupported XML declarations.')
            return ET.fromstring(raw)
        def rels(path):
            folder, name = posixpath.split(path)
            relpath = folder + '/_rels/' + name + '.rels'
            if relpath not in z.namelist():
                return {}
            return {r.get('Id'): posixpath.normpath(folder+'/'+r.get('Target','')) for r in xml(relpath) if r.get('TargetMode') != 'External'}
        def preview(raw):
            with Image.open(io.BytesIO(raw)) as img:
                if img.width * img.height > 20_000_000:
                    raise ValueError('Image dimensions exceed the import limit.')
                img.thumbnail((1200, 800))
                output = io.BytesIO()
                img.convert('RGBA').save(output, format='PNG', optimize=True)
                return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
        masters_path = 'visio/masters/masters.xml'
        if masters_path not in z.namelist():
            raise ValueError('The file contains no Visio master library.')
        mapping = rels(masters_path)
        library = filename.rsplit('.',1)[0]
        digest = hashlib.sha256(payload).hexdigest()[:20]
        records, skipped = [], []
        for master in xml(masters_path):
            name = master.get('Name') or master.get('NameU') or master.get('ID')
            image, quality = None, 'Embedded artwork'
            rel = master.find(V+'Rel')
            path = mapping.get(rel.get(R+'id')) if rel is not None else None
            if path:
                media = rels(path)
                candidates = xml(path).findall('.//'+V+'ForeignData/'+V+'Rel')
                for ref in candidates:
                    target = media.get(ref.get(R+'id'))
                    if target and target.lower().endswith(('.bmp','.png','.jpg','.jpeg','.gif')):
                        try:
                            image = preview(z.read(target))
                            break
                        except (OSError, ValueError):
                            pass
            if not image:
                encoded = master.findtext(V+'Icon')
                if encoded:
                    try:
                        image = preview(base64.b64decode(encoded))
                        quality = 'Visio thumbnail'
                    except (OSError, ValueError):
                        pass
            if not image:
                skipped.append(name)
                continue
            records.append({'id': 'vssx-'+digest+'-'+master.get('ID'), 'name': name,
                            'vendor': library, 'library': library, 'image': image,
                            'format': 'image/png', 'previewQuality': quality})
        if not records:
            raise ValueError('No supported artwork or master thumbnails found in this library.')
        return records, skipped
