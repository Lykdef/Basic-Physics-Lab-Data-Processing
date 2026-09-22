import { _electron as electron } from '@playwright/test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs/promises';
const root=path.resolve('.electron-test'); await fs.mkdir(root,{recursive:true});
const dir=await fs.mkdtemp(path.join(root,'run-'));
const app=await electron.launch({args:['.'],env:{...process.env,PHYSICAL_LAB_TEST_DIR:dir}});
try {
  const page=await app.firstWindow();
  await page.getByRole('heading',{name:'基础物理实验',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>typeof window.labDesktop?.saveProject),'function');
  assert.equal(await page.evaluate(()=>typeof window.require),'undefined');
  await app.evaluate(({dialog}, dir)=>{
    dialog.showSaveDialog=async()=>({canceled:false,filePath:dir+'/saved-project.json'});
    dialog.showOpenDialog=async()=>({canceled:false,filePaths:[dir+'/saved-project.json']});
  },dir);
  await page.getByRole('textbox',{name:'第1行 直径'}).fill('12.98765');
  await page.getByRole('textbox',{name:'第1行 直径'}).press('Tab');
  await page.getByRole('button',{name:'保存项目',exact:true}).click();
  await page.getByRole('status').filter({hasText:'项目已导出'}).waitFor();
  const saved=JSON.parse(await fs.readFile(path.join(dir,'saved-project.json'),'utf8'));
  assert.equal(saved.datasets[0].rows[0].values[0],12.98765);
  await page.getByRole('button',{name:'保存项目',exact:true}).click();
  await page.getByRole('button',{name:'导入项目',exact:true}).click();
  await page.getByRole('heading',{name:'基础物理实验（导入副本）',exact:true}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'第1行 直径'}).inputValue(),'12.99');
  await page.getByRole('button',{name:'统计评定',exact:true}).click();
  assert.notEqual(await page.getByTestId('stat-ua').textContent(),'—');
  const propagated=await page.evaluate(()=>window.labDesktop.calculate({operation:'propagate',expression:'x^2',variables:[{symbol:'x',value:3,uncertainty:.1}],k:2}));
  assert.equal(propagated.value,9);assert.ok(Math.abs(propagated.uncertainty-.6)<1e-12);
  await page.locator('.dataset-tabs').getByRole('button',{name:'伏安法测电阻'}).click();
  await page.getByRole('button',{name:'不确定度传播',exact:true}).click();
  await page.getByLabel('传播最佳估计值').waitFor();
  console.log('PASS: Electron 离线加载、隔离桥接、原生文件保存/覆盖/重新打开，原始精度完整保留。');
} finally { await app.close(); }
