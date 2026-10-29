import datetime
import ipaddress
import math


HARDWARE_KEYS = ('manufacturer', 'model', 'kind', 'height', 'ports', 'widthMm', 'depthMm', 'heightMm', 'usableWidthMm', 'usableDepthMm')
INTERFACE_TYPES = ('Ethernet', 'Fiber', 'Wi-Fi', 'Virtual', 'LAG', 'Power inlet', 'Power outlet')


def validate_details(state):
    for rack in state['racks']:
        coords = [rack.get('latitude'), rack.get('longitude')]
        if any(v is not None for v in coords):
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in coords) or not -90 <= coords[0] <= 90 or not -180 <= coords[1] <= 180:
                raise ValueError('Enter valid latitude and longitude together.')
    for device in state['devices'] + state.get('services', []):
        spec = device.get('hardwareSpec')
        if spec is not None:
            if not isinstance(spec, dict):
                raise ValueError('Hardware specifications must be an object.')
            for key in HARDWARE_KEYS:
                if key in spec and device.get(key) != spec[key]:
                    raise ValueError('Predefined device hardware specifications cannot be changed: ' + key)
        date = device.get('purchaseDate')
        if date:
            try:
                datetime.date.fromisoformat(date)
            except (TypeError, ValueError):
                raise ValueError('Enter a valid purchase date.')
        interfaces = device.get('interfaces', [])
        if not isinstance(interfaces, list) or len(interfaces) > 256:
            raise ValueError('Provide at most 256 interfaces per device.')
        names = set()
        for interface in interfaces:
            if not isinstance(interface, dict) or not isinstance(interface.get('name'), str) or not interface['name'].strip() or interface['name'] in names:
                raise ValueError('Interface names must be non-empty and unique within a device.')
            names.add(interface['name'])
            if interface.get('type') not in INTERFACE_TYPES:
                raise ValueError('Choose a supported interface type.')
            speed = interface.get('speedMbps')
            if speed is not None and (type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 1600000):
                raise ValueError('Interface speed must be greater than zero, in Mbps.')
            if interface.get('mode', '') not in ('', 'Access', 'Trunk', 'Routed'):
                raise ValueError('Choose Access, Trunk or Routed for VLAN mode.')
            native = interface.get('nativeVlan')
            tagged = interface.get('taggedVlans', [])
            if native is not None and (type(native) is not int or not 1 <= native <= 4094):
                raise ValueError('Native VLAN must be between 1 and 4094.')
            if not isinstance(tagged, list) or len(tagged) > 4094 or any(type(v) is not int or not 1 <= v <= 4094 for v in tagged) or len(set(tagged)) != len(tagged):
                raise ValueError('Tagged VLANs must be unique numbers between 1 and 4094.')
            if interface.get('connector', '') not in ('', 'RJ45', 'SFP', 'SFP+', 'SFP28', 'QSFP+', 'QSFP28', 'QSFP-DD', 'LC', 'SC', 'MPO', 'DAC', 'Virtual', 'Other'):
                raise ValueError('Choose a supported interface connector.')
            if not isinstance(interface.get('ips', []), list) or len(interface.get('ips', [])) > 64:
                raise ValueError('Interface addresses must be a list of at most 64 IPs.')
            ips = set()
            for value in interface.get('ips', []):
                if not isinstance(value, str):
                    raise ValueError('Interface IP addresses must be text.')
                normalized = str(ipaddress.ip_address(value))
                if normalized in ips:
                    raise ValueError('Duplicate IP address on this interface.')
                ips.add(normalized)
        for interface in interfaces:
            lag = interface.get('lag')
            if lag and (interface.get('type') not in ('Ethernet', 'Fiber') or not any(i['name'] == lag and i['type'] == 'LAG' for i in interfaces)):
                raise ValueError('LAG membership must reference a LAG on the same device.')
