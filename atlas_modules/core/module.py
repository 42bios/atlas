"""Shared inventory validation."""
from atlas_core.modules import Module

from atlas_core.models.hardware_validation import validate as hardware
from atlas_core.models.applications_validation import validate as applications
from atlas_core.models.ipam_validation import validate as ipam
from atlas_core.models.connections_validation import validate as connections

module = Module("core", {}, (hardware, applications, ipam, connections))
