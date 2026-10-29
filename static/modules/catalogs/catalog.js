

function catalogIntegration(){return catalogSourceManager();}



document.addEventListener('click',async e=>{const button=e.target.closest('[data-catalog-import]');if(!button)return;button.disabled=true;$('#catalog-error').textContent='';try{const response=await fetch('/api/catalog/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:button.dataset.catalogImport||$('#catalog-url').value})});const result=await response.json();if(!response.ok)throw Error(result.error||'Unable to import catalog');state=await(await fetch('/api/state')).json();shell();toast(`${result.imported} device models imported`);}catch(error){if($('#catalog-error'))$('#catalog-error').textContent=error.message;}finally{button.disabled=false;}});
