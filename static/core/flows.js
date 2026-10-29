// Shared flows: preserve drafts, distinguish import intents and keep large inventories browsable.
const draftEqual=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function mergeInventoryDraft(base,draft,latest){
 const merged=structuredClone(latest);
 const conflict=(label)=>{throw Error(`Another update changed ${label}. Your draft is still open. Copy your changes, then close and reopen this editor to review the latest version.`);};
 for(const key of new Set([...Object.keys(base),...Object.keys(draft)])){
  if(key==='_revision'||draftEqual(base[key],draft[key]))continue;
  const before=base[key],after=draft[key];
  if(Array.isArray(before)&&Array.isArray(after)&&[...before,...after].every(r=>r&&typeof r.id==='string')){
   const old=new Map(before.map(r=>[r.id,r])),desired=new Map(after.map(r=>[r.id,r])),current=new Map((latest[key]||[]).map(r=>[r.id,r]));
   for(const id of new Set([...old.keys(),...desired.keys()])){
    const a=old.get(id),b=desired.get(id),c=current.get(id);if(draftEqual(a,b))continue;
    const label=`${key}: ${a?.name||b?.name||id}`;
    if(!a){if(c&&!draftEqual(b,c))conflict(label);current.set(id,structuredClone(b));continue;}
    if(!b){if(c&&!draftEqual(a,c))conflict(label);current.delete(id);continue;}
    if(!c)conflict(label+' (removed)');const record=structuredClone(c);
    for(const field of new Set([...Object.keys(a),...Object.keys(b)])){
     if(draftEqual(a[field],b[field]))continue;
     if(field==='_overrides'){record[field]=[...new Set([...(c[field]||[]),...(b[field]||[])])];continue;}
     if(!draftEqual(a[field],c[field])&&!draftEqual(b[field],c[field]))conflict(label+' · '+field);
     if(field in b)record[field]=structuredClone(b[field]);else delete record[field];
    }current.set(id,record);
   }merged[key]=[...current.values()];
  }else{if(!draftEqual(before,latest[key])&&!draftEqual(after,latest[key]))conflict(key);if(key in draft)merged[key]=structuredClone(after);else delete merged[key];}
 }return merged;
}
function validateImportIntent(data,intent){
 if(!data||typeof data!=='object'||Array.isArray(data))throw Error('Choose a valid Atlas JSON file.');
 if(intent==='snapshot'){if(!data.connector)throw Error('This is not a connector snapshot. Use Restore backup for inventory backups.');if(data.schemaVersion!==1)throw Error('Connector snapshots must use schemaVersion 1.');for(const k of ['devices','services','networks','links'])if(data[k]!==undefined&&!Array.isArray(data[k]))throw Error('Invalid snapshot collection: '+k);}
 else{if(data.connector)throw Error('This is a connector snapshot. Use Import snapshot to merge it.');for(const k of ['racks','devices','services','networks','addresses','links'])if(!Array.isArray(data[k]))throw Error('Backup is missing an inventory collection: '+k);}
}
function improveEditorDialog(dialog){
 const form=dialog.querySelector('form');let dirty=false,saving=false;dialog.onclose=()=>{if(state._revision!==editorBaseState?._revision)renderView();};
 const changed=()=>{dirty=true;};form.addEventListener('input',changed);form.addEventListener('change',changed);
 const close=e=>{e.preventDefault();if(saving||form.dataset.saving==='true')return;if(!dirty){dialog.close();return;}if(form.querySelector('#discard-confirm'))return;const warning=document.createElement('section');warning.id='discard-confirm';warning.className='draft-confirm';warning.setAttribute('role','alert');warning.innerHTML='<p>Discard the unsaved changes in this dialog?</p><button type="button" class="button" data-keep-draft>Keep editing</button><button type="button" class="button danger" data-discard-draft>Discard changes</button>';form.querySelector('.modal-footer').before(warning);warning.querySelector('[data-keep-draft]').onclick=()=>warning.remove();warning.querySelector('[data-discard-draft]').onclick=()=>dialog.close();warning.querySelector('[data-keep-draft]').focus();};
 dialog.querySelectorAll('.modal-close').forEach(b=>b.onclick=close);dialog.oncancel=close;
 // Native validation must reveal a required field inside a collapsed optional section.
 form.addEventListener('invalid',e=>{let parent=e.target.parentElement;while(parent&&parent!==form){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}},true);
 const submit=form.onsubmit;form.onsubmit=async e=>{if(saving){e.preventDefault();return;}saving=true;const buttons=[...form.querySelectorAll('button[type="submit"],#save-connect')];try{const pending=submit(e);buttons.forEach(b=>b.disabled=true);await pending;}finally{saving=false;buttons.forEach(b=>b.disabled=false);}};
 form.querySelector('input:not([type="hidden"]):not([type="file"]):not([disabled])')?.focus();
}
function objectChoiceLabel(o){return `${o.name} · ${o.kind||'Object'}${o.host?' · '+name(o.host):''}`;}








document.addEventListener('click',e=>{if(e.target.closest('[data-unassigned-devices]')){navigate('devices');deviceCategory='devices';deviceFilter={kind:'',rack:'unassigned',location:''};renderView();}const jump=e.target.closest('[data-rack-jump]');if(jump){const viewport=$('.rack-viewport');if(!viewport)return;if(jump.dataset.rackJump==='top')viewport.scrollTop=0;else if(jump.dataset.rackJump==='bottom')viewport.scrollTop=viewport.scrollHeight;else viewport.querySelector('.rack-device')?.scrollIntoView({block:'center',behavior:'smooth'});}});

function confirmRecordDeletion(remove){const form=$('#edit-form');if(form.querySelector('#delete-confirm'))return;const warning=document.createElement('section');warning.id='delete-confirm';warning.className='draft-confirm';warning.setAttribute('role','alert');warning.innerHTML='<p>Delete this record? Connections may be removed and hosted records detached. Export a backup to recover it later.</p><button type="button" class="button" data-action="export">Download backup</button><button type="button" class="button" data-keep-record>Keep record</button><button type="button" class="button danger" data-confirm-delete>Delete record</button>';form.querySelector('.modal-footer').before(warning);warning.querySelector('[data-keep-record]').onclick=()=>warning.remove();warning.querySelector('[data-confirm-delete]').onclick=async()=>{const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);form.dataset.saving='true';try{await remove();$('#editor').close();}catch(error){$('#form-error').textContent=error.message;$('#form-error').scrollIntoView({block:'nearest'});}finally{delete form.dataset.saving;buttons.forEach(b=>b.disabled=false);}};warning.querySelector('[data-keep-record]').focus();}


