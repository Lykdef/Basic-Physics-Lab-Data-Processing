import { _electron as electron } from '@playwright/test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs/promises';
const metadata=JSON.parse(await fs.readFile('package.json','utf8'));
const executable=path.resolve(`release/PhysicalLab-${metadata.version}-win-x64/PhysicalLab.exe`);
const root=path.resolve('.electron-test');await fs.mkdir(root,{recursive:true});const dir=await fs.mkdtemp(path.join(root,'packaged-'));
const app=await electron.launch({executablePath:executable,args:[],env:{...process.env,PHYSICAL_LAB_TEST_DIR:dir,PHYSICAL_LAB_PYTHON:'Z:\\not-installed\\python.exe',PATH:process.env.SystemRoot+'\\System32'}});
try{
 const page=await app.firstWindow();await page.getByRole('heading',{name:'基础物理实验',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>typeof window.require),'undefined');
 const result=await page.evaluate(()=>window.labDesktop.calculate({operation:'propagate',expression:'x^2',variables:[{symbol:'x',value:3,uncertainty:.1}],k:2}));
 assert.equal(result.value,9);assert.ok(Math.abs(result.uncertainty-.6)<1e-12);
 await page.locator('.dataset-tabs').getByRole('button',{name:'伏安法测电阻'}).click();await page.getByRole('button',{name:'数据预览',exact:true}).click();await page.getByRole('checkbox',{name:'曲线拟合',exact:true}).check();
 await page.locator('.fit-metrics').waitFor();assert.ok((await page.locator('.fit-metrics').textContent()).includes('拟合结果'));
 await app.evaluate(({dialog},dir)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:dir+'/saved.json'});dialog.showOpenDialog=async()=>({canceled:false,filePaths:[dir+'/saved.json']});},dir);
 await page.getByRole('button',{name:'保存项目',exact:true}).click();await page.getByRole('status').filter({hasText:'项目已导出'}).waitFor();await fs.access(path.join(dir,'saved.json'));
 await page.getByRole('button',{name:'导入项目',exact:true}).click();await page.getByRole('heading',{name:'基础物理实验（导入副本）',exact:true}).waitFor();
 await page.screenshot({path:'artifacts/packaged-app.png',fullPage:true});console.log('PASS: standalone package loads, fits, propagates and saves/opens files without system Python or Node on PATH.');
}finally{await app.close();}
