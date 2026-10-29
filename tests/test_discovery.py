import importlib.util
from pathlib import Path
import unittest
from server import demo,validate
from connector_engine import merge

def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parent.parent/'plugins'/name/'collector.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class DiscoveryTests(unittest.TestCase):
    def test_interface_validation(self):
        for field,value in [('speedMbps',0),('speedMbps',float('nan')),('nativeVlan',4095),('taggedVlans',[2,2]),('taggedVlans',[2.5]),('connector','invalid')]:
            data=demo();data['links']=[];data['devices'][0]['interfaces']=[dict(name='eth0',type='Ethernet',ips=[],**{field:value})]
            with self.assertRaises(ValueError):validate(data)
        data=demo();data['links']=[];data['devices'][0]['interfaces']=[dict(name='eth0',type='Fiber',speedMbps=25000,connector='SFP28',mode='Trunk',nativeVlan=10,taggedVlans=[20,30],ips=[])]
        validate(data)

    def test_snmp_scope_and_index_mapping(self):
        m=load('snmp')
        self.assertEqual(len(m.targets({'targets':['192.0.2.0/30']})),2)
        with self.assertRaises(ValueError):m.targets({'targets':['192.0.0.0/16']})
        tables={'description':{'101':'uplink','102':'access'},'type':{'101':'6','102':'6'},'name':{'101':'Gi1','102':'Gi2'},'highSpeed':{'101':'10000'},'oper':{'101':'1','102':'2'},'bridge':{'1':'101','2':'102'},'pvid':{'2':'20'},'localPort':{'9':'Gi1'},'neighborName':{'0.9.1':'switch-b'},'neighborPort':{'0.9.1':'Gi7'},'egress':{'0.30':'C0'},'untagged':{'0.30':'40'},'fdb':{'0.1.2.3.4.5':'2'}}
        device=m.build_device('192.0.2.1',{'name':'switch-a'},tables,'now')
        self.assertEqual(device['interfaces'][0]['speedMbps'],10000)
        self.assertEqual(device['interfaces'][0]['observation']['neighbors'][0]['port'],'Gi7')
        self.assertEqual(device['interfaces'][0]['taggedVlans'],[30])
        self.assertEqual(device['interfaces'][1]['nativeVlan'],20)
        self.assertEqual(device['interfaces'][1]['observation']['learnedMacs'],['00:01:02:03:04:05'])
        snap=m.collect(lambda a:{'name':'test'},lambda a,oid:tables.get(next((k for k,v in m.OIDS.items() if v==oid),'')),{'targets':['192.0.2.1']},'test-snmp')
        self.assertEqual(snap['links'],[])
        data=demo();data['links']=[];validate(merge(data,snap)[0])

    def test_kubernetes_ownership_endpoints_and_no_secrets(self):
        m=load('kubernetes');resources={k:[] for k in m.RESOURCES}
        def item(uid,name,namespace=None,**kwargs):return {'metadata':dict(uid=uid,name=name,**({'namespace':namespace} if namespace else {})),**kwargs}
        resources['Namespace']=[item('ns','apps')];resources['Node']=[item('node','worker')]
        dep=item('dep','web','apps',spec={'replicas':2});resources['Deployment']=[dep]
        rs=item('rs','web-rs','apps');rs['metadata']['ownerReferences']=[{'uid':'dep','controller':True}];resources['ReplicaSet']=[rs]
        pod=item('pod','web-pod','apps',spec={'nodeName':'worker','containers':[{'name':'web','image':'nginx','env':[{'value':'SECRET'}]}]});pod['metadata']['ownerReferences']=[{'uid':'rs','controller':True}];resources['Pod']=[pod]
        resources['Service']=[item('svc','web','apps',spec={'clusterIPs':['10.0.0.1']})]
        slice=item('slice','web-1','apps',endpoints=[{'targetRef':{'uid':'pod'}}]);slice['metadata']['labels']={'kubernetes.io/service-name':'web'};resources['EndpointSlice']=[slice]
        result=m.collect(lambda path:{'items':resources[next(k for k,v in m.RESOURCES.items() if path.startswith(v+'?'))]},'kube-test')
        records={r['id']:r for r in result['services']};self.assertEqual(records['pod']['host'],'rs');self.assertEqual(records['rs']['host'],'dep')
        self.assertTrue(any(l['type']=='Scheduled on' and l['target']=='node' for l in result['links']))
        self.assertTrue(any(l['type']=='Routes to' and l['source']=='svc' for l in result['links']))
        self.assertNotIn('SECRET',str(result));validate(merge(demo(),result)[0])
        with self.assertRaises(RuntimeError):m.collect(lambda path:(_ for _ in ()).throw(RuntimeError('denied')),'kube-test')
