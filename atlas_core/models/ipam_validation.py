import math
import ipaddress
from .ipam_details import validate_addresses, validate_planning, validate_network_metadata

def validate(state):
    validate_planning(state)
    validate_addresses(state)
    for network in state['networks']:
        ipaddress.ip_network(network.get('cidr', ''), strict=True)
        if type(network.get('vlan')) is not int or not 0 <= network['vlan'] <= 4094:
            raise ValueError('VLAN must be between 0 (untagged) and 4094.')
    validate_network_metadata(state)
