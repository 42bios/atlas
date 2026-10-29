// Build private binding contracts from each installed feature package.
// Node's bundled parser is used only during development; deployment uses Python.
const fs=require('fs'),vm=require('vm'),path=require('path');const parser={exports:{}};vm.runInNewContext(process.binding('natives')['internal/deps/acorn/acorn/dist/acorn'],{exports:parser.exports,module:parser});
const manifests=[],allAssets=[],allBindings={};
for(const id of fs.readdirSync('atlas_modules').sort()){
 const file=path.join('atlas_modules',id,'plugin.json');if(!fs.existsSync(file))continue;
 const manifest=JSON.parse(fs.readFileSync(file));manifest.bindings={};
 for(const asset of manifest.assets){const source=fs.readFileSync('static'+asset.path,'utf8'),ast=parser.exports.parse(source,{ecmaVersion:'latest'}),bindings=[];for(const node of ast.body){if(node.type==='FunctionDeclaration')bindings.push({name:node.id.name,writable:true});if(node.type==='VariableDeclaration')for(const d of node.declarations){if(d.id.type!=='Identifier')throw Error('Use named plugin bindings: '+asset.path);bindings.push({name:d.id.name,writable:node.kind!=='const'});}}manifest.bindings[asset.path]=bindings;allBindings[asset.path]=bindings;allAssets.push(asset);}
 fs.writeFileSync(file,JSON.stringify(manifest,null,2)+'\n');const {assets,bindings,backendRoutes,...metadata}=manifest;manifests.push(metadata);
}
fs.writeFileSync('atlas_modules/bindings.json',JSON.stringify(allBindings,null,2)+'\n');
fs.writeFileSync('atlas_modules/manifest.json',JSON.stringify(manifests,null,2)+'\n');
fs.writeFileSync('atlas_modules/assets.json',JSON.stringify(allAssets,null,2)+'\n');
