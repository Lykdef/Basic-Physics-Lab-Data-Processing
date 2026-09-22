const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');
const compute=require('../compute/bridge.cjs');
let win;
if (process.env.PHYSICAL_LAB_TEST_DIR) app.setPath('userData', process.env.PHYSICAL_LAB_TEST_DIR);
function validateSender(event) { if (!win || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame) throw new Error('Invalid sender'); }
app.whenReady().then(() => {
  win = new BrowserWindow({ show: !process.env.PHYSICAL_LAB_TEST_DIR, width: 1500, height: 980, minWidth: 1050, minHeight: 720, title: '物理实验室 · Physical Lab', backgroundColor: '#f6f8fa', autoHideMenuBar: true, webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', e => e.preventDefault());
  win.loadFile(path.join(__dirname, '../dist/index.html'));
  ipcMain.handle('calculate', (event,payload)=>{validateSender(event);return compute.calculate(payload);});
  ipcMain.handle('project:open', async event => { validateSender(event); const result = await dialog.showOpenDialog(win, { filters: [{ name: '实验项目', extensions: ['json'] }], properties: ['openFile'] }); if (result.canceled) return null; const stat = await fs.stat(result.filePaths[0]); if (stat.size > 15_000_000) throw new Error('文件超过 15 MB'); return fs.readFile(result.filePaths[0], 'utf8'); });
  ipcMain.handle('project:save', async (event, name, content) => { validateSender(event); if (typeof content !== 'string' || content.length > 15_000_000) throw new Error('项目大小不合法'); JSON.parse(content); const result = await dialog.showSaveDialog(win, { defaultPath: `${String(name).replace(/[<>:"/\\|?*]/g, '_')}.json`, filters: [{name:'实验项目',extensions:['json']}] }); if (result.canceled || !result.filePath) return false; const temporary = `${result.filePath}.${Date.now()}.tmp`; try { await fs.writeFile(temporary, content, 'utf8'); await fs.rename(temporary, result.filePath); } catch (e) { await fs.rm(temporary, {force:true}).catch(() => {}); throw e; } return true; });
});
app.on('before-quit',()=>compute.stop());
app.on('window-all-closed', () => app.quit());
