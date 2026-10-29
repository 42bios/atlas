const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const assets=JSON.parse(fs.readFileSync('atlas_modules/assets.json')).sort((a,b)=>a.order-b.order),manifests=JSON.parse(fs.readFileSync('atlas_modules/manifest.json'));
const inventory={racks:[{id:'r',name:'Rack',units:18}],devices:[{id:'host',name:'Host',kind:'Server',rack:'r',height:1,unit:1,ports:2,interfaces:[{name:'eth0',type:'Ethernet',ips:['192.0.2.2']}]}],services:[{id:'app',name:'App',kind:'Container',host:'host'}],networks:[{id:'net',name:'Net',cidr:'192.0.2.0/24'}],addresses:[],links:[{id:'link',source:'host',target:'host',type:'Network',sourcePort:'eth0',targetPort:'2',cableMedium:'dac'}],stencils:[]};
const bindings=JSON.parse(fs.readFileSync('atlas_modules/bindings.json'));
function wrap(a){const descriptors=bindings[a.path].map(b=>`${JSON.stringify(b.name)}:{get:()=>${b.name}${b.writable?`,set:value=>{${b.name}=value;}`:''}}`).join(',');return `AtlasPluginHost.load(${JSON.stringify(a.owner)},function(pluginContext,publish){with(pluginContext){${fs.readFileSync('static'+a.path,'utf8')}\npublish({${descriptors}});}})`;}

let count=0;
for(let mask=0;mask<64;mask++){
 const optional=['hardware','applications','ipam','connections','topology','catalogs'], enabled=new Set(manifests.filter(m=>['core','overview','settings','connectors'].includes(m.id)).map(m=>m.id));optional.forEach((id,i)=>{if(mask&(1<<i))enabled.add(id);});
 if(manifests.some(m=>enabled.has(m.id)&&m.requires.some(id=>!enabled.has(id))))continue;
 const listeners={};const modules=manifests.map(m=>({...m,enabled:enabled.has(m.id)})),elements=new Map(),document={addEventListener(type,fn){(listeners[type]??=[]).push(fn);},querySelector(sel){if(!elements.has(sel))elements.set(sel,{addEventListener(){},innerHTML:'',textContent:'',classList:{add(){},remove(){}},querySelectorAll:()=>[],querySelector:()=>null});return elements.get(sel);},querySelectorAll:()=>[]};
 const ctx=vm.createContext({document,window:{addEventListener(){},innerWidth:1600,scrollTo(){}},location:{hash:'#overview'},history:{state:{},replaceState(){},pushState(){}},URLSearchParams,structuredClone,crypto:{randomUUID:()=> 'id'},setTimeout:()=>0,clearTimeout(){},console,localStorage:{getItem:()=>null,setItem(){}},fetch:async()=>({ok:true,json:async()=>({})})});
 try{
 vm.runInContext(fs.readFileSync('static/core/module-registry.js','utf8'),ctx);ctx.config={schemaVersion:1,modules,assets};vm.runInContext('AtlasModules.configure(config)',ctx);
 vm.runInContext(fs.readFileSync('static/core/plugin-host.js','utf8'),ctx);vm.runInContext('AtlasPluginHost.configure(config.modules)',ctx);
 for(const a of assets.filter(a=>enabled.has(a.owner)))vm.runInContext(wrap(a),ctx,{filename:a.path});
 ctx.inventory=structuredClone(inventory);vm.runInContext('with(AtlasPluginHost.context("core")){state=inventory;AtlasModules.verify();readRoute();}',ctx);
 for(const page of modules.filter(m=>m.enabled).flatMap(m=>m.pages)){
  vm.runInContext(`with(AtlasPluginHost.context('core')){view=${JSON.stringify(page.id)};AtlasModules.render(view);}`,ctx);
 }
 if(enabled.has('hardware')){
  vm.runInContext("with(AtlasPluginHost.context('hardware')){state.devices.push({id:'unassigned-switch',name:'Switch',kind:'Switch',ports:4});selected='unassigned-switch';}",ctx);
  const unassigned=vm.runInContext("with(AtlasPluginHost.context('hardware')){inspector();}",ctx);
  assert.match(unassigned,/<dt>Placement<\/dt>/);assert.doesNotMatch(unassigned,/<dt>Host<\/dt>|<dt>Port<\/dt>/);
  vm.runInContext("with(AtlasPluginHost.context('hardware')){state.devices=state.devices.filter(d=>d.id!=='unassigned-switch');selected='host';}",ctx);
 }
 vm.runInContext("with(AtlasPluginHost.context('core')){renderView=()=>{};shell=()=>{};}",ctx);
 for(const [owner,selector,dataset]of [['connectors','[data-market-systems]',{}],...(enabled.has('applications')?[['connectors','[data-market-inventory]',{marketInventory:'test-source',marketInventoryPage:'services'}]]:[]),['topology','[data-topology-mode]',{topologyMode:'power'}],['connections','[data-connection-filter]',{connectionFilter:'power'}],['hardware','[data-device-category]',{deviceCategory:'accessories'}],['ipam','[data-ip-status]',{ipStatus:'Reserved'}]]){
  if(!enabled.has(owner))continue;const target={dataset,closest:sel=>sel.split(',').includes(selector)?target:null,matches:()=>false};for(const listener of listeners.click||[])listener({target,preventDefault(){}});
 }
 assert.equal(vm.runInContext('typeof state',ctx),'undefined');assert.equal(vm.runInContext('typeof renderIPs',ctx),'undefined');assert.equal(vm.runInContext('typeof editDevice',ctx),'undefined');
 count++;
 }catch(e){console.error('Activation failed:',[...enabled].join(', '));throw e;}
}
console.log('Independent plugin combinations passed:',count);
// Unrelated plugins cannot accidentally read another plugin's exported bindings.
const isolated=vm.createContext({});vm.runInContext(fs.readFileSync('static/core/plugin-host.js','utf8'),isolated);
vm.runInContext("AtlasPluginHost.configure([{id:'a',requires:[]},{id:'b',requires:[]}]);AtlasPluginHost.load('a',(_,publish)=>publish({privateValue:{get:()=>42}}));",isolated);
assert.throws(()=>vm.runInContext("AtlasPluginHost.context('b').privateValue",isolated),/declared dependency/);
