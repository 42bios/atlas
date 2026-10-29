import json
from .marketplace import Marketplace

def status(self,app):return self.json_response(200,Marketplace(app).status())
def icons(self,app):return self.json_response(200,Marketplace(app).icons())
def post(self,app):
    origin=self.headers.get('Origin')
    if origin and origin not in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')):return self.json_response(403,{'error':'Origin rejected'})
    try:
        length=int(self.headers.get('Content-Length',0))
        if not 0<length<=60000:raise ValueError('Marketplace requests must be smaller than 60 KB.')
        body=json.loads(self.rfile.read(length))
        if not isinstance(body,dict):raise ValueError('Provide a JSON object.')
        market=Marketplace(app);action=self.path.rsplit('/',1)[-1]
        if action=='source':result=market.source(body)
        elif action=='refresh':result=market.refresh(body.get('id'))
        elif action=='details':result=market.details(body.get('key'))
        elif action=='preview':result=market.preview(body.get('key'))
        elif action=='install':result=market.install(body)
        elif action=='remove':result=market.remove(body.get('key'))
        elif action=='rollback':result=market.rollback(body.get('key'))
        else:raise ValueError('Unknown marketplace action.')
        return self.json_response(200,result)
    except (OSError,ValueError,TypeError,KeyError) as error:return self.json_response(400,{'error':str(error)})
