AtlasModules.register('connectors',{views:{marketplace:()=>renderMarketplace()},afterRender:page=>{if(page==='marketplace')loadMarketplace();}});
