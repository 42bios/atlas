AtlasModules.register('hardware',{views:{racks:()=>renderRacks(),devices:()=>renderDevices()},afterRender:page=>{if(page==='racks')restoreRackScroll();}});
