"""settings feature registration."""
from atlas_core.modules import Module
from . import backups
from .api import do_PUT, get_state, get_inventory

module = Module('settings', {('GET', '/api/state'):get_state, ('GET', '/api/v1/inventory'):get_inventory, ('PUT', '/api/state'):do_PUT, ('GET','/api/v1/backups'):backups.status, ('POST','/api/v1/backups'):backups.post})
