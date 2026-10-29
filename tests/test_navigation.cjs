const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({document:{addEventListener(){},querySelector(s){return s==='#editor'?{addEventListener(){}}:null}},window:{addEventListener(){}},location:{hash:'#ips'},history:{state:null,pushState(a,b,hash){this.state=a;ctx.location.hash=hash;},replaceState(a){this.state=a;}},URLSearchParams,structuredClone,crypto:{randomUUID:()=> 'test-id'},setTimeout(){},clearTimeout(){},console,localStorage:{getItem:()=>null,setItem(){}}});
for(const file of ['module-registry','app','views','actions','stencils','racks','catalog','accessories','shelf-layout','rack-placement','inventory','planning','workflows','graph-ui','dependency-map','plugins','topology-map','flows','discovery','ipam','connections','navigation'])vm.runInContext(require('./assets.cjs').source(file),ctx);
vm.runInContext(require('./assets.cjs').source('entries'),ctx);
const run=code=>vm.runInContext(code,ctx);

run(`state={devices:[{id:'d',name:'Host',kind:'Server',rack:'r',ip:'192.0.2.1'}],services:[{id:'vm',name:'VM',kind:'Virtual machine',host:'d'}],racks:[{id:'r',name:'Rack',units:42}],networks:[],links:[{id:'l',type:'Requires',source:'vm',target:'d'}],addresses:[]};view='devices';selected='d';deviceFilter={kind:'Server',rack:'r',location:''};query='Host';saveRoute();`);
assert.equal(ctx.location.hash,'#devices?object=d&q=Host&kind=Server&rack=r');
run("selected=null;query='';readRoute()");assert.equal(run('selected'),'d');assert.equal(run('query'),'Host');assert.equal(run('deviceFilter.rack'),'r');
run("view='connections';connectionObjectId='d';connectionFilter='logical';saveRoute()");assert.equal(run('connectionMatches(state.links[0])'),true);
run("connectionObjectId='unrelated'");assert.equal(run('connectionMatches(state.links[0])'),false);
run("view='ips';ipamObjectId='d';ipamTab='addresses';selected=null;query='';saveRoute();readRoute()");assert.equal(run('ipamObjectId'),'d');assert.equal(run('ipamAddressRows(addressInventory()).length'),1);
run("view='map';selected='d';topologyMode='physical';topologyFocusOnly=true;topologyUnconnected=true;topologyQuery='Host';saveRoute();topologyFocusOnly=false;readRoute()");assert.equal(run('topologyFocusOnly'),true);assert.equal(run('topologyQuery'),'Host');
console.log('Navigation checks passed: selected-object deep links, device filters, IP/connection scope and topology state.');

run("view='ips';ipamQuery='192.0';ipamFamily='32';ipStatusFilter='Reserved';saveRoute();ipamQuery='';ipamFamily='all';ipStatusFilter='all';readRoute()");assert.equal(run('ipamQuery'),'192.0');assert.equal(run('ipamFamily'),'32');assert.equal(run('ipStatusFilter'),'Reserved');
