// Runs before styles to avoid a light flash when a saved/system dark theme applies.
(()=>{
 const key='atlas.appearance',choices=['light','dark','auto'];
 let preference='auto';try{const saved=localStorage.getItem(key);if(choices.includes(saved))preference=saved;}catch(_){}
 const system=window.matchMedia?window.matchMedia('(prefers-color-scheme: dark)'):null;
 function apply(){const resolved=preference==='auto'?(system?.matches?'dark':'light'):preference;document.documentElement.dataset.theme=resolved;document.documentElement.dataset.appearance=preference;document.documentElement.style.colorScheme=resolved;window.dispatchEvent(new CustomEvent('atlas:appearance-change',{detail:{preference,resolved}}));}
 function setPreference(value){if(!choices.includes(value))throw Error('Choose light, dark or auto.');preference=value;try{localStorage.setItem(key,value);}catch(_){}apply();}
 system?.addEventListener?.('change',()=>{if(preference==='auto')apply();});
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null){preference=choices.includes(event.newValue)?event.newValue:'auto';apply();}});
 window.AtlasAppearance=Object.freeze({getPreference:()=>preference,getResolved:()=>document.documentElement.dataset.theme,setPreference});apply();
})();
