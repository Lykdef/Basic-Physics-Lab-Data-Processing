import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
output=root/f'release/PhysicalLab-WebView-{version}-win-x64'
if output.exists():
    raise SystemExit(f'输出目录已存在，未覆盖：{output}')
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','PhysicalLab',
               '--paths',str(root),'--distpath',str(root/'.webview-build/dist'),'--workpath',str(root/'.webview-build/work'),
               '--specpath',str(root/'.webview-build'),'--add-data',f'{root / "dist"};dist',
               '--exclude-module','matplotlib','--exclude-module','IPython','--exclude-module','pytest',
               str(root/'desktop/main.py')],cwd=root,check=True)
shutil.copytree(root/'.webview-build/dist/PhysicalLab',output)
shutil.copy2(root/'LICENSE',output/'LICENSE')
(output/'使用说明.txt').write_text('物理实验室 pywebview 版\n\n完整解压后双击 PhysicalLab.exe。\n无需安装 Python 或 Node.js。\nWindows 需已安装 Microsoft Edge WebView2 Runtime（多数 Windows 10/11 已具备）。\n项目自动保存在 %LOCALAPPDATA%\\PhysicalLab\\workspace.json。\n其他版本项目可先导出 JSON，再在本版导入。\n',encoding='utf-8')
licenses=output/'THIRD-PARTY-LICENSES'
for package in ['pywebview','pythonnet','clr_loader','numpy','scipy','sympy','mpmath','bottle','proxy_tools','cffi']:
    dist=importlib.metadata.distribution(package)
    for file in dist.files or []:
        if any(part.lower().startswith(('license','copying','copyright','notice')) for part in file.parts):
            source=Path(dist.locate_file(file))
            if source.is_file():
                target=licenses/package/str(file).replace('..','_')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,target)
for dependency in ['vue','@vue/shared','@vue/reactivity','@vue/runtime-core','@vue/runtime-dom','lucide-vue-next','zod']:
    for source in (root/'node_modules'/dependency).glob('LICENSE*'):
        target=licenses/dependency.replace('/','-')/source.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license,output/'LICENSE-Python.txt')
# Keep dotted version names intact when naming the archive.
archive=Path(str(output)+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,6) as zip:
    for file in output.rglob('*'):
        if file.is_file():
            zip.write(file,file.relative_to(output.parent))
with archive.open('rb') as stream:
    digest=hashlib.file_digest(stream,'sha256').hexdigest()
Path(str(archive)+'.sha256').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
print(f'Packaged: {archive}')
