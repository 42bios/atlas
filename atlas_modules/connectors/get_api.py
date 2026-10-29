import json
from urllib.parse import urlsplit, parse_qs
from . import setup, engine, contract
from .download import connector_package_response

def addins(self, app): return self.json_response(200, app.addins().status())
def packages(self, app): return self.json_response(200, setup.PLUGINS)
def connector_contract(self, app): return self.json_response(200, contract.CONTRACT)
def schema(self, app): return self.json_response(200, engine.SCHEMA)
def installed(self, app): return self.json_response(200, [{k:v for k,v in item.items() if not k.startswith('_')} for item in engine.installed()])
def reports(self, app):
    with app.connection() as con:
        con.execute('CREATE TABLE IF NOT EXISTS plugin_status (id TEXT PRIMARY KEY, body TEXT)')
        return self.json_response(200,[json.loads(row[0]) for row in con.execute('SELECT body FROM plugin_status ORDER BY id')])
def package(self, app):
    try:
        if len(self.path)>10000: raise ValueError('Connector setup URL is too long.')
        values=parse_qs(urlsplit(self.path).query,strict_parsing=True)
        if set(values)!={'configuration'} or len(values['configuration'])!=1: raise ValueError('Provide one setup configuration.')
        return connector_package_response(self,json.loads(values['configuration'][0]),app)
    except (OSError,ValueError,TypeError,KeyError) as error: return self.json_response(400,{'error':str(error)})
routes={('GET',path):handler for path,handler in [('/api/v1/addins',addins),('/api/v1/connector-packages',packages),('/api/v1/connector-contract',connector_contract),('/api/connector-schema',schema),('/api/connectors',installed),('/api/v1/connectors',reports),('/api/v1/connector-setup/package',package)]}
