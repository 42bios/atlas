"""Serve only active plugin assets, with private scopes and declared bindings."""
import json
from pathlib import Path

def plugin_script(source, owner, bindings):
    entries=[]
    for item in bindings:
        name=item['name']
        setter=',set:value=>{'+name+'=value;}' if item['writable'] else ''
        entries.append(json.dumps(name)+':{get:()=>'+name+setter+'}')
    # Private function scope preserves closures and legacy feature implementation.
    return 'AtlasPluginHost.load('+json.dumps(owner)+',function(pluginContext,publish){with(pluginContext){\n'+source+'\npublish({'+','.join(entries)+'});\n}});\n'

def active_assets(manifest):
    enabled={m['id'] for m in manifest['modules'] if m.get('enabled',True)}
    return [a for a in manifest['assets'] if a['owner'] in enabled]
