import {test,expect} from '@playwright/test';
test('按数据类型显示页面，切组回到可用页面',async({page})=>{
 await page.goto('/');await expect(page.getByRole('button',{name:'统计评定',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'数据预览',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'不确定度传播',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'数据预览',exact:true}).click();await expect(page.getByLabel('自变量 · 横轴')).toBeDisabled();await expect(page.getByLabel('自变量 · 横轴')).toHaveValue('sequence');await expect(page.getByRole('checkbox',{name:'曲线拟合',exact:true})).toHaveCount(0);await expect(page.getByRole('checkbox',{name:'连接数据点',exact:true})).toHaveCount(0);await expect(page.locator('.large-plot svg polyline')).toHaveCount(0);await expect(page.locator('.large-plot svg circle')).toHaveCount(10);
 await page.getByRole('button',{name:'统计评定',exact:true}).click();await page.locator('.dataset-tabs').getByRole('button',{name:'伏安法测电阻'}).click();
 await expect(page.getByRole('button',{name:'统计评定',exact:true})).toHaveCount(0);await expect(page.locator('.inspector')).toBeVisible();
 await page.getByRole('button',{name:'不确定度传播',exact:true}).click();await page.locator('.dataset-tabs').getByRole('button',{name:'长度的重复测量'}).click();await expect(page.locator('.propagation-panel')).toHaveCount(0);await expect(page.locator('.inspector')).toBeVisible();
 await page.locator('.inspector select').first().selectOption('paired');await expect(page.getByRole('button',{name:'数据预览',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'统计评定',exact:true})).toHaveCount(0);
});
test('逐字符录入 0.006、小数及科学计数法不被数值回填截断',async({page})=>{
 await page.goto('/');await page.locator('.dataset-tabs').getByRole('button',{name:'伏安法测电阻'}).click();await page.getByRole('button',{name:'不确定度传播',exact:true}).click();
 const u=page.getByLabel('变量 1 标准不确定度');await u.fill('');await u.pressSequentially('0.006',{delay:120});await expect(u).toHaveValue('0.006');await expect(page.getByLabel('传播最佳估计值')).toHaveText('(1.000 ± 0.006)');
 await u.fill('');await u.pressSequentially('6e-3',{delay:120});await expect(u).toHaveValue('6e-3');await u.press('Tab');await expect(page.getByLabel('传播最佳估计值')).toHaveText('(1.000 ± 0.006)');
 await u.fill('-0.1');await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByLabel('传播最佳估计值')).toHaveCount(0);
 await u.fill('0.006');await page.reload();await page.getByRole('button',{name:'不确定度传播',exact:true}).click();await expect(u).toHaveValue('0.006');
});
