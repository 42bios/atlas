const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let resolve,calls=0,appended='';const gate=new Promise(r=>{resolve=r}),catalog={innerHTML:'initial',querySelector:()=>null,insertAdjacentHTML:(where,html)=>{appended+=html}};
const context=vm.createContext({AbortController,document:{addEventListener(){},querySelectorAll:()=>[]},$:()=>catalog,esc:v=>String(v??''),pill:v=>v,repositoryPackageDetails:()=>'',clearTimeout,setTimeout,state:{devices:[],services:[]},view:'integrations',fetch:async url=>{calls++;await gate;return {ok:true,json:async()=>url==='/api/v1/addins'?{packages:[],instances:[]}:[]}}});
vm.runInContext(fs.readFileSync('static/modules/connectors/addins.js','utf8'),context);
(async()=>{
 const first=vm.runInContext('loadAtlasAddins()',context),second=vm.runInContext('loadAtlasAddins()',context);
 assert.equal(calls,2,'one shared status request, two endpoint fetches');resolve();await Promise.all([first,second]);assert.match(catalog.innerHTML,/No systems connected yet/);
 catalog.querySelector=()=>({});catalog.innerHTML='previous successful cards';context.fetch=async()=>{throw Error('Temporary network error')};
 await vm.runInContext('loadAtlasAddins()',context);assert.equal(catalog.innerHTML,'previous successful cards');assert.match(appended,/Retry/);
 context.setTimeout=fn=>setTimeout(fn,5);context.fetch=async(path,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Object.assign(Error('aborted'),{name:'AbortError'}))));
 await assert.rejects(vm.runInContext("connectorFetch('/test')",context),/Refresh status.*before retrying/);
 console.log('Status fetches deduplicate, failed refresh preserves loaded cards, and bounded waits explain recovery.');
})().catch(e=>{console.error(e);process.exitCode=1});
