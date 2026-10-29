import unittest
from server import demo,validate

class IPAMTests(unittest.TestCase):
    def test_network_details(self):
        s=demo();n=s['networks'][0];n.update(gateway='10.0.10.1',dns=['1.1.1.1','2001:4860:4860::8888'],dhcpStart='10.0.10.100',dhcpEnd='10.0.10.200');validate(s)
        for change in [{'gateway':'10.0.20.1'},{'dhcpEnd':'10.0.10.50'},{'dhcpEnd':''},{'dns':['bad']},{'dhcpStart':'10.0.10.0'},{'gateway':123}]:
            old=dict(n);n.update(change)
            with self.assertRaises(ValueError):validate(s)
            n.clear();n.update(old)
    def test_duplicate_prefix_and_nested_prefix(self):
        s=demo();s['networks'].append(dict(id='child',name='Child',cidr='10.0.10.0/25',vlan=10));validate(s)
        s['networks'][-1]['cidr']='10.0.10.0/24'
        with self.assertRaisesRegex(ValueError,'already documented'):validate(s)
    def test_small_prefix_and_ipv6_ranges(self):
        s=demo();s['networks']=[dict(id='small',name='Point to point',cidr='192.0.2.0/31',vlan=0,gateway='192.0.2.0'),dict(id='v6',name='IPv6',cidr='2001:db8::/64',vlan=0,dhcpStart='2001:db8::100',dhcpEnd='2001:db8::ffff')];validate(s)
        s['networks'][1]['dhcpEnd']='2001:db9::1'
        with self.assertRaises(ValueError):validate(s)
