import datetime
import ipaddress
import math

def validate_terminations(state):
    objects = {o['id']: o for o in state['devices'] + state['services']}
    used = set()
    for link in state['links']:
        if link.get('type') == 'Wi-Fi':
            client, ap = objects.get(link.get('source')), objects.get(link.get('target'))
            if not client or client not in state['devices'] or client.get('kind') in ('Patch panel', 'Rack shelf', 'Network outlet', 'Cable management'):
                raise ValueError('Choose a device as the Wi-Fi client.')
            if not ap or ap.get('kind') not in ('Access point', 'Router'):
                raise ValueError('Choose an access point or wireless router for endpoint B.')
            if link.get('wifiBand', '') not in ('', '2.4 GHz', '5 GHz', '6 GHz', '60 GHz'):
                raise ValueError('Choose a supported Wi-Fi frequency band.')
            for key in ('ssid', 'bssid', 'wifiNotes'):
                if not isinstance(link.get(key, ''), str) or len(link.get(key, '')) > (2000 if key == 'wifiNotes' else 128):
                    raise ValueError('Wi-Fi details must be text within their length limits.')
        if link.get('type') == 'VPN' and link.get('vpnProtocol', 'Other') not in ('WireGuard', 'IPsec', 'OpenVPN', 'Tailscale', 'Other'):
            raise ValueError('Choose a supported VPN protocol.')
        if link.get('type') not in ('Network', 'Powered by'):
            continue
        for key in ('source', 'target'):
            obj = objects.get(link.get(key))
            if not obj:
                continue  # Existing link validation reports the missing object.
            port = str(link.get(key + 'Port', ''))
            if not port:
                continue  # Preserve older undocumented connections.
            if link['type'] == 'Network' and any(i['name'] == port and i['type'] == 'Wi-Fi' for i in obj.get('interfaces', [])):
                raise ValueError('Wi-Fi interfaces cannot terminate physical cables.')
            if link['type'] == 'Network' and obj.get('kind') in ('Patch panel', 'Network outlet'):
                face, sep, number = port.partition(':')
                if not sep:
                    face, number = 'front', port
                names = [i['name'] for i in obj.get('interfaces', [])] or [str(n) for n in range(1, int(obj.get('ports', 0)) + 1)]
                if face not in ('front', 'rear') or number not in names:
                    raise ValueError('Choose an existing front or rear patch-panel port.')
                port = face + ':' + number
            elif link['type'] == 'Network' and any(i['type'] in ('Ethernet', 'Fiber') for i in obj.get('interfaces', [])):
                if not any(i['name'] == port and i['type'] in ('Ethernet', 'Fiber') for i in obj['interfaces']) and not (port.isdigit() and 1 <= int(port) <= int(obj.get('ports', 0))):
                    raise ValueError('Network cables must terminate on a physical interface.')
            if link['type'] == 'Network' and not obj.get('interfaces') and port.isdigit() and not 1 <= int(port) <= int(obj.get('ports', 0)):
                raise ValueError('Port number is outside the device port count.')
            slot = (link['type'], obj['id'], port)
            if slot in used:
                raise ValueError('This physical port is already connected.')
            used.add(slot)
