import copy
import unittest
from server import demo, validate


class DetailTests(unittest.TestCase):
    def device(self):
        data = demo()
        device = data['devices'][0]
        device['interfaces'] = [dict(name='eth0', type='Ethernet', ips=['192.0.2.2'], lag='bond0'), dict(name='bond0', type='LAG', ips=[])]
        data['links'] = [l for l in data['links'] if device['id'] not in (l['source'], l['target'])]
        return data, device

    def test_multiple_ips_and_primary_alias(self):
        data, device = self.device()
        device['ip'] = '192.0.2.2'
        device['interfaces'][0]['ips'].append('2001:db8::2')
        validate(data)
        device['interfaces'].append(dict(name='eth1', type='Ethernet', ips=['192.0.2.2']))
        with self.assertRaisesRegex(ValueError, 'multiple interfaces'):
            validate(data)

    def test_duplicate_interface_ip_across_devices(self):
        data, device = self.device()
        data['devices'][1]['interfaces'] = [dict(name='eth0', type='Ethernet', ips=['192.0.2.2'])]
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            validate(data)

    def test_invalid_lag(self):
        data, device = self.device()
        device['interfaces'][0]['lag'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'LAG'):
            validate(data)

    def test_fixed_model(self):
        data, device = self.device()
        device['hardwareSpec'] = {k: device[k] for k in ('kind', 'model', 'height', 'ports')}
        validate(data)
        device['height'] += 1
        device['rack'] = ''
        with self.assertRaisesRegex(ValueError, 'specifications cannot'):
            validate(data)

    def test_coordinates_and_date(self):
        data, device = self.device()
        data['racks'][0].update(latitude=46.5, longitude=11.3)
        device['purchaseDate'] = '2026-10-02'
        validate(data)
        data['racks'][0]['latitude'] = 91
        with self.assertRaisesRegex(ValueError, 'latitude'):
            validate(data)

    def test_port_occupancy(self):
        data, device = self.device()
        data['links'] = [dict(id='new1', source=device['id'], sourcePort='eth0', target=data['devices'][1]['id'], targetPort='1', type='Network')]
        validate(data)
        data['links'].append(dict(id='new2', source=device['id'], sourcePort='eth0', target=data['devices'][2]['id'], targetPort='2', type='Network'))
        with self.assertRaisesRegex(ValueError, 'physical port is already'):
            validate(data)

    def test_cable_cannot_use_lag(self):
        data, device = self.device()
        data['links'] = [dict(id='new1', source=device['id'], sourcePort='bond0', target=data['devices'][1]['id'], targetPort='1', type='Network')]
        with self.assertRaisesRegex(ValueError, 'physical interface'):
            validate(data)

    def test_vpn_does_not_occupy_ports(self):
        data, device = self.device()
        data['links'] = [dict(id='vpn'+str(n), source=device['id'], target=data['devices'][1]['id'], type='VPN', sourcePort='wg0', targetPort='wg0', vpnProtocol='WireGuard') for n in range(2)]
        data['networks'].append(dict(id='v6', name='IPv6', cidr='2001:db8::/64', vlan=0))
        validate(data)
