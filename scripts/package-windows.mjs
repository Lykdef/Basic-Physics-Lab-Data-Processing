import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
process.chdir(root);
if(process.platform!=='win32' || process.arch!=='x64')throw new Error('Build on Windows x64.');
const metadata=JSON.parse(await fs.readFile('package.json','utf8'));
const name=`PhysicalLab-${metadata.version}-win-x64`;
const output=path.join(root,'release',name),app=path.join(output,'resources/app');
// Refuse to overwrite an existing package; the output is a reviewable artifact.
try{await fs.access(output);throw new Error(`Output already exists: ${output}`);}catch(e){if(e.code!=='ENOENT')throw e;}
await fs.access('dist/index.html');await fs.access('.python-deps/scipy/__init__.py');
const cache=path.join(root,'.pack-cache');await fs.mkdir(cache,{recursive:true});
const archive=path.join(cache,'python-3.14.7-embed-amd64.zip');
const expected='d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15';
try{await fs.access(archive);}catch{
 const download=spawnSync('curl.exe',['-L','--fail','--retry','2','--connect-timeout','15','--max-time','900','--output',archive,'https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip'],{stdio:'inherit',windowsHide:true});
 if(download.status!==0)throw new Error('Python download failed; remove the incomplete cache archive before retrying.');
}
if(createHash('sha256').update(await fs.readFile(archive)).digest('hex')!==expected)throw new Error('Python archive checksum mismatch');
await fs.cp('node_modules/electron/dist',output,{recursive:true});
await fs.rename(path.join(output,'electron.exe'),path.join(output,'PhysicalLab.exe'));
await fs.mkdir(app,{recursive:true});
await fs.copyFile('LICENSE',path.join(output,'LICENSE-PhysicalLab.txt'));
for(const dir of ['dist','electron','compute'])await fs.cp(dir,path.join(app,dir),{recursive:true,filter:src=>!src.split(path.sep).includes('__pycache__')});
await fs.cp('.python-deps',path.join(app,'.python-deps'),{recursive:true,filter:src=>!src.split(path.sep).some(part=>['__pycache__','tests','benchmarks'].includes(part))});
await fs.writeFile(path.join(app,'package.json'),JSON.stringify({name:metadata.name,version:metadata.version,main:'electron/main.cjs',description:'物理实验室'},null,2));
const python=path.join(app,'runtime/python');await fs.mkdir(python,{recursive:true});
const quote=s=>"'"+s.replaceAll("'","''")+"'";
const extracted=spawnSync('powershell.exe',['-NoProfile','-Command',`Expand-Archive -LiteralPath ${quote(archive)} -DestinationPath ${quote(python)}`],{stdio:'inherit',windowsHide:true});
if(extracted.status!==0)throw new Error('Python extraction failed');
await fs.writeFile(path.join(output,'使用说明.txt'),'物理实验室 Windows x64 便携版\r\n\r\n完整解压此文件夹，双击 PhysicalLab.exe 启动。\r\n无需安装 Node.js 或 Python；全部计算可离线使用。\r\n请保持 resources 等文件与程序位于同一文件夹。\r\n项目自动保存在当前 Windows 用户的应用数据目录，可用“保存项目”导出 JSON 备份。\r\n');
await fs.writeFile(path.join(output,'THIRD-PARTY-NOTICES.txt'),'Electron: LICENSE and LICENSES.chromium.html in this folder.\r\nPython: resources/app/runtime/python/LICENSE.txt.\r\nNumPy, SciPy, SymPy, mpmath: license files in resources/app/.python-deps/*dist-info.\r\nVue, Lucide, Zod: see THIRD-PARTY-LICENSES in this folder.\r\n');
for(const dependency of ['vue','@vue/shared','@vue/reactivity','@vue/runtime-core','@vue/runtime-dom','lucide-vue-next','zod']){
 const dir=path.join(root,'node_modules',dependency);const names=await fs.readdir(dir);
 for(const file of names.filter(n=>/^licen[sc]e/i.test(n))){const dest=path.join(output,'THIRD-PARTY-LICENSES',dependency.replaceAll('/','-'));await fs.mkdir(dest,{recursive:true});await fs.cp(path.join(dir,file),path.join(dest,file));}
}
const zipped=spawnSync(path.join(python,'python.exe'),['-c',`import pathlib,zipfile; root=pathlib.Path(${JSON.stringify(output)}); z=zipfile.ZipFile(str(root)+'.zip','w',zipfile.ZIP_DEFLATED,6); [z.write(p,p.relative_to(root.parent)) for p in root.rglob('*') if p.is_file()]; z.close()`],{stdio:'inherit',windowsHide:true});
if(zipped.status!==0)throw new Error('ZIP creation failed');
const zip=output+'.zip';const hash=createHash('sha256').update(await fs.readFile(zip)).digest('hex');await fs.writeFile(zip+'.sha256',`${hash}  ${path.basename(zip)}\n`);
console.log(`Packaged: ${zip}`);
