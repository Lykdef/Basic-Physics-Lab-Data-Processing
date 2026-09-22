import {test,expect} from '@playwright/test';
test('清理旧本机记录与已删除项目，排除不新增历史',async({page})=>{
 await page.goto('/');await page.evaluate(()=>{const key='physical-lab.workspace.v1',s=JSON.parse(localStorage.getItem(key)!);s.deletedProjects=[s.projects[0]];s.projects[0].exclusions=[{dataset_id:'old',row_id:'old',reason:'old',at:'old',action:'exclude'}];localStorage.setItem(key,JSON.stringify(s));});await page.reload();
 for(const name of ['操作记录','已删除项目','使用指南'])await expect(page.getByRole('button',{name,exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'排除第1行',exact:true}).click();
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('physical-lab.workspace.v1')!));expect(saved.deletedProjects).toBeUndefined();expect(saved.projects[0].exclusions).toEqual([]);expect(saved.projects[0].datasets[0].rows[0].excluded).toBe(true);
 await page.getByTitle('撤销',{exact:true}).click();await expect(page.getByRole('button',{name:'排除第1行',exact:true})).toHaveCount(1);
});
