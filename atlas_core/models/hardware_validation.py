import math
import ipaddress
from .hardware_details import validate_details

def validate(state):
    racks = {r['id']: r for r in state['racks']}
    for rack in racks.values():
        if type(rack.get('units')) is not int or not 1 <= rack['units'] <= 60:
            raise ValueError('Rack size must be between 1 and 60 U.')
    devices = {d['id']: d for d in state['devices']}
    shelf_widths = {}
    shelf_footprints = {}
    for device in devices.values():
        for key in ('widthMm', 'depthMm', 'heightMm', 'usableWidthMm', 'usableDepthMm', 'shelfXmm', 'shelfYmm'):
            value = device.get(key)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not (0 if key in ('shelfXmm', 'shelfYmm') else 0.1) <= value <= 10000):
                raise ValueError('Dimensions and shelf coordinates must be finite millimetre values within 0–10000.')
        if bool(device.get('usableWidthMm')) != bool(device.get('usableDepthMm')):
            raise ValueError('Enter both usable shelf width and depth.')
    for device in devices.values():
        if device.get('kind') == 'Rack shelf':
            space = device.get('shelfSpace')
            if space is not None and (type(space) is not int or not 1 <= space <= 60):
                raise ValueError('Total shelf space must be a whole number between 1 and 60 U.')
            clearance = device.get('shelfClearance', 0)
            if type(clearance) is not int or not 0 <= clearance <= 59:
                raise ValueError('Shelf clearance must be a whole number between 0 and 59 U.')
        if not device.get('shelfId'):
            continue
        shelf = devices.get(device['shelfId'])
        if not shelf or shelf.get('kind') != 'Rack shelf' or not shelf.get('rack'):
            raise ValueError('Choose an existing rack-mounted shelf.')
        if device.get('rack') or device.get('kind') in ('Rack shelf', 'Cable manager', 'PDU', 'Patch panel'):
            raise ValueError('Shelf devices cannot also be rack-mounted or be rack accessories.')
        height, width = device.get('height'), device.get('shelfWidth')
        if type(height) is not int or not 1 <= height <= shelf.get('shelfSpace', shelf.get('shelfClearance', 0)):
            raise ValueError('Device height exceeds the clearance reserved above the shelf.')
        if type(width) is not int or not 1 <= width <= 100:
            raise ValueError('Shelf width must be a whole percentage between 1 and 100.')
        if shelf.get('usableWidthMm') and shelf.get('usableDepthMm'):
            if not all(device.get(k) for k in ('widthMm', 'depthMm', 'heightMm')):
                raise ValueError('Shelf devices need width, depth and height for a measured layout.')
            previous = shelf_footprints.setdefault(shelf['id'], [])
            cursor = previous[-1][0] + previous[-1][2] if previous else 0
            x, y = device.get('shelfXmm', cursor), device.get('shelfYmm', 0)
            w, depth = device['widthMm'], device['depthMm']
            if x + w > shelf['usableWidthMm'] + 1e-6 or y + depth > shelf['usableDepthMm'] + 1e-6:
                raise ValueError('Device extends beyond the usable shelf area.')
            space = shelf.get('shelfSpace', shelf.get('height', 1) + shelf.get('shelfClearance', 0))
            if device['heightMm'] + 4 > space * 44.45 + 1e-6:
                raise ValueError('Device physical height exceeds reserved shelf space including its floor.')
            for px, py, pw, pd in previous:
                if x < px + pw - 1e-6 and x + w > px + 1e-6 and y < py + pd - 1e-6 and y + depth > py + 1e-6:
                    raise ValueError('Shelf device footprints overlap.')
            previous.append((x, y, w, depth))
        else:
            shelf_widths[shelf['id']] = shelf_widths.get(shelf['id'], 0) + width
            if shelf_widths[shelf['id']] > 100:
                raise ValueError('Devices on this shelf exceed 100% of its available width.')
    occupied = set()
    objects = {x['id']: x for x in state['devices'] + state['services']}
    for device in state['devices']:
        if not device.get('rack'):
            continue
        rack = racks.get(device['rack'])
        if not rack:
            raise ValueError('Unknown rack.')
        u, h = device.get('unit'), device.get('height')
        if type(u) is not int or type(h) is not int:
            raise ValueError('Rack position and height must be whole numbers.')
        if device.get('kind') == 'PDU' and u == 0 and h == 0:
            continue
        clearance = device.get('shelfSpace', h + device.get('shelfClearance', 0)) - h if device.get('kind') == 'Rack shelf' else 0
        start = u - clearance if rack.get('numbering') == 'top' else u
        end = u + h - 1 if rack.get('numbering') == 'top' else u + h + clearance - 1
        if start < 1 or h < 1 or end > rack['units']:
            raise ValueError('Device does not fit inside the rack.')
        for pos in range(start, end + 1):
            slot = (rack['id'], pos)
            if slot in occupied:
                raise ValueError('Rack positions overlap. Choose an empty slot.')
            occupied.add(slot)
    validate_details(state)
