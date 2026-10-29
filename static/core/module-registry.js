// Built-in features declare pages and lifecycle hooks. The host composes them.
const AtlasModules=(()=>{
 let manifest={modules:[],assets:[]};const features=new Map();let mounted='';
 function configure(value){if(value?.schemaVersion!==1)throw Error('Unsupported module manifest');const ids=new Set(value.modules.map(m=>m.id));if(ids.size!==value.modules.length)throw Error('Duplicate module ID');for(const m of value.modules)for(const dependency of m.requires)if(!ids.has(dependency))throw Error('Missing module dependency: '+dependency);manifest=value;}
 function register(id,implementation){if(!manifest.modules.some(m=>m.id===id))throw Error('Unknown module: '+id);if(features.has(id))throw Error('Module already registered: '+id);features.set(id,implementation);}
 function pages(){return manifest.modules.filter(m=>m.enabled!==false).flatMap(m=>m.pages.map(page=>({...page,module:m.id}))).sort((a,b)=>a.order-b.order);}
 function render(page){const p=pages().find(p=>p.id===page);const module=features.get(p?.module);if(!module?.views?.[page])throw Error('Module view unavailable: '+page);return module.views[page]();}
 function afterRender(page){if(mounted&&mounted!==page){const previous=pages().find(p=>p.id===mounted);features.get(previous?.module)?.leave?.(mounted);}mounted=page;const current=pages().find(p=>p.id===page);features.get(current?.module)?.afterRender?.(page);}
 function verify(){for(const m of manifest.modules.filter(m=>m.enabled!==false)){if(!features.has(m.id))throw Error('Module not initialized: '+m.id);for(const page of m.pages)if(typeof features.get(m.id).views?.[page.id]!=='function')throw Error('Page not registered: '+page.id);}}
 return Object.freeze({configure,register,pages,available:page=>pages().some(p=>p.id===page),render,afterRender,verify,manifest:()=>manifest});
})();
