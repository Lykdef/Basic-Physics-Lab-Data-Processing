import {test,expect} from '@playwright/test';
test('Grubbs 仅两个选项，查表结果与一键剔除',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'统计评定',exact:true}).click();
 const select=page.getByLabel('显著性水平',{exact:true});await expect(select.locator('option')).toHaveText(['0.01','0.05']);
 await expect(page.getByTestId('grubbs-critical')).toHaveText('2.289954');await select.selectOption('0.01');await expect(page.getByTestId('grubbs-critical')).toHaveText('2.482083');
});
test('合成数据组仅不确定度页面，各组独立保存并可重新导入',async({page})=>{
 await page.goto('/');
 const add=async(name:string)=>{await page.locator('.dataset-tree').getByRole('button',{name:'添加数据组',exact:true}).click();await page.getByLabel('名称',{exact:true}).fill(name);await page.getByLabel('数据类型',{exact:true}).selectOption('combined');await page.getByRole('button',{name:'确认',exact:true}).click();};
 await add('合成一');await expect(page.locator('.view-tabs button')).toHaveText(['科学计算']);await expect(page.locator('.measurement-grid')).toHaveCount(0);await expect(page.locator('.inspector')).toHaveCount(0);
 await page.getByLabel('变量 1 标准不确定度').fill('0.03');await page.getByRole('button',{name:'添加输入变量',exact:false}).click();await page.getByLabel('变量 2 标准不确定度').fill('0.04');await page.getByLabel('传播公式').fill('x+x2');await expect(page.getByLabel('传播最佳估计值')).toHaveText('(2.00 ± 0.05)');
 await add('合成二');await expect(page.getByLabel('传播公式')).toHaveValue('x');await page.locator('.dataset-tabs').getByRole('button',{name:'合成一',exact:true}).click();await expect(page.getByLabel('传播公式')).toHaveValue('x+x2');
 await page.reload();await expect(page.locator('.view-tabs button')).toHaveText(['科学计算']);await expect(page.getByLabel('传播最佳估计值')).toHaveText('(2.00 ± 0.05)');
 const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'保存项目',exact:true}).click();const download=await downloadPromise;await page.locator('input[type=file]').setInputFiles((await download.path())!);await page.locator('.dataset-tabs').getByRole('button',{name:'合成一',exact:true}).click();await expect(page.getByLabel('传播公式')).toHaveValue('x+x2');
});
