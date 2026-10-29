import math
import ipaddress
from .connections_details import validate_terminations

def validate(state):
    objects = {x['id']: x for x in state['devices'] + state['services']}
    outlets = set()
    for link in state['links']:
        if link.get('cableMedium') not in (None, '', 'copper', 'fiber', 'dac', 'aoc'):
            raise ValueError('Choose copper, fiber, DAC or AOC as the cable medium.')
        if link.get('dacMode') not in (None, '', 'active', 'passive'):
            raise ValueError('Choose active or passive DAC construction.')
        if 'cableSpeedMbps' in link and (type(link['cableSpeedMbps']) not in (int, float) or not 0 < link['cableSpeedMbps'] <= 1600000):
            raise ValueError('Cable rated speed must be between 1 and 1600000 Mbps.')
        if link.get('fiberType') not in (None, '', 'OS1', 'OS2', 'OM1', 'OM2', 'OM3', 'OM4', 'OM5'):
            raise ValueError('Choose a supported fiber type.')
        if 'fiberCount' in link and (type(link['fiberCount']) is not int or not 1 <= link['fiberCount'] <= 144):
            raise ValueError('Fiber count must be a whole number between 1 and 144.')
        if 'cableLength' in link and (type(link['cableLength']) not in (int, float) or not 0 < link['cableLength'] <= 100000):
            raise ValueError('Cable length must be greater than zero and at most 100000 m.')
        if link.get('source') not in objects or link.get('target') not in objects or link['source'] == link['target']:
            raise ValueError('Connections need two different existing objects.')
        if link.get('type') == 'Powered by':
            target = objects[link['target']]
            port = str(link.get('targetPort', ''))
            if target.get('kind') != 'PDU' or not port.isdigit() or not 1 <= int(port) <= int(target.get('ports', 0)):
                raise ValueError('Choose a valid PDU outlet number.')
            slot = (link['target'], int(port))
            if slot in outlets:
                raise ValueError('This PDU outlet is already assigned.')
            outlets.add(slot)
    validate_terminations(state)
