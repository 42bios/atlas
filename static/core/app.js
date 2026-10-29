const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
  unlock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0M12 14v3"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  rack:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M5 8h14M5 15h14M8 5h1m-1 6h1m-1 7h1"/>',
  server:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5M12 17.5h5"/>',
  network:'<rect x="8" y="2" width="8" height="6" rx="1"/><rect x="2" y="16" width="7" height="6" rx="1"/><rect x="15" y="16" width="7" height="6" rx="1"/><path d="M12 8v4M5 16v-4h14v4"/>',
  box:'<path d="m12 2 10 5-10 5L2 7l10-5ZM2 7v10l10 5 10-5V7M12 12v10M7 4.5l10 5"/>',
  plug:'<path d="M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0V7Zm6 10v5"/>',
  globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  arrow:'<path d="M7 17 17 7M7 7h10v10"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  link:'<path d="m10 13 4-4m-6 6-2 2a4 4 0 0 1-5-5l5-5a4 4 0 0 1 6 0m0 2 2-2a4 4 0 0 1 5 5l-5 5a4 4 0 0 1-6 0"/>',
  edit:'<path d="m15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14v6Z"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
};
const icon = (name, size=20) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.server}</svg>`;
let state, view='overview', rackId='rack-1', side='front', selected=null, query='', networkId='', serviceGroup='All applications', serviceHostId='';
const nav = AtlasModules.pages().map(p=>[p.id,p.icon,p.label]);
const navGroups = [...new Set(AtlasModules.pages().map(p=>p.group))].map(group=>[group,AtlasModules.pages().filter(p=>p.group===group).map(p=>[p.id,p.icon,p.label])]);
function routeHash(){return '#'+view+(view==='services'&&serviceHostId?'?host='+encodeURIComponent(serviceHostId):view==='racks'&&rackId?'?rack='+encodeURIComponent(rackId):'');}
function saveRoute(){if(location.hash!==routeHash())history.pushState(null,'',routeHash());}
function navigate(next){if(!AtlasModules.available(next))next='integrations';graphExpanded=false;view=next;query='';selected=null;serviceHostId='';serviceGroup='All applications';saveRoute();shell();window.scrollTo(0,0);}
function readRoute(){const [page,params]=location.hash.slice(1).split('?');view=nav.some(n=>n[0]===page)?page:'overview';query='';selected=null;if(view==='racks'){const id=new URLSearchParams(params||'').get('rack');if(state.racks.some(r=>r.id===id))rackId=id;}serviceGroup='All applications';serviceHostId=view==='services'?new URLSearchParams(params||'').get('host')||'':'';if(serviceHostId&&!find(serviceHostId))serviceHostId='';selected=serviceHostId||null;}
window.addEventListener('hashchange',()=>{if(state){readRoute();shell();}});
const objects = () => [...state.devices, ...state.services];
const find = id => objects().find(x => x.id === id);
const name = id => find(id)?.name || 'Unassigned';
const kindIcon = x => x.kind === 'PDU' || x.kind === 'UPS' ? 'plug' : ['Container','Service','Virtual machine','LXC'].includes(x.kind) ? 'box' : x.kind === 'Router' || x.kind === 'Switch' ? 'network' : 'server';
const pill = (text, cls='') => `<span class="pill ${cls}">${esc(text)}</span>`;
function shell(){
  $('#app').innerHTML = `<aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark">A</span>atlas<span class="brand-period">.</span></a><nav aria-label="Main navigation">${navGroups.map(([group,items])=>`<div class="nav-group"><div class="nav-label">${group}</div>${items.map(([id,i,label])=>`<button class="nav-item ${view===id?'active':''}" data-nav="${id}" aria-label="${label}" title="${label}" ${view===id?'aria-current="page"':''}>${icon(i)}<span>${label}</span>${id==='devices'?`<em>${state.devices.filter(d=>!d.missing&&!isRackAccessory(d)).length}</em>`:''}</button>`).join('')}</div>`).join('')}</nav></aside><div class="workspace-main"><header class="topbar"><div class="breadcrumb">Workspace ${icon('chevron',14)} <strong>${nav.find(x=>x[0]===view)?.[2]}</strong></div></header><main id="main"></main><footer>ATLAS <span>Your homelab, documented.</span><span class="footer-right">Inventory & documentation · No monitoring</span></footer></div>`;
  renderView();
}
function header(eyebrow,title,description,actions=''){return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="heading-actions">${actions}</div></div>`;}
const button = (label, action, cls='', i='plus')=>`<button class="button ${cls}" data-action="${action}">${icon(i,17)}${label}</button>`;
function renderView(){
  if(!AtlasModules.available(view))view='integrations';
  $('#main').innerHTML = AtlasModules.render(view);
  AtlasModules.afterRender(view);
  if(selected&&!['services','map'].includes(view)&&window.innerWidth<=850){const panel=$('.inspector');if(panel){panel.classList.add('mobile-open');panel.scrollIntoView({block:'start'});}}
}


function empty(title,desc){return `<div class="empty">${icon('box',32)}<h3>${title}</h3><p>${desc}</p></div>`;}
document.addEventListener('click',e=>{
  const n=e.target.closest('[data-nav]');if(n){navigate(n.dataset.nav);return;}
  const s=e.target.closest('[data-side]');if(s){side=s.dataset.side;const rv=rackViews.get(rackId);if(rv)rv.dual=false;saveRackPreferences();renderView();return;}
  const d=e.target.closest('[data-select]');if(d){selected=d.dataset.select;if(AtlasModules.available('services')&&(state.services.some(s=>s.id===selected)||state.services.some(s=>s.host===selected))&&(view==='services'||d.classList.contains('connection-row'))){applicationPresentation='map';openHostApplications(selected);return;}saveRoute();renderView();if(view==='map')[...document.querySelectorAll('[data-graph-node]')].find(n=>n.dataset.graphNode===selected)?.focus();return;}
  const a=e.target.closest('[data-action]');if(a && typeof action==='function')action(a.dataset.action,a);
});
document.addEventListener('change',e=>{if(e.target.id==='rack-select'){rackId=e.target.value;selected=null;saveRoute();renderView();}});
async function boot(){try{AtlasModules.verify();const response=await fetch('/api/state');if(!response.ok)throw Error('Could not load inventory');state=await response.json();readRoute();shell();}catch(error){$('#app').innerHTML=`<div class="empty"><h1>Unable to open Atlas</h1><p>${esc(error.message)}</p><button onclick="location.reload()">Try again</button></div>`;}}
window.addEventListener('DOMContentLoaded',boot);

let connectionObjectId='',ipamObjectId='';

let inventoryIncludeMissing=false;
function inventoryVisible(object){return !!object&&(inventoryIncludeMissing||!object.missing);}
function inventoryLinkVisible(link){return inventoryVisible(find(link.source))&&inventoryVisible(find(link.target));}
function inventoryHistoryLabel(object){return object?.missing?`<small class="history-label">Missing import · ${esc(object.origin||'Unknown source')}${object.lastSeen?' · Last seen '+esc(new Date(object.lastSeen).toLocaleDateString('en-GB')):''}</small>`:'';}
function inventoryHistoryControl(items=objects()) {const count=items.filter(o=>o.missing).length;return `<label class="history-control"><input type="checkbox" data-inventory-history ${inventoryIncludeMissing?'checked':''}> Include missing imports${count?` <span>(${count} historical objects)</span>`:''}</label>`;}
document.addEventListener('change',e=>{if(!e.target.matches('[data-inventory-history]'))return;inventoryIncludeMissing=e.target.checked;saveRoute();renderView();document.querySelector('[data-inventory-history]')?.focus();});
