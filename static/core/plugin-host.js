// Trusted built-in plugin contexts. Each file has a private lexical scope and a
// declared binding interface; only the host and module registry are globals.
const AtlasPluginHost=(()=>{
 const namespaces=new Map(),owners=new Map();let manifests=new Map();
 function configure(modules){manifests=new Map(modules.map(m=>[m.id,m]));for(const m of modules)namespaces.set(m.id,new Map());}
 function dependencies(id,result=new Set()){if(result.has(id))return result;result.add(id);for(const dep of manifests.get(id)?.requires||[])dependencies(dep,result);return result;}
 function allowed(id,owner){return dependencies(id).has(owner)||(manifests.get(id)?.optional||[]).includes(owner);}
 function binding(id,key){const own=namespaces.get(id)?.get(key);if(own)return own;const owner=owners.get(key);if(owner&&allowed(id,owner))return namespaces.get(owner).get(key);if(owner)throw Error(`Plugin ${id} needs a declared dependency on ${owner} for ${key}`);}
 function scope(id){return new Proxy(Object.create(null),{has(_,key){if(typeof key!=='string')return false;return !!binding(id,key);},get(_,key){if(key===Symbol.unscopables)return undefined;return binding(id,key)?.get();},set(_,key,value){const target=binding(id,key);if(!target?.set)throw Error(`Read-only plugin binding: ${id}.${String(key)}`);target.set(value);return true;}});}
 function publish(id,values){const space=namespaces.get(id);if(!space)throw Error('Unknown plugin: '+id);for(const [key,value]of Object.entries(values)){const owner=owners.get(key);if(owner&&owner!==id)throw Error(`Duplicate plugin export ${key}: ${owner}, ${id}`);space.set(key,value);owners.set(key,id);}}
 function load(id,factory){if(manifests.get(id)?.enabled===false)throw Error('Disabled plugin attempted to load: '+id);factory(scope(id),values=>publish(id,values));}
 function inspect(){return [...namespaces].filter(([,v])=>v.size).map(([id,values])=>({id,bindings:[...values.keys()]}));}
 return Object.freeze({configure,load,context:scope,inspect});
})();
