"""SNMP inventory. LLDP and learned MACs are observations, never fabricated cables."""
import datetime
import ipaddress
import re
from concurrent.futures import ThreadPoolExecutor

OIDS={'description':'1.3.6.1.2.1.2.2.1.2','type':'1.3.6.1.2.1.2.2.1.3','speed':'1.3.6.1.2.1.2.2.1.5','mac':'1.3.6.1.2.1.2.2.1.6','admin':'1.3.6.1.2.1.2.2.1.7','oper':'1.3.6.1.2.1.2.2.1.8','name':'1.3.6.1.2.1.31.1.1.1.1','highSpeed':'1.3.6.1.2.1.31.1.1.1.15','alias':'1.3.6.1.2.1.31.1.1.1.18','connectorPresent':'1.3.6.1.2.1.31.1.1.1.17','bridge':'1.3.6.1.2.1.17.1.4.1.2','pvid':'1.3.6.1.2.1.17.7.1.4.5.1.1','localPort':'1.0.8802.1.1.2.1.3.7.1.3','localPortDescription':'1.0.8802.1.1.2.1.3.7.1.4','neighborName':'1.0.8802.1.1.2.1.4.1.1.9','neighborPort':'1.0.8802.1.1.2.1.4.1.1.7','neighborChassis':'1.0.8802.1.1.2.1.4.1.1.5','fdb':'1.3.6.1.2.1.17.4.3.1.2','qfdb':'1.3.6.1.2.1.17.7.1.2.2.1.2','egress':'1.3.6.1.2.1.17.7.1.4.2.1.4','untagged':'1.3.6.1.2.1.17.7.1.4.2.1.5','arp':'1.3.6.1.2.1.4.22.1.2'}

def targets(config):
    values=set()
    for value in config.get('targets', []):
        net=ipaddress.ip_network(value, strict=False)
        if net.version != 4 or net.num_addresses > 1024: raise ValueError('Discovery scope must be IPv4 and at most 1024 addresses')
        values.update(str(a) for a in (net.hosts() if net.prefixlen < 31 else net))
        if len(values)>1024: raise ValueError('Discovery scope exceeds 1024 addresses')
    if not values: raise ValueError('Configure explicit discovery networks or addresses')
    return sorted(values,key=ipaddress.ip_address)

