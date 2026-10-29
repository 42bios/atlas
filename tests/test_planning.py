import unittest
from server import demo, validate


class PlanningTests(unittest.TestCase):
    def test_planned_address_and_network(self):
        data = demo()
        data['addresses'][0].update(status='Planned', plannedFor='future-host', targetDate='2026-12-01')
        data['networks'][0]['status'] = 'Planned'
        validate(data)
        data['addresses'][0]['targetDate'] = '2026-02-31'
        with self.assertRaisesRegex(ValueError, 'target date'):
            validate(data)

    def test_planned_addresses_block_duplicate_assignments(self):
        data = demo()
        data['addresses'][0]['status'] = 'Planned'
        data['devices'][0]['ip'] = data['addresses'][0]['ip']
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            validate(data)

    def test_front_and_rear_patch_panel_connections(self):
        data = demo()
        data['links'] = [dict(id='a', type='Network', source='gateway', sourcePort='2', target='patch', targetPort='front:1'), dict(id='b', type='Network', source='patch', sourcePort='rear:1', target='switch', targetPort='2')]
        validate(data)
        data['links'].append(dict(id='c', type='Network', source='atlas', sourcePort='2', target='patch', targetPort='1'))
        with self.assertRaisesRegex(ValueError, 'already connected'):
            validate(data)

    def test_invalid_patch_panel_side(self):
        data = demo()
        data['links'] = [dict(id='a', type='Network', source='gateway', sourcePort='2', target='patch', targetPort='side:1')]
        with self.assertRaisesRegex(ValueError, 'front or rear'):
            validate(data)

    def test_assigning_a_plan_keeps_other_addresses(self):
        data = demo()
        plan = data['addresses'].pop()
        device = data['devices'][0]
        primary = device['ip']
        device['interfaces'] = [dict(name='ipam0', type='Virtual', ips=[plan['ip']])]
        validate(data)
        self.assertEqual(device['ip'], primary)
        self.assertEqual(device['interfaces'][0]['ips'], [plan['ip']])
