import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from common.runtime import run, secret
from collector import collect

VALUE=re.compile(r'^\.?([0-9.]+)\s*=\s*(.*)$')
def parse(raw, root):
    if 'No Such Object' in raw:return None
    result={}
    for line in raw.splitlines():
        match=VALUE.match(line)
        if not match: continue
        oid,value=match.groups()
        if 'No Such' in value or 'No more variables' in value: continue
        if not oid.startswith(root+'.'): continue
        value=re.sub(r'^[A-Za-z0-9 -]+:\s*','',value).strip().strip('"')
        enum=re.fullmatch(r'[^()]+\((\d+)\)',value)
        if enum: value=enum.group(1)
        result[oid[len(root)+1:]]=value
    return result

def snapshot(source):
    config=json.loads(Path(os.environ['DISCOVERY_CONFIG_FILE']).read_text())
    version=config.get('version','2c')
    if version not in ('2c','3'): raise ValueError('Supported SNMP versions: 2c and 3')
    # Credentials are private config files, never process arguments or log output.
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'snmp.conf'
        if version=='2c': settings='defCommunity '+secret('SNMP_COMMUNITY_FILE')+'\n'
        else:
            creds=json.loads(Path(os.environ['SNMP_CREDENTIALS_FILE']).read_text())
            settings='\n'.join('def'+key+' '+str(creds[key]) for key in ('SecurityName','SecurityLevel','AuthType','AuthPassphrase','PrivType','PrivPassphrase') if key in creds)+'\n'
        if any('\n' in v or '\r' in v for v in ([secret('SNMP_COMMUNITY_FILE')] if version=='2c' else [str(v) for v in creds.values()])): raise ValueError('Invalid credential value')
        path.write_text(settings);path.chmod(0o600)
        env={**os.environ,'SNMPCONFPATH':directory,'MIBS':''}
        def command(tool,address,oid):
            proc=subprocess.run([tool,'-v',version,'-t','1','-r','0','-On',address,oid],env=env,capture_output=True,text=True,timeout=35)
            return proc.stdout if proc.returncode==0 else None
        def probe(address):
            root='1.3.6.1.2.1.1'
            raw=command('snmpget',address,root+'.1.0')
            if not raw:return None
            descr=(parse(raw,root) or {}).get('1.0')
            if not descr:return None
            rawname=command('snmpget',address,root+'.5.0') or ''
            return dict(description=descr,name=(parse(rawname,root) or {}).get('5.0',''))
        def walk(address,oid):
            try: raw=command('snmpwalk',address,oid)
            except subprocess.TimeoutExpired:return None
            return parse(raw,oid) if raw is not None else None
        return collect(probe,walk,config,source)

if __name__=='__main__':run('snmp-discovery',snapshot)
