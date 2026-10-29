"""Compose installed feature packages without importing inactive route code."""
from pathlib import Path
from atlas_core.modules import ModuleRegistry
from atlas_core.plugin_packages import discover
ROOT = Path(__file__).resolve().parent
manifests, modules, assets = discover(ROOT)
registry = ModuleRegistry(manifests, modules, assets)
