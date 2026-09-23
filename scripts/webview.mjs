import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');process.chdir(root);
const python=path.join(root,'.venv-webview/Scripts/python.exe');
if(!fs.existsSync(python)){console.error('请先创建 .venv-webview 并安装 desktop/requirements.txt。');process.exit(1);}
const target=process.argv[2]==='test'?'tests/webview_integration.py':process.argv[2]==='package'?'scripts/package-webview.py':'desktop/main.py';
const result=spawnSync(python,[target,...process.argv.slice(3)],{stdio:'inherit',windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});process.exit(result.status ?? 1);
