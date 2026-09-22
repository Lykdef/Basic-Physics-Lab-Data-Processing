import {test,expect} from '@playwright/test';
test('方向键按可见表格方向移动并提交输入，横向操作悬停出现',async({page})=>{
 await page.goto('/');await page.locator('.dataset-tabs').getByRole('button',{name:'伏安法测电阻'}).click();
 const first=page.getByRole('textbox',{name:'第1行 电压',exact:true});await first.fill('1.23');await first.press('ArrowRight');
 await expect(page.getByRole('textbox',{name:'第1行 电流',exact:true})).toBeFocused();await expect(first).toHaveValue('1.23');
 await page.keyboard.press('ArrowDown');await expect(page.getByRole('textbox',{name:'第2行 电流',exact:true})).toBeFocused();
 await page.keyboard.press('ArrowLeft');await expect(page.getByRole('textbox',{name:'第2行 电压',exact:true})).toBeFocused();
 await page.keyboard.press('ArrowUp');await expect(first).toBeFocused();
 await page.getByRole('button',{name:'横向表格',exact:true}).click();await first.focus();await first.press('ArrowRight');await expect(page.getByRole('textbox',{name:'第2行 电压',exact:true})).toBeFocused();
 await page.keyboard.press('ArrowDown');await expect(page.getByRole('textbox',{name:'第2行 电流',exact:true})).toBeFocused();
 await page.getByRole('heading',{name:'基础物理实验',exact:true}).hover();
 const actions=page.locator('.horizontal-actions').nth(1);await expect(actions).toHaveCSS('opacity','0');
 await page.getByRole('textbox',{name:'第2行 电压',exact:true}).hover();await expect(actions).toHaveCSS('opacity','1');
 await page.getByRole('heading',{name:'基础物理实验',exact:true}).hover();await expect(actions).toHaveCSS('opacity','0');
});
test('侧栏删除指定数据组且可撤销，新组仅两行',async({page})=>{
 await page.goto('/');const entry=page.locator('.dataset-entry').filter({hasText:'伏安法测电阻'});await entry.hover();await entry.getByRole('button',{name:'删除数据组 伏安法测电阻',exact:true}).click();
 await expect(page.locator('.modal-intro')).toContainText('伏安法测电阻');await page.getByRole('button',{name:'确认删除',exact:true}).click();
 await expect(page.locator('.dataset-tabs button.selected')).toHaveText('长度的重复测量');await expect(entry).toHaveCount(0);await page.getByTitle('撤销',{exact:true}).click();await expect(entry).toHaveCount(1);
 await page.locator('.dataset-tree').getByRole('button',{name:'添加数据组',exact:true}).click();await page.getByLabel('名称',{exact:true}).fill('两行数据');await page.getByRole('button',{name:'确认',exact:true}).click();
 await expect(page.locator('.measure-table tbody tr')).toHaveCount(2);await page.reload();await expect(page.locator('.measure-table tbody tr')).toHaveCount(2);
});
