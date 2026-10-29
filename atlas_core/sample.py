"""Sample inventory, independent of storage and HTTP."""
def demo():
    return {
        'demo': True,
        'racks': [{'id': 'rack-1', 'name': 'Studio rack', 'units': 18, 'location': 'Home office', 'numbering': 'bottom'}],
        'devices': [
            {'id': 'gateway', 'name': 'Gateway', 'model': 'Rackmount gateway', 'kind': 'Router', 'rack': 'rack-1', 'unit': 18, 'height': 1, 'ip': '10.0.10.1', 'ports': 8, 'notes': 'Routes the management, services and IoT networks.'},
            {'id': 'switch', 'name': 'Core switch', 'model': '24-port PoE switch', 'kind': 'Switch', 'rack': 'rack-1', 'unit': 17, 'height': 1, 'ip': '10.0.10.2', 'ports': 24},
            {'id': 'patch', 'name': 'Patch panel', 'model': '24-port keystone panel', 'kind': 'Patch panel', 'rack': 'rack-1', 'unit': 16, 'height': 1, 'ip': '', 'ports': 24},
            {'id': 'atlas', 'name': 'Atlas', 'model': 'Virtualization server', 'kind': 'Server', 'rack': 'rack-1', 'unit': 12, 'height': 2, 'ip': '10.0.10.10', 'ports': 4, 'notes': 'Primary compute host. Rack positions and wiring are maintained manually.'},
            {'id': 'vault', 'name': 'Vault', 'model': '4-bay storage server', 'kind': 'NAS', 'rack': 'rack-1', 'unit': 8, 'height': 2, 'ip': '10.0.10.20', 'ports': 2},
            {'id': 'ups', 'name': 'Battery backup', 'model': 'Rackmount UPS', 'kind': 'UPS', 'rack': 'rack-1', 'unit': 1, 'height': 2, 'ip': '', 'ports': 0},
            {'id': 'pdu', 'name': 'PDU A', 'model': '8-outlet vertical PDU', 'kind': 'PDU', 'rack': 'rack-1', 'unit': 0, 'height': 0, 'ip': '', 'ports': 8},
        ],
        'networks': [
            {'id': 'management', 'name': 'Management', 'cidr': '10.0.10.0/24', 'vlan': 10, 'description': 'Physical infrastructure'},
            {'id': 'services', 'name': 'Services', 'cidr': '10.0.20.0/24', 'vlan': 20, 'description': 'Applications and virtual machines'},
            {'id': 'iot', 'name': 'IoT', 'cidr': '10.0.30.0/24', 'vlan': 30, 'description': 'Home devices'},
        ],
        'addresses': [{'id': 'reserved-1', 'ip': '10.0.20.50', 'name': 'Future application host', 'status': 'Reserved in Atlas'}],
        'services': [
            {'id': 'docker', 'name': 'Docker host', 'kind': 'Virtual machine', 'host': 'atlas', 'group': 'Infrastructure', 'ip': '10.0.20.10', 'port': '', 'url': '', 'image': '', 'notes': 'Example virtual machine on Atlas.'},
            {'id': 'photos', 'name': 'Photos', 'kind': 'Container', 'host': 'docker', 'group': 'Photos & documents', 'port': '2283', 'url': '', 'image': 'immich-server', 'notes': 'Example photo application.'},
            {'id': 'postgres', 'name': 'PostgreSQL', 'kind': 'Container', 'host': 'docker', 'group': 'Photos & documents', 'port': '5432', 'image': 'postgres:16'},
            {'id': 'redis', 'name': 'Redis', 'kind': 'Container', 'host': 'docker', 'group': 'Photos & documents', 'port': '6379', 'image': 'redis:7'},
            {'id': 'bookstack', 'name': 'BookStack', 'kind': 'Container', 'host': 'docker', 'group': 'Photos & documents', 'port': '6875', 'image': 'bookstack'},
            {'id': 'proxy', 'name': 'Reverse proxy', 'kind': 'Container', 'host': 'docker', 'group': 'Infrastructure', 'port': '443', 'image': 'caddy:2'},
            {'id': 'home', 'name': 'Home Assistant', 'kind': 'Virtual machine', 'host': 'atlas', 'group': 'Home automation', 'ip': '10.0.20.30', 'port': '8123'},
        ],
        'links': [
            {'id': 'l1', 'source': 'photos', 'target': 'postgres', 'type': 'Requires', 'sourcePort': '', 'targetPort': ''},
            {'id': 'l2', 'source': 'photos', 'target': 'redis', 'type': 'Requires', 'sourcePort': '', 'targetPort': ''},
            {'id': 'l3', 'source': 'photos', 'target': 'vault', 'type': 'Uses storage', 'sourcePort': '', 'targetPort': '/photos'},
            {'id': 'l4', 'source': 'proxy', 'target': 'photos', 'type': 'Routes to', 'sourcePort': '443', 'targetPort': '2283'},
            {'id': 'l5', 'source': 'atlas', 'target': 'pdu', 'type': 'Powered by', 'sourcePort': 'PSU 1', 'targetPort': '3'},
            {'id': 'l6', 'source': 'vault', 'target': 'pdu', 'type': 'Powered by', 'sourcePort': 'PSU 1', 'targetPort': '4'},
            {'id': 'l7', 'source': 'gateway', 'target': 'switch', 'type': 'Network', 'sourcePort': 'LAN 1', 'targetPort': '24'},
            {'id': 'l8', 'source': 'switch', 'target': 'atlas', 'type': 'Network', 'sourcePort': '8', 'targetPort': 'eth0'},
            {'id': 'l9', 'source': 'switch', 'target': 'vault', 'type': 'Network', 'sourcePort': '9', 'targetPort': 'eth0'},
        ],
        'stencils': [],
    }
