import {test, expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('导出当前预览为高清 PNG，支持桌面保存与取消', async ({page}) => {
  await page.goto('/');
  await page.getByRole('button', {name:'数据预览', exact:true}).click();
  await page.getByRole('checkbox', {name:'显示平均值', exact:true}).check();
  await page.getByRole('checkbox', {name:'标准差标线（x̄ ± s）', exact:true}).check();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name:'导出图像', exact:true}).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('长度的重复测量.png');
  const bytes = await readFile((await download.path())!);
  expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  expect(bytes.readUInt32BE(16)).toBe(2280);
  expect(bytes.readUInt32BE(20)).toBe(888);
  await download.saveAs('artifacts/plot-export.png');
  await page.evaluate(() => {
    (window as any).exportedImage = null;
    (window as any).labDesktop = {saveImage:async (name:string, content:string) => {
      (window as any).exportedImage = {name, content};
      return false;
    }};
  });
  await page.getByRole('button', {name:'导出图像', exact:true}).click();
  await expect.poll(() => page.evaluate(() => (window as any).exportedImage?.content?.startsWith('iVBOR'))).toBe(true);
  await expect(page.getByRole('button', {name:'导出图像', exact:true})).toBeEnabled();
});
