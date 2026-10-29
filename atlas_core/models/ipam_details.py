import datetime
import ipaddress
import math

def validate_addresses(state):
    owners = {}
    for obj in state['devices'] + state['services'] + state['addresses']:
        primary = obj.get('ip', '')
        if not isinstance(primary, str):
            raise ValueError('IP addresses must be text.')
        assignments = [(primary, 'primary')] if primary.strip() else []
        assignments += [(ip, i['name']) for i in obj.get('interfaces', []) for ip in i.get('ips', [])]
        local = {}
        for value, interface in assignments:
            normalized = str(ipaddress.ip_address(value.strip()))
            if normalized in owners and owners[normalized] != obj['id']:
                raise ValueError('This IP address is already assigned or reserved.')
            if normalized in local and interface != 'primary' and local[normalized] != 'primary':
                raise ValueError('This IP address is assigned to multiple interfaces.')
            owners[normalized] = obj['id']
            local[normalized] = interface


def validate_planning(state):
    for record in state['addresses']:
        if record.get('status') not in (None, '', 'Reserved in Atlas', 'Reserved', 'Planned'):
            raise ValueError('Choose Planned or Reserved for an IP plan.')
        date = record.get('targetDate')
        if date:
            try:
                datetime.date.fromisoformat(date)
            except (TypeError, ValueError):
                raise ValueError('Enter a valid planning target date.')
    for network in state['networks']:
        if network.get('status') not in (None, '', 'Active', 'Planned'):
            raise ValueError('Choose Active or Planned for a network.')


def validate_network_metadata(state):
    prefixes = set()
    for network in state['networks']:
        subnet = ipaddress.ip_network(network['cidr'], strict=True)
        if subnet in prefixes:
            raise ValueError('This network prefix is already documented.')
        prefixes.add(subnet)
        def usable(value):
            address = ipaddress.ip_address(value)
            return address in subnet and (subnet.version != 4 or subnet.prefixlen >= 31 or address not in (subnet.network_address, subnet.broadcast_address))
        for key in ('gateway', 'dhcpStart', 'dhcpEnd'):
            if not isinstance(network.get(key, ''), str):
                raise ValueError('Network addresses must be text.')
        gateway = network.get('gateway', '')
        if gateway and not usable(gateway):
            raise ValueError('Gateway must be a usable address inside its network.')
        dns = network.get('dns', [])
        if not isinstance(dns, list) or len(dns) > 16 or any(not isinstance(v, str) for v in dns):
            raise ValueError('Provide at most 16 DNS server addresses.')
        for value in dns:
            ipaddress.ip_address(value)
        start, end = network.get('dhcpStart', ''), network.get('dhcpEnd', '')
        if bool(start) != bool(end):
            raise ValueError('Enter both DHCP pool start and end.')
        if start and (not usable(start) or not usable(end) or ipaddress.ip_address(start) > ipaddress.ip_address(end)):
            raise ValueError('DHCP pool must be an ordered usable range inside its network.')
