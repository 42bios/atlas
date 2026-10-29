"""Compatibility import; implementation belongs to the module package."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('atlas_modules.connectors.manager')
