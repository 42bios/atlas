"""Build the handbook's declared route table from installed package manifests."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'docs/handbook/api-reference.md'
START='<!-- BEGIN GENERATED ROUTES -->'
END='<!-- END GENERATED ROUTES -->'
rows=[]
for file in sorted((ROOT/'atlas_modules').glob('*/plugin.json')):
    package=json.loads(file.read_text())
    for method,path in package.get('backendRoutes',[]):
        access='Connector-scoped Bearer token' if path in ('/api/v1/connectors/snapshot','/api/v1/connectors/status') else 'Trusted application access'
        rows.append((path,method,package['id'],access))
table='| Method | Path | Owner | Access model |\n| --- | --- | --- | --- |\n'
for path,method,owner,access in sorted(rows):table+=f'| {method} | `{path}` | {owner} | {access} |\n'
text=TARGET.read_text();before,rest=text.split(START,1);_,after=rest.split(END,1)
TARGET.write_text(before+START+'\n'+table+END+after)
print(f'Generated {len(rows)} declared routes')
