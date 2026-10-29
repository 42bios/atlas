"""connectors feature registration."""
from atlas_core.modules import Module
from .api import addin_post, connector_setup_post, connector_post, snapshot_post
from .get_api import routes
from . import marketplace_api

module = Module('connectors', {**routes,
 ('GET','/api/v1/marketplace'):marketplace_api.status,('GET','/api/v1/icon-library'):marketplace_api.icons,
 **{('POST','/api/v1/marketplace/'+p):marketplace_api.post for p in ('source','refresh','preview','install','remove','rollback','details')},
 **{('POST',p):addin_post for p in ('/api/v1/addins/configure','/api/v1/addins/action','/api/v1/addins/repository/preview','/api/v1/addins/repository/install','/api/v1/addins/repository/access','/api/v1/addins/migration/rollback')},
 **{('POST',p):connector_setup_post for p in ('/api/v1/connector-setup/preview','/api/v1/connector-setup/package')},
 **{('POST',p):connector_post for p in ('/api/v1/connectors/snapshot','/api/v1/connectors/status')},
 **{('POST',p):snapshot_post for p in ('/api/import','/api/sync')}})
