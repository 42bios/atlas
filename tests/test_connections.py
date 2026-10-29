import unittest
from server import demo, validate

class ConnectionCableTests(unittest.TestCase):
    def test_direct_attach_cables(self):
        for medium in ('dac', 'aoc'):
            s=demo();l=next(x for x in s['links'] if x['type']=='Network')
            l.update(cableMedium=medium,sourceConnector='SFP+',targetConnector='SFP28',cableSpeedMbps=10000,cableLength=3)
            if medium=='dac': l['dacMode']='passive'
            validate(s)
            l['cableSpeedMbps']=-1
            with self.assertRaisesRegex(ValueError,'rated speed'):validate(s)
    def test_invalid_dac_mode(self):
        s=demo();s['links'][0]['dacMode']='invalid'
        with self.assertRaisesRegex(ValueError,'DAC'):validate(s)
    def test_wifi_clients_outside_racks_and_shared_ap(self):
        s=demo()
        for i in range(2):
            s['devices'].append(dict(id=f'wifi-{i}',name=f'Laptop {i}',kind='Laptop',rack='',height=1,unit=0,ports=0,interfaces=[dict(name='wlan0',type='Wi-Fi',ips=[],lag='')]))
            s['links'].append(dict(id=f'wireless-{i}',source=f'wifi-{i}',target='gateway',type='Wi-Fi',ssid='Home',wifiBand='5 GHz',sourcePort='wlan0',targetPort='radio0'))
        validate(s)
        s['links'][-1]['target']='switch'
        with self.assertRaisesRegex(ValueError,'access point'):validate(s)
