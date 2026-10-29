"""Import a public GitHub catalog without executing repository code."""
import json
import math
from atlas_core.models.hardware_details import validate_details
import urllib.request
from urllib.parse import urlsplit, urljoin, unquote


def catalog_url(value):
    if not isinstance(value, str):
        raise ValueError('Provide a GitHub catalog URL as text.')
    url = urlsplit(value.strip())
    if url.scheme != 'https' or url.username or url.password or url.port:
        raise ValueError('Use an HTTPS GitHub repository or JSON file URL.')
    parts = url.path.strip('/').split('/')
    if url.hostname == 'github.com':
        if len(parts) == 2:
            parts += ['main', 'catalog.json']
        elif len(parts) >= 5 and parts[2] == 'blob':
            parts.pop(2)
        else:
            raise ValueError('Use a repository URL or a GitHub file URL.')
        return 'https://raw.githubusercontent.com/' + '/'.join(parts)
    if url.hostname == 'raw.githubusercontent.com' and len(parts) >= 4:
        return 'https://raw.githubusercontent.com/' + '/'.join(parts)
    raise ValueError('Only public GitHub catalogs are supported.')


def parse_catalog(payload, source):
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('devices'), list):
        raise ValueError('Expected a version 1 catalog with a devices array.')
    if not 1 <= len(data['devices']) <= 500:
        raise ValueError('A catalog must contain between 1 and 500 device templates.')
    records, ids = [], set()
    repository = urlsplit(source).path.strip('/').split('/')[:2]
    for item in data['devices']:
        if not isinstance(item, dict):
            raise ValueError('Device templates must be objects.')
        record = {}
        for key in ('id', 'name', 'manufacturer', 'model', 'kind'):
            value = item.get(key, '')
            if not isinstance(value, str) or len(value) > 200:
                raise ValueError('Template text fields must be shorter than 200 characters.')
            record[key] = value.strip()
        if not record['id'] or not record['name'] or record['id'] in ids:
            raise ValueError('Each template needs a name and a unique ID.')
        ids.add(record['id'])
        if record['kind'] not in ('Server', 'NAS', 'Router', 'Switch', 'Access point', 'Patch panel', 'Cable manager', 'Rack shelf', 'UPS', 'PDU', 'Other'):
            raise ValueError('Choose a supported device kind for each template.')
        for key, maximum in [('height', 60), ('ports', 96)]:
            value = item.get(key)
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError(f'Template {key} must be a whole number between 0 and {maximum}.')
            record[key] = value
        if record['height'] == 0 and record['kind'] != 'PDU':
            raise ValueError('Only a PDU can have a height of 0U.')
        for key, maximum in [('shelfSpace', 60), ('shelfWidth', 100)]:
            if key in item:
                value = item[key]
                if type(value) is not int or not 1 <= value <= maximum:
                    raise ValueError(f'Template {key} must be between 1 and {maximum}.')
                record[key] = value
        for key in ('widthMm', 'depthMm', 'heightMm', 'usableWidthMm', 'usableDepthMm'):
            if key in item:
                value = item[key]
                if type(value) not in (int, float) or not math.isfinite(value) or not 0.1 <= value <= 10000:
                    raise ValueError('Catalog dimensions must be finite positive millimetres up to 10000.')
                record[key] = value
        if bool(record.get('usableWidthMm')) != bool(record.get('usableDepthMm')):
            raise ValueError('Provide both usable shelf dimensions.')
        if 'interfaces' in item:
            record['interfaces'] = item['interfaces']
            validate_details({'racks': [], 'devices': [record]})
            for interface in record['interfaces']:
                interface['ips'] = []  # Addresses belong to instances, never models.
        if 'notes' in item:
            if not isinstance(item['notes'], str) or len(item['notes']) > 2000:
                raise ValueError('Template notes must be text shorter than 2000 characters.')
            record['notes'] = item['notes']
        for key in ('frontImage', 'rearImage'):
            value = item.get(key, '')
            if not isinstance(value, str) or len(value) > 1000:
                raise ValueError('Images must be repository paths or raw GitHub URLs.')
            if value:
                image = urlsplit(urljoin(source, value))
                if image.scheme != 'https' or image.hostname != 'raw.githubusercontent.com' or image.username or image.password or image.port or image.path.strip('/').split('/')[:2] != repository:
                    raise ValueError('Images must belong to the same GitHub repository.')
                if not unquote(image.path).lower().endswith(('.svg', '.png', '.jpg', '.jpeg', '.webp')):
                    raise ValueError('Use SVG, PNG, JPEG or WebP artwork.')
                record[key] = image.geturl()
        for face in ('front', 'rear'):
            key = face + 'ImageFrame'
            if key not in item:
                continue
            frame = item[key]
            if not record.get(face + 'Image') or not isinstance(frame, dict):
                raise ValueError('Image frames require a corresponding image.')
            values = ('x', 'y', 'width', 'height', 'canvasWidth', 'canvasHeight')
            if any(type(frame.get(k)) not in (int, float) or not math.isfinite(frame[k]) for k in values):
                raise ValueError('Image frame coordinates must be finite numbers.')
            if min(frame['x'], frame['y']) < 0 or min(frame[k] for k in values[2:]) <= 0 or max(frame[k] for k in values) > 20000:
                raise ValueError('Image frame dimensions are out of range.')
            if frame['x'] + frame['width'] > frame['canvasWidth'] or frame['y'] + frame['height'] > frame['canvasHeight']:
                raise ValueError('Image frame must fit inside its original canvas.')
            if 'rackSuitable' in frame and type(frame['rackSuitable']) is not bool:
                raise ValueError('Rack suitability must be a boolean.')
            record[key] = {k: frame[k] for k in values}
            record[key]['rackSuitable'] = frame.get('rackSuitable', True)
        records.append(record)
    return records


