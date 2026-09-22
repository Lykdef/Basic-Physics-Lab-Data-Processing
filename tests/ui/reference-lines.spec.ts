import {test,expect} from '@playwright/test';
test('直接排除、预览参考线、标准差及保存恢复',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'排除第1行',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('tr.excluded')).toHaveCount(1);
 await page.getByRole('button',{name:'数据预览',exact:true}).click();await page.getByLabel('显示平均值',{exact:true}).check();await page.getByLabel('标准差标线（x̄ ± s）',{exact:true}).check();await expect(page.locator('.reference-marker')).toHaveCount(3);
 await expect(page.getByLabel('相对误差百分比')).toHaveCount(0);await expect(page.locator('.reference-marker')).toContainText(['平均值','x̄ − s','x̄ + s']);
 await page.reload();await page.getByRole('button',{name:'数据预览',exact:true}).click();await expect(page.getByLabel('标准差标线（x̄ ± s）',{exact:true})).toBeChecked();await expect(page.locator('.reference-marker')).toHaveCount(3);
 await page.getByLabel('显示平均值',{exact:true}).uncheck();await expect(page.locator('.reference-marker')).toHaveCount(2);
});
