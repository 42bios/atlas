import math
import ipaddress

def validate(state):
    objects = {x['id']: x for x in state['devices'] + state['services']}
    for service in state['services']:
        current, seen = service, {service['id']}
        while current.get('host'):
            host = current['host']
            if host not in objects or host in seen:
                raise ValueError('Host assignments must reference existing objects without a cycle.')
            seen.add(host)
            current = objects[host]