def build_device(address, system, tables, observed_at):
    interfaces=[]; names=set(); by_index={}
    for idx, descr in tables.get('description', {}).items():
        # Physical Ethernet only; do not call loopbacks, VLANs or CPU ports free switch ports.
        if str(tables.get('type', {}).get(idx)) not in ('6','ethernetCsmacd(6)'): continue
        name=tables.get('name', {}).get(idx) or descr
        if not name or name in names:
            base=(name or 'port')+'-'+str(idx);name=base;suffix=2
            while name in names:name=base+'-'+str(suffix);suffix+=1
        names.add(name)
        high=tables.get('highSpeed', {}).get(idx, '0')
        speed=float(high) if str(high).isdigit() and int(high)>0 else float(tables.get('speed', {}).get(idx,'0'))/1000000 if str(tables.get('speed', {}).get(idx,'')).isdigit() else 0
        obs=dict(observedAt=observed_at, operStatus={'1':'up','2':'down'}.get(str(tables.get('oper', {}).get(idx)),'unknown'), adminStatus={'1':'up','2':'down'}.get(str(tables.get('admin', {}).get(idx)),'unknown'),neighbors=[],learnedMacs=[])
        present=str(tables.get('connectorPresent', {}).get(idx,''))
        virtual=present=='2' or bool(re.match(r'^(br|vlan|wifi|wlan|ath|veth|docker|tun|tap)',name,re.I)) or '.' in name
        rec=dict(name=name,type='Virtual' if virtual else 'Ethernet',ips=[],lag='',observation=obs,description=tables.get('alias', {}).get(idx,'') or descr)
        if 0<speed<=1600000 and (str(high).isdigit() and int(high)>0 or str(tables.get('speed', {}).get(idx,''))!='4294967295'): rec['speedMbps']=speed
        mac=tables.get('mac', {}).get(idx)
        if mac:
            try: rec['mac']=':'.join(f'{b:02x}' for b in bytes.fromhex(mac))
            except ValueError: rec['mac']=mac
        interfaces.append(rec); by_index[str(idx)]=rec
    bridge=tables.get('bridge', {})
    for port,idx in bridge.items():
        rec=by_index.get(str(idx));pvid=str(tables.get('pvid', {}).get(port,''))
        if rec and pvid.isdigit() and 1<=int(pvid)<=4094: rec['nativeVlan']=int(pvid)
    def bitmap(value):
        try:
            data=bytes.fromhex(value.replace(' ', ''))
            return {byte*8+bit+1 for byte,val in enumerate(data) for bit in range(8) if val & (128 >> bit)}
        except ValueError:
            return None
    for key,value in tables.get('egress', {}).items():
        vlan=key.split('.')[-1]
        members=bitmap(value);untagged=bitmap(tables.get('untagged', {})[key]) if key in tables.get('untagged', {}) else None
        if not vlan.isdigit() or not 1<=int(vlan)<=4094 or members is None or untagged is None: continue
        for port in members-untagged:
            rec=by_index.get(str(bridge.get(str(port))))
            if rec: rec.setdefault('taggedVlans', []).append(int(vlan))
    for rec in interfaces:
        if rec.get('taggedVlans'): rec['taggedVlans']=sorted(set(rec['taggedVlans']))
    # LLDP local port numbers are NOT ifIndex. Match advertised local IDs to ifName/ifDescr.
    unmatched=[]
    for key, neighbor in tables.get('neighborName', {}).items():
        parts=key.split('.')
        if len(parts)!=3: continue
        local=tables.get('localPort', {}).get(parts[1])
        description=tables.get('localPortDescription', {}).get(parts[1])
        labels={str(v) for v in (local,description) if v}
        # Some agents advertise Port N but explicitly describe Slot S / Port P.
        # Match that identity to S/P; never assume the LLDP local number is ifIndex.
        slot=re.search(r'Slot:\s*(\d+)\s+Port:\s*(\d+)(?:\s|$)',description or '',re.I)
        if slot:labels.add(slot[1]+'/'+slot[2])
        candidates=[r for idx,r in by_index.items() if labels.intersection({r['name'],tables.get('description', {}).get(idx)})]
        peer=dict(name=neighbor,port=tables.get('neighborPort', {}).get(key,''),chassis=tables.get('neighborChassis', {}).get(key,''))
        if len(candidates)==1:
            rec=candidates[0]
            if peer not in rec['observation']['neighbors']:rec['observation']['neighbors'].append(peer)
        else:
            observation={**peer,'localPortId':local or '', 'localPortDescription':description or '', 'reason':'ambiguous' if candidates else 'unmatched'}
            if observation not in unmatched:unmatched.append(observation)
    forwarding={**tables.get('fdb', {}),**{'.'.join(k.split('.')[-6:]):v for k,v in tables.get('qfdb', {}).items()}}
    for mac,port in forwarding.items():
        rec=by_index.get(str(bridge.get(str(port))))
        parts=mac.split('.')
        if rec and len(parts)==6 and all(p.isdigit() and int(p)<=255 for p in parts): rec['observation']['learnedMacs'].append(':'.join(f'{int(p):02x}' for p in parts))
    for rec in interfaces:rec['observation']['learnedMacs']=sorted(set(rec['observation']['learnedMacs']))
    advertised=system.get('name','')
    # Bridge support alone cannot distinguish a switch from an AP or a router.
    kind='Switch' if advertised.upper().startswith('USW') else 'Access point' if advertised.upper().startswith(('U6-','U7-','UAP-')) else 'Router' if advertised.upper().startswith(('UXG-','UDM-','USG-')) else 'Other'
    return dict(id='snmp-'+address.replace('.','-'),name=advertised or address,kind=kind,model=system.get('description','SNMP device'),ports=sum(i['type']=='Ethernet' for i in interfaces),interfaces=interfaces,ip=address,discovery=dict(protocol='SNMP',address=address,observedAt=observed_at,unsupportedTables=[k for k in OIDS if k not in tables],emptyTables=[k for k in OIDS if k in tables and not tables[k]],unmatchedNeighbors=unmatched))

def collect(probe, walk, config, source):
    addresses=targets(config)
    with ThreadPoolExecutor(max_workers=24) as pool: found=list(pool.map(probe,addresses))
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();devices=[];arp={}
    for address,system in zip(addresses,found):
        if not system: continue
        tables={}
        for key,oid in OIDS.items():
            result=walk(address,oid)
            if result is not None: tables[key]=result
        if not tables.get('description') or not tables.get('type'): raise ValueError('Detected device interface inventory failed; keep previous snapshot')
        for key,mac in tables.get('arp', {}).items():
            try:
                normalized=':'.join(f'{b:02x}' for b in bytes.fromhex(mac))
                ip=str(ipaddress.ip_address('.'.join(key.split('.')[-4:])))
                arp.setdefault(normalized,set()).add(ip)
            except ValueError: pass
        devices.append(build_device(address,system,tables,now))
    if not devices:raise ValueError('No SNMP devices responded; check scope, reachability and credentials. Previous inventory is retained.')
    for device in devices:
        for interface in device['interfaces']:
            interface['observation']['learnedEndpoints']=[{'mac':mac,'ips':sorted(arp.get(mac,[]))} for mac in interface['observation']['learnedMacs']]
    return dict(schemaVersion=1,connector=source,devices=devices,services=[],networks=[],links=[])