def fetch_catalog(value):
    source = catalog_url(value)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('Catalog redirects are not supported.')
    request = urllib.request.Request(source, headers={'User-Agent': 'Atlas-Homelab/1', 'Accept': 'application/json'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError('The catalog must be smaller than 1 MB.')
    return source, parse_catalog(payload, source)


def merge_catalog(state, source, records):
    """Update one source, preserving other sources and instantiated hardware."""
    import copy
    import hashlib
    from datetime import datetime, timezone
    result = copy.deepcopy(state)
    sources = result.setdefault('catalogSources', [])
    if not sources and result.get('catalogSource'):
        legacy = result['catalogSource']
        legacy_id = hashlib.sha256(legacy.encode()).hexdigest()[:16]
        sources.append(dict(id=legacy_id, url=legacy, name='/'.join(urlsplit(legacy).path.strip('/').split('/')[:2]), enabled=True))
        for model in result.get('deviceCatalog', []):
            model['catalogId'] = legacy_id
    source_id = hashlib.sha256(source.encode()).hexdigest()[:16]
    previous = next((s for s in sources if s['id'] == source_id), None)
    entry = dict(id=source_id, url=source, name='/'.join(urlsplit(source).path.strip('/').split('/')[:2]), enabled=previous.get('enabled', True) if previous else True, updated=datetime.now(timezone.utc).isoformat(), count=len(records))
    sources[:] = [s for s in sources if s['id'] != source_id] + [entry]
    imported = []
    for model in records:
        model = copy.deepcopy(model)
        model.update(modelId=model['id'], id='catalog:'+source_id+':'+model['id'], catalogId=source_id, catalogName=entry['name'], catalogUrl=source, catalogVersion=entry['updated'])
        imported.append(model)
    result['deviceCatalog'] = [m for m in result.get('deviceCatalog', []) if m.get('catalogId') != source_id] + imported
    result.pop('catalogSource', None)
    return result
